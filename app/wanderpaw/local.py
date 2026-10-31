"""Wanderpaw's small maps: what's inside each big hex (PLAN.md 11n).

Each big hex is a hexagon of small hexes, LOCAL_RADIUS from its middle
(91 hexes), built from the world seed and the big hex's place, so it's the
same every time. The hexagons tile one seamless world grid: big hex b's
middle is world hex center(b), and its six neighbors sit at SPANS (a
little turned from the small grid, so the big map is drawn turned to
match). Small hex h of big hex b is world hex to_world(b, h); owner()
goes back.

Along an open big edge you can cross wherever both sides are walkable;
1-3 exits (a pair of facing hexes, the same on both sides) are where the
trails meet, so there's always a way. A walled edge is one hex thick, on
one side or the other (picked per edge): that side fills its edge with
the wall (river -> water, cliff, thicket -> trees, rocks). A gated edge
is the same, with the gate in the wall. The edge of the world is ocean.

Inside, the biome's STYLE sets the feel: open fields with clumps of
bushes, orchards in rows, patchy or deep forest, canyon or mountain cliff
bands, a river, ponds, a lake, or islands. Big open stretches get broken
up by short spines of the style's blocker (TWISTS), so the land is twisty
with bottlenecks. Then trails wiggle from every exit and special place to
the campfire (windier in forests and cliffs), crossing water on bridges
and fords; a few trails fork and rejoin around something (FORKS), so you
can pick your way; anything left cut off is joined up or filled in, so
every walkable hex can be reached; and a few short one-wide spurs dig
into the blockers to dead ends (SPURS), where a treat waits.

Nooks: little things to find, on top of the land (their own random
stream, like the places of interest). Caves sit in cliffs and rock with
one way in (a deep one needs Ember levels to light the way); tunnels go
through a cliff between two far-apart sides; glades sit inside solid
woods with one way in (an overgrown one needs Leaf); fishing and dive
spots sit on the shore; and every dead end gets a treat at the end
(TREATS: a buried chest, a lookout, a spring, a rune stone, ...). Each
holds a few finds (FINDS). A clue points to a buried cache somewhere
nearby (clue_target). `need` is (type, levels): the party's total levels
of that type it takes.

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

WALKABLE = frozenset({"grass", "flowers", "path", "sand", "plaza", "bridge", "ford", "building", "campfire", "camp", "temple", "stone"})
BLOCKED = frozenset({"tree", "bush", "rock", "cliff", "water", "ocean"})
WALL_TILES = {"river": "water", "cliff": "cliff", "thicket": "tree", "rocks": "rock"}
# What stands in a gated exit until it's cleared (by a field skill, or for
# "quest", by finishing the region's story quest). Blocked until then.
GATE_TILES = {"ember": "dark", "splash": "flames", "leaf": "gap", "shock": "old_gate", "dream": "guardian", "quest": "broken_bridge"}
CLEARED_TILES = {"gap": "bridge", "broken_bridge": "bridge"}  # else path
POI_KINDS = ("forage", "chest", "shrine", "lost")
# Town buildings: the region's quest town has the elder.
BUILDING_ROLES = ("board", "inn", "shop")
FORAGE_SPOTS = (1, 3)
CHEST_CHANCE = (0.15, 0.07)  # + per ring from Camp
SHRINE_CHANCE = 0.12
EDGE_OF_WORLD = "ocean"
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
# Spines of blocker dropped into big open stretches, and trails that split
# and rejoin, per style.
TWISTS = {"open": 5, "orchard": 1, "forest": 4, "deep_forest": 2, "canyon": 5, "mountain": 4,
          "river": 6, "ponds": 4, "lake": 5, "isles": 2}
FORKS = {"open": 2, "orchard": 1, "forest": 2, "deep_forest": 2, "canyon": 2, "mountain": 2,
         "river": 2, "ponds": 2, "lake": 2, "isles": 1}
OPEN_AROUND = 0.85  # a hex this walkable within 2 steps is "big open"
SPURS = (1, 3)  # one-wide dead ends dug into the blockers (each gets a treat)

# --- nooks ---
# What each kind of nook can hold (one set picked). coins: once ever;
# forage, energy, fish: once a day; clue: once, marks a cache; view: shows
# the land around; lore, tip, creature: just words (creatures fight later).
FINDS = {
    "cave": (("coins",), ("coins", "creature"), ("clue",), ("forage", "lore"), ("creature", "lore")),
    "tunnel": (("creature",),),
    "glade": (("forage", "energy"), ("coins",), ("clue",), ("lore", "forage")),
    "fishing": (("fish",),),
    "dive": (("coins",), ("clue",)),
    "buried": (("coins",),),
    "lookout": (("view",),),
    "spring": (("energy",),),
    "ruin": (("clue", "lore"), ("lore",)),
    "nest": (("forage",),),
    "berries": (("forage",),),
    "log": (("forage",), ("clue",)),
    "statue": (("lore",),),
    "traveler": (("tip",),),
    "well": (("energy",), ("coins",)),
    "rune": (("coins",), ("clue",)),
    "machine": (("coins",), ("view",)),
    "tangle": (("coins",), ("forage",)),
    "hole": (("coins",), ("clue",)),
    "ring": (("energy",), ("coins",)),
}
# Nooks that need a type's levels (caves only when deep, glades only when overgrown).
NOOK_SKILL = {"rune": "dream", "ring": "dream", "machine": "shock", "tangle": "leaf", "hole": "ember",
              "dive": "splash", "cave": "ember", "glade": "leaf"}
DEEP_CHANCE = 0.4  # a cave that's deep / a glade that's overgrown
# Dead-end treats: these anywhere, plus the region's own (twice as likely).
TREATS = ("buried", "lookout", "spring", "ruin", "nest", "berries", "log", "statue", "traveler", "well")
REGION_TREATS = {"ember": ("hole", "spring"), "splash": ("well", "nest"), "leaf": ("tangle", "berries"),
                 "dream": ("rune", "ring"), "shock": ("machine", "lookout"), "camp": ("berries", "traveler")}
GROUND = ("grass", "flowers", "path", "sand")  # where nooks on open ground go
IN_WALL = ("cave", "tunnel", "glade")  # nooks inside a blocker, gone into from their doors
CAVES = {"mountain": 1.5, "canyon": 1.2}  # caves per map (the fraction: a chance of one more)
GLADES = {"deep_forest": 1.5, "forest": 1.2, "orchard": 0.3}
OTHER_CAVE = 0.3  # a cave in any other land with cliffs or rocks
TUNNEL_CHANCE = 0.5  # in mountains and canyons
TUNNEL_DETOUR = 8  # a tunnel's sides must be at least this far apart walking round
FISHING = {"river": 1.5, "ponds": 1.5, "lake": 2, "isles": 2}
DIVE_CHANCE = 0.5  # in watery lands
MAX_DEAD_ENDS = 3


@dataclass(frozen=True, slots=True)
class Nook:
    kind: str  # FINDS' keys
    doors: tuple[Hex, ...]  # in a wall (IN_WALL): the hexes you go in from; else ()
    need: tuple[str, int] | None  # (type, levels) the party needs to get at the finds
    finds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalMap:
    big: Hex
    biome: str
    style: str
    tiles: dict[Hex, str]
    exits: dict[Hex, int]  # exit hex -> big-map direction it leads
    campfire: Hex
    buildings: dict[Hex, str]  # building hex -> its role (BUILDING_ROLES)
    gates: dict[Hex, tuple[Hex, Hex]]  # gate tile -> the big edge it guards
    pois: dict[Hex, str]  # places of interest on walkable hexes: POI_KINDS
    nooks: dict[Hex, Nook]

    def walkable(self, h: Hex) -> bool:
        return self.tiles.get(h) in WALKABLE


# --- the world grid -----------------------------------------------------------------

_R = LOCAL_RADIUS
# Where the middles of the big hexes east (0, 0)+(1, 0) and south-east
# (0, 0)+(0, 1) of big hex (0, 0) sit, in world hexes.
SPANS: tuple[Hex, Hex] = ((2 * _R + 1, -_R), (_R, _R + 1))
_AREA = len(CELLS)  # = the determinant of SPANS


def center(big: Hex) -> Hex:
    """The world hex at the middle of big hex `big`."""
    (aq, ar), (bq, br) = SPANS
    return (aq * big[0] + bq * big[1], ar * big[0] + br * big[1])


def to_world(big: Hex, h: Hex) -> Hex:
    return hx.add(center(big), h)


def owner(g: Hex) -> tuple[Hex, Hex]:
    """(big hex, small hex inside it) of world hex g."""
    (aq, ar), (bq, br) = SPANS
    fq = (br * g[0] - bq * g[1]) / _AREA
    fr = (-ar * g[0] + aq * g[1]) / _AREA
    guess = (round(fq), round(fr))
    for big in [guess, *hx.neighbors(guess)]:
        h = (g[0] - center(big)[0], g[1] - center(big)[1])
        if h in CELL_SET:
            return big, h
    raise AssertionError(g)  # the tiling covers everything


def _sides() -> dict[int, list[tuple[Hex, Hex]]]:
    """Per big direction d: the touching pairs (our hex, their hex) along
    that edge, in order along it."""
    out = {}
    for d in range(6):
        off = center(hx.DIRECTIONS[d])
        pairs = [(h, (n[0] - off[0], n[1] - off[1])) for h in OUTER for n in hx.neighbors(h)
                 if n not in CELL_SET and (n[0] - off[0], n[1] - off[1]) in CELL_SET]
        out[d] = sorted(pairs, key=lambda p: (OUTER.index(p[0]) - OUTER.index(_corner(d))) % len(OUTER))
    return out


def _corner(d: int) -> Hex:
    """An outer hex well before big direction d's side, to order it from."""
    a = (hx.angle(center(hx.DIRECTIONS[d])) - 60) % 360
    return min(OUTER, key=lambda h: (min(abs(hx.angle(h) - a), 360 - abs(hx.angle(h) - a)), h))


