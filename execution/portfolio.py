"""
execution/portfolio.py — Portfolio Manager, Dynamic Position Sizing & Risk Controls.
"""

from typing import List, Dict, Optional, Tuple, Union
import math

import config
from data.instrument_master import InstrumentMaster
from data.expiry_calendar import ExpiryCalendar
from data.span_margin import SpanMarginCalculator, estimate_span_margin
from execution.order import OrderSide, InstrumentType, Trade
from execution.risk_manager import RiskManager
from execution.simulator import ExecutionSimulator


class Portfolio:
    """Tracks capital, active positions, trailing stop-losses, kill switches, and performance."""

    def __init__(
        self,
        initial_capital: float = config.DEFAULT_CAPITAL,
        risk_pct_per_trade: float = config.DEFAULT_RISK_PCT_PER_TRADE,
        simulator: Optional[ExecutionSimulator] = None,
        risk_manager: Optional[RiskManager] = None,
        sizing_mode: str = "risk_based",
        fixed_lots: int = 1,
        lot_multiplier: float = 1.0,
        custom_lot_size: Optional[int] = None,
        fixed_qty: int = 0,
        capital_pct: float = 0.10,
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.blocked_margin: float = 0.0
        self.risk_pct_per_trade = risk_pct_per_trade
        self.simulator = simulator or ExecutionSimulator()
        self.risk_manager = risk_manager or RiskManager(capital=initial_capital)
        self.sizing_mode = sizing_mode
        self.fixed_lots = max(1, int(fixed_lots)) if fixed_lots else 1
        self.lot_multiplier = max(0.1, float(lot_multiplier)) if lot_multiplier else 1.0
        self.custom_lot_size = int(custom_lot_size) if custom_lot_size and int(custom_lot_size) > 0 else None
        self.fixed_qty = int(fixed_qty) if fixed_qty else 0
        self.capital_pct = float(capital_pct) if capital_pct else 0.10

        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        self.daily_pnl: float = 0.0

    def can_open_trade(
        self,
        symbol: str,
        sector: str = "",
        new_trade_value: float = 0.0,
        price_history: Optional[Dict[str, List[float]]] = None
    ) -> Tuple[bool, str]:
        """Check risk manager state, portfolio capacity, sector limits, and correlation limits."""
        # 1. Institutional Risk Controls / Kill Switch Check
        allowed, reason = self.risk_manager.check_entry_allowed()
        if not allowed:
            return False, reason

        # 2. Maximum Concurrent Positions
        if len(self.open_trades) >= config.MAX_POSITIONS:
            return False, f"Max positions reached ({config.MAX_POSITIONS})"

        # 3. No duplicate positions in same symbol
        if any(t.symbol == symbol for t in self.open_trades):
            return False, f"Already holding position in {symbol}"

        # 4. Sector Concentration (Position count limit)
        if sector and sector not in ("Other", "Index", "Unknown"):
            sector_count = sum(1 for t in self.open_trades if t.metadata.get("sector") == sector)
            if sector_count >= config.MAX_POSITIONS_PER_SECTOR:
                return False, f"Sector limit reached for {sector} ({config.MAX_POSITIONS_PER_SECTOR})"

        # 5. Sector Exposure Limit (% of capital)
        sec_allowed, sec_reason = self.risk_manager.check_sector_exposure(
            self.open_trades,
            sector,
            new_trade_value=new_trade_value,
            capital=self.capital
        )
        if not sec_allowed:
            return False, sec_reason

        # 6. Correlated Legs Limit
        corr_allowed, corr_reason = self.risk_manager.check_correlation_limit(
            self.open_trades,
            symbol,
            price_history=price_history
        )
        if not corr_allowed:
            return False, corr_reason

        return True, "OK"

    def get_position(self, symbol: str) -> Optional[Trade]:
        """Returns active open trade for symbol if present, else None."""
        for t in self.open_trades:
            if t.symbol == symbol:
                return t
        return None

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        score: int = 70,
        lot_size: Optional[int] = None,
        symbol: str = "NIFTY",
        trade_date: Optional[str] = None,
        instrument_type: InstrumentType = InstrumentType.FUTURES,
        side: OrderSide = OrderSide.BUY
    ) -> int:
        """
        Calculates position size strictly bounded by risk-per-trade,
        margin requirements, instrument-specific point-in-time lot sizes, custom overrides,
        and NSE freeze limits.
        """
        risk_per_unit = abs(entry_price - stop_loss)
        
        # Determine base lot size (custom override takes highest precedence)
        if self.custom_lot_size is not None and self.custom_lot_size > 0:
            effective_lot = self.custom_lot_size
        elif lot_size is not None and lot_size > 1:
            effective_lot = lot_size
        else:
            effective_lot = InstrumentMaster.get_lot_size(symbol, trade_date, is_derivative=True)
            if effective_lot <= 0:
                effective_lot = 1

        effective_lot = max(1, int(round(effective_lot * self.lot_multiplier)))
        freeze_qty = InstrumentMaster.get_freeze_qty(symbol)
        max_allowed = min(freeze_qty, config.MAX_QTY_PER_TRADE)

        # Mode 1: Fixed Quantity
        if self.sizing_mode == "fixed_qty" and self.fixed_qty > 0:
            return max(1, min(self.fixed_qty, max_allowed))

        # Mode 2: Fixed Lots
        if self.sizing_mode == "fixed_lots":
            lots = max(1, self.fixed_lots)
            qty = lots * effective_lot
            return max(effective_lot, min(qty, max_allowed))

        # Effective capital includes unrealized P&L
        effective_capital = (
            self.equity_curve[-1]["equity"] if self.equity_curve else self.capital
        )
        available_capital = max(0.0, effective_capital - getattr(self, "blocked_margin", 0.0))

        # Mode 3: Fixed Capital Percentage
        if self.sizing_mode == "fixed_capital_pct":
            trade_capital = available_capital * self.capital_pct
            raw_qty = trade_capital / max(1.0, entry_price)
            lots = max(1, math.floor(raw_qty / effective_lot))
            qty = lots * effective_lot
            return max(effective_lot, min(qty, max_allowed))

        # Mode 4: Risk-Based (default)
        if risk_per_unit <= 0:
            return effective_lot

        risk_capital = available_capital * self.risk_pct_per_trade

        # Score scaling
        if score >= 80:
            risk_capital *= 1.5
        elif score < 60:
            risk_capital *= 0.5

        raw_qty = risk_capital / risk_per_unit

        # Lot size normalization
        lots = max(1, math.floor(raw_qty / effective_lot))
        qty = lots * effective_lot

        # Dynamic SPAN Margin Constraint
        margin_per_lot = SpanMarginCalculator.estimate_margin(
            symbol=symbol,
            instrument_type=instrument_type,
            side=side,
            price=entry_price,
            qty=effective_lot,
            trade_date=trade_date
        )
        if margin_per_lot > 0 and available_capital > 0:
            max_lots_by_margin = math.floor(available_capital / margin_per_lot)
            if max_lots_by_margin < lots:
                lots = max(1, max_lots_by_margin)
                qty = lots * effective_lot

        return max(effective_lot, min(qty, max_allowed))

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
        bid_ask_spread: float = 0.0,
        depth_row: Optional[Dict] = None
    ) -> Optional[Trade]:
        """Opens a new trade, applying slippage, entry charges, and margin blocking."""
        meta = metadata.copy() if metadata else {}
        est_val = price * qty
        can_open, reason = self.can_open_trade(
            symbol=symbol,
            sector=meta.get("sector", ""),
            new_trade_value=est_val,
            price_history=meta.get("price_history")
        )
        if not can_open:
            return None

        # Block margin
        trade_date_str = entry_time.split(" ")[0] if " " in entry_time else None
        required_margin = SpanMarginCalculator.estimate_margin(
            symbol=symbol,
            instrument_type=instrument_type,
            side=side,
            price=price,
            qty=qty,
            underlying_price=meta.get("underlying_price"),
            trade_date=trade_date_str
        )
        meta["margin_blocked"] = required_margin
        self.blocked_margin += required_margin

        meta["entry_bar_time"] = entry_time

        fill_price = self.simulator.calculate_fill_price(
            side=side,
            reference_price=price,
            bid_ask_spread=bid_ask_spread,
            qty=qty,
            depth_row=depth_row
        )

        entry_charges_dict = self.simulator.calculate_charges(
            side=side,
            price=fill_price,
            qty=qty,
            instrument_type=instrument_type
        )
        entry_charges = entry_charges_dict["total"]

        meta["entry_charges"] = entry_charges_dict
        trade = Trade(
            symbol=symbol,
            security_id=security_id,
            side=side,
            entry_time=entry_time,
            entry_price=fill_price,
            qty=qty,
            initial_sl=sl,
            current_sl=sl,
            target=target,
            instrument_type=instrument_type,
            charges=entry_charges,
            metadata=meta
        )
        self._record_trade_component_charges(trade, entry_charges_dict)
        self.open_trades.append(trade)
        return trade

    def _record_trade_component_charges(self, trade: Trade, charges_dict: Dict[str, float]):
        trade.metadata["brokerage"] = trade.metadata.get("brokerage", 0.0) + charges_dict["brokerage"]
        trade.metadata["stt"] = trade.metadata.get("stt", 0.0) + charges_dict["stt"]
        trade.metadata["exchange_fee"] = trade.metadata.get("exchange_fee", 0.0) + charges_dict["exchange_fee"]
        trade.metadata["gst"] = trade.metadata.get("gst", 0.0) + charges_dict["gst"]
        trade.metadata["sebi"] = trade.metadata.get("sebi", 0.0) + charges_dict["sebi"]
        trade.metadata["stamp_duty"] = trade.metadata.get("stamp_duty", 0.0) + charges_dict["stamp_duty"]

    def _finalize_trade_charges(self, trade: Trade, exit_charges_dict: Dict[str, float]):
        self._record_trade_component_charges(trade, exit_charges_dict)
        trade.metadata["exit_charges"] = exit_charges_dict
        entry_c = trade.metadata.get("entry_charges", {})
        combined = {}
        for k in ["brokerage", "stt", "exchange_fee", "gst", "sebi", "stamp_duty", "total"]:
            combined[k] = round(entry_c.get(k, 0.0) + exit_charges_dict.get(k, 0.0), 2)
        trade.metadata["charges_breakdown"] = combined

    def _release_trade_margin(self, trade: Trade) -> float:
        """Frees blocked margin associated with a trade upon exit."""
        margin_blocked = trade.metadata.get("margin_blocked", 0.0)
        if margin_blocked > 0:
            self.blocked_margin = max(0.0, self.blocked_margin - margin_blocked)
            trade.metadata["margin_freed"] = margin_blocked
        return margin_blocked

    def close_trade(
        self,
        trade: Trade,
        exit_time: str,
        exit_price: float,
        exit_reason: str = "MANUAL_CLOSE",
        exit_charges: float = 0.0
    ) -> Trade:
        """Explicitly closes an active trade, updates PnL, frees margin, and moves to closed trades."""
        trade.close(
            exit_time=exit_time,
            exit_price=exit_price,
            exit_reason=exit_reason,
            total_charges=trade.charges + exit_charges
        )
        self.capital += trade.net_pnl
        self.daily_pnl += trade.net_pnl
        self.risk_manager.record_trade_completion(trade.net_pnl, exit_time)
        self._release_trade_margin(trade)
        if trade in self.open_trades:
            self.open_trades.remove(trade)
        self.closed_trades.append(trade)
        return trade

    def close_position_manually(
        self,
        symbol: str,
        timestamp: str,
        exit_price: float,
        reason: str = "MANUAL_EXIT",
        depth_row: Optional[Dict] = None
    ) -> Optional[Trade]:
        """Manually closes an active open position."""
        trade = self.get_position(symbol)
        if not trade:
            return None

        exit_side = OrderSide.SELL if trade.side == OrderSide.BUY else OrderSide.BUY
        fill_exit_price = self.simulator.calculate_fill_price(
            side=exit_side,
            reference_price=exit_price,
            qty=trade.qty,
            depth_row=depth_row
        )

        exit_charges_dict = self.simulator.calculate_charges(
            side=exit_side,
            price=fill_exit_price,
            qty=trade.qty,
            instrument_type=trade.instrument_type
        )
        exit_charges = exit_charges_dict["total"]
        self._finalize_trade_charges(trade, exit_charges_dict)

        trade.close(
            exit_time=timestamp,
            exit_price=fill_exit_price,
            exit_reason=reason,
            total_charges=trade.charges + exit_charges
        )

        self.capital += trade.net_pnl
        self.daily_pnl += trade.net_pnl
        self.risk_manager.record_trade_completion(trade.net_pnl, timestamp)
        self._release_trade_margin(trade)

        self.open_trades.remove(trade)
        self.closed_trades.append(trade)
        return trade

    def check_positions_on_bar(
        self,
        timestamp: str,
        symbol_quotes: Dict[str, Dict]
    ) -> List[Trade]:
        """
        Evaluates stops, targets, time exits, and kill switches on every incoming bar.
        Enforces:
        1. Intraday Daily Loss Kill Switch.
        2. Lookahead bias protection (no intra-bar SL/target exit on entry bar).
        3. Conservative SL before Target priority during ambiguous bars.
        """
        just_closed: List[Trade] = []
        self.risk_manager.step_bar()

        # Check Kill Switch
        if self.risk_manager.evaluate_intraday_pnl(self.daily_pnl, timestamp):
            # Liquidate all open positions immediately
            for trade in list(self.open_trades):
                quote = symbol_quotes.get(trade.symbol)
                mkt_price = quote.get("close", trade.entry_price) if quote else trade.entry_price
                closed_trade = self.close_position_manually(
                    trade.symbol, timestamp, mkt_price, reason="KILL_SWITCH_HIT"
                )
                if closed_trade:
                    just_closed.append(closed_trade)
            return just_closed

        remaining: List[Trade] = []
        time_part = timestamp.split(" ")[-1][:5] if " " in timestamp else timestamp[:5]

        for trade in self.open_trades:
            quote = symbol_quotes.get(trade.symbol)
            if not quote:
                remaining.append(trade)
                continue

            curr_close = float(quote.get("close", quote.get("ltp", trade.entry_price)))
            curr_high = float(quote.get("high", curr_close))
            curr_low = float(quote.get("low", curr_close))

            # ── Excursion tracking (MFE & MAE) ───────────────────────────────
            if trade.side == OrderSide.BUY:
                favorable_pts = curr_high - trade.entry_price
                adverse_pts = trade.entry_price - curr_low
            else:
                favorable_pts = trade.entry_price - curr_low
                adverse_pts = curr_high - trade.entry_price

            if favorable_pts > trade.mfe_pts:
                trade.mfe_pts = round(favorable_pts, 2)
                trade.mfe_pct = round((favorable_pts / trade.entry_price) * 100, 4) if trade.entry_price > 0 else 0.0

            if adverse_pts > trade.mae_pts:
                trade.mae_pts = round(adverse_pts, 2)
                trade.mae_pct = round((adverse_pts / trade.entry_price) * 100, 4) if trade.entry_price > 0 else 0.0

            # ── Expiry Day ITM Option STT Penalty ────────────────────────────
            date_part = timestamp.split(" ")[0] if " " in timestamp else ""
            if date_part and time_part >= "15:15":
                if trade.instrument_type in (InstrumentType.OPTION_CE, InstrumentType.OPTION_PE):
                    underlying = trade.metadata.get("underlying", "NIFTY")
                    try:
                        if ExpiryCalendar.is_expiry(date_part, underlying):
                            strike = float(trade.metadata.get("strike", 0.0))
                            und_price = float(symbol_quotes.get(underlying, {}).get("close", curr_close))
                            is_itm = (
                                (trade.instrument_type == InstrumentType.OPTION_CE and und_price > strike)
                                or (trade.instrument_type == InstrumentType.OPTION_PE and und_price < strike)
                            ) if strike > 0 else False

                            if is_itm and trade.side == OrderSide.BUY and "expiry_stt_penalty" not in trade.metadata:
                                notional = curr_close * trade.qty
                                expiry_stt = round(notional * 0.00125, 2)
                                trade.metadata["expiry_stt_penalty"] = expiry_stt
                                trade.charges += expiry_stt
                    except Exception:
                        pass

            # ── 1. End of Day Force Square-off ────────────────────────────────
            if time_part >= config.FORCE_SQUARE_OFF_TIME:
                exit_price = curr_close
                exit_side = OrderSide.SELL if trade.side == OrderSide.BUY else OrderSide.BUY
                exit_charges_dict = self.simulator.calculate_charges(
                    exit_side, exit_price, trade.qty, trade.instrument_type
                )
                exit_charges = exit_charges_dict["total"]
                self._finalize_trade_charges(trade, exit_charges_dict)
                trade.close(timestamp, exit_price, "TIME_SQUARE_OFF", trade.charges + exit_charges)

                self.capital += trade.net_pnl
                self.daily_pnl += trade.net_pnl
                self.risk_manager.record_trade_completion(trade.net_pnl, timestamp)
                self._release_trade_margin(trade)
                self.closed_trades.append(trade)
                just_closed.append(trade)
                continue

            # ── 2. Lookahead Bias Protection ──────────────────────────────────
            # A trade entered on the current bar cannot be triggered on the bar's extreme
            # range formed prior to entry
            is_entry_bar = (trade.metadata.get("entry_bar_time") == timestamp)

            closed = False
            if trade.side == OrderSide.BUY:
                # 1. Stop Loss Hit — checked BEFORE target
                if not is_entry_bar and curr_low <= trade.current_sl:
                    exit_price = trade.current_sl
                    exit_charges_dict = self.simulator.calculate_charges(
                        OrderSide.SELL, exit_price, trade.qty, trade.instrument_type
                    )
                    exit_charges = exit_charges_dict["total"]
                    self._finalize_trade_charges(trade, exit_charges_dict)
                    trade.close(timestamp, exit_price, "SL_HIT", trade.charges + exit_charges)
                    closed = True
                # 2. Target Hit — only if SL was NOT hit
                elif not is_entry_bar and curr_high >= trade.target:
                    exit_price = trade.target
                    exit_charges_dict = self.simulator.calculate_charges(
                        OrderSide.SELL, exit_price, trade.qty, trade.instrument_type
                    )
                    exit_charges = exit_charges_dict["total"]
                    self._finalize_trade_charges(trade, exit_charges_dict)
                    trade.close(timestamp, exit_price, "TARGET_HIT", trade.charges + exit_charges)
                    closed = True
                # 3. Trailing / Breakeven SL Update
                else:
                    initial_risk = trade.entry_price - trade.initial_sl
                    if initial_risk > 0 and (curr_close - trade.entry_price) >= initial_risk:
                        if trade.current_sl < trade.entry_price:
                            trade.current_sl = trade.entry_price
                            trade.trailing_sl = trade.entry_price

            else:  # SELL
                if not is_entry_bar and curr_high >= trade.current_sl:
                    exit_price = trade.current_sl
                    exit_charges_dict = self.simulator.calculate_charges(
                        OrderSide.BUY, exit_price, trade.qty, trade.instrument_type
                    )
                    exit_charges = exit_charges_dict["total"]
                    self._finalize_trade_charges(trade, exit_charges_dict)
                    trade.close(timestamp, exit_price, "SL_HIT", trade.charges + exit_charges)
                    closed = True
                elif not is_entry_bar and curr_low <= trade.target:
                    exit_price = trade.target
                    exit_charges_dict = self.simulator.calculate_charges(
                        OrderSide.BUY, exit_price, trade.qty, trade.instrument_type
                    )
                    exit_charges = exit_charges_dict["total"]
                    self._finalize_trade_charges(trade, exit_charges_dict)
                    trade.close(timestamp, exit_price, "TARGET_HIT", trade.charges + exit_charges)
                    closed = True
                else:
                    initial_risk = trade.initial_sl - trade.entry_price
                    if initial_risk > 0 and (trade.entry_price - curr_close) >= initial_risk:
                        if trade.current_sl > trade.entry_price:
                            trade.current_sl = trade.entry_price
                            trade.trailing_sl = trade.entry_price

            if closed:
                self.capital += trade.net_pnl
                self.daily_pnl += trade.net_pnl
                self.risk_manager.record_trade_completion(trade.net_pnl, timestamp)
                self._release_trade_margin(trade)
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
        self.risk_manager.evaluate_equity_drawdown(current_equity, timestamp)

        self.equity_curve.append({
            "timestamp": timestamp,
            "equity": current_equity,
            "cash": round(self.capital, 2),
            "open_positions": len(self.open_trades),
            "unrealized_pnl": round(unrealized, 2)
        })

    def update_open_trades(self, timestamp: str, symbol_quotes: Dict[str, Dict]) -> List[Trade]:
        """Backward-compatible alias for check_positions_on_bar."""
        return self.check_positions_on_bar(timestamp, symbol_quotes)

