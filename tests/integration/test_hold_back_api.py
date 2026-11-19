"""Integration tests for a grown-up holding keys back (app/lessons.py hold_back):
the keys leave practice, what they opened stays open, and the brain teaches them
again once the rest is solid."""

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main
from app.activities.teach_curriculum import INTRO_ID, PAIR_ID
from app.brain import lesson_ref
from tests.integration.lesson_helpers import run_lesson

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    lessons._LESSONS.clear()
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    client.post("/api/grownups/pin", json={"pin": "1234"})
    yield


def teach(*pairs):
    with db.open_db(main.DB_PATH) as conn:
        db.mark_taught(conn, 1, lesson_ref(INTRO_ID, ""), "lesson")
        for pair in pairs:
            db.mark_taught(conn, 1, lesson_ref(PAIR_ID, pair), "lesson")


def states():
    return {k["key"]: k["state"] for k in client.get("/api/parent/keys").json()["keys"]}


def pool():
    with db.open_db(main.DB_PATH) as conn:
        return lessons.taught_keys(conn, 1)


def test_the_keyboard_shows_each_keys_state():
    teach("fj", "dk")
    s = states()
    assert s["f"] == s["j"] == s["d"] == s["k"] == "pool"
    assert s["s"] == "new" and s["q"] == "new"


def test_holding_a_key_takes_its_lesson_partner_out_too():
    teach("fj", "dk", "sl")
    r = client.post("/api/parent/keys/hold", json={"key": "K"})
    assert r.status_code == 200, r.text
    assert r.json()["pair"] == "dk"
    s = states()
    assert s["d"] == s["k"] == "held" and s["s"] == "pool"
    assert "d" not in pool() and "k" not in pool() and "f" in pool()


def test_only_learned_keys_can_be_held_and_only_held_ones_let_back():
    teach("fj")
    assert client.post("/api/parent/keys/hold", json={"key": "q"}).status_code == 400
    assert client.post("/api/parent/keys/release", json={"key": "f"}).status_code == 400
    assert client.post("/api/parent/keys/hold", json={"key": " "}).status_code == 400


def test_letting_a_key_back_puts_it_straight_back_in_the_pool():
    teach("fj", "dk")
    client.post("/api/parent/keys/hold", json={"key": "d"})
    assert client.post("/api/parent/keys/release", json={"key": "d"}).status_code == 200
    assert states()["d"] == "pool" and "d" in pool()


def test_it_needs_the_grown_up_pin():
    teach("fj")
    client.post("/api/grownups/lock")
    assert client.post("/api/parent/keys/hold", json={"key": "f"}).status_code in (401, 403)


def test_what_the_keys_opened_stays_open():
    teach("fj", "dk", "sl", "a;", "gh")
    before = client.get("/api/me").json()["unlocks"]["pet_coupon"]
    client.post("/api/parent/keys/hold", json={"key": "g"})
    assert client.get("/api/me").json()["unlocks"]["pet_coupon"] == before
    with db.open_db(main.DB_PATH) as conn:
        assert {"g", "h"} <= lessons.earned_keys(conn, 1)


def test_the_brain_teaches_a_held_key_again_next(monkeypatch):
    teach("fj", "dk", "sl")
    client.post("/api/parent/keys/hold", json={"key": "d"})
    # as if every key still in the pool were solid already
    monkeypatch.setattr(lessons.brain, "learn_blocker", lambda inp: None)
    monkeypatch.setattr(lessons.brain, "current_sitting", lambda inp: [object()])
    monkeypatch.setattr(lessons.brain, "frustration", lambda *a: None)
    done = run_lesson(client)
    assert done["lesson"]["kind"] == "learn" and done["lesson"]["teach_keys"] == "dk"
    assert states()["d"] == "pool"
    with db.open_db(main.DB_PATH) as conn:
        assert lessons.held_back(conn, 1) == []


def test_a_held_key_is_not_practiced(monkeypatch):
    teach("fj", "dk", "sl", "a;")
    client.post("/api/parent/keys/hold", json={"key": "a"})
    with db.open_db(main.DB_PATH) as conn:
        inp = lessons.brain_input(conn, 1, main.now())
    assert "a" not in inp.taught_keys and ";" not in inp.taught_keys
