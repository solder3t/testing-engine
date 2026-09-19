"""
analytics/factor_attribution.py — Strategy Factor Alpha Attribution & Config Exporter.

Performs factor ablation passes toggling individual Strategy v4 filters (CPR, 15m HTF,
ADX, India VIX, PCR sentiment, and Signal Scorer) to quantify marginal alpha contributions,
and generates actionable configuration presets for trading-engine (.env and JSON).
"""

import copy
import logging
from typing import List, Dict, Any, Optional, Union
import numpy as np

from data.data_loader import DataLoader
from engine.backtest_engine import BacktestEngine
from strategies.trading_engine_v4 import TradingEngineV4Strategy
from analytics.metrics import calculate_performance_metrics

logger = logging.getLogger("factor_attribution")

# The core factor switches available in TradingEngineV4Strategy
CORE_FACTORS = [
    {
        "key": "use_cpr",
        "name": "Central Pivot Range (CPR)",
        "description": "Restricts entries when price is trapped within daily pivot levels (TC-BC)",
        "ablated_value": False,
        "base_value": True,
    },
    {
        "key": "use_htf_15m",
        "name": "15-Minute Higher Timeframe (HTF)",
        "description": "Requires 15m trend (Supertrend + EMA cross) to align with 1m execution",
        "ablated_value": False,
        "base_value": True,
    },
    {
        "key": "use_adx_regime",
        "name": "ADX Trend Regime",
        "description": "Enforces ADX > 25 for trending setups vs ranging/choppy regimes",
        "ablated_value": False,
        "base_value": True,
    },
    {
        "key": "use_vix_filter",
        "name": "India VIX Volatility Gating",
        "description": "Halts option buying entries when India VIX spikes above halt threshold",
        "ablated_value": False,
        "base_value": True,
    },
    {
        "key": "use_pcr_filter",
        "name": "Options PCR Sentiment",
        "description": "Filters long trades against extreme PCR sentiment thresholds",
        "ablated_value": False,
        "base_value": True,
    },
]


