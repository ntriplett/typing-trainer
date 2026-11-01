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
    for big in sorted(world.hexes):
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
