"""Pet Supplies (PLAN.md 11l): treats, toys, fish food, and color potions.

Treats (and fish food) are used up; toys are kept. In a habitat you throw
one by typing a word, and the pets there that like it run to it and get
happier: each pet has up to MAX_JOY hearts, one more per treat or toy it
plays with, and one fewer for each day nobody plays with it. Fish just eat.

Color potions repaint a pet (and its whole school). The shop has new ones
each day, two in each tier; a tier says how much of the potion's two colors
you can see before you buy it (a mystery shows none).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date

from app import db
from app import pet_genes as g

MAX_JOY = 5


@dataclass(frozen=True, slots=True)
class Supply:
    id: str
    name: str
    kind: str  # treat, toy, fish_food
    price: int
    likes: tuple[str, ...] = ()  # species that run after it
    sinks: bool = False  # fish food: sinks to the bottom feeders, or floats down slowly


SUPPLIES: dict[str, Supply] = {
    s.id: s
    for s in [
        # treats: used up
        Supply("bone_biscuit", "Bone Biscuit", "treat", 5, ("dog", "fox")),
        Supply("fishy_cracker", "Fishy Cracker", "treat", 5, ("cat",)),
        Supply("carrot_stick", "Carrot Stick", "treat", 5, ("bunny", "goat")),
        Supply("apple_slice", "Apple Slice", "treat", 5, ("sheep", "llama", "turtle")),
        Supply("cricket_crunch", "Cricket Crunch", "treat", 5, ("lizard", "snake")),
        Supply("berry_bites", "Berry Bites", "treat", 5, ("fox", "bunny", "turtle")),
        Supply("ember_candy", "Ember Candy", "treat", 5, ("dragon", "phoenix")),
        Supply("star_sugar", "Star Sugar", "treat", 5, ("unicorn", "llama")),
        # toys: kept
        Supply("ball", "Bouncy Ball", "toy", 100, ("dog", "cat", "fox", "goat")),
        Supply("frisbee", "Frisbee", "toy", 100, ("dog",)),
        Supply("feather_wand", "Feather Wand", "toy", 100, ("cat", "fox")),
        Supply("yarn_ball", "Yarn Ball", "toy", 100, ("cat", "bunny")),
        Supply("jolly_ball", "Jolly Ball", "toy", 100, ("goat", "sheep", "llama")),
        Supply("hay_ball", "Hay Ball", "toy", 100, ("bunny", "goat", "sheep")),
        Supply("wiggle_worm", "Wiggle Worm", "toy", 100, ("lizard", "snake", "turtle")),
        Supply("treasure_orb", "Treasure Orb", "toy", 100, ("dragon",)),
        Supply("rainbow_ribbon", "Rainbow Ribbon", "toy", 100, ("unicorn",)),
        Supply("flame_feather", "Flame Feather", "toy", 100, ("phoenix",)),
        # fish food: used up, in tanks
        Supply("fish_flakes", "Fish Flakes", "fish_food", 5, ("fish",)),
        Supply("sinking_pellets", "Sinking Pellets", "fish_food", 5, ("fish",), sinks=True),
    ]
}

# Potion tiers: price, and which of its two colors (main, second) show before you buy.
POTION_TIERS = {
    "mystery": (20, ()),
    "second": (40, (1,)),
    "main": (60, (0,)),
    "clear": (150, (0, 1)),
}
POTIONS_PER_TIER = 2
# Potions use the shared colors (no metals, no species' own families), so most pets can wear them.
POTION_COLORS = tuple(
    c.id for c in g.COLORS.values()
    if c.family != "metal" and c.id not in g.GLOW_ONLY and not any(c.family.startswith(f) for f in g.OWN_FAMILIES)
)


class SupplyError(ValueError):
    """Kid-readable, like ShopError."""


def _pay(conn, learner_id: int, cost: int, what: str, ref: str) -> None:
    balance = db.get_coin_balance(conn, learner_id)
    if balance < cost:
        raise SupplyError(f"You need {cost - balance:,} more coins for the {what}.")
    db.add_coins(conn, learner_id, -cost, "purchase", ref=ref)


# --- treats, toys, fish food ---------------------------------------------------------


def buy(conn, learner_id: int, item_id: str) -> dict:
    item = SUPPLIES.get(item_id)
    if item is None:
        raise SupplyError("There's nothing like that in the shop.")
    have = db.get_supply_counts(conn, learner_id).get(item_id, 0)
    if item.kind == "toy" and have:
        raise SupplyError(f"You already have a {item.name}! Toys never get used up.")
    _pay(conn, learner_id, item.price, item.name, f"supply:{item_id}")
    db.add_supply(conn, learner_id, item_id, 1)
    return {"item": item_id, "have": have + 1}


def _use(conn, learner_id: int, item_id: str, kinds: tuple[str, ...]) -> Supply:
    item = SUPPLIES.get(item_id)
    if item is None or item.kind not in kinds:
        raise SupplyError("You can't use that here.")
    if db.get_supply_counts(conn, learner_id).get(item_id, 0) < 1:
        raise SupplyError(f"You don't have any {item.name}. Get some at the Pet Shop!")
    if item.kind != "toy":
        db.add_supply(conn, learner_id, item_id, -1)
    return item


# --- happiness ----------------------------------------------------------------------


def joy(pet: dict, today: date) -> int:
    """Hearts now: what it had, one fewer for each day since anyone played."""
    if not pet.get("joy") or not pet.get("joy_on"):
        return 0
    days = (today - date.fromisoformat(pet["joy_on"])).days
    return max(0, min(MAX_JOY, pet["joy"] - max(0, days)))


def play(conn, learner_id: int, spot: int, item_id: str, today: date) -> dict:
    """Throw a treat or toy in a habitat: the pets there that like it get a heart."""
    if not any(h["spot"] == spot for h in db.list_habitats(conn, learner_id)):
        raise SupplyError("There's no habitat there yet.")
    item = _use(conn, learner_id, item_id, ("treat", "toy"))
    likers = {}
    for pet in db.list_v3_pets(conn, learner_id):
        if pet["home"] == f"trail:{spot}" and pet["species"] in item.likes:
            hearts = min(MAX_JOY, joy(pet, today) + 1)
            db.update_v3_pet(conn, learner_id, pet["id"], joy=hearts, joy_on=today.isoformat())
            likers[pet["id"]] = hearts
    return {"item": item_id, "likers": likers, "used_up": item.kind == "treat"}


def feed_fish(conn, learner_id: int, spot: int, item_id: str) -> dict:
    if not any(t["spot"] == spot for t in db.list_tanks(conn, learner_id)):
        raise SupplyError("There's no tank there yet.")
    item = _use(conn, learner_id, item_id, ("fish_food",))
    return {"item": item_id, "sinks": item.sinks}


# --- potions ------------------------------------------------------------------------


def potion_stock(learner_id: int, today: date) -> list[dict]:
    """Today's potions: two in each tier, the same all day, new tomorrow."""
    rng = random.Random(f"potions:{learner_id}:{today.isoformat()}")
    out = []
    for tier in POTION_TIERS:
        for _ in range(POTIONS_PER_TIER):
            main, second = rng.sample(POTION_COLORS, 2)
            out.append({"index": len(out), "tier": tier, "colors": [main, second]})
    return out


