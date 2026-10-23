"""FastAPI app: the local server the launcher starts and the browser talks to.

Two things live here today:
  - the original walking-skeleton hello-world endpoint/page (kept as-is,
    still a useful smoke-test surface)
  - a real session flow: start a scheduler-built plan, serve each step's
    generated content, and accept completed keystrokes to score + persist

v1 simplification, called out explicitly: the in-progress plan for a
session lives in memory (_SESSION_PLANS), not the DB. A server restart
mid-session loses where you were -- acceptable for now since sessions
are short and this is for interactive/manual testing; the durable
record (key_stat, keystroke_log, session/session_event rows) is
written on every step completion regardless.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import analytics, bigram_model, db, scheduler, skill_model
from app.activities import get_activity
from app.activities.base import KeystrokeEvent
from app.activities.hello_world import HelloWorldActivity
from app.models import KeyStat
from app.scheduler import SessionPlan

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
DB_PATH = Path(__file__).resolve().parent.parent / "typing.db"

app = FastAPI(title="Typing Trainer")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

# session_id -> the plan built for it. See module docstring re: v1 scope.
_SESSION_PLANS: dict[int, SessionPlan] = {}


def get_db():
    with db.open_db(DB_PATH) as conn:
        yield conn


def ensure_learner(conn) -> int:
    """v1 is single-learner (PLAN.md Section 4) -- always learner id 1."""
    existing = db.get_learner(conn, 1)
    if existing:
        return existing.id
    created = db.create_learner(conn, "Learner")
    return created.id


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/activities/hello-world")
def hello_world_activity() -> dict:
    return HelloWorldActivity().generate()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/session")
def session_page() -> FileResponse:
    return FileResponse(WEB_DIR / "session.html")


@app.get("/analysis")
def analysis_page() -> FileResponse:
    return FileResponse(WEB_DIR / "analysis.html")


# --- analytics API -------------------------------------------------------------


@app.get("/api/analytics/keys")
def analytics_keys(conn=Depends(get_db)) -> list[dict]:
    learner_id = ensure_learner(conn)
    return analytics.key_report(conn, learner_id)


@app.get("/api/analytics/fingers")
def analytics_fingers(conn=Depends(get_db)) -> dict:
    learner_id = ensure_learner(conn)
    key_stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    return {finger: asdict(stat) for finger, stat in analytics.finger_stats(key_stats).items()}


@app.get("/api/analytics/bigrams")
def analytics_bigrams(limit: int = 10, conn=Depends(get_db)) -> list[dict]:
    learner_id = ensure_learner(conn)
    return [asdict(b) for b in analytics.worst_bigrams(conn, learner_id, limit=limit)]


@app.get("/api/analytics/trend")
def analytics_trend(days: int | None = None, conn=Depends(get_db)) -> list[dict]:
    learner_id = ensure_learner(conn)
    return analytics.daily_trend(conn, learner_id, days=days)


# --- session API --------------------------------------------------------------


def _serialize_step(step) -> dict:
    return {
        "phase": step.phase,
        "activity_id": step.activity_id,
        "focus_keys": step.focus_keys,
        "duration_s": step.duration_s,
        "content": asdict(step.content),
    }


class KeystrokeIn(BaseModel):
    expected_char: str
    typed_char: str
    correct: bool
    latency_ms: int


class CompleteStepRequest(BaseModel):
    keystrokes: list[KeystrokeIn]


@app.post("/api/session/start")
def start_session(conn=Depends(get_db)) -> dict:
    learner_id = ensure_learner(conn)
    key_stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}

    plan = scheduler.build_session_plan(key_stats, now=datetime.now(UTC))
    session = db.start_session(conn, learner_id)
    _SESSION_PLANS[session.id] = plan

    return {
        "session_id": session.id,
        "active_keys": plan.active_keys,
        "game_options": plan.game_options,
        "steps": [_serialize_step(s) for s in plan.steps],
    }


@app.post("/api/session/{session_id}/steps/{step_index}/complete")
def complete_step(
    session_id: int, step_index: int, body: CompleteStepRequest, conn=Depends(get_db)
) -> dict:
    plan = _SESSION_PLANS.get(session_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Unknown or expired session")
    if step_index < 0 or step_index >= len(plan.steps):
        raise HTTPException(status_code=404, detail="Unknown step index")

    step = plan.steps[step_index]
    activity = get_activity(step.activity_id)
    keystrokes = [KeystrokeEvent(**k.model_dump()) for k in body.keystrokes]
    result = activity.score(step.content, keystrokes)

    learner_id = ensure_learner(conn)
    now = datetime.now(UTC)

    event = db.log_session_event(conn, session_id, step.phase, step.activity_id)
    for seq, ke in enumerate(keystrokes):
        db.log_keystroke(
            conn, event.id, seq, ke.expected_char, ke.typed_char, ke.correct, ke.latency_ms
        )
    db.end_session_event(conn, event.id, summary_stats=asdict(result))

    _apply_keystrokes_to_skill_model(conn, learner_id, step.content.keys, keystrokes, now)
    _apply_keystrokes_to_bigram_model(conn, learner_id, keystrokes)

    session_complete = step_index == len(plan.steps) - 1
    if session_complete:
        db.end_session(conn, session_id)
        del _SESSION_PLANS[session_id]

    return {"result": asdict(result), "session_complete": session_complete}


def _apply_keystrokes_to_skill_model(
    conn, learner_id: int, focus_keys: list[str], keystrokes: list[KeystrokeEvent], now: datetime
) -> None:
    """Fold this step's keystrokes into each key's running stats and
    persist them -- the thing that makes tomorrow's plan different from
    today's.
    """
    touched: dict[str, KeyStat] = {}

    def get_or_new(key: str) -> KeyStat:
        if key in touched:
            return touched[key]
        existing = db.get_key_stat(conn, learner_id, key)
        return existing if existing is not None else skill_model.new_key_stat(learner_id, key)

    for key in focus_keys:
        touched[key] = skill_model.mark_unlocked(get_or_new(key), now)

    for ke in keystrokes:
        stat = get_or_new(ke.expected_char)
        touched[ke.expected_char] = skill_model.record_attempt(
            stat, correct=ke.correct, latency_ms=ke.latency_ms, now=now
        )

    for stat in touched.values():
        db.upsert_key_stat(conn, stat)


def _apply_keystrokes_to_bigram_model(
    conn, learner_id: int, keystrokes: list[KeystrokeEvent]
) -> None:
    """Fold this step's consecutive keystroke pairs into bigram_stat.

    One batch at the end of the step, not a write per keystroke (PLAN.md
    Section 2's research basis doesn't call for live bigram adaptation --
    this is detail-level data for the analysis page and recommender).
    """
    for key1, key2, correct, latency_ms in bigram_model.bigrams_from_keystrokes(keystrokes):
        existing = db.get_bigram_stat(conn, learner_id, key1, key2)
        stat = existing if existing is not None else bigram_model.new_bigram_stat(learner_id, key1, key2)
        updated = bigram_model.record_bigram_attempt(stat, correct=correct, latency_ms=latency_ms)
        db.upsert_bigram_stat(conn, updated)
