"""
strategies package — Institutional & Quantitative Backtesting Strategies.
"""

from strategies.base_strategy import BaseStrategy
from strategies.equity_momentum import EquityMomentumStrategy
from strategies.vwap_reversion import VwapReversionStrategy
from strategies.rsi_momentum import RsiMomentumStrategy
from strategies.nifty_options import NiftyOptionsStrategy
from strategies.ai_evaluator import AiSnapshotStrategy
from strategies.orb_breakout import OrbBreakoutStrategy
from strategies.supertrend_trend import SupertrendTrendStrategy
from strategies.camarilla_breakout import CamarillaBreakoutStrategy
from strategies.ema_ribbon import EmaRibbonStrategy
from strategies.bollinger_percent_b import BollingerPercentBStrategy
from strategies.macd_acceleration import MacdAccelerationStrategy
from strategies.short_straddle import ShortStraddleStrategy
from strategies.pcr_reversion import PcrReversionStrategy
from strategies.banknifty_options import BankNiftyOptionsStrategy
from strategies.futures_trend import FuturesTrendStrategy
from strategies.max_pain import MaxPainConvergenceStrategy

__all__ = [
    "BaseStrategy",
    "EquityMomentumStrategy",
    "VwapReversionStrategy",
    "RsiMomentumStrategy",
    "NiftyOptionsStrategy",
    "AiSnapshotStrategy",
    "OrbBreakoutStrategy",
    "SupertrendTrendStrategy",
    "CamarillaBreakoutStrategy",
    "EmaRibbonStrategy",
    "BollingerPercentBStrategy",
    "MacdAccelerationStrategy",
    "ShortStraddleStrategy",
    "PcrReversionStrategy",
    "BankNiftyOptionsStrategy",
    "FuturesTrendStrategy",
    "MaxPainConvergenceStrategy",
]
