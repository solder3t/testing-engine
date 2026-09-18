"""
execution/order.py — Order, Trade, and Position Data Models.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import uuid


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "SL_M"
    TARGET = "TARGET"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class InstrumentType(str, Enum):
    EQUITY = "EQUITY"
    OPTION_CE = "CE"
    OPTION_PE = "PE"
    FUTURES = "FUT"


@dataclass
class Order:
    symbol: str
    security_id: int
    side: OrderSide
    order_type: OrderType
    qty: int
    price: float = 0.0
    trigger_price: float = 0.0
    instrument_type: InstrumentType = InstrumentType.EQUITY
    created_at: str = ""
    status: OrderStatus = OrderStatus.PENDING
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class Trade:
    symbol: str
    security_id: int
    side: OrderSide
    qty: int
    entry_time: str
    entry_price: float
    initial_sl: float
    current_sl: float
    target: float
    instrument_type: InstrumentType = InstrumentType.EQUITY
    trailing_sl: Optional[float] = None
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    status: str = "OPEN"
    gross_pnl: float = 0.0
    charges: float = 0.0
    net_pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_bars: int = 0
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metadata: Dict[str, Any] = field(default_factory=dict)

    def close(self, exit_time: str, exit_price: float, reason: str, charges: float = 0.0):
        """Close this open trade and compute P&L."""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = reason
        self.status = "CLOSED"

        if self.side == OrderSide.BUY:
            self.gross_pnl = round((exit_price - self.entry_price) * self.qty, 2)
        else:
            self.gross_pnl = round((self.entry_price - exit_price) * self.qty, 2)

        self.charges = round(charges, 2)
        self.net_pnl = round(self.gross_pnl - self.charges, 2)
        invested = self.entry_price * self.qty
        self.pnl_pct = round((self.net_pnl / invested) * 100, 2) if invested > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert trade object to a clean JSON-serializable dictionary."""
        entry_t = str(self.entry_time or "")
        meta = dict(self.metadata or {})
        date_val = meta.get("date") or (entry_t.split(" ")[0] if " " in entry_t else "")
        return {
            "trade_id": self.trade_id,
            "date": date_val,
            "symbol": self.symbol,
            "security_id": self.security_id,
            "side": getattr(self.side, "value", str(self.side)),
            "qty": self.qty,
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "initial_sl": self.initial_sl,
            "current_sl": self.current_sl,
            "target": self.target,
            "instrument_type": getattr(self.instrument_type, "value", str(self.instrument_type)),
            "trailing_sl": self.trailing_sl,
            "exit_time": self.exit_time,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "status": self.status,
            "gross_pnl": self.gross_pnl,
            "charges": self.charges,
            "net_pnl": self.net_pnl,
            "pnl_pct": self.pnl_pct,
            "holding_bars": self.holding_bars,
            "metadata": meta
        }
