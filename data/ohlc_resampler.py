"""
data/ohlc_resampler.py — High-Performance Tick-to-OHLC Resampler.

Converts second-by-second raw ticks from equities.db and indices.db
into synchronized 1-minute, 5-minute, and 15-minute OHLCV candle series.
"""

import pandas as pd
import numpy as np
from typing import Optional


def resample_ticks_to_ohlc(
    df_ticks: pd.DataFrame,
    timeframe: str = "1min",
    fill_gaps: bool = False
) -> pd.DataFrame:
    """
    Resamples a tick DataFrame into standard OHLCV candles.

    Args:
        df_ticks: DataFrame with at least 'tick_time' and 'ltp'.
                  Optional columns: 'volume', 'atp', 'bid_ask_spread', 'depth_imbalance'.
        timeframe: Pandas offset string, e.g. '1min', '5min', '15min'.
        fill_gaps: If True, forward-fills close price into empty minutes.

    Returns:
        DataFrame indexed by timestamp with columns:
        ['open', 'high', 'low', 'close', 'volume', 'vwap', 'bid_ask_spread', 'depth_imbalance']
    """
    if df_ticks.empty or "ltp" not in df_ticks.columns:
        return pd.DataFrame()

    df = df_ticks.copy()
    if "tick_time" in df.columns:
        df["timestamp"] = pd.to_datetime(df["tick_time"])
    elif "timestamp" not in df.columns:
        return pd.DataFrame()

    df = df.sort_values("timestamp").set_index("timestamp")

    # OHLC from LTP
    resampled = df["ltp"].resample(timeframe).ohlc()
    resampled.dropna(subset=["close"], inplace=True)

    if resampled.empty:
        return pd.DataFrame()

    # Volume: if cumulative volume is present, delta across bar; else count / trade qty
    if "volume" in df.columns:
        # Check if volume is cumulative or per-tick
        vol_max = df["volume"].resample(timeframe).max()
        vol_min = df["volume"].resample(timeframe).min()
        vol_delta = (vol_max - vol_min).clip(lower=0)
        # If delta is 0 throughout (e.g. indices), fallback to last trade qty or 0
        if vol_delta.sum() == 0 and "last_traded_qty" in df.columns:
            resampled["volume"] = df["last_traded_qty"].resample(timeframe).sum()
        else:
            resampled["volume"] = vol_delta
    elif "last_traded_qty" in df.columns:
        resampled["volume"] = df["last_traded_qty"].resample(timeframe).sum()
    else:
        resampled["volume"] = 0

    # VWAP / ATP
    if "atp" in df.columns:
        resampled["vwap"] = df["atp"].resample(timeframe).last()
        # Fallback to close if ATP is 0 (as in some early ticks)
        resampled["vwap"] = np.where(resampled["vwap"] > 0, resampled["vwap"], resampled["close"])
    else:
        resampled["vwap"] = resampled["close"]

    # Bid-Ask spread & depth imbalance
    if "bid_ask_spread" in df.columns:
        resampled["bid_ask_spread"] = df["bid_ask_spread"].resample(timeframe).mean()
    else:
        resampled["bid_ask_spread"] = 0.0

    if "depth_imbalance" in df.columns:
        resampled["depth_imbalance"] = df["depth_imbalance"].resample(timeframe).mean()
    else:
        resampled["depth_imbalance"] = 0.0

    if fill_gaps:
        resampled = resampled.asfreq(timeframe)
        resampled["close"] = resampled["close"].ffill()
        resampled["open"] = resampled["open"].fillna(resampled["close"])
        resampled["high"] = resampled["high"].fillna(resampled["close"])
        resampled["low"] = resampled["low"].fillna(resampled["close"])
        resampled["volume"] = resampled["volume"].fillna(0)
        resampled["vwap"] = resampled["vwap"].ffill()
        resampled["bid_ask_spread"] = resampled["bid_ask_spread"].fillna(0)
        resampled["depth_imbalance"] = resampled["depth_imbalance"].fillna(0)

    return resampled.reset_index()
