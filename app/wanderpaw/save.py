"""A player's Wanderpaw save (PLAN.md 11n): their world's seed and what
they've found. The world and its small maps are rebuilt from the seed
(world.py, local.py).

Where you are: `at`, the big hex, and `spot`, the small hex inside it.
You walk small hex by small hex and see only your hex and the six touching
it; everything you've seen stays on your map (`seen`: per big hex, a
bitmask over local.CELLS). Leaving by an exit hex puts you on the matching
exit of the neighbor. Every big hex's campfire can be spotted from
anywhere inside it; one you've seen counts as found.

Trips: walking needs a trip. A trip has energy (for now just steps,
TRIP_ENERGY; pets' energy replaces it later). Out of energy, you nap and
wake at the nearest campfire you've found; at a campfire you can end a
trip early. The next trip starts where you are, or at Camp.

view() only ever returns what the player has seen, so the browser can't
spoil the map: the big map shows visited big hexes and glimpses of the
ones touching them (their land, not their names), and the walls around
the visited ones.
"""

from __future__ import annotations

import random

from app import db
from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import world as wd
from app.wanderpaw.hexes import Hex

SAVE_VERSION = 2
CAMP: Hex = (0, 0)
TRIP_ENERGY = 120  # steps, until pets bring their own energy


class WanderError(ValueError):
    """Kid-readable, like FarmError."""


def _key(h: Hex) -> str:
    return f"{h[0]},{h[1]}"


def _unkey(k: str) -> Hex:
    q, r = k.split(",")
    return (int(q), int(r))


def seen_in(save: dict, big: Hex) -> set[Hex]:
    mask = int(save["seen"].get(_key(big), "0"), 16)
    return {h for i, h in enumerate(lc.CELLS) if mask >> i & 1}


def seen_all(save: dict) -> dict[str, list[list[int]]]:
    """Every small hex seen, per big hex ("q,r")."""
    return {k: sorted(map(list, seen_in(save, _unkey(k)))) for k in save["seen"]}


def _see(save: dict, big: Hex, spot: Hex) -> dict:
    """The save after looking around from spot: it and the six touching it."""
    mask = int(save["seen"].get(_key(big), "0"), 16)
    for h in [spot, *hx.neighbors(spot)]:
        if h in lc.INDEX:
            mask |= 1 << lc.INDEX[h]
    visited = save["visited"] if list(big) in save["visited"] else [*save["visited"], list(big)]
    return {**save, "seen": {**save["seen"], _key(big): format(mask, "x")}, "visited": visited}


def new_save(seed: int) -> dict:
    save = {
        "version": SAVE_VERSION, "world_version": wd.WORLD_VERSION, "seed": seed,
        "at": list(CAMP), "spot": [0, 0], "visited": [], "seen": {}, "trip": None, "note": None,
    }
    return _see(save, CAMP, (0, 0))


def world_of(save: dict) -> wd.World:
    return wd.generate(save["seed"])


def local_of(save: dict, big: Hex | None = None) -> lc.LocalMap:
    return lc.generate(save["seed"], tuple(big or save["at"]))


def fit(save: dict) -> dict:
    """The save, made to fit after the generators (or the save layout)
    changed: places that no longer exist are forgotten and a player who
    can't stand where they are goes to that big hex's campfire, or Camp."""
    world = world_of(save)
    save = {"trip": None, "note": None, "seen": {}, **save, "version": SAVE_VERSION, "world_version": wd.WORLD_VERSION}
    save["visited"] = [v for v in save["visited"] if tuple(v) in world.hexes]
    save["seen"] = {k: v for k, v in save["seen"].items() if _unkey(k) in world.hexes}
    at = tuple(save["at"]) if tuple(save["at"]) in world.hexes else CAMP
    local = local_of(save, at)
    spot = tuple(save.get("spot") or local.campfire)
    if not local.walkable(spot):
        spot = local.campfire
    save = {**save, "at": list(at), "spot": list(spot)}
    return _see(_see(save, CAMP, (0, 0)), at, spot)


def load(conn, learner_id: int, rng: random.Random | None = None) -> dict:
    save = db.get_wander(conn, learner_id)
    if save is None:
        save = new_save((rng or random.Random()).randrange(2**31))
        db.save_wander(conn, learner_id, save)
    elif save.get("world_version") != wd.WORLD_VERSION or save.get("version") != SAVE_VERSION:
        save = fit(save)
        db.save_wander(conn, learner_id, save)
    return save


def campfires_found(save: dict) -> list[Hex]:
    found = []
    for k in save["seen"]:
        big = _unkey(k)
        if local_of(save, big).campfire in seen_in(save, big):
            found.append(big)
    return sorted(found)


def nearest_campfire(save: dict, big: Hex) -> Hex:
    """The found campfire fewest big-map steps from big (then the nearest
    as the crow flies)."""
    steps = wd.distances_from(world_of(save), big)
    return min(campfires_found(save), key=lambda c: (steps.get(c, 999), hx.distance(c, big), c))


# --- trips ----------------------------------------------------------------------


def start_trip(save: dict, from_camp: bool = False) -> dict:
    if save["trip"]:
        raise WanderError("You're already out exploring!")
    if from_camp:
        save = {**save, "at": list(CAMP), "spot": [0, 0]}
    save = {**save, "trip": {"energy": TRIP_ENERGY, "max": TRIP_ENERGY}, "note": None}
    return _see(save, tuple(save["at"]), tuple(save["spot"]))


