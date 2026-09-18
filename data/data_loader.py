"""
data/data_loader.py — Unified Historical Data Loader.

Queries equities ticks, index ticks, precomputed indicators, option chains,
and master metadata from the extracted SQLite databases.
"""

import os
import json
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
        self._connections: Dict[str, sqlite3.Connection] = {}
        self._ohlc_cache: Dict[tuple, pd.DataFrame] = {}
        self._circuit_limits_cache: Dict[str, Dict] = {}

    def _get_connection(self, db_path: str) -> sqlite3.Connection:
        """Returns a cached read-only connection to the SQLite database."""
        if db_path not in self._connections:
            self._connections[db_path] = sqlite3.connect(
                f"file:{db_path}?mode=ro",
                uri=True,
                check_same_thread=False
            )
        return self._connections[db_path]

    def close(self):
        """Closes all open cached SQLite connections and clears caches."""
        for conn in self._connections.values():
            try:
                conn.close()
            except Exception:
                pass
        self._connections.clear()
        self._ohlc_cache.clear()
        self._circuit_limits_cache.clear()

    def _get_db_path(self, date_str: str, db_name: str) -> Optional[str]:
        return self.archive_manager.get_database_path(date_str, db_name, target_dir=self.source_dir)

    # ── Equities Data ─────────────────────────────────────────────────────────

    def get_equity_ticks(self, date_str: str, security_id: int, symbol: str = "") -> pd.DataFrame:
        """Fetch raw tick dataframe for an equity instrument."""
        db_path = self._get_db_path(date_str, "equities.db")
        if not db_path:
            logger.warning(f"equities.db not found for {date_str}")
            return pd.DataFrame()

        conn = self._get_connection(db_path)
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
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? LIMIT 1",
                (f"eq_{security_id}_%",)
            ).fetchone()
            if match:
                table_name = match[0]

        if not table_name:
            return pd.DataFrame()

        df = pd.read_sql_query(f"SELECT * FROM \"{table_name}\" ORDER BY id ASC", conn)
        return df

    def get_equity_ohlc(
        self,
        date_str: str,
        security_id: int,
        symbol: str = "",
        timeframe: str = "1min"
    ) -> pd.DataFrame:
        """Fetch resampled OHLC candles for an equity instrument (cached in-memory)."""
        cache_key = ("equity", date_str, security_id, symbol, timeframe)
        if cache_key in self._ohlc_cache:
            return self._ohlc_cache[cache_key].copy()

        df_ticks = self.get_equity_ticks(date_str, security_id, symbol)
        if df_ticks.empty:
            return pd.DataFrame()
        ohlc = resample_ticks_to_ohlc(df_ticks, timeframe=timeframe)
        self._ohlc_cache[cache_key] = ohlc
        return ohlc.copy()

    # ── Index Data ────────────────────────────────────────────────────────────

    def get_index_ticks(self, date_str: str, identifier: str = "NIFTY") -> pd.DataFrame:
        """
        Fetch index ticks from indices.db.
        Identifier can be e.g. 'NIFTY', 'BANKNIFTY', 'INDIA_VIX', or 13, 21, 25.
        """
        db_path = self._get_db_path(date_str, "indices.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
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
            return pd.DataFrame()

        df = pd.read_sql_query(f"SELECT * FROM \"{table_name}\" ORDER BY id ASC", conn)
        return df

    def get_index_ohlc(self, date_str: str, identifier: str = "NIFTY", timeframe: str = "1min") -> pd.DataFrame:
        """Fetch resampled OHLC candles for an index (cached in-memory)."""
        cache_key = ("index", date_str, identifier, timeframe)
        if cache_key in self._ohlc_cache:
            return self._ohlc_cache[cache_key].copy()

        df_ticks = self.get_index_ticks(date_str, identifier)
        if df_ticks.empty:
            return pd.DataFrame()
        ohlc = resample_ticks_to_ohlc(df_ticks, timeframe=timeframe)
        self._ohlc_cache[cache_key] = ohlc
        return ohlc.copy()

    # ── Circuit Limits ────────────────────────────────────────────────────────

    def get_circuit_limits(self, date_str: str) -> Dict[str, Any]:
        """
        Fetch upper/lower circuit limits from circuit_limits.json for a session date.
        Returns a dictionary indexed by both security_id and uppercase symbol.
        """
        if date_str in self._circuit_limits_cache:
            return self._circuit_limits_cache[date_str]

        json_path = self._get_db_path(date_str, "circuit_limits.json")
        if not json_path or not os.path.exists(json_path):
            return {}

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            lookup = {}
            for k, v in data.items():
                if k.startswith("_") or not isinstance(v, dict):
                    continue
                sym = str(v.get("symbol", "")).strip().upper()
                lower = float(v.get("lower", 0.0))
                upper = float(v.get("upper", 0.0))
                entry = {"security_id": k, "symbol": sym, "lower": lower, "upper": upper}
                lookup[k] = entry
                try:
                    lookup[int(k)] = entry
                except ValueError:
                    pass
                if sym:
                    lookup[sym] = entry
            self._circuit_limits_cache[date_str] = lookup
            return lookup
        except Exception as e:
            logger.warning(f"Error loading circuit_limits.json for {date_str}: {e}")
            return {}

    # ── Precomputed Indicators ────────────────────────────────────────────────

    def get_precomputed_indicators(self, date_str: str, security_id: Optional[int] = None) -> pd.DataFrame:
        """Fetch precomputed indicators from indicators.db (indicators_equity)."""
        db_path = self._get_db_path(date_str, "indicators.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        if security_id is not None:
            query = "SELECT * FROM indicators_equity WHERE security_id=? ORDER BY calc_time ASC"
            df = pd.read_sql_query(query, conn, params=(security_id,))
        else:
            query = "SELECT * FROM indicators_equity ORDER BY calc_time ASC"
            df = pd.read_sql_query(query, conn)
        return df

    def get_market_indicators(self, date_str: str) -> pd.DataFrame:
        """Fetch market breadth indicators from indicators_market."""
        db_path = self._get_db_path(date_str, "indicators.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        df = pd.read_sql_query("SELECT * FROM indicators_market ORDER BY calc_time ASC", conn)
        return df

    # ── Real Execution Logs & AI Snapshots ────────────────────────────────────

    def get_ai_snapshots(self, date_str: str) -> pd.DataFrame:
        """Fetch recorded Gemini AI snapshots from trade.db."""
        db_path = self._get_db_path(date_str, "trade.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        df = pd.read_sql_query("SELECT * FROM ai_snapshots ORDER BY snapshot_time ASC", conn)
        return df

    def get_recorded_trades(self, date_str: str) -> pd.DataFrame:
        """Fetch live executed trades from trade.db."""
        db_path = self._get_db_path(date_str, "trade.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY entry_time ASC", conn)
        return df

    # ── Master Scrip Data ─────────────────────────────────────────────────────

    def get_equity_master(self, date_str: str) -> pd.DataFrame:
        """Fetch equity master definitions from master.db."""
        db_path = self._get_db_path(date_str, "master.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        df = pd.read_sql_query("SELECT * FROM equity_master", conn)
        return df

