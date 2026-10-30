"""Wanderpaw's hex math and world generator (PLAN.md 11n)."""

import pytest

from app.wanderpaw import hexes as hx
from app.wanderpaw import world as wd

SEEDS = range(40)


# --- hexes ---------------------------------------------------------------------


def test_neighbors_are_one_step_and_opposite_directions_undo():
    h = (2, -1)
    assert all(hx.distance(h, n) == 1 for n in hx.neighbors(h))
    for d in range(6):
        assert hx.neighbor(hx.neighbor(h, d), (d + 3) % 6) == h
        assert hx.direction_to(h, hx.neighbor(h, d)) == d


def test_rings_and_spirals_count():
    assert len(hx.ring((0, 0), 0)) == 1
    assert len(hx.ring((0, 0), 3)) == 18
    assert all(hx.distance((0, 0), h) == 3 for h in hx.ring((0, 0), 3))
    assert len(set(hx.spiral((0, 0), 5))) == 91


def test_edge_key_is_order_free():
    assert hx.edge_key((0, 0), (1, 0)) == hx.edge_key((1, 0), (0, 0))


def test_angle_goes_counter_clockwise_from_east():
    assert hx.angle((1, 0)) == pytest.approx(0)
    assert hx.angle((0, -1)) == pytest.approx(120)
    assert hx.angle((-1, 0)) == pytest.approx(180)


# --- world ---------------------------------------------------------------------


def test_same_seed_same_world():
    wd.generate.cache_clear()
    a = wd.to_json(wd.generate(7))
    wd.generate.cache_clear()
    assert wd.to_json(wd.generate(7)) == a
    assert wd.to_json(wd.generate(8)) != a


@pytest.mark.parametrize("seed", SEEDS)
def test_world_shape(seed):
    world = wd.generate(seed)
    assert 60 <= len(world.hexes) <= 90
    assert world.hexes[(0, 0)].special == "camp"
    assert sum(b.special == "final" for b in world.hexes.values()) == 1
    assert all(b.region == wd.HEARTLAND for b in world.hexes.values() if b.ring <= wd.HEARTLAND_RADIUS)
    assert len({b.name for b in world.hexes.values()}) == len(world.hexes)


@pytest.mark.parametrize("seed", SEEDS)
def test_one_temple_per_region_on_the_outer_edge(seed):
    world = wd.generate(seed)
    temples = world.temples()
    assert set(temples) == set(wd.REGIONS)
    for region, h in temples.items():
        assert world.hexes[h].region == region
        assert world.hexes[h].ring == wd.MAP_RADIUS
        assert any(n not in world.hexes for n in hx.neighbors(h))


@pytest.mark.parametrize("seed", SEEDS)
def test_regions_are_one_piece_with_towns(seed):
    world = wd.generate(seed)
    for region in wd.REGIONS:
        cells = [h for h, b in world.hexes.items() if b.region == region]
        assert len(wd._components(cells)) == 1
        assert any(world.hexes[h].special == "town" for h in cells)


@pytest.mark.parametrize("seed", SEEDS)
def test_everything_reachable_but_you_have_to_weave(seed):
    world = wd.generate(seed)
    dist = wd.distances_from(world, (0, 0))
    assert set(dist) == set(world.hexes)
    walls = [k for k, v in world.edges.items() if v != "open"]
    assert len(walls) > len(world.edges) / 3
    assert all(v in {"open", "river", "cliff", "thicket", "rocks"} for v in world.edges.values())


def test_temples_take_weaving_to_reach():
    walks = [d for seed in SEEDS for d in (lambda w: [wd.distances_from(w, (0, 0))[h] for h in w.temples().values()])(wd.generate(seed))]
    assert sum(walks) / len(walks) >= 8  # a straight line is 5


@pytest.mark.parametrize("seed", SEEDS)
def test_each_region_opens_onto_the_heartland_once(seed):
    world = wd.generate(seed)
    for region in wd.REGIONS:
        gates = [
            k for k, v in world.edges.items()
            if v == "open" and {world.hexes[k[0]].region, world.hexes[k[1]].region} == {wd.HEARTLAND, region}
        ]
        assert len(gates) == 1


def test_biomes_belong_to_their_region_and_ring():
    world = wd.generate(3)
    for b in world.hexes.values():
        assert any(name == b.biome and lo <= b.ring <= hi for name, lo, hi in wd.BIOMES[b.region])
