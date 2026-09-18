"""
execution/simulator.py — Realistic Execution Simulator with Slippage and Statutory Fees.
"""

from typing import Dict, Optional
import math
from config import (
    BROKERAGE_FLAT_PER_ORDER,
    STT_EQUITY_INTRADAY,
    STT_OPTIONS_TURNOVER,
    EXCHANGE_TXN_FEE_EQUITY,
    EXCHANGE_TXN_FEE_OPTIONS,
    GST_RATE,
    SEBI_CHARGES,
    STAMP_DUTY_EQUITY_BUY,
    STAMP_DUTY_OPTIONS_BUY,
    DEFAULT_SLIPPAGE_PCT
)
from execution.order import OrderSide, InstrumentType


class ExecutionSimulator:
    """Simulates market fills, slippage, and exact Indian regulatory charges."""

    def __init__(self, slippage_pct: float = DEFAULT_SLIPPAGE_PCT):
        self.slippage_pct = slippage_pct

    def calculate_fill_price(
        self,
        side: OrderSide,
        reference_price: float,
        bid_ask_spread: float = 0.0,
        depth_imbalance: float = 0.0,
        bar_range_pct: float = 0.0
    ) -> float:
        """
        Determines the realistic fill price taking into account bid/ask spread,
        depth imbalance, and candle volatility.
        """
        if reference_price <= 0:
            return reference_price

        # Half-spread cost if spread is recorded, otherwise baseline slippage
        spread_cost = (bid_ask_spread / 2.0) if bid_ask_spread > 0 else (reference_price * self.slippage_pct)

        # Depth imbalance penalty: if buying into heavy ask pressure
        imbalance_adj = 0.0
        if side == OrderSide.BUY and depth_imbalance < -0.3:
            imbalance_adj = reference_price * 0.0002
        elif side == OrderSide.SELL and depth_imbalance > 0.3:
            imbalance_adj = reference_price * 0.0002

        # Volatility expansion: if candle range (high - low) / close exceeds normal 0.5% threshold
        volatility_adj = 0.0
        if bar_range_pct > 0.005:
            # Scale extra slippage up to a max cap of 0.2% during severe volatility
            volatility_adj = reference_price * min(0.002, (bar_range_pct - 0.005) * 0.2)

        slippage = spread_cost + imbalance_adj + volatility_adj

        if side == OrderSide.BUY:
            return round(reference_price + slippage, 2)
        else:
            return round(max(0.05, reference_price - slippage), 2)

    def calculate_charges(
        self,
        side: OrderSide,
        price: float,
        qty: int,
        instrument_type: InstrumentType = InstrumentType.EQUITY
    ) -> Dict[str, float]:
        """
        Computes statutory exchange transaction fees, STT, GST, and SEBI charges.
        Follows official NSE circular fee structure.
        """
        turnover = price * qty
        if turnover <= 0:
            return {
                "brokerage": 0.0, "stt": 0.0, "exchange_fee": 0.0,
                "gst": 0.0, "sebi": 0.0, "stamp_duty": 0.0, "total": 0.0
            }

        # Brokerage (₹20 or 0.05%, whichever is lower)
        brokerage = min(BROKERAGE_FLAT_PER_ORDER, round(turnover * 0.0005, 2))

        # STT
        stt = 0.0
        if side == OrderSide.SELL:
            if instrument_type == InstrumentType.EQUITY:
                stt = round(turnover * STT_EQUITY_INTRADAY, 2)
            elif instrument_type in (InstrumentType.OPTION_CE, InstrumentType.OPTION_PE):
                stt = round(turnover * STT_OPTIONS_TURNOVER, 2)

        # Exchange Txn Fee
        if instrument_type == InstrumentType.EQUITY:
            exchange_fee = round(turnover * EXCHANGE_TXN_FEE_EQUITY, 2)
        else:
            exchange_fee = round(turnover * EXCHANGE_TXN_FEE_OPTIONS, 2)

        # GST (18% on brokerage + exchange txn fee)
        gst = round((brokerage + exchange_fee) * GST_RATE, 2)

        # SEBI Turnover Charges
        sebi = round(turnover * SEBI_CHARGES, 2)

        # Stamp Duty (Buy side only)
        stamp_duty = 0.0
        if side == OrderSide.BUY:
            if instrument_type == InstrumentType.EQUITY:
                stamp_duty = round(turnover * STAMP_DUTY_EQUITY_BUY, 2)
            else:
                stamp_duty = round(turnover * STAMP_DUTY_OPTIONS_BUY, 2)

        total = round(brokerage + stt + exchange_fee + gst + sebi + stamp_duty, 2)

        return {
            "brokerage": brokerage,
            "stt": stt,
            "exchange_fee": exchange_fee,
            "gst": gst,
            "sebi": sebi,
            "stamp_duty": stamp_duty,
            "total": total
        }
