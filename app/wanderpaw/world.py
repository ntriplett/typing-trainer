"""Wanderpaw's world, built from a seed (PLAN.md 11n).

The big map is a hexagon of MAP_RADIUS big hexes around Camp, its outer
ring trimmed ragged. The heartland (Camp's ring and Camp) belongs to no
type; the rest is five type regions, wedges in the order of the type ring
(REGIONS), each with its temple on the far edge of the map. Biomes deepen
with distance from Camp, and every hex gets a made-up name.

Edges: you can't walk any direction. Neighboring big hexes are either
joined ("open") or walled off by a river, cliff, thicket or rocks. Each
region is a maze (a tree) grown from its one way in off the heartland,
plus loops that never join two zones (see gates), so getting somewhere
means weaving around. Regions only meet through broken shortcuts.

Gates (a level of a type, cleared once for good; _plan_region):
- the heartland (Camp and its ring) is free;
- entering a region: ENTRY_LEVEL of its own type;
- its temple: the region's farthest hex (in steps from Camp, at least
  TEMPLE_MIN_STEPS) with one neighbor, behind TEMPLE_LEVEL of its own type;
- about half the region, temple side, behind SPLIT_LEVEL of the type it's
  very strong against (strong_against);
- its town (TOWN_RINGS from Camp, outside that half) behind TOWN_LEVEL of
  its own type;
- maybe a pocket of 1-2 hexes behind POCKET_LEVEL of the type it's weak
  against (weak_against).
A zone is the hexes behind the same gates. Each region's broken shortcut
(a quest gate its elder repairs) cuts through the border to the next
region around the ring, between two places that each take exactly one 3
(of any type) and no 8; the quest checks both of those 3s, so opening it
never skips anything above a 2. A layout that breaks a rule is thrown out and the seed tried
again (World.rerolls says why).

The same seed always builds the same world (generate() is cached), so a
save only keeps the seed and what the player found. Bump WORLD_VERSION when
a change here would move things under existing players.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache

from app.wanderpaw import hexes as hx
from app.wanderpaw.hexes import Hex

WORLD_VERSION = 2
STORY_VERSION = 2  # places of interest in small maps
MAP_RADIUS = 6
HEARTLAND_RADIUS = 1
TRIM_CHANCE = 0.35  # outer-ring hexes dropped for a ragged coast
REGION_JITTER = 9  # degrees: wobbles the wedge borders
MAZE_WINDING = 0.7  # how often the maze keeps digging from its newest hex
LOOP_CHANCE = 0.12  # extra open edges inside a region
MAZE_TRIES = 40  # mazes tried per region; the first that fits the rules wins
MAX_TRIES = 300  # layouts tried for a seed before giving up
ENTRY_LEVEL = 2
TOWN_LEVEL = 3
SPLIT_LEVEL = 3
POCKET_LEVEL = 3
TEMPLE_LEVEL = 13
TEMPLE_MIN_STEPS = 7
TOWN_RINGS = (3, 5)
SPLIT_SHARE = (0.3, 0.7)  # of the region behind the split gate
POCKET_SIZE = (1, 2)
TOWN_TRIES = 10  # towns tried per region to find its shortcut a place
SHORTCUT_LEVEL = 3  # each side of a shortcut takes exactly one gate this high

# The type ring, in order around the map (each beats the next two).
REGIONS = ("splash", "ember", "dream", "leaf", "shock")
HEARTLAND = "camp"


def tw(kind: str) -> str:
    """A type's name as it goes in text the player reads: "{ember}". The page
    draws these all caps in the type's color (wander_text.js)."""
    return "{" + kind + "}"

