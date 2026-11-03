"""The Pet Care Center and the Trailhead's habitats (PLAN.md 11i): feeding,
naming, homes, and which pets come along with the avatar. Pets live in
app/db.py's v3 `pet` table; habitats are bought in the Pet Shop."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

from app import aquarium, db, garden, pet_supplies
from app import pet_genes as g

MAX_GROWTH = 10
FAVORITE_GROWTH = 2  # its favorite veggie grows a pet twice as much
MAX_ALONG = 2  # avatar slots 1 (right) and 2 (left)
MAX_NAME = 16
TRAIL_SPOTS = 10
HABITAT_PETS = 6
WATER_ONLY = {"fish"}  # they wait for the Aquarium
SWIMMERS_ONLY = {"mermaid"}  # habitats with enough water to swim in, and nowhere else


@dataclass(frozen=True, slots=True)
class HabitatKind:
    id: str
    name: str
    tier: str  # TIER_PRICE; magical ones open with the Mythical department
    water: bool = False  # a pool big enough for a grown mermaid (habitats.js draws it)


TIER_PRICE = {"everyday": 1500, "cozy": 2500, "magical": 5000}
FREE_TIER = "everyday"  # a player's first habitat is free if it's an everyday one

# Each kind's look is web/static/js/habitats.js HABITAT_LOOKS; a kind is sold
# once it has one. More come in batches (PLAN.md 11j).
HABITAT_KINDS: dict[str, HabitatKind] = {
    h.id: h
    for h in [
        HabitatKind("meadow", "Meadow", "everyday"),
        HabitatKind("forest", "Forest", "everyday"),
        HabitatKind("stream", "Stream", "everyday", water=True),
        HabitatKind("mountain", "Mountain", "everyday"),
        HabitatKind("farmyard", "Farmyard", "everyday"),
        HabitatKind("backyard", "Backyard", "everyday"),
        HabitatKind("beach", "Beach", "everyday", water=True),
        HabitatKind("desert", "Desert", "everyday"),
        HabitatKind("jungle", "Jungle", "everyday", water=True),
        HabitatKind("tundra", "Snowy Tundra", "everyday"),
        HabitatKind("orchard", "Autumn Orchard", "everyday"),
        HabitatKind("pond", "Pond & Marsh", "everyday", water=True),
        HabitatKind("savanna", "Savanna", "everyday", water=True),
        HabitatKind("cottage", "Cozy Cottage", "cozy"),
        HabitatKind("greenhouse", "Greenhouse", "cozy"),
        HabitatKind("treehouse", "Treehouse Village", "cozy"),
        HabitatKind("library", "Library Nook", "cozy"),
        HabitatKind("playroom", "Playroom", "cozy"),
        HabitatKind("hayloft", "Hay Loft", "cozy"),
        HabitatKind("attic", "Attic Hideaway", "cozy"),
        HabitatKind("porch", "Sunny Porch", "cozy"),
        HabitatKind("crystalcave", "Crystal Cave", "magical", water=True),
        HabitatKind("cloudkingdom", "Cloud Kingdom", "magical"),
        HabitatKind("volcano", "Volcano Rim", "magical"),
        HabitatKind("grove", "Enchanted Grove", "magical", water=True),
        HabitatKind("observatory", "Starry Observatory", "magical"),
        HabitatKind("lagoon", "Foggy Lagoon", "magical", water=True),
    ]
}


class CareError(ValueError):
    """Kid-readable, like ShopError."""


def home_id(spot: int) -> str:
    return f"trail:{spot}"


def home_spot(home: str | None) -> int | None:
    return int(home.split(":")[1]) if home and home.startswith("trail:") else None


def _pet(conn, learner_id: int, pet_id: int) -> dict:
    pet = db.get_v3_pet(conn, learner_id, pet_id)
    if pet is None:
        raise CareError("You don't have that pet.")
    return pet


def view(pet: dict, today: date) -> dict:
    genes = g.resolve(pet["genes"])
    return {
        "id": pet["id"], "name": pet["name"], "species": pet["species"], "growth": pet["growth"],
        "genes": genes, "source": pet["source"], "adopted_at": pet["adopted_at"],
        "spot": home_spot(pet["home"]), "tank": aquarium.tank_spot(pet["home"]), "along": pet["along"],
        "fed_today": pet["last_fed"] == today.isoformat(),
        "grown": pet["growth"] >= MAX_GROWTH,
        "rarity": round(g.rarity(pet["genes"]), 3),
        "rare": g.rare_features(pet["genes"]),
        "water": pet["species"] in WATER_ONLY,
        "swimmer": pet["species"] in SWIMMERS_ONLY,
        "companion": pet["species"] in g.COMPANIONS,
        "joy": pet_supplies.joy(pet, today),
    }


# --- one pet ----------------------------------------------------------------------------


# --- schools: copies of a fish (pet.school is the first fish's id) ------------------


def school_of(conn, learner_id: int, pet_id: int) -> list[dict]:
    """A fish and every copy of it (the first fish first); any other pet alone."""
    pet = _pet(conn, learner_id, pet_id)
    head = pet["school"] or pet["id"]
    return [p for p in db.list_v3_pets(conn, learner_id) if p["id"] == head or p["school"] == head]


def _each_in_school(conn, learner_id: int, pet_id: int, **fields) -> None:
    for p in school_of(conn, learner_id, pet_id):
        db.update_v3_pet(conn, learner_id, p["id"], **fields)


def rename(conn, learner_id: int, pet_id: int, name: str) -> None:
    _pet(conn, learner_id, pet_id)
    name = " ".join(name.split())
    if not name:
        raise CareError("Your pet needs a name!")
    if len(name) > MAX_NAME:
        raise CareError(f"Names can be up to {MAX_NAME} letters.")
    _each_in_school(conn, learner_id, pet_id, name=name)


def feed(conn, learner_id: int, pet_id: int, veggie: str, today: date) -> dict:
    """One veggie a day: +1 growth, +2 if it's the pet's favorite."""
    pet = _pet(conn, learner_id, pet_id)
    if veggie not in garden.VEGGIES:
        raise CareError("That's not a veggie.")
    if pet["growth"] >= MAX_GROWTH:
        raise CareError(f"{pet['name']} is all grown up!")
    if pet["last_fed"] == today.isoformat():
        raise CareError(f"{pet['name']} is full. Come back tomorrow!")
    if db.get_veggies(conn, learner_id).get(veggie, 0) < 1:
        raise CareError(f"You don't have any {garden.VEGGIES[veggie].plural.lower()}. Grow some in the garden!")
    favorite = g.resolve(pet["genes"])["personality"]["favorite"] == veggie
    growth = min(MAX_GROWTH, pet["growth"] + (FAVORITE_GROWTH if favorite else 1))
    db.add_veggies(conn, learner_id, veggie, -1, f"fed:pet:{pet_id}")
    _each_in_school(conn, learner_id, pet_id, growth=growth, last_fed=today.isoformat())  # a school grows together
    return {"growth": growth, "favorite": favorite}


def set_along(conn, learner_id: int, pet_id: int, slot: int | None) -> None:
    """Bring a pet along in avatar slot 1 or 2 (whoever was there stays
    home), or leave it home (slot None)."""
    pet = _pet(conn, learner_id, pet_id)
    if slot is not None:
        if slot not in range(1, MAX_ALONG + 1):
            raise CareError("Pets can come along on your left or right.")
        if pet["species"] in WATER_ONLY:
            raise CareError("Fish need to stay in the water!")
        for other in db.list_v3_pets(conn, learner_id):
            if other["along"] == slot and other["id"] != pet_id:
                db.update_v3_pet(conn, learner_id, other["id"], along=None)
    db.update_v3_pet(conn, learner_id, pet_id, along=slot)


def set_home(conn, learner_id: int, pet_id: int, spot: int | None) -> None:
    """Move a pet into a habitat, or back to the Care Center (spot None)."""
    pet = _pet(conn, learner_id, pet_id)
    if spot is not None:
        habitat = next((h for h in db.list_habitats(conn, learner_id) if h["spot"] == spot), None)
        if habitat is None:
            raise CareError("There's no habitat there yet.")
        if pet["species"] in WATER_ONLY:
            raise CareError("Fish need water! They'll live in the Aquarium.")
        if pet["species"] in SWIMMERS_ONLY and not HABITAT_KINDS[habitat["kind"]].water:
            raise CareError(f"{habitat['name']} doesn't have enough water for a {pet['species']}.")
        living = [p for p in db.list_v3_pets(conn, learner_id) if p["home"] == home_id(spot) and p["id"] != pet_id]
        if len(living) >= HABITAT_PETS:
            raise CareError(f"{habitat['name']} is full ({HABITAT_PETS} pets).")
    db.update_v3_pet(conn, learner_id, pet_id, home=home_id(spot) if spot is not None else None)


def along_pets(conn, learner_id: int) -> list[dict]:
    """The pets riding with the avatar (avatar.js draws them by `slot`)."""
    return sorted(
        (
            {"id": p["id"], "name": p["name"], "species": p["species"], "growth": p["growth"],
             "genes": g.resolve(p["genes"]), "slot": p["along"]}
            for p in db.list_v3_pets(conn, learner_id)
            if p["along"]
        ),
        key=lambda p: p["slot"],
    )


def guard_pet(conn, learner_id: int) -> dict:
    """Who runs out for you in Crow Patrol: your first pet along, or a friendly stray."""
    along = along_pets(conn, learner_id)
    if along:
        return along[0]
    return {"name": "", "species": "dog", "growth": 10, "genes": g.resolve(g.roll("dog", None, None, learner_id)), "slot": None}


# --- habitats -------------------------------------------------------------------------


def habitat_price(conn, learner_id: int, kind: str) -> int:
    tier = HABITAT_KINDS[kind].tier
    if tier == FREE_TIER and not db.list_habitats(conn, learner_id):
        return 0
    return TIER_PRICE[tier]


def buy_habitat(conn, learner_id: int, kind: str, magical_open: bool = False) -> dict:
    """A new habitat takes the first empty spot on the trail. The same kind
    can be bought again ("Forest 2")."""
    if kind not in HABITAT_KINDS:
        raise CareError("There's no habitat like that.")
    if HABITAT_KINDS[kind].tier == "magical" and not magical_open:
        raise CareError("Magical habitats open with the Mythical Pets department.")
    habitats = db.list_habitats(conn, learner_id)
    taken = {h["spot"] for h in habitats}
    spot = next((s for s in range(TRAIL_SPOTS) if s not in taken), None)
    if spot is None:
        raise CareError("Your trail is full!")
    cost = habitat_price(conn, learner_id, kind)
    if cost:
        balance = db.get_coin_balance(conn, learner_id)
        if balance < cost:
            raise CareError(f"You need {cost - balance:,} more coins for this {HABITAT_KINDS[kind].name}.")
        db.add_coins(conn, learner_id, -cost, "purchase", ref=f"habitat:{kind}")
    same = sum(1 for h in habitats if h["kind"] == kind)
    name = HABITAT_KINDS[kind].name + (f" {same + 1}" if same else "")
    db.add_habitat(conn, learner_id, spot, kind, name)
    return {"spot": spot, "kind": kind, "name": name, "price": cost}


def habitats_state(conn, learner_id: int, magical_open: bool = False) -> dict:
    """The Pet Shop's Habitats department."""
    habitats = db.list_habitats(conn, learner_id)
    return {
        "kinds": [
            {
                "id": h.id, "name": h.name, "tier": h.tier, "price": habitat_price(conn, learner_id, h.id),
                "open": h.tier != "magical" or magical_open,
            }
            for h in HABITAT_KINDS.values()
        ],
        "owned": len(habitats),
        "spots": TRAIL_SPOTS,
        "capacity": HABITAT_PETS,
    }


