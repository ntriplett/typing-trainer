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

import os
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import analytics, appearance, bigram_model, config, db, pets, profiles, room, scheduler, skill_model, store
from app.activities import get_activity
from app.catalog import group_places, night_item_id
from app.activities.base import ActivityContent, KeystrokeEvent, score_attempt
from app.activities.hello_world import HelloWorldActivity
from app.activities.teach_curriculum import known_before, lessons as teach_lessons
from app.activities.teach_modules import get_teach_module, list_teach_modules
from app.finger_map import KEY_TO_FINGER
from app.models import KeyStat
from app.scheduler import SessionConfig, SessionSkeleton, StepPlan

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
# Overridable via env var so a separately-spawned server process (e.g.
# a Playwright e2e test's live server) can point at an isolated temp
# DB without touching the dev typing.db -- monkeypatching DB_PATH only
# works for in-process tests (TestClient), not a real subprocess.
DB_PATH = Path(
    os.environ.get("TYPING_TRAINER_DB_PATH", str(Path(__file__).resolve().parent.parent / "typing.db"))
)

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


# Bonus coin rules on top of each activity's own coins() (PLAN.md 11c).
KEY_MASTERED_BONUS = 50
SESSION_COMPLETE_BONUS = 100

# session_id -> its runtime. See module docstring re: v1 scope.
_SESSION_PLANS: dict[int, SessionRuntime] = {}


def get_db():
    with db.open_db(DB_PATH) as conn:
        yield conn


# The current player, remembered per browser (PLAN.md 11d). Not a
# security boundary -- it's a family PC with no passwords by design.
LEARNER_COOKIE = "typing_learner"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def current_learner(request: Request, conn=Depends(get_db)) -> int:
    """The learner this request acts for, from the browser's cookie. Every
    endpoint that touches per-learner data goes through here. With no (or
    an unknown) player picked it's a 401, and the pages send you to the
    welcome screen to pick one. FastAPI caches get_db per request, so this
    shares the endpoint's connection.
    """
    raw = request.cookies.get(LEARNER_COOKIE, "")
    learner_id = int(raw) if raw.isdigit() else None
    if learner_id is None or not profiles.exists(conn, learner_id):
        raise HTTPException(status_code=401, detail="Pick who's playing first!")
    store.grant_starters(conn, learner_id)
    _grant_dev_coins(conn, learner_id)
    return learner_id


