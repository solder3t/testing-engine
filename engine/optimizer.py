"""
engine/optimizer.py — Grid Search Parameter Optimizer for Strategies.
"""

from typing import List, Dict, Any, Type, Optional
import itertools
import logging

from strategies.base_strategy import BaseStrategy
from engine.multi_day_runner import MultiDayRunner

logger = logging.getLogger("optimizer")


class StrategyOptimizer:
    """Performs grid-search optimization across strategy parameter combinations."""

    def __init__(self, runner: MultiDayRunner):
        self.runner = runner

    def optimize(
        self,
        strategy_class: Type[BaseStrategy],
        param_grid: Dict[str, List[Any]],
        dates: List[str],
        symbols: Optional[List[str]] = None,
        rank_by: str = "sharpe_ratio"
    ) -> List[Dict[str, Any]]:
        """
        Executes backtests across parameter grid combinations and ranks them.
        """
        keys = list(param_grid.keys())
        combinations = list(itertools.product(*[param_grid[k] for k in keys]))
        results = []

        logger.info(f"Optimizing {strategy_class.__name__} over {len(combinations)} parameter sets...")

        for combo in combinations:
            params = dict(zip(keys, combo))
            strat_instance = strategy_class(params=params)

            run_res = self.runner.run(
                dates=dates,
                strategy=strat_instance,
                symbols=symbols
            )

            m = run_res["metrics"]
            results.append({
                "params": params,
                "net_pnl": m["net_pnl"],
                "return_pct": m["return_pct"],
                "win_rate": m["win_rate"],
                "profit_factor": m["profit_factor"],
                "sharpe_ratio": m["sharpe_ratio"],
                "max_drawdown_pct": m["max_drawdown_pct"],
                "total_trades": m["total_trades"]
            })

        # Rank combinations
        results.sort(key=lambda r: r.get(rank_by, 0.0), reverse=True)
        return results

    def stream_optimize(
        self,
        strategy_class: Type[BaseStrategy],
        param_grid: Dict[str, List[Any]],
        dates: List[str],
        symbols: Optional[List[str]] = None,
        rank_by: str = "sharpe_ratio"
    ):
        """
        Generator version of optimize(). Yields progress events as combinations are evaluated,
        then yields a final 'complete' dict with sorted ranked combinations.
        """
        keys = list(param_grid.keys())
        combinations = list(itertools.product(*[param_grid[k] for k in keys]))
        total = len(combinations)
        results = []

        logger.info(f"[stream_optimize] Optimizing {strategy_class.__name__} over {total} parameter sets...")

        for idx, combo in enumerate(combinations, start=1):
            params = dict(zip(keys, combo))
            strat_instance = strategy_class(params=params)

            run_res = self.runner.run(
                dates=dates,
                strategy=strat_instance,
                symbols=symbols
            )

            m = run_res["metrics"]
            res_item = {
                "params": params,
                "net_pnl": m["net_pnl"],
                "return_pct": m["return_pct"],
                "win_rate": m["win_rate"],
                "profit_factor": m["profit_factor"],
                "sharpe_ratio": m["sharpe_ratio"],
                "max_drawdown_pct": m["max_drawdown_pct"],
                "total_trades": m["total_trades"]
            }
            results.append(res_item)

            yield {
                "type": "progress",
                "current": idx,
                "total": total,
                "params": params,
                "net_pnl": round(float(m["net_pnl"]), 2),
                "sharpe_ratio": round(float(m["sharpe_ratio"]), 2)
            }

        results.sort(key=lambda r: r.get(rank_by, 0.0), reverse=True)
        yield {
            "type": "complete",
            "strategy": strategy_class.__name__,
            "rank_by": rank_by,
            "total_combinations": int(len(results)),
            "best_params": results[0]["params"] if results else {},
            "ranked_results": results[:50]
        }

