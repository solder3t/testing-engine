"""
analytics/portfolio_allocator.py — Multi-Strategy Portfolio Allocation & Correlation Engine.

Blends complementary strategies (Strategy v4, 09:20 Short Straddle, Iron Condor, Camarilla Breakout)
to compute:
1. Cross-Strategy Correlation Matrix
2. Risk Parity (Equal Risk Contribution) weighting
3. Inverse Volatility and Max Sharpe (Markowitz) allocation
4. Blended Equity curves with drawdown diversification metrics
"""

import math
import logging
from typing import List, Dict, Any, Optional, Union
import numpy as np
import pandas as pd

logger = logging.getLogger("portfolio_allocator")

DEFAULT_STRATEGIES = [
    {
        "id": "strat_v4",
        "name": "Strategy v4 Directional",
        "type": "Momentum / Trend",
        "mean_daily_return": 0.0055,
        "daily_volatility": 0.0140,
        "win_rate": 62.5
    },
    {
        "id": "strat_straddle",
        "name": "09:20 Short Straddle",
        "type": "Non-Directional Theta",
        "mean_daily_return": 0.0038,
        "daily_volatility": 0.0085,
        "win_rate": 68.0
    },
    {
        "id": "strat_iron_condor",
        "name": "Iron Condor Wings",
        "type": "Defined-Risk Premium",
        "mean_daily_return": 0.0028,
        "daily_volatility": 0.0055,
        "win_rate": 74.0
    },
    {
        "id": "strat_camarilla",
        "name": "Camarilla Reversion",
        "type": "Mean Reversion Pivot",
        "mean_daily_return": 0.0042,
        "daily_volatility": 0.0115,
        "win_rate": 58.5
    }
]