def _shown(tier: str, colors: list[str]) -> list[dict | None]:
    """The potion's colors as the label shows them (None: a mystery)."""
    visible = POTION_TIERS[tier][1]
    return [_color(c) if i in visible else None for i, c in enumerate(colors)]


def _color(color_id: str) -> dict:
    c = g.COLORS[color_id]
    return {"id": c.id, "name": c.name, "hex": c.hex}


def buy_potion(conn, learner_id: int, index: int, today: date) -> dict:
    stock = potion_stock(learner_id, today)
    if not 0 <= index < len(stock):
        raise SupplyError("There's no potion there.")
    if any(p["slot"] == index and p["bought_on"] == today.isoformat() for p in db.list_potions(conn, learner_id)):
        raise SupplyError("That potion is sold! New ones come tomorrow.")
    potion = stock[index]
    _pay(conn, learner_id, POTION_TIERS[potion["tier"]][0], "potion", f"potion:{potion['tier']}")
    pid = db.add_potion(conn, learner_id, potion["colors"], potion["tier"], index, today.isoformat())
    return {"id": pid, "tier": potion["tier"]}


def potions_state(conn, learner_id: int, today: date) -> dict:
    sold = {p["slot"] for p in db.list_potions(conn, learner_id) if p["bought_on"] == today.isoformat()}
    return {
        "stock": [
            {"index": p["index"], "tier": p["tier"], "price": POTION_TIERS[p["tier"]][0],
             "shown": _shown(p["tier"], p["colors"]), "sold": p["index"] in sold}
            for p in potion_stock(learner_id, today)
        ],
        "owned": len([p for p in db.list_potions(conn, learner_id) if not p["used_on"]]),
    }


