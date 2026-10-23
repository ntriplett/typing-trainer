"""Integration tests for the real session flow: start a scheduler-built
plan, submit keystrokes for a step, confirm scoring + persistence.

Each test gets its own temp SQLite file (via monkeypatching app.main.DB_PATH)
so tests don't share state through a real typing.db on disk.
"""

import pytest
from fastapi.testclient import TestClient

from app import db, main
from app.skill_model import INITIAL_ACTIVE_KEY_COUNT

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    main._SESSION_PLANS.clear()
    yield


def _keystrokes_for(content: dict, all_correct: bool = True) -> list[dict]:
    """Build a keystroke list that exercises every char in the prompt."""
    result = []
    for ch in content["prompt"]:
        if ch == " ":
            continue
        result.append(
            {
                "expected_char": ch,
                "typed_char": ch if all_correct else "?",
                "correct": all_correct,
                "latency_ms": 200,
            }
        )
    return result


def test_start_session_returns_a_full_plan():
    resp = client.post("/api/session/start")
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data["session_id"], int)
    assert len(data["active_keys"]) == INITIAL_ACTIVE_KEY_COUNT
    phases = [s["phase"] for s in data["steps"]]
    # brand-new learner: warmup + teach (room to grow) + practice + game, no eval yet
    assert phases == ["warmup", "teach", "practice", "game"]
    for step in data["steps"]:
        assert step["content"]["prompt"]


def test_quick_mode_produces_much_shorter_prompts():
    normal = client.post("/api/session/start").json()
    quick = client.post("/api/session/start?quick=1").json()

    normal_len = len(normal["steps"][0]["content"]["prompt"])
    quick_len = len(quick["steps"][0]["content"]["prompt"])
    assert quick_len < normal_len


def test_complete_step_scores_and_is_not_session_complete_yet():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    step0 = start["steps"][0]

    resp = client.post(
        f"/api/session/{session_id}/steps/0/complete",
        json={"keystrokes": _keystrokes_for(step0["content"])},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_complete"] is False
    assert data["result"]["accuracy"] == 1.0
    assert data["result"]["reward_signal"] == "nailed_it"


def test_completing_a_step_persists_key_stats():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    step0 = start["steps"][0]
    focus_key = step0["focus_keys"][0]

    client.post(
        f"/api/session/{session_id}/steps/0/complete",
        json={"keystrokes": _keystrokes_for(step0["content"])},
    )

    with db.open_db(main.DB_PATH) as conn:
        stat = db.get_key_stat(conn, 1, focus_key)
        assert stat is not None
        assert stat.sample_count > 0
        assert stat.unlocked_at is not None


def test_completing_a_step_persists_bigram_stats():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    step0 = start["steps"][0]

    client.post(
        f"/api/session/{session_id}/steps/0/complete",
        json={"keystrokes": _keystrokes_for(step0["content"])},
    )

    with db.open_db(main.DB_PATH) as conn:
        pairs = db.list_bigram_stats(conn, 1)
        assert len(pairs) > 0
        assert all(p.accuracy_rolling == 1.0 for p in pairs)  # all-correct keystrokes in this test


def test_full_session_runs_through_every_step_and_ends():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    steps = start["steps"]

    last_response = None
    for i, step in enumerate(steps):
        last_response = client.post(
            f"/api/session/{session_id}/steps/{i}/complete",
            json={"keystrokes": _keystrokes_for(step["content"])},
        )
        assert last_response.status_code == 200

    assert last_response.json()["session_complete"] is True

    with db.open_db(main.DB_PATH) as conn:
        row = conn.execute(
            "SELECT ended_at FROM session WHERE id = ?", (session_id,)
        ).fetchone()
        assert row["ended_at"] is not None


def test_complete_step_with_mistakes_scores_lower_and_does_not_crash():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    step0 = start["steps"][0]

    resp = client.post(
        f"/api/session/{session_id}/steps/0/complete",
        json={"keystrokes": _keystrokes_for(step0["content"], all_correct=False)},
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["accuracy"] == 0.0


def test_unknown_session_id_returns_404():
    resp = client.post(
        "/api/session/999999/steps/0/complete", json={"keystrokes": []}
    )
    assert resp.status_code == 404


def test_out_of_range_step_index_returns_404():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    resp = client.post(
        f"/api/session/{session_id}/steps/999/complete", json={"keystrokes": []}
    )
    assert resp.status_code == 404


def test_session_page_is_served():
    resp = client.get("/session")
    assert resp.status_code == 200
    assert "Typing Trainer" in resp.text
