"""Wanderpaw's pets (PLAN.md 11n, phase 4): types, levels, stats, the party.

Types live here (only this game uses them). Each species has a primary
type; mythicals also have a second one from level 1, as strong as the
first. Fish stay home (no type).

Levels: the first takes XP_FIRST_LEVEL XP and each one after takes XP_GROWTH
times the last, up to MAX_LEVEL. A pet's type levels are what gates, nooks
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
dict: {id (None for a starter), name, species, xp, types, stats() (level,
energy, power, speed, mana), and its looks (genes, growth) for drawing}.
"""

from __future__ import annotations

import random
from bisect import bisect_right
from dataclasses import dataclass, field, replace
from itertools import accumulate

from app import pet_genes
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
# No art yet: what a wild one of these looks like until it's designed.
STAND_IN = {"mermaid": "turtle", "flower_fairy": "bunny"}
# The color families a tougher creature wears, rarest for the toughest.
TIER_COLORS = {"tough": ("bold_red", "bold_blue", "bold_purple", "bold_green", "bold_teal", "bold_pink"), "champion": ("neon",), "boss": ("metal",)}
XP_FIRST_LEVEL = 500
XP_GROWTH = 1.08
MAX_LEVEL = 21
FOCUS_LEVEL = 3
SECOND_TYPE_LEVEL = 5
MIX_LEVEL = 7
UPGRADE_LEVEL = 9
SEVENTH_SLOT_LEVEL = 11
REVERSE_MIX_LEVEL = 13
THIRD_TYPE_LEVEL = 15
EIGHTH_SLOT_LEVEL = 17
ANY_MIX_LEVEL = 19
CAPSTONE_LEVEL = 21
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
    focus: str | None = None  # what it chose at FOCUS_LEVEL (battle.FOCUSES)
    swaps: dict[str, str] = field(default_factory=dict)  # move id it gave up -> move id it got (level choices)
    upgrades: list[str] = field(default_factory=list)  # move ids made "+" ("refocus": took a focus back instead)
    extra: list[str] = field(default_factory=list)  # move ids in the slots past six
    third: str | None = None
    third_at: int | None = None
    pending: str | None = None  # a move picked at a level, waiting for its slot
    done: list[str] = field(default_factory=list)  # choices made that leave no other trace
    capstone: str | None = None  # "first:second", chosen at CAPSTONE_LEVEL (battle.CAPSTONES)


def can_go(species: str) -> bool:
    return species in SPECIES_TYPES


def _level_costs(growth: float = XP_GROWTH) -> list[int]:
    """XP from each level to the next, to the nearest 5."""
    return [5 * round(XP_FIRST_LEVEL * growth**i / 5) for i in range(MAX_LEVEL - 1)]


LEVEL_XP = (0, *accumulate(_level_costs()))  # the XP that reaches each level (level 1 first)


def xp_for(lv: int) -> int:
    """The XP that reaches level lv."""
    return LEVEL_XP[min(lv, MAX_LEVEL) - 1]


def level(xp: int) -> int:
    return bisect_right(LEVEL_XP, xp)


def progress(xp: int) -> tuple[int, int] | None:
    """XP into this level and what it takes (None: fully leveled)."""
    lv = level(xp)
    return None if lv == MAX_LEVEL else (xp - xp_for(lv), xp_for(lv + 1) - xp_for(lv))


def type_levels(species: str, rec: Record) -> dict[str, int]:
    first, born_second = SPECIES_TYPES[species]
    lv = level(rec.xp)
    out = {first: lv}
    if born_second:
        out[born_second] = lv
    elif rec.second:
        out[rec.second] = lv - rec.second_at + 1
    if rec.third:
        out[rec.third] = lv - rec.third_at + 1
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
    return learn_second(rec, choice, level(rec.xp))


def third_choices(seed: int, species: str, rec: Record) -> tuple[str, str] | None:
    """The two types offered at THIRD_TYPE_LEVEL (None: nothing to pick): the
    type it has fought beside most that it doesn't have (else a random one), and another."""
    if rec.third or level(rec.xp) < THIRD_TYPE_LEVEL:
        return None
    others = [t for t in TYPES if t not in type_levels(species, rec)]
    if len(others) < 2:
        return None
    rng = random.Random(f"wanderpaw-third:{seed}")
    fought = [t for t in others if rec.partners.get(t)]
    best = max(fought, key=lambda t: (rec.partners[t], -others.index(t))) if fought else rng.choice(others)
    return best, rng.choice([t for t in others if t != best])


