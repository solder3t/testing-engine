"""
execution/portfolio.py — Portfolio Manager, Position Sizing & Risk Controls.
"""

from typing import List, Dict, Optional
import math

from config import (
    DEFAULT_CAPITAL,
    DEFAULT_RISK_PCT_PER_TRADE,
    MAX_POSITIONS,
    MAX_POSITIONS_PER_SECTOR,
    MAX_QTY_PER_TRADE,
    FORCE_SQUARE_OFF_TIME
)
from execution.order import OrderSide, InstrumentType, Trade
from execution.simulator import ExecutionSimulator


class Portfolio:
    """Tracks capital, active positions, trailing stop-losses, and performance."""

    def __init__(
        self,
        initial_capital: float = DEFAULT_CAPITAL,
        risk_pct_per_trade: float = DEFAULT_RISK_PCT_PER_TRADE,
        simulator: Optional[ExecutionSimulator] = None
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_pct_per_trade = risk_pct_per_trade
        self.simulator = simulator or ExecutionSimulator()

        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        self.daily_pnl: float = 0.0

    def can_open_trade(self, symbol: str, sector: str = "") -> tuple[bool, str]:
        """Check portfolio capacity and sector concentration limits."""
        if len(self.open_trades) >= MAX_POSITIONS:
            return False, f"Max positions reached ({MAX_POSITIONS})"

        # Check if already in trade on this symbol
        if any(t.symbol == symbol for t in self.open_trades):
            return False, f"Already holding position in {symbol}"

        # Sector concentration check
        if sector and sector != "Other" and sector != "Index":
            sector_count = sum(1 for t in self.open_trades if t.metadata.get("sector") == sector)
            if sector_count >= MAX_POSITIONS_PER_SECTOR:
                return False, f"Sector limit reached for {sector} ({MAX_POSITIONS_PER_SECTOR})"

        return True, "OK"

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        score: int = 70,
        lot_size: int = 1
    ) -> int:
        """
        Calculates position size strictly bounded by risk-per-trade.
        """
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return lot_size

        risk_capital = self.capital * self.risk_pct_per_trade

        # Score scaling
        if score >= 80:
            risk_capital *= 1.5
        elif score < 60:
            risk_capital *= 0.5

        raw_qty = risk_capital / risk_per_unit

        # Lot size normalization
        lots = max(1, math.floor(raw_qty / lot_size))
        qty = lots * lot_size
        return max(lot_size, min(qty, MAX_QTY_PER_TRADE))

    def open_trade(
        self,
        symbol: str,
        security_id: int,
        side: OrderSide,
        price: float,
        qty: int,
        sl: float,
        target: float,
        entry_time: str,
        instrument_type: InstrumentType = InstrumentType.EQUITY,
        metadata: Optional[Dict] = None,
        bid_ask_spread: float = 0.0
    ) -> Optional[Trade]:
        """Opens a new trade, applying slippage and entry charges."""
        can_open, reason = self.can_open_trade(symbol, metadata.get("sector", "") if metadata else "")
        if not can_open:
            return None

        fill_price = self.simulator.calculate_fill_price(
            side=side,
            reference_price=price,
            bid_ask_spread=bid_ask_spread
        )

        entry_charges_dict = self.simulator.calculate_charges(
            side=side,
            price=fill_price,
            qty=qty,
            instrument_type=instrument_type
        )
        entry_charges = entry_charges_dict["total"]

        trade_meta = dict(metadata or {})
        trade_meta["entry_charges"] = entry_charges_dict

        trade = Trade(
            symbol=symbol,
            security_id=security_id,
            side=side,
            qty=qty,
            entry_time=entry_time,
            entry_price=fill_price,
            initial_sl=sl,
            current_sl=sl,
            target=target,
            instrument_type=instrument_type,
            charges=entry_charges,
            metadata=trade_meta
        )

        self.open_trades.append(trade)
        return trade

    def _finalize_trade_charges(self, trade: Trade, exit_charges_dict: Dict[str, float]):
        entry_dict = trade.metadata.get("entry_charges", {})
        combined = {
            "brokerage": round(entry_dict.get("brokerage", 0.0) + exit_charges_dict.get("brokerage", 0.0), 2),
            "stt": round(entry_dict.get("stt", 0.0) + exit_charges_dict.get("stt", 0.0), 2),
            "exchange_fee": round(entry_dict.get("exchange_fee", 0.0) + exit_charges_dict.get("exchange_fee", 0.0), 2),
            "gst": round(entry_dict.get("gst", 0.0) + exit_charges_dict.get("gst", 0.0), 2),
            "sebi": round(entry_dict.get("sebi", 0.0) + exit_charges_dict.get("sebi", 0.0), 2),
            "stamp_duty": round(entry_dict.get("stamp_duty", 0.0) + exit_charges_dict.get("stamp_duty", 0.0), 2),
            "total": round(entry_dict.get("total", 0.0) + exit_charges_dict.get("total", 0.0), 2),
        }
        trade.metadata["exit_charges"] = exit_charges_dict
        trade.metadata["charges_breakdown"] = combined

    def update_open_trades(
        self,
        timestamp: str,
        symbol_quotes: Dict[str, Dict]
    ) -> List[Trade]:
        """
        Evaluates open trades against latest high/low/close prices.
        Checks for Target hit, Stop-Loss hit, and updates breakeven/trailing stops.
        Returns list of trades closed during this step.
        """
        just_closed = []
        remaining = []

        is_eod = False
        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        if time_part >= FORCE_SQUARE_OFF_TIME:
            is_eod = True

        for trade in self.open_trades:
            trade.holding_bars += 1
            quote = symbol_quotes.get(trade.symbol)
            if not quote:
                remaining.append(trade)
                continue

            curr_close = quote.get("close", quote.get("ltp", trade.entry_price))
            curr_high = quote.get("high", curr_close)
            curr_low = quote.get("low", curr_close)
            spread = quote.get("bid_ask_spread", 0.0)

            # ── Check EOD Force Close ─────────────────────────────────────────
            if is_eod:
                exit_price = self.simulator.calculate_fill_price(
                    side=OrderSide.SELL if trade.side == OrderSide.BUY else OrderSide.BUY,
                    reference_price=curr_close,
                    bid_ask_spread=spread
                )
                exit_charges_dict = self.simulator.calculate_charges(
                    side=OrderSide.SELL if trade.side == OrderSide.BUY else OrderSide.BUY,
                    price=exit_price,
                    qty=trade.qty,
                    instrument_type=trade.instrument_type
                )
                exit_charges = exit_charges_dict["total"]
                self._finalize_trade_charges(trade, exit_charges_dict)
                trade.close(
                    exit_time=timestamp,
                    exit_price=exit_price,
                    reason="EOD_SQUAREOFF",
                    charges=trade.charges + exit_charges
                )
                self.capital += trade.net_pnl
                self.daily_pnl += trade.net_pnl
                self.closed_trades.append(trade)
                just_closed.append(trade)
                continue

            # ── Check Target and SL Hits ──────────────────────────────────────
            closed = False
            if trade.side == OrderSide.BUY:
                # 1. Target Hit
                if curr_high >= trade.target:
                    exit_price = trade.target
                    exit_charges_dict = self.simulator.calculate_charges(
                        OrderSide.SELL, exit_price, trade.qty, trade.instrument_type
                    )
                    exit_charges = exit_charges_dict["total"]
                    self._finalize_trade_charges(trade, exit_charges_dict)
                    trade.close(timestamp, exit_price, "TARGET_HIT", trade.charges + exit_charges)
                    closed = True
                # 2. Stop Loss Hit
                elif curr_low <= trade.current_sl:
                    exit_price = trade.current_sl
                    exit_charges_dict = self.simulator.calculate_charges(
                        OrderSide.SELL, exit_price, trade.qty, trade.instrument_type
                    )
                    exit_charges = exit_charges_dict["total"]
                    self._finalize_trade_charges(trade, exit_charges_dict)
                    trade.close(timestamp, exit_price, "SL_HIT", trade.charges + exit_charges)
                    closed = True
                # 3. Trailing / Breakeven SL Update
                else:
                    initial_risk = trade.entry_price - trade.initial_sl
                    if initial_risk > 0 and (curr_close - trade.entry_price) >= initial_risk:
                        # Move SL to breakeven
                        if trade.current_sl < trade.entry_price:
                            trade.current_sl = trade.entry_price
                            trade.trailing_sl = trade.entry_price

            else:  # SELL
                # 1. Target Hit
                if curr_low <= trade.target:
                    exit_price = trade.target
                    exit_charges_dict = self.simulator.calculate_charges(
                        OrderSide.BUY, exit_price, trade.qty, trade.instrument_type
                    )
                    exit_charges = exit_charges_dict["total"]
                    self._finalize_trade_charges(trade, exit_charges_dict)
                    trade.close(timestamp, exit_price, "TARGET_HIT", trade.charges + exit_charges)
                    closed = True
                # 2. Stop Loss Hit
                elif curr_high >= trade.current_sl:
                    exit_price = trade.current_sl
                    exit_charges_dict = self.simulator.calculate_charges(
                        OrderSide.BUY, exit_price, trade.qty, trade.instrument_type
                    )
                    exit_charges = exit_charges_dict["total"]
                    self._finalize_trade_charges(trade, exit_charges_dict)
                    trade.close(timestamp, exit_price, "SL_HIT", trade.charges + exit_charges)
                    closed = True
                # 3. Trailing / Breakeven SL Update
                else:
                    initial_risk = trade.initial_sl - trade.entry_price
                    if initial_risk > 0 and (trade.entry_price - curr_close) >= initial_risk:
                        if trade.current_sl > trade.entry_price:
                            trade.current_sl = trade.entry_price
                            trade.trailing_sl = trade.entry_price

            if closed:
                self.capital += trade.net_pnl
                self.daily_pnl += trade.net_pnl
                self.closed_trades.append(trade)
                just_closed.append(trade)
            else:
                remaining.append(trade)

        self.open_trades = remaining
        return just_closed

    def record_equity_point(self, timestamp: str, symbol_quotes: Dict[str, Dict]):
        """Records current portfolio equity snapshot."""
        unrealized = 0.0
        for trade in self.open_trades:
            quote = symbol_quotes.get(trade.symbol)
            if quote:
                curr_price = quote.get("close", quote.get("ltp", trade.entry_price))
                if trade.side == OrderSide.BUY:
                    unrealized += (curr_price - trade.entry_price) * trade.qty
                else:
                    unrealized += (trade.entry_price - curr_price) * trade.qty

        current_equity = round(self.capital + unrealized, 2)
        self.equity_curve.append({
            "timestamp": timestamp,
            "equity": current_equity,
            "cash": round(self.capital, 2),
            "open_positions": len(self.open_trades),
            "unrealized_pnl": round(unrealized, 2)
        })
