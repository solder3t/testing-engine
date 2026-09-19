"""
strategies/trading_engine_v4.py — Canonical Multi-Factor Strategy v4 from Trading Engine.

Faithfully implements the 7-condition multi-factor model with dual-timeframe confirmation,
anchored VWAP, CPR pivot levels, ADX regime adaptation, India VIX dynamic gating,
Options PCR sentiment, and the canonical 0–100 composite scorer.
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
    calculate_adx,
    calculate_cpr,
    calculate_camarilla_pivots,
    calculate_volume_ratio
)


def compute_signal_score(sig: dict) -> int:
    """
    Composite 0–100 score measuring signal quality from trading-engine/core/scorer.py.
    """
    action    = sig.get("signal", "HOLD")
    rsi       = sig.get("rsi",           50)
    hist      = sig.get("macd_hist",     0)
    vol_ratio = sig.get("vol_ratio",     1.0)
    entry     = sig.get("entry_price",   0)
    vwap      = sig.get("vwap",          entry)
    st_dir    = sig.get("supertrend_dir", 0)
    st_flip   = sig.get("supertrend_flip", False)
    htf_bull  = sig.get("htf_bullish",   False)
    htf_bear  = sig.get("htf_bearish",   False)
    htf_valid = sig.get("htf_valid",     False)
    rr_ratio  = sig.get("rr_ratio",      0.0)
    anom_z    = sig.get("anomaly_zscore", 0.0)
    adx_val   = sig.get("adx",           0.0)
    adx_plus  = sig.get("adx_plus_di",   0.0)
    adx_minus = sig.get("adx_minus_di",  0.0)
    bias_15m_bull = sig.get("htf_15m_bullish", False)
    bias_15m_bear = sig.get("htf_15m_bearish", False)

    if action not in ("BUY", "SELL"):
        return 0

    score = 0

    # RSI momentum (20 pts)
    if action == "BUY":
        if 55 <= rsi <= 70:    score += 20
        elif 50 <= rsi < 55:   score += 12
        elif rsi > 70:         score +=  8
    elif action == "SELL":
        if 30 <= rsi <= 45:    score += 20
        elif 45 < rsi <= 50:   score += 12
        elif rsi < 30:         score +=  8

    # MACD strength (20 pts)
    abs_hist = abs(hist)
    hist_pts = min(abs_hist / 0.2 * 20, 20)
    if (action == "BUY" and hist > 0) or (action == "SELL" and hist < 0):
        score += int(hist_pts)

    # Volume ratio (20 pts)
    score += int(min(vol_ratio / 3.0 * 20, 20))

    # VWAP proximity (20 pts)
    if entry > 0 and vwap > 0:
        vwap_pct = abs(entry - vwap) / vwap * 100
        if vwap_pct <= 0.1:     score += 20
        elif vwap_pct <= 0.3:   score += 14
        elif vwap_pct <= 0.6:   score +=  8
        elif vwap_pct <= 1.0:   score +=  4
        if action == "BUY"  and entry < vwap:  score = max(score - 8, 0)
        if action == "SELL" and entry > vwap:  score = max(score - 8, 0)

    # Supertrend (10 pts)
    if (action == "BUY" and st_dir == 1) or (action == "SELL" and st_dir == -1):
        score += 7
    if st_flip:
        score += 3

    # HTF alignment (10 pts)
    if htf_valid:
        if (action == "BUY" and htf_bull) or (action == "SELL" and htf_bear):
            score += 10
        else:
            score += 4

    # R:R quality bonus (+10 pts)
    if rr_ratio >= 2.5:
        score += 10
    elif rr_ratio >= 1.5:
        score += int((rr_ratio - 1.5) / 1.0 * 10)

    # ADX trend confirmation (+5 pts)
    if adx_val >= 25:
        if action == "BUY"  and adx_plus  > adx_minus:  score += 5
        if action == "SELL" and adx_minus > adx_plus:   score += 5

    # 15-min bias confirmation (+5 pts)
    if action == "BUY"  and bias_15m_bull:  score += 5
    if action == "SELL" and bias_15m_bear:  score += 5

    # Anomaly penalty (-15 pts)
    if abs(anom_z) >= 2.5:
        score = max(score - 15, 0)

    return min(max(score, 0), 100)


class TradingEngineV4Strategy(BaseStrategy):
    """
    High-fidelity Strategy v4 matching trading-engine/agents/quant_agent.py.
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "ema_fast": 9,
            "ema_slow": 21,
            "rsi_period": 14,
            "rsi_buy_min": 45,
            "rsi_buy_max": 75,
            "rsi_sell_min": 25,
            "rsi_sell_max": 55,
            "supertrend_period": 10,
            "supertrend_multiplier": 3.0,
            "adx_period": 14,
            "adx_trend_threshold": 25,
            "min_signal_score": 50,
            "vix_halt_threshold": 25.0,
            "vix_high_threshold": 20.0,
            "vix_elev_threshold": 15.0,
            "volume_confirm_ratio": 1.2,
            "min_rr_ratio": 1.5,
            "trailing_sl_r": 1.0,
            "use_cpr": True,
            "use_htf_15m": True,
            "use_adx_regime": True,
            "use_vix_filter": True,
            "use_pcr_filter": True,
            "trade_options": True,
        }
        if params:
            default_params.update(params)
        super().__init__(name="TradingEngine_StrategyV4", params=default_params)
        self.pivots: Dict[str, Dict[str, float]] = {}
        self.pcr_sentiment: str = "NEUTRAL"
        self.history_dfs: Dict[str, pd.DataFrame] = {}
        self.option_loader = None
        self.session_date: str = ""

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.session_date = date_str
        self.pivots.clear()
        self.history_dfs.clear()
        self.option_loader = context.get("option_loader")
        ohlc_map = context.get("ohlc_data", {})

        # Compute CPR and Camarilla pivots from session open or historical high/low
        for sym, df in ohlc_map.items():
            if not df.empty and len(df) >= 1:
                h = float(df["high"].max())
                l = float(df["low"].min())
                c = float(df["close"].iloc[0])
                cpr = calculate_cpr(h, l, c)
                cam = calculate_camarilla_pivots(h, l, c)
                self.pivots[sym] = {**cpr, **cam}

        # Check PCR sentiment if option loader available
        opt_loader = context.get("option_loader")
        if opt_loader and self.params["use_pcr_filter"]:
            try:
                chain = opt_loader.get_nearest_chain(date_str, "09:30:00", "NIFTY")
                if chain is not None and not chain.empty:
                    pcr = opt_loader.calculate_pcr(chain)
                    if pcr >= 1.2:
                        self.pcr_sentiment = "BULLISH"
                    elif pcr <= 0.8:
                        self.pcr_sentiment = "BEARISH"
                    else:
                        self.pcr_sentiment = "NEUTRAL"
            except Exception:
                self.pcr_sentiment = "NEUTRAL"

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        # Trading window: 09:30 - 15:00 IST
        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        if time_part < "09:30:00" or time_part > "15:00:00":
            return []

        # India VIX Filter
        current_vix = context.get("current_vix", 15.0)
        if self.params["use_vix_filter"] and current_vix >= self.params["vix_halt_threshold"]:
            return []

        signals = []

        for sym, q in quotes.items():
            if sym in ("INDIA_VIX",) or "OPTION" in sym:
                continue

            # Need OHLC history for indicators
            df_full = context.get("ohlc_data", {}).get(sym)
            if df_full is None or df_full.empty:
                continue

            # Up to current bar
            sub_df = df_full[df_full["timestamp"].astype(str) <= timestamp]
            if len(sub_df) < 28:
                continue

            close_s = sub_df["close"]
            price = float(q["close"])
            if price <= 0:
                continue

            # 1. 1-min indicators
            ema9_s = calculate_ema(close_s, self.params["ema_fast"])
            ema21_s = calculate_ema(close_s, self.params["ema_slow"])
            rsi_s = calculate_rsi(close_s, self.params["rsi_period"])
            atr_s = calculate_atr(sub_df, 14)
            macd_df = calculate_macd(close_s)
            vwap_s = calculate_vwap(sub_df)
            st_df = calculate_supertrend(
                sub_df,
                period=self.params["supertrend_period"],
                multiplier=self.params["supertrend_multiplier"]
            )
            adx_df = calculate_adx(sub_df, period=self.params["adx_period"])

            latest_ema9 = float(ema9_s.iloc[-1])
            latest_ema21 = float(ema21_s.iloc[-1])
            latest_rsi = float(rsi_s.iloc[-1])
            latest_atr = float(atr_s.iloc[-1]) if not atr_s.empty else (price * 0.01)
            latest_macd_hist = float(macd_df["histogram"].iloc[-1])
            latest_vwap = float(vwap_s.iloc[-1])
            st_dir = int(st_df["direction"].iloc[-1])
            st_flip = bool(st_df["just_flipped"].iloc[-1])
            latest_adx = float(adx_df["adx"].iloc[-1])
            adx_plus = float(adx_df["plus_di"].iloc[-1])
            adx_minus = float(adx_df["minus_di"].iloc[-1])

            # 2. Volume confirmation
            vol_ratio = calculate_volume_ratio(sub_df, period=20)
            volume_ok = vol_ratio >= self.params["volume_confirm_ratio"]

            # 3. CPR levels
            pivots = self.pivots.get(sym, {})
            tc = pivots.get("TC", 0.0)
            bc = pivots.get("BC", 0.0)

            # 4. 15m HTF bias approximation (using last 15 bars)
            bias_15m_bull = False
            bias_15m_bear = False
            if self.params["use_htf_15m"] and len(close_s) >= 15:
                # 15m trend from last 15-bar slope
                bias_15m_bull = close_s.iloc[-1] > close_s.iloc[-15]
                bias_15m_bear = close_s.iloc[-1] < close_s.iloc[-15]

            # 5. VIX-adjusted stop multiplier
            if current_vix >= self.params["vix_high_threshold"]:
                sl_mult = 2.0
            elif current_vix >= self.params["vix_elev_threshold"]:
                sl_mult = 1.8
            else:
                sl_mult = 1.5

            # 6. ADX Regime R:R target
            is_trending = latest_adx >= self.params["adx_trend_threshold"] if self.params["use_adx_regime"] else True
            rr_target_ratio = 2.0 if is_trending else self.params["min_rr_ratio"]

            # ── Condition Checks ──────────────────────────────────────────

            # BUY Conditions:
            # - EMA9 > EMA21
            # - Price > VWAP
            # - Price > CPR TC (if enabled)
            # - MACD hist > 0
            # - RSI 45..75 or < 32 (oversold bounce)
            # - Supertrend bullish (st_dir == 1)
            # - PCR sentiment != BEARISH
            cpr_buy_ok = (not self.params["use_cpr"]) or (tc > 0 and price > tc)
            pcr_buy_ok = (not self.params["use_pcr_filter"]) or (self.pcr_sentiment != "BEARISH")
            htf_buy_ok = (not self.params["use_htf_15m"]) or bias_15m_bull

            is_buy = (
                latest_ema9 > latest_ema21
                and price > latest_vwap
                and cpr_buy_ok
                and latest_macd_hist > 0
                and ((self.params["rsi_buy_min"] <= latest_rsi <= self.params["rsi_buy_max"]) or latest_rsi < 32)
                and st_dir == 1
                and pcr_buy_ok
                and htf_buy_ok
                and volume_ok
            )

            # SELL Conditions:
            cpr_sell_ok = (not self.params["use_cpr"]) or (bc > 0 and price < bc)
            pcr_sell_ok = (not self.params["use_pcr_filter"]) or (self.pcr_sentiment != "BULLISH")
            htf_sell_ok = (not self.params["use_htf_15m"]) or bias_15m_bear

            is_sell = (
                latest_ema9 < latest_ema21
                and price < latest_vwap
                and cpr_sell_ok
                and latest_macd_hist < 0
                and ((self.params["rsi_sell_min"] <= latest_rsi <= self.params["rsi_sell_max"]) or latest_rsi > 68)
                and st_dir == -1
                and pcr_sell_ok
                and htf_sell_ok
                and volume_ok
            )

            if not is_buy and not is_sell:
                continue

            side = OrderSide.BUY if is_buy else OrderSide.SELL
            sl_dist = latest_atr * sl_mult
            sl = round(price - sl_dist, 2) if is_buy else round(price + sl_dist, 2)
            target = round(price + (sl_dist * rr_target_ratio), 2) if is_buy else round(price - (sl_dist * rr_target_ratio), 2)

            sig_dict = {
                "signal": side.value,
                "rsi": latest_rsi,
                "macd_hist": latest_macd_hist,
                "vol_ratio": vol_ratio,
                "entry_price": price,
                "vwap": latest_vwap,
                "supertrend_dir": st_dir,
                "supertrend_flip": st_flip,
                "htf_valid": True,
                "htf_bullish": bias_15m_bull,
                "htf_bearish": bias_15m_bear,
                "rr_ratio": rr_target_ratio,
                "adx": latest_adx,
                "adx_plus_di": adx_plus,
                "adx_minus_di": adx_minus,
                "htf_15m_bullish": bias_15m_bull,
                "htf_15m_bearish": bias_15m_bear,
                "anomaly_zscore": 0.0
            }

            score = compute_signal_score(sig_dict)
            if score < self.params["min_signal_score"]:
                continue

            # If evaluating NIFTY index and options trading is enabled, route to ATM option contracts
            if sym in ("NIFTY", "NIFTY 50", "NIFTY_50") and self.params.get("trade_options", True) and self.option_loader:
                opt_type = "CE" if is_buy else "PE"
                contract = self.option_loader.get_atm_contract(
                    date_str=self.session_date,
                    timestamp=timestamp,
                    option_type=opt_type,
                    underlying="NIFTY",
                    step=50.0,
                )
                if contract and float(contract.get("ltp", 0.0)) > 0:
                    opt_ltp = float(contract["ltp"])
                    opt_strike = float(contract["strike_price"])
                    opt_sym = f"NIFTY50-SEP2026-{int(opt_strike)}-{opt_type}"
                    # Risk parameters on options contract
                    opt_sl = round(max(5.0, opt_ltp * 0.8), 2)
                    opt_tgt = round(opt_ltp * 1.3, 2)
                    signals.append({
                        "symbol": opt_sym,
                        "side": OrderSide.BUY,
                        "price": opt_ltp,
                        "sl": opt_sl,
                        "target": opt_tgt,
                        "score": score,
                        "security_id": int(contract.get("security_id", 0)),
                        "instrument_type": InstrumentType.OPTION_CE if opt_type == "CE" else InstrumentType.OPTION_PE,
                        "lot_size": 65,
                        "metadata": {
                            "strategy": "TradingEngine_StrategyV4",
                            "score": score,
                            "underlying": "NIFTY",
                            "underlying_ltp": price,
                            "strike": opt_strike,
                            "option_type": opt_type,
                            "delta": contract.get("delta", 0.5 if opt_type == "CE" else -0.5),
                            "vix": current_vix,
                            "adx": latest_adx,
                        }
                    })
                    continue

            signals.append({
                "symbol": sym,
                "side": side,
                "price": price,
                "sl": sl,
                "target": target,
                "score": score,
                "security_id": q.get("security_id", 0),
                "instrument_type": InstrumentType.EQUITY,
                "lot_size": 1,
                "metadata": {
                    "strategy": "TradingEngine_StrategyV4",
                    "score": score,
                    "vix": current_vix,
                    "adx": latest_adx,
                    "vol_ratio": round(vol_ratio, 2),
                    "sector": q.get("sector", "Other")
                }
            })

        # Apply Break-even Trailing SL to open positions
        if self.params["trailing_sl_r"] > 0:
            for trade in portfolio.open_trades:
                current_q = quotes.get(trade.symbol)
                if not current_q:
                    continue
                curr_price = float(current_q["close"])
                initial_risk = abs(trade.entry_price - trade.initial_sl)
                if initial_risk > 0:
                    if trade.side == OrderSide.BUY:
                        profit = curr_price - trade.entry_price
                        if profit >= initial_risk * self.params["trailing_sl_r"]:
                            # Move SL to entry price (break-even)
                            if trade.current_sl < trade.entry_price:
                                trade.current_sl = trade.entry_price
                    elif trade.side == OrderSide.SELL:
                        profit = trade.entry_price - curr_price
                        if profit >= initial_risk * self.params["trailing_sl_r"]:
                            if trade.current_sl > trade.entry_price:
                                trade.current_sl = trade.entry_price

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        pass
