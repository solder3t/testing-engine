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
    assert b"STOCKS ENGINE" in res.data
    assert b"TESTING ENGINE" in res.data


def test_api_archives_default(client):
    res = client.get("/api/archives")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "archives" in data
    assert len(data["archives"]) >= 5


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
