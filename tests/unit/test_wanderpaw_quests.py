"""Wanderpaw's quests: two quest-givers per bridge, bridge parts, lost
things in pockets and nooks, training a pet, key rumors (PLAN.md 11n)."""

import pytest

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app.wanderpaw import quests as qs
from app.wanderpaw import save as sv
from app.wanderpaw import story as st
from app.wanderpaw import world as wd

SEED = 102
WORLD = wd.generate(SEED)
PLAN = qs.plan(SEED)


def _team(*kinds, lv=5):
    return [wp.starter(k, lv) for k in kinds or wd.REGIONS]


def _trip(team=None):
    return sv.start_trip({**sv.new_save(SEED), "team": team or _team()})


def _at(save, big, spot):
    return sv._see({**save, "at": list(big), "spot": list(spot)}, big, spot)


def _beside(big, h):
    local = lc.generate(SEED, big)
    return next(n for n in hx.neighbors(h) if n in lc.CELL_SET and local.walkable(n) and n not in local.nooks)


def _visit(save, g):
    return _at(save, g.town, g.house)


def _pair(shortcut):
    """The two quest-givers about one bridge."""
    return sorted((g for g in PLAN.givers.values() if g.shortcut == shortcut), key=lambda g: g.id)


def _fetch(save, g):
    """Go get g's lost thing (walking up, or searching its nook)."""
    if g.lost.check:
        here = _at(save, g.lost.big, g.lost.at)
        return sv.act(here, "fetch", arg=g.id)
    return sv.apply_walk(_at(save, g.lost.big, _beside(g.lost.big, g.lost.at)), g.lost.at)


def _bump(save, shortcut, side):
    """Walk into the broken bridge from big hex `side`."""
    edge = WORLD.quests[shortcut].shortcut
    wall = lc.wall_side(SEED, *edge)
    local = lc.generate(SEED, wall)
    gate = next(h for h, e in local.gates.items() if e == edge)
    if side == wall:
        return sv.apply_walk(_at(save, wall, _beside(wall, gate)), gate)
    d = hx.direction_to(side, wall)
    near = next(h for h, f in lc.exit_pairs(SEED, side, wall, 1) if f == gate)
    c = lc.center(side)
    g = lc.to_world(wall, gate)
    return sv.apply_walk(_at(save, side, near), (g[0] - c[0], g[1] - c[1]))


def test_every_town_has_two_quest_givers_one_per_bridge():
    for region in wd.REGIONS:
        here = [g for g in PLAN.givers.values() if g.region == region]
        assert sorted(g.shortcut for g in here) == sorted(qs.givers_in(region))
        town = lc.generate(SEED, WORLD.quests[region].town)
        for g in here:
            assert town.buildings[g.house] == g.role
    for shortcut in wd.REGIONS:
        a, b = _pair(shortcut)
        sides = {WORLD.hexes[h].region for h in WORLD.quests[shortcut].shortcut}
        assert {a.region, b.region} == sides  # one in the town on each side


@pytest.mark.parametrize("seed", range(8))
def test_lost_things_hide_in_the_pocket_or_a_nook_that_takes_3(seed):
    world, plan = wd.generate(seed), qs.plan(seed)
    spots = set()
    for g in plan.givers.values():
        spot = g.lost
        assert world.hexes[spot.big].region == g.region
        assert (spot.big, spot.at) not in spots
        spots.add((spot.big, spot.at))
        local = lc.generate(seed, spot.big)
        if spot.kind == "pocket":
            assert spot.big in world.quests[g.region].pocket and spot.check is None and local.walkable(spot.at)
        elif spot.kind != "ground":
            assert local.nooks[spot.at].kind == spot.kind and spot.check == (lc.NOOK_SKILL[spot.kind], 3)
    for region, key in plan.keys.items():
        assert world.hexes[key.big].region == region and (key.big, key.at) not in spots


def test_the_first_quest_giver_you_help_mends_the_bridge_the_other_trains():
    a, b = _pair("splash")
    save = _trip()
    fix_a, fix_b = (st.NPCS[(g.region, g.shortcut)].fix for g in (a, b))
    assert fix_a != fix_b  # each says how they'd fix it, their own way
    assert fix_a in sv.screen(_visit(save, a))["text"] and fix_b in sv.screen(_visit(save, b))["text"]
    fix = fix_a
    save = sv.act(_visit(save, b), "ask")
    assert save["menders"] == {"splash": b.id} and save["quests"][b.id] == "asked"
    pitch = sv.screen(_visit(save, a))
    assert pitch["action"] == "ask" and "level" in pitch["text"] and fix not in pitch["text"]
    assert len(sv.quests_view(save)) == 1 and sv.quests_view(save)[0]["title"].startswith("Mend")


