"""
data/expiry_calendar.py — Indian Exchange Expiry Calendar & Holiday Resolver.

Handles weekly and monthly derivative expiry calculation, exchange trading holidays,
preceding-day holiday expiry shifts, and instrument-specific expiry schedules.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Set, Union


class ExpiryCalendar:
    """
    NSE & BSE Expiry resolver with trading holiday adjustment.
    """

    # Major NSE Trading Holidays (YYYY-MM-DD)
    _HOLIDAYS: Set[str] = {
        # 2024
        "2024-01-22", "2024-01-26", "2024-03-08", "2024-03-25", "2024-03-29",
        "2024-04-11", "2024-04-17", "2024-05-01", "2024-05-20", "2024-06-17",
        "2024-07-17", "2024-08-15", "2024-10-02", "2024-11-01", "2024-11-15", "2024-12-25",
        # 2025
        "2025-01-26", "2025-02-26", "2025-03-14", "2025-03-31", "2025-04-10",
        "2025-04-14", "2025-04-18", "2025-05-01", "2025-06-07", "2025-08-15",
        "2025-08-27", "2025-10-02", "2025-10-21", "2025-11-05", "2025-12-25",
        # 2026
        "2026-01-26", "2026-03-03", "2026-03-20", "2026-04-03", "2026-04-14",
        "2026-05-01", "2026-05-28", "2026-08-15", "2026-10-02", "2026-10-20",
        "2026-11-24", "2026-12-25",
    }

    # Standard weekday mapping (Monday=0 ... Sunday=6)
    # Post-2024 SEBI rationalization: Nifty=Thursday, BankNifty=Wednesday (then monthly Thursday),
    # FinNifty=Tuesday, MidcpNifty=Monday, Sensex=Friday.
    _EXPIRY_WEEKDAY: dict = {
        "NIFTY": 3,      # Thursday
        "NIFTY50": 3,    # Thursday
        "BANKNIFTY": 2,  # Wednesday (or Thursday for monthly)
        "FINNIFTY": 1,   # Tuesday
        "MIDCPNIFTY": 0, # Monday
        "SENSEX": 4,     # Friday
        "BANKEX": 0,     # Monday
    }

    @classmethod
    def _to_date(cls, d: Union[str, date, datetime]) -> date:
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, date):
            return d
        # String format: YYYY-MM-DD or YYYY_MM_DD or YYYYMMDD
        s = str(d).replace("_", "-").split("T")[0].split(" ")[0]
        if len(s) == 8 and s.isdigit():
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        return date.fromisoformat(s[:10])

    @classmethod
    def is_holiday(cls, check_date: Union[str, date, datetime]) -> bool:
        """Returns True if the given date is a weekend or listed exchange holiday."""
        d = cls._to_date(check_date)
        if d.weekday() >= 5:  # Saturday or Sunday
            return True
        return d.isoformat() in cls._HOLIDAYS

    @classmethod
    def get_expiry_weekday(cls, symbol: str) -> int:
        """Returns standard expiry weekday index (0=Monday .. 4=Friday)."""
        s = symbol.upper().strip()
        for k, v in cls._EXPIRY_WEEKDAY.items():
            if k in s:
                return v
        return 3  # Default Thursday for stock/index derivatives

    @classmethod
    def adjust_for_holiday(cls, target_date: date) -> date:
        """If target date is a holiday or weekend, rolls backward to previous trading day."""
        curr = target_date
        while cls.is_holiday(curr):
            curr -= timedelta(days=1)
        return curr

    @classmethod
    def get_nearest_expiry(
        cls, 
        symbol: str, 
        from_date: Union[str, date, datetime],
        expiry_type: str = "weekly"
    ) -> date:
        """
        Finds the nearest valid expiry on or after from_date.
        If expiry_type is 'monthly', finds the last expiry of the current month.
        """
        curr = cls._to_date(from_date)
        weekday = cls.get_expiry_weekday(symbol)

        if expiry_type.lower() == "monthly":
            # Find last Thursday (or relevant weekday) of the month
            next_month = curr.replace(day=28) + timedelta(days=4)
            last_day_of_month = next_month - timedelta(days=next_month.day)
            
            # Walk backward from last day to find weekday
            d = last_day_of_month
            while d.weekday() != weekday:
                d -= timedelta(days=1)
            
            adjusted = cls.adjust_for_holiday(d)
            if adjusted < curr:
                # If current date is past this month's expiry, get next month's
                nm = (curr.replace(day=28) + timedelta(days=4))
                return cls.get_nearest_expiry(symbol, nm.replace(day=1), "monthly")
            return adjusted

        # Weekly expiry
        days_ahead = (weekday - curr.weekday()) % 7
        candidate = curr + timedelta(days=days_ahead)
        adjusted = cls.adjust_for_holiday(candidate)
        
        # If adjusted expiry rolled into the past, step to next week
        if adjusted < curr:
            candidate += timedelta(days=7)
            adjusted = cls.adjust_for_holiday(candidate)
        return adjusted

    @classmethod
    def is_expiry_day(cls, symbol: str, current_date: Union[str, date, datetime]) -> bool:
        """Checks if current_date is the effective expiry day for the symbol."""
        d = cls._to_date(current_date)
        nearest = cls.get_nearest_expiry(symbol, d)
        return nearest == d

    @classmethod
    def is_expiry(cls, current_date: Union[str, date, datetime], symbol: str = "NIFTY") -> bool:
        """Alias for is_expiry_day supporting both is_expiry(date, symbol) and is_expiry(date)."""
        return cls.is_expiry_day(symbol, current_date)

    # Alias for convenience
    get_next_expiry = get_nearest_expiry


