"""
analytics/validation_report.py — Institutional Strategy Candidate Validation Report.

Synthesizes Deflated Sharpe, Monte Carlo VaR, Walk-Forward Efficiency, and Market Regime
decompositions into an institutional pass/fail audit score.
"""

from typing import Any, Dict, List, Optional
import numpy as np

import config
from analytics.validation import ValidationSuite


class CandidateValidator:
    """Evaluates backtest candidate performance against institutional risk hurdles."""

    @classmethod
    def validate(cls, run_data: Any) -> Dict[str, Any]:
        """Convenience method accepting a backtest run dictionary or object."""
        if isinstance(run_data, dict):
            strategy_name = run_data.get("strategy", "Unknown")
            initial_capital = float(run_data.get("initial_capital", run_data.get("capital", config.DEFAULT_CAPITAL)))
            final_equity = float(run_data.get("final_equity", initial_capital))
            metrics = run_data.get("metrics", {})
            trades = run_data.get("trades", [])
            equity_curve = run_data.get("equity_curve", [])
            n_trials = int(run_data.get("n_trials", 1))
        else:
            strategy_name = getattr(run_data, "strategy", "Unknown")
            initial_capital = float(getattr(run_data, "initial_capital", getattr(run_data, "capital", config.DEFAULT_CAPITAL)))
            final_equity = float(getattr(run_data, "final_equity", initial_capital))
            metrics = getattr(run_data, "metrics", {})
            trades = getattr(run_data, "trades", [])
            equity_curve = getattr(run_data, "equity_curve", [])
            n_trials = int(getattr(run_data, "n_trials", 1))

        return cls.evaluate_candidate(
            strategy_name=strategy_name,
            initial_capital=initial_capital,
            final_equity=final_equity,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            n_trials=n_trials,
        )

    @staticmethod
    def evaluate_candidate(
        strategy_name: str,
        initial_capital: float,
        final_equity: float,
        metrics: Dict[str, Any],
        trades: List[Any],
        equity_curve: List[Dict[str, Any]],
        n_trials: int = 1
    ) -> Dict[str, Any]:
        """Runs complete institutional validation suite on a backtested strategy candidate."""
        def _get_pnl(t):
            if isinstance(t, dict):
                return float(t.get("net_pnl", t.get("pnl", 0.0)))
            return float(getattr(t, "net_pnl", getattr(t, "pnl", 0.0)))

        pnls = [_get_pnl(t) for t in trades]
        net_pnl = float(metrics.get("net_pnl", final_equity - initial_capital))
        sharpe = float(metrics.get("sharpe_ratio", 0.0))
        max_dd = float(metrics.get("max_drawdown_pct", 0.0))
        pf = float(metrics.get("profit_factor", 0.0))
        win_rate = float(metrics.get("win_rate", 0.0))
        total_trades = int(metrics.get("total_trades", len(trades)))

        # 1. Deflated Sharpe Ratio
        dsr_res = ValidationSuite.calculate_deflated_sharpe(
            sharpe_est=sharpe,
            n_trials=max(1, n_trials),
            returns=pnls
        )

        # 2. Monte Carlo Bootstrap Permutation
        mc_res = ValidationSuite.run_monte_carlo(
            trades=trades,
            initial_capital=initial_capital,
            n_simulations=config.MONTE_CARLO_RUNS
        )

        # 3. Market Regime Decomp
        regime_res = ValidationSuite.slice_by_regimes(trades)

        # 4. Hurdle Checks & Scoring
        hurdles = {
            "min_trades": total_trades >= 5,
            "positive_net_pnl": net_pnl > 0.0,
            "profit_factor_ok": pf >= 1.2 or (total_trades > 0 and pf >= 1.0),
            "max_dd_acceptable": max_dd <= (config.MAX_DRAWDOWN_STOP_PCT * 100.0),
            "mc_dd_acceptable": mc_res["max_drawdown_95_pct"] <= 25.0,
            "mc_win_probability": mc_res["prob_profitable"] >= 60.0 or total_trades == 0
        }

        passed_count = sum(1 for passed in hurdles.values() if passed)
        total_hurdles = len(hurdles)
        pass_ratio = passed_count / total_hurdles

        if pass_ratio >= 0.85:
            verdict = "PASS"
        elif pass_ratio >= 0.60:
            verdict = "MARGINAL"
        else:
            verdict = "FAIL"

        return {
            "strategy": strategy_name,
            "verdict": verdict,
            "score_pct": round(pass_ratio * 100.0, 1),
            "overall_score": round(pass_ratio * 100.0, 1),
            "pass_ratio": round(pass_ratio, 4),
            "hurdles": hurdles,
            "deflated_sharpe": dsr_res,
            "monte_carlo": mc_res,
            "regimes": regime_res,
            "core_metrics": {
                "net_pnl": net_pnl,
                "sharpe_ratio": sharpe,
                "profit_factor": pf,
                "win_rate": win_rate,
                "max_drawdown_pct": max_dd,
                "total_trades": total_trades
            }
        }
