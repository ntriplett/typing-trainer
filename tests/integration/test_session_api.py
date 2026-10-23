"""Integration tests for the real session flow: build a skeleton from
the learner's config, fetch each step's lazily-generated content,
submit keystrokes, confirm scoring + persistence + the running WPM
estimate updates.

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


def _content_for(session_id: int, index: int, start_response: dict) -> dict:
    """Step 0's content comes back with /start; every other step is
    fetched lazily via the content endpoint, exactly as the front-end
    would.
    """
    if index == 0:
        return start_response["first_step_content"]
    resp = client.get(f"/api/session/{session_id}/steps/{index}/content")
    assert resp.status_code == 200
    return resp.json()["content"]


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


def test_start_session_returns_a_skeleton_and_first_step_content():
    resp = client.post("/api/session/start")
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data["session_id"], int)
    assert len(data["active_keys"]) == INITIAL_ACTIVE_KEY_COUNT
    assert data["estimated_wpm"] > 0
    phases = [s["phase"] for s in data["steps"]]
    # brand-new learner, default config: ~10 short steps, opening with warmup,
    # with at least one teach step since there's plenty of room to grow
    assert phases[0] == "warmup"
    assert "teach" in phases
    assert 8 <= len(phases) <= 12
    # skeleton steps carry no content -- that's generated lazily
    for step in data["steps"]:
        assert "content" not in step
    assert data["first_step_content"]["prompt"]


def test_config_duration_affects_total_time_budget():
    short = client.post("/api/session/start", json={"duration_minutes": 15}).json()
    long = client.post("/api/session/start", json={"duration_minutes": 30}).json()
    short_total = sum(s["duration_s"] for s in short["steps"])
    long_total = sum(s["duration_s"] for s in long["steps"])
    assert long_total > short_total


def test_config_learn_vs_practice_zero_skips_teach():
    data = client.post("/api/session/start", json={"learn_vs_practice": 0.0}).json()
    assert "teach" not in [s["phase"] for s in data["steps"]]


def test_quick_mode_produces_much_shorter_prompts():
    normal = client.post("/api/session/start").json()
    quick = client.post("/api/session/start?quick=1").json()
    assert len(quick["first_step_content"]["prompt"]) < len(normal["first_step_content"]["prompt"])
    assert quick["steps"][0]["duration_s"] < normal["steps"][0]["duration_s"]


def test_get_step_content_generates_and_caches():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]

    first = client.get(f"/api/session/{session_id}/steps/1/content").json()
    second = client.get(f"/api/session/{session_id}/steps/1/content").json()
    assert first == second  # cached, not regenerated differently each call


def test_complete_step_scores_and_is_not_session_complete_yet():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    content0 = _content_for(session_id, 0, start)

    resp = client.post(
        f"/api/session/{session_id}/steps/0/complete",
        json={"keystrokes": _keystrokes_for(content0)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_complete"] is False
    assert data["result"]["accuracy"] == 1.0
    assert data["result"]["reward_signal"] == "nailed_it"
    assert "estimated_wpm" in data


def test_fast_typing_raises_the_estimated_wpm_for_later_steps():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    content0 = _content_for(session_id, 0, start)

    # Blazing fast, fully correct -- should pull the estimate up a lot
    # from the beginner default.
    keystrokes = [
        {"expected_char": ch, "typed_char": ch, "correct": True, "latency_ms": 50}
        for ch in content0["prompt"]
        if ch != " "
    ]
    resp = client.post(
        f"/api/session/{session_id}/steps/0/complete", json={"keystrokes": keystrokes}
    )
    assert resp.json()["estimated_wpm"] > start["estimated_wpm"]


def test_completing_a_step_persists_key_stats():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    content0 = _content_for(session_id, 0, start)
    focus_key = start["steps"][0]["focus_keys"][0]

    client.post(
        f"/api/session/{session_id}/steps/0/complete",
        json={"keystrokes": _keystrokes_for(content0)},
    )

    with db.open_db(main.DB_PATH) as conn:
        stat = db.get_key_stat(conn, 1, focus_key)
        assert stat is not None
        assert stat.sample_count > 0
        assert stat.unlocked_at is not None


def test_completing_a_step_persists_bigram_stats():
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    content0 = _content_for(session_id, 0, start)

    client.post(
        f"/api/session/{session_id}/steps/0/complete",
        json={"keystrokes": _keystrokes_for(content0)},
    )

    with db.open_db(main.DB_PATH) as conn:
        pairs = db.list_bigram_stats(conn, 1)
        assert len(pairs) > 0
        assert all(p.accuracy_rolling == 1.0 for p in pairs)  # all-correct keystrokes in this test


def test_full_session_runs_through_every_step_and_ends():
    start = client.post("/api/session/start?quick=1").json()
    session_id = start["session_id"]
    steps = start["steps"]

    last_response = None
    for i in range(len(steps)):
        content = _content_for(session_id, i, start)
        last_response = client.post(
            f"/api/session/{session_id}/steps/{i}/complete",
            json={"keystrokes": _keystrokes_for(content)},
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
    content0 = _content_for(session_id, 0, start)

    resp = client.post(
        f"/api/session/{session_id}/steps/0/complete",
        json={"keystrokes": _keystrokes_for(content0, all_correct=False)},
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


def test_content_endpoint_404s_for_unknown_session():
    resp = client.get("/api/session/999999/steps/0/content")
    assert resp.status_code == 404


def test_session_page_is_served():
    resp = client.get("/session")
    assert resp.status_code == 200
    assert "Typing Trainer" in resp.text
