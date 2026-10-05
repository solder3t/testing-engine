"""
engine/rollover_manager.py — Derivative Contract Expiry Rollover Manager.

Manages expiry-day contract lifecycle, rollover schedules, and auto-square-off
prior to physical settlement / margin spike cutoffs.
"""

from datetime import datetime
import logging
from typing import Dict, List, Optional
import config
from data.expiry_calendar import ExpiryCalendar
from data.instrument_master import InstrumentMaster
from execution.order import InstrumentType, OrderSide, Trade
from execution.portfolio import Portfolio

logger = logging.getLogger("rollover_manager")


class RolloverManager:
    """Detects and processes derivative contracts nearing or reaching expiry."""

    def __init__(
        self,
        expiry_cutoff_time: str = config.EXPIRY_CUTOFF_TIME,
        auto_rollover: bool = True
    ):
        self.cutoff_time = expiry_cutoff_time
        self.auto_rollover = auto_rollover

    def check_and_process_rollovers(
        self,
        current_time_str: str,
        current_date_str: str,
        portfolio: Portfolio,
        quotes: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Scans portfolio open positions on expiry day. If time >= cutoff_time,
        executes square-off or rolls to the subsequent contract.
        """
        time_part = current_time_str.split(" ")[-1][:5] if " " in current_time_str else current_time_str[:5]
        if time_part < self.cutoff_time:
            return []

        rollover_events = []
        for trade in list(portfolio.open_trades):
            if trade.instrument_type not in (
                InstrumentType.OPTION_CE, InstrumentType.OPTION_PE, InstrumentType.FUTURES
            ):
                continue

            root_sym = trade.metadata.get("underlying") or InstrumentMaster.clean_symbol(trade.symbol)
            is_expiry = ExpiryCalendar.is_expiry_day(root_sym, current_date_str)
            if not is_expiry:
                continue

            # Contract is expiring today and we reached the cutoff time
            quote = quotes.get(trade.symbol, {})
            exit_price = quote.get("close", quote.get("ltp", trade.entry_price))

            closed_trade = portfolio.close_position_manually(
                symbol=trade.symbol,
                timestamp=current_time_str,
                exit_price=exit_price,
                reason="EXPIRY_CUTOFF_SQUAREOFF"
            )

            event = {
                "action": "EXPIRY_SQUARE_OFF",
                "symbol": trade.symbol,
                "exit_price": exit_price,
                "net_pnl": closed_trade.net_pnl if closed_trade else 0.0,
                "timestamp": current_time_str
            }
            logger.info(f"RolloverManager: Squared off expiring {trade.symbol} at {current_time_str} (PnL: {event['net_pnl']:.2f})")
            rollover_events.append(event)

        return rollover_events
