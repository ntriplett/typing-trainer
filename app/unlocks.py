"""Rooms that open as the learner learns; until then a room is a "mystery"
on the home page. None wait today: the Home (bedroom, dressing room, window
nook) and Pets are open from the start, and the Pet Shop opens its
departments by itself (app/pet_shop.py). Unlocking never takes anything away.
"""

from __future__ import annotations

import sqlite3

from app import lessons, pet_shop

# room -> (keys it needs, what to tell the learner)
NEEDS: dict[str, tuple[str, str]] = {}


class Locked(PermissionError):
    """Kid-readable, like StoreError."""


def status(conn: sqlite3.Connection, learner_id: int) -> dict:
    """{room: open?, ..., "pet_coupon": bool, "missing": {room: keys still to learn}, "hints": ...}."""
    taught = lessons.taught_keys(conn, learner_id)
    missing = {room: "".join(k for k in keys if k not in taught) for room, (keys, _) in NEEDS.items()}
    return {
        **{room: not keys for room, keys in missing.items()},
        "missing": missing,
        "hints": {room: hint for room, (_, hint) in NEEDS.items()},
        "pet_coupon": pet_shop.has_coupon(conn, learner_id),
    }


def require(conn: sqlite3.Connection, learner_id: int, room: str) -> None:
    if not status(conn, learner_id)[room]:
        raise Locked(f"This room is still a mystery! {NEEDS[room][1]}")


def newly_unlocked(before: dict, after: dict) -> list[str]:
    return [room for room in NEEDS if after[room] and not before[room]]
