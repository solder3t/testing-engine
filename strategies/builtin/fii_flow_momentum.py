"""
fii_flow_momentum.py - FII Flow & Participant OI Momentum Strategy.
"""

from typing import Dict, Any, Optional, List
from ..base_strategy import BaseStrategy, Signal
from ..parameter_space import Parameter


class FiiFlowMomentumStrategy(BaseStrategy):
    """
    Macro Institutional Alignment Strategy.
    Enters trades only in the direction of FII Index Futures positioning & Cash Flows,
    confirmed by intraday opening range breakouts.
    """

    def __init__(self):
        super().__init__(
            name="FII Flow Alignment",
            description="Trades strictly aligned with FII Index Futures Long/Short ratio & Cash Flows from NSE archives.",
            category="MACRO_FLOW"
        )
        self.entered_today = False

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("min_sentiment_score", "float", 0.3, 0.1, 0.8, 0.1, description="Min sentiment score required"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 15.0, 10.0, 30.0, 2.5, description="Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 35.0, 20.0, 70.0, 5.0, description="Target profit points"))

    def reset(self) -> None:
        self.entered_today = False

    def on_candle(
        self,
        candle: Dict[str, Any],
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Signal]:
        if self.entered_today or len(history) < 15:
            return None

        if not context or "macro_sentiment" not in context:
            return None

        macro = context.get("macro_sentiment", {})
        score = float(macro.get("sentiment_score", 0.0))
        bias = str(macro.get("composite_bias", "NEUTRAL")).upper()
        min_score = self.current_params["min_sentiment_score"]

        # Intraday confirmation: opening 15-min high / low
        first_15 = history[:15]
        hi_15 = max(float(c.get("high", 0)) for c in first_15)
        lo_15 = min(float(c.get("low", 0)) for c in first_15)

        cur_close = float(candle.get("close", 0))
        time_str = str(candle.get("candle_time", ""))

        # FII Bullish Alignment + Breakout above 15m high
        if score >= min_score and bias == "BULLISH" and cur_close > hi_15:
            self.entered_today = True
            return Signal(
                action="ENTER",
                market_bias="CALL",
                option_type="CE",
                strike=round(cur_close / 50.0) * 50.0,
                entry_price=cur_close,
                stop_loss=self.current_params["stop_loss_pts"],
                target=self.current_params["target_pts"],
                confidence=0.88,
                reasoning=f"FII Institutional Bullish Bias (Score={score}, L/S={macro.get('fii_fut_long_short_ratio')}) + 15m Breakout",
                timestamp=time_str,
                metadata=macro
            )

        # FII Bearish Alignment + Breakdown below 15m low
        if score <= -min_score and bias == "BEARISH" and cur_close < lo_15:
            self.entered_today = True
            return Signal(
                action="ENTER",
                market_bias="PUT",
                option_type="PE",
                strike=round(cur_close / 50.0) * 50.0,
                entry_price=cur_close,
                stop_loss=self.current_params["stop_loss_pts"],
                target=self.current_params["target_pts"],
                confidence=0.88,
                reasoning=f"FII Institutional Bearish Bias (Score={score}, L/S={macro.get('fii_fut_long_short_ratio')}) + 15m Breakdown",
                timestamp=time_str,
                metadata=macro
            )

        return None
