"""
engine/mass_optimizer.py — Backward Compatibility Shim.

The mass iteration and optimization system has been modularized into `engine.optimizer`:
- `engine.optimizer.sampling`: Multi-modal parameter sampling (Grid, Random, LHS, Sobol)
- `engine.optimizer.job_tracker`: Asynchronous HyperJob state and SSE tracking
- `engine.optimizer.executor`: MassOptimizer execution engine

All symbols are re-exported here for full backward compatibility.
"""

from engine.optimizer import (
    MassOptimizer,
    HyperJob,
    _grid_sample,
    _random_sample,
    _latin_hypercube_sample,
    _sobol_sample,
    grid_sample,
    random_sample,
    latin_hypercube_sample,
    sobol_sample,
)

__all__ = [
    "MassOptimizer",
    "HyperJob",
    "_grid_sample",
    "_random_sample",
    "_latin_hypercube_sample",
    "_sobol_sample",
    "grid_sample",
    "random_sample",
    "latin_hypercube_sample",
    "sobol_sample",
]
