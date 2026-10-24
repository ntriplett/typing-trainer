"""Integration tests for player profiles (PLAN.md 11d): pick/create with a
per-browser cookie, switching, placement, and two players at once."""

import pytest
from fastapi.testclient import TestClient

from app import db, main, skill_model


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    main._SESSION_PLANS.clear()
    yield


def browser() -> TestClient:
    """A fresh client = a separate browser with its own cookies."""
    return TestClient(main.app)


def test_no_player_picked_is_a_401():
    resp = browser().get("/api/me")
    assert resp.status_code == 401


def test_create_picks_the_new_player():
    b = browser()
    me = b.post("/api/profiles", json={"name": "Robin"}).json()
    assert me["learner"]["name"] == "Robin"
    assert b.get("/api/me").json()["learner"]["id"] == me["learner"]["id"]


def test_names_must_be_unique_and_non_blank():
    b = browser()
    b.post("/api/profiles", json={"name": "Robin"})
    assert b.post("/api/profiles", json={"name": "robin"}).status_code == 400
    assert b.post("/api/profiles", json={"name": "   "}).status_code == 400


def test_list_select_and_logout():
    b = browser()
    robin = b.post("/api/profiles", json={"name": "Robin"}).json()["learner"]["id"]
    sam = b.post("/api/profiles", json={"name": "Sam"}).json()["learner"]["id"]
    assert [p["name"] for p in browser().get("/api/profiles").json()] == ["Robin", "Sam"]

    assert b.get("/api/me").json()["learner"]["id"] == sam
    b.post(f"/api/profiles/{robin}/select")
    assert b.get("/api/me").json()["learner"]["id"] == robin
    b.post("/api/profiles/logout")
    assert b.get("/api/me").status_code == 401
    assert b.post("/api/profiles/999/select").status_code == 404


def test_two_browsers_play_at_once_without_mixing():
    robin, sam = browser(), browser()
    robin.post("/api/profiles", json={"name": "Robin"})
    sam.post("/api/profiles", json={"name": "Sam"})
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, 1000, "test")  # Robin only
    robin.post("/api/store/buy/hat_straw")
    robin.post("/api/store/equip/hat_straw")

    assert robin.get("/api/me").json()["coins"] == 700
    assert sam.get("/api/me").json()["coins"] == 0
    assert "hat" not in sam.get("/api/me").json()["avatar"]
    assert robin.get("/api/me").json()["avatar"]["hat"] == "hat_straw"


def test_placement_marks_known_keys_learned_and_sets_speed():
    b = browser()
    b.post("/api/profiles", json={"name": "Robin"})
    assert b.put("/api/profiles/placement", json={"keys": "home_row", "speed": "comfy"}).status_code == 200
    with db.open_db(main.DB_PATH) as conn:
        stats = {s.key: s for s in db.list_key_stats(conn, 1)}
    assert set(stats) == set(skill_model.KEY_ORDER[:11])
    assert all(s.mastered_at is not None for s in stats.values())

    start = b.post("/api/session/start").json()
    assert start["estimated_wpm"] == 22
    # lessons now start past the home row
    assert skill_model.KEY_ORDER[11] in start["active_keys"]
    assert b.put("/api/profiles/placement", json={"keys": "?", "speed": "comfy"}).status_code == 400


def test_new_placement_teaches_from_scratch():
    b = browser()
    b.post("/api/profiles", json={"name": "Robin"})
    b.put("/api/profiles/placement", json={"keys": "new", "speed": "starting"})
    start = b.post("/api/session/start").json()
    assert start["steps"][0]["focus_keys"] == [" "]  # the space bar lesson first


def test_wardrobe_lists_owned_wearables_including_starters():
    b = browser()
    b.post("/api/profiles", json={"name": "Robin"})
    slots = b.get("/api/wardrobe").json()["slots"]
    assert [i["id"] for i in slots["shirt"]] == ["shirt_tunic"]
    assert slots["hat"] == []
    assert "background" not in slots


def test_new_pages_are_served():
    b = browser()
    for path in ("/welcome", "/placement", "/wardrobe"):
        assert b.get(path).status_code == 200
