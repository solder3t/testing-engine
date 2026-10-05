from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class VolumePriceActionBreakoutStrategy(BaseStrategy):
    """Breakout confirmed by 2.0x+ volume expansion."""
    def __init__(self):
        super().__init__(
            name="Volume Price Action Breakout",
            description="Trades multi-candle high/low breakouts confirmed by sudden volume surges.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("lookback_bars", "int", 15, 8, 30, 1, "Breakout lookback bars"))
        self.parameters.add(Parameter("vol_multiplier", "float", 2.0, 1.3, 3.5, 0.2, "Volume multiplier vs 20-SMA"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 3.0, 1.0, 10.0, 0.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 8.0, 2.5, 25.0, 1.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)
        self._vol_sma = self.math.sma(v, 20)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        bars = self.current_params["lookback_bars"]
        if len(history) < bars + 1:
            return None

        idx = (context or {}).get("candle_index", len(history))
        recent = history[-bars:]
        box_high = max(float(c.get("high", 0)) for c in recent)
        box_low = min(float(c.get("low", 0)) for c in recent)
        c_close = float(candle.get("close", 0))

        v_curr = float(candle.get("volume", 0))
        v_avg = self._vol_sma[idx] if hasattr(self, "_vol_sma") else 1.0

        if v_avg > 0 and (v_curr / v_avg) >= self.current_params["vol_multiplier"]:
            if c_close > box_high:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="High Volume Price Action Breakout")
            elif c_close < box_low:
                return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="High Volume Price Action Breakdown")
        return None


class DonchianChannelTurtleStrategy(BaseStrategy):
    """Turtle trading channel breakout (Donchian Channels)."""
    def __init__(self):
        super().__init__(
            name="Donchian Channel Turtle",
            description="Classic Turtle Trend Following based on 20-period Donchian Channel band breakouts.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("donchian_period", "int", 20, 10, 40, 2, "Channel lookback period"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.5, 0.8, 8.0, 0.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 7.5, 2.0, 22.0, 1.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        p = self.current_params["donchian_period"]
        self._dh = self.math.donchian_channels(h, l, p)[0] if hasattr(self.math, "donchian_channels") else h
        self._dl = self.math.donchian_channels(h, l, p)[2] if hasattr(self.math, "donchian_channels") else l

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        p = self.current_params["donchian_period"]
        if len(history) < p + 1:
            return None

        c_close = float(candle.get("close", 0))
        p_high = max(float(c.get("high", 0)) for c in history[-p:])
        p_low = min(float(c.get("low", 0)) for c in history[-p:])

        if c_close > p_high:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="Donchian Upper Channel Breakout")
        elif c_close < p_low:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="Donchian Lower Channel Breakdown")
        return None


class IchimokuCloudBreakoutStrategy(BaseStrategy):
    """Ichimoku Kinko Hyo Tenkan/Kijun cross with Kumo breakout."""
    def __init__(self):
        super().__init__(
            name="Ichimoku Cloud Breakout",
            description="Classic Japanese trend breakout entering when Tenkan-sen crosses Kijun-sen.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("tenkan_p", "int", 9, 7, 14, 1, "Tenkan-sen period"))
        self.parameters.add(Parameter("kijun_p", "int", 26, 18, 35, 2, "Kijun-sen period"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.5, 0.8, 8.0, 0.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 7.0, 2.0, 22.0, 1.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        kp = self.current_params["kijun_p"]
        if len(history) < kp + 2:
            return None

        tp = self.current_params["tenkan_p"]
        t_high = max(float(c.get("high", 0)) for c in history[-tp:])
        t_low = min(float(c.get("low", 0)) for c in history[-tp:])
        tenkan_curr = (t_high + t_low) / 2.0

        k_high = max(float(c.get("high", 0)) for c in history[-kp:])
        k_low = min(float(c.get("low", 0)) for c in history[-kp:])
        kijun_curr = (k_high + k_low) / 2.0

        p_close = float(history[-1].get("close", 0))
        c_close = float(candle.get("close", 0))

        if p_close <= kijun_curr and c_close > kijun_curr and tenkan_curr > kijun_curr:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="Ichimoku TK Bullish Cross")
        elif p_close >= kijun_curr and c_close < kijun_curr and tenkan_curr < kijun_curr:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="Ichimoku TK Bearish Cross")
        return None


class LinearRegressionSlopeStrategy(BaseStrategy):
    """Linear regression trendline slope inflection."""
    def __init__(self):
        super().__init__(
            name="Linear Regression Slope",
            description="Statistical linear regression slope indicator detecting sudden angle inflection.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("lr_period", "int", 14, 8, 25, 2, "Linear regression lookback"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.0, 0.6, 7.0, 0.4, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 5.5, 1.8, 18.0, 0.8, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        p = self.current_params["lr_period"]
        if len(history) < p + 2:
            return None

        closes = [float(c.get("close", 0)) for c in history[-p:]] + [float(candle.get("close", 0))]
        x = np.arange(len(closes))
        slope, _ = np.polyfit(x, closes, 1)

        prev_closes = [float(c.get("close", 0)) for c in history[-p - 1:-1]]
        prev_slope, _ = np.polyfit(np.arange(len(prev_closes)), prev_closes, 1)

        if prev_slope <= 0 and slope > 0.05:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="Linear Regression Positive Slope Inflection")
        elif prev_slope >= 0 and slope < -0.05:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="Linear Regression Negative Slope Inflection")
        return None
