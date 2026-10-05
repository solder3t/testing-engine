"""
data/nse_macro_loader.py — Historical NSE Macro, Flow & Market Internals Loader.

Parses 255+ trading days of historical data from nse_scrapper/NSE_Database/.
Supports:
- Bhavcopy (equities, delivery %, volumes)
- FO Bhavcopy & Implied Volatilities
- Participant-wise Open Interest (Client, DII, FII, Pro)
- FII/DII Cash and Derivatives Flows
- Daily Index Closes & Valuation (P/E, P/B, Div Yield)
- Macro & derived daily sentiment indicators for regime-aware backtesting
"""

import os
import csv
from typing import List, Dict, Any, Optional
from functools import lru_cache


class NseDataLoader:
    """Access layer for NSE historical files with LRU in-memory caching."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            # Walk up dynamically to find workspace root containing nse_scrapper/NSE_Database
            curr = os.path.abspath(__file__)
            target = curr
            found_dir = None
            while target and os.path.dirname(target) != target:
                if os.path.exists(os.path.join(target, "nse_scrapper", "NSE_Database")):
                    found_dir = target
                    break
                target = os.path.dirname(target)
            base_dir = found_dir if found_dir is not None else os.path.dirname(os.path.dirname(os.path.dirname(curr)))
        self.base_dir = os.path.abspath(base_dir)
        self.nse_dir = os.path.join(self.base_dir, "nse_scrapper", "NSE_Database")
        self.daily_dir = os.path.join(self.nse_dir, "daily")

    def get_available_dates(self) -> List[str]:
        """
        Return all available trading dates (YYYY-MM-DD), sorted chronologically.
        Filters out 'Common' or non-date folders.
        """
        if not os.path.exists(self.daily_dir):
            return []

        dates = []
        for name in os.listdir(self.daily_dir):
            parts = name.split("-")
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                path = os.path.join(self.daily_dir, name)
                if os.path.isdir(path):
                    dates.append(name)
        dates.sort()
        return dates

    def _read_csv(self, file_path: str, skip_rows: int = 0) -> List[Dict[str, str]]:
        """Safely parse CSV file into list of row dictionaries."""
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for _ in range(skip_rows):
                    f.readline()
                reader = csv.DictReader(f)
                cleaned_rows = []
                for row in reader:
                    cleaned_row = {
                        k.strip(): (v.strip() if isinstance(v, str) else v)
                        for k, v in row.items() if k is not None
                    }
                    cleaned_rows.append(cleaned_row)
                return cleaned_rows
        except Exception:
            return []

    def load_bhavcopy(self, date_str: str) -> Dict[str, Dict[str, Any]]:
        """Load equity bhavcopy for date. Returns mapping of SYMBOL -> data dict."""
        file_path = os.path.join(self.daily_dir, date_str, "market", "bhavcopy.csv")
        rows = self._read_csv(file_path)
        result = {}
        for r in rows:
            sym = r.get("SYMBOL")
            if sym and r.get("SERIES") == "EQ":
                try:
                    result[sym] = {
                        "symbol": sym,
                        "date": r.get("DATE1", date_str),
                        "prev_close": float(r.get("PREV_CLOSE", 0) or 0),
                        "open": float(r.get("OPEN_PRICE", 0) or 0),
                        "high": float(r.get("HIGH_PRICE", 0) or 0),
                        "low": float(r.get("LOW_PRICE", 0) or 0),
                        "close": float(r.get("CLOSE_PRICE", 0) or 0),
                        "volume": int(r.get("TTL_TRD_QNTY", 0) or 0),
                        "turnover_lacs": float(r.get("TURNOVER_LACS", 0) or 0),
                        "deliv_qty": int(r.get("DELIV_QTY", 0) or 0) if r.get("DELIV_QTY") not in (None, "-", "") else 0,
                        "deliv_pct": float(r.get("DELIV_PER", 0) or 0) if r.get("DELIV_PER") not in (None, "-", "") else 0.0,
                    }
                except (ValueError, TypeError):
                    continue
        return result

    def load_participant_oi(self, date_str: str) -> Dict[str, Dict[str, float]]:
        """Load participant-wise OI (Client, DII, FII, Pro)."""
        file_path = os.path.join(self.daily_dir, date_str, "market", "participant_oi.csv")
        if not os.path.exists(file_path):
            return {}

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline()
        skip = 1 if "Participant wise" in first_line else 0

        rows = self._read_csv(file_path, skip_rows=skip)
        result = {}
        for r in rows:
            client = r.get("Client Type", "").strip()
            if not client:
                continue
            parsed = {}
            for k, v in r.items():
                if k != "Client Type":
                    try:
                        parsed[k] = float(v.replace(",", "").strip() or 0)
                    except ValueError:
                        parsed[k] = 0.0
            result[client] = parsed
        return result

    def load_fii_dii_cash(self, date_str: str) -> Dict[str, Any]:
        """Load FII / DII net cash investments (crores)."""
        file_path = os.path.join(self.daily_dir, date_str, "flows", "fii_dii_cash.csv")
        rows = self._read_csv(file_path)
        net_equity_crore = 0.0
        details = []
        for r in rows:
            category = r.get("category", "")
            try:
                net_val = float(r.get("net_investment_crore", 0) or 0)
            except ValueError:
                net_val = 0.0
            if "Equity" in category:
                net_equity_crore += net_val
            details.append({
                "category": category,
                "route": r.get("route", ""),
                "gross_purchases": float(r.get("gross_purchases_crore", 0) or 0),
                "gross_sales": float(r.get("gross_sales_crore", 0) or 0),
                "net_investment": net_val
            })
        return {
            "date": date_str,
            "fii_net_equity_crore": round(net_equity_crore, 2),
            "details": details
        }

    def load_index_close(self, date_str: str) -> Dict[str, Dict[str, Any]]:
        """Load all index closes, PE, PB, and returns for date."""
        file_path = os.path.join(self.daily_dir, date_str, "market", "index_close.csv")
        rows = self._read_csv(file_path)
        indices = {}
        for r in rows:
            name = r.get("Index Name")
            if not name:
                continue
            try:
                indices[name] = {
                    "name": name,
                    "date": r.get("Index Date", date_str),
                    "open": float(r.get("Open Index Value", 0) or 0),
                    "high": float(r.get("High Index Value", 0) or 0),
                    "low": float(r.get("Low Index Value", 0) or 0),
                    "close": float(r.get("Closing Index Value", 0) or 0),
                    "change_pts": float(r.get("Points Change", 0) or 0),
                    "change_pct": float(r.get("Change(%)", 0) or 0),
                    "volume": float(r.get("Volume", 0) or 0) if r.get("Volume") not in ("-", "") else 0.0,
                    "turnover_cr": float(r.get("Turnover (Rs. Cr.)", 0) or 0) if r.get("Turnover (Rs. Cr.)") not in ("-", "") else 0.0,
                    "pe": float(r.get("P/E", 0) or 0) if r.get("P/E") not in ("-", "") else 0.0,
                    "pb": float(r.get("P/B", 0) or 0) if r.get("P/B") not in ("-", "") else 0.0,
                    "div_yield": float(r.get("Div Yield", 0) or 0) if r.get("Div Yield") not in ("-", "") else 0.0,
                }
            except (ValueError, TypeError):
                continue
        return indices

    def load_volatility(self, date_str: str) -> Dict[str, Dict[str, float]]:
        """Load FO volatility data per symbol."""
        file_path = os.path.join(self.daily_dir, date_str, "market", "fo_volatility.csv")
        rows = self._read_csv(file_path)
        vols = {}
        for r in rows:
            sym = r.get("Symbol")
            if not sym:
                continue
            try:
                vols[sym] = {
                    "underlying_close": float(r.get("Underlying Close Price (A)", 0) or 0),
                    "daily_volatility": float(r.get("Applicable Daily Volatility (M) = Max (E or K)", 0) or 0),
                    "annualized_volatility": float(r.get("Applicable Annualised Volatility (N) = M*Sqrt(365)", 0) or 0),
                }
            except (ValueError, TypeError):
                continue
        return vols
