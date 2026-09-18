"""
tests/test_engine_extractor_improvements.py — Comprehensive tests for extractor & engine enhancements.
"""

import os
import zipfile
import sqlite3
import pytest
import pandas as pd

from data.archive_manager import ArchiveManager
from data.data_loader import DataLoader
from data.option_chain_loader import OptionChainLoader
from execution.simulator import ExecutionSimulator
from execution.portfolio import Portfolio
from execution.order import OrderSide, InstrumentType
from engine.multi_day_runner import MultiDayRunner
from strategies.base_strategy import BaseStrategy


# ── Extractor: Native ZIP Extraction & Path Matching ──────────────────────────

def test_zip_extraction_nested_and_flat(tmp_path):
    downloads = tmp_path / "downloads"
    cache = tmp_path / "cache"
    downloads.mkdir()
    cache.mkdir()

    # 1. Create a zip archive with nested folder: 2026_09_20/equities.db
    zip_nested = downloads / "2026_09_20.zip"
    with zipfile.ZipFile(zip_nested, "w") as zf:
        zf.writestr("2026_09_20/equities.db", b"SQLITE_NESTED_MOCK_DATA")
        zf.writestr("2026_09_20/indices.db", b"SQLITE_INDICES_MOCK_DATA")

    # 2. Create a zip archive with flat root files: equities.db
    zip_flat = downloads / "2026_09_21.zip"
    with zipfile.ZipFile(zip_flat, "w") as zf:
        zf.writestr("equities.db", b"SQLITE_FLAT_MOCK_DATA")
        zf.writestr("indices.db", b"SQLITE_INDICES_FLAT_DATA")

    mgr = ArchiveManager(downloads_dir=str(downloads), cache_dir=str(cache))

    # Test extracting nested
    res_nested = mgr.extract_archive("2026-09-20", files_to_extract=["equities.db"], target_dir=str(downloads))
    assert res_nested["success"] is True
    eq_nested = cache / "2026_09_20" / "equities.db"
    assert eq_nested.exists()
    assert eq_nested.read_bytes() == b"SQLITE_NESTED_MOCK_DATA"

    # Test extracting flat
    res_flat = mgr.extract_archive("2026_09_21", files_to_extract=["equities.db"], target_dir=str(downloads))
    assert res_flat["success"] is True
    eq_flat = cache / "2026_09_21" / "equities.db"
    assert eq_flat.exists()
    assert eq_flat.read_bytes() == b"SQLITE_FLAT_MOCK_DATA"


def test_verify_database_integrity(tmp_path):
    mgr = ArchiveManager(downloads_dir=str(tmp_path), cache_dir=str(tmp_path))

    # Valid SQLite file
    valid_db = str(tmp_path / "valid.db")
    with sqlite3.connect(valid_db) as conn:
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'hello')")
        conn.commit()

    assert mgr.verify_database_integrity(valid_db) is True

    # Corrupt / invalid SQLite file
    corrupt_db = str(tmp_path / "corrupt.db")
    with open(corrupt_db, "wb") as f:
        f.write(b"NOT_A_VALID_SQLITE_DATABASE_HEADER_GARBAGE")

    assert mgr.verify_database_integrity(corrupt_db) is False

    # Non-existent file
    assert mgr.verify_database_integrity(str(tmp_path / "non_existent.db")) is False


# ── Extractor: OptionChainLoader Caching & Bisect Search ───────────────────────

