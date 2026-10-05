from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class IvExpansionBreakoutStrategy(BaseStrategy):
    """Implied Volatility Expansion Breakout with Bollinger Bandwidth filter."""
    def __init__(self):
        super().__init__(
            name="IV Expansion Breakout",
            description="Captures explosive directional expansion following volatility compression.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("bb_period", "int", 20, 10, 40, 2, "Bollinger lookback period"))
        self.parameters.add(Parameter("bb_std", "float", 2.0, 1.5, 3.0, 0.25, "Bollinger standard deviations"))
        self.parameters.add(Parameter("bandwidth_threshold", "float", 0.012, 0.005, 0.03, 0.002, "Compression threshold"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 5.0, 40.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 40.0, 15.0, 90.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        closes = np.array([float(c.get("close", 0)) for c in candles], dtype=np.float64)
        u, m, l = self.math.bollinger_bands(closes, self.current_params["bb_period"], self.current_params["bb_std"])
        self._bb_u, self._bb_m, self._bb_l = u, m, l
        self._bw = np.where(m > 0, (u - l) / m, 0.0)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["bb_period"] + 2:
            return None

        close = float(candle.get("close", 0))
        prev_close = float(history[-1].get("close", 0)) if history else close
        was_compressed = self._bw[idx - 1] <= self.current_params["bandwidth_threshold"]

        if was_compressed and close > self._bb_u[idx] and prev_close <= self._bb_u[idx - 1]:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.80, reasoning="IV Expansion Call Breakout")
        elif was_compressed and close < self._bb_l[idx] and prev_close >= self._bb_l[idx - 1]:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.80, reasoning="IV Expansion Put Breakdown")
        return None


class StraddlePremiumDecayStrategy(BaseStrategy):
    """Intraday ATM straddle seller / premium erosion capture."""
    def __init__(self):
        super().__init__(
            name="Straddle Premium Decay",
            description="Exploits intraday theta decay during non-trending equilibrium regimes.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("adx_max", "float", 22.0, 15.0, 30.0, 1.0, "Max ADX to ensure non-trending regime"))
        self.parameters.add(Parameter("start_time_min", "int", 45, 15, 90, 15, "Minutes after open to enter (e.g. 10:00 IST)"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 12.0, 4.0, 30.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 20.0, 6.0, 45.0, 2.5, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        h = np.array([float(c.get("high", 0)) for c in candles], dtype=np.float64)
        l = np.array([float(c.get("low", 0)) for c in candles], dtype=np.float64)
        c = np.array([float(c.get("close", 0)) for c in candles], dtype=np.float64)
        adx_val, _, _ = self.math.adx(h, l, c, 14)
        self._adx = adx_val

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 30:
            return None

        if idx == self.current_params["start_time_min"]:
            cur_adx = self._adx[idx] if hasattr(self, "_adx") and not np.isnan(self._adx[idx]) else 20.0
            if cur_adx <= self.current_params["adx_max"]:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.78, reasoning="Theta Decay Equilibrium Entry")
        return None


class ThetaHarvestSlopeStrategy(BaseStrategy):
    """Range-bound decay harvesting with EMA channel slope boundaries."""
    def __init__(self):
        super().__init__(
            name="Theta Harvest Slope",
            description="Trades sideways decay when price oscillates within flat 20/50 EMA boundaries.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("slope_max_deg", "float", 0.08, 0.02, 0.20, 0.02, "Max EMA slope for flat regime"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 14.0, 5.0, 35.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 24.0, 8.0, 50.0, 3.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        closes = np.array([float(c.get("close", 0)) for c in candles], dtype=np.float64)
        self._ema20 = self.math.ema(closes, 20)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 25:
            return None

        slope = abs(self._ema20[idx] - self._ema20[idx - 5]) / 5.0 if hasattr(self, "_ema20") else 0.0
        c_close = float(candle.get("close", 0))
        c_ema = self._ema20[idx]

        if slope <= self.current_params["slope_max_deg"]:
            if c_close < c_ema * 0.998:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.76, reasoning="Theta Range Lower Bound Buy")
            elif c_close > c_ema * 1.002:
                return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.76, reasoning="Theta Range Upper Bound Fade")
        return None


class VolatilityCrushReversionStrategy(BaseStrategy):
    """Entry following morning IV spike contraction."""
    def __init__(self):
        super().__init__(
            name="Volatility Crush Reversion",
            description="Mean reversion post opening range IV spike contraction back to baseline.",
            category="OPTIONS"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("rsi_cutoff", "float", 72.0, 65.0, 85.0, 2.0, "Overbought RSI cutoff"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 5.0, 40.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 30.0, 10.0, 70.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        self._rsi = self.math.rsi(c, 14)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 20 or idx > 120:
            return None

        rsi_v = self._rsi[idx] if hasattr(self, "_rsi") else 50.0
        if rsi_v >= self.current_params["rsi_cutoff"]:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.78, reasoning="Morning Vol Crush Put Entry")
        elif rsi_v <= 100.0 - self.current_params["rsi_cutoff"]:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.78, reasoning="Morning Vol Crush Call Bounce")
        return None
