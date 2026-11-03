"""What the picture of a place shows (the Party book and campfires).

describe() turns where you stand into plain facts for the page to paint
(wander_scene.js): which land, what you're standing on, what's around you,
and what can be spotted far off. No pictures are stored: the page has a kit
of parts and paints from these facts, and `seed` picks where exactly things
go, so a small hex looks the same every time. It reads the true land, fog or
not: spotting a far-off town's roofs is a fun hint, and you can't tell
exactly which way it is.

Three depths:
  ground/setting  your own hex: the foreground (camp, town, temple, shrine, wild)
  mid             each hex within MID_RINGS: one thing each in the middle distance
  far, landmarks  out to FAR_RINGS: the horizon, sector by sector, and the
                  things worth spotting on it

`at` is across the picture, -1 (left edge) to 1 (right edge). The view aims
at whatever's most interesting, and the whole way round is squeezed in, so
things behind you are pulled in at the edges: a cheat, but nothing's missed.
"""

from __future__ import annotations

import math
import zlib
from collections import Counter

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import world as wd
from app.wanderpaw.hexes import Hex

MID_RINGS = 2
FAR_RINGS = 2 * lc.LOCAL_RADIUS + 1  # about a big hex's width
SECTORS = 12  # slices of the horizon
SECTOR_DEG = 360 / SECTORS

HALL = lc.HALL_BLOCKS | {"court", "temple"}
CAMP_GROUND = ("campfire", "camp")
CAVES = ("cave", "grotto", "mine", "tunnel")
# How much a thing pulls the view its way (over distance).
PULL = {"heartstone": 12, "temple": 10, "town": 9, "shrine": 6, "house": 4, "cave": 4, "river": 3, "lake": 3, "pond": 2,
        "sea": 3, "smoke": 1}
PEAK_PULL = 2.5  # a sector that's all cliffs
WOBBLE_DEG = 25  # the view's a little off whatever it's aimed at, so it's not always dead center
TOWN_SIZE = 3  # this many buildings together is a town; fewer, a house
LANDMARK_WATER = 3  # hexes of water it takes to be worth spotting
# The nearest few of each; more is just clutter.
MOST = {"cave": 1, "water": 2, "smoke": 1, "shrine": 1}
WATER_MARKS = ("river", "lake", "pond")
HEAVY_RINGS = 4
WATER_STYLES = {"river": "river", "lake": "lake", "isles": "lake", "ponds": "pond"}
WATER_HEAVY = frozenset(WATER_STYLES)  # lands where water this close is in the picture too
WALKED_ON = {**lc.CLEARED_TILES, **{g: "path" for g in lc.GATE_TILES.values() if g not in lc.CLEARED_TILES}}  # a gate you got past


def scene_seed(seed: int, g: Hex) -> int:
    """A steady number for one small hex (not hash(): that changes per run)."""
    return zlib.crc32(f"{seed}:{g[0]}:{g[1]}".encode())


def _bearing(a: Hex, b: Hex) -> float:
    """The way from a to b, in degrees (0 east, counter-clockwise, like hexes.angle)."""
    ax, ay = hx.to_pixel(a)
    bx, by = hx.to_pixel(b)
    return math.degrees(math.atan2(ay - by, bx - ax)) % 360


def _mean_bearing(bearings: list[float]) -> float:
    x = sum(math.cos(math.radians(b)) for b in bearings)
    y = sum(math.sin(math.radians(b)) for b in bearings)
    return math.degrees(math.atan2(y, x)) % 360


def _at(bearing: float, view: float) -> float:
    """Across the picture: looking along `view`, counter-clockwise is left."""
    off = (bearing - view + 180) % 360 - 180
    return round(-off / 180, 3)


def _tile(seed: int, world: wd.World, g: Hex) -> dict:
    """What's on world hex g: its kind, nook, place of interest, and whose land."""
    big, h = lc.owner(g)
    if big not in world.hexes:
        return {"kind": lc.EDGE_OF_WORLD, "big": big, "biome": None, "style": None}
    m = lc.generate(seed, big)
    out = {"kind": m.tiles[h], "big": big, "biome": m.biome, "style": m.style}
    if h in m.nooks:
        out["nook"] = m.nooks[h].kind
    if h in m.pois:
        out["poi"] = m.pois[h]
    if h in m.buildings:
        out["role"] = m.buildings[h]
    return out


def _setting(ground: str, tile: dict, near: list[dict]) -> str:
    """What your own hex makes of the picture."""
    if ground in CAMP_GROUND:
        return "camp"
    if ground == "stone":
        return "heartstone"
    if ground in HALL:
        return "temple"
    close = [t for t in near if t["ring"] == 1]
    if ground == "plaza" or sum(t["kind"] == "building" for t in near) >= 2 or any(t["kind"] == "plaza" for t in close):
        return "town"
    if ground == "building":
        return "house"
    if tile.get("poi") == "shrine" or any(t.get("poi") == "shrine" for t in close):
        return "shrine"
    return "wild"


