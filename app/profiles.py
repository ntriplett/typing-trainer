"""Player profiles (PLAN.md 11d): pick or create a player, no passwords.
The current player is remembered per browser in a cookie (main.py), so two
kids can play at once in separate browsers on the same PC; every table is
keyed by learner_id, so their data never mixes.

New players answer a quick placement -- which keys they already know and
roughly how fast they type -- so lessons start at the right spot instead
of re-teaching f and j to someone who already types.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from app import db, skill_model, store
from app.models import KeyStat

MAX_NAME = 20
SETTING_PLACEMENT_WPM = "placement_wpm"

# Which keys count as already known, by placement answer (KEY_ORDER
# prefixes: space + home row, + top and bottom rows, everything).
PLACEMENT_KEYS = {
    "new": 0,
    "home_row": 11,
    "letters": 31,
    "everything": len(skill_model.KEY_ORDER),
}
# Rough typing speed answer -> a starting WPM guess for lesson sizing.
PLACEMENT_WPM = {"starting": 5, "some": 12, "comfy": 22, "fast": 32}


class ProfileError(ValueError):
    """Kid-readable, like StoreError."""


def list_profiles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, name FROM learner ORDER BY id").fetchall()
    return [
        {"id": r["id"], "name": r["name"], "avatar": store.get_avatar(conn, r["id"])}
        for r in rows
    ]


def create(conn: sqlite3.Connection, name: str) -> int:
    name = name.strip()
    if not name or len(name) > MAX_NAME:
        raise ProfileError(f"Names need 1 to {MAX_NAME} letters.")
    if any(p["name"].lower() == name.lower() for p in conn.execute("SELECT name FROM learner")):
        raise ProfileError(f"There's already a player called {name}.")
    learner_id = db.create_learner(conn, name).id
    store.grant_starters(conn, learner_id)
    return learner_id


def exists(conn: sqlite3.Connection, learner_id: int) -> bool:
    return db.get_learner(conn, learner_id) is not None


def apply_placement(conn: sqlite3.Connection, learner_id: int, keys: str, speed: str) -> None:
    """Mark the keys a new player already knows as learned, at a speed
    matching their answer, and remember the speed for lesson sizing."""
    if keys not in PLACEMENT_KEYS or speed not in PLACEMENT_WPM:
        raise ProfileError("Pick one answer for each question.")
    wpm = PLACEMENT_WPM[speed]
    db.set_setting(conn, learner_id, SETTING_PLACEMENT_WPM, str(wpm))
    ms_per_key = 60_000 / (wpm * 5)
    now = datetime.now(UTC)
    for key in skill_model.KEY_ORDER[: PLACEMENT_KEYS[keys]]:
        existing = db.get_key_stat(conn, learner_id, key)
        if existing is not None and existing.mastered_at is not None:
            continue  # real practice beats a guess
        db.upsert_key_stat(conn, KeyStat(
            learner_id=learner_id,
            key=key,
            ema_time_ms=ms_per_key,
            confidence=skill_model.TARGET_MS_PER_KEYSTROKE / ms_per_key,
            accuracy_rolling=skill_model.ACCURACY_FLOOR,
            sample_count=skill_model.MIN_SAMPLES_FOR_MASTERY,
            unlocked_at=now,
            mastered_at=now,
        ))


def placement_wpm(conn: sqlite3.Connection, learner_id: int) -> float | None:
    value = db.get_setting(conn, learner_id, SETTING_PLACEMENT_WPM)
    return float(value) if value else None