# region -> [(biome, nearest ring, farthest ring)]
BIOMES: dict[str, list[tuple[str, int, int]]] = {
    HEARTLAND: [("fields", 0, 1), ("orchard", 0, 1)],
    "leaf": [("meadow", 2, 3), ("woods", 2, 6), ("fern_hollow", 3, 6), ("deepwood", 4, 6)],
    "splash": [("brookside", 2, 3), ("marsh", 2, 6), ("lakeshore", 3, 6), ("isles", 4, 6)],
    "ember": [("heath", 2, 3), ("red_rocks", 2, 6), ("hot_springs", 3, 6), ("ember_peaks", 4, 6)],
    "shock": [("windy_hills", 2, 3), ("mesa", 2, 6), ("ridge", 3, 6), ("storm_peaks", 4, 6)],
    "dream": [("glade", 2, 3), ("mushroom_grove", 2, 6), ("mist_vale", 3, 6), ("crystal_hollow", 4, 6)],
}

# What walls off a blocked edge, by the biomes on either side (first match wins).
WALL_KINDS: list[tuple[str, set[str]]] = [
    ("river", {"brookside", "marsh", "lakeshore", "isles", "hot_springs"}),
    ("cliff", {"red_rocks", "ember_peaks", "mesa", "ridge", "storm_peaks", "crystal_hollow", "windy_hills"}),
    ("thicket", {"woods", "deepwood", "fern_hollow", "mushroom_grove", "orchard"}),
]
WALL_DEFAULT = "rocks"

NAME_FIRST: dict[str, list[str]] = {
    HEARTLAND: ["Hearth", "Sunny", "Clover", "Honey", "Maple", "Butter"],
    "leaf": ["Thistle", "Fern", "Acorn", "Moss", "Willow", "Hazel", "Bramble", "Sorrel", "Ivy", "Nettle"],
    "splash": ["Reed", "Pebble", "Otter", "Lily", "Brook", "Minnow", "Heron", "Rain", "Ripple", "Shell"],
    "ember": ["Amber", "Cinder", "Lantern", "Ruby", "Copper", "Glow", "Saffron", "Rust", "Marigold", "Chestnut"],
    "shock": ["Thunder", "Bolt", "Gale", "Spark", "Zephyr", "Flint", "Bright", "Crackle", "Kite", "Breezy"],
    "dream": ["Moon", "Star", "Hush", "Velvet", "Lull", "Twilight", "Dusk", "Mist", "Opal", "Wisp"],
}
NAME_LAST: dict[str, list[str]] = {
    "fields": ["Fields", "Acres", "Green"], "orchard": ["Orchard", "Grove"],
    "meadow": ["Meadow", "Lea"], "woods": ["Wood", "Copse", "Glen"],
    "fern_hollow": ["Hollow", "Dell"], "deepwood": ["Deepwood", "Wildwood"],
    "brookside": ["Brook", "Run", "Banks"], "marsh": ["Marsh", "Fen"],
    "lakeshore": ["Shore", "Mere"], "isles": ["Isles", "Shoals"],
    "heath": ["Heath", "Moor"], "red_rocks": ["Rocks", "Bluffs"],
    "hot_springs": ["Springs", "Pools"], "ember_peaks": ["Peaks", "Crags"],
    "windy_hills": ["Hills", "Downs"], "mesa": ["Mesa", "Flats"],
    "ridge": ["Ridge", "Spine"], "storm_peaks": ["Heights", "Summit"],
    "glade": ["Glade", "Bower"], "mushroom_grove": ["Rings", "Grove"],
    "mist_vale": ["Vale", "Hollow"], "crystal_hollow": ["Caverns", "Grotto"],
}
TOWN_ENDINGS = ["ford", "by", "wick", "ton", "stead"]


@dataclass(frozen=True, slots=True)
class BigHex:
    coord: Hex
    region: str
    ring: int  # steps from Camp: how hard it is out there
    biome: str
    name: str
    special: str | None = None  # "camp" | "final" | "temple" | "town"


