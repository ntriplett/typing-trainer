"""Sharing a pet's design with a friend: another player on this computer.

The sender keeps their pet. A copy of its look waits in the friend's
Special Orders from the next day, until they adopt it (for an average
day's shop price) or say no thanks. It comes home a baby, with none of
the Wanderpaw levels (those live in the Wanderpaw save anyway).

One share waits at a time from each player to each friend. A friend can
only be sent a pet their shop sells already: its department and Special
Orders have to be open. Companions are themselves, so they aren't shared.
"""

from __future__ import annotations

import copy
from datetime import date

from app import db, lessons, pet_shop
from app import pet_genes as g
from app.pet_shop import DEPARTMENTS, Department

ROW_NAMES = {
    pet_shop.HOME_KEYS: "home row", pet_shop.TOP_ROW: "top row",
    pet_shop.BOTTOM_ROW: "bottom row", pet_shop.NUMBERS: "numbers",
}


class ShareError(ValueError):
    """Kid-readable, like ShopError."""


def species_dept(species: str) -> Department | None:
    return next((d for d in DEPARTMENTS.values() if species in d.species and d.id != "companions"), None)


def design(genes: dict) -> dict:
    """The look to copy: everything in the genes, but a fresh level 1."""
    out = copy.deepcopy(genes)
    if "battle" in out:
        out["battle"] = {**out["battle"], "level": 1, "xp": 0}
    return out


def _name(conn, learner_id: int) -> str:
    return db.get_learner(conn, learner_id).name


def blocker(conn, sender: int, friend: int, species: str) -> str | None:
    """Why this friend can't be sent this pet now, or None."""
    name = _name(conn, friend)
    taught = lessons.taught_keys(conn, friend)
    for dept in (DEPARTMENTS["orders"], species_dept(species)):
        if not pet_shop.is_open(dept, taught):
            return f"{name} needs to learn the {ROW_NAMES.get(dept.needs, 'keys')} first."
    if db.waiting_pet_shares(conn, from_learner=sender, to_learner=friend):
        return f"Your last pet for {name} is still waiting for them."
    return None


def _shareable(conn, learner_id: int, pet_id: int) -> dict:
    pet = db.get_v3_pet(conn, learner_id, pet_id)
    if pet is None:
        raise ShareError("You don't have that pet.")
    if pet["species"] in g.COMPANIONS:
        raise ShareError("She's one of a kind, so she can't be shared.")
    if species_dept(pet["species"]) is None:
        raise ShareError("This pet can't be shared.")
    return pet


def friends(conn, learner_id: int, pet_id: int) -> list[dict]:
    """Everyone else on this computer, and why each can't get this pet now (None: they can)."""
    pet = _shareable(conn, learner_id, pet_id)
    rows = conn.execute("SELECT id, name FROM learner WHERE id != ? ORDER BY id", (learner_id,))
    return [{"id": r["id"], "name": r["name"], "why": blocker(conn, learner_id, r["id"], pet["species"])} for r in rows]


def send(conn, learner_id: int, pet_id: int, friend: int, today: date) -> dict:
    pet = _shareable(conn, learner_id, pet_id)
    if friend == learner_id or db.get_learner(conn, friend) is None:
        raise ShareError("There's no friend like that.")
    why = blocker(conn, learner_id, friend, pet["species"])
    if why:
        raise ShareError(why)
    share_id = db.add_pet_share(conn, learner_id, friend, design(pet["genes"]), today.isoformat())
    return {"id": share_id, "to": _name(conn, friend)}


def price(conn, learner_id: int, genes: dict) -> int:
    return pet_shop.price(genes, db.list_pet_color_unlocks(conn, learner_id), pet_shop.PRICE_ROLL_MEAN)


def arrived(share: dict, today: date) -> bool:
    return date.fromisoformat(share["sent_on"]) < today


def waiting_for(conn, learner_id: int, today: date) -> list[dict]:
    """Friends' pets waiting in this player's Special Orders (sent before today)."""
    unlocked = db.list_pet_color_unlocks(conn, learner_id)
    return [
        {
            "id": s["id"], "from": _name(conn, s["from_learner"]), "species": s["species"],
            "genes": g.resolve(s["genes"]), "price": pet_shop.price(s["genes"], unlocked, pet_shop.PRICE_ROLL_MEAN),
            "new_colors": g.new_to_player(s["genes"], unlocked), "rare": g.rare_features(s["genes"]),
        }
        for s in db.waiting_pet_shares(conn, to_learner=learner_id)
        if arrived(s, today)
    ]


def _incoming(conn, learner_id: int, share_id: int, today: date) -> dict:
    share = db.get_pet_share(conn, share_id)
    if share is None or share["to_learner"] != learner_id or share["status"] != "waiting" or not arrived(share, today):
        raise ShareError("That pet isn't waiting for you.")
    return share


def adopt(conn, learner_id: int, share_id: int, today: date) -> dict:
    """Pay for a friend's pet: it comes home like a shop pet. Returns the new pet."""
    share = _incoming(conn, learner_id, share_id, today)
    cost = price(conn, learner_id, share["genes"])
    balance = db.get_coin_balance(conn, learner_id)
    if balance < cost:
        raise ShareError(f"You need {cost - balance:,} more coins for this {g.species_name(share['species']).lower()}.")
    db.add_coins(conn, learner_id, -cost, "purchase", ref=f"pet:share:{share_id}")
    pet = pet_shop.adopt(conn, learner_id, share["genes"], "friend")
    db.finish_pet_share(conn, share_id, "adopted", today.isoformat(), pet["id"])
    return {**pet, "from": _name(conn, share["from_learner"])}


def decline(conn, learner_id: int, share_id: int, today: date) -> None:
    _incoming(conn, learner_id, share_id, today)
    db.finish_pet_share(conn, share_id, "declined", today.isoformat())
