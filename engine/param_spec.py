"""
engine/param_spec.py — Declarative Parameter Specification & Grid Generator.

Enables type-safe, validated strategy parameter definitions with automatic
grid generation, coarse-to-fine step sizing, and parameter validation.
"""

from dataclasses import dataclass, field
import itertools
import random
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union


@dataclass
class ParamSpec:
    """Specification for a single optimizable strategy parameter."""
    name: str
    param_type: str  # "int", "float", "categorical", "bool"
    default: Any
    min_val: Optional[Union[int, float]] = None
    max_val: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None
    choices: Optional[List[Any]] = None
    description: str = ""

    def __post_init__(self):
        self.param_type = self.param_type.lower()
        if self.param_type in ("int", "float"):
            if self.min_val is not None and self.max_val is not None:
                if self.min_val > self.max_val:
                    raise ValueError(f"ParamSpec {self.name}: min_val {self.min_val} > max_val {self.max_val}")
        elif self.param_type == "categorical":
            if not self.choices:
                raise ValueError(f"ParamSpec {self.name}: categorical requires non-empty choices")
        elif self.param_type == "bool":
            self.choices = [True, False]

    def generate_values(self, coarse: bool = False) -> List[Any]:
        """Generates list of test values. If coarse=True, uses doubled step size or reduced set."""
        if self.param_type == "categorical" or self.param_type == "bool":
            return list(self.choices or [self.default])

        if self.min_val is None or self.max_val is None:
            return [self.default]

        effective_step = self.step
        if effective_step is None:
            effective_step = 1 if self.param_type == "int" else (self.max_val - self.min_val) / 5.0

        if coarse:
            effective_step = effective_step * 2

        vals = []
        curr = float(self.min_val)
        max_f = float(self.max_val)
        while curr <= max_f + 1e-9:
            if self.param_type == "int":
                v = int(round(curr))
            else:
                v = round(curr, 6)
            if v not in vals:
                vals.append(v)
            curr += float(effective_step)

        if not vals:
            vals = [self.default]
        return vals

    def validate(self, val: Any) -> bool:
        """Validates if value satisfies type and boundary constraints."""
        if self.param_type == "int":
            if not isinstance(val, (int, float)) or int(val) != val:
                return False
            if self.min_val is not None and val < self.min_val:
                return False
            if self.max_val is not None and val > self.max_val:
                return False
            return True
        elif self.param_type == "float":
            if not isinstance(val, (int, float)):
                return False
            if self.min_val is not None and val < self.min_val:
                return False
            if self.max_val is not None and val > self.max_val:
                return False
            return True
        elif self.param_type in ("categorical", "bool"):
            return val in (self.choices or [])
        return True


class ParamGrid:
    """Collection of ParamSpecs representing an optimization search space."""

    def __init__(self, specs: Sequence[ParamSpec]):
        self.specs: Dict[str, ParamSpec] = {s.name: s for s in specs}

    def total_combinations(self, coarse: bool = False) -> int:
        """Calculates total number of permutations."""
        total = 1
        for s in self.specs.values():
            total *= len(s.generate_values(coarse=coarse))
        return total

    def generate_all(self, coarse: bool = False) -> List[Dict[str, Any]]:
        """Generates all combinations as list of dictionaries."""
        keys = list(self.specs.keys())
        value_lists = [self.specs[k].generate_values(coarse=coarse) for k in keys]
        
        combinations = []
        for combo in itertools.product(*value_lists):
            combinations.append(dict(zip(keys, combo)))
        return combinations

    def generate_random_sample(self, n: int, seed: Optional[int] = 42) -> List[Dict[str, Any]]:
        """Generates a random sample of N combinations."""
        all_combos = self.generate_all(coarse=False)
        if len(all_combos) <= n:
            return all_combos
        rng = random.Random(seed)
        return rng.sample(all_combos, n)

    def get_defaults(self) -> Dict[str, Any]:
        """Returns dictionary of default parameter values."""
        return {s.name: s.default for s in self.specs.values()}