@dataclass(frozen=True, slots=True)
class Gate:
    """Something in the way on an open big edge: a field skill clears it
    (`kind` a type, `level` the party's levels of it), or, for kind
    "quest", the story quest of `region` repairs it (a shortcut); the
    quest takes `level` of each type in `types` (the 3 on each side)."""

    kind: str
    level: int = 0
    region: str | None = None
    types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Quest:
    """A region's places for its quests (quests.py): its `town`, its broken
    `shortcut` (to the next region around the ring), and its `pocket` (the
    1-2 hexes behind the weak-against gate; maybe none)."""

    region: str
    town: Hex
    shortcut: tuple[Hex, Hex]
    pocket: tuple[Hex, ...] = ()


@dataclass(frozen=True, slots=True)
class World:
    seed: int
    hexes: dict[Hex, BigHex]
    edges: dict[tuple[Hex, Hex], str]  # edge_key -> "open" or a wall kind
    gates: dict[tuple[Hex, Hex], Gate]  # on open edges
    quests: dict[str, Quest]
    rerolls: tuple[str, ...] = ()  # why earlier layouts of this seed were thrown out
    mazes: int = 0  # mazes tried for the regions of the layout that worked

    def is_open(self, a: Hex, b: Hex) -> bool:
        return self.edges.get(hx.edge_key(a, b)) == "open"

    def exits(self, h: Hex) -> list[Hex]:
        """The neighbors you can walk to from h."""
        return [n for n in hx.neighbors(h) if self.is_open(h, n)]

    def temples(self) -> dict[str, Hex]:
        return {b.region: b.coord for b in self.hexes.values() if b.special == "temple"}


class Reroll(Exception):
    """This layout breaks a rule: try the seed again."""


def strong_against(region: str) -> str:
    """The type `region` is very strong against (the next in the ring)."""
    return REGIONS[(REGIONS.index(region) + 1) % len(REGIONS)]


def weak_against(region: str) -> str:
    """The type that's very strong against `region` (the one before it)."""
    return REGIONS[(REGIONS.index(region) - 1) % len(REGIONS)]


@lru_cache(maxsize=32)
def generate(seed: int) -> World:
    reasons: list[str] = []
    for attempt in range(MAX_TRIES):
        rng = random.Random(f"wanderpaw:{WORLD_VERSION}:{seed}:{attempt}")
        try:
            return _build(seed, rng, tuple(reasons))
        except Reroll as why:
            reasons.append(str(why))
    raise RuntimeError(f"no world for seed {seed} after {MAX_TRIES} tries: {reasons[-3:]}")


