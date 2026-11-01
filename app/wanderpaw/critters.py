"""Wanderpaw's wild creatures (PLAN.md 11n, phase 5): who's where, from the
seed, standing on small hexes you can see coming.

Guardians stand at key spots, the same every day: in front of a nook's
door, beside a chest or a dead-end treat, in a one-wide stretch of trail.
Wanderers turn up somewhere new each day (seeded by the day). A beaten
creature is gone for the rest of the trip.

They're wild animals of the pet species, mostly their region's (Ember
lands: foxes and lizards, ...), with their own rolled looks. Their level
follows how deep the place is: the type levels it takes to get there
(world.gate_needs, the cheapest way) and how far out it is. The heartland
has plenty of weak ones, enough to take a starting party up a level.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app.wanderpaw import world as wd
from app.wanderpaw.hexes import Hex

GUARDIANS = {"heartland": (2, 3), "region": (2, 3)}  # per big hex
WANDERERS = {"heartland": (1, 2), "region": (1, 2)}  # per big hex, per day
OTHER_SPECIES = 0.2  # a creature from outside its region
KEEP_CLEAR = 2  # steps from the campfire with no creatures
COMMON = sorted(s for s, (_, second) in wp.SPECIES_TYPES.items() if not second)


@dataclass(frozen=True, slots=True)
class Critter:
    id: str
    big: Hex
    at: Hex
    species: str
    kind: str  # its type
    level: int
    guardian: bool
    seed: int  # its looks (pet_genes.roll)


def _region_species(region: str) -> list[str]:
    return [s for s in COMMON if wp.SPECIES_TYPES[s][0] == region] or COMMON


@lru_cache(maxsize=8)
def _depth(seed: int) -> dict[Hex, int]:
    """How deep each big hex is: the highest gate level on the cheapest way in."""
    needs = wd.gate_needs(wd.generate(seed), (0, 0), shortcuts_open=False)
    return {h: max(n[0].values(), default=0) for h, n in needs.items()}


def _level(rng: random.Random, seed: int, big: Hex) -> int:
    depth = _depth(seed).get(big, 0)
    ring = wd.generate(seed).hexes[big].ring
    if depth == 0:
        return rng.randint(1, 2)
    return max(1, depth + rng.randint(0, 1) + ring // 3 - 1)


def _free(local: lc.LocalMap, taken: set[Hex]) -> list[Hex]:
    """Walkable hexes a creature may stand on: not near the campfire, not on
    a building, gate, exit, place of interest or nook."""
    near_fire = set(hx.spiral(local.campfire, KEEP_CLEAR))
    return [h for h in sorted(lc.reachable(local.tiles, local.campfire))
            if local.tiles[h] in lc.GROUND and h not in near_fire and h not in taken
            and h not in local.exits and h not in local.pois and h not in local.nooks]


def _make(rng: random.Random, seed: int, big: Hex, at: Hex, guardian: bool, cid: str) -> Critter:
    here = wd.generate(seed).hexes[big]
    region = here.region if here.region in wd.REGIONS else None
    if region and rng.random() >= OTHER_SPECIES:
        species = rng.choice(_region_species(region))
    else:
        species = rng.choice(COMMON)
    return Critter(cid, big, at, species, wp.SPECIES_TYPES[species][0], _level(rng, seed, big), guardian,
                   rng.randrange(2**31))


@lru_cache(maxsize=256)
def guardians(seed: int, big: Hex) -> tuple[Critter, ...]:
    world = wd.generate(seed)
    here = world.hexes[big]
    if here.special in ("camp", "town", "final", "temple"):
        return ()
    local = lc.generate(seed, big)
    rng = random.Random(f"wanderpaw-guardians:{wd.STORY_VERSION}:{seed}:{big}")
    free = set(_free(local, set()))
    # Key spots first: in front of a nook's door or beside a treat, then
    # one-wide stretches of trail.
    keys = []
    for h, nook in sorted(local.nooks.items()):
        keys += [d for d in nook.doors if d in free] or [n for n in hx.neighbors(h) if n in free]
    for h, poi in sorted(local.pois.items()):
        if poi == "chest":
            keys += [n for n in hx.neighbors(h) if n in free]
    narrow = [h for h in sorted(free) if local.tiles[h] == "path"
              and sum(local.walkable(n) for n in hx.neighbors(h) if n in lc.CELL_SET) == 2]
    rng.shuffle(keys)
    rng.shuffle(narrow)
    want = rng.randint(*GUARDIANS["heartland" if here.region == wd.HEARTLAND else "region"])
    spots: list[Hex] = []
    for h in keys + narrow:
        if len(spots) < want and h not in spots and not any(hx.distance(h, s) < 3 for s in spots):
            spots.append(h)
    return tuple(_make(rng, seed, big, h, True, f"g:{big[0]},{big[1]}:{h[0]},{h[1]}") for h in spots)


def wanderers(seed: int, big: Hex, day: int) -> tuple[Critter, ...]:
    world = wd.generate(seed)
    here = world.hexes[big]
    if here.special in ("camp", "town", "final", "temple"):
        return ()
    local = lc.generate(seed, big)
    rng = random.Random(f"wanderpaw-wanderers:{wd.STORY_VERSION}:{seed}:{big}:{day}")
    taken = {c.at for c in guardians(seed, big)}
    free = [h for h in _free(local, taken) if not any(hx.distance(h, t) < 2 for t in taken)]
    rng.shuffle(free)
    want = rng.randint(*WANDERERS["heartland" if here.region == wd.HEARTLAND else "region"])
    return tuple(_make(rng, seed, big, h, False, f"w{day}:{big[0]},{big[1]}:{h[0]},{h[1]}") for h in free[:want])


def at(seed: int, big: Hex, day: int) -> dict[Hex, Critter]:
    """Every creature in a big hex on a given day, by where it stands."""
    return {c.at: c for c in (*guardians(seed, big), *wanderers(seed, big, day))}