def test_mending_a_bridge_takes_the_lost_thing_and_a_part_from_each_side():
    a, _ = _pair("splash")
    edge = WORLD.quests["splash"].shortcut
    near_side = next(h for h in edge if WORLD.hexes[h].region == a.region)
    far_side = next(h for h in edge if h != near_side)
    far_type = WORLD.gates[edge].types[edge.index(far_side)]
    near, far = sv._parts(_trip(), "splash", a.region)
    # without the far side's type, only this side's part
    weak = [t for t in wd.REGIONS if t != far_type]
    save = sv.act(_visit(_trip(_team(*weak)), a), "ask")
    bumped = _bump(save, "splash", near_side)
    assert bumped["items"].get(near) and not bumped["items"].get(far)
    assert "far side" in bumped["events"][0]["text"]
    assert bumped["bridges"] == {"splash": "found"}
    # with it, a pet brings the far part across
    strong = sv.act(_visit(_trip(), a), "ask")
    both = _bump(strong, "splash", near_side)
    assert both["items"].get(near) and both["items"].get(far)
    # and the lost thing
    assert sv.screen(_visit(both, a))["action"] is None
    ready = _fetch(both, a)
    assert ready["items"].get(st.NPCS[(a.region, a.shortcut)].lost)
    shown = sv.screen(_visit(ready, a))
    assert shown["action"] == "mend"
    done = sv.act(_visit(ready, a), "mend")
    assert sv.cleared(done, edge) and done["quests"][a.id] == "done"
    assert not any(done["items"].get(x) for x in (near, far))


def test_walking_round_to_the_far_side_gets_its_part_too():
    a, _ = _pair("splash")
    edge = WORLD.quests["splash"].shortcut
    far_side = next(h for h in edge if WORLD.hexes[h].region != a.region)
    far_type = WORLD.gates[edge].types[edge.index(far_side)]
    save = _trip(_team(*(t for t in wd.REGIONS if t != far_type)))
    there = _bump(save, "splash", far_side)
    _, far = sv._parts(save, "splash", a.region)
    assert there["items"].get(far)


def test_the_trainer_levels_up_the_pet_you_pick():
    a, b = _pair("ember")
    real = {"id": 7, "name": "Rusty", "species": "fox", "xp": 0, "types": {"ember": 1}, **wp.stats("fox", wp.STARTER_STATS, wp.Record())}
    save = sv.act(_visit(_trip([real, *_team("splash")]), a), "ask")  # a mends
    save = sv.act(_visit(save, b), "ask")  # b trains
    assert sv.screen(_visit(save, b))["action"] is None  # not found yet
    found = _fetch(save, b)
    shown = sv.screen(_visit(found, b))
    assert [o["arg"] for o in shown["options"]] == [7]
    trained = sv.act(_visit(found, b), "train", arg=7)
    assert trained["quests"][b.id] == "done"
    assert [e for e in trained["events"] if e["kind"] == "train"][0]["pet"] == 7
    with pytest.raises(sv.WanderError):
        sv.act(_visit(found, b), "train", arg=99)


def test_finishing_a_quest_brings_a_key_rumor():
    _, b = _pair("ember")
    save = sv.act(_visit(_trip(), b), "ask")
    save = {**_fetch(save, b), "menders": {"ember": "someone else"}}
    save = {**save, "quests": {**save["quests"], b.id: "done"}}
    shown = sv.screen(_visit(save, b))
    assert shown["action"] == "rumor"
    told = sv.act(_visit(save, b), "rumor")
    key = PLAN.keys[b.region]
    assert b.region in told["rumors"] and list(key.big) in sv.big_view(told)["marks"]
    name = st.STORIES[b.region].key
    assert name in told["events"][0]["text"]
    # and it's there, behind 3 of the nook's type
    got = sv.act(_at(told, key.big, key.at), "fetch", arg=f"key:{b.region}")
    assert got["items"][name] == 1
    weak = {**told, "team": _team(*(t for t in wd.REGIONS if t != key.check[0]))}
    assert not any(o.get("arg") == f"key:{b.region}" for o in sv.screen(_at(weak, key.big, key.at)).get("options", []))


def test_townsfolk_point_you_to_the_quest_giver():
    a, _ = _pair("splash")
    edge = WORLD.quests["splash"].shortcut
    side = next(h for h in edge if WORLD.hexes[h].region == a.region)
    save = _bump(_trip(), "splash", side)
    town = lc.generate(SEED, a.town)
    house = next(h for h, role in town.buildings.items() if role in ("inn", "shop", "house"))
    shown = sv.screen(_at(save, a.town, house))
    assert shown["action"] == "ask_bridge"
    told = sv.act(_at(save, a.town, house), "ask_bridge")
    assert st.NPCS[(a.region, a.shortcut)].name in told["events"][0]["text"]
