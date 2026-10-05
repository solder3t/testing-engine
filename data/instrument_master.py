"""
data/instrument_master.py — Universal Multi-Instrument Specifications Master.

Provides point-in-time lot sizes, strike intervals, tick sizes, freeze quantities,
asset classification, and price/strike rounding rules across all NSE/BSE instruments
(Indices, Equities, Futures, Options).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
import math
from typing import Dict, List, Optional, Tuple, Union


@dataclass(frozen=True)
class LotSizeRevision:
    effective_from: str  # YYYY-MM-DD
    lot_size: int


@dataclass
class InstrumentSpec:
    symbol: str
    asset_type: str  # "INDEX", "EQUITY", "COMMODITY"
    base_tick_size: float = 0.05
    strike_interval: float = 50.0
    freeze_qty: int = 1800
    lot_history: List[LotSizeRevision] = field(default_factory=list)
    multiplier: float = 1.0


class InstrumentMaster:
    """
    Central repository of market microstructure parameters and point-in-time contract
    specifications.
    """

    _SPECS: Dict[str, InstrumentSpec] = {
        "NIFTY": InstrumentSpec(
            symbol="NIFTY",
            asset_type="INDEX",
            base_tick_size=0.05,
            strike_interval=50.0,
            freeze_qty=1800,
            lot_history=[
                LotSizeRevision("2000-01-01", 50),
                LotSizeRevision("2024-04-26", 25),
                LotSizeRevision("2024-11-20", 75),
            ]
        ),
        "NIFTY50": InstrumentSpec(
            symbol="NIFTY50",
            asset_type="INDEX",
            base_tick_size=0.05,
            strike_interval=50.0,
            freeze_qty=1800,
            lot_history=[
                LotSizeRevision("2000-01-01", 50),
                LotSizeRevision("2024-04-26", 25),
                LotSizeRevision("2024-11-20", 75),
            ]
        ),
        "BANKNIFTY": InstrumentSpec(
            symbol="BANKNIFTY",
            asset_type="INDEX",
            base_tick_size=0.05,
            strike_interval=100.0,
            freeze_qty=900,
            lot_history=[
                LotSizeRevision("2000-01-01", 25),
                LotSizeRevision("2023-07-01", 15),
                LotSizeRevision("2024-11-20", 30),
            ]
        ),
        "FINNIFTY": InstrumentSpec(
            symbol="FINNIFTY",
            asset_type="INDEX",
            base_tick_size=0.05,
            strike_interval=50.0,
            freeze_qty=1800,
            lot_history=[
                LotSizeRevision("2020-01-01", 40),
                LotSizeRevision("2024-11-20", 65),
            ]
        ),
        "MIDCPNIFTY": InstrumentSpec(
            symbol="MIDCPNIFTY",
            asset_type="INDEX",
            base_tick_size=0.05,
            strike_interval=25.0,
            freeze_qty=4200,
            lot_history=[
                LotSizeRevision("2020-01-01", 75),
                LotSizeRevision("2024-11-20", 120),
            ]
        ),
        "SENSEX": InstrumentSpec(
            symbol="SENSEX",
            asset_type="INDEX",
            base_tick_size=0.05,
            strike_interval=100.0,
            freeze_qty=1000,
            lot_history=[
                LotSizeRevision("2000-01-01", 10),
                LotSizeRevision("2024-11-20", 20),
            ]
        ),
        "BANKEX": InstrumentSpec(
            symbol="BANKEX",
            asset_type="INDEX",
            base_tick_size=0.05,
            strike_interval=100.0,
            freeze_qty=1000,
            lot_history=[
                LotSizeRevision("2020-01-01", 15),
                LotSizeRevision("2024-11-20", 30),
            ]
        ),
        # Sample major equities
        "RELIANCE": InstrumentSpec(
            symbol="RELIANCE",
            asset_type="EQUITY",
            base_tick_size=0.05,
            strike_interval=20.0,
            freeze_qty=25000,
            lot_history=[LotSizeRevision("2020-01-01", 250)]
        ),
        "TCS": InstrumentSpec(
            symbol="TCS",
            asset_type="EQUITY",
            base_tick_size=0.05,
            strike_interval=50.0,
            freeze_qty=17500,
            lot_history=[LotSizeRevision("2020-01-01", 175)]
        ),
        "INFY": InstrumentSpec(
            symbol="INFY",
            asset_type="EQUITY",
            base_tick_size=0.05,
            strike_interval=20.0,
            freeze_qty=40000,
            lot_history=[LotSizeRevision("2020-01-01", 400)]
        ),
        "HDFCBANK": InstrumentSpec(
            symbol="HDFCBANK",
            asset_type="EQUITY",
            base_tick_size=0.05,
            strike_interval=20.0,
            freeze_qty=55000,
            lot_history=[LotSizeRevision("2020-01-01", 550)]
        ),
        "ICICIBANK": InstrumentSpec(
            symbol="ICICIBANK",
            asset_type="EQUITY",
            base_tick_size=0.05,
            strike_interval=10.0,
            freeze_qty=70000,
            lot_history=[LotSizeRevision("2020-01-01", 700)]
        ),
    }

    @classmethod
    def clean_symbol(cls, symbol: str) -> str:
        """Extracts the root underlying symbol from complex derivative or prefixed names."""
        s = symbol.upper().strip()
        for prefix in ("OPT_", "FUT_", "EQ_", "IDX_", "CHAIN_"):
            if s.startswith(prefix):
                parts = s.split("_")
                # e.g. opt_69676_BANKNIFTY_20260929_52600_CE -> BANKNIFTY
                if len(parts) >= 3 and parts[1].isdigit():
                    return parts[2]
                elif len(parts) >= 2:
                    return parts[1]
        
        # Check standard tokens (longest/compound names first to prevent substring collisions)
        for index_name in ("BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTY50", "BANKEX", "SENSEX", "NIFTY"):
            if index_name in s:
                return "NIFTY" if index_name == "NIFTY50" else index_name
        
        # Strip trailing numbers/expiry
        base = s.split("_")[0]
        return base

    @classmethod
    def get_lot_size(
        cls, 
        symbol: str, 
        trade_date: Optional[Union[str, date, datetime]] = None,
        is_derivative: bool = True
    ) -> int:
        """
        Returns point-in-time lot size for the given symbol and trade date.
        If is_derivative=False (Cash Equity), returns 1.
        """
        root = cls.clean_symbol(symbol)
        spec = cls._SPECS.get(root)

        if not is_derivative or (spec and spec.asset_type == "EQUITY" and not is_derivative):
            return 1

        if not spec or not spec.lot_history:
            # Default fallback for unknown stock derivatives is 100 or 1 for cash
            return 1 if not is_derivative else 1

        if trade_date is None:
            # Return most recent lot size
            return spec.lot_history[-1].lot_size

        # Convert trade_date to 'YYYY-MM-DD' string
        if isinstance(trade_date, datetime) or isinstance(trade_date, date):
            date_str = trade_date.strftime("%Y-%m-%d")
        else:
            d_clean = str(trade_date).replace("_", "-")[:10]
            date_str = d_clean

        effective_lot = spec.lot_history[0].lot_size
        for rev in spec.lot_history:
            if date_str >= rev.effective_from:
                effective_lot = rev.lot_size
            else:
                break
        return effective_lot

    @classmethod
    def get_strike_interval(cls, symbol: str, spot_price: Optional[float] = None) -> float:
        """Returns the standard strike step interval for options selection."""
        root = cls.clean_symbol(symbol)
        if root in cls._SPECS:
            return cls._SPECS[root].strike_interval
        
        if spot_price is not None and spot_price > 0:
            if spot_price < 100:
                return 2.5
            elif spot_price < 250:
                return 5.0
            elif spot_price < 500:
                return 10.0
            elif spot_price < 1000:
                return 20.0
            elif spot_price < 2500:
                return 50.0
            else:
                return 100.0
        return 50.0

    @classmethod
    def get_tick_size(cls, symbol: str) -> float:
        """Returns the minimum price tick size for orders."""
        root = cls.clean_symbol(symbol)
        spec = cls._SPECS.get(root)
        return spec.base_tick_size if spec else 0.05

    @classmethod
    def get_freeze_qty(cls, symbol: str) -> int:
        """Returns the maximum quantity permitted in a single order (NSE freeze limit)."""
        root = cls.clean_symbol(symbol)
        spec = cls._SPECS.get(root)
        return spec.freeze_qty if spec else 1800

    @classmethod
    def is_index(cls, symbol: str) -> bool:
        """Returns True if the symbol is an index or index derivative."""
        root = cls.clean_symbol(symbol)
        spec = cls._SPECS.get(root)
        return spec.asset_type == "INDEX" if spec else False

    @classmethod
    def round_to_tick(cls, price: float, symbol: str = "NIFTY") -> float:
        """Rounds price to the nearest valid exchange tick."""
        tick = cls.get_tick_size(symbol)
        if tick <= 0:
            return price
        return round(round(price / tick) * tick, 4)

    @classmethod
    def round_to_strike(cls, price: float, symbol: str = "NIFTY") -> float:
        """Rounds price to the nearest standard strike price."""
        interval = cls.get_strike_interval(symbol, price)
        if interval <= 0:
            return price
        return round(round(price / interval) * interval, 2)

    # Alias for convenience
    get_strike_step = get_strike_interval

