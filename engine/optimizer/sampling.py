"""
engine/optimizer/sampling.py — Multi-modal hyperparameter space sampling strategies.
Supports Grid, Random, Latin Hypercube (LHS), and Sobol low-discrepancy sequences.
"""

import itertools
import math
import random
from typing import Any, Dict, List


def _grid_sample(param_axes: Dict[str, List[Any]], max_combos: int) -> List[Dict[str, Any]]:
    """Cartesian product grid sampling."""
    keys = list(param_axes.keys())
    if not keys:
        return [{}]
    combos = []
    for prod in itertools.product(*[param_axes[k] for k in keys]):
        combos.append(dict(zip(keys, prod)))
        if len(combos) >= max_combos:
            break
    return combos


def _random_sample(param_axes: Dict[str, List[Any]], n_samples: int, seed: int = 42) -> List[Dict[str, Any]]:
    """Uniform random sampling."""
    rng = random.Random(seed)
    keys = list(param_axes.keys())
    if not keys:
        return [{}] * n_samples
    results = []
    for _ in range(n_samples):
        results.append({k: rng.choice(param_axes[k]) for k in keys})
    return results


def _latin_hypercube_sample(param_axes: Dict[str, List[Any]], n_samples: int, seed: int = 42) -> List[Dict[str, Any]]:
    """Latin Hypercube Sampling ensuring stratified parameter coverage."""
    rng = random.Random(seed)
    keys = list(param_axes.keys())
    if not keys:
        return [{}] * n_samples

    sampled: Dict[str, List[Any]] = {}
    for k in keys:
        vals = param_axes[k]
        cycle = (vals * math.ceil(n_samples / len(vals)))[:n_samples]
        rng.shuffle(cycle)
        sampled[k] = cycle

    return [{k: sampled[k][i] for k in keys} for i in range(n_samples)]


def _sobol_sample(param_axes: Dict[str, List[Any]], n_samples: int, seed: int = 42) -> List[Dict[str, Any]]:
    """Sobol low-discrepancy sequence sampling with SciPy or Van der Corput fallback."""
    keys = list(param_axes.keys())
    if not keys:
        return [{}] * n_samples

    d = len(keys)
    try:
        from scipy.stats import qmc  # type: ignore
        sampler = qmc.Sobol(d=d, seed=seed)
        sample_matrix = sampler.random(n=n_samples)
    except Exception:
        # High quality Van der Corput quasi-random sequence fallback
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47][:d]
        while len(primes) < d:
            primes.append(primes[-1] + 2)
        sample_matrix = []
        for i in range(1, n_samples + 1):
            row = []
            for base in primes:
                f, q, b = 0.0, 1.0, float(base)
                n = i
                while n > 0:
                    q /= b
                    f += (n % base) * q
                    n //= base
                row.append(f)
            sample_matrix.append(row)

    results = []
    for row in sample_matrix:
        combo = {}
        for dim_idx, k in enumerate(keys):
            vals = param_axes[k]
            val_idx = min(int(row[dim_idx] * len(vals)), len(vals) - 1)
            combo[k] = vals[val_idx]
        results.append(combo)
    return results


# Public aliases
grid_sample = _grid_sample
random_sample = _random_sample
latin_hypercube_sample = _latin_hypercube_sample
sobol_sample = _sobol_sample

__all__ = [
    "_grid_sample",
    "_random_sample",
    "_latin_hypercube_sample",
    "_sobol_sample",
    "grid_sample",
    "random_sample",
    "latin_hypercube_sample",
    "sobol_sample",
]