def _build(seed: int, rng: random.Random, rerolls: tuple[str, ...]) -> World:
    rotation = rng.uniform(0, 360)
    regions = _assign_regions(rng, rotation)
    coords = _trim(rng, regions, set())
    regions = {h: regions[h] for h in coords}
    _make_contiguous(regions)
    biomes = _assign_biomes(rng, regions)
    pairs = sorted({hx.edge_key(h, n) for h in regions for n in hx.neighbors(h) if n in regions})
    open_ = {(a, b) for a, b in pairs if regions[a] == regions[b] == HEARTLAND}
    gates: dict[tuple[Hex, Hex], Gate] = {}
    specials = {(0, 0): "camp", rng.choice([h for h in hx.ring((0, 0), 1) if h in regions]): "final"}
    zones: dict[Hex, tuple] = {h: () for h, r in regions.items() if r == HEARTLAND}
    tries = [0]
    plans = {region: _plan_region(rng, region, regions, pairs, tries) for region in REGIONS}
    for plan in plans.values():
        open_ |= {plan.entry, *plan.maze}
        specials[plan.temple] = "temple"
    towns = {region: plan.towns[0] for region, plan in plans.items()}

    def settle(region: str) -> None:
        gates_, zone_of = _settle(plans[region], towns[region])
        gates.update(gates_)
        zones.update(zone_of)

    for region in REGIONS:
        settle(region)
    shortcuts = {}
    for region in REGIONS:
        # Move the town (a few times) if its shortcut has nowhere to go.
        for town in plans[region].towns[:TOWN_TRIES]:
            for e in _settle(plans[region], towns[region])[0]:
                gates.pop(e, None)
            towns[region] = town
            settle(region)
            needs = {h: _zone_needs(zone, gates) for h, zone in zones.items()}
            # (a town that moves can't take the 3 from under a shortcut already placed)
            if any(not _shortcut_side(needs[h]) for e in shortcuts.values() for h in e):
                continue
            try:
                shortcuts[region] = _pick_shortcut(rng, region, regions, pairs, open_, specials, zones, needs)
                break
            except Reroll:
                continue
        else:
            raise Reroll(f"{region}: no place for a shortcut")
        open_.add(shortcuts[region])
        threes = tuple(next(t for t, v in needs[h].items() if v == SHORTCUT_LEVEL) for h in shortcuts[region])
        gates[shortcuts[region]] = Gate("quest", SHORTCUT_LEVEL, region, threes)
    quests = {}
    for region in REGIONS:
        specials[towns[region]] = "town"
        quests[region] = Quest(region, towns[region], shortcuts[region], plans[region].pocket)
    # Loops, only inside a zone (never to a temple, which keeps one neighbor).
    temples = {plan.temple for plan in plans.values()}
    for a, b in pairs:
        if regions[a] == regions[b] != HEARTLAND and not {a, b} & temples \
                and zones[a] == zones[b] and (a, b) not in open_ and rng.random() < LOOP_CHANCE:
            open_.add((a, b))
    edges = {e: "open" if e in open_ else _wall(biomes[e[0]], biomes[e[1]]) for e in pairs}
    names = _name_hexes(rng, regions, biomes, specials)
    big = {
        h: BigHex(h, regions[h], hx.distance(h, (0, 0)), biomes[h], names[h], specials.get(h))
        for h in sorted(coords)
    }
    world = World(seed, big, edges, gates, quests, rerolls, tries[0])
    _check(world)
    return world


def _tree(open_: set, start: Hex, cells: set[Hex]) -> tuple[dict[Hex, Hex | None], dict[Hex, int]]:
    """Parents and depths of a maze (a tree over cells) from start."""
    parent, depth, todo = {start: None}, {start: 0}, [start]
    for h in todo:
        for n in hx.neighbors(h):
            if n in cells and n not in parent and hx.edge_key(h, n) in open_:
                parent[n] = h
                depth[n] = depth[h] + 1
                todo.append(n)
    return parent, depth


@dataclass(slots=True)
class RegionPlan:
    """One region's maze and where its temple, gates and town can go."""

    cells: set[Hex]
    entry: tuple[Hex, Hex]
    start: Hex
    maze: set[tuple[Hex, Hex]]
    parent: dict[Hex, Hex | None]
    depth: dict[Hex, int]
    temple: Hex
    gates: dict[tuple[Hex, Hex], Gate]  # all but the town's
    towns: list[Hex]  # best first
    pocket: tuple[Hex, ...] = ()


def _plan_region(rng, region, regions, pairs, tries) -> RegionPlan:
    """One region's maze, temple, gates and town spots (see the module's
    rules): up to MAZE_TRIES mazes, the first that fits. tries counts
    mazes tried."""
    cells = {h for h, r in regions.items() if r == region}
    entries = [(a, b) for a, b in pairs if {regions[a], regions[b]} == {HEARTLAND, region}]
    if not cells or not entries:
        raise Reroll(f"{region}: no way in")
    why = ""
    for _ in range(MAZE_TRIES):
        tries[0] += 1
        entry = rng.choice(entries)
        start = next(h for h in entry if h in cells)
        try:
            return _lay_out(rng, region, regions, cells, entry, start, _maze(rng, start, cells))
        except Reroll as no:
            why = str(no)
    raise Reroll(f"{region}: {why}")


