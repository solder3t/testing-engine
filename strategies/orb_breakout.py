"""
strategies/orb_breakout.py — Opening Range Breakout (ORB) Strategy.

Identifies the High and Low established during the opening window (default: first 15 minutes,
e.g. 09:15 - 09:30) and trades subsequent directional momentum breakouts confirmed by ATR volatility.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import calculate_atr
from config import TRADING_START, TRADING_END


class OrbBreakoutStrategy(BaseStrategy):
    """15-Minute Opening Range Breakout (ORB) Strategy with ATR trailing bounds."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "opening_minutes": 15,     # 09:15 to 09:30
            "breakout_buffer": 0.0,    # Buffer above/below ORB level
            "risk_reward": 2.0,        # 1:2 R:R
            "max_trades_per_sym": 1,   # Max 1 breakout trade per symbol per session
        }
        if params:
            default_params.update(params)
        super().__init__(name="Opening_Range_Breakout_15M", params=default_params)

        self.orb_levels: Dict[str, Dict[str, float]] = {}
        self.bar_history: Dict[str, List[Dict[str, float]]] = {}
        self.trade_counts: Dict[str, int] = {}
        self.range_finalized = False

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.orb_levels.clear()
        self.bar_history.clear()
        self.trade_counts.clear()
        self.range_finalized = False

    def _parse_minute_of_day(self, time_str: str) -> int:
        """Converts 'HH:MM:SS' into minutes since midnight."""
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
        market_open = "09:15"
        if not (market_open <= time_part <= TRADING_END):
            return []

        mins_now = self._parse_minute_of_day(time_part)
        market_open_mins = self._parse_minute_of_day(market_open)
        orb_cutoff_mins = market_open_mins + int(self.params["opening_minutes"])

        signals = []

        for sym, q in quotes.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(q)

            high = float(q.get("high", q.get("close", 0.0)))
            low = float(q.get("low", q.get("close", 0.0)))
            close = float(q.get("close", q.get("ltp", 0.0)))

            # 1. Establish Opening Range
            if sym not in self.orb_levels:
                self.orb_levels[sym] = {"high": high, "low": low}
            else:
                if mins_now < orb_cutoff_mins:
                    self.orb_levels[sym]["high"] = max(self.orb_levels[sym]["high"], high)
                    self.orb_levels[sym]["low"] = min(self.orb_levels[sym]["low"], low)

            # Still in range formation window
            if mins_now < orb_cutoff_mins:
                continue

            # Don't exceed max trades per symbol
            if self.trade_counts.get(sym, 0) >= self.params["max_trades_per_sym"]:
                continue

            # Check if symbol already has active position
            if portfolio.get_position(sym):
                continue

            history = self.bar_history[sym]
            if len(history) < 5:
                continue

            # Compute ATR for sizing stop loss buffer
            df = pd.DataFrame(history)
            atr_series = calculate_atr(df, period=min(14, len(history)))
            atr_val = float(atr_series.iloc[-1]) if not atr_series.empty and not np.isnan(atr_series.iloc[-1]) else 5.0
            buffer = float(self.params.get("breakout_buffer", 0.0))

            orb_high = self.orb_levels[sym]["high"]
            orb_low = self.orb_levels[sym]["low"]
            orb_range = orb_high - orb_low

            if orb_range <= 0:
                continue

            # Bullish Breakout: Close > ORB High + buffer
            if close > (orb_high + buffer):
                sl = round(max(orb_low, close - atr_val * 1.5), 2)
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
                        "score": 85,
                        "instrument_type": InstrumentType.EQUITY,
                        "metadata": {
                            "strategy": self.name,
                            "orb_high": orb_high,
                            "orb_low": orb_low,
                            "atr": round(atr_val, 2)
                        }
                    })
                    self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

            # Bearish Breakdown: Close < ORB Low - buffer
            elif close < (orb_low - buffer):
                sl = round(min(orb_high, close + atr_val * 1.5), 2)
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
                        "score": 85,
                        "instrument_type": InstrumentType.EQUITY,
                        "metadata": {
                            "strategy": self.name,
                            "orb_high": orb_high,
                            "orb_low": orb_low,
                            "atr": round(atr_val, 2)
                        }
                    })
                    self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.orb_levels.clear()
        self.bar_history.clear()
        self.trade_counts.clear()
