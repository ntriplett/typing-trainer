"""A player's Wanderpaw save (PLAN.md 11n): their world's seed and what
they've found. The world itself is rebuilt from the seed (world.py).

Fog: the player sees the big hexes they've visited and the ones touching
those (glimpsed: their land, not their names), and the walls around the
visited ones. view() only ever returns that much, so the browser can't
spoil the map.
"""

from __future__ import annotations

import random

from app import db
from app.wanderpaw import hexes as hx
from app.wanderpaw import world as wd
from app.wanderpaw.hexes import Hex

SAVE_VERSION = 1
CAMP: Hex = (0, 0)


class WanderError(ValueError):
    """Kid-readable, like FarmError."""


def new_save(seed: int) -> dict:
    return {"version": SAVE_VERSION, "world_version": wd.WORLD_VERSION, "seed": seed, "at": list(CAMP), "visited": [list(CAMP)]}


def world_of(save: dict) -> wd.World:
    return wd.generate(save["seed"])


def fit(save: dict) -> dict:
    """The save, made to fit its world after the generator changed: places
    that no longer exist are forgotten and a lost player goes back to Camp."""
    world = world_of(save)
    visited = [v for v in save["visited"] if tuple(v) in world.hexes]
    at = save["at"] if tuple(save["at"]) in world.hexes else list(CAMP)
    if list(CAMP) not in visited:
        visited.insert(0, list(CAMP))
    return {**save, "world_version": wd.WORLD_VERSION, "at": at, "visited": visited}


def load(conn, learner_id: int, rng: random.Random | None = None) -> dict:
    save = db.get_wander(conn, learner_id)
    if save is None:
        save = new_save((rng or random.Random()).randrange(2**31))
        db.save_wander(conn, learner_id, save)
    elif save.get("world_version") != wd.WORLD_VERSION:
        save = fit(save)
        db.save_wander(conn, learner_id, save)
    return save


def apply_step(save: dict, to: Hex) -> dict:
    world = world_of(save)
    at = tuple(save["at"])
    if to not in world.hexes or hx.distance(at, to) != 1:
        raise WanderError("You can only walk to a place next to you.")
    if not world.is_open(at, to):
        kind = world.edges[hx.edge_key(at, to)]
        raise WanderError(f"A {kind.replace('_', ' ')} is in the way.")
    visited = save["visited"] if list(to) in save["visited"] else [*save["visited"], list(to)]
    return {**save, "at": list(to), "visited": visited}


def step(conn, learner_id: int, to: Hex) -> dict:
    save = apply_step(load(conn, learner_id), to)
    db.save_wander(conn, learner_id, save)
    return save


def view(save: dict) -> dict:
    """What the player can see of their world."""
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


# --- lab (admin) moves: no walls, no fog --------------------------------------


def teleport(conn, learner_id: int, to: Hex) -> dict:
    save = load(conn, learner_id)
    if to not in world_of(save).hexes:
        raise WanderError("That place isn't on the map.")
    visited = save["visited"] if list(to) in save["visited"] else [*save["visited"], list(to)]
    save = {**save, "at": list(to), "visited": visited}
    db.save_wander(conn, learner_id, save)
    return save


def reset(conn, learner_id: int, seed: int | None = None) -> dict:
    save = new_save(seed if seed is not None else random.randrange(2**31))
    db.save_wander(conn, learner_id, save)
    return save
