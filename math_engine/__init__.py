"""
math_engine — Hardware-Accelerated Vectorized Indicator & Quantitative Math Core.
"""

from .hardware import is_gpu_available, get_array_module
from .indicator_engine import MathEngine, IndicatorEngine

__all__ = [
    "is_gpu_available",
    "get_array_module",
    "MathEngine",
    "IndicatorEngine",
]
