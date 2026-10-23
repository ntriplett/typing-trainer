"""FastAPI app: the local server the launcher starts and the browser talks to.

Two things live here today:
  - the original walking-skeleton hello-world endpoint/page (kept as-is,
    still a useful smoke-test surface)
  - a real session flow: build a scheduler skeleton from the learner's
    pre-session choices, generate each step's content lazily (so later
    steps can adapt to today's observed typing speed), and accept
    completed keystrokes to score + persist

v1 simplification, called out explicitly: the in-progress session
runtime (skeleton + generated-content cache + the running WPM estimate)
lives in memory (_SESSION_PLANS), not the DB. A server restart
mid-session loses where you were -- acceptable for now since sessions
are short and this is for interactive/manual testing; the durable
record (key_stat, keystroke_log, session/session_event rows) is
written on every step completion regardless.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import analytics, bigram_model, db, scheduler, skill_model
from app.activities import get_activity
from app.activities.base import ActivityContent, KeystrokeEvent
from app.activities.hello_world import HelloWorldActivity
from app.models import KeyStat
from app.scheduler import SessionConfig, SessionSkeleton, StepPlan

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
DB_PATH = Path(__file__).resolve().parent.parent / "typing.db"

app = FastAPI(title="Typing Trainer")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.middleware("http")
async def no_cache_responses(request, call_next):
    """Neither StaticFiles nor FileResponse set Cache-Control, which
    leaves browsers free to apply heuristic caching -- silently reusing
    an old response without even a conditional request. That's produced
    the "I fixed the bug but the browser is still showing the old
    version" confusion more than once, and it wasn't limited to JS/CSS
    under /static/: the page routes themselves (/, /session, /analysis)
    are just as cacheable, which is exactly what made the analysis page
    (served from analysis.html) need a hard refresh after being edited.
    Force no-store on every response while this is actively changing;
    revisit with real cache-busting (versioned filenames) once the
    front-end stabilizes.
    """
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@dataclass
class SessionRuntime:
    """Everything the server needs to keep track of mid-session.

    `estimated_wpm` is mutable on purpose -- complete_step() updates it
    after every scored step, and get_step_content() reads the current
    value when it generates a not-yet-seen step. That's the whole
    mechanism behind "later lessons adapt to how fast things are going."
    """

    skeleton: SessionSkeleton
    estimated_wpm: float
    learner_id: int
    content_cache: dict[int, ActivityContent] = field(default_factory=dict)


# session_id -> its runtime. See module docstring re: v1 scope.
_SESSION_PLANS: dict[int, SessionRuntime] = {}


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


class SessionConfigIn(BaseModel):
    """The pre-session slider screen's choices."""

    duration_minutes: int = Field(default=15, ge=5, le=60)
    learn_vs_practice: float = Field(default=0.5, ge=0.0, le=1.0)
    focus_vs_general: float = Field(default=0.3, ge=0.0, le=1.0)


class KeystrokeIn(BaseModel):
    expected_char: str
    typed_char: str
    correct: bool
    latency_ms: int


class CompleteStepRequest(BaseModel):
    keystrokes: list[KeystrokeIn]


def _serialize_skeleton_step(step: StepPlan) -> dict:
    return {
        "phase": step.phase,
        "activity_id": step.activity_id,
        "focus_keys": step.focus_keys,
        "duration_s": step.duration_s,
    }


