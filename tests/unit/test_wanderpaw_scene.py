"""The facts behind a place's picture (app/wanderpaw/scene.py)."""

import json

import pytest

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import scene as sc
from app.wanderpaw import world as wd

SEED = 3
WORLD = wd.generate(SEED)
CAMP = next(b for b, h in WORLD.hexes.items() if h.special == "camp")


def _spots(kinds=None):
    for big in WORLD.hexes:
        m = lc.generate(SEED, big)
        for h, kind in m.tiles.items():
            if m.walkable(h) and (kinds is None or kind in kinds):
                yield big, h


def _first(kinds):
    return next(_spots(kinds))


def test_the_same_hex_gives_the_same_picture():
    big, h = _first({"grass"})
    assert sc.describe(SEED, big, h) == sc.describe(SEED, big, h)
    json.dumps(sc.describe(SEED, big, h))  # goes to the page as it is


def test_scene_seed_is_steady_and_differs_by_hex():
    assert sc.scene_seed(3, (4, -2)) == sc.scene_seed(3, (4, -2))
    numbers = {sc.scene_seed(3, g) for g in hx.spiral((0, 0), 12)}
    assert len(numbers) == len(hx.spiral((0, 0), 12))


def test_everything_stays_in_the_picture():
    for big, h in list(_spots())[::40]:
        s = sc.describe(SEED, big, h)
        assert s["biome"] == WORLD.hexes[big].biome
        assert len(s["far"]) == sc.SECTORS
        for thing in [*s["mid"], *s["far"], *s["landmarks"], *([s["water"]] if s["water"] else [])]:
            assert -1 <= thing["at"] <= 1


def test_mid_is_your_rings_and_skips_plain_grass():
    big, h = _first({"grass"})
    s = sc.describe(SEED, big, h)
    assert all(1 <= t["ring"] <= sc.MID_RINGS for t in s["mid"])
    assert all(t["kind"] != "grass" or "nook" in t or "poi" in t for t in s["mid"])


@pytest.mark.parametrize("kinds,setting", [
    ({"campfire"}, "camp"), ({"camp"}, "camp"), ({"plaza"}, "town"), ({"court"}, "temple"), ({"stone"}, "heartstone"),
])
def test_your_own_hex_sets_the_scene(kinds, setting):
    big, h = _first(kinds)
    assert sc.describe(SEED, big, h)["setting"] == setting


def test_a_shrine_beside_you_sets_the_scene():
    for big in WORLD.hexes:
        m = lc.generate(SEED, big)
        for h, poi in m.pois.items():
            if poi == "shrine" and m.tiles[h] == "grass":
                assert sc.describe(SEED, big, h)["setting"] == "shrine"
                return
    pytest.skip("no shrine on grass in this world")


def test_a_nearby_town_shows_on_the_horizon_but_a_far_one_doesnt():
    town = next(b for b, h in WORLD.hexes.items() if h.special == "town")
    m = lc.generate(SEED, town)
    plaza = next(h for h, k in m.tiles.items() if k == "plaza")
    g = lc.to_world(town, plaza)
    away = next(x for x in hx.ring(g, 6) if lc.owner(x)[0] in WORLD.hexes and lc.generate(SEED, lc.owner(x)[0]).walkable(lc.owner(x)[1]))
    s = sc.describe(SEED, *lc.owner(away))
    towns = [t for t in s["landmarks"] if t["kind"] == "town"]
    assert towns and towns[0]["dist"] <= 8


def test_the_view_aims_at_what_is_most_interesting():
    town = next(b for b, h in WORLD.hexes.items() if h.special == "town")
    m = lc.generate(SEED, town)
    plaza = next(h for h, k in m.tiles.items() if k == "plaza")
    s = sc.describe(SEED, town, plaza)
    towns = [t for t in s["landmarks"] if t["kind"] == "town"]
    assert towns and abs(towns[0]["at"]) <= (sc.WOBBLE_DEG + 1) / 180


def _kind(x):
    b, inner = lc.owner(x)
    return lc.generate(SEED, b).tiles[inner] if b in WORLD.hexes else lc.EDGE_OF_WORLD


def test_water_is_there_only_where_it_makes_sense():
    wet = dry = 0
    for big, h in list(_spots())[::10]:
        s = sc.describe(SEED, big, h)
        g = lc.to_world(big, h)
        reach = sc.HEAVY_RINGS if s["style"] in sc.WATER_HEAVY else sc.MID_RINGS
        by = any(_kind(x) in ("water", lc.EDGE_OF_WORLD) for x in hx.spiral(g, reach)[1:])
        assert bool(s["water"]) == (by or s["ground"] in ("bridge", "ford"))
        wet += bool(s["water"])
        dry += not s["water"]
    assert wet and dry


def test_water_a_little_further_off_counts_only_in_watery_lands():
    for big, h in list(_spots())[::10]:
        s = sc.describe(SEED, big, h)
        g = lc.to_world(big, h)
        if s["style"] not in sc.WATER_HEAVY and s["ground"] not in ("bridge", "ford"):
            near = any(_kind(x) in ("water", lc.EDGE_OF_WORLD) for x in hx.spiral(g, sc.MID_RINGS)[1:])
            assert bool(s["water"]) == near


def test_too_many_of_a_thing_is_just_clutter():
    for big, h in list(_spots())[::15]:
        kinds = [m["kind"] for m in sc.describe(SEED, big, h)["landmarks"]]
        assert kinds.count("cave") <= sc.MOST["cave"]
        assert kinds.count("smoke") <= sc.MOST["smoke"]
        assert sum(k in sc.WATER_MARKS for k in kinds) <= sc.MOST["water"]


def test_gates_you_got_past_are_walked_on():
    for gate, walked in sc.WALKED_ON.items():
        assert walked in ("path", "bridge"), gate


def test_rivers_and_seas_are_spotted():
    kinds = {m["kind"] for big, h in list(_spots())[::15] for m in sc.describe(SEED, big, h)["landmarks"]}
    assert {"town", "cave", "sea"} <= kinds
    assert kinds & {"river", "lake", "pond"}
