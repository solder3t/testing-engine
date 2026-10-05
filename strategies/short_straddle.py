"""
strategies/short_straddle.py — Intraday Short Straddle / Strangle Premium Decay Strategy.

Executes institutional intraday option writing:
1. At entry_time (default 09:20), identifies the ATM strike for the underlying instrument.
2. Simultaneously sells ATM/OTM Call (CE) and Put (PE) options.
3. Sets a strict individual stop-loss (default 25%) and decay target (default 60%) on each leg.
4. Harvests intraday theta decay until 15:15 EOD square-off.
Works for ANY underlying (NIFTY, BANKNIFTY, FINNIFTY, SENSEX, or equities).
"""

from typing import Dict, List, Any, Optional
from data.instrument_master import InstrumentMaster
from data.option_chain_loader import OptionChainLoader
from engine.param_spec import ParamSpec
from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy


class ShortStraddleStrategy(BaseStrategy):
    """Institutional Short Straddle / Strangle Strategy with dynamic strike & lot resolution."""

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
            "entry_time": "09:20",
            "sl_pct": 0.25,        # 25% stop-loss above entry premium
            "target_pct": 0.60,    # 60% decay profit target
            "lot_size": 25,        # Standard NIFTY lot size default
            "strike_step": 50.0,   # Dynamic from InstrumentMaster if not overridden
            "otm_strikes": 0       # 0 = ATM Straddle, 1+ = OTM Strangle
        }
        if actual_params and isinstance(actual_params, dict):
            default_params.update(actual_params)

        super().__init__(name="ShortStraddleTheta", params=default_params)
        self.option_loader = actual_loader if isinstance(actual_loader, OptionChainLoader) else OptionChainLoader()
        self.entered_today = False
        self.current_date = ""

    @classmethod
    def param_specs(cls) -> List[ParamSpec]:
        return [
            ParamSpec("entry_time", "categorical", default="09:20", choices=["09:20", "09:30", "09:45"], description="Entry timestamp"),
            ParamSpec("sl_pct", "float", default=0.25, min_val=0.15, max_val=0.40, step=0.05, description="Individual leg stop loss % above entry premium"),
            ParamSpec("target_pct", "float", default=0.60, min_val=0.40, max_val=0.80, step=0.05, description="Decay profit target %"),
            ParamSpec("otm_strikes", "int", default=0, min_val=0, max_val=2, step=1, description="Number of strikes OTM for strangle (0 for ATM straddle)"),
        ]

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        if context and "option_loader" in context and isinstance(context["option_loader"], OptionChainLoader):
            self.option_loader = context["option_loader"]
        self.entered_today = False
        self.current_date = date_str

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if self.entered_today:
            return []

        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        entry_time = self.params.get("entry_time", "09:20")

        # Wait until target entry time (09:20) and not after 10:00
        if time_part < entry_time or time_part > "10:00":
            return []

        underlying = self.params.get("underlying", "NIFTY")
        u_quote = quotes.get(underlying) or quotes.get(f"{underlying} 50") or quotes.get("NIFTY") or quotes.get("NIFTY 50")
        if not u_quote:
            return []

        u_ltp = float(u_quote.get("close", u_quote.get("ltp", 0.0)))
        if u_ltp <= 0:
            return []

        date_str = self.current_date or timestamp.split(" ")[0].replace("-", "_")
        step = self.params.get("strike_step")
        if not step:
            step = InstrumentMaster.get_strike_interval(underlying, u_ltp)
        step = float(step)

        atm_strike = self.option_loader.get_atm_strike(u_ltp, step=step, symbol=underlying)
        otm_offset = int(self.params.get("otm_strikes", 0)) * step

        ce_strike = atm_strike + otm_offset
        pe_strike = atm_strike - otm_offset

        chain_df = self.option_loader.get_nearest_chain(date_str, timestamp, underlying=underlying)
        if chain_df is None or chain_df.empty:
            return []

        # Find CE contract
        ce_row = chain_df[chain_df["strike_price"] == ce_strike]
        if ce_row.empty:
            ce_row = chain_df.loc[[(chain_df["strike_price"] - ce_strike).abs().idxmin()]]
        r_ce = ce_row.iloc[0]
        ce_ltp = float(r_ce.get("ce_ltp") or 0.0)

        # Find PE contract
        pe_row = chain_df[chain_df["strike_price"] == pe_strike]
        if pe_row.empty:
            pe_row = chain_df.loc[[(chain_df["strike_price"] - pe_strike).abs().idxmin()]]
        r_pe = pe_row.iloc[0]
        pe_ltp = float(r_pe.get("pe_ltp") or 0.0)

        if ce_ltp <= 0 or pe_ltp <= 0:
            return []

        sl_pct = float(self.params.get("sl_pct", 0.25))
        tgt_pct = float(self.params.get("target_pct", 0.60))

        lot_size = self.params.get("lot_size")
        if not lot_size:
            lot_size = InstrumentMaster.get_lot_size(underlying, date_str, is_derivative=True)

        ce_symbol = f"OPT_{int(r_ce.get('ce_security_id') or 0)}_{underlying}_{int(r_ce['strike_price'])}_CE"
        pe_symbol = f"OPT_{int(r_pe.get('pe_security_id') or 0)}_{underlying}_{int(r_pe['strike_price'])}_PE"

        signals = [
            {
                "symbol": ce_symbol,
                "security_id": int(r_ce.get("ce_security_id") or 0),
                "side": OrderSide.SELL,
                "price": ce_ltp,
                "sl": round(ce_ltp * (1.0 + sl_pct), 2),
                "target": round(ce_ltp * (1.0 - tgt_pct), 2),
                "instrument_type": InstrumentType.OPTION_CE,
                "lot_size": lot_size,
                "score": 80,
                "metadata": {
                    "strike": float(r_ce["strike_price"]),
                    "option_type": "CE",
                    "underlying": underlying,
                    "leg": "SHORT_CE",
                    "strategy": self.name
                }
            },
            {
                "symbol": pe_symbol,
                "security_id": int(r_pe.get("pe_security_id") or 0),
                "side": OrderSide.SELL,
                "price": pe_ltp,
                "sl": round(pe_ltp * (1.0 + sl_pct), 2),
                "target": round(pe_ltp * (1.0 - tgt_pct), 2),
                "instrument_type": InstrumentType.OPTION_PE,
                "lot_size": lot_size,
                "score": 80,
                "metadata": {
                    "strike": float(r_pe["strike_price"]),
                    "option_type": "PE",
                    "underlying": underlying,
                    "leg": "SHORT_PE",
                    "strategy": self.name
                }
            }
        ]

        self.entered_today = True
        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.entered_today = False
