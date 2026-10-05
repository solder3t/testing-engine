"""
analytics/session_store.py — Persistent Storage for Mass Iteration Experiment Sessions.

Saves each completed mass optimization session as JSON in `results/sessions/<session_id>.json`
and maintains `results/sessions/_index.json` for rapid catalog browsing.
"""

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional


_DEFAULT_SESSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # testing-engine-main/
    "results",
    "sessions"
)


class SessionStore:
    """Manages persistence and retrieval of mass optimization sessions."""

    def __init__(self, sessions_dir: Optional[str] = None):
        self.sessions_dir = sessions_dir or _DEFAULT_SESSIONS_DIR
        os.makedirs(self.sessions_dir, exist_ok=True)
        self._index_path = os.path.join(self.sessions_dir, "_index.json")
        self._index: Dict[str, Dict[str, Any]] = self._load_index()

    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def save_session(
        self,
        job_results: Dict[str, Any],
        spec: Dict[str, Any],
        name: Optional[str] = None
    ) -> str:
        """Persists a completed job to disk and updates index."""
        session_id = str(uuid.uuid4())[:16]
        saved_at = time.time()

        if name is None:
            strat = spec.get("strategy_type", "STRATEGY")
            n_runs = job_results.get("total_runs", 0)
            ts = time.strftime("%Y%m%d_%H%M", time.localtime(saved_at))
            name = f"{strat}_{n_runs}runs_{ts}"

        best = job_results.get("best_run") or {}
        summary = {
            "total_runs": job_results.get("total_runs", 0),
            "valid_runs": job_results.get("valid_runs", 0),
            "errored_runs": job_results.get("errored_runs", 0),
            "execution_time_ms": job_results.get("execution_time_ms", 0),
            "strategy_type": job_results.get("strategy_type", ""),
            "sampling_mode": job_results.get("sampling_mode", "GRID"),
            "best_pnl_net": best.get("pnl_net", 0.0),
            "best_sharpe": best.get("sharpe_ratio", 0.0),
            "best_win_rate": best.get("win_rate_pct", 0.0),
            "best_params": best.get("parameters", {}),
        }

        session_data = {
            "session_id": session_id,
            "name": name,
            "saved_at": saved_at,
            "spec": spec,
            "summary": summary,
            "results": job_results,
        }

        file_path = os.path.join(self.sessions_dir, f"{session_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, default=str)

        self._index[session_id] = {
            "session_id": session_id,
            "name": name,
            "saved_at": saved_at,
            "saved_at_human": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(saved_at)),
            "summary": summary,
        }
        self._save_index()
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Loads full session payload from disk."""
        file_path = os.path.join(self.sessions_dir, f"{session_id}.json")
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Returns sorted list of session summaries."""
        sessions = list(self._index.values())
        sessions.sort(key=lambda s: s.get("saved_at", 0), reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Deletes session file and index entry."""
        file_path = os.path.join(self.sessions_dir, f"{session_id}.json")
        deleted = False
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                deleted = True
            except Exception:
                pass

        if session_id in self._index:
            del self._index[session_id]
            self._save_index()
            deleted = True

        return deleted
