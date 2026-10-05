"""
data/data_loader.py — Universal Historical Data Loader.

Queries equities ticks, index ticks, futures, options, market depth,
and indicators across both Legacy (table-per-symbol) and Unified (consolidated tables)
SQLite schemas, backed by transparent Apache Parquet caching.
"""

from datetime import datetime
import logging
import os
from pathlib import Path
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

import config
from data.archive_manager import ArchiveManager
from data.corporate_actions import CorporateActionsManager, get_adjustment_factor
from data.instrument_master import InstrumentMaster
from data.ohlc_resampler import resample_ticks_to_ohlc
from data.parquet_cache import ParquetDataCache
from data.quality_auditor import DataQualityAuditor, QualityReport

logger = logging.getLogger("data_loader")


class DataLoader:
    """Universal high-performance data loader supporting Unified and Legacy schemas."""

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
        self._connections: Dict[str, sqlite3.Connection] = {}
        self._circuit_limits_cache: Dict[str, Dict[str, Any]] = {}
        self.parquet_cache = ParquetDataCache(self.cache_dir)
        self.db_mode = config.DATABASE_MODE  # "auto", "unified", "legacy"


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
        """Closes all open cached SQLite connections."""
        for conn in self._connections.values():
            try:
                conn.close()
            except Exception:
                pass
        self._connections.clear()

    def _get_db_path(self, date_str: str, db_name: str) -> Optional[str]:
        return self.archive_manager.get_database_path(date_str, db_name, target_dir=self.source_dir)

    def get_available_dates(self) -> List[str]:
        """Returns sorted list of available date strings (YYYY_MM_DD)."""
        archives = self.archive_manager.list_archives(target_dir=self.source_dir)
        return sorted(list({a["date"] for a in archives if a.get("date")}))

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
            logger.warning(f"Error loading circuit limits for {date_str}: {e}")
            return {}

    def _check_table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        cur = conn.cursor()
        res = cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        return res is not None


    # ── Equities Data ─────────────────────────────────────────────────────────

    def get_equity_ticks(self, date_str: str, security_id: int, symbol: str = "") -> pd.DataFrame:
        """Fetch raw tick dataframe for an equity instrument (supports Unified & Legacy)."""
        db_path = self._get_db_path(date_str, "equities.db")
        if not db_path:
            logger.warning(f"equities.db not found for {date_str}")
            return pd.DataFrame()

        conn = self._get_connection(db_path)

        # 1. Try Unified Schema if mode allows
        if self.db_mode in ("auto", "unified") and self._check_table_exists(conn, "equity_ticks"):
            query = "SELECT * FROM equity_ticks WHERE security_id = ? ORDER BY tick_time ASC"
            df = pd.read_sql_query(query, conn, params=(security_id,))
            if not df.empty:
                return df

        # 2. Try Legacy per-instrument schema: eq_{security_id}_{symbol}
        cur = conn.cursor()
        table_name = None
        if symbol:
            candidate = f"eq_{security_id}_{symbol}"
            if self._check_table_exists(conn, candidate):
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
        """Fetch resampled OHLC candles for an equity instrument with Parquet caching."""
        cache_sym = symbol or f"EQ_{security_id}"
        cached = self.parquet_cache.get(date_str, cache_sym, timeframe)
        if cached is not None:
            return cached

        # Determine corporate actions adjustment factor
        factor = get_adjustment_factor(symbol, date_str) if symbol else 1.0

        # Check if unified precomputed OHLC exists
        db_path = self._get_db_path(date_str, "equities.db")
        if db_path:
            conn = self._get_connection(db_path)
            if self.db_mode in ("auto", "unified") and self._check_table_exists(conn, "equity_ohlc"):
                tf_code = "1m" if timeframe in ("1min", "1m") else timeframe
                df_ohlc = pd.read_sql_query(
                    "SELECT candle_time, open, high, low, close, volume, vwap FROM equity_ohlc WHERE security_id=? AND timeframe=? ORDER BY candle_time ASC",
                    conn,
                    params=(security_id, tf_code)
                )
                if not df_ohlc.empty:
                    df_ohlc["candle_time"] = pd.to_datetime(df_ohlc["candle_time"])
                    df_ohlc.set_index("candle_time", inplace=True)
                    if abs(factor - 1.0) > 1e-6:
                        df_ohlc = CorporateActionsManager.adjust_dataframe(df_ohlc, factor)
                    self.parquet_cache.put(date_str, cache_sym, timeframe, df_ohlc)
                    return df_ohlc

        df_ticks = self.get_equity_ticks(date_str, security_id, symbol)
        if df_ticks.empty:
            return pd.DataFrame()

        df_res = resample_ticks_to_ohlc(df_ticks, timeframe=timeframe)
        if not df_res.empty:
            if abs(factor - 1.0) > 1e-6:
                df_res = CorporateActionsManager.adjust_dataframe(df_res, factor)
            self.parquet_cache.put(date_str, cache_sym, timeframe, df_res)
        return df_res

    # ── Index Data ────────────────────────────────────────────────────────────

    def get_index_ticks(self, date_str: str, identifier: str = "NIFTY") -> pd.DataFrame:
        """Fetch index ticks from indices.db."""
        db_path = self._get_db_path(date_str, "indices.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        cur = conn.cursor()

        query_pattern = f"%{identifier}%"
        match = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? ORDER BY length(name) ASC LIMIT 1",
            (query_pattern,)
        ).fetchone()

        if not match:
            return pd.DataFrame()

        table_name = match[0]
        df = pd.read_sql_query(f"SELECT * FROM \"{table_name}\" ORDER BY id ASC", conn)
        return df

    def get_index_ohlc(self, date_str: str, identifier: str = "NIFTY", timeframe: str = "1min") -> pd.DataFrame:
        """Fetch resampled OHLC candles for an index with Parquet caching."""
        cached = self.parquet_cache.get(date_str, identifier, timeframe)
        if cached is not None:
            return cached

        df_ticks = self.get_index_ticks(date_str, identifier)
        if df_ticks.empty:
            return pd.DataFrame()

        df_res = resample_ticks_to_ohlc(df_ticks, timeframe=timeframe)
        if not df_res.empty:
            self.parquet_cache.put(date_str, identifier, timeframe, df_res)
        return df_res

    # ── Futures Data ──────────────────────────────────────────────────────────

    def get_futures_ticks(self, date_str: str, identifier: str = "NIFTY") -> pd.DataFrame:
        """Fetch nearest futures ticks from futures_data.db."""
        db_path = self._get_db_path(date_str, "futures_data.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        cur = conn.cursor()
        query_pattern = f"%fut_%{identifier}%"
        match = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? ORDER BY length(name) ASC LIMIT 1",
            (query_pattern,)
        ).fetchone()

        if not match:
            return pd.DataFrame()

        table_name = match[0]
        df = pd.read_sql_query(f"SELECT * FROM \"{table_name}\" ORDER BY id ASC", conn)
        return df

    def get_futures_ohlc(self, date_str: str, identifier: str = "NIFTY", timeframe: str = "1min") -> pd.DataFrame:
        """Fetch resampled futures OHLC candles."""
        cached = self.parquet_cache.get(date_str, f"FUT_{identifier}", timeframe)
        if cached is not None:
            return cached

        df_ticks = self.get_futures_ticks(date_str, identifier)
        if df_ticks.empty:
            return pd.DataFrame()

        df_res = resample_ticks_to_ohlc(df_ticks, timeframe=timeframe)
        if not df_res.empty:
            self.parquet_cache.put(date_str, f"FUT_{identifier}", timeframe, df_res)
        return df_res

    # ── Level 2 Market Depth Data ─────────────────────────────────────────────

    def get_market_depth_l2(self, date_str: str, identifier: str) -> pd.DataFrame:
        """Fetch 20-level order book depth snapshots from market_depth_20.db."""
        db_path = self._get_db_path(date_str, "market_depth_20.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        cur = conn.cursor()
        query_pattern = f"%depth20_%{identifier}%"
        match = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? ORDER BY length(name) ASC LIMIT 1",
            (query_pattern,)
        ).fetchone()

        if not match:
            return pd.DataFrame()

        table_name = match[0]
        df = pd.read_sql_query(f"SELECT * FROM \"{table_name}\" ORDER BY id ASC", conn)
        return df

    # ── Universal Instrument Bar Resolver ─────────────────────────────────────

    def get_bars(
        self,
        date_str: str,
        symbol: str,
        timeframe: str = "1min",
        security_id: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Universal resolver: dynamically queries Indices, Equities, or Futures
        based on symbol type.
        """
        clean = InstrumentMaster.clean_symbol(symbol)
        
        # 1. If explicitly index or known index name
        if InstrumentMaster.is_index(clean) or clean in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "INDIA_VIX"):
            df = self.get_index_ohlc(date_str, clean, timeframe)
            if not df.empty:
                return df

        # 2. Try as Equity
        if security_id is not None:
            df = self.get_equity_ohlc(date_str, security_id, symbol, timeframe)
            if not df.empty:
                return df

        # Try resolving equity by symbol
        df_eq = self._find_equity_by_symbol_ohlc(date_str, symbol, timeframe)
        if not df_eq.empty:
            return df_eq

        # 3. Try Futures fallback
        return self.get_futures_ohlc(date_str, clean, timeframe)

    def _find_equity_by_symbol_ohlc(self, date_str: str, symbol: str, timeframe: str) -> pd.DataFrame:
        db_path = self._get_db_path(date_str, "equities.db")
        if not db_path:
            return pd.DataFrame()
        conn = self._get_connection(db_path)
        cur = conn.cursor()
        match = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? LIMIT 1",
            (f"%_{symbol.upper()}%",)
        ).fetchone()
        if match:
            parts = match[0].split("_")
            if len(parts) >= 3 and parts[1].isdigit():
                sid = int(parts[1])
                return self.get_equity_ohlc(date_str, sid, symbol, timeframe)
        return pd.DataFrame()

    # ── Precomputed Indicators & Execution ────────────────────────────────────

    def get_precomputed_indicators(self, date_str: str, security_id: Optional[int] = None) -> pd.DataFrame:
        """Fetch precomputed indicators from indicators.db."""
        db_path = self._get_db_path(date_str, "indicators.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        if not self._check_table_exists(conn, "indicators_equity"):
            return pd.DataFrame()

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
        if not self._check_table_exists(conn, "indicators_market"):
            return pd.DataFrame()

        df = pd.read_sql_query("SELECT * FROM indicators_market ORDER BY calc_time ASC", conn)
        return df

    def get_ai_snapshots(self, date_str: str) -> pd.DataFrame:
        """Fetch recorded Gemini AI snapshots from trade.db."""
        db_path = self._get_db_path(date_str, "trade.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        if not self._check_table_exists(conn, "ai_snapshots"):
            return pd.DataFrame()

        df = pd.read_sql_query("SELECT * FROM ai_snapshots ORDER BY snapshot_time ASC", conn)
        return df

    def get_recorded_trades(self, date_str: str) -> pd.DataFrame:
        """Fetch live executed trades from trade.db."""
        db_path = self._get_db_path(date_str, "trade.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        if not self._check_table_exists(conn, "trades"):
            return pd.DataFrame()

        df = pd.read_sql_query("SELECT * FROM trades ORDER BY entry_time ASC", conn)
        return df

    def get_equity_master(self, date_str: str) -> pd.DataFrame:
        """Fetch equity master definitions from master.db."""
        db_path = self._get_db_path(date_str, "master.db")
        if not db_path:
            return pd.DataFrame()

        conn = self._get_connection(db_path)
        if not self._check_table_exists(conn, "equity_master"):
            return pd.DataFrame()

        df = pd.read_sql_query("SELECT * FROM equity_master", conn)
        return df
