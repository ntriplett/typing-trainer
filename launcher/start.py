"""Launcher: what the desktop icon actually runs.

Logic (see PLAN.md Section 3):
  1. If something is already listening on our port, assume it's us and
     just open/focus the browser tab.
  2. Otherwise, start the FastAPI app in the background, wait for it to
     answer /health, then open the browser.

The listening port itself is the single-instance mutex: attempting to
bind it is atomic at the OS level, so two near-simultaneous double-clicks
can't both start a server. No separate lockfile to go stale if a
previous run crashed.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8420
HEALTH_URL = f"http://{HOST}:{PORT}/health"
APP_URL = f"http://{HOST}:{PORT}/"
REPO_ROOT = Path(__file__).resolve().parent.parent


def port_in_use(host: str, port: int) -> bool:
    """True if something is already listening on host:port.

    SO_REUSEADDR matters here: without it, a port can appear "in use" for
    a couple of minutes after the previous server's connections enter
    TCP TIME_WAIT, even though nothing is actually listening. uvicorn
    sets this on its own listening socket too, so this matches what the
    real server does.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.2)
        try:
            sock.bind((host, port))
        except OSError:
            return True
        return False


def wait_for_health(timeout_s: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=0.5) as resp:
                if resp.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.2)
    return False


def spawn_server() -> subprocess.Popen:
    """Start uvicorn detached from this launcher process."""
    kwargs: dict = {
        "cwd": REPO_ROOT,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True

    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(PORT)],
        **kwargs,
    )


def main(open_browser: bool = True) -> bool:
    """Ensure the server is running, optionally open the browser.

    Returns True if the server was reachable by the end (new or already
    running), False if it failed to come up.
    """
    if not port_in_use(HOST, PORT):
        spawn_server()

    healthy = wait_for_health()
    if healthy and open_browser:
        webbrowser.open(APP_URL)
    return healthy


if __name__ == "__main__":
    ok = main(open_browser="--no-browser" not in sys.argv)
    if not ok:
        print("Server did not become healthy in time.", file=sys.stderr)
        sys.exit(1)
