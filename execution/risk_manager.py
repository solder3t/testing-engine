"""
execution/risk_manager.py — Institutional Risk Controls & Kill Switches.

Monitors daily loss thresholds, peak-to-trough drawdowns, consecutive losses,
and applies circuit breakers / kill switches to protect trading capital.
"""

from dataclasses import dataclass
import logging
from typing import Optional, Tuple, List, Dict, Any
import numpy as np
import config

logger = logging.getLogger("risk_manager")


@dataclass
class RiskBreachEvent:
    event_type: str  # "DAILY_LOSS_KILL_SWITCH", "MAX_DRAWDOWN_BREACH", "CONSECUTIVE_LOSS_COOLDOWN"
    message: str
    timestamp: str
    pnl_value: float
    threshold_value: float


class RiskManager:
    """Intraday and Engine-Level Risk Guard."""

    def __init__(
        self,
        capital: Optional[float] = None,
        daily_max_loss_pct: Optional[float] = None,
        daily_max_loss_inr: Optional[float] = None,
        max_drawdown_stop_pct: Optional[float] = None,
        max_consecutive_losses: Optional[int] = None,
        cooldown_bars: Optional[int] = None,
        **kwargs
    ):
        cap = capital if capital is not None else kwargs.get("initial_capital", config.DEFAULT_CAPITAL)
        self.starting_capital = float(cap)
        self.peak_capital = float(cap)
        
        # Loss pct: support 3.0 (meaning 3%) or 0.03
        loss_pct = daily_max_loss_pct if daily_max_loss_pct is not None else kwargs.get("max_daily_loss_pct", config.DAILY_MAX_LOSS_PCT)
        if loss_pct > 1.0:
            loss_pct /= 100.0
        self.daily_max_loss_pct = float(loss_pct)

        self.daily_max_loss_inr = float(daily_max_loss_inr if daily_max_loss_inr is not None else kwargs.get("max_daily_loss_inr", config.DAILY_MAX_LOSS_INR))
        
        dd_pct = max_drawdown_stop_pct if max_drawdown_stop_pct is not None else kwargs.get("max_drawdown_pct", config.MAX_DRAWDOWN_STOP_PCT)
        if dd_pct > 1.0:
            dd_pct /= 100.0
        self.max_drawdown_stop_pct = float(dd_pct)

        self.max_consecutive_losses = int(max_consecutive_losses if max_consecutive_losses is not None else kwargs.get("consecutive_loss_limit", config.MAX_CONSECUTIVE_LOSSES))
        self.cooldown_bars_total = int(cooldown_bars if cooldown_bars is not None else kwargs.get("cooldown_bars_total", config.COOLDOWN_BARS))


        # Dynamic state
        self.daily_kill_switch_triggered = False
        self.engine_drawdown_halt = False
        self.consecutive_losses = 0
        self.cooldown_bars_remaining = 0
        self.last_breach_event: Optional[RiskBreachEvent] = None

    def reset_daily_session(self, current_capital: float) -> None:
        """Resets intraday counters at the start of each daily session."""
        self.starting_capital = current_capital
        self.daily_kill_switch_triggered = False
        self.cooldown_bars_remaining = 0
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital

    def check_entry_allowed(self) -> Tuple[bool, str]:
        """Validates whether new trades can be initiated under current risk state."""
        if self.engine_drawdown_halt:
            return False, "ENGINE_HALTED: Peak-to-trough max drawdown threshold breached"

        if self.daily_kill_switch_triggered:
            return False, "DAILY_KILL_SWITCH_ACTIVE: Daily loss limit breached, all entries halted for session"

        if self.cooldown_bars_remaining > 0:
            return False, f"COOLDOWN_ACTIVE: {self.cooldown_bars_remaining} bars remaining following consecutive losses"

        return True, "OK"

    def evaluate_intraday_pnl(self, daily_pnl: float, timestamp: str = "") -> bool:
        """
        Evaluates cumulative daily PnL (realized + unrealized).
        If loss exceeds threshold, triggers daily kill switch. Returns True if breached.
        """
        if self.daily_kill_switch_triggered:
            return True

        pct_loss = -daily_pnl / self.starting_capital if self.starting_capital > 0 else 0.0
        pct_breach = pct_loss >= self.daily_max_loss_pct
        inr_breach = daily_pnl <= -abs(self.daily_max_loss_inr)

        if pct_breach or inr_breach:
            self.daily_kill_switch_triggered = True
            msg = (
                f"KILL SWITCH TRIGGERED at {timestamp}: Daily P&L = {daily_pnl:.2f} "
                f"(-{pct_loss*100:.2f}%), exceeding limit "
                f"(-{self.daily_max_loss_pct*100:.2f}% / ₹{self.daily_max_loss_inr:.2f})"
            )
            logger.warning(msg)
            self.last_breach_event = RiskBreachEvent(
                event_type="DAILY_LOSS_KILL_SWITCH",
                message=msg,
                timestamp=timestamp,
                pnl_value=daily_pnl,
                threshold_value=-self.daily_max_loss_inr
            )
            return True
        return False

    def evaluate_equity_drawdown(self, current_equity: float, timestamp: str = "") -> bool:
        """
        Evaluates overall peak-to-trough portfolio drawdown.
        Returns True if engine halt circuit breaker is triggered.
        """
        if current_equity > self.peak_capital:
            self.peak_capital = current_equity

        dd_pct = (self.peak_capital - current_equity) / self.peak_capital if self.peak_capital > 0 else 0.0
        if dd_pct >= self.max_drawdown_stop_pct:
            self.engine_drawdown_halt = True
            msg = (
                f"MAX DRAWDOWN BREACH at {timestamp}: Current Equity = ₹{current_equity:.2f}, "
                f"Peak = ₹{self.peak_capital:.2f}, Drawdown = {dd_pct*100:.2f}% "
                f"(Threshold = {self.max_drawdown_stop_pct*100:.2f}%)"
            )
            logger.critical(msg)
            self.last_breach_event = RiskBreachEvent(
                event_type="MAX_DRAWDOWN_BREACH",
                message=msg,
                timestamp=timestamp,
                pnl_value=current_equity,
                threshold_value=self.max_drawdown_stop_pct
            )
            return True
        return False

    def record_trade_completion(self, net_pnl: float, timestamp: str = "") -> None:
        """Updates consecutive loss tracker and triggers cooldown if threshold met."""
        if net_pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.cooldown_bars_remaining = self.cooldown_bars_total
                msg = (
                    f"COOLDOWN TRIGGERED at {timestamp}: {self.consecutive_losses} consecutive losing trades. "
                    f"Pausing entries for {self.cooldown_bars_total} bars."
                )
                logger.info(msg)
                self.last_breach_event = RiskBreachEvent(
                    event_type="CONSECUTIVE_LOSS_COOLDOWN",
                    message=msg,
                    timestamp=timestamp,
                    pnl_value=net_pnl,
                    threshold_value=self.max_consecutive_losses
                )
        else:
            self.consecutive_losses = 0

    def step_bar(self) -> None:
        """Decrements cooldown counter on every new bar."""
        if self.cooldown_bars_remaining > 0:
            self.cooldown_bars_remaining -= 1

    def check_sector_exposure(
        self,
        open_trades: List[Any],
        new_sector: str,
        new_trade_value: float = 0.0,
        capital: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Validates that capital concentration in a single sector does not exceed MAX_SECTOR_EXPOSURE_PCT."""
        if not new_sector or new_sector in ("Other", "Index", "Unknown"):
            return True, "OK"

        cap = capital if capital is not None else self.starting_capital
        if cap <= 0:
            return True, "OK"

        existing_val = sum(
            float(getattr(t, "entry_price", 0.0) * getattr(t, "qty", 0))
            for t in open_trades
            if getattr(t, "metadata", {}).get("sector") == new_sector
        )
        total_sector_val = existing_val + new_trade_value
        exposure_pct = total_sector_val / cap
        limit = getattr(config, "MAX_SECTOR_EXPOSURE_PCT", 0.35)

        if exposure_pct > limit:
            return False, f"Sector '{new_sector}' exposure {exposure_pct:.1%} exceeds {limit:.0%} limit"
        return True, "OK"

    def check_correlation_limit(
        self,
        open_trades: List[Any],
        new_symbol: str,
        price_history: Optional[Dict[str, List[float]]] = None
    ) -> Tuple[bool, str]:
        """Ensures concurrent correlated positions do not exceed MAX_CORRELATED_LEGS."""
        max_legs = getattr(config, "MAX_CORRELATED_LEGS", 2)
        if len(open_trades) < max_legs or not price_history:
            return True, "OK"

        new_series = price_history.get(new_symbol)
        if not new_series or len(new_series) < 10:
            return True, "OK"

        correlated_count = 0
        for t in open_trades:
            exist_sym = getattr(t, "symbol", "")
            exist_series = price_history.get(exist_sym)
            if exist_series and len(exist_series) >= 10:
                min_len = min(len(new_series), len(exist_series), 20)
                s1 = np.array(new_series[-min_len:], dtype=float)
                s2 = np.array(exist_series[-min_len:], dtype=float)
                if np.std(s1) > 1e-6 and np.std(s2) > 1e-6:
                    corr = float(np.corrcoef(s1, s2)[0, 1])
                    if corr > 0.75:
                        correlated_count += 1

        if correlated_count >= max_legs:
            return False, f"Correlated legs ({correlated_count}) reached maximum limit ({max_legs})"
        return True, "OK"
