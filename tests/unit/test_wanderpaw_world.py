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
    assert 95 <= len(world.hexes) <= 127
    assert world.hexes[(0, 0)].special == "camp"
    assert sum(b.special == "final" for b in world.hexes.values()) == 1
    assert all(b.region == wd.HEARTLAND for b in world.hexes.values() if b.ring <= wd.HEARTLAND_RADIUS)
    assert len({b.name for b in world.hexes.values()}) == len(world.hexes)


@pytest.mark.parametrize("seed", SEEDS)
def test_regions_are_one_piece_with_one_town(seed):
    world = wd.generate(seed)
    for region in wd.REGIONS:
        cells = [h for h, b in world.hexes.items() if b.region == region]
        assert len(wd._components(cells)) == 1
        assert sum(world.hexes[h].special == "town" for h in cells) == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_everything_reachable_but_you_have_to_weave(seed):
    world = wd.generate(seed)
    dist = wd.distances_from(world, (0, 0), _before_shortcuts)
    assert set(dist) == set(world.hexes)
    walls = [k for k, v in world.edges.items() if v != "open"]
    assert len(walls) > len(world.edges) / 3
    assert all(v in {"open", "river", "cliff", "thicket", "rocks"} for v in world.edges.values())


def _before_shortcuts(key, gate):
    return gate.kind != "quest"


def _gate(world, a, b):
    return world.gates.get(hx.edge_key(a, b))


def _has(needs, kind, level):
    """Every way in takes at least `level` of `kind`."""
    return all(n.get(kind, 0) >= level for n in needs)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_gate_rules(seed):
    world = wd.generate(seed)
    shut = wd.gate_needs(world, (0, 0), False)
    both = wd.gate_needs(world, (0, 0), True)
    steps = wd.distances_from(world, (0, 0))
    # 1. the heartland is free
    assert all(shut[h] == [{}] for h, b in world.hexes.items() if b.region == wd.HEARTLAND)
    for region in wd.REGIONS:
        strong, weak = wd.strong_against(region), wd.weak_against(region)
        cells = [h for h, b in world.hexes.items() if b.region == region]
        # 2. one way in from the heartland, behind 2 of the region's type
        ways_in = [(a, b) for a in cells for b in world.exits(a) if world.hexes[b].region == wd.HEARTLAND]
        assert len(ways_in) == 1 and _gate(world, *ways_in[0]) == wd.Gate(region, wd.ENTRY_LEVEL)
        assert all(_has(shut[h], region, wd.ENTRY_LEVEL) for h in cells)
        # 3-5. the temple: one neighbor, behind 8 of its own type there, and 3
        # of the type it's strong against, even with every shortcut open
        temple = world.temples()[region]
        assert world.hexes[temple].region == region
        assert len(world.exits(temple)) == 1
        assert _gate(world, temple, world.exits(temple)[0]) == wd.Gate(region, wd.TEMPLE_LEVEL)
        assert _has(both[temple], region, wd.TEMPLE_LEVEL) and _has(both[temple], strong, wd.SPLIT_LEVEL)
        assert steps[temple] >= wd.TEMPLE_MIN_STEPS
        # 6. the town: 3-5 out, behind 3 of the region's type, not behind the split
        town = world.quests[region].town
        assert wd.TOWN_RINGS[0] <= world.hexes[town].ring <= wd.TOWN_RINGS[1]
        assert any(_gate(world, town, n) == wd.Gate(region, wd.TOWN_LEVEL) for n in world.exits(town))
        assert any(strong not in n for n in shut[town])
        # 7. about half the region (the temple's side) behind 3 of the strong-against type
        split = [h for h in cells if _has(shut[h], strong, wd.SPLIT_LEVEL)]
        assert wd.SPLIT_SHARE[0] * len(cells) <= len(split) <= wd.SPLIT_SHARE[1] * len(cells)
        # 8. maybe a pocket of 1-2 behind 3 of the weak-against type
        pocket = [h for h in cells if _has(shut[h], weak, wd.POCKET_LEVEL)]
        assert len(pocket) <= wd.POCKET_SIZE[1]
        # 9. the shortcut cuts the border to the next region, between two
        # places that each take exactly one 3 and no 8; its quest checks both 3s
        a, b = world.quests[region].shortcut
        assert {world.hexes[a].region, world.hexes[b].region} == {region, strong}
        gate = world.gates[(a, b)]
        assert gate.kind == "quest" and gate.region == region and gate.level == 3
        for h, t in zip((a, b), gate.types):
            (need,) = shut[h]
            assert list(need.values()).count(3) == 1 and need[t] == 3 and 8 not in need.values()
    for key in world.gates:
        assert world.edges[key] == "open"


@pytest.mark.parametrize("seed", SEEDS)
def test_quests(seed):
    world = wd.generate(seed)
    before = wd.distances_from(world, (0, 0), _before_shortcuts)
    assert set(world.quests) == set(wd.REGIONS)
    for region, q in world.quests.items():
        assert world.hexes[q.town].special == "town" and world.hexes[q.town].region == region
        assert q.town in before  # reachable before the shortcut
        assert all(world.hexes[h].region == region and not world.hexes[h].special for h in q.pocket)


def test_rerolls_stay_rare():
    counts = [len(wd.generate(seed).rerolls) for seed in SEEDS]
    assert sum(counts) / len(counts) < 5


def test_biomes_belong_to_their_region_and_ring():
    world = wd.generate(3)
    for b in world.hexes.values():
        assert any(name == b.biome and lo <= b.ring <= hi for name, lo, hi in wd.BIOMES[b.region])


def test_gate_needs_track_type_levels_to_each_place():
    for seed in range(5):
        world = wd.generate(seed)
        shut = wd.gate_needs(world, (0, 0), False)
        both = wd.gate_needs(world, (0, 0), True)
        assert shut[(0, 0)] == [{}]
        # everything is reachable with enough levels, shortcuts or not
        assert set(shut) == set(both) == set(world.hexes)
        levels = {g.level for g in world.gates.values() if g.kind != "quest"}
        for h, needs in shut.items():
            # no need beats another on every type
            for a in needs:
                assert all(v in levels for v in a.values())
                assert not any(b != a and all(b.get(t, 0) <= a.get(t, 0) for t in wd.REGIONS) for b in needs)
            # open shortcuts never make a place harder
            best = min(sum(n.values()) for n in needs)
            assert min(sum(n.values()) for n in both[h]) <= best
