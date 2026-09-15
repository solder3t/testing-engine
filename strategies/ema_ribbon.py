"""
strategies/ema_ribbon.py — Triple EMA Ribbon Alignment Strategy.

Tracks Fast (9), Medium (21), and Slow (50) Exponential Moving Averages.
Executes high-probability continuation trades when the ribbon expands in full alignment
and price completes a healthy shallow pullback.
"""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import calculate_ema
from config import TRADING_START, TRADING_END


class EmaRibbonStrategy(BaseStrategy):
    """Triple EMA Ribbon (9 / 21 / 50) Alignment and Pullback Strategy."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "fast_ema": 9,
            "med_ema": 21,
            "slow_ema": 50,
            "sl_pts": 15.0,
            "target_pts": 30.0,
            "max_trades_per_sym": 2
        }
        if params:
            default_params.update(params)
        super().__init__(name="Triple_EMA_Ribbon_Alignment", params=default_params)

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
        min_bars = int(self.params["slow_ema"]) + 5

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

            fast_s = calculate_ema(closes_s, int(self.params["fast_ema"]))
            med_s = calculate_ema(closes_s, int(self.params["med_ema"]))
            slow_s = calculate_ema(closes_s, int(self.params["slow_ema"]))

            curr_c = closes[-1]
            prev_c = closes[-2]
            f_now, f_prev = float(fast_s.iloc[-1]), float(fast_s.iloc[-2])
            m_now, m_prev = float(med_s.iloc[-1]), float(med_s.iloc[-2])
            s_now, s_prev = float(slow_s.iloc[-1]), float(slow_s.iloc[-2])

            open_price = float(q.get("open", curr_c))

            # 1. Bullish Ribbon: Fast > Med > Slow
            is_bull_ribbon = (f_now > m_now > s_now) and (f_prev > m_prev > s_prev)
            # Pullback trigger: previous bar touched or neared med EMA, current bar rebounds up
            bull_rebound = (prev_c <= f_prev * 1.002) and (curr_c > f_now) and (curr_c > open_price)

            if is_bull_ribbon and bull_rebound:
                sl_val = round(min(s_now, curr_c - float(self.params["sl_pts"])), 2)
                tgt_val = round(curr_c + float(self.params["target_pts"]), 2)
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": curr_c,
                    "sl": sl_val,
                    "target": tgt_val,
                    "score": 82,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {
                        "strategy": self.name,
                        "fast_ema": round(f_now, 2),
                        "med_ema": round(m_now, 2),
                        "slow_ema": round(s_now, 2),
                        "ribbon": "BULLISH"
                    }
                })
                self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

            # 2. Bearish Ribbon: Fast < Med < Slow
            is_bear_ribbon = (f_now < m_now < s_now) and (f_prev < m_prev < s_prev)
            bear_reject = (prev_c >= f_prev * 0.998) and (curr_c < f_now) and (curr_c < open_price)

            if is_bear_ribbon and bear_reject:
                sl_val = round(max(s_now, curr_c + float(self.params["sl_pts"])), 2)
                tgt_val = round(curr_c - float(self.params["target_pts"]), 2)
                signals.append({
                    "symbol": sym,
                    "security_id": q.get("security_id", 0),
                    "side": OrderSide.SELL,
                    "price": curr_c,
                    "sl": sl_val,
                    "target": tgt_val,
                    "score": 82,
                    "instrument_type": InstrumentType.EQUITY,
                    "metadata": {
                        "strategy": self.name,
                        "fast_ema": round(f_now, 2),
                        "med_ema": round(m_now, 2),
                        "slow_ema": round(s_now, 2),
                        "ribbon": "BEARISH"
                    }
                })
                self.trade_counts[sym] = self.trade_counts.get(sym, 0) + 1

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.bar_history.clear()
        self.trade_counts.clear()
