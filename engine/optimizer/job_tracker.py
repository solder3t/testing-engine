"""
engine/optimizer/job_tracker.py — Optimization job tracking and SSE event streaming state.
"""

import queue
import time
from typing import Any, Dict, Optional


class HyperJob:
    """Tracks state and progress of an asynchronous mass optimization job."""

    def __init__(self, job_id: str, total: int):
        self.job_id = job_id
        self.total = total
        self.completed = 0
        self.started_at = time.time()
        self.finished_at: Optional[float] = None
        self.status = "RUNNING"  # RUNNING | DONE | ERROR | CANCELLED
        self.error: Optional[str] = None
        self.results: Optional[Dict[str, Any]] = None
        self.progress_queue: queue.Queue = queue.Queue(maxsize=5000)

    @property
    def elapsed_sec(self) -> float:
        end = self.finished_at or time.time()
        return round(end - self.started_at, 2)

    @property
    def pct_complete(self) -> float:
        if self.total == 0:
            return 100.0
        return round((self.completed / self.total) * 100.0, 1)

    @property
    def eta_sec(self) -> Optional[float]:
        if self.completed == 0:
            return None
        rate = self.completed / max(self.elapsed_sec, 0.001)
        remaining = self.total - self.completed
        return round(remaining / rate, 1)

    def to_status_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "total": self.total,
            "completed": self.completed,
            "pct_complete": self.pct_complete,
            "elapsed_sec": self.elapsed_sec,
            "eta_sec": self.eta_sec,
        }


__all__ = ["HyperJob"]
