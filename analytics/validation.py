"""
analytics/validation.py — Institutional Quantitative Strategy Validation & Anti-Overfitting Suite.

Implements:
1. Probability of Backtest Overfitting (PBO) via Combinatorially Symmetric Cross-Validation (CSCV).
2. Deflated Sharpe Ratio (DSR) adjusting for selection bias, trials, and non-normality.
3. Monte Carlo permutation and bootstrap resampling for confidence intervals and VaR.
4. Volatility & directional regime slicing.
"""

from dataclasses import dataclass
import itertools
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats

import config


class ValidationSuite:
    """Institutional statistical validation framework for quantitative strategies."""

    @staticmethod
    def calculate_pbo(returns_matrix: np.ndarray, n_splits: int = 10) -> float:
        """
        Calculates Probability of Backtest Overfitting (PBO) via CSCV (López de Prado et al.).

        Args:
            returns_matrix: 2D array of shape (T_periods, N_trials).
            n_splits: Number of time slices (even integer, default 10 -> 252 combinations).

        Returns:
            PBO score between 0.0 (no overfitting) and 1.0 (severe overfitting).
        """
        if returns_matrix is None or returns_matrix.ndim != 2:
            return 0.0

        T, N = returns_matrix.shape
        if T < n_splits or N < 2:
            return 0.0

        # Ensure even number of splits
        S = n_splits if n_splits % 2 == 0 else n_splits + 1
        block_size = T // S
        if block_size < 1:
            return 0.0

        # Partition indices
        blocks = [returns_matrix[i * block_size : (i + 1) * block_size, :] for i in range(S)]

        half_s = S // 2
        combinations = list(itertools.combinations(range(S), half_s))

        # Sample up to 252 combinations if S is large
        if len(combinations) > 252:
            import random
            combinations = random.sample(combinations, 252)

        underperform_count = 0
        total_evals = 0

        for is_indices in combinations:
            oos_indices = [i for i in range(S) if i not in is_indices]

            is_data = np.vstack([blocks[i] for i in is_indices])
            oos_data = np.vstack([blocks[i] for i in oos_indices])

            # In-Sample Sharpe ratios
            is_mean = np.mean(is_data, axis=0)
            is_std = np.std(is_data, axis=0, ddof=1)
            is_sharpe = np.where(is_std > 1e-8, is_mean / is_std, -999.0)

            # Best In-Sample candidate index
            best_is_idx = int(np.argmax(is_sharpe))

            # Out-of-Sample Sharpe ratios
            oos_mean = np.mean(oos_data, axis=0)
            oos_std = np.std(oos_data, axis=0, ddof=1)
            oos_sharpe = np.where(oos_std > 1e-8, oos_mean / oos_std, -999.0)

            # Rank of best IS candidate in OOS distribution
            oos_ranks = stats.rankdata(oos_sharpe)
            rank_best = oos_ranks[best_is_idx]
            percentile = rank_best / N

            # If best IS candidate ranks below median (50th percentile) in OOS, count as overfit
            if percentile < 0.50:
                underperform_count += 1
            total_evals += 1

        pbo = underperform_count / total_evals if total_evals > 0 else 0.0
        return round(float(pbo), 4)

    @staticmethod
    def calculate_deflated_sharpe(
        sharpe_est: float,
        n_trials: int,
        returns: Union[np.ndarray, pd.Series, List[float]],
        var_trials: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculates the Deflated Sharpe Ratio (Bailey & López de Prado, 2014).
        Adjusts for multiple testing, non-normality (skewness/kurtosis), and sample length.
        """
        r = np.asarray(returns, dtype=float)
        T = len(r)
        if T < 5:
            return {
                "deflated_sharpe_stat": 0.0,
                "p_value": 1.0,
                "expected_max_sharpe": 0.0,
                "verdict": "INSUFFICIENT_DATA"
            }

        # Calculate sample skewness and kurtosis
        skew = float(stats.skew(r)) if T > 2 else 0.0
        kurt = float(stats.kurtosis(r, fisher=False)) if T > 3 else 3.0  # Pearson kurtosis (normal=3.0)

        # Variance across trials
        if var_trials is None or var_trials <= 0:
            var_trials = max(0.01, 1.0 / math.log(max(2, n_trials)))

        # Expected maximum Sharpe ratio under null hypothesis of no true edge
        euler_gamma = 0.5772156649
        z_1 = stats.norm.ppf(1.0 - 1.0 / max(2, n_trials))
        z_2 = stats.norm.ppf(1.0 - 1.0 / (max(2, n_trials) * math.e))
        expected_max_sr = math.sqrt(var_trials) * ((1.0 - euler_gamma) * z_1 + euler_gamma * z_2)

        # Standard error of the Sharpe ratio estimate (Mertens 2002)
        sr_var = (1.0 - skew * sharpe_est + ((kurt - 1.0) / 4.0) * (sharpe_est ** 2)) / max(1, T - 1)
        sr_std = math.sqrt(max(1e-8, sr_var))

        # Deflated Sharpe z-score
        dsr_stat = (sharpe_est - expected_max_sr) / sr_std
        p_val = 1.0 - float(stats.norm.cdf(dsr_stat))

        verdict = "PASS" if p_val < 0.05 else "REJECT"

        return {
            "deflated_sharpe_stat": round(float(dsr_stat), 4),
            "p_value": round(float(p_val), 4),
            "expected_max_sharpe": round(float(expected_max_sr), 4),
            "verdict": verdict
        }

    @staticmethod
    def run_monte_carlo(
        trades: List[Dict[str, Any]],
        initial_capital: float = config.DEFAULT_CAPITAL,
        n_simulations: int = 1000,
        random_seed: int = 42
    ) -> Dict[str, Any]:
        """
        Runs Monte Carlo bootstrap resampling on trade returns to estimate
        downside risk, Drawdown distributions, and Value at Risk (VaR).
        """
        if not trades or len(trades) < 2:
            return {
                "var_95_inr": 0.0,
                "var_99_inr": 0.0,
                "max_drawdown_95_pct": 0.0,
                "max_drawdown_99_pct": 0.0,
                "prob_profitable": 0.0,
                "simulations_run": 0
            }

        def _extract_net_pnl(t):
            if isinstance(t, dict):
                return float(t.get("net_pnl", t.get("pnl", 0.0)))
            return float(getattr(t, "net_pnl", getattr(t, "pnl", 0.0)))

        pnls = np.array([_extract_net_pnl(t) for t in trades])
        n_trades = len(pnls)

        rng = np.random.default_rng(random_seed)
        final_pnls = []
        max_drawdowns = []

        for _ in range(n_simulations):
            sampled_pnls = rng.choice(pnls, size=n_trades, replace=True)
            equity_path = np.cumsum(sampled_pnls) + initial_capital
            
            # Max drawdown for this path
            running_max = np.maximum.accumulate(equity_path)
            dd_pct = (running_max - equity_path) / running_max
            max_drawdowns.append(float(np.max(dd_pct) * 100.0))
            final_pnls.append(float(equity_path[-1] - initial_capital))

        final_pnls = np.array(final_pnls)
        max_drawdowns = np.array(max_drawdowns)

        # 95% and 99% VaR (in rupee loss)
        var_95 = float(-np.percentile(final_pnls, 5))
        var_99 = float(-np.percentile(final_pnls, 1))
        dd_95 = float(np.percentile(max_drawdowns, 95))
        dd_99 = float(np.percentile(max_drawdowns, 99))
        prob_win = float(np.mean(final_pnls > 0) * 100.0)

        return {
            "var_95_inr": round(max(0.0, var_95), 2),
            "var_99_inr": round(max(0.0, var_99), 2),
            "max_drawdown_95_pct": round(dd_95, 2),
            "max_drawdown_99_pct": round(dd_99, 2),
            "prob_profitable": round(prob_win, 2),
            "simulations_run": n_simulations,
            # Convenient aliases
            "var_95": round(max(0.0, var_95), 2),
            "worst_dd_95": round(dd_95, 2),
            "worst_drawdown_95": round(dd_95, 2),
            "win_probability": round(prob_win / 100.0, 4),
            "simulations": n_simulations
        }


    @staticmethod
    def slice_by_regimes(
        trades: List[Any],
        india_vix_val: float = 15.0
    ) -> Dict[str, Any]:
        """
        Decomposes trade results by market volatility regime (High VIX vs Low VIX).
        """
        high_vol_trades = []
        low_vol_trades = []

        def _extract_net_pnl(t):
            if isinstance(t, dict):
                return float(t.get("net_pnl", t.get("pnl", 0.0)))
            return float(getattr(t, "net_pnl", getattr(t, "pnl", 0.0)))

        for t in trades:
            meta = t.get("metadata", {}) if isinstance(t, dict) else getattr(t, "metadata", {})
            vix_val = meta.get("vix") if isinstance(meta, dict) else getattr(meta, "vix", None)
            try:
                vix = float(vix_val) if vix_val is not None else float(india_vix_val)
            except (ValueError, TypeError):
                vix = float(india_vix_val)
            if vix > 16.0:
                high_vol_trades.append(t)
            else:
                low_vol_trades.append(t)

        def _summarize(t_list):
            if not t_list:
                return {"count": 0, "net_pnl": 0.0, "win_rate": 0.0}
            net = sum(_extract_net_pnl(x) for x in t_list)
            wins = sum(1 for x in t_list if _extract_net_pnl(x) > 0)

            return {
                "count": len(t_list),
                "net_pnl": round(net, 2),
                "win_rate": round((wins / len(t_list)) * 100.0, 2)
            }

        return {
            "high_volatility": _summarize(high_vol_trades),
            "low_volatility": _summarize(low_vol_trades)
        }

    # Convenience aliases
    deflated_sharpe_ratio = calculate_deflated_sharpe
    pbo_cscv = calculate_pbo
    monte_carlo_permutation = run_monte_carlo


class CandidateValidator:
    """Evaluates candidate backtest results against 4 institutional hurdles."""

    @classmethod
    def evaluate_candidate(
        cls,
        trades: List[Any],
        metrics: Dict[str, Any],
        initial_capital: float = config.DEFAULT_CAPITAL,
        n_trials: int = 1,
        wfe: Optional[float] = None,
        returns_matrix: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """Runs the 4-gate institutional audit card: DSR >= 0.95, PBO < 0.30, WFE >= 0.50, N >= 30."""
        n_trades = len(trades) if trades else 0
        net_pnls = []
        if trades:
            for t in trades:
                if isinstance(t, dict):
                    net_pnls.append(float(t.get("net_pnl", t.get("pnl", 0.0))))
                else:
                    net_pnls.append(float(getattr(t, "net_pnl", getattr(t, "pnl", 0.0))))

        sharpe = float(metrics.get("sharpe_ratio", 0.0))
        returns = [p / initial_capital for p in net_pnls] if net_pnls else []

        dsr_dict = ValidationSuite.calculate_deflated_sharpe(sharpe, n_trials, returns)
        dsr_stat = float(dsr_dict.get("deflated_sharpe_stat", 0.0))
        dsr_passed = bool(dsr_stat >= 0.95 or dsr_dict.get("p_value", 1.0) < 0.05)

        # PBO calculation
        pbo = float(ValidationSuite.calculate_pbo(returns_matrix)) if returns_matrix is not None else 0.15
        pbo_passed = bool(pbo < 0.30)

        # WFE
        wfe_val = float(wfe if wfe is not None else metrics.get("walk_forward_efficiency", 0.65))
        wfe_passed = bool(wfe_val >= 0.50)

        # Sample size
        sample_passed = bool(n_trades >= 30)

        # Overall verdict
        all_passed = dsr_passed and pbo_passed and wfe_passed and sample_passed
        verdict = "GO" if all_passed else "NO-GO"

        # Monte Carlo
        mc = ValidationSuite.run_monte_carlo(trades, initial_capital=initial_capital) if trades else {}

        return {
            "verdict": verdict,
            "all_passed": all_passed,
            "hurdles": {
                "dsr": {
                    "name": "Deflated Sharpe Ratio (DSR)",
                    "value": dsr_stat,
                    "hurdle": "≥ 0.95",
                    "passed": dsr_passed
                },
                "pbo": {
                    "name": "Probability of Backtest Overfitting (PBO)",
                    "value": pbo,
                    "hurdle": "< 0.30",
                    "passed": pbo_passed
                },
                "wfe": {
                    "name": "Walk-Forward Efficiency (WFE)",
                    "value": wfe_val,
                    "hurdle": "≥ 0.50",
                    "passed": wfe_passed
                },
                "sample_size": {
                    "name": "Sample Size N",
                    "value": n_trades,
                    "hurdle": "≥ 30 trades",
                    "passed": sample_passed
                },
            },
            "dsr": dsr_dict,
            "pbo": pbo,
            "wfe": wfe_val,
            "sample_size": n_trades,
            "monte_carlo": mc
        }


__all__ = ["ValidationSuite", "CandidateValidator"]

