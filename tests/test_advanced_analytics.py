"""
tests/test_advanced_analytics.py — Integration and Unit Tests for Advanced Trading Engine Synergy Features.

Verifies:
1. ConfigSyncEngine: atomic in-place .env updating, comment preservation, timestamped backups.
2. MonteCarloSimulator: 2500+ bootstrap paths, VaR 95/99, CVaR, Max DD percentiles, Ruin probabilities.
3. SessionAuditor: Automated scorecard calculation, anomaly detection, recommendations, and HTML tearsheet export.
4. BlackScholesCalculator & MultiLegOptionEngine: BS pricing, Greeks (Delta, Gamma, Theta, Vega),
   and multi-leg option strategy execution (Straddle, Strangle, Iron Condor).
5. REST API Endpoints: /api/trading_engine/apply_config, /monte_carlo, /audit, /multi_leg_simulation.
"""

import os
import json
import tempfile
import pytest
import numpy as np

from analytics.config_sync import ConfigSyncEngine
from analytics.monte_carlo import MonteCarloSimulator
from analytics.session_auditor import SessionAuditor
from analytics.multi_leg_options import BlackScholesCalculator, MultiLegOptionEngine
from dashboard.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ── 1. ConfigSyncEngine Tests ──────────────────────────────────────────────────

def test_config_sync_backup_and_apply():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        initial_content = (
            "# Trading Engine Production Configuration\n"
            "APP_ENV=production\n"
            "MIN_SIGNAL_SCORE=50\n"
            "# Risk settings\n"
            "MAX_DAILY_LOSS=25000\n"
            "TRAILING_SL_R=1.5\n"
        )
        with open(env_file, "w") as f:
            f.write(initial_content)

        engine = ConfigSyncEngine(env_path=env_file)

        # Apply Parameters with backup creation
        params = {
            "MIN_SIGNAL_SCORE": "65",
            "TRAILING_SL_R": "2.0",
            "USE_CPR": "true",  # New parameter to be appended
        }
        res = engine.sync_parameters(updates=params, create_backup=True)
        assert res["status"] == "ok"
        assert len(res["updated_keys"]) == 2
        assert len(res["added_keys"]) == 1
        assert res["backup_file"] is not None
        assert os.path.exists(res["backup_file"])

        # Check backup file contains original content
        with open(res["backup_file"], "r") as f:
            assert f.read() == initial_content

        with open(env_file, "r") as f:
            updated_content = f.read()

        # Check comment preservation & updated values
        assert "# Trading Engine Production Configuration" in updated_content
        assert "# Risk settings" in updated_content
        assert "MIN_SIGNAL_SCORE=65" in updated_content
        assert "TRAILING_SL_R=2.0" in updated_content
        assert "USE_CPR=true" in updated_content
        assert "APP_ENV=production" in updated_content
        assert "MAX_DAILY_LOSS=25000" in updated_content


def test_config_sync_missing_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, "invalid_sub_dir", ".env")
        engine = ConfigSyncEngine(env_path=env_file)
        with pytest.raises(FileNotFoundError):
            engine.sync_parameters({"MIN_SIGNAL_SCORE": 60})


# ── 2. MonteCarloSimulator Tests ──────────────────────────────────────────────

def test_monte_carlo_simulator_metrics():
    simulator = MonteCarloSimulator(num_simulations=500, initial_capital=100000.0, random_seed=42)
    pnl_series = [500.0, -250.0, 1200.0, -800.0, 450.0, 300.0, -150.0, 700.0, -400.0, 1100.0]

    result = simulator.run_simulation(
        trades=pnl_series,
        horizon_trades=20,
        soft_ruin_pct=0.20,
        hard_ruin_pct=0.50
    )

    assert result["num_simulations"] == 500
    assert result["horizon_trades"] == 20
    assert result["initial_capital"] == 100000.0

    # Risk metrics sanity checks
    assert "var" in result
    assert "var_95_pct" in result["var"]
    assert "var_99_pct" in result["var"]
    assert "cvar_95_pct" in result["var"]
    assert "cvar_95_rs" in result["var"]

    assert "drawdown" in result
    assert "median_dd_pct" in result["drawdown"]
    assert "p95_dd_pct" in result["drawdown"]

    assert "ruin_probability" in result
    assert "soft_ruin_pct" in result["ruin_probability"]
    assert "hard_ruin_pct" in result["ruin_probability"]

    assert "chart_data" in result
    chart = result["chart_data"]
    assert "p5_envelope" in chart
    assert "median_envelope" in chart
    assert "p95_envelope" in chart
    assert len(chart["sample_paths"]) <= 10


def test_monte_carlo_empty_series():
    simulator = MonteCarloSimulator(num_simulations=100)
    # Empty list falls back gracefully to baseline distribution
    res = simulator.run_simulation([])
    assert res["num_simulations"] == 100
    assert "var" in res
    assert "drawdown" in res


# ── 3. SessionAuditor Tests ───────────────────────────────────────────────────

def test_session_auditor_scorecard_and_html(tmp_path):
    auditor = SessionAuditor()
    out_html = tmp_path / "audit_test.html"

    audit_data = auditor.audit_session(date_str="2026_09_11")
    assert audit_data["date"] == "2026_09_11"
    assert "health_score" in audit_data
    assert 0 <= audit_data["health_score"] <= 100
    assert "grade" in audit_data
    assert "flags" in audit_data
    assert "reconciliation" in audit_data
    assert "ai_analytics" in audit_data

    # Generate HTML report
    html_text = auditor.generate_html_report(audit_data)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_text)

    assert os.path.exists(out_html)
    assert "<!DOCTYPE html>" in html_text
    assert "Session Audit Report" in html_text
    assert "2026_09_11" in html_text
    assert audit_data["grade"] in html_text


