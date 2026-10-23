"""The coin store (PLAN.md Section 11c): an in-code item catalog plus the
rules for buying and equipping. Storage is app/db.py's owned_item /
equipped_item tables; this module owns the rules.

The catalog lives in code, like the activity registry -- adding an item
is a code change (plus its sprite in web/static/js/sprites.js, keyed by
the same id), never a DB edit.

Starting avatars are free hidden "starter" items in the body slot, and
each clothing slot and the background have a starter too, so an avatar
is just "whatever is equipped in each slot" with no special cases.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app import db

# Draw order, back to front -- the front-end avatar renderer layers in
# this same order.
SLOTS = ("background", "body", "shoes", "pants", "shirt", "hat", "pet")
REQUIRED_SLOTS = ("body",)


@dataclass(frozen=True, slots=True)
class StoreItem:
    id: str
    name: str
    slot: str
    price: int
    description: str
    starter: bool = False


# Prices are pegged to ~1K coins per 15-minute session: a small item
# after one session, a pet after a few.
_ITEMS = [
    # starters (free, not shown in the store)
    StoreItem("body_sprout", "Sprout", "body", 0, "Brown hair, ready for adventure.", starter=True),
    StoreItem("body_ember", "Ember", "body", 0, "Red hair, full of energy.", starter=True),
    StoreItem("body_moss", "Moss", "body", 0, "Dark curls, calm and steady.", starter=True),
    StoreItem("bg_meadow", "Sunny Meadow", "background", 0, "Where every journey starts.", starter=True),
    StoreItem("shirt_tunic", "Cream Tunic", "shirt", 0, "Plain, comfy, and ready for anything.", starter=True),
    StoreItem("pants_trousers", "Brown Trousers", "pants", 0, "Good for climbing and kneeling.", starter=True),
    StoreItem("shoes_boots", "Leather Boots", "shoes", 0, "Sturdy enough for any trail.", starter=True),
    # hats
    StoreItem("hat_straw", "Straw Hat", "hat", 300, "Keeps the sun out of your eyes."),
    StoreItem("hat_acorn", "Acorn Cap", "hat", 600, "Borrowed from a very large acorn."),
    StoreItem("hat_leaf_crown", "Autumn Leaf Crown", "hat", 1200, "Woven from the brightest fall leaves."),
    # shirts
    StoreItem("shirt_sweater", "Pumpkin Sweater", "shirt", 500, "Cozy, orange, and a little bit itchy."),
    # (overalls cover the legs too, so they live in the shirt slot as a full outfit)
    StoreItem("shirt_overalls", "Garden Overalls", "shirt", 900, "Pockets for seeds and snacks."),
    # pets
    StoreItem("pet_hedgehog", "Hedgehog", "pet", 1500, "Small, spiky, and very loyal."),
    StoreItem("pet_fox", "Fox Kit", "pet", 2500, "Curious about everything you type."),
    # backgrounds
    StoreItem("bg_autumn_forest", "Autumn Forest", "background", 800, "Red and gold trees all around."),
    StoreItem("bg_beach", "Sandy Beach", "background", 1000, "Warm sand and gentle waves."),
]

CATALOG: dict[str, StoreItem] = {item.id: item for item in _ITEMS}
DEFAULT_BODY = "body_sprout"
DEFAULT_BACKGROUND = "bg_meadow"
# What a slot falls back to when emptied ("take off" puts these back on).
SLOT_DEFAULTS: dict[str, str] = {
    "background": DEFAULT_BACKGROUND,
    "shirt": "shirt_tunic",
    "pants": "pants_trousers",
    "shoes": "shoes_boots",
}


class StoreError(ValueError):
    """A rule was broken (unknown item, not enough coins, ...). The message
    is kid-readable -- the API passes it straight through to the page."""


def starter_bodies() -> list[StoreItem]:
    return [i for i in _ITEMS if i.starter and i.slot == "body"]


def _get_item(item_id: str) -> StoreItem:
    item = CATALOG.get(item_id)
    if item is None:
        raise StoreError(f"There's no item called {item_id!r}.")
    return item


def grant_starters(conn: sqlite3.Connection, learner_id: int, body: str | None = None) -> None:
    """Give a learner every starter item and fill any empty required/starter
    slot. Idempotent, and never overrides something already equipped."""
    for item in _ITEMS:
        if item.starter:
            db.add_owned_item(conn, learner_id, item.id)
    equipped = db.get_equipped(conn, learner_id)
    if "body" not in equipped:
        chosen = body if body is not None else DEFAULT_BODY
        if chosen not in {b.id for b in starter_bodies()}:
            raise StoreError(f"{chosen!r} isn't a starting avatar.")
        db.set_equipped(conn, learner_id, "body", chosen)
    for slot, item_id in SLOT_DEFAULTS.items():
        if slot not in equipped:
            db.set_equipped(conn, learner_id, slot, item_id)


def owned_ids(conn: sqlite3.Connection, learner_id: int) -> set[str]:
    return db.list_owned_item_ids(conn, learner_id)


def get_avatar(conn: sqlite3.Connection, learner_id: int) -> dict[str, str]:
    """slot -> item_id; the shape the front-end avatar renderer draws."""
    return db.get_equipped(conn, learner_id)


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
    item = _get_item(item_id)
    if item.id not in owned_ids(conn, learner_id):
        raise StoreError(f"You don't own the {item.name} yet.")
    db.set_equipped(conn, learner_id, item.slot, item.id)


def unequip(conn: sqlite3.Connection, learner_id: int, slot: str) -> None:
    if slot not in SLOTS:
        raise StoreError(f"There's no {slot!r} slot.")
    if slot in REQUIRED_SLOTS:
        raise StoreError("You always need a body!")
    if slot in SLOT_DEFAULTS:
        # Starters aren't listed in the store, so "taking off" a bought
        # piece puts the starter back on rather than leaving the slot empty.
        db.set_equipped(conn, learner_id, slot, SLOT_DEFAULTS[slot])
        return
    db.clear_equipped(conn, learner_id, slot)
