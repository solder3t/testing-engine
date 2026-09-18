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
import zipfile
import shutil
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

        # 0. Check if scan_path is a single file (e.g. 2026_09_02.rar or equities.db)
        if os.path.isfile(scan_path):
            basename = os.path.basename(scan_path)
            if scan_path.lower().endswith((".rar", ".zip")):
                date_match = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", basename)
                date_str = date_match.group(1).replace("-", "_") if date_match else os.path.splitext(basename)[0].replace("-", "_")
                size_mb = os.path.getsize(scan_path) / (1024 * 1024)
                cache_path = os.path.join(self.cache_dir, date_str)
                is_extracted = os.path.isdir(cache_path) and any(
                    os.path.exists(os.path.join(cache_path, db)) for db in ["equities.db", "trade.db", "indicators.db"]
                )
                extracted_dbs = []
                if os.path.isdir(cache_path):
                    extracted_dbs = [os.path.basename(p) for p in glob.glob(os.path.join(cache_path, "*"))]
                return [{
                    "date": date_str,
                    "name": basename,
                    "filename": basename,
                    "path": scan_path,
                    "type": "rar" if basename.lower().endswith(".rar") else "archive",
                    "source_type": "archive",
                    "format": os.path.splitext(basename)[1].lstrip("."),
                    "size_mb": round(size_mb, 1),
                    "is_extracted": is_extracted,
                    "cache_path": cache_path,
                    "extracted_files": extracted_dbs,
                    "parent_dir": os.path.dirname(scan_path)
                }]
            elif scan_path.lower().endswith(".db"):
                parent_dir = os.path.dirname(scan_path)
                return self.list_archives(target_dir=parent_dir)

        # 1. Check if scan_path itself is a market session directory
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

        # Also search 1 level down in subdirectories (e.g. ~/Downloads/trading-data/*.rar)
        if os.path.isdir(scan_path):
            try:
                for sub in os.listdir(scan_path):
                    sub_path = os.path.join(scan_path, sub)
                    if os.path.isdir(sub_path) and not sub.startswith("."):
                        for pat in [os.path.join(sub_path, "*.rar"), os.path.join(sub_path, "*.zip")]:
                            archive_files.extend(glob.glob(pat))
            except Exception:
                pass

        for f in sorted(archive_files):
            basename = os.path.basename(f)
            date_match = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", basename)
            if not date_match:
                # Skip non-market archive files (e.g. BOT 2.0 modified with scrapper.rar, trade.zip)
                continue

            date_str = date_match.group(1).replace("-", "_")
            if date_str in seen_dates:
                continue

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
                "parent_dir": os.path.dirname(f)
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

    def verify_database_integrity(self, db_path: str) -> bool:
        """Verifies SQLite database page integrity using PRAGMA quick_check."""
        if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
            return False
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                cursor = conn.cursor()
                res = cursor.execute("PRAGMA quick_check;").fetchone()
                return bool(res and res[0] == "ok")
        except Exception as e:
            logger.warning(f"Integrity check failed for {db_path}: {e}")
            return False

    def extract_archive(
        self,
        date_str: str,
        files_to_extract: Optional[List[str]] = None,
        force: bool = False,
        target_dir: Optional[str] = None
    ) -> Dict:
        """
        Selectively extract databases from a date's ZIP or RAR archive.
        If source is already an extracted folder, returns success immediately.
        Supports native zipfile for .zip, and unrar -> 7z -> unar fallbacks for .rar.
        Automatically handles nested vs flat archive folder structures.
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
        arch_path = arch["path"]

        # Check which files actually need extraction
        needed = []
        for item in selected:
            dest_file = os.path.join(cache_target_dir, item)
            if not force and os.path.exists(dest_file):
                continue
            needed.append(item)

        if not needed:
            return {
                "success": True,
                "message": f"All requested files already available for {norm_date}",
                "cache_dir": cache_target_dir,
                "extracted_files": os.listdir(cache_target_dir)
            }

        # 1. Native ZIP handling (zero external CLI dependencies)
        if arch_path.lower().endswith(".zip"):
            try:
                extracted = []
                with zipfile.ZipFile(arch_path, "r") as zf:
                    namelist = zf.namelist()
                    for item in needed:
                        dest_file = os.path.join(cache_target_dir, item)
                        # Match member by exact name, basename, or nested path
                        match = next(
                            (m for m in namelist if os.path.basename(m) == item or m.endswith(f"/{item}") or m == item),
                            None
                        )
                        if match:
                            with zf.open(match) as src, open(dest_file, "wb") as dst:
                                shutil.copyfileobj(src, dst)
                            extracted.append(item)
                return {
                    "success": True,
                    "message": f"Extracted {len(extracted)} files from ZIP for {norm_date}",
                    "cache_dir": cache_target_dir,
                    "extracted_files": os.listdir(cache_target_dir)
                }
            except Exception as e:
                logger.exception(f"ZIP extraction failed: {e}")
                return {"success": False, "error": str(e)}

        # 2. RAR handling with multi-backend fallbacks (unrar -> 7z -> unar)
        unrar_bin = shutil.which("unrar")
        p7z_bin = shutil.which("7z")
        unar_bin = shutil.which("unar")

        # Patterns matching both root and nested paths (e.g. *equities.db or 2026_09_02/equities.db)
        extract_patterns = [f"*{item}" for item in needed]
        last_err = ""

        # A. Try unrar
        if unrar_bin:
            cmd = [unrar_bin, "e", "-o+", arch_path] + extract_patterns + [cache_target_dir]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return {
                    "success": True,
                    "message": f"Extracted {len(needed)} files for {norm_date} using unrar",
                    "cache_dir": cache_target_dir,
                    "extracted_files": os.listdir(cache_target_dir)
                }
            # Fallback to explicit nested prefix: {norm_date}/item
            cmd_fb = [unrar_bin, "e", "-o+", arch_path] + [f"{norm_date}/{item}" for item in needed] + [cache_target_dir]
            res_fb = subprocess.run(cmd_fb, capture_output=True, text=True, check=False)
            if res_fb.returncode == 0:
                return {
                    "success": True,
                    "message": f"Extracted {len(needed)} files for {norm_date} using unrar path fallback",
                    "cache_dir": cache_target_dir,
                    "extracted_files": os.listdir(cache_target_dir)
                }
            last_err = res.stderr or res_fb.stderr

        # B. Try 7z
        if p7z_bin:
            cmd = [p7z_bin, "e", "-y", f"-o{cache_target_dir}", arch_path] + extract_patterns
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return {
                    "success": True,
                    "message": f"Extracted {len(needed)} files for {norm_date} using 7z",
                    "cache_dir": cache_target_dir,
                    "extracted_files": os.listdir(cache_target_dir)
                }
            last_err = res.stderr or last_err

        # C. Try unar
        if unar_bin:
            cmd = [unar_bin, "-f", "-o", cache_target_dir, arch_path]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return {
                    "success": True,
                    "message": f"Extracted files for {norm_date} using unar",
                    "cache_dir": cache_target_dir,
                    "extracted_files": os.listdir(cache_target_dir)
                }
            last_err = res.stderr or last_err

        if not unrar_bin and not p7z_bin and not unar_bin:
            return {
                "success": False,
                "error": "No RAR extraction tool found. Please install 'unrar', 'p7zip-full' (7z), or 'unar'."
            }

        return {"success": False, "error": last_err or "RAR extraction failed with all available tools"}

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
