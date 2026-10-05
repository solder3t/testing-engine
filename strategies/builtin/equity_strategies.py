"""
equity_strategies.py - Backward Compatibility Shim.

All institutional cash equity strategies have been modularized into:
`strategies.builtin.equity.*`

This module re-exports all strategies so that existing imports:
`from strategies.builtin.equity_strategies import ...`
continue to work without modification.
"""

from .equity import (
    MomentumRsiEmaStrategy,
    KeltnerChannelMomentumStrategy,
    StochasticRsiCrossoverStrategy,
    MacdHistogramAccelerationStrategy,
    HullMaDirectionFlipStrategy,
    VolumePriceActionBreakoutStrategy,
    DonchianChannelTurtleStrategy,
    IchimokuCloudBreakoutStrategy,
    LinearRegressionSlopeStrategy,
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
