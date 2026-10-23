"""Integration tests for the teach-demo API: stateless, no DB
persistence -- these just prove the HTTP surface works end to end.
"""

from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_list_modules_returns_all_three():
    resp = client.get("/api/teach-demo/modules")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert {m["id"] for m in data} == {
        "teach_hand_anchor_demo_v1",
        "teach_reach_return_demo_v1",
        "teach_staged_combo_demo_v1",
    }


def test_get_content_for_a_known_module():
    resp = client.get(
        "/api/teach-demo/teach_hand_anchor_demo_v1/content",
        params={"focus_key": "r", "allowed_keys": "f,j"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["micro_steps"]
    assert data["micro_steps"][0]["kind"] == "diagram"
    assert "r" in data["keys"]


def test_get_content_for_unknown_module_404s():
    resp = client.get(
        "/api/teach-demo/not-a-real-module/content", params={"focus_key": "r"}
    )
    assert resp.status_code == 404


def test_get_content_for_invalid_focus_key_400s_instead_of_crashing():
    # Regression: an empty or unrecognized focus_key used to reach
    # finger_for_key() and raise an unhandled ValueError -> 500.
    for bad_key in ("", "zz", "not-a-key"):
        resp = client.get(
            "/api/teach-demo/teach_hand_anchor_demo_v1/content",
            params={"focus_key": bad_key},
        )
        assert resp.status_code == 400, bad_key


def test_get_content_works_with_no_allowed_keys():
    resp = client.get(
        "/api/teach-demo/teach_staged_combo_demo_v1/content", params={"focus_key": "r"}
    )
    assert resp.status_code == 200
    assert resp.json()["micro_steps"]


def test_complete_scores_submitted_keystrokes():
    resp = client.post(
        "/api/teach-demo/teach_hand_anchor_demo_v1/complete",
        json={
            "keys": ["r", "f", "j"],
            "keystrokes": [
                {"expected_char": "r", "typed_char": "r", "correct": True, "latency_ms": 200},
                {"expected_char": "f", "typed_char": "f", "correct": True, "latency_ms": 180},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["accuracy"] == 1.0
    assert data["reward_signal"] == "nailed_it"


def test_complete_for_unknown_module_404s():
    resp = client.post(
        "/api/teach-demo/not-a-real-module/complete",
        json={"keys": ["r"], "keystrokes": []},
    )
    assert resp.status_code == 404


def test_complete_does_not_touch_the_real_learner_data(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    client.post(
        "/api/teach-demo/teach_hand_anchor_demo_v1/complete",
        json={
            "keys": ["r"],
            "keystrokes": [
                {"expected_char": "r", "typed_char": "r", "correct": True, "latency_ms": 200}
            ],
        },
    )
    # the demo endpoint never opens the DB -- the temp file shouldn't even exist
    assert not (tmp_path / "test.db").exists()


def test_teach_demo_page_is_served():
    resp = client.get("/teach-demo")
    assert resp.status_code == 200
