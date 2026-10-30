"""Wanderpaw saves: walking, fog, fitting a changed world (PLAN.md 11n)."""

import pytest

from app.wanderpaw import hexes as hx
from app.wanderpaw import save as sv
from app.wanderpaw import world as wd

SEED = 11


def _open_and_walled(save):
    world = sv.world_of(save)
    at = tuple(save["at"])
    near = [n for n in hx.neighbors(at) if n in world.hexes]
    return [n for n in near if world.is_open(at, n)], [n for n in near if not world.is_open(at, n)]


def test_new_save_starts_at_camp():
    save = sv.new_save(SEED)
    assert save["at"] == [0, 0] and save["visited"] == [[0, 0]]


def test_step_through_an_open_edge():
    save = sv.new_save(SEED)
    to = _open_and_walled(save)[0][0]
    after = sv.apply_step(save, to)
    assert after["at"] == list(to)
    assert list(to) in after["visited"]
    back = sv.apply_step(after, (0, 0))
    assert back["visited"].count([0, 0]) == 1


def test_walls_and_far_hexes_block():
    save = sv.new_save(SEED)
    world = sv.world_of(save)
    # walk out until there's a wall next to us
    for h in wd.distances_from(world, (0, 0)):
        save = {**save, "at": list(h)}
        if _open_and_walled(save)[1]:
            break
    with pytest.raises(sv.WanderError, match="in the way"):
        sv.apply_step(save, _open_and_walled(save)[1][0])
    with pytest.raises(sv.WanderError, match="next to you"):
        sv.apply_step(sv.new_save(SEED), (3, 0))


def test_view_shows_only_visited_and_glimpsed():
    save = sv.new_save(SEED)
    view = sv.view(save)
    coords = {(h["q"], h["r"]) for h in view["hexes"]}
    assert coords == {(0, 0), *hx.neighbors((0, 0))}
    glimpsed = [h for h in view["hexes"] if not h["visited"]]
    assert glimpsed and all(h["name"] is None for h in glimpsed)
    assert all((0, 0) in (tuple(e["a"]), tuple(e["b"])) for e in view["edges"])


def test_fit_sends_a_lost_player_home():
    save = {**sv.new_save(SEED), "world_version": -1, "at": [99, 99], "visited": [[99, 99]]}
    fitted = sv.fit(save)
    assert fitted["at"] == [0, 0]
    assert fitted["visited"] == [[0, 0]]
    assert fitted["world_version"] == wd.WORLD_VERSION
