"""
data/archive_manager.py — Discovery and Selective Extraction of Market Archives.

Scans any user-specified directory for RAR archives or pre-extracted date folders,
and manages selective extraction into the testing-engine cache directory.
"""

import os
import re
import glob
import sqlite3
import subprocess
import logging
from typing import List, Dict, Optional

from config import DOWNLOADS_DIR, DATA_CACHE_DIR

logger = logging.getLogger("archive_manager")

STANDARD_DBS = [
    "equities.db",
    "indices.db",
    "indicators.db",
    "trade.db",
    "optionchain_snapshot.db",
    "master.db",
    "circuit_limits.json",
]


def _detect_session_date_from_folder(folder_path: str) -> Optional[str]:
    """Inspects SQLite databases inside a folder to determine the exact market session date."""
    idx_db = os.path.join(folder_path, "indices.db")
    if os.path.exists(idx_db):
        try:
            with sqlite3.connect(f"file:{idx_db}?mode=ro", uri=True) as conn:
                for tbl in ["idx_13_NIFTY", "idx_nifty"]:
                    try:
                        row = conn.execute(f"SELECT tick_time FROM {tbl} LIMIT 1").fetchone()
                        if row and row[0]:
                            return row[0][:10].replace("-", "_")
                    except Exception:
                        pass
        except Exception:
            pass

    eq_db = os.path.join(folder_path, "equities.db")
    if os.path.exists(eq_db):
        try:
            with sqlite3.connect(f"file:{eq_db}?mode=ro", uri=True) as conn:
                tbl = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'eq_%' LIMIT 1").fetchone()
                if tbl:
                    row = conn.execute(f"SELECT tick_time FROM {tbl[0]} LIMIT 1").fetchone()
                    if row and row[0]:
                        return row[0][:10].replace("-", "_")
        except Exception:
            pass
    return None


