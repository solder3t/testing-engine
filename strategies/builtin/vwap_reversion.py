"""
vwap_reversion.py - Bollinger Bands & VWAP Mean Reversion Strategy.
"""

from typing import Dict, Any, Optional, List
import numpy as np
from ..base_strategy import BaseStrategy, Signal
from ..parameter_space import Parameter
from math_engine import MathEngine


class VwapReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy exploiting extreme Bollinger Band deviations back toward VWAP.
    Enters CE on Lower Band rejection bounce.
    Enters PE on Upper Band exhaustion rejection.
    """

    def __init__(self):
        super().__init__(
            name="VWAP Mean Reversion",
            description="Mean reversion from 2.0+ standard deviation Bollinger Band extremes back to VWAP.",
            category="MEAN_REVERSION"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("bb_period", "int", 20, 10, 30, 2, description="Bollinger Bands lookback"))
        self.parameters.add(Parameter("bb_std", "float", 2.0, 1.5, 3.0, 0.25, description="Standard deviations multiplier"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 12.0, 5.0, 30.0, 2.0, description="Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 25.0, 10.0, 50.0, 5.0, description="Target profit points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        v = np.array([float(x.get("volume", 0)) for x in candles], dtype=np.float64)
        period = self.current_params["bb_period"]
        std = self.current_params["bb_std"]
        self._upper, self._middle, self._lower = self.math.bollinger_bands(c, period, std)
        self._vwap = self.math.vwap(h, l, c, v)
        self._c = c

    def on_candle(
        self,
        candle: Dict[str, Any],
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Signal]:
        period = self.current_params["bb_period"]
        idx = (context or {}).get("candle_index", len(history))
        if idx < period + 2:
            return None

        if hasattr(self, "_upper"):
            cur_c = self._c[idx]
            prev_c = self._c[idx - 1]
            prev2_c = self._c[idx - 2]
            cur_low_band = self._lower[idx]
            cur_high_band = self._upper[idx]
            prev_low_band = self._lower[idx - 1]
            prev_high_band = self._upper[idx - 1]
            cur_vwap = self._vwap[idx]
        else:
            closes = [float(c.get("close", 0)) for c in history] + [float(candle.get("close", 0))]
            highs = [float(c.get("high", 0)) for c in history] + [float(candle.get("high", 0))]
            lows = [float(c.get("low", 0)) for c in history] + [float(candle.get("low", 0))]
            vols = [float(c.get("volume", 0)) for c in history] + [float(candle.get("volume", 0))]

            p_arr = np.array(closes, dtype=np.float64)
            upper, middle, lower = self.math.bollinger_bands(p_arr, period, self.current_params["bb_std"])
            vwap_arr = self.math.vwap(highs, lows, closes, vols)

            cur_c = closes[-1]
            prev_c = closes[-2]
            prev2_c = closes[-3]
            cur_low_band = lower[-1]
            cur_high_band = upper[-1]
            prev_low_band = lower[-2]
            prev_high_band = upper[-2]
            cur_vwap = vwap_arr[-1]

        time_str = str(candle.get("candle_time", ""))

        # CE Entry: Prior candle dipped below lower band, current candle closes back inside (bullish hammer/bounce)
        if prev_c <= prev_low_band and cur_c > cur_low_band and cur_c < cur_vwap:
            return Signal(
                action="ENTER",
                market_bias="CALL",
                option_type="CE",
                strike=round(cur_c / 50.0) * 50.0,
                entry_price=cur_c,
                stop_loss=self.current_params["stop_loss_pts"],
                target=self.current_params["target_pts"],
                confidence=0.78,
                reasoning=f"Lower Band oversold bounce back towards VWAP (Spot={round(cur_c, 1)}, VWAP={round(cur_vwap, 1)})",
                timestamp=time_str,
                metadata={"bb_lower": round(cur_low_band, 2), "vwap": round(cur_vwap, 2)}
            )

        # PE Entry: Prior candle pierced above upper band, current candle closes back inside (exhaustion/rejection)
        if prev_c >= prev_high_band and cur_c < cur_high_band and cur_c > cur_vwap:
            return Signal(
                action="ENTER",
                market_bias="PUT",
                option_type="PE",
                strike=round(cur_c / 50.0) * 50.0,
                entry_price=cur_c,
                stop_loss=self.current_params["stop_loss_pts"],
                target=self.current_params["target_pts"],
                confidence=0.78,
                reasoning=f"Upper Band exhaustion rejection back towards VWAP (Spot={round(cur_c, 1)}, VWAP={round(cur_vwap, 1)})",
                timestamp=time_str,
                metadata={"bb_upper": round(cur_high_band, 2), "vwap": round(cur_vwap, 2)}
            )

        return None
