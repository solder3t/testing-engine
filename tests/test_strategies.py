"""
tests/test_strategies.py — Unit tests for quantitative backtesting strategies.
"""

import pytest
from execution.portfolio import Portfolio
from execution.order import OrderSide
from strategies.vwap_reversion import VwapReversionStrategy
from strategies.rsi_momentum import RsiMomentumStrategy
from strategies.orb_breakout import OrbBreakoutStrategy
from strategies.supertrend_trend import SupertrendTrendStrategy
from strategies.camarilla_breakout import CamarillaBreakoutStrategy
from strategies.ema_ribbon import EmaRibbonStrategy
from strategies.bollinger_percent_b import BollingerPercentBStrategy
from strategies.macd_acceleration import MacdAccelerationStrategy


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


def test_orb_breakout_strategy():
    strat = OrbBreakoutStrategy(params={"opening_minutes": 15, "risk_reward": 2.0})
    assert strat.params["opening_minutes"] == 15
    assert strat.params["risk_reward"] == 2.0
    assert "Opening_Range_Breakout" in strat.name

    port = Portfolio(initial_capital=100000.0)
    strat.on_session_start("2026_09_02", port, {})
    assert len(strat.orb_levels) == 0

    # Stream 15 bars within opening window
    for m in range(15, 30):
        quotes = {
            "RELIANCE": {"high": 2500.0 + (m - 15), "low": 2480.0, "close": 2490.0 + (m - 15), "volume": 1000}
        }
        sig = strat.on_bar(f"2026-09-02 09:{m:02d}:00", quotes, port, {})
        assert sig == []  # No breakout during range establishment

    assert "RELIANCE" in strat.orb_levels
    assert strat.orb_levels["RELIANCE"]["high"] == 2514.0

    # Breakout bar at 09:31
    quotes = {
        "RELIANCE": {"high": 2530.0, "low": 2510.0, "close": 2525.0, "volume": 5000}
    }
    sig = strat.on_bar("2026-09-02 09:31:00", quotes, port, {})
    assert len(sig) == 1
    assert sig[0]["side"] == OrderSide.BUY
    assert sig[0]["symbol"] == "RELIANCE"
    assert sig[0]["price"] == 2525.0


def test_supertrend_strategy():
    strat = SupertrendTrendStrategy(params={"atr_period": 10, "multiplier": 3.0, "ema_filter": 20})
    assert strat.params["atr_period"] == 10
    assert strat.params["multiplier"] == 3.0
    assert strat.name == "Supertrend_Trend_Follower"

    port = Portfolio(initial_capital=100000.0)
    strat.on_session_start("2026_09_02", port, {})
    assert len(strat.bar_history) == 0


def test_camarilla_breakout_strategy():
    strat = CamarillaBreakoutStrategy(params={"formation_minutes": 15, "risk_reward": 2.0})
    assert strat.params["formation_minutes"] == 15
    assert strat.name == "Camarilla_Floor_Pivot_Breakout"

    port = Portfolio(initial_capital=100000.0)
    context = {
        "previous_day_ohlc": {
            "RELIANCE": {"high": 2500.0, "low": 2400.0, "close": 2450.0}
        }
    }
    strat.on_session_start("2026_09_02", port, context)
    assert "RELIANCE" in strat.pivots
    p = strat.pivots["RELIANCE"]
    assert p["R4"] > p["R3"] > p["S3"] > p["S4"]


def test_ema_ribbon_strategy():
    strat = EmaRibbonStrategy(params={"fast_ema": 9, "med_ema": 21, "slow_ema": 50})
    assert strat.params["fast_ema"] == 9
    assert strat.params["med_ema"] == 21
    assert strat.params["slow_ema"] == 50
    assert strat.name == "Triple_EMA_Ribbon_Alignment"

    port = Portfolio(initial_capital=100000.0)
    strat.on_session_start("2026_09_02", port, {})
    assert len(strat.bar_history) == 0


def test_bollinger_percent_b_strategy():
    strat = BollingerPercentBStrategy(params={"period": 20, "std_dev": 2.0})
    assert strat.params["period"] == 20
    assert strat.params["std_dev"] == 2.0
    assert strat.name == "Bollinger_PercentB_MeanReversion"

    port = Portfolio(initial_capital=100000.0)
    strat.on_session_start("2026_09_02", port, {})
    assert len(strat.bar_history) == 0


def test_macd_acceleration_strategy():
    strat = MacdAccelerationStrategy(params={"fast_period": 12, "slow_period": 26, "signal_period": 9})
    assert strat.params["fast_period"] == 12
    assert strat.params["slow_period"] == 26
    assert strat.name == "MACD_Histogram_Acceleration"

    port = Portfolio(initial_capital=100000.0)
    strat.on_session_start("2026_09_02", port, {})
    assert len(strat.bar_history) == 0
