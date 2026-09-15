import pandas as pd
import numpy as np


def calculate_ema(series, period):
    """Calculates Exponential Moving Average (EMA)."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series, period=14):
    """Calculates Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's smoothing technique for average gain and loss
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    # Avoid division by zero
    rs = np.where(avg_loss == 0, np.nan, avg_gain / avg_loss)
    rsi_vals = 100 - (100 / (1 + rs))

    # For initial values where avg_loss is 0 (or nan)
    rsi_vals = np.where(avg_loss == 0, 100.0, rsi_vals)

    return pd.Series(rsi_vals, index=series.index)


def calculate_atr(df, period=14):
    """Calculates Average True Range (ATR)."""
    high = df['high']
    low = df['low']
    close_prev = df['close'].shift(1)

    tr = pd.concat([
        high - low,
        (high - close_prev).abs(),
        (low - close_prev).abs()
    ], axis=1).max(axis=1)

    return tr.ewm(span=period, adjust=False).mean()


def calculate_camarilla_pivots(high_prev, low_prev, close_prev):
    """Calculates Camarilla Pivot Points for support/resistance."""
    tr = high_prev - low_prev
    r4 = close_prev + tr * 1.1 / 2
    r3 = close_prev + tr * 1.1 / 4
    s3 = close_prev - tr * 1.1 / 4
    s4 = close_prev - tr * 1.1 / 2
    p = (high_prev + low_prev + close_prev) / 3
    return {
        "P": p,
        "R3": r3,
        "R4": r4,
        "S3": s3,
        "S4": s4
    }


def calculate_cpr(high_prev, low_prev, close_prev):
    """Calculates Central Pivot Range (CPR)."""
    p = (high_prev + low_prev + close_prev) / 3
    bc = (high_prev + low_prev) / 2
    tc = (p - bc) + p

    # Ensure TC is top central and BC is bottom central
    tc_final = max(tc, bc)
    bc_final = min(tc, bc)

    return {
        "P": p,
        "TC": tc_final,
        "BC": bc_final
    }


