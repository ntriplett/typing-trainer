"""Integration tests for seeds and the garden: half the daily goal pays a
seed and waters the garden; plant, pick and the basket over HTTP."""

import pytest
from fastapi.testclient import TestClient

from app import db, lessons, main
from tests.integration.lesson_helpers import run_lesson, use_clock

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    lessons._LESSONS.clear()
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    client.put("/api/profiles/placement", json={"keys": "home_row", "speed": "some"})
    client.post("/api/grownups/pin", json={"pin": "1234"})
    client.put("/api/parent/settings", json={"goal_minutes": 2, "learn_vs_practice": 0.5})
    yield


@pytest.fixture
def clock(monkeypatch):
    return use_clock(monkeypatch)


def test_half_the_goal_pays_one_seed_and_waters(clock):
    early = run_lesson(client, clock, seconds=30)["done"]
    assert early["seeds_earned"] == [] and early["watered"] is None
    assert early["day"]["seed_seconds"] == 60 and not early["day"]["seed_reached"]

    half = run_lesson(client, clock, seconds=30)["done"]
    assert half["seeds_earned"] == [{"amount": 1, "reason": "daily_seed"}]
    assert half["watered"] == {"ripened": []}
    assert half["seed_balance"] == 1 and half["day"]["seed_reached"]

    more = run_lesson(client, clock, seconds=60)["done"]  # the goal: tokens, no second seed
    assert more["seeds_earned"] == [] and more["watered"] is None
    assert client.get("/api/me").json()["seeds"] == 1


def test_a_planted_seed_ripens_at_the_next_chunks_watering(clock):
    run_lesson(client, clock, seconds=60)
    planted = client.post("/api/garden/plant", json={"slot": 4})
    assert planted.status_code == 200
    body = planted.json()
    assert body["seeds"] == 0 and body["garden"]["spots"][4]["babies"] == 5

    clock.advance(hours=19)  # the unfinished chunk resets; a new one starts
    done = run_lesson(client, clock, seconds=60)["done"]
    assert [r["slot"] for r in done["watered"]["ripened"]] == [4]

    me = client.get("/api/me").json()
    assert me["garden"] == {"ready": 1, "growing": 1, "basket_total": 0, "seeds": 1}
    picked = client.post("/api/garden/pick", json={"slot": 4}).json()
    assert picked["done"]["count"] == 1
    assert sum(picked["garden"]["veggies"].values()) == 1


def test_garden_errors_are_kid_readable(clock):
    r = client.post("/api/garden/plant", json={"slot": 0})
    assert r.status_code == 400 and "seed" in r.json()["detail"]
    assert client.post("/api/garden/pick", json={"slot": 0}).status_code == 400
    assert client.post("/api/garden/basket").status_code == 400


def test_a_missed_stretch_withers_into_the_basket(clock):
    run_lesson(client, clock, seconds=60)
    client.post("/api/garden/plant", json={"slot": 0})
    clock.advance(hours=19)
    run_lesson(client, clock, seconds=60)  # ripens one
    clock.advance(hours=37)
    g = client.get("/api/garden").json()["garden"]
    assert g["growing"] == 0 and sum(g["basket"].values()) == 1
    collected = client.post("/api/garden/basket").json()
    assert sum(collected["garden"]["veggies"].values()) == 1
    with db.open_db(main.DB_PATH) as conn:
        assert db.get_basket(conn, 1) == {}
