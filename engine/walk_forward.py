"""
engine/walk_forward.py — Institutional Walk-Forward Optimization (WFO) Engine.

Evaluates strategy robustness and prevents curve-fitting / overfitting by:
1. Splitting historical session dates into rolling or anchored in-sample (training) and out-of-sample (testing) windows.
2. Optimizing parameters on in-sample data.
3. Executing the chosen parameter set on unseen out-of-sample data.
4. Aggregating out-of-sample returns to compute the Walk-Forward Efficiency (WFE) ratio.
"""

import os
import sys
from typing import List, Dict, Any, Type, Optional
import logging
import numpy as np

# Ensure testing-engine root is on sys.path
_ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ENGINE_ROOT not in sys.path:
    sys.path.insert(0, _ENGINE_ROOT)

import config
from analytics.metrics import calculate_performance_metrics
from analytics.results_db import ResultsDB
from analytics.validation import ValidationSuite
from engine.multi_day_runner import MultiDayRunner
from engine.optimizer import StrategyOptimizer
from strategies.base_strategy import BaseStrategy

logger = logging.getLogger("walk_forward")


class WalkForwardOptimizer:
    """Executes rolling and anchored Walk-Forward Analysis across multiple market sessions."""

    def __init__(
        self,
        runner: MultiDayRunner,
        in_sample_len: int = 3,
        out_of_sample_len: int = 1,
        anchored: bool = False,
        results_db: Optional[ResultsDB] = None,
        **kwargs
    ):
        self.runner = runner
        
        # Support n_splits / train_ratio if passed
        if "n_splits" in kwargs:
            splits = int(kwargs["n_splits"])
            ratio = float(kwargs.get("train_ratio", 0.7))
            self.in_sample_len = max(1, int(round(splits * ratio)))
            self.out_of_sample_len = max(1, splits - self.in_sample_len)
        else:
            self.in_sample_len = in_sample_len
            self.out_of_sample_len = out_of_sample_len

        self.anchored = anchored
        self.results_db = results_db or ResultsDB()
        self.optimizer = StrategyOptimizer(runner=self.runner, results_db=self.results_db)


    def generate_windows(self, dates: List[str]) -> List[Dict[str, List[str]]]:
        """Splits sorted dates into (in_sample, out_of_sample) windows."""
        sorted_dates = sorted(dates)
        total_window = self.in_sample_len + self.out_of_sample_len
        if len(sorted_dates) < total_window:
            raise ValueError(
                f"Need at least {total_window} dates for WFO (in_sample={self.in_sample_len}, "
                f"out_of_sample={self.out_of_sample_len}), got {len(sorted_dates)}"
            )

        windows = []
        start = 0
        while start + total_window <= len(sorted_dates):
            is_start = 0 if self.anchored else start
            is_dates = sorted_dates[is_start : start + self.in_sample_len]
            oos_dates = sorted_dates[start + self.in_sample_len : start + total_window]
            windows.append({
                "window_index": len(windows) + 1,
                "in_sample": is_dates,
                "out_of_sample": oos_dates
            })
            start += self.out_of_sample_len

        return windows

    def run_walk_forward(
        self,
        strategy_class: Type[BaseStrategy],
        param_grid: Dict[str, List[Any]],
        dates: List[str],
        symbols: Optional[List[str]] = None,
        rank_by: str = "sharpe_ratio",
        n_jobs: int = 1
    ) -> Dict[str, Any]:
        """
        Executes walk-forward optimization and evaluates out-of-sample efficiency.
        """
        windows = self.generate_windows(dates)
        window_results = []
        all_oos_trades = []
        all_oos_equity_curves = []

        is_sharpes = []
        oos_sharpes = []
        is_annualized_returns = []
        oos_annualized_returns = []

        for win in windows:
            w_idx = win["window_index"]
            is_dates = win["in_sample"]
            oos_dates = win["out_of_sample"]

            logger.info(f"[WFO Window {w_idx}] In-Sample optimization on {is_dates}...")
            ranked_params = self.optimizer.optimize(
                strategy_class=strategy_class,
                param_grid=param_grid,
                dates=is_dates,
                symbols=symbols,
                rank_by=rank_by,
                n_jobs=n_jobs,
                save_to_db=False
            )

            best_param_set = ranked_params[0]["params"] if ranked_params else {}
            best_is_metric = ranked_params[0] if ranked_params else {}
            is_sharpes.append(best_is_metric.get("sharpe_ratio", 0.0))
            is_annualized_returns.append(best_is_metric.get("return_pct", 0.0))

            logger.info(f"[WFO Window {w_idx}] Out-of-Sample evaluation on {oos_dates} with {best_param_set}...")
            strat_oos = strategy_class(params=best_param_set)
            oos_run = self.runner.run(
                dates=oos_dates,
                strategy=strat_oos,
                symbols=symbols
            )

            m_oos = oos_run["metrics"]
            oos_sharpes.append(m_oos.get("sharpe_ratio", 0.0))
            oos_annualized_returns.append(m_oos.get("return_pct", 0.0))
            all_oos_trades.extend(oos_run["trades"])
            all_oos_equity_curves.extend(oos_run["equity_curve"])

            window_results.append({
                "window": w_idx,
                "in_sample_dates": is_dates,
                "out_of_sample_dates": oos_dates,
                "best_params": best_param_set,
                "in_sample_metrics": {
                    "net_pnl": best_is_metric.get("net_pnl", 0.0),
                    "return_pct": best_is_metric.get("return_pct", 0.0),
                    "sharpe_ratio": best_is_metric.get("sharpe_ratio", 0.0),
                    "win_rate": best_is_metric.get("win_rate", 0.0)
                },
                "out_of_sample_metrics": {
                    "net_pnl": m_oos.get("net_pnl", 0.0),
                    "return_pct": m_oos.get("return_pct", 0.0),
                    "sharpe_ratio": m_oos.get("sharpe_ratio", 0.0),
                    "win_rate": m_oos.get("win_rate", 0.0),
                    "total_trades": m_oos.get("total_trades", 0)
                }
            })

        overall_oos_metrics = calculate_performance_metrics(
            trades=all_oos_trades,
            initial_capital=self.runner.capital,
            equity_curve=all_oos_equity_curves
        )

        avg_is_sharpe = float(np.mean(is_sharpes)) if is_sharpes else 0.0
        avg_oos_sharpe = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
        
        # WFE ratio based on Sharpe (or returns if Sharpe is non-positive)
        if avg_is_sharpe > 0.01:
            wfe = max(0.0, avg_oos_sharpe / avg_is_sharpe)
        else:
            avg_is_ret = float(np.mean(is_annualized_returns)) if is_annualized_returns else 0.0
            avg_oos_ret = float(np.mean(oos_annualized_returns)) if oos_annualized_returns else 0.0
            wfe = max(0.0, avg_oos_ret / avg_is_ret) if avg_is_ret > 0.01 else 0.0

        is_robust = (wfe >= config.WFE_HURDLE and overall_oos_metrics.get("net_pnl", 0.0) > 0.0)

        # Run Monte Carlo on OOS trades
        mc_results = ValidationSuite.run_monte_carlo(
            trades=all_oos_trades,
            initial_capital=self.runner.capital,
            n_simulations=config.MONTE_CARLO_RUNS
        )

        psi_data = self._compute_parameter_stability_index(window_results)

        return {
            "strategy": strategy_class.__name__,
            "total_windows": len(windows),
            "walk_forward_efficiency": round(wfe, 4),
            "wfe_score": round(wfe, 4),
            "wfe_hurdle": config.WFE_HURDLE,
            "parameter_stability_index": psi_data,
            "psi": psi_data,
            "verdict": "PASS" if is_robust else "FAIL",
            "is_robust": is_robust,
            "avg_in_sample_sharpe": round(avg_is_sharpe, 4),
            "avg_out_of_sample_sharpe": round(avg_oos_sharpe, 4),
            "overall_oos_metrics": overall_oos_metrics,
            "monte_carlo_oos": mc_results,
            "window_details": window_results,
            "windows": window_results
        }

    @staticmethod
    def _compute_parameter_stability_index(window_results: List[Dict]) -> Dict[str, Any]:
        """
        Normalized coefficient of variation (CV) for each parameter across windows.
        Lower CV = more stable. Overall PSI < 0.25 is considered stable.
        """
        if not window_results:
            return {"per_param": {}, "overall_psi": 0.0, "is_stable": True}

        all_params = [w.get("best_params", {}) for w in window_results]
        first = all_params[0] if all_params else {}
        numeric_params = {
            k: [] for k, v in first.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }

        for params in all_params:
            for k in numeric_params:
                if k in params:
                    numeric_params[k].append(float(params[k]))

        psi = {}
        for k, vals in numeric_params.items():
            if len(vals) > 1:
                mean = float(np.mean(vals))
                std = float(np.std(vals))
                psi[k] = round(std / mean, 4) if abs(mean) > 1e-9 else 0.0
            else:
                psi[k] = 0.0

        overall_psi = round(float(np.mean(list(psi.values()))), 4) if psi else 0.0
        return {
            "per_param": psi,
            "overall_psi": overall_psi,
            "is_stable": bool(overall_psi < 0.25)
        }

    # Alias for convenience
    run = run_walk_forward

