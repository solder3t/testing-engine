"""
strategies/base_strategy.py — Base Strategy Lifecycle Interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from execution.portfolio import Portfolio


class BaseStrategy(ABC):
    """Abstract base class for all backtesting strategies."""

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        """Called once at the beginning of each trading day before bars stream."""
        pass

    @abstractmethod
    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Called on every synchronized bar (e.g. 1-minute).
        
        Args:
            timestamp: Current bar time string 'YYYY-MM-DD HH:MM:SS'
            quotes: Map of symbol -> {open, high, low, close, volume, vwap, ...}
            portfolio: The active portfolio instance
            context: Shared session context (indices, indicators, breadth)
            
        Returns:
            List of generated trade setup dicts:
            [{
                'symbol': 'RELIANCE',
                'security_id': 2885,
                'side': OrderSide.BUY,
                'price': 2890.0,
                'sl': 2870.0,
                'target': 2930.0,
                'score': 82,
                'metadata': {'sector': 'Energy', 'strategy': self.name}
            }]
        """
        pass

    @abstractmethod
    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        """Called once at the end of each trading session after market close."""
        pass
