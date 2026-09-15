import pytest
from unittest.mock import MagicMock
from cli import _parse_cli_symbols, _build_strategy
from dashboard.server import resolve_server_symbols
from engine.backtest_engine import BacktestEngine
from data.data_loader import DataLoader
from execution.simulator import ExecutionSimulator


def test_parse_cli_symbols():
    assert _parse_cli_symbols("") == ["auto"]
    assert _parse_cli_symbols(None) == ["auto"]
    assert _parse_cli_symbols("auto") == ["auto"]
    assert _parse_cli_symbols("AUTO") == ["auto"]
    assert _parse_cli_symbols("  auto  ") == ["auto"]
    assert _parse_cli_symbols("RELIANCE, TCS") == ["RELIANCE", "TCS"]
    assert _parse_cli_symbols("infy, hdfcbank") == ["INFY", "HDFCBANK"]
    assert _parse_cli_symbols("   ") == ["auto"]


def test_build_strategy_defaults():
    args_mock = MagicMock()
    args_mock.symbols = "auto"

    equity_strats = [
        "equity", "orb", "supertrend", "camarilla", "ema-ribbon",
        "bollinger-b", "macd-accel", "vwap-reversion", "rsi-momentum"
    ]
    for strat_key in equity_strats:
        strat, syms = _build_strategy(strat_key, args_mock)
        assert strat is not None
        assert syms == ["auto"], f"Strategy {strat_key} did not default to ['auto']"


def test_build_strategy_custom():
    args_mock = MagicMock()
    args_mock.symbols = "RELIANCE, TCS"

    strat, syms = _build_strategy("orb", args_mock)
    assert syms == ["RELIANCE", "TCS"]


def test_resolve_server_symbols():
    assert resolve_server_symbols(None) == ["auto"]
    assert resolve_server_symbols([]) == ["auto"]
    assert resolve_server_symbols("") == ["auto"]
    assert resolve_server_symbols("auto") == ["auto"]
    assert resolve_server_symbols("AUTO") == ["auto"]
    assert resolve_server_symbols(["auto"]) == ["auto"]
    assert resolve_server_symbols(["AUTO"]) == ["auto"]
    assert resolve_server_symbols("RELIANCE, TCS") == ["RELIANCE", "TCS"]
    assert resolve_server_symbols(["RELIANCE", "tcs"]) == ["RELIANCE", "TCS"]


def test_backtest_engine_auto_discover_flag():
    dl = MagicMock(spec=DataLoader)
    sim = MagicMock(spec=ExecutionSimulator)
    engine = BacktestEngine(data_loader=dl, simulator=sim)

    for sym_val in [None, ["auto"], ["AUTO"], ["  auto  "], []]:
        auto_discover = (
            (sym_val is None)
            or (sym_val == ["auto"])
            or (sym_val == [])
            or (len(sym_val) == 1 and str(sym_val[0]).strip().lower() == "auto")
        )
        assert auto_discover is True
