"""
tests/test_math_engine.py — Unit tests for hardware acceleration and vectorized indicators.
"""

import numpy as np
import pytest
from math_engine import MathEngine, is_gpu_available, get_array_module


def test_hardware_detection():
    has_gpu = is_gpu_available()
    assert isinstance(has_gpu, bool)
    xp = get_array_module(use_gpu=False)
    assert xp is np


def test_vectorized_moving_averages():
    me = MathEngine(use_gpu=False)
    prices = np.array([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0])

    sma5 = me.sma(prices, 5)
    assert np.isnan(sma5[3])
    assert pytest.approx(sma5[4], 0.01) == 12.0
    assert pytest.approx(sma5[-1], 0.01) == 17.0

    ema5 = me.ema(prices, 5)
    assert np.isnan(ema5[3])
    assert pytest.approx(ema5[4], 0.01) == 12.0
    assert not np.isnan(ema5[-1])


def test_vectorized_rsi():
    me = MathEngine(use_gpu=False)
    # Monotonically increasing prices -> RSI should approach 100
    prices = np.linspace(100, 200, 30)
    rsi14 = me.rsi(prices, 14)
    assert np.isnan(rsi14[13])
    assert pytest.approx(rsi14[-1], 0.01) == 100.0


def test_vectorized_supertrend():
    me = MathEngine(use_gpu=False)
    highs = np.linspace(102, 202, 30)
    lows = np.linspace(98, 198, 30)
    closes = np.linspace(100, 200, 30)

    st, direction = me.supertrend(highs, lows, closes, period=10, multiplier=3.0)
    assert len(st) == 30
    assert len(direction) == 30
    # In a pure uptrend, direction should be 1
    assert direction[-1] == 1


def test_vectorized_vwap_and_atr():
    me = MathEngine(use_gpu=False)
    highs = np.array([105.0, 110.0, 115.0, 112.0, 118.0])
    lows = np.array([95.0, 100.0, 105.0, 102.0, 108.0])
    closes = np.array([100.0, 105.0, 110.0, 108.0, 115.0])
    volumes = np.array([1000.0, 1500.0, 2000.0, 1200.0, 1800.0])

    vwap_vals = me.vwap(highs, lows, closes, volumes)
    assert len(vwap_vals) == 5
    assert not np.any(np.isnan(vwap_vals))

    atr_vals = me.atr(highs, lows, closes, period=3)
    assert len(atr_vals) == 5
    assert not np.isnan(atr_vals[-1])


def test_candle_anatomy():
    me = MathEngine(use_gpu=False)
    opens = np.array([100.0])
    highs = np.array([110.0])
    lows = np.array([90.0])
    closes = np.array([105.0])

    body_ratio = me.candle_body_ratio(opens, highs, lows, closes)[0]
    upper_wick = me.upper_wick_ratio(opens, highs, lows, closes)[0]
    lower_wick = me.lower_wick_ratio(opens, highs, lows, closes)[0]

    # Total range = 20, body = 5 (ratio = 0.25)
    assert pytest.approx(body_ratio, 0.01) == 0.25
    # Upper wick = 110 - 105 = 5 (ratio = 0.25)
    assert pytest.approx(upper_wick, 0.01) == 0.25
    # Lower wick = 100 - 90 = 10 (ratio = 0.50)
    assert pytest.approx(lower_wick, 0.01) == 0.50


def test_compute_custom_indicator_dispatch():
    me = MathEngine(use_gpu=False)
    data = {
        "closes": np.linspace(100, 150, 30),
        "highs": np.linspace(105, 155, 30),
        "lows": np.linspace(95, 145, 30),
        "opens": np.linspace(98, 148, 30),
        "volumes": np.full(30, 1000.0),
    }

    rsi = me.compute_custom_indicator("rsi", {"period": 14}, data)
    assert len(rsi) == 30

    st = me.compute_custom_indicator("supertrend", {"period": 10, "multiplier": 3.0}, data)
    assert len(st) == 30