def test_option_chain_loader_caching_and_bisect(tmp_path):
    db_file = str(tmp_path / "optionchain_snapshot.db")
    with sqlite3.connect(db_file) as conn:
        conn.execute("""
            CREATE TABLE chain_NIFTY_20260904 (
                snapshot_time TEXT,
                underlying_ltp REAL,
                strike_price REAL,
                ce_ltp REAL,
                ce_bid REAL,
                ce_ask REAL,
                ce_security_id INTEGER,
                pe_ltp REAL,
                pe_bid REAL,
                pe_ask REAL,
                pe_security_id INTEGER
            )
        """)
        # Insert 3 snapshots: 09:15:00, 09:20:00, 09:25:00
        for ts, ltp in [("09:15:00", 25000.0), ("09:20:00", 25050.0), ("09:25:00", 25100.0)]:
            conn.execute("""
                INSERT INTO chain_NIFTY_20260904 VALUES (
                    ?, ?, 25000.0, 100.0, 99.0, 101.0, 1001, 80.0, 79.0, 81.0, 1002
                )
            """, (ts, ltp))
        conn.commit()

    date_dir = tmp_path / "2026_09_04"
    date_dir.mkdir()
    (date_dir / "optionchain_snapshot.db").write_bytes(open(db_file, "rb").read())

    loader = OptionChainLoader(cache_dir=str(tmp_path), source_dir=str(tmp_path))

    # 1. Test table listing caching
    tables1 = loader.list_chain_tables("2026_09_04")
    assert "chain_NIFTY_20260904" in tables1
    assert "2026_09_04" in loader._table_cache

    # 2. Test bisect search for timestamp between snapshots (09:22:00 -> should pick 09:20:00)
    chain = loader.get_nearest_chain("2026_09_04", "09:22:00", underlying="NIFTY")
    assert chain is not None
    assert chain.iloc[0]["snapshot_time"] == "09:20:00"
    assert float(chain.iloc[0]["underlying_ltp"]) == 25050.0

    # 3. Test timestamp before earliest (09:10:00 -> should fallback to earliest 09:15:00)
    chain_early = loader.get_nearest_chain("2026_09_04", "09:10:00", underlying="NIFTY")
    assert chain_early is not None
    assert chain_early.iloc[0]["snapshot_time"] == "09:15:00"

    # 4. Test connection reuse
    assert len(loader._connections) >= 1
    loader.close()
    assert len(loader._connections) == 0


# ── Extractor: DataLoader OHLC Caching & Circuit Limits ────────────────────────

def test_data_loader_caching_and_circuit_limits(tmp_path):
    date_dir = tmp_path / "2026_09_02"
    date_dir.mkdir()

    # Mock circuit_limits.json
    circuit_json = date_dir / "circuit_limits.json"
    circuit_json.write_text("""
    {
        "2885": {
            "symbol": "RELIANCE",
            "lower": 1270.0,
            "upper": 1350.0
        },
        "13": {
            "symbol": "NIFTY",
            "lower": 0.0,
            "upper": 0.0
        }
    }
    """)

    loader = DataLoader(cache_dir=str(tmp_path), source_dir=str(tmp_path))

    # Test circuit limits lookup
    limits = loader.get_circuit_limits("2026_09_02")
    assert "RELIANCE" in limits
    assert limits["RELIANCE"]["lower"] == 1270.0
    assert limits["RELIANCE"]["upper"] == 1350.0
    assert 2885 in limits

    # Test OHLC caching with mock data
    cache_key = ("equity", "2026_09_02", 2885, "RELIANCE", "1min")
    mock_df = pd.DataFrame({"timestamp": ["09:15:00"], "open": [1300.0], "high": [1305.0], "low": [1295.0], "close": [1302.0], "volume": [100], "vwap": [1300.0]})
    loader._ohlc_cache[cache_key] = mock_df

    res_df = loader.get_equity_ohlc("2026_09_02", 2885, "RELIANCE", "1min")
    assert len(res_df) == 1
    assert float(res_df.iloc[0]["close"]) == 1302.0

    # Ensure returned copy is safe against mutation
    res_df.loc[0, "close"] = 9999.0
    assert loader._ohlc_cache[cache_key].iloc[0]["close"] == 1302.0

    loader.close()
    assert len(loader._ohlc_cache) == 0


# ── Testing Engine: Volatility-Adjusted Slippage ───────────────────────────────

def test_volatility_adjusted_slippage():
    sim = ExecutionSimulator(slippage_pct=0.0005)

    # Normal calm bar (range 0.1%)
    fill_calm = sim.calculate_fill_price(
        side=OrderSide.BUY,
        reference_price=1000.0,
        bid_ask_spread=0.0,
        bar_range_pct=0.001
    )
    # Expected: 1000 + (1000 * 0.0005) = 1000.50
    assert fill_calm == 1000.50

    # High volatility breakout bar (range 2.5% = 0.025)
    fill_volatile = sim.calculate_fill_price(
        side=OrderSide.BUY,
        reference_price=1000.0,
        bid_ask_spread=0.0,
        bar_range_pct=0.025
    )
    # Slippage should be expanded beyond baseline 0.50
    assert fill_volatile > fill_calm
    assert fill_volatile <= 1003.0  # Respects maximum volatility cap