@app.post("/api/session/start")
def start_session(
    config: SessionConfigIn = SessionConfigIn(), quick: bool = False, conn=Depends(get_db)
) -> dict:
    learner_id = ensure_learner(conn)
    key_stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    bigram_stats = db.list_bigram_stats(conn, learner_id)

    # `quick` is a dev/testing convenience (PLAN.md's "very short smoke
    # session"), not a different pedagogy: it shrinks both the total
    # time budget AND each step's length, so a smoke test isn't just
    # fewer ~1-2 minute steps at the normal length.
    session_config = SessionConfig(
        duration_minutes=2 if quick else config.duration_minutes,
        learn_vs_practice=config.learn_vs_practice,
        focus_vs_general=config.focus_vs_general,
    )
    skeleton = scheduler.build_session_skeleton(
        key_stats,
        session_config,
        now=datetime.now(UTC),
        bigram_stats=bigram_stats,
        step_seconds_scale=0.15 if quick else 1.0,
    )

    estimated_wpm = analytics.estimate_starting_wpm(conn, learner_id)
    session = db.start_session(conn, learner_id)
    runtime = SessionRuntime(skeleton=skeleton, estimated_wpm=estimated_wpm, learner_id=learner_id)
    _SESSION_PLANS[session.id] = runtime

    first_content = scheduler.generate_step_content(skeleton.steps[0], estimated_wpm)
    runtime.content_cache[0] = first_content

    return {
        "session_id": session.id,
        "active_keys": skeleton.active_keys,
        "game_options": skeleton.game_options,
        "estimated_wpm": estimated_wpm,
        "steps": [_serialize_skeleton_step(s) for s in skeleton.steps],
        "first_step_content": asdict(first_content),
    }


@app.get("/api/session/{session_id}/steps/{step_index}/content")
def get_step_content(session_id: int, step_index: int) -> dict:
    """Generate (if not already cached) and return one step's actual
    typing content, sized to the session's CURRENT WPM estimate rather
    than whatever it was when the session started -- this is what lets
    a later step's content length reflect how today has actually gone.
    """
    runtime = _SESSION_PLANS.get(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Unknown or expired session")
    if step_index < 0 or step_index >= len(runtime.skeleton.steps):
        raise HTTPException(status_code=404, detail="Unknown step index")

    if step_index not in runtime.content_cache:
        step = runtime.skeleton.steps[step_index]
        runtime.content_cache[step_index] = scheduler.generate_step_content(
            step, runtime.estimated_wpm
        )

    return {"content": asdict(runtime.content_cache[step_index])}


@app.post("/api/session/{session_id}/steps/{step_index}/complete")
def complete_step(
    session_id: int, step_index: int, body: CompleteStepRequest, conn=Depends(get_db)
) -> dict:
    runtime = _SESSION_PLANS.get(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Unknown or expired session")
    if step_index < 0 or step_index >= len(runtime.skeleton.steps):
        raise HTTPException(status_code=404, detail="Unknown step index")

    step = runtime.skeleton.steps[step_index]
    if step_index not in runtime.content_cache:
        runtime.content_cache[step_index] = scheduler.generate_step_content(
            step, runtime.estimated_wpm
        )
    content = runtime.content_cache[step_index]

    activity = get_activity(step.activity_id)
    keystrokes = [KeystrokeEvent(**k.model_dump()) for k in body.keystrokes]
    result = activity.score(content, keystrokes)

    learner_id = ensure_learner(conn)
    now = datetime.now(UTC)

    event = db.log_session_event(conn, session_id, step.phase, step.activity_id)
    for seq, ke in enumerate(keystrokes):
        db.log_keystroke(
            conn, event.id, seq, ke.expected_char, ke.typed_char, ke.correct, ke.latency_ms
        )
    db.end_session_event(conn, event.id, summary_stats=asdict(result))

    _apply_keystrokes_to_skill_model(conn, learner_id, content.keys, keystrokes, now)
    _apply_keystrokes_to_bigram_model(conn, learner_id, keystrokes)

    # Blend this step's real WPM into the running estimate so the next
    # not-yet-generated step reflects it. Guarded against an empty/zero
    # result (e.g. "End this step now" with nothing typed yet).
    if result.attempts > 0 and result.wpm > 0:
        runtime.estimated_wpm = 0.5 * runtime.estimated_wpm + 0.5 * result.wpm

    session_complete = step_index == len(runtime.skeleton.steps) - 1
    if session_complete:
        db.end_session(conn, session_id)
        del _SESSION_PLANS[session_id]

    return {
        "result": asdict(result),
        "session_complete": session_complete,
        "estimated_wpm": runtime.estimated_wpm,
    }


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
