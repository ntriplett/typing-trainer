"""Wanderpaw's API: your world, trips, walking, and the admin lab (PLAN.md 11n)."""

import pytest
from fastapi.testclient import TestClient

from app import db, main
from app import pet_genes as g
from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import battle as bt
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


def test_the_move_lab_lists_every_move_tile():
    assert client.get("/move-lab").status_code == 200
    groups = {g["name"]: g["tiles"] for g in client.get("/api/move-lab").json()["groups"]}
    assert len(groups["Mixes"]) == 40 and len(groups["Capstones"]) == 20 and len(groups["Mythical mixes"]) == 20 and len(groups["Focus moves"]) == 40
    names = {t["name"] for t in groups["Mixes"]}
    assert "Fire Seed" in names and "Fire Seed+" in names
    for tiles in groups.values():
        for t in tiles:
            assert t["party"]["label"] and t["battle"]["icons"] is not None
    plus = next(t for t in groups["Focus moves"] if t["name"] == "Cozy Hearth+")
    assert plus["party"]["label"] == "Cozy Hearth+"
    mythic = next(t for t in groups["Mythical mixes"] if t["name"] == "Stormfire Breath")
    assert mythic["party"]["label"] == "Stormfire Breath"


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


def _to_level_nine(pet, focus="healer", mix_slot="attack2"):
    client.post("/api/wander/trip/start", json={})
    _level_to(pet, 9)
    _finish(None, focus, None)
    five = client.get("/api/wander").json()["levelups"][0]
    return _finish(five["choose"]["options"][0]["id"], "rest", None, mix_slot, None)


def test_level_nine_grows_the_focus_and_upgrades_a_chosen_move():
    fox = _add_pet("fox")
    step = _to_level_nine(fox)["levelups"][0]
    assert step["level"] == 9 and step["choose"]["kind"] == "upgrade"
    assert "Cozy Hearth+" in step["choose"]["ask"]
    labels = {m["id"]: m["label"] for m in step["moves"]}
    assert labels["healer"] == "Cozy Hearth+"  # already grown
    # every move but the focus's: and the mix
    assert {o["id"] for o in step["choose"]["options"]} == {"attack", "big", "focus", "cheer", "mix"}
    option = next(o for o in step["choose"]["options"] if o["id"] == "big")
    assert option["label"].endswith("+") and option["icons"]["cost"] == {"mana": 5}
    assert client.post("/api/wander/levelup", json={}).status_code == 400
    assert client.post("/api/wander/levelup", json={"choice": "healer"}).status_code == 400
    data = _finish("big")
    assert data["levelups"] == []
    me = next(m for m in data["team"] if m["id"] == fox)
    assert next(m for m in me["moves"] if m["id"] == "big")["label"].endswith("+") and me["upgrades"] == ["big"]
    with db.open_db(main.DB_PATH) as conn:
        assert db.get_wander_pets(conn, 1)[fox]["upgrades"] == ["big"]


def test_level_eleven_brings_a_slot_a_move_back_and_an_upgrade():
    fox = _add_pet("fox")
    _to_level_nine(fox)  # Healer, second attack for rest, mix for the second attack
    _finish("big", None)  # level 9's upgrade, then level 10
    _level_to(fox, 11)
    data = client.get("/api/wander").json()
    step = data["levelups"][0]
    if step["level"] == 10:
        data = _finish(None)
        step = data["levelups"][0]
    assert step["level"] == 11 and step["choose"]["kind"] == "slot"
    assert {o["id"] for o in step["choose"]["options"]} == {"guard", "rest", "attack2"}
    assert client.post("/api/wander/levelup", json={}).status_code == 400
    data = _finish("rest")
    # the same page goes on: an upgrade, of anything with no + yet
    step = data["levelups"][0]
    assert step["level"] == 11 and step["choose"]["kind"] == "upgrade"
    ids = {o["id"] for o in step["choose"]["options"]}
    assert "big" not in ids and "healer" not in ids and "rest" in ids and "mix" in ids
    assert len(step["moves"]) == 7
    data = _finish("rest")
    assert data["levelups"] == []
    me = next(m for m in data["team"] if m["id"] == fox)
    assert len(me["moves"]) == 7 and me["moves"][-1]["label"] == "Rest+" and me["extra"] == ["rest"]
    assert me["upgrades"] == ["big", "rest"]


