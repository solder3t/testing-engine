"""
tests/test_archive_manager.py — Tests for ArchiveManager.
"""

import os
import pytest
from data.archive_manager import ArchiveManager
from config import DOWNLOADS_DIR


def test_list_archives():
    mgr = ArchiveManager()
    archives = mgr.list_archives()
    assert isinstance(archives, list)
    assert len(archives) >= 1

    dates = [a["date"] for a in archives]
    assert "2026_09_02" in dates


def test_date_normalization():
    mgr = ArchiveManager()
    arch_dash = mgr.get_archive_by_date("2026-09-02")
    arch_underscore = mgr.get_archive_by_date("2026_09_02")
    assert arch_dash is not None
    assert arch_underscore is not None
    assert arch_dash["date"] == arch_underscore["date"]


def test_list_archives_custom_directory(tmp_path):
    # Create mock session folders in a custom directory
    session_dir = tmp_path / "custom_sessions"
    session_dir.mkdir()
    d1 = session_dir / "2026_09_15"
    d1.mkdir()
    (d1 / "equities.db").touch()
    (d1 / "indices.db").touch()

    mgr = ArchiveManager(downloads_dir=str(session_dir))
    archives = mgr.list_archives(target_dir=str(session_dir))
    assert len(archives) == 1
    assert archives[0]["date"] == "2026_09_15"
    assert archives[0]["type"] == "folder"
    assert "equities.db" in archives[0]["extracted_files"]
