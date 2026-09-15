"""
strategies/rsi_momentum.py — RSI Momentum & Dual EMA Strategy (from BOT 2.0).

Follows trend breakouts when fast EMA (9) crosses slow EMA (21)
confirmed by RSI(14) directional momentum (>60 for Long, <40 for Short).
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import calculate_ema, calculate_rsi, calculate_atr
from config import TRADING_START, TRADING_END


class RsiMomentumStrategy(BaseStrategy):
    """Trend-following momentum strategy with RSI confirmation."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "rsi_period": 14,
            "rsi_long_cutoff": 60.0,
            "rsi_short_cutoff": 40.0,
            "fast_ema": 9,
            "slow_ema": 21,
            "sl_pts": 15.0,
            "target_pts": 35.0
        }
        if params:
            default_params.update(params)
        super().__init__(name="RSI_Momentum_Breakout", params=default_params)
        self.bar_history: Dict[str, List[Dict[str, float]]] = {}

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        if not (TRADING_START <= time_part <= TRADING_END):
            return []

        signals = []
        min_bars = max(self.params["rsi_period"], self.params["slow_ema"]) + 3

        for sym, q in quotes.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(q)

            history = self.bar_history[sym]
            if len(history) < min_bars:
                continue

            closes = np.array([bar.get("close", bar.get("ltp", 0.0)) for bar in history], dtype=float)
            closes_s = pd.Series(closes)
            fast_ema = calculate_ema(closes_s, self.params["fast_ema"]).values
            slow_ema = calculate_ema(closes_s, self.params["slow_ema"]).values
            rsi = calculate_rsi(closes_s, self.params["rsi_period"]).values

            curr_c = closes[-1]
            curr_fast = fast_ema[-1]
            prev_fast = fast_ema[-2]
            curr_slow = slow_ema[-1]
            prev_slow = slow_ema[-2]
            curr_rsi = rsi[-1]

            # Bullish Crossover + RSI Momentum
            if prev_fast <= prev_slow and curr_fast > curr_slow and curr_rsi >= self.params["rsi_long_cutoff"]:
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": curr_c,
                    "sl": round(curr_c - self.params["sl_pts"], 2),
                    "target": round(curr_c + self.params["target_pts"], 2),
                    "score": 80,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {"strategy": self.name, "rsi": round(curr_rsi, 1), "fast_ema": curr_fast}
                })

            # Bearish Crossover + RSI Weakness
            elif prev_fast >= prev_slow and curr_fast < curr_slow and curr_rsi <= self.params["rsi_short_cutoff"]:
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.SELL,
                    "price": curr_c,
                    "sl": round(curr_c + self.params["sl_pts"], 2),
                    "target": round(curr_c - self.params["target_pts"], 2),
                    "score": 80,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {"strategy": self.name, "rsi": round(curr_rsi, 1), "fast_ema": curr_fast}
                })

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()
