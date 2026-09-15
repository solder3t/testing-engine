"""
core/scorer.py — Standalone signal quality scorer (0–100).

Extracted from agents/quant_agent.py so it can be unit-tested and imported
without pulling in the full google.antigravity SDK.

agents/quant_agent.py imports this function:
    from core.scorer import compute_signal_score
"""


def compute_signal_score(sig: dict) -> int:
    """
    Composite 0–100 score measuring signal quality.
    Components:
        RSI momentum       20 pts  (BUY: 55–70 ideal; SELL: 30–45 ideal)
        MACD strength      20 pts  (|histogram| vs typical range)
        Volume ratio       20 pts  (vol_ratio clipped 0–3 → 0–20)
        VWAP proximity     20 pts  (within 0.3% = max)
        Supertrend         10 pts  (direction + flip bonus)
        HTF alignment      10 pts  (5-min agrees = full points)
        R:R quality       +10 pts  (bonus: rr_ratio ≥ 2.5 = max)
        ADX trend          +5 pts  (bonus: ADX ≥ 25 and direction aligns)
        15m bias           +5 pts  (bonus: 15-min HTF agrees with signal)
        Anomaly penalty   −15 pts  (penalty: |z-score| ≥ 2.5 on entry bar)
    Total is clamped to [0, 100].
    """
    action    = sig.get("signal", "HOLD")
    rsi       = sig.get("rsi",           50)
    hist      = sig.get("macd_hist",     0)
    vol_ratio = sig.get("vol_ratio",     1.0)
    entry     = sig.get("entry_price",   0)
    vwap      = sig.get("vwap",          entry)
    st_dir    = sig.get("supertrend_dir", 0)
    st_flip   = sig.get("supertrend_flip", False)
    htf_bull  = sig.get("htf_bullish",   False)
    htf_bear  = sig.get("htf_bearish",   False)
    htf_valid = sig.get("htf_valid",     False)
    rr_ratio  = sig.get("rr_ratio",      0.0)
    anom_z    = sig.get("anomaly_zscore", 0.0)
    # M1: ADX regime
    adx_val   = sig.get("adx",           0.0)
    adx_plus  = sig.get("adx_plus_di",   0.0)
    adx_minus = sig.get("adx_minus_di",  0.0)
    # M3: 15-min bias
    bias_15m_bull = sig.get("htf_15m_bullish", False)
    bias_15m_bear = sig.get("htf_15m_bearish", False)

    if action not in ("BUY", "SELL"):
        return 0

    score = 0

    # RSI momentum (20 pts)
    if action == "BUY":
        if 55 <= rsi <= 70:    score += 20
        elif 50 <= rsi < 55:   score += 12
        elif rsi > 70:         score +=  8   # overbought — weaker
    elif action == "SELL":
        if 30 <= rsi <= 45:    score += 20
        elif 45 < rsi <= 50:   score += 12
        elif rsi < 30:         score +=  8

    # MACD strength (20 pts)
    abs_hist = abs(hist)
    hist_pts = min(abs_hist / 0.2 * 20, 20)  # 0.2 hist = full score
    if (action == "BUY" and hist > 0) or (action == "SELL" and hist < 0):
        score += int(hist_pts)

    # Volume ratio (20 pts)
    score += int(min(vol_ratio / 3.0 * 20, 20))

    # VWAP proximity (20 pts)
    if entry > 0 and vwap > 0:
        vwap_pct = abs(entry - vwap) / vwap * 100
        if vwap_pct <= 0.1:     score += 20
        elif vwap_pct <= 0.3:   score += 14
        elif vwap_pct <= 0.6:   score +=  8
        elif vwap_pct <= 1.0:   score +=  4
        # if price is on the wrong side of VWAP for the direction, add no points:
        if action == "BUY"  and entry < vwap:  score = max(score - 8, 0)
        if action == "SELL" and entry > vwap:  score = max(score - 8, 0)

    # Supertrend (10 pts)
    if (action == "BUY" and st_dir == 1) or (action == "SELL" and st_dir == -1):
        score += 7
    if st_flip:
        score += 3

    # HTF alignment (10 pts)
    if htf_valid:
        if (action == "BUY" and htf_bull) or (action == "SELL" and htf_bear):
            score += 10
        else:
            score += 4  # partial credit

    # ── R:R quality bonus (+10 pts) ───────────────────────────────────────────
    # Rewards higher reward-to-risk setups. rr_ratio ≥ 2.5 = full 10 points.
    # Between 1.5 (minimum) and 2.5 = proportional bonus.
    if rr_ratio >= 2.5:
        score += 10
    elif rr_ratio >= 1.5:
        score += int((rr_ratio - 1.5) / 1.0 * 10)   # 0–10 linear

    # ── M1: ADX trend confirmation bonus (+5 pts) ─────────────────────────────
    # Strong trend (ADX ≥ 25) with directional alignment is higher quality.
    if adx_val >= 25:
        if action == "BUY"  and adx_plus  > adx_minus:  score += 5
        if action == "SELL" and adx_minus > adx_plus:   score += 5

    # ── M3: 15-min bias confirmation bonus (+5 pts) ───────────────────────────
    # If the 15-min timeframe agrees with the signal direction, add confidence.
    if action == "BUY"  and bias_15m_bull:  score += 5
    if action == "SELL" and bias_15m_bear:  score += 5

    # ── Anomaly entry penalty (−15 pts) ───────────────────────────────────────
    # Penalise entering into statistically unusual spike bars. The engine will
    # still execute if score ≥ MIN_SIGNAL_SCORE, but quality is flagged lower.
    if abs(anom_z) >= 2.5:
        score = max(score - 15, 0)

    return min(max(score, 0), 100)