def _landmarks(seed: int, world: wd.World, me: Hex, around: list[tuple[Hex, dict, int]]) -> list[dict]:
    """The things worth spotting, near or far: [{kind, bearing, dist, ...}].
    Buildings, halls and water are gathered up per big hex: one town, not ten roofs."""
    found: list[dict] = []
    groups: dict[tuple[str, Hex], list[tuple[Hex, int]]] = {}
    for g, t, dist in around:
        kind = t["kind"]
        if kind == "building":
            groups.setdefault(("building", t["big"]), []).append((g, dist))
        elif kind in HALL or kind == "stone":
            groups.setdefault(("hall", t["big"]), []).append((g, dist))
        elif kind == "water":
            groups.setdefault(("water", t["big"]), []).append((g, dist))
        elif kind == lc.EDGE_OF_WORLD:
            groups.setdefault(("sea", (0, 0)), []).append((g, dist))
        elif kind in CAMP_GROUND:
            found.append({"kind": "smoke", "bearing": _bearing(me, g), "dist": dist})
        if t.get("nook") in CAVES:
            found.append({"kind": "cave", "nook": t["nook"], "bearing": _bearing(me, g), "dist": dist})
        if t.get("poi") == "shrine":
            found.append({"kind": "shrine", "bearing": _bearing(me, g), "dist": dist})
    for (what, big), spots in groups.items():
        bearing = _mean_bearing([_bearing(me, g) for g, _ in spots])
        dist = min(d for _, d in spots)
        n = len(spots)
        if what == "building":
            found.append({"kind": "town" if n >= TOWN_SIZE else "house", "bearing": bearing, "dist": dist, "n": n})
        elif what == "hall":
            here = world.hexes[big]
            found.append({"kind": "heartstone" if here.special == "final" else "temple", "bearing": bearing, "dist": dist, "region": here.region})
        elif what == "sea":
            found.append({"kind": "sea", "bearing": bearing, "dist": dist, "n": n})
        elif n >= LANDMARK_WATER:
            kind = WATER_STYLES.get(lc.generate(seed, big).style, "river")  # a walled edge's water is a river
            found.append({"kind": kind, "bearing": bearing, "dist": dist, "n": n})
    kept, taken = [], Counter()
    for f in sorted(found, key=lambda f: (f["dist"], f["bearing"])):
        group = "water" if f["kind"] in WATER_MARKS else f["kind"]
        if taken[group] < MOST.get(group, 99):
            kept.append(f)
            taken[group] += 1
    return kept


