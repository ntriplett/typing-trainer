"""Wanderpaw's small maps: what's inside each big hex (PLAN.md 11n).

Each big hex opens into a hexagon of small hexes, LOCAL_RADIUS on a side
(91 hexes), built from the world seed and the big hex's place, so it's the
same every time. Directions match the big map: the outer ring splits into
six zones of five hexes, each centered on the corner hex pointing at that
big-map neighbor. An open big edge puts 1-3 exit hexes in its zone (both
sides of the edge agree where: the zone on the far side is the mirror
image), the only places you can leave by; a walled edge fills its zone
with that wall (river -> water, cliff, thicket -> trees, rocks), and the
edge of the world is water.

Inside, the biome's STYLE sets the feel: open fields with clumps of
bushes, orchards in rows, patchy or deep forest, canyon or mountain cliff
bands, a river, ponds, a lake, or islands. Then trails wiggle from every
exit and special place to the campfire (windier in forests and cliffs),
crossing water on bridges and fords, and anything left cut off is joined
up or filled in, so every walkable hex can be reached.

Special big hexes: Camp is a cleared camp in the middle (its campfire is
Camp itself); a town fills about a quarter of its hex (a plaza, buildings,
the campfire in the square); a temple stands toward the edge of the world;
the Heartstone stands in the middle.
"""

from __future__ import annotations

import heapq
import random
from dataclasses import dataclass
from functools import lru_cache

from app.wanderpaw import hexes as hx
from app.wanderpaw import world as wd
from app.wanderpaw.hexes import Hex

LOCAL_RADIUS = 5
CELLS: tuple[Hex, ...] = tuple(hx.spiral((0, 0), LOCAL_RADIUS))
INDEX = {h: i for i, h in enumerate(CELLS)}
CELL_SET = frozenset(CELLS)
OUTER: tuple[Hex, ...] = tuple(hx.ring((0, 0), LOCAL_RADIUS))
ZONE_HALF = 2  # a zone is the corner hex and two either side

WALKABLE = frozenset({"grass", "flowers", "path", "sand", "plaza", "bridge", "ford", "building", "campfire", "camp", "temple", "stone"})
BLOCKED = frozenset({"tree", "bush", "rock", "cliff", "water"})
WALL_TILES = {"river": "water", "cliff": "cliff", "thicket": "tree", "rocks": "rock"}
EDGE_OF_WORLD = "water"
# What a trail turns a blocker into when it has to go through one.
CROSSING = {"water": "bridge", "tree": "path", "bush": "path", "rock": "path", "cliff": "path"}


@dataclass(frozen=True, slots=True)
class Style:
    name: str
    obstacle: str  # what fills cut-off pockets
    windy: float  # how much trails wander
    exit_width: int  # exits per open side (1 narrow .. 3 wide open)


STYLES = {
    "open": Style("open", "bush", 0.6, 3),
    "orchard": Style("orchard", "tree", 0.4, 3),
    "forest": Style("forest", "tree", 2.5, 2),
    "deep_forest": Style("deep_forest", "tree", 4.0, 1),
    "canyon": Style("canyon", "cliff", 2.0, 2),
    "mountain": Style("mountain", "cliff", 3.5, 1),
    "river": Style("river", "bush", 1.0, 2),
    "ponds": Style("ponds", "water", 1.5, 2),
    "lake": Style("lake", "water", 1.0, 2),
    "isles": Style("isles", "water", 2.0, 1),
}
BIOME_STYLES = {
    "fields": "open", "orchard": "orchard",
    "meadow": "open", "woods": "forest", "fern_hollow": "deep_forest", "deepwood": "deep_forest",
    "brookside": "river", "marsh": "ponds", "lakeshore": "lake", "isles": "isles",
    "heath": "open", "red_rocks": "canyon", "hot_springs": "ponds", "ember_peaks": "mountain",
    "windy_hills": "open", "mesa": "canyon", "ridge": "mountain", "storm_peaks": "mountain",
    "glade": "open", "mushroom_grove": "deep_forest", "mist_vale": "open", "crystal_hollow": "mountain",
}
# The scattered blocker in open land, by biome.
OPEN_OBSTACLE = {"heath": "rock", "windy_hills": "rock", "mist_vale": "rock", "glade": "tree"}


@dataclass(frozen=True, slots=True)
class LocalMap:
    big: Hex
    biome: str
    style: str
    tiles: dict[Hex, str]
    exits: dict[Hex, int]  # exit hex -> big-map direction it leads
    campfire: Hex
    buildings: tuple[Hex, ...] = ()

    def walkable(self, h: Hex) -> bool:
        return self.tiles.get(h) in WALKABLE


