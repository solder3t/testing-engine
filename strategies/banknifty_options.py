"""
strategies/banknifty_options.py — BankNifty High-Beta Option Breakout Strategy.

Institutional BankNifty Options Strategy:
1. Operates on high-volatility BankNifty index (strike step: 100 points, lot size: 15).
2. Establishes the 09:15 - 09:30 Opening Range Breakout (ORB) channel.
3. Upon breakout with EMA ribbon (EMA 9 vs 21) & RSI momentum confirmation:
   - Bullish breakout: Buys ATM Call Option (CE).
   - Bearish breakdown: Buys ATM Put Option (PE).
4. Employs BankNifty-specific risk brackets (30 pts SL, 2.0x target multiplier).
"""

from typing import Dict, List, Any, Optional
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from data.option_chain_loader import OptionChainLoader
from indicators.indicators import calculate_ema, calculate_rsi
from config import TRADING_START


class BankNiftyOptionsStrategy(BaseStrategy):
    """BankNifty High-Beta Option Breakout Strategy."""

    def __init__(self, params: Optional[Dict[str, Any]] = None, option_loader: Optional[Any] = None):
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
            "orb_window_minutes": 15,
            "sl_points": 30.0,           # Points on BankNifty option premium
            "target_multiplier": 2.0,    # Target = 2.0 * sl_points = 60 pts
            "lot_size": 15,              # Standard BankNifty lot size
            "strike_step": 100.0,        # 100-pt strike intervals for BankNifty
            "underlying": "BANKNIFTY"
        }
        if actual_params and isinstance(actual_params, dict):
            default_params.update(actual_params)

        super().__init__(name="BankNiftyOptionBreakout", params=default_params)
        self.option_loader = actual_loader if isinstance(actual_loader, OptionChainLoader) else OptionChainLoader()
        self.orb_high: Optional[float] = None
        self.orb_low: Optional[float] = None
        self.orb_established = False
        self.daily_bars: List[Dict[str, Any]] = []
        self.last_trade_time = ""

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        if context and "option_loader" in context and isinstance(context["option_loader"], OptionChainLoader):
            self.option_loader = context["option_loader"]
        self.orb_high = None
        self.orb_low = None
        self.orb_established = False
        self.daily_bars.clear()
        self.last_trade_time = ""

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        underlying = self.params.get("underlying", "BANKNIFTY")
        bn_quote = quotes.get(underlying) or quotes.get("BANKNIFTY") or quotes.get("NIFTY BANK")
        if not bn_quote:
            return []

        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        bn_ltp = float(bn_quote.get("close", bn_quote.get("ltp", 0.0)))
        bn_high = float(bn_quote.get("high", bn_ltp))
        bn_low = float(bn_quote.get("low", bn_ltp))

        if bn_ltp <= 0:
            return []

        self.daily_bars.append(bn_quote)

        # ── Establish ORB between 09:15 and 09:30 ─────────────────────────────
        if time_part < "09:15":
            return []

        if "09:15" <= time_part < "09:30":
            if self.orb_high is None or bn_high > self.orb_high:
                self.orb_high = bn_high
            if self.orb_low is None or bn_low < self.orb_low:
                self.orb_low = bn_low
            return []

        self.orb_established = True

        # Only trade between 09:30 and 14:45
        if time_part < TRADING_START or time_part >= "14:45":
            return []

        # Cooldown: avoid duplicate trades in quick succession
        if self.last_trade_time and timestamp <= self.last_trade_time:
            return []

        if len(self.daily_bars) < 15:
            return []

        closes = pd.Series([float(b.get("close", b.get("ltp", 0.0))) for b in self.daily_bars])
        ema9 = calculate_ema(closes, 9).iloc[-1]
        ema21 = calculate_ema(closes, 21).iloc[-1]
        rsi = calculate_rsi(closes, 14).iloc[-1]

        signals = []
        date_str = timestamp.split(" ")[0]
        step = float(self.params.get("strike_step", 100.0))
        sl_points = float(self.params.get("sl_points", 30.0))
        tgt_mult = float(self.params.get("target_multiplier", 2.0))
        lot_size = int(self.params.get("lot_size", 15))

        # ── Bullish Breakout -> BUY ATM CE ───────────────────────────────────
        bullish_orb = (self.orb_high is not None) and (bn_ltp > self.orb_high) and (ema9 > ema21) and (rsi >= 55)
        bullish_trend = (time_part >= "13:00") and (bn_ltp > ema9 > ema21) and (rsi >= 60)

        if bullish_orb or bullish_trend:
            atm_contract = self.option_loader.get_atm_contract(
                date_str=date_str,
                timestamp=timestamp,
                option_type="CE",
                underlying=underlying,
                step=step
            )
            if atm_contract and atm_contract.get("ltp", 0) > 30:
                opt_ltp = atm_contract["ltp"]
                opt_strike = atm_contract["strike_price"]
                opt_symbol = f"{underlying}_{int(opt_strike)}_CE"
                sl = round(max(5.0, opt_ltp - sl_points), 2)
                tgt = round(opt_ltp + (sl_points * tgt_mult), 2)

                signals.append({
                    "symbol": opt_symbol,
                    "security_id": atm_contract.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": opt_ltp,
                    "sl": sl,
                    "target": tgt,
                    "score": 85,
                    "instrument_type": InstrumentType.OPTION_CE,
                    "lot_size": lot_size,
                    "metadata": {
                        "underlying": underlying,
                        "underlying_ltp": bn_ltp,
                        "strike": opt_strike,
                        "option_type": "CE",
                        "strategy": self.name,
                        "delta": atm_contract.get("delta", 0.5)
                    }
                })
                self.last_trade_time = timestamp

        # ── Bearish Breakdown -> BUY ATM PE ───────────────────────────────────
        elif (self.orb_low is not None) and (bn_ltp < self.orb_low) and (ema9 < ema21) and (rsi <= 45):
            atm_contract = self.option_loader.get_atm_contract(
                date_str=date_str,
                timestamp=timestamp,
                option_type="PE",
                underlying=underlying,
                step=step
            )
            if atm_contract and atm_contract.get("ltp", 0) > 30:
                opt_ltp = atm_contract["ltp"]
                opt_strike = atm_contract["strike_price"]
                opt_symbol = f"{underlying}_{int(opt_strike)}_PE"
                sl = round(max(5.0, opt_ltp - sl_points), 2)
                tgt = round(opt_ltp + (sl_points * tgt_mult), 2)

                signals.append({
                    "symbol": opt_symbol,
                    "security_id": atm_contract.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": opt_ltp,
                    "sl": sl,
                    "target": tgt,
                    "score": 85,
                    "instrument_type": InstrumentType.OPTION_PE,
                    "lot_size": lot_size,
                    "metadata": {
                        "underlying": underlying,
                        "underlying_ltp": bn_ltp,
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
