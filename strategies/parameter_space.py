"""
strategies/parameter_space.py — Parameter definitions and search space configuration.
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field


@dataclass
class Parameter:
    """Definition of a strategy parameter."""
    name: str
    param_type: str  # "int", "float", "str", "bool", "choice"
    default: Any
    min_val: Optional[Union[int, float]] = None
    max_val: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None
    choices: Optional[List[Any]] = None
    description: str = ""

    def validate(self, value: Any) -> Any:
        """Validate and cast a value to the correct type and bounds."""
        if self.param_type == "int":
            v = int(value)
            if self.min_val is not None:
                v = max(int(self.min_val), v)
            if self.max_val is not None:
                v = min(int(self.max_val), v)
            return v
        elif self.param_type == "float":
            v = float(value)
            if self.min_val is not None:
                v = max(float(self.min_val), v)
            if self.max_val is not None:
                v = min(float(self.max_val), v)
            return v
        elif self.param_type == "bool":
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        elif self.param_type == "choice":
            if self.choices and value not in self.choices:
                return self.default
            return value
        return str(value)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for frontend dashboard."""
        return {
            "name": self.name,
            "type": self.param_type,
            "default": self.default,
            "min": self.min_val,
            "max": self.max_val,
            "step": self.step,
            "choices": self.choices,
            "description": self.description
        }


@dataclass
class ParameterSpace:
    """Collection of parameters with search grid generation capabilities."""
    parameters: Dict[str, Parameter] = field(default_factory=dict)

    def add(self, param: Parameter) -> "ParameterSpace":
        self.parameters[param.name] = param
        return self

    def get_defaults(self) -> Dict[str, Any]:
        return {name: p.default for name, p in self.parameters.items()}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize parameter definitions for frontend dashboard."""
        return {name: p.to_dict() for name, p in self.parameters.items()}

    def validate_all(self, values: Dict[str, Any]) -> Dict[str, Any]:
        validated = {}
        for name, param in self.parameters.items():
            val = values.get(name, param.default)
            validated[name] = param.validate(val)
        return validated

    def generate_grid(self, max_combinations: int = 25) -> List[Dict[str, Any]]:
        """Generate a representative grid of parameter combinations."""
        import itertools
        grid_axes = {}
        for name, p in self.parameters.items():
            if p.param_type == "choice" and p.choices:
                grid_axes[name] = p.choices[:3]
            elif p.param_type == "bool":
                grid_axes[name] = [False, True]
            elif p.param_type in ("int", "float") and p.min_val is not None and p.max_val is not None:
                vals = sorted(list(set([p.min_val, p.default, p.max_val])))
                grid_axes[name] = vals
            else:
                grid_axes[name] = [p.default]

        keys = list(grid_axes.keys())
        combos = []
        for prod in itertools.product(*[grid_axes[k] for k in keys]):
            combos.append(dict(zip(keys, prod)))
            if len(combos) >= max_combinations:
                break
        return combos
