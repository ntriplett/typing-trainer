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


@pytest.fixture(autouse=True)
def no_creatures(monkeypatch):
    """These tests aren't about wild creatures (test_wanderpaw_battle.py is)."""
    monkeypatch.setattr(sv.cr, "at", lambda *a: {})


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


def _actions(shown):
    return [o["action"] for o in shown["options"]]


def _ask(save, g, topic):
    return sv.act(_visit(save, g), "folk", arg=topic)


def _take(save, g):
    return sv.act(_ask(save, g, "help"), "ask")


def _returned(save, g):
    return sv.act(_visit(_fetch(_take(save, g), g), g), "give_back")


def test_a_quest_giver_only_says_hello_until_you_ask():
    a, _ = _pair("splash")
    npc = st.NPCS[(a.region, a.shortcut)]
    shown = sv.screen(_visit(_trip(), a))
    assert shown["text"] == npc.hello and npc.lost not in shown["text"]
    assert "ask" not in _actions(shown)
    asked = sv.screen(_ask(_trip(), a, "help"))
    assert npc.lost in asked["text"] and "ask" in _actions(asked)


def test_the_lost_thing_is_its_own_quest_and_earns_a_favor():
    a, _ = _pair("splash")
    npc = st.NPCS[(a.region, a.shortcut)]
    save = _take(_trip(), a)
    assert save["quests"][a.id] == "asked" and not save["menders"]  # no bridge in it
    assert [q["title"] for q in sv.quests_view(save)] == [f"{npc.name}'s {npc.lost}"]
    found = _fetch(save, a)
    assert "give_back" in _actions(sv.screen(_visit(found, a)))
    back = sv.act(_visit(found, a), "give_back")
    assert back["quests"][a.id] == "done" and not back["items"].get(npc.lost)
    assert sv.quests_view(back)[0]["done"]


def test_asking_about_a_bridge_first_still_starts_with_the_lost_thing():
    a, _ = _pair("splash")
    edge = WORLD.quests["splash"].shortcut
    side = next(h for h in edge if WORLD.hexes[h].region == a.region)
    save = _bump(_trip(), "splash", side)
    npc = st.NPCS[(a.region, a.shortcut)]
    assert "take_mend" not in _actions(sv.screen(_visit(save, a)))
    pitch = sv.screen(_ask(save, a, "bridge_first"))
    assert npc.fix in pitch["text"] and npc.lost in pitch["text"] and "ask" in _actions(pitch)


def test_the_journal_says_who_can_help_with_a_bridge_you_found():
    a, b = _pair("splash")
    edge = WORLD.quests["splash"].shortcut
    side = next(h for h in edge if WORLD.hexes[h].region == a.region)
    entry = sv.quests_view(_bump(_trip(), "splash", side))[0]
    assert st.NPCS[(a.region, a.shortcut)].name in entry["text"] and st.NPCS[(b.region, b.shortcut)].name in entry["text"]


def test_mending_a_bridge_is_a_separate_job_and_takes_a_part_from_each_side():
    a, b = _pair("splash")
    edge = WORLD.quests["splash"].shortcut
    near_side = next(h for h in edge if WORLD.hexes[h].region == a.region)
    far_side = next(h for h in edge if h != near_side)
    far_type = WORLD.gates[edge].types[edge.index(far_side)]
    near, far = sv._parts(_trip(), "splash", a.region)
    # without the far side's type, only this side's part
    weak = [t for t in wd.REGIONS if t != far_type]
    bumped = _bump(_trip(_team(*weak)), "splash", near_side)
    assert bumped["items"].get(near) and not bumped["items"].get(far)
    assert "far side" in bumped["events"][0]["text"]
    assert bumped["bridges"] == {"splash": "found"}
    # with it, a pet brings the far part across
    both = _bump(_trip(), "splash", near_side)
    assert both["items"].get(near) and both["items"].get(far)
    # the favor first, then the job, then it's mended
    done_favor = _returned(both, a)
    assert not sv.cleared(done_favor, edge)
    shown = sv.screen(_visit(done_favor, a))
    assert "take_mend" in _actions(shown) and "mend" not in _actions(shown)
    taken = sv.act(_visit(done_favor, a), "take_mend")
    assert taken["menders"] == {"splash": a.id}
    assert "Mend" in " ".join(q["title"] for q in sv.quests_view(taken))
    assert "mend" in _actions(sv.screen(_visit(taken, a)))
    done = sv.act(_visit(taken, a), "mend")
    assert sv.cleared(done, edge)
    assert not any(done["items"].get(x) for x in (near, far))
    # the other side's quest-giver won't take it on as well
    other = _returned(done, b)
    assert "take_mend" not in _actions(sv.screen(_visit(other, b)))


def test_a_giver_tells_you_what_parts_are_still_missing():
    a, _ = _pair("splash")
    edge = WORLD.quests["splash"].shortcut
    near_side = next(h for h in edge if WORLD.hexes[h].region == a.region)
    far_side = next(h for h in edge if h != near_side)
    far_type = WORLD.gates[edge].types[edge.index(far_side)]
    save = _bump(_trip(_team(*(t for t in wd.REGIONS if t != far_type))), "splash", near_side)
    taken = sv.act(_visit(_returned(save, a), a), "take_mend")
    near, far = sv._parts(save, "splash", a.region)
    text = sv.screen(_visit(taken, a))["text"]
    assert far.split(" for ")[0] in text and near.split(" for ")[0] not in text


def test_walking_round_to_the_far_side_gets_its_part_too():
    a, _ = _pair("splash")
    edge = WORLD.quests["splash"].shortcut
    far_side = next(h for h in edge if WORLD.hexes[h].region != a.region)
    far_type = WORLD.gates[edge].types[edge.index(far_side)]
    save = _trip(_team(*(t for t in wd.REGIONS if t != far_type)))
    there = _bump(save, "splash", far_side)
    _, far = sv._parts(save, "splash", a.region)
    assert there["items"].get(far)


def test_a_favor_can_train_the_pet_you_pick():
    a, b = _pair("ember")
    real = {"id": 7, "name": "Rusty", "species": "fox", "xp": 0, "types": {"ember": 1}, **wp.stats("fox", wp.STARTER_STATS, wp.Record()), "id": 7}
    save = _returned(_trip([real, *_team("splash")]), b)
    assert "train" not in _actions(sv.screen(_visit(save, b)))
    asked = _ask(save, b, "train")
    shown = sv.screen(_visit(asked, b))
    assert [o["arg"] for o in shown["options"] if o["action"] == "train"] == [7]
    trained = sv.act(_visit(asked, b), "train", arg=7)
    assert b.id in trained["trained"]
    assert [e for e in trained["events"] if e["kind"] == "train"][0]["pet"] == 7
    with pytest.raises(sv.WanderError):
        sv.act(_visit(asked, b), "train", arg=99)
    assert "train" not in {o.get("arg") for o in sv.screen(_visit(trained, b))["options"]}  # one favor


def test_finishing_a_quest_brings_a_key_rumor():
    _, b = _pair("ember")
    told = _returned(_trip(), b)
    key = PLAN.keys[b.region]
    assert b.region in told["rumors"] and list(key.big) in sv.big_view(told)["marks"]
    name = st.STORIES[b.region].key
    assert name in sv.screen(_visit(told, b))["text"]
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
    assert "bridge" in [o["arg"] for o in shown["options"]]
    told = sv.act(_at(save, a.town, house), "folk", arg="bridge")
    assert st.NPCS[(a.region, a.shortcut)].name in sv.screen(told)["text"]

