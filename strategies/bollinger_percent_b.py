"""
strategies/bollinger_percent_b.py — Bollinger %B Mean Reversion Strategy.

Capitalizes on statistical exhaustion where price stretches beyond normal distribution bounds
(%B < 0.05 or %B > 0.95) confirmed by RSI oversold/overbought momentum extremes.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import calculate_bollinger_bands, calculate_rsi
from config import TRADING_START, TRADING_END


class BollingerPercentBStrategy(BaseStrategy):
    """Bollinger %B Statistical Mean Reversion Strategy."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "period": 20,
            "std_dev": 2.0,
            "oversold_b": 0.05,
            "overbought_b": 0.95,
            "rsi_period": 14,
            "sl_pts": 15.0,
            "target_pts": 30.0,
            "max_trades_per_sym": 2
        }
        if params:
            default_params.update(params)
        super().__init__(name="Bollinger_PercentB_MeanReversion", params=default_params)

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
        min_bars = max(int(self.params["period"]), int(self.params["rsi_period"])) + 5

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

            bb_df = calculate_bollinger_bands(
                closes_s,
                period=int(self.params["period"]),
                std_dev=float(self.params["std_dev"])
            )
            rsi_series = calculate_rsi(closes_s, period=int(self.params["rsi_period"]))

            curr_c = closes[-1]
            pct_b = float(bb_df["percent_b"].iloc[-1])
            prev_b = float(bb_df["percent_b"].iloc[-2])
            curr_rsi = float(rsi_series.iloc[-1])
            mid_band = float(bb_df["middle"].iloc[-1])

            # 1. Oversold Reversion: %B pierced lower band and begins bouncing back up
            if (prev_b <= float(self.params["oversold_b"]) or pct_b <= float(self.params["oversold_b"])) and curr_rsi <= 38.0:
                sl_val = round(curr_c - float(self.params["sl_pts"]), 2)
                tgt_val = round(max(mid_band, curr_c + float(self.params["target_pts"])), 2)
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": curr_c,
                    "sl": sl_val,
                    "target": tgt_val,
                    "score": 80,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {
                        "strategy": self.name,
                        "percent_b": round(pct_b, 3),
                        "rsi": round(curr_rsi, 1),
                        "setup": "OVERSOLD_REVERSION"
                    }
                })
                self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

            # 2. Overbought Reversion: %B pierced upper band and begins rejecting down
            elif (prev_b >= float(self.params["overbought_b"]) or pct_b >= float(self.params["overbought_b"])) and curr_rsi >= 62.0:
                sl_val = round(curr_c + float(self.params["sl_pts"]), 2)
                tgt_val = round(min(mid_band, curr_c - float(self.params["target_pts"])), 2)
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.SELL,
                    "price": curr_c,
                    "sl": sl_val,
                    "target": tgt_val,
                    "score": 80,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {
                        "strategy": self.name,
                        "percent_b": round(pct_b, 3),
                        "rsi": round(curr_rsi, 1),
                        "setup": "OVERBOUGHT_REVERSION"
                    }
                })
                self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()
        self.trade_counts.clear()
