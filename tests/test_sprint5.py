"""
tests/test_sprint5.py — Verification of Sprint 5 Features:
1. Strategy Parameter Grids registry
2. Institutional Performance Tearsheet generation
3. Walk-Forward API (/api/walk_forward)
4. Parameter Optimization API (/api/optimize)
5. Tearsheet endpoints (/api/tearsheet and /api/export_tearsheet)
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch

from engine.param_grids import (
    STRATEGY_REGISTRY,
    DEFAULT_PARAM_GRIDS,
    get_strategy_class,
    get_default_param_grid
)
from analytics.tearsheet import generate_html_tearsheet
from dashboard.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_strategy_registry_and_default_grids():
    """Verify all 11 strategies are registered and have valid default parameter grids."""
    expected_strats = [
        "equity", "orb", "supertrend", "camarilla", "ema-ribbon",
        "bollinger-b", "macd-accel", "vwap-reversion", "rsi-momentum",
        "options", "ai-replay"
    ]
    for s in expected_strats:
        assert s in STRATEGY_REGISTRY, f"Missing strategy {s} in STRATEGY_REGISTRY"
        assert s in DEFAULT_PARAM_GRIDS, f"Missing default grid for {s} in DEFAULT_PARAM_GRIDS"
        cls = get_strategy_class(s)
        assert cls is not None
        grid = get_default_param_grid(s)
        assert isinstance(grid, dict) and len(grid) > 0


def test_tearsheet_html_generation():
    """Verify tearsheet generator builds clean standalone HTML with correct metrics."""
    mock_run = {
        "strategy": "Opening Range Breakout (ORB)",
        "dates_tested": ["2026_02_02", "2026_02_03"],
        "initial_capital": 500000.0,
        "final_equity": 524500.0,
        "metrics": {
            "net_pnl": 24500.0,
            "return_pct": 4.90,
            "gross_pnl": 26000.0,
            "total_charges": 1500.0,
            "sharpe_ratio": 2.15,
            "sortino_ratio": 3.40,
            "calmar_ratio": 3.80,
            "max_drawdown_pct": 1.29,
            "max_drawdown_rs": 6450.0,
            "profit_factor": 2.45,
            "win_rate": 68.5,
            "expectancy": 490.0,
            "total_trades": 50,
            "wins": 34,
            "losses": 14,
            "breakeven_count": 2,
            "max_consecutive_wins": 5,
            "max_consecutive_losses": 2,
            "avg_trade_pnl": 490.0,
            "best_trade": 3200.0,
            "worst_trade": -1400.0,
            "avg_holding_bars": 18.2,
            "drawdown_curve": [
                {"timestamp": "2026-02-02 09:30", "drawdown_pct": 0.5, "drawdown_rs": 2500.0},
                {"timestamp": "2026-02-03 14:15", "drawdown_pct": 1.29, "drawdown_rs": 6450.0}
            ]
        },
        "daily_breakdown": [
            {"date": "2026_02_02", "starting_equity": 500000.0, "ending_equity": 512000.0, "pnl": 12000.0, "return_pct": 2.4, "trades": 25},
            {"date": "2026_02_03", "starting_equity": 512000.0, "ending_equity": 524500.0, "pnl": 12500.0, "return_pct": 2.44, "trades": 25}
        ],
        "equity_curve": [
            {"timestamp": "2026-02-02 09:15", "equity": 500000.0},
            {"timestamp": "2026-02-02 15:30", "equity": 512000.0},
            {"timestamp": "2026-02-03 15:30", "equity": 524500.0}
        ]
    }

    html = generate_html_tearsheet(mock_run)
    assert "<!DOCTYPE html>" in html
    assert "TESTING ENGINE" in html
    assert "Opening Range Breakout (ORB)" in html or "OPENING RANGE BREAKOUT" in html
    assert "₹24,500.00" in html
    assert "2.15" in html  # Sharpe ratio
    assert "Underwater Drawdown Profile" in html
    assert "Session-by-Session Performance Breakdown" in html
    assert "window.print()" in html


def test_api_strategy_params(client):
    """Verify /api/strategy_params returns all strategy keys and default grids."""
    res = client.get("/api/strategy_params")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "orb" in data["grids"]
    assert "equity" in data["grids"]
    assert len(data["strategies"]) >= 11


def test_api_tearsheet_endpoints(client):
    """Verify /api/tearsheet renders HTML and /api/export_tearsheet downloads file."""
    import dashboard.server as srv
    srv.latest_run_result = {
        "strategy": "ORB",
        "dates_tested": ["2026_02_02"],
        "initial_capital": 500000.0,
        "final_equity": 505000.0,
        "metrics": {"net_pnl": 5000.0, "return_pct": 1.0, "total_trades": 10},
        "daily_breakdown": [],
        "equity_curve": [],
        "drawdown_curve": []
    }

    res = client.get("/api/tearsheet")
    assert res.status_code == 200
    assert "text/html" in res.content_type
    assert "ORB" in res.get_data(as_text=True)

    export_res = client.get("/api/export_tearsheet")
    assert export_res.status_code == 200
    assert "attachment" in export_res.headers.get("Content-Disposition", "")


def test_api_walk_forward_validation(client):
    """Verify /api/walk_forward validates minimum required dates."""
    res = client.post("/api/walk_forward", json={
        "strategy": "orb",
        "dates": ["2026_02_02"],  # only 1 date, need at least 3+1=4
        "in_sample": 3,
        "out_of_sample": 1
    })
    assert res.status_code == 400
    data = res.get_json()
    assert "at least 4 dates" in data["message"]


def test_api_walk_forward_execution(client):
    """Verify /api/walk_forward returns valid WFE and windows when mocked."""
    mock_wfo_res = {
        "strategy": "OrbBreakoutStrategy",
        "total_windows": 2,
        "walk_forward_efficiency": 0.85,
        "is_robust": True,
        "windows": [
            {
                "window": 1,
                "in_sample_dates": ["2026_02_02", "2026_02_03"],
                "out_of_sample_dates": ["2026_02_04"],
                "best_params": {"opening_minutes": 15},
                "in_sample_metrics": {"sharpe_ratio": 2.1, "net_pnl": 15000.0},
                "out_of_sample_metrics": {"sharpe_ratio": 1.8, "net_pnl": 8000.0, "win_rate": 60.0, "total_trades": 5}
            }
        ],
        "overall_oos_metrics": {"net_pnl": 8000.0, "sharpe_ratio": 1.8}
    }

    with patch("dashboard.server.WalkForwardOptimizer.run_walk_forward", return_value=mock_wfo_res):
        with patch("dashboard.server.ArchiveManager.extract_archive"):
            res = client.post("/api/walk_forward", json={
                "strategy": "orb",
                "dates": ["2026_02_02", "2026_02_03", "2026_02_04"],
                "in_sample": 2,
                "out_of_sample": 1
            })
            assert res.status_code == 200
            data = res.get_json()
            assert data["status"] == "success"
            assert data["walk_forward_efficiency"] == 0.85
            assert data["is_robust"] is True
            assert len(data["windows"]) == 1


def test_api_optimize_execution(client):
    """Verify /api/optimize returns ranked combinations and best parameters."""
    mock_ranked = [
        {
            "params": {"opening_minutes": 15, "risk_reward": 2.0},
            "net_pnl": 12500.0,
            "return_pct": 2.5,
            "win_rate": 65.0,
            "profit_factor": 2.1,
            "sharpe_ratio": 2.4,
            "max_drawdown_pct": 1.1,
            "total_trades": 20
        },
        {
            "params": {"opening_minutes": 10, "risk_reward": 1.5},
            "net_pnl": 6000.0,
            "return_pct": 1.2,
            "win_rate": 55.0,
            "profit_factor": 1.5,
            "sharpe_ratio": 1.6,
            "max_drawdown_pct": 1.8,
            "total_trades": 25
        }
    ]

    with patch("dashboard.server.StrategyOptimizer.optimize", return_value=mock_ranked):
        with patch("dashboard.server.ArchiveManager.extract_archive"):
            res = client.post("/api/optimize", json={
                "strategy": "orb",
                "dates": ["2026_02_02"],
                "param_grid": {"opening_minutes": [10, 15], "risk_reward": [1.5, 2.0]},
                "rank_by": "sharpe_ratio"
            })
            assert res.status_code == 200
            data = res.get_json()
            assert data["status"] == "success"
            assert data["total_combinations"] == 2
            assert data["best_params"]["opening_minutes"] == 15
            assert len(data["ranked_results"]) == 2


def test_api_walk_forward_numpy_types_serialization(client):
    """Verify /api/walk_forward cleanly serializes numpy data types (np.bool_, np.float64, np.int64)."""
    import numpy as np
    mock_wfo_res = {
        "strategy": "OrbBreakoutStrategy",
        "total_windows": np.int64(2),
        "walk_forward_efficiency": np.float64(0.85),
        "is_robust": np.bool_(True),
        "windows": [
            {
                "window": np.int64(1),
                "in_sample_dates": ["2026_02_02", "2026_02_03"],
                "out_of_sample_dates": ["2026_02_04"],
                "best_params": {"opening_minutes": np.int64(15)},
                "in_sample_metrics": {"sharpe_ratio": np.float64(2.1), "net_pnl": np.float64(15000.0)},
                "out_of_sample_metrics": {
                    "sharpe_ratio": np.float64(1.8),
                    "net_pnl": np.float64(8000.0),
                    "win_rate": np.float64(60.0),
                    "total_trades": np.int64(5)
                }
            }
        ],
        "overall_oos_metrics": {"net_pnl": np.float64(8000.0), "sharpe_ratio": np.float64(1.8)}
    }

    with patch("dashboard.server.WalkForwardOptimizer.run_walk_forward", return_value=mock_wfo_res):
        with patch("dashboard.server.ArchiveManager.extract_archive"):
            res = client.post("/api/walk_forward", json={
                "strategy": "orb",
                "dates": ["2026_02_02", "2026_02_03", "2026_02_04"],
                "in_sample": 2,
                "out_of_sample": 1
            })
            assert res.status_code == 200
            data = res.get_json()
            assert data["status"] == "success"
            assert data["walk_forward_efficiency"] == 0.85
            assert data["is_robust"] is True
            assert isinstance(data["is_robust"], bool)
            assert isinstance(data["total_windows"], int)
            assert isinstance(data["walk_forward_efficiency"], float)

