"""Wanderpaw phase 3 (PLAN.md 11n): gates, places, quests, temples, the ending."""

import pytest

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import save as sv
from app.wanderpaw import story as st
from app.wanderpaw import world as wd

SEED = 11
WORLD = wd.generate(SEED)


def _trip(**changes):
    return {**sv.start_trip(sv.new_save(SEED)), **changes}


def _at(save, big, spot):
    return {**save, "at": list(big), "spot": list(spot)}


def _beside(local, h):
    """A standable hex next to h (inside the map)."""
    return next(n for n in hx.neighbors(h) if n in lc.CELL_SET and local.walkable(n))


def _find_gate(kind=None, need=None):
    for big in WORLD.hexes:
        local = lc.generate(SEED, big)
        for h, edge in sorted(local.gates.items()):
            gate = WORLD.gates[edge]
            if gate.kind != "quest" and (kind is None or gate.kind == kind) and (need is None or gate.need == need):
                return big, local, h, gate
    raise LookupError


def _find_poi(kind):
    for big in WORLD.hexes:
        local = lc.generate(SEED, big)
        for h, poi in sorted(local.pois.items()):
            if poi == kind:
                return big, local, h
    raise LookupError


# --- gates -----------------------------------------------------------------------


def test_a_field_skill_clears_a_gate_for_good():
    big, local, h, gate = _find_gate(need=1)
    save = _at(_trip(), big, _beside(local, h))
    after = sv.apply_walk(save, h)
    assert after["spot"] == list(h)
    assert sv.cleared(after, local.gates[h])
    assert after["trip"]["energy"] == save["trip"]["energy"] - st.GATE_ENERGY - 1
    assert "cleared" in [e["kind"] for e in after["events"]]
    # without the type it's a no
    with pytest.raises(sv.WanderError, match="You need a"):
        sv.apply_walk({**save, "party": [t for t in save["party"] if t != gate.kind]}, h)


def test_two_pet_gates_need_two():
    big, local, h, gate = _find_gate(need=2)
    save = _at(_trip(), big, _beside(local, h))
    with pytest.raises(sv.WanderError, match="two"):
        sv.apply_walk(save, h)
    assert sv.apply_walk({**save, "party": [gate.kind, gate.kind]}, h)["spot"] == list(h)


def test_a_cleared_gate_leads_on():
    big, local, h, gate = _find_gate(need=1)
    save = sv.apply_walk(_at(_trip(), big, _beside(local, h)), h)
    d = local.exits[h]
    on = sv.apply_walk(save, hx.neighbor(h, d))
    assert on["at"] == list(hx.neighbor(big, d))
    # and from the far side, the same gate is open
    assert sv.standable(on, sv.local_of(on), tuple(on["spot"]))


# --- places --------------------------------------------------------------------


def test_forage_once_per_trip():
    big, local, h = _find_poi("forage")
    save = _at(_trip(), big, _beside(local, h))
    got = sv.apply_walk(save, h)
    item = st.FORAGE[WORLD.hexes[big].region]
    assert got["items"][item] == 1
    back = sv.apply_walk(sv.apply_walk(got, tuple(save["spot"])), h)
    assert back["items"][item] == 1
    fresh = sv.start_trip({**back, "trip": None})
    assert sv.apply_walk(_at(fresh, big, tuple(save["spot"])), h)["items"][item] == 2


def test_chests_open_once_ever_and_pay():
    big, local, h = _find_poi("chest")
    save = _at(_trip(), big, _beside(local, h))
    got = sv.apply_walk(save, h)
    coins = [e for e in got["events"] if e["kind"] == "coins"]
    assert coins and coins[0]["amount"] >= st.CHEST_COINS[0]
    again = sv.apply_walk(sv.apply_walk(got, tuple(save["spot"])), h)
    assert not [e for e in again["events"] if e["kind"] == "coins"]
    assert all(t.get("poi") != "chest" or (t["q"], t["r"]) != h for t in sv.local_view(again)["tiles"])


def test_inn_and_shrine_give_energy_once_per_trip():
    for big in WORLD.hexes:
        local = lc.generate(SEED, big)
        inn = next((h for h, role in local.buildings.items() if role == "inn"), None)
        if inn:
            break
    save = _at(_trip(), big, inn)
    save = {**save, "trip": {**save["trip"], "energy": 50}}
    fed = sv.act(save, "inn")
    assert fed["trip"]["energy"] == 50 + st.INN_ENERGY
    with pytest.raises(sv.WanderError):
        sv.act(fed, "inn")

    big, local, h = _find_poi("shrine")
    save = _at(_trip(), big, h)
    save = {**save, "trip": {**save["trip"], "energy": 50}}
    assert sv.screen(save)["line"]
    prayed = sv.act(save, "shrine", accuracy=0.6)
    assert prayed["trip"]["energy"] == 50 + round(st.SHRINE_ENERGY * 0.6)


