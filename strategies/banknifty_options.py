"""
strategies/banknifty_options.py — BankNifty High-Beta Option Breakout Strategy.

Institutional BankNifty Options Strategy:
1. Operates on high-volatility BankNifty index (100 pt strike interval, point-in-time lot size).
2. Establishes the 09:15 - 09:30 Opening Range Breakout (ORB) channel.
3. Upon breakout above ORB High: Buys ATM Call Option (CE).
4. Upon breakdown below ORB Low: Buys ATM Put Option (PE).
5. Employs BankNifty risk brackets (30 pts SL, 2.0x target multiplier).
"""

from typing import Dict, List, Any, Optional
import pandas as pd

from config import TRADING_START
from data.instrument_master import InstrumentMaster
from data.option_chain_loader import OptionChainLoader
from engine.param_spec import ParamSpec
from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy


class BankNiftyOptionsStrategy(BaseStrategy):
    """BankNifty High-Beta Option Breakout Strategy with dynamic lot and strike resolution."""

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
        self.current_date = ""

    @classmethod
    def param_specs(cls) -> List[ParamSpec]:
        return [
            ParamSpec("orb_window_minutes", "int", default=15, min_val=5, max_val=30, step=5, description="ORB period minutes"),
            ParamSpec("sl_points", "float", default=30.0, min_val=15.0, max_val=60.0, step=5.0, description="Stop loss points on option premium"),
            ParamSpec("target_multiplier", "float", default=2.0, min_val=1.5, max_val=3.5, step=0.5, description="Target multiple"),
        ]

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        if context and "option_loader" in context and isinstance(context["option_loader"], OptionChainLoader):
            self.option_loader = context["option_loader"]
        self.orb_high = None
        self.orb_low = None
        self.orb_established = False
        self.daily_bars.clear()
        self.last_trade_time = ""
        self.current_date = date_str

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

        if self.last_trade_time and timestamp <= self.last_trade_time:
            return []

        date_str = self.current_date or timestamp.split(" ")[0].replace("-", "_")
        signals = []

        step = float(self.params.get("strike_step", 100.0))
        lot_size = self.params.get("lot_size")
        if not lot_size:
            lot_size = InstrumentMaster.get_lot_size(underlying, date_str, is_derivative=True)

        strike_mode = str(self.params.get("strike_mode", "ATM"))

        # Bullish Breakout -> Buy ATM / Selected Strike CE
        if bn_ltp > self.orb_high:
            contract = self.option_loader.get_contract(
                date_str=date_str,
                timestamp=time_part,
                option_type="CE",
                underlying=underlying,
                strike_mode=strike_mode,
                step=step
            )
            if contract and contract.get("ltp", 0.0) > 10.0:
                prem = contract["ltp"]
                sl_pts = float(self.params.get("sl_points", 30.0))
                tgt_pts = sl_pts * float(self.params.get("target_multiplier", 2.0))
                sl_price = max(1.0, round(prem - sl_pts, 2))
                tgt_price = round(prem + tgt_pts, 2)

                contract_sym = f"OPT_{contract['security_id']}_{underlying}_{contract['strike_price']}_CE"
                signals.append({
                    "symbol": contract_sym,
                    "security_id": contract["security_id"],
                    "side": OrderSide.BUY,
                    "price": prem,
                    "sl": sl_price,
                    "target": tgt_price,
                    "score": 85,
                    "lot_size": lot_size,
                    "instrument_type": InstrumentType.OPTION_CE,
                    "metadata": {
                        "underlying": underlying,
                        "strike": contract["strike_price"],
                        "option_type": "CE",
                        "delta": contract.get("delta", 0.5),
                        "iv": contract.get("iv", 18.0),
                        "strategy": self.name
                    }
                })
                self.last_trade_time = timestamp

        # Bearish Breakdown -> Buy ATM / Selected Strike PE
        elif bn_ltp < self.orb_low:
            contract = self.option_loader.get_contract(
                date_str=date_str,
                timestamp=time_part,
                option_type="PE",
                underlying=underlying,
                strike_mode=strike_mode,
                step=step
            )
            if contract and contract.get("ltp", 0.0) > 10.0:
                prem = contract["ltp"]
                sl_pts = float(self.params.get("sl_points", 30.0))
                tgt_pts = sl_pts * float(self.params.get("target_multiplier", 2.0))
                sl_price = max(1.0, round(prem - sl_pts, 2))
                tgt_price = round(prem + tgt_pts, 2)

                contract_sym = f"OPT_{contract['security_id']}_{underlying}_{contract['strike_price']}_PE"
                signals.append({
                    "symbol": contract_sym,
                    "security_id": contract["security_id"],
                    "side": OrderSide.BUY,
                    "price": prem,
                    "sl": sl_price,
                    "target": tgt_price,
                    "score": 85,
                    "lot_size": lot_size,
                    "instrument_type": InstrumentType.OPTION_PE,
                    "metadata": {
                        "underlying": underlying,
                        "strike": contract["strike_price"],
                        "option_type": "PE",
                        "delta": contract.get("delta", -0.5),
                        "iv": contract.get("iv", 18.0),
                        "strategy": self.name
                    }
                })
                self.last_trade_time = timestamp

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.orb_high = None
        self.orb_low = None
        self.orb_established = False
        self.daily_bars.clear()
        self.last_trade_time = ""
