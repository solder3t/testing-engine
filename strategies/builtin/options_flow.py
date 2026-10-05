"""
options_flow.py - Options Chain Flow Strategy (PCR, Max Pain, ATM IV Skew).
"""

from typing import Dict, Any, Optional, List
from ..base_strategy import BaseStrategy, Signal
from ..parameter_space import Parameter


class OptionsFlowStrategy(BaseStrategy):
    """
    Options Flow & Positioning Strategy.
    Exploits institutional options order flow, Put-Call Ratio extremes,
    and distance from Max Pain / Gamma flip levels.
    """

    def __init__(self):
        super().__init__(
            name="Options Flow & PCR",
            description="Institutional sentiment from live Options Chain PCR, Max Pain, and ATM IV skew.",
            category="OPTIONS_FLOW"
        )
        self.last_signal_time = ""

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("pcr_bullish", "float", 1.20, 1.0, 1.8, 0.05, description="Bullish PCR threshold"))
        self.parameters.add(Parameter("pcr_bearish", "float", 0.80, 0.4, 1.0, 0.05, description="Bearish PCR threshold"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 8.0, 35.0, 2.5, description="Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 30.0, 15.0, 60.0, 5.0, description="Target profit points"))

    def reset(self) -> None:
        self.last_signal_time = ""

    def on_candle(
        self,
        candle: Dict[str, Any],
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Signal]:
        if not context or "options_data" not in context:
            return None

        opt = context.get("options_data", {})
        if not opt:
            return None

        pcr = float(opt.get("pcr_oi", 0) or 0)
        max_pain = float(opt.get("max_pain_strike", 0) or 0)
        gamma_zone = str(opt.get("gamma_zone", "")).upper()
        spot = float(candle.get("close", 0))
        time_str = str(candle.get("candle_time", ""))

        # Only evaluate once every 5 candles to prevent over-triggering
        if len(history) % 5 != 0:
            return None

        pcr_bull = self.current_params["pcr_bullish"]
        pcr_bear = self.current_params["pcr_bearish"]

        # Strong Bullish Flow: PCR > 1.20 and Spot above Max Pain
        if pcr >= pcr_bull and (max_pain == 0 or spot >= max_pain):
            return Signal(
                action="ENTER",
                market_bias="CALL",
                option_type="CE",
                strike=round(spot / 50.0) * 50.0,
                entry_price=spot,
                stop_loss=self.current_params["stop_loss_pts"],
                target=self.current_params["target_pts"],
                confidence=0.85,
                reasoning=f"Bullish Options Flow: PCR={round(pcr, 2)} >= {pcr_bull}, Spot={round(spot, 1)} above MaxPain={max_pain}",
                timestamp=time_str,
                metadata={"pcr": pcr, "max_pain": max_pain, "gamma_zone": gamma_zone}
            )

        # Strong Bearish Flow: PCR < 0.80 and Spot below Max Pain
        if 0 < pcr <= pcr_bear and (max_pain == 0 or spot <= max_pain):
            return Signal(
                action="ENTER",
                market_bias="PUT",
                option_type="PE",
                strike=round(spot / 50.0) * 50.0,
                entry_price=spot,
                stop_loss=self.current_params["stop_loss_pts"],
                target=self.current_params["target_pts"],
                confidence=0.85,
                reasoning=f"Bearish Options Flow: PCR={round(pcr, 2)} <= {pcr_bear}, Spot={round(spot, 1)} below MaxPain={max_pain}",
                timestamp=time_str,
                metadata={"pcr": pcr, "max_pain": max_pain, "gamma_zone": gamma_zone}
            )

        return None
