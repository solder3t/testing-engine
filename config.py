"""
config.py — Configuration and Settings for Testing Engine.

Independent configuration for historical backtesting, archive discovery,
data caching, execution simulation, and dashboard server.
"""

import os
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# ── Base Directories ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", os.path.expanduser("~/Downloads"))
DATA_CACHE_DIR = os.getenv("DATA_CACHE_DIR", os.path.join(BASE_DIR, "data_cache"))
RESULTS_DIR = os.getenv("RESULTS_DIR", os.path.join(BASE_DIR, "results"))
DATA_DIR = os.path.join(BASE_DIR, "data")
WATCHLIST_PATH = os.path.join(DATA_DIR, "watchlist.json")

os.makedirs(DATA_CACHE_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ── Default Capital & Risk Controls ───────────────────────────────────────────
DEFAULT_CAPITAL = float(os.getenv("DEFAULT_CAPITAL", "500000.0"))        # ₹5,00,000
DEFAULT_RISK_PCT_PER_TRADE = float(os.getenv("RISK_PCT_PER_TRADE", "0.01"))  # 1% risk per trade
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))
MAX_POSITIONS_PER_SECTOR = int(os.getenv("MAX_POSITIONS_PER_SECTOR", "2"))
MAX_QTY_PER_TRADE = int(os.getenv("MAX_QTY_PER_TRADE", "500"))
MIN_RR_RATIO = float(os.getenv("MIN_RR_RATIO", "1.5"))

# ── Session Timings (IST) ─────────────────────────────────────────────────────
TRADING_START = "09:15"   # NSE market open (was incorrectly "09:30")
TRADING_END = "15:00"
FORCE_SQUARE_OFF_TIME = "15:15"
EXPIRY_CUTOFF_TIME = "13:00"

# ── Indian Statutory Exchange & Regulatory Fee Schedule ────────────────────────
BROKERAGE_FLAT_PER_ORDER = 20.0       # ₹20 per executed order (discount broker model)
STT_EQUITY_INTRADAY = 0.00025         # 0.025% on sell turnover
STT_OPTIONS_TURNOVER = 0.000625       # 0.0625% on sell option premium
EXCHANGE_TXN_FEE_EQUITY = 0.0000297   # NSE 0.00297% turnover
EXCHANGE_TXN_FEE_OPTIONS = 0.00035    # NSE 0.035% on premium turnover
GST_RATE = 0.18                       # 18% on (brokerage + exchange txn fee)
SEBI_CHARGES = 0.000001               # ₹10 per crore (0.0001%)
STAMP_DUTY_EQUITY_BUY = 0.00003       # 0.003% on buy value
STAMP_DUTY_OPTIONS_BUY = 0.00003      # 0.003% on buy premium

# ── Slippage & Execution Modeling ─────────────────────────────────────────────
DEFAULT_SLIPPAGE_PCT = 0.0005         # 5 bps standard slippage
ENABLE_DEPTH_SLIPPAGE = True          # Use L2/L3 order book depth if available

# ── Dashboard Server ──────────────────────────────────────────────────────────
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5690