SIDES = _sides()
SIDE_CELLS = {d: list(dict.fromkeys(h for h, _ in pairs)) for d, pairs in SIDES.items()}
# Hexes on two sides at once (where three big hexes meet): never exits.
CORNERS = frozenset(h for d in range(6) for h in SIDE_CELLS[d] if h in SIDE_CELLS[(d + 1) % 6])


def exit_pairs(seed: int, a: Hex, b: Hex, width: int) -> list[tuple[Hex, Hex]]:
    """The exits on the edge a-b: pairs (hex in a, the hex it faces in b).
    Seeded by the edge so both sides agree."""
    lo, hi = hx.edge_key(a, b)
    rng = random.Random(f"wanderpaw-exit:{wd.WORLD_VERSION}:{seed}:{lo}:{hi}")
    d = hx.direction_to(lo, hi)
    pairs = [(h, f) for h, f in SIDES[d] if h not in CORNERS and f not in CORNERS]
    cells = list(dict.fromkeys(h for h, _ in pairs))
    start = rng.randint(0, len(cells) - width)
    chosen = [next(p for p in pairs if p[0] == h) for h in cells[start:start + width]]
    return chosen if a == lo else [(f, h) for h, f in chosen]


def wall_side(seed: int, a: Hex, b: Hex) -> Hex:
    """Which big hex holds the (one hex thick) wall or gate on edge a-b."""
    lo, hi = hx.edge_key(a, b)
    return lo if random.Random(f"wanderpaw-wall:{wd.WORLD_VERSION}:{seed}:{lo}:{hi}").random() < 0.5 else hi


