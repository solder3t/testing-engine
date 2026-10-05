"""
engine/bayesian_tpe.py — Tree-structured Parzen Estimator (TPE) Optimizer.

Implements Bayesian optimization via TPE for parameter tuning in quantitative
trading strategies. Replaces naive brute-force grid search with guided search
maximizing Expected Improvement (EI).
"""

from typing import Dict, List, Any, Optional, Tuple
import math
import random
import numpy as np


class BayesianTpeOptimizer:
    """Tree-structured Parzen Estimator for parameter space exploration."""

    def __init__(
        self,
        param_axes: Dict[str, List[Any]],
        gamma: float = 0.20,
        warmup_trials: int = 10,
        seed: int = 42
    ):
        self.param_axes = param_axes
        self.gamma = gamma
        self.warmup_trials = warmup_trials
        self.rng = random.Random(seed)
        self.np_rng = np.random.RandomState(seed)
        self.trials: List[Tuple[Dict[str, Any], float]] = []

    def tell(self, params: Dict[str, Any], score: float) -> None:
        """Record an evaluated parameter trial and its objective score."""
        self.trials.append((dict(params), float(score)))

    def tell_batch(self, batch: List[Tuple[Dict[str, Any], float]]) -> None:
        """Record multiple evaluated trials."""
        for p, s in batch:
            self.tell(p, s)

    def _sample_random(self) -> Dict[str, Any]:
        """Sample a uniform random point from parameter axes."""
        return {k: self.rng.choice(vals) for k, vals in self.param_axes.items()}

    def _kde_score_ratio(self, val: Any, l_vals: List[Any], g_vals: List[Any], all_vals: List[Any]) -> float:
        """
        Calculates ratio l(x) / g(x) for Expected Improvement.
        Uses smoothed categorical probability or Gaussian kernel density estimate.
        """
        # 1. Categorical / discrete check
        is_numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in all_vals)

        if not is_numeric:
            alpha = 1.0  # Laplace smoothing
            n_choices = len(all_vals)
            l_count = sum(1 for x in l_vals if x == val)
            g_count = sum(1 for x in g_vals if x == val)
            p_l = (l_count + alpha) / (len(l_vals) + alpha * n_choices)
            p_g = (g_count + alpha) / (len(g_vals) + alpha * n_choices)
            return p_l / max(p_g, 1e-6)

        # 2. Numeric Gaussian KDE
        val_f = float(val)
        l_arr = np.array([float(x) for x in l_vals], dtype=np.float64)
        g_arr = np.array([float(x) for x in g_vals], dtype=np.float64)

        std_l = max(float(np.std(l_arr)), 1e-3)
        std_g = max(float(np.std(g_arr)), 1e-3)

        # Gaussian density computation
        p_l = float(np.mean(np.exp(-0.5 * ((val_f - l_arr) / std_l) ** 2) / (std_l * np.sqrt(2 * np.pi))))
        p_g = float(np.mean(np.exp(-0.5 * ((val_f - g_arr) / std_g) ** 2) / (std_g * np.sqrt(2 * np.pi))))

        return (p_l + 1e-5) / max(p_g + 1e-5, 1e-6)

    def suggest(self, n_suggestions: int = 1) -> List[Dict[str, Any]]:
        """
        Suggests the next parameter configurations to evaluate.
        If under warmup_trials, returns random/LHS configurations.
        Otherwise, samples candidates and picks highest Expected Improvement.
        """
        suggestions: List[Dict[str, Any]] = []

        for _ in range(n_suggestions):
            if len(self.trials) < self.warmup_trials:
                suggestions.append(self._sample_random())
                continue

            # Sort trials by score descending
            sorted_trials = sorted(self.trials, key=lambda x: x[1], reverse=True)
            n_l = max(1, int(len(sorted_trials) * self.gamma))

            l_trials = [t[0] for t in sorted_trials[:n_l]]
            g_trials = [t[0] for t in sorted_trials[n_l:]]

            # Generate candidate pool (e.g. 24 candidate points)
            best_candidate = None
            best_ei = -float("inf")

            candidates = [self._sample_random() for _ in range(24)]

            for cand in candidates:
                # Combined log ratio across all dimensions
                ei_log_sum = 0.0
                for k, vals in self.param_axes.items():
                    val = cand[k]
                    l_vals = [t[k] for t in l_trials if k in t]
                    g_vals = [t[k] for t in g_trials if k in t]
                    ratio = self._kde_score_ratio(val, l_vals, g_vals, vals)
                    ei_log_sum += math.log(max(ratio, 1e-9))

                if ei_log_sum > best_ei:
                    best_ei = ei_log_sum
                    best_candidate = cand

            suggestions.append(best_candidate or self._sample_random())

        return suggestions