def potions_for(conn, learner_id: int, pet: dict) -> list[dict]:
    """Your unused potions that can go on this pet (its species can wear both colors)."""
    return [
        {"id": p["id"], "tier": p["tier"], "shown": _shown(p["tier"], p["colors"])}
        for p in db.list_potions(conn, learner_id)
        if not p["used_on"] and all(g.fits(pet["species"], c) for c in p["colors"])
    ]


def use_potion(conn, learner_id: int, pet_ids: list[int], potion_id: int, today: date) -> dict:
    """Repaint a pet (all of `pet_ids`: a school) with a potion's two colors,
    and unlock them. Returns the colors, revealed."""
    potion = next((p for p in db.list_potions(conn, learner_id) if p["id"] == potion_id and not p["used_on"]), None)
    if potion is None:
        raise SupplyError("You don't have that potion.")
    pets = [db.get_v3_pet(conn, learner_id, i) for i in pet_ids]
    if not pets or None in pets:
        raise SupplyError("You don't have that pet.")
    if not all(g.fits(pets[0]["species"], c) for c in potion["colors"]):
        raise SupplyError(f"That potion doesn't work on a {pets[0]['species']}.")
    for pet in pets:
        genes = pet["genes"]
        colors = list(genes["coat"]["colors"])
        colors[0], colors[1] = potion["colors"]
        genes = {**genes, "coat": {**genes["coat"], "colors": colors}}
        db.update_v3_pet_genes(conn, learner_id, pet["id"], json.dumps(genes))
    db.use_potion(conn, learner_id, potion_id, today.isoformat())
    db.unlock_pet_colors(conn, learner_id, potion["colors"])
    return {"colors": [_color(c) for c in potion["colors"]]}


# --- the shop and the shelves --------------------------------------------------------


def supplies_state(conn, learner_id: int, today: date) -> dict:
    have = db.get_supply_counts(conn, learner_id)
    return {
        "items": [
            {"id": s.id, "name": s.name, "kind": s.kind, "price": s.price, "likes": list(s.likes),
             "sinks": s.sinks, "have": have.get(s.id, 0)}
            for s in SUPPLIES.values()
        ],
        "potions": potions_state(conn, learner_id, today),
    }


def shelf(conn, learner_id: int, kinds: tuple[str, ...]) -> list[dict]:
    """What you have to play with (habitats) or feed (tanks)."""
    have = db.get_supply_counts(conn, learner_id)
    return [
        {"id": s.id, "name": s.name, "kind": s.kind, "likes": list(s.likes), "sinks": s.sinks, "have": have[s.id]}
        for s in SUPPLIES.values()
        if s.kind in kinds and have.get(s.id, 0) > 0
    ]
