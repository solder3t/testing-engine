"""
tests/test_sprint4.py — Unit and integration tests for Sprint 4 infrastructure improvements:
1. SQLite connection pooling in DataLoader
2. TradeExporter safety against None metadata
3. Configuration validation bounds checking
4. Parallel MultiDayRunner execution
5. WalkForwardOptimizer rolling window generation and execution
"""

import pytest
from config import validate_config, DEFAULT_CAPITAL
from data.data_loader import DataLoader
from execution.order import Trade, OrderSide, InstrumentType
from analytics.trade_exporter import TradeExporter
from engine.multi_day_runner import MultiDayRunner
from engine.walk_forward import WalkForwardOptimizer
from strategies.nifty_options import NiftyOptionsStrategy


def test_data_loader_connection_pooling():
    """Verify DataLoader caches SQLite connections and close() shuts them down."""
    loader = DataLoader()
    assert len(loader._connections) == 0

    # Query master or index table for a known session
    df = loader.get_equity_master("2026_09_11")
    if not df.empty:
        # Connection should now be in cache
        assert len(loader._connections) >= 1
        initial_conn = list(loader._connections.values())[0]

        # Second query should reuse the exact same connection object
        df2 = loader.get_equity_master("2026_09_11")
        assert list(loader._connections.values())[0] is initial_conn

    # Close should clean up
    loader.close()
    assert len(loader._connections) == 0


def test_trade_exporter_none_metadata():
    """Verify TradeExporter.to_dataframe safely handles None metadata."""
    trade = Trade(
        trade_id="T_TEST_1",
        symbol="NIFTY",
        security_id=1,
        instrument_type=InstrumentType.OPTION_CE,
        side=OrderSide.BUY,
        qty=50,
        entry_time="2026-09-11 09:30:00",
        entry_price=100.0,
        exit_time="2026-09-11 09:45:00",
        exit_price=110.0,
        exit_reason="TARGET_HIT",
        initial_sl=90.0,
        current_sl=90.0,
        target=110.0,
        gross_pnl=500.0,
        charges=45.0,
        net_pnl=455.0,
        pnl_pct=10.0,
        holding_bars=15,
        status="CLOSED",
        metadata=None  # Explicitly None
    )

    df = TradeExporter.to_dataframe([trade])
    assert not df.empty
    assert df.iloc[0]["trade_id"] == "T_TEST_1"
    assert df.iloc[0]["charges_breakdown"] == {}
    assert df.iloc[0]["metadata"] == {}


def test_config_validation():
    """Verify config bounds checking."""
    # Current config should validate cleanly
    validate_config()


def test_parallel_multi_day_runner():
    """Verify MultiDayRunner runs with parallel=True and produces identical structure."""
    runner = MultiDayRunner(capital=250000.0, risk_pct=0.01, compound_capital=False, parallel=True)
    strat = NiftyOptionsStrategy(params={"sl_points": 12.0, "target_multiplier": 1.5, "lot_size": 25})
    res = runner.run(dates=["2026_09_11"], strategy=strat, symbols=["NIFTY"])

    assert res["initial_capital"] == 250000.0
    assert "metrics" in res
    assert "daily_breakdown" in res
    assert "equity_curve" in res


def test_walk_forward_window_generator():
    """Verify WalkForwardOptimizer splits dates into rolling (IS, OOS) windows."""
    runner = MultiDayRunner(capital=100000.0)
    wfo = WalkForwardOptimizer(runner=runner, in_sample_len=2, out_of_sample_len=1)
    dates = ["2026_09_01", "2026_09_02", "2026_09_03", "2026_09_04", "2026_09_05"]

    windows = wfo.generate_windows(dates)
    assert len(windows) == 3
    assert windows[0]["in_sample"] == ["2026_09_01", "2026_09_02"]
    assert windows[0]["out_of_sample"] == ["2026_09_03"]
    assert windows[1]["in_sample"] == ["2026_09_02", "2026_09_03"]
    assert windows[1]["out_of_sample"] == ["2026_09_04"]
    assert windows[2]["in_sample"] == ["2026_09_03", "2026_09_04"]
    assert windows[2]["out_of_sample"] == ["2026_09_05"]
