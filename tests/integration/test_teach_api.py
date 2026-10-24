"""Integration tests for the keyboard-driven teach module API and page.
Stateless like the teach demo: nothing is saved yet.
"""

from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)
INTRO = "teach_intro_home_row_v1"


def test_list_modules_includes_the_intro():
    resp = client.get("/api/teach/modules")
    assert resp.status_code == 200
    assert INTRO in {m["id"] for m in resp.json()}


def test_content_has_show_and_type_steps():
    resp = client.get(f"/api/teach/{INTRO}/content")
    assert resp.status_code == 200
    kinds = {s["kind"] for s in resp.json()["micro_steps"]}
    assert kinds == {"show", "type"}


def test_unknown_module_404s_everywhere():
    assert client.get("/api/teach/nope/content").status_code == 404
    assert client.post("/api/teach/nope/complete", json={"keys": [], "keystrokes": []}).status_code == 404
    assert client.get("/teach/nope").status_code == 404


def test_complete_scores_keystrokes():
    body = {
        "keys": ["f", "j"],
        "keystrokes": [
            {"expected_char": "f", "typed_char": "f", "correct": True, "latency_ms": 300},
            {"expected_char": "j", "typed_char": "j", "correct": True, "latency_ms": 300},
        ],
    }
    resp = client.post(f"/api/teach/{INTRO}/complete", json=body)
    assert resp.status_code == 200
    assert resp.json()["accuracy"] == 1.0


def test_page_is_served():
    resp = client.get(f"/teach/{INTRO}")
    assert resp.status_code == 200
    assert "teach_player.js" in resp.text
