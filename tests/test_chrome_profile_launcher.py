"""
tests/test_chrome_profile_launcher.py — Verification for Chrome Profile Launcher.
"""

import pytest
from unittest.mock import patch, MagicMock
from dashboard.browser_launcher import (
    find_chrome_executable,
    is_debug_port_open,
    open_dashboard_in_profile
)
from dashboard.server import app
import config


def test_find_chrome_executable():
    exe = find_chrome_executable()
    assert isinstance(exe, str)
    assert len(exe) > 0


def test_is_debug_port_open():
    # Test checking closed port
    is_open = is_debug_port_open(port=59999, timeout=0.1)
    assert isinstance(is_open, bool)


def test_open_dashboard_in_profile_cdp_mode():
    with patch("dashboard.browser_launcher.is_debug_port_open", return_value=True):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"{}"
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            ok = open_dashboard_in_profile(url="http://127.0.0.1:5690/", delay=0.0)
            assert ok is True
            mock_urlopen.assert_called_once()
            req = mock_urlopen.call_args[0][0]
            assert "9222/json/new?http://127.0.0.1:5690/" in req.full_url
            assert req.get_method() == "PUT"


def test_open_dashboard_in_profile_process_launch():
    with patch("dashboard.browser_launcher.is_debug_port_open", return_value=False):
        with patch("dashboard.browser_launcher.os.path.isfile", return_value=True):
            with patch("subprocess.Popen") as mock_popen:
                ok = open_dashboard_in_profile(url="http://127.0.0.1:5690/", delay=0.0)
                assert ok is True
                mock_popen.assert_called_once()
                cmd = mock_popen.call_args[0][0]
                assert any("--user-data-dir=" in str(arg) for arg in cmd)
                assert any("ChromeProfile" in str(arg) for arg in cmd)
                assert any("--remote-debugging-port=" in str(arg) for arg in cmd)


def test_api_open_browser_endpoint():
    with app.test_client() as client:
        with patch("dashboard.server.open_dashboard_in_profile", return_value=True):
            res = client.get("/api/open_browser")
            assert res.status_code == 200
            data = res.get_json()
            assert data["status"] == "success"
            assert data["opened"] is True
            assert "ChromeProfile" in data["profile"]
