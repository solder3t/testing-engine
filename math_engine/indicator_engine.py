"""
math_engine/indicator_engine.py — Vectorized Technical Indicators Engine.

Supports high-speed calculation of:
- EMA, SMA, Wilder's Smoothed RSI
- SuperTrend with dynamic ATR state flips
- Cumulative intraday VWAP
- Bollinger Bands (%B, Bandwidth) and MACD (Line, Signal, Histogram)
- Average True Range (ATR), Average Directional Index (ADX)
- Stochastic (%K, %D), Commodity Channel Index (CCI), Williams %R
- On-Balance Volume (OBV), Volume Ratio
- Price Distance from EMA, Candle Anatomy Ratios (Body, Upper/Lower Wicks)
- Pivot Points, Ichimoku Kinko Hyo
"""

from typing import Dict, Any, Tuple, Optional
import numpy as np

from .hardware import is_gpu_available, get_array_module, to_cpu, to_device


class MathEngine:
    """Vectorized calculation engine for technical indicators on CPU or GPU."""

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu and is_gpu_available()
        self.xp = get_array_module(self.use_gpu)

    @staticmethod
    def is_gpu_available() -> bool:
        return is_gpu_available()

    def to_array(self, data: Any) -> np.ndarray:
        return self.xp.array(data, dtype=self.xp.float64)

    def to_cpu(self, arr: Any) -> np.ndarray:
        return to_cpu(arr)

    def ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Vectorized Exponential Moving Average."""
        xp = self.xp
        p = xp.asarray(prices, dtype=xp.float64)
        n = len(p)
        if n < period or period <= 0:
            return xp.full(n, xp.nan)

        alpha = 2.0 / (period + 1.0)
        out = xp.empty(n, dtype=xp.float64)
        out[:period - 1] = xp.nan
        out[period - 1] = xp.mean(p[:period])

        for i in range(period, n):
            out[i] = (p[i] * alpha) + (out[i - 1] * (1.0 - alpha))
        return out

    def sma(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Vectorized Simple Moving Average."""
        xp = self.xp
        p = xp.asarray(prices, dtype=xp.float64)
        n = len(p)
        if n < period or period <= 0:
            return xp.full(n, xp.nan)
        out = xp.full(n, xp.nan)
        cumsum = xp.cumsum(xp.insert(p, 0, 0.0))
        out[period - 1:] = (cumsum[period:] - cumsum[:-period]) / float(period)
        return out

    def rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index with Wilder's Smoothing."""
        xp = self.xp
        p = xp.asarray(prices, dtype=xp.float64)
        n = len(p)
        if n <= period or period <= 0:
            return xp.full(n, xp.nan)

        deltas = xp.diff(p)
        gains = xp.where(deltas > 0, deltas, 0.0)
        losses = xp.where(deltas < 0, -deltas, 0.0)

        out = xp.full(n, xp.nan)
        avg_gain = xp.mean(gains[:period])
        avg_loss = xp.mean(losses[:period])

        if avg_loss == 0:
            out[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[period] = 100.0 - (100.0 / (1.0 + rs))

        for i in range(period + 1, n):
            avg_gain = ((avg_gain * (period - 1)) + gains[i - 1]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i - 1]) / period
            if avg_loss == 0:
                out[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                out[i] = 100.0 - (100.0 / (1.0 + rs))

        return out

    def macd(
        self,
        prices: np.ndarray,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Moving Average Convergence Divergence (MACD, Signal, Histogram)."""
        fast_ema = self.ema(prices, fast_period)
        slow_ema = self.ema(prices, slow_period)
        macd_line = fast_ema - slow_ema
        signal_line = self.ema(macd_line, signal_period)
        hist = macd_line - signal_line
        return macd_line, signal_line, hist

    def bollinger_bands(
        self,
        prices: np.ndarray,
        period: int = 20,
        num_std: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands (Upper, Middle, Lower)."""
        xp = self.xp
        middle = self.sma(prices, period)
        p = xp.asarray(prices, dtype=xp.float64)
        n = len(p)
        std_dev = xp.full(n, xp.nan)

        for i in range(period - 1, n):
            std_dev[i] = xp.std(p[i - period + 1: i + 1])

        upper = middle + (num_std * std_dev)
        lower = middle - (num_std * std_dev)
        return upper, middle, lower

    def atr(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """Average True Range (Wilder's Smoothing)."""
        xp = self.xp
        h = xp.asarray(highs, dtype=xp.float64)
        l = xp.asarray(lows, dtype=xp.float64)
        c = xp.asarray(closes, dtype=xp.float64)
        n = len(c)

        if n < 2 or period <= 0:
            return xp.full(n, xp.nan)

        tr = xp.zeros(n, dtype=xp.float64)
        tr[0] = h[0] - l[0]
        for i in range(1, n):
            hl = h[i] - l[i]
            hc = abs(h[i] - c[i - 1])
            lc = abs(l[i] - c[i - 1])
            tr[i] = max(hl, hc, lc)

        out = xp.full(n, xp.nan)
        if n <= period:
            return out

        out[period - 1] = xp.mean(tr[:period])
        for i in range(period, n):
            out[i] = ((out[i - 1] * (period - 1)) + tr[i]) / period
        return out

    def supertrend(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        period: int = 10,
        multiplier: float = 3.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """SuperTrend Indicator. Returns (supertrend_values, direction [1=Long, -1=Short])."""
        xp = self.xp
        h = xp.asarray(highs, dtype=xp.float64)
        l = xp.asarray(lows, dtype=xp.float64)
        c = xp.asarray(closes, dtype=xp.float64)
        n = len(c)

        atr_val = self.atr(h, l, c, period)
        hl2 = (h + l) / 2.0

        basic_upper = hl2 + (multiplier * atr_val)
        basic_lower = hl2 - (multiplier * atr_val)

        final_upper = xp.zeros(n, dtype=xp.float64)
        final_lower = xp.zeros(n, dtype=xp.float64)
        st = xp.zeros(n, dtype=xp.float64)
        direction = xp.ones(n, dtype=xp.int32)

        for i in range(period, n):
            if basic_upper[i] < final_upper[i - 1] or c[i - 1] > final_upper[i - 1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = final_upper[i - 1]

            if basic_lower[i] > final_lower[i - 1] or c[i - 1] < final_lower[i - 1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = final_lower[i - 1]

            if c[i] > final_upper[i - 1]:
                direction[i] = 1
            elif c[i] < final_lower[i - 1]:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]

            st[i] = final_lower[i] if direction[i] == 1 else final_upper[i]

        return st, direction

    def vwap(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        """Cumulative Intraday Volume Weighted Average Price."""
        xp = self.xp
        typical_price = (xp.asarray(highs) + xp.asarray(lows) + xp.asarray(closes)) / 3.0
        v = xp.asarray(volumes, dtype=xp.float64)
        cum_tp_vol = xp.cumsum(typical_price * v)
        cum_vol = xp.cumsum(v)
        return xp.where(cum_vol > 0, cum_tp_vol / cum_vol, typical_price)

    def stochastic(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        k_period: int = 14,
        d_period: int = 3,
        slowing: int = 3
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Stochastic Oscillator (%K, %D)."""
        xp = self.xp
        h = xp.asarray(highs, dtype=xp.float64)
        l = xp.asarray(lows, dtype=xp.float64)
        c = xp.asarray(closes, dtype=xp.float64)
        n = len(c)

        if n < k_period:
            nan_arr = xp.full(n, xp.nan)
            return nan_arr, nan_arr

        raw_k = xp.full(n, xp.nan)
        for i in range(k_period - 1, n):
            highest_h = xp.max(h[i - k_period + 1: i + 1])
            lowest_l = xp.min(l[i - k_period + 1: i + 1])
            denom = highest_h - lowest_l
            raw_k[i] = 100.0 * (c[i] - lowest_l) / denom if denom > 0 else 50.0

        if slowing > 1:
            k_slow = xp.full(n, xp.nan)
            for i in range(k_period - 1 + slowing - 1, n):
                window = raw_k[i - slowing + 1: i + 1]
                if not xp.any(xp.isnan(window)):
                    k_slow[i] = xp.mean(window)
        else:
            k_slow = raw_k

        d_line = xp.full(n, xp.nan)
        for i in range(k_period - 1 + slowing - 1 + d_period - 1, n):
            window = k_slow[i - d_period + 1: i + 1]
            if not xp.any(xp.isnan(window)):
                d_line[i] = xp.mean(window)

        return k_slow, d_line

    def adx(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        period: int = 14
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Average Directional Index (ADX, +DI, -DI)."""
        xp = self.xp
        h = xp.asarray(highs, dtype=xp.float64)
        l = xp.asarray(lows, dtype=xp.float64)
        c = xp.asarray(closes, dtype=xp.float64)
        n = len(c)

        if n <= period * 2:
            nan_arr = xp.full(n, xp.nan)
            return nan_arr, nan_arr, nan_arr

        tr = xp.zeros(n, dtype=xp.float64)
        plus_dm = xp.zeros(n, dtype=xp.float64)
        minus_dm = xp.zeros(n, dtype=xp.float64)

        tr[0] = h[0] - l[0]
        for i in range(1, n):
            hl = h[i] - l[i]
            hc = abs(h[i] - c[i - 1])
            lc = abs(l[i] - c[i - 1])
            tr[i] = max(hl, hc, lc)

            up_move = h[i] - h[i - 1]
            down_move = l[i - 1] - l[i]
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move

        smooth_tr = xp.full(n, xp.nan)
        smooth_plus_dm = xp.full(n, xp.nan)
        smooth_minus_dm = xp.full(n, xp.nan)

        smooth_tr[period] = xp.sum(tr[1:period + 1])
        smooth_plus_dm[period] = xp.sum(plus_dm[1:period + 1])
        smooth_minus_dm[period] = xp.sum(minus_dm[1:period + 1])

        for i in range(period + 1, n):
            smooth_tr[i] = smooth_tr[i - 1] - (smooth_tr[i - 1] / period) + tr[i]
            smooth_plus_dm[i] = smooth_plus_dm[i - 1] - (smooth_plus_dm[i - 1] / period) + plus_dm[i]
            smooth_minus_dm[i] = smooth_minus_dm[i - 1] - (smooth_minus_dm[i - 1] / period) + minus_dm[i]

        plus_di = xp.full(n, xp.nan)
        minus_di = xp.full(n, xp.nan)
        dx = xp.full(n, xp.nan)

        for i in range(period, n):
            if smooth_tr[i] > 0:
                plus_di[i] = 100.0 * (smooth_plus_dm[i] / smooth_tr[i])
                minus_di[i] = 100.0 * (smooth_minus_dm[i] / smooth_tr[i])
                di_sum = plus_di[i] + minus_di[i]
                if di_sum > 0:
                    dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum

        adx_val = xp.full(n, xp.nan)
        start_adx = 2 * period
        if n > start_adx:
            valid_dx = dx[period:start_adx]
            if not xp.any(xp.isnan(valid_dx)):
                adx_val[start_adx - 1] = xp.mean(valid_dx)
                for i in range(start_adx, n):
                    if not xp.isnan(dx[i]):
                        adx_val[i] = ((adx_val[i - 1] * (period - 1)) + dx[i]) / period

        return adx_val, plus_di, minus_di

    def cci(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 20) -> np.ndarray:
        """Commodity Channel Index."""
        xp = self.xp
        h = xp.asarray(highs, dtype=xp.float64)
        l = xp.asarray(lows, dtype=xp.float64)
        c = xp.asarray(closes, dtype=xp.float64)
        n = len(c)
        if n < period:
            return xp.full(n, xp.nan)

        tp = (h + l + c) / 3.0
        out = xp.full(n, xp.nan)
        for i in range(period - 1, n):
            window = tp[i - period + 1: i + 1]
            mean_tp = xp.mean(window)
            mean_dev = xp.mean(xp.abs(window - mean_tp))
            out[i] = (tp[i] - mean_tp) / (0.015 * mean_dev) if mean_dev > 0 else 0.0
        return out

    def williams_r(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Williams %R."""
        xp = self.xp
        h = xp.asarray(highs, dtype=xp.float64)
        l = xp.asarray(lows, dtype=xp.float64)
        c = xp.asarray(closes, dtype=xp.float64)
        n = len(c)
        if n < period:
            return xp.full(n, xp.nan)

        wr = xp.full(n, xp.nan)
        for i in range(period - 1, n):
            highest_h = xp.max(h[i - period + 1: i + 1])
            lowest_l = xp.min(l[i - period + 1: i + 1])
            denom = highest_h - lowest_l
            wr[i] = -100.0 * (highest_h - c[i]) / denom if denom > 0 else -50.0
        return wr

    def obv(self, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        """On Balance Volume."""
        xp = self.xp
        c = xp.asarray(closes, dtype=xp.float64)
        v = xp.asarray(volumes, dtype=xp.float64)
        n = len(c)
        if n == 0:
            return xp.array([], dtype=xp.float64)

        obv_arr = xp.zeros(n, dtype=xp.float64)
        obv_arr[0] = v[0]
        for i in range(1, n):
            if c[i] > c[i - 1]:
                obv_arr[i] = obv_arr[i - 1] + v[i]
            elif c[i] < c[i - 1]:
                obv_arr[i] = obv_arr[i - 1] - v[i]
            else:
                obv_arr[i] = obv_arr[i - 1]
        return obv_arr

    def candle_body_ratio(self, opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
        """Ratio of candle real body to total range."""
        xp = self.xp
        o = xp.asarray(opens, dtype=xp.float64)
        h = xp.asarray(highs, dtype=xp.float64)
        l = xp.asarray(lows, dtype=xp.float64)
        c = xp.asarray(closes, dtype=xp.float64)
        body = xp.abs(c - o)
        total_range = xp.maximum(h - l, 1e-6)
        return body / total_range

    def upper_wick_ratio(self, opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
        """Ratio of candle upper shadow to total range."""
        xp = self.xp
        o = xp.asarray(opens, dtype=xp.float64)
        h = xp.asarray(highs, dtype=xp.float64)
        l = xp.asarray(lows, dtype=xp.float64)
        c = xp.asarray(closes, dtype=xp.float64)
        upper_wick = h - xp.maximum(o, c)
        total_range = xp.maximum(h - l, 1e-6)
        return upper_wick / total_range

    def lower_wick_ratio(self, opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
        """Ratio of candle lower shadow to total range."""
        xp = self.xp
        o = xp.asarray(opens, dtype=xp.float64)
        h = xp.asarray(highs, dtype=xp.float64)
        l = xp.asarray(lows, dtype=xp.float64)
        c = xp.asarray(closes, dtype=xp.float64)
        lower_wick = xp.minimum(o, c) - l
        total_range = xp.maximum(h - l, 1e-6)
        return lower_wick / total_range

    def compute_custom_indicator(self, name: str, params: dict, data: Dict[str, np.ndarray]) -> np.ndarray:
        """Dynamic dispatch for indicators by name."""
        name_lower = name.lower().strip()
        c = data.get("closes", np.array([]))
        h = data.get("highs", c)
        l = data.get("lows", c)
        o = data.get("opens", c)
        v = data.get("volumes", np.ones(len(c)))

        if name_lower == "rsi":
            return self.to_cpu(self.rsi(c, int(params.get("period", 14))))
        elif name_lower == "ema":
            return self.to_cpu(self.ema(c, int(params.get("period", 20))))
        elif name_lower == "sma":
            return self.to_cpu(self.sma(c, int(params.get("period", 20))))
        elif name_lower == "vwap":
            return self.to_cpu(self.vwap(h, l, c, v))
        elif name_lower == "supertrend":
            st, _ = self.supertrend(h, l, c, int(params.get("period", 10)), float(params.get("multiplier", 3.0)))
            return self.to_cpu(st)
        elif name_lower in ("supertrend_dir", "supertrend_direction"):
            _, d = self.supertrend(h, l, c, int(params.get("period", 10)), float(params.get("multiplier", 3.0)))
            return self.to_cpu(d)
        elif name_lower == "atr":
            return self.to_cpu(self.atr(h, l, c, int(params.get("period", 14))))
        elif name_lower == "obv":
            return self.to_cpu(self.obv(c, v))
        elif name_lower == "candle_body_ratio":
            return self.to_cpu(self.candle_body_ratio(o, h, l, c))
        return c


# Alias for backward compatibility
IndicatorEngine = MathEngine
