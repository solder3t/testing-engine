"""
engine/optimizer/executor.py — High-Throughput Strategy Parameter Sweep & Optimization Executor.
"""

import logging
import queue
import time
import uuid
import sys
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from data.data_loader import DataLoader
from engine.multi_day_runner import MultiDayRunner
from engine.shared_memory import SharedBarCache
from engine.bayesian_tpe import BayesianTpeOptimizer
from engine.param_grids import STRATEGY_REGISTRY, get_default_param_grid, get_strategy_class
from .sampling import _grid_sample, _random_sample, _latin_hypercube_sample, _sobol_sample
from .job_tracker import HyperJob

logger = logging.getLogger("mass_optimizer")

# Set start method safely on Windows if not already initialized
if sys.platform == "win32":
    try:
        multiprocessing.set_start_method("spawn", force=False)
    except (RuntimeError, ValueError):
        pass


def _rank_key_func(obj_metric: str) -> Callable[[Dict[str, Any]], Tuple[float, float]]:
    """Returns sorting key lambda based on user-selected objective metric."""
    m = str(obj_metric or "sharpe_ratio").lower().strip()
    if m in ("sharpe", "sharpe_ratio"):
        return lambda x: (float(x.get("sharpe_ratio", 0.0)), float(x.get("pnl_net", 0.0)))
    elif m in ("profit_factor", "pf"):
        return lambda x: (float(x.get("profit_factor", 0.0)), float(x.get("sharpe_ratio", 0.0)))
    elif m in ("win_rate", "win_rate_pct"):
        return lambda x: (float(x.get("win_rate_pct", 0.0)), float(x.get("pnl_net", 0.0)))
    elif m in ("max_drawdown", "max_drawdown_pct", "min_drawdown"):
        return lambda x: (-abs(float(x.get("max_drawdown_pct", 100.0))), float(x.get("pnl_net", 0.0)))
    else:  # default or net pnl
        return lambda x: (float(x.get("pnl_net", 0.0)), float(x.get("sharpe_ratio", 0.0)))


def _compute_tpe_score(res: Dict[str, Any], obj_metric: str) -> float:
    """Computes single scalar score for Bayesian TPE optimization feedback."""
    m = str(obj_metric or "sharpe_ratio").lower().strip()
    if m in ("pnl", "pnl_net", "net_pnl"):
        return float(res.get("pnl_net", 0.0))
    elif m in ("profit_factor", "pf"):
        return float(res.get("profit_factor", 0.0))
    elif m in ("win_rate", "win_rate_pct"):
        return float(res.get("win_rate_pct", 0.0))
    elif m in ("max_drawdown", "max_drawdown_pct", "min_drawdown"):
        return -abs(float(res.get("max_drawdown_pct", 100.0)))
    else:
        s = float(res.get("sharpe_ratio", 0.0))
        if s == 0.0 and res.get("pnl_net", 0.0) != 0.0:
            s = float(res.get("pnl_net", 0.0)) / 1000.0
        return s


