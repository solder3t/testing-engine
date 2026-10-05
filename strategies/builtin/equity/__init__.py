"""
Cash Equities strategies suite package.
Modularized into momentum, breakout, and mean-reversion categories.
"""

from .momentum import (
    MomentumRsiEmaStrategy,
    KeltnerChannelMomentumStrategy,
    StochasticRsiCrossoverStrategy,
    MacdHistogramAccelerationStrategy,
    HullMaDirectionFlipStrategy,
)
from .breakout import (
    VolumePriceActionBreakoutStrategy,
    DonchianChannelTurtleStrategy,
    IchimokuCloudBreakoutStrategy,
    LinearRegressionSlopeStrategy,
)
from .mean_reversion import (
    VwapInstitutionalBounceStrategy,
    ConnorsRsi2PullbackStrategy,
    RelativeStrengthAlphaStrategy,
    BollingerPercentBReversalStrategy,
)

__all__ = [
    "MomentumRsiEmaStrategy",
    "KeltnerChannelMomentumStrategy",
    "StochasticRsiCrossoverStrategy",
    "MacdHistogramAccelerationStrategy",
    "HullMaDirectionFlipStrategy",
    "VolumePriceActionBreakoutStrategy",
    "DonchianChannelTurtleStrategy",
    "IchimokuCloudBreakoutStrategy",
    "LinearRegressionSlopeStrategy",
    "VwapInstitutionalBounceStrategy",
    "ConnorsRsi2PullbackStrategy",
    "RelativeStrengthAlphaStrategy",
    "BollingerPercentBReversalStrategy",
]
