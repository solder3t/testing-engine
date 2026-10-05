"""
engine/optimizer/strategy_optimizer.py — Parallel Grid Search & Coarse-to-Fine Strategy Optimizer.
"""

import itertools
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import config
from analytics.results_db import ResultsDB
from engine.multi_day_runner import MultiDayRunner
from strategies.base_strategy import BaseStrategy

logger = logging.getLogger("optimizer")


class StrategyOptimizer:
    """Performs parallel grid-search and coarse-to-fine optimization."""

    def __init__(
        self,
        runner: MultiDayRunner,
        results_db: Optional[ResultsDB] = None,
        n_jobs: int = 1
    ):
        self.runner = runner
        self.results_db = results_db or ResultsDB()
        self.n_jobs = n_jobs

    def estimate_grid(self, param_grid: Dict[str, List[Any]]) -> int:
        """Returns total number of parameter combinations."""
        total = 1
        for vals in param_grid.values():
            total *= max(1, len(vals))
        return total

    def _eval_single_combo(
        self,
        strategy_class: Type[BaseStrategy],
        params: Dict[str, Any],
        dates: List[str],
        symbols: Optional[List[str]],
        save_to_db: bool
    ) -> Dict[str, Any]:
        """Evaluates a single parameter combination through MultiDayRunner."""
        try:
            strat_instance = strategy_class(params=params)
            run_res = self.runner.run(
                dates=dates,
                strategy=strat_instance,
                symbols=symbols
            )
            m = run_res["metrics"]
            res = {
                "params": params,
                "strategy": strategy_class.__name__,
                "net_pnl": m["net_pnl"],
                "return_pct": m["return_pct"],
                "win_rate": m["win_rate"],
                "profit_factor": m["profit_factor"],
                "sharpe_ratio": m["sharpe_ratio"],
                "sortino_ratio": m.get("sortino_ratio", 0.0),
                "max_drawdown_pct": m["max_drawdown_pct"],
                "total_trades": m["total_trades"],
                "final_equity": run_res.get("final_equity", self.runner.capital),
                "trades": run_res.get("trades", [])
            }

            if save_to_db and self.results_db:
                inst_str = ",".join(symbols or ["DEFAULT"])
                d_start = dates[0] if dates else ""
                d_end = dates[-1] if dates else ""
                self.results_db.save_run(
                    strategy_name=strategy_class.__name__,
                    instrument=inst_str,
                    timeframe="1min",
                    start_date=d_start,
                    end_date=d_end,
                    initial_capital=self.runner.capital,
                    final_equity=res["final_equity"],
                    metrics=m,
                    params=params
                )
            return res
        except Exception as e:
            logger.error(f"Error evaluating combo {params}: {e}")
            return {
                "params": params,
                "strategy": strategy_class.__name__,
                "net_pnl": -999999.0,
                "return_pct": -100.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": -99.0,
                "sortino_ratio": -99.0,
                "max_drawdown_pct": 100.0,
                "total_trades": 0,
                "error": str(e)
            }

    def optimize(
        self,
        strategy_class: Type[BaseStrategy],
        param_grid: Dict[str, List[Any]],
        dates: List[str],
        symbols: Optional[List[str]] = None,
        rank_by: str = "sharpe_ratio",
        n_jobs: Optional[int] = None,
        save_to_db: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes parallel backtests across parameter grid combinations and ranks them.
        """
        keys = list(param_grid.keys())
        combinations = [dict(zip(keys, c)) for c in itertools.product(*[param_grid[k] for k in keys])]
        total_combos = len(combinations)
        effective_jobs = n_jobs if n_jobs is not None else self.n_jobs

        logger.info(
            f"Optimizing {strategy_class.__name__} over {total_combos} parameter combinations "
            f"(workers={effective_jobs})..."
        )
        t0 = time.time()
        results: List[Dict[str, Any]] = []

        if effective_jobs > 1 and total_combos > 1:
            workers = min(effective_jobs, 16, total_combos)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(
                        self._eval_single_combo, strategy_class, combo, dates, symbols, save_to_db
                    )
                    for combo in combinations
                ]
                for idx, fut in enumerate(futures):
                    res = fut.result()
                    results.append(res)
                    if progress_callback:
                        progress_callback(idx + 1, total_combos)
        else:
            for idx, combo in enumerate(combinations):
                res = self._eval_single_combo(strategy_class, combo, dates, symbols, save_to_db)
                results.append(res)
                if progress_callback:
                    progress_callback(idx + 1, total_combos)

        elapsed = time.time() - t0
        logger.info(f"Optimization completed in {elapsed:.2f}s ({len(results)} evaluated).")

        results.sort(key=lambda r: r.get(rank_by, -999999.0), reverse=True)
        return results

    def coarse_to_fine_optimize(
        self,
        strategy_class: Type[BaseStrategy],
        param_grid: Dict[str, List[Any]],
        dates: List[str],
        symbols: Optional[List[str]] = None,
        rank_by: str = "sharpe_ratio",
        top_k_coarse: int = 3,
        n_jobs: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Two-stage search: First evaluates coarse grid (step 2), then refines top candidates.
        """
        coarse_grid = {k: v[::2] if len(v) >= 3 else v for k, v in param_grid.items()}
        logger.info("Starting Stage 1: Coarse Grid Search...")
        coarse_results = self.optimize(
            strategy_class, coarse_grid, dates, symbols, rank_by=rank_by, n_jobs=n_jobs
        )

        top_candidates = coarse_results[:top_k_coarse]
        logger.info(f"Coarse search identified top {len(top_candidates)} candidates. Refining...")

        all_fine_results = list(coarse_results)
        evaluated_hashes = {str(r["params"]) for r in coarse_results}

        for cand in top_candidates:
            cand_params = cand["params"]
            local_grid = {}
            for k, val in cand_params.items():
                orig_vals = param_grid.get(k, [val])
                idx = orig_vals.index(val) if val in orig_vals else -1
                if idx >= 0:
                    low_idx = max(0, idx - 1)
                    high_idx = min(len(orig_vals), idx + 2)
                    local_grid[k] = orig_vals[low_idx:high_idx]
                else:
                    local_grid[k] = [val]

            keys = list(local_grid.keys())
            fine_combos = [
                dict(zip(keys, c)) for c in itertools.product(*[local_grid[k] for k in keys])
                if str(dict(zip(keys, c))) not in evaluated_hashes
            ]
            for combo in fine_combos:
                res = self._eval_single_combo(strategy_class, combo, dates, symbols, save_to_db=True)
                all_fine_results.append(res)
                evaluated_hashes.add(str(combo))

        all_fine_results.sort(key=lambda r: r.get(rank_by, -999999.0), reverse=True)
        return all_fine_results


__all__ = ["StrategyOptimizer"]
