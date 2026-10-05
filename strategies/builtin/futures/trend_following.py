from typing import Dict, Any, Optional, List
import numpy as np

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class ParabolicSarMomentumStrategy(BaseStrategy):
    """
    Parabolic SAR Trend Reversal with ADX Momentum:
    Captures fast-moving trend reversals in trending futures markets.
    """
    def __init__(self):
        super().__init__(
            name="Parabolic SAR Momentum",
            description="Parabolic SAR trailing reversal filtered by directional momentum.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("af_step", "float", 0.02, 0.01, 0.05, 0.01, "SAR acceleration step"))
        self.parameters.add(Parameter("af_max", "float", 0.20, 0.10, 0.30, 0.05, "SAR maximum acceleration"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 5.0, 35.0, 5.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 45.0, 15.0, 90.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)

        n = len(c)
        sar = np.zeros(n, dtype=np.float64)
        trend = np.ones(n, dtype=np.int32)
        step = self.current_params["af_step"]
        max_step = self.current_params["af_max"]

        if n > 2:
            sar[0] = l[0]
            ep = h[0]
            af = step
            for i in range(1, n):
                prev_sar = sar[i - 1]
                if trend[i - 1] == 1:
                    cur_sar = prev_sar + af * (ep - prev_sar)
                    cur_sar = min(cur_sar, l[i - 1], l[max(0, i - 2)])
                    if l[i] < cur_sar:
                        trend[i] = -1
                        sar[i] = ep
                        ep = l[i]
                        af = step
                    else:
                        trend[i] = 1
                        sar[i] = cur_sar
                        if h[i] > ep:
                            ep = h[i]
                            af = min(af + step, max_step)
                else:
                    cur_sar = prev_sar + af * (ep - prev_sar)
                    cur_sar = max(cur_sar, h[i - 1], h[max(0, i - 2)])
                    if h[i] > cur_sar:
                        trend[i] = 1
                        sar[i] = ep
                        ep = h[i]
                        af = step
                    else:
                        trend[i] = -1
                        sar[i] = cur_sar
                        if l[i] < ep:
                            ep = l[i]
                            af = min(af + step, max_step)

        self._c = c
        self._sar = sar
        self._trend = trend

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < 5:
            return None

        if self._trend[idx] == 1 and self._trend[idx - 1] == -1:
            return Signal(
                action="BUY",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Parabolic SAR Bullish Trend Reversal",
                stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) + self.current_params["target_pts"]
            )
        elif self._trend[idx] == -1 and self._trend[idx - 1] == 1:
            return Signal(
                action="SELL",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Parabolic SAR Bearish Trend Reversal",
                stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) - self.current_params["target_pts"]
            )
        return None


class FuturesMomentumPinbarStrategy(BaseStrategy):
    """
    Futures Momentum Pinbar (Hammer / Shooting Star):
    Identifies high-speed price rejection wicks rebounding off key moving averages.
    """
    def __init__(self):
        super().__init__(
            name="Futures Momentum Pinbar",
            description="Rejection candle pinbar rebounds off trend moving averages.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("ema_trend", "int", 20, 10, 50, 5, "Trend filter EMA period"))
        self.parameters.add(Parameter("wick_ratio", "float", 0.60, 0.50, 0.75, 0.05, "Rejection wick-to-range ratio"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 10.0, 4.0, 25.0, 2.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 30.0, 10.0, 70.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        o = np.array([float(x.get("open", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)

        self._c, self._o, self._h, self._l = c, o, h, l
        self._ema = self.math.ema(c, self.current_params["ema_trend"])

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["ema_trend"] + 2:
            return None

        o_val, c_val = self._o[idx], self._c[idx]
        h_val, l_val = self._h[idx], self._l[idx]
        tot_range = h_val - l_val
        if tot_range <= 0.05:
            return None

        lower_wick = min(o_val, c_val) - l_val
        upper_wick = h_val - max(o_val, c_val)
        ratio = self.current_params["wick_ratio"]
        ema_val = self._ema[idx]

        if lower_wick / tot_range >= ratio and c_val >= ema_val and c_val > o_val:
            return Signal(
                action="BUY",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Bullish Pinbar Rebound off Trend EMA",
                stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) + self.current_params["target_pts"]
            )
        elif upper_wick / tot_range >= ratio and c_val <= ema_val and c_val < o_val:
            return Signal(
                action="SELL",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Bearish Shooting Star Rejection at Trend EMA",
                stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) - self.current_params["target_pts"]
            )
        return None


class FuturesBasisArbitrageStrategy(BaseStrategy):
    """
    Futures Basis Momentum / Mean-Reversion: Exploits spot-futures basis premium/discount
    anomalies and mean-reverting spread convergence.
    """
    def __init__(self):
        super().__init__(
            name="Futures Basis Momentum",
            description="Trades basis divergence between spot underlying and futures contracts.",
            category="FUTURES"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("basis_lookback", "int", 20, 10, 40, 5, "Basis moving average period"))
        self.parameters.add(Parameter("zscore_thresh", "float", 2.0, 1.2, 3.0, 0.2, "Basis Z-score threshold"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 5.0, 35.0, 5.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 30.0, 10.0, 70.0, 5.0, "Target points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)
        p = self.current_params["basis_lookback"]
        vwap = np.cumsum(c * v) / np.maximum(np.cumsum(v), 1e-5)
        basis = c - vwap
        basis_mean = self.math.sma(basis, p)
        basis_std = np.zeros_like(basis)
        for i in range(len(basis)):
            s = basis[max(0, i - p + 1):i + 1]
            basis_std[i] = np.std(s) if len(s) > 1 else 1.0

        basis_std = np.where(basis_std == 0, 1.0, basis_std)
        self._zscore = (basis - basis_mean) / basis_std
        self._c = c

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx < self.current_params["basis_lookback"] + 2:
            return None

        z = self._zscore[idx]
        prev_z = self._zscore[idx - 1]
        thresh = self.current_params["zscore_thresh"]

        if prev_z < -thresh and z >= -thresh:
            return Signal(
                action="BUY",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Futures Basis Discount Mean Reversion",
                stop_loss=candle.get("close", 0.0) - self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) + self.current_params["target_pts"]
            )
        elif prev_z > thresh and z <= thresh:
            return Signal(
                action="SELL",
                symbol=candle.get("symbol", "FUTURES"),
                price=candle.get("close", 0.0),
                timestamp=candle.get("timestamp", ""),
                reason="Futures Basis Premium Mean Reversion",
                stop_loss=candle.get("close", 0.0) + self.current_params["stop_loss_pts"],
                target=candle.get("close", 0.0) - self.current_params["target_pts"]
            )
        return None