def _horizon(far: list[tuple[Hex, dict, int]], me: Hex) -> list[dict]:
    """Slices of the horizon: how much of each thing, and whose land."""
    slices = [{"n": 0, "kinds": Counter(), "biomes": Counter()} for _ in range(SECTORS)]
    for g, t, _ in far:
        s = slices[int(_bearing(me, g) // SECTOR_DEG) % SECTORS]
        s["n"] += 1
        s["kinds"][t["kind"]] += 1
        s["biomes"][t["biome"]] += 1
    out = []
    for i, s in enumerate(slices):
        top = sorted(s["biomes"].items(), key=lambda kv: (-kv[1], str(kv[0])))
        out.append({"bearing": (i + 0.5) * SECTOR_DEG, "biome": top[0][0] if top else None,
                    **{k: round(s["kinds"][k] / max(1, s["n"]), 2) for k in ("tree", "cliff", "rock", "water", "ocean")}})
    return out


def _aim(seed: int, marks: list[dict], horizon: list[dict], pool: dict | None) -> float:
    """Where to look: at whatever pulls hardest, a little off center."""
    pulls = [(PULL[m["kind"]] / (1 + m["dist"] / lc.LOCAL_RADIUS), m["bearing"]) for m in marks]
    pulls += [(PEAK_PULL * s["cliff"], s["bearing"]) for s in horizon]
    if pool:
        pulls.append((PULL["lake"], pool["bearing"]))
    best = max(pulls, key=lambda p: (round(p[0], 6), p[1]), default=(0, 0))
    wobble = seed % (2 * WOBBLE_DEG + 1) - WOBBLE_DEG
    # nothing to see: any way will do
    return (best[1] + wobble) % 360 if best[0] > 0 else float(seed % 360)


def _pool(near: list[dict], ground: str, style: str | None, close: list[tuple[float, str]]) -> dict | None:
    """Water close enough to be in the picture, big enough to swim in: right
    beside you, or a little further off in a land that's mostly water.
    `close`: (bearing, kind) of the hexes just past `near`."""
    wet = [t for t in near if t["kind"] in ("water", lc.EDGE_OF_WORLD)]
    if not wet and style in WATER_HEAVY:
        lapping = [b for b, kind in close if kind in ("water", lc.EDGE_OF_WORLD)]
        if lapping:
            return {"kind": "water", "size": 1, "bearing": _mean_bearing(lapping)}
    if not wet and ground not in ("bridge", "ford"):
        return None
    if not wet:
        return {"kind": ground, "size": 1, "bearing": 0.0}
    kind = "sea" if any(t["kind"] == lc.EDGE_OF_WORLD for t in wet) else "water"
    return {"kind": kind, "size": 1 if len(wet) <= 2 else 2 if len(wet) <= 5 else 3,
            "bearing": _mean_bearing([t["bearing"] for t in wet])}


def describe(seed: int, big: Hex, spot: Hex) -> dict:
    """The facts of the picture from small hex `spot` of big hex `big`."""
    world = wd.generate(seed)
    me = lc.to_world(big, spot)
    here = world.hexes[big]
    tile = _tile(seed, world, me)
    ground = WALKED_ON.get(tile["kind"], tile["kind"])
    near = []
    for g in hx.spiral(me, MID_RINGS)[1:]:
        t = _tile(seed, world, g)
        near.append({**t, "ring": hx.distance(me, g), "bearing": _bearing(me, g)})
    far = [(g, _tile(seed, world, g), hx.distance(me, g)) for g in hx.spiral(me, FAR_RINGS)[1 + len(near):]]
    number = scene_seed(seed, me)
    horizon = _horizon(far, me)
    marks = _landmarks(seed, world, me, [(lc_g, t, t["ring"]) for lc_g, t in zip(hx.spiral(me, MID_RINGS)[1:], near)] + far)
    close = [(_bearing(me, g), t["kind"]) for g, t, dist in far if dist <= HEAVY_RINGS]
    pool = _pool(near, ground, tile["style"], close)
    view = _aim(number, marks, horizon, pool)
    mid = [{k: t[k] for k in ("kind", "ring", "biome", "nook", "poi", "role") if k in t} | {"at": _at(t["bearing"], view)}
           for t in near if t["kind"] != "grass" or "nook" in t or "poi" in t]
    return {
        "seed": number, "name": here.name, "region": here.region, "biome": here.biome, "style": tile["style"],
        "special": here.special, "ground": ground, "setting": _setting(ground, tile, near),
        "nook": tile.get("nook"), "poi": tile.get("poi"), "role": tile.get("role"),
        "mid": mid,
        "far": sorted(({**{k: v for k, v in s.items() if k != "bearing"}, "at": _at(s["bearing"], view)} for s in horizon), key=lambda s: s["at"]),
        "landmarks": sorted(({**{k: v for k, v in m.items() if k != "bearing"}, "at": _at(m["bearing"], view)} for m in marks), key=lambda m: m["dist"]),
        "water": {"kind": pool["kind"], "size": pool["size"], "at": _at(pool["bearing"], view)} if pool else None,
    }


def samples(seed: int) -> list[dict]:
    """A look at everything for the scene lab: two spots per biome, then each setting."""
    world = wd.generate(seed)
    out: list[dict] = []
    done: Counter = Counter()

    def add(label: str, big: Hex, h: Hex) -> None:
        out.append({"label": f"{label}: {world.hexes[big].name}", "big": list(big), "spot": list(h), "spec": describe(seed, big, h)})

    for big, here in sorted(world.hexes.items()):
        if done[here.biome] or here.special:
            continue
        done[here.biome] += 1
        m = lc.generate(seed, big)
        open_ground = [h for h in lc.CELLS if m.walkable(h) and m.tiles[h] in ("grass", "flowers", "path", "sand")]
        for h in (open_ground[0], open_ground[len(open_ground) // 2]) if open_ground else ():
            add(here.biome, big, h)
    for special, kinds in (("camp", ("camp",)), ("town", ("campfire", "plaza", "path")), ("temple", ("court", "temple")), ("final", ("stone", "court"))):
        big = next(b for b, h in sorted(world.hexes.items()) if h.special == special)
        m = lc.generate(seed, big)
        for kind in kinds:
            h = next((c for c in lc.CELLS if m.tiles[c] == kind), None)
            if h:
                add(f"{special} {kind}", big, h)
    for big, here in sorted(world.hexes.items()):
        m = lc.generate(seed, big)
        shrine = next((h for h, poi in m.pois.items() if poi == "shrine"), None)
        if shrine:
            add("shrine", big, shrine)
            break
    return out
