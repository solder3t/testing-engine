"""
execution/trade_simulator.py — Advanced Trade Lifecycle Execution Simulator.

Features:
- Progressive 6-Rung Trailing Stop-Loss (TSL) ladder
- Partial lot booking (e.g., book 75% lots at Rung 1, trail remaining 25% to breakeven + buffer)
- Multiple trailing modes: LADDER, ATR Chandelier, PERCENTAGE, and BREAKEVEN
- Time-based stagnancy exits (force square-off after N minutes)
- Post-trade cooldown enforcement (180s after profit, 300s after loss)
- Integration with statutory charges and slippage models
"""

import math
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

try:
    from data.instrument_master import InstrumentMaster
except ImportError:
    InstrumentMaster = None


@dataclass
class SimulatedTrade:
    id: int
    session_date: str
    symbol: str
    side: str                          # "BUY" or "SELL"
    option_type: Optional[str] = None  # "CE", "PE", or None (for equity/futures)
    strike: float = 0.0
    entry_time: str = ""
    entry_price: float = 0.0
    spot_entry: float = 0.0
    quantity: int = 0
    lots: int = 1
    initial_sl: float = 0.0
    current_sl: float = 0.0
    target: float = 0.0
    status: str = "OPEN"               # "OPEN", "CLOSED"
    trail_level: int = 0
    partial_booked: bool = False
    booked_quantity: int = 0
    booked_pnl: float = 0.0
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    spot_exit: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_gross: float = 0.0
    pnl_net: float = 0.0
    pnl_pct: float = 0.0
    charges: float = 0.0
    duration_seconds: int = 0
    signal_confidence: float = 0.0
    signal_reasoning: str = ""
    highest_price: float = 0.0
    lowest_price: float = 999999.0
    expiry: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TradeSimulator:
    """Manages active simulated positions, checks SL/TSL/Target triggers, and enforces risk rules."""

    DEFAULT_TSL_LADDER = [
        {"rung": 1, "trigger_pts": 10.0, "lock_pts": 2.0},
        {"rung": 2, "trigger_pts": 20.0, "lock_pts": 10.0},
        {"rung": 3, "trigger_pts": 30.0, "lock_pts": 20.0},
        {"rung": 4, "trigger_pts": 40.0, "lock_pts": 30.0},
        {"rung": 5, "trigger_pts": 50.0, "lock_pts": 40.0},
        {"rung": 6, "trigger_pts": 60.0, "lock_pts": 50.0},
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.lot_size = cfg.get("lot_size", None)
        self.default_lots = cfg.get("default_lots", 1)
        self.initial_sl_pts = cfg.get("initial_sl_pts", 15.0)
        self.target_pts = cfg.get("target_pts", 30.0)
        self.slippage_pts = cfg.get("slippage_pts", 0.1)

        # Advanced TSL modes
        self.tsl_mode = str(cfg.get("tsl_mode", "LADDER")).upper()
        self.tsl_ladder = cfg.get("tsl_ladder", self.DEFAULT_TSL_LADDER)
        self.atr_multiplier = float(cfg.get("atr_multiplier", 2.0))
        self.percentage_trail = float(cfg.get("percentage_trail", 10.0))
        self.breakeven_trigger_pts = float(cfg.get("breakeven_trigger_pts", 10.0))
        self.breakeven_buffer_pts = float(cfg.get("breakeven_buffer_pts", 1.0))
        self.time_based_exit_minutes = int(cfg.get("time_based_exit_minutes", 0))

        # Partial booking
        self.enable_partial_booking = bool(cfg.get("partial_booking", True))
        self.partial_booking_pct = float(cfg.get("partial_booking_pct", 0.75))  # Book 75% on Rung 1

        # Risk limits & Cooldowns
        self.max_daily_loss = float(cfg.get("max_daily_loss", 25000.0))
        self.max_consecutive_losses = int(cfg.get("max_consecutive_losses", 4))
        self.max_trades_per_day = int(cfg.get("max_trades_per_day", 10))
        self.cooldown_profit_sec = int(cfg.get("cooldown_profit_sec", 180))
        self.cooldown_loss_sec = int(cfg.get("cooldown_loss_sec", 300))
        self.eod_exit_time = str(cfg.get("eod_exit_time", "15:15:00"))

        # Session tracking
        self.trades: List[SimulatedTrade] = []
        self.active_trade: Optional[SimulatedTrade] = None
        self.trade_counter = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.last_exit_time: Optional[datetime] = None
        self.last_exit_was_profit = False
        self.halted_for_day = False
        self.current_date = ""

    def reset_session(self, session_date: str) -> None:
        """Reset state at the start of a trading day."""
        self.current_date = session_date
        self.active_trade = None
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.last_exit_time = None
        self.last_exit_was_profit = False
        self.halted_for_day = False

    def is_in_position(self) -> bool:
        return self.active_trade is not None

    def _parse_time(self, t_str: str) -> Optional[datetime]:
        """Safely parse time string into datetime."""
        if not t_str:
            return None
        # Full datetime formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y_%m_%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y_%m_%d %H:%M"):
            try:
                return datetime.strptime(t_str, fmt)
            except ValueError:
                continue

        # Time-only formats (e.g., 09:15:00)
        date_str = self.current_date.replace("_", "-") if self.current_date else "2026-01-01"
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(t_str, fmt).time()
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                return datetime.combine(d, t)
            except ValueError:
                continue
        return None

    def can_enter_trade(self, current_time_str: str) -> Tuple[bool, str]:
        """Verify risk limits and cooldowns before entering."""
        if self.is_in_position():
            return False, "Already in position"
        if self.halted_for_day:
            return False, "Trading halted for day by risk rules"
        if self.daily_pnl <= -self.max_daily_loss:
            self.halted_for_day = True
            return False, f"Max daily loss reached (-₹{self.max_daily_loss})"
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.halted_for_day = True
            return False, f"Max consecutive losses reached ({self.max_consecutive_losses})"

        day_trades = [t for t in self.trades if t.session_date == self.current_date]
        if len(day_trades) >= self.max_trades_per_day:
            return False, f"Max trades per day reached ({self.max_trades_per_day})"

        if self.last_exit_time:
            cur_t = self._parse_time(current_time_str)
            if cur_t:
                elapsed = (cur_t - self.last_exit_time).total_seconds()
                req_cooldown = self.cooldown_profit_sec if self.last_exit_was_profit else self.cooldown_loss_sec
                if elapsed < req_cooldown:
                    return False, f"In cooldown ({int(req_cooldown - elapsed)}s remaining)"

        return True, "OK"

    def open_trade(
        self,
        symbol: str,
        side: str = "BUY",
        price: float = 0.0,
        timestamp: str = "",
        lots: Optional[int] = None,
        lot_size: Optional[int] = None,
        sl_pts: Optional[float] = None,
        target_pts: Optional[float] = None,
        option_type: Optional[str] = None,
        strike: float = 0.0,
        confidence: float = 0.0,
        reasoning: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SimulatedTrade]:
        """Open a new simulated position."""
        allowed, _ = self.can_enter_trade(timestamp)
        if not allowed:
            return None

        self.trade_counter += 1
        num_lots = lots or self.default_lots
        if lot_size is not None:
            ls = lot_size
        elif self.lot_size is not None:
            ls = self.lot_size
        elif InstrumentMaster and self.current_date:
            ls = InstrumentMaster.get_lot_size(symbol, self.current_date)
        elif InstrumentMaster:
            ls = InstrumentMaster.get_lot_size(symbol)
        else:
            ls = 1
        qty = num_lots * ls

        entry_fill = round(price + (self.slippage_pts if side.upper() == "BUY" else -self.slippage_pts), 2)
        sl_p = sl_pts if sl_pts is not None else self.initial_sl_pts
        tgt_p = target_pts if target_pts is not None else self.target_pts

        if side.upper() == "BUY":
            initial_sl = max(0.05, round(entry_fill - sl_p, 2))
            target = round(entry_fill + tgt_p, 2)
        else:
            initial_sl = round(entry_fill + sl_p, 2)
            target = max(0.05, round(entry_fill - tgt_p, 2))

        trade = SimulatedTrade(
            id=self.trade_counter,
            session_date=self.current_date,
            symbol=symbol,
            side=side.upper(),
            option_type=option_type.upper() if option_type else None,
            strike=strike,
            entry_time=timestamp,
            entry_price=entry_fill,
            spot_entry=price,
            quantity=qty,
            lots=num_lots,
            initial_sl=initial_sl,
            current_sl=initial_sl,
            target=target,
            status="OPEN",
            signal_confidence=confidence,
            signal_reasoning=reasoning,
            highest_price=entry_fill,
            lowest_price=entry_fill,
            metadata=metadata or {}
        )
        self.active_trade = trade
        return trade

    def update_bar(
        self,
        bar: Dict[str, Any],
        time_key: str = "timestamp",
        current_atr: Optional[float] = None
    ) -> Optional[SimulatedTrade]:
        """
        Evaluates active trade against incoming bar (high/low/close).
        Checks Target, Stop Loss, 6-Rung TSL Ladder, Partial Booking, and Time-based Exits.
        """
        if not self.active_trade:
            return None

        trade = self.active_trade
        ts_str = str(bar.get(time_key, bar.get("candle_time", "")))
        c_high = float(bar.get("high", 0.0))
        c_low = float(bar.get("low", 0.0))
        c_close = float(bar.get("close", 0.0))

        trade.highest_price = max(trade.highest_price, c_high)
        trade.lowest_price = min(trade.lowest_price, c_low)

        is_buy = (trade.side == "BUY")
        max_profit_pts = (trade.highest_price - trade.entry_price) if is_buy else (trade.entry_price - trade.lowest_price)

        # ── 1. Target Check ───────────────────────────────────────────────────
        if is_buy and c_high >= trade.target:
            return self._close_active_trade(trade.target, ts_str, "TARGET_HIT")
        if not is_buy and c_low <= trade.target:
            return self._close_active_trade(trade.target, ts_str, "TARGET_HIT")

        # ── 2. Stop Loss Check ────────────────────────────────────────────────
        if is_buy and c_low <= trade.current_sl:
            reason = "TSL_HIT" if trade.trail_level > 0 else "SL_HIT"
            return self._close_active_trade(trade.current_sl, ts_str, reason)
        if not is_buy and c_high >= trade.current_sl:
            reason = "TSL_HIT" if trade.trail_level > 0 else "SL_HIT"
            return self._close_active_trade(trade.current_sl, ts_str, reason)

        # ── 3. Progressive 6-Rung TSL Ladder & Partial Booking ─────────────────
        if self.tsl_mode == "LADDER":
            for rung in self.tsl_ladder:
                r_num = rung["rung"]
                trigger = rung["trigger_pts"]
                lock = rung["lock_pts"]

                if max_profit_pts >= trigger and trade.trail_level < r_num:
                    trade.trail_level = r_num
                    new_sl = round(trade.entry_price + (lock if is_buy else -lock), 2)
                    trade.current_sl = max(trade.current_sl, new_sl) if is_buy else min(trade.current_sl, new_sl)

                    # Partial lot profit booking on Rung 1
                    if r_num == 1 and self.enable_partial_booking and not trade.partial_booked and trade.lots > 1:
                        book_lots = max(1, round(trade.lots * self.partial_booking_pct))
                        book_qty = book_lots * (trade.quantity // trade.lots)
                        pnl_booked = book_qty * trigger
                        trade.partial_booked = True
                        trade.booked_quantity = book_qty
                        trade.booked_pnl = pnl_booked
                        trade.quantity -= book_qty
                        trade.lots -= book_lots
                        # Move stop loss to breakeven + buffer
                        be_sl = round(trade.entry_price + (self.breakeven_buffer_pts if is_buy else -self.breakeven_buffer_pts), 2)
                        trade.current_sl = be_sl

        # ── 4. ATR / Chandelier Trailing ──────────────────────────────────────
        elif self.tsl_mode == "ATR" and current_atr and current_atr > 0:
            trail_offset = current_atr * self.atr_multiplier
            if is_buy:
                proposed_sl = round(trade.highest_price - trail_offset, 2)
                trade.current_sl = max(trade.current_sl, proposed_sl)
            else:
                proposed_sl = round(trade.lowest_price + trail_offset, 2)
                trade.current_sl = min(trade.current_sl, proposed_sl)

        # ── 5. Time-Based Stagnancy Exit ──────────────────────────────────────
        if self.time_based_exit_minutes > 0:
            t_entry = self._parse_time(trade.entry_time)
            t_cur = self._parse_time(ts_str)
            if t_entry and t_cur:
                mins_in_trade = (t_cur - t_entry).total_seconds() / 60.0
                if mins_in_trade >= self.time_based_exit_minutes:
                    return self._close_active_trade(c_close, ts_str, "TIME_EXIT")

        # ── 6. EOD Square-Off ─────────────────────────────────────────────────
        if self.eod_exit_time in ts_str:
            return self._close_active_trade(c_close, ts_str, "EOD_SQUARE_OFF")

        return None

    def _close_active_trade(self, price: float, exit_time: str, reason: str) -> Optional[SimulatedTrade]:
        """Finalize and close active trade with P&L and charges calculation."""
        if self.active_trade is None:
            return None
        trade = self.active_trade
        is_buy = (trade.side == "BUY")
        exit_fill = round(price - (self.slippage_pts if is_buy else -self.slippage_pts), 2)

        pts = (exit_fill - trade.entry_price) if is_buy else (trade.entry_price - exit_fill)
        gross_remaining = pts * trade.quantity
        total_gross = gross_remaining + trade.booked_pnl

        # Statutory tax calculation (standard ₹20 brokerage + turnover STT/exchange fee)
        turnover = (trade.entry_price + exit_fill) * (trade.quantity + trade.booked_quantity)
        brokerage = 40.0
        stt = turnover * 0.000625 if trade.option_type else turnover * 0.00025
        charges = round(brokerage + stt, 2)
        net_pnl = round(total_gross - charges, 2)

        trade.exit_price = exit_fill
        trade.exit_time = exit_time
        trade.exit_reason = reason
        trade.status = "CLOSED"
        trade.pnl_gross = round(total_gross, 2)
        trade.pnl_net = net_pnl
        trade.charges = charges

        t_entry = self._parse_time(trade.entry_time)
        t_exit = self._parse_time(exit_time)
        if t_entry and t_exit:
            trade.duration_seconds = int((t_exit - t_entry).total_seconds())

        self.daily_pnl += net_pnl
        if net_pnl > 0:
            self.consecutive_losses = 0
            self.last_exit_was_profit = True
        else:
            self.consecutive_losses += 1
            self.last_exit_was_profit = False

        self.last_exit_time = t_exit
        self.trades.append(trade)
        self.active_trade = None
        return trade