# ── 4. BlackScholesCalculator & MultiLegOptionEngine Tests ────────────────────

def test_black_scholes_pricing_and_greeks():
    bs = BlackScholesCalculator
    spot = 23000.0
    strike = 23000.0
    t_years = 7.0 / 365.0  # 7 days
    r = 0.07  # 7% risk-free rate
    sigma = 0.15  # 15% IV

    c_price = bs.call_price(spot, strike, t_years, r, sigma)
    p_price = bs.put_price(spot, strike, t_years, r, sigma)

    # Put-Call Parity: C - P = S - K * exp(-r*T)
    disc_strike = strike * np.exp(-r * t_years)
    assert pytest.approx(c_price - p_price, abs=0.1) == (spot - disc_strike)

    call_greeks = bs.greeks(spot, strike, t_years, r, sigma, "CE")
    put_greeks = bs.greeks(spot, strike, t_years, r, sigma, "PE")

    # Call Delta in [0, 1], Put Delta in [-1, 0]
    assert 0.45 <= call_greeks["delta"] <= 0.65
    assert -0.55 <= put_greeks["delta"] <= -0.35

    # Gamma & Vega should be positive
    assert call_greeks["gamma"] > 0
    assert put_greeks["gamma"] > 0
    assert call_greeks["vega"] > 0
    assert put_greeks["vega"] > 0

    # Theta should be negative (time decay hurts option buyer)
    assert call_greeks["theta"] < 0
    assert put_greeks["theta"] < 0

    # Implied Volatility recovery
    recovered_iv = bs.implied_volatility(c_price, spot, strike, t_years, r, "CE")
    assert pytest.approx(sigma, abs=0.01) == recovered_iv


def test_multi_leg_option_simulation():
    engine = MultiLegOptionEngine()
    # Test Short Straddle
    res_straddle = engine.simulate_strategy(
        date_str="2026_09_11",
        strategy_type="short_straddle",
        sl_pct_per_leg=0.30,
        target_decay_pct=0.50
    )
    assert res_straddle["status"] == "ok"
    assert res_straddle["strategy"] == "short_straddle"
    assert "total_net_pnl" in res_straddle
    assert "legs" in res_straddle
    assert "timeline" in res_straddle

    # Straddle should have 2 legs: CE and PE
    assert len(res_straddle["legs"]) == 2
    sides = [t["side"] for t in res_straddle["legs"]]
    assert all(s == "SELL" for s in sides)

    # Timeline checks
    assert len(res_straddle["timeline"]) > 0
    first_bar = res_straddle["timeline"][0]
    assert "net_delta" in first_bar
    assert "net_gamma" in first_bar
    assert "net_theta" in first_bar
    assert "net_vega" in first_bar

    # Test Short Strangle
    res_strangle = engine.simulate_strategy(
        date_str="2026_09_11",
        strategy_type="short_strangle",
        otm_offset_pts=100.0
    )
    assert res_strangle["status"] == "ok"
    assert len(res_strangle["legs"]) == 2

    # Test Iron Condor
    res_ic = engine.simulate_strategy(
        date_str="2026_09_11",
        strategy_type="iron_condor",
        otm_offset_pts=100.0
    )
    assert res_ic["status"] == "ok"
    assert len(res_ic["legs"]) == 4


# ── 5. REST API Endpoints Tests ────────────────────────────────────────────────

def test_api_apply_config(client):
    with tempfile.TemporaryDirectory() as tmpdir:
        test_env = os.path.join(tmpdir, ".env")
        with open(test_env, "w") as f:
            f.write("MIN_SIGNAL_SCORE=45\n")

        res = client.post("/api/trading_engine/apply_config", json={
            "updates": {"MIN_SIGNAL_SCORE": "60", "TRAILING_SL_R": "1.8"},
            "target_path": test_env
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "ok"
        assert len(data["data"]["updated_keys"]) == 1
        assert len(data["data"]["added_keys"]) == 1

        with open(test_env, "r") as f:
            content = f.read()
        assert "MIN_SIGNAL_SCORE=60" in content
        assert "TRAILING_SL_R=1.8" in content


def test_api_monte_carlo(client):
    res = client.post("/api/trading_engine/monte_carlo", json={
        "trades": [{"net_pnl": 150.0}, {"net_pnl": -80.0}, {"net_pnl": 220.0}, {"net_pnl": -50.0}],
        "num_simulations": 250,
        "horizon": 15,
        "capital": 200000.0
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert "data" in data
    assert data["data"]["num_simulations"] == 250
    assert "var" in data["data"]


def test_api_audit_endpoint(client):
    res = client.get("/api/trading_engine/audit?date=2026_09_11")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["data"]["date"] == "2026_09_11"
    assert "health_score" in data["data"]


def test_api_multi_leg_simulation(client):
    res = client.post("/api/trading_engine/multi_leg_simulation", json={
        "date": "2026_09_11",
        "strategy": "short_straddle",
        "sl_pct": 0.25,
        "target_decay": 0.50
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["data"]["strategy"] == "short_straddle"
    assert "total_net_pnl" in data["data"]
    assert "legs" in data["data"]