def calculate_macd(series, fast=12, slow=26, signal=9):
    """Calculates MACD line, signal line, and histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram
    })


def calculate_vwap(df):
    """Calculates intraday Volume-Weighted Average Price (VWAP).
    Requires 'high', 'low', 'close', and 'volume' columns.
    Falls back to a simple SMA of close if volume is unavailable.
    """
    if "volume" in df.columns and df["volume"].sum() > 0:
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
        return vwap
    # Graceful fallback: 20-period SMA of close
    return df["close"].rolling(window=20, min_periods=1).mean()


def calculate_rr_ratio(entry, stop_loss, target):
    """Calculates Risk:Reward ratio. Returns 0 if risk is zero."""
    risk = abs(entry - stop_loss)
    reward = abs(target - entry)
    if risk == 0:
        return 0.0
    return round(reward / risk, 2)


def calculate_bollinger_bands(series, period=20, std_dev=2.0):
    """Calculates Bollinger Bands.

    Returns a DataFrame with:
    - upper: Upper band (SMA + 2*SD)
    - middle: Middle band (SMA)
    - lower: Lower band (SMA - 2*SD)
    - percent_b: %B position of price within bands (0=lower, 0.5=middle, 1=upper)
    - bandwidth: Band width as % of middle band (squeeze detector — low = compression)
    """
    sma = series.rolling(window=period, min_periods=1).mean()
    std = series.rolling(window=period, min_periods=1).std().fillna(0)

    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)

    band_range = (upper - lower).replace(0, np.nan)
    percent_b = (series - lower) / band_range
    bandwidth = (band_range / sma) * 100

    return pd.DataFrame({
        "upper":     upper,
        "middle":    sma,
        "lower":     lower,
        "percent_b": percent_b.fillna(0.5),
        "bandwidth": bandwidth.fillna(0)
    })


def calculate_supertrend(df, period=10, multiplier=3.0):
    """Calculates Supertrend indicator.

    Returns a DataFrame with:
    - supertrend: The trailing stop level
    - direction:  +1 = bullish (price above supertrend), -1 = bearish
    - just_flipped: True if direction changed on the last bar (strong signal)
    """
    atr = calculate_atr(df, period)
    hl_avg = (df['high'] + df['low']) / 2

    basic_upper = (hl_avg + multiplier * atr).values
    basic_lower = (hl_avg - multiplier * atr).values
    close = df['close'].values
    n = len(df)

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend = np.full(n, np.nan)
    direction = np.zeros(n, dtype=int)

    # Initialise first bar
    supertrend[0] = basic_upper[0]
    direction[0] = -1

    for i in range(1, n):
        # Lower band: can only rise, never fall
        final_lower[i] = (
            basic_lower[i]
            if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]
            else final_lower[i - 1]
        )
        # Upper band: can only fall, never rise
        final_upper[i] = (
            basic_upper[i]
            if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]
            else final_upper[i - 1]
        )

        # Direction logic
        prev_st = supertrend[i - 1]
        if prev_st == final_upper[i - 1]:
            direction[i] = 1 if close[i] > final_upper[i] else -1
        else:
            direction[i] = -1 if close[i] < final_lower[i] else 1

        supertrend[i] = final_lower[i] if direction[i] == 1 else final_upper[i]

    # Detect direction flip on the last bar
    just_flipped = bool(n > 1 and direction[-1] != direction[-2])

    return pd.DataFrame({
        "supertrend":   supertrend,
        "direction":    direction,
        "just_flipped": [False] * (n - 1) + [just_flipped]
    }, index=df.index)


def calculate_volume_ratio(df: 'pd.DataFrame', period: int = 20) -> float:
    """
    Returns the ratio of the latest bar's volume to the N-period average volume.
    Values > 1.5 indicate above-average participation (confirmation signal).
    Returns 1.0 if volume data is absent or insufficient.
    """
    import pandas as pd
    if 'volume' not in df.columns or len(df) < 2:
        return 1.0
    vol = df['volume'].dropna()
    if len(vol) < 2:
        return 1.0
    avg = vol.iloc[-min(period, len(vol)):-1].mean()
    if avg == 0:
        return 1.0
    return round(float(vol.iloc[-1]) / avg, 3)


def detect_price_anomalies(
    df: 'pd.DataFrame',
    zscore_thresh: float = 2.5,
    vol_spike_mult: float = 3.0,
    window: int = 20,
) -> dict:
    """
    Detect statistically unusual price moves and volume spikes.
    Ported from live_converter.py._detect_anomalies (polars → pandas).

    Methodology:
      - Compute rolling 20-bar Z-score on tick-to-tick price moves.
      - Flag bars where |Z| > zscore_thresh OR volume > vol_spike_mult × avg volume.

    Returns a dict with:
      - anomaly_count (int): number of anomalous bars in the series
      - latest_zscore (float): Z-score of the most recent price move
      - latest_is_anomaly (bool): whether the latest bar is anomalous
      - vol_spike (bool): whether the latest bar has a volume spike
    """
    result = {
        "anomaly_count":    0,
        "latest_zscore":    0.0,
        "latest_is_anomaly": False,
        "vol_spike":        False,
    }
    if df.empty or 'close' not in df.columns or len(df) < window:
        return result

    # Price-move Z-score
    moves = df['close'].diff()
    roll_mean = moves.rolling(window=window, min_periods=window).mean()
    roll_std  = moves.rolling(window=window, min_periods=window).std().replace(0, np.nan)
    z_scores  = (moves - roll_mean) / roll_std
    z_scores  = z_scores.fillna(0.0)

    price_anom = z_scores.abs() > zscore_thresh

    # Volume spike flag (optional — if volume column exists)
    vol_anom = pd.Series(False, index=df.index)
    if 'volume' in df.columns:
        vol = df['volume'].fillna(0)
        vol_mean = vol.rolling(window=window, min_periods=window).mean()
        vol_anom = (vol > vol_mean * vol_spike_mult) & (vol_mean > 0)

    combined = price_anom | vol_anom

    result["anomaly_count"]     = int(combined.sum())
    result["latest_zscore"]     = round(float(z_scores.iloc[-1]), 3)
    result["latest_is_anomaly"] = bool(combined.iloc[-1])
    result["vol_spike"]         = bool(vol_anom.iloc[-1]) if 'volume' in df.columns else False

    return result


def calculate_stochastic_rsi(
    series: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> pd.DataFrame:
    """
    Stochastic RSI — oscillates between 0 and 1.

    Useful as a secondary filter: StochRSI-K > 0.8 = overbought,
    StochRSI-K < 0.2 = oversold.

    Formula:
        RSI → rolling (rsi_period) RSI
        StochRSI = (RSI − min(RSI, stoch_period)) / (max − min)
        K = SMA(StochRSI, smooth_k)
        D = SMA(K, smooth_d)

    Returns a DataFrame with columns:
        stoch_rsi   — raw StochRSI (0–1)
        k           — smoothed %K  (0–1)
        d           — signal line %D (0–1)
    """
    rsi = calculate_rsi(series, rsi_period)

    rsi_min  = rsi.rolling(window=stoch_period, min_periods=1).min()
    rsi_max  = rsi.rolling(window=stoch_period, min_periods=1).max()
    rsi_rng  = (rsi_max - rsi_min).replace(0, np.nan)
    stoch    = (rsi - rsi_min) / rsi_rng
    stoch    = stoch.fillna(0.5)   # mid-point when range is zero

    k = stoch.rolling(window=smooth_k, min_periods=1).mean()
    d = k.rolling(window=smooth_d, min_periods=1).mean()

    return pd.DataFrame({
        "stoch_rsi": stoch.round(4),
        "k":         k.round(4),
        "d":         d.round(4),
    }, index=series.index)


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Average Directional Index (ADX) with +DI and -DI lines.

    Uses Wilder's smoothing (same method as ATR) for consistency.

    Returns a DataFrame with columns:
        adx      — trend strength (0–100). ≥ 25 = trending; < 25 = ranging/sideways.
        plus_di  — positive directional indicator (+DI)
        minus_di — negative directional indicator (-DI)

    Interpretation:
        ADX ≥ 25 + (+DI > -DI)  → strong uptrend
        ADX ≥ 25 + (-DI > +DI)  → strong downtrend
        ADX < 25                 → choppy/ranging — momentum signals unreliable
        ADX rising               → trend strengthening
        ADX falling              → trend weakening

    Requires at least (period * 2) bars for meaningful output.
    """
    if df.empty or len(df) < period + 1:
        empty = pd.Series(np.nan, index=df.index)
        return pd.DataFrame({"adx": empty, "plus_di": empty, "minus_di": empty})

    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    # ── True Range ────────────────────────────────────────────────────────────
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)

    # ── Directional Movement ──────────────────────────────────────────────────
    up_move   = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move,   0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm_s  = pd.Series(plus_dm,  index=df.index)
    minus_dm_s = pd.Series(minus_dm, index=df.index)

    # ── Wilder's smoothing (equivalent to ewm with com = period-1) ────────────
    tr_smooth       = tr.ewm(com=period - 1, adjust=False).mean()
    plus_dm_smooth  = plus_dm_s.ewm(com=period - 1, adjust=False).mean()
    minus_dm_smooth = minus_dm_s.ewm(com=period - 1, adjust=False).mean()

    # ── Directional Indicators ────────────────────────────────────────────────
    plus_di  = 100 * plus_dm_smooth  / tr_smooth.replace(0, np.nan)
    minus_di = 100 * minus_dm_smooth / tr_smooth.replace(0, np.nan)

    # ── DX and ADX ────────────────────────────────────────────────────────────
    di_sum  = (plus_di + minus_di).replace(0, np.nan)
    dx      = 100 * (plus_di - minus_di).abs() / di_sum
    adx     = dx.ewm(com=period - 1, adjust=False).mean()

    return pd.DataFrame({
        "adx":      adx.round(2).fillna(0),
        "plus_di":  plus_di.round(2).fillna(0),
        "minus_di": minus_di.round(2).fillna(0),
    }, index=df.index)
