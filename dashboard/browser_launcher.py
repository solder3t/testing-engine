"""
dashboard/browser_launcher.py — Chrome Profile Launcher for Testing Engine Dashboard.

Guarantees that the Testing Engine dashboard (http://127.0.0.1:5690/) opens in the
EXACT same Google Chrome profile used by:
1. NSE Scrapper
2. TradingView Scrapper
3. Bot Live Dashboard

Default Profile Directory: C:\\selenium\\ChromeProfile
Default Debug Port: 9222
"""

import os
import sys
import time
import socket
import logging
import subprocess
import urllib.request
import webbrowser
from typing import Optional

try:
    from config import (
        DASHBOARD_PORT,
        CHROME_PATH,
        CHROME_PROFILE_DIR,
        CHROME_DEBUG_PORT,
        CHROME_AUTO_OPEN,
    )
except ImportError:
    DASHBOARD_PORT = 5690
    CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    CHROME_PROFILE_DIR = r"C:\selenium\ChromeProfile"
    CHROME_DEBUG_PORT = 9222
    CHROME_AUTO_OPEN = True

logger = logging.getLogger("dashboard_browser")


def find_chrome_executable(configured_path: Optional[str] = None) -> str:
    """Finds an existing Google Chrome binary on the system."""
    candidates = [
        configured_path,
        CHROME_PATH,
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return configured_path or r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def is_debug_port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    """Checks whether Chrome's remote debugging port is already listening."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def open_dashboard_in_profile(
    url: Optional[str] = None,
    delay: float = 0.5,
    profile_dir: Optional[str] = None,
    debug_port: Optional[int] = None,
    chrome_path: Optional[str] = None
) -> bool:
    """
    Opens the Testing Engine dashboard URL in the shared bot Chrome profile.
    
    1. If Chrome is already running on the debug port (e.g. scraper is active),
       sends a CDP PUT request to open a new tab directly in that instance.
    2. If Chrome is not running, launches a fresh Chrome process pointing to
       the shared profile directory (--user-data-dir=C:\\selenium\\ChromeProfile)
       and debug port (--remote-debugging-port=9222).
    3. Falls back to system webbrowser as last resort.
    """
    if delay > 0:
        time.sleep(delay)

    target_url = url or f"http://127.0.0.1:{DASHBOARD_PORT}/"
    profile = profile_dir or CHROME_PROFILE_DIR
    port = debug_port or CHROME_DEBUG_PORT
    exe = find_chrome_executable(chrome_path)

    os.makedirs(profile, exist_ok=True)

    # ── Method 1: Existing Chrome session with CDP ────────────────────────────
    if is_debug_port_open(port):
        try:
            cdp_new_tab = f"http://127.0.0.1:{port}/json/new?{target_url}"
            req = urllib.request.Request(
                cdp_new_tab,
                data=b"",       # Chrome 115+ requires PUT with empty body
                method="PUT"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            logger.info(
                f"[Dashboard] Opened as new tab in active Chrome profile session ({profile}): {target_url}"
            )
            return True
        except Exception as e:
            logger.warning(f"[Dashboard] CDP PUT to port {port} failed: {e}. Trying process launch fallback...")

    # ── Method 2: Launch Chrome with shared profile ───────────────────────────
    if os.path.isfile(exe):
        try:
            cmd = [
                exe,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1600,1000",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-session-crashed-bubble",
                target_url
            ]

            popen_kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            subprocess.Popen(cmd, **popen_kwargs)
            logger.info(
                f"[Dashboard] Launched Chrome with bot profile ({profile}) on port {port}: {target_url}"
            )
            return True
        except Exception as e:
            logger.warning(f"[Dashboard] Chrome process launch failed: {e}")

    # ── Method 3: System default browser fallback ─────────────────────────────
    try:
        webbrowser.open(target_url)
        logger.info(f"[Dashboard] Opened via system default browser fallback: {target_url}")
        return True
    except Exception as e:
        logger.error(f"[Dashboard] All browser open methods failed: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Launching dashboard in shared Chrome profile: {CHROME_PROFILE_DIR} ...")
    success = open_dashboard_in_profile(delay=0.0)
    print(f"Launch status: {'SUCCESS' if success else 'FAILED'}")
