"""
strategies/base_strategy.py — Universal Strategy Lifecycle Interface.

Supports both:
1. Event-driven synchronous bar execution (`on_bar`, `on_session_start`)
2. Vectorized / candle-based signal evaluation (`prepare_session`, `on_candle`, `Signal`)
3. Declarative parameter spaces (`ParameterSpace`, `ParamSpec`)
"""

from abc import ABC
from typing import Dict, List, Any, Optional

from engine.param_spec import ParamSpec
from execution.portfolio import Portfolio
from execution.order import OrderSide
from .signal import Signal
from .parameter_space import ParameterSpace, Parameter

# Re-export for submodules
__all__ = ["BaseStrategy", "Signal", "ParameterSpace", "Parameter"]


class BaseStrategy(ABC):
    """Abstract base class for all backtesting strategies."""

    def __init__(
        self,
        name: str = "",
        params: Optional[Dict[str, Any]] = None,
        description: str = "",
        category: str = "TECHNICAL",
        *args,
        **kwargs
    ):
        self.name = name
        self.description = description
        self.category = category
        self.params = params or {}
        self.target_instruments: List[str] = []
        self.parameters = ParameterSpace()
        self._history: Dict[str, List[Dict[str, Any]]] = {}

        self._setup_parameters()
        self.current_params = self.parameters.get_defaults()
        if self.params:
            self.current_params.update(self.params)

    def _setup_parameters(self) -> None:
        """Optional hook for strategies to register parameter definitions."""
        pass

    @classmethod
    def param_specs(cls) -> List[ParamSpec]:
        """Returns declarative list of optimizable parameters."""
        return []

    def get_param(self, key: str, default: Any = None) -> Any:
        """Type-safe parameter retriever with fallback."""
        if key in self.current_params:
            return self.current_params[key]
        return self.params.get(key, default)

    def set_parameters(self, params: Dict[str, Any]) -> None:
        """Apply and validate user parameters."""
        self.params.update(params)
        self.current_params.update(self.parameters.validate_all(params))

    def reset(self) -> None:
        """Reset state between backtesting sessions/days."""
        self._history.clear()

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        """Optional hook called at the start of each session before bars stream."""
        pass

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        """Called once at the beginning of each trading day before bars stream."""
        self.reset()
        ohlc_map = (context or {}).get("ohlc_data", {})
        candles: List[Dict[str, Any]] = []
        if isinstance(ohlc_map, dict) and ohlc_map:
            target = getattr(self, "target_instruments", [])
            chosen_df = None
            if target:
                for t in target:
                    if t in ohlc_map:
                        chosen_df = ohlc_map[t]
                        break
            if chosen_df is None:
                chosen_df = next(iter(ohlc_map.values()))

            if hasattr(chosen_df, "to_dict"):
                candles = chosen_df.to_dict("records")
            elif isinstance(chosen_df, list):
                candles = chosen_df

        try:
            self.prepare_session(candles, context or {})
        except Exception:
            pass

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        """Called once at the end of each trading day after bars stream."""
        pass

    def on_candle(
        self,
        candle: Dict[str, Any],
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Signal]:
        """Evaluate logic on new candle close."""
        return None

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Called on every synchronized bar (e.g. 1-minute).
        Provides automatic bridging to on_candle if subclass implements on_candle.
        """
        setups: List[Dict[str, Any]] = []

        for sym, q in quotes.items():
            if sym not in self._history:
                self._history[sym] = []

            candle = dict(q)
            candle["candle_time"] = timestamp
            candle["timestamp"] = timestamp
            candle["symbol"] = sym

            hist = self._history[sym]
            ctx = dict(context or {})
            ctx["candle_index"] = len(hist)

            try:
                sig = self.on_candle(candle, hist, ctx)
            except Exception:
                sig = None

            hist.append(candle)

            if sig and sig.is_entry():
                is_buy = sig.market_bias in ("CALL", "BUY") or sig.action.upper() in ("BUY", "LONG")
                entry_p = float(sig.entry_price or q.get("close", 0.0))
                sl_val = float(sig.stop_loss)
                target_val = float(sig.target)
                if entry_p > 0:
                    if is_buy and sl_val < entry_p / 2:
                        sl_val = entry_p - sl_val
                    elif not is_buy and sl_val < entry_p / 2:
                        sl_val = entry_p + sl_val

                    if is_buy and target_val < entry_p / 2:
                        target_val = entry_p + target_val
                    elif not is_buy and target_val < entry_p / 2:
                        target_val = max(1.0, entry_p - target_val)

                setups.append({
                    "symbol": sig.symbol or sym,
                    "side": OrderSide.BUY if is_buy else OrderSide.SELL,
                    "price": entry_p,
                    "order_type": "MARKET",
                    "sl": sl_val,
                    "target": target_val,
                    "confidence": sig.confidence,
                    "reasoning": sig.reasoning,
                    "tag": self.name
                })

        return setups

    def on_order_fill(self, trade: Any, portfolio: Portfolio):
        """Optional hook called immediately upon trade execution."""
        pass

    def on_expiry_rollover(self, symbol: str, expiring_contract: str, next_contract: str, portfolio: Portfolio):
        """Optional hook called when an expiring contract is rolled over."""
        pass

    def get_info(self) -> Dict[str, Any]:
        """Return strategy metadata and parameters for dashboard display."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters.to_dict(),
            "current_params": self.current_params
        }
