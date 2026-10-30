"""Wanderpaw's small maps (PLAN.md 11n)."""

import statistics
from collections import defaultdict

import pytest

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import world as wd

SEEDS = range(6)


def _maps():
    for seed in SEEDS:
        for big in wd.generate(seed).hexes:
            yield seed, big, lc.generate(seed, big)


def test_zones_split_the_outer_ring():
    cells = [h for d in range(6) for h in lc.zone(d)]
    assert len(cells) == len(set(cells)) == len(lc.OUTER) == 30
    for d in range(6):
        corner = lc.zone(d)[lc.ZONE_HALF]
        assert corner == (hx.DIRECTIONS[d][0] * lc.LOCAL_RADIUS, hx.DIRECTIONS[d][1] * lc.LOCAL_RADIUS)
        # every zone hex looks off the map in its direction
        assert all(hx.neighbor(h, d) not in lc.CELL_SET for h in lc.zone(d))


def test_mirror_goes_back_and_forth():
    for d in range(6):
        for h in lc.zone(d):
            m = lc.mirror(h, d)
            assert m in lc.zone((d + 3) % 6)
            assert lc.mirror(m, (d + 3) % 6) == h


def test_same_place_same_map():
    lc.generate.cache_clear()
    a = lc.to_json(lc.generate(3, (0, 0)))
    lc.generate.cache_clear()
    assert lc.to_json(lc.generate(3, (0, 0))) == a


def test_every_walkable_hex_reachable_and_exits_line_up():
    for seed, big, local in _maps():
        walkable = {h for h in lc.CELLS if local.walkable(h)}
        assert walkable == lc.reachable(local.tiles, local.campfire), (seed, big)
        assert local.tiles[local.campfire] in ("campfire", "camp")
        for h, d in local.exits.items():
            far = lc.generate(seed, hx.neighbor(big, d))
            assert far.exits.get(lc.mirror(h, d)) == (d + 3) % 6, (seed, big, h)


def test_open_sides_have_exits_and_walled_sides_are_solid():
    for seed, big, local in _maps():
        world = wd.generate(seed)
        for d in range(6):
            n = hx.neighbor(big, d)
            zone = lc.zone(d)
            if n in world.hexes and world.is_open(big, n):
                assert any(local.exits.get(h) == d for h in zone)
            else:
                assert not any(local.walkable(h) for h in zone)


def test_feels_differ():
    share = defaultdict(list)
    for _, _, local in _maps():
        share[local.style].append(sum(local.walkable(h) for h in lc.CELLS) / len(lc.CELLS))
    mean = {k: statistics.mean(v) for k, v in share.items()}
    assert mean["open"] > 0.7
    assert mean["open"] > mean["forest"] > mean["deep_forest"]
    assert all(m >= 0.45 for m in mean.values())  # most hexes walkable


def test_every_biome_has_a_style():
    assert {b for biomes in wd.BIOMES.values() for b, *_ in biomes} == set(lc.BIOME_STYLES)


@pytest.mark.parametrize("seed", SEEDS)
def test_specials(seed):
    world = wd.generate(seed)
    camp = lc.generate(seed, (0, 0))
    assert camp.campfire == (0, 0) and camp.tiles[(0, 0)] == "camp"
    for big in world.hexes.values():
        local = lc.generate(seed, big.coord)
        kinds = set(local.tiles.values())
        if big.special == "town":
            assert len(local.buildings) >= 5 and "plaza" in kinds
        if big.special == "temple":
            assert "temple" in kinds
        if big.special == "final":
            assert "stone" in kinds