def _habitat_view(habitat: dict, pets: list[dict]) -> dict:
    living = [p for p in pets if p["spot"] == habitat["spot"]]
    return {**habitat, "pets": living, "capacity": HABITAT_PETS}


def trail(conn, learner_id: int, today: date) -> dict:
    """All 10 spots along the trail: a habitat with its pets, or an empty lot (None)."""
    pets = [view(p, today) for p in db.list_v3_pets(conn, learner_id)]
    by_spot = {h["spot"]: h for h in db.list_habitats(conn, learner_id)}
    return {
        "spots": [_habitat_view(by_spot[s], pets) if s in by_spot else None for s in range(TRAIL_SPOTS)],
    }


def habitat(conn, learner_id: int, spot: int, today: date) -> dict:
    found = next((h for h in db.list_habitats(conn, learner_id) if h["spot"] == spot), None)
    if found is None:
        raise CareError("There's no habitat there yet.")
    return _habitat_view(found, [view(p, today) for p in db.list_v3_pets(conn, learner_id)])


# --- the Care Center book -----------------------------------------------------------


def care_state(conn, learner_id: int, today: date) -> dict:
    """The book: one entry per pet, a school of fish as one entry with its count."""
    rows = db.list_v3_pets(conn, learner_id)
    every = [view(p, today) for p in rows]  # every fish counts in its tank
    schools: dict[int, list[dict]] = {}
    for p in rows:
        schools.setdefault(p["school"] or p["id"], []).append(p)
    pets = []
    for row, v in zip(rows, every, strict=True):
        if row["school"]:
            continue
        members = schools[row["id"]]
        entry = {**v, "school": len(members), "school_tanks": sorted({aquarium.tank_spot(m["home"]) for m in members} - {None})}
        if v["water"]:
            from app import pet_shop  # pet_shop imports this module; prices live there

            entry["copy_price"] = pet_shop.copy_price(conn, learner_id, row["genes"])
        pets.append(entry)
    return {
        "pets": pets,
        "habitats": [
            {**h, "count": sum(1 for p in pets if p["spot"] == h["spot"]), "capacity": HABITAT_PETS, "water": HABITAT_KINDS[h["kind"]].water}
            for h in db.list_habitats(conn, learner_id)
        ],
        "tanks": [
            {"spot": t["spot"], "name": t["name"], "count": sum(1 for p in every if p["tank"] == t["spot"]),
             "capacity": aquarium.TANK_FISH}
            for t in aquarium.tanks(conn, learner_id)
        ],
        "veggies": db.get_veggies(conn, learner_id),
        "veggie_names": {v.id: v.name for v in garden.VEGGIES.values()},
        "max_growth": MAX_GROWTH,
        "max_along": MAX_ALONG,
        "max_name": MAX_NAME,
    }


