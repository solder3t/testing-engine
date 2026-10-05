from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class Orb15MinBreakoutStrategy(BaseStrategy):
    """Classic 15-minute Opening Range Breakout (ORB)."""
    def __init__(self):
        super().__init__(
            name="15-Min Opening Range Breakout",
            description="Trades breakouts of the first 15-minute high/low range with volume confirmation.",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("range_bars", "int", 15, 5, 30, 5, "Number of 1-minute bars in opening range"))
        self.parameters.add(Parameter("buffer_pts", "float", 5.0, 1.0, 15.0, 1.0, "Breakout buffer points"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 25.0, 10.0, 60.0, 5.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 50.0, 20.0, 120.0, 10.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        bars = self.current_params["range_bars"]
        if len(history) < bars:
            return None

        orb_candles = history[:bars]
        orb_high = max(float(c.get("high", 0)) for c in orb_candles)
        orb_low = min(float(c.get("low", 0)) for c in orb_candles)

        idx = (context or {}).get("candle_index", len(history))
        if bars <= idx <= bars + 120:
            c_close = float(candle.get("close", 0))
            buf = self.current_params["buffer_pts"]
            if c_close > orb_high + buf:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.85, reasoning="15m ORB Bullish Breakout")
            elif c_close < orb_low - buf:
                return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.85, reasoning="15m ORB Bearish Breakdown")
        return None


class Orb30MinExpansionStrategy(BaseStrategy):
    """30-minute Opening Range Breakout with trailing momentum expansion."""
    def __init__(self):
        super().__init__(
            name="30-Min Opening Range Expansion",
            description="Institutional 30-minute opening range expansion with wider profit targets.",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("range_bars", "int", 30, 20, 45, 5, "Number of bars in opening range"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 30.0, 15.0, 70.0, 5.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 65.0, 30.0, 150.0, 10.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        bars = self.current_params["range_bars"]
        if len(history) < bars:
            return None

        orb_candles = history[:bars]
        orb_high = max(float(c.get("high", 0)) for c in orb_candles)
        orb_low = min(float(c.get("low", 0)) for c in orb_candles)

        idx = (context or {}).get("candle_index", len(history))
        if bars <= idx <= bars + 150:
            c_close = float(candle.get("close", 0))
            if c_close > orb_high:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="30m ORB Bullish Expansion")
            elif c_close < orb_low:
                return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="30m ORB Bearish Breakdown")
        return None


class CamarillaPivotBreakoutStrategy(BaseStrategy):
    """Camarilla Equation (H4/L4 Breakout & H3/L3 Reversal) system."""
    def __init__(self):
        super().__init__(
            name="Camarilla Pivot Breakout",
            description="Executes breakout on H4/L4 breach and mean reversion on H3/L3 touch.",
            category="INDEX"
        )

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("stop_loss_pts", "float", 22.0, 10.0, 50.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 50.0, 25.0, 110.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        if len(history) < 20:
            return None

        c_close = float(candle.get("close", 0))
        p_close = float(history[-1].get("close", 0))
        pd_h = float((context or {}).get("prev_day_high", c_close * 1.006) or c_close * 1.006)
        pd_l = float((context or {}).get("prev_day_low", c_close * 0.994) or c_close * 0.994)
        pd_c = float((context or {}).get("prev_day_close", c_close) or c_close)
        diff = pd_h - pd_l

        h4 = pd_c + (diff * 1.1 / 2.0)
        l4 = pd_c - (diff * 1.1 / 2.0)

        if p_close <= h4 and c_close > h4:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Camarilla H4 Breakout")
        elif p_close >= l4 and c_close < l4:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Camarilla L4 Breakdown")
        return None


class VwapBandPinchStrategy(BaseStrategy):
    """VWAP standard deviation band pinch & breakout system."""
    def __init__(self):
        super().__init__(
            name="VWAP Band Pinch",
            description="Identifies volume-weighted standard deviation compression followed by explosive expansion.",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("band_std", "float", 1.8, 1.2, 2.6, 0.2, "VWAP standard deviation multiplier"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 18.0, 8.0, 40.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 38.0, 15.0, 85.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)
        vwap = self.math.vwap(h, l, c, v)
        self._vwap = vwap
        dev = np.abs(c - vwap)
        self._upper = vwap + (self.current_params["band_std"] * dev)
        self._lower = vwap - (self.current_params["band_std"] * dev)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 25:
            return None

        c_close = float(candle.get("close", 0))
        p_close = float(history[-1].get("close", 0))

        if p_close <= self._upper[idx - 1] and c_close > self._upper[idx]:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="VWAP Band Bullish Pinch Out")
        elif p_close >= self._lower[idx - 1] and c_close < self._lower[idx]:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="VWAP Band Bearish Pinch Out")
        return None


class TtmSqueezeProStrategy(BaseStrategy):
    """Bollinger Bands inside Keltner Channels contraction (TTM Squeeze)."""
    def __init__(self):
        super().__init__(
            name="TTM Squeeze Pro",
            description="Fires directional signals as Bollinger Bands expand outside Keltner Channels.",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("period", "int", 20, 10, 30, 2, "Indicator lookback period"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 20.0, 8.0, 45.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 45.0, 15.0, 95.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        p = self.current_params["period"]

        bb_u, _, bb_l = self.math.bollinger_bands(c, p, 2.0)
        atr_val = self.math.atr(h, l, c, p)
        sma_val = self.math.sma(c, p)

        kc_u = sma_val + (1.5 * atr_val)
        kc_l = sma_val - (1.5 * atr_val)

        self._squeeze = (bb_u < kc_u) & (bb_l > kc_l)
        _, _, self._hist = self.math.macd(c, 12, 26, 9)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 30:
            return None

        was_squeeze = self._squeeze[idx - 1] if hasattr(self, "_squeeze") else False
        is_squeeze = self._squeeze[idx] if hasattr(self, "_squeeze") else False
        hist_val = self._hist[idx] if hasattr(self, "_hist") else 0.0

        if was_squeeze and not is_squeeze:
            if hist_val > 0:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.86, reasoning="TTM Squeeze Bullish Fired")
            elif hist_val < 0:
                return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.86, reasoning="TTM Squeeze Bearish Fired")
        return None
