"""Wanderpaw's API: your world, trips, walking, and the admin lab (PLAN.md 11n)."""

import pytest
from fastapi.testclient import TestClient

from app import db, main
from app import pet_genes as g
from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app.wanderpaw import quests as qs
from app.wanderpaw import save as sv
from app.wanderpaw import world as wd

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    yield


def _seed():
    return client.get("/api/wander-lab/world").json()["seed"]


def test_pages_serve():
    assert client.get("/wanderpaw").status_code == 200
    assert client.get("/wander-lab").status_code == 200


def test_new_player_starts_at_camp_with_words():
    data = client.get("/api/wander").json()
    assert data["local"]["big"] == [0, 0] and data["local"]["spot"] == [0, 0]
    assert len(data["local"]["tiles"]) == 7
    assert data["trip"] is None
    assert set(data["words"]) == {"letter", "short", "medium", "long"} and len(data["words"]["short"]) >= 6
    assert all(len(s) == 3 and s[2] in ("letter", "short", "medium", "long") for s in data["local"]["steps"])
    assert client.get("/api/wander").json()["local"] == data["local"]


def test_trip_walk_and_end():
    local = lc.generate(_seed(), (0, 0))
    to = next(n for n in hx.neighbors((0, 0)) if local.walkable(n))
    assert client.post("/api/wander/walk", json={"q": to[0], "r": to[1]}).status_code == 400  # no trip yet
    data = client.post("/api/wander/trip/start", json={}).json()
    assert data["trip"]["energy"] == data["trip"]["max"]
    data = client.post("/api/wander/walk", json={"q": to[0], "r": to[1]}).json()
    assert data["local"]["spot"] == list(to)
    ended = client.post("/api/wander/trip/end").json()  # ends the day from anywhere
    assert ended["note"] == "rested" and ended["trip"] is None and ended["local"]["spot"] == [0, 0]


def test_next_day():
    data = client.post("/api/wander/day").json()
    assert data["trip"]["energy"] == data["trip"]["max"]


def test_lab_world_local_and_gallery():
    seed = _seed()
    mine = client.get("/api/wander-lab/world").json()
    assert mine["me"]["spot"] == [0, 0] and "0,0" in mine["me"]["seen"]
    local = client.get("/api/wander-lab/local", params={"seed": seed, "q": 0, "r": 0}).json()
    assert len(local["tiles"]) == 91 and local["campfire"] == [0, 0]
    assert client.get("/api/wander-lab/local", params={"seed": seed, "q": 40, "r": 40}).status_code == 404
    gallery = client.get("/api/wander-lab/gallery").json()
    assert len({g["biome"] for g in gallery}) >= 15


def test_lab_teleport_refill_and_reset():
    seed = _seed()
    world = wd.generate(seed)
    temple = next(b for b in world.hexes.values() if b.special == "temple")
    data = client.post("/api/wander-lab/teleport", json={"q": temple.coord[0], "r": temple.coord[1]}).json()
    assert data["me"]["at"] == list(temple.coord)
    assert data["me"]["spot"] == list(lc.generate(seed, temple.coord).campfire)
    local = lc.generate(seed, temple.coord)
    blocked = next(h for h in lc.CELLS if not local.walkable(h))
    res = client.post("/api/wander-lab/teleport", json={"q": temple.coord[0], "r": temple.coord[1], "spot": list(blocked)})
    assert res.status_code == 400
    assert client.post("/api/wander-lab/refill").json()["me"]["trip"]["energy"] > 0
    fresh = client.post("/api/wander-lab/reset", json={"seed": 1234}).json()
    assert fresh["seed"] == 1234 and fresh["me"]["at"] == [0, 0]


def test_going_in_and_party():
    seed = _seed()
    world = wd.generate(seed)
    g = qs.plan(seed).givers["leaf:leaf"]
    client.post("/api/wander/trip/start", json={})
    client.post("/api/wander-lab/teleport", json={"q": g.town[0], "r": g.town[1], "spot": list(g.house)})
    data = client.get("/api/wander").json()
    assert data["screen"]["action"] == "ask"
    data = client.post("/api/wander/act", json={"action": "ask"}).json()
    assert data["quests"][0]["title"].startswith("Mend")
    assert client.post("/api/wander/act", json={"action": "ask"}).status_code == 400


# --- pets (phase 4) -------------------------------------------------------------------


def _add_pet(species, seed=1):
    with db.open_db(main.DB_PATH) as conn:
        return db.add_v3_pet(conn, 1, g.roll(species, None, None, seed), species.capitalize(), "shop")


