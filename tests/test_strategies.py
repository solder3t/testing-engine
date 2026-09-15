"""
tests/test_strategies.py — Unit tests for built-in strategies from BOT 2.0.
"""

import pytest
from execution.portfolio import Portfolio
from strategies.vwap_reversion import VwapReversionStrategy
from strategies.rsi_momentum import RsiMomentumStrategy


def test_vwap_reversion_strategy_init():
    strat = VwapReversionStrategy(params={"bb_period": 10, "bb_std": 1.5})
    assert strat.params["bb_period"] == 10
    assert strat.params["bb_std"] == 1.5
    assert strat.name == "VWAP_Mean_Reversion"

    port = Portfolio(initial_capital=100000.0)
    strat.on_session_start("2026_09_02", port, {})
    assert len(strat.bar_history) == 0


def test_rsi_momentum_strategy_init():
    strat = RsiMomentumStrategy(params={"fast_ema": 5, "slow_ema": 15, "rsi_period": 10})
    assert strat.params["fast_ema"] == 5
    assert strat.params["slow_ema"] == 15
    assert strat.params["rsi_period"] == 10
    assert strat.name == "RSI_Momentum_Breakout"

    port = Portfolio(initial_capital=100000.0)
    strat.on_session_start("2026_09_02", port, {})
    assert len(strat.bar_history) == 0