def end_trip(save: dict) -> dict:
    """Head home from a campfire."""
    if not save["trip"]:
        raise WanderError("You're not on a trip.")
    if tuple(save["spot"]) != local_of(save).campfire:
        raise WanderError("Find a campfire to rest at first.")
    return {**save, "trip": None, "note": "rested"}


def nap(save: dict) -> dict:
    """Out of energy: wake at the nearest campfire you've found."""
    big = nearest_campfire(save, tuple(save["at"]))
    save = {**save, "at": list(big), "spot": list(local_of(save, big).campfire), "trip": None, "note": "napped"}
    return _see(save, big, tuple(save["spot"]))


def apply_walk(save: dict, to: Hex) -> dict:
    """One step to a small hex next to you, or out through an exit (to is
    then the hex just past the edge of the map)."""
    if not save["trip"]:
        raise WanderError("Start a trip first!")
    big, spot = tuple(save["at"]), tuple(save["spot"])
    local = local_of(save)
    if hx.distance(spot, to) != 1:
        raise WanderError("You can only walk to a place next to you.")
    if to in lc.CELL_SET:
        if not local.walkable(to):
            raise WanderError(f"The {local.tiles[to]} is in the way.")
        save = {**save, "spot": list(to)}
    else:
        d = hx.direction_to(spot, to)
        if local.exits.get(spot) != d:
            raise WanderError("There's no way out here.")
        nxt = hx.neighbor(big, d)
        save = {**save, "at": list(nxt), "spot": list(lc.mirror(spot, d))}
    save = _see(save, tuple(save["at"]), tuple(save["spot"]))
    energy = save["trip"]["energy"] - 1
    save = {**save, "trip": {**save["trip"], "energy": energy}}
    return nap(save) if energy <= 0 else save


def _write(conn, learner_id: int, change) -> dict:
    save = change(load(conn, learner_id))
    db.save_wander(conn, learner_id, save)
    return save


def walk(conn, learner_id: int, to: Hex) -> dict:
    return _write(conn, learner_id, lambda s: apply_walk(s, to))


def begin(conn, learner_id: int, from_camp: bool) -> dict:
    return _write(conn, learner_id, lambda s: start_trip(s, from_camp))


def finish(conn, learner_id: int) -> dict:
    return _write(conn, learner_id, end_trip)


# --- what the player sees ---------------------------------------------------------


def big_view(save: dict) -> dict:
    world = world_of(save)
    visited = {tuple(v) for v in save["visited"]}
    seen = visited | {n for v in visited for n in hx.neighbors(v) if n in world.hexes}
    hexes = []
    for h in sorted(seen):
        out = wd.hex_json(world.hexes[h])
        out["visited"] = h in visited
        if h not in visited:
            out["name"] = None
        hexes.append(out)
    edges = [wd.edge_json(k, v) for k, v in world.edges.items() if k[0] in visited or k[1] in visited]
    return {"at": save["at"], "radius": wd.MAP_RADIUS, "hexes": hexes, "edges": edges}


def local_view(save: dict) -> dict:
    world = world_of(save)
    big, spot = tuple(save["at"]), tuple(save["spot"])
    here = world.hexes[big]
    local = local_of(save)
    seen = seen_in(save, big)
    near = {spot, *hx.neighbors(spot)}
    tiles = []
    for h in lc.CELLS:
        if h in seen:
            tiles.append({**lc.tile_json(local, h), "near": h in near})
    # Standing on an exit: the land just past it, where the next step goes.
    ghosts = []
    if spot in local.exits:
        d = local.exits[spot]
        nxt = world.hexes[hx.neighbor(big, d)]
        to = hx.neighbor(spot, d)
        ghosts.append({"q": to[0], "r": to[1], "biome": nxt.biome, "region": nxt.region,
                       "name": nxt.name if list(nxt.coord) in save["visited"] else None})
    return {
        "big": list(big), "name": here.name, "region": here.region, "biome": here.biome, "special": here.special,
        "radius": lc.LOCAL_RADIUS, "spot": list(spot), "campfire": list(local.campfire),
        "tiles": tiles, "ghosts": ghosts,
    }


def view(save: dict) -> dict:
    return {
        "big": big_view(save),
        "local": local_view(save),
        "trip": save["trip"],
        "note": save["note"],
        "campfires": len(campfires_found(save)),
        "at_camp": tuple(save["at"]) == CAMP,
    }


# --- lab (admin) moves: no walls, no fog --------------------------------------------


def teleport(conn, learner_id: int, big: Hex, spot: Hex | None = None) -> dict:
    save = load(conn, learner_id)
    if big not in world_of(save).hexes:
        raise WanderError("That place isn't on the map.")
    local = local_of(save, big)
    spot = spot if spot is not None else local.campfire
    if spot not in lc.CELL_SET or not local.walkable(spot):
        raise WanderError("You can't stand there.")
    save = _see({**save, "at": list(big), "spot": list(spot)}, big, spot)
    db.save_wander(conn, learner_id, save)
    return save


def refill(conn, learner_id: int) -> dict:
    """Full energy (starting a trip where you are if you're not on one)."""
    def change(s: dict) -> dict:
        s = s if s["trip"] else start_trip(s)
        return {**s, "trip": {"energy": TRIP_ENERGY, "max": TRIP_ENERGY}}
    return _write(conn, learner_id, change)


def reset(conn, learner_id: int, seed: int | None = None) -> dict:
    save = new_save(seed if seed is not None else random.randrange(2**31))
    db.save_wander(conn, learner_id, save)
    return save
