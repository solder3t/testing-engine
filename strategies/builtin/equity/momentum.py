from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class MomentumRsiEmaStrategy(BaseStrategy):
    """Dual EMA crossover with RSI momentum confirmation."""
    def __init__(self):
        super().__init__(
            name="Momentum RSI & EMA",
            description="Dual EMA crossover filtered by RSI momentum cutoff.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("fast_ema", "int", 9, 3, 20, 1, "Fast EMA period"))
        self.parameters.add(Parameter("slow_ema", "int", 21, 10, 50, 1, "Slow EMA period"))
        self.parameters.add(Parameter("rsi_period", "int", 14, 5, 30, 1, "RSI period"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.0, 0.5, 10.0, 0.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 6.0, 1.5, 25.0, 1.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        self._f_ema = self.math.ema(c, self.current_params["fast_ema"])
        self._s_ema = self.math.ema(c, self.current_params["slow_ema"])
        self._rsi = self.math.rsi(c, self.current_params["rsi_period"])

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["slow_ema"] + 2:
            return None

        fc, fp = self._f_ema[idx], self._f_ema[idx - 1]
        sc, sp = self._s_ema[idx], self._s_ema[idx - 1]
        rsi_val = self._rsi[idx] if hasattr(self, "_rsi") else 50.0

        if fp <= sp and fc > sc and rsi_val >= 52.0:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Momentum RSI Bullish Cross")
        elif fp >= sp and fc < sc and rsi_val <= 48.0:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Momentum RSI Bearish Cross")
        return None


class KeltnerChannelMomentumStrategy(BaseStrategy):
    """Keltner Channel breakout with ATR trailing bands."""
    def __init__(self):
        super().__init__(
            name="Keltner Channel Momentum",
            description="Trades directional expansion riding outside Keltner Channels.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("kc_period", "int", 20, 10, 30, 2, "Keltner EMA lookback"))
        self.parameters.add(Parameter("kc_multiplier", "float", 1.8, 1.2, 2.8, 0.2, "ATR multiplier"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.2, 0.8, 7.0, 0.4, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 6.5, 2.0, 20.0, 1.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        p = self.current_params["kc_period"]
        m = self.current_params["kc_multiplier"]

        ema_val = self.math.ema(c, p)
        atr_val = self.math.atr(h, l, c, p)
        self._kc_upper = ema_val + (m * atr_val)
        self._kc_lower = ema_val - (m * atr_val)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 25:
            return None

        c_close = float(candle.get("close", 0))
        p_close = float(history[-1].get("close", 0))

        if p_close <= self._kc_upper[idx - 1] and c_close > self._kc_upper[idx]:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Keltner Upper Band Momentum Ride")
        elif p_close >= self._kc_lower[idx - 1] and c_close < self._kc_lower[idx]:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Keltner Lower Band Momentum Ride")
        return None


class StochasticRsiCrossoverStrategy(BaseStrategy):
    """Stochastic RSI fast momentum crossover."""
    def __init__(self):
        super().__init__(
            name="Stochastic RSI Crossover",
            description="Captures turning points via Stochastic RSI %K and %D crossovers.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("rsi_period", "int", 14, 7, 21, 1, "RSI period"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.0, 0.5, 6.0, 0.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 5.5, 1.5, 16.0, 0.5, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        rsi = self.math.rsi(c, self.current_params["rsi_period"])
        self._stoch_k, self._stoch_d = self.math.stochastic(rsi, rsi, rsi, 14, 3, 3)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 30:
            return None

        k_c, k_p = self._stoch_k[idx], self._stoch_k[idx - 1]
        d_c, d_p = self._stoch_d[idx], self._stoch_d[idx - 1]

        if k_p <= d_p and k_c > d_c and k_c <= 30.0:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.80, reasoning="Stoch RSI Oversold Bullish Cross")
        elif k_p >= d_p and k_c < d_c and k_c >= 70.0:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.80, reasoning="Stoch RSI Overbought Bearish Cross")
        return None


class MacdHistogramAccelerationStrategy(BaseStrategy):
    """MACD Histogram acceleration / slope divergence."""
    def __init__(self):
        super().__init__(
            name="MACD Histogram Acceleration",
            description="Detects momentum acceleration before moving average crossover occurs.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.0, 0.5, 7.0, 0.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 6.0, 2.0, 18.0, 1.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        _, _, self._hist = self.math.macd(c, 12, 26, 9)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 30:
            return None

        h0, h1, h2 = self._hist[idx], self._hist[idx - 1], self._hist[idx - 2]
        if h2 < h1 < h0 and h2 < 0 and h0 > 0:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="MACD Histogram Upward Acceleration")
        elif h2 > h1 > h0 and h2 > 0 and h0 < 0:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="MACD Histogram Downward Acceleration")
        return None


class HullMaDirectionFlipStrategy(BaseStrategy):
    """Zero-lag Hull Moving Average (HMA) direction flip."""
    def __init__(self):
        super().__init__(
            name="Hull MA Direction Flip",
            description="Zero-lag trend filter trading instantaneous slope reversals in Hull Moving Average.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("hma_period", "int", 16, 9, 30, 2, "Hull MA period"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.0, 0.6, 7.0, 0.4, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 6.0, 1.8, 18.0, 1.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        p = self.current_params["hma_period"]
        wma_half = self.math.ema(c, max(int(p / 2), 2))
        wma_full = self.math.ema(c, p)
        raw_diff = (2.0 * wma_half) - wma_full
        self._hma = self.math.ema(raw_diff, max(int(np.sqrt(p)), 2))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 20:
            return None

        h0, h1, h2 = self._hma[idx], self._hma[idx - 1], self._hma[idx - 2]
        if h2 >= h1 and h1 < h0:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Hull MA Bullish Direction Flip")
        elif h2 <= h1 and h1 > h0:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Hull MA Bearish Direction Flip")
        return None