def zone(d: int) -> list[Hex]:
    """The five outer hexes facing big-map direction d, in ring order."""
    corner = (hx.DIRECTIONS[d][0] * LOCAL_RADIUS, hx.DIRECTIONS[d][1] * LOCAL_RADIUS)
    i = OUTER.index(corner)
    return [OUTER[(i + k) % len(OUTER)] for k in range(-ZONE_HALF, ZONE_HALF + 1)]


def mirror(h: Hex, d: int) -> Hex:
    """Where you come out in the neighbor (direction d) after leaving
    through outer hex h: the matching spot of the opposite zone."""
    return zone((d + 3) % 6)[2 * ZONE_HALF - zone(d).index(h)]


def exit_slots(seed: int, a: Hex, b: Hex, width: int) -> list[int]:
    """Positions (0..4 in big hex a's zone toward b) of the exits on the
    edge a-b. Seeded by the edge so both sides agree."""
    lo, hi = hx.edge_key(a, b)
    rng = random.Random(f"wanderpaw-exit:{wd.WORLD_VERSION}:{seed}:{lo}:{hi}")
    start = rng.randint(0, 2 * ZONE_HALF + 1 - width)
    slots = list(range(start, start + width))
    # The slots are picked from the lower hex's side; the other side mirrors them.
    return slots if a == lo else [2 * ZONE_HALF - s for s in slots]


