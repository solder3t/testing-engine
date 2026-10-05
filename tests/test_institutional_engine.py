"""
tests/test_institutional_engine.py — Comprehensive Unit & Integration Tests
for Institutional Multi-Instrument Upgrades.
"""

from datetime import date
import numpy as np
import pandas as pd
import pytest

from analytics.results_db import ResultsDB
from analytics.validation import ValidationSuite
from analytics.validation_report import CandidateValidator
from data.expiry_calendar import ExpiryCalendar
from data.instrument_master import InstrumentMaster
from data.quality_auditor import DataQualityAuditor
from engine.param_spec import ParamSpec, ParamGrid
from engine.rollover_manager import RolloverManager
from execution.order import InstrumentType, OrderSide, Trade
from execution.portfolio import Portfolio
from execution.risk_manager import RiskManager
from execution.simulator import ExecutionSimulator


# ── 1. InstrumentMaster Tests ─────────────────────────────────────────────────

def test_instrument_master_lot_sizes():
    # NIFTY point-in-time lot size history
    assert InstrumentMaster.get_lot_size("NIFTY", "2024-01-15") == 50
    assert InstrumentMaster.get_lot_size("NIFTY", "2024-05-10") == 25
    assert InstrumentMaster.get_lot_size("NIFTY", "2024-11-25") == 75

    # BankNifty point-in-time
    assert InstrumentMaster.get_lot_size("BANKNIFTY", "2024-01-15") == 15
    assert InstrumentMaster.get_lot_size("BANKNIFTY", "2024-11-25") == 30

    # FinNifty and MidcpNifty
    assert InstrumentMaster.get_lot_size("FINNIFTY", "2024-11-25") == 65
    assert InstrumentMaster.get_lot_size("MIDCPNIFTY", "2024-11-25") == 120

    # Cash Equities should be 1
    assert InstrumentMaster.get_lot_size("RELIANCE", is_derivative=False) == 1
    # Equity derivatives
    assert InstrumentMaster.get_lot_size("RELIANCE", is_derivative=True) == 250


def test_instrument_master_strikes_and_freeze():
    assert InstrumentMaster.get_strike_interval("NIFTY") == 50.0
    assert InstrumentMaster.get_strike_interval("BANKNIFTY") == 100.0
    assert InstrumentMaster.get_strike_interval("MIDCPNIFTY") == 25.0

    assert InstrumentMaster.get_freeze_qty("NIFTY") == 1800
    assert InstrumentMaster.get_freeze_qty("BANKNIFTY") == 900
    assert InstrumentMaster.get_freeze_qty("MIDCPNIFTY") == 4200

    # Strike rounding
    assert InstrumentMaster.round_to_strike(24218.4, "NIFTY") == 24200.0
    assert InstrumentMaster.round_to_strike(51280.0, "BANKNIFTY") == 51300.0


# ── 2. ExpiryCalendar Tests ───────────────────────────────────────────────────

def test_expiry_calendar():
    # Test holiday detection
    assert ExpiryCalendar.is_holiday("2024-01-26") is True   # Republic Day
    assert ExpiryCalendar.is_holiday("2024-08-15") is True   # Independence Day
    assert ExpiryCalendar.is_holiday("2024-01-27") is True   # Saturday

    # Nearest weekly expiry for NIFTY (Thursday)
    # 2024-08-12 is Monday -> nearest Thursday is 2024-08-15 (Holiday!) -> rolls to 2024-08-14 (Wednesday)
    exp = ExpiryCalendar.get_nearest_expiry("NIFTY", "2024-08-12")
    assert exp == date(2024, 8, 14)


# ── 3. ParamSpec and ParamGrid Tests ──────────────────────────────────────────

def test_param_spec_and_grid():
    spec_int = ParamSpec("window", "int", default=10, min_val=5, max_val=15, step=5)
    spec_float = ParamSpec("mult", "float", default=1.5, min_val=1.0, max_val=2.0, step=0.5)
    spec_cat = ParamSpec("mode", "categorical", default="FAST", choices=["FAST", "SLOW"])

    assert spec_int.generate_values() == [5, 10, 15]
    assert len(spec_float.generate_values()) == 3
    assert spec_cat.generate_values() == ["FAST", "SLOW"]

    grid = ParamGrid([spec_int, spec_float, spec_cat])
    assert grid.total_combinations() == 3 * 3 * 2
    combos = grid.generate_all()
    assert len(combos) == 18
    assert all("window" in c and "mult" in c and "mode" in c for c in combos)


# ── 4. ResultsDB Persistence Tests ────────────────────────────────────────────