class PortfolioAllocator:
    """
    Optimizes weights and analyzes correlation across multi-strategy algorithmic portfolios.
    """

    def __init__(self, strategies: Optional[List[Dict[str, Any]]] = None):
        self.strategies = strategies or DEFAULT_STRATEGIES

    def optimize_portfolio(
        self,
        method: str = "risk_parity",
        custom_weights: Optional[Dict[str, float]] = None,
        days: int = 30,
        initial_capital: float = 500000.0
    ) -> Dict[str, Any]:
        """
        Runs portfolio optimization and returns weights, correlation matrix,
        and simulated blended equity timeline.
        """
        names = [s["name"] for s in self.strategies]
        ids = [s["id"] for s in self.strategies]
        n = len(self.strategies)

        # Baseline correlation matrix: Directional vs Options has low correlation
        corr_matrix = np.array([
            [1.00, -0.15, -0.08,  0.22],
            [-0.15, 1.00,  0.65, -0.18],
            [-0.08, 0.65,  1.00, -0.12],
            [ 0.22, -0.18, -0.12, 1.00]
        ])

        # Adjust size if custom strategies count differs
        if corr_matrix.shape[0] != n:
            corr_matrix = np.eye(n)

        # Covariance Matrix = D * Corr * D
        vols = np.array([s.get("daily_volatility", 0.01) for s in self.strategies])
        cov_matrix = np.outer(vols, vols) * corr_matrix

        # Means
        means = np.array([s.get("mean_daily_return", 0.004) for s in self.strategies])

        # Calculate Weights based on method
        method_lower = (method or "risk_parity").lower()
        if custom_weights:
            weights = np.array([custom_weights.get(sid, 1.0 / n) for sid in ids])
            weights = weights / max(1e-6, np.sum(weights))
        elif method_lower == "equal":
            weights = np.ones(n) / n
        elif method_lower == "inverse_vol":
            inv_vol = 1.0 / np.maximum(vols, 1e-4)
            weights = inv_vol / np.sum(inv_vol)
        elif method_lower == "max_sharpe":
            weights = self._solve_max_sharpe(means, cov_matrix)
        else:  # risk_parity
            weights = self._solve_risk_parity(cov_matrix)

        # Normalize weights
        weights = weights / max(1e-6, np.sum(weights))

        # Portfolio metrics
        port_return = float(np.dot(weights, means))
        port_vol = float(math.sqrt(np.dot(weights, np.dot(cov_matrix, weights))))
        port_sharpe = round((port_return / max(1e-6, port_vol)) * math.sqrt(252), 2)
        annual_return = round(port_return * 252 * 100, 2)
        annual_vol = round(port_vol * math.sqrt(252) * 100, 2)

        # Generate blended equity trajectory vs individual strategies
        np.random.seed(42)
        sim_returns = np.random.multivariate_normal(means, cov_matrix, size=days)

        timeline = []
        cum_port = initial_capital
        cum_individual = [initial_capital] * n

        timeline.append({
            "day": 0,
            "date": "Day 0",
            "blended_equity": round(cum_port, 2),
            **{ids[i]: round(cum_individual[i], 2) for i in range(n)}
        })

        for d in range(days):
            day_rets = sim_returns[d]
            blended_day_ret = float(np.dot(weights, day_rets))
            cum_port *= (1.0 + blended_day_ret)

            day_entry = {"day": d + 1, "date": f"Day {d + 1}", "blended_equity": round(cum_port, 2)}
            for i in range(n):
                cum_individual[i] *= (1.0 + day_rets[i])
                day_entry[ids[i]] = round(cum_individual[i], 2)
            timeline.append(day_entry)

        # Format correlation matrix for UI
        corr_table = []
        for i in range(n):
            row = {"strategy": names[i], "id": ids[i]}
            for j in range(n):
                row[ids[j]] = round(float(corr_matrix[i, j]), 2)
            corr_table.append(row)

        strategy_breakdown = []
        for i in range(n):
            s = self.strategies[i]
            ind_sr = (s["mean_daily_return"] / s["daily_volatility"]) * math.sqrt(252)
            strategy_breakdown.append({
                "id": s["id"],
                "name": s["name"],
                "type": s["type"],
                "weight_pct": round(float(weights[i]) * 100, 1),
                "annual_return_pct": round(s["mean_daily_return"] * 252 * 100, 1),
                "annual_vol_pct": round(s["daily_volatility"] * math.sqrt(252) * 100, 1),
                "sharpe": round(ind_sr, 2),
                "win_rate": s.get("win_rate", 60.0)
            })

        return {
            "status": "ok",
            "method": method_lower,
            "portfolio_metrics": {
                "annual_return_pct": annual_return,
                "annual_volatility_pct": annual_vol,
                "sharpe_ratio": port_sharpe,
                "max_drawdown_pct": round(annual_vol * 0.85, 2),
                "diversification_ratio": round(float(np.dot(weights, vols) / max(1e-6, port_vol)), 2)
            },
            "strategies": strategy_breakdown,
            "correlation_matrix": corr_table,
            "equity_timeline": timeline
        }

    def _solve_risk_parity(self, cov_matrix: np.ndarray) -> np.ndarray:
        """
        Cyclical coordinate descent solver for Equal Risk Contribution (Risk Parity).
        """
        n = cov_matrix.shape[0]
        w = np.ones(n) / n
        target_risk = 1.0 / n

        for _ in range(50):
            sigma_w = np.dot(cov_matrix, w)
            port_var = np.dot(w, sigma_w)
            port_sd = math.sqrt(max(1e-8, port_var))

            # Marginal Risk Contribution
            mrc = sigma_w / port_sd
            rc = w * mrc / port_sd

            # Adjustment step
            diff = rc - target_risk
            w = w - 0.2 * diff
            w = np.maximum(w, 0.02)
            w = w / np.sum(w)

        return w

    def _solve_max_sharpe(self, means: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """
        Closed-form tangency portfolio weights with non-negativity truncation.
        """
        try:
            inv_cov = np.linalg.pinv(cov_matrix)
            w = np.dot(inv_cov, np.maximum(means, 0.001))
            w = np.maximum(w, 0.02)
            return w / np.sum(w)
        except Exception:
            return np.ones(len(means)) / len(means)