def test_level_thirteen_brings_the_mix_the_other_way_around():
    fox = _add_pet("fox")
    with db.open_db(main.DB_PATH) as conn:
        db.save_wander_pet(conn, 1, fox, {"xp": wp.xp_for(12), "second": "leaf", "second_at": 5, "partners": {}, "starred": False, "focus": "healer",
                                          "swaps": {"rest": "attack2", "attack2": "mix"}, "upgrades": ["big", "attack"], "extra": ["guard"]})
    client.post("/api/wander/trip/start", json={})
    step = _level_to(fox, 13)[0]
    assert step["level"] == 13 and step["choose"]["kind"] == "mix2"
    assert step["choose"]["new"]["label"] == bt.MIX_MOVES["leaf", "ember"].name
    assert step["choose"]["new"]["type"] == "leaf" and step["choose"]["new"]["cost"] == bt.MIX_MANA
    assert len(step["choose"]["options"]) == 7  # any of the seven
    assert client.post("/api/wander/levelup", json={}).status_code == 400
    # taking the 7th slot's move
    data = _finish("guard")
    assert data["levelups"] == []
    me = next(m for m in data["team"] if m["id"] == fox)
    assert len(me["moves"]) == 7 and me["moves"][-1]["id"] == "mix2" and not me["moves"][-1]["label"].endswith("+")
    assert me["extra"] == ["mix2"] and "mix2" not in me["upgrades"]
    assert "mix" in {m["id"] for m in me["moves"]}


def _in_battle_as(species, rec, partner=True):
    pet = _add_pet(species, 7)
    with db.open_db(main.DB_PATH) as conn:
        db.save_wander_pet(conn, 1, pet, rec)
    if partner:
        _add_pet("bunny", 8)
    client.post("/api/wander/trip/start", json={})
    seed, data = _seed(), client.get("/api/wander").json()
    from app.wanderpaw import critters as cr
    from app.wanderpaw import hexes as hx
    world, day = wd.generate(seed), data["stats"]["trips"]
    big, h = next((b, h) for b in sorted(world.hexes) if world.hexes[b].region == wd.HEARTLAND for h in sorted(cr.at(seed, b, day)))
    local = lc.generate(seed, big)
    n = next(n for n in hx.neighbors(h) if n in lc.CELL_SET and local.walkable(n) and n not in cr.at(seed, big, day))
    client.post("/api/wander-lab/teleport", json={"q": big[0], "r": big[1], "spot": list(n)})
    g = lc.to_world(big, h)
    return pet, client.post("/api/wander/walk", json={"q": g[0], "r": g[1]}).json()


MYTH_REC = {"xp": wp.xp_for(13), "second": None, "second_at": None, "partners": {}, "starred": False, "focus": None, "swaps": {"rest": "mix2"}, "upgrades": [], "extra": []}


def test_a_mythical_gets_its_own_reverse_move_at_level_thirteen():
    unicorn = _add_pet("unicorn", 5)
    with db.open_db(main.DB_PATH) as conn:
        db.save_wander_pet(conn, 1, unicorn, {**MYTH_REC, "xp": wp.xp_for(12), "swaps": {"rest": "mix"}})
    step = _level_to(unicorn, 13)[0]
    assert step["choose"]["new"]["label"] == "Sanctuary"


def test_a_once_a_battle_move_shows_it_can_not_be_used_again():
    pet, data = _in_battle_as("unicorn", MYTH_REC)
    mine = lambda d: next(m for m in d["battle"]["fighters"][0]["moves"] if m["id"] == "mix2")  # noqa: E731
    assert mine(data)["can"] is True
    data = client.post("/api/wander/battle/turn", json={"moves": [{"move": "mix2", "slips": 0}, {"move": "attack", "slips": 0}]}).json()
    if not data["battle"]["over"]:
        assert mine(data)["can"] is False
        res = client.post("/api/wander/battle/turn", json={"moves": [{"move": "mix2", "slips": 0}, {"move": "attack", "slips": 0}]})
        assert res.status_code == 400


def test_golden_flame_pays_its_coins_and_nectar_its_xp():
    pet, data = _in_battle_as("dragon", MYTH_REC)
    before = data["coin_balance"]
    data = client.post("/api/wander/battle/turn", json={"moves": [{"move": "mix2", "slips": 0}, {"move": "attack", "slips": 0}]}).json()
    while not data["battle"]["over"]:
        moves = [{"move": "attack", "slips": 0} for f in data["battle"]["fighters"] if f["energy"] > 0]
        data = client.post("/api/wander/battle/turn", json={"moves": moves}).json()
    # (it pays only if it was the Golden Flame that won: a heartland creature falls to one)
    if any(e.get("text", "").startswith("Golden Flame") for e in data["events"]):
        assert data["coin_balance"] > before


