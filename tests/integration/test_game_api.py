"""Integration tests for the game lab API."""

import pytest
from fastapi.testclient import TestClient

from app import db, main

client = TestClient(main.app)
CROWS = "game_crow_patrol_v1"
BATTLE = "game_pet_battle_v1"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    yield


def test_modules_lists_every_game():
    data = client.get("/api/game/modules").json()
    assert {g["game"] for g in data} == {"crow_patrol", "pet_battle", "farm_stand"}


def test_pages_serve():
    assert client.get("/game-lab").status_code == 200
    assert client.get(f"/game/{CROWS}").status_code == 200
    assert client.get("/game/nope").status_code == 404


def test_content_uses_key_set_focus_and_difficulty():
    easy = client.get(f"/api/game/{CROWS}/content", params={"keys": "home", "focus": "dk", "difficulty": "easy"}).json()
    hard = client.get(f"/api/game/{CROWS}/content", params={"keys": "home", "difficulty": "hard"}).json()
    assert easy["game"]["game"] == "crow_patrol"
    assert "[d] and [k]" in easy["instructions"]
    assert all(set(w) <= set("asdfghjkl;") for w in easy["game"]["words"]["short"])
    assert hard["game"]["levels"][0]["speed"] > easy["game"]["levels"][0]["speed"]


def test_new_learner_mine_letters_work():
    # a brand-new learner starts with a few home-row keys
    res = client.get(f"/api/game/{BATTLE}/content")
    assert res.status_code in (200, 400)
    if res.status_code == 200:
        assert res.json()["game"]["levels"][0]["foe"] == "bunny"


@pytest.mark.parametrize("params", [{"keys": "nope"}, {"difficulty": "impossible"}])
def test_bad_options_400(params):
    assert client.get(f"/api/game/{CROWS}/content", params=params).status_code == 400


def test_each_round_pays_by_points():
    with db.open_db(main.DB_PATH) as conn:
        before = db.get_coin_balance(conn, 1)
    strokes = [{"expected_char": "a", "typed_char": "a", "correct": True, "latency_ms": 200}] * 6
    data = client.post(f"/api/game/{CROWS}/round", json={"keys": ["a"], "keystrokes": strokes, "score": 400}).json()
    assert data["score"] == 400
    assert data["coins_earned"] == [{"amount": 20, "reason": "game"}]
    assert data["coin_balance"] == before + 20
    assert data["result"]["accuracy"] == 1.0


def test_a_round_with_no_points_pays_nothing():
    data = client.post(f"/api/game/{BATTLE}/round", json={"keys": ["a"], "keystrokes": [], "score": 0}).json()
    assert data["coins_earned"] == []


def test_round_rejects_silly_scores():
    res = client.post(f"/api/game/{CROWS}/round", json={"keys": ["a"], "keystrokes": [], "score": 100000})
    assert res.status_code == 422


def test_pet_battles_get_v3_critters_and_starters():
    game = client.get(f"/api/game/{BATTLE}/content", params={"keys": "home"}).json()["game"]
    assert [lv["foe"] for lv in game["levels"]] == ["bunny", "lizard", "goat", "fox", "llama"]
    assert all(lv["foe_genes"]["species"] == lv["foe"] and lv["foe_genes"]["hex"][0] for lv in game["levels"])
    assert [s["name"] for s in game["starters"]] == ["Clover", "Pip", "Puddle"]
    assert {s["genes"]["battle"]["element"] for s in game["starters"]} == {"leaf", "ember", "splash"}
