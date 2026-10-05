"""
strategies/builtin/ai/local_ai.py — Mode 2: Local AI Backtesting via Ollama.

Communicates with local Ollama daemon (default: http://localhost:11434).
Features:
- Auto-discovers local models (e.g. qwen2.5:3b, mistral:7b, deepseek)
- Non-streaming high-speed generation
- JSON parsing and conversion into Signal objects
- In-memory response caching
- Latency benchmarking with graceful fallback when Ollama is offline
"""

import json
import time
import hashlib
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List, Tuple
from strategies.signal import Signal


class LocalAIEngine:
    """Client for local Ollama models in backtesting."""

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "qwen2.5:3b"

    DEFAULT_SYSTEM_PROMPT = """You are an algorithmic options trading assistant.
Evaluate the market candle data and return a JSON decision:
{
  "action": "ENTER" | "WAIT" | "HOLD" | "EXIT_NOW",
  "market_bias": "CALL" | "PUT" | "NEUTRAL",
  "option_type": "CE" | "PE" | null,
  "strike": 0,
  "stop_loss": 15.0,
  "target": 30.0,
  "confidence": 0.8,
  "reasoning": "Brief technical justification"
}
Respond with ONLY the JSON object."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: Optional[str] = None,
        timeout_sec: int = 120
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.timeout_sec = timeout_sec
        self.response_cache: Dict[str, Dict[str, Any]] = {}

    def get_installed_models(self) -> List[str]:
        """Query Ollama daemon for available local models."""
        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def evaluate_market_state(
        self,
        candle: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[Signal], float]:
        """
        Queries Ollama model with market snapshot.
        Returns (Signal, latency_ms).
        """
        t0 = time.perf_counter()
        ctx_str = json.dumps({"candle": candle, "context": context or {}}, default=str)
        cache_key = hashlib.md5(f"{self.model}:{ctx_str}".encode("utf-8")).hexdigest()

        if cache_key in self.response_cache:
            raw = self.response_cache[cache_key]
            latency = round((time.perf_counter() - t0) * 1000, 2)
            return self._parse_json_to_signal(raw), latency

        payload = {
            "model": self.model,
            "prompt": f"System: {self.DEFAULT_SYSTEM_PROMPT}\nUser: Current market: {ctx_str}\nAssistant:",
            "stream": False,
            "format": "json"
        }

        url = f"{self.base_url}/api/generate"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                resp_text = data.get("response", "{}")
                parsed = json.loads(resp_text)
                self.response_cache[cache_key] = parsed
                latency = round((time.perf_counter() - t0) * 1000, 2)
                return self._parse_json_to_signal(parsed), latency
        except Exception:
            latency = round((time.perf_counter() - t0) * 1000, 2)
            return None, latency

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
            reasoning=d.get("reasoning", "Local AI decision"),
        )
