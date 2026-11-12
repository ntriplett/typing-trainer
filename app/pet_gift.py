"""Pets a grown-up gives a player: a design from the pet lab (a JSON copy of
its genes), pasted on the For Grown-ups page. It waits wrapped up at the Pet
Shop (a box at its door on the Pets hub, and on the welcome rug inside)
until the player opens it, names it and takes it home, free, as a baby.
Several can wait; they're opened one at a time, oldest first."""

from __future__ import annotations

from app import db, pet_care, pet_shop
from app import pet_genes as g

MAX_FROM = 20


class GiftError(ValueError):
    """Kid- (or grown-up-) readable."""


def _clean_name(name: object, fallback: str, limit: int) -> str:
    text = " ".join(str(name or "").split())[:limit]
    return text or fallback


def send(conn, to_learner: int, from_name: str, design: object) -> dict:
    """Wrap a design up for a player. `design` is the lab's JSON: genes, or
    {"name": ..., "genes": {...}}."""
    if db.get_learner(conn, to_learner) is None:
        raise GiftError("There's no player like that.")
    name = None
    if isinstance(design, dict) and isinstance(design.get("genes"), dict):
        name, design = design.get("name"), design["genes"]
    try:
        genes = g.design_from(design)
    except (g.GeneError, KeyError, TypeError, ValueError) as exc:
        raise GiftError(f"That pet couldn't be wrapped up: {exc}") from None
    name = _clean_name(name, g.species_name(genes["species"]), pet_care.MAX_NAME)
    giver = _clean_name(from_name, "a grown-up", MAX_FROM)
    gift_id = db.add_pet_gift(conn, to_learner, giver, name, genes)
    return {"id": gift_id, "name": name, "species": genes["species"], "from": giver}


def waiting(conn, learner_id: int) -> dict | None:
    """The next gift to open (oldest first), or None."""
    gifts = db.waiting_pet_gifts(conn, learner_id)
    if not gifts:
        return None
    gift = gifts[0]
    return {"id": gift["id"], "from": gift["from_name"], "name": gift["name"], "species": gift["genes"]["species"],
            "genes": g.resolve(gift["genes"]), "note": gift["note"], "more": len(gifts) - 1}


def open_gift(conn, learner_id: int, gift_id: int, name: object) -> dict:
    """Open a gift and take the pet home, with the name the player picked."""
    gift = next((x for x in db.waiting_pet_gifts(conn, learner_id) if x["id"] == gift_id), None)
    if gift is None:
        raise GiftError("That gift isn't here.")
    pet = pet_shop.adopt(conn, learner_id, gift["genes"], "gift")
    pet_name = _clean_name(name, gift["name"], pet_care.MAX_NAME)
    db.update_v3_pet(conn, learner_id, pet["id"], name=pet_name)
    db.open_pet_gift(conn, gift_id, pet["id"])
    return {**pet, "name": pet_name, "from": gift["from_name"]}
