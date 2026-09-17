"""
analytics/metrics.py — Quantitative Performance and Risk Analytics.
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd

from execution.order import Trade


def _consecutive_streaks(pnls: List[float]):
    """Returns (max_consecutive_wins, max_consecutive_losses) from a list of trade P&Ls."""
    max_wins = max_losses = cur_wins = cur_losses = 0
    for p in pnls:
        if p > 0:
            cur_wins += 1
            cur_losses = 0
        elif p < 0:
            cur_losses += 1
            cur_wins = 0
        else:
            cur_wins = 0
            cur_losses = 0
        max_wins = max(max_wins, cur_wins)
        max_losses = max(max_losses, cur_losses)
    return max_wins, max_losses


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
            "breakeven_count": 0,
            "win_rate": 0.0,
            "gross_pnl": 0.0,
            "total_charges": 0.0,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_rs": 0.0,
            "avg_trade_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_holding_bars": 0.0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0
        }

    pnls = [t.net_pnl for t in trades]
    gross_pnls = [t.gross_pnl for t in trades]
    charges = [t.charges for t in trades]

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    breakeven_count = len([p for p in pnls if p == 0])

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

    max_cons_wins, max_cons_losses = _consecutive_streaks(pnls)

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

    # ── Calmar Ratio ──────────────────────────────────────────────────────────
    # Annualized Return / Max Drawdown%. Use raw return_pct as proxy for annualized
    # (valid for single-session and multi-day runs of similar horizon).
    calmar = round(return_pct / max_dd_pct, 2) if max_dd_pct > 0 else 0.0

    # ── Sharpe & Sortino Ratios ───────────────────────────────────────────────
    # Correct method: compute from DAILY equity returns (not per-trade returns).
    # This ensures √252 annualization is applied to the right time unit.
    sharpe = 0.0
    sortino = 0.0

    if equity_curve and len(equity_curve) > 1:
        # Build a date-keyed daily closing equity series from the equity curve
        ec_df = pd.DataFrame(equity_curve)
        ec_df["date"] = ec_df["timestamp"].astype(str).str[:10]
        daily_equity = ec_df.groupby("date")["equity"].last()

        if len(daily_equity) >= 2:
            daily_returns = daily_equity.pct_change().dropna()
            mean_r = float(daily_returns.mean())
            std_r = float(daily_returns.std())

            if std_r > 0:
                sharpe = round(float((mean_r / std_r) * np.sqrt(252)), 2)

            downside = daily_returns[daily_returns < 0]
            downside_std = float(downside.std()) if len(downside) > 1 else 0.0
            if downside_std > 0:
                sortino = round(float((mean_r / downside_std) * np.sqrt(252)), 2)
        else:
            # Single day: fall back to per-trade returns (no annualization applied)
            if len(pnls) > 1:
                returns = np.array(pnls) / initial_capital
                mean_r = float(np.mean(returns))
                std_r = float(np.std(returns))
                if std_r > 0:
                    sharpe = round(float(mean_r / std_r), 2)  # No √252 for intraday
                downside = returns[returns < 0]
                ds = float(np.std(downside)) if len(downside) > 0 else 0.0
                if ds > 0:
                    sortino = round(float(mean_r / ds), 2)

    avg_bars = round(sum(t.holding_bars for t in trades) / total_trades, 1)

    return {
        "total_trades": total_trades,
        "wins": win_count,
        "losses": loss_count,
        "breakeven_count": breakeven_count,
        "win_rate": win_rate,
        "gross_pnl": total_gross,
        "total_charges": total_charges,
        "net_pnl": total_net,
        "return_pct": return_pct,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_rs": max_dd_rs,
        "avg_trade_pnl": round(float(total_net / total_trades), 2),
        "best_trade": round(float(max(pnls)), 2) if pnls else 0.0,
        "worst_trade": round(float(min(pnls)), 2) if pnls else 0.0,
        "avg_holding_bars": avg_bars,
        "max_consecutive_wins": max_cons_wins,
        "max_consecutive_losses": max_cons_losses,
        "drawdown_curve": drawdown_curve
    }