def test_your_pets_make_the_team():
    fox, bunny = _add_pet("fox"), _add_pet("bunny", 2)
    _add_pet("fish", 3)  # fish stay home
    data = client.get("/api/wander/pets").json()
    assert [p["id"] for p in data["pets"]] == [fox, bunny]
    assert data["pets"][0]["types"] == {"ember": 1} and data["pets"][0]["level"] == 1
    # never picked: your first pets go, starters fill the missing types
    assert [m["id"] for m in data["team"]] == [fox, bunny, None, None, None]
    assert {t for m in data["team"] for t in m["types"]} == set(wd.REGIONS)
    picked = client.post("/api/wander/party", json={"pets": [bunny]}).json()
    assert [m["id"] for m in picked["team"]][:1] == [bunny] and picked["team"][1]["id"] is None
    assert client.post("/api/wander/party", json={"pets": [999]}).status_code == 400
    data = client.post("/api/wander/trip/start", json={}).json()
    assert data["trip"]["energy"] == sv.WALK_ENERGY + wp.team_energy(data["team"])
    assert client.post("/api/wander/party", json={"pets": [fox]}).status_code == 400  # not mid-trip


def _level_to(pet, lv):
    now = next(p for p in client.get("/api/wander/pets").json()["pets"] if p["id"] == pet)["xp"]
    client.post("/api/wander-lab/xp", json={"pet_id": pet, "xp": wp.xp_for(lv) - now})
    return client.get("/api/wander").json()["levelups"]


def _finish(*choices):
    data = None
    for choice in choices:
        data = client.post("/api/wander/levelup", json={"choice": choice}).json()
    return data


def test_level_ups_wait_in_turn_with_what_grew():
    fox, bunny = _add_pet("fox"), _add_pet("bunny", 2)
    _level_to(fox, 2)
    ups = _level_to(bunny, 2)
    assert [(u["pet"], u["level"]) for u in ups] == [(fox, 2), (bunny, 2)]
    assert ups[0]["now"]["power"] == ups[0]["was"]["power"] + 1 and ups[0]["now"]["energy"] == ups[0]["was"]["energy"] + 2
    assert len(ups[0]["moves"]) == 6 and not any(u["choose"] for u in ups)
    data = client.post("/api/wander/levelup", json={}).json()
    assert [(u["pet"], u["level"]) for u in data["levelups"]] == [(bunny, 2)]
    assert client.post("/api/wander/levelup", json={}).json()["levelups"] == []
    assert client.post("/api/wander/levelup", json={}).status_code == 400
    assert client.get("/api/wander").json()["levelups"] == []  # and they stay done


def test_level_three_chooses_a_focus_that_changes_its_moves():
    fox = _add_pet("fox")
    client.post("/api/wander/trip/start", json={})
    ups = _level_to(fox, 4)
    three = ups[1]
    assert three["level"] == 3 and three["choose"]["kind"] == "focus"
    options = {o["id"]: o for o in three["choose"]["options"]}
    assert set(options) == {"healer", "elementalist", "daredevil", "guardian"}
    assert options["healer"]["label"] == "Cozy Hearth" and options["healer"]["replaces"] == "Guard" and options["healer"]["passive"]
    # each previews its six moves; choosing nothing doesn't get past it
    assert "healer" in [m["id"] for m in options["healer"]["moves"]] and "guard" not in [m["id"] for m in options["healer"]["moves"]]
    _finish(None)  # level 2
    assert client.post("/api/wander/levelup", json={}).status_code == 400
    assert client.post("/api/wander/levelup", json={"choice": "wizard"}).status_code == 400
    data = _finish("guardian")
    # on the trip at once, and on the pop-ups still to come
    me = next(m for m in data["team"] if m["id"] == fox)
    ids = [m["id"] for m in me["moves"]]
    assert me["focus"] == "guardian" and "guardian" in ids and "focus" not in ids
    assert next(m for m in me["moves"] if m["id"] == "guard")["label"] == "Flame Guard"
    assert "guardian" in [m["id"] for m in data["levelups"][0]["moves"]] and data["levelups"][0]["choose"] is None
    with db.open_db(main.DB_PATH) as conn:
        assert db.get_wander_pets(conn, 1)[fox]["focus"] == "guardian"


