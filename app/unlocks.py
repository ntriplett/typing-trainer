"""Rooms that open as the learner learns: the Bedroom once the top row is
taught. Until then it's a "mystery" on the home page. (Pets are open from
the start; the Pet Shop opens its departments by itself, app/pet_shop.py.)

Players who already decorated their bedroom keep it open: unlocking never
takes anything away.
"""

from __future__ import annotations

import sqlite3

from app import db, lessons, pet_shop
from app.catalog import CATALOG

TOP_ROW = "qwertyuiop"
ROOM_SLOTS = ("furniture", "wallpaper", "flooring")

# room -> (keys it needs, what to tell the learner)
NEEDS = {
    "bedroom": (TOP_ROW, "Finish learning the top row to open it."),
}


class Locked(PermissionError):
    """Kid-readable, like StoreError."""


def _decorated(conn: sqlite3.Connection, learner_id: int) -> bool:
    owned = db.list_owned_item_ids(conn, learner_id)
    bought = any(CATALOG[i].slot in ROOM_SLOTS and not CATALOG[i].starter for i in owned if i in CATALOG)
    return bought or bool(db.list_room_items(conn, learner_id, "bedroom"))


def status(conn: sqlite3.Connection, learner_id: int) -> dict:
    """{"bedroom": bool, "pet_coupon": bool, "missing": {room: keys still to learn}, "hints": ...}."""
    taught = lessons.taught_keys(conn, learner_id)
    missing = {room: "".join(k for k in keys if k not in taught) for room, (keys, _) in NEEDS.items()}
    return {
        "bedroom": _decorated(conn, learner_id) or not missing["bedroom"],
        "missing": missing,
        "hints": {room: hint for room, (_, hint) in NEEDS.items()},
        "pet_coupon": pet_shop.has_coupon(conn, learner_id),
    }


def require(conn: sqlite3.Connection, learner_id: int, room: str) -> None:
    if not status(conn, learner_id)[room]:
        raise Locked(f"This room is still a mystery! {NEEDS[room][1]}")


def newly_unlocked(before: dict, after: dict) -> list[str]:
    return [room for room in NEEDS if after[room] and not before[room]]
