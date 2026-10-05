"""
tests/test_strategy_catalog.py - Verification of the 56 Institutional Strategies Catalog.
"""

from typing import Any, Dict
import pytest
import numpy as np
from strategies.builtin import BUILTIN_STRATEGIES
from engine.param_grids import STRATEGY_REGISTRY, get_default_param_grid, get_strategy_class
from strategies.composable import ComposableStrategy, RuleNode, RuleCondition, RuleAction


def test_strategy_catalog_count():
    """Verify all 56 strategies are loaded in the catalog."""
    assert len(BUILTIN_STRATEGIES) == 56, f"Expected 56 strategies, got {len(BUILTIN_STRATEGIES)}"


def test_strategy_instantiation_and_parameters():
    """Verify each strategy can be instantiated and has a valid parameter space."""
    for key, cls in BUILTIN_STRATEGIES.items():
        strat = cls()
        assert strat.name, f"Strategy {key} missing name"
        assert hasattr(strat, "parameters"), f"Strategy {key} missing parameters"
        assert len(strat.parameters.parameters) > 0, f"Strategy {key} has empty parameter space"

        # Verify defaults validate without errors
        defaults = strat.parameters.get_defaults()
        validated = strat.parameters.validate_all(defaults)
        assert validated == defaults, f"Strategy {key} defaults validation altered values: {defaults} vs {validated}"


def test_strategy_registry_and_grids():
    """Verify all strategies are registered in STRATEGY_REGISTRY and have param grids."""
    for key in BUILTIN_STRATEGIES.keys():
        assert key in STRATEGY_REGISTRY, f"Strategy {key} not found in STRATEGY_REGISTRY"
        cls = get_strategy_class(key)
        assert cls == BUILTIN_STRATEGIES[key]

        grid = get_default_param_grid(key)
        assert isinstance(grid, dict), f"Param grid for {key} is not a dict"
        assert len(grid) > 0, f"Param grid for {key} is empty"
        for param_name, values in grid.items():
            assert isinstance(values, list), f"Param {param_name} in {key} values is not a list"
            assert len(values) > 0, f"Param {param_name} in {key} has no values"


def test_strategy_session_smoke():
    """Smoke test: feed synthetic candles into each strategy to verify prepare_session and on_candle."""
    # Create 60 realistic 1-minute mock candles
    base_price = 24000.0
    candles = []
    for i in range(60):
        o = base_price + np.sin(i / 5.0) * 20.0
        h = o + 5.0
        l = o - 5.0
        c = o + 2.0
        v = 1500 + int(abs(np.cos(i / 3.0)) * 500)
        candles.append({
            "timestamp": f"2024-10-04 09:{15 + i // 60:02d}:{i % 60:02d}",
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "oi": 100000 + i * 50,
            "call_oi": 50000,
            "put_oi": 52000,
            "iv": 14.5,
            "vwap": o,
            "fii_net": 120.0,
            "dii_net": -50.0,
        })

    for key, cls in BUILTIN_STRATEGIES.items():
        strat = cls()
        context: Dict[str, Any] = {"date": "2024-10-04", "symbol": "NIFTY", "instrument": "NIFTY"}
        try:
            strat.prepare_session(candles, context)
        except Exception as e:
            pytest.fail(f"Strategy {key}.prepare_session failed: {e}")

        history = []
        for idx, candle in enumerate(candles):
            history.append(candle)
            context["candle_index"] = idx
            try:
                sig = strat.on_candle(candle, history, context)
                if sig is not None:
                    assert hasattr(sig, "action"), f"{key} signal missing action"
            except Exception as e:
                pytest.fail(f"Strategy {key}.on_candle failed on candle {idx}: {e}")


def test_composable_strategy_evaluation():
    """Verify the composable rule-tree strategy builds and executes rules."""
    root = RuleNode(
        condition=RuleCondition("rsi", "<", 30),
        action=RuleAction("BUY", "CE", 1.0, 15.0, 30.0)
    )
    strat = ComposableStrategy(name="Test Composable", rule_tree=root)
    assert strat.name == "Test Composable"

    # Test condition matching
    ctx = {"rsi": 25.0}
    action = root.evaluate(ctx)
    assert action is not None
    assert action.action == "BUY"
    assert action.option_type == "CE"

    # Test condition not matching
    ctx_false = {"rsi": 45.0}
    action_false = root.evaluate(ctx_false)
    assert action_false is None
