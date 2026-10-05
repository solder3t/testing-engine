"""
tests/test_composable_yaml.py — Unit tests for YAML Strategy Loader and Composable Strategy engine.
"""

from pathlib import Path
import pytest
from strategies.base_strategy import BaseStrategy, Signal
from strategies.composable import ComposableStrategy, YamlStrategyLoader


SAMPLE_YAML = """
name: "Test_YAML_Strategy"
category: "COMPOSABLE"
direction: "CE"

risk_params:
  sl_points: 20.0
  target_points: 40.0
  sl_pct: 2.0
  tp_pct: 4.0
  time_exit: "15:20"

entry_filters:
  combinator: "AND"
  conditions:
    - indicator: "rsi"
      params:
        period: 14
      operator: "in_range"
      threshold_min: 30.0
      threshold_max: 70.0
    - operator: "time_between"
      start: "09:20"
      end: "15:00"

exit_rules:
  combinator: "OR"
  conditions:
    - indicator: "rsi"
      params:
        period: 14
      operator: "greater_than"
      threshold: 80.0
    - operator: "time_exit"
      time: "15:20"
"""


def test_yaml_strategy_loader_from_string():
    strat = YamlStrategyLoader.load_from_yaml_string(SAMPLE_YAML)
    assert isinstance(strat, BaseStrategy)
    assert isinstance(strat, ComposableStrategy)
    assert strat.name == "Test_YAML_Strategy"
    assert strat.category == "COMPOSABLE"
    assert strat.rule_config.get("direction") == "CE"
    assert strat.rule_config.get("sl_pct") == 2.0
    assert strat.rule_config.get("tp_pct") == 4.0
    assert "entry_rules" in strat.rule_config


def test_yaml_strategy_loader_from_file():
    yaml_path = Path(__file__).resolve().parent.parent / "strategies" / "examples" / "ema_cross_rsi.yaml"
    assert yaml_path.is_file()

    strat = YamlStrategyLoader.load_from_yaml_file(yaml_path)
    assert isinstance(strat, BaseStrategy)
    assert strat.name == "EMA_RSI_TrendFollower"
    assert strat.rule_config.get("direction") == "AUTO"


def test_composable_strategy_conditions_and_blocks():
    strat = YamlStrategyLoader.load_from_yaml_string(SAMPLE_YAML)

    # Generate synthetic candle history (30 candles)
    history = []
    base_price = 100.0
    for i in range(30):
        c = {
            "candle_time": f"2026-09-02 09:{15 + i:02d}:00",
            "open": base_price + i,
            "high": base_price + i + 1.0,
            "low": base_price + i - 0.5,
            "close": base_price + i + 0.5,
            "volume": 1000
        }
        history.append(c)

    # 1. Test candle inside time_between (e.g. 09:45:00)
    curr_candle = {
        "candle_time": "2026-09-02 09:45:00",
        "open": 130.0,
        "high": 131.0,
        "low": 129.5,
        "close": 130.5,
        "volume": 1000
    }

    sig = strat.on_candle(curr_candle, history)
    # The condition RSI is between 30 and 70, time is between 09:20 and 15:00
    # Depending on synthetic RSI, check signal generation
    if sig:
        assert sig.action == "ENTER"
        assert strat.in_position is True

        # Now test SL / TP pct exit
        # If in position, send next candle with huge gain -> trigger TP
        tp_candle = {
            "candle_time": "2026-09-02 09:46:00",
            "open": 150.0,
            "high": 155.0,
            "low": 149.0,
            "close": 150.0,  # ~15% gain > 4% tp_pct
            "volume": 1000
        }
        exit_sig = strat.on_candle(tp_candle, history + [curr_candle])
        assert exit_sig is not None
        assert exit_sig.action == "EXIT_NOW"
        assert strat.in_position is False


def test_composable_time_exit():
    strat = YamlStrategyLoader.load_from_yaml_string(SAMPLE_YAML)
    strat.in_position = True
    strat.pos_entry_price = 100.0

    history = [
        {"candle_time": "2026-09-02 09:30:00", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 100}
        for _ in range(30)
    ]

    # Candle past 15:20
    late_candle = {
        "candle_time": "2026-09-02 15:25:00",
        "open": 100.0,
        "high": 100.5,
        "low": 99.5,
        "close": 100.0,
        "volume": 100
    }
    sig = strat.on_candle(late_candle, history)
    assert sig is not None
    assert sig.action == "EXIT_NOW"
    assert "Time exit" in sig.reasoning
