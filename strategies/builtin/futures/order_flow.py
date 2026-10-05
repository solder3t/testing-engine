from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class FuturesVolumeSpreadAnalysisStrategy(BaseStrategy):
    """
    Volume Spread Analysis (VSA): Detects ultra-high volume climactic stopping volume
    and subsequent test bars for high-probability futures reversals.
    """
    def __init__(self):
        super().__init__(
            name="Futures Volume Spread Analysis",
            description="VSA stopping volume detection with narrow spread test confirmation.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("volume_lookback", "int", 20, 10, 50, 5, "Lookback for average volume"))
        self.parameters.add(Parameter("volume_mult", "float", 2.0, 1.5, 3.5, 0.5, "Climactic volume multiplier"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 5.0, 40.0, 5.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 40.0, 15.0, 100.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        o = np.array([float(x.get("open", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)

        self._c, self._o, self._h, self._l, self._v = c, o, h, l, v
        self._v_sma = self.math.sma(v, self.current_params["volume_lookback"])
        self._spread = h - l

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["volume_lookback"] + 2:
            return None

        v_curr = self._v[idx - 1]
        v_avg = self._v_sma[idx - 1]
        mult = self.current_params["volume_mult"]

        if v_curr > v_avg * mult:
            # Climactic volume: if bar closed in top 30% of wide spread after down move -> Bullish absorption
            bar_spread = self._spread[idx - 1]
            if bar_spread > 0:
                pos_in_bar = (self._c[idx - 1] - self._l[idx - 1]) / bar_spread
                if pos_in_bar > 0.7 and self._c[idx] > self._h[idx - 1]:
                    return Signal(
                        action="BUY",
                        symbol=candle.get("symbol", "FUTURES"),
                        price=candle.get("close", 0.0),
                        timestamp=candle.get("timestamp", ""),
                        reason="VSA Bullish Stopping Volume Reversal",
                        stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                        target=candle.get("close", 0.0) + self.current_params["target_pts"]
                    )
                elif pos_in_bar < 0.3 and self._c[idx] < self._l[idx - 1]:
                    return Signal(
                        action="SELL",
                        symbol=candle.get("symbol", "FUTURES"),
                        price=candle.get("close", 0.0),
                        timestamp=candle.get("timestamp", ""),
                        reason="VSA Bearish Climactic Upthrust Reversal",
                        stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                        target=candle.get("close", 0.0) - self.current_params["target_pts"]
                    )
        return None


class OrderFlowImbalanceStrategy(BaseStrategy):
    """
    Order Flow Imbalance: Estimates aggressive buyer/seller delta pressure
    from candle tick micro-structure and volume clustering.
    """
    def __init__(self):
        super().__init__(
            name="Order Flow Imbalance",
            description="Cumulative delta imbalance momentum for futures scalping.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("delta_period", "int", 10, 5, 20, 1, "Rolling delta period"))
        self.parameters.add(Parameter("imbalance_threshold", "float", 0.65, 0.55, 0.85, 0.05, "Imbalance ratio threshold"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 12.0, 4.0, 30.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 35.0, 10.0, 80.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        o = np.array([float(x.get("open", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)

        rng = np.where((h - l) == 0, 1e-4, h - l)
        # Delta proxy: signed volume weighted by close position inside range
        delta = v * ((c - l) / rng - (h - c) / rng)
        p = self.current_params["delta_period"]
        cum_delta = np.zeros_like(delta)
        for i in range(len(delta)):
            cum_delta[i] = np.sum(delta[max(0, i - p + 1):i + 1])
            tot_v = np.sum(v[max(0, i - p + 1):i + 1])
            if tot_v > 0:
                cum_delta[i] = cum_delta[i] / tot_v

        self._c = c
        self._ratio = cum_delta

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["delta_period"] + 2:
            return None

        imb = self._ratio[idx]
        prev_imb = self._ratio[idx - 1]
        thresh = self.current_params["imbalance_threshold"]

        if imb > thresh and prev_imb <= thresh:
            return Signal(
                action="BUY",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Bullish Order Flow Delta Imbalance",
                stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) + self.current_params["target_pts"]
            )
        elif imb < -thresh and prev_imb >= -thresh:
            return Signal(
                action="SELL",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Bearish Order Flow Delta Imbalance",
                stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) - self.current_params["target_pts"]
            )
        return None


class FuturesOiDivergenceStrategy(BaseStrategy):
    """
    Open Interest (OI) & Price Trend Divergence: Identifies fresh long build-up
    or aggressive short covering surges.
    """
    def __init__(self):
        super().__init__(
            name="Futures OI Divergence",
            description="Trades Price-OI trend synergy and divergence patterns.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("trend_period", "int", 15, 5, 30, 5, "Price & OI trend period"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 12.0, 5.0, 30.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 36.0, 15.0, 80.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)
        # OI proxy from cumulative volume directional flow
        oi = np.cumsum(np.where(c >= np.roll(c, 1), v, -v))
        p = self.current_params["trend_period"]

        self._c = c
        self._c_sma = self.math.sma(c, p)
        self._oi_sma = self.math.sma(oi, p)
        self._oi = oi

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["trend_period"] + 2:
            return None

        p_up = self._c[idx] > self._c_sma[idx] and self._c[idx - 1] <= self._c_sma[idx - 1]
        oi_up = self._oi[idx] > self._oi_sma[idx]

        if p_up and oi_up:
            return Signal(
                action="BUY",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Long Buildup (Price & OI Co-expansion)",
                stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) + self.current_params["target_pts"]
            )

        p_down = self._c[idx] < self._c_sma[idx] and self._c[idx - 1] >= self._c_sma[idx - 1]
        if p_down and oi_up:
            return Signal(
                action="SELL",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Short Buildup (Price Fall & OI Expansion)",
                stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) - self.current_params["target_pts"]
            )
        return None
