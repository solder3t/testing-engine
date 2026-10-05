from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class OptionsFlowMomentumStrategy(BaseStrategy):
    """Institutional call/put flow momentum & volume surge detection."""
    def __init__(self):
        super().__init__(
            name="Options Flow Momentum",
            description="Trades directional surges confirmed by option volume multiplier and fast EMA momentum.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("volume_mult", "float", 1.8, 1.2, 4.0, 0.2, "Volume surge multiplier vs 20-SMA"))
        self.parameters.add(Parameter("fast_ema", "int", 8, 3, 20, 1, "Fast EMA period"))
        self.parameters.add(Parameter("slow_ema", "int", 21, 10, 50, 1, "Slow EMA period"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 5.0, 50.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 35.0, 10.0, 90.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        closes = np.array([float(c.get("close", 0)) for c in candles], dtype=np.float64)
        vols = np.array([float(c.get("volume", 0)) for c in candles], dtype=np.float64)
        self._f_ema = self.math.ema(closes, self.current_params["fast_ema"])
        self._s_ema = self.math.ema(closes, self.current_params["slow_ema"])
        self._vol_sma = self.math.sma(vols, 20)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["slow_ema"] + 2:
            return None

        vol = float(candle.get("volume", 0))
        vol_avg = self._vol_sma[idx] if hasattr(self, "_vol_sma") else 1.0
        if np.isnan(vol_avg) or vol_avg <= 0:
            return None

        is_vol_surge = (vol / vol_avg) >= self.current_params["volume_mult"]
        f_curr, f_prev = self._f_ema[idx], self._f_ema[idx - 1]
        s_curr, s_prev = self._s_ema[idx], self._s_ema[idx - 1]

        if is_vol_surge and f_prev <= s_prev and f_curr > s_curr:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Call Flow Momentum Surge")
        elif is_vol_surge and f_prev >= s_prev and f_curr < s_curr:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Put Flow Momentum Surge")
        return None


class GammaScalpMomentumStrategy(BaseStrategy):
    """High-delta ITM/ATM gamma scalping on momentum surges."""
    def __init__(self):
        super().__init__(
            name="Gamma Scalp Momentum",
            description="Ultra-fast option scalping on rapid 3-candle ATR expansion.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("atr_period", "int", 7, 3, 14, 1, "Fast ATR lookback"))
        self.parameters.add(Parameter("atr_spike_mult", "float", 1.6, 1.2, 2.5, 0.1, "ATR expansion threshold"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 8.0, 3.0, 20.0, 1.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 16.0, 6.0, 40.0, 2.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        h = np.array([float(c.get("high", 0)) for c in candles], dtype=np.float64)
        l = np.array([float(c.get("low", 0)) for c in candles], dtype=np.float64)
        c = np.array([float(c.get("close", 0)) for c in candles], dtype=np.float64)
        self._atr = self.math.atr(h, l, c, self.current_params["atr_period"])

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["atr_period"] + 3:
            return None

        c_close = float(candle.get("close", 0))
        p_close = float(history[-1].get("close", 0))
        c_range = abs(c_close - p_close)
        cur_atr = self._atr[idx] if hasattr(self, "_atr") else 10.0

        if cur_atr > 0 and (c_range / cur_atr) >= self.current_params["atr_spike_mult"]:
            if c_close > p_close:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="Gamma Surge Bullish Scalp")
            else:
                return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="Gamma Surge Bearish Scalp")
        return None


class OptionBuyerVwapCrossStrategy(BaseStrategy):
    """Option buyer scalp entry when option LTP reclaims VWAP with volume surge."""
    def __init__(self):
        super().__init__(
            name="Option Buyer VWAP Cross",
            description="Enters Long Call/Put as soon as spot/option crosses above intraday VWAP with volume.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("vol_multiplier", "float", 1.5, 1.1, 3.0, 0.1, "Volume surge multiplier"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 10.0, 4.0, 25.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 25.0, 10.0, 60.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        h = np.array([float(c.get("high", 0)) for c in candles], dtype=np.float64)
        l = np.array([float(c.get("low", 0)) for c in candles], dtype=np.float64)
        c = np.array([float(c.get("close", 0)) for c in candles], dtype=np.float64)
        v = np.array([float(c.get("volume", 0)) for c in candles], dtype=np.float64)
        self._vwap = self.math.vwap(h, l, c, v)
        self._v_sma = self.math.sma(v, 15)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 16:
            return None

        c_close = float(candle.get("close", 0))
        p_close = float(history[-1].get("close", 0))
        cur_vwap = self._vwap[idx]
        prev_vwap = self._vwap[idx - 1]
        v_ratio = float(candle.get("volume", 0)) / max(self._v_sma[idx], 1.0)

        if p_close <= prev_vwap and c_close > cur_vwap and v_ratio >= self.current_params["vol_multiplier"]:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="Bullish VWAP Reclaim with Volume")
        elif p_close >= prev_vwap and c_close < cur_vwap and v_ratio >= self.current_params["vol_multiplier"]:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="Bearish VWAP Breakdown with Volume")
        return None


class OptionBreakoutConsolidationStrategy(BaseStrategy):
    """Consolidation range squeeze on option tick flow preceding explosive breakout."""
    def __init__(self):
        super().__init__(
            name="Option Breakout Consolidation",
            description="Enters breakout after 10+ candles of tight consolidation range.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("consolidation_bars", "int", 12, 6, 25, 1, "Consolidation lookback bars"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 12.0, 4.0, 30.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 30.0, 10.0, 75.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        bars = self.current_params["consolidation_bars"]
        if len(history) < bars + 1:
            return None

        recent = history[-bars:]
        box_high = max(float(c.get("high", 0)) for c in recent)
        box_low = min(float(c.get("low", 0)) for c in recent)
        c_close = float(candle.get("close", 0))

        if c_close > box_high:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Consolidation Box Upward Breakout")
        elif c_close < box_low:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Consolidation Box Downward Breakdown")
        return None
