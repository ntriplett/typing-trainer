"""Wanderpaw phase 3 (PLAN.md 11n): gates, places, quests, temples, the ending."""

import pytest

from pathlib import Path

from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app.wanderpaw import save as sv
from app.wanderpaw import story as st
from app.wanderpaw import world as wd

SEED = 11
WORLD = wd.generate(SEED)


@pytest.fixture(autouse=True)
def no_creatures(monkeypatch):
    """These tests aren't about wild creatures (test_wanderpaw_battle.py is)."""
    monkeypatch.setattr(sv.cr, "at", lambda *a: {})


def _team(*kinds, lv=5):
    """Starters of these types at a level (all five by default)."""
    return [wp.starter(k, lv) for k in kinds or wd.REGIONS]


def _trip(**changes):
    return {**sv.start_trip({**sv.new_save(SEED), "team": _team()}), **changes}


def _at(save, big, spot):
    return {**save, "at": list(big), "spot": list(spot)}


def _beside(local, h):
    """A standable hex next to h (inside the map)."""
    return next(n for n in hx.neighbors(h) if n in lc.CELL_SET and local.walkable(n))


def _find_gate(kind=None, level=None):
    for big in WORLD.hexes:
        local = lc.generate(SEED, big)
        for h, edge in sorted(local.gates.items()):
            gate = WORLD.gates[edge]
            if gate.kind != "quest" and (kind is None or gate.kind == kind) and (level is None or gate.level == level):
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
    big, local, h, gate = _find_gate(level=3)
    save = _at(_trip(), big, _beside(local, h))
    after = sv.apply_walk(save, h)
    assert after["spot"] == list(h)
    assert sv.cleared(after, local.gates[h])
    assert after["trip"]["energy"] == save["trip"]["energy"] - st.GATE_ENERGY - 1
    assert "cleared" in [e["kind"] for e in after["events"]]
    # without the type it's a no
    with pytest.raises(sv.WanderError, match="It takes 3 .* levels"):
        sv.apply_walk({**save, "team": _team(*(t for t in wd.REGIONS if t != gate.kind))}, h)


def test_gates_count_type_levels():
    big, local, h, gate = _find_gate(level=wd.TEMPLE_LEVEL)
    save = _at(_trip(), big, _beside(local, h))
    with pytest.raises(sv.WanderError, match="you have 5"):
        sv.apply_walk(save, h)  # one pet at level 5 isn't enough
    assert sv.apply_walk({**save, "team": _team(gate.kind, gate.kind, lv=7)}, h)["spot"] == list(h)  # two pets add up
    assert sv.apply_walk({**save, "team": _team(gate.kind, lv=wd.TEMPLE_LEVEL)}, h)["spot"] == list(h)


def test_a_cleared_gate_leads_on():
    big, local, h, gate = _find_gate(level=3)
    save = sv.apply_walk(_at(_trip(), big, _beside(local, h)), h)
    d = local.exits[h]
    f = next(f for e, f in lc.exit_pairs(SEED, big, hx.neighbor(big, d), 1) if e == h)
    g, c = lc.to_world(hx.neighbor(big, d), f), lc.center(big)
    on = sv.apply_walk(save, (g[0] - c[0], g[1] - c[1]))
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
    save = sv._spend(save, 60)
    fed = sv.act(save, "inn")
    assert fed["trip"]["energy"] == save["trip"]["energy"] + st.INN_ENERGY
    with pytest.raises(sv.WanderError):
        sv.act(fed, "inn")

    big, local, h = _find_poi("shrine")
    save = _at(_trip(), big, h)
    save = sv._spend(save, 60)
    assert sv.screen(save)["line"]
    prayed = sv.act(save, "shrine", accuracy=0.6)
    assert prayed["trip"]["energy"] == save["trip"]["energy"] + round(st.SHRINE_ENERGY * 0.6)


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


