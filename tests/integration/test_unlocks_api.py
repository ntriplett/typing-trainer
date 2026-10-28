"""Integration tests for rooms that unlock as letters are learned: the
Bedroom (top row). Pets are open from the start (the Pet Shop opens its
departments itself, tests/integration/test_pet_shop_api.py)."""

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


def test_a_new_player_has_the_bedroom_locked():
    u = unlocks()
    assert not u["bedroom"] and "pets" not in u and not u["pet_coupon"]
    assert u["missing"]["bedroom"] == "qwertyuiop"
    assert client.get("/api/room").status_code == 403


def test_bedroom_things_cant_be_bought_while_its_locked():
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, 5000, "test")
    assert client.post("/api/store/buy/furniture_bed_blue").status_code == 403


def test_the_home_row_brings_the_pet_coupon():
    teach("fj", "dk", "sl", "a;", "gh")
    u = unlocks()
    assert u["pet_coupon"] and not u["bedroom"]


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
    assert done["done"]["unlocked"] == []  # nothing to unlock: pets are open from the start
    assert unlocks()["pet_coupon"]