class FactorAttributionEngine:
    """
    Quantifies marginal alpha and risk contributions of individual strategy factors
    via structured ablation testing, and formats actionable config exports.
    """

    def __init__(self, data_loader: Optional[DataLoader] = None):
        self.data_loader = data_loader or DataLoader()

    def run_ablation(
        self,
        date_strings: List[str],
        symbols: Optional[List[str]] = None,
        base_params: Optional[Dict[str, Any]] = None,
        capital: float = 100000.0,
    ) -> Dict[str, Any]:
        """
        Runs baseline backtest followed by single-factor ablation passes across specified dates.
        """
        if not date_strings:
            date_strings = self.data_loader.get_available_dates()[:2]

        target_symbols = symbols or ["NIFTY"]
        base_p = copy.deepcopy(base_params or {})

        # Step 1: Run Baseline
        logger.info(f"Running Baseline Factor Backtest on {len(date_strings)} sessions...")
        base_perf = self._evaluate_param_set(date_strings, target_symbols, base_p, capital)

        # Step 2: Ablation Passes
        ablation_results = []
        for factor in CORE_FACTORS:
            f_key = factor["key"]
            f_name = factor["name"]
            f_desc = factor["description"]

            # Set param to ablated value
            ablated_p = copy.deepcopy(base_p)
            ablated_p[f_key] = factor["ablated_value"]

            logger.info(f"Running Ablation Pass for Factor '{f_name}' ({f_key}={factor['ablated_value']})...")
            ablated_perf = self._evaluate_param_set(date_strings, target_symbols, ablated_p, capital)

            # Compute Deltas (Baseline minus Ablated)
            # Positive delta means factor ADDS value (baseline is better than without factor)
            d_sharpe = round(base_perf["sharpe_ratio"] - ablated_perf["sharpe_ratio"], 2)
            d_wr = round(base_perf["win_rate"] - ablated_perf["win_rate"], 1)
            d_pnl = round(base_perf["net_pnl"] - ablated_perf["net_pnl"], 2)
            d_dd = round(ablated_perf["max_drawdown_pct"] - base_perf["max_drawdown_pct"], 2) # positive means factor reduces DD
            trades_pruned = ablated_perf["total_trades"] - base_perf["total_trades"]

            # Factor rating
            if d_sharpe > 0.05 or d_wr > 2.0 or (d_pnl > 0 and d_dd > 0):
                status = "VALUE_ADD"
                action_rec = "KEEP_ENABLED"
            elif d_sharpe < -0.05 and d_wr < -2.0 and d_pnl < 0:
                status = "DRAG"
                action_rec = "CONSIDER_DISABLING"
            else:
                status = "NEUTRAL"
                action_rec = "KEEP_AS_SAFETY_GATE"

            ablation_results.append({
                "factor_key": f_key,
                "factor_name": f_name,
                "description": f_desc,
                "status": status,
                "action_recommendation": action_rec,
                "baseline_sharpe": base_perf["sharpe_ratio"],
                "ablated_sharpe": ablated_perf["sharpe_ratio"],
                "delta_sharpe": d_sharpe,
                "baseline_win_rate": base_perf["win_rate"],
                "ablated_win_rate": ablated_perf["win_rate"],
                "delta_win_rate": d_wr,
                "baseline_net_pnl": base_perf["net_pnl"],
                "ablated_net_pnl": ablated_perf["net_pnl"],
                "delta_net_pnl": d_pnl,
                "drawdown_reduction_pct": d_dd,
                "trades_filtered": trades_pruned,
            })

        # Calculate total alpha score
        value_add_count = sum(1 for r in ablation_results if r["status"] == "VALUE_ADD")
        drag_count = sum(1 for r in ablation_results if r["status"] == "DRAG")

        return {
            "sessions_evaluated": len(date_strings),
            "date_range": [date_strings[0], date_strings[-1]] if date_strings else [],
            "baseline_performance": base_perf,
            "factors": ablation_results,
            "summary": {
                "total_factors_tested": len(CORE_FACTORS),
                "value_add_factors": value_add_count,
                "drag_factors": drag_count,
                "neutral_factors": len(CORE_FACTORS) - value_add_count - drag_count,
            },
        }

    def _evaluate_param_set(
        self,
        date_strings: List[str],
        symbols: List[str],
        params: Dict[str, Any],
        capital: float,
    ) -> Dict[str, Any]:
        """Runs backtest across dates and aggregates performance metrics."""
        engine = BacktestEngine(data_loader=self.data_loader, capital=capital)
        all_trades = []

        for d in date_strings:
            try:
                st = TradingEngineV4Strategy(params=params)
                res = engine.run_session(date_str=d, strategy=st, symbols=symbols)
                all_trades.extend(res.get("trades", []))
            except Exception as e:
                logger.error(f"Error evaluating {d}: {e}")

        metrics = calculate_performance_metrics(all_trades, initial_capital=capital)
        return {
            "total_trades": metrics.get("total_trades", 0),
            "win_rate": metrics.get("win_rate", 0.0),
            "net_pnl": metrics.get("net_pnl", 0.0),
            "profit_factor": metrics.get("profit_factor", 0.0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
        }

    def export_trading_engine_config(
        self,
        ablation_results: Optional[Dict[str, Any]] = None,
        ai_analytics: Optional[Dict[str, Any]] = None,
        custom_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generates production configuration recommendations for trading-engine
        in JSON and .env format based on empirical factor and AI calibration data.
        """
        # Determine recommended factor toggles
        factor_settings = {
            "STRATEGY_USE_CPR": "true",
            "STRATEGY_USE_HTF_15M": "true",
            "STRATEGY_USE_ADX_REGIME": "true",
            "STRATEGY_USE_VIX_FILTER": "true",
            "STRATEGY_USE_PCR_FILTER": "true",
            "STRATEGY_MIN_SIGNAL_SCORE": 65,
            "STRATEGY_VIX_HALT_THRESHOLD": 24.0,
            "STRATEGY_TRAILING_SL_R": 1.0,
            "GEMINI_MIN_CONFIDENCE": 0.70,
            "GEMINI_CALL_INTERVAL_SECONDS": 20,
            "EXECUTION_MAX_SLIPPAGE_PCT": 2.5,
            "EXECUTION_MAX_LOTS": 2,
        }

        recommendations = []

        if ablation_results and "factors" in ablation_results:
            for f in ablation_results["factors"]:
                k = f["factor_key"]
                env_k = f"STRATEGY_{k.upper()}"
                if f["status"] == "DRAG":
                    factor_settings[env_k] = "false"
                    recommendations.append(
                        f"Disable {f['factor_name']} ({env_k}=false): empirical backtest shows drag of "
                        f"{abs(f['delta_sharpe'])} Sharpe ratio and {abs(f['delta_pnl'])} P&L."
                    )
                else:
                    factor_settings[env_k] = "true"
                    if f["status"] == "VALUE_ADD":
                        recommendations.append(
                            f"Keep {f['factor_name']} active ({env_k}=true): provides +{f['delta_sharpe']} Sharpe "
                            f"and pruned {f['trades_filtered']} suboptimal trades."
                        )

        if ai_analytics and "optimal_threshold" in ai_analytics:
            opt_th = ai_analytics["optimal_threshold"]
            factor_settings["GEMINI_MIN_CONFIDENCE"] = opt_th
            recommendations.append(
                f"Set GEMINI_MIN_CONFIDENCE={opt_th}: maximizes trading expectancy based on "
                f"{ai_analytics.get('total_snapshots', 0)} analyzed Gemini decisions."
            )

        if not recommendations:
            recommendations.append("Applied baseline institutional Strategy v4 parameters and risk guardrails.")

        if custom_overrides:
            factor_settings.update(custom_overrides)

        # Generate .env representation
        env_lines = [
            "# =====================================================================",
            "# Optimized Parameters Generated by testing-engine Quantitative Analysis",
            "# Copy into trading-engine/.env to apply these institutional improvements.",
            "# =====================================================================",
            "",
            "# AI Decision Gating",
            f"GEMINI_MIN_CONFIDENCE={factor_settings['GEMINI_MIN_CONFIDENCE']}",
            f"GEMINI_CALL_INTERVAL_SECONDS={factor_settings['GEMINI_CALL_INTERVAL_SECONDS']}",
            "",
            "# Multi-Factor Strategy v4 Parameters",
            f"STRATEGY_MIN_SIGNAL_SCORE={factor_settings['STRATEGY_MIN_SIGNAL_SCORE']}",
            f"STRATEGY_VIX_HALT_THRESHOLD={factor_settings['STRATEGY_VIX_HALT_THRESHOLD']}",
            f"STRATEGY_TRAILING_SL_R={factor_settings['STRATEGY_TRAILING_SL_R']}",
            f"STRATEGY_USE_CPR={factor_settings['STRATEGY_USE_CPR']}",
            f"STRATEGY_USE_HTF_15M={factor_settings['STRATEGY_USE_HTF_15M']}",
            f"STRATEGY_USE_ADX_REGIME={factor_settings['STRATEGY_USE_ADX_REGIME']}",
            f"STRATEGY_USE_VIX_FILTER={factor_settings['STRATEGY_USE_VIX_FILTER']}",
            f"STRATEGY_USE_PCR_FILTER={factor_settings['STRATEGY_USE_PCR_FILTER']}",
            "",
            "# Execution & Risk Guardrails",
            f"EXECUTION_MAX_SLIPPAGE_PCT={factor_settings['EXECUTION_MAX_SLIPPAGE_PCT']}",
            f"EXECUTION_MAX_LOTS={factor_settings['EXECUTION_MAX_LOTS']}",
        ]
        env_string = "\n".join(env_lines)

        return {
            "config_json": factor_settings,
            "env_content": env_string,
            "recommendations": recommendations,
        }
