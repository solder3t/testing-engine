"""
strategies/supertrend_trend.py — Supertrend with Trend Filter Strategy.

Uses ATR-based Supertrend trailing stop to detect directional trend regime flips,
filtered by 50-period Exponential Moving Average (EMA) to avoid counter-trend noise.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import calculate_supertrend, calculate_ema
from config import TRADING_START, TRADING_END


class SupertrendTrendStrategy(BaseStrategy):
    """Supertrend Trend Following with 50-EMA Macro Trend Filter."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "atr_period": 10,
            "multiplier": 3.0,
            "ema_filter": 50,
            "risk_reward": 2.0,
            "max_trades_per_sym": 2,
        }
        if params:
            default_params.update(params)
        super().__init__(name="Supertrend_Trend_Follower", params=default_params)

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
        min_bars = max(int(self.params["atr_period"]), int(self.params["ema_filter"])) + 5

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

            df = pd.DataFrame(history)
            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif "ltp" in df.columns:
                    df[col] = pd.to_numeric(df["ltp"], errors="coerce")

            st_df = calculate_supertrend(
                df,
                period=int(self.params["atr_period"]),
                multiplier=float(self.params["multiplier"])
            )
            ema_series = calculate_ema(df["close"], period=int(self.params["ema_filter"]))

            curr_close = float(df["close"].iloc[-1])
            curr_st = float(st_df["supertrend"].iloc[-1])
            curr_dir = int(st_df["direction"].iloc[-1])
            prev_dir = int(st_df["direction"].iloc[-2])
            curr_ema = float(ema_series.iloc[-1])

            # Trend flip detected
            flipped_bullish = (prev_dir == -1 and curr_dir == 1)
            flipped_bearish = (prev_dir == 1 and curr_dir == -1)

            # 1. Bullish Flip above EMA filter
            if flipped_bullish and curr_close > curr_ema:
                sl = round(min(curr_st, curr_close * 0.995), 2)
                risk = curr_close - sl
                if risk > 0:
                    tgt = round(curr_close + (risk * float(self.params["risk_reward"])), 2)
                    signals.append({
                        "symbol": sym,
                        "security_id": q.get("security_id", 0),
                        "side": OrderSide.BUY,
                        "price": curr_close,
                        "sl": sl,
                        "target": tgt,
                        "score": 88,
                        "instrument_type": InstrumentType.EQUITY,
                        "metadata": {
                            "strategy": self.name,
                            "supertrend": curr_st,
                            "ema_filter": round(curr_ema, 2),
                            "direction": "BULLISH"
                        }
                    })
                    self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

            # 2. Bearish Flip below EMA filter
            elif flipped_bearish and curr_close < curr_ema:
                sl = round(max(curr_st, curr_close * 1.005), 2)
                risk = sl - curr_close
                if risk > 0:
                    tgt = round(curr_close - (risk * float(self.params["risk_reward"])), 2)
                    signals.append({
                        "symbol": sym,
                        "security_id": q.get("security_id", 0),
                        "side": OrderSide.SELL,
                        "price": curr_close,
                        "sl": sl,
                        "target": tgt,
                        "score": 88,
                        "instrument_type": InstrumentType.EQUITY,
                        "metadata": {
                            "strategy": self.name,
                            "supertrend": curr_st,
                            "ema_filter": round(curr_ema, 2),
                            "direction": "BEARISH"
                        }
                    })
                    self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()
        self.trade_counts.clear()
