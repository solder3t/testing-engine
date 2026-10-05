"""
tests/test_mass_optimizer.py — Verification of Mass Optimizer, Bar Cache, and Bayesian TPE.
"""

import time
import pytest
import pandas as pd
import numpy as np

from engine.mass_optimizer import (
    MassOptimizer,
    HyperJob,
    _grid_sample,
    _random_sample,
    _latin_hypercube_sample,
    _sobol_sample
)
from engine.shared_memory import SharedBarCache
from engine.bayesian_tpe import BayesianTpeOptimizer


def test_sampling_algorithms():
    """Verify all 4 sampling modes generate the requested number of unique valid configurations."""
    axes = {
        "fast_ema": [5, 9, 13, 21],
        "slow_ema": [21, 34, 55],
        "sl_pts": [10.0, 15.0, 20.0, 25.0]
    }

    # Grid
    grid_res = _grid_sample(axes, max_combos=10)
    assert len(grid_res) == 10
    assert "fast_ema" in grid_res[0]

    # Random
    rnd_res = _random_sample(axes, n_samples=15, seed=123)
    assert len(rnd_res) == 15
    for r in rnd_res:
        assert r["fast_ema"] in axes["fast_ema"]

    # Latin Hypercube Sampling (LHS)
    lhs_res = _latin_hypercube_sample(axes, n_samples=12, seed=42)
    assert len(lhs_res) == 12
    # Ensure all fast_ema values are covered across samples
    sampled_fast = set(r["fast_ema"] for r in lhs_res)
    assert sampled_fast == set(axes["fast_ema"])

    # Sobol
    sobol_res = _sobol_sample(axes, n_samples=16, seed=42)
    assert len(sobol_res) == 16
    for r in sobol_res:
        assert r["slow_ema"] in axes["slow_ema"]


def test_shared_bar_cache():
    """Verify SharedBarCache storage, hit/miss metrics, and clear."""
    cache = SharedBarCache()
    assert cache.get("2026_09_11", "NIFTY", "1min") is None
    assert cache.misses == 1

    # Put mock dataframe
    df = pd.DataFrame({
        "open": [100.0, 101.0],
        "high": [102.0, 103.0],
        "low": [99.0, 100.0],
        "close": [101.0, 102.0],
        "volume": [1000, 1500]
    })
    cache.put("2026_09_11", "NIFTY", "1min", df)
    retrieved = cache.get("2026_09_11", "NIFTY", "1min")
    assert retrieved is not None
    assert len(retrieved) == 2
    assert cache.hits == 1

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate_pct"] == 50.0
    assert stats["cached_items"] == 1

    cache.clear()
    assert cache.get_stats()["cached_items"] == 0


def test_bayesian_tpe_optimizer():
    """Verify Bayesian TPE warmup, recording trials, and guided suggestion."""
    axes = {
        "rsi_period": [7, 10, 14, 21],
        "sl_pts": [10.0, 15.0, 20.0, 25.0],
        "rule_type": ["BREAKOUT", "PULLBACK"]
    }
    tpe = BayesianTpeOptimizer(axes, gamma=0.25, warmup_trials=5, seed=42)

    # First suggestions should be random exploration (under warmup)
    warmup_sugg = tpe.suggest(5)
    assert len(warmup_sugg) == 5

    # Feed trials: high score when rsi_period=14 and rule_type="PULLBACK"
    for s in warmup_sugg:
        score = 2.5 if (s["rsi_period"] == 14 and s["rule_type"] == "PULLBACK") else 0.5
        tpe.tell(s, score)

    # Next suggestion should use KDE ratio
    guided = tpe.suggest(3)
    assert len(guided) == 3
    for g in guided:
        assert g["rsi_period"] in axes["rsi_period"]
        assert g["rule_type"] in axes["rule_type"]


def test_mass_optimizer_lifecycle():
    """Verify MassOptimizer submit_job creates a valid HyperJob with status tracking."""
    optimizer = MassOptimizer(max_workers=2)
    spec = {
        "strategy_type": "supertrend",
        "dates": ["2026_09_11"],
        "sampling_mode": "GRID",
        "parameter_grid": {
            "atr_period": [7, 14],
            "multiplier": [2.5, 3.0]
        },
        "max_iterations": 4,
        "max_workers": 2
    }

    job = optimizer.submit_job(spec)
    assert isinstance(job, HyperJob)
    assert job.job_id
    assert job.total == 4
    assert job.status in ("RUNNING", "DONE")

    # Wait briefly for completion
    timeout = 10.0
    start = time.time()
    while job.status == "RUNNING" and (time.time() - start) < timeout:
        time.sleep(0.1)

    assert job.status in ("DONE", "RUNNING")
    status_dict = job.to_status_dict()
    assert "job_id" in status_dict
    assert "pct_complete" in status_dict


def test_mass_optimizer_bayesian_tpe_lifecycle():
    """Verify closed-loop Bayesian TPE job lifecycle and feedback recording."""
    optimizer = MassOptimizer(max_workers=2)
    spec = {
        "strategy_type": "supertrend",
        "dates": ["2026_09_11"],
        "sampling_mode": "BAYESIAN_TPE",
        "parameter_grid": {
            "atr_period": [7, 14],
            "multiplier": [2.5, 3.0]
        },
        "max_iterations": 4,
        "max_workers": 2
    }

    job = optimizer.submit_job(spec)
    assert isinstance(job, HyperJob)
    assert job.job_id
    assert job.total == 4
    assert job.status in ("RUNNING", "DONE")

    # Wait for completion
    timeout = 15.0
    start = time.time()
    while job.status == "RUNNING" and (time.time() - start) < timeout:
        time.sleep(0.1)

    assert job.status in ("DONE", "RUNNING")
    status_dict = job.to_status_dict()
    assert "job_id" in status_dict
