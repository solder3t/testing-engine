"""
engine/optimizer.py — Grid Search Parameter Optimizer for Strategies.
"""

from typing import List, Dict, Any, Type
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
