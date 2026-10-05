"""
data/option_chain_loader.py — Historical Option Chain, Strike Selector & Greeks Replayer.

Extracts option chains, dynamic ATM strike selection, Greeks, PCR, and Max Pain
from optionchain_snapshot.db, supporting all instruments with strike step auto-discovery.
"""

import os
import sqlite3
import bisect
import logging
from typing import Optional, List, Dict, Union
import pandas as pd
import numpy as np

import config
from data.archive_manager import ArchiveManager
from data.instrument_master import InstrumentMaster

logger = logging.getLogger("option_chain_loader")


class StrikeSelector:
    """Intelligent strike selection supporting fixed-offset and liquidity-scored modes."""

    @staticmethod
    def select_strikes(
        chain: pd.DataFrame,
        underlying_price: float,
        count: int = 5,
        mode: str = "offset",
        step: float = 50.0
    ) -> pd.DataFrame:
        """
        Selects a subset of strikes around ATM or by liquidity.
        mode: 'offset' (centered around ATM) or 'liquidity' (highest combined volume/OI)
        """
        if chain is None or chain.empty:
            return pd.DataFrame()

        df = chain.copy()
        if "strike_price" not in df.columns:
            return df

        if mode == "liquidity":
            # Score = normalized volume + normalized OI - normalized spread
            ce_vol = df["ce_volume"].fillna(0)
            pe_vol = df["pe_volume"].fillna(0)
            tot_vol = ce_vol + pe_vol

            ce_oi = df["ce_oi"].fillna(0)
            pe_oi = df["pe_oi"].fillna(0)
            tot_oi = ce_oi + pe_oi

            # Rank by combined volume and OI
            vol_rank = tot_vol.rank(pct=True)
            oi_rank = tot_oi.rank(pct=True)
            score = 0.5 * vol_rank + 0.5 * oi_rank
            df["liquidity_score"] = score
            return df.sort_values(by="liquidity_score", ascending=False).head(count)

        # Default 'offset' mode: center around ATM
        atm_strike = round(underlying_price / step) * step
        df["distance_from_atm"] = (df["strike_price"] - atm_strike).abs()
        selected = df.sort_values(by="distance_from_atm", ascending=True).head(count)
        return selected.sort_values(by="strike_price", ascending=True)