def test_nectar_gives_partner_its_xp():
    # (a stand-in fairy on the team: this is where the battle hands the save its XP)
    from app.wanderpaw import critters as cr
    from app.wanderpaw import save as sv
    fairy = {**wp.starter("leaf", 13), "species": "flower_fairy", "types": {"leaf": 13, "splash": 9}, "swaps": {"rest": "mix2"}, "id": 1}
    partner = {**wp.starter("ember", 13), "id": 2, "progress": (0, 1000)}
    save = sv.start_trip({**sv.new_save(5), "team": [fairy, partner]})
    c = cr.Critter("g:0,0:0,0", (0, 0), (0, 0), "sheep", "dream", 2, True, 1)
    save = {**sv._start_battle(save, c)}
    save = {**save, "battle": {**save["battle"], "energy": 9999, "max": 9999}}
    after = sv.battle_turn(save, [{"move": "mix2", "slips": 0}, {"move": "guard", "slips": 0}])
    assert {"kind": "xp", "amount": 100, "pets": [2]} in after["events"]


def test_reborn_is_once_a_day_across_battles():
    from app.wanderpaw import save as sv
    team = [{**wp.starter("ember", 13), "species": "phoenix", "types": {"ember": 13, "dream": 9}, "swaps": {"rest": "mix2"}, "id": None}, wp.starter("leaf", 13)]
    save = sv.start_trip({**sv.new_save(5), "team": team})
    from app.wanderpaw import critters as cr
    c = cr.Critter("g:0,0:0,0", (0, 0), (0, 0), "sheep", "dream", 2, True, 1)
    assert sv._start_battle(save, c)["battle"]["reborn"] == [0]
    assert sv._start_battle({**save, "trip": {**save["trip"], "reborn": [0]}}, c)["battle"]["reborn"] == []


REC_14 = {"xp": wp.xp_for(14), "second": "leaf", "second_at": 5, "partners": {}, "starred": False, "focus": "healer",
          "swaps": {"rest": "attack2", "attack2": "mix", "focus": "mix2"}, "upgrades": ["big", "attack"], "extra": ["guard"]}


def test_levels_fifteen_to_nineteen():
    fox = _add_pet("fox")
    with db.open_db(main.DB_PATH) as conn:
        db.save_wander_pet(conn, 1, fox, REC_14)
    client.post("/api/wander/trip/start", json={})
    ups = _level_to(fox, 19)
    assert [u["level"] for u in ups] == [15, 16, 17, 18, 19]
    # 15: a third type, then its attack+, in any slot
    third = ups[0]["choose"]
    assert third["kind"] == "third" and len(third["options"]) == 2
    kind = third["options"][0]["id"]
    assert kind not in ("ember", "leaf")
    data = _finish(kind)
    step = data["levelups"][0]
    assert step["level"] == 15 and step["choose"]["kind"] == "attack3" and len(step["choose"]["options"]) == 7
    preview = next(m for m in step["choose"]["options"][0]["moves"] if m["id"] == "attack3")
    assert preview["label"].endswith("attack+")
    data = _finish("cheer")
    me = next(m for m in data["team"] if m["id"] == fox)
    assert me["types"][kind] == 5 and "attack3" in me["upgrades"] and "attack3" in {m["id"] for m in me["moves"]}
    assert [u["level"] for u in data["levelups"]] == [16, 17, 18, 19]
    # 17: an 8th slot, for a mix with the third type
    data = _finish(None)
    step = data["levelups"][0]
    assert step["level"] == 17 and step["choose"]["kind"] == "mix_slot"
    ids = {o["id"] for o in step["choose"]["options"]}
    assert ids == {f"mix:ember:{kind}", f"mix:{kind}:ember", f"mix:leaf:{kind}", f"mix:{kind}:leaf"}
    data = _finish(f"mix:ember:{kind}")
    me = next(m for m in data["team"] if m["id"] == fox)
    assert len(me["moves"]) == 8 and me["moves"][-1]["id"] == f"mix:ember:{kind}"
    # 19: any mix it doesn't have, then its slot, then an upgrade
    data = _finish(None)
    step = data["levelups"][0]
    assert step["level"] == 19 and step["choose"]["kind"] == "pick_mix"
    assert {o["id"] for o in step["choose"]["options"]} == {f"mix:{kind}:ember", f"mix:leaf:{kind}", f"mix:{kind}:leaf"}
    data = _finish(f"mix:{kind}:leaf")
    step = data["levelups"][0]
    assert step["choose"]["kind"] == "place" and len(step["choose"]["options"]) == 8
    assert client.get("/api/wander").json()["levelups"][0]["choose"]["kind"] == "place"  # a reload keeps its place
    data = _finish("big")
    me = next(m for m in data["team"] if m["id"] == fox)
    ids = [m["id"] for m in me["moves"]]
    assert "big" not in ids and f"mix:{kind}:leaf" in ids and len(ids) == 8
    step = data["levelups"][0]
    assert step["choose"]["kind"] == "plus19"
    data = _finish(f"mix:{kind}:leaf")
    assert data["levelups"] == []
    me = next(m for m in data["team"] if m["id"] == fox)
    assert next(m for m in me["moves"] if m["id"] == f"mix:{kind}:leaf")["cost"] == 3
    with db.open_db(main.DB_PATH) as conn:
        rec = db.get_wander_pets(conn, 1)[fox]
    assert rec["third"] == kind and rec["third_at"] == 15 and rec["pending"] is None and {"mix19", "plus19"} <= set(rec["done"])