def _execute_single_run_worker(args: tuple) -> Dict[str, Any]:
    """
    Module-level picklable worker function for multiprocessing.
    args: (run_id, instrument, dates, strat_key, param_combo, spec, source_dir)
    """
    run_id, instrument, dates, strat_key, param_combo, spec, source_dir = args
    t0 = time.perf_counter()
    sym = instrument.get("symbol", "NIFTY")
    disp = instrument.get("display_name", sym)

    try:
        strat_cls = get_strategy_class(strat_key)
        strat_inst = strat_cls(params=param_combo)
    except Exception:
        strat_cls = get_strategy_class(strat_key)
        strat_inst = strat_cls()
        if hasattr(strat_inst, "current_params"):
            strat_inst.current_params.update(param_combo)

    runner = MultiDayRunner(
        capital=float(spec.get("capital", 100000.0)),
        risk_pct=float(spec.get("risk_pct", 0.01)),
        compound_capital=False,
        source_dir=source_dir,
        parallel=False
    )

    try:
        res = runner.run(dates=dates, strategy=strat_inst, symbols=[sym])
        m = res.get("metrics", {})
        trades = res.get("closed_trades", [])

        pnl_net = float(m.get("total_net_pnl", 0.0))
        pnl_gross = float(m.get("total_gross_pnl", 0.0))
        charges = float(m.get("total_charges", 0.0))
        win_rate = float(m.get("win_rate", 0.0))
        sharpe = float(m.get("sharpe_ratio", 0.0))
        max_dd = float(m.get("max_drawdown_pct", 0.0))
        profit_factor = float(m.get("profit_factor", 0.0))

        return {
            "run_id": run_id,
            "instrument": disp,
            "symbol": sym,
            "parameters": param_combo,
            "dates_tested": dates,
            "total_trades": len(trades),
            "wins": m.get("wins", 0),
            "losses": m.get("losses", 0),
            "win_rate_pct": win_rate,
            "pnl_net": pnl_net,
            "pnl_gross": pnl_gross,
            "charges": charges,
            "sharpe_ratio": sharpe,
            "profit_factor": profit_factor,
            "max_drawdown_pct": max_dd,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
            "metrics": m
        }
    except Exception as exc:
        return {
            "run_id": run_id,
            "instrument": disp,
            "symbol": sym,
            "parameters": param_combo,
            "dates_tested": dates,
            "error": str(exc),
            "pnl_net": 0.0,
            "win_rate_pct": 0.0,
            "sharpe_ratio": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "total_trades": 0,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        }


def _run_batch_with_pool(specs: List[tuple], workers: int, use_processes: bool = True) -> List[Dict[str, Any]]:
    """Runs a batch of work specs across ProcessPoolExecutor with graceful ThreadPoolExecutor fallback."""
    if use_processes and workers > 1:
        try:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_execute_single_run_worker, s) for s in specs]
                return [f.result() for f in as_completed(futures)]
        except Exception:
            pass  # Fallback to ThreadPoolExecutor if process spawning encounters environment/mock constraints
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_execute_single_run_worker, s) for s in specs]
        return [f.result() for f in as_completed(futures)]


