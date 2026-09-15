"""
tests/test_ohlc_resampler.py — Tests for tick-to-candle resampler.
"""

import pandas as pd
import numpy as np
import pytest
from data.ohlc_resampler import resample_ticks_to_ohlc


def test_resample_ticks_to_ohlc_basic():
    ticks = pd.DataFrame({
        "tick_time": [
            "2026-09-02 09:30:05",
            "2026-09-02 09:30:15",
            "2026-09-02 09:30:45",
            "2026-09-02 09:31:10",
            "2026-09-02 09:31:30"
        ],
        "ltp": [100.0, 105.0, 98.0, 102.0, 107.0],
        "volume": [10, 25, 40, 60, 90],
        "atp": [100.0, 101.5, 100.5, 101.0, 102.0],
        "bid_ask_spread": [0.1, 0.2, 0.1, 0.15, 0.2],
        "depth_imbalance": [0.1, -0.2, 0.0, 0.3, -0.1]
    })

    res = resample_ticks_to_ohlc(ticks, timeframe="1min")
    assert len(res) == 2
    assert "open" in res.columns
    assert "close" in res.columns

    # Bar 1 (09:30:00)
    bar1 = res.iloc[0]
    assert bar1["open"] == 100.0
    assert bar1["high"] == 105.0
    assert bar1["low"] == 98.0
    assert bar1["close"] == 98.0
    assert bar1["volume"] == 30  # 40 - 10

    # Bar 2 (09:31:00)
    bar2 = res.iloc[1]
    assert bar2["open"] == 102.0
    assert bar2["high"] == 107.0
    assert bar2["low"] == 102.0
    assert bar2["close"] == 107.0
