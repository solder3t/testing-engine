from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class VwapValueAreaPocStrategy(BaseStrategy):
    """
    Market Profile / Value Area (VAH / VAL / POC): Enters on breakouts or retests
    of Value Area High (VAH), Value Area Low (VAL), or Point of Control (POC).
    """
    def __init__(self):
        super().__init__(
            name="VWAP Value Area & POC",
            description="Trades volume profile value area boundaries and POC migrations.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("va_pct", "float", 0.70, 0.60, 0.80, 0.05, "Value Area coverage %"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 12.0, 5.0, 30.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 36.0, 15.0, 80.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)
        cum_vol = np.cumsum(v)
        cum_pv = np.cumsum(c * v)
        vwap = cum_pv / np.maximum(cum_vol, 1e-5)
        sq_diff = (c - vwap) ** 2
        cum_sq = np.cumsum(sq_diff * v)
        std = np.sqrt(cum_sq / np.maximum(cum_vol, 1e-5))

        self._c = c
        self._poc = vwap
        self._vah = vwap + std
        self._val = vwap - std

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 30:
            return None

        c_curr, c_prev = self._c[idx], self._c[idx - 1]
        vah_curr = self._vah[idx]
        val_curr = self._val[idx]

        if c_prev <= vah_curr and c_curr > vah_curr:
            return Signal(
                action="BUY",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Value Area High (VAH) Bullish Expansion",
                stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) + self.current_params["target_pts"]
            )
        elif c_prev >= val_curr and c_curr < val_curr:
            return Signal(
                action="SELL",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Value Area Low (VAL) Bearish Expansion",
                stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) - self.current_params["target_pts"]
            )
        return None


class FuturesVwapMeanReversionStrategy(BaseStrategy):
    """
    Futures Multi-Sigma VWAP Envelope Reversion: Enters counter-trend when price
    extends beyond 2.5 standard deviations from the daily session VWAP.
    """
    def __init__(self):
        super().__init__(
            name="Futures VWAP Envelope Reversion",
            description="Multi-sigma VWAP deviation fade for intraday futures mean-reversion.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("sigma_mult", "float", 2.2, 1.5, 3.2, 0.2, "VWAP standard deviation multiplier"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 5.0, 35.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 30.0, 10.0, 70.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)
        cum_vol = np.cumsum(v)
        cum_pv = np.cumsum(c * v)
        vwap = cum_pv / np.maximum(cum_vol, 1e-5)
        sq_diff = (c - vwap) ** 2
        cum_sq = np.cumsum(sq_diff * v)
        std = np.sqrt(cum_sq / np.maximum(cum_vol, 1e-5))

        mult = self.current_params["sigma_mult"]
        self._c = c
        self._vwap = vwap
        self._upper = vwap + mult * std
        self._lower = vwap - mult * std

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 25 or idx > 330:
            return None

        c_curr, c_prev = self._c[idx], self._c[idx - 1]

        if c_prev < self._lower[idx - 1] and c_curr >= self._lower[idx]:
            return Signal(
                action="BUY",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="VWAP Lower Band Reversion Bounce",
                stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) + self.current_params["target_pts"]
            )
        elif c_prev > self._upper[idx - 1] and c_curr <= self._upper[idx]:
            return Signal(
                action="SELL",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="VWAP Upper Band Reversion Rejection",
                stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) - self.current_params["target_pts"]
            )
        return None
