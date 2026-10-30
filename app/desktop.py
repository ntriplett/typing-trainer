"""The installed (Windows) copy: version, update checks, and shutting down
when nobody is using the app.

The launcher (launcher/start.py) sets TYPING_TRAINER_HOME to the install
folder when it starts the server; without it (dev, tests) everything here
is off. The server never updates itself: asking for an update writes
data/update.json and exits, and the launcher, which is waiting on the
server, applies it (launcher/update.py) and reopens the app.
"""

from __future__ import annotations

import json
import os
import threading
import time
import tomllib
import urllib.request
from pathlib import Path

REPO = "ntriplett/typing-trainer"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_EVERY_S = 3600
# Pages ping every 30 s (alive.js). Hidden tabs can be throttled to one
# timer a minute, so allow a few missed pings before deciding we're done.
IDLE_EXIT_S = 180

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
VERSION = tomllib.loads(_PYPROJECT.read_text())["project"]["version"]


def home() -> Path | None:
    raw = os.environ.get("TYPING_TRAINER_HOME")
    return Path(raw) if raw else None


def parse_version(tag: str) -> tuple[int, ...] | None:
    """"v1.2.0" or "1.2" -> (1, 2, 0) / (1, 2); None if it isn't one."""
    parts = tag.strip().lstrip("vV").split(".")
    if not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def is_newer(tag: str, current: str = VERSION) -> bool:
    new, old = parse_version(tag), parse_version(current)
    return new is not None and old is not None and new > old


def fetch_latest() -> dict | None:
    """The newest GitHub release, or None when offline or it has no zip."""
    req = urllib.request.Request(LATEST_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"typing-trainer/{VERSION}",
    })
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            release = json.load(resp)
    except (OSError, ValueError):
        return None
    zips = [a["browser_download_url"] for a in release.get("assets", [])
            if a.get("name", "").startswith("typing-trainer-") and a["name"].endswith(".zip")]
    if not zips:
        return None
    return {
        "tag": release.get("tag_name", ""),
        "zip_url": zips[0],
        "notes": release.get("body") or "",
        "page": release.get("html_url", ""),
    }


_cache: dict = {"at": None, "latest": None}


def latest(force: bool = False) -> dict | None:
    """fetch_latest, at most once an hour (GitHub allows 60 calls an hour)."""
    at = _cache["at"]
    if force or at is None or time.monotonic() - at > CHECK_EVERY_S:
        _cache["latest"] = fetch_latest()
        _cache["at"] = time.monotonic()
    return _cache["latest"]


def status() -> dict:
    if home() is None:
        return {"installed": False, "current": VERSION, "available": False}
    release = latest()
    available = bool(release) and is_newer(release["tag"])
    return {
        "installed": True,
        "current": VERSION,
        "available": available,
        "latest": release["tag"] if release else None,
        "notes": release["notes"] if available else "",
        "page": release["page"] if release else "",
    }


def request_update() -> dict:
    """Leave the update for the launcher, then stop the server."""
    root = home()
    if root is None:
        raise RuntimeError("not an installed copy")
    release = latest(force=True)
    if not release or not is_newer(release["tag"]):
        raise LookupError("no newer version")
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "update.json").write_text(json.dumps({"tag": release["tag"], "zip_url": release["zip_url"]}))
    exit_soon()
    return {"tag": release["tag"]}


def exit_soon(delay_s: float = 0.5) -> None:
    """Exit after the current response has gone out. Nothing is mid-write:
    every request commits (or rolls back) its own transaction."""
    threading.Timer(delay_s, lambda: os._exit(0)).start()


_last_seen = time.monotonic()


def touch() -> None:
    global _last_seen
    _last_seen = time.monotonic()


def start_idle_watch() -> None:
    """Installed copy only: quit once no page has pinged for IDLE_EXIT_S.
    The launcher normally stops the server when the app window closes;
    this catches the cases it can't see (a window it didn't open, or the
    launcher itself was closed)."""
    if home() is None:
        return

    def watch():
        while True:
            time.sleep(15)
            if time.monotonic() - _last_seen > IDLE_EXIT_S:
                os._exit(0)

    threading.Thread(target=watch, daemon=True, name="idle-watch").start()
