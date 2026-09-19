"""
analytics/config_sync.py — Safe Synchronization Engine from Testing Engine to Trading Engine.

Safely updates configuration parameters in trading-engine/.env:
1. Creates an automatic timestamped backup (.env.bak.<YYYYMMDD_HHMMSS>).
2. Performs in-place key replacement preserving existing comments, whitespace, and ordering.
3. Appends previously non-existent parameters under an explicit provenance banner.
4. Performs atomic write via temporary file replacement.
"""

import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple


DEFAULT_TRADING_ENGINE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "trading-engine")
)
DEFAULT_ENV_PATH = os.path.join(DEFAULT_TRADING_ENGINE_DIR, ".env")


class ConfigSyncEngine:
    """Synchronizes empirical strategy and AI parameters to trading-engine/.env."""

    def __init__(self, env_path: Optional[str] = None):
        self.env_path = os.path.abspath(env_path) if env_path else DEFAULT_ENV_PATH

    def sync_parameters(
        self,
        updates: Dict[str, Any],
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """
        Safely apply key-value updates to the target .env file.
        
        Args:
            updates: Dictionary of { KEY: VALUE } pairs to update or add.
            create_backup: If True, writes .env.bak.<timestamp> before modifying.
            
        Returns:
            Dict containing operation summary: status, backup_path, updated_keys, added_keys.
        """
        if not os.path.exists(self.env_path):
            # If target .env does not exist, check if directory exists
            target_dir = os.path.dirname(self.env_path)
            if not os.path.exists(target_dir):
                raise FileNotFoundError(f"Trading engine directory not found at: {target_dir}")

        backup_path = None
        if os.path.exists(self.env_path) and create_backup:
            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.env_path}.bak.{ts_str}"
            shutil.copy2(self.env_path, backup_path)

        existing_lines: List[str] = []
        if os.path.exists(self.env_path):
            with open(self.env_path, "r", encoding="utf-8") as f:
                existing_lines = f.readlines()

        # Format update values into string representations
        normalized_updates: Dict[str, str] = {}
        for k, v in updates.items():
            clean_key = str(k).strip()
            if isinstance(v, bool):
                val_str = "True" if v else "False"
            elif v is None:
                val_str = ""
            else:
                val_str = str(v).strip()
            normalized_updates[clean_key] = val_str

        updated_keys: List[str] = []
        added_keys: List[str] = []
        new_lines: List[str] = []
        keys_seen = set()

        for line in existing_lines:
            stripped = line.strip()
            # If line is a comment or blank, keep intact
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            if "=" in line:
                key, _ = line.split("=", 1)
                clean_key = key.strip()
                if clean_key in normalized_updates:
                    new_val = normalized_updates[clean_key]
                    new_lines.append(f"{clean_key}={new_val}\n")
                    updated_keys.append(clean_key)
                    keys_seen.add(clean_key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # Keys in updates that were not present in existing lines
        remaining_keys = [k for k in normalized_updates if k not in keys_seen]
        if remaining_keys:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append("\n# ── Tuned by Testing Engine Optimization Cockpit ───────────────────\n")
            new_lines.append(f"# Synchronized on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            for k in remaining_keys:
                new_val = normalized_updates[k]
                new_lines.append(f"{k}={new_val}\n")
                added_keys.append(k)

        # Atomic write via temporary file
        tmp_path = f"{self.env_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        os.replace(tmp_path, self.env_path)

        return {
            "status": "ok",
            "message": f"Successfully synchronized {len(updated_keys) + len(added_keys)} parameters to trading-engine/.env",
            "env_path": self.env_path,
            "backup_file": backup_path,
            "updated_keys": updated_keys,
            "added_keys": added_keys
        }


def sync_to_trading_engine(
    updates: Dict[str, Any],
    env_path: Optional[str] = None
) -> Dict[str, Any]:
    """Helper functional interface for ConfigSyncEngine."""
    engine = ConfigSyncEngine(env_path=env_path)
    return engine.sync_parameters(updates=updates, create_backup=True)
