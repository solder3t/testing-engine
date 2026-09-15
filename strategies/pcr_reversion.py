"""
strategies/pcr_reversion.py — Put-Call Ratio (PCR) Sentiment Mean-Reversion Strategy.

Institutional options sentiment model:
1. Computes instantaneous Put-Call Ratio (PCR = total PE OI / total CE OI) from the real option chain.
2. Identifies extreme sentiment imbalances:
   - PCR < pcr_oversold (default 0.70): Excessive call writing / panic put buying -> Reversal bounce -> Buy ATM CE.
   - PCR > pcr_overbought (default 1.35): Extreme bullish complacency / heavy put writing -> Pullback -> Buy ATM PE.
3. Uses technical momentum confirmation (RSI / candle price action) to trigger high-probability entries.
4. Manages trades with explicit SL points/percentage and profit targets.
"""

from typing import Dict, List, Any, Optional
import pandas as pd

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from data.option_chain_loader import OptionChainLoader
from indicators.indicators import calculate_rsi
from config import TRADING_START


class PcrReversionStrategy(BaseStrategy):
    """Institutional PCR Sentiment Mean-Reversion Strategy for NIFTY Index Options."""

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
            "pcr_oversold": 0.70,      # PCR <= 0.70 triggers bullish reversal
            "pcr_overbought": 1.35,    # PCR >= 1.35 triggers bearish reversal
            "sl_pct": 0.25,            # 25% stop loss on option premium
            "target_pct": 0.50,        # 50% target gain on option premium
            "lot_size": 25,            # Standard NIFTY lot size
            "strike_step": 50.0,
            "cooldown_bars": 15,       # Minimum bars between consecutive entries
            "underlying": "NIFTY"
        }
        if actual_params and isinstance(actual_params, dict):
            default_params.update(actual_params)

        super().__init__(name="PcrReversionSentiment", params=default_params)
        self.option_loader = actual_loader if isinstance(actual_loader, OptionChainLoader) else OptionChainLoader()
        self.bars_since_last_trade = 999
        self.daily_bars: List[Dict[str, Any]] = []

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        if context and "option_loader" in context and isinstance(context["option_loader"], OptionChainLoader):
            self.option_loader = context["option_loader"]
        self.bars_since_last_trade = 999
        self.daily_bars.clear()

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        time_part = timestamp.split(" ")[-1] if " " in timestamp else timestamp
        if time_part < TRADING_START or time_part >= "14:45":
            return []

        underlying = self.params.get("underlying", "NIFTY")
        spot_quote = quotes.get(underlying) or quotes.get(f"{underlying} 50")
        if not spot_quote:
            return []

        spot_ltp = float(spot_quote.get("close", spot_quote.get("ltp", 0.0)))
        if spot_ltp <= 0:
            return []

        self.daily_bars.append(spot_quote)
        self.bars_since_last_trade += 1

        cooldown = int(self.params.get("cooldown_bars", 15))
        if self.bars_since_last_trade < cooldown:
            return []

        if len(self.daily_bars) < 14:
            return []

        date_str = timestamp.split(" ")[0]
        chain_df = self.option_loader.get_nearest_chain(date_str, timestamp, underlying=underlying)
        if chain_df is None or chain_df.empty:
            return []

        pcr = self.option_loader.calculate_pcr(chain_df)
        pcr_oversold = float(self.params.get("pcr_oversold", 0.70))
        pcr_overbought = float(self.params.get("pcr_overbought", 1.35))

        closes = pd.Series([float(b.get("close", b.get("ltp", 0.0))) for b in self.daily_bars])
        rsi = calculate_rsi(closes, 14).iloc[-1]

        signals = []
        sl_pct = float(self.params.get("sl_pct", 0.25))
        tgt_pct = float(self.params.get("target_pct", 0.50))
        lot_size = int(self.params.get("lot_size", 25))
        step = float(self.params.get("strike_step", 50.0))

        # ── Bullish Mean Reversion: PCR Oversold (< 0.70) + RSI Confirmation ──────
        if pcr <= pcr_oversold and rsi <= 40:
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
                        "pcr": pcr,
                        "rsi": round(rsi, 2),
                        "strategy": self.name
                    }
                })
                self.bars_since_last_trade = 0

        # ── Bearish Mean Reversion: PCR Overbought (> 1.35) + RSI Confirmation ───
        elif pcr >= pcr_overbought and rsi >= 60:
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
                        "pcr": pcr,
                        "rsi": round(rsi, 2),
                        "strategy": self.name
                    }
                })
                self.bars_since_last_trade = 0

        return signals

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.daily_bars.clear()
