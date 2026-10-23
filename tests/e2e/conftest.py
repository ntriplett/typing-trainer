"""Shared fixture for real-browser e2e tests: spawns the actual FastAPI
app as a subprocess (the same way the launcher does), pointed at an
isolated temp DB via TYPING_TRAINER_DB_PATH, and tears it down after
each test. Playwright's `page` fixture (from pytest-playwright) picks
up the `base_url` fixture below automatically for relative page.goto().
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

HOST = "127.0.0.1"
PORT = 8421
BASE_URL = f"http://{HOST}:{PORT}"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.2)
        try:
            sock.bind((host, port))
        except OSError:
            return True
        return False


def _wait_for(predicate, timeout_s: float, interval_s: float = 0.1) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return False


def _wait_for_health(timeout_s: float = 15.0) -> bool:
    def check() -> bool:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=0.5) as resp:
                return resp.status == 200
        except OSError:
            return False

    return _wait_for(check, timeout_s)


@pytest.fixture()
def live_server(tmp_path):
    """A real server process for one test, with its own temp DB."""
    assert _wait_for(lambda: not _port_in_use(HOST, PORT), timeout_s=5.0), (
        "port 8421 still occupied from a previous test"
    )

    db_path = tmp_path / "e2e.db"
    env = {**os.environ, "TYPING_TRAINER_DB_PATH": str(db_path)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(PORT)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert _wait_for_health(), "server did not become healthy in time"
        yield BASE_URL
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        _wait_for(lambda: not _port_in_use(HOST, PORT), timeout_s=5.0)