# --- the hub field ----------------------------------------------------------------


FIELD_UNASSIGNED = 4


def field_pets(conn, learner_id: int, today: date) -> list[dict]:
    """The hub field: the pets along, plus the newest land pets without a home."""
    pets = [view(p, today) for p in db.list_v3_pets(conn, learner_id)]
    along = sorted((p for p in pets if p["along"]), key=lambda p: p["along"])
    waiting = [p for p in pets if not p["along"] and p["spot"] is None and not p["water"]]
    return along + sorted(waiting, key=lambda p: p["id"], reverse=True)[:FIELD_UNASSIGNED]


# --- Pet Battles ----------------------------------------------------------------


# Partners for players without pets along: fixed seeds, so they look the same every game.
BATTLE_STARTERS = (("Clover", "bunny", 101), ("Pip", "fox", 202), ("Puddle", "dog", 303))
STARTER_GROWTH = 5
WILD_GROWTH = 10


def battle_pets(game: dict, rng: random.Random | None = None) -> dict:
    """Pet Battles' game data with v3 looks: each level's wild critter
    (`foe_genes`, new every game, in starter colors) and the starters."""
    rng = rng or random.Random()
    wild = lambda species: g.resolve(g.shop_roll(species, set(), g.new_seed(rng)))  # noqa: E731
    return {
        **game,
        "levels": [{**lv, "foe_genes": wild(lv["foe"]), "foe_growth": WILD_GROWTH} for lv in game["levels"]],
        "starters": [
            {"name": name, "species": sp, "growth": STARTER_GROWTH, "genes": g.resolve(g.shop_roll(sp, set(), seed))}
            for name, sp, seed in BATTLE_STARTERS
        ],
    }
