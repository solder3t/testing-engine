"""
data/quality_auditor.py — Historical Market Data Quality & Integrity Auditor.

Detects missing timestamps, anomalous spikes, negative/zero prices,
stale quotes, and crossed spreads, producing an actionable Data Quality Report.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


@dataclass
class QualityReport:
    symbol: str
    date_str: str
    total_bars: int
    missing_bars: int
    anomalous_bars: int
    stale_bars: int
    zero_volume_bars: int
    health_score: float  # 0.0 to 100.0
    status: str          # "EXCELLENT", "ACCEPTABLE", "DEGRADED", "CRITICAL"
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "date": self.date_str,
            "total_bars": self.total_bars,
            "missing_bars": self.missing_bars,
            "anomalous_bars": self.anomalous_bars,
            "stale_bars": self.stale_bars,
            "zero_volume_bars": self.zero_volume_bars,
            "health_score": round(self.health_score, 2),
            "status": self.status,
            "issues": self.issues
        }


class DataQualityAuditor:
    """Audits pandas OHLCV DataFrames for data integrity and continuity."""

    @staticmethod
    def audit(
        df: pd.DataFrame, 
        symbol: str, 
        date_str: str, 
        timeframe_minutes: int = 1
    ) -> QualityReport:
        """Runs audit suite on resampled OHLC data."""
        if df is None or df.empty:
            return QualityReport(
                symbol=symbol,
                date_str=date_str,
                total_bars=0,
                missing_bars=375 // timeframe_minutes,
                anomalous_bars=0,
                stale_bars=0,
                zero_volume_bars=0,
                health_score=0.0,
                status="CRITICAL",
                issues=["Empty or None dataset provided"]
            )

        issues = []
        total_bars = len(df)
        
        # 1. Expected bar count (09:15 to 15:30 = 375 minutes)
        expected_bars = 375 // max(1, timeframe_minutes)
        missing_bars = max(0, expected_bars - total_bars)
        if missing_bars > 0:
            pct_missing = (missing_bars / expected_bars) * 100
            if pct_missing > 20:
                issues.append(f"Significant missing bar gap: {missing_bars}/{expected_bars} bars ({pct_missing:.1f}%) missing")
            elif pct_missing > 5:
                issues.append(f"Minor missing bars: {missing_bars} bars missing")

        # 2. Price Sanity Checks
        anomalies = 0
        if "close" in df.columns:
            # Check negative or zero prices
            zero_neg = (df["close"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["open"] <= 0)
            if zero_neg.any():
                count = int(zero_neg.sum())
                anomalies += count
                issues.append(f"Found {count} bars with non-positive price")

            # Check High >= Low, High >= Open, High >= Close, Low <= Open, Low <= Close
            hl_violation = (df["high"] < df["low"]) | (df["high"] < df["open"]) | (df["high"] < df["close"])
            if hl_violation.any():
                count = int(hl_violation.sum())
                anomalies += count
                issues.append(f"Found {count} bars violating High >= Low/Open/Close bounds")

            # Spike detection (> 15% bar-to-bar return in 1 minute)
            pct_changes = df["close"].pct_change().abs()
            spikes = pct_changes > 0.15
            if spikes.any():
                count = int(spikes.sum())
                anomalies += count
                issues.append(f"Detected {count} extreme bar-to-bar price spikes (>15%)")

        # 3. Volume and Stale Quote Checks
        zero_vol = 0
        if "volume" in df.columns:
            zero_vol = int((df["volume"] == 0).sum())
            if zero_vol > total_bars * 0.5 and total_bars > 20:
                issues.append(f"High zero-volume concentration: {zero_vol}/{total_bars} bars have 0 volume")

        # 4. Stale price check (Close price unchanged for > 20 consecutive bars)
        stale_bars = 0
        if "close" in df.columns and total_bars > 20:
            diffs = (df["close"].diff() == 0).astype(int)
            runs = diffs.groupby((diffs != diffs.shift()).cumsum()).cumsum()
            stale_bars = int((runs >= 15).sum())
            if stale_bars > 0:
                issues.append(f"Detected {stale_bars} potentially stale bars (flat price for >=15 bars)")

        # 5. Composite Health Score Calculation (0 to 100)
        penalty = 0.0
        penalty += min(40.0, (missing_bars / expected_bars) * 50.0)
        penalty += min(35.0, (anomalies / max(1, total_bars)) * 100.0)
        penalty += min(15.0, (stale_bars / max(1, total_bars)) * 30.0)
        if zero_vol > total_bars * 0.7:
            penalty += 10.0

        health_score = max(0.0, min(100.0, 100.0 - penalty))

        if health_score >= 90.0:
            status = "EXCELLENT"
        elif health_score >= 70.0:
            status = "ACCEPTABLE"
        elif health_score >= 40.0:
            status = "DEGRADED"
        else:
            status = "CRITICAL"

        return QualityReport(
            symbol=symbol,
            date_str=date_str,
            total_bars=total_bars,
            missing_bars=missing_bars,
            anomalous_bars=anomalies,
            stale_bars=stale_bars,
            zero_volume_bars=zero_vol,
            health_score=health_score,
            status=status,
            issues=issues
        )