def test_temples_want_the_key_and_a_pet_of_their_type():
    region = "splash"
    tale = st.STORIES[region]
    temple = WORLD.temples()[region]
    local = lc.generate(SEED, temple)
    door = next(h for h, kind in local.tiles.items() if kind == "temple")
    save = _at(_trip(), temple, door)
    assert sv.screen(save)["action"] is None  # no key
    keyed = {**save, "items": {tale.key: 1}}
    assert sv.screen({**keyed, "team": _team("leaf")})["action"] is None  # no splash pet
    assert sv.screen(keyed)["action"] == "boss"  # its Keeper first
    with pytest.raises(sv.WanderError):
        sv.act(keyed, "temple")
    assert sv.act(keyed, "boss")["battle"]["tier"] == "boss"
    keyed = {**keyed, "bosses": [region], "letters": {region: 3}}
    opened = sv.act(keyed, "temple")
    assert region in opened["temples"]
    assert opened["items"][tale.relic] == 1
    assert opened["buffs"][region] == tale.buff
    assert sv.screen(opened)["action"] == "keeper_talk"  # a friend now


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
    assert fitted["party"] is None and len(fitted["team"]) == 5 and fitted["items"] == {} and fitted["version"] == sv.SAVE_VERSION


def test_type_names_in_text_are_tokens_for_the_page_to_style():
    """Words that mean a type say so ("{ember}"); a thing that happens to be
    called that doesn't (the Sun Ember, dreaming big)."""
    import re

    from app.wanderpaw import battle as bt
    from app.wanderpaw import pets as wp
    from app.wanderpaw import story as st

    assert st.TYPE_NAMES["ember"] == "{ember}"
    assert st.fill("It takes {need} {ember} levels for {item}.", need=3, item="a nut") == "It takes 3 {ember} levels for a nut."
    assert st.fill("{item}", item="{leaf}") == "{leaf}"
    bare = re.compile(r"\b(Ember|Splash|Leaf|Dream|Shock) (levels|lands|friend|pet|attack|Temple)\b")
    source = (Path(st.__file__)).read_text() + Path(bt.__file__).read_text()
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    assert not bare.findall(code)
    for member in (wp.starter("ember", 3), {**wp.starter("ember", 3), "types": {"ember": 3, "leaf": 1}}):
        for focus in (None, *bt.FOCUSES):
            for m in bt.described_moves({**member, "focus": focus}) + bt.moves({**member, "focus": focus}, "dream"):
                for text in (m["label"], m["note"]):
                    assert not re.search(r"\b(Ember|Splash|Leaf|Shock|ember|splash|leaf|shock)\b(?!\})", re.sub(r"\{\w+\}", "", text)), text


def test_each_relic_makes_gates_two_levels_harder():
    save = sv.start_trip(sv.new_save(5))
    world = sv.world_of(save)
    edge, gate = next((e, g) for e, g in world.gates.items() if g.kind != "quest" and g.level == wd.TEMPLE_LEVEL)
    assert gate.level == 13
    big = edge[0]
    local = sv.local_of(save, big)
    h = next(h for h, e in local.gates.items() if e == edge)
    team = lambda n: [{**wp.starter(gate.kind, 1), "id": 1, "types": {gate.kind: n}}]  # noqa: E731
    assert sv._try_gate({**save, "team": team(13)}, local, h)["cleared"]  # no relics: 13 will do
    two = {**save, "temples": ["ember", "leaf"]}
    assert sv.gate_level(two, gate.level) == 17
    with pytest.raises(sv.WanderError, match="17"):
        sv._try_gate({**two, "team": team(16)}, local, h)
    assert sv._try_gate({**two, "team": team(17)}, local, h)["cleared"]
    # the map shows what it takes now
    shown = {**two, "visited": [list(big)]}
    assert any(e.get("gate") and e["gate"]["kind"] == gate.kind and e["gate"]["level"] == 17 for e in sv.big_view(shown)["edges"])


def test_a_gate_you_already_cleared_stays_cleared_when_relics_come_out():
    save = sv.start_trip(sv.new_save(5))
    world = sv.world_of(save)
    edge = next(e for e, g in world.gates.items() if g.kind != "quest")
    done = {**save, "cleared": [sv._edge_id(edge)], "temples": ["ember", "leaf", "dream"]}
    assert sv.cleared(done, edge)
