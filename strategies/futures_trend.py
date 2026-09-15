"""
strategies/futures_trend.py — Nifty Index Futures Directional Trend Following Strategy.

Trades NIFTY index futures with institutional trend following rules:
1. Filters market regime using VWAP and the triple EMA Ribbon (EMA 9, 21, 50).
2. Generates directional signals:
   - Long (BUY): Price > VWAP and EMA 9 > EMA 21 > EMA 50 with bullish confirmation.
   - Short (SELL): Price < VWAP and EMA 9 < EMA 21 < EMA 50 with bearish confirmation.
3. Sized for standard Nifty Futures (lot size 25) with ATR-based volatility stops.
4. Square off at EOD or upon target / stop-loss hit.
"""

from typing import Dict, List, Any, Optional
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import calculate_ema, calculate_atr, calculate_vwap
from config import TRADING_START


class FuturesTrendStrategy(BaseStrategy):
    """Nifty Index Futures Directional Trend Following Strategy."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "fast_ema": 9,
            "mid_ema": 21,
            "slow_ema": 50,
            "atr_period": 14,
            "atr_multiplier": 1.5,
            "risk_reward": 2.0,
            "lot_size": 25,
            "underlying": "NIFTY"
        }
        if params and isinstance(params, dict):
            default_params.update(params)

        super().__init__(name="FuturesTrendFollower", params=default_params)
        self.daily_bars: List[Dict[str, Any]] = []

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.daily_bars.clear()

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        if time_part < TRADING_START or time_part >= "15:00":
            return []

        underlying = self.params.get("underlying", "NIFTY")
        spot_quote = quotes.get(underlying) or quotes.get(f"{underlying} 50")
        if not spot_quote:
            return []

        price = float(spot_quote.get("close", spot_quote.get("ltp", 0.0)))
        if price <= 0:
            return []

        self.daily_bars.append(spot_quote)

        # Do not stack multiple futures positions
        sym = f"{underlying}_FUT"
        for t in portfolio.open_trades:
            if t.symbol == sym:
                return []

        slow_period = int(self.params.get("slow_ema", 50))
        if len(self.daily_bars) < slow_period:
            return []

        df = pd.DataFrame(self.daily_bars)
        closes = df["close"].astype(float)
        highs = df["high"].astype(float)
        lows = df["low"].astype(float)
        volumes = df["volume"].astype(float) if "volume" in df.columns else pd.Series(1.0, index=df.index)

        fast_period = int(self.params.get("fast_ema", 9))
        mid_period = int(self.params.get("mid_ema", 21))
        atr_period = int(self.params.get("atr_period", 14))

        ema_fast = calculate_ema(closes, fast_period).iloc[-1]
        ema_mid = calculate_ema(closes, mid_period).iloc[-1]
        ema_slow = calculate_ema(closes, slow_period).iloc[-1]
        atr_series = calculate_atr(df, atr_period)
        atr_val = atr_series.iloc[-1] if not atr_series.empty and pd.notna(atr_series.iloc[-1]) else 15.0

        vwap_series = calculate_vwap(df) if "volume" in df.columns and (df["volume"] > 0).any() else closes
        current_vwap = vwap_series.iloc[-1] if not vwap_series.empty and pd.notna(vwap_series.iloc[-1]) else price

        atr_mult = float(self.params.get("atr_multiplier", 1.5))
        rr = float(self.params.get("risk_reward", 2.0))
        lot_size = int(self.params.get("lot_size", 25))

        sl_distance = max(10.0, atr_val * atr_mult)

        signals = []

        # ── Bullish Trend Setup ──────────────────────────────────────────────
        bullish = (price > current_vwap) and (ema_fast > ema_mid > ema_slow) and (closes.iloc[-1] >= closes.iloc[-2])
        if bullish:
            sl = round(price - sl_distance, 2)
            tgt = round(price + (sl_distance * rr), 2)
            signals.append({
                "symbol": sym,
                "security_id": int(spot_quote.get("security_id", 0)),
                "side": OrderSide.BUY,
                "price": price,
                "sl": sl,
                "target": tgt,
                "score": 85,
                "instrument_type": InstrumentType.FUTURES,
                "lot_size": lot_size,
                "metadata": {
                    "underlying": underlying,
                    "vwap": round(current_vwap, 2),
                    "atr": round(atr_val, 2),
                    "strategy": self.name
                }
            })

        # ── Bearish Trend Setup ──────────────────────────────────────────────
        elif (price < current_vwap) and (ema_fast < ema_mid < ema_slow) and (closes.iloc[-1] <= closes.iloc[-2]):
            sl = round(price + sl_distance, 2)
            tgt = round(price - (sl_distance * rr), 2)
            signals.append({
                "symbol": sym,
                "security_id": int(spot_quote.get("security_id", 0)),
                "side": OrderSide.SELL,
                "price": price,
                "sl": sl,
                "target": tgt,
                "score": 85,
                "instrument_type": InstrumentType.FUTURES,
                "lot_size": lot_size,
                "metadata": {
                    "underlying": underlying,
                    "vwap": round(current_vwap, 2),
                    "atr": round(atr_val, 2),
                    "strategy": self.name
                }
            })

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.daily_bars.clear()
