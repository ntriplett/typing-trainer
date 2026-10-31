"""Wanderpaw's API: your world, trips, walking, and the admin lab (PLAN.md 11n)."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
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
    assert len(data["words"]) >= 6
    assert client.get("/api/wander").json()["local"] == data["local"]


def test_trip_walk_and_end():
    local = lc.generate(_seed(), (0, 0))
    to = next(n for n in hx.neighbors((0, 0)) if local.walkable(n))
    assert client.post("/api/wander/walk", json={"q": to[0], "r": to[1]}).status_code == 400  # no trip yet
    data = client.post("/api/wander/trip/start", json={}).json()
    assert data["trip"]["energy"] == data["trip"]["max"]
    data = client.post("/api/wander/walk", json={"q": to[0], "r": to[1]}).json()
    assert data["local"]["spot"] == list(to)
    assert client.post("/api/wander/trip/end").status_code == 400  # not at the campfire
    client.post("/api/wander/walk", json={"q": 0, "r": 0})
    assert client.post("/api/wander/trip/end").json()["note"] == "rested"


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
    q = world.quests["leaf"]
    town = lc.generate(seed, q.town)
    elder = next(h for h, role in town.buildings.items() if role == "elder")
    client.post("/api/wander/trip/start", json={})
    client.post("/api/wander-lab/teleport", json={"q": q.town[0], "r": q.town[1], "spot": list(elder)})
    data = client.get("/api/wander").json()
    assert data["screen"]["action"] == "ask"
    data = client.post("/api/wander/act", json={"action": "ask"}).json()
    assert data["quests"][0]["state"] == "asked"
    assert client.post("/api/wander/act", json={"action": "ask"}).status_code == 400
    assert client.post("/api/wander-lab/party", json={"party": ["leaf", "leaf"]}).json()["me"]["party"] == ["leaf", "leaf"]
    assert client.post("/api/wander-lab/party", json={"party": ["fire"]}).status_code == 400
