"""
tests/test_metrics.py — Tests for performance and risk metrics calculations.
"""

import pytest
from execution.order import OrderSide, Trade
from analytics.metrics import calculate_performance_metrics, _consecutive_streaks


def test_calculate_performance_metrics_basic():
    t1 = Trade("RELIANCE", 2885, OrderSide.BUY, 10, "09:30", 1000.0, 980.0, 980.0, 1040.0)
    t1.close("09:45", 1040.0, "TARGET_HIT", charges=25.0)  # PnL: +400 - 25 = +375

    t2 = Trade("INFY", 1594, OrderSide.BUY, 10, "10:00", 1500.0, 1480.0, 1480.0, 1550.0)
    t2.close("10:15", 1480.0, "SL_HIT", charges=25.0)      # PnL: -200 - 25 = -225

    metrics = calculate_performance_metrics([t1, t2], initial_capital=100000.0)

    assert metrics["total_trades"] == 2
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["breakeven_count"] == 0
    assert metrics["win_rate"] == 50.0
    assert metrics["net_pnl"] == 150.0
    assert metrics["profit_factor"] > 1.0
    assert metrics["return_pct"] > 0

    # New metrics always present
    assert "calmar_ratio" in metrics
    assert "max_consecutive_wins" in metrics
    assert "max_consecutive_losses" in metrics


def test_consecutive_streaks():
    pnls = [100, -50, 200, 300, -100, -200, -50, 400]
    max_wins, max_losses = _consecutive_streaks(pnls)
    assert max_wins == 2   # 200, 300
    assert max_losses == 3  # -100, -200, -50


def test_consecutive_streaks_all_wins():
    max_wins, max_losses = _consecutive_streaks([100, 200, 300])
    assert max_wins == 3
    assert max_losses == 0


def test_consecutive_streaks_with_breakeven():
    max_wins, max_losses = _consecutive_streaks([100, 0, 100, -50])
    # 0 breaks streaks
    assert max_wins == 1  # individual wins, reset by breakeven
    assert max_losses == 1


def test_empty_metrics_has_all_keys():
    """Ensure zero-trade result has all required keys."""
    m = calculate_performance_metrics([], initial_capital=100000.0)
    required_keys = [
        "total_trades", "wins", "losses", "breakeven_count", "win_rate",
        "gross_pnl", "total_charges", "net_pnl", "return_pct", "profit_factor",
        "expectancy", "sharpe_ratio", "sortino_ratio", "calmar_ratio",
        "max_drawdown_pct", "max_drawdown_rs", "avg_trade_pnl", "best_trade",
        "worst_trade", "avg_holding_bars", "max_consecutive_wins", "max_consecutive_losses"
    ]
    for key in required_keys:
        assert key in m, f"Missing key in empty metrics: {key}"
