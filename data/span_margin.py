"""
data/span_margin.py — Dynamic SPAN & Exposure Margin Calculator.

Calculates estimated margin requirements for Equity (MIS / CNC), Futures,
and Option writing / buying in Indian markets (NSE).
"""

import math
from typing import Optional, Union
from execution.order import InstrumentType, OrderSide
from data.instrument_master import InstrumentMaster


class SpanMarginCalculator:
    """
    NSE-style dynamic SPAN and Exposure margin estimator.
    """
    FUTURES_MARGIN_PCT = 0.22         # SPAN + Exposure ~20-25%
    SHORT_OPTION_BASE_PCT = 0.18      # Base underlying notional exposure ~18%
    EQUITY_INTRADAY_MARGIN_PCT = 0.20 # MIS margin ~20% (5x leverage)
    EQUITY_CNC_MARGIN_PCT = 1.0       # CNC delivery margin 100%

    @classmethod
    def estimate_margin(
        cls,
        symbol: str,
        instrument_type: Union[InstrumentType, str],
        side: Union[OrderSide, str],
        price: float,
        qty: int,
        underlying_price: Optional[float] = None,
        trade_date: Optional[str] = None,
        is_intraday: bool = True
    ) -> float:
        """
        Estimates total required margin in INR for a position.
        """
        if isinstance(instrument_type, str):
            try:
                instrument_type = InstrumentType(instrument_type)
            except ValueError:
                instrument_type = InstrumentType.EQUITY
        if isinstance(side, str):
            try:
                side = OrderSide(side.upper())
            except ValueError:
                side = OrderSide.BUY

        if qty <= 0 or price <= 0:
            return 0.0

        notional_value = price * qty

        # 1. Equity Cash / MIS
        if instrument_type == InstrumentType.EQUITY:
            margin_pct = cls.EQUITY_INTRADAY_MARGIN_PCT if is_intraday else cls.EQUITY_CNC_MARGIN_PCT
            return round(notional_value * margin_pct, 2)

        # 2. Futures
        elif instrument_type == InstrumentType.FUTURES:
            return round(notional_value * cls.FUTURES_MARGIN_PCT, 2)

        # 3. Options
        elif instrument_type in (InstrumentType.OPTION_CE, InstrumentType.OPTION_PE):
            if side == OrderSide.BUY:
                # Option Buyer pays 100% of premium
                return round(notional_value, 2)
            else:
                # Option Seller: SPAN + Exposure on underlying notional + premium buffer
                und_price = underlying_price if underlying_price and underlying_price > 0 else price
                und_notional = und_price * qty
                span_exposure = und_notional * cls.SHORT_OPTION_BASE_PCT
                return round(span_exposure + notional_value, 2)

        return round(notional_value, 2)


def estimate_span_margin(
    symbol: str,
    instrument_type: Union[InstrumentType, str] = InstrumentType.FUTURES,
    lots: int = 1,
    lot_size: Optional[int] = None,
    side: Union[OrderSide, str] = OrderSide.BUY,
    price: float = 100.0,
    underlying_price: Optional[float] = None,
    trade_date: Optional[str] = None,
    is_intraday: bool = True
) -> float:
    """
    Convenience helper to estimate total margin for a given number of lots.
    """
    if lot_size is None or lot_size <= 0:
        lot_size = InstrumentMaster.get_lot_size(symbol, trade_date, is_derivative=True)
    qty = lots * lot_size
    return SpanMarginCalculator.estimate_margin(
        symbol=symbol,
        instrument_type=instrument_type,
        side=side,
        price=price,
        qty=qty,
        underlying_price=underlying_price,
        trade_date=trade_date,
        is_intraday=is_intraday
    )