@lru_cache(maxsize=256)
def generate(seed: int, big: Hex) -> LocalMap:
    world = wd.generate(seed)
    here = world.hexes[big]
    style = STYLES[BIOME_STYLES[here.biome]]
    rng = random.Random(f"wanderpaw-local:{wd.WORLD_VERSION}:{seed}:{big[0]}:{big[1]}")
    tiles = {h: "grass" for h in CELLS}
    _paint_style(rng, tiles, style.name, here.biome)

    locked: set[Hex] = set()  # tiles trails may not change
    exits: dict[Hex, int] = {}
    for d in range(6):
        n = hx.neighbor(big, d)
        cells = zone(d)
        if n in world.hexes and world.is_open(big, n):
            # Beside the exits it's just land: you can only leave by an exit.
            width = min(style.exit_width, STYLES[BIOME_STYLES[world.hexes[n].biome]].exit_width)
            for slot in exit_slots(seed, big, n, width):
                exits[cells[slot]] = d
                tiles[cells[slot]] = "path"
                locked.add(cells[slot])
            continue
        wall = WALL_TILES[world.edges[hx.edge_key(big, n)]] if n in world.hexes else EDGE_OF_WORLD
        for h in cells:
            tiles[h] = wall
            locked.add(h)

    campfire, buildings, landmarks = _place_specials(rng, tiles, locked, here, world, big)
    tiles[campfire] = "camp" if here.special == "camp" else "campfire"
    locked.add(campfire)

    noise = {h: rng.random() for h in CELLS}
    # One trail per open side (from its middle exit) that you can see; the
    # other exits and the landmarks just get a way through.
    sides: dict[int, list[Hex]] = {}
    for h in sorted(exits, key=lambda x: zone(exits[x]).index(x)):
        sides.setdefault(exits[h], []).append(h)
    for d in sorted(sides):
        middle = sides[d][len(sides[d]) // 2]
        _carve(tiles, locked, noise, style, middle, campfire, trail=True)
    for start in sorted(exits) + landmarks:
        _carve(tiles, locked, noise, style, start, campfire)
    _join_or_fill(tiles, locked, noise, style, campfire)
    return LocalMap(big, here.biome, style.name, tiles, exits, campfire, tuple(buildings))


# --- terrain by style ------------------------------------------------------------


def _clumps(rng: random.Random, share: float, smooth: int = 2) -> set[Hex]:
    """Clumpy random cells, exactly `share` of the map: random noise,
    blurred with its neighbors, then the highest cells."""
    field = {h: rng.random() for h in CELLS}
    for _ in range(smooth):
        field = {
            h: (field[h] + sum(field[n] for n in hx.neighbors(h) if n in field)) / (1 + sum(n in field for n in hx.neighbors(h)))
            for h in CELLS
        }
    ranked = sorted(CELLS, key=lambda h: (-field[h], h))
    return set(ranked[: round(share * len(CELLS))])


def _blob(rng: random.Random, center: Hex, radius: int, ragged: float = 0.35) -> set[Hex]:
    return {h for h in CELLS if hx.distance(h, center) <= radius - (rng.random() < ragged)}


def _band(rng: random.Random, length: int) -> list[Hex]:
    """A wandering line (a cliff band or a river), drifting in one direction."""
    h = rng.choice(CELLS)
    d = rng.randrange(6)
    out = [h]
    for _ in range(length - 1):
        d = (d + rng.choice((-1, 0, 0, 0, 1))) % 6
        h = hx.neighbor(h, d)
        if h not in CELL_SET:
            break
        out.append(h)
    return out


def _paint_style(rng: random.Random, tiles: dict[Hex, str], style: str, biome: str) -> None:
    if style == "open":
        obstacle = OPEN_OBSTACLE.get(biome, "bush")
        for h in _clumps(rng, 0.16):
            tiles[h] = obstacle
        for h in CELLS:
            if tiles[h] == "grass" and rng.random() < 0.12:
                tiles[h] = "flowers"
    elif style == "orchard":
        lean = rng.randrange(2)
        for q, r in CELLS:
            if r % 2 == 0 and (q + lean) % 2 == 0 and rng.random() < 0.85:
                tiles[(q, r)] = "tree"
    elif style in ("forest", "deep_forest"):
        for h in _clumps(rng, 0.34 if style == "forest" else 0.44):
            tiles[h] = "tree"
        for h in CELLS:
            if tiles[h] == "grass" and rng.random() < 0.1:
                tiles[h] = "bush"
    elif style in ("canyon", "mountain"):
        bands, length = (4, 7) if style == "canyon" else (5, 8)
        for _ in range(bands):
            for h in _band(rng, rng.randint(length - 2, length + 2)):
                tiles[h] = "cliff"
        for h in _clumps(rng, 0.12 if style == "canyon" else 0.18):
            if tiles[h] == "grass":
                tiles[h] = "rock"
        if style == "canyon":
            for h in CELLS:
                if tiles[h] == "grass" and rng.random() < 0.3:
                    tiles[h] = "sand"
    elif style == "river":
        d = rng.randrange(3)
        h = (-hx.DIRECTIONS[d][0] * LOCAL_RADIUS, -hx.DIRECTIONS[d][1] * LOCAL_RADIUS)
        while h in CELL_SET:
            tiles[h] = "water"
            h = hx.neighbor(h, (d + rng.choice((-1, 0, 0, 1))) % 6)
        for h in _clumps(rng, 0.14):
            if tiles[h] == "grass":
                tiles[h] = "bush"
    elif style == "ponds":
        for _ in range(rng.randint(5, 8)):
            for h in _blob(rng, rng.choice(CELLS), rng.randint(0, 1)):
                tiles[h] = "water"
        for h in _clumps(rng, 0.14):
            if tiles[h] == "grass":
                tiles[h] = "bush" if biome == "marsh" else "rock"
    elif style == "lake":
        d = rng.randrange(6)
        center = (hx.DIRECTIONS[d][0] * 3, hx.DIRECTIONS[d][1] * 3)
        lake = _blob(rng, center, 3)
        for h in lake:
            tiles[h] = "water"
        for h in CELLS:
            if tiles[h] == "grass" and any(n in lake for n in hx.neighbors(h)):
                tiles[h] = "sand"
    elif style == "isles":
        land = _clumps(rng, 0.55, 1)
        for h in CELLS:
            if h not in land:
                tiles[h] = "water"
            elif any(n not in land for n in hx.neighbors(h) if n in CELL_SET) and rng.random() < 0.5:
                tiles[h] = "sand"


# --- specials -------------------------------------------------------------------


def _clear(tiles: dict[Hex, str], locked: set[Hex], cells, kind: str) -> None:
    for h in cells:
        if h in CELL_SET and h not in locked:
            tiles[h] = kind


def _place_specials(rng, tiles, locked, here: wd.BigHex, world: wd.World, big: Hex) -> tuple[Hex, list[Hex], list[Hex]]:
    """(campfire, building hexes, landmarks the trails must reach)."""
    inner = [h for h in CELLS if hx.distance(h, (0, 0)) <= LOCAL_RADIUS - 2]
    if here.special == "camp":
        _clear(tiles, locked, hx.spiral((0, 0), 1), "plaza")
        return (0, 0), [], []
    if here.special == "town":
        town = rng.choice(hx.ring((0, 0), 2))
        _clear(tiles, locked, hx.spiral(town, 2), "plaza")
        spots = [h for h in hx.ring(town, 1) + hx.ring(town, 2) if h in CELL_SET and h not in locked]
        rng.shuffle(spots)
        buildings = sorted(spots[: rng.randint(5, 7)])
        for h in buildings:
            tiles[h] = "building"
            locked.add(h)
        locked.add(town)
        return town, buildings, buildings
    if here.special in ("temple", "final"):
        if here.special == "temple":
            outward = [d for d in range(6) if hx.neighbor(big, d) not in world.hexes]
            d = rng.choice(outward)
            spot = (hx.DIRECTIONS[d][0] * 3, hx.DIRECTIONS[d][1] * 3)
        else:
            spot = (0, 0)
        _clear(tiles, locked, hx.spiral(spot, 1), "plaza")
        tiles[spot] = "temple" if here.special == "temple" else "stone"
        locked.add(spot)
        fires = [h for h in inner if hx.distance(h, spot) >= 2 and hx.distance(h, (0, 0)) <= 3]
        campfire = rng.choice(fires)
        _clear(tiles, locked, hx.ring(campfire, 1), "grass")
        return campfire, [], [spot]
    campfire = rng.choice([h for h in CELLS if hx.distance(h, (0, 0)) <= 2])
    _clear(tiles, locked, hx.ring(campfire, 1), "grass")
    return campfire, [], []


# --- trails and joining up -------------------------------------------------------


def _cost(tiles, noise, style: Style, h: Hex) -> float:
    """Trails like to follow trails (so they merge), go round blockers if
    they can, and wander with the noise."""
    base = 0.4 if tiles[h] in ("path", "bridge", "ford") else 1.0 if tiles[h] in WALKABLE else 6.0
    return base + noise[h] * style.windy


def _carve(tiles, locked, noise, style: Style, start: Hex, goal: Hex, trail: bool = False) -> None:
    """A way from start to goal: cheapest way through, where blockers cost
    more and noise makes it wander. Blockers on it become crossings; a
    `trail` also turns the open ground it crosses into path."""
    best = {start: 0.0}
    came: dict[Hex, Hex] = {}
    todo = [(0.0, start)]
    while todo:
        cost, h = heapq.heappop(todo)
        if h == goal:
            break
        if cost > best[h]:
            continue
        for n in hx.neighbors(h):
            if n not in CELL_SET or (n in locked and n != goal):
                continue
            c = cost + _cost(tiles, noise, style, n)
            if c < best.get(n, float("inf")):
                best[n] = c
                came[n] = h
                heapq.heappush(todo, (c, n))
    if goal not in came and goal != start:
        return
    h = goal
    while h != start:
        h = came[h]
        if h in locked:
            continue
        if tiles[h] == "water" and style.name == "ponds":
            tiles[h] = "ford"
        elif tiles[h] in BLOCKED:
            tiles[h] = CROSSING[tiles[h]]
        elif trail and tiles[h] in ("grass", "flowers", "sand"):
            tiles[h] = "path"


def reachable(tiles: dict[Hex, str], start: Hex) -> set[Hex]:
    seen, todo = {start}, [start]
    while todo:
        for n in hx.neighbors(todo.pop()):
            if n in tiles and n not in seen and tiles[n] in WALKABLE:
                seen.add(n)
                todo.append(n)
    return seen


def _join_or_fill(tiles, locked, noise, style: Style, campfire: Hex) -> None:
    """Pockets cut off from the campfire: big ones get a trail, small ones fill in."""
    while True:
        main = reachable(tiles, campfire)
        cut_off = [h for h in CELLS if tiles[h] in WALKABLE and h not in main]
        if not cut_off:
            return
        pocket = reachable(tiles, cut_off[0])
        if len(pocket) >= 2:
            _carve(tiles, locked, noise, style, min(pocket), campfire)
            if min(pocket) in reachable(tiles, campfire):
                continue
        for h in pocket:
            tiles[h] = style.obstacle


# --- JSON -----------------------------------------------------------------------


def tile_json(local: LocalMap, h: Hex) -> dict:
    out = {"q": h[0], "r": h[1], "kind": local.tiles[h]}
    if h in local.exits:
        out["exit"] = local.exits[h]
    return out


def to_json(local: LocalMap) -> dict:
    """The whole small map, fog and all (the lab's view)."""
    walkable = sum(local.walkable(h) for h in CELLS)
    return {
        "big": list(local.big),
        "biome": local.biome,
        "style": local.style,
        "radius": LOCAL_RADIUS,
        "campfire": list(local.campfire),
        "tiles": [tile_json(local, h) for h in CELLS],
        "walkable": round(walkable / len(CELLS), 2),
    }
