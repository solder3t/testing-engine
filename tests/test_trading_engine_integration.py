"""
tests/test_trading_engine_integration.py — Integration and Unit Tests for Trading Engine Synergy.

Verifies:
1. Strategy v4 multi-factor logic, scoring, and option routing.
2. Live vs simulated execution reconciliation (drift, slippage, latency, efficiency score).
3. Gemini AI decision intelligence, calibration, counterfactual matrix, and optimal threshold.
4. Strategy factor alpha attribution and .env/JSON configuration exporter.
5. REST API endpoints in dashboard/server.py.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from strategies.trading_engine_v4 import TradingEngineV4Strategy, compute_signal_score
from execution.order import OrderSide, InstrumentType, Trade
from execution.portfolio import Portfolio
from analytics.reconciliation import ReconciliationEngine, parse_datetime
from analytics.ai_decision_analyzer import AIDecisionAnalyzer, parse_snapshot_time
from analytics.factor_attribution import FactorAttributionEngine
from dashboard.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ── 1. Strategy v4 Unit & Signal Tests ────────────────────────────────────────

def test_strategy_v4_init_and_scoring():
    strat = TradingEngineV4Strategy()
    assert strat.name == "TradingEngine_StrategyV4"
    assert strat.params["min_signal_score"] == 50
    assert strat.params["vix_halt_threshold"] == 25.0
    assert strat.params["use_cpr"] is True
    assert strat.params["use_htf_15m"] is True
    assert strat.params["trade_options"] is True

    # Test Scorer
    bull_sig = {
        "signal": "BUY",
        "rsi": 62,
        "macd_hist": 0.15,
        "vol_ratio": 2.5,
        "entry_price": 23400,
        "vwap": 23380,
        "supertrend_dir": 1,
        "supertrend_flip": True,
        "htf_valid": True,
        "htf_bullish": True,
        "rr_ratio": 2.0,
        "adx": 28,
        "adx_plus_di": 25,
        "adx_minus_di": 12,
        "htf_15m_bullish": True,
    }
    score = compute_signal_score(bull_sig)
    assert score >= 60, f"Expected high score for strong bullish signal, got {score}"

    hold_sig = {"signal": "HOLD"}
    assert compute_signal_score(hold_sig) == 0


def test_strategy_v4_pivots_and_trailing():
    strat = TradingEngineV4Strategy(params={"trailing_sl_r": 1.0})
    port = Portfolio(initial_capital=100000.0)

    # Mock historical data for NIFTY
    df_nifty = pd.DataFrame({
        "timestamp": ["2026-09-11 09:15:00", "2026-09-11 09:16:00"],
        "open": [23200.0, 23210.0],
        "high": [23300.0, 23310.0],
        "low": [23150.0, 23200.0],
        "close": [23280.0, 23290.0],
        "volume": [1000, 1200]
    })
    strat.on_session_start("2026_09_11", port, {"ohlc_data": {"NIFTY": df_nifty}})
    assert "NIFTY" in strat.pivots
    pivots = strat.pivots["NIFTY"]
    assert "P" in pivots
    assert "TC" in pivots
    assert "BC" in pivots

    # Test break-even trailing SL on open trade
    trade = Trade(
        symbol="NIFTY",
        security_id=13,
        side=OrderSide.BUY,
        qty=1,
        entry_time="2026-09-11 09:30:00",
        entry_price=23300.0,
        initial_sl=23200.0,
        current_sl=23200.0,
        target=23500.0,
    )
    port.open_trades.append(trade)

    # When price advances by 1R (100 pts) to 23410, trailing SL should move to entry
    quotes = {"NIFTY": {"open": 23410.0, "high": 23415.0, "low": 23405.0, "close": 23410.0}}
    strat.on_bar("2026-09-11 09:35:00", quotes, port, {"current_vix": 14.0})
    assert trade.current_sl == 23300.0, f"Expected trailing SL to move to break-even (23300.0), got {trade.current_sl}"


# ── 2. Reconciliation Engine Tests ────────────────────────────────────────────

def test_reconciliation_normalization_and_pairing():
    rec = ReconciliationEngine()

    live_trades = [
        {
            "trade_id": "live-1",
            "symbol": "NIFTY50-SEP2026-23400-CE",
            "side": "BUY",
            "entry_time": "2026-09-11 14:02:05",
            "entry_price": 108.1,
            "exit_time": "2026-09-11 14:02:25",
            "exit_price": 134.2,
            "net_pnl": 1626.50,
            "qty": 65,
            "exit_reason": "TARGET_HIT",
        },
        {
            "trade_id": "live-2",
            "symbol": "NIFTY50-SEP2026-23250-CE",
            "side": "BUY",
            "entry_time": "2026-09-11 09:30:18",
            "entry_price": 110.8,
            "exit_time": "2026-09-11 09:32:11",
            "exit_price": 112.9,
            "net_pnl": 274.50,
            "qty": 65,
            "exit_reason": "MANUAL_EXIT",
        }
    ]

    sim_trades = [
        {
            "trade_id": "sim-1",
            "symbol": "NIFTY50-SEP2026-23400-CE",
            "side": "BUY",
            "entry_time": "2026-09-11 14:01:59",
            "entry_price": 108.1,
            "exit_time": "2026-09-11 14:03:00",
            "exit_price": 135.0,
            "net_pnl": 1748.50,
            "qty": 65,
            "exit_reason": "TARGET_HIT",
        },
        {
            "trade_id": "sim-2",
            "symbol": "NIFTY50-SEP2026-23300-PE",
            "side": "BUY",
            "entry_time": "2026-09-11 10:28:00",
            "entry_price": 107.9,
            "exit_time": "2026-09-11 11:14:00",
            "exit_price": 86.28,
            "net_pnl": -1405.30,
            "qty": 65,
            "exit_reason": "SL_HIT",
        }
    ]

    res = rec.reconcile(live_trades, sim_trades, max_entry_diff_seconds=300)
    summary = res["summary"]

    assert summary["total_live_trades"] == 2
    assert summary["total_sim_trades"] == 2
    assert summary["matched_count"] == 1
    assert summary["unprompted_live_count"] == 1
    assert summary["missed_signals_count"] == 1

    matched = res["matched_pairs"][0]
    assert matched["live_trade"]["trade_id"] == "live-1"
    assert matched["sim_trade"]["trade_id"] == "sim-1"
    assert matched["entry_slippage_rs"] == 0.0
    assert matched["entry_slippage_pct"] == 0.0
    assert matched["latency_seconds"] == 6.0
    assert matched["execution_efficiency"] >= 95.0


def test_reconciliation_live_session():
    rec = ReconciliationEngine()
    res = rec.run_reconciliation("2026_09_11")
    assert res["summary"]["total_live_trades"] == 4
    assert "matched_pairs" in res
    assert "missed_signals" in res
    assert "unprompted_live" in res


# ── 3. AI Decision Analyzer Tests ─────────────────────────────────────────────

def test_ai_decision_analyzer_session():
    analyzer = AIDecisionAnalyzer()
    res = analyzer.analyze_session("2026_09_11", confidence_threshold=0.70)
    assert res["total_snapshots"] == 726
    assert res["action_breakdown"]["WAIT"] == 333
    assert res["action_breakdown"]["ENTER"] == 3

    # Counterfactual Matrix
    mat = res["counterfactual_matrix"]
    assert mat["threshold"] == 0.70
    assert mat["true_positives"] >= 1
    assert mat["accuracy"] > 95.0
    assert mat["signals_filtered"] > 600

    # Calibration Buckets
    assert len(res["calibration"]) == 6
    assert any(b["bucket"] == "0.7-0.8" for b in res["calibration"])

    # Keywords
    assert len(res["reasoning_insights"]) >= 1


# ── 4. Factor Attribution & Config Exporter Tests ─────────────────────────────

def test_factor_attribution_export():
    fae = FactorAttributionEngine()
    export_res = fae.export_trading_engine_config()
    cfg = export_res["config_json"]
    assert "GEMINI_MIN_CONFIDENCE" in cfg
    assert "STRATEGY_USE_CPR" in cfg
    assert "STRATEGY_USE_HTF_15M" in cfg
    assert "STRATEGY_MIN_SIGNAL_SCORE" in cfg

    env = export_res["env_content"]
    assert "GEMINI_MIN_CONFIDENCE=" in env
    assert "STRATEGY_USE_CPR=" in env
    assert "STRATEGY_MIN_SIGNAL_SCORE=" in env
    assert len(export_res["recommendations"]) >= 1


# ── 5. REST API Endpoint Tests ────────────────────────────────────────────────

def test_api_reconciliation_endpoint(client):
    res = client.get("/api/trading_engine/reconciliation?date=2026_09_11")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "ok"
    assert "summary" in json_data["data"]
    assert json_data["data"]["summary"]["total_live_trades"] == 4


def test_api_ai_analytics_endpoint(client):
    res = client.get("/api/trading_engine/ai_analytics?date=2026_09_11&confidence_threshold=0.70")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "ok"
    assert json_data["data"]["total_snapshots"] == 726
    assert "counterfactual_matrix" in json_data["data"]


def test_api_config_export_endpoints(client):
    # Test JSON export
    res_json = client.get("/api/trading_engine/export_config")
    assert res_json.status_code == 200
    d = res_json.get_json()
    assert d["status"] == "ok"
    assert "config_json" in d["data"]
    assert "env_content" in d["data"]

    # Test .env plain text download
    res_env = client.get("/api/trading_engine/export_config?format=env")
    assert res_env.status_code == 200
    assert b"GEMINI_MIN_CONFIDENCE=" in res_env.data
    assert "attachment" in res_env.headers.get("Content-Disposition", "")