def test_level_five_has_to_choose_a_type_and_it_counts_at_once():
    fox = _add_pet("fox")
    client.post("/api/wander/trip/start", json={})
    ups = _level_to(fox, 6)
    five = next(u for u in ups if u["level"] == 5)
    offered = [o["id"] for o in five["choose"]["options"]]
    assert len(offered) == 2 and {u["level"] for u in ups if u["choose"]} == {3, 5}
    _finish(None, "healer", None)
    assert client.post("/api/wander/levelup", json={}).status_code == 400  # no choice
    assert client.post("/api/wander/levelup", json={"choice": "ember"}).status_code == 400  # its own type
    data = _finish(offered[0])
    # counted from 5, the level that offered it, and already on the trip's team
    assert next(m for m in data["team"] if m["id"] == fox)["types"] == {"ember": 6, offered[0]: 2}
    assert next(p for p in client.get("/api/wander/pets").json()["pets"] if p["id"] == fox)["choices"] is None
    # the same page goes on: what does its new attack replace? (a reload keeps its place)
    assert client.get("/api/wander").json()["levelups"] == data["levelups"]
    step = data["levelups"][0]
    assert [u["level"] for u in data["levelups"]] == [5, 6] and step["choose"]["kind"] == "attack2"
    assert [o["id"] for o in step["choose"]["options"]] == ["focus", "cheer", "rest"]  # Healer took guard
    assert client.post("/api/wander/levelup", json={"choice": "attack"}).status_code == 400  # only grey ones
    data = _finish("cheer")
    assert [u["level"] for u in data["levelups"]] == [6]
    me = next(m for m in data["team"] if m["id"] == fox)
    assert [m["id"] for m in me["moves"]] == ["attack", "big", "healer", "focus", "attack2", "rest"]
    assert me["moves"][4]["type"] == offered[0] and me["moves"][0]["label"] == "{ember} attack"
    with db.open_db(main.DB_PATH) as conn:
        assert db.get_wander_pets(conn, 1)[fox]["swaps"] == {"cheer": "attack2"}


def test_level_seven_brings_a_mix_that_can_replace_any_of_the_six():
    fox = _add_pet("fox")
    client.post("/api/wander/trip/start", json={})
    ups = _level_to(fox, 7)
    _finish(None, "healer", None)
    five = client.get("/api/wander").json()["levelups"][0]
    data = _finish(five["choose"]["options"][0]["id"], "rest", None)
    step = data["levelups"][0]
    assert step["level"] == 7 and step["choose"]["kind"] == "mix"
    second = five["choose"]["options"][0]["id"]
    assert step["choose"]["new"]["type"] == "ember" and step["choose"]["new"]["type2"] == second
    assert [o["id"] for o in step["choose"]["options"]] == ["attack", "big", "healer", "focus", "cheer", "attack2"]  # all six, typed too
    assert client.post("/api/wander/levelup", json={}).status_code == 400
    data = _finish("attack2")
    assert data["levelups"] == []
    me = next(m for m in data["team"] if m["id"] == fox)
    assert [m["id"] for m in me["moves"]] == ["attack", "big", "healer", "focus", "cheer", "mix"]
    assert me["swaps"] == {"rest": "attack2", "attack2": "mix"}
    assert len(ups) == 6


def test_a_mythical_gets_its_own_mix():
    unicorn = _add_pet("unicorn", 5)
    _level_to(unicorn, 7)
    data = _finish(None, "healer", None, "focus", None)
    step = data["levelups"][0]
    assert step["choose"]["new"]["label"] == "Rainbow Blessing"


def test_mythicals_focus_in_their_first_type_and_only_choose_what_their_second_attack_replaces():
    unicorn = _add_pet("unicorn", 5)
    ups = _level_to(unicorn, 5)
    assert [u["level"] for u in ups if u["choose"]] == [3, 5]
    first, second = wp.SPECIES_TYPES["unicorn"]
    assert all(o["type"] == first for o in ups[1]["choose"]["options"])
    assert ups[3]["choose"]["kind"] == "attack2"  # the type's already theirs: just what its attack replaces
    assert f"{{{second}}}" in ups[3]["choose"]["ask"]
    _finish(None, "daredevil", None)
    me = next(m for m in _finish("guard")["team"] if m["id"] == unicorn)
    assert next(m for m in me["moves"] if m["id"] == "attack2")["type"] == second


def test_picking_from_the_party_list_answers_a_waiting_pop_up():
    fox = _add_pet("fox")
    five = _level_to(fox, 5)[-1]
    client.post(f"/api/wander/pets/{fox}/second", json={"type": five["choose"]["options"][0]["id"]})
    assert client.get("/api/wander").json()["levelups"][-1]["choose"]["kind"] == "attack2"


