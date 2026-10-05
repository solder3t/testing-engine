"""
execution/simulator.py — Realistic Execution Simulator with Depth-Walk, Slippage & Statutory Taxes.
"""

from typing import Any, Dict, Optional, Union
import math
import config
from execution.order import OrderSide, InstrumentType


class ExecutionSimulator:
    """Simulates market fills, L2 depth book walking, slippage, and exact Indian statutory taxes."""

    def __init__(
        self,
        slippage_pct: float = config.DEFAULT_SLIPPAGE_PCT,
        slippage_model: str = config.SLIPPAGE_MODEL,
        fixed_ticks: int = config.FIXED_SLIPPAGE_TICKS,
        enable_depth_slippage: bool = config.ENABLE_DEPTH_SLIPPAGE,
        latency_ms: int = config.LATENCY_MS
    ):
        self.slippage_pct = slippage_pct
        self.slippage_model = slippage_model
        self.fixed_ticks = fixed_ticks
        self.enable_depth_slippage = enable_depth_slippage
        self.latency_ms = latency_ms

    def calculate_depth_walk_fill(
        self,
        side: OrderSide,
        qty: int,
        depth_row: Dict[str, Any],
        fallback_price: float
    ) -> float:
        """
        Simulates walking the Level 2/3 order book up to the requested quantity.
        Uses depth columns: ask_p1..20, ask_q1..20 for BUY; bid_p1..20, bid_q1..20 for SELL.
        """
        if qty <= 0:
            return fallback_price

        needed_qty = qty
        total_spent = 0.0
        prefix = "ask" if side == OrderSide.BUY else "bid"

        for i in range(1, 21):
            p_key = f"{prefix}_p{i}"
            q_key = f"{prefix}_q{i}"
            if p_key not in depth_row or q_key not in depth_row:
                break
            price = depth_row[p_key]
            book_qty = depth_row[q_key]
            if price is None or book_qty is None or price <= 0 or book_qty <= 0:
                continue

            fill_here = min(needed_qty, book_qty)
            total_spent += fill_here * price
            needed_qty -= fill_here

            if needed_qty <= 0:
                break

        if needed_qty > 0:
            # Remainder filled at deepest price + 0.1% penalty
            deepest_price = fallback_price
            penalty = 1.001 if side == OrderSide.BUY else 0.999
            total_spent += needed_qty * (deepest_price * penalty)

        avg_fill = total_spent / qty
        return round(avg_fill, 2)

    def calculate_market_impact_slippage(
        self,
        order_qty: int,
        bar_volume: float,
        atr: float,
        lambda_factor: float = 0.1,
        alpha: float = 0.5
    ) -> float:
        """
        Kyle's Lambda / Almgren-Chriss square-root market impact model.
        Impact = λ · (Order_Qty / Bar_Volume)^α · σ_ATR
        """
        if bar_volume <= 0:
            return round(atr * 0.05, 4) if atr > 0 else 0.0
        participation_ratio = min(1.0, max(0.0, order_qty / bar_volume))
        impact = lambda_factor * (participation_ratio ** alpha) * atr
        return round(impact, 4)

    def calculate_fill_price(
        self,
        side: OrderSide,
        reference_price: Optional[float] = None,
        bid_ask_spread: float = 0.0,
        depth_imbalance: float = 0.0,
        qty: int = 1,
        depth_row: Optional[Dict[str, Any]] = None,
        bar_volume: float = 0.0,
        atr: float = 0.0,
        **kwargs
    ) -> float:
        """
        Determines realistic fill price taking into account slippage model,
        Almgren-Chriss market impact, bid/ask spread, and Level-2 order book depth if available.
        """
        ref_price = reference_price if reference_price is not None else kwargs.get("price", 0.0)
        if ref_price <= 0:
            return ref_price
        reference_price = ref_price

        # Extract bar_volume and atr from kwargs if provided
        b_vol = bar_volume or float(kwargs.get("volume", 0.0))
        atr_val = atr or float(kwargs.get("atr_val", 0.0))

        # 1. Depth-walk if enabled and depth_row present
        if self.enable_depth_slippage and depth_row:
            return self.calculate_depth_walk_fill(side, qty, depth_row, reference_price)

        # 2. Fixed tick slippage model
        if self.slippage_model == "fixed":
            tick_cost = self.fixed_ticks * 0.05
            if side == OrderSide.BUY:
                return round(reference_price + tick_cost, 2)
            else:
                return round(max(0.05, reference_price - tick_cost), 2)

        # 3. Standard percentage + half-spread + market impact slippage model
        spread_cost = (bid_ask_spread / 2.0) if bid_ask_spread > 0 else (reference_price * self.slippage_pct)

        # Market impact if volume and volatility available
        market_impact = 0.0
        if b_vol > 0 and atr_val > 0:
            market_impact = self.calculate_market_impact_slippage(qty, b_vol, atr_val)

        # Depth imbalance penalty
        imbalance_adj = 0.0
        if side == OrderSide.BUY and depth_imbalance < -0.3:
            imbalance_adj = reference_price * 0.0002
        elif side == OrderSide.SELL and depth_imbalance > 0.3:
            imbalance_adj = reference_price * 0.0002

        slippage = spread_cost + market_impact + imbalance_adj

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
        Computes statutory exchange transaction fees, STT, GST, SEBI charges, and Stamp Duty.
        Follows official NSE regulatory circular fee schedule.
        """
        turnover = price * qty
        if turnover <= 0:
            return {
                "brokerage": 0.0, "stt": 0.0, "exchange_fee": 0.0,
                "gst": 0.0, "sebi": 0.0, "stamp_duty": 0.0, "total": 0.0
            }

        # Brokerage (₹20 or 0.05%, whichever is lower)
        brokerage = min(config.BROKERAGE_FLAT_PER_ORDER, round(turnover * 0.0005, 2))

        # STT
        stt = 0.0
        if side == OrderSide.SELL:
            if instrument_type == InstrumentType.EQUITY:
                stt = round(turnover * config.STT_EQUITY_INTRADAY, 2)
            elif instrument_type in (InstrumentType.OPTION_CE, InstrumentType.OPTION_PE):
                stt = round(turnover * config.STT_OPTIONS_TURNOVER, 2)

        # Exchange Txn Fee
        if instrument_type == InstrumentType.EQUITY:
            exchange_fee = round(turnover * config.EXCHANGE_TXN_FEE_EQUITY, 2)
        else:
            exchange_fee = round(turnover * config.EXCHANGE_TXN_FEE_OPTIONS, 2)

        # GST (18% on brokerage + exchange txn fee)
        gst = round((brokerage + exchange_fee) * config.GST_RATE, 2)

        # SEBI Turnover Charges
        sebi = round(turnover * config.SEBI_CHARGES, 2)

        # Stamp Duty (Buy side only)
        stamp_duty = 0.0
        if side == OrderSide.BUY:
            if instrument_type == InstrumentType.EQUITY:
                stamp_duty = round(turnover * config.STAMP_DUTY_EQUITY_BUY, 2)
            else:
                stamp_duty = round(turnover * config.STAMP_DUTY_OPTIONS_BUY, 2)

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

    def calculate_expiry_exercise_charges(
        self,
        settlement_price: float,
        strike_price: float,
        qty: int,
        instrument_type: InstrumentType
    ) -> Dict[str, float]:
        """
        Computes statutory charges for options exercised at expiry.
        Under Indian tax law, STT on exercised ITM options is 0.125% on INTRINSIC VALUE.
        """
        intrinsic_per_unit = 0.0
        if instrument_type == InstrumentType.OPTION_CE:
            intrinsic_per_unit = max(0.0, settlement_price - strike_price)
        elif instrument_type == InstrumentType.OPTION_PE:
            intrinsic_per_unit = max(0.0, strike_price - settlement_price)

        total_intrinsic = intrinsic_per_unit * qty
        if total_intrinsic <= 0:
            return {"brokerage": 0.0, "stt": 0.0, "exchange_fee": 0.0, "gst": 0.0, "sebi": 0.0, "stamp_duty": 0.0, "total": 0.0}

        stt = round(total_intrinsic * config.STT_OPTIONS_EXERCISE, 2)
        brokerage = config.BROKERAGE_FLAT_PER_ORDER
        gst = round(brokerage * config.GST_RATE, 2)
        total = round(stt + brokerage + gst, 2)

        return {
            "brokerage": brokerage,
            "stt": stt,
            "exchange_fee": 0.0,
            "gst": gst,
            "sebi": 0.0,
            "stamp_duty": 0.0,
            "total": total
        }
