"""FastAPI app: the local server the launcher starts and the browser talks to.

The main loop: the home page's Practice button asks the brain
(app/brain.py, run by app/lessons.py) for one lesson at a time; finished
lessons add up toward the day's practice goal, which pays arcade tokens
(app/daily.py) to spend in the arcade (app/arcade.py). Coins pay for the
store, pets, and rooms. The labs (/teach-lab, /practice-lab, /game-lab)
try any module directly and are linked from the parent page.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import analytics, appearance, arcade, brain, config, daily, db, garden, lessons, pet_genes, pet_shop, pets, profiles, room, skill_model, store, unlocks
from app.catalog import group_places, night_item_id
from app.activities.base import ActivityContent, KeystrokeEvent, score_attempt
from app.activities.hello_world import HelloWorldActivity
from app.activities.game_modules import GAME_MODULES, MAX_ROUND_SCORE
from app.activities.practice_modules import PRACTICE_MODULES
from app.activities.practice_text import snapshot_from_stats
from app.activities.teach_curriculum import known_before, lessons as teach_lessons
from app.activities.teach_modules import get_teach_module, list_teach_modules
from app.finger_map import KEY_TO_FINGER

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


def now() -> datetime:
    """The clock for the daily goal and lessons; tests move it forward."""
    return datetime.now(UTC)


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
def pets_hub_page() -> FileResponse:
    return FileResponse(WEB_DIR / "pets_hub.html")


@app.get("/pets/room")
def pet_room_page() -> FileResponse:
    """The old pet room (pets before v3), until the Pet Care Center replaces it."""
    return FileResponse(WEB_DIR / "pets.html")


@app.get("/pets/shop")
def pet_shop_page() -> FileResponse:
    return FileResponse(WEB_DIR / "pet_shop.html")


@app.get("/bedroom")
def bedroom_page() -> FileResponse:
    return FileResponse(WEB_DIR / "bedroom.html")


@app.get("/arcade")
def arcade_page() -> FileResponse:
    return FileResponse(WEB_DIR / "arcade.html")


@app.get("/garden")
def garden_page() -> FileResponse:
    return FileResponse(WEB_DIR / "garden.html")


@app.get("/parent")
def parent_page() -> FileResponse:
    return FileResponse(WEB_DIR / "parent.html")


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


# --- keyboard hint (any short lesson) ------------------------------------------


class HintIn(BaseModel):
    ref: str = Field(default="", max_length=200)  # which lesson it was bought for


@app.post("/api/hint/keyboard")
def buy_keyboard_hint(body: HintIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    """Spend coins to show the keyboard with hands for the rest of one lesson."""
    price = config.KEYBOARD_HINT_PRICE
    if db.get_coin_balance(conn, learner_id) < price:
        raise HTTPException(status_code=402, detail=f"A keyboard hint costs {price} coins.")
    db.add_coins(conn, learner_id, -price, "keyboard_hint", ref=body.ref or None)
    return {"spent": price, "coin_balance": db.get_coin_balance(conn, learner_id)}


# --- pet lab (grow and roll pets for free; dev only, nothing is saved) -----------


@app.get("/pet-lab")
def pet_lab_page() -> FileResponse:
    return FileResponse(WEB_DIR / "pet_lab.html")


@app.get("/api/pet-lab/species")
def pet_lab_species() -> dict:
    return {
        species: {
            "colors": pet_genes.color_catalog(pet_genes.starting_unlocks(), species),
            "starters": list(pet_genes.STARTER_COLORS[species]),
        }
        for species in pet_genes.SPECIES_COLORS
    }


@app.get("/api/pet-lab/roll")
def pet_lab_roll(species: str, primary: str = "", secondary: str = "", seed: int | None = None, count: int = 1) -> dict:
    """`count` pets from consecutive seeds (a random start if no seed). The
    third color rolls as if a new learner's colors plus the two picks were
    unlocked. A blank color lets the game pick it."""
    primary = primary or None
    secondary = (secondary or None) if primary else None
    unlocked = pet_genes.starting_unlocks() | {c for c in (primary, secondary) if c}
    start = seed if seed is not None else pet_genes.new_seed()
    try:
        rolled = [
            pet_genes.resolve(pet_genes.roll(species, primary, secondary, start + i, unlocked))
            for i in range(max(1, min(count, 60)))
        ]
    except pet_genes.GeneError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"pets": rolled}


# --- practice lab (try every practice module) -----------------------------------
#
# Uses the player's real weak spots and typing speed, pays coins like a
# lesson, but doesn't feed the skill model (that's what sessions are for).

PRACTICE_BY_ID = {m.id: m for m in PRACTICE_MODULES}
PRACTICE_KEY_SETS = {
    "home": "asdfghjkl;",
    "home_top": "asdfghjkl;qwertyuiop",
    "letters": "abcdefghijklmnopqrstuvwxyz",
}
PRACTICE_LENGTHS = {"short": 45, "medium": 90, "long": 150}
PRACTICE_DIFFICULTIES = {"easy": 0.15, "medium": 0.5, "hard": 0.9}


def _practice_module(activity_id: str):
    module = PRACTICE_BY_ID.get(activity_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Unknown practice module")
    return module


@app.get("/practice-lab")
def practice_lab_page() -> FileResponse:
    return FileResponse(WEB_DIR / "practice_lab.html")


@app.get("/practice/{activity_id}")
def practice_page(activity_id: str) -> FileResponse:
    _practice_module(activity_id)
    return FileResponse(WEB_DIR / "practice.html")


@app.get("/api/practice/modules")
def practice_modules() -> list[dict]:
    return [{"id": m.id, "title": m.title, "blurb": m.blurb, "scene": m.scene} for m in PRACTICE_MODULES]


@app.get("/api/practice/{activity_id}/content")
def practice_content(
    activity_id: str,
    keys: str = "mine",
    focus: str = "",
    length: str = "medium",
    difficulty: str = "medium",
    conn=Depends(get_db),
    learner_id: int = Depends(current_learner),
) -> dict:
    module = _practice_module(activity_id)
    if length not in PRACTICE_LENGTHS or difficulty not in PRACTICE_DIFFICULTIES:
        raise HTTPException(status_code=400, detail="Unknown length or difficulty")
    focus_keys, allowed, key_stats = _lab_letters(conn, learner_id, keys, focus)
    wpm = _lab_wpm(conn, learner_id)
    content = module.generate(
        focus_keys,
        allowed,
        PRACTICE_LENGTHS[length],
        chars_per_second=brain.chars_per_second_for_wpm(wpm),
        difficulty=PRACTICE_DIFFICULTIES[difficulty],
        skill=snapshot_from_stats(key_stats, db.list_bigram_stats(conn, learner_id)),
    )
    return asdict(content)


class PracticeCompleteRequest(BaseModel):
    keys: list[str]
    prompt_length: int = Field(ge=0)
    keystrokes: list[KeystrokeIn]
    skipped_chars: int = Field(default=0, ge=0)


@app.post("/api/practice/{activity_id}/complete")
def practice_complete(
    activity_id: str,
    body: PracticeCompleteRequest,
    conn=Depends(get_db),
    learner_id: int = Depends(current_learner),
) -> dict:
    module = _practice_module(activity_id)
    keystrokes = [KeystrokeEvent(**k.model_dump()) for k in body.keystrokes]
    # The coin rule only looks at the prompt's length (how much was finished),
    # minus the spaces dropped at line wraps, which are never typed.
    typed_length = max(0, body.prompt_length - body.skipped_chars)
    content = ActivityContent(activity_id, module.kind, body.keys, prompt="x" * typed_length)
    result = module.score(content, keystrokes)
    amount = module.coins(content, result)
    coins_earned = []
    if amount > 0:
        db.add_coins(conn, learner_id, amount, "lesson", ref=f"practice_lab:{activity_id}")
        coins_earned.append({"amount": amount, "reason": "lesson"})
    return {
        "result": asdict(result),
        "coins_earned": coins_earned,
        "coin_balance": db.get_coin_balance(conn, learner_id),
    }


# --- game lab (try every game) ---------------------------------------------------
#
# Like the practice lab: real weak spots, no skill-model updates. Each round
# is posted when it ends and paid right away. Games aren't in sessions yet.

GAMES_BY_ID = {g.id: g for g in GAME_MODULES}


def _game_module(activity_id: str):
    module = GAMES_BY_ID.get(activity_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Unknown game")
    return module


def _lab_letters(conn, learner_id: int, keys: str, focus: str) -> tuple[list[str], list[str], dict]:
    """(focus keys, allowed keys with space, key stats) for a lab's ?keys=&focus= options."""
    key_stats = {s.key: s for s in db.list_key_stats(conn, learner_id)}
    if keys == "mine":
        allowed = [k for k in skill_model.KEY_ORDER if k in lessons.taught_keys(conn, learner_id) and k != " "]
    elif keys in PRACTICE_KEY_SETS:
        allowed = list(PRACTICE_KEY_SETS[keys])
    else:
        raise HTTPException(status_code=400, detail=f"Unknown key set {keys!r}")
    focus_keys = [k for k in dict.fromkeys(focus.lower()) if k in KEY_TO_FINGER and k != " "]
    return focus_keys, [" ", *dict.fromkeys(allowed + focus_keys)], key_stats