def test_starting_the_world_over_starts_pets_over_but_keeps_stars():
    fox = _add_pet("fox")
    _level_to(fox, 4)
    _finish(None, "healer")
    client.post(f"/api/wander/pets/{fox}/star")
    client.post("/api/wander-lab/reset", json={"seed": 7})
    me = next(p for p in client.get("/api/wander/pets").json()["pets"] if p["id"] == fox)
    assert me["level"] == 1 and me["focus"] is None and me["starred"]
    assert client.get("/api/wander").json()["levelups"] == []


def test_levels_second_types_and_stars():
    fox = _add_pet("fox")
    unicorn = _add_pet("unicorn", 5)
    pets = client.post("/api/wander-lab/xp", json={"pet_id": fox, "xp": wp.xp_for(5)}).json()["pets"]
    me = next(p for p in pets if p["id"] == fox)
    assert me["level"] == 5 and len(me["choices"]) == 2
    assert client.post(f"/api/wander/pets/{fox}/second", json={"type": "ember"}).status_code == 400
    second = me["choices"][1]
    pets = client.post(f"/api/wander/pets/{fox}/second", json={"type": second}).json()["pets"]
    me = next(p for p in pets if p["id"] == fox)
    assert me["types"] == {"ember": 5, second: 1} and me["choices"] is None
    assert next(p for p in pets if p["id"] == unicorn)["types"] == {"dream": 1, "leaf": 1}
    pets = client.post(f"/api/wander/pets/{unicorn}/star").json()["pets"]
    assert pets[0]["id"] == unicorn and pets[0]["starred"]


def test_quests_give_the_team_xp():
    fox = _add_pet("fox")
    seed = _seed()
    world = wd.generate(seed)
    g = qs.plan(seed).givers["leaf:leaf"]
    client.post("/api/wander/trip/start", json={})
    client.post("/api/wander-lab/teleport", json={"q": g.town[0], "r": g.town[1], "spot": list(g.house)})
    client.post("/api/wander/act", json={"action": "ask"})
    with db.open_db(main.DB_PATH) as conn:
        save = sv.load(conn, 1)
        have = [sv.st.NPCS[("leaf", "leaf")].lost, *sv._parts(save, "leaf", "leaf")]
        db.save_wander(conn, 1, {**save, "items": {x: 1 for x in have}})
    data = client.post("/api/wander/act", json={"action": "mend"}).json()
    assert data["team"][0]["id"] == fox
    with db.open_db(main.DB_PATH) as conn:
        assert db.get_wander_pets(conn, 1)[fox]["xp"] == sv.st.XP_QUEST


def test_a_battle_pays_its_fighters():
    from app.wanderpaw import critters as cr
    from app.wanderpaw import hexes as hx
    fox, bunny = _add_pet("fox"), _add_pet("bunny", 2)
    seed = _seed()
    client.post("/api/wander/trip/start", json={})
    data = client.get("/api/wander").json()
    day = data["stats"]["trips"]
    world = wd.generate(seed)
    spot = None
    for big in sorted(b for b, h in world.hexes.items() if h.region == wd.HEARTLAND):  # creatures a new party can beat
        local = lc.generate(seed, big)
        here = cr.at(seed, big, day)
        for h in sorted(here):
            n = next((n for n in hx.neighbors(h) if n in lc.CELL_SET and local.walkable(n) and n not in here), None)
            if n:
                spot = (big, h, n)
                break
        if spot:
            break
    big, h, n = spot
    client.post("/api/wander-lab/teleport", json={"q": big[0], "r": big[1], "spot": list(n)})
    g = lc.to_world(big, h)
    data = client.post("/api/wander/walk", json={"q": g[0], "r": g[1]}).json()
    assert data["battle"] and [f["place"] for f in data["battle"]["fighters"]] == [0, 1]
    while not data["battle"]["over"]:
        moves = [{"move": f["moves"][0]["id"], "slips": 0} for f in data["battle"]["fighters"] if f["energy"] > 0]
        data = client.post("/api/wander/battle/turn", json={"moves": moves}).json()
    assert data["battle"]["over"] in ("won", "lost")
    if data["battle"]["over"] == "won":
        with db.open_db(main.DB_PATH) as conn:
            recs = db.get_wander_pets(conn, 1)
        assert recs[fox]["xp"] > 0 and recs[bunny]["xp"] > 0
        assert recs[fox]["partners"] == {"leaf": 1} and recs[bunny]["partners"] == {"ember": 1}
    left = client.post("/api/wander/battle/leave", json={}).json()
    assert left["battle"] is None
    assert client.post("/api/wander/fighters", json={"slots": [1, 0]}).json()["fighters"] == [1, 0]
