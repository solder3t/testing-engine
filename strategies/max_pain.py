"""
strategies/max_pain.py — Expiry Max Pain Convergence Magnet Strategy.

Capitalizes on institutional option pinning / gamma gravity:
1. Calculates the instantaneous Max Pain strike from real option chain OI distribution.
2. If spot price is displaced from Max Pain by >= min_displacement (default 40 pts) after 11:30 AM:
   - Spot < Max Pain: Bullish convergence expected -> Buy ATM Call (CE).
   - Spot > Max Pain: Bearish convergence expected -> Buy ATM Put (PE).
3. Holds until convergence target, stop-loss, or 15:15 EOD square-off.
"""

from typing import Dict, List, Any, Optional

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from data.option_chain_loader import OptionChainLoader


class MaxPainConvergenceStrategy(BaseStrategy):
    """Expiry Max Pain Convergence Strategy for NIFTY Index Options."""

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
            "entry_start_time": "11:30",
            "entry_end_time": "14:15",
            "min_displacement": 40.0,   # Minimum points spot must be away from Max Pain strike
            "sl_pct": 0.30,             # 30% stop-loss on option premium
            "target_pct": 0.50,         # 50% target on option premium
            "lot_size": 25,             # Standard NIFTY lot size
            "strike_step": 50.0,
            "underlying": "NIFTY"
        }
        if actual_params and isinstance(actual_params, dict):
            default_params.update(actual_params)

        super().__init__(name="MaxPainConvergence", params=default_params)
        self.option_loader = actual_loader if isinstance(actual_loader, OptionChainLoader) else OptionChainLoader()
        self.entered_today = False

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        if context and "option_loader" in context and isinstance(context["option_loader"], OptionChainLoader):
            self.option_loader = context["option_loader"]
        self.entered_today = False

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
        start_time = self.params.get("entry_start_time", "11:30")
        end_time = self.params.get("entry_end_time", "14:15")

        if time_part < start_time or time_part > end_time:
            return []

        underlying = self.params.get("underlying", "NIFTY")
        spot_quote = quotes.get(underlying) or quotes.get(f"{underlying} 50")
        if not spot_quote:
            return []

        spot_ltp = float(spot_quote.get("close", spot_quote.get("ltp", 0.0)))
        if spot_ltp <= 0:
            return []

        date_str = timestamp.split(" ")[0]
        chain_df = self.option_loader.get_nearest_chain(date_str, timestamp, underlying=underlying)
        if chain_df is None or chain_df.empty:
            return []

        max_pain = self.option_loader.calculate_max_pain(chain_df)
        if max_pain <= 0:
            return []

        displacement = spot_ltp - max_pain
        min_disp = float(self.params.get("min_displacement", 40.0))

        if abs(displacement) < min_disp:
            return []

        step = float(self.params.get("strike_step", 50.0))
        sl_pct = float(self.params.get("sl_pct", 0.30))
        tgt_pct = float(self.params.get("target_pct", 0.50))
        lot_size = int(self.params.get("lot_size", 25))

        signals = []

        # ── Spot is below Max Pain by >= min_displacement -> BUY ATM CE ───────
        if displacement <= -min_disp:
            atm_contract = self.option_loader.get_atm_contract(
                date_str=date_str,
                timestamp=timestamp,
                option_type="CE",
                underlying=underlying,
                step=step
            )
            if atm_contract and atm_contract.get("ltp", 0) > 20:
                opt_ltp = atm_contract["ltp"]
                opt_strike = atm_contract["strike_price"]
                opt_symbol = f"{underlying}_{int(opt_strike)}_CE"
                sl_price = round(max(5.0, opt_ltp * (1.0 - sl_pct)), 2)
                tgt_price = round(opt_ltp * (1.0 + tgt_pct), 2)

                signals.append({
                    "symbol": opt_symbol,
                    "security_id": atm_contract.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": opt_ltp,
                    "sl": sl_price,
                    "target": tgt_price,
                    "score": 85,
                    "instrument_type": InstrumentType.OPTION_CE,
                    "lot_size": lot_size,
                    "metadata": {
                        "underlying": underlying,
                        "strike": opt_strike,
                        "option_type": "CE",
                        "max_pain": max_pain,
                        "displacement": round(displacement, 2),
                        "strategy": self.name
                    }
                })
                self.entered_today = True

        # ── Spot is above Max Pain by >= min_displacement -> BUY ATM PE ───────
        elif displacement >= min_disp:
            atm_contract = self.option_loader.get_atm_contract(
                date_str=date_str,
                timestamp=timestamp,
                option_type="PE",
                underlying=underlying,
                step=step
            )
            if atm_contract and atm_contract.get("ltp", 0) > 20:
                opt_ltp = atm_contract["ltp"]
                opt_strike = atm_contract["strike_price"]
                opt_symbol = f"{underlying}_{int(opt_strike)}_PE"
                sl_price = round(max(5.0, opt_ltp * (1.0 - sl_pct)), 2)
                tgt_price = round(opt_ltp * (1.0 + tgt_pct), 2)

                signals.append({
                    "symbol": opt_symbol,
                    "security_id": atm_contract.get("security_id", 0),
                    "side": OrderSide.BUY,
                    "price": opt_ltp,
                    "sl": sl_price,
                    "target": tgt_price,
                    "score": 85,
                    "instrument_type": InstrumentType.OPTION_PE,
                    "lot_size": lot_size,
                    "metadata": {
                        "underlying": underlying,
                        "strike": opt_strike,
                        "option_type": "PE",
                        "max_pain": max_pain,
                        "displacement": round(displacement, 2),
                        "strategy": self.name
                    }
                })
                self.entered_today = True

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.entered_today = False
