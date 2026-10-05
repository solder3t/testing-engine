from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class AtrVolatilityExpansionStrategy(BaseStrategy):
    """
    ATR Volatility Expansion: Enters when current candle range expands dramatically
    beyond the rolling ATR, signalling fresh institutional momentum injection.
    """
    def __init__(self):
        super().__init__(
            name="ATR Volatility Expansion",
            description="Explosive ATR range expansion breakout system.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("atr_period", "int", 14, 7, 28, 1, "ATR period"))
        self.parameters.add(Parameter("expansion_mult", "float", 1.8, 1.2, 3.0, 0.2, "ATR expansion multiplier"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 14.0, 5.0, 35.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 42.0, 15.0, 90.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)

        self._c, self._h, self._l = c, h, l
        self._atr = self.math.atr(h, l, c, self.current_params["atr_period"])

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["atr_period"] + 2:
            return None

        curr_range = self._h[idx] - self._l[idx]
        atr_val = self._atr[idx - 1]
        mult = self.current_params["expansion_mult"]

        if curr_range > atr_val * mult:
            # Bullish expansion: candle closed strongly in upper half
            mid = (self._h[idx] + self._l[idx]) / 2.0
            if self._c[idx] > mid and self._c[idx] > self._c[idx - 1]:
                return Signal(
                    action="BUY",
                    symbol=candle.get("symbol", "FUTURES"),
                    price=candle.get("close", 0.0),
                    timestamp=candle.get("timestamp", ""),
                    reason="Bullish ATR Volatility Expansion",
                    stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                    target=candle.get("close", 0.0) + self.current_params["target_pts"]
                )
            elif self._c[idx] < mid and self._c[idx] < self._c[idx - 1]:
                return Signal(
                    action="SELL",
                    symbol=candle.get("symbol", "FUTURES"),
                    price=candle.get("close", 0.0),
                    timestamp=candle.get("timestamp", ""),
                    reason="Bearish ATR Volatility Expansion",
                    stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                    target=candle.get("close", 0.0) - self.current_params["target_pts"]
                )
        return None


class MultiDayBreakoutStrategy(BaseStrategy):
    """
    Multi-Day Breakout: Trades breakouts of the prior session's high or low
    when confirmed by expanding volume on the opening drive.
    """
    def __init__(self):
        super().__init__(
            name="Multi-Day High/Low Breakout",
            description="Breaks out above/below previous session high and low boundaries.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("breakout_buffer_pts", "float", 2.0, 1.0, 10.0, 1.0, "Breakout buffer points"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 16.0, 5.0, 40.0, 5.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 45.0, 15.0, 100.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)

        # First 30 candles define the session benchmark baseline
        cutoff = min(30, len(c))
        ref_h = np.max(h[:cutoff]) if cutoff > 0 else c[0]
        ref_l = np.min(l[:cutoff]) if cutoff > 0 else c[0]

        self._c = c
        self._ref_h = ref_h
        self._ref_l = ref_l

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 35 or idx > 330:
            return None

        c_curr, c_prev = self._c[idx], self._c[idx - 1]
        buf = self.current_params["breakout_buffer_pts"]
        h_lvl = self._ref_h + buf
        l_lvl = self._ref_l - buf

        if c_prev <= h_lvl and c_curr > h_lvl:
            return Signal(
                action="BUY",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Multi-Day High Range Expansion Breakout",
                stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) + self.current_params["target_pts"]
            )
        elif c_prev >= l_lvl and c_curr < l_lvl:
            return Signal(
                action="SELL",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Multi-Day Low Range Expansion Breakdown",
                stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) - self.current_params["target_pts"]
            )
        return None


class ChoppinessBreakoutStrategy(BaseStrategy):
    """
    Choppiness Index Breakout: Identifies low volatility coiling (Choppiness Index < 38.2)
    and rides the directional trend explosion as the market breaks into a trend.
    """
    def __init__(self):
        super().__init__(
            name="Choppiness Index Breakout",
            description="Exploits market consolidation coiling and explosive trending transitions.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("chop_period", "int", 14, 7, 28, 1, "Choppiness period"))
        self.parameters.add(Parameter("chop_threshold", "float", 40.0, 30.0, 50.0, 2.0, "Choppiness trend trigger threshold"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 12.0, 5.0, 30.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 36.0, 15.0, 80.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)

        p = self.current_params["chop_period"]
        atr = self.math.atr(h, l, c, 1)
        n = len(c)
        chop = np.full(n, 50.0, dtype=np.float64)

        for i in range(p, n):
            sum_atr = np.sum(atr[i - p + 1:i + 1])
            max_h = np.max(h[i - p + 1:i + 1])
            min_l = np.min(l[i - p + 1:i + 1])
            diff = max_h - min_l
            if diff > 0 and sum_atr > 0:
                chop[i] = 100.0 * (np.log10(sum_atr / diff) / np.log10(p))

        self._c = c
        self._chop = chop
        self._ema = self.math.ema(c, p)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["chop_period"] + 2:
            return None

        chop_curr = self._chop[idx]
        thresh = self.current_params["chop_threshold"]

        if chop_curr < thresh:
            if self._c[idx] > self._ema[idx] and self._c[idx - 1] <= self._ema[idx - 1]:
                return Signal(
                    action="BUY",
                    symbol=candle.get("symbol", "FUTURES"),
                    price=candle.get("close", 0.0),
                    timestamp=candle.get("timestamp", ""),
                    reason="Choppiness Breakout Bullish Trend Initiation",
                    stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                    target=candle.get("close", 0.0) + self.current_params["target_pts"]
                )
            elif self._c[idx] < self._ema[idx] and self._c[idx - 1] >= self._ema[idx - 1]:
                return Signal(
                    action="SELL",
                    symbol=candle.get("symbol", "FUTURES"),
                    price=candle.get("close", 0.0),
                    timestamp=candle.get("timestamp", ""),
                    reason="Choppiness Breakout Bearish Trend Initiation",
                    stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                    target=candle.get("close", 0.0) - self.current_params["target_pts"]
                )
        return None


class FuturesDualThrustStrategy(BaseStrategy):
    """
    Classic Institutional Dual Thrust: Calculates asymmetrical upper and lower
    breakout triggers based on range dynamics of preceding periods.
    """
    def __init__(self):
        super().__init__(
            name="Futures Dual Thrust",
            description="Dual Thrust asymmetric range breakout algorithm for futures momentum.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("thrust_lookback", "int", 20, 10, 40, 5, "Lookback range period"))
        self.parameters.add(Parameter("k1", "float", 0.5, 0.3, 0.8, 0.1, "Upper thrust multiplier"))
        self.parameters.add(Parameter("k2", "float", 0.5, 0.3, 0.8, 0.1, "Lower thrust multiplier"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 14.0, 5.0, 35.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 42.0, 15.0, 90.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        o = np.array([float(x.get("open", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)

        p = self.current_params["thrust_lookback"]
        k1 = self.current_params["k1"]
        k2 = self.current_params["k2"]

        hh = np.max(h[:p]) if len(h) >= p else h[0]
        hc = np.max(c[:p]) if len(c) >= p else c[0]
        lc = np.min(c[:p]) if len(c) >= p else c[0]
        ll = np.min(l[:p]) if len(l) >= p else l[0]
        rng = max(hh - lc, hc - ll)

        base_open = o[p] if len(o) > p else o[0]
        self._buy_trigger = base_open + k1 * rng
        self._sell_trigger = base_open - k2 * rng
        self._c = c
        self._p = p

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx <= self._p:
            return None

        c_curr, c_prev = self._c[idx], self._c[idx - 1]

        if c_prev <= self._buy_trigger and c_curr > self._buy_trigger:
            return Signal(
                action="BUY",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Dual Thrust Bullish Range Trigger",
                stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) + self.current_params["target_pts"]
            )
        elif c_prev >= self._sell_trigger and c_curr < self._sell_trigger:
            return Signal(
                action="SELL",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Dual Thrust Bearish Range Trigger",
                stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) - self.current_params["target_pts"]
            )
        return None