def test_level_twenty_one_chooses_a_capstone_that_helps_from_the_bench():
    fox, bunny = _add_pet("fox"), _add_pet("bunny", 2)
    with db.open_db(main.DB_PATH) as conn:
        db.save_wander_pet(conn, 1, fox, {**REC_14, "xp": wp.xp_for(20), "third": "shock", "third_at": 15, "done": ["mix19", "plus19"], "extra": ["guard", "mix:ember:shock"]})
    step = _level_to(fox, 21)[0]
    assert step["level"] == 21 and step["max"] and step["choose"]["kind"] == "capstone"
    assert [o["id"] for o in step["choose"]["options"]] == ["ember:leaf", "ember:shock", "leaf:shock"]
    assert client.post("/api/wander/levelup", json={}).status_code == 400
    data = _finish("ember:shock")
    assert data["levelups"] == []
    me = next(m for m in data["team"] if m["id"] == fox)
    assert me["capstone"] == "ember:shock" and me["capstone_card"]["label"] == "Battle Cry"
    with db.open_db(main.DB_PATH) as conn:
        assert db.get_wander_pets(conn, 1)[fox]["capstone"] == "ember:shock"
    assert bunny


def test_trail_runner_makes_the_first_steps_free():
    from app.wanderpaw import save as sv
    team = [{**wp.starter("shock", 21), "capstone": "shock:leaf", "id": None}, wp.starter("leaf", 21)]
    save = sv.start_trip({**sv.new_save(5), "team": team})
    before = save["trip"]["energy"]
    for step in sv.steps(save)[:1]:
        big, h = lc.owner(step)
        after = sv.apply_walk(save, h) if big == tuple(save["at"]) else save
        if after is not save and not after.get("battle"):
            assert after["trip"]["energy"] == before and after["trip"]["free_steps"] == 1


def test_a_guardian_plus_cant_also_upgrade_its_guard():
    fox = _add_pet("fox")
    client.post("/api/wander/trip/start", json={})
    _level_to(fox, 9)
    _finish(None, "guardian", None)
    five = client.get("/api/wander").json()["levelups"][0]
    step = _finish(five["choose"]["options"][0]["id"], "rest", None, "attack2", None)["levelups"][0]
    assert "guard" not in {o["id"] for o in step["choose"]["options"]}


def test_a_pet_that_gave_up_its_focus_can_take_it_back():
    fox = _add_pet("fox")
    step = _to_level_nine(fox, mix_slot="healer")["levelups"][0]
    assert "healer" not in {m["id"] for m in step["moves"]}
    back = next(o for o in step["choose"]["options"] if o["id"] == "refocus")
    assert back["label"] == "Cozy Hearth+" and "healer" in {m["id"] for m in back["moves"]}
    data = _finish("refocus")
    # its mix needs a new slot, on the same page
    step = data["levelups"][0]
    assert step["level"] == 9 and step["choose"]["kind"] == "mix" and "healer" not in {o["id"] for o in step["choose"]["options"]}
    data = _finish("cheer")
    assert data["levelups"] == []
    me = next(m for m in data["team"] if m["id"] == fox)
    ids = [m["id"] for m in me["moves"]]
    assert "healer" in ids and "mix" in ids and "cheer" not in ids
    assert me["upgrades"] == ["refocus"]


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


