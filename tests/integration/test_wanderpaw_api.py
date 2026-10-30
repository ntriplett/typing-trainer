"""Wanderpaw's API: your world, walking, and the admin lab (PLAN.md 11n)."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.wanderpaw import hexes as hx
from app.wanderpaw import world as wd

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    yield


def test_pages_serve():
    assert client.get("/wanderpaw").status_code == 200
    assert client.get("/wander-lab").status_code == 200


def test_new_player_starts_at_camp_with_words():
    data = client.get("/api/wander").json()
    assert data["at"] == [0, 0]
    assert len(data["hexes"]) == 7
    assert len(data["words"]) >= 6
    # the world stays the same between loads
    assert client.get("/api/wander").json()["hexes"] == data["hexes"]


def test_step_saves_and_walls_refuse():
    seed = client.get("/api/wander-lab/world").json()["seed"]
    world = wd.generate(seed)
    to = world.exits((0, 0))[0]
    data = client.post("/api/wander/step", json={"q": to[0], "r": to[1]}).json()
    assert data["at"] == list(to)
    assert client.get("/api/wander").json()["at"] == list(to)
    walled = [n for n in hx.neighbors(to) if n in world.hexes and not world.is_open(to, n)]
    if walled:
        res = client.post("/api/wander/step", json={"q": walled[0][0], "r": walled[0][1]})
        assert res.status_code == 400 and "in the way" in res.json()["detail"]


def test_lab_sees_everything_and_any_seed():
    mine = client.get("/api/wander-lab/world").json()
    assert len(mine["hexes"]) == len(wd.generate(mine["seed"]).hexes)
    assert mine["me"]["at"] == [0, 0]
    other = client.get("/api/wander-lab/world", params={"seed": 5}).json()
    assert other["seed"] == 5 and "me" not in other


def test_lab_teleport_and_reset():
    mine = client.get("/api/wander-lab/world").json()
    far = next(h for h in mine["hexes"] if h["special"] == "temple")
    data = client.post("/api/wander-lab/teleport", json={"q": far["q"], "r": far["r"]}).json()
    assert data["me"]["at"] == [far["q"], far["r"]]
    assert client.get("/api/wander").json()["at"] == [far["q"], far["r"]]
    assert client.post("/api/wander-lab/teleport", json={"q": 40, "r": 40}).status_code == 400
    fresh = client.post("/api/wander-lab/reset", json={"seed": 1234}).json()
    assert fresh["seed"] == 1234 and fresh["me"]["at"] == [0, 0]
