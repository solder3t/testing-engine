"""
engine/shared_memory.py — High-Performance In-Memory Zero-Copy Bar Cache.

Caches resampled multi-day candle DataFrames across iterations to eliminate
redundant SQLite disk I/O during mass-optimization and parameter sweeps.
"""

from typing import Dict, Any, List, Optional, Tuple
import threading
import sys
import pandas as pd
import logging

logger = logging.getLogger("shared_memory")


class SharedBarCache:
    """Thread-safe zero-redundancy candle cache for multi-run backtests."""

    _instance: Optional["SharedBarCache"] = None
    _lock = threading.Lock()

    def __init__(self, max_memory_mb: float = 2048.0):
        self.max_memory_mb = max_memory_mb
        self._cache: Dict[Tuple[str, str, str], pd.DataFrame] = {}
        self._rw_lock = threading.RLock()
        self.hits: int = 0
        self.misses: int = 0

    @classmethod
    def get_global_instance(cls) -> "SharedBarCache":
        """Singleton accessor for cross-thread optimization jobs."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = SharedBarCache()
            return cls._instance

    def _make_key(self, date_str: str, symbol: str, timeframe: str) -> Tuple[str, str, str]:
        return (date_str.strip(), symbol.strip().upper(), timeframe.strip().lower())

    def get(self, date_str: str, symbol: str, timeframe: str = "1min") -> Optional[pd.DataFrame]:
        """Retrieve cached DataFrame if available."""
        key = self._make_key(date_str, symbol, timeframe)
        with self._rw_lock:
            if key in self._cache:
                self.hits += 1
                # Return direct read-only reference for zero-copy sharing
                return self._cache[key]
            self.misses += 1
            return None

    def put(self, date_str: str, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        """Store a candle DataFrame in memory, marking numeric buffers read-only."""
        if df is None or df.empty:
            return
        key = self._make_key(date_str, symbol, timeframe)
        with self._rw_lock:
            # Check current memory usage
            if self.get_memory_mb() < self.max_memory_mb:
                cached_df = df.copy()
                for col in cached_df.select_dtypes(include="number").columns:
                    try:
                        cached_df[col].values.flags.writeable = False
                    except Exception:
                        pass
                self._cache[key] = cached_df

    def preload(
        self,
        data_loader: Any,
        dates: List[str],
        symbols: List[str],
        timeframe: str = "1min"
    ) -> int:
        """
        Preload all bars for specified dates and symbols into cache in advance.
        Returns the number of candles loaded.
        """
        count = 0
        for d in dates:
            for sym in symbols:
                key = self._make_key(d, sym, timeframe)
                with self._rw_lock:
                    if key in self._cache:
                        continue
                # Load via data loader
                try:
                    # Check if index
                    if hasattr(data_loader, "get_index_ohlc"):
                        df = data_loader.get_index_ohlc(d, sym, timeframe=timeframe)
                    elif hasattr(data_loader, "load_ohlc"):
                        df = data_loader.load_ohlc(d, sym, timeframe=timeframe)
                    else:
                        df = pd.DataFrame()

                    if df is not None and not df.empty:
                        self.put(d, sym, timeframe, df)
                        count += 1
                except Exception as e:
                    logger.debug(f"Preload error for {d} {sym}: {e}")
        return count

    def get_memory_mb(self) -> float:
        """Calculates approximate memory occupied by cached DataFrames."""
        with self._rw_lock:
            total_bytes = 0
            for df in self._cache.values():
                total_bytes += df.memory_usage(deep=True).sum()
            return round(total_bytes / (1024 * 1024), 2)

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry."""
        with self._rw_lock:
            total = self.hits + self.misses
            rate = round((self.hits / total) * 100, 2) if total > 0 else 0.0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate_pct": rate,
                "cached_items": len(self._cache),
                "memory_mb": self.get_memory_mb(),
                "max_memory_mb": self.max_memory_mb
            }

    def clear(self) -> None:
        """Flushes the cache."""
        with self._rw_lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
