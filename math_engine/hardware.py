"""
math_engine/hardware.py — Hardware Acceleration and CuPy/NumPy Array Abstraction.

Detects NVIDIA RTX CUDA GPU availability via CuPy, providing transparent fallback
to high-performance vectorized NumPy on CPU.
"""

import warnings
from typing import Any
import numpy as np

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=UserWarning, module=r"cupy.*")
    try:
        import cupy as cp  # type: ignore
        _GPU_AVAILABLE = bool(cp.cuda.is_available()) if hasattr(cp, "cuda") else True
    except Exception:
        cp = None
        _GPU_AVAILABLE = False


def is_gpu_available() -> bool:
    """Returns True if CuPy and a compatible NVIDIA CUDA GPU are available."""
    return _GPU_AVAILABLE


def get_array_module(use_gpu: bool = False):
    """Returns cupy if use_gpu is True and GPU is available, else numpy."""
    if use_gpu and _GPU_AVAILABLE and cp is not None:
        return cp
    return np


def to_cpu(arr: Any) -> np.ndarray:
    """Converts a CuPy or NumPy array into a standard CPU NumPy ndarray."""
    if arr is None:
        return np.array([])
    if hasattr(arr, "get"):
        return arr.get()
    return np.asarray(arr)


def to_device(arr: Any, use_gpu: bool = False) -> Any:
    """Transfers array to active hardware device (GPU or CPU)."""
    xp = get_array_module(use_gpu)
    return xp.asarray(arr, dtype=xp.float64)