def _lab_wpm(conn, learner_id: int) -> float:
    default = profiles.placement_wpm(conn, learner_id) or analytics.DEFAULT_STARTING_WPM
    return analytics.estimate_starting_wpm(conn, learner_id, default=default)


@app.get("/game-lab")
def game_lab_page() -> FileResponse:
    return FileResponse(WEB_DIR / "game_lab.html")


@app.get("/game/{activity_id}")
def game_page(activity_id: str) -> FileResponse:
    _game_module(activity_id)
    return FileResponse(WEB_DIR / "game.html")


@app.get("/api/game/modules")
def game_modules() -> list[dict]:
    return [{"id": g.id, "title": g.title, "blurb": g.blurb, "game": g.game} for g in GAME_MODULES]


@app.get("/api/game/{activity_id}/content")
def game_content(
    activity_id: str,
    keys: str = "mine",
    focus: str = "",
    difficulty: str = "medium",
    conn=Depends(get_db),
    learner_id: int = Depends(current_learner),
) -> dict:
    module = _game_module(activity_id)
    if difficulty not in PRACTICE_DIFFICULTIES:
        raise HTTPException(status_code=400, detail="Unknown difficulty")
    focus_keys, allowed, key_stats = _lab_letters(conn, learner_id, keys, focus)
    if not module.is_eligible(focus_keys, allowed):
        raise HTTPException(status_code=400, detail="Games need at least 4 letters. Learn a few more first!")
    content = module.generate(
        focus_keys,
        allowed,
        chars_per_second=brain.chars_per_second_for_wpm(_lab_wpm(conn, learner_id)),
        difficulty=PRACTICE_DIFFICULTIES[difficulty],
        skill=snapshot_from_stats(key_stats, db.list_bigram_stats(conn, learner_id)),
    )
    return asdict(content)


