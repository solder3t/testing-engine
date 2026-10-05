"""
tests/test_trade_simulator.py — Unit tests for advanced TradeSimulator features.
"""

import pytest
from execution.trade_simulator import TradeSimulator


def test_basic_trade_open_and_target():
    sim = TradeSimulator({"lot_size": 50, "default_lots": 1, "initial_sl_pts": 10.0, "target_pts": 20.0})
    sim.reset_session("2026_09_11")

    trade = sim.open_trade("NIFTY", side="BUY", price=100.0, timestamp="09:15:00")
    assert trade is not None
    assert trade.quantity == 50
    assert trade.status == "OPEN"

    # Candle reaches target
    bar = {"timestamp": "09:16:00", "high": 125.0, "low": 98.0, "close": 122.0}
    closed = sim.update_bar(bar)
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.exit_reason == "TARGET_HIT"
    assert closed.pnl_gross > 0


def test_tsl_ladder_and_partial_booking():
    sim = TradeSimulator({
        "lot_size": 25,
        "default_lots": 4,           # 4 lots = 100 qty
        "initial_sl_pts": 15.0,
        "target_pts": 60.0,
        "partial_booking": True,
        "partial_booking_pct": 0.75  # 75% = 3 lots booked on Rung 1
    })
    sim.reset_session("2026_09_11")

    trade = sim.open_trade("BANKNIFTY", side="BUY", price=500.0, timestamp="09:20:00")
    assert trade is not None
    assert trade.quantity == 100
    assert trade.lots == 4

    # Bar triggers Rung 1 (+10 pts) -> should book 75% (3 lots = 75 qty) and move SL to breakeven + buffer
    bar1 = {"timestamp": "09:21:00", "high": 512.0, "low": 498.0, "close": 511.0}
    sim.update_bar(bar1)
    assert trade.trail_level == 1
    assert trade.partial_booked is True
    assert trade.booked_quantity == 75
    assert trade.quantity == 25
    assert trade.lots == 1
    assert trade.current_sl > 500.0  # Trailed to breakeven + buffer

    # Subsequent bar triggers Rung 2 (+20 pts)
    bar2 = {"timestamp": "09:22:00", "high": 522.0, "low": 508.0, "close": 521.0}
    sim.update_bar(bar2)
    assert trade.trail_level == 2

    # Price reverses and hits trailed SL
    bar3 = {"timestamp": "09:23:00", "high": 520.0, "low": 505.0, "close": 506.0}
    closed = sim.update_bar(bar3)
    assert closed is not None
    assert closed.exit_reason == "TSL_HIT"
    assert closed.pnl_net > 0  # Still in profit due to partial booking


def test_cooldown_enforcement():
    sim = TradeSimulator({"cooldown_profit_sec": 180, "cooldown_loss_sec": 300})
    sim.reset_session("2026_09_11")

    trade = sim.open_trade("NIFTY", side="BUY", price=100.0, timestamp="09:15:00")
    sim.update_bar({"timestamp": "09:16:00", "high": 80.0, "low": 70.0, "close": 75.0})  # Loss

    # Immediately trying to enter next second -> in cooldown (300s)
    allowed, reason = sim.can_enter_trade("09:16:30")
    assert allowed is False
    assert "In cooldown" in reason

    # After 301 seconds -> allowed
    allowed_later, _ = sim.can_enter_trade("09:22:00")
    assert allowed_later is True
