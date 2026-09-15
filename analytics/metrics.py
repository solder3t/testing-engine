"""
analytics/metrics.py — Quantitative Performance and Risk Analytics.
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd

from execution.order import Trade


def calculate_performance_metrics(
    trades: List[Trade],
    initial_capital: float,
    equity_curve: List[Dict] = None
) -> Dict[str, Any]:
    """
    Computes professional quantitative metrics from closed trades and equity series.
    """
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "gross_pnl": 0.0,
            "total_charges": 0.0,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_rs": 0.0,
            "avg_trade_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_holding_bars": 0.0
        }

    pnls = [t.net_pnl for t in trades]
    gross_pnls = [t.gross_pnl for t in trades]
    charges = [t.charges for t in trades]

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = round((win_count / total_trades) * 100, 2)

    total_gross = round(sum(gross_pnls), 2)
    total_charges = round(sum(charges), 2)
    total_net = round(sum(pnls), 2)
    return_pct = round((total_net / initial_capital) * 100, 2)

    sum_wins = sum(wins)
    sum_losses = abs(sum(losses))
    profit_factor = round(sum_wins / sum_losses, 2) if sum_losses > 0 else (99.0 if sum_wins > 0 else 0.0)

    avg_win = (sum_wins / win_count) if win_count > 0 else 0.0
    avg_loss = (sum_losses / loss_count) if loss_count > 0 else 0.0
    expectancy = round(((win_count / total_trades) * avg_win) - ((loss_count / total_trades) * avg_loss), 2)

    # ── Max Drawdown ──────────────────────────────────────────────────────────
    max_dd_pct = 0.0
    max_dd_rs = 0.0

    drawdown_curve = []
    if equity_curve and len(equity_curve) > 0:
        equities = [pt["equity"] for pt in equity_curve]
        peaks = pd.Series(equities).cummax()
        drawdowns_rs = peaks - pd.Series(equities)
        drawdowns_pct = (drawdowns_rs / peaks) * 100

        max_dd_rs = round(float(drawdowns_rs.max()), 2)
        max_dd_pct = round(float(drawdowns_pct.max()), 2)

        for pt, dd_pct, dd_val in zip(equity_curve, drawdowns_pct, drawdowns_rs):
            drawdown_curve.append({
                "timestamp": pt["timestamp"],
                "drawdown_pct": round(float(dd_pct), 2),
                "drawdown_rs": round(float(dd_val), 2)
            })
    else:
        # Fallback from cumulative trade PnL
        running = initial_capital
        peak = initial_capital
        for p in pnls:
            running += p
            peak = max(peak, running)
            dd = peak - running
            dd_pct = (dd / peak) * 100
            max_dd_rs = max(max_dd_rs, dd)
            max_dd_pct = max(max_dd_pct, dd_pct)

    # ── Sharpe & Sortino Ratios ───────────────────────────────────────────────
    sharpe = 0.0
    sortino = 0.0

    if len(pnls) > 1:
        returns = np.array(pnls) / initial_capital
        mean_r = np.mean(returns)
        std_r = np.std(returns)
        if std_r > 0:
            sharpe = round(float((mean_r / std_r) * np.sqrt(252)), 2)

        downside = returns[returns < 0]
        downside_std = np.std(downside) if len(downside) > 0 else 0.0
        if downside_std > 0:
            sortino = round(float((mean_r / downside_std) * np.sqrt(252)), 2)

    avg_bars = round(sum(t.holding_bars for t in trades) / total_trades, 1)

    return {
        "total_trades": total_trades,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": win_rate,
        "gross_pnl": total_gross,
        "total_charges": total_charges,
        "net_pnl": total_net,
        "return_pct": return_pct,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_rs": max_dd_rs,
        "avg_trade_pnl": round(total_net / total_trades, 2),
        "best_trade": round(max(pnls), 2) if pnls else 0.0,
        "worst_trade": round(min(pnls), 2) if pnls else 0.0,
        "avg_holding_bars": avg_bars,
        "drawdown_curve": drawdown_curve
    }
