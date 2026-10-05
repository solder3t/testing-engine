"""
strategies/signal.py — Unified Trading Signal Schema.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class Signal:
    """Trading signal emitted by a strategy."""
    action: str                        # "ENTER", "BUY", "SELL", "WAIT", "HOLD", "EXIT_NOW"
    market_bias: str = "NEUTRAL"       # "CALL", "PUT", "BUY", "SELL", "NEUTRAL"
    option_type: Optional[str] = None  # "CE", "PE", or None
    strike: float = 0.0
    entry_price: float = 0.0
    price: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    risk_reward: str = "1:2"
    confidence: float = 0.0
    reasoning: str = ""
    reason: str = ""
    timestamp: str = ""
    symbol: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.entry_price and self.price:
            self.entry_price = self.price
        elif not self.price and self.entry_price:
            self.price = self.entry_price
        if not self.reasoning and self.reason:
            self.reasoning = self.reason
        elif not self.reason and self.reasoning:
            self.reason = self.reasoning
        if self.action.upper() in ("BUY", "LONG") and self.market_bias == "NEUTRAL":
            self.market_bias = "CALL"
        elif self.action.upper() in ("SELL", "SHORT") and self.market_bias == "NEUTRAL":
            self.market_bias = "PUT"

    def is_entry(self) -> bool:
        act = self.action.upper()
        return act in ("ENTER", "BUY", "SELL", "LONG", "SHORT")

    def is_exit(self) -> bool:
        act = self.action.upper()
        return act in ("EXIT_NOW", "EXIT", "CLOSE", "SQUARE_OFF")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "market_bias": self.market_bias,
            "option_type": self.option_type,
            "strike": self.strike,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "risk_reward": self.risk_reward,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "metadata": self.metadata
        }