def _lay_out(rng, region, regions, cells, entry, start, maze) -> RegionPlan:
    """The temple, gates and town spots for one maze, or Reroll if it can't
    follow the rules."""
    parent, depth = _tree(maze, start, cells)
    steps = {h: d + 2 for h, d in depth.items()}  # Camp -> its ring -> start
    children: dict[Hex, list[Hex]] = {}
    for h, p in parent.items():
        if p:
            children.setdefault(p, []).append(h)

    def below(h: Hex) -> set[Hex]:
        out, todo = {h}, [h]
        for x in todo:
            todo += children.get(x, [])
            out.update(children.get(x, []))
        return out

    # The temple: as far as it gets, at the end of a branch.
    leaves = [h for h in cells if h not in children]
    temple = max(sorted(leaves), key=lambda h: (steps[h], rng.random()))
    if steps[temple] < TEMPLE_MIN_STEPS:
        raise Reroll(f"temple only {steps[temple]} steps out")
    path = [temple]
    while parent[path[-1]]:
        path.append(parent[path[-1]])
    path.reverse()  # start .. temple
    # The split: an edge on the way to the temple with about half the region behind it ...
    lo, hi = (len(cells) * f for f in SPLIT_SHARE)
    splits = sorted(path[1:-1], key=lambda h: (abs(len(below(h)) - len(cells) / 2), h))
    splits = [h for h in splits if lo <= len(below(h)) <= hi]
    if not splits:
        raise Reroll("no even split")
    for split in splits:
        behind = below(split)
        # ... and towns on this side of it, off the way to the temple.
        towns = [h for h in sorted(cells - behind) if h not in path and TOWN_RINGS[0] <= hx.distance(h, (0, 0)) <= TOWN_RINGS[1]]
        if towns:
            break
    else:
        raise Reroll("no split with a town outside it")
    gates = {
        entry: Gate(region, ENTRY_LEVEL),
        hx.edge_key(parent[temple], temple): Gate(region, TEMPLE_LEVEL),
        hx.edge_key(parent[split], split): Gate(strong_against(region), SPLIT_LEVEL),
    }
    # A little pocket behind the type it's weak against, if there's room.
    pockets = [h for h in sorted(cells - behind) if h != start and h not in path and POCKET_SIZE[0] <= len(below(h)) <= POCKET_SIZE[1]]
    pocket_cells: set[Hex] = set()
    if pockets:
        pocket = rng.choice(pockets)
        pocket_cells = below(pocket)
        pocket_cells = {pocket, *pocket_cells}
        gates[hx.edge_key(parent[pocket], pocket)] = Gate(weak_against(region), POCKET_LEVEL)
    # Towns whose zone (what's behind them) runs along the region before
    # this one (whose temple half is behind this region's type), then any
    # neighbor, so the region's shortcut has somewhere to go.
    before = weak_against(region)

    def touches(h: Hex, other) -> int:
        return sum(1 for c in below(h) for n in hx.neighbors(c) if regions.get(n) in other)

    towns = [h for h in towns if h not in pocket_cells]
    if not towns:
        raise Reroll("no split with a town outside it")
    towns.sort(key=lambda h: (-touches(h, {before}), -touches(h, set(REGIONS) - {region}), rng.random()))
    return RegionPlan(cells, entry, start, maze, parent, depth, temple, gates, towns, tuple(sorted(pocket_cells)))


def _settle(plan: RegionPlan, town: Hex) -> tuple[dict, dict[Hex, tuple]]:
    """The region's gates with its town in place, and each hex's zone (the
    gates on the way in from the heartland)."""
    gates = {**plan.gates, hx.edge_key(plan.parent[town], town): Gate(plan.gates[plan.entry].kind, TOWN_LEVEL)}
    zone_of: dict[Hex, tuple] = {}
    for h in sorted(plan.cells, key=lambda x: plan.depth[x]):
        p = plan.parent[h]
        edge = plan.entry if p is None else hx.edge_key(p, h)
        zone_of[h] = (zone_of[p] if p else ()) + ((edge,) if edge in gates else ())
    return gates, zone_of


