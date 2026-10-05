"""
strategies/builtin/ai/online_ai.py — Mode 1: Online AI Evaluation via Yantra Gateway.

Features:
- Dedicated safe key: uses YANTRA_API_KEY_3 or GEMINI_API_KEY from .env
- Direct urllib.request implementation
- JSON markdown parsing into structured Signal objects
- Response caching to avoid redundant API credit consumption during repeated runs
- Latency and cost tracking
"""

import os
import json
import time
import hashlib
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Tuple, List
from strategies.signal import Signal


class OnlineAIEngine:
    """Yantra Online AI gateway client for backtesting."""

    DEFAULT_URL = "https://api.aitklabs.in/v1/chat/completions"
    DEFAULT_MODEL = "gemini-2.5-flash"

    DEFAULT_SYSTEM_PROMPT = """You are an elite institutional options scalping AI for NSE India (NIFTY 50 and BANKNIFTY).
Analyze the real-time technicals, market internals, options chain, and breadth data provided.
Decide whether to ENTER a high-probability trade, WAIT for a cleaner setup, HOLD an open position, or EXIT_NOW.

You MUST respond ONLY with a valid JSON object adhering to this schema:
{
  "action": "ENTER" | "WAIT" | "HOLD" | "EXIT_NOW",
  "market_bias": "CALL" | "PUT" | "NEUTRAL",
  "option_type": "CE" | "PE" | null,
  "strike": 0,
  "stop_loss": 15.0,
  "target": 30.0,
  "risk_reward": "1:2.0",
  "confidence": 0.85,
  "reasoning": "Clear concise institutional rationale"
}
Do NOT include any commentary outside the JSON."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_sec: int = 60
    ):
        self.api_key = api_key or self._load_key_from_env()
        self.model = model or self.DEFAULT_MODEL
        self.timeout_sec = timeout_sec
        self.response_cache: Dict[str, Dict[str, Any]] = {}

    def _load_key_from_env(self) -> str:
        """Load API key from environment."""
        return os.environ.get("YANTRA_API_KEY_3") or os.environ.get("GEMINI_API_KEY") or ""

    def evaluate_market_state(
        self,
        candle: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[Signal], float]:
        """
        Submits market data snapshot to LLM gateway.
        Returns (Signal, latency_ms).
        """
        t0 = time.perf_counter()
        if not self.api_key:
            return None, 0.0

        ctx_str = json.dumps({"candle": candle, "context": context or {}}, default=str)
        cache_key = hashlib.md5(ctx_str.encode("utf-8")).hexdigest()

        if cache_key in self.response_cache:
            raw = self.response_cache[cache_key]
            latency = round((time.perf_counter() - t0) * 1000, 2)
            return self._parse_json_to_signal(raw), latency

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Current market state: {ctx_str}"}
            ],
            "temperature": 0.2
        }

        try:
            req = urllib.request.Request(
                self.DEFAULT_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = self._extract_json(content)
                self.response_cache[cache_key] = parsed
                latency = round((time.perf_counter() - t0) * 1000, 2)
                return self._parse_json_to_signal(parsed), latency
        except Exception:
            latency = round((time.perf_counter() - t0) * 1000, 2)
            return None, latency

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON object from markdown fenced text."""
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        return json.loads(cleaned)

    def _parse_json_to_signal(self, d: Dict[str, Any]) -> Signal:
        """Converts raw decision dictionary into Signal object."""
        return Signal(
            action=d.get("action", "WAIT"),
            market_bias=d.get("market_bias", "NEUTRAL"),
            option_type=d.get("option_type", "CE"),
            strike=float(d.get("strike", 0.0)),
            stop_loss=float(d.get("stop_loss", 15.0)),
            target=float(d.get("target", 30.0)),
            confidence=float(d.get("confidence", 0.8)),
            reasoning=d.get("reasoning", "AI decision"),
        )
