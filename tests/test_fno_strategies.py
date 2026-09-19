"""
tests/test_fno_strategies.py — Unit Tests for the 5 New Institutional F&O Strategies.

Tests:
1. Instantiation and default parameters of all 5 F&O models.
2. Complete 16-strategy registry and parameter grids.
3. CLI builder support for all 5 models.
4. Server factory instantiation for all 5 models.
5. Short selling lifecycle (OrderSide.SELL) in Portfolio simulator (Target hit, SL hit, P&L math).
6. Signal generation checks on simulated bars for all 5 strategies.
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from execution.simulator import ExecutionSimulator
from engine.param_grids import STRATEGY_REGISTRY, DEFAULT_PARAM_GRIDS, get_strategy_class, get_default_param_grid
from strategies.short_straddle import ShortStraddleStrategy
from strategies.pcr_reversion import PcrReversionStrategy
from strategies.banknifty_options import BankNiftyOptionsStrategy
from strategies.futures_trend import FuturesTrendStrategy
from strategies.max_pain import MaxPainConvergenceStrategy
from cli import ALL_STRATEGIES, _build_strategy
from dashboard.server import create_strategy_instance


# ── 1. Strategy Instantiation & Defaults ──────────────────────────────────────

def test_short_straddle_instantiation():
    strat = ShortStraddleStrategy()
    assert strat.name == "ShortStraddleTheta"
    assert strat.params["entry_time"] == "09:20"
    assert strat.params["sl_pct"] == 0.25
    assert strat.params["target_pct"] == 0.60
    assert strat.params["lot_size"] == 25


def test_pcr_reversion_instantiation():
    strat = PcrReversionStrategy()
    assert strat.name == "PcrReversionSentiment"
    assert strat.params["pcr_oversold"] == 0.70
    assert strat.params["pcr_overbought"] == 1.35
    assert strat.params["sl_pct"] == 0.25
    assert strat.params["lot_size"] == 25


def test_banknifty_options_instantiation():
    strat = BankNiftyOptionsStrategy()
    assert strat.name == "BankNiftyOptionBreakout"
    assert strat.params["strike_step"] == 100.0
    assert strat.params["lot_size"] == 15
    assert strat.params["sl_points"] == 30.0


def test_futures_trend_instantiation():
    strat = FuturesTrendStrategy()
    assert strat.name == "FuturesTrendFollower"
    assert strat.params["fast_ema"] == 9
    assert strat.params["slow_ema"] == 50
    assert strat.params["lot_size"] == 25


def test_max_pain_instantiation():
    strat = MaxPainConvergenceStrategy()
    assert strat.name == "MaxPainConvergence"
    assert strat.params["min_displacement"] == 40.0
    assert strat.params["sl_pct"] == 0.30
    assert strat.params["lot_size"] == 25


# ── 2. Strategy Registry & Param Grids (16 Models) ───────────────────────────

def test_full_strategy_registry():
    assert len(STRATEGY_REGISTRY) >= 16
    expected_fno_keys = ["short-straddle", "pcr-reversion", "banknifty-options", "futures-trend", "max-pain"]
    for k in expected_fno_keys:
        assert k in STRATEGY_REGISTRY
        assert k in DEFAULT_PARAM_GRIDS
        cls = get_strategy_class(k)
        assert cls is not None
        grid = get_default_param_grid(k)
        assert isinstance(grid, dict) and len(grid) > 0


# ── 3. CLI & Server Wiring ───────────────────────────────────────────────────

def test_cli_all_strategies_list():
    assert len(ALL_STRATEGIES) >= 16
    for k in ["short-straddle", "pcr-reversion", "banknifty-options", "futures-trend", "max-pain"]:
        assert k in ALL_STRATEGIES


def test_cli_build_strategy():
    args_mock = MagicMock()
    args_mock.symbols = "auto"
    for strat_key in ["short-straddle", "pcr-reversion", "banknifty-options", "futures-trend", "max-pain"]:
        strat, syms = _build_strategy(strat_key, args_mock)
        assert strat is not None
        assert len(syms) > 0


def test_server_create_strategy_instance():
    data = {
        "entry_time": "09:20",
        "sl_pct": 0.25,
        "pcr_oversold": 0.70,
        "sl_points": 30.0,
        "fast_ema": 9,
        "min_displacement": 40.0
    }
    for strat_key in ["short-straddle", "pcr-reversion", "banknifty-options", "futures-trend", "max-pain"]:
        strat, syms = create_strategy_instance(strat_key, data, ["NIFTY"])
        assert strat is not None
        assert len(syms) > 0


# ── 4. Short Selling Portfolio Accounting & Simulator ────────────────────────

def test_short_trade_target_hit():
    sim = ExecutionSimulator(slippage_pct=0.0)
    port = Portfolio(initial_capital=100000.0, simulator=sim)

    # Sell 1 lot of NIFTY option at 100.0, SL at 125.0, Target at 40.0
    trade = port.open_trade(
        symbol="NIFTY_22500_CE",
        security_id=12345,
        side=OrderSide.SELL,
        price=100.0,
        qty=25,
        sl=125.0,
        target=40.0,
        entry_time="09:20:00",
        instrument_type=InstrumentType.OPTION_CE
    )
    assert trade is not None
    assert trade.side == OrderSide.SELL

    # Premium drops to 38.0 (below target 40.0)
    closed = port.update_open_trades("10:00:00", {
        "NIFTY_22500_CE": {"open": 42.0, "high": 45.0, "low": 38.0, "close": 39.0}
    })
    assert len(closed) == 1
    t = closed[0]
    assert t.exit_reason == "TARGET_HIT"
    assert t.exit_price == 40.0
    # Gross profit = (100 - 40) * 25 = +1500
    assert t.gross_pnl == pytest.approx(1500.0, rel=1e-2)
    assert t.net_pnl > 1400.0


def test_short_trade_sl_hit():
    sim = ExecutionSimulator(slippage_pct=0.0)
    port = Portfolio(initial_capital=100000.0, simulator=sim)

    # Sell 1 lot of NIFTY option at 100.0, SL at 125.0, Target at 40.0
    trade = port.open_trade(
        symbol="NIFTY_22500_CE",
        security_id=12345,
        side=OrderSide.SELL,
        price=100.0,
        qty=25,
        sl=125.0,
        target=40.0,
        entry_time="09:20:00",
        instrument_type=InstrumentType.OPTION_CE
    )
    assert trade is not None

    # Premium jumps to 130.0 (above SL 125.0)
    closed = port.update_open_trades("09:45:00", {
        "NIFTY_22500_CE": {"open": 105.0, "high": 130.0, "low": 102.0, "close": 128.0}
    })
    assert len(closed) == 1
    t = closed[0]
    assert t.exit_reason == "SL_HIT"
    assert t.exit_price == 125.0
    # Gross loss = (100 - 125) * 25 = -625
    assert t.gross_pnl == pytest.approx(-625.0, rel=1e-2)
    assert t.net_pnl < -625.0


# ── 5. Strategy Signal Logic Tests ───────────────────────────────────────────

def test_short_straddle_signals():
    strat = ShortStraddleStrategy()
    port = Portfolio()
    mock_loader = MagicMock()
    mock_loader.get_atm_strike.return_value = 22500.0

    chain_df = pd.DataFrame([
        {"strike_price": 22500.0, "ce_ltp": 120.0, "pe_ltp": 110.0, "ce_security_id": 1, "pe_security_id": 2}
    ])
    mock_loader.get_nearest_chain.return_value = chain_df
    strat.option_loader = mock_loader

    strat.on_session_start("2026-09-02", port, {})
    quotes = {"NIFTY": {"ltp": 22510.0, "close": 22510.0}}

    # Before 09:20 -> no signals
    sig_early = strat.on_bar("2026-09-02 09:16:00", quotes, port, {})
    assert len(sig_early) == 0

    # At 09:20 -> generates both CE and PE SELL signals
    signals = strat.on_bar("2026-09-02 09:20:00", quotes, port, {})
    assert len(signals) == 2
    assert signals[0]["side"] == OrderSide.SELL
    assert signals[0]["instrument_type"] == InstrumentType.OPTION_CE
    assert signals[1]["side"] == OrderSide.SELL
    assert signals[1]["instrument_type"] == InstrumentType.OPTION_PE


def test_pcr_reversion_signals():
    strat = PcrReversionStrategy()
    port = Portfolio()
    mock_loader = MagicMock()
    mock_loader.get_atm_contract.return_value = {
        "ltp": 85.0, "strike_price": 22500.0, "security_id": 100
    }
    strat.option_loader = mock_loader

    strat.on_session_start("2026-09-02", port, {})
    # Feed 15 bars
    for i in range(15):
        strat.on_bar(f"2026-09-02 09:{20+i:02d}:00", {"NIFTY": {"close": 22500.0 - i * 10}}, port, {})

    # Mock oversold PCR (< 0.70)
    mock_loader.get_nearest_chain.return_value = pd.DataFrame({"strike_price": [22500.0]})
    mock_loader.calculate_pcr.return_value = 0.60
    signals = strat.on_bar("2026-09-02 09:36:00", {"NIFTY": {"close": 22350.0}}, port, {})
    assert len(signals) == 1
    assert signals[0]["side"] == OrderSide.BUY
    assert signals[0]["instrument_type"] == InstrumentType.OPTION_CE


def test_banknifty_options_signals():
    strat = BankNiftyOptionsStrategy()
    port = Portfolio()
    mock_loader = MagicMock()
    mock_loader.get_atm_contract.return_value = {
        "ltp": 250.0, "strike_price": 48000.0, "security_id": 200, "delta": 0.52
    }
    strat.option_loader = mock_loader

    strat.on_session_start("2026-09-02", port, {})
    # Establish ORB between 09:15 and 09:30
    for m in range(15, 30):
        strat.on_bar(f"2026-09-02 09:{m:02d}:00", {"BANKNIFTY": {"open": 48000, "high": 48100, "low": 47900, "close": 48050}}, port, {})

    assert strat.orb_high == 48100.0
    assert strat.orb_low == 47900.0

    # Breakout above ORB High
    signals = strat.on_bar("2026-09-02 09:35:00", {"BANKNIFTY": {"open": 48105, "high": 48180, "low": 48100, "close": 48160}}, port, {})
    assert len(signals) == 1
    assert signals[0]["side"] == OrderSide.BUY
    assert signals[0]["instrument_type"] == InstrumentType.OPTION_CE
    assert signals[0]["lot_size"] == 15


def test_futures_trend_signals():
    strat = FuturesTrendStrategy()
    port = Portfolio()
    strat.on_session_start("2026-09-02", port, {})

    # Generate 55 bars of upward trending data
    for i in range(55):
        p = 22000.0 + i * 5.0
        strat.on_bar(f"2026-09-02 09:{15+i:02d}:00", {
            "NIFTY": {"open": p - 2.0, "high": p + 4.0, "low": p - 3.0, "close": p, "volume": 1000.0}
        }, port, {})

    p_last = 22000.0 + 55 * 5.0
    signals = strat.on_bar("2026-09-02 10:11:00", {
        "NIFTY": {"open": p_last - 2.0, "high": p_last + 5.0, "low": p_last - 1.0, "close": p_last, "volume": 1500.0}
    }, port, {})
    assert len(signals) == 1
    assert signals[0]["instrument_type"] == InstrumentType.FUTURES
    assert signals[0]["side"] == OrderSide.BUY
    assert signals[0]["lot_size"] == 25


def test_max_pain_signals():
    strat = MaxPainConvergenceStrategy()
    port = Portfolio()
    mock_loader = MagicMock()
    mock_loader.get_atm_contract.return_value = {
        "ltp": 95.0, "strike_price": 22500.0, "security_id": 300
    }
    # Max pain at 22500, but spot at 22400 (displacement = -100 <= -40)
    mock_loader.calculate_max_pain.return_value = 22500.0
    mock_loader.get_nearest_chain.return_value = pd.DataFrame({"strike_price": [22500.0]})
    strat.option_loader = mock_loader

    strat.on_session_start("2026-09-02", port, {})
    signals = strat.on_bar("2026-09-02 12:00:00", {"NIFTY": {"close": 22400.0}}, port, {})
    assert len(signals) == 1
    assert signals[0]["side"] == OrderSide.BUY
    assert signals[0]["instrument_type"] == InstrumentType.OPTION_CE
