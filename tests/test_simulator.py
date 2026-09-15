"""
tests/test_simulator.py — Tests for ExecutionSimulator and regulatory fees.
"""

import pytest
from execution.order import OrderSide, InstrumentType
from execution.simulator import ExecutionSimulator


def test_fill_price_slippage():
    sim = ExecutionSimulator(slippage_pct=0.001)

    # Buy with positive slippage
    fill_buy = sim.calculate_fill_price(OrderSide.BUY, reference_price=1000.0)
    assert fill_buy > 1000.0

    # Sell with negative slippage
    fill_sell = sim.calculate_fill_price(OrderSide.SELL, reference_price=1000.0)
    assert fill_sell < 1000.0


def test_charges_calculation_equity():
    sim = ExecutionSimulator()

    # Buy 100 shares @ 1000
    buy_charges = sim.calculate_charges(OrderSide.BUY, price=1000.0, qty=100, instrument_type=InstrumentType.EQUITY)
    assert buy_charges["brokerage"] == 20.0
    assert buy_charges["stt"] == 0.0  # No STT on intraday buy
    assert buy_charges["stamp_duty"] > 0
    assert buy_charges["gst"] > 0
    assert buy_charges["total"] > 0

    # Sell 100 shares @ 1020
    sell_charges = sim.calculate_charges(OrderSide.SELL, price=1020.0, qty=100, instrument_type=InstrumentType.EQUITY)
    assert sell_charges["stt"] > 0  # STT applies on sell side
    assert sell_charges["stamp_duty"] == 0.0


def test_charges_calculation_options():
    sim = ExecutionSimulator()

    # Buy 500 options @ 100
    charges = sim.calculate_charges(OrderSide.BUY, price=100.0, qty=500, instrument_type=InstrumentType.OPTION_CE)
    assert charges["total"] > 0
    assert charges["brokerage"] == 20.0