class OptionChainLoader:
    """Historical option chain loader and analytics calculator."""

    def __init__(
        self,
        cache_dir: str = config.DATA_CACHE_DIR,
        archive_manager: Optional[ArchiveManager] = None,
        source_dir: Optional[str] = None
    ):
        self.cache_dir = os.path.expanduser(cache_dir)
        self.source_dir = os.path.expanduser(source_dir) if source_dir else None
        self.archive_manager = archive_manager or ArchiveManager(
            downloads_dir=self.source_dir or config.DOWNLOADS_DIR,
            cache_dir=self.cache_dir
        )
        self._session_cache: Dict[Tuple[str, str], Dict[str, pd.DataFrame]] = {}
        self._sorted_times: Dict[Tuple[str, str], List[str]] = {}

    def _get_db_path(self, date_str: str) -> Optional[str]:
        return self.archive_manager.get_database_path(
            date_str, "optionchain_snapshot.db", target_dir=self.source_dir
        )

    def list_chain_tables(self, date_str: str) -> List[str]:
        """List all option chain tables in the snapshot database."""
        db_path = self._get_db_path(date_str)
        if not db_path:
            return []

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        tables = [
            r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'chain_%'"
            ).fetchall()
        ]
        conn.close()
        return tables

    def load_session_chains(
        self,
        date_str: str,
        underlying: str = "NIFTY"
    ) -> Dict[str, pd.DataFrame]:
        """Preload all option chain snapshots for a date into an in-memory dictionary.
        Returns Dict[snapshot_time -> DataFrame].
        """
        root = InstrumentMaster.clean_symbol(underlying)
        cache_key = (date_str, root)
        if cache_key in self._session_cache:
            return self._session_cache[cache_key]

        tables = self.list_chain_tables(date_str)
        matching = [t for t in tables if t.upper().startswith(f"CHAIN_{root}_")]
        if not matching:
            matching = [t for t in tables if root in t.upper()]
        if not matching:
            self._session_cache[cache_key] = {}
            self._sorted_times[cache_key] = []
            return {}

        target_table = matching[0]
        db_path = self._get_db_path(date_str)
        if not db_path:
            self._session_cache[cache_key] = {}
            self._sorted_times[cache_key] = []
            return {}

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            full_df = pd.read_sql_query(
                f'SELECT * FROM "{target_table}" ORDER BY snapshot_time ASC, strike_price ASC',
                conn
            )
        finally:
            conn.close()

        if full_df.empty:
            self._session_cache[cache_key] = {}
            self._sorted_times[cache_key] = []
            return {}

        chains = {}
        for snap_time, group in full_df.groupby("snapshot_time", sort=False):
            chains[str(snap_time)] = group

        self._session_cache[cache_key] = chains
        self._sorted_times[cache_key] = sorted(chains.keys())
        return chains

    def get_nearest_chain(
        self,
        date_str: str,
        timestamp: str,
        underlying: str = "NIFTY"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch the nearest option chain snapshot at or before the given timestamp.
        Uses in-memory cache with bisect lookup for sub-millisecond execution.
        """
        root = InstrumentMaster.clean_symbol(underlying)
        cache_key = (date_str, root)
        if cache_key not in self._session_cache:
            self.load_session_chains(date_str, underlying=underlying)

        chains = self._session_cache.get(cache_key, {})
        sorted_times = self._sorted_times.get(cache_key, [])
        if not chains or not sorted_times:
            return None

        # Direct exact match
        if timestamp in chains:
            return chains[timestamp]

        # Binary search for snapshot_time <= timestamp
        idx = bisect.bisect_right(sorted_times, timestamp) - 1
        if idx >= 0:
            return chains[sorted_times[idx]]
        # Fallback to earliest snapshot
        return chains[sorted_times[0]]

    @staticmethod
    def get_atm_strike(
        underlying_ltp: float,
        step: Optional[float] = None,
        symbol: str = "NIFTY"
    ) -> float:
        """Find the ATM strike for an underlying price with dynamic step detection."""
        if underlying_ltp <= 0:
            return 0.0
        effective_step = step or InstrumentMaster.get_strike_interval(symbol, underlying_ltp)
        if effective_step <= 0:
            effective_step = 50.0
        return round(underlying_ltp / effective_step) * effective_step

    def get_atm_contract(
        self,
        date_str: str,
        timestamp: str,
        option_type: str = "CE",
        underlying: str = "NIFTY",
        step: Optional[float] = None
    ) -> Optional[Dict]:
        """
        Retrieves the exact ATM CE or PE contract snapshot for a given timestamp.
        """
        chain = self.get_nearest_chain(date_str, timestamp, underlying)
        if chain is None or chain.empty:
            return None

        underlying_ltp = float(chain["underlying_ltp"].iloc[0])
        effective_step = step or InstrumentMaster.get_strike_interval(underlying, underlying_ltp)
        atm_strike = self.get_atm_strike(underlying_ltp, step=effective_step, symbol=underlying)

        match = chain[chain["strike_price"] == atm_strike]
        if match.empty:
            # Nearest available strike
            diffs = (chain["strike_price"] - atm_strike).abs()
            match = chain.loc[[diffs.idxmin()]]

        row = match.iloc[0]
        prefix = option_type.lower()

        return {
            "snapshot_time": row["snapshot_time"],
            "underlying_ltp": underlying_ltp,
            "strike_price": float(row["strike_price"]),
            "security_id": int(row[f"{prefix}_security_id"]),
            "ltp": float(row[f"{prefix}_ltp"]),
            "iv": float(row[f"{prefix}_iv"]) if f"{prefix}_iv" in row and pd.notna(row[f"{prefix}_iv"]) else 0.0,
            "delta": float(row[f"{prefix}_delta"]) if f"{prefix}_delta" in row and pd.notna(row[f"{prefix}_delta"]) else 0.0,
            "theta": float(row[f"{prefix}_theta"]) if f"{prefix}_theta" in row and pd.notna(row[f"{prefix}_theta"]) else 0.0,
            "gamma": float(row[f"{prefix}_gamma"]) if f"{prefix}_gamma" in row and pd.notna(row[f"{prefix}_gamma"]) else 0.0,
            "vega": float(row[f"{prefix}_vega"]) if f"{prefix}_vega" in row and pd.notna(row[f"{prefix}_vega"]) else 0.0,
            "oi": float(row[f"{prefix}_oi"]) if f"{prefix}_oi" in row and pd.notna(row[f"{prefix}_oi"]) else 0.0,
            "volume": int(row[f"{prefix}_volume"]) if f"{prefix}_volume" in row and pd.notna(row[f"{prefix}_volume"]) else 0,
            "bid": float(row[f"{prefix}_bid"]) if f"{prefix}_bid" in row and pd.notna(row[f"{prefix}_bid"]) else 0.0,
            "ask": float(row[f"{prefix}_ask"]) if f"{prefix}_ask" in row and pd.notna(row[f"{prefix}_ask"]) else 0.0,
        }

    def calculate_pcr(self, chain: pd.DataFrame) -> Dict[str, float]:
        """Calculates Put-Call Ratio by Open Interest and Volume."""
        if chain is None or chain.empty:
            return {"pcr_oi": 0.0, "pcr_volume": 0.0}

        tot_ce_oi = chain["ce_oi"].fillna(0).sum()
        tot_pe_oi = chain["pe_oi"].fillna(0).sum()
        pcr_oi = tot_pe_oi / tot_ce_oi if tot_ce_oi > 0 else 0.0

        tot_ce_vol = chain["ce_volume"].fillna(0).sum()
        tot_pe_vol = chain["pe_volume"].fillna(0).sum()
        pcr_vol = tot_pe_vol / tot_ce_vol if tot_ce_vol > 0 else 0.0

        return {
            "pcr_oi": round(float(pcr_oi), 4),
            "pcr_volume": round(float(pcr_vol), 4)
        }

    def calculate_max_pain(self, chain: pd.DataFrame) -> float:
        """Calculates the Max Pain strike where option buyers lose the maximum total payoff."""
        if chain is None or chain.empty or "strike_price" not in chain.columns:
            return 0.0

        strikes = chain["strike_price"].values
        ce_oi = chain["ce_oi"].fillna(0).values
        pe_oi = chain["pe_oi"].fillna(0).values

        total_losses = []
        for s in strikes:
            # Loss for call writers = max(0, s - strike) * ce_oi
            call_loss = np.maximum(0, s - strikes) * ce_oi
            # Loss for put writers = max(0, strike - s) * pe_oi
            put_loss = np.maximum(0, strikes - s) * pe_oi
            total_losses.append(np.sum(call_loss + put_loss))

        min_idx = int(np.argmin(total_losses))
        return float(strikes[min_idx])
