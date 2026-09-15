"""
strategies/equity_momentum.py — Strategy v4/v5 Equity Momentum.

Multi-factor technical momentum strategy across 1-minute bars:
- EMA 9/21 trend filter
- Supertrend directional confirmation
- RSI momentum healthy zones
- MACD histogram alignment
- VWAP proximity
- Camarilla R4/S4 profit targets
- ATR-based stop losses with 1.5x minimum Risk:Reward
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from indicators.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    calculate_macd,
    calculate_vwap,
    calculate_supertrend,
    calculate_camarilla_pivots,
    calculate_bollinger_bands
)
from indicators.scorer import compute_signal_score
from config import TRADING_START, TRADING_END, EXPIRY_CUTOFF_TIME, MIN_RR_RATIO


class EquityMomentumStrategy(BaseStrategy):
    """Implementation of Equity Momentum Strategy v4/v5."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "min_score": 55,
            "min_rr": MIN_RR_RATIO,
            "atr_sl_mult": 1.5,
            "atr_tgt_mult": 3.0,
            "vix_threshold": 25.0
        }
        if params:
            default_params.update(params)
        super().__init__(name="EquityMomentum_v5", params=default_params)

        self.indicators_cache: Dict[str, Dict] = {}

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        """Precomputes technical indicator series for each instrument's day data."""
        self.indicators_cache.clear()
        ohlc_data = context.get("ohlc_data", {})

        for symbol, df in ohlc_data.items():
            if df.empty or len(df) < 25:
                continue

            close = df["close"].astype(float)
            high = df["high"].astype(float)
            low = df["low"].astype(float)

            ema9 = calculate_ema(close, 9)
            ema21 = calculate_ema(close, 21)
            rsi = calculate_rsi(close, 14)
            atr = calculate_atr(df, 14)
            macd_dict = calculate_macd(close)
            vwap = calculate_vwap(df)
            st_dict = calculate_supertrend(df, period=10, multiplier=3.0)
            bb_dict = calculate_bollinger_bands(close)

            # Camarilla pivots from rolling previous bar
            cam_r4 = []
            cam_s4 = []
            for i in range(len(df)):
                if i == 0:
                    cam_r4.append(close.iloc[i] * 1.01)
                    cam_s4.append(close.iloc[i] * 0.99)
                else:
                    cp = calculate_camarilla_pivots(high.iloc[i - 1], low.iloc[i - 1], close.iloc[i - 1])
                    cam_r4.append(cp["R4"])
                    cam_s4.append(cp["S4"])

            # Map by timestamp string for instantaneous O(1) lookup during bar loop
            ts_keys = df["timestamp"].astype(str).values
            indicator_map = {}
            for i, ts in enumerate(ts_keys):
                vol_period = min(20, i)
                vol_avg = float(df["volume"].iloc[max(0, i - vol_period):i].mean()) if i > 0 else 1.0
                curr_vol = float(df["volume"].iloc[i])
                vol_ratio = (curr_vol / vol_avg) if vol_avg > 0 else 1.0

                indicator_map[ts] = {
                    "close": float(close.iloc[i]),
                    "high": float(high.iloc[i]),
                    "low": float(low.iloc[i]),
                    "ema9": float(ema9.iloc[i]),
                    "ema21": float(ema21.iloc[i]),
                    "rsi": float(rsi.iloc[i]),
                    "atr": float(atr.iloc[i]),
                    "macd_hist": float(macd_dict["histogram"].iloc[i]),
                    "macd_val": float(macd_dict["macd"].iloc[i]),
                    "vwap": float(vwap.iloc[i]),
                    "st_dir": int(st_dict["direction"].iloc[i]),
                    "cam_r4": float(cam_r4[i]),
                    "cam_s4": float(cam_s4[i]),
                    "vol_ratio": vol_ratio,
                    "bb_squeeze": bool(bb_dict["squeeze"].iloc[i]) if "squeeze" in bb_dict else False,
                }

            self.indicators_cache[symbol] = indicator_map

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Scans instruments at the current bar and emits high-conviction signals."""
        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        if time_part < TRADING_START or time_part >= TRADING_END:
            return []

        # Check VIX halt
        vix_val = context.get("current_vix", 15.0)
        if vix_val >= self.params["vix_threshold"]:
            return []

        signals = []

        for symbol, quote in quotes.items():
            ind_map = self.indicators_cache.get(symbol)
            if not ind_map or timestamp not in ind_map:
                continue

            ind = ind_map[timestamp]
            curr_close = ind["close"]
            curr_atr = ind["atr"]
            if curr_atr <= 0:
                continue

            # Core conditions
            ema_bull = ind["ema9"] > ind["ema21"]
            ema_bear = ind["ema9"] < ind["ema21"]
            rsi_bull = 52 <= ind["rsi"] <= 75
            rsi_bear = 25 <= ind["rsi"] <= 48
            above_vwap = curr_close > ind["vwap"]
            below_vwap = curr_close < ind["vwap"]
            st_bull = ind["st_dir"] == 1
            st_bear = ind["st_dir"] == -1
            macd_bull = ind["macd_hist"] > 0
            macd_bear = ind["macd_hist"] < 0
            vol_ok = ind["vol_ratio"] >= 1.0

            # ── BUY Evaluation ────────────────────────────────────────────────
            if ema_bull and above_vwap and rsi_bull and st_bull and macd_bull and vol_ok:
                sl = curr_close - self.params["atr_sl_mult"] * curr_atr
                cam_tgt = ind["cam_r4"]
                tgt = cam_tgt if cam_tgt > curr_close else (curr_close + self.params["atr_tgt_mult"] * curr_atr)
                rr = (tgt - curr_close) / (curr_close - sl) if curr_close > sl else 0.0

                if rr >= self.params["min_rr"]:
                    sig_payload = {
                        "signal": "BUY",
                        "rsi": ind["rsi"],
                        "macd_hist": ind["macd_hist"],
                        "vol_ratio": ind["vol_ratio"],
                        "entry_price": curr_close,
                        "vwap": ind["vwap"],
                        "supertrend_dir": 1,
                        "supertrend_flip": False,
                        "rr_ratio": rr,
                    }
                    score = compute_signal_score(sig_payload)
                    if score >= self.params["min_score"]:
                        signals.append({
                            "symbol": symbol,
                            "security_id": quote.get("security_id", 0),
                            "side": OrderSide.BUY,
                            "price": curr_close,
                            "sl": sl,
                            "target": tgt,
                            "score": score,
                            "instrument_type": InstrumentType.EQUITY,
                            "metadata": {
                                "sector": quote.get("sector", "Other"),
                                "score": score,
                                "rr": round(rr, 2),
                                "strategy": self.name
                            }
                        })

            # ── SELL Evaluation ───────────────────────────────────────────────
            elif ema_bear and below_vwap and rsi_bear and st_bear and macd_bear and vol_ok:
                sl = curr_close + self.params["atr_sl_mult"] * curr_atr
                cam_tgt = ind["cam_s4"]
                tgt = cam_tgt if cam_tgt < curr_close else (curr_close - self.params["atr_tgt_mult"] * curr_atr)
                rr = (curr_close - tgt) / (sl - curr_close) if sl > curr_close else 0.0

                if rr >= self.params["min_rr"]:
                    sig_payload = {
                        "signal": "SELL",
                        "rsi": ind["rsi"],
                        "macd_hist": ind["macd_hist"],
                        "vol_ratio": ind["vol_ratio"],
                        "entry_price": curr_close,
                        "vwap": ind["vwap"],
                        "supertrend_dir": -1,
                        "supertrend_flip": False,
                        "rr_ratio": rr,
                    }
                    score = compute_signal_score(sig_payload)
                    if score >= self.params["min_score"]:
                        signals.append({
                            "symbol": symbol,
                            "security_id": quote.get("security_id", 0),
                            "side": OrderSide.SELL,
                            "price": curr_close,
                            "sl": sl,
                            "target": tgt,
                            "score": score,
                            "instrument_type": InstrumentType.EQUITY,
                            "metadata": {
                                "sector": quote.get("sector", "Other"),
                                "score": score,
                                "rr": round(rr, 2),
                                "strategy": self.name
                            }
                        })

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.indicators_cache.clear()
