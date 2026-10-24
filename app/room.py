"""Decoratable rooms (PLAN.md 11c-2, phase 5): a wallpaper, a flooring,
and furniture placed by dragging. Only the bedroom exists today, but
everything is keyed by room name so a pet room can reuse it.

Room coordinates are pixels on a 96x96 grid (the wall is the top part,
the floor the bottom; web/static/js/room.js draws and clamps). Furniture
is bought in the store like any item; each piece can be placed once.
"""

from __future__ import annotations

import sqlite3

from app import db
from app.catalog import CATALOG

ROOMS = ("bedroom",)
ROOM_SIZE = 96
DEFAULT_SURFACES = {"wallpaper": "wallpaper_cream", "flooring": "flooring_planks"}
# Where a newly bought piece first appears, by zone (x, y of its top-left).
DEFAULT_SPOT = {"wall": (38, 14), "floor": (40, 66)}


class RoomError(ValueError):
    """Kid-readable, like StoreError."""


def _check_room(room: str) -> None:
    if room not in ROOMS:
        raise RoomError(f"There's no room called {room!r}.")


def _owned_piece(conn: sqlite3.Connection, learner_id: int, item_id: str):
    item = CATALOG.get(item_id)
    if item is None or item.slot != "furniture":
        raise RoomError("That isn't furniture.")
    if item_id not in db.list_owned_item_ids(conn, learner_id):
        raise RoomError(f"You don't own the {item.name} yet.")
    return item


def _clamp(value: int) -> int:
    return max(0, min(ROOM_SIZE - 1, int(value)))


def state(conn: sqlite3.Connection, learner_id: int, room: str = "bedroom") -> dict:
    _check_room(room)
    surfaces = {**DEFAULT_SURFACES, **db.get_room_surfaces(conn, learner_id, room)}
    owned = db.list_owned_item_ids(conn, learner_id)
    placed = db.list_room_items(conn, learner_id, room)
    placed_ids = {p["item_id"] for p in placed}
    pieces = [i for i in CATALOG.values() if i.id in owned and i.slot in ("furniture", "wallpaper", "flooring")]
    return {
        "room": room,
        "wallpaper": surfaces["wallpaper"],
        "flooring": surfaces["flooring"],
        "items": placed,
        "inventory": [  # owned furniture not in the room yet
            {"item_id": i.id, "name": i.name, "zone": i.group} for i in pieces
            if i.slot == "furniture" and i.id not in placed_ids
        ],
        "names": {i.id: i.name for i in pieces},
        "zones": {i.id: i.group for i in pieces if i.slot == "furniture"},
        "wallpapers": [i.id for i in pieces if i.slot == "wallpaper"],
        "floorings": [i.id for i in pieces if i.slot == "flooring"],
    }


def place(conn: sqlite3.Connection, learner_id: int, item_id: str, x: int | None = None,
          y: int | None = None, room: str = "bedroom") -> int:
    _check_room(room)
    item = _owned_piece(conn, learner_id, item_id)
    if any(p["item_id"] == item_id for p in db.list_room_items(conn, learner_id, room)):
        raise RoomError(f"The {item.name} is already in your room.")
    dx, dy = DEFAULT_SPOT[item.group]
    return db.add_room_item(conn, learner_id, room, item_id, _clamp(dx if x is None else x), _clamp(dy if y is None else y))


def move(conn: sqlite3.Connection, learner_id: int, placed_id: int, x: int, y: int) -> None:
    if not db.move_room_item(conn, learner_id, placed_id, _clamp(x), _clamp(y)):
        raise RoomError("That isn't in your room.")


def put_away(conn: sqlite3.Connection, learner_id: int, placed_id: int) -> None:
    if not db.remove_room_item(conn, learner_id, placed_id):
        raise RoomError("That isn't in your room.")


def set_surface(conn: sqlite3.Connection, learner_id: int, item_id: str, room: str = "bedroom") -> None:
    _check_room(room)
    item = CATALOG.get(item_id)
    if item is None or item.slot not in DEFAULT_SURFACES:
        raise RoomError("That isn't wallpaper or flooring.")
    if not item.starter and item_id not in db.list_owned_item_ids(conn, learner_id):
        raise RoomError(f"You don't own the {item.name} yet.")
    db.set_room_surface(conn, learner_id, room, item.slot, item_id)
