"""Wanderpaw saves: walking, fog, trips, naps, fitting a changed world (PLAN.md 11n)."""

import pytest

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import save as sv
from app.wanderpaw import world as wd

SEED = 11


def _on_trip():
    return sv.start_trip(sv.new_save(SEED))


def _path(local, start, goal):
    """Small-map steps from start to goal (breadth first)."""
    came, todo = {start: None}, [start]
    for h in todo:
        for n in hx.neighbors(h):
            if n in lc.CELL_SET and n not in came and local.walkable(n):
                came[n] = h
                todo.append(n)
    out, h = [], goal
    while h != start:
        out.append(h)
        h = came[h]
    return out[::-1]


def test_new_save_starts_at_camp_having_seen_around_it():
    save = sv.new_save(SEED)
    assert save["at"] == [0, 0] and save["spot"] == [0, 0]
    assert sv.seen_in(save, (0, 0)) == {(0, 0), *hx.neighbors((0, 0))}
    assert save["trip"] is None


def test_walking_needs_a_trip_and_costs_energy():
    save = sv.new_save(SEED)
    to = next(n for n in hx.neighbors((0, 0)) if sv.local_of(save).walkable(n))
    with pytest.raises(sv.WanderError, match="trip"):
        sv.apply_walk(save, to)
    save = sv.apply_walk(sv.start_trip(save), to)
    assert save["spot"] == list(to)
    assert save["trip"]["energy"] == sv.TRIP_ENERGY - 1
    assert hx.neighbors(to)[0] in sv.seen_in(save, (0, 0)) or hx.neighbors(to)[0] not in lc.CELL_SET


def test_blocked_and_far_hexes_refuse():
    save = _on_trip()
    local = sv.local_of(save)
    with pytest.raises(sv.WanderError, match="next to you"):
        sv.apply_walk(save, (3, 0))
    blocked = [h for h in lc.CELLS if not local.walkable(h)]
    spot = next(h for h in lc.CELLS if local.walkable(h) and any(n in blocked for n in hx.neighbors(h)))
    save = {**save, "spot": list(spot)}
    with pytest.raises(sv.WanderError, match="in the way"):
        sv.apply_walk(save, next(n for n in hx.neighbors(spot) if n in blocked))


def test_leaving_by_an_exit_lands_on_the_matching_exit():
    save = _on_trip()
    local = sv.local_of(save)
    h, d = next(iter(local.exits.items()))
    save = {**save, "spot": list(h)}
    after = sv.apply_walk(save, hx.neighbor(h, d))
    nxt = hx.neighbor((0, 0), d)
    assert after["at"] == list(nxt)
    assert after["spot"] == list(lc.mirror(h, d))
    assert list(nxt) in after["visited"]
    # non-exit edge hexes don't lead out
    edge = next(x for x in lc.OUTER if local.walkable(x) and x not in local.exits)
    with pytest.raises(sv.WanderError):
        sv.apply_walk({**save, "spot": list(edge)}, next(n for n in hx.neighbors(edge) if n not in lc.CELL_SET))


def test_out_of_energy_naps_at_the_nearest_found_campfire():
    save = _on_trip()
    local = sv.local_of(save)
    h, d = next(iter(local.exits.items()))
    save = sv.apply_walk({**save, "spot": list(h)}, hx.neighbor(h, d))
    nxt = tuple(save["at"])
    # walk to the new hex's campfire, then run out of energy there
    for step in _path(sv.local_of(save), tuple(save["spot"]), sv.local_of(save).campfire):
        save = sv.apply_walk(save, step)
    assert nxt in sv.campfires_found(save)
    away = next(n for n in hx.neighbors(tuple(save["spot"])) if sv.local_of(save).walkable(n))
    save = {**save, "trip": {"energy": 1, "max": sv.TRIP_ENERGY}}
    napped = sv.apply_walk(save, away)
    assert napped["trip"] is None and napped["note"] == "napped"
    assert napped["at"] == list(nxt)
    assert napped["spot"] == list(sv.local_of(napped).campfire)


def test_end_a_trip_only_at_a_campfire_and_start_again_at_camp():
    save = _on_trip()
    rested = sv.end_trip(save)  # Camp's camp is a campfire
    assert rested["trip"] is None and rested["note"] == "rested"
    away = {**_on_trip(), "spot": [1, 0]} if sv.local_of(save).walkable((1, 0)) else None
    if away:
        with pytest.raises(sv.WanderError, match="campfire"):
            sv.end_trip(away)
    far = {**rested, "at": [1, 0], "spot": list(sv.local_of(rested, (1, 0)).campfire)}
    again = sv.start_trip(far, from_camp=True)
    assert again["at"] == [0, 0] and again["trip"]["energy"] == sv.TRIP_ENERGY


def test_view_shows_only_what_you_have_seen():
    save = sv.new_save(SEED)
    view = sv.view(save)
    big = {(h["q"], h["r"]) for h in view["big"]["hexes"]}
    assert big == {(0, 0), *[n for n in hx.neighbors((0, 0)) if n in wd.generate(SEED).hexes]}
    assert all(h["name"] is None for h in view["big"]["hexes"] if not h["visited"])
    tiles = {(t["q"], t["r"]) for t in view["local"]["tiles"]}
    assert tiles == {(0, 0), *hx.neighbors((0, 0))}
    assert all(t["near"] for t in view["local"]["tiles"])
    assert view["local"]["campfire"] == [0, 0]


def test_ghost_past_an_exit():
    save = sv.new_save(SEED)
    h, d = next(iter(sv.local_of(save).exits.items()))
    ghosts = sv.local_view({**save, "spot": list(h)})["ghosts"]
    assert [(g["q"], g["r"]) for g in ghosts] == [hx.neighbor(h, d)]


def test_fit_sends_a_lost_player_to_a_campfire():
    old = {"version": 1, "world_version": -1, "seed": SEED, "at": [99, 99], "visited": [[99, 99]]}
    fitted = sv.fit(old)
    assert fitted["at"] == [0, 0] and fitted["spot"] == [0, 0]
    assert fitted["visited"] == [[0, 0]]
    assert fitted["version"] == sv.SAVE_VERSION and fitted["trip"] is None
