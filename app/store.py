"""The coin store's rules (PLAN.md Section 11c): buying, equipping, and
using items. The items themselves are defined in app/catalog.py; storage
is app/db.py's owned_item / equipped_item tables.

Each clothing slot and the background have a free starter item, so an
avatar is just "whatever is equipped in each slot" plus the learner's
appearance (app/appearance.py) -- no special cases.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace

from app import appearance, db, pets, room
from app.catalog import (
    CATALOG, DEFAULT_BACKGROUND, ITEMS, SLOT_DEFAULTS, WEARABLE_SLOTS, StoreItem, group_places, night_item_id,
    place_group,
)

# Re-exported so callers have one place to look for store names.
SLOTS = WEARABLE_SLOTS
__all__ = [
    "CATALOG", "DEFAULT_BACKGROUND", "SLOTS", "SLOT_DEFAULTS", "StoreError", "StoreItem",
    "buy", "equip", "get_avatar", "grant_starters", "night_status", "owned_ids", "set_night", "unequip",
]

NIGHT_SETTING = "night"


class StoreError(ValueError):
    """A rule was broken (unknown item, not enough coins, ...). The message
    is kid-readable -- the API passes it straight through to the page."""


def _get_item(item_id: str) -> StoreItem:
    item = CATALOG.get(item_id)
    if item is None:
        raise StoreError(f"There's no item called {item_id!r}.")
    return item


def grant_starters(conn: sqlite3.Connection, learner_id: int) -> None:
    """Give a learner every starter item and fill any empty starter slot.
    Idempotent, and never overrides something already equipped."""
    for item in ITEMS:
        if item.starter:
            db.add_owned_item(conn, learner_id, item.id)
    equipped = db.get_equipped(conn, learner_id)
    for slot, item_id in SLOT_DEFAULTS.items():
        if slot not in equipped:
            db.set_equipped(conn, learner_id, slot, item_id)


def owned_ids(conn: sqlite3.Connection, learner_id: int) -> set[str]:
    return db.list_owned_item_ids(conn, learner_id)


def get_avatar(conn: sqlite3.Connection, learner_id: int) -> dict:
    """slot -> item_id for each worn slot, plus "appearance", "night", and
    the pets that come along; the shape the front-end avatar renderer draws."""
    look = appearance.load(conn, learner_id)
    pets.migrate_legacy(conn, learner_id)
    worn = {
        slot: item_id
        for slot, item_id in db.get_equipped(conn, learner_id).items()
        if slot in WEARABLE_SLOTS
    }
    return {**worn, "night": night_status(conn, learner_id)["on"], "pets": pets.along(conn, learner_id), "appearance": {
        "gender": look.gender, "skin": look.skin,
        "hair_color": look.hair_color, "hair_style": look.hair_style, "eye_color": look.eye_color,
    }}


def night_status(conn: sqlite3.Connection, learner_id: int) -> dict:
    """Night is a saved on/off wish, but it only shows while the current
    place's group night is unlocked -- so switching to a place without
    its night unlock just shows day, and switching back restores night."""
    background = db.get_equipped(conn, learner_id).get("background", DEFAULT_BACKGROUND)
    group = place_group(background)
    available = group is not None and night_item_id(group) in owned_ids(conn, learner_id)
    wanted = db.get_setting(conn, learner_id, NIGHT_SETTING) == "on"
    return {"available": available, "on": available and wanted, "group": group}


def set_night(conn: sqlite3.Connection, learner_id: int, on: bool) -> None:
    if on and not night_status(conn, learner_id)["available"]:
        raise StoreError("Unlock night for this place in the store first!")
    db.set_setting(conn, learner_id, NIGHT_SETTING, "on" if on else "off")


def buy(conn: sqlite3.Connection, learner_id: int, item_id: str) -> StoreItem:
    item = _get_item(item_id)
    if item.starter:
        raise StoreError(f"{item.name} isn't for sale.")
    if item.id in owned_ids(conn, learner_id):
        raise StoreError(f"You already own the {item.name}.")
    balance = db.get_coin_balance(conn, learner_id)
    if balance < item.price:
        raise StoreError(f"You need {item.price - balance} more coins for the {item.name}.")
    db.add_coins(conn, learner_id, -item.price, "purchase", ref=item.id)
    db.add_owned_item(conn, learner_id, item.id)
    return item


def equip(conn: sqlite3.Connection, learner_id: int, item_id: str) -> None:
    """Wear a wearable, or apply a usable item (a hair dye recolors hair)."""
    item = _get_item(item_id)
    if item.id not in owned_ids(conn, learner_id):
        raise StoreError(f"You don't own the {item.name} yet.")
    if item.slot == "night":
        # "Using" a night unlock turns on night -- going to one of its
        # places first if you're somewhere else.
        current = place_group(db.get_equipped(conn, learner_id).get("background", DEFAULT_BACKGROUND))
        if current != item.group:
            owned = owned_ids(conn, learner_id)
            mine = [p for p in group_places(item.group) if p in owned]
            if not mine:
                names = ", ".join(CATALOG[p].name for p in group_places(item.group))
                raise StoreError(f"Get one of these places first: {names}.")
            db.set_equipped(conn, learner_id, "background", mine[0])
        set_night(conn, learner_id, True)
        return
    if item.slot in ("wallpaper", "flooring"):
        room.set_surface(conn, learner_id, item.id)
        return
    if item.slot == "furniture":
        # "using" furniture = putting it in your room (once)
        if not any(p["item_id"] == item.id for p in db.list_room_items(conn, learner_id, "bedroom")):
            room.place(conn, learner_id, item.id)
        return
    if item.slot == "hair_dye":
        color = item.id.removeprefix("dye_")
        look = appearance.load(conn, learner_id)
        appearance.save(conn, learner_id, replace(look, hair_color=color))
        return
    if item.slot not in WEARABLE_SLOTS:
        raise StoreError(f"The {item.name} isn't something you can wear.")
    db.set_equipped(conn, learner_id, item.slot, item.id)


def unequip(conn: sqlite3.Connection, learner_id: int, slot: str) -> None:
    if slot not in WEARABLE_SLOTS:
        raise StoreError(f"There's no {slot!r} slot.")
    if slot in SLOT_DEFAULTS:
        # Starters aren't listed in the store, so "taking off" a bought
        # piece puts the starter back on rather than leaving the slot empty.
        db.set_equipped(conn, learner_id, slot, SLOT_DEFAULTS[slot])
        return
    db.clear_equipped(conn, learner_id, slot)