def test_the_battle_shows_and_keeps_to_energy_going_in():
    fox, _ = _add_pet("fox"), _add_pet("bunny", 2)
    from app.wanderpaw import critters as cr
    from app.wanderpaw import hexes as hx
    from app.wanderpaw import save as sv
    client.post("/api/wander/trip/start", json={})
    with db.open_db(main.DB_PATH) as conn:
        save = sv.load(conn, 1)
        db.save_wander(conn, 1, {**save, "trip": {**save["trip"], "pets": [9, 9, *save["trip"]["pets"][2:]]}})
    seed, data = _seed(), client.get("/api/wander").json()
    world, day = wd.generate(seed), data["stats"]["trips"]
    big, h = next((b, h) for b in sorted(world.hexes) if world.hexes[b].region == wd.HEARTLAND for h in sorted(cr.at(seed, b, day)))
    local = lc.generate(seed, big)
    n = next(n for n in hx.neighbors(h) if n in lc.CELL_SET and local.walkable(n) and n not in cr.at(seed, big, day))
    client.post("/api/wander-lab/teleport", json={"q": big[0], "r": big[1], "spot": list(n)})
    g = lc.to_world(big, h)
    data = client.post("/api/wander/walk", json={"q": g[0], "r": g[1]}).json()
    assert [f["max"] for f in data["battle"]["fighters"]] == [9, 9] and fox


def test_numbers_never_label_a_step():
    # they open the bag, journal and party, however many keys you've learned
    from app import lessons, pet_shop
    with db.open_db(main.DB_PATH) as conn:
        lessons.record_placement(conn, 1, set(pet_shop.HOME_ROW + pet_shop.TOP_ROW + pet_shop.BOTTOM_ROW + pet_shop.NUMBERS))
    words = client.get("/api/wander").json()["words"]
    assert words["letter"] and "a" in words["letter"]
    assert not [w for group in words.values() for w in group if any(c.isdigit() for c in w)]


def test_the_lab_takes_you_to_a_boss_at_its_door():
    _add_pet("fox", 1)
    client.post("/api/wander-lab/boss", json={"region": "ember"})
    state = client.get("/api/wander").json()
    assert state["trip"] and state["screen"]
    screen = client.get("/api/wander").json()["screen"]
    assert screen["action"] == "boss" and screen["label"] == "Face the guardian"
    fight = client.post("/api/wander/act", json={"action": "boss"}).json()
    assert fight["battle"]["tier"] == "boss" and fight["battle"]["kind"] == "ember"
    assert client.post("/api/wander-lab/boss", json={"region": "nope"}).status_code == 400


# --- shops and items ----------------------------------------------------------------


def _at_the_shop(region="dream", coins=20000):
    from app.wanderpaw import shop as sh  # noqa: F401
    if not client.get("/api/wander").json()["trip"]:
        client.post("/api/wander/trip/start", json={})
    with db.open_db(main.DB_PATH) as conn:
        save = sv.load(conn, 1)
        world = sv.world_of(save)
        big, spot = next((h, s) for h, x in world.hexes.items() if x.special == "town" and x.region == region for s, role in sv.local_of(save, h).buildings.items() if role == "shop")
        sv.teleport(conn, 1, big, spot)
        db.add_coins(conn, 1, coins - db.get_coin_balance(conn, 1), "test")
    return client.get("/api/wander").json()


def test_a_town_shop_sells_things_for_your_coins():
    state = _at_the_shop("dream", 3000)
    screen = state["screen"]
    assert screen["action"] == "shop" and "Alchemist" in screen["title"]
    names = [x["name"] for x in screen["stock"]]
    assert "Full Mana Potion" in names and "Friendship Token" in names
    r = client.post("/api/wander/shop/buy", json={"item": "Mana Drop"}).json()
    assert r["items"]["Mana Drop"] == 1 and r["coin_balance"] == 2500
    assert client.post("/api/wander/shop/buy", json={"item": "Fine Fishing Rod"}).status_code == 400  # not this shop
    assert client.post("/api/wander/shop/buy", json={"item": "Full Mana Potion"}).status_code == 200
    broke = client.post("/api/wander/shop/buy", json={"item": "Full Mana Potion"})
    assert broke.status_code == 400 and "more coins" in broke.json()["detail"]


