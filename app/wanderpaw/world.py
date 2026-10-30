"""Wanderpaw's world, built from a seed (PLAN.md 11n).

The big map is a hexagon of MAP_RADIUS big hexes around Camp, its outer
ring trimmed ragged. The heartland (Camp's ring and Camp) belongs to no
type; the rest is five type regions, wedges in the order of the type ring
(REGIONS), each with its temple on the far edge of the map. Biomes deepen
with distance from Camp, and every hex gets a made-up name.

Edges: you can't walk any direction. Neighboring big hexes are either
joined ("open") or walled off by a river, cliff, thicket or rocks. The
open edges are a random spanning tree (so everything is reachable) plus a
few extra loops, built region by region: each region opens onto the
heartland in one place and onto its neighbors only rarely, so getting
somewhere means weaving around.

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

WORLD_VERSION = 1
MAP_RADIUS = 5
HEARTLAND_RADIUS = 1
TRIM_CHANCE = 0.35  # outer-ring hexes dropped for a ragged coast
REGION_JITTER = 9  # degrees: wobbles the wedge borders
MAZE_WINDING = 0.7  # how often the maze keeps digging from its newest hex
LOOP_CHANCE = 0.12  # extra open edges inside a region
MAZE_TRIES = 16  # mazes tried per region; the one whose temple walk is nearest TEMPLE_WALK wins
TEMPLE_WALK = 10  # big-hex steps from the region's gate to its temple
BORDER_LOOP_CHANCE = 0.06  # ... between two type regions
TOWNS_PER_REGION = (1, 2)

# The type ring, in order around the map (each beats the next two).
REGIONS = ("splash", "ember", "dream", "leaf", "shock")
HEARTLAND = "camp"

# region -> [(biome, nearest ring, farthest ring)]
BIOMES: dict[str, list[tuple[str, int, int]]] = {
    HEARTLAND: [("fields", 0, 1), ("orchard", 0, 1)],
    "leaf": [("meadow", 2, 3), ("woods", 2, 5), ("fern_hollow", 3, 5), ("deepwood", 4, 5)],
    "splash": [("brookside", 2, 3), ("marsh", 2, 5), ("lakeshore", 3, 5), ("isles", 4, 5)],
    "ember": [("heath", 2, 3), ("red_rocks", 2, 5), ("hot_springs", 3, 5), ("ember_peaks", 4, 5)],
    "shock": [("windy_hills", 2, 3), ("mesa", 2, 5), ("ridge", 3, 5), ("storm_peaks", 4, 5)],
    "dream": [("glade", 2, 3), ("mushroom_grove", 2, 5), ("mist_vale", 3, 5), ("crystal_hollow", 4, 5)],
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
class World:
    seed: int
    hexes: dict[Hex, BigHex]
    edges: dict[tuple[Hex, Hex], str]  # edge_key -> "open" or a wall kind

    def is_open(self, a: Hex, b: Hex) -> bool:
        return self.edges.get(hx.edge_key(a, b)) == "open"

    def exits(self, h: Hex) -> list[Hex]:
        """The neighbors you can walk to from h."""
        return [n for n in hx.neighbors(h) if self.is_open(h, n)]

    def temples(self) -> dict[str, Hex]:
        return {b.region: b.coord for b in self.hexes.values() if b.special == "temple"}


@lru_cache(maxsize=32)
def generate(seed: int) -> World:
    rng = random.Random(f"wanderpaw:{WORLD_VERSION}:{seed}")
    rotation = rng.uniform(0, 360)
    regions = _assign_regions(rng, rotation)
    temples = _pick_temples(regions, rotation)
    coords = _trim(rng, regions, set(temples.values()))
    regions = {h: regions[h] for h in coords}
    _make_contiguous(regions, keep=set(temples.values()))
    biomes = _assign_biomes(rng, regions)
    specials = _place_specials(rng, regions, temples)
    edges = _build_edges(rng, regions, biomes, temples)
    names = _name_hexes(rng, regions, biomes, specials)
    big = {
        h: BigHex(h, regions[h], hx.distance(h, (0, 0)), biomes[h], names[h], specials.get(h))
        for h in sorted(coords)
    }
    return World(seed, big, edges)


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


def _pick_temples(regions: dict[Hex, str], rotation: float) -> dict[str, Hex]:
    """Each region's temple: the outer-ring hex nearest the middle of its wedge."""
    temples = {}
    width = 360 / len(REGIONS)
    for i, region in enumerate(REGIONS):
        middle = (rotation + (i + 0.5) * width) % 360
        outer = [h for h in hx.ring((0, 0), MAP_RADIUS) if regions[h] == region]
        temples[region] = min(outer, key=lambda h: (_angle_gap(hx.angle(h), middle), h))
    return temples


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