def _remember(response: Response, learner_id: int) -> None:
    response.set_cookie(LEARNER_COOKIE, str(learner_id), max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax")


def _grant_dev_coins(conn, learner_id: int) -> None:
    """Dev mode only (config.DEV_START_COINS): a one-time free balance."""
    if config.DEV_START_COINS <= 0:
        return
    granted = conn.execute(
        "SELECT 1 FROM coin_ledger WHERE learner_id = ? AND reason = 'dev_grant'", (learner_id,)
    ).fetchone()
    if not granted:
        db.add_coins(conn, learner_id, config.DEV_START_COINS, "dev_grant")


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


@app.get("/store")
def store_page() -> FileResponse:
    return FileResponse(WEB_DIR / "store.html")


@app.get("/profile")
def profile_page() -> FileResponse:
    return FileResponse(WEB_DIR / "profile.html")


@app.get("/designer")
def designer_page() -> FileResponse:
    return FileResponse(WEB_DIR / "designer.html")


@app.get("/pets")
def pets_page() -> FileResponse:
    return FileResponse(WEB_DIR / "pets.html")


@app.get("/bedroom")
def bedroom_page() -> FileResponse:
    return FileResponse(WEB_DIR / "bedroom.html")


@app.get("/welcome")
def welcome_page() -> FileResponse:
    return FileResponse(WEB_DIR / "welcome.html")


@app.get("/placement")
def placement_page() -> FileResponse:
    return FileResponse(WEB_DIR / "placement.html")


@app.get("/wardrobe")
def wardrobe_page() -> FileResponse:
    return FileResponse(WEB_DIR / "wardrobe.html")


@app.get("/teach-lab")
def teach_lab_page() -> FileResponse:
    return FileResponse(WEB_DIR / "teach_lab.html")


# --- teach modules (keyboard-driven, not in the live scheduler yet) ------------
#
# Tried out from /teach-lab. Nothing feeds the skill model yet; finishing
# one pays coins (an activity's first_finish_coins the first time, then
# its normal coin rule).


class KeystrokeIn(BaseModel):
    expected_char: str
    typed_char: str
    correct: bool
    latency_ms: int


class TeachCompleteRequest(BaseModel):
    keys: list[str]
    keystrokes: list[KeystrokeIn]


def _teach_keys(activity, keys: str) -> list[str]:
    """`keys` is a string of characters ("dk"); only modules with an
    is_eligible check on it (the key-pair one) use it."""
    if activity.id in ("teach_intro_home_row_v1", "teach_caps_intro_v1"):
        return []
    focus = list(keys)
    if not activity.is_eligible(focus, []):
        raise HTTPException(status_code=400, detail=f"Can't teach keys {keys!r}")
    return focus


def _get_teach_module(activity_id: str):
    try:
        return get_teach_module(activity_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown teach module") from None


@app.get("/teach/{activity_id}")
def teach_page(activity_id: str) -> FileResponse:
    _get_teach_module(activity_id)
    return FileResponse(WEB_DIR / "teach.html")


@app.get("/api/teach/modules")
def teach_modules() -> list[dict]:
    return list_teach_modules()


@app.get("/api/teach/lessons")
def teach_lesson_list() -> list[dict]:
    return teach_lessons()


@app.get("/api/teach/{activity_id}/content")
def teach_content(activity_id: str, keys: str = "") -> dict:
    activity = _get_teach_module(activity_id)
    focus = _teach_keys(activity, keys)
    # Capitals come after every letter, so they don't need a known-keys list.
    known = known_before(focus) if focus and activity.id == "teach_key_pair_v1" else []
    return asdict(activity.generate(focus, known, duration_s=120))


@app.post("/api/teach/{activity_id}/complete")
def teach_complete(
    activity_id: str,
    body: TeachCompleteRequest,
    keys: str = "",
    conn=Depends(get_db),
    learner_id: int = Depends(current_learner),
) -> dict:
    activity = _get_teach_module(activity_id)
    _teach_keys(activity, keys)
    keystrokes = [KeystrokeEvent(**k.model_dump()) for k in body.keystrokes]
    # The whole prompt is always typed by the end, so an empty prompt here
    # makes the coin rule count it as complete (accuracy-based).
    content = ActivityContent(activity_id, activity.kind, body.keys, prompt="")
    result = activity.score(content, keystrokes)

    ref = f"{activity_id}:{keys}" if keys else activity_id
    first_bonus = getattr(activity, "first_finish_coins", 0)
    if first_bonus and not db.has_coin_entry(conn, learner_id, "teach_first", ref):
        amount, reason = first_bonus, "teach_first"
    else:
        amount = activity.coins(content, result)
        reason = "teach"
    coins_earned = []
    if amount > 0:
        db.add_coins(conn, learner_id, amount, reason, ref=ref)
        coins_earned.append({"amount": amount, "reason": reason})
    return {
        "result": asdict(result),
        "coins_earned": coins_earned,
        "coin_balance": db.get_coin_balance(conn, learner_id),
    }


# --- analytics API -------------------------------------------------------------


@app.get("/api/analytics/keys")
def analytics_keys(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> list[dict]:
    return analytics.key_report(conn, learner_id)


@app.get("/api/analytics/fingers")
def analytics_fingers(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    key_stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    return {finger: asdict(stat) for finger, stat in analytics.finger_stats(key_stats).items()}


@app.get("/api/analytics/bigrams")
def analytics_bigrams(limit: int = 10, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> list[dict]:
    return [asdict(b) for b in analytics.worst_bigrams(conn, learner_id, limit=limit)]


@app.get("/api/analytics/trend")
def analytics_trend(days: int | None = None, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> list[dict]:
    return analytics.daily_trend(conn, learner_id, days=days)


# --- session API --------------------------------------------------------------


class SessionConfigIn(BaseModel):
    """The pre-session slider screen's choices."""

    duration_minutes: int = Field(default=15, ge=5, le=60)
    learn_vs_practice: float = Field(default=0.5, ge=0.0, le=1.0)
    focus_vs_general: float = Field(default=0.3, ge=0.0, le=1.0)


class CompleteStepRequest(BaseModel):
    keystrokes: list[KeystrokeIn]
    # The session timer ran out during this step: finish the session after
    # it instead of moving on to the next planned step.
    end_session: bool = False
    # Spaces the page dropped where lines wrap (prompt_view.js): never typed,
    # so they don't count against how much of the prompt was finished.
    skipped_chars: int = Field(default=0, ge=0)


def _serialize_skeleton_step(step: StepPlan) -> dict:
    return {
        "phase": step.phase,
        "activity_id": step.activity_id,
        "focus_keys": step.focus_keys,
        "duration_s": step.duration_s,
    }


@app.post("/api/session/start")
def start_session(
    config: SessionConfigIn = SessionConfigIn(),
    quick: bool = False,
    conn=Depends(get_db),
    learner_id: int = Depends(current_learner),
) -> dict:
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

    placement = profiles.placement_wpm(conn, learner_id)
    estimated_wpm = (
        analytics.estimate_starting_wpm(conn, learner_id, default=placement)
        if placement
        else analytics.estimate_starting_wpm(conn, learner_id)
    )
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

    learner_id = runtime.learner_id
    now = datetime.now(UTC)

    event = db.log_session_event(conn, session_id, step.phase, step.activity_id)
    for seq, ke in enumerate(keystrokes):
        db.log_keystroke(
            conn, event.id, seq, ke.expected_char, ke.typed_char, ke.correct, ke.latency_ms
        )
    db.end_session_event(conn, event.id, summary_stats=asdict(result))

    newly_mastered = _apply_keystrokes_to_skill_model(
        conn, learner_id, content.keys, keystrokes, now
    )
    _apply_keystrokes_to_bigram_model(conn, learner_id, keystrokes)

    # Blend this step's real WPM into the running estimate so the next
    # not-yet-generated step reflects it. Guarded against an empty/zero
    # result (e.g. "End this step now" with nothing typed yet).
    if result.attempts > 0 and result.wpm > 0:
        runtime.estimated_wpm = 0.5 * runtime.estimated_wpm + 0.5 * result.wpm

    session_complete = body.end_session or step_index == len(runtime.skeleton.steps) - 1
    if session_complete:
        db.end_session(conn, session_id)
        del _SESSION_PLANS[session_id]

    # Coins (PLAN.md 11c): the activity's own rule, then bonus rules.
    typed_part = replace(content, prompt=content.prompt[: max(0, len(content.prompt) - body.skipped_chars)])
    earned = [(activity.coins(typed_part, result), "lesson", f"event:{event.id}")]
    earned += [(KEY_MASTERED_BONUS, "key_mastered", key) for key in newly_mastered]
    if session_complete:
        earned.append((SESSION_COMPLETE_BONUS, "session_complete", f"session:{session_id}"))
    coins_earned = []
    for amount, reason, ref in earned:
        if amount > 0:
            db.add_coins(conn, learner_id, amount, reason, ref=ref)
            coins_earned.append({"amount": amount, "reason": reason})

    return {
        "result": asdict(result),
        "session_complete": session_complete,
        "estimated_wpm": runtime.estimated_wpm,
        "coins_earned": coins_earned,
        "coin_balance": db.get_coin_balance(conn, learner_id),
    }


def _apply_keystrokes_to_skill_model(
    conn, learner_id: int, focus_keys: list[str], keystrokes: list[KeystrokeEvent], now: datetime
) -> list[str]:
    """Fold this step's keystrokes into each key's running stats and
    persist them -- the thing that makes tomorrow's plan different from
    today's. Returns the keys mastered for the first time by this step
    (mastered_at is set once and never cleared, so this can't repeat).
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

    newly_mastered = []
    for stat in touched.values():
        before = db.get_key_stat(conn, learner_id, stat.key)
        if stat.mastered_at is not None and (before is None or before.mastered_at is None):
            newly_mastered.append(stat.key)
        db.upsert_key_stat(conn, stat)
    return newly_mastered


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


# --- player + store API ---------------------------------------------------------


def _me(conn, learner_id: int) -> dict:
    learner = db.get_learner(conn, learner_id)
    return {
        "learner": {"id": learner.id, "name": learner.name},
        "coins": db.get_coin_balance(conn, learner_id),
        "avatar": store.get_avatar(conn, learner_id),
        "night": store.night_status(conn, learner_id),
    }


@app.get("/api/me")
def me(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _me(conn, learner_id)


@app.get("/api/store")
def store_catalog(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    owned = store.owned_ids(conn, learner_id)
    avatar = store.get_avatar(conn, learner_id)
    # "equipped" = worn, or (for a hair dye) the hair color in use
    equipped = {v for k, v in avatar.items() if k in store.SLOTS}
    equipped.add(appearance.dye_item_id(avatar["appearance"]["hair_color"]))
    bedroom = room.state(conn, learner_id)
    equipped |= {bedroom["wallpaper"], bedroom["flooring"]} | {p["item_id"] for p in bedroom["items"]}
    night = store.night_status(conn, learner_id)
    if night["on"]:
        equipped.add(night_item_id(night["group"]))
    coins = db.get_coin_balance(conn, learner_id)
    items = [
        {
            **asdict(item),
            "owned": item.id in owned,
            "equipped": item.id in equipped,
            "affordable": item.price <= coins,
        }
        for item in store.CATALOG.values()
        if not item.starter
    ]
    # night unlocks list the places they work in (and which you own)
    for entry in items:
        if entry["slot"] == "night":
            entry["places"] = [
                {"id": p, "name": store.CATALOG[p].name, "owned": p in owned}
                for p in group_places(entry["group"])
            ]
    return {**_me(conn, learner_id), "items": items}


def _store_action(action, conn, learner_id: int, arg: str) -> dict:
    try:
        action(conn, learner_id, arg)
    except store.StoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _me(conn, learner_id)


@app.post("/api/store/buy/{item_id}")
def store_buy(item_id: str, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _store_action(store.buy, conn, learner_id, item_id)


@app.post("/api/store/equip/{item_id}")
def store_equip(item_id: str, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _store_action(store.equip, conn, learner_id, item_id)


class NightIn(BaseModel):
    on: bool


@app.put("/api/me/night")
def set_night(body: NightIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    try:
        store.set_night(conn, learner_id, body.on)
    except store.StoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _me(conn, learner_id)


@app.post("/api/store/unequip/{slot}")
def store_unequip(slot: str, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _store_action(store.unequip, conn, learner_id, slot)


# --- profile + character designer API ---------------------------------------------


class AppearanceIn(BaseModel):
    gender: str
    skin: str
    hair_color: str
    hair_style: str
    eye_color: str = "brown"


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=20)


@app.get("/api/profile")
def profile(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return {**_me(conn, learner_id), "stats": db.profile_stats(conn, learner_id)}


@app.put("/api/me/name")
def rename(body: NameIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Your name can't be blank.")
    db.rename_learner(conn, learner_id, name)
    return _me(conn, learner_id)


@app.get("/api/appearance")
def appearance_options(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return {**_me(conn, learner_id), "options": appearance.options(conn, learner_id)}


@app.put("/api/appearance")
def save_appearance(
    body: AppearanceIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)
) -> dict:
    try:
        appearance.save(conn, learner_id, appearance.Appearance(**body.model_dump()))
    except appearance.AppearanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _me(conn, learner_id)


# --- pets API -----------------------------------------------------------------------


class AdoptIn(BaseModel):
    species: str
    color: str


class PetNameIn(BaseModel):
    name: str


class AlongIn(BaseModel):
    slot: int | None = None


def _pets_state(conn, learner_id: int) -> dict:
    return {
        **_me(conn, learner_id),
        "pets": pets.list_pets(conn, learner_id),
        "species": pets.catalog(),
        "food_price": pets.FOOD_PRICE,
        "max_along": pets.MAX_ALONG,
    }


def _pet_action(action, conn, learner_id: int, *args) -> dict:
    try:
        action(conn, learner_id, *args)
    except pets.PetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _pets_state(conn, learner_id)


@app.get("/api/pets")
def list_pets(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _pets_state(conn, learner_id)


@app.post("/api/pets/adopt")
def adopt_pet(body: AdoptIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _pet_action(pets.adopt, conn, learner_id, body.species, body.color)


@app.post("/api/pets/{pet_id}/feed")
def feed_pet(pet_id: int, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _pet_action(pets.feed, conn, learner_id, pet_id)


@app.put("/api/pets/{pet_id}/name")
def rename_pet(
    pet_id: int, body: PetNameIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)
) -> dict:
    return _pet_action(pets.rename, conn, learner_id, pet_id, body.name)


@app.put("/api/pets/{pet_id}/along")
def pet_along(
    pet_id: int, body: AlongIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)
) -> dict:
    return _pet_action(pets.set_along, conn, learner_id, pet_id, body.slot)


# --- room API -------------------------------------------------------------------------


class PlaceIn(BaseModel):
    item_id: str
    x: int | None = None
    y: int | None = None


class MoveIn(BaseModel):
    x: int
    y: int


class SurfaceIn(BaseModel):
    item_id: str


def _room_state(conn, learner_id: int) -> dict:
    return {**_me(conn, learner_id), "room": room.state(conn, learner_id)}


def _room_action(action, conn, learner_id: int, *args) -> dict:
    try:
        action(conn, learner_id, *args)
    except room.RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _room_state(conn, learner_id)


@app.get("/api/room")
def get_room(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _room_state(conn, learner_id)


@app.post("/api/room/items")
def place_item(body: PlaceIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _room_action(room.place, conn, learner_id, body.item_id, body.x, body.y)


@app.put("/api/room/items/{placed_id}")
def move_item(
    placed_id: int, body: MoveIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)
) -> dict:
    return _room_action(room.move, conn, learner_id, placed_id, body.x, body.y)


@app.delete("/api/room/items/{placed_id}")
def put_away_item(placed_id: int, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _room_action(room.put_away, conn, learner_id, placed_id)


@app.put("/api/room/surface")
def set_room_surface(body: SurfaceIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _room_action(room.set_surface, conn, learner_id, body.item_id)


# --- profiles API ---------------------------------------------------------------------
# Picking/creating doesn't need a current player, so these skip current_learner.


class ProfileIn(BaseModel):
    name: str


class PlacementIn(BaseModel):
    keys: str
    speed: str


@app.get("/api/profiles")
def list_profiles(conn=Depends(get_db)) -> list[dict]:
    return profiles.list_profiles(conn)


@app.post("/api/profiles")
def create_profile(body: ProfileIn, response: Response, conn=Depends(get_db)) -> dict:
    try:
        learner_id = profiles.create(conn, body.name)
    except profiles.ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    _grant_dev_coins(conn, learner_id)
    _remember(response, learner_id)
    return _me(conn, learner_id)


@app.post("/api/profiles/{learner_id}/select")
def select_profile(learner_id: int, response: Response, conn=Depends(get_db)) -> dict:
    if not profiles.exists(conn, learner_id):
        raise HTTPException(status_code=404, detail="There's no player like that.")
    _remember(response, learner_id)
    store.grant_starters(conn, learner_id)
    return _me(conn, learner_id)


@app.post("/api/profiles/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(LEARNER_COOKIE)
    return {"ok": True}


@app.put("/api/profiles/placement")
def placement(body: PlacementIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    try:
        profiles.apply_placement(conn, learner_id, body.keys, body.speed)
    except profiles.ProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _me(conn, learner_id)


@app.get("/api/wardrobe")
def wardrobe(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    """Everything wearable you own (starters included), by slot."""
    owned = store.owned_ids(conn, learner_id)
    worn = [s for s in store.SLOTS if s != "background"]
    return {
        **_me(conn, learner_id),
        "slots": {
            slot: [
                {"id": i.id, "name": i.name, "starter": i.starter}
                for i in store.CATALOG.values()
                if i.slot == slot and i.id in owned
            ]
            for slot in worn
        },
        "defaults": {s: store.SLOT_DEFAULTS.get(s) for s in worn},
    }
