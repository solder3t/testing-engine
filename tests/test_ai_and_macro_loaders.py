"""
tests/test_ai_and_macro_loaders.py — Verification of NseDataLoader, OnlineAIEngine, and LocalAIEngine.
"""

import tempfile
import os
import pytest
from data.nse_macro_loader import NseDataLoader
from strategies.builtin.ai.online_ai import OnlineAIEngine
from strategies.builtin.ai.local_ai import LocalAIEngine
from strategies.signal import Signal


def test_nse_data_loader_structure():
    """Verify NseDataLoader initializes paths and scans available dates."""
    loader = NseDataLoader()
    assert loader.base_dir
    assert loader.daily_dir
    dates = loader.get_available_dates()
    assert isinstance(dates, list)


def test_nse_data_loader_csv_parsing():
    """Verify NseDataLoader parses CSV rows cleanly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create synthetic market day folder
        day_dir = os.path.join(tmp_dir, "nse_scrapper", "NSE_Database", "daily", "2024-05-15", "market")
        os.makedirs(day_dir, exist_ok=True)

        # Write dummy bhavcopy
        bhav_path = os.path.join(day_dir, "bhavcopy.csv")
        with open(bhav_path, "w", encoding="utf-8") as f:
            f.write("SYMBOL,SERIES,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE,PREV_CLOSE,TTL_TRD_QNTY\n")
            f.write("RELIANCE,EQ,2800.0,2850.0,2790.0,2840.0,2795.0,150000\n")
            f.write("TCS,EQ,3800.0,3850.0,3790.0,3820.0,3800.0,80000\n")

        loader = NseDataLoader(base_dir=tmp_dir)
        dates = loader.get_available_dates()
        assert dates == ["2024-05-15"]

        bhav = loader.load_bhavcopy("2024-05-15")
        assert "RELIANCE" in bhav
        assert bhav["RELIANCE"]["close"] == 2840.0
        assert bhav["RELIANCE"]["volume"] == 150000


def test_online_ai_signal_parsing():
    """Verify OnlineAIEngine markdown extraction and signal schema creation."""
    engine = OnlineAIEngine(api_key="test_key")
    raw_markdown = """```json
    {
      "action": "ENTER",
      "market_bias": "CALL",
      "option_type": "CE",
      "strike": 24500.0,
      "stop_loss": 15.0,
      "target": 35.0,
      "confidence": 0.88,
      "reasoning": "Breakout above VWAP with high institutional volume"
    }
    ```"""
    parsed = engine._extract_json(raw_markdown)
    sig = engine._parse_json_to_signal(parsed)
    assert isinstance(sig, Signal)
    assert sig.action == "ENTER"
    assert sig.option_type == "CE"
    assert sig.strike == 24500.0
    assert sig.confidence == 0.88


def test_local_ai_signal_parsing():
    """Verify LocalAIEngine handles json response and creates Signal."""
    engine = LocalAIEngine()
    dummy_resp = {
        "action": "WAIT",
        "market_bias": "NEUTRAL",
        "option_type": "CE",
        "strike": 0.0,
        "stop_loss": 10.0,
        "target": 20.0,
        "confidence": 0.5,
        "reasoning": "Market consolidating within range"
    }
    sig = engine._parse_json_to_signal(dummy_resp)
    assert isinstance(sig, Signal)
    assert sig.action == "WAIT"
    assert sig.market_bias == "NEUTRAL"
