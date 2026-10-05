"""
config.py — Configuration and Settings for Testing Engine.

Independent configuration for historical backtesting, archive discovery,
data caching, execution simulation, and dashboard server.
Loads settings from config.yaml with full environment variable overrides
and backward compatibility.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
import yaml

IST = ZoneInfo("Asia/Kolkata")

# ── Base Directories ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML_PATH = os.path.join(BASE_DIR, "config.yaml")

def _load_yaml_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_YAML_PATH):
        try:
            with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to parse config.yaml: {e}. Falling back to defaults.")
    return {}

_RAW_CONFIG = _load_yaml_config()

def _resolve_dir(candidates: List[str], fallback: str) -> str:
    """Finds the first existing directory from candidates relative to BASE_DIR."""
    for c in candidates:
        p = os.path.abspath(os.path.join(BASE_DIR, c))
        if os.path.isdir(p):
            return p
    return os.path.abspath(os.path.join(BASE_DIR, fallback))

# Live market data root discovery
_path_cfg = _RAW_CONFIG.get("paths", {})
_candidate_live_dirs = _path_cfg.get("live_db_dirs", [
    "../../databases/daily",
    "../databases/daily",
    "Database/daily",
    "databases/daily"
])
LIVE_DB_DIR = os.getenv("LIVE_DB_DIR", _resolve_dir(_candidate_live_dirs, "../../databases/daily"))

DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", LIVE_DB_DIR)
DATA_CACHE_DIR = os.getenv("DATA_CACHE_DIR", os.path.abspath(os.path.join(BASE_DIR, _path_cfg.get("data_cache_dir", "data_cache"))))
RESULTS_DIR = os.getenv("RESULTS_DIR", os.path.abspath(os.path.join(BASE_DIR, _path_cfg.get("results_dir", "results"))))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, _path_cfg.get("data_dir", "data")))
WATCHLIST_PATH = os.path.join(DATA_DIR, "watchlist.json")
RESULTS_DB_PATH = os.getenv("RESULTS_DB_PATH", os.path.abspath(os.path.join(BASE_DIR, _path_cfg.get("results_db_path", "results/results.db"))))

os.makedirs(DATA_CACHE_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.dirname(RESULTS_DB_PATH), exist_ok=True)

# ── Capital & Risk Controls ───────────────────────────────────────────────────
_risk_cfg = _RAW_CONFIG.get("capital_and_risk", {})
DEFAULT_CAPITAL = float(os.getenv("DEFAULT_CAPITAL", str(_risk_cfg.get("default_capital", 500000.0))))
DEFAULT_RISK_PCT_PER_TRADE = float(os.getenv("RISK_PCT_PER_TRADE", str(_risk_cfg.get("risk_pct_per_trade", 0.01))))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", str(_risk_cfg.get("max_positions", 5))))
MAX_POSITIONS_PER_SECTOR = int(os.getenv("MAX_POSITIONS_PER_SECTOR", str(_risk_cfg.get("max_positions_per_sector", 2))))
MAX_QTY_PER_TRADE = int(os.getenv("MAX_QTY_PER_TRADE", str(_risk_cfg.get("max_qty_per_trade", 500))))
MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", str(_risk_cfg.get("min_rr_ratio", 1.5))))

# Kill Switches & Cooldowns
DAILY_MAX_LOSS_PCT = float(os.getenv("DAILY_MAX_LOSS_PCT", str(_risk_cfg.get("daily_max_loss_pct", 0.03))))
DAILY_MAX_LOSS_INR = float(os.getenv("DAILY_MAX_LOSS_INR", str(_risk_cfg.get("daily_max_loss_inr", 25000.0))))
MAX_DRAWDOWN_STOP_PCT = float(os.getenv("MAX_DRAWDOWN_STOP_PCT", str(_risk_cfg.get("max_drawdown_stop_pct", 0.15))))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", str(_risk_cfg.get("max_consecutive_losses", 4))))
COOLDOWN_BARS = int(os.getenv("COOLDOWN_BARS", str(_risk_cfg.get("cooldown_bars", 5))))

# ── Session Timings (IST) ─────────────────────────────────────────────────────
_timing_cfg = _RAW_CONFIG.get("timings", {})
TRADING_START = os.getenv("TRADING_START", str(_timing_cfg.get("trading_start", "09:15")))
TRADING_END = os.getenv("TRADING_END", str(_timing_cfg.get("trading_end", "15:00")))
FORCE_SQUARE_OFF_TIME = os.getenv("FORCE_SQUARE_OFF_TIME", str(_timing_cfg.get("force_square_off_time", "15:15")))
EXPIRY_CUTOFF_TIME = os.getenv("EXPIRY_CUTOFF_TIME", str(_timing_cfg.get("expiry_cutoff_time", "13:00")))

# ── Indian Statutory Exchange & Regulatory Fee Schedule ────────────────────────
_stat_cfg = _RAW_CONFIG.get("statutory_charges", {})
BROKERAGE_FLAT_PER_ORDER = float(_stat_cfg.get("brokerage_flat_per_order", 20.0))
STT_EQUITY_INTRADAY = float(_stat_cfg.get("stt_equity_intraday", 0.00025))
STT_OPTIONS_TURNOVER = float(_stat_cfg.get("stt_options_turnover", 0.000625))
STT_OPTIONS_EXERCISE = float(_stat_cfg.get("stt_options_exercise", 0.00125))
EXCHANGE_TXN_FEE_EQUITY = float(_stat_cfg.get("exchange_txn_fee_equity", 0.0000297))
EXCHANGE_TXN_FEE_OPTIONS = float(_stat_cfg.get("exchange_txn_fee_options", 0.00035))
GST_RATE = float(_stat_cfg.get("gst_rate", 0.18))
SEBI_CHARGES = float(_stat_cfg.get("sebi_charges", 0.000001))
STAMP_DUTY_EQUITY_BUY = float(_stat_cfg.get("stamp_duty_equity_buy", 0.00003))
STAMP_DUTY_OPTIONS_BUY = float(_stat_cfg.get("stamp_duty_options_buy", 0.00003))

# ── Execution & Slippage Modeling ─────────────────────────────────────────────
_exec_cfg = _RAW_CONFIG.get("execution", {})
SLIPPAGE_MODEL = os.getenv("SLIPPAGE_MODEL", str(_exec_cfg.get("slippage_model", "pct")))
DEFAULT_SLIPPAGE_PCT = float(os.getenv("DEFAULT_SLIPPAGE_PCT", str(_exec_cfg.get("default_slippage_pct", 0.0005))))
FIXED_SLIPPAGE_TICKS = int(_exec_cfg.get("fixed_slippage_ticks", 1))
LATENCY_MS = int(os.getenv("LATENCY_MS", str(_exec_cfg.get("latency_ms", 0))))
ENABLE_DEPTH_SLIPPAGE = bool(_exec_cfg.get("enable_depth_slippage", True))
FILL_PROBABILITY_LIMIT_ORDERS = float(_exec_cfg.get("fill_probability_limit_orders", 1.0))

# ── Margin Modeling ───────────────────────────────────────────────────────────
_margin_cfg = _RAW_CONFIG.get("margin", {})
SPAN_EXPOSURE_FUTURES_PCT = float(_margin_cfg.get("span_exposure_futures_pct", 0.20))
SPAN_EXPOSURE_SHORT_OPT_PCT = float(_margin_cfg.get("span_exposure_short_opt_pct", 0.20))
LONG_OPTION_PREMIUM_REQUIRED = float(_margin_cfg.get("long_option_premium_required", 1.0))
MAX_SECTOR_EXPOSURE_PCT = float(os.getenv("MAX_SECTOR_EXPOSURE_PCT", "0.35"))   # Max 35% of capital in any single sector
MAX_CORRELATED_LEGS = int(os.getenv("MAX_CORRELATED_LEGS", "2"))               # Max concurrent assets with rolling correlation > 0.75

# ── Database & Cache ──────────────────────────────────────────────────────────
_db_cfg = _RAW_CONFIG.get("database", {})
DATABASE_MODE = os.getenv("DATABASE_MODE", str(_db_cfg.get("mode", "auto")))  # "auto", "unified", "legacy"
CACHE_RESAMPLED_BARS = bool(_db_cfg.get("cache_resampled_bars", True))
CACHE_FORMAT = str(_db_cfg.get("cache_format", "parquet"))

# ── Validation ────────────────────────────────────────────────────────────────
_val_cfg = _RAW_CONFIG.get("validation", {})
PBO_PARTITIONS = int(_val_cfg.get("pbo_partitions", 10))
MONTE_CARLO_RUNS = int(_val_cfg.get("monte_carlo_runs", 1000))
WFE_HURDLE = float(_val_cfg.get("wfe_hurdle", 0.50))
CONFIDENCE_LEVEL = float(_val_cfg.get("confidence_level", 0.95))

# ── Dashboard Server ──────────────────────────────────────────────────────────
_dash_cfg = _RAW_CONFIG.get("dashboard", {})
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", str(_dash_cfg.get("host", "127.0.0.1")))
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", str(_dash_cfg.get("port", 5690))))

# ── Chrome Profile Configuration (Matches Bot / Scrapers) ────────────────────
_chrome_cfg = _RAW_CONFIG.get("chrome", {})
CHROME_PATH = os.getenv(
    "CHROME_PATH",
    str(_chrome_cfg.get("path", r"C:\Program Files\Google\Chrome\Application\chrome.exe"))
)
CHROME_PROFILE_DIR = os.getenv(
    "CHROME_PROFILE_DIR",
    str(_chrome_cfg.get("profile_dir", r"C:\selenium\ChromeProfile"))
)
CHROME_DEBUG_PORT = int(
    os.getenv("CHROME_DEBUG_PORT", str(_chrome_cfg.get("debug_port", 9222)))
)
CHROME_AUTO_OPEN = bool(
    os.getenv("CHROME_AUTO_OPEN", str(_chrome_cfg.get("auto_open", True)))
)


def get_full_config() -> Dict[str, Any]:
    """Returns the entire configuration hierarchy as a dictionary."""
    return _RAW_CONFIG


def validate_config():
    """Validates configuration parameters and environment variables against valid bounds."""
    errors = []
    if DEFAULT_CAPITAL <= 0:
        errors.append(f"DEFAULT_CAPITAL must be positive, got {DEFAULT_CAPITAL}")
    if not (0.0 < DEFAULT_RISK_PCT_PER_TRADE <= 0.50):
        errors.append(f"DEFAULT_RISK_PCT_PER_TRADE must be in (0.0, 0.50], got {DEFAULT_RISK_PCT_PER_TRADE}")
    if MAX_POSITIONS <= 0:
        errors.append(f"MAX_POSITIONS must be >= 1, got {MAX_POSITIONS}")
    if MAX_QTY_PER_TRADE <= 0:
        errors.append(f"MAX_QTY_PER_TRADE must be >= 1, got {MAX_QTY_PER_TRADE}")
    if MIN_RR_RATIO <= 0:
        errors.append(f"MIN_RR_RATIO must be positive, got {MIN_RR_RATIO}")
    if TRADING_START >= TRADING_END:
        errors.append(f"TRADING_START ({TRADING_START}) must precede TRADING_END ({TRADING_END})")
    if errors:
        raise ValueError("Testing Engine configuration validation failed:\n" + "\n".join(errors))


validate_config()
