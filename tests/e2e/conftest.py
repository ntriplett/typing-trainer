"""Shared fixture + helpers for real-browser e2e tests: spawns the
actual FastAPI app as a subprocess (the same way the launcher does),
pointed at an isolated temp DB via TYPING_TRAINER_DB_PATH, and tears it
down after each test. `live_server` gives tests the base URL to build
absolute page.goto() calls from (pytest-playwright's own `base_url`
fixture is session-scoped and can't depend on our function-scoped one).
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
from playwright.sync_api import Page, expect

from app import grownup_pin

GROWNUP_PIN = "1234"
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
def live_server(tmp_path, request):
    """A real server process for one test, with its own temp DB. The grown-ups' PIN is
    already chosen (GROWNUP_PIN), unless the test's marked `first_run`; `installed`
    runs it as an install does: no labs, no free days."""
    assert _wait_for(lambda: not _port_in_use(HOST, PORT), timeout_s=5.0), (
        "port 8421 still occupied from a previous test"
    )

    db_path = tmp_path / "e2e.db"
    env = {**os.environ, "TYPING_TRAINER_DB_PATH": str(db_path)}
    if "first_run" not in request.keywords:
        grownup_pin.set_pin(grownup_pin.path_for(db_path), GROWNUP_PIN)
    if "installed" in request.keywords:
        env.update(TYPING_TRAINER_DEV="0", TYPING_TRAINER_WANDER_FREE_DAYS="0")
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


# --- shared session-flow helpers, used across test_session_flow.py, ---
# --- test_analysis_page.py (needs real data to show), etc. -------------


@pytest.fixture(autouse=True)
def player(request):
    """Browser tests start with a player already picked (learner 1, via the
    real API so the browser gets the cookie), except tests that ask for
    `no_player` to exercise the welcome screen themselves."""
    if "page" not in request.fixturenames or "live_server" not in request.fixturenames:
        return
    if "no_player" in request.keywords:
        return
    page = request.getfixturevalue("page")
    live_server = request.getfixturevalue("live_server")
    resp = page.request.post(f"{live_server}/api/profiles", data={"name": "Tester"})
    assert resp.ok, resp.text()


def unlock_grownups(page: Page, live_server: str) -> None:
    """Open the For Grown-ups APIs, as typing the PIN does."""
    resp = page.request.post(f"{live_server}/api/grownups/unlock", data={"pin": GROWNUP_PIN})
    assert resp.ok, resp.text()


def place_on_home_row(page: Page, live_server: str) -> None:
    """Skip the first teach lessons: the home row counts as taught, so the
    brain's first lesson is a warmup on the practice page."""
    resp = page.request.put(f"{live_server}/api/profiles/placement", data={"keys": "home_row", "speed": "some"})
    assert resp.ok, resp.text()


def start_practice_lesson(page: Page, live_server: str) -> None:
    place_on_home_row(page, live_server)
    page.goto(f"{live_server}/session")
    page.wait_for_function("contentLoaded")


def type_current_lesson(page: Page) -> None:
    """Type the full, correct prompt of the lesson on screen."""
    page.wait_for_function("contentLoaded && view.typed === 0")
    # what's actually typed: the spaces where lines wrap are dropped
    page.keyboard.type(page.evaluate("view.typeable"))
    expect(page.locator("#lesson-result")).to_be_visible()
