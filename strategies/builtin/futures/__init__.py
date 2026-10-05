"""
Futures strategies suite package.
Categorized into order flow, volatility breakouts, trend following, and mean reversion.
"""

from .order_flow import (
    FuturesVolumeSpreadAnalysisStrategy,
    OrderFlowImbalanceStrategy,
    FuturesOiDivergenceStrategy,
)
from .volatility_breakout import (
    AtrVolatilityExpansionStrategy,
    MultiDayBreakoutStrategy,
    ChoppinessBreakoutStrategy,
    FuturesDualThrustStrategy,
)
from .trend_following import (
    ParabolicSarMomentumStrategy,
    FuturesMomentumPinbarStrategy,
    FuturesBasisArbitrageStrategy,
)
from .mean_reversion import (
    VwapValueAreaPocStrategy,
    FuturesVwapMeanReversionStrategy,
)

__all__ = [
    "FuturesVolumeSpreadAnalysisStrategy",
    "OrderFlowImbalanceStrategy",
    "FuturesOiDivergenceStrategy",
    "AtrVolatilityExpansionStrategy",
    "MultiDayBreakoutStrategy",
    "ChoppinessBreakoutStrategy",
    "FuturesDualThrustStrategy",
    "ParabolicSarMomentumStrategy",
    "FuturesMomentumPinbarStrategy",
    "FuturesBasisArbitrageStrategy",
    "VwapValueAreaPocStrategy",
    "FuturesVwapMeanReversionStrategy",
]
