"""
Options strategies suite package.
Modularized into flow momentum, volatility decay, and strike/OI positioning.
"""

from .flow_momentum import (
    OptionsFlowMomentumStrategy,
    GammaScalpMomentumStrategy,
    OptionBuyerVwapCrossStrategy,
    OptionBreakoutConsolidationStrategy,
)
from .volatility_decay import (
    IvExpansionBreakoutStrategy,
    StraddlePremiumDecayStrategy,
    ThetaHarvestSlopeStrategy,
    VolatilityCrushReversionStrategy,
)
from .strike_oi import (
    PcrExtremeReversalStrategy,
    ExpiryPinningMagnetStrategy,
    MaxPainConvergenceStrategy,
    OiBuildupTrendStrategy,
)

__all__ = [
    "OptionsFlowMomentumStrategy",
    "GammaScalpMomentumStrategy",
    "OptionBuyerVwapCrossStrategy",
    "OptionBreakoutConsolidationStrategy",
    "IvExpansionBreakoutStrategy",
    "StraddlePremiumDecayStrategy",
    "ThetaHarvestSlopeStrategy",
    "VolatilityCrushReversionStrategy",
    "PcrExtremeReversalStrategy",
    "ExpiryPinningMagnetStrategy",
    "MaxPainConvergenceStrategy",
    "OiBuildupTrendStrategy",
]
