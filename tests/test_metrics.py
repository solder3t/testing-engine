"""
tests/test_metrics.py — Tests for performance and risk metrics calculations.
"""

import pytest
from execution.order import OrderSide, Trade
from analytics.metrics import calculate_performance_metrics


def test_calculate_performance_metrics_basic():
    t1 = Trade("RELIANCE", 2885, OrderSide.BUY, 10, "09:30", 1000.0, 980.0, 980.0, 1040.0)
    t1.close("09:45", 1040.0, "TARGET_HIT", charges=25.0)  # PnL: +400 - 25 = +375

    t2 = Trade("INFY", 1594, OrderSide.BUY, 10, "10:00", 1500.0, 1480.0, 1480.0, 1550.0)
    t2.close("10:15", 1480.0, "SL_HIT", charges=25.0)      # PnL: -200 - 25 = -225

    metrics = calculate_performance_metrics([t1, t2], initial_capital=100000.0)

    assert metrics["total_trades"] == 2
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["win_rate"] == 50.0
    assert metrics["net_pnl"] == 150.0
    assert metrics["profit_factor"] > 1.0
    assert metrics["return_pct"] > 0
