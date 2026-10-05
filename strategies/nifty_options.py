"""
strategies/nifty_options.py — Index Options Breakout & Momentum Strategy.

Replays intraday option buying (ATM CE / PE) using Opening Range Breakout (ORB)
and moving-average momentum confirmation with dynamic option chain lookups.
Works for ANY underlying index or stock option (NIFTY, BANKNIFTY, FINNIFTY, etc.).
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

from config import TRADING_START, TRADING_END
from data.instrument_master import InstrumentMaster
from data.option_chain_loader import OptionChainLoader
from engine.param_spec import ParamSpec
from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from indicators.indicators import calculate_ema, calculate_rsi
from strategies.base_strategy import BaseStrategy


class NiftyOptionsStrategy(BaseStrategy):
    """Index Options Strategy with dynamic ATM option chain execution."""

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
            "underlying": "NIFTY",
            "orb_window_minutes": 15,    # 09:15 to 09:30 define ORB range
            "min_rr": 1.5,
            "sl_points": 12.0,           # Points on option premium
            "target_multiplier": 1.8,
            "lot_size": None,            # Dynamically resolved via InstrumentMaster
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
        self.current_date = ""

    @classmethod
    def param_specs(cls) -> List[ParamSpec]:
        return [
            ParamSpec("orb_window_minutes", "int", default=15, min_val=5, max_val=30, step=5, description="Opening range breakout duration in minutes"),
            ParamSpec("sl_points", "float", default=12.0, min_val=8.0, max_val=25.0, step=2.0, description="Stop loss points on option premium"),
            ParamSpec("target_multiplier", "float", default=1.8, min_val=1.2, max_val=3.0, step=0.2, description="Target multiple of stop loss"),
            ParamSpec("min_rr", "float", default=1.5, min_val=1.0, max_val=2.5, step=0.25, description="Minimum acceptable risk-reward"),
        ]

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        if context and "option_loader" in context and isinstance(context["option_loader"], OptionChainLoader):
            self.option_loader = context["option_loader"]
        self.orb_high = None
        self.orb_low = None
        self.orb_established = False
        self.daily_bars = []
        self.last_trade_time = ""
        self.current_date = date_str

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        underlying = self.params.get("underlying", "NIFTY")
        u_quote = quotes.get(underlying) or quotes.get(f"{underlying} 50") or quotes.get("NIFTY") or quotes.get("NIFTY 50")
        if not u_quote:
            return []

        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        u_ltp = float(u_quote.get("close", u_quote.get("ltp", 0.0)))
        u_high = float(u_quote.get("high", u_ltp))
        u_low = float(u_quote.get("low", u_ltp))

        self.daily_bars.append(u_quote)

        # ── Establish ORB between 09:15 and 09:30 ─────────────────────────────
        if time_part < "09:15":
            return []

        if "09:15" <= time_part < "09:30":
            if self.orb_high is None or u_high > self.orb_high:
                self.orb_high = u_high
            if self.orb_low is None or u_low < self.orb_low:
                self.orb_low = u_low
            return []

        self.orb_established = True

        # Only trade between 09:30 and 14:45
        if time_part < TRADING_START or time_part >= "14:45":
            return []

        if self.last_trade_time and timestamp <= self.last_trade_time:
            return []

        if len(self.daily_bars) < 15:
            return []

        closes = pd.Series([float(b.get("close", b.get("ltp", 0.0))) for b in self.daily_bars])
        ema9 = calculate_ema(closes, 9).iloc[-1]
        ema21 = calculate_ema(closes, 21).iloc[-1]
        rsi = calculate_rsi(closes, 14).iloc[-1]

        date_str = self.current_date or timestamp.split(" ")[0].replace("-", "_")
        signals = []

        # Bullish Breakout -> Buy ATM CE
        if u_ltp > self.orb_high and ema9 > ema21 and 55 <= rsi <= 75:
            step = InstrumentMaster.get_strike_interval(underlying, u_ltp)
            contract = self.option_loader.get_atm_contract(
                date_str=date_str,
                timestamp=time_part,
                option_type="CE",
                underlying=underlying,
                step=step
            )
            if contract and contract.get("ltp", 0.0) > 10.0:
                prem = contract["ltp"]
                sl_pts = float(self.params.get("sl_points", 12.0))
                tgt_pts = sl_pts * float(self.params.get("target_multiplier", 1.8))
                sl_price = max(1.0, round(prem - sl_pts, 2))
                tgt_price = round(prem + tgt_pts, 2)

                lot_size = self.params.get("lot_size")
                if not lot_size:
                    lot_size = InstrumentMaster.get_lot_size(underlying, date_str, is_derivative=True)

                contract_sym = f"OPT_{contract['security_id']}_{underlying}_{contract['strike_price']}_CE"
                signals.append({
                    "symbol": contract_sym,
                    "security_id": contract["security_id"],
                    "side": OrderSide.BUY,
                    "price": prem,
                    "sl": sl_price,
                    "target": tgt_price,
                    "score": 80,
                    "lot_size": lot_size,
                    "instrument_type": InstrumentType.OPTION_CE,
                    "metadata": {
                        "underlying": underlying,
                        "strike": contract["strike_price"],
                        "option_type": "CE",
                        "delta": contract.get("delta", 0.5),
                        "iv": contract.get("iv", 15.0),
                        "strategy": self.name
                    }
                })
                self.last_trade_time = timestamp

        # Bearish Breakdown -> Buy ATM PE
        elif u_ltp < self.orb_low and ema9 < ema21 and 25 <= rsi <= 45:
            step = InstrumentMaster.get_strike_interval(underlying, u_ltp)
            contract = self.option_loader.get_atm_contract(
                date_str=date_str,
                timestamp=time_part,
                option_type="PE",
                underlying=underlying,
                step=step
            )
            if contract and contract.get("ltp", 0.0) > 10.0:
                prem = contract["ltp"]
                sl_pts = float(self.params.get("sl_points", 12.0))
                tgt_pts = sl_pts * float(self.params.get("target_multiplier", 1.8))
                sl_price = max(1.0, round(prem - sl_pts, 2))
                tgt_price = round(prem + tgt_pts, 2)

                lot_size = self.params.get("lot_size")
                if not lot_size:
                    lot_size = InstrumentMaster.get_lot_size(underlying, date_str, is_derivative=True)

                contract_sym = f"OPT_{contract['security_id']}_{underlying}_{contract['strike_price']}_PE"
                signals.append({
                    "symbol": contract_sym,
                    "security_id": contract["security_id"],
                    "side": OrderSide.BUY,
                    "price": prem,
                    "sl": sl_price,
                    "target": tgt_price,
                    "score": 80,
                    "lot_size": lot_size,
                    "instrument_type": InstrumentType.OPTION_PE,
                    "metadata": {
                        "underlying": underlying,
                        "strike": contract["strike_price"],
                        "option_type": "PE",
                        "delta": contract.get("delta", -0.5),
                        "iv": contract.get("iv", 15.0),
                        "strategy": self.name
                    }
                })
                self.last_trade_time = timestamp

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.orb_high = None
        self.orb_low = None
        self.orb_established = False
        self.daily_bars = []
        self.last_trade_time = ""
