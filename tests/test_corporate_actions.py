"""
tests/test_corporate_actions.py — Tests for historical corporate actions and price adjustment.
"""

import pandas as pd
import pytest
from data.corporate_actions import CorporateActionsManager, get_adjustment_factor, adjust_equity_ohlc


def test_corporate_actions_adjustment_factor():
    # RELIANCE has bonuses on 2017_09_07 (1:1) and 2024_10_28 (1:1)
    # After 2024_10_28 -> factor = 1.0
    factor_recent = get_adjustment_factor("RELIANCE", "2026_09_11")
    assert factor_recent == 1.0

    # Between 2017_09_07 and 2024_10_28 -> factor = 0.5 (only 2024 bonus applies)
    factor_mid = get_adjustment_factor("RELIANCE", "2023_01_01")
    assert factor_mid == 0.5

    # Prior to 2017_09_07 -> factor = 0.5 * 0.5 = 0.25
    factor_early = get_adjustment_factor("RELIANCE", "2016_01_01")
    assert factor_early == 0.25

    # HDFCBANK split on 2019_09_19 (1:2)
    # Prior to split date:
    factor_hdfc_pre = get_adjustment_factor("HDFCBANK", "2018_01_01")
    assert factor_hdfc_pre == 0.5

    # After split date:
    factor_hdfc_post = get_adjustment_factor("HDFCBANK", "2021_01_01")
    assert factor_hdfc_post == 1.0

    # Date normalization with hyphen
    factor_hyphen = get_adjustment_factor("HDFCBANK", "2018-01-01")
    assert factor_hyphen == 0.5


def test_corporate_actions_adjust_dataframe():
    df = pd.DataFrame({
        "open": [1000.0, 1020.0],
        "high": [1050.0, 1060.0],
        "low": [990.0, 1010.0],
        "close": [1040.0, 1030.0],
        "volume": [10000, 20000]
    })

    # Adjust by factor 0.5 (e.g. 1:2 split or 1:1 bonus)
    adjusted = CorporateActionsManager.adjust_dataframe(df, 0.5)

    assert adjusted["open"].iloc[0] == 500.0
    assert adjusted["high"].iloc[0] == 525.0
    assert adjusted["low"].iloc[0] == 495.0
    assert adjusted["close"].iloc[0] == 520.0
    assert adjusted["volume"].iloc[0] == 20000  # Volume multiplied by 2 (divided by 0.5)

    # Factor 1.0 returns unchanged
    noop = CorporateActionsManager.adjust_dataframe(df, 1.0)
    assert noop["close"].iloc[0] == 1040.0
