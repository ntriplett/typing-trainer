"""Integration tests for the analytics read endpoints, driven through
the real session API so the data is exactly what a real session would
produce (not hand-inserted rows).
"""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.skill_model import KEY_ORDER

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    main._SESSION_PLANS.clear()
    client.cookies.clear()
    client.post("/api/profiles", json={"name": "Tester"})  # picks the player (cookie) as learner 1
    yield


def _run_one_step():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    step0 = start["steps"][0]
    keystrokes = [
        {"expected_char": ch, "typed_char": ch, "correct": True, "latency_ms": 200}
        for ch in start["first_step_content"]["prompt"]  # spaces included, as the front-end sends them
    ]
    client.post(f"/api/session/{session_id}/steps/0/complete", json={"keystrokes": keystrokes})
    return step0


def test_analytics_keys_lists_every_key():
    resp = client.get("/api/analytics/keys")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(KEY_ORDER)
    assert {row["key"] for row in data} == set(KEY_ORDER)


def test_analytics_keys_reflects_a_completed_step():
    step0 = _run_one_step()
    focus_key = step0["focus_keys"][0]

    data = client.get("/api/analytics/keys").json()
    entry = next(r for r in data if r["key"] == focus_key)
    assert entry["sample_count"] > 0
    assert entry["unlocked"] is True


def test_analytics_fingers_covers_all_eight_fingers_plus_thumbs():
    resp = client.get("/api/analytics/fingers")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 9
    assert "left_index" in data
    assert data["thumb"]["keys"] == [" "]


def test_analytics_bigrams_empty_before_any_activity():
    resp = client.get("/api/analytics/bigrams")
    assert resp.status_code == 200
    assert resp.json() == []  # nothing has enough samples yet


def test_analytics_trend_reflects_a_completed_step():
    _run_one_step()
    resp = client.get("/api/analytics/trend")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["count"] == 1
