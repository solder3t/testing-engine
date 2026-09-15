"""
strategies/vwap_reversion.py — VWAP Mean Reversion Strategy (from BOT 2.0).

Exploits extreme price extensions beyond Bollinger Bands (2.0+ std)
taking high-probability mean reversion trades back toward the intraday VWAP.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import calculate_bollinger_bands, calculate_vwap, calculate_atr
from config import TRADING_START, TRADING_END


class VwapReversionStrategy(BaseStrategy):
    """Mean reversion toward VWAP from extreme Bollinger Band deviations."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "min_rr": 1.5,
            "sl_pts": 15.0,
            "target_pts": 30.0,
            "atr_sl_mult": 1.5,
        }
        if params:
            default_params.update(params)
        super().__init__(name="VWAP_Mean_Reversion", params=default_params)
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
        period = self.params["bb_period"]
        std_mult = self.params["bb_std"]

        for sym, q in quotes.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(q)

            history = self.bar_history[sym]
            if len(history) < period + 2:
                continue

            closes = np.array([bar.get("close", bar.get("ltp", 0.0)) for bar in history], dtype=float)
            highs = np.array([bar.get("high", bar.get("close", 0.0)) for bar in history], dtype=float)
            lows = np.array([bar.get("low", bar.get("close", 0.0)) for bar in history], dtype=float)

            closes_s = pd.Series(closes)
            bb_df = calculate_bollinger_bands(closes_s, period=period, std_dev=std_mult)
            upper = bb_df["upper"].values
            middle = bb_df["middle"].values
            lower = bb_df["lower"].values

            curr_c = closes[-1]
            prev_c = closes[-2]
            curr_lower = lower[-1]
            curr_upper = upper[-1]
            curr_vwap = middle[-1]

            # Long Reversion: Previous bar pierced below lower band, current bar crosses back above
            if prev_c <= lower[-2] and curr_c > curr_lower and curr_c < curr_vwap:
                sl = round(curr_c - self.params["sl_pts"], 2)
                target = round(max(curr_c + self.params["target_pts"], curr_vwap), 2)
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": curr_c,
                    "sl": sl,
                    "target": target,
                    "score": 75,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {"strategy": self.name, "vwap": curr_vwap, "lower_bb": curr_lower}
                })

            # Short Reversion: Previous bar pierced above upper band, current bar crosses back below
            elif prev_c >= upper[-2] and curr_c < curr_upper and curr_c > curr_vwap:
                sl = round(curr_c + self.params["sl_pts"], 2)
                target = round(min(curr_c - self.params["target_pts"], curr_vwap), 2)
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.SELL,
                    "price": curr_c,
                    "sl": sl,
                    "target": target,
                    "score": 75,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {"strategy": self.name, "vwap": curr_vwap, "upper_bb": curr_upper}
                })

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()