def test_side_quest_at_the_board_resets_each_trip():
    for big in WORLD.hexes:
        local = lc.generate(SEED, big)
        board = next((h for h, role in local.buildings.items() if role == "board"), None)
        if board:
            break
    item = st.FORAGE[WORLD.hexes[big].region]
    save = _at(_trip(), big, board)
    taken = sv.act(save, "board")
    assert sv.screen(taken)["action"] is None  # not enough yet
    rich = {**taken, "items": {item: 4}}
    paid = sv.act(rich, "board")
    assert paid["items"][item] == 1
    assert paid["events"][0]["amount"] == st.SIDE_QUEST_COINS
    # a new trip forgets a job you took
    again = sv.start_trip({**sv.act(save, "board"), "trip": None})
    assert _at(again, big, board)["trip"]["side"] == {}


# --- the story -------------------------------------------------------------------


def _quest_places(region):
    q = WORLD.quests[region]
    town = lc.generate(SEED, q.town)
    elder = next(h for h, role in town.buildings.items() if role == "elder")
    lost = lc.generate(SEED, q.lost)
    spot = next(h for h, poi in lost.pois.items() if poi == "lost")
    return q, elder, lost, spot


def test_a_story_quest_from_ask_to_shortcut():
    region = "leaf"
    tale = st.STORIES[region]
    q, elder, lost, spot = _quest_places(region)
    save = _at(_trip(), q.town, elder)
    assert sv.screen(save)["action"] == "ask"
    save = sv.act(save, "ask")
    assert save["quests"][region] == "asked"
    assert list(q.lost) in sv.big_view(save)["marks"]
    # the shortcut is a quest gate: broken until the quest is done
    side = lc.generate(SEED, q.shortcut[0])
    gate = next(h for h, e in side.gates.items() if e == q.shortcut)
    with pytest.raises(sv.WanderError, match="broken"):
        sv.apply_walk(_at(save, q.shortcut[0], _beside(side, gate)), gate)
    # find the lost thing
    found = sv.apply_walk(_at(save, q.lost, _beside(lost, spot)), spot)
    assert found["items"][tale.lost] == 1
    # bring it back
    home = _at(found, q.town, elder)
    assert sv.screen(home)["action"] == "give"
    done = sv.act(home, "give")
    assert done["quests"][region] == "done"
    assert done["items"][tale.key] == 1 and not done["items"][tale.lost]
    walked = sv.apply_walk(_at(done, q.shortcut[0], _beside(side, gate)), gate)
    assert walked["spot"] == list(gate)


def test_temples_want_the_key_and_a_pet_of_their_type():
    region = "splash"
    tale = st.STORIES[region]
    temple = WORLD.temples()[region]
    local = lc.generate(SEED, temple)
    door = next(h for h, kind in local.tiles.items() if kind == "temple")
    save = _at(_trip(), temple, door)
    assert sv.screen(save)["action"] is None  # no key
    keyed = {**save, "items": {tale.key: 1}}
    assert sv.screen({**keyed, "party": ["leaf"]})["action"] is None  # no splash pet
    opened = sv.act(keyed, "temple")
    assert region in opened["temples"]
    assert opened["items"][tale.relic] == 1
    assert opened["charms"] == 1 and opened["buffs"][region] == tale.buff
    assert sv.screen(opened)["action"] is None


def test_the_heartstone_wants_all_five_relics():
    final = next(b.coord for b in WORLD.hexes.values() if b.special == "final")
    local = lc.generate(SEED, final)
    stone = next(h for h, kind in local.tiles.items() if kind == "stone")
    save = _at(_trip(), final, stone)
    assert sv.screen(save)["action"] is None
    ready = {**save, "temples": list(wd.REGIONS)}
    done = sv.act(ready, "heartstone")
    assert done["finished"]
    assert sv.view(done)["credits"] == st.CREDITS
    assert sv.screen(done)["action"] == "credits"


def test_old_saves_fit():
    old = {"version": 2, "world_version": wd.WORLD_VERSION, "seed": SEED, "at": [0, 0], "spot": [0, 0],
           "visited": [[0, 0]], "seen": {}, "trip": None, "note": None}
    fitted = sv.fit(old)
    assert fitted["party"] == sv.STAND_IN_PARTY and fitted["items"] == {} and fitted["version"] == sv.SAVE_VERSION
