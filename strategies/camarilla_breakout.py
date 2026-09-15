"""
strategies/camarilla_breakout.py — Camarilla Floor Pivot Breakout Strategy.

Computes Camarilla Pivot levels (H4, H3, L3, L4).
Trades sharp institutional breakouts when price violates H4 (Long) or L4 (Short),
utilizing H3/L3 as structural stop boundaries.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import calculate_camarilla_pivots
from config import TRADING_START, TRADING_END


class CamarillaBreakoutStrategy(BaseStrategy):
    """Camarilla H4/L4 Breakout Strategy."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "formation_minutes": 30,  # Range to compute pivots if previous day unavailable
            "risk_reward": 2.0,
            "sl_buffer_pts": 5.0,
            "max_trades_per_sym": 1
        }
        if params:
            default_params.update(params)
        super().__init__(name="Camarilla_Floor_Pivot_Breakout", params=default_params)

        self.bar_history: Dict[str, List[Dict[str, float]]] = {}
        self.pivots: Dict[str, Dict[str, float]] = {}
        self.trade_counts: Dict[str, int] = {}

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()
        self.pivots.clear()
        self.trade_counts.clear()

        # If previous session high/low/close are available in context, use them
        prev_data = context.get("previous_day_ohlc", {})
        for sym, ohlc in prev_data.items():
            h = ohlc.get("high")
            l = ohlc.get("low")
            c = ohlc.get("close")
            if h and l and c and h > l:
                self.pivots[sym] = calculate_camarilla_pivots(h, l, c)

    def _parse_minute_of_day(self, time_str: str) -> int:
        parts = [int(p) for p in time_str.split(":")[:2]]
        return parts[0] * 60 + parts[1]

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

        mins_now = self._parse_minute_of_day(time_part)
        market_open_mins = self._parse_minute_of_day(TRADING_START)
        cutoff_mins = market_open_mins + int(self.params["formation_minutes"])

        signals = []

        for sym, q in quotes.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(q)

            history = self.bar_history[sym]
            close = float(q.get("close", q.get("ltp", 0.0)))

            # If pivots not yet calculated, calculate from initial formation window
            if sym not in self.pivots:
                if mins_now >= cutoff_mins and len(history) >= 10:
                    highs = [float(b.get("high", b.get("close", 0.0))) for b in history]
                    lows = [float(b.get("low", b.get("close", 0.0))) for b in history]
                    closes = [float(b.get("close", b.get("ltp", 0.0))) for b in history]
                    h_max = max(highs)
                    l_min = min(lows)
                    c_last = closes[-1]
                    if h_max > l_min:
                        self.pivots[sym] = calculate_camarilla_pivots(h_max, l_min, c_last)
                else:
                    continue

            p = self.pivots.get(sym)
            if not p:
                continue

            if self.trade_counts.get(sym, 0) >= int(self.params["max_trades_per_sym"]):
                continue

            if portfolio.get_position(sym):
                continue

            if len(history) < 2:
                continue

            prev_close = float(history[-2].get("close", history[-2].get("ltp", 0.0)))
            r4 = p["R4"]
            r3 = p["R3"]
            s3 = p["S3"]
            s4 = p["S4"]
            buffer = float(self.params["sl_buffer_pts"])

            # 1. Bullish Camarilla Breakout above R4
            if prev_close <= r4 and close > r4:
                sl = round(max(r3, close - (r4 - r3) - buffer), 2)
                risk = close - sl
                if risk > 0:
                    tgt = round(close + (risk * float(self.params["risk_reward"])), 2)
                    signals.append({
                        "symbol": sym,
                        "security_id": q.get("security_id", 0),
                        "side": OrderSide.BUY,
                        "price": close,
                        "sl": sl,
                        "target": tgt,
                        "score": 86,
                        "instrument_type": InstrumentType.EQUITY,
                        "metadata": {
                            "strategy": self.name,
                            "R4": round(r4, 2),
                            "R3": round(r3, 2),
                            "camarilla_type": "H4_BREAKOUT"
                        }
                    })
                    self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

            # 2. Bearish Camarilla Breakdown below S4
            elif prev_close >= s4 and close < s4:
                sl = round(min(s3, close + (s3 - s4) + buffer), 2)
                risk = sl - close
                if risk > 0:
                    tgt = round(close - (risk * float(self.params["risk_reward"])), 2)
                    signals.append({
                        "symbol": sym,
                        "security_id": q.get("security_id", 0),
                        "side": OrderSide.SELL,
                        "price": close,
                        "sl": sl,
                        "target": tgt,
                        "score": 86,
                        "instrument_type": InstrumentType.EQUITY,
                        "metadata": {
                            "strategy": self.name,
                            "S4": round(s4, 2),
                            "S3": round(s3, 2),
                            "camarilla_type": "L4_BREAKDOWN"
                        }
                    })
                    self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()
        self.pivots.clear()
        self.trade_counts.clear()
