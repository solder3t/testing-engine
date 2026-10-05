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


def test_portfolio_sector_and_correlation_limits():
    port = Portfolio(initial_capital=100000.0)

    # 1. Sector Concentration Limit (MAX_SECTOR_EXPOSURE_PCT = 0.35 -> max 35,000 INR)
    # Opening 30,000 INR of IT sector is OK (30%)
    t1 = port.open_trade(
        symbol="INFY",
        security_id=1,
        side=OrderSide.BUY,
        price=1000.0,
        qty=30,
        sl=950.0,
        target=1100.0,
        entry_time="2026-09-02 09:30:00",
        metadata={"sector": "Information Technology"}
    )
    assert t1 is not None
    assert len(port.open_trades) == 1

    # Attempting another 10,000 INR in IT would make 40,000 INR (40% > 35%) -> Blocked!
    t2 = port.open_trade(
        symbol="TCS",
        security_id=2,
        side=OrderSide.BUY,
        price=1000.0,
        qty=10,
        sl=950.0,
        target=1100.0,
        entry_time="2026-09-02 09:31:00",
        metadata={"sector": "Information Technology"}
    )
    assert t2 is None
    assert len(port.open_trades) == 1


def test_span_margin_tracking_and_release():
    port = Portfolio(initial_capital=100000.0)
    assert port.blocked_margin == 0.0

    # Open a futures trade (Futures margin ~22% of notional)
    # Notional = 20,000 * 25 = 500,000. Margin ~ 110,000.
    # Let's open 1 lot of 10 qty at 1000 = 10,000 notional -> margin ~ 2,200
    trade = port.open_trade(
        symbol="NIFTY",
        security_id=100,
        side=OrderSide.BUY,
        price=1000.0,
        qty=10,
        sl=980.0,
        target=1040.0,
        entry_time="2026-09-02 09:30:00",
        instrument_type=InstrumentType.FUTURES
    )
    assert trade is not None
    assert "margin_blocked" in trade.metadata
    blocked = trade.metadata["margin_blocked"]
    assert blocked > 0
    assert port.blocked_margin == blocked

    # Close trade and verify margin is released
    quotes = {"NIFTY": {"open": 1020.0, "high": 1045.0, "low": 1015.0, "close": 1042.0}}
    closed = port.update_open_trades("2026-09-02 09:40:00", quotes)

    assert len(closed) == 1
    assert closed[0].metadata.get("margin_freed") == blocked
    assert port.blocked_margin == 0.0

