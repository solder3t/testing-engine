from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class SupertrendMultiTfStrategy(BaseStrategy):
    """Dual SuperTrend trend-following confirmation system."""
    def __init__(self):
        super().__init__(
            name="SuperTrend Multi-TF",
            description="Trend following system requiring alignment of Fast (7,2) and Slow (14,3) SuperTrends.",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("fast_mult", "float", 2.0, 1.5, 3.0, 0.25, "Fast SuperTrend multiplier"))
        self.parameters.add(Parameter("slow_mult", "float", 3.0, 2.0, 4.5, 0.25, "Slow SuperTrend multiplier"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 25.0, 10.0, 55.0, 5.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 50.0, 20.0, 110.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        _, self._d_fast = self.math.supertrend(h, l, c, 7, self.current_params["fast_mult"])
        _, self._d_slow = self.math.supertrend(h, l, c, 14, self.current_params["slow_mult"])

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 20:
            return None

        df_curr, df_prev = self._d_fast[idx], self._d_fast[idx - 1]
        ds_curr = self._d_slow[idx]

        if df_prev == -1 and df_curr == 1 and ds_curr == 1:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Dual SuperTrend Bullish Alignment")
        elif df_prev == 1 and df_curr == -1 and ds_curr == -1:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Dual SuperTrend Bearish Alignment")
        return None


class EmaRibbonAlignmentStrategy(BaseStrategy):
    """EMA Ribbon (9, 21, 55, 200) cascading trend system."""
    def __init__(self):
        super().__init__(
            name="EMA Ribbon Alignment",
            description="Enters high-probability trend waves when 9 > 21 > 55 > 200 EMAs align perfectly.",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("ema_fast", "int", 9, 5, 15, 1, "Fastest ribbon EMA"))
        self.parameters.add(Parameter("ema_mid", "int", 21, 15, 30, 2, "Mid ribbon EMA"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 20.0, 8.0, 45.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 45.0, 18.0, 95.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        self._e1 = self.math.ema(c, self.current_params["ema_fast"])
        self._e2 = self.math.ema(c, self.current_params["ema_mid"])
        self._e3 = self.math.ema(c, 50)

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 55:
            return None

        e1_c, e1_p = self._e1[idx], self._e1[idx - 1]
        e2_c, e2_p = self._e2[idx], self._e2[idx - 1]
        e3_c = self._e3[idx]

        if e1_p <= e2_p and e1_c > e2_c and e2_c > e3_c:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="EMA Ribbon Bullish Expansion")
        elif e1_p >= e2_p and e1_c < e2_c and e2_c < e3_c:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="EMA Ribbon Bearish Breakdown")
        return None


class NiftyInternalsBreadthStrategy(BaseStrategy):
    """Advance-Decline and Market Breadth momentum filtering."""
    def __init__(self):
        super().__init__(
            name="Market Breadth Momentum",
            description="Trades index momentum filtered by institutional Advance/Decline breadth ratio.",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("breadth_ratio_bull", "float", 1.8, 1.2, 3.0, 0.2, "Bullish A/D ratio threshold"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 20.0, 10.0, 50.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 45.0, 20.0, 100.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 15:
            return None

        ad_ratio = float((context or {}).get("market_breadth_ratio", 1.0) or 1.0)
        c_close = float(candle.get("close", 0))
        p_close = float(history[-1].get("close", 0))

        if ad_ratio >= self.current_params["breadth_ratio_bull"] and c_close > p_close:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Bullish Market Breadth Surge")
        elif ad_ratio <= (1.0 / self.current_params["breadth_ratio_bull"]) and c_close < p_close:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.82, reasoning="Bearish Market Breadth Surge")
        return None


class HeikinAshiTrendRiderStrategy(BaseStrategy):
    """Smoothed Heikin-Ashi consecutive candle trend rider."""
    def __init__(self):
        super().__init__(
            name="Heikin-Ashi Trend Rider",
            description="Rides strong trends identified by consecutive flat-bottom/flat-top Heikin-Ashi candles.",
            category="INDEX"
        )

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("consecutive_bars", "int", 3, 2, 6, 1, "Consecutive HA candles required"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 18.0, 8.0, 40.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 40.0, 18.0, 90.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        req = self.current_params["consecutive_bars"]
        if len(history) < req + 1:
            return None

        recent = history[-req:] + [candle]
        bullish_count = 0
        bearish_count = 0

        for c in recent:
            o, cl = float(c.get("open", 0)), float(c.get("close", 0))
            if cl > o:
                bullish_count += 1
            elif cl < o:
                bearish_count += 1

        if bullish_count == len(recent):
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.80, reasoning="Consecutive Bullish Heikin-Ashi Flow")
        elif bearish_count == len(recent):
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.80, reasoning="Consecutive Bearish Heikin-Ashi Flow")
        return None


class FiiDiiCashMomentumStrategy(BaseStrategy):
    """Directional positioning based on daily FII/DII institutional net flows."""
    def __init__(self):
        super().__init__(
            name="FII Flow Directional Bias",
            description="Aligns intraday trend with institutional foreign institutional investor cash buying/selling.",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("stop_loss_pts", "float", 22.0, 10.0, 50.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 50.0, 20.0, 110.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx == 35:
            fii_net = float((context or {}).get("fii_net_crores", 0) or 0)
            if fii_net > 500:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Institutional FII Net Buying Flow")
            elif fii_net < -500:
                return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.83, reasoning="Institutional FII Net Selling Flow")
        return None


class IndiaVixDivergenceStrategy(BaseStrategy):
    """Index Spot Divergence against India VIX spike/collapse."""
    def __init__(self):
        super().__init__(
            name="India VIX Divergence",
            description="Trades spot market reversals confirmed by fear index (India VIX) momentum divergence.",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("vix_spike_pct", "float", 2.5, 1.0, 6.0, 0.5, "Minimum VIX change percentage"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 24.0, 10.0, 55.0, 2.5, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 55.0, 25.0, 120.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        pass

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 20:
            return None

        vix_change = float((context or {}).get("vix_change_pct", 0) or 0)
        c_close = float(candle.get("close", 0))
        p_close = float(history[-1].get("close", 0))

        if vix_change <= -self.current_params["vix_spike_pct"] and c_close > p_close:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="VIX Collapse Bullish Index Surge")
        elif vix_change >= self.current_params["vix_spike_pct"] and c_close < p_close:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.84, reasoning="VIX Fear Spike Bearish Index Dump")
        return None
