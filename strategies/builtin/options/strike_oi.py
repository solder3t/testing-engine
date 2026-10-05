from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class PcrExtremeReversalStrategy(BaseStrategy):
    """Put-Call Ratio (PCR) divergence and extreme exhaustion reversal."""
    def __init__(self):
        super().__init__(
            name="PCR Extreme Reversal",
            description="Mean reversion signals triggered when market PCR reaches extreme overbought or oversold bands.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("rsi_period", "int", 14, 5, 30, 1, "RSI confirmation period"))
        self.parameters.add(Parameter("pcr_oversold", "float", 0.65, 0.40, 0.85, 0.05, "Extreme bearish PCR threshold"))
        self.parameters.add(Parameter("pcr_overbought", "float", 1.45, 1.20, 1.80, 0.05, "Extreme bullish PCR threshold"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 18.0, 5.0, 45.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 36.0, 10.0, 80.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        closes = np.array([float(c.get("close", 0)) for c in candles], dtype=np.float64)
        self._rsi = self.math.rsi(closes, self.current_params["rsi_period"])

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["rsi_period"] + 2:
            return None

        pcr = float((context or {}).get("pcr", 1.0) or 1.0)
        rsi_val = self._rsi[idx] if hasattr(self, "_rsi") else 50.0

        if pcr <= self.current_params["pcr_oversold"] and rsi_val <= 32.0:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.85, reasoning="PCR Extreme Oversold Bounce")
        elif pcr >= self.current_params["pcr_overbought"] and rsi_val >= 68.0:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.85, reasoning="PCR Extreme Overbought Exhaustion")
        return None


class ExpiryPinningMagnetStrategy(BaseStrategy):
    """Strike gravity pinning model approaching 14:00–15:15 IST on expiry days."""
    def __init__(self):
        super().__init__(
            name="Expiry Pinning Magnet",
            description="Trades mean-reversion toward highest open interest cluster during expiry afternoon sessions.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("strike_distance_max", "float", 35.0, 15.0, 80.0, 5.0, "Max distance to pin target"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 12.0, 5.0, 30.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 24.0, 10.0, 50.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        t_str = str(candle.get("candle_time", ""))
        if " 13:45" <= t_str[-8:] <= " 15:00":
            c_close = float(candle.get("close", 0))
            pin_target = round(c_close / 50.0) * 50.0
            diff = pin_target - c_close

            if 10.0 <= diff <= self.current_params["strike_distance_max"]:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=abs(diff), confidence=0.79, reasoning="Expiry Pin Magnet Bullish Pull")
            elif -self.current_params["strike_distance_max"] <= diff <= -10.0:
                return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=abs(diff), confidence=0.79, reasoning="Expiry Pin Magnet Bearish Pull")
        return None


class MaxPainConvergenceStrategy(BaseStrategy):
    """Option Max Pain strike convergence directional positioning."""
    def __init__(self):
        super().__init__(
            name="Max Pain Convergence",
            description="Aligns intraday trades toward option chain Max Pain strike.",
            category="OPTIONS"
        )

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("min_distance_pts", "float", 25.0, 10.0, 60.0, 5.0, "Minimum required distance to Max Pain"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 16.0, 5.0, 40.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 35.0, 15.0, 80.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 30:
            return None

        c_close = float(candle.get("close", 0))
        max_pain = float((context or {}).get("max_pain", c_close) or c_close)
        diff = max_pain - c_close

        if diff >= self.current_params["min_distance_pts"]:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.77, reasoning="Max Pain Upward Pull")
        elif diff <= -self.current_params["min_distance_pts"]:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.77, reasoning="Max Pain Downward Pull")
        return None


class OiBuildupTrendStrategy(BaseStrategy):
    """Option Open Interest buildup analysis (Long vs Short Buildup)."""
    def __init__(self):
        super().__init__(
            name="OI Buildup Trend",
            description="Identifies institutional Long Buildup (Price UP, OI UP) and Short Buildup (Price DOWN, OI UP).",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("oi_surge_pct", "float", 3.0, 1.0, 8.0, 0.5, "Minimum OI change percentage"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 5.0, 40.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 35.0, 10.0, 80.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        if len(history) < 5:
            return None

        c_close = float(candle.get("close", 0))
        p_close = float(history[-1].get("close", 0))
        c_oi = float(candle.get("oi", 0) or 0)
        p_oi = float(history[-1].get("oi", 0) or 0)

        if p_oi > 0:
            oi_change = ((c_oi - p_oi) / p_oi) * 100.0
            if oi_change >= self.current_params["oi_surge_pct"]:
                if c_close > p_close:
                    return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Institutional Long Buildup")
                elif c_close < p_close:
                    return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Institutional Short Buildup")
        return None