class ArchiveManager:
    """Manages archive discovery, folder inspection, and selective extraction."""

    def __init__(self, downloads_dir: str = DOWNLOADS_DIR, cache_dir: str = DATA_CACHE_DIR):
        self.downloads_dir = os.path.expanduser(downloads_dir)
        self.cache_dir = os.path.expanduser(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

    def list_archives(self, target_dir: Optional[str] = None) -> List[Dict]:
        """
        Discovers market recordings and pre-extracted sessions in target_dir.
        Filters specifically for valid market sessions (date matching YYYY-MM-DD / YYYY_MM_DD or DB presence),
        preventing non-trading archives from polluting the session list.
        """
        scan_path = os.path.expanduser(target_dir) if target_dir else self.downloads_dir
        if not os.path.exists(scan_path):
            return []

        # Check if scan_path itself is a market session directory
        if os.path.isdir(scan_path):
            self_dbs = [f for f in STANDARD_DBS if os.path.exists(os.path.join(scan_path, f))]
            if self_dbs:
                basename = os.path.basename(scan_path.rstrip("/\\"))
                date_match = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", basename)
                norm_date = date_match.group(1).replace("-", "_") if date_match else _detect_session_date_from_folder(scan_path)
                if norm_date:
                    size_mb = sum(os.path.getsize(os.path.join(scan_path, f)) for f in self_dbs) / (1024 * 1024)
                    return [{
                        "date": norm_date,
                        "name": basename,
                        "filename": basename,
                        "path": scan_path,
                        "type": "folder",
                        "source_type": "folder",
                        "format": "directory",
                        "size_mb": round(size_mb, 1),
                        "is_extracted": True,
                        "cache_path": scan_path,
                        "extracted_files": self_dbs,
                        "parent_dir": os.path.dirname(scan_path)
                    }]

        sources = []
        seen_dates = set()

        # 1. Look for date-patterned .rar and .zip archives (e.g. 2026_09_02.rar, 2026-09-08.zip)
        archive_files = []
        for pat in [os.path.join(scan_path, "*.rar"), os.path.join(scan_path, "*.zip")]:
            archive_files.extend(glob.glob(pat))

        for f in sorted(archive_files):
            basename = os.path.basename(f)
            date_match = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", basename)
            if not date_match:
                # Skip non-market archive files (e.g. BOT 2.0 modified with scrapper.rar, trade.zip)
                continue

            date_str = date_match.group(1).replace("-", "_")
            size_mb = os.path.getsize(f) / (1024 * 1024)
            cache_path = os.path.join(self.cache_dir, date_str)

            is_extracted = os.path.isdir(cache_path) and any(
                os.path.exists(os.path.join(cache_path, db)) for db in ["equities.db", "trade.db", "indicators.db"]
            )
            extracted_dbs = []
            if os.path.isdir(cache_path):
                extracted_dbs = [os.path.basename(p) for p in glob.glob(os.path.join(cache_path, "*"))]

            sources.append({
                "date": date_str,
                "name": basename,
                "filename": basename,
                "path": f,
                "type": "rar" if basename.endswith(".rar") else "archive",
                "source_type": "archive",
                "format": os.path.splitext(basename)[1].lstrip("."),
                "size_mb": round(size_mb, 1),
                "is_extracted": is_extracted,
                "cache_path": cache_path,
                "extracted_files": extracted_dbs,
                "parent_dir": scan_path
            })
            seen_dates.add(date_str)

        # 2. Look for pre-extracted session directories in scan_path
        try:
            entries = os.listdir(scan_path)
            for entry in sorted(entries):
                full_entry_path = os.path.join(scan_path, entry)
                if not os.path.isdir(full_entry_path):
                    continue

                dbs_found = [
                    f for f in STANDARD_DBS
                    if os.path.exists(os.path.join(full_entry_path, f))
                ]
                if dbs_found:
                    date_match = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", entry)
                    norm_date = date_match.group(1).replace("-", "_") if date_match else None
                    if not norm_date:
                        norm_date = _detect_session_date_from_folder(full_entry_path)
                    if not norm_date:
                        # Skip directories without identifiable market dates
                        continue

                    if norm_date not in seen_dates:
                        # Fast size calculation of DB files only (avoids deep recursive traversal)
                        folder_size_mb = sum(
                            os.path.getsize(os.path.join(full_entry_path, f))
                            for f in dbs_found
                        ) / (1024 * 1024)

                        sources.append({
                            "date": norm_date,
                            "name": entry,
                            "filename": entry,
                            "path": full_entry_path,
                            "type": "folder",
                            "source_type": "folder",
                            "format": "directory",
                            "size_mb": round(folder_size_mb, 1),
                            "is_extracted": True,
                            "cache_path": full_entry_path,
                            "extracted_files": dbs_found,
                            "parent_dir": scan_path
                        })
                        seen_dates.add(norm_date)
        except Exception as e:
            logger.warning(f"Error scanning directories in {scan_path}: {e}")

        sources.sort(key=lambda x: x["date"])
        return sources

    def get_archive_by_date(self, date_str: str, target_dir: Optional[str] = None) -> Optional[Dict]:
        """Retrieve source info for a specific date (supports '2026-09-02' or '2026_09_02')."""
        norm_date = date_str.replace("-", "_")
        for arch in self.list_archives(target_dir=target_dir):
            if arch["date"] == norm_date:
                return arch
        return None

    def extract_archive(
        self,
        date_str: str,
        files_to_extract: Optional[List[str]] = None,
        force: bool = False,
        target_dir: Optional[str] = None
    ) -> Dict:
        """
        Selectively extract databases from a date's RAR archive.
        If source is already an extracted folder, returns success immediately.
        """
        norm_date = date_str.replace("-", "_")
        arch = self.get_archive_by_date(norm_date, target_dir=target_dir)
        if not arch:
            return {"success": False, "error": f"Archive or folder for date {norm_date} not found."}

        # If already a pre-extracted directory, no extraction needed
        if arch.get("source_type") == "folder":
            return {
                "success": True,
                "message": f"Session {norm_date} is already an extracted directory.",
                "cache_dir": arch["path"],
                "extracted_files": arch["extracted_files"]
            }

        cache_target_dir = os.path.join(self.cache_dir, norm_date)
        os.makedirs(cache_target_dir, exist_ok=True)

        selected = files_to_extract or STANDARD_DBS
        rar_path = arch["path"]

        # Build list of archive internal paths
        extract_args = []
        for item in selected:
            dest_file = os.path.join(cache_target_dir, item)
            if not force and os.path.exists(dest_file):
                continue
            extract_args.append(f"{norm_date}/{item}")

        if not extract_args:
            return {
                "success": True,
                "message": f"All requested files already available for {norm_date}",
                "cache_dir": cache_target_dir,
                "extracted_files": os.listdir(cache_target_dir)
            }

        cmd = ["unrar", "e", "-o+", rar_path] + extract_args + [cache_target_dir]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                logger.error(f"Unrar error for {norm_date}: {res.stderr}")
                return {"success": False, "error": res.stderr}
            return {
                "success": True,
                "message": f"Extracted {len(extract_args)} files for {norm_date}",
                "cache_dir": cache_target_dir,
                "extracted_files": os.listdir(cache_target_dir)
            }
        except Exception as e:
            logger.exception(f"Extraction failed: {e}")
            return {"success": False, "error": str(e)}

    def get_database_path(self, date_str: str, db_name: str, target_dir: Optional[str] = None) -> Optional[str]:
        """
        Get the absolute path to a database.
        Checks:
        1. Direct folder if user pointed to an extracted directory
        2. Cached directory
        3. Attempts selective extraction from RAR
        """
        norm_date = date_str.replace("-", "_")

        # 1. Check if source is a direct folder
        arch = self.get_archive_by_date(norm_date, target_dir=target_dir)
        if arch and arch.get("source_type") == "folder":
            direct_file = os.path.join(arch["path"], db_name)
            if os.path.exists(direct_file):
                return direct_file

        # 2. Check cache directory
        target_path = os.path.join(self.cache_dir, norm_date, db_name)
        if os.path.exists(target_path):
            return target_path

        # 3. Attempt selective extraction
        res = self.extract_archive(norm_date, [db_name], target_dir=target_dir)
        if res.get("success") and os.path.exists(target_path):
            return target_path

        return None
