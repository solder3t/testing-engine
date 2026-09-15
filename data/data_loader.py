"""
data/data_loader.py — Unified Historical Data Loader.

Queries equities ticks, index ticks, precomputed indicators, option chains,
and master metadata from the extracted SQLite databases.
"""

import os
import sqlite3
import logging
from typing import Optional, List, Dict
import pandas as pd

from config import DATA_CACHE_DIR, DOWNLOADS_DIR
from data.archive_manager import ArchiveManager
from data.ohlc_resampler import resample_ticks_to_ohlc

logger = logging.getLogger("data_loader")


class DataLoader:
    """Provides structured data queries across dates and instruments."""

    def __init__(
        self,
        cache_dir: str = DATA_CACHE_DIR,
        archive_manager: Optional[ArchiveManager] = None,
        source_dir: Optional[str] = None
    ):
        self.cache_dir = os.path.expanduser(cache_dir)
        self.source_dir = os.path.expanduser(source_dir) if source_dir else None
        self.archive_manager = archive_manager or ArchiveManager(downloads_dir=self.source_dir or DOWNLOADS_DIR, cache_dir=self.cache_dir)

    def _get_db_path(self, date_str: str, db_name: str) -> Optional[str]:
        return self.archive_manager.get_database_path(date_str, db_name, target_dir=self.source_dir)

    # ── Equities Data ─────────────────────────────────────────────────────────

    def get_equity_ticks(self, date_str: str, security_id: int, symbol: str = "") -> pd.DataFrame:
        """Fetch raw tick dataframe for an equity instrument."""
        db_path = self._get_db_path(date_str, "equities.db")
        if not db_path:
            logger.warning(f"equities.db not found for {date_str}")
            return pd.DataFrame()

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()

        # Find matching table name: eq_{security_id}_{symbol}
        table_name = None
        if symbol:
            candidate = f"eq_{security_id}_{symbol}"
            exists = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (candidate,)
            ).fetchone()
            if exists:
                table_name = candidate

        if not table_name:
            match = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?", (f"eq_{security_id}_%",)
            ).fetchone()
            if match:
                table_name = match[0]

        if not table_name:
            conn.close()
            return pd.DataFrame()

        query = f"SELECT * FROM \"{table_name}\" ORDER BY id ASC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_equity_ohlc(
        self,
        date_str: str,
        security_id: int,
        symbol: str = "",
        timeframe: str = "1min"
    ) -> pd.DataFrame:
        """Fetch resampled OHLC candles for an equity instrument."""
        df_ticks = self.get_equity_ticks(date_str, security_id, symbol)
        if df_ticks.empty:
            return pd.DataFrame()
        return resample_ticks_to_ohlc(df_ticks, timeframe=timeframe)

    # ── Index Data ────────────────────────────────────────────────────────────

    def get_index_ticks(self, date_str: str, identifier: str = "NIFTY") -> pd.DataFrame:
        """
        Fetch index ticks from indices.db.
        Identifier can be e.g. 'NIFTY', 'BANKNIFTY', 'INDIA_VIX', or 13, 21, 25.
        """
        db_path = self._get_db_path(date_str, "indices.db")
        if not db_path:
            return pd.DataFrame()

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()

        table_name = None
        # Match pattern
        query_pattern = f"%{identifier}%"
        match = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? ORDER BY length(name) ASC LIMIT 1",
            (query_pattern,)
        ).fetchone()

        if match:
            table_name = match[0]

        if not table_name:
            conn.close()
            return pd.DataFrame()

        df = pd.read_sql_query(f"SELECT * FROM \"{table_name}\" ORDER BY id ASC", conn)
        conn.close()
        return df

    def get_index_ohlc(self, date_str: str, identifier: str = "NIFTY", timeframe: str = "1min") -> pd.DataFrame:
        """Fetch resampled OHLC candles for an index."""
        df_ticks = self.get_index_ticks(date_str, identifier)
        if df_ticks.empty:
            return pd.DataFrame()
        return resample_ticks_to_ohlc(df_ticks, timeframe=timeframe)

    # ── Precomputed Indicators ────────────────────────────────────────────────

    def get_precomputed_indicators(self, date_str: str, security_id: Optional[int] = None) -> pd.DataFrame:
        """Fetch precomputed indicators from indicators.db (indicators_equity)."""
        db_path = self._get_db_path(date_str, "indicators.db")
        if not db_path:
            return pd.DataFrame()

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        if security_id is not None:
            query = "SELECT * FROM indicators_equity WHERE security_id=? ORDER BY calc_time ASC"
            df = pd.read_sql_query(query, conn, params=(security_id,))
        else:
            query = "SELECT * FROM indicators_equity ORDER BY calc_time ASC"
            df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_market_indicators(self, date_str: str) -> pd.DataFrame:
        """Fetch market breadth indicators from indicators_market."""
        db_path = self._get_db_path(date_str, "indicators.db")
        if not db_path:
            return pd.DataFrame()

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        df = pd.read_sql_query("SELECT * FROM indicators_market ORDER BY calc_time ASC", conn)
        conn.close()
        return df

    # ── Real Execution Logs & AI Snapshots ────────────────────────────────────

    def get_ai_snapshots(self, date_str: str) -> pd.DataFrame:
        """Fetch recorded Gemini AI snapshots from trade.db."""
        db_path = self._get_db_path(date_str, "trade.db")
        if not db_path:
            return pd.DataFrame()

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        df = pd.read_sql_query("SELECT * FROM ai_snapshots ORDER BY snapshot_time ASC", conn)
        conn.close()
        return df

    def get_recorded_trades(self, date_str: str) -> pd.DataFrame:
        """Fetch live executed trades from trade.db."""
        db_path = self._get_db_path(date_str, "trade.db")
        if not db_path:
            return pd.DataFrame()

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY entry_time ASC", conn)
        conn.close()
        return df

    # ── Master Scrip Data ─────────────────────────────────────────────────────

    def get_equity_master(self, date_str: str) -> pd.DataFrame:
        """Fetch equity master definitions from master.db."""
        db_path = self._get_db_path(date_str, "master.db")
        if not db_path:
            return pd.DataFrame()

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        df = pd.read_sql_query("SELECT * FROM equity_master", conn)
        conn.close()
        return df