def _place_specials(rng: random.Random, regions: dict[Hex, str], temples: dict[str, Hex]) -> dict[Hex, str]:
    specials = {(0, 0): "camp", rng.choice(hx.ring((0, 0), 1)): "final"}
    specials.update({h: "temple" for h in temples.values()})
    for region in REGIONS:
        for ring in (3, 4)[: rng.randint(*TOWNS_PER_REGION)]:
            spots = [
                h for h in sorted(regions)
                if regions[h] == region and hx.distance(h, (0, 0)) == ring
                and not any(n in specials for n in [h, *hx.neighbors(h)])
            ]
            if spots:
                specials[rng.choice(spots)] = "town"
    return specials


def _build_edges(rng: random.Random, regions: dict[Hex, str], biomes: dict[Hex, str], temples: dict[str, Hex]) -> dict[tuple[Hex, Hex], str]:
    pairs = sorted({hx.edge_key(h, n) for h in regions for n in hx.neighbors(h) if n in regions})
    open_ = {(a, b) for a, b in pairs if regions[a] == regions[b] == HEARTLAND}
    for region in REGIONS:
        cells = {h for h, r in regions.items() if r == region}
        inner = [(a, b) for a, b in pairs if a in cells and b in cells]
        gate = rng.choice([(a, b) for a, b in pairs if {regions[a], regions[b]} == {HEARTLAND, region}])
        inside = next(h for h in gate if h in cells)
        tries = []
        for _ in range(MAZE_TRIES):
            maze = _maze(rng, inside, cells)
            maze |= {e for e in inner if e not in maze and rng.random() < LOOP_CHANCE}
            tries.append((abs(_walk(maze, inside, temples[region]) - TEMPLE_WALK), maze))
        open_ |= {gate, *min(tries, key=lambda t: t[0])[1]}
    # Rare crossings between neighboring regions.
    for a, b in pairs:
        if regions[a] != regions[b] and HEARTLAND not in (regions[a], regions[b]) and rng.random() < BORDER_LOOP_CHANCE:
            open_.add((a, b))
    return {e: "open" if e in open_ else _wall(biomes[e[0]], biomes[e[1]]) for e in pairs}


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


def distances_from(world: World, start: Hex) -> dict[Hex, int]:
    """Walking steps from start to every reachable hex (open edges only)."""
    dist, todo = {start: 0}, [start]
    for h in todo:
        for n in world.exits(h):
            if n not in dist:
                dist[n] = dist[h] + 1
                todo.append(n)
    return dist


def hex_json(b: BigHex) -> dict:
    return {"q": b.coord[0], "r": b.coord[1], "region": b.region, "ring": b.ring, "biome": b.biome, "name": b.name, "special": b.special}


def edge_json(key: tuple[Hex, Hex], kind: str) -> dict:
    return {"a": list(key[0]), "b": list(key[1]), "kind": kind}


def to_json(world: World) -> dict:
    """The whole world, fog and all (the lab's view)."""
    return {
        "seed": world.seed,
        "version": WORLD_VERSION,
        "radius": MAP_RADIUS,
        "hexes": [hex_json(b) for b in world.hexes.values()],
        "edges": [edge_json(k, v) for k, v in world.edges.items()],
    }