def _border_blocker(style: Style, biome: str) -> str:
    if style.name == "open":
        return OPEN_OBSTACLE.get(biome, "bush")
    return style.obstacle


@lru_cache(maxsize=256)
def generate(seed: int, big: Hex) -> LocalMap:
    world = wd.generate(seed)
    here = world.hexes[big]
    style = STYLES[BIOME_STYLES[here.biome]]
    rng = random.Random(f"wanderpaw-local:{wd.WORLD_VERSION}:{seed}:{big[0]}:{big[1]}")
    tiles = {h: "grass" for h in CELLS}
    _paint_style(rng, tiles, style.name, here.biome)
    _twist(rng, tiles, _border_blocker(style, here.biome), TWISTS[style.name])

    locked: set[Hex] = set()  # tiles trails may not change
    exits: dict[Hex, int] = {}
    gates = {}
    # Walls go on last, so where an open side meets a walled one, the wall wins.
    for d in sorted(range(6), key=lambda d: not world.is_open(big, hx.neighbor(big, d))):
        n = hx.neighbor(big, d)
        key = hx.edge_key(big, n)
        mine = n not in world.hexes or wall_side(seed, big, n) == big
        if n in world.hexes and world.is_open(big, n):
            width = min(style.exit_width, STYLES[BIOME_STYLES[world.hexes[n].biome]].exit_width)
            gated = key in world.gates
            if gated:
                # A wall with the gate in it (on one side). Gates are placed
                # (and locked) before any trails, so nothing inside comes to
                # depend on walking through one.
                width = 1
                if mine:
                    for h in SIDE_CELLS[d]:
                        tiles[h] = _border_blocker(style, here.biome)
                        locked.add(h)
            for h, _ in exit_pairs(seed, big, n, width):
                exits[h] = d
                tiles[h] = GATE_TILES[world.gates[key].kind] if gated and mine else "path"
                locked.add(h)
                if gated and mine:
                    gates[h] = key
            continue
        if not mine:
            continue  # the wall is on their side
        wall = WALL_TILES[world.edges[key]] if n in world.hexes else EDGE_OF_WORLD
        for h in SIDE_CELLS[d]:
            tiles[h] = wall
            locked.add(h)

    campfire, buildings, landmarks = _place_specials(rng, tiles, locked, here, world, big)
    tiles[campfire] = "camp" if here.special == "camp" else "campfire"
    locked.add(campfire)

    noise = {h: rng.random() for h in CELLS}
    # One trail per open side (from its middle exit) that you can see; the
    # other exits and the landmarks just get a way through.
    sides: dict[int, list[Hex]] = {}
    for h in sorted(exits, key=lambda x: SIDE_CELLS[exits[x]].index(x)):
        sides.setdefault(exits[h], []).append(h)
    for d in sorted(sides):
        middle = sides[d][len(sides[d]) // 2]
        _carve(tiles, locked, noise, style, middle, campfire, trail=True)
    for start in sorted(exits) + landmarks:
        _carve(tiles, locked, noise, style, start, campfire)
    _fork(rng, tiles, locked, noise, style, FORKS[style.name])
    _join_or_fill(tiles, locked, noise, style, campfire)
    _spurs(rng, tiles, locked, campfire, SPURS)

    # Places of interest have their own random stream (the land stays put).
    story = random.Random(f"wanderpaw-poi:{wd.STORY_VERSION}:{seed}:{big[0]}:{big[1]}")
    roles = _building_roles(story, buildings, any(q.town == big for q in world.quests.values()))
    pois = _place_pois(story, tiles, exits, campfire, here, any(q.lost == big for q in world.quests.values()))
    nooks = _place_nooks(story, tiles, exits, campfire, here, style, pois, set(roles))
    return LocalMap(big, here.biome, style.name, tiles, exits, campfire, roles, gates, pois, nooks)


def _building_roles(rng: random.Random, buildings: list[Hex], quest_town: bool) -> dict[Hex, str]:
    roles = (["elder"] if quest_town else []) + list(BUILDING_ROLES)
    order = sorted(buildings)
    rng.shuffle(order)
    return {h: roles[i] if i < len(roles) else "house" for i, h in enumerate(order)}


def _place_pois(rng: random.Random, tiles, exits, campfire: Hex, here: wd.BigHex, lost: bool) -> dict[Hex, str]:
    """Forage spots, maybe a chest or a shrine, and the lost thing of a
    region's story, on open ground away from the campfire and exits."""
    ground = [h for h in CELLS if tiles[h] in ("grass", "flowers", "path", "sand")
              and h not in exits and hx.distance(h, campfire) >= 2]
    rng.shuffle(ground)
    pois: dict[Hex, str] = {}

    def put(kind: str, spots: list[Hex]) -> None:
        free = [h for h in spots if h not in pois and not any(n in pois for n in hx.neighbors(h))]
        if free:
            pois[free[0]] = kind

    if lost:  # as far from the campfire as it gets
        put("lost", sorted(ground, key=lambda h: (-hx.distance(h, campfire), h)))
    if here.special in ("camp", "town", "temple", "final"):
        return pois
    for _ in range(rng.randint(*FORAGE_SPOTS)):
        put("forage", ground)
    if rng.random() < CHEST_CHANCE[0] + CHEST_CHANCE[1] * here.ring:
        put("chest", sorted(ground, key=lambda h: (-hx.distance(h, campfire), rng.random())))
    if here.region != wd.HEARTLAND and rng.random() < SHRINE_CHANCE:
        put("shrine", ground)
    return pois


def _count(rng: random.Random, mean: float) -> int:
    return int(mean) + (rng.random() < mean - int(mean))


def _need(rng: random.Random, kind: str, ring: int) -> tuple[str, int]:
    """Levels go up the farther out you are: 1-2 near Camp, 8-10 at the edge."""
    return NOOK_SKILL[kind], max(1, min(10, 2 * ring - 1 + rng.randint(-1, 1)))


def _place_nooks(rng: random.Random, tiles, exits, campfire: Hex, here: wd.BigHex, style: Style,
                 pois: dict[Hex, str], buildings: set[Hex]) -> dict[Hex, Nook]:
    if here.special in ("camp", "final"):
        return {}
    main = reachable(tiles, campfire)
    nooks: dict[Hex, Nook] = {}
    taken = set(pois) | set(exits) | buildings | {campfire}

    def free(h: Hex) -> bool:  # open ground, with nothing else beside it
        return tiles[h] in GROUND and h not in taken and not any(n in taken for n in hx.neighbors(h))

    def put(h: Hex, kind: str, doors=(), deep: bool | None = None) -> None:
        need = None
        if kind in NOOK_SKILL and (deep is None or deep):
            need = _need(rng, kind, here.ring)
        nooks[h] = Nook(kind, tuple(sorted(doors)), need, rng.choice(FINDS[kind]))
        taken.add(h)
        taken.update(doors)

    def doors_of(h: Hex) -> list[Hex]:
        return [n for n in hx.neighbors(h) if n in main]

    def walled(h: Hex) -> int:  # neighbors that are blockers (or off the map)
        return sum(n not in CELL_SET or tiles[n] in BLOCKED for n in hx.neighbors(h))

    def pick(cells, n: int, kind: str, deep_chance: float | None = None) -> None:
        cells = sorted(cells)
        rng.shuffle(cells)
        for h in cells:
            if n <= 0:
                return
            doors = doors_of(h) if kind in IN_WALL else ()
            if h in taken or any(d in taken for d in doors) or (kind not in IN_WALL and not free(h)):
                continue
            put(h, kind, doors, None if deep_chance is None else rng.random() < deep_chance)
            n -= 1

    rocky = [h for h in CELLS if tiles[h] in ("cliff", "rock") and h not in exits]
    # caves: one way in, deep in the rock
    caves = [h for h in rocky if len(doors_of(h)) == 1 and walled(h) >= 4]
    want = _count(rng, CAVES[style.name]) if style.name in CAVES else int(rng.random() < OTHER_CAVE)
    pick(caves, want, "cave", DEEP_CHANCE)
    # tunnels: through a cliff, between two sides far apart the long way round
    if style.name in CAVES and rng.random() < TUNNEL_CHANCE:
        ends = []
        for h in rocky:
            doors = doors_of(h)
            if len(doors) == 2 and hx.distance(*doors) == 2 and _walk(tiles, doors[0], doors[1]) >= TUNNEL_DETOUR:
                ends.append(h)
        pick(ends, 1, "tunnel")
    # glades: one way into thick woods
    woods = [h for h in CELLS if tiles[h] == "tree" and len(doors_of(h)) == 1
             and sum(tiles.get(n) == "tree" for n in hx.neighbors(h)) >= 3]
    pick(woods, _count(rng, GLADES.get(style.name, 0.1)), "glade", DEEP_CHANCE)
    # the shore
    shore = [h for h in main if any(tiles.get(n) in ("water", "ocean") for n in hx.neighbors(h))]
    wet = style.name in FISHING
    pick(shore, _count(rng, FISHING[style.name]) if wet else int(rng.random() < 0.4), "fishing")
    if wet and rng.random() < DIVE_CHANCE:
        pick([h for h in shore if sum(tiles.get(n) == "water" for n in hx.neighbors(h)) >= 3], 1, "dive")
    # a treat at the end of every dead end (a few)
    if here.special is None:
        def tucked(h: Hex) -> bool:  # a dead end, or a corner whose two ways in touch
            ways = [n for n in hx.neighbors(h) if n in main]
            return len(ways) == 1 or (len(ways) == 2 and hx.distance(*ways) == 1)

        ends = [h for h in main if tucked(h) and hx.distance(h, (0, 0)) < LOCAL_RADIUS]
        treats = TREATS + REGION_TREATS.get(here.region, ()) * 2
        ends.sort(key=lambda h: (sum(n in main for n in hx.neighbors(h)), -hx.distance(h, campfire), h))
        for h in ends[:MAX_DEAD_ENDS]:
            if free(h):
                put(h, rng.choice(treats))
        # and one out in the open, sometimes
        if rng.random() < 0.5:
            pick([h for h in main if tiles[h] in ("grass", "flowers", "sand")], 1, rng.choice(treats))
    return nooks


def _walk(tiles, a: Hex, b: Hex) -> int:
    """Steps from a to b over walkable hexes (999: no way)."""
    dist, todo = {a: 0}, [a]
    for h in todo:
        if h == b:
            return dist[h]
        for n in hx.neighbors(h):
            if n in tiles and n not in dist and tiles[n] in WALKABLE:
                dist[n] = dist[h] + 1
                todo.append(n)
    return 999


def clue_target(seed: int, big: Hex, h: Hex) -> tuple[Hex, Hex]:
    """Where the clue at (big, h) points: a buried cache on open ground in
    a big hex up to two steps away, far from its campfire."""
    world = wd.generate(seed)
    rng = random.Random(f"wanderpaw-clue:{wd.STORY_VERSION}:{seed}:{big}:{h}")
    near = sorted(b for b in world.hexes if 0 < hx.distance(b, big) <= 2
                  and world.hexes[b].special not in ("camp", "final"))
    far = rng.choice(near or [big])
    m = generate(seed, far)
    taken = set(m.pois) | set(m.nooks) | set(m.exits) | set(m.buildings) | {m.campfire}
    ground = sorted(c for c in reachable(m.tiles, m.campfire) if c not in taken and m.tiles[c] in ("grass", "flowers", "sand"))
    ground.sort(key=lambda c: -hx.distance(c, m.campfire))
    return far, rng.choice(ground[: max(1, len(ground) // 3)])


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
        for h in _clumps(rng, 0.13):
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
        for h in _clumps(rng, 0.31 if style == "forest" else 0.41):
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


def _twist(rng: random.Random, tiles: dict[Hex, str], blocker: str, spines: int) -> None:
    """Break up big open stretches: short wandering spines of blocker,
    dropped where it's most open, so ways get twisty and pinch."""
    for _ in range(spines):
        def openness(h: Hex) -> float:
            around = [n for n in hx.spiral(h, 2) if n in CELL_SET]
            return sum(tiles[n] in WALKABLE for n in around) / len(around)
        wide = [h for h in CELLS if tiles[h] in WALKABLE and openness(h) >= OPEN_AROUND]
        if not wide:
            return
        h = rng.choice(wide)
        d = rng.randrange(6)
        for _ in range(rng.randint(2, 4)):
            if h not in CELL_SET:
                break
            tiles[h] = blocker
            d = (d + rng.choice((-1, 0, 1))) % 6
            h = hx.neighbor(h, d)


def _fork(rng: random.Random, tiles, locked, noise, style: Style, forks: int) -> None:
    """Trails that split and rejoin: pick two trail hexes a few steps
    apart and make a second way between them that doesn't use the first."""
    trail = sorted(h for h in CELLS if tiles[h] == "path" and h not in locked)
    for _ in range(forks):
        if not trail:
            return
        a = rng.choice(trail)
        # walk the trail a few steps out from a
        dist, todo = {a: 0}, [a]
        for h in todo:
            for n in hx.neighbors(h):
                if n in CELL_SET and n not in dist and tiles[n] in ("path", "bridge", "ford"):
                    dist[n] = dist[h] + 1
                    todo.append(n)
        far = [h for h, k in dist.items() if 4 <= k <= 6]
        if not far:
            continue
        b = rng.choice(sorted(far))
        middle = {h for h, k in dist.items() if 0 < k < dist[b] and hx.distance(h, a) < hx.distance(a, b) + 1}
        route = _carve(tiles, locked | middle, noise, style, a, b, trail=True, through=False)
        if route:
            trail = sorted(set(trail) | set(route))


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
            toward = hx.angle(center(hx.DIRECTIONS[rng.choice(outward)]))
            spot = min(hx.ring((0, 0), 3), key=lambda h: (min(abs(hx.angle(h) - toward), 360 - abs(hx.angle(h) - toward)), h))
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


def _carve(tiles, locked, noise, style: Style, start: Hex, goal: Hex, trail: bool = False,
           through: bool = True) -> list[Hex]:
    """A way from start to goal: cheapest way through, where blockers cost
    more and noise makes it wander. Blockers on it become crossings; a
    `trail` also turns the open ground it crosses into path; `through`
    False keeps to open ground. Returns the hexes on the way (empty if
    there's none)."""
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
            if n not in CELL_SET or (n in locked and n != goal) or (not through and tiles[n] in BLOCKED):
                continue
            c = cost + _cost(tiles, noise, style, n)
            if c < best.get(n, float("inf")):
                best[n] = c
                came[n] = h
                heapq.heappush(todo, (c, n))
    if goal not in came and goal != start:
        return []
    h = goal
    route = []
    while h != start:
        h = came[h]
        route.append(h)
        if h in locked:
            continue
        if tiles[h] == "water" and style.name == "ponds":
            tiles[h] = "ford"
        elif tiles[h] in BLOCKED:
            tiles[h] = CROSSING[tiles[h]]
        elif trail and tiles[h] in ("grass", "flowers", "sand"):
            tiles[h] = "path"
    return route


def _spurs(rng: random.Random, tiles, locked, campfire: Hex, count: tuple[int, int]) -> None:
    """Short one-wide ways into the blockers that end in a dead end."""
    main = reachable(tiles, campfire)
    for _ in range(rng.randint(*count)):
        starts = sorted(h for h in main if tiles[h] in ("grass", "flowers", "path", "sand"))
        rng.shuffle(starts)
        for start in starts:
            way, h = [], start
            for _ in range(rng.randint(2, 4)):
                # into a blocker (off the big edge) that touches no other open
                # ground (but the mouth may touch the ground around it)
                near = {h, *hx.neighbors(h)} if not way else {h}
                options = [n for n in hx.neighbors(h) if n in CELL_SET and n not in locked and n not in way
                           and hx.distance(n, (0, 0)) < LOCAL_RADIUS and tiles[n] in ("tree", "bush", "rock", "cliff")
                           and all(m in near or m not in CELL_SET or tiles[m] in BLOCKED for m in hx.neighbors(n))]
                if not options:
                    break
                h = rng.choice(options)
                way.append(h)
            if len(way) >= 2:
                for h in way:
                    tiles[h] = "grass"
                    main.add(h)
                break


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
    if h in local.pois:
        out["poi"] = local.pois[h]
    if h in local.buildings:
        out["role"] = local.buildings[h]
    if h in local.nooks:
        nook = local.nooks[h]
        out["nook"] = nook.kind
        if nook.doors:
            out["doors"] = [hx.direction_to(h, d) for d in nook.doors]
    return out


def beyond(seed: int, big: Hex) -> list[dict]:
    """The ring of hexes just outside big hex `big` (in its own frame),
    from the big hexes around it (the sea past the edge of the world)."""
    world = wd.generate(seed)
    out = []
    for h in hx.ring((0, 0), LOCAL_RADIUS + 1):
        far, fh = owner(to_world(big, h))
        if far in world.hexes:
            m = generate(seed, far)
            out.append({**tile_json(m, fh), "q": h[0], "r": h[1], "biome": m.biome, "big": list(far), "at": list(fh)})
        else:
            out.append({"q": h[0], "r": h[1], "kind": EDGE_OF_WORLD, "biome": None, "big": list(far), "at": list(fh)})
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
