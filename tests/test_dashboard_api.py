"""
tests/test_dashboard_api.py — Integration tests for Dashboard Flask API.
"""

import os
import json
import pytest
from dashboard.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"TESTING ENGINE" in res.data
    assert b"STOCKS ENGINE" not in res.data
    assert b"Institutional Simulator" not in res.data


def test_api_archives_default(client):
    res = client.get("/api/archives")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "archives" in data
    assert len(data["archives"]) >= 1


def test_api_archives_custom_dir(client, tmp_path):
    custom_dir = tmp_path / "custom_market_data"
    custom_dir.mkdir()
    d1 = custom_dir / "2026_09_15"
    d1.mkdir()
    (d1 / "equities.db").touch()

    res = client.get(f"/api/archives?dir={custom_dir}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["archives"]) == 1
    assert data["archives"][0]["date"] == "2026_09_15"
    assert data["archives"][0]["type"] == "folder"


def test_api_results_and_run(client):
    # Test running options backtest for 1 session with custom params
    payload = {
        "dates": ["2026_09_11"],
        "strategy": "options",
        "timeframe": "1min",
        "capital": 250000.0,
        "risk_pct": 0.01,
        "sl_points": 10.0,
        "target_multiplier": 1.5,
        "lot_size": 25
    }
    res = client.post("/api/run", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "result" in data
    result = data["result"]
    assert "metrics" in result
    assert "trades" in result
    assert "drawdown_curve" in result

    # Test /api/results
    res_latest = client.get("/api/results")
    assert res_latest.status_code == 200
    latest_data = res_latest.get_json()
    assert latest_data["status"] == "success"
    assert latest_data["result"]["strategy"] == "NiftyOptionsBreakout"

    # Test /api/export_csv
    res_csv = client.get("/api/export_csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.content_type


def test_api_run_stream(client):
    payload = {
        "dates": ["2026_09_11"],
        "strategy": "options",
        "timeframe": "1min",
        "capital": 250000.0,
        "risk_pct": 0.01
    }
    res = client.post("/api/run/stream", json=payload)
    assert res.status_code == 200
    assert "text/event-stream" in res.content_type
    raw_data = res.data.decode("utf-8")
    assert "data: " in raw_data
    assert '"type": "complete"' in raw_data


def test_api_compare(client):
    payload = {
        "dates": ["2026_09_11"],
        "strategies": ["options", "orb"],
        "capital": 250000.0
    }
    res = client.post("/api/compare", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "comparison" in data
    assert len(data["comparison"]) == 2
    assert data["comparison"][0]["strategy_key"] == "options"
    assert "metrics" in data["comparison"][0]


def test_api_browse_filesystem(client, tmp_path):
    sub = tmp_path / "market_session_2026_09_02"
    sub.mkdir()
    (sub / "equities.db").touch()
    rar_file = tmp_path / "2026_09_02.rar"
    rar_file.touch()

    res = client.get(f"/api/browse?path={tmp_path}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "items" in data
    names = [it["name"] for it in data["items"]]
    assert "market_session_2026_09_02" in names
    assert "2026_09_02.rar" in names


def test_api_archives_single_file(client, tmp_path):
    rar_file = tmp_path / "2026_09_12.rar"
    rar_file.touch()

    res = client.get(f"/api/archives?dir={rar_file}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["archives"]) == 1
    assert data["archives"][0]["date"] == "2026_09_12"
    assert data["archives"][0]["name"] == "2026_09_12.rar"


def test_tabs_and_inspector_rendered(client):
    res = client.get("/")
    assert res.status_code == 200
    content = res.data.decode("utf-8")
    assert "btnTabConsole" in content
    assert "btnTabAnalytics" in content
    assert "btnTabInspector" in content
    assert "btnTabExplorer" in content
    assert "tabConsole" in content
    assert "tabAnalytics" in content
    assert "tabInspector" in content
    assert "tabExplorer" in content
    assert "tradeInspectorCard" in content
    assert "explorerSessionsGrid" in content

    # Branding verification: ONLY "⚡ TESTING ENGINE"
    assert "⚡ TESTING ENGINE" in content
    assert "Institutional Simulator" not in content
    assert "INSTITUTIONAL SIMULATOR" not in content

    # 6 Analytics charts verification
    assert "equityChart" in content
    assert "dailyChart" in content
    assert "drawdownChart" in content
    assert "hourlyChart" in content
    assert "outcomeChart" in content
    assert "pnlDistChart" in content

    # Strategy options verification
    assert 'value="orb"' in content
    assert 'value="supertrend"' in content
    assert 'value="camarilla"' in content
    assert 'value="ema-ribbon"' in content
    assert 'value="bollinger-b"' in content
    assert 'value="macd-accel"' in content

    # New KPI cards verification (Sprint 1 additions)
    assert "kpiCalmar" in content
    assert "kpiMaxWinStreak" in content
    assert "kpiMaxLossStreak" in content
    assert "kpiBreakeven" in content
    assert "0W / 0L / 0BE" in content

    # Mass Iteration Lab tab verification
    assert "btnTabMassIteration" in content
    assert "tabMassIteration" in content
    assert "massStrategySelect" in content
    assert "massSamplingMode" in content


def test_api_strategies_catalog(client):
    """Verify /api/strategies/catalog returns all 56 strategies with metadata."""
    res = client.get("/api/strategies/catalog")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] == 56
    assert len(data["strategies"]) == 56

    strat_keys = set(s["key"] for s in data["strategies"])
    assert "supertrend_multi_tf" in strat_keys
    assert "options_flow_momentum" in strat_keys
    assert "connors_rsi2_pullback" in strat_keys
    assert "futures_vsa_climactic" in strat_keys


def test_api_mass_optimize_and_sessions(client):
    """Verify submitting a mass optimization job, polling status, and saving/retrieving sessions."""
    # 1. Submit job
    payload = {
        "strategy_type": "supertrend",
        "sampling_mode": "GRID",
        "max_iterations": 2,
        "parameter_grid": {"atr_period": [7, 14]},
        "dates": ["2026_09_11"]
    }
    submit_res = client.post("/api/mass_optimize", json=payload)
    assert submit_res.status_code == 200
    sub_data = submit_res.get_json()
    assert sub_data["status"] == "submitted"
    job_id = sub_data["job_id"]
    assert job_id

    # 2. Check status
    stat_res = client.get(f"/api/mass_optimize/status/{job_id}")
    assert stat_res.status_code == 200
    assert stat_res.get_json()["status"] == "success"

    # 3. Test Sessions API
    sess_list = client.get("/api/sessions")
    assert sess_list.status_code == 200
    assert sess_list.get_json()["status"] == "success"

    # Save mock session
    save_payload = {
        "name": "Integration Test Session",
        "spec": payload,
        "results": {
            "total_runs": 2,
            "valid_runs": 2,
            "errored_runs": 0,
            "strategy_type": "supertrend",
            "best_run": {"pnl_net": 5000.0, "sharpe_ratio": 2.1, "win_rate_pct": 60.0},
            "ranked_results": [
                {
                    "run_id": 0,
                    "instrument": "NIFTY",
                    "parameters": {"atr_period": 7},
                    "pnl_net": 5000.0,
                    "sharpe_ratio": 2.1,
                    "win_rate_pct": 60.0,
                    "per_date_breakdown": {
                        "2026_09_11": {"pnl_net": 5000.0, "win_rate_pct": 60.0}
                    }
                }
            ]
        }
    }
    save_res = client.post("/api/sessions/save", json=save_payload)
    assert save_res.status_code == 200
    session_id = save_res.get_json()["session_id"]
    assert session_id

    # Retrieve session
    get_res = client.get(f"/api/sessions/{session_id}")
    assert get_res.status_code == 200
    assert get_res.get_json()["session"]["name"] == "Integration Test Session"

    # Run analysis
    analysis_res = client.get(f"/api/analysis/{session_id}")
    assert analysis_res.status_code == 200
    analysis = analysis_res.get_json()["analysis"]
    assert "instrument_stats" in analysis
    assert "date_stats" in analysis