def _zone_needs(zone: tuple, gates: dict) -> dict[str, int]:
    need: dict[str, int] = {}
    for e in zone:
        g = gates[e]
        need[g.kind] = max(need.get(g.kind, 0), g.level)
    return need


def _shortcut_side(need: dict[str, int]) -> bool:
    """Exactly one 3 and no 8."""
    levels = list(need.values())
    return levels.count(SHORTCUT_LEVEL) == 1 and TEMPLE_LEVEL not in levels


def _pick_shortcut(rng, region, regions, pairs, open_, specials, zones, needs) -> tuple[Hex, Hex]:
    """A wall on the border between the region and the next one around the
    ring, where each side takes exactly one 3 (of any type) and no 8."""
    other = strong_against(region)
    fits = lambda h: _shortcut_side(needs[h])  # noqa: E731
    ok = [(a, b) for a, b in pairs
          if (a, b) not in open_ and {regions[a], regions[b]} == {region, other}
          and specials.get(a) != "temple" and specials.get(b) != "temple"
          and fits(a) and fits(b)]
    if not ok:
        raise Reroll(f"{region}: no place for a shortcut")
    return rng.choice(ok)


def _check(world: World) -> None:
    """With every shortcut open, each temple still wants its own type at
    TEMPLE_LEVEL and its strong-against type at SPLIT_LEVEL, and stays
    TEMPLE_MIN_STEPS out."""
    needs = gate_needs(world, (0, 0), shortcuts_open=True)
    steps = distances_from(world, (0, 0))
    for region, temple in world.temples().items():
        for need in needs[temple]:
            if need.get(region, 0) < TEMPLE_LEVEL or need.get(strong_against(region), 0) < SPLIT_LEVEL:
                raise Reroll(f"{region}: a shortcut skips a temple gate")
        if steps[temple] < TEMPLE_MIN_STEPS:
            raise Reroll(f"{region}: a shortcut brings the temple too close")