def test_results_db_persistence(tmp_path):
    db_file = tmp_path / "test_results.db"
    rdb = ResultsDB(str(db_file))

    run_id = rdb.save_run(
        strategy_name="UniversalORB",
        instrument="NIFTY",
        timeframe="1min",
        start_date="2026-09-01",
        end_date="2026-09-05",
        initial_capital=500000.0,
        final_equity=525000.0,
        metrics={"net_pnl": 25000.0, "win_rate": 66.7, "sharpe_ratio": 2.1},
        params={"orb_minutes": 15}
    )

    loaded = rdb.get_run(run_id)
    assert loaded is not None
    assert loaded["strategy_name"] == "UniversalORB"
    assert loaded["net_pnl"] == 25000.0
    assert loaded["params"]["orb_minutes"] == 15

    # Test saving validation metrics
    rdb.save_validation(
        run_id=run_id,
        pbo_score=0.12,
        deflated_sharpe=2.45,
        wfe_score=0.78,
        mc_var_95=12000.0,
        mc_max_dd_95=6.5,
        verdict="PASS"
    )

    runs = rdb.list_runs(strategy="UniversalORB")
    assert len(runs) == 1


# ── 5. DataQualityAuditor Tests ───────────────────────────────────────────────

def test_data_quality_auditor():
    # Create healthy dummy OHLC data
    dates = pd.date_range("2026-09-01 09:15:00", periods=375, freq="1min")
    df_healthy = pd.DataFrame({
        "open": np.linspace(24000, 24100, 375),
        "high": np.linspace(24010, 24110, 375),
        "low": np.linspace(23990, 24090, 375),
        "close": np.linspace(24005, 24105, 375),
        "volume": np.ones(375) * 500
    }, index=dates)

    report = DataQualityAuditor.audit(df_healthy, "NIFTY", "2026_09_01")
    assert report.status == "EXCELLENT"
    assert report.health_score >= 95.0

    # Corrupt data with negative price
    df_corrupt = df_healthy.copy()
    df_corrupt.loc[df_corrupt.index[10], "close"] = -100.0
    report_bad = DataQualityAuditor.audit(df_corrupt, "NIFTY", "2026_09_01")
    assert report_bad.anomalous_bars >= 1


# ── 6. ValidationSuite (PBO, Deflated Sharpe, Monte Carlo) ─────────────────────

def test_validation_suite():
    # 1. PBO: generate random returns for 200 bars x 10 trials
    rng = np.random.default_rng(42)
    matrix = rng.normal(0.0005, 0.01, size=(200, 8))
    pbo = ValidationSuite.calculate_pbo(matrix, n_splits=6)
    assert 0.0 <= pbo <= 1.0

    # 2. Deflated Sharpe Ratio
    returns = rng.normal(0.001, 0.01, size=150)
    dsr = ValidationSuite.calculate_deflated_sharpe(sharpe_est=1.8, n_trials=50, returns=returns)
    assert "deflated_sharpe_stat" in dsr
    assert "p_value" in dsr
    assert "verdict" in dsr

    # 3. Monte Carlo
    trades = [{"net_pnl": 1500.0}, {"net_pnl": -500.0}, {"net_pnl": 2000.0}, {"net_pnl": -800.0}] * 10
    mc = ValidationSuite.run_monte_carlo(trades, initial_capital=100000.0, n_simulations=100)
    assert mc["simulations_run"] == 100
    assert mc["prob_profitable"] > 0.0


# ── 7. RiskManager & Kill Switches ───────────────────────────────────────────

def test_risk_manager_kill_switch():
    rm = RiskManager(capital=100000.0, daily_max_loss_pct=0.03, daily_max_loss_inr=5000.0)

    # Mild loss should not trigger
    assert rm.evaluate_intraday_pnl(-1000.0, "09:30") is False
    assert rm.check_entry_allowed()[0] is True

    # Severe loss breaching 3% (₹3,000) should trigger Kill Switch
    assert rm.evaluate_intraday_pnl(-3500.0, "10:15") is True
    assert rm.daily_kill_switch_triggered is True
    allowed, reason = rm.check_entry_allowed()
    assert allowed is False
    assert "DAILY_KILL_SWITCH_ACTIVE" in reason


# ── 8. ExecutionSimulator Depth-Walk & Expiry STT ─────────────────────────────

def test_simulator_depth_walk_and_expiry():
    sim = ExecutionSimulator()
    depth_mock = {
        "ask_p1": 100.0, "ask_q1": 50,
        "ask_p2": 101.0, "ask_q2": 100,
        "ask_p3": 102.0, "ask_q3": 200,
    }

    # BUY 100 units walks ask_p1 (50 @ 100) + ask_p2 (50 @ 101) = avg 100.5
    fill = sim.calculate_depth_walk_fill(OrderSide.BUY, 100, depth_mock, fallback_price=100.0)
    assert fill == 100.5

    # Expiry STT calculation: CE strike 24000, settlement 24100 -> intrinsic = 100 * 50 qty = 5000
    charges = sim.calculate_expiry_exercise_charges(
        settlement_price=24100.0,
        strike_price=24000.0,
        qty=50,
        instrument_type=InstrumentType.OPTION_CE
    )
    # STT = 5000 * 0.00125 = ₹6.25
    assert charges["stt"] == 6.25
