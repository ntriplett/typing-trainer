"""Wanderpaw's quests (PLAN.md 11n): who gives them and where things hide,
built from the seed (the world and its small maps), the same every time.

Each region's town has two quest-givers (story.NPCS), one for each broken
shortcut on its borders: its own (to the next region around the ring) and
the region before's. So every shortcut has a quest-giver in the town on
each side. Each lost thing hides somewhere (a Spot): one of a town's two
in the region's pocket (behind its weak-against gate) if it has one, the
other in a nook a few big hexes from town that takes 3 levels of the
nook's type (a cave: Ember, a dive spot: Splash, a glade: Leaf, a
grotto: Dream, a mine: Shock).
The region's temple key hides in another such nook, on the temple's side
if it can.

Each side of a broken shortcut has a part waiting by it
(story.SHORTCUTS' parts); the shortcut's gate knows the 3 on
each side (world.Gate.types), which is what it takes to bring the far
part across without walking round.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import world as wd
from app.wanderpaw.hexes import Hex

FETCH_LEVEL = 3  # what a nook with a lost thing or a key takes
QUEST_NOOKS = ("cave", "glade", "dive", "grotto", "mine")  # first choice of hiding places: one per type
NEAR_TOWN = (2, 4)  # big-hex steps from town, best first


@dataclass(frozen=True, slots=True)
class Spot:
    """Where something hides: big hex, small hex, what kind of place
    ("pocket", "ground", or a nook kind) and what it takes there (a type
    and its levels; None: just walk up)."""

    big: Hex
    at: Hex
    kind: str
    check: tuple[str, int] | None = None


@dataclass(frozen=True, slots=True)
class Giver:
    """A quest-giver: in `town` (of region `region`), in the building with
    role `role`, about the broken shortcut of region `shortcut`."""

    id: str  # "town region:shortcut region"
    region: str
    shortcut: str
    town: Hex
    house: Hex
    lost: Spot

    @property
    def role(self) -> str:
        return role_for(self.shortcut)


@dataclass(frozen=True, slots=True)
class Plan:
    givers: dict[str, Giver]
    keys: dict[str, Spot]  # region -> where its temple key hides


def role_for(shortcut: str) -> str:
    """The building role of the quest-giver about a region's shortcut."""
    return lc.QUEST_ROLE.format(shortcut)


def givers_in(region: str) -> list[str]:
    """The shortcuts a region's town has quest-givers for: its own and the region before's."""
    return [region, wd.weak_against(region)]


@lru_cache(maxsize=32)
def plan(seed: int) -> Plan:
    world = wd.generate(seed)
    rng = random.Random(f"wanderpaw-quests:{wd.STORY_VERSION}:{seed}")
    shut = wd.gate_needs(world, (0, 0), shortcuts_open=False)
    givers, keys = {}, {}
    for region in wd.REGIONS:
        q = world.quests[region]
        used: set[tuple[Hex, Hex]] = set()
        town = lc.generate(seed, q.town)
        for i, shortcut in enumerate(givers_in(region)):
            house = next(h for h, role in town.buildings.items() if role == role_for(shortcut))
            spot = None
            if i == 0 and q.pocket:
                spot = _ground(seed, max(q.pocket, key=lambda b: (hx.distance(b, q.town), b)), "pocket", used)
            spot = spot or _nook(rng, seed, world, region, q.town, used)
            used.add((spot.big, spot.at))
            gid = f"{region}:{shortcut}"
            givers[gid] = Giver(gid, region, shortcut, q.town, house, spot)
        # The key: the temple's side of the region if it can.
        guard = wd.strong_against(region)
        behind = {h for h, b in world.hexes.items() if b.region == region and all(n.get(guard, 0) >= 3 for n in shut[h])}
        keys[region] = _nook(rng, seed, world, region, q.town, used, prefer=behind)
    return Plan(givers, keys)


def _nook(rng, seed: int, world: wd.World, region: str, town: Hex, used: set, prefer: set[Hex] = frozenset()) -> Spot:
    """A nook in the region a few steps from town (preferring QUEST_NOOKS,
    then any nook that takes a type, then open ground)."""
    steps = wd.distances_from(world, town)
    cells = [h for h, b in sorted(world.hexes.items()) if b.region == region and not b.special]

    def order(h: Hex) -> tuple:
        d = steps.get(h, 99)
        return (h not in prefer, not NEAR_TOWN[0] <= d <= NEAR_TOWN[1], abs(d - NEAR_TOWN[0]), rng.random())

    for kinds in (QUEST_NOOKS, tuple(lc.NOOK_SKILL)):
        for big in sorted(cells, key=order):
            local = lc.generate(seed, big)
            for h, nook in sorted(local.nooks.items()):
                if nook.kind in kinds and (big, h) not in used:
                    return Spot(big, h, nook.kind, (lc.NOOK_SKILL[nook.kind], FETCH_LEVEL))
    big = min(cells, key=order)
    return _ground(seed, big, "ground", used) or Spot(big, lc.generate(seed, big).campfire, "ground")


def _ground(seed: int, big: Hex, kind: str, used: set) -> Spot | None:
    """Open ground in a big hex, as far from its campfire as it gets."""
    local = lc.generate(seed, big)
    taken = set(local.pois) | set(local.nooks) | set(local.exits) | set(local.buildings) | {local.campfire}
    ground = [h for h in lc.reachable(local.tiles, local.campfire)
              if local.tiles[h] in lc.GROUND and h not in taken and (big, h) not in used]
    if not ground:
        return None
    return Spot(big, max(ground, key=lambda h: (hx.distance(h, local.campfire), h)), kind)


def bridge_sides(world: wd.World, region: str) -> dict[Hex, str]:
    """A shortcut's two sides (big hex -> the type of the 3 on that side)."""
    edge = world.quests[region].shortcut
    return dict(zip(edge, world.gates[edge].types))


def plan_json(p: Plan) -> dict:
    """The lab's view: every quest-giver's lost thing and every key."""
    spot = lambda s: {"big": list(s.big), "at": list(s.at), "kind": s.kind, "check": list(s.check) if s.check else None}  # noqa: E731
    return {"givers": [{"id": g.id, "region": g.region, "shortcut": g.shortcut, "town": list(g.town), "lost": spot(g.lost)}
                       for g in p.givers.values()],
            "keys": {r: spot(s) for r, s in p.keys.items()}}
