"""
strategies/custom_strategy.py — Starter Template for Custom User Strategies.
"""

from typing import Dict, List, Any, Optional
from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy


class CustomStrategy(BaseStrategy):
    """
    Starter template for defining custom trading strategies.
    Implement your logic in on_session_start, on_bar, and on_session_end.
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "fast_period": 9,
            "slow_period": 21,
            "sl_pct": 0.01,
            "tgt_pct": 0.02
        }
        if params:
            default_params.update(params)
        super().__init__(name="CustomStrategy", params=default_params)

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        """Initialize session state."""
        pass

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Evaluate bars and return signals."""
        signals = []
        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        """Cleanup session state."""
        pass
