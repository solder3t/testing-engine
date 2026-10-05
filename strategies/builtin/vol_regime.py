"""
vol_regime.py - Adaptive Volatility Regime Switching Strategy.
"""

from typing import Dict, Any, Optional, List
import numpy as np
from ..base_strategy import BaseStrategy, Signal
from ..parameter_space import Parameter
from math_engine import MathEngine


class VolRegimeStrategy(BaseStrategy):
    """
    Volatility-Adaptive Regime Strategy.
    Dynamically adjusts position holding horizon, stop-loss, and profit targets
    based on prevailing volatility regime (ATR / India VIX).
    """

    def __init__(self):
        super().__init__(
            name="Volatility Regime Adaptive",
            description="Dynamic ATR & SuperTrend strategy that auto-scales risk/reward to market volatility regimes.",
            category="VOLATILITY_ADAPTIVE"
        )
        self.math = MathEngine(use_gpu=False)
        self.last_dir = 0

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("st_period", "int", 10, 7, 20, 1, description="SuperTrend lookback"))
        self.parameters.add(Parameter("st_multiplier", "float", 3.0, 1.5, 5.0, 0.5, description="SuperTrend ATR multiplier"))
        self.parameters.add(Parameter("base_sl_pts", "float", 15.0, 8.0, 30.0, 2.0, description="Base Stop Loss points"))
        self.parameters.add(Parameter("base_target_pts", "float", 30.0, 15.0, 60.0, 5.0, description="Base Target points"))

    def reset(self) -> None:
        self.last_dir = 0

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        h = np.array([float(x.get("high", 0)) for x in candles], dtype=np.float64)
        l = np.array([float(x.get("low", 0)) for x in candles], dtype=np.float64)
        period = self.current_params["st_period"]
        mult = self.current_params["st_multiplier"]
        self._st_vals, self._st_dirs = self.math.supertrend(h, l, c, period, mult)
        self._atr = self.math.atr(h, l, c, 14)
        self._c = c

    def on_candle(
        self,
        candle: Dict[str, Any],
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Signal]:
        period = self.current_params["st_period"]
        idx = (context or {}).get("candle_index", len(history))
        if idx < period + 5:
            return None

        if hasattr(self, "_st_dirs"):
            cur_dir = self._st_dirs[idx]
            prev_dir = self._st_dirs[idx - 1]
            cur_atr = self._atr[idx]
            cur_close = self._c[idx]
        else:
            closes = [float(c.get("close", 0)) for c in history] + [float(candle.get("close", 0))]
            highs = [float(c.get("high", 0)) for c in history] + [float(candle.get("high", 0))]
            lows = [float(c.get("low", 0)) for c in history] + [float(candle.get("low", 0))]

            h_arr = np.array(highs, dtype=np.float64)
            l_arr = np.array(lows, dtype=np.float64)
            c_arr = np.array(closes, dtype=np.float64)

            mult = self.current_params["st_multiplier"]
            st_vals, st_dirs = self.math.supertrend(h_arr, l_arr, c_arr, period, mult)
            atr_vals = self.math.atr(h_arr, l_arr, c_arr, 14)

            cur_dir = st_dirs[-1]
            prev_dir = st_dirs[-2]
            cur_atr = atr_vals[-1]
            cur_close = closes[-1]
        time_str = str(candle.get("candle_time", ""))

        # Adaptive SL & Target based on current candle ATR
        vol_scalar = max(0.6, min(2.0, cur_atr / 15.0)) if not np.isnan(cur_atr) and cur_atr > 0 else 1.0
        adaptive_sl = round(self.current_params["base_sl_pts"] * vol_scalar, 1)
        adaptive_tgt = round(self.current_params["base_target_pts"] * vol_scalar, 1)

        # Bullish Flip (-1 to +1)
        if prev_dir == -1 and cur_dir == 1:
            return Signal(
                action="ENTER",
                market_bias="CALL",
                option_type="CE",
                strike=round(cur_close / 50.0) * 50.0,
                entry_price=cur_close,
                stop_loss=adaptive_sl,
                target=adaptive_tgt,
                confidence=0.83,
                reasoning=f"SuperTrend Bullish Flip with ATR={round(cur_atr, 1)} (Vol Scalar={round(vol_scalar, 2)})",
                timestamp=time_str,
                metadata={"atr": round(cur_atr, 2), "vol_scalar": round(vol_scalar, 2)}
            )

        # Bearish Flip (+1 to -1)
        if prev_dir == 1 and cur_dir == -1:
            return Signal(
                action="ENTER",
                market_bias="PUT",
                option_type="PE",
                strike=round(cur_close / 50.0) * 50.0,
                entry_price=cur_close,
                stop_loss=adaptive_sl,
                target=adaptive_tgt,
                confidence=0.83,
                reasoning=f"SuperTrend Bearish Flip with ATR={round(cur_atr, 1)} (Vol Scalar={round(vol_scalar, 2)})",
                timestamp=time_str,
                metadata={"atr": round(cur_atr, 2), "vol_scalar": round(vol_scalar, 2)}
            )

        return None
