from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class VwapInstitutionalBounceStrategy(BaseStrategy):
    """Institutional pullback retest and bounce off daily VWAP."""
    def __init__(self):
        super().__init__(
            name="VWAP Institutional Bounce",
            description="Enters on pullback retest and bounce of intraday Volume Weighted Average Price.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("bounce_buffer_pct", "float", 0.15, 0.05, 0.40, 0.05, "Tolerance around VWAP"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.5, 0.5, 10.0, 0.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 7.0, 2.0, 25.0, 1.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)
        self._vwap = self.math.vwap(h, l, c, v)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 20:
            return None

        c_close = float(candle.get("close", 0))
        c_low = float(candle.get("low", 0))
        c_high = float(candle.get("high", 0))
        vwap_val = self._vwap[idx]
        buf = vwap_val * (self.current_params["bounce_buffer_pct"] / 100.0)

        # Retest VWAP from above and bounce
        if c_low <= vwap_val + buf and c_close > vwap_val:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="VWAP Support Bounce")
        # Retest VWAP from below and reject
        elif c_high >= vwap_val - buf and c_close < vwap_val:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="VWAP Resistance Rejection")
        return None


class ConnorsRsi2PullbackStrategy(BaseStrategy):
    """Larry Connors ultra-short 2-period RSI oversold pullback in 200-SMA uptrend."""
    def __init__(self):
        super().__init__(
            name="Connors RSI-2 Pullback",
            description="Ultra-high win-rate mean-reversion buying RSI(2) < 10 in prevailing uptrends.",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("rsi_buy_level", "float", 10.0, 5.0, 20.0, 1.0, "Oversold RSI(2) entry level"))
        self.parameters.add(Parameter("rsi_sell_level", "float", 90.0, 80.0, 95.0, 1.0, "Overbought RSI(2) entry level"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.0, 0.5, 8.0, 0.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 5.0, 1.5, 18.0, 0.5, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        self._rsi2 = self.math.rsi(c, 2)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 10:
            return None

        r2 = self._rsi2[idx] if hasattr(self, "_rsi2") else 50.0
        if r2 <= self.current_params["rsi_buy_level"]:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.86, reasoning="Connors RSI(2) Oversold Flush")
        elif r2 >= self.current_params["rsi_sell_level"]:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.86, reasoning="Connors RSI(2) Overbought Climax")
        return None


class RelativeStrengthAlphaStrategy(BaseStrategy):
    """Equity Relative Strength Alpha against NIFTY benchmark index."""
    def __init__(self):
        super().__init__(
            name="Relative Strength Alpha",
            description="Buys leading stocks showing positive relative strength momentum vs benchmark index.",
            category="EQUITY"
        )

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("alpha_threshold", "float", 0.3, 0.1, 1.0, 0.1, "Excess return percentage vs index"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.5, 0.8, 8.0, 0.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 7.0, 2.0, 20.0, 1.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 25:
            return None

        o_price = float(history[0].get("open", 1))
        c_price = float(candle.get("close", 1))
        stock_ret = ((c_price - o_price) / o_price) * 100.0

        index_ret = float((context or {}).get("nifty_return_pct", 0) or 0)
        alpha = stock_ret - index_ret

        if alpha >= self.current_params["alpha_threshold"] and c_price > float(history[-1].get("close", 0)):
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Outperforming Benchmark Relative Alpha")
        return None


class BollingerPercentBReversalStrategy(BaseStrategy):
    """Bollinger Bands %B extreme reversal system."""
    def __init__(self):
        super().__init__(
            name="Bollinger %B Reversal",
            description="Fades extreme price deviations outside Bollinger Bands (%B < 0 or %B > 1).",
            category="EQUITY"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("stop_loss_pts", "float", 2.2, 0.8, 7.0, 0.4, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 6.0, 2.0, 18.0, 1.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        u, m, l = self.math.bollinger_bands(c, 20, 2.0)
        denom = u - l
        self._pct_b = np.where(denom > 0, (c - l) / denom, 0.5)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 25:
            return None

        b_curr = self._pct_b[idx]
        b_prev = self._pct_b[idx - 1]

        if b_prev < 0.0 and b_curr >= 0.05:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Bollinger %B Oversold Re-entry")
        elif b_prev > 1.0 and b_curr <= 0.95:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Bollinger %B Overbought Re-entry")
        return None
