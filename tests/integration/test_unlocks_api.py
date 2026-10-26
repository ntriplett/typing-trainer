"""Integration tests for rooms that unlock as letters are learned: the Pet
Room (home row, with a free first pet) and the Bedroom (top row)."""

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main
from app.activities.teach_curriculum import PAIR_ID
from app.brain import lesson_ref
from tests.integration.lesson_helpers import run_lesson

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    lessons._LESSONS.clear()
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    yield


def unlocks():
    return client.get("/api/me").json()["unlocks"]


def teach(*pairs):
    with db.open_db(main.DB_PATH) as conn:
        for pair in pairs:
            db.mark_taught(conn, 1, lesson_ref(PAIR_ID, pair), "lesson")


def test_a_new_player_has_both_rooms_locked():
    u = unlocks()
    assert (u["pets"], u["bedroom"], u["free_pet"]) == (False, False, False)
    assert u["missing"]["pets"] == "asdfghjkl;"
    assert client.get("/api/pets").status_code == 403
    assert client.get("/api/room").status_code == 403
    assert "home row" in client.post("/api/pets/adopt", json={"species": "dog", "color": "golden"}).json()["detail"]


def test_bedroom_things_cant_be_bought_while_its_locked():
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, 5000, "test")
    assert client.post("/api/store/buy/furniture_bed_blue").status_code == 403


def test_the_home_row_opens_the_pet_room_with_one_free_pet():
    teach("fj", "dk", "sl", "a;", "gh")
    u = unlocks()
    assert u["pets"] and u["free_pet"] and not u["bedroom"]
    data = client.post("/api/pets/adopt", json={"species": "fox", "color": "red"}).json()
    assert data["coins"] == 0  # free
    assert data["pets"][0]["stage"] == "baby"
    assert not data["unlocks"]["free_pet"]
    again = client.post("/api/pets/adopt", json={"species": "fox", "color": "red"})
    assert again.status_code == 400  # the next one costs coins


def test_the_top_row_opens_the_bedroom():
    teach("fj", "dk", "sl", "a;", "gh", "ru", "ei", "wo", "qp", "ty")
    assert unlocks()["bedroom"]
    assert client.get("/api/room").status_code == 200


def test_finishing_the_last_home_row_lesson_reports_the_unlock(monkeypatch):
    teach("fj", "dk", "sl", "a;")
    with db.open_db(main.DB_PATH) as conn:
        db.mark_taught(conn, 1, "teach_intro_home_row_v1:", "lesson")
    # make the brain pick the next new lesson (G and H) right away
    monkeypatch.setattr(lessons.brain, "learn_blocker", lambda inp: None)
    monkeypatch.setattr(lessons.brain, "current_sitting", lambda inp: [object()])
    monkeypatch.setattr(lessons.brain, "frustration", lambda *a: None)
    done = run_lesson(client)
    assert done["lesson"]["teach_keys"] == "gh"
    assert done["done"]["unlocked"] == ["pets"]
    assert done["done"]["free_pet"]


def test_players_with_pets_keep_their_pet_room():
    with db.open_db(main.DB_PATH) as conn:
        db.add_pet(conn, 1, "dog", "golden", "Rex", growth=3, slot=None)
    u = unlocks()
    assert u["pets"] and not u["free_pet"]
