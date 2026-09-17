"""
engine/walk_forward.py — Institutional Walk-Forward Optimization (WFO) Engine.

Evaluates strategy robustness and prevents curve-fitting / overfitting by:
1. Splitting historical session dates into rolling in-sample (training) and out-of-sample (forward testing) windows.
2. Optimizing parameters on in-sample data.
3. Executing the chosen parameter set on unseen out-of-sample data.
4. Aggregating out-of-sample returns to compute the Walk-Forward Efficiency (WFE) ratio.
"""

from typing import List, Dict, Any, Type, Optional
import logging

from strategies.base_strategy import BaseStrategy
from engine.multi_day_runner import MultiDayRunner
from engine.optimizer import StrategyOptimizer
from analytics.metrics import calculate_performance_metrics

logger = logging.getLogger("walk_forward")


class WalkForwardOptimizer:
    """
    Executes rolling Walk-Forward Analysis across multiple market sessions.
    """

    def __init__(
        self,
        runner: MultiDayRunner,
        in_sample_len: int = 3,
        out_of_sample_len: int = 1
    ):
        self.runner = runner
        self.in_sample_len = in_sample_len
        self.out_of_sample_len = out_of_sample_len
        self.optimizer = StrategyOptimizer(runner=self.runner)

    def generate_windows(self, dates: List[str]) -> List[Dict[str, List[str]]]:
        """
        Splits sorted dates into rolling (in_sample, out_of_sample) windows.
        """
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
            is_dates = sorted_dates[start : start + self.in_sample_len]
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
        rank_by: str = "sharpe_ratio"
    ) -> Dict[str, Any]:
        """
        Executes rolling walk-forward optimization and evaluates out-of-sample efficiency.
        """
        windows = self.generate_windows(dates)
        window_results = []
        all_oos_trades = []
        all_oos_equity_curves = []

        is_sharpes = []
        oos_sharpes = []

        for win in windows:
            w_idx = win["window_index"]
            is_dates = win["in_sample"]
            oos_dates = win["out_of_sample"]

            logger.info(f"[WFO Window {w_idx}] In-Sample optimization on {is_dates}...")
            # 1. Optimize on in-sample
            ranked_params = self.optimizer.optimize(
                strategy_class=strategy_class,
                param_grid=param_grid,
                dates=is_dates,
                symbols=symbols,
                rank_by=rank_by
            )

            best_param_set = ranked_params[0]["params"] if ranked_params else {}
            best_is_metric = ranked_params[0] if ranked_params else {}
            is_sharpes.append(best_is_metric.get("sharpe_ratio", 0.0))

            # 2. Forward-test on out-of-sample
            logger.info(f"[WFO Window {w_idx}] Out-of-Sample evaluation on {oos_dates} with {best_param_set}...")
            strat_oos = strategy_class(params=best_param_set)
            oos_run = self.runner.run(
                dates=oos_dates,
                strategy=strat_oos,
                symbols=symbols
            )

            m_oos = oos_run["metrics"]
            oos_sharpes.append(m_oos.get("sharpe_ratio", 0.0))
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

        avg_is_sharpe = float(sum(is_sharpes) / len(is_sharpes)) if is_sharpes else 0.0
        avg_oos_sharpe = float(sum(oos_sharpes) / len(oos_sharpes)) if oos_sharpes else 0.0
        wfe_ratio = round(float(avg_oos_sharpe / avg_is_sharpe), 2) if avg_is_sharpe > 0 else 0.0

        return {
            "strategy": strategy_class.__name__,
            "total_windows": int(len(windows)),
            "walk_forward_efficiency": float(wfe_ratio),
            "is_robust": bool(wfe_ratio >= 0.5),
            "overall_oos_metrics": overall_oos_metrics,
            "windows": window_results,
            "out_of_sample_trades": all_oos_trades,
            "out_of_sample_equity_curve": all_oos_equity_curves
        }