def learn_third(rec: Record, choice: str, at: int) -> Record:
    return replace(rec, third=choice, third_at=at)


def learn_second(rec: Record, choice: str, at: int) -> Record:
    return replace(rec, second=choice, second_at=at)


def learn_focus(rec: Record, focus: str) -> Record:
    return replace(rec, focus=focus)


def learn_swap(rec: Record, gives_up: str, gets: str) -> Record:
    return replace(rec, swaps={**rec.swaps, gives_up: gets})


def learn_upgrade(rec: Record, move: str) -> Record:
    return replace(rec, upgrades=[*rec.upgrades, move])


def learn_move(rec: Record, gives_up: str, gets: str) -> Record:
    """A new move takes a slot: one of the six, or one past them."""
    if gives_up in rec.extra:
        return replace(rec, extra=[gets if m == gives_up else m for m in rec.extra])
    return learn_swap(rec, gives_up, gets)


def learn_capstone(rec: Record, capstone: str) -> Record:
    return replace(rec, capstone=capstone)


def note_done(rec: Record, what: str) -> Record:
    return replace(rec, done=[*rec.done, what])


def pick_move(rec: Record, move: str, what: str) -> Record:
    """A move picked, waiting for its slot."""
    return replace(rec, pending=move, done=[*rec.done, what])


def place_pending(rec: Record, gives_up: str) -> Record:
    return replace(learn_move(rec, gives_up, rec.pending), pending=None)


def learn_slot(rec: Record, move: str) -> Record:
    return replace(rec, extra=[*rec.extra, move])


def take_back(rec: Record, focus_move: str) -> Record:
    """A focus's move returns to its slot, in place of the level's upgrade (what took its slot needs a new one)."""
    return replace(rec, swaps={k: v for k, v in rec.swaps.items() if k != focus_move}, upgrades=[*rec.upgrades, "refocus"])


def at_level(rec: Record, lv: int) -> Record:
    """The record as it stands on reaching level lv."""
    return replace(rec, xp=xp_for(lv))


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
    return {"id": pet["id"], "name": pet["name"], "species": pet["species"], "xp": rec.xp, "progress": progress(rec.xp), "focus": rec.focus, "swaps": rec.swaps, "upgrades": rec.upgrades, "extra": rec.extra, "capstone": rec.capstone,
            "types": type_levels(pet["species"], rec), **stats(pet["species"], pet["genes"]["battle"], rec),
            "genes": pet_genes.resolve(pet["genes"]) if "coat" in pet["genes"] else None, "growth": pet.get("growth", 10)}


def starter(kind: str, lv: int = 1) -> dict:
    """A temporary starter of a type (lv: tests and the lab only)."""
    name, species = STARTERS[kind]
    rec = Record(xp=xp_for(lv))
    return {"id": None, "name": name, "species": species, "xp": rec.xp, "types": {kind: lv},
            **stats(species, STARTER_STATS, rec), "genes": looks(species, sum(map(ord, name))), "growth": 10}


def looks(species: str, seed: int) -> dict:
    """Rolled looks for a pet that isn't anyone's (a starter, a wild creature)."""
    return pet_genes.resolve(pet_genes.roll(species, None, None, seed))


def tier_looks(species: str, seed: int, tier: str) -> dict:
    """A tougher creature's rare colors, so it stands out in battle."""
    return pet_genes.resolve(pet_genes.wild_rare(species, seed, TIER_COLORS[tier]))


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
    return {"xp": rec.xp, "second": rec.second, "second_at": rec.second_at, "partners": rec.partners, "starred": rec.starred, "focus": rec.focus, "swaps": rec.swaps, "upgrades": rec.upgrades, "extra": rec.extra, "third": rec.third, "third_at": rec.third_at,
            "pending": rec.pending, "done": rec.done, "capstone": rec.capstone}


def record_from(data: dict | None) -> Record:
    return Record(**data) if data else Record()
