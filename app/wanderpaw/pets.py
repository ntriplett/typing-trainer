"""Wanderpaw's pets (PLAN.md 11n, phase 4): types, levels, stats, the party.

Types live here (only this game uses them). Each species has a primary
type; mythicals also have a second one from level 1, as strong as the
first. Fish stay home (no type).

Levels: XP_PER_LEVEL XP a level. A pet's type levels are what gates, nooks
and temples count (summed over the party): the primary type is the pet's
level; at SECOND_TYPE_LEVEL a pet picks a second type from two offered
(the type it has fought beside most, and one more), which counts up from
1 (a level 7 pet that picked at 5: 7 and 3).

A pet's Wanderpaw record (`Record`, the wander_pet table) is its XP, its
second type and the level it picked it at, battles fought beside each
type (`partners`), and whether it's starred (listed first).

Stats come from the pet's genes (battle: strength, speed, stamina, 1..10)
and its level. A party's energy is pooled for a trip (steps cost from the
pool). Empty party slots get temporary starters (level 1, one of each
missing type) that don't level.

A team member (`member()`, kept in the save for the trip) is a plain
dict: {id (None for a starter), name, species, xp, types, and stats():
level, energy, power, speed, mana}.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from app.wanderpaw import world as wd

TYPES = wd.REGIONS
SPECIES_TYPES: dict[str, tuple[str, str | None]] = {
    # farm and household pets: two of each type
    "dog": ("splash", None), "turtle": ("splash", None),
    "fox": ("ember", None), "lizard": ("ember", None),
    "bunny": ("leaf", None), "goat": ("leaf", None),
    "llama": ("dream", None), "sheep": ("dream", None),
    "cat": ("shock", None), "snake": ("shock", None),
    # mythicals: both types from level 1, each pair different
    "dragon": ("shock", "ember"),
    "phoenix": ("ember", "dream"),
    "unicorn": ("dream", "leaf"),
    "mermaid": ("splash", "shock"),  # a stub until its art is designed
    "flower_fairy": ("leaf", "splash"),  # a stub until its art is designed
}
MYTHICAL = frozenset(s for s, (_, second) in SPECIES_TYPES.items() if second)
XP_PER_LEVEL = 500
SECOND_TYPE_LEVEL = 5
PARTY_SIZE = 5
STARTERS = {"splash": ("Puddle", "dog"), "ember": ("Pip", "fox"), "leaf": ("Clover", "bunny"),
            "dream": ("Fluff", "sheep"), "shock": ("Zip", "cat")}
STARTER_STATS = {"strength": 5, "speed": 5, "stamina": 5}


@dataclass(frozen=True, slots=True)
class Record:
    xp: int = 0
    second: str | None = None
    second_at: int | None = None
    partners: dict[str, int] = field(default_factory=dict)  # type -> battles fought beside it
    starred: bool = False


def can_go(species: str) -> bool:
    return species in SPECIES_TYPES


def level(xp: int) -> int:
    return 1 + xp // XP_PER_LEVEL


def type_levels(species: str, rec: Record) -> dict[str, int]:
    first, born_second = SPECIES_TYPES[species]
    lv = level(rec.xp)
    out = {first: lv}
    if born_second:
        out[born_second] = lv
    elif rec.second:
        out[rec.second] = lv - rec.second_at + 1
    return out


def stats(species: str, battle: dict, rec: Record) -> dict:
    """energy (for the trip's pool), power, speed, mana (battles), level."""
    lv = level(rec.xp)
    return {
        "level": lv,
        "energy": 14 + battle["stamina"] + 2 * lv,
        "power": battle["strength"] + lv,
        "speed": battle["speed"] + lv,
        "mana": 10 + lv,
    }


def second_choices(seed: int, species: str, rec: Record) -> tuple[str, str] | None:
    """The two types offered at SECOND_TYPE_LEVEL (None: nothing to pick):
    the type it has fought beside most (else a random one), and another."""
    if species in MYTHICAL or rec.second or level(rec.xp) < SECOND_TYPE_LEVEL:
        return None
    first = SPECIES_TYPES[species][0]
    rng = random.Random(f"wanderpaw-second:{seed}")
    others = [t for t in TYPES if t != first]
    fought = [t for t in others if rec.partners.get(t)]
    best = max(fought, key=lambda t: (rec.partners[t], -others.index(t))) if fought else rng.choice(others)
    return best, rng.choice([t for t in others if t != best])


def pick_second(seed: int, species: str, rec: Record, choice: str) -> Record:
    offered = second_choices(seed, species, rec)
    if not offered or choice not in offered:
        raise ValueError("That type isn't one of the choices.")
    return replace(rec, second=choice, second_at=level(rec.xp))


def note_battle(rec: Record, partner_types: list[str]) -> Record:
    """One battle fought beside pets of these types."""
    partners = dict(rec.partners)
    for t in partner_types:
        partners[t] = partners.get(t, 0) + 1
    return replace(rec, partners=partners)


def gain_xp(rec: Record, amount: int) -> Record:
    return replace(rec, xp=rec.xp + amount)


# --- the team --------------------------------------------------------------------


def member(pet: dict, rec: Record) -> dict:
    """A real pet as it goes on a trip (pet: a pets v3 row with genes)."""
    return {"id": pet["id"], "name": pet["name"], "species": pet["species"], "xp": rec.xp,
            "types": type_levels(pet["species"], rec), **stats(pet["species"], pet["genes"]["battle"], rec)}


def starter(kind: str, lv: int = 1) -> dict:
    """A temporary starter of a type (lv: tests and the lab only)."""
    name, species = STARTERS[kind]
    rec = Record(xp=(lv - 1) * XP_PER_LEVEL)
    return {"id": None, "name": name, "species": species, "xp": rec.xp, "types": {kind: lv},
            **stats(species, STARTER_STATS, rec)}


def team(members: list[dict]) -> list[dict]:
    """The party, its empty slots filled with starters of the types it's missing."""
    have = {t for m in members for t in m["types"]}
    missing = [t for t in TYPES if t not in have]
    return members[:PARTY_SIZE] + [starter(t) for t in missing[: PARTY_SIZE - len(members)]]


def team_levels(members: list[dict], kind: str) -> int:
    return sum(m["types"].get(kind, 0) for m in members)


def team_energy(members: list[dict]) -> int:
    return sum(m["energy"] for m in members)


def record_json(rec: Record) -> dict:
    return {"xp": rec.xp, "second": rec.second, "second_at": rec.second_at, "partners": rec.partners, "starred": rec.starred}


def record_from(data: dict | None) -> Record:
    return Record(**data) if data else Record()
