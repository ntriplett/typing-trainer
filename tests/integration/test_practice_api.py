"""Integration tests for the practice lab API and the keyboard hint purchase."""

import pytest
from fastapi.testclient import TestClient

from app import db, main

client = TestClient(main.app)
FISH = "practice_fishing_v1"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    yield


def _give_coins(amount: int) -> None:
    with db.open_db(main.DB_PATH) as conn:
        db.add_coins(conn, 1, amount, "test")


def test_modules_lists_plain_plus_ten_themes():
    data = client.get("/api/practice/modules").json()
    assert len(data) == 11
    assert {m["scene"] for m in data if m["scene"]} >= {"fishing", "garden", "rocket", "frog"}


def test_content_uses_key_set_focus_length_and_difficulty():
    short = client.get(f"/api/practice/{FISH}/content", params={"keys": "home", "focus": "dk", "length": "short"}).json()
    long = client.get(f"/api/practice/{FISH}/content", params={"keys": "home", "focus": "dk", "length": "long"}).json()
    assert short["scene"] == "fishing" and short["title"] == "Gone fishing"
    assert set(short["prompt"]) <= set("asdfghjkl; ")
    assert "[d] and [k]" in short["instructions"]
    assert len(long["prompt"]) > 2 * len(short["prompt"])


def test_focus_outside_the_key_set_is_added():
    data = client.get(f"/api/practice/{FISH}/content", params={"keys": "home", "focus": "e"}).json()
    assert "e" in data["keys"]


@pytest.mark.parametrize("params", [{"keys": "nope"}, {"length": "huge"}, {"difficulty": "impossible"}])
def test_bad_options_400(params):
    assert client.get(f"/api/practice/{FISH}/content", params=params).status_code == 400


def test_unknown_module_404s():
    assert client.get("/api/practice/nope/content").status_code == 404
    assert client.get("/practice/nope").status_code == 404


def test_complete_pays_coins_counting_wrap_spaces_as_done():
    strokes = [{"expected_char": "a", "typed_char": "a", "correct": True, "latency_ms": 200}] * 8
    data = client.post(
        f"/api/practice/{FISH}/complete",
        json={"keys": ["a"], "prompt_length": 10, "skipped_chars": 2, "keystrokes": strokes},
    ).json()
    assert data["coins_earned"] == [{"amount": 100, "reason": "lesson"}]


def test_keyboard_hint_costs_ten_coins():
    _give_coins(25)
    data = client.post("/api/hint/keyboard", json={"ref": "session:1:2"}).json()
    assert data == {"spent": 10, "coin_balance": 15}


def test_keyboard_hint_needs_enough_coins():
    _give_coins(5)
    resp = client.post("/api/hint/keyboard", json={})
    assert resp.status_code == 402
    assert client.get("/api/me").json()["coins"] == 5


def test_pages_are_served():
    assert "lab-cards" in client.get("/practice-lab").text
    assert "practice_stage.js" in client.get(f"/practice/{FISH}").text