class GameRoundRequest(BaseModel):
    """One finished round: its points and the keys typed during it."""

    keys: list[str]
    keystrokes: list[KeystrokeIn]
    score: int = Field(ge=0, le=MAX_ROUND_SCORE)


@app.post("/api/game/{activity_id}/round")
def game_round(
    activity_id: str,
    body: GameRoundRequest,
    conn=Depends(get_db),
    learner_id: int = Depends(current_learner),
) -> dict:
    module = _game_module(activity_id)
    keystrokes = [KeystrokeEvent(**k.model_dump()) for k in body.keystrokes]
    content = ActivityContent(activity_id, module.kind, body.keys, prompt="")
    result = module.score(content, keystrokes)
    amount = module.coins_for(body.score)
    coins_earned = []
    if amount > 0:
        db.add_coins(conn, learner_id, amount, "game", ref=f"game_lab:{activity_id}")
        coins_earned.append({"amount": amount, "reason": "game"})
    return {
        "result": asdict(result),
        "score": body.score,
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


# --- lessons (the brain) + the day's goal --------------------------------------------


class LessonCompleteRequest(BaseModel):
    keystrokes: list[KeystrokeIn]
    # Typing time with idle stretches left out, measured by the page; the
    # server caps it at the lesson's wall-clock time.
    active_ms: int = Field(default=0, ge=0)
    # Spaces the page dropped where lines wrap (prompt_view.js): never typed,
    # so they don't count against how much of the prompt was finished.
    skipped_chars: int = Field(default=0, ge=0)


def _resting(exc: daily.PracticeResting) -> HTTPException:
    return HTTPException(status_code=409, detail={"message": "Practice is done for today!", "resting_until": str(exc)})


@app.get("/api/day")
def day_status(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return daily.status(conn, learner_id, now())


@app.post("/api/lesson/next")
def next_lesson(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    try:
        lesson = lessons.serve_next(conn, learner_id, now())
    except daily.PracticeResting as exc:
        raise _resting(exc) from None
    return {"lesson": lessons.describe(lesson), "content": asdict(lesson.content)}


@app.get("/api/lesson/{lesson_id}")
def get_lesson(lesson_id: int, learner_id: int = Depends(current_learner)) -> dict:
    try:
        lesson = lessons.get_served(lesson_id, learner_id)
    except lessons.LessonError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return {"lesson": lessons.describe(lesson), "content": asdict(lesson.content)}


@app.post("/api/lesson/{lesson_id}/complete")
def complete_lesson(
    lesson_id: int, body: LessonCompleteRequest, conn=Depends(get_db), learner_id: int = Depends(current_learner)
) -> dict:
    keystrokes = [KeystrokeEvent(**k.model_dump()) for k in body.keystrokes]
    before = unlocks.status(conn, learner_id)
    try:
        done = lessons.complete(
            conn, learner_id, lesson_id, keystrokes, body.active_ms, body.skipped_chars, now()
        )
    except lessons.LessonError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    after = unlocks.status(conn, learner_id)
    return {**done, "unlocked": unlocks.newly_unlocked(before, after), "free_pet": after["free_pet"]}


# --- parent page -----------------------------------------------------------------------
# Open for now (a password may come later). Shows every player, so it
# doesn't use the current-player cookie.


class SettingsIn(BaseModel):
    goal_minutes: int = Field(ge=daily.MIN_GOAL_MINUTES, le=daily.MAX_GOAL_MINUTES)
    learn_vs_practice: float = Field(ge=0.0, le=1.0)


def _parent_entry(conn, learner_id: int) -> dict:
    when = now()
    inp = lessons.brain_input(conn, learner_id, when)
    preview = brain.plan_next_lesson(inp)
    upcoming = brain.next_curriculum_lesson(inp.taught_lessons)
    learner = db.get_learner(conn, learner_id)
    return {
        "id": learner_id,
        "name": learner.name,
        "avatar": store.get_avatar(conn, learner_id),
        "settings": asdict(daily.get_settings(conn, learner_id)),
        "day": daily.status(conn, learner_id, when),
        "tokens": db.get_token_balance(conn, learner_id),
        "solid_bar": brain.solid_bar(inp.learn_vs_practice),
        "next_new_lesson": upcoming["title"] if upcoming else None,
        "predicted_wpm": round(brain.predicted_wpm(inp), 1),
        "brain": {"kind": preview.kind, "activity_id": preview.activity_id, "reasons": list(preview.reasons)},
    }


@app.get("/api/parent")
def parent_overview(conn=Depends(get_db)) -> list[dict]:
    return [_parent_entry(conn, p["id"]) for p in profiles.list_profiles(conn)]


@app.put("/api/parent/{learner_id}/settings")
def parent_settings(learner_id: int, body: SettingsIn, conn=Depends(get_db)) -> dict:
    if not profiles.exists(conn, learner_id):
        raise HTTPException(status_code=404, detail="There's no player like that.")
    daily.save_settings(conn, learner_id, daily.Settings(body.goal_minutes, body.learn_vs_practice))
    return _parent_entry(conn, learner_id)


# --- arcade --------------------------------------------------------------------------------


@app.get("/api/arcade")
def arcade_games(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return {**_me(conn, learner_id), "games": arcade.games(conn, learner_id)}


@app.post("/api/arcade/play/{game_id}")
def arcade_play(game_id: str, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    try:
        arcade.play(conn, learner_id, game_id)
    except arcade.ArcadeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _me(conn, learner_id)


# --- garden ---------------------------------------------------------------------


def _garden_summary(g: dict) -> dict:
    """The bit of the garden the home tile shows."""
    return {k: g[k] for k in ("ready", "growing", "basket_total", "seeds")}


class SpotIn(BaseModel):
    slot: int


def _garden_action(action, conn, learner_id: int, *args) -> dict:
    try:
        done = action(conn, learner_id, *args, now())
    except garden.GardenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {**_me(conn, learner_id), "done": done, "garden": garden.status(conn, learner_id, now())}


@app.get("/api/garden")
def garden_status(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return {**_me(conn, learner_id), "garden": garden.status(conn, learner_id, now())}


@app.post("/api/garden/plant")
def garden_plant(body: SpotIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _garden_action(garden.plant, conn, learner_id, body.slot)


@app.post("/api/garden/pick")
def garden_pick(body: SpotIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _garden_action(garden.pick, conn, learner_id, body.slot)


@app.post("/api/garden/basket")
def garden_basket(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _garden_action(garden.collect_basket, conn, learner_id)


# --- player + store API ---------------------------------------------------------


def _me(conn, learner_id: int) -> dict:
    learner = db.get_learner(conn, learner_id)
    return {
        "learner": {"id": learner.id, "name": learner.name},
        "coins": db.get_coin_balance(conn, learner_id),
        "tokens": db.get_token_balance(conn, learner_id),
        "seeds": db.get_seed_balance(conn, learner_id),
        "garden": _garden_summary(garden.status(conn, learner_id, now())),
        "day": daily.status(conn, learner_id, now()),
        "unlocks": unlocks.status(conn, learner_id),
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
    item = store.CATALOG.get(item_id)
    if item and item.slot in unlocks.ROOM_SLOTS:
        _require(conn, learner_id, "bedroom")
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
    _require(conn, learner_id, "pets")
    return {
        **_me(conn, learner_id),
        "pets": pets.list_pets(conn, learner_id),
        "species": pets.catalog(),
        "food_price": pets.FOOD_PRICE,
        "max_along": pets.MAX_ALONG,
    }


def _require(conn, learner_id: int, room_name: str) -> None:
    try:
        unlocks.require(conn, learner_id, room_name)
    except unlocks.Locked as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


def _pet_action(action, conn, learner_id: int, *args) -> dict:
    _require(conn, learner_id, "pets")
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
    free = unlocks.status(conn, learner_id)["free_pet"]
    state = _pet_action(pets.adopt, conn, learner_id, body.species, body.color, free)
    if free:
        unlocks.claim_free_pet(conn, learner_id)
    return state


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


# --- pet shop API (pets v3, PLAN.md 11h) --------------------------------------------


class BuyPetIn(BaseModel):
    coupon: bool = False


class SavePetIn(BaseModel):
    dept: str
    index: int


class OrderIn(BaseModel):
    species: str
    primary: str
    secondary: str | None = None


def _today():
    """The shop restocks at local midnight."""
    return now().astimezone().date()


def _shop_call(action, *args):
    try:
        return action(*args)
    except pet_shop.Closed as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except pet_shop.ShopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


def _department(conn, learner_id: int, dept: str) -> dict:
    return {**_me(conn, learner_id), **_shop_call(pet_shop.department_state, conn, learner_id, dept, _today())}


@app.get("/api/pets/hub")
def pets_hub(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return {**_me(conn, learner_id), **pet_shop.hub_state(conn, learner_id, _today())}


@app.get("/api/pets/shop")
def pet_shop_front(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return {**_me(conn, learner_id), **pet_shop.shop_state(conn, learner_id, _today())}


@app.get("/api/pets/shop/orders/preview")
def preview_order(
    species: str, primary: str, secondary: str | None = None,
    conn=Depends(get_db), learner_id: int = Depends(current_learner),
) -> dict:
    return {"pet": _shop_call(pet_shop.order_preview, conn, learner_id, species, primary, secondary)}


@app.post("/api/pets/shop/orders")
def place_order(body: OrderIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    _shop_call(pet_shop.place_order, conn, learner_id, body.species, body.primary, body.secondary, _today())
    return _department(conn, learner_id, "orders")


@app.get("/api/pets/shop/{dept}")
def pet_shop_department(dept: str, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    return _department(conn, learner_id, dept)


@app.post("/api/pets/shop/{dept}/{index}/buy")
def buy_shop_pet(
    dept: str, index: int, body: BuyPetIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)
) -> dict:
    bought = _shop_call(pet_shop.buy, conn, learner_id, dept, index, _today(), body.coupon)
    return {**_department(conn, learner_id, dept), "bought": bought}


@app.put("/api/pets/shop/save")
def save_shop_pet(body: SavePetIn, conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    _shop_call(pet_shop.save_pet, conn, learner_id, body.dept, body.index, _today())
    return _department(conn, learner_id, body.dept)


@app.delete("/api/pets/shop/save")
def unsave_shop_pet(conn=Depends(get_db), learner_id: int = Depends(current_learner)) -> dict:
    dept = _shop_call(pet_shop.unsave_pet, conn, learner_id, _today())
    return _department(conn, learner_id, dept)


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
    _require(conn, learner_id, "bedroom")
    return {**_me(conn, learner_id), "room": room.state(conn, learner_id)}


def _room_action(action, conn, learner_id: int, *args) -> dict:
    _require(conn, learner_id, "bedroom")
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
    lessons.record_placement(conn, learner_id, set(skill_model.KEY_ORDER[: profiles.PLACEMENT_KEYS[body.keys]]))
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
