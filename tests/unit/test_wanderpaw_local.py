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


def test_big_hexes_tile_one_world_grid():
    found = {}
    for big in hx.spiral((0, 0), 3):
        for h in lc.CELLS:
            g = lc.to_world(big, h)
            assert g not in found
            found[g] = (big, h)
            assert lc.owner(g) == (big, h)
    # no gaps: everything near the middle is owned
    assert all(g in found for g in hx.spiral((0, 0), 20))


def test_sides_face_their_neighbors():
    for d in range(6):
        assert len(lc.SIDE_CELLS[d]) == 6
        for h, f in lc.SIDES[d]:
            assert lc.owner(lc.to_world((0, 0), h)) == ((0, 0), h)
            assert lc.owner(hx.add(lc.center(hx.DIRECTIONS[d]), f)) == (hx.DIRECTIONS[d], f)
            assert hx.distance(lc.to_world((0, 0), h), lc.to_world(hx.DIRECTIONS[d], f)) == 1


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
            facing = [f for e, f in lc.SIDES[d] if e == h]
            assert any(far.exits.get(f) == (d + 3) % 6 for f in facing), (seed, big, h)


def test_open_sides_have_exits_and_walled_sides_are_solid():
    for seed, big, local in _maps():
        world = wd.generate(seed)
        for d in range(6):
            n = hx.neighbor(big, d)
            side = lc.SIDE_CELLS[d]
            if n in world.hexes and world.is_open(big, n):
                assert any(local.exits.get(h) == d for h in side)
            elif n not in world.hexes or lc.wall_side(seed, big, n) == big:
                assert not any(local.walkable(h) for h in side)  # the wall, one hex thick
            else:
                far = lc.generate(seed, n)  # the wall's on their side: no way across
                assert not any(local.walkable(h) and far.walkable(f) for h, f in lc.SIDES[d])


def test_feels_differ():
    share = defaultdict(list)
    for _, _, local in _maps():
        share[local.style].append(sum(local.walkable(h) for h in lc.CELLS) / len(lc.CELLS))
    mean = {k: statistics.mean(v) for k, v in share.items()}
    assert mean["open"] > 0.65
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


def test_gates_sit_in_exits_and_lead_inside():
    for seed, big, local in _maps():
        world = wd.generate(seed)
        for h, edge in local.gates.items():
            assert h in local.exits and edge in world.gates
            assert local.tiles[h] == lc.GATE_TILES[world.gates[edge].kind]
            assert any(local.walkable(n) for n in hx.neighbors(h) if n in lc.CELL_SET)


def test_pois_and_building_roles():
    for seed, big, local in _maps():
        world = wd.generate(seed)
        assert all(local.walkable(h) and h not in local.exits for h in local.pois)
        if world.hexes[big].special == "town":
            roles = set(local.buildings.values())
            assert {"board", "inn", "shop"} <= roles
            region = world.hexes[big].region
            assert {f"quest:{region}", f"quest:{wd.weak_against(region)}"} <= roles


def test_beyond_is_the_ring_around():
    for seed, big, local in _maps():
        world = wd.generate(seed)
        past = lc.beyond(seed, big)
        assert len(past) == 36
        for b in past:
            far = tuple(b["big"])
            if far in world.hexes:
                assert b["kind"] == lc.generate(seed, far).tiles[tuple(b["at"])]
            else:
                assert b["kind"] == lc.EDGE_OF_WORLD


def test_nooks_sit_where_they_belong():
    kinds = defaultdict(int)
    for seed, big, local in _maps():
        main = lc.reachable(local.tiles, local.campfire)
        for h, nook in local.nooks.items():
            kinds[nook.kind] += 1
            assert nook.finds in lc.FINDS[nook.kind]
            assert h not in local.pois and h not in local.exits
            if nook.kind in lc.IN_WALL:
                # in a blocker, gone into from walkable doors beside it
                assert local.tiles[h] in lc.BLOCKED and nook.doors
                assert all(d in main and hx.distance(d, h) == 1 for d in nook.doors)
                assert len(nook.doors) == (2 if nook.kind == "tunnel" else 1)
            else:
                assert h in main and local.tiles[h] in lc.GROUND and not nook.doors
            if nook.need:
                assert nook.need[0] == lc.NOOK_SKILL[nook.kind] and 1 <= nook.need[1] <= 10
    # every kind turns up somewhere, and caves and glades often
    assert set(kinds) == set(lc.FINDS)
    assert kinds["cave"] >= 100 and kinds["glade"] >= 60


def test_tunnels_are_shortcuts():
    for seed, big, local in _maps():
        for h, nook in local.nooks.items():
            if nook.kind == "tunnel":
                assert lc._walk(local.tiles, *nook.doors) >= lc.TUNNEL_DETOUR


def test_clues_point_to_open_ground_nearby():
    for seed, big, local in list(_maps())[:200]:
        for h, nook in local.nooks.items():
            if "clue" in nook.finds:
                far, at = lc.clue_target(seed, big, h)
                assert hx.distance(far, big) <= 2
                m = lc.generate(seed, far)
                assert m.tiles[at] in lc.GROUND and at in lc.reachable(m.tiles, m.campfire)
                assert at not in m.nooks and at not in m.pois


@pytest.mark.parametrize("seed", range(4))
def test_the_heartstone_and_temples_are_great_halls(seed):
    world = wd.generate(seed)
    for big, b in world.hexes.items():
        if b.special not in ("final", "temple"):
            continue
        local = lc.generate(seed, big)
        heart = local.tiles[(0, 0)]
        assert heart == ("stone" if b.special == "final" else "temple")
        ring2 = [local.tiles[h] for h in hx.ring((0, 0), 2)]
        assert ring2.count("court") == 1  # one doorway in the walled ring
        assert ring2.count("colonnade") == 6
        if b.special == "final":
            assert sorted(k for k in ring2 if k.startswith("pillar_")) == sorted(f"pillar_{t}" for t in wd.REGIONS)
        else:
            assert sum(k == f"feature_{b.region}" for k in ring2 + [local.tiles[h] for h in hx.ring((0, 0), 1)]) == 7
        assert all(local.tiles[h] == "court" for h in hx.ring((0, 0), 3))
        # the heart is reached through the doorway
        assert (0, 0) in lc.reachable(local.tiles, local.campfire)