def _wedge(h: Hex, rotation: float, jitter: float) -> str:
    return REGIONS[int(((hx.angle(h) - rotation + jitter) % 360) // (360 / len(REGIONS)))]


def _assign_regions(rng: random.Random, rotation: float) -> dict[Hex, str]:
    regions = {}
    for h in hx.spiral((0, 0), MAP_RADIUS):
        jitter = rng.uniform(-REGION_JITTER, REGION_JITTER)
        regions[h] = HEARTLAND if hx.distance(h, (0, 0)) <= HEARTLAND_RADIUS else _wedge(h, rotation, jitter)
    _make_contiguous(regions)
    return regions


def _make_contiguous(regions: dict[Hex, str], keep: set[Hex] = frozenset()) -> None:
    """Every region one piece: stray bits join the region around them
    (the piece holding a `keep` hex, a temple, is never the stray one)."""
    changed = True
    while changed:
        changed = False
        for region in REGIONS:
            parts = _components([h for h, r in regions.items() if r == region])
            for part in sorted(parts, key=lambda p: (bool(p & keep), len(p)))[:-1]:
                for h in sorted(part):
                    around = [regions[n] for n in hx.neighbors(h) if n in regions and regions[n] not in (region, HEARTLAND)]
                    if around:
                        regions[h] = max(set(around), key=lambda r: (around.count(r), r))
                        changed = True


def _components(cells: list[Hex]) -> list[set[Hex]]:
    left, parts = set(cells), []
    while left:
        start = min(left)
        part, todo = {start}, [start]
        while todo:
            for n in hx.neighbors(todo.pop()):
                if n in left and n not in part:
                    part.add(n)
                    todo.append(n)
        left -= part
        parts.append(part)
    return parts


def _angle_gap(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def _trim(rng: random.Random, regions: dict[Hex, str], keep: set[Hex]) -> set[Hex]:
    coords = set(regions)
    for h in hx.ring((0, 0), MAP_RADIUS):
        if h not in keep and rng.random() < TRIM_CHANCE:
            coords.discard(h)
    return coords


def _assign_biomes(rng: random.Random, regions: dict[Hex, str]) -> dict[Hex, str]:
    def options(h: Hex) -> list[str]:
        ring = hx.distance(h, (0, 0))
        return [b for b, lo, hi in BIOMES[regions[h]] if lo <= ring <= hi]

    biomes = {h: rng.choice(options(h)) for h in sorted(regions)}
    # One smoothing pass so biomes come in patches, not confetti.
    smoothed = {}
    for h in sorted(regions):
        near = [biomes[n] for n in hx.neighbors(h) if n in regions and regions[n] == regions[h]] + [biomes[h]]
        allowed = options(h)
        best = max(sorted(set(near) & set(allowed)), key=near.count)
        smoothed[h] = best if near.count(best) >= 3 else biomes[h]
    return smoothed


def _walk(open_: set[tuple[Hex, Hex]], start: Hex, goal: Hex) -> int:
    """Steps from start to goal along open edges."""
    dist, todo = {start: 0}, [start]
    for h in todo:
        if h == goal:
            return dist[h]
        for n in hx.neighbors(h):
            if n not in dist and hx.edge_key(h, n) in open_:
                dist[n] = dist[h] + 1
                todo.append(n)
    raise ValueError("goal not reachable")


def _maze(rng: random.Random, start: Hex, cells: set[Hex]) -> set[tuple[Hex, Hex]]:
    """A "growing tree" maze over cells: mostly keeps digging from the newest
    hex (long winding paths), sometimes branches from an older one."""
    seen, active, open_ = {start}, [start], set()
    while active:
        i = len(active) - 1 if rng.random() < MAZE_WINDING else rng.randrange(len(active))
        h = active[i]
        fresh = [n for n in hx.neighbors(h) if n in cells and n not in seen]
        if not fresh:
            active.pop(i)
            continue
        n = rng.choice(fresh)
        seen.add(n)
        active.append(n)
        open_.add(hx.edge_key(h, n))
    return open_


def _wall(a: str, b: str) -> str:
    for kind, biomes in WALL_KINDS:
        if a in biomes or b in biomes:
            return kind
    return WALL_DEFAULT


def _name_hexes(rng: random.Random, regions: dict[Hex, str], biomes: dict[Hex, str], specials: dict[Hex, str]) -> dict[Hex, str]:
    names, used = {}, set()
    for h in sorted(regions):
        region, special = regions[h], specials.get(h)
        if special == "camp":
            name = "Camp"
        elif special == "final":
            name = "The Heartstone"
        elif special == "temple":
            name = f"{region.title()} Temple"
        else:
            for _ in range(50):
                first = rng.choice(NAME_FIRST[region])
                name = f"{first}{rng.choice(TOWN_ENDINGS)}" if special == "town" else f"{first} {rng.choice(NAME_LAST[biomes[h]])}"
                if name not in used:
                    break
            else:
                name = f"{name} {len(used)}"
        used.add(name)
        names[h] = name
    return names


# --- the story: quests, shortcuts, gates -----------------------------------------


def _steps(edges: dict, start: Hex, extra: tuple[Hex, Hex] | None = None) -> dict[Hex, int]:
    """Walking steps from start over open edges (and one extra edge)."""
    nbrs: dict[Hex, list[Hex]] = {}
    for (a, b), kind in edges.items():
        if kind == "open" or (a, b) == extra:
            nbrs.setdefault(a, []).append(b)
            nbrs.setdefault(b, []).append(a)
    dist, todo = {start: 0}, [start]
    for h in todo:
        for n in nbrs.get(h, []):
            if n not in dist:
                dist[n] = dist[h] + 1
                todo.append(n)
    return dist


def _path(edges: dict, start: Hex, goal: Hex) -> list[Hex]:
    dist = _steps(edges, goal)
    path = [start]
    while path[-1] != goal:
        h = path[-1]
        path.append(min((n for n in hx.neighbors(h) if edges.get(hx.edge_key(h, n)) == "open" and n in dist), key=lambda n: (dist[n], n)))
    return path


def gate_needs(world: World, start: Hex, shortcuts_open: bool) -> dict[Hex, list[dict[str, int]]]:
    """What it takes to reach each big hex from start: the type levels a
    party needs for the gates on the way. Different ways can need different types, so each hex gets
    every need that no other way beats on all types (cheapest first);
    {} means free. Broken shortcuts are open or shut by shortcuts_open."""
    best: dict[Hex, list[tuple[int, ...]]] = {start: [(0,) * len(REGIONS)]}
    todo = [(start, best[start][0])]
    while todo:
        h, need = todo.pop()
        if need not in best.get(h, []):
            continue  # beaten since it was queued
        for n in world.exits(h):
            gate = world.gates.get(hx.edge_key(h, n))
            nxt = need
            if gate and gate.kind == "quest":
                if not shortcuts_open:
                    continue
                for t in gate.types:  # the quest checks the 3 on each side
                    i = REGIONS.index(t)
                    nxt = nxt[:i] + (max(nxt[i], gate.level),) + nxt[i + 1:]
            elif gate:
                i = REGIONS.index(gate.kind)
                nxt = need[:i] + (max(need[i], gate.level),) + need[i + 1:]
            have = best.get(n, [])
            if any(all(a <= b for a, b in zip(o, nxt)) for o in have):
                continue
            best[n] = [o for o in have if not all(a <= b for a, b in zip(nxt, o))] + [nxt]
            todo.append((n, nxt))
    return {h: [{t: v for t, v in zip(REGIONS, need) if v} for need in sorted(needs, key=lambda x: (sum(x), x))]
            for h, needs in best.items()}


def distances_from(world: World, start: Hex, passable=None) -> dict[Hex, int]:
    """Walking steps from start to every reachable hex (open edges only;
    `passable(edge_key, gate)` can rule out gated ones)."""
    dist, todo = {start: 0}, [start]
    for h in todo:
        for n in world.exits(h):
            key = hx.edge_key(h, n)
            if passable and key in world.gates and not passable(key, world.gates[key]):
                continue
            if n not in dist:
                dist[n] = dist[h] + 1
                todo.append(n)
    return dist


def hex_json(b: BigHex) -> dict:
    return {"q": b.coord[0], "r": b.coord[1], "region": b.region, "ring": b.ring, "biome": b.biome, "name": b.name, "special": b.special}


def edge_json(key: tuple[Hex, Hex], kind: str, gate: Gate | None = None) -> dict:
    out = {"a": list(key[0]), "b": list(key[1]), "kind": kind}
    if gate:
        out["gate"] = {"kind": gate.kind, "level": gate.level, "region": gate.region, "types": list(gate.types)}
    return out


def quest_json(q: Quest) -> dict:
    return {"region": q.region, "town": list(q.town), "shortcut": [list(q.shortcut[0]), list(q.shortcut[1])],
            "pocket": [list(h) for h in q.pocket]}


def to_json(world: World) -> dict:
    """The whole world, fog and all (the lab's view)."""
    return {
        "seed": world.seed,
        "version": WORLD_VERSION,
        "radius": MAP_RADIUS,
        "hexes": [hex_json(b) for b in world.hexes.values()],
        "edges": [edge_json(k, v, world.gates.get(k)) for k, v in world.edges.items()],
        "quests": [quest_json(q) for q in world.quests.values()],
        "rerolls": list(world.rerolls),
    }
