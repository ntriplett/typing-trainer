"""Launcher: what the desktop icon actually runs.

Logic (see PLAN.md Section 3):
  1. If something is already listening on our port, assume it's us and
     just open/focus the browser tab.
  2. Otherwise, start the FastAPI app in the background, wait for it to
     answer /health, then open the browser.

main() is the dev version (`python launcher/start.py`). run_installed()
is the Windows install (windows/install.ps1): the app opens in its own
Chrome (or Edge) window, closing that window stops the server, and an
update the app asked for (app/desktop.py) is applied before reopening.

The listening port itself is the single-instance mutex: attempting to
bind it is atomic at the OS level, so two near-simultaneous double-clicks
can't both start a server. No separate lockfile to go stale if a
previous run crashed.
"""

from __future__ import annotations

import json
import os
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


def spawn_server(env: dict | None = None, log=subprocess.DEVNULL) -> subprocess.Popen:
    """Start uvicorn detached from this launcher process."""
    kwargs: dict = {
        "cwd": REPO_ROOT,
        "stdout": log,
        "stderr": log,
        "env": env,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True

    return subprocess.Popen(
        [console_python(), "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(PORT)],
        **kwargs,
    )


def console_python() -> str:
    """The shortcut runs us under pythonw.exe (no console window); give the
    server plain python.exe from the same venv so its logging has a real
    stderr. CREATE_NO_WINDOW keeps that hidden too."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return sys.executable


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


# --- The installed Windows copy -------------------------------------------

# A browser that exits this quickly handed our window to a copy of itself
# already running with the same profile, so we can't watch it close.
HANDOFF_S = 5


def browser_candidates(environ=os.environ) -> list[Path]:
    """Chrome first, then Edge (every Windows 10/11 has Edge)."""
    found = []
    for base_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = environ.get(base_var)
        if base:
            found.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    for base_var in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        base = environ.get(base_var)
        if base:
            found.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    return found


def find_browser(environ=os.environ) -> Path | None:
    return next((p for p in browser_candidates(environ) if p.exists()), None)


def app_window_args(browser: Path, profile: Path) -> list[str]:
    """Its own window with no tabs or address bar, in a profile of its own
    (so it's a separate process we can wait on, and the player cookie
    lives with the app rather than in someone's everyday browser)."""
    return [
        str(browser), f"--app={APP_URL}", f"--user-data-dir={profile}",
        "--no-first-run", "--no-default-browser-check", "--window-size=1400,900",
    ]


def open_app_window(data: Path) -> subprocess.Popen | None:
    """The app window, or None when we had to fall back to the default
    browser (and so can't tell when it closes)."""
    browser = find_browser()
    if browser is None:
        webbrowser.open(APP_URL)
        return None
    return subprocess.Popen(app_window_args(browser, data / "browser"), cwd=data)


def installed_env(root: Path) -> dict:
    env = dict(os.environ)
    env["TYPING_TRAINER_HOME"] = str(root)
    env["TYPING_TRAINER_DB_PATH"] = str(root / "data" / "typing.db")
    env["TYPING_TRAINER_DEV_START_COINS"] = "0"
    return env


def wait_for_close(server: subprocess.Popen, window: subprocess.Popen | None, clock=time.monotonic, sleep=time.sleep) -> None:
    """Return once the server has stopped: because the app window closed
    (we stop it), or because the server quit by itself (asked to update,
    or idle with no window we could watch)."""
    opened = clock()
    while server.poll() is None:
        if window is not None and window.poll() is not None:
            if clock() - opened < HANDOFF_S:
                window = None  # handed off; the server's idle watch takes over
            else:
                server.terminate()
                server.wait(timeout=10)
                return
        sleep(0.5)
    if window is not None and window.poll() is None:
        window.terminate()


def run_installed(root: Path) -> None:
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    if port_in_use(HOST, PORT):
        open_app_window(data)  # already running: just another window
        return
    with open(data / "server.log", "ab") as log:
        server = spawn_server(env=installed_env(root), log=log)
        if not wait_for_health(timeout_s=30.0):
            server.terminate()
            return
        wait_for_close(server, open_app_window(data))

    pending = data / "update.json"
    if pending.exists():
        from launcher import update
        update.apply(root, json.loads(pending.read_text()))
        update.relaunch(root)


if __name__ == "__main__":
    ok = main(open_browser="--no-browser" not in sys.argv)
    if not ok:
        print("Server did not become healthy in time.", file=sys.stderr)
        sys.exit(1)
