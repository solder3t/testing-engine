"""
tests/test_portfolio.py — Tests for Portfolio and Risk Controls.
"""

import pytest
from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio


def test_portfolio_trade_lifecycle():
    port = Portfolio(initial_capital=100000.0)

    # Open Buy Trade
    trade = port.open_trade(
        symbol="RELIANCE",
        security_id=2885,
        side=OrderSide.BUY,
        price=1000.0,
        qty=10,
        sl=980.0,
        target=1040.0,
        entry_time="2026-09-02 09:35:00"
    )

    assert trade is not None
    assert len(port.open_trades) == 1
    assert trade.status == "OPEN"

    # Bar 1: Price goes to 1045 -> Target Hit!
    quotes = {"RELIANCE": {"open": 1020.0, "high": 1045.0, "low": 1015.0, "close": 1042.0}}
    closed = port.update_open_trades("2026-09-02 09:40:00", quotes)

    assert len(closed) == 1
    assert closed[0].status == "CLOSED"
    assert closed[0].exit_reason == "TARGET_HIT"
    assert closed[0].net_pnl > 0
    assert len(port.open_trades) == 0
    assert port.capital > 100000.0


def test_portfolio_stop_loss_hit():
    port = Portfolio(initial_capital=100000.0)

    trade = port.open_trade(
        symbol="INFY",
        security_id=1594,
        side=OrderSide.BUY,
        price=1500.0,
        qty=10,
        sl=1480.0,
        target=1550.0,
        entry_time="2026-09-02 09:35:00"
    )

    quotes = {"INFY": {"open": 1490.0, "high": 1495.0, "low": 1475.0, "close": 1478.0}}
    closed = port.update_open_trades("2026-09-02 09:40:00", quotes)

    assert len(closed) == 1
    assert closed[0].exit_reason == "SL_HIT"
    assert closed[0].net_pnl < 0
    assert port.capital < 100000.0


def test_charges_breakdown_in_portfolio():
    port = Portfolio(initial_capital=100000.0)

    trade = port.open_trade(
        symbol="TCS",
        security_id=11536,
        side=OrderSide.BUY,
        price=3500.0,
        qty=10,
        sl=3450.0,
        target=3600.0,
        entry_time="2026-09-02 09:35:00"
    )
    assert "entry_charges" in trade.metadata
    assert trade.metadata["entry_charges"]["brokerage"] > 0

    quotes = {"TCS": {"open": 3550.0, "high": 3610.0, "low": 3540.0, "close": 3605.0}}
    closed = port.update_open_trades("2026-09-02 09:45:00", quotes)

    assert len(closed) == 1
    cb = closed[0].metadata.get("charges_breakdown", {})
    assert "brokerage" in cb
    assert "stt" in cb
    assert "exchange_fee" in cb
    assert "gst" in cb
    assert "sebi" in cb
    assert "stamp_duty" in cb
    assert cb["total"] > 0
    assert cb["total"] == closed[0].charges
