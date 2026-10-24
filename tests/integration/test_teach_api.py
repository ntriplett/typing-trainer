"""Integration tests for the keyboard-driven teach module API and pages,
including the coins paid for finishing a lesson.
"""

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)
INTRO = "teach_intro_home_row_v1"
PAIR = "teach_key_pair_v1"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})
    yield


def _finish(module: str, keys: str = "", correct: int = 2, wrong: int = 0) -> dict:
    strokes = [{"expected_char": "f", "typed_char": "f", "correct": True, "latency_ms": 300}] * correct
    strokes += [{"expected_char": "f", "typed_char": "d", "correct": False, "latency_ms": 300}] * wrong
    resp = client.post(f"/api/teach/{module}/complete", params={"keys": keys}, json={"keys": ["f"], "keystrokes": strokes})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_list_modules_includes_intro_and_pairs():
    ids = {m["id"] for m in client.get("/api/teach/modules").json()}
    assert {INTRO, PAIR} <= ids


def test_lessons_list_covers_the_curriculum():
    data = client.get("/api/teach/lessons").json()
    assert data[0]["module"] == INTRO
    assert {"module": PAIR, "keys": "ei", "group": "Top row", "title": "E and I"} in data


def test_intro_content_has_show_and_type_steps():
    kinds = {s["kind"] for s in client.get(f"/api/teach/{INTRO}/content").json()["micro_steps"]}
    assert kinds == {"show", "type"}


def test_pair_content_uses_the_keys_param():
    data = client.get(f"/api/teach/{PAIR}/content", params={"keys": "c,"}).json()
    assert "c" in data["keys"] and "," in data["keys"]


@pytest.mark.parametrize("keys", ["", "abc", "ff", "€"])
def test_pair_content_rejects_bad_keys(keys):
    assert client.get(f"/api/teach/{PAIR}/content", params={"keys": keys}).status_code == 400


def test_unknown_module_404s_everywhere():
    assert client.get("/api/teach/nope/content").status_code == 404
    assert client.post("/api/teach/nope/complete", json={"keys": [], "keystrokes": []}).status_code == 404
    assert client.get("/teach/nope").status_code == 404


def test_intro_pays_250_the_first_time_whatever_the_accuracy():
    data = _finish(INTRO, correct=1, wrong=9)
    assert data["coins_earned"] == [{"amount": 250, "reason": "teach_first"}]
    assert data["coin_balance"] == 250
    assert data["result"]["accuracy"] == pytest.approx(0.1)


def test_intro_replay_pays_the_normal_rate():
    _finish(INTRO)
    again = _finish(INTRO, correct=9, wrong=1)
    assert again["coins_earned"] == [{"amount": 90, "reason": "teach"}]
    assert again["coin_balance"] == 340


def test_pair_lesson_pays_by_accuracy():
    data = _finish(PAIR, keys="dk", correct=4, wrong=1)
    assert data["coins_earned"] == [{"amount": 80, "reason": "teach"}]


def test_complete_needs_a_player():
    client.cookies.clear()
    resp = client.post(f"/api/teach/{INTRO}/complete", json={"keys": [], "keystrokes": []})
    assert resp.status_code == 401


def test_pages_are_served():
    assert "teach_player.js" in client.get(f"/teach/{INTRO}").text
    assert "lab-list" in client.get("/teach-lab").text
