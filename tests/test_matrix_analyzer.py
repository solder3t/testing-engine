"""
tests/test_matrix_analyzer.py — Verification of MatrixAnalyzer and SessionStore.
"""

import tempfile
import pytest
from analytics.matrix_analyzer import MatrixAnalyzer
from analytics.session_store import SessionStore


@pytest.fixture
def mock_results():
    return [
        {
            "run_id": 0,
            "instrument": "NIFTY",
            "symbol": "NIFTY",
            "parameters": {"fast_ema": 9, "slow_ema": 21},
            "pnl_net": 12500.0,
            "pnl_gross": 13000.0,
            "charges": 500.0,
            "win_rate_pct": 65.0,
            "sharpe_ratio": 2.1,
            "profit_factor": 1.8,
            "max_drawdown_pct": 4.5,
            "total_trades": 18,
            "per_date_breakdown": {
                "2026_09_10": {"pnl_net": 6000.0, "win_rate_pct": 70.0, "total_trades": 8},
                "2026_09_11": {"pnl_net": 6500.0, "win_rate_pct": 60.0, "total_trades": 10},
            }
        },
        {
            "run_id": 1,
            "instrument": "NIFTY",
            "symbol": "NIFTY",
            "parameters": {"fast_ema": 13, "slow_ema": 34},
            "pnl_net": -2500.0,
            "pnl_gross": -2000.0,
            "charges": 500.0,
            "win_rate_pct": 35.0,
            "sharpe_ratio": -0.5,
            "profit_factor": 0.8,
            "max_drawdown_pct": 8.0,
            "total_trades": 12,
            "per_date_breakdown": {
                "2026_09_10": {"pnl_net": -1000.0, "win_rate_pct": 40.0, "total_trades": 5},
                "2026_09_11": {"pnl_net": -1500.0, "win_rate_pct": 30.0, "total_trades": 7},
            }
        },
        {
            "run_id": 2,
            "instrument": "BANKNIFTY",
            "symbol": "BANKNIFTY",
            "parameters": {"fast_ema": 9, "slow_ema": 21},
            "pnl_net": 18200.0,
            "pnl_gross": 19000.0,
            "charges": 800.0,
            "win_rate_pct": 70.0,
            "sharpe_ratio": 2.5,
            "profit_factor": 2.2,
            "max_drawdown_pct": 5.0,
            "total_trades": 22,
            "per_date_breakdown": {
                "2026_09_10": {"pnl_net": 10000.0, "win_rate_pct": 75.0, "total_trades": 12},
                "2026_09_11": {"pnl_net": 8200.0, "win_rate_pct": 65.0, "total_trades": 10},
            }
        }
    ]


def test_matrix_analyzer_components(mock_results):
    """Verify matrix analytics aggregations and heatmaps."""
    # 1. Per-instrument stats
    inst_stats = MatrixAnalyzer.per_instrument_stats(mock_results)
    assert len(inst_stats) == 2
    assert inst_stats[0]["instrument"] in ("BANKNIFTY", "NIFTY")

    # 2. Per-date stats
    date_stats = MatrixAnalyzer.per_date_stats(mock_results)
    assert len(date_stats) == 2

    # 3. Heatmap
    heatmap = MatrixAnalyzer.instrument_date_heatmap(mock_results, "pnl_net")
    assert len(heatmap["x_labels"]) == 2  # 2 dates
    assert len(heatmap["y_labels"]) == 2  # 2 instruments
    assert len(heatmap["matrix"]) == 2

    # 4. Parameter sensitivity
    sens = MatrixAnalyzer.parameter_sensitivity(mock_results, "pnl_net")
    assert "fast_ema" in sens["parameters"]
    assert "slow_ema" in sens["parameters"]

    # 5. 2-param heatmap
    p2p = MatrixAnalyzer.two_param_heatmap(mock_results, "fast_ema", "slow_ema", "pnl_net")
    assert len(p2p["matrix"]) > 0

    # 6. Scatter 3D
    s3d = MatrixAnalyzer.scatter_3d(mock_results)
    assert len(s3d["points"]) == 3

    # 7. Monte Carlo
    trades = [
        {"pnl_net": 500.0}, {"pnl_net": -200.0}, {"pnl_net": 800.0},
        {"pnl_net": -300.0}, {"pnl_net": 1200.0}
    ]
    mc = MatrixAnalyzer.monte_carlo(trades, n_simulations=50, starting_capital=100000.0)
    assert mc["simulations"] == 50
    assert "final_equity_median" in mc["stats"]

    # 8. Full analysis bundle
    bundle = MatrixAnalyzer.full_analysis(mock_results, param1="fast_ema", param2="slow_ema")
    assert "instrument_stats" in bundle
    assert "two_param_heatmap" in bundle


def test_session_store_crud(mock_results):
    """Verify SessionStore saves, indexes, retrieves, and deletes sessions."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = SessionStore(sessions_dir=tmp_dir)
        spec = {"strategy_type": "supertrend", "max_iterations": 3}
        job_results = {
            "total_runs": 3,
            "valid_runs": 3,
            "errored_runs": 0,
            "best_run": mock_results[0],
            "ranked_results": mock_results
        }

        # 1. Save
        s_id = store.save_session(job_results, spec, name="Test Session Alpha")
        assert s_id

        # 2. List
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == s_id
        assert sessions[0]["name"] == "Test Session Alpha"

        # 3. Get
        loaded = store.get_session(s_id)
        assert loaded is not None
        assert loaded["name"] == "Test Session Alpha"
        assert loaded["summary"]["total_runs"] == 3

        # 4. Delete
        del_res = store.delete_session(s_id)
        assert del_res is True
        assert len(store.list_sessions()) == 0
        assert store.get_session(s_id) is None
