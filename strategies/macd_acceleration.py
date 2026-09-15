"""
strategies/macd_acceleration.py — MACD Histogram Acceleration Strategy.

Monitors 2nd-derivative velocity of the MACD histogram.
Captures momentum expansion surges where histogram expansion accelerates in the direction
of the primary trend before retail indicators trigger lagging crossovers.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import calculate_macd
from config import TRADING_START, TRADING_END


class MacdAccelerationStrategy(BaseStrategy):
    """MACD Histogram Momentum Acceleration Strategy."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "sl_pts": 15.0,
            "target_pts": 35.0,
            "max_trades_per_sym": 2
        }
        if params:
            default_params.update(params)
        super().__init__(name="MACD_Histogram_Acceleration", params=default_params)

        self.bar_history: Dict[str, List[Dict[str, float]]] = {}
        self.trade_counts: Dict[str, int] = {}

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()
        self.trade_counts.clear()

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
        min_bars = int(self.params["slow_period"]) + int(self.params["signal_period"]) + 5

        for sym, q in quotes.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(q)

            history = self.bar_history[sym]
            if len(history) < min_bars:
                continue

            if self.trade_counts.get(sym, 0) >= int(self.params["max_trades_per_sym"]):
                continue

            if portfolio.get_position(sym):
                continue

            closes = np.array([float(b.get("close", b.get("ltp", 0.0))) for b in history])
            closes_s = pd.Series(closes)

            macd_df = calculate_macd(
                closes_s,
                fast=int(self.params["fast_period"]),
                slow=int(self.params["slow_period"]),
                signal=int(self.params["signal_period"])
            )

            curr_c = closes[-1]
            macd_val = float(macd_df["macd"].iloc[-1])
            sig_val = float(macd_df["signal"].iloc[-1])
            h_now = float(macd_df["histogram"].iloc[-1])
            h_prev = float(macd_df["histogram"].iloc[-2])
            h_prev2 = float(macd_df["histogram"].iloc[-3])

            # 1. Bullish Acceleration: MACD above signal, histogram positive & strictly accelerating
            bull_accel = (macd_val > sig_val) and (h_now > 0) and (h_now > h_prev > h_prev2 or (h_prev <= 0 and h_now > 0))

            if bull_accel:
                sl_val = round(curr_c - float(self.params["sl_pts"]), 2)
                tgt_val = round(curr_c + float(self.params["target_pts"]), 2)
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": curr_c,
                    "sl": sl_val,
                    "target": tgt_val,
                    "score": 84,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {
                        "strategy": self.name,
                        "macd": round(macd_val, 2),
                        "signal": round(sig_val, 2),
                        "histogram": round(h_now, 2),
                        "momentum": "BULLISH_ACCELERATION"
                    }
                })
                self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

            # 2. Bearish Acceleration: MACD below signal, histogram negative & strictly accelerating downward
            bear_accel = (macd_val < sig_val) and (h_now < 0) and (h_now < h_prev < h_prev2 or (h_prev >= 0 and h_now < 0))

            if bear_accel:
                sl_val = round(curr_c + float(self.params["sl_pts"]), 2)
                tgt_val = round(curr_c - float(self.params["target_pts"]), 2)
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.SELL,
                    "price": curr_c,
                    "sl": sl_val,
                    "target": tgt_val,
                    "score": 84,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {
                        "strategy": self.name,
                        "macd": round(macd_val, 2),
                        "signal": round(sig_val, 2),
                        "histogram": round(h_now, 2),
                        "momentum": "BEARISH_ACCELERATION"
                    }
                })
                self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()
        self.trade_counts.clear()
