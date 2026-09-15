"""
data/option_chain_loader.py — Historical Option Chain & Greeks Replayer.

Extracts option chains, ATM strike selection, Greeks, PCR, and Max Pain
from optionchain_snapshot.db.
"""

import os
import sqlite3
import logging
from typing import Optional, List, Dict
import pandas as pd
import numpy as np

from config import DATA_CACHE_DIR, DOWNLOADS_DIR
from data.archive_manager import ArchiveManager

logger = logging.getLogger("option_chain_loader")


class OptionChainLoader:
    """Historical option chain loader and analytics calculator."""

    def __init__(
        self,
        cache_dir: str = DATA_CACHE_DIR,
        archive_manager: Optional[ArchiveManager] = None,
        source_dir: Optional[str] = None
    ):
        self.cache_dir = os.path.expanduser(cache_dir)
        self.source_dir = os.path.expanduser(source_dir) if source_dir else None
        self.archive_manager = archive_manager or ArchiveManager(downloads_dir=self.source_dir or DOWNLOADS_DIR, cache_dir=self.cache_dir)

    def _get_db_path(self, date_str: str) -> Optional[str]:
        return self.archive_manager.get_database_path(date_str, "optionchain_snapshot.db", target_dir=self.source_dir)

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

    def get_nearest_chain(
        self,
        date_str: str,
        timestamp: str,
        underlying: str = "NIFTY"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch the nearest option chain snapshot at or before the given timestamp.
        """
        tables = self.list_chain_tables(date_str)
        matching = [t for t in tables if t.upper().startswith(f"CHAIN_{underlying.upper()}_")]
        if not matching:
            matching = [t for t in tables if underlying.upper() in t.upper()]
        if not matching:
            return None

        # Pick near-month expiry table
        target_table = matching[0]
        db_path = self._get_db_path(date_str)
        if not db_path:
            return None

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()

        # Find nearest snapshot_time <= timestamp
        nearest_time_row = cur.execute(
            f"SELECT snapshot_time FROM \"{target_table}\" WHERE snapshot_time <= ? ORDER BY snapshot_time DESC LIMIT 1",
            (timestamp,)
        ).fetchone()

        if not nearest_time_row:
            # Fallback to earliest snapshot
            nearest_time_row = cur.execute(
                f"SELECT snapshot_time FROM \"{target_table}\" ORDER BY snapshot_time ASC LIMIT 1"
            ).fetchone()

        if not nearest_time_row:
            conn.close()
            return None

        snap_time = nearest_time_row[0]
        df = pd.read_sql_query(
            f"SELECT * FROM \"{target_table}\" WHERE snapshot_time = ? ORDER BY strike_price ASC",
            conn,
            params=(snap_time,)
        )
        conn.close()
        return df

    @staticmethod
    def get_atm_strike(underlying_ltp: float, step: float = 50.0) -> float:
        """Find the ATM strike for an underlying price with a given strike interval."""
        if underlying_ltp <= 0 or step <= 0:
            return 0.0
        return round(underlying_ltp / step) * step

    def get_atm_contract(
        self,
        date_str: str,
        timestamp: str,
        option_type: str = "CE",
        underlying: str = "NIFTY",
        step: float = 50.0
    ) -> Optional[Dict]:
        """
        Retrieves the exact ATM CE or PE contract snapshot for a given timestamp.
        """
        chain = self.get_nearest_chain(date_str, timestamp, underlying)
        if chain is None or chain.empty:
            return None

        underlying_ltp = float(chain["underlying_ltp"].iloc[0])
        atm_strike = self.get_atm_strike(underlying_ltp, step=step)

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
            "option_type": option_type.upper(),
            "security_id": int(row[f"{prefix}_security_id"]) if pd.notna(row.get(f"{prefix}_security_id")) else 0,
            "ltp": float(row[f"{prefix}_ltp"]) if pd.notna(row.get(f"{prefix}_ltp")) else 0.0,
            "iv": float(row[f"{prefix}_iv"]) if pd.notna(row.get(f"{prefix}_iv")) else 0.0,
            "delta": float(row[f"{prefix}_delta"]) if pd.notna(row.get(f"{prefix}_delta")) else 0.0,
            "gamma": float(row[f"{prefix}_gamma"]) if pd.notna(row.get(f"{prefix}_gamma")) else 0.0,
            "theta": float(row[f"{prefix}_theta"]) if pd.notna(row.get(f"{prefix}_theta")) else 0.0,
            "vega": float(row[f"{prefix}_vega"]) if pd.notna(row.get(f"{prefix}_vega")) else 0.0,
            "bid": float(row[f"{prefix}_bid"]) if pd.notna(row.get(f"{prefix}_bid")) else 0.0,
            "ask": float(row[f"{prefix}_ask"]) if pd.notna(row.get(f"{prefix}_ask")) else 0.0,
            "oi": int(row[f"{prefix}_oi"]) if pd.notna(row.get(f"{prefix}_oi")) else 0,
            "volume": int(row[f"{prefix}_volume"]) if pd.notna(row.get(f"{prefix}_volume")) else 0,
        }

    @staticmethod
    def calculate_pcr(chain_df: pd.DataFrame) -> float:
        """Calculates Put-Call Ratio (PE OI / CE OI)."""
        if chain_df.empty or "pe_oi" not in chain_df.columns or "ce_oi" not in chain_df.columns:
            return 1.0
        pe_oi = chain_df["pe_oi"].dropna().sum()
        ce_oi = chain_df["ce_oi"].dropna().sum()
        return round(float(pe_oi / ce_oi), 2) if ce_oi > 0 else 1.0

    @staticmethod
    def calculate_max_pain(chain_df: pd.DataFrame) -> float:
        """Calculates Max Pain strike where option sellers incur minimal total payout."""
        if chain_df.empty:
            return 0.0
        strikes = chain_df["strike_price"].values
        total_pains = []

        for s in strikes:
            # CE loss if spot finishes at s
            ce_payout = np.maximum(0, s - strikes) * chain_df["ce_oi"].fillna(0).values
            # PE loss if spot finishes at s
            pe_payout = np.maximum(0, strikes - s) * chain_df["pe_oi"].fillna(0).values
            total_pains.append(ce_payout.sum() + pe_payout.sum())

        min_idx = np.argmin(total_pains)
        return float(strikes[min_idx])