# ── Testing Engine: Circuit Limits & Order Freeze Enforcement ─────────────────

def test_portfolio_circuit_limits():
    limits = {
        "RELIANCE": {"symbol": "RELIANCE", "lower": 1270.0, "upper": 1350.0}
    }
    port = Portfolio(initial_capital=100000.0, circuit_limits=limits)

    # Normal price within bounds
    can_open, _ = port.can_open_trade("RELIANCE", side=OrderSide.BUY, price=1300.0)
    assert can_open is True

    # Price at or above Upper Circuit -> BUY should be rejected
    can_open_uc, reason_uc = port.can_open_trade("RELIANCE", side=OrderSide.BUY, price=1350.0)
    assert can_open_uc is False
    assert "Upper circuit" in reason_uc

    # Price at or below Lower Circuit -> SELL short should be rejected
    can_open_lc, reason_lc = port.can_open_trade("RELIANCE", side=OrderSide.SELL, price=1270.0)
    assert can_open_lc is False
    assert "Lower circuit" in reason_lc


def test_portfolio_freeze_limits():
    port = Portfolio(initial_capital=10000000.0, risk_pct_per_trade=0.20)

    # For NIFTY options, statutory order freeze is 1800 qty
    qty_nifty = port.calculate_position_size(
        entry_price=100.0,
        stop_loss=99.0,  # 1 pt risk on large capital would want 2,000,000 qty
        score=70,
        lot_size=25,
        instrument_type=InstrumentType.OPTION_CE,
        underlying="NIFTY"
    )
    assert qty_nifty <= 1800
    assert qty_nifty % 25 == 0

    # For BANKNIFTY options, statutory order freeze is 900 qty
    qty_bn = port.calculate_position_size(
        entry_price=100.0,
        stop_loss=99.0,
        score=70,
        lot_size=15,
        instrument_type=InstrumentType.OPTION_PE,
        underlying="BANKNIFTY"
    )
    assert qty_bn <= 900
    assert qty_bn % 15 == 0


# ── Testing Engine: MultiDayRunner Compounding State Isolation ────────────────

class DummyStrategy(BaseStrategy):
    """Simple test strategy that generates 1 trade per session."""
    def __init__(self):
        super().__init__(name="DummyStrategy")
        self.trade_opened = False

    def on_session_start(self, date_str, portfolio, context):
        self.trade_opened = False

    def on_bar(self, timestamp, quotes, portfolio, context):
        if not self.trade_opened and "RELIANCE" in quotes:
            self.trade_opened = True
            return [{
                "symbol": "RELIANCE",
                "side": OrderSide.BUY,
                "price": quotes["RELIANCE"]["close"],
                "sl": quotes["RELIANCE"]["close"] * 0.95,
                "target": quotes["RELIANCE"]["close"] * 1.05,
                "score": 75,
                "lot_size": 1
            }]
        return []

    def on_session_end(self, date_str, portfolio, context):
        # Close any open trade at last bar
        for t in list(portfolio.open_trades):
            portfolio.close_trade(t, exit_time="15:25:00", exit_price=t.entry_price * 1.02, exit_reason="TARGET")


def test_multi_day_runner_compounding_no_duplicates():
    runner = MultiDayRunner(capital=100000.0, compound_capital=True)

    # Run multi-day backtest across 2 dates
    res = runner.run(
        dates=["2026_09_02", "2026_09_08"],
        strategy=DummyStrategy(),
        symbols=["RELIANCE"]
    )

    # 1. Verify daily summaries count
    assert len(res["daily_breakdown"]) == 2

    # 2. Check trades per day: exactly 1 trade per session, total 2 trades
    d1_trades = res["daily_breakdown"][0]["trades"]
    d2_trades = res["daily_breakdown"][1]["trades"]
    assert d1_trades == 1
    assert d2_trades == 1
    assert len(res["trades"]) == 2  # CRITICAL: NO DUPLICATE TRADES FROM DAY 1!

    # 3. Verify starting equity compounding
    d1_end = res["daily_breakdown"][0]["ending_equity"]
    d2_start = res["daily_breakdown"][1]["starting_equity"]
    assert d2_start == pytest.approx(d1_end, rel=1e-3)
