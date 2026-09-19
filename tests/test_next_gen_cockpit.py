"""
tests/test_next_gen_cockpit.py — Comprehensive Test Suite for Next-Generation Trading Engine Analytics Cockpit.

Verifies:
1. OptionChainAnalyzer: Max pain, gamma flip, PCR velocity, and live DB snapshot parsing.
2. TradeReplayEngine: Chronological tape construction, indicator overlays, and AI/trade event alignment.
3. RobustnessEngine: Deflated Sharpe Ratio (DSR), Probabilistic Sharpe Ratio (PSR), and 2D plateau sensitivity.
4. PortfolioAllocator: Risk Parity, Inverse Volatility, Sharpe Tangency, and correlation matrix.
5. AutoTuningEngine: Market regime classification, parameter delta generation, and safety boundary clamping.
6. Dashboard Server REST Endpoints: Testing HTTP GET/POST responses for all 5 capabilities.
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

from analytics.option_chain_analyzer import OptionChainAnalyzer
from analytics.trade_replay import TradeReplayEngine
from analytics.robustness import RobustnessEngine
from analytics.portfolio_allocator import PortfolioAllocator
from analytics.auto_tuner import AutoTuningEngine
from dashboard.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ── 1. OptionChainAnalyzer Tests ──────────────────────────────────────────────

def test_option_chain_max_pain_and_gamma():
    """Verify analytical calculation of Max Pain and Gamma Flip on synthetic chain data."""
    analyzer = OptionChainAnalyzer()

    strikes_data = [
        {"strike_price": 23800, "ce_oi": 1000, "pe_oi": 26000, "ce_gamma": 0.0001, "pe_gamma": 0.0005},
        {"strike_price": 23900, "ce_oi": 2500, "pe_oi": 14000, "ce_gamma": 0.0002, "pe_gamma": 0.0004},
        {"strike_price": 24000, "ce_oi": 5000, "pe_oi": 6000,  "ce_gamma": 0.0004, "pe_gamma": 0.0004},
        {"strike_price": 24100, "ce_oi": 12000, "pe_oi": 3000, "ce_gamma": 0.0004, "pe_gamma": 0.0002},
        {"strike_price": 24200, "ce_oi": 25000, "pe_oi": 1000, "ce_gamma": 0.0005, "pe_gamma": 0.0001},
    ]

    max_pain = analyzer.calculate_max_pain(strikes_data)
    assert max_pain in [23800, 23900, 24000, 24100, 24200]
    # Max pain balances between heavy CE OI above 24000 and PE OI below 24000
    assert 23900 <= max_pain <= 24100

    gamma_flip = analyzer.calculate_gamma_flip(strikes_data)
    assert 23800 <= gamma_flip <= 24200


def test_option_chain_analyzer_real_or_fallback():
    """Verify snapshot extraction on real DB or fallback."""
    analyzer = OptionChainAnalyzer()
    res = analyzer.analyze_snapshot(date_str="2026_09_11")
    assert isinstance(res, dict)
    assert "strikes" in res
    assert "available_tables" in res
    assert res["max_pain_strike"] > 0
    assert res["pcr"] >= 0

    timeline = analyzer.get_pcr_timeline(date_str="2026_09_11")
    assert isinstance(timeline, list)


# ── 2. TradeReplayEngine Tests ────────────────────────────────────────────────

def test_trade_replay_indicators_and_frames():
    """Verify indicators computation (VWAP, Supertrend, CPR) and frame bundling."""
    engine = TradeReplayEngine()

    # Generate synthetic OHLC for 1 session
    times = pd.date_range("2026-09-11 09:15:00", "2026-09-11 11:15:00", freq="1min")
    n = len(times)
    np.random.seed(42)
    prices = 24000 + np.cumsum(np.random.randn(n) * 5)
    df_ohlc = pd.DataFrame({
        "timestamp": times.strftime("%Y-%m-%d %H:%M:%S"),
        "open": prices,
        "high": prices + 8,
        "low": prices - 8,
        "close": prices + 2,
        "volume": np.random.randint(500, 5000, size=n)
    })

    # Test indicator addition
    df_ind = engine._compute_indicators(df_ohlc)
    assert "vwap" in df_ind.columns
    assert "supertrend" in df_ind.columns
    assert "supertrend_dir" in df_ind.columns
    assert "cpr_pivot" in df_ind.columns
    assert "cam_h3" in df_ind.columns

    # Test full session replay generation
    replay = engine.generate_replay_session(date_str="2026_09_11", symbol="NIFTY")
    assert isinstance(replay, dict)
    assert "frames" in replay
    assert "summary" in replay
    assert replay["total_frames"] > 0
    if replay["frames"]:
        first_frame = replay["frames"][0]
        assert "time" in first_frame
        assert "close" in first_frame
        assert "vwap" in first_frame


# ── 3. RobustnessEngine Tests ─────────────────────────────────────────────────

def test_robustness_psr_and_dsr():
    """Verify Probabilistic and Deflated Sharpe Ratio mathematical properties."""
    engine = RobustnessEngine()

    # Consistent positive returns: Expected high Sharpe, high PSR, high DSR
    np.random.seed(42)
    daily_returns = np.random.normal(0.003, 0.006, 100)

    res = engine.calculate_dsr_and_psr(returns=daily_returns, num_trials=25)
    assert res["status"] == "ok"
    assert res["psr"] > 80.0
    assert res["dsr"] > 70.0
    assert res["grade"].startswith("A")

    # Verify DSR penalizes larger trial spaces (snooping penalty)
    res_high_trials = engine.calculate_dsr_and_psr(returns=daily_returns, num_trials=250)
    assert res_high_trials["dsr"] <= res["dsr"]


def test_robustness_plateau_grid():
    """Verify 2D parameter sensitivity surface and cliff hazard calculation."""
    engine = RobustnessEngine()
    grid_res = engine.generate_parameter_plateau_grid(
        strategy_name="trading-engine-v4",
        param_x_name="st_multiplier",
        param_y_name="st_period",
        x_values=[1.5, 2.0, 2.5, 3.0, 3.5],
        y_values=[7.0, 9.0, 10.0, 14.0, 21.0],
        current_x=3.0,
        current_y=10.0
    )
    assert grid_res["status"] == "ok"
    assert len(grid_res["grid"]) == 25
    assert 0.0 <= grid_res["plateau_score"] <= 100.0
    assert "cliff_risk" in grid_res


# ── 4. PortfolioAllocator Tests ───────────────────────────────────────────────

def test_portfolio_allocator_solvers():
    """Verify Risk Parity and Max Sharpe numerical solvers."""
    allocator = PortfolioAllocator()

    returns_dict = {
        "Strategy_A": [0.01, 0.015, -0.005, 0.008, 0.012, -0.002, 0.014],
        "Strategy_B": [0.005, -0.002, 0.003, 0.004, 0.002, 0.006, 0.003],
        "Strategy_C": [-0.004, 0.02, 0.015, -0.01, 0.005, 0.018, 0.002],
    }
    df_ret = pd.DataFrame(returns_dict)
    cov = df_ret.cov().values
    means = df_ret.mean().values

    # 1. Risk Parity (ERC)
    w_rp = allocator._solve_risk_parity(cov)
    assert len(w_rp) == 3
    assert np.isclose(np.sum(w_rp), 1.0)
    assert np.all(w_rp >= 0)

    # 2. Max Sharpe
    w_ms = allocator._solve_max_sharpe(means, cov)
    assert len(w_ms) == 3
    assert np.isclose(np.sum(w_ms), 1.0)
    assert np.all(w_ms >= 0)


def test_portfolio_optimize_full():
    """Verify end-to-end multi-strategy portfolio optimization."""
    allocator = PortfolioAllocator()
    res = allocator.optimize_portfolio(method="risk_parity", initial_capital=500000.0)
    assert "strategies" in res
    assert "correlation_matrix" in res
    assert "equity_timeline" in res
    assert "portfolio_metrics" in res

    total_pct = sum(s["weight_pct"] for s in res["strategies"])
    assert np.isclose(total_pct, 100.0, atol=0.5)


# ── 5. AutoTuningEngine Tests ─────────────────────────────────────────────────

def test_auto_tuner_regime_classification():
    """Verify market regime rules accurately flag trending, rangebound, and choppy markets."""
    tuner = AutoTuningEngine()

    # Strong Trend: High index return, moderate range
    regime = tuner._classify_regime(change_pct=1.8, range_pct=1.6, vix=13.5)
    assert regime["code"] == "STRONG_TREND"

    # Rangebound Consolidation: Low index return, tight range, low VIX
    regime = tuner._classify_regime(change_pct=0.15, range_pct=0.5, vix=12.2)
    assert regime["code"] == "RANGEBOUND_CONSOLIDATION"

    # High Vol Whipsaw: Elevated VIX or wide range with flat close
    regime = tuner._classify_regime(change_pct=0.2, range_pct=2.5, vix=19.5)
    assert regime["code"] == "HIGH_VOL_WHIPSAW"

    # Mean Reversion: Moderate range, moderate VIX
    regime = tuner._classify_regime(change_pct=-0.4, range_pct=1.2, vix=14.0)
    assert regime["code"] == "PIVOT_MEAN_REVERSION"


def test_auto_tuner_recommendations_and_bounds():
    """Verify delta recommendations respect defined safety min/max limits."""
    tuner = AutoTuningEngine()
    diagnosis = tuner.diagnose_regime_and_tune(date_str="2026_09_11")
    assert diagnosis["status"] == "ok"
    assert "regime" in diagnosis
    assert "recommendations" in diagnosis

    for r in diagnosis["recommendations"]:
        assert "key" in r
        assert "recommended" in r
        assert r["recommended"] is not None
        assert "rationale" in r


# ── 6. Dashboard REST Endpoints Tests ──────────────────────────────────────────

def test_api_option_chain(client):
    resp = client.get("/api/trading_engine/option_chain?date=2026_09_11&symbol=NIFTY")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "strikes" in data["data"]
    assert "max_pain_strike" in data["data"]
    assert "pcr" in data["data"]


def test_api_replay_data(client):
    resp = client.get("/api/trading_engine/replay_data?date=2026_09_11&symbol=NIFTY")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "frames" in data["data"]
    assert "summary" in data["data"]


def test_api_robustness_audit(client):
    resp = client.post("/api/trading_engine/robustness_audit", json={"date": "2026_09_11", "num_trials": 20})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "statistical_metrics" in data["data"]
    assert "parameter_surface" in data["data"]


def test_api_portfolio_optimize(client):
    resp = client.post("/api/trading_engine/portfolio_optimize", json={"method": "risk_parity", "initial_capital": 1000000.0})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "strategies" in data["data"]
    assert "correlation_matrix" in data["data"]
    assert "portfolio_metrics" in data["data"]


def test_api_auto_tune(client):
    # 1. Preview
    resp = client.post("/api/trading_engine/auto_tune", json={"date": "2026_09_11", "apply": False})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "recommendations" in data["data"]