def test_one_friendship_token_per_shop_and_three_tomes():
    _at_the_shop("leaf")
    assert client.post("/api/wander/shop/buy", json={"item": "Friendship Token"}).status_code == 200
    assert client.post("/api/wander/shop/buy", json={"item": "Friendship Token"}).status_code == 400
    for _ in range(3):
        assert client.post("/api/wander/shop/buy", json={"item": "Type Tome"}).status_code == 200
    assert client.post("/api/wander/shop/buy", json={"item": "Type Tome"}).status_code == 400
    state = _at_the_shop("dream")  # another town, another token
    assert next(x for x in state["screen"]["stock"] if x["name"] == "Friendship Token")["left"] == 1


def test_you_cant_buy_away_from_a_shop():
    client.post("/api/wander/trip/start", json={})
    assert client.post("/api/wander/shop/buy", json={"item": "Mana Drop"}).status_code == 400


def test_a_tome_raises_a_type_for_good_but_not_the_pets_level():
    fox = _add_pet("fox", 1)
    client.post("/api/wander/party", json={"pets": [fox]})
    with db.open_db(main.DB_PATH) as conn:
        sv.give_xp(conn, 1, fox, wp.xp_for(6))
    state = _at_the_shop("leaf")
    before = next(m for m in state["team"] if m["id"] == fox)
    client.post("/api/wander/shop/buy", json={"item": "Type Tome"})
    choices = client.get("/api/wander").json()["item_uses"]["Type Tome"]["choices"]
    assert f"{fox}:ember" in [c["arg"] for c in choices]
    after = client.post("/api/wander/use", json={"item": "Type Tome", "arg": f"{fox}:ember"}).json()
    me = next(m for m in after["team"] if m["id"] == fox)
    assert me["types"]["ember"] == before["types"]["ember"] + 1 and me["level"] == before["level"]
    assert "Type Tome" not in after["items"]
    with db.open_db(main.DB_PATH) as conn:
        assert wp.record_from(db.get_wander_pets(conn, 1)[fox]).type_bonus == {"ember": 1}


def test_befriending_a_beaten_creature_makes_it_yours_at_its_level():
    from app.wanderpaw import critters as cr
    from app.wanderpaw import shop as sh
    fox, bunny = _add_pet("fox", 1), _add_pet("bunny", 2)
    client.post("/api/wander/party", json={"pets": [fox, bunny]})
    client.post("/api/wander/trip/start", json={})
    with db.open_db(main.DB_PATH) as conn:
        save = sv.load(conn, 1)
        c = cr.Critter("g:0,0:0,0", (0, 0), (0, 0), "goat", "leaf", 6, False, 77, None, "")
        save = sv._start_battle({**save, "items": {sh.TOKEN: 1}}, c)
        mana = [100 for _ in save["trip"]["mana"]]
        save = {**save, "battle": {**save["battle"], "over": "won"}, "trip": {**save["trip"], "mana": mana}, "events": []}
        db.save_wander(conn, 1, save)
    state = client.get("/api/wander").json()
    assert state["battle"]["befriend"] == {"cost": 6, "can": True, "tokens": 1}
    r = client.post("/api/wander/befriend")
    assert r.status_code == 200
    data = r.json()
    assert "Friendship Token" not in data["items"] and data["battle"]["befriend"] is None
    assert [f["mana"] for f in data["battle"]["fighters"]] == [94, 94]
    assert data["levelups"]  # every level's choices to make, as she catches up
    with db.open_db(main.DB_PATH) as conn:
        friend = [p for p in db.list_v3_pets(conn, 1) if p["source"] == "friend"]
        assert len(friend) == 1 and friend[0]["species"] == "goat" and friend[0]["growth"] == 10
        assert wp.level(wp.record_from(db.get_wander_pets(conn, 1)[friend[0]["id"]]).xp) == 6
    assert client.post("/api/wander/befriend").status_code == 400  # only once


def test_the_guidebook_comes_from_the_real_type_chart():
    g = client.get("/api/wander/guide").json()
    assert g["chart"]["shock"]["ember"] == bt.matchup("shock", "ember") == 1.5  # shock IS strong against ember
    assert g["chart"]["splash"]["ember"] == 2 and g["chart"]["dream"]["ember"] == 0.5
    assert set(g["order"]) == set(wd.REGIONS) and g["marks"] and g["effects"] and g["lands"]
    assert "Your first type" in g["fight"]