class MassOptimizer:
    """Next-Gen High-Throughput Strategy Parameter Sweep & Optimizer."""

    _jobs: Dict[str, HyperJob] = {}

    def __init__(
        self,
        data_loader: Optional[DataLoader] = None,
        source_dir: Optional[str] = None,
        max_workers: int = 4
    ):
        self.source_dir = source_dir
        self.data_loader = data_loader or DataLoader(source_dir=source_dir)
        self.max_workers = max_workers
        self.bar_cache = SharedBarCache.get_global_instance()

    @staticmethod
    def build_param_axes(parameter_grid: Dict[str, Any]) -> Dict[str, List[Any]]:
        """Parses parameter grid into discrete axes."""
        axes: Dict[str, List[Any]] = {}
        for k, v in parameter_grid.items():
            if isinstance(v, list):
                axes[k] = v
            elif isinstance(v, dict) and "min" in v and "max" in v:
                step = v.get("step", 1)
                lo, hi = v["min"], v["max"]
                vals = []
                cur = lo
                while cur <= hi + 1e-9:
                    vals.append(round(cur, 6) if isinstance(step, float) else int(round(cur)))
                    cur += step
                axes[k] = vals if vals else [lo]
            else:
                axes[k] = [v]
        return axes

    @classmethod
    def get_job(cls, job_id: str) -> Optional[HyperJob]:
        return cls._jobs.get(job_id)

    @classmethod
    def list_jobs(cls) -> List[Dict[str, Any]]:
        return [j.to_status_dict() for j in cls._jobs.values()]

    @classmethod
    def cancel_job(cls, job_id: str) -> bool:
        job = cls._jobs.get(job_id)
        if job and job.status == "RUNNING":
            job.status = "CANCELLED"
            return True
        return False

    def submit_job(self, spec: Dict[str, Any]) -> HyperJob:
        """Kicks off a mass optimization job in a background daemon thread."""
        job_id = str(uuid.uuid4())[:12]
        instruments = spec.get("instruments", [{"asset_type": "INDEX", "symbol": "NIFTY"}])

        # Auto-expand strikes if options requested
        expanded_instruments = []
        for inst in instruments:
            asset_t = str(inst.get("asset_type", "INDEX")).upper()
            trade_as = str(inst.get("trade_as", "SPOT")).upper()
            sym = inst.get("symbol", "NIFTY")
            exp_mode = inst.get("expiry_mode", "NEAREST")

            if asset_t == "INDEX" and trade_as == "OPTION":
                itm_count = int(inst.get("itm_count", 2))
                otm_count = int(inst.get("otm_count", 2))
                inc_atm = bool(inst.get("include_atm", True))

                strike_modes = []
                for k in range(itm_count, 0, -1):
                    strike_modes.append((f"ITM{k}", f"ITM {k}"))
                if inc_atm:
                    strike_modes.append(("ATM", "ATM"))
                for k in range(1, otm_count + 1):
                    strike_modes.append((f"OTM{k}", f"OTM {k}"))

                for sm_key, sm_label in strike_modes:
                    expanded_instruments.append({
                        "asset_type": "INDEX",
                        "symbol": sym,
                        "display_name": f"{sym} OPT {sm_label} ({exp_mode})",
                        "strike_mode": sm_key,
                        "expiry_mode": exp_mode
                    })
            else:
                expanded_instruments.append(inst)

        instruments = expanded_instruments
        dates = spec.get("dates", [])
        strat_key = str(spec.get("strategy_type", "supertrend")).lower()
        param_grid_raw = spec.get("parameter_grid") or get_default_param_grid(strat_key)
        sampling_mode = str(spec.get("sampling_mode", "GRID")).upper()
        max_iterations = int(spec.get("max_iterations", 100))
        workers = int(spec.get("max_workers", self.max_workers))
        seed = int(spec.get("seed", 42))
        early_pruning = bool(spec.get("early_pruning", False))

        param_axes = self.build_param_axes(param_grid_raw)

        # Closed-loop Bayesian TPE
        if sampling_mode == "BAYESIAN_TPE":
            warmup_count = min(10, max(2, max_iterations // 2))
            tpe = BayesianTpeOptimizer(param_axes, warmup_trials=warmup_count, seed=seed)
            total = len(instruments) * max_iterations
            job = HyperJob(job_id=job_id, total=total)
            MassOptimizer._jobs[job_id] = job

            import threading
            t = threading.Thread(
                target=self._run_tpe_job_thread,
                args=(job, tpe, instruments, dates, strat_key, param_axes, max_iterations, workers, spec),
                daemon=True
            )
            t.start()
            return job

        # Sampling dispatch for non-TPE modes
        if sampling_mode == "RANDOM":
            param_combos = _random_sample(param_axes, max_iterations, seed=seed)
        elif sampling_mode == "LHS":
            param_combos = _latin_hypercube_sample(param_axes, max_iterations, seed=seed)
        elif sampling_mode == "SOBOL":
            param_combos = _sobol_sample(param_axes, max_iterations, seed=seed)
        else:
            param_combos = _grid_sample(param_axes, max_iterations)

        # Build run specs
        run_specs = []
        run_id = 0
        for inst in instruments:
            for combo in param_combos:
                run_specs.append((run_id, inst, dates, strat_key, combo, spec, self.source_dir))
                run_id += 1

        total = len(run_specs)
        job = HyperJob(job_id=job_id, total=total)
        MassOptimizer._jobs[job_id] = job

        import threading
        t = threading.Thread(
            target=self._run_job_thread,
            args=(job, run_specs, workers, early_pruning, spec),
            daemon=True
        )
        t.start()
        return job

    def _execute_single_run(
        self,
        run_id: int,
        instrument: Dict[str, Any],
        dates: List[str],
        strat_key: str,
        param_combo: Dict[str, Any],
        spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Runs backtest across dates for a single instrument and parameter combo."""
        return _execute_single_run_worker(
            (run_id, instrument, dates, strat_key, param_combo, spec, self.source_dir)
        )

    def _run_tpe_job_thread(
        self,
        job: HyperJob,
        tpe: BayesianTpeOptimizer,
        instruments: List[Dict[str, Any]],
        dates: List[str],
        strat_key: str,
        param_axes: Dict[str, List[Any]],
        max_iterations: int,
        workers: int,
        original_spec: Dict[str, Any]
    ) -> None:
        """Active closed-loop Bayesian TPE feedback runner."""
        all_results: List[Dict[str, Any]] = []
        wall_start = time.perf_counter()
        run_id = 0
        BATCH_SIZE = min(8, max(2, workers * 2))

        try:
            for inst in instruments:
                completed_for_inst = 0
                while completed_for_inst < max_iterations:
                    batch_n = min(BATCH_SIZE, max_iterations - completed_for_inst)
                    combos = tpe.suggest(batch_n)
                    batch_specs = [
                        (run_id + i, inst, dates, strat_key, c, original_spec, self.source_dir)
                        for i, c in enumerate(combos)
                    ]
                    run_id += len(combos)

                    batch_results = _run_batch_with_pool(batch_specs, workers)

                    tpe_feedback = []
                    target_obj = original_spec.get("objective_metric") or original_spec.get("rank_by", "sharpe_ratio")
                    for res in batch_results:
                        all_results.append(res)
                        job.completed += 1
                        score = _compute_tpe_score(res, target_obj)
                        tpe_feedback.append((res.get("parameters", {}), score))

                        try:
                            job.progress_queue.put_nowait({
                                "type": "progress",
                                "stage": "Bayesian Guided Search",
                                "completed": job.completed,
                                "total": job.total,
                                "pct": job.pct_complete,
                                "eta_sec": job.eta_sec,
                                "last_run": res
                            })
                        except queue.Full:
                            pass

                    tpe.tell_batch(tpe_feedback)
                    completed_for_inst += len(batch_results)

        except Exception as exc:
            job.status = "ERROR"
            job.error = str(exc)
            job.finished_at = time.time()
            try:
                job.progress_queue.put_nowait({"type": "error", "error": str(exc)})
            except queue.Full:
                pass
            return

        wall_ms = round((time.perf_counter() - wall_start) * 1000, 2)
        valid = [r for r in all_results if "error" not in r]
        errored = [r for r in all_results if "error" in r]
        target_obj = original_spec.get("objective_metric") or original_spec.get("rank_by", "sharpe_ratio")
        valid.sort(key=_rank_key_func(target_obj), reverse=True)

        job.results = {
            "job_id": job.job_id,
            "strategy_type": original_spec.get("strategy_type", ""),
            "sampling_mode": "BAYESIAN_TPE",
            "total_runs": len(all_results),
            "valid_runs": len(valid),
            "errored_runs": len(errored),
            "execution_time_ms": wall_ms,
            "best_run": valid[0] if valid else None,
            "top10": valid[:10],
            "ranked_results": valid,
            "errored_results": errored,
            "all_results": all_results,
        }
        job.status = "DONE"
        job.finished_at = time.time()
        try:
            job.progress_queue.put_nowait({
                "type": "done",
                "job_id": job.job_id,
                "total_runs": len(all_results),
                "valid_runs": len(valid),
                "execution_time_ms": wall_ms
            })
        except queue.Full:
            pass

    def _run_job_thread(
        self,
        job: HyperJob,
        run_specs: List[tuple],
        workers: int,
        early_pruning: bool,
        original_spec: Dict[str, Any]
    ) -> None:
        """Coordinates execution across pool with live SSE streaming."""
        all_results: List[Dict[str, Any]] = []
        wall_start = time.perf_counter()

        try:
            # Multi-fidelity Successive Halving
            if early_pruning and len(run_specs) > 8:
                all_dates = original_spec.get("dates", [])
                n_sample = max(1, int(len(all_dates) * 0.3))
                stage1_dates = all_dates[:n_sample]

                stage1_specs = [
                    (rid, inst, stage1_dates, sk, combo, spec, sdir)
                    for (rid, inst, _, sk, combo, spec, sdir) in run_specs
                ]

                stage1_results = []
                pool_results = _run_batch_with_pool(stage1_specs, workers)
                for res in pool_results:
                    stage1_results.append(res)
                    job.completed += 1
                    try:
                        job.progress_queue.put_nowait({
                            "type": "progress",
                            "stage": "Stage 1 Pruning (30% Dates)",
                            "completed": job.completed,
                            "total": job.total,
                            "pct": job.pct_complete,
                            "eta_sec": job.eta_sec,
                            "last_run": res
                        })
                    except queue.Full:
                        pass

                # Retain top 50% based on user objective
                valid_s1 = [r for r in stage1_results if "error" not in r]
                target_obj = original_spec.get("objective_metric") or original_spec.get("rank_by", "sharpe_ratio")
                valid_s1.sort(key=_rank_key_func(target_obj), reverse=True)
                top_cutoff = max(1, len(valid_s1) // 2)
                top_run_ids = set(r["run_id"] for r in valid_s1[:top_cutoff])

                # Stage 2: Full dates for the top configurations
                remaining_specs = [
                    s for s in run_specs if s[0] in top_run_ids
                ]
                pool_results = _run_batch_with_pool(remaining_specs, workers)
                for res in pool_results:
                    all_results.append(res)
                    try:
                        job.progress_queue.put_nowait({
                            "type": "progress",
                            "stage": "Stage 2 Final (100% Dates)",
                            "completed": job.completed,
                            "total": job.total,
                            "pct": job.pct_complete,
                            "eta_sec": job.eta_sec,
                            "last_run": res
                        })
                    except queue.Full:
                        pass

            else:
                # Standard full-evaluation loop
                pool_results = _run_batch_with_pool(run_specs, workers)
                for res in pool_results:
                    all_results.append(res)
                    job.completed += 1
                    try:
                        job.progress_queue.put_nowait({
                            "type": "progress",
                            "completed": job.completed,
                            "total": job.total,
                            "pct": job.pct_complete,
                            "eta_sec": job.eta_sec,
                            "last_run": res
                        })
                    except queue.Full:
                        pass

        except Exception as exc:
            job.status = "ERROR"
            job.error = str(exc)
            job.finished_at = time.time()
            try:
                job.progress_queue.put_nowait({"type": "error", "error": str(exc)})
            except queue.Full:
                pass
            return

        wall_ms = round((time.perf_counter() - wall_start) * 1000, 2)
        valid = [r for r in all_results if "error" not in r]
        errored = [r for r in all_results if "error" in r]
        target_obj = original_spec.get("objective_metric") or original_spec.get("rank_by", "sharpe_ratio")
        valid.sort(key=_rank_key_func(target_obj), reverse=True)

        job.results = {
            "job_id": job.job_id,
            "strategy_type": original_spec.get("strategy_type", ""),
            "sampling_mode": original_spec.get("sampling_mode", "GRID"),
            "total_runs": len(all_results),
            "valid_runs": len(valid),
            "errored_runs": len(errored),
            "execution_time_ms": wall_ms,
            "best_run": valid[0] if valid else None,
            "top10": valid[:10],
            "ranked_results": valid,
            "errored_results": errored,
            "all_results": all_results,
        }
        job.status = "DONE"
        job.finished_at = time.time()

        try:
            job.progress_queue.put_nowait({
                "type": "done",
                "job_id": job.job_id,
                "total_runs": len(all_results),
                "valid_runs": len(valid),
                "execution_time_ms": wall_ms
            })
        except queue.Full:
            pass


__all__ = ["MassOptimizer", "_execute_single_run_worker"]
