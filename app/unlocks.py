"""Rooms that open as the learner learns: the Pet Room once the home row is
taught (with a free first baby pet), the Bedroom once the top row is.
Until then each is a "mystery" on the home page.

Players who already have pets, or already decorated their bedroom, keep
those rooms open: unlocking never takes anything away.
"""

from __future__ import annotations

import sqlite3

from app import db, lessons
from app.catalog import CATALOG

HOME_ROW = "asdfghjkl;"
TOP_ROW = "qwertyuiop"
ROOM_SLOTS = ("furniture", "wallpaper", "flooring")
SETTING_FREE_PET = "free_pet_claimed"

# room -> (keys it needs, what to tell the learner)
NEEDS = {
    "pets": (HOME_ROW, "Finish learning the home row to open it."),
    "bedroom": (TOP_ROW, "Finish learning the top row to open it."),
}


class Locked(PermissionError):
    """Kid-readable, like StoreError."""


def _decorated(conn: sqlite3.Connection, learner_id: int) -> bool:
    owned = db.list_owned_item_ids(conn, learner_id)
    bought = any(CATALOG[i].slot in ROOM_SLOTS and not CATALOG[i].starter for i in owned if i in CATALOG)
    return bought or bool(db.list_room_items(conn, learner_id, "bedroom"))


def status(conn: sqlite3.Connection, learner_id: int) -> dict:
    """{"pets": bool, "bedroom": bool, "free_pet": bool, "missing": {room: keys still to learn}}."""
    taught = lessons.taught_keys(conn, learner_id)
    has_pets = bool(db.list_pets(conn, learner_id))
    missing = {room: "".join(k for k in keys if k not in taught) for room, (keys, _) in NEEDS.items()}
    pets = has_pets or not missing["pets"]
    return {
        "pets": pets,
        "bedroom": _decorated(conn, learner_id) or not missing["bedroom"],
        "free_pet": pets and not has_pets and db.get_setting(conn, learner_id, SETTING_FREE_PET) is None,
        "missing": missing,
        "hints": {room: hint for room, (_, hint) in NEEDS.items()},
    }


def require(conn: sqlite3.Connection, learner_id: int, room: str) -> None:
    if not status(conn, learner_id)[room]:
        raise Locked(f"This room is still a mystery! {NEEDS[room][1]}")


def claim_free_pet(conn: sqlite3.Connection, learner_id: int) -> None:
    db.set_setting(conn, learner_id, SETTING_FREE_PET, "1")


def newly_unlocked(before: dict, after: dict) -> list[str]:
    return [room for room in NEEDS if after[room] and not before[room]]
