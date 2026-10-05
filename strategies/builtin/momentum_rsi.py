"""
momentum_rsi.py - Dual EMA Crossover + RSI Momentum Filter Strategy.
"""

from typing import Dict, Any, Optional, List
import numpy as np
from ..base_strategy import BaseStrategy, Signal
from ..parameter_space import Parameter
from math_engine import MathEngine


class MomentumRsiStrategy(BaseStrategy):
    """
    Momentum Trend Following Strategy.
    Enters CE when fast EMA crosses above slow EMA above trend filter with healthy RSI.
    Enters PE when fast EMA crosses below slow EMA below trend filter with weak RSI.
    """

    def __init__(self):
        super().__init__(
            name="Momentum RSI & EMA",
            description="Dual EMA trend crossover filtered by RSI momentum and baseline 50 EMA.",
            category="MOMENTUM"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("rsi_period", "int", 14, 5, 30, 1, description="RSI calculation period"))
        self.parameters.add(Parameter("rsi_upper", "float", 70.0, 60.0, 85.0, 2.0, description="RSI overbought cutoff"))
        self.parameters.add(Parameter("rsi_lower", "float", 30.0, 15.0, 40.0, 2.0, description="RSI oversold cutoff"))
        self.parameters.add(Parameter("fast_ema", "int", 9, 3, 20, 1, description="Fast EMA period"))
        self.parameters.add(Parameter("slow_ema", "int", 21, 10, 50, 1, description="Slow EMA period"))
        self.parameters.add(Parameter("trend_ema", "int", 50, 20, 200, 5, description="Higher timeframe trend EMA"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 5.0, 40.0, 2.5, description="Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 30.0, 10.0, 80.0, 5.0, description="Target profit points"))

    def prepare_session(self, candles: List[Dict[str, Any]], context: Dict[str, Any]) -> None:
        c = np.array([float(x.get("close", 0)) for x in candles], dtype=np.float64)
        fast_p = self.current_params["fast_ema"]
        slow_p = self.current_params["slow_ema"]
        trend_p = self.current_params["trend_ema"]
        rsi_p = self.current_params["rsi_period"]
        self._fast_ema = self.math.ema(c, fast_p)
        self._slow_ema = self.math.ema(c, slow_p)
        self._trend_ema = self.math.ema(c, trend_p)
        self._rsi = self.math.rsi(c, rsi_p)
        self._c = c

    def on_candle(
        self,
        candle: Dict[str, Any],
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Signal]:
        min_required = max(
            self.current_params["rsi_period"] + 5,
            self.current_params["slow_ema"] + 5,
            self.current_params["trend_ema"] + 5
        )
        idx = (context or {}).get("candle_index", len(history))
        if idx < min_required:
            return None

        fast_p = self.current_params["fast_ema"]
        slow_p = self.current_params["slow_ema"]
        trend_p = self.current_params["trend_ema"]
        rsi_p = self.current_params["rsi_period"]

        if hasattr(self, "_fast_ema"):
            cur_fast = self._fast_ema[idx]
            prev_fast = self._fast_ema[idx - 1]
            cur_slow = self._slow_ema[idx]
            prev_slow = self._slow_ema[idx - 1]
            cur_trend = self._trend_ema[idx]
            cur_rsi = self._rsi[idx]
            cur_close = self._c[idx]
        else:
            # Build close series including current candle
            closes = [float(c.get("close", 0)) for c in history] + [float(candle.get("close", 0))]
            p_arr = np.array(closes, dtype=np.float64)

            fast_ema = self.math.ema(p_arr, fast_p)
            slow_ema = self.math.ema(p_arr, slow_p)
            trend_ema = self.math.ema(p_arr, trend_p)
            rsi_vals = self.math.rsi(p_arr, rsi_p)

            cur_close = closes[-1]
            cur_fast = fast_ema[-1]
            prev_fast = fast_ema[-2]
            cur_slow = slow_ema[-1]
            prev_slow = slow_ema[-2]
            cur_trend = trend_ema[-1]
            cur_rsi = rsi_vals[-1]

        if np.isnan(cur_fast) or np.isnan(cur_slow) or np.isnan(cur_trend) or np.isnan(cur_rsi):
            return None

        time_str = str(candle.get("candle_time", ""))

        # Bullish Crossover: Fast crosses above Slow, Close > Trend EMA, RSI between 52 and upper bound
        if (
            prev_fast <= prev_slow
            and cur_fast > cur_slow
            and cur_close > cur_trend
            and 52.0 <= cur_rsi < self.current_params["rsi_upper"]
        ):
            return Signal(
                action="ENTER",
                market_bias="CALL",
                option_type="CE",
                strike=round(cur_close / 50.0) * 50.0,
                entry_price=cur_close,
                stop_loss=self.current_params["stop_loss_pts"],
                target=self.current_params["target_pts"],
                confidence=0.82,
                reasoning=f"Bullish EMA({fast_p}/{slow_p}) crossover above EMA({trend_p}), RSI={round(cur_rsi, 1)}",
                timestamp=time_str,
                metadata={"rsi": round(cur_rsi, 2), "fast_ema": round(cur_fast, 2), "slow_ema": round(cur_slow, 2)}
            )

        # Bearish Crossunder: Fast crosses below Slow, Close < Trend EMA, RSI between lower bound and 48
        if (
            prev_fast >= prev_slow
            and cur_fast < cur_slow
            and cur_close < cur_trend
            and self.current_params["rsi_lower"] < cur_rsi <= 48.0
        ):
            return Signal(
                action="ENTER",
                market_bias="PUT",
                option_type="PE",
                strike=round(cur_close / 50.0) * 50.0,
                entry_price=cur_close,
                stop_loss=self.current_params["stop_loss_pts"],
                target=self.current_params["target_pts"],
                confidence=0.82,
                reasoning=f"Bearish EMA({fast_p}/{slow_p}) crossunder below EMA({trend_p}), RSI={round(cur_rsi, 1)}",
                timestamp=time_str,
                metadata={"rsi": round(cur_rsi, 2), "fast_ema": round(cur_fast, 2), "slow_ema": round(cur_slow, 2)}
            )

        return None
