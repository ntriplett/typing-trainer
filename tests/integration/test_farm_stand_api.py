"""Integration tests for the Farm Stand API: the game content's farm and
customers, the upgrade shop, and finished days (saved only from the arcade)."""

import pytest
from fastapi.testclient import TestClient

from app import db, farm_stand, main

client = TestClient(main.app)
FARM = farm_stand.GAME_ID
DAY = {"served": 9, "missed": 1, "sold": {"radish": 12}, "earned": 30, "spent": 6}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    yield


def _arcade_play():
    client.put("/api/profiles/placement", json={"keys": "home_row", "speed": "some"})
    with db.open_db(main.DB_PATH) as conn:
        db.add_tokens(conn, 1, 1, "test")
    res = client.post(f"/api/arcade/play/{FARM}")
    assert res.status_code == 200, res.text


def test_content_has_the_farm_and_grown_animal_customers():
    game = client.get(f"/api/game/{FARM}/content", params={"keys": "home"}).json()["game"]
    assert game["game"] == "farm_stand" and game["hours"] == 4 and len(game["levels"]) == 4
    assert len(game["deliveries"]) == 2
    assert game["farm"]["plots"] == 4 and game["farm"]["money"] == farm_stand.START_MONEY
    assert len(game["customers"]) == farm_stand.CUSTOMERS_PER_DAY
    assert all(c["growth"] == 10 and c["genes"]["hex"][0] for c in game["customers"])
    assert all(set(w) <= set("asdfghjkl;") for w in game["words"]["short"])


def test_the_arcade_sells_farm_stand_for_one_token():
    games = {g["id"]: g for g in client.get("/api/arcade").json()["games"]}
    assert games[FARM]["price"] == 1


def test_a_lab_day_is_not_saved():
    out = client.post("/api/farm/day", json=DAY).json()
    assert out["stars"] == 3 and not out["counted"] and out["veggie"] is None
    assert client.get("/api/farm").json()["day"] == 0


def test_an_arcade_day_is_saved_and_pays_a_veggie():
    _arcade_play()
    out = client.post("/api/farm/day", json=DAY).json()
    assert out["counted"] and out["veggie"] == "radish"
    assert out["farm"]["day"] == 1 and out["farm"]["money"] == farm_stand.START_MONEY + 24
    with db.open_db(main.DB_PATH) as conn:
        assert db.get_veggies(conn, 1) == {"radish": 1}
    assert not client.post("/api/farm/day", json=DAY).json()["counted"]


def test_impossible_days_are_refused():
    res = client.post("/api/farm/day", json={**DAY, "sold": {"pumpkin": 1}})
    assert res.status_code == 400 and "isn't open" in res.json()["detail"]
    assert client.post("/api/farm/day", json={**DAY, "earned": -1}).status_code == 422


def test_buying_upgrades():
    poor = client.post("/api/farm/buy/plots")
    assert poor.status_code == 400 and "costs" in poor.json()["detail"]
    with db.open_db(main.DB_PATH) as conn:
        db.save_farm(conn, 1, {**farm_stand.new_save(), "money": 100})
    farm = client.post("/api/farm/buy/plots").json()
    assert farm["plots"] == 5 and farm["money"] == 60
    assert client.post("/api/farm/buy/nope").status_code == 400
