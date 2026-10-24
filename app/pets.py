"""Pets (PLAN.md 11c-2, phase 4): each pet is an individual the learner
owns -- species, coloring, name, and growth from 0 (baby) to 10 (grown).
Food is bought and fed once per pet per day, one growth point each, so
growing up takes ~10 practice days. Up to 2 pets come along on the
avatar; the rest wait in the pet room.

Species/coloring ids are drawing keys for web/static/js/pets.js.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from app import db

MAX_GROWTH = 10
MAX_ALONG = 2  # avatar slots 1 (right) and 2 (left)
FOOD_PRICE = 100
MAX_NAME = 16


@dataclass(frozen=True, slots=True)
class Species:
    id: str
    name: str
    price: int
    colors: tuple[str, ...]
    description: str


SPECIES: dict[str, Species] = {
    s.id: s
    for s in [
        Species("hedgehog", "Hedgehog", 1500, ("brown", "cream", "dark"), "Small, spiky, and very loyal."),
        Species("bunny", "Bunny", 1800, ("white", "brown", "gray", "cream", "black"), "Hops along beside you."),
        Species("cat", "Cat", 2000, ("orange", "gray", "black", "white", "tabby"), "Naps on warm keyboards."),
        Species("dog", "Dog", 2200, ("golden", "brown", "black", "white", "gray"), "Always happy to see you."),
        Species("sheep", "Sheep", 2500, ("white", "cream", "gray", "black", "pink"), "Fluffy and soft."),
        Species("goat", "Goat", 2500, ("white", "brown", "black", "tan"), "Climbs everything."),
        Species("fox", "Fox", 3000, ("red", "arctic", "silver"), "Curious about everything you type."),
        Species("llama", "Llama", 3500, ("white", "brown", "cream", "gray"), "Tall, calm, and a little bit silly."),
    ]
}

# Pets bought before this module existed were plain store items.
_LEGACY_PET_ITEMS = {"pet_hedgehog": ("hedgehog", "brown"), "pet_fox": ("fox", "red")}


class PetError(ValueError):
    """Kid-readable, like StoreError."""


def stage(growth: int) -> str:
    if growth >= MAX_GROWTH:
        return "grown"
    return "young" if growth >= 4 else "baby"


def _today() -> str:
    return date.today().isoformat()


def _view(row: dict) -> dict:
    return {
        **row,
        "species_name": SPECIES[row["species"]].name,
        "stage": stage(row["growth"]),
        "fed_today": row["last_fed"] == _today(),
        "max_growth": MAX_GROWTH,
    }


def migrate_legacy(conn: sqlite3.Connection, learner_id: int) -> None:
    """Turn old pet_* store items into grown pets (keeping one along if
    it was equipped). Idempotent: the items are removed once converted."""
    owned = db.list_owned_item_ids(conn, learner_id)
    equipped = db.get_equipped(conn, learner_id).get("pet")
    for item_id, (species, color) in _LEGACY_PET_ITEMS.items():
        if item_id not in owned:
            continue
        slot = 1 if equipped == item_id else None
        db.add_pet(conn, learner_id, species, color, SPECIES[species].name, growth=MAX_GROWTH, slot=slot)
        db.remove_owned_item(conn, learner_id, item_id)
    db.clear_equipped(conn, learner_id, "pet")


def list_pets(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    return [_view(p) for p in db.list_pets(conn, learner_id)]


def along(conn: sqlite3.Connection, learner_id: int) -> list[dict]:
    """The pets drawn on the avatar, as the renderer wants them."""
    return [
        {"id": p["id"], "species": p["species"], "color": p["color"], "stage": p["stage"], "slot": p["slot"]}
        for p in list_pets(conn, learner_id)
        if p["slot"] is not None
    ]


def _get(conn: sqlite3.Connection, learner_id: int, pet_id: int) -> dict:
    pet = db.get_pet(conn, learner_id, pet_id)
    if pet is None:
        raise PetError("That pet isn't yours.")
    return pet


def _spend(conn: sqlite3.Connection, learner_id: int, price: int, what: str, ref: str) -> None:
    balance = db.get_coin_balance(conn, learner_id)
    if balance < price:
        raise PetError(f"You need {price - balance} more coins for {what}.")
    db.add_coins(conn, learner_id, -price, "purchase", ref=ref)


def adopt(conn: sqlite3.Connection, learner_id: int, species: str, color: str) -> dict:
    kind = SPECIES.get(species)
    if kind is None or color not in kind.colors:
        raise PetError("There's no pet like that.")
    _spend(conn, learner_id, kind.price, f"a {kind.name.lower()}", f"pet:{species}_{color}")
    # a new baby comes along straight away if there's a free spot
    used = {p["slot"] for p in db.list_pets(conn, learner_id)}
    free = next((s for s in range(1, MAX_ALONG + 1) if s not in used), None)
    pet_id = db.add_pet(conn, learner_id, species, color, kind.name, growth=0, slot=free)
    return _view(db.get_pet(conn, learner_id, pet_id))


def feed(conn: sqlite3.Connection, learner_id: int, pet_id: int) -> dict:
    pet = _get(conn, learner_id, pet_id)
    if pet["growth"] >= MAX_GROWTH:
        raise PetError(f"{pet['name']} is all grown up!")
    if pet["last_fed"] == _today():
        raise PetError(f"{pet['name']} is full. Come back tomorrow!")
    _spend(conn, learner_id, FOOD_PRICE, "pet food", f"food:{pet_id}")
    db.update_pet(conn, learner_id, pet_id, growth=pet["growth"] + 1, last_fed=_today())
    return _view(db.get_pet(conn, learner_id, pet_id))


def rename(conn: sqlite3.Connection, learner_id: int, pet_id: int, name: str) -> dict:
    _get(conn, learner_id, pet_id)
    name = name.strip()
    if not name or len(name) > MAX_NAME:
        raise PetError(f"Pet names need 1 to {MAX_NAME} letters.")
    db.update_pet(conn, learner_id, pet_id, name=name)
    return _view(db.get_pet(conn, learner_id, pet_id))


def set_along(conn: sqlite3.Connection, learner_id: int, pet_id: int, slot: int | None) -> None:
    """Bring a pet along in avatar slot 1 or 2 (whoever was there goes home),
    or send it home with slot=None."""
    pet = _get(conn, learner_id, pet_id)
    if slot is not None and slot not in range(1, MAX_ALONG + 1):
        raise PetError("Pets can only come along on your left or right.")
    if slot is not None:
        for other in db.list_pets(conn, learner_id):
            if other["slot"] == slot and other["id"] != pet["id"]:
                db.update_pet(conn, learner_id, other["id"], slot=None)
    db.update_pet(conn, learner_id, pet_id, slot=slot)


def catalog() -> list[dict]:
    return [
        {"species": s.id, "name": s.name, "price": s.price, "colors": list(s.colors), "description": s.description}
        for s in SPECIES.values()
    ]
