"""
strategies/nifty_options.py — NIFTY Index Options Breakout & Momentum Strategy.

Replays intraday Nifty option buying (ATM CE / PE) using Opening Range Breakout (ORB)
and moving-average momentum confirmation with dynamic option chain lookups.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from data.option_chain_loader import OptionChainLoader
from indicators.indicators import calculate_ema, calculate_rsi
from config import TRADING_START, TRADING_END


class NiftyOptionsStrategy(BaseStrategy):
    """NIFTY Index Options Strategy with dynamic ATM option chain execution."""

    def __init__(self, params: Optional[Dict[str, Any]] = None, option_loader: Optional[Any] = None):
        # Support either order of parameters or dictionary as first argument
        if isinstance(params, OptionChainLoader):
            actual_loader = params
            actual_params = option_loader
        elif isinstance(option_loader, dict) and params is None:
            actual_params = option_loader
            actual_loader = None
        else:
            actual_params = params
            actual_loader = option_loader

        default_params = {
            "orb_window_minutes": 15,    # 09:15 to 09:30 define ORB range
            "min_rr": 1.5,
            "sl_points": 12.0,           # Points on option premium
            "target_multiplier": 1.8,
            "lot_size": 25,              # Standard NIFTY lot size
            "max_lots": 4
        }
        if actual_params and isinstance(actual_params, dict):
            default_params.update(actual_params)
        super().__init__(name="NiftyOptionsBreakout", params=default_params)

        self.option_loader = actual_loader if isinstance(actual_loader, OptionChainLoader) else OptionChainLoader()
        self.orb_high = None
        self.orb_low = None
        self.orb_established = False
        self.daily_bars = []
        self.last_trade_time = ""

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        if context and "option_loader" in context and isinstance(context["option_loader"], OptionChainLoader):
            self.option_loader = context["option_loader"]
        self.orb_high = None
        self.orb_low = None
        self.orb_established = False
        self.daily_bars = []
        self.last_trade_time = ""

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        nifty_quote = quotes.get("NIFTY") or quotes.get("NIFTY 50")
        if not nifty_quote:
            return []

        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        nifty_ltp = float(nifty_quote.get("close", nifty_quote.get("ltp", 0.0)))
        nifty_high = float(nifty_quote.get("high", nifty_ltp))
        nifty_low = float(nifty_quote.get("low", nifty_ltp))

        self.daily_bars.append(nifty_quote)

        # ── Establish ORB between 09:15 and 09:30 ─────────────────────────────
        if time_part < "09:15":
            return []

        if "09:15" <= time_part < "09:30":
            if self.orb_high is None or nifty_high > self.orb_high:
                self.orb_high = nifty_high
            if self.orb_low is None or nifty_low < self.orb_low:
                self.orb_low = nifty_low
            return []

        self.orb_established = True

        # Only trade between 09:30 and 14:45
        if time_part < TRADING_START or time_part >= "14:45":
            return []

        # Cooldown: avoid multiple trades in same 10-minute window
        if self.last_trade_time and timestamp <= self.last_trade_time:
            return []

        # We need at least 15 bars of history for EMA and RSI
        if len(self.daily_bars) < 15:
            return []

        closes = pd.Series([float(b.get("close", b.get("ltp", 0.0))) for b in self.daily_bars])
        ema9 = calculate_ema(closes, 9).iloc[-1]
        ema21 = calculate_ema(closes, 21).iloc[-1]
        rsi = calculate_rsi(closes, 14).iloc[-1]

        signals = []
        date_str = timestamp.split(" ")[0]

        # ── Bullish Breakout -> BUY ATM CE ───────────────────────────────────
        bullish_orb = (nifty_ltp > self.orb_high) and (ema9 > ema21) and (rsi >= 55)
        # Continuation setup: holds above EMA9 after 13:30 with RSI momentum
        bullish_continuation = (time_part >= "13:30") and (nifty_ltp > ema9 > ema21) and (rsi >= 65)

        if bullish_orb or bullish_continuation:
            atm_contract = self.option_loader.get_atm_contract(
                date_str=date_str,
                timestamp=timestamp,
                option_type="CE",
                underlying="NIFTY",
                step=50.0
            )
            if atm_contract and atm_contract.get("ltp", 0) > 20:
                opt_ltp = atm_contract["ltp"]
                opt_strike = atm_contract["strike_price"]
                opt_symbol = f"NIFTY-{int(opt_strike)}-CE"
                sl = round(max(5.0, opt_ltp - self.params["sl_points"]), 2)
                tgt = round(opt_ltp + (self.params["sl_points"] * self.params["target_multiplier"]), 2)

                signals.append({
                    "symbol": opt_symbol,
                    "security_id": atm_contract.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": opt_ltp,
                    "sl": sl,
                    "target": tgt,
                    "score": 80,
                    "instrument_type": InstrumentType.OPTION_CE,
                    "metadata": {
                        "underlying_ltp": nifty_ltp,
                        "strike": opt_strike,
                        "option_type": "CE",
                        "strategy": self.name,
                        "delta": atm_contract.get("delta", 0.5)
                    }
                })
                self.last_trade_time = timestamp

        # ── Bearish Breakdown -> BUY ATM PE ───────────────────────────────────
        elif nifty_ltp < self.orb_low and ema9 < ema21 and rsi <= 45:
            atm_contract = self.option_loader.get_atm_contract(
                date_str=date_str,
                timestamp=timestamp,
                option_type="PE",
                underlying="NIFTY",
                step=50.0
            )
            if atm_contract and atm_contract.get("ltp", 0) > 20:
                opt_ltp = atm_contract["ltp"]
                opt_strike = atm_contract["strike_price"]
                opt_symbol = f"NIFTY-{int(opt_strike)}-PE"
                sl = round(max(5.0, opt_ltp - self.params["sl_points"]), 2)
                tgt = round(opt_ltp + (self.params["sl_points"] * self.params["target_multiplier"]), 2)

                signals.append({
                    "symbol": opt_symbol,
                    "security_id": atm_contract.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": opt_ltp,
                    "sl": sl,
                    "target": tgt,
                    "score": 80,
                    "instrument_type": InstrumentType.OPTION_PE,
                    "metadata": {
                        "underlying_ltp": nifty_ltp,
                        "strike": opt_strike,
                        "option_type": "PE",
                        "strategy": self.name,
                        "delta": atm_contract.get("delta", -0.5)
                    }
                })
                self.last_trade_time = timestamp

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.daily_bars.clear()
