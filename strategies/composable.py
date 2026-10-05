"""
composable_strategy.py - Dynamic rule-tree strategy builder for the Strategy Engine.

Allows composing pure mathematical entry and exit rules using 20+ indicators,
threshold ranges, dual-handle sliders, and cross-indicator logic without code.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import numpy as np
import yaml
from .base_strategy import BaseStrategy, Signal
from .parameter_space import Parameter
from math_engine import MathEngine


@dataclass
class RuleCondition:
    indicator: str
    operator: str  # "<", ">", "<=", ">=", "==", "IN_RANGE", "CROSSES_ABOVE", "CROSSES_BELOW"
    threshold: Any = 0.0
    threshold_min: float = 0.0
    threshold_max: float = 0.0
    params: Dict[str, Any] = field(default_factory=dict)
    compare_indicator: Optional[str] = None
    compare_params: Optional[Dict[str, Any]] = None

    def evaluate(self, context: Dict[str, Any]) -> bool:
        val = context.get(self.indicator)
        if val is None:
            return False
        op = self.operator
        if op in ("<", "LESS_THAN"):
            return float(val) < float(self.threshold)
        elif op in (">", "GREATER_THAN"):
            return float(val) > float(self.threshold)
        elif op in ("<=", "LESS_THAN_OR_EQUAL"):
            return float(val) <= float(self.threshold)
        elif op in (">=", "GREATER_THAN_OR_EQUAL"):
            return float(val) >= float(self.threshold)
        elif op in ("==", "EQUALS"):
            return abs(float(val) - float(self.threshold)) < 1e-4
        elif op == "IN_RANGE":
            return float(self.threshold_min) <= float(val) <= float(self.threshold_max)
        return False


@dataclass
class RuleAction:
    action: str = "ENTER"  # "ENTER", "EXIT", "BUY", "SELL"
    option_type: str = "CE"  # "CE", "PE", "FUT", "EQ"
    quantity: float = 1.0
    stop_loss_pts: float = 20.0
    target_pts: float = 40.0
    confidence: float = 0.85
    reasoning: str = ""


@dataclass
class RuleNode:
    condition: Optional[RuleCondition] = None
    action: Optional[RuleAction] = None
    children: List["RuleNode"] = field(default_factory=list)
    combinator: str = "AND"

    def evaluate(self, context: Dict[str, Any]) -> Optional[RuleAction]:
        if self.condition:
            if not self.condition.evaluate(context):
                return None
        if self.action:
            return self.action
        for child in self.children:
            res = child.evaluate(context)
            if res:
                return res
        return None


class ComposableStrategy(BaseStrategy):
    """
    A runtime-configurable strategy executing user-defined indicator rules.
    """

    DEFAULT_CONFIG = {
        "name": "Custom Composed Strategy",
        "direction": "AUTO",  # "CE", "PE", or "AUTO"
        "entry_rules": {
            "combinator": "AND",
            "conditions": [
                {
                    "indicator": "rsi",
                    "params": {"period": 14},
                    "operator": "IN_RANGE",
                    "threshold_min": 30.0,
                    "threshold_max": 50.0
                },
                {
                    "indicator": "ema",
                    "params": {"period": 9},
                    "operator": "CROSSES_ABOVE",
                    "compare_indicator": "ema",
                    "compare_params": {"period": 21}
                }
            ]
        },
        "exit_rules": {
            "combinator": "OR",
            "conditions": [
                {
                    "indicator": "rsi",
                    "params": {"period": 14},
                    "operator": "GREATER_THAN",
                    "threshold": 75.0
                }
            ]
        },
        "sl_points": 20.0,
        "target_points": 40.0,
        "confidence": 0.85
    }

    def __init__(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None, rule_tree: Optional[RuleNode] = None):
        cfg: Dict[str, Any] = dict(config or self.DEFAULT_CONFIG)
        strategy_name: str = str(name or cfg.get("name", "Custom Composed Strategy"))
        cfg["name"] = strategy_name
        super().__init__(
            name=strategy_name,
            description="User-composed indicator rule strategy",
            category="COMPOSABLE"
        )
        self.rule_config: Dict[str, Any] = cfg
        self.rule_tree = rule_tree
        self.math_engine = MathEngine(use_gpu=False)
        self.in_position = False
        self.pos_entry_price = 0.0
        self.pos_direction = "CE"

    def _setup_parameters(self) -> None:
        """Register default parameter placeholders."""
        self.parameters.add(Parameter("sl_points", "float", 20.0, 5.0, 150.0, 1.0, description="Stop loss points"))
        self.parameters.add(Parameter("target_points", "float", 40.0, 10.0, 300.0, 5.0, description="Target points"))

    def update_rules(self, rule_config: Dict[str, Any]) -> None:
        """Update the active rule definition."""
        self.rule_config = rule_config
        self.name = str(rule_config.get("name", self.name))
        if "sl_points" in rule_config:
            self.current_params["sl_points"] = float(rule_config["sl_points"])
        if "target_points" in rule_config:
            self.current_params["target_points"] = float(rule_config["target_points"])

    def reset(self) -> None:
        self.in_position = False
        self.pos_entry_price = 0.0
        self.pos_direction = "CE"

    def on_candle(
        self,
        candle: Dict[str, Any],
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Signal]:
        all_candles = history + [candle]
        if len(all_candles) < 25:
            return None

        # Build numpy arrays for MathEngine
        closes = np.array([float(c.get("close", 0.0)) for c in all_candles])
        highs = np.array([float(c.get("high", c.get("close", 0.0))) for c in all_candles])
        lows = np.array([float(c.get("low", c.get("close", 0.0))) for c in all_candles])
        opens = np.array([float(c.get("open", c.get("close", 0.0))) for c in all_candles])
        volumes = np.array([float(c.get("volume", 0.0)) for c in all_candles])

        data = {
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "opens": opens,
            "volumes": volumes
        }

        # 1. Check Exit conditions if currently in position
        if self.in_position:
            curr_c = float(closes[-1])
            time_str = str(candle.get("candle_time", ""))
            time_part = time_str.split(" ")[-1][:5] if " " in time_str else time_str[:5]

            # Time exit check
            time_exit_val = self.rule_config.get("time_exit") or self.rule_config.get("risk_params", {}).get("time_exit")
            if time_exit_val and time_part >= str(time_exit_val):
                self.in_position = False
                return Signal(
                    action="EXIT_NOW",
                    reasoning=f"Time exit triggered ({time_part} >= {time_exit_val})",
                    timestamp=time_str
                )

            # SL pct check
            sl_pct = float(self.rule_config.get("sl_pct", self.rule_config.get("risk_params", {}).get("sl_pct", 0.0)))
            if sl_pct > 0 and self.pos_entry_price > 0:
                pnl_pct = (
                    ((curr_c - self.pos_entry_price) / self.pos_entry_price) * 100.0
                    if self.pos_direction == "CE"
                    else ((self.pos_entry_price - curr_c) / self.pos_entry_price) * 100.0
                )
                if pnl_pct <= -sl_pct:
                    self.in_position = False
                    return Signal(
                        action="EXIT_NOW",
                        reasoning=f"Stop loss pct breached ({pnl_pct:.2f}% <= -{sl_pct}%)",
                        timestamp=time_str
                    )

            # TP pct check
            tp_pct = float(self.rule_config.get("tp_pct", self.rule_config.get("risk_params", {}).get("tp_pct", 0.0)))
            if tp_pct > 0 and self.pos_entry_price > 0:
                pnl_pct = (
                    ((curr_c - self.pos_entry_price) / self.pos_entry_price) * 100.0
                    if self.pos_direction == "CE"
                    else ((self.pos_entry_price - curr_c) / self.pos_entry_price) * 100.0
                )
                if pnl_pct >= tp_pct:
                    self.in_position = False
                    return Signal(
                        action="EXIT_NOW",
                        reasoning=f"Take profit pct reached ({pnl_pct:.2f}% >= {tp_pct}%)",
                        timestamp=time_str
                    )

            exit_rules = self.rule_config.get("exit_rules", {})
            if isinstance(exit_rules, dict) and self._evaluate_rule_group(exit_rules, data, candle):
                self.in_position = False
                return Signal(
                    action="EXIT_NOW",
                    reasoning="Composable exit conditions satisfied",
                    timestamp=time_str
                )
            return None

        # 2. Check Entry conditions
        entry_rules = self.rule_config.get("entry_rules") or self.rule_config.get("entry_filters", {})
        if isinstance(entry_rules, dict) and self._evaluate_rule_group(entry_rules, data, candle):
            direction = str(self.rule_config.get("direction", "AUTO")).upper()
            if direction == "AUTO":
                # Detect bias from close vs EMA or Supertrend
                ema_val = self.math_engine.compute_custom_indicator("ema", {"period": 20}, data)
                curr_c = closes[-1]
                curr_ema = ema_val[-1] if not np.isnan(ema_val[-1]) else curr_c
                option_type = "CE" if curr_c >= curr_ema else "PE"
            elif direction in ("PE", "PUT", "SHORT", "SELL"):
                option_type = "PE"
            else:
                option_type = "CE"

            curr_price = float(closes[-1])
            sl_val = self.rule_config.get("sl_points", self.current_params.get("sl_points", 20.0))
            target_val = self.rule_config.get("target_points", self.current_params.get("target_points", 40.0))
            conf_val = self.rule_config.get("confidence", 0.85)

            sl_pts = float(sl_val) if isinstance(sl_val, (int, float, str)) else 20.0
            target_pts = float(target_val) if isinstance(target_val, (int, float, str)) else 40.0
            confidence = float(conf_val) if isinstance(conf_val, (int, float, str)) else 0.85

            self.in_position = True
            self.pos_entry_price = curr_price
            self.pos_direction = option_type
            return Signal(
                action="ENTER",
                market_bias="CALL" if option_type == "CE" else "PUT",
                option_type=option_type,
                strike=round(curr_price / 50.0) * 50.0,
                entry_price=curr_price,
                stop_loss=sl_pts,
                target=target_pts,
                confidence=confidence,
                reasoning=f"Composable entry conditions triggered ({self.name})",
                timestamp=str(candle.get("candle_time", "")),
                metadata={"rule_name": self.name, "direction": option_type}
            )

        return None

    def _evaluate_rule_group(
        self,
        rule_group: Dict[str, Any],
        data: Dict[str, np.ndarray],
        candle: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Evaluate a group of conditions connected with AND / OR."""
        if not rule_group:
            return False

        conditions = rule_group.get("conditions", [])
        if not conditions:
            return False

        combinator = rule_group.get("combinator", "AND").upper()
        results = [self._evaluate_single_condition(cond, data, candle) for cond in conditions]

        if combinator == "OR":
            return any(results)
        return all(results)

    def _evaluate_single_condition(
        self,
        cond: Dict[str, Any],
        data: Dict[str, np.ndarray],
        candle: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Evaluate a single indicator or temporal condition."""
        operator = str(cond.get("operator", "GREATER_THAN")).upper().strip()
        time_str = str(candle.get("candle_time", "")) if candle else ""
        time_part = time_str.split(" ")[-1][:5] if " " in time_str else time_str[:5]

        # Time-based operators
        if operator in ("TIME_BETWEEN", "BETWEEN_TIME"):
            start_t = cond.get("start", cond.get("threshold_min", "09:15"))
            end_t = cond.get("end", cond.get("threshold_max", "15:15"))
            return start_t <= time_part <= end_t

        if operator in ("TIME_EXIT", "AFTER_TIME"):
            exit_t = cond.get("time", cond.get("threshold", "15:15"))
            return time_part >= exit_t

        ind_name = cond.get("indicator")
        if not ind_name:
            return False

        params = cond.get("params", {})
        series = self.math_engine.compute_custom_indicator(str(ind_name).lower(), params, data)
        if len(series) < 2 or np.isnan(series[-1]):
            return False

        curr_val = series[-1]
        prev_val = series[-2]

        # Determine target comparison value or series
        if operator in ("CROSSES_ABOVE", "CROSS_ABOVE"):
            compare_ind = cond.get("compare_indicator")
            if compare_ind:
                comp_params = cond.get("compare_params", {})
                comp_series = self.math_engine.compute_custom_indicator(str(compare_ind).lower(), comp_params, data)
                if len(comp_series) < 2 or np.isnan(comp_series[-1]) or np.isnan(comp_series[-2]):
                    return False
                prev_comp = comp_series[-2]
                curr_comp = comp_series[-1]
            else:
                threshold = float(cond.get("threshold", 0.0))
                prev_comp = threshold
                curr_comp = threshold

            return prev_val <= prev_comp and curr_val > curr_comp

        elif operator in ("CROSSES_BELOW", "CROSS_BELOW"):
            compare_ind = cond.get("compare_indicator")
            if compare_ind:
                comp_params = cond.get("compare_params", {})
                comp_series = self.math_engine.compute_custom_indicator(str(compare_ind).lower(), comp_params, data)
                if len(comp_series) < 2 or np.isnan(comp_series[-1]) or np.isnan(comp_series[-2]):
                    return False
                prev_comp = comp_series[-2]
                curr_comp = comp_series[-1]
            else:
                threshold = float(cond.get("threshold", 0.0))
                prev_comp = threshold
                curr_comp = threshold

            return prev_val >= prev_comp and curr_val < curr_comp

        elif operator in ("IN_RANGE", "BETWEEN"):
            min_v = float(cond.get("threshold_min", cond.get("min", 0.0)))
            max_v = float(cond.get("threshold_max", cond.get("max", 100.0)))
            return min_v <= curr_val <= max_v

        elif operator in ("GREATER_THAN", "GT", ">"):
            th = float(cond.get("threshold", 0.0))
            return curr_val > th

        elif operator in ("LESS_THAN", "LT", "<"):
            th = float(cond.get("threshold", 0.0))
            return curr_val < th

        elif operator in ("GREATER_THAN_OR_EQUAL", "GTE", ">="):
            th = float(cond.get("threshold", 0.0))
            return curr_val >= th

        elif operator in ("LESS_THAN_OR_EQUAL", "LTE", "<="):
            th = float(cond.get("threshold", 0.0))
            return curr_val <= th

        elif operator in ("EQUALS", "EQ", "=="):
            th = float(cond.get("threshold", 0.0))
            return abs(curr_val - th) < 1e-4

        elif operator == "INCREASING":
            return curr_val > prev_val

        elif operator == "DECREASING":
            return curr_val < prev_val

        return False


class YamlStrategyLoader:
    """
    Parses YAML strategy specs and instantiates a runnable strategy class
    conforming to BaseStrategy.
    """

    @staticmethod
    def load_from_yaml_string(yaml_content: str) -> ComposableStrategy:
        raw = yaml.safe_load(yaml_content)
        if not isinstance(raw, dict):
            raise ValueError("YAML strategy content must be a dictionary / mapping.")

        cfg = dict(raw)
        # Normalize entry_filters to entry_rules
        if "entry_filters" in cfg and "entry_rules" not in cfg:
            cfg["entry_rules"] = cfg["entry_filters"]

        # Merge risk_params into top-level if present
        risk_params = cfg.get("risk_params", {})
        if isinstance(risk_params, dict):
            for k, v in risk_params.items():
                if k not in cfg:
                    cfg[k] = v

        name = cfg.get("name", "YAML Composed Strategy")
        return ComposableStrategy(name=name, config=cfg)

    @staticmethod
    def load_from_yaml_file(file_path: Union[str, Path]) -> ComposableStrategy:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Strategy YAML file not found: {file_path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return YamlStrategyLoader.load_from_yaml_string(content)


__all__ = ["ComposableStrategy", "YamlStrategyLoader", "RuleCondition", "RuleAction", "RuleNode"]

