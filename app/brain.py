"""The brain: picks the next lesson each time the learner presses Practice.

Pure function over already-fetched state (BrainInput -> LessonPlan), no
DB and no clock beyond `now`, so every rule below is unit-testable. The
DB side (app/lessons.py) gathers the input and runs the plan.

How it decides, in order:
  1. Nothing taught yet (or no letters to practice with): learn.
  2. First lesson of a sitting: a short, easy warmup.
  3. The learner just struggled: an easy "comfort" lesson (strong keys,
     no weak runs, short). Never a new letter right after a struggle.
  4. Every taught key is solidly above the accuracy bar, with enough
     data, enough practice since the last new letter, and no new letter
     yet today: learn the next curriculum lesson. The bar slides from
     98% (all "practice") to 80% (all "learn").
  5. Otherwise practice, focused on regressions, newly taught keys, weak
     keys, and exceptionally weak letter pairs, sized to the predicted
     typing speed, a bit easier when the day's goal is about to land.

Every plan carries `reasons`: short plain-English notes on why it was
picked, for the parent page and for tuning.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.activities.practice_modules import PRACTICE_MODULES
from app.activities.teach_curriculum import lessons as curriculum_lessons
from app.models import BigramStat
from app.skill_model import KEY_ORDER

# 5 chars/word (the same convention as score_attempt's WPM).
CHARS_PER_WORD = 5

# A gap this long between lessons starts a new sitting (and a warmup).
SITTING_GAP = timedelta(minutes=20)

# Learn gate: recent accuracy bar at each end of the practice<->learn slider.
SOLID_BAR_PRACTICE = 0.98
SOLID_BAR_LEARN = 0.80
# "Enough data that we aren't in the noise."
MIN_RECENT_ATTEMPTS = 30
MIN_PRACTICES_SINCE_LEARN = 3
MAX_LEARNS_PER_DAY = 1

# Frustration: any of these on the last lesson of this sitting.
STRUGGLE_ACCURACY = 0.85
QUIT_EARLY_SHARE = 0.6
SPEED_CRASH = 0.7  # wpm below this share of the predicted speed
# ...or two lessons in a row below this.
MEH_ACCURACY = 0.90

# Difficulty (practice_text.py: how many weak letters/pairs come in a row).
WARMUP_DIFFICULTY = 0.15
COMFORT_DIFFICULTY = 0.0
START_DIFFICULTY = 0.5
MIN_DIFFICULTY = 0.2
MAX_DIFFICULTY = 0.85
DIFFICULTY_STEP = 0.1
GREAT_ACCURACY = 0.96
EASE_OFF = 0.15  # the last lesson before a goal lands ends on an easy note

# Seconds per lesson; practice length follows the predicted speed.
WARMUP_SECONDS = 50
COMFORT_SECONDS = 60
MIN_LESSON_SECONDS = 40

# Focus picking.
MAX_FOCUS_KEYS = 3
REGRESSION_DROP = 0.06
REGRESSION_MIN_RECENT = 15
REGRESSION_MIN_OLDER = 30
WEAK_KEY_MIN_ATTEMPTS = 10
WEAK_BIGRAM_MIN_SAMPLES = 8
WEAK_BIGRAM_ACCURACY = 0.8
WEAK_BIGRAM_BELOW_MEAN = 0.1
MAX_FOCUS_BIGRAMS = 2
# Comfort lessons need at least this many strong letters to leave weak ones out.
MIN_COMFORT_LETTERS = 4

# Themes not to repeat for this many lessons.
THEME_MEMORY = 5

PREDICTED_WPM_ALPHA = 0.35
MIN_PREDICTED_WPM = 3.0


@dataclass(frozen=True, slots=True)
class KeyRecord:
    """One key's recent history from the keystroke log: the newest
    attempts, and the ones before those (for spotting regressions)."""

    recent_attempts: int = 0
    recent_correct: int = 0
    older_attempts: int = 0
    older_correct: int = 0

    @property
    def recent_accuracy(self) -> float | None:
        return self.recent_correct / self.recent_attempts if self.recent_attempts else None

    @property
    def older_accuracy(self) -> float | None:
        return self.older_correct / self.older_attempts if self.older_attempts else None


@dataclass(frozen=True, slots=True)
class LessonRecord:
    """One finished lesson (oldest first in BrainInput.history)."""

    kind: str  # "warmup" | "learn" | "practice"
    activity_id: str
    finished_at: datetime
    accuracy: float
    wpm: float
    finished_share: float = 1.0  # how much of the prompt got typed
    difficulty: float | None = None
    predicted_wpm: float | None = None
    focus_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BrainInput:
    now: datetime
    taught_lessons: frozenset[str]  # curriculum refs, "module:keys"
    taught_keys: frozenset[str]
    # Keys the learner said they knew at placement: they don't block a new
    # letter until there's real data on them.
    placement_keys: frozenset[str] = frozenset()
    keys: dict[str, KeyRecord] = field(default_factory=dict)
    bigrams: list[BigramStat] = field(default_factory=list)
    history: list[LessonRecord] = field(default_factory=list)
    learn_vs_practice: float = 0.5  # 0 = all practice, 1 = all learn
    goal_seconds: int = 600
    practiced_seconds: float = 0.0  # in the current daily chunk
    learns_today: int = 0
    fallback_wpm: float = 10.0
    newest_keys: tuple[str, ...] = ()  # the last learn lesson's new keys


@dataclass(frozen=True, slots=True)
class LessonPlan:
    kind: str  # "warmup" | "learn" | "practice"
    activity_id: str
    reasons: tuple[str, ...]
    focus_keys: tuple[str, ...] = ()
    allowed_keys: tuple[str, ...] = ()
    focus_bigrams: tuple[str, ...] = ()
    difficulty: float = START_DIFFICULTY
    duration_s: int = 90
    predicted_wpm: float = 10.0
    teach_keys: str = ""  # learn: the curriculum lesson's keys ("dk")
    comfort: bool = False


def lesson_ref(module: str, keys: str) -> str:
    return f"{module}:{keys}"


def chars_per_second_for_wpm(wpm: float) -> float:
    return max(0.5, wpm) * CHARS_PER_WORD / 60


def solid_bar(learn_vs_practice: float) -> float:
    t = max(0.0, min(1.0, learn_vs_practice))
    return SOLID_BAR_PRACTICE + (SOLID_BAR_LEARN - SOLID_BAR_PRACTICE) * t


def next_curriculum_lesson(taught: frozenset[str]) -> dict | None:
    return next((l for l in curriculum_lessons() if lesson_ref(l["module"], l["keys"]) not in taught), None)


def predicted_wpm(inp: BrainInput) -> float:
    """An EMA over recent finished typing lessons (learn lessons are mostly
    reading and drills, so they don't count)."""
    speeds = [
        r.wpm for r in inp.history[-12:] if r.kind != "learn" and r.finished_share >= 0.5 and r.wpm > 0
    ]
    estimate = max(MIN_PREDICTED_WPM, inp.fallback_wpm)
    for wpm in speeds:
        estimate = PREDICTED_WPM_ALPHA * wpm + (1 - PREDICTED_WPM_ALPHA) * estimate
    return estimate


def practice_seconds(wpm: float) -> int:
    """Slow typers get shorter lessons; their text is already shorter
    (chars = seconds x speed), this keeps the effort from dragging."""
    if wpm < 8:
        return 70
    if wpm < 18:
        return 90
    return 110


def current_sitting(inp: BrainInput) -> list[LessonRecord]:
    """Lessons since the last SITTING_GAP-long break, oldest first."""
    sitting: list[LessonRecord] = []
    cursor = inp.now
    for record in reversed(inp.history):
        if cursor - record.finished_at > SITTING_GAP:
            break
        sitting.append(record)
        cursor = record.finished_at
    return list(reversed(sitting))


def frustration(inp: BrainInput, sitting: list[LessonRecord], wpm: float) -> str | None:
    """Why the learner looks frustrated right now, or None."""
    if not sitting:
        return None
    last = sitting[-1]
    if last.finished_share < QUIT_EARLY_SHARE:
        return "stopped the last lesson early"
    if last.accuracy < STRUGGLE_ACCURACY:
        return f"last lesson was hard ({last.accuracy:.0%} accuracy)"
    expected = last.predicted_wpm or wpm
    if last.kind != "learn" and last.wpm < SPEED_CRASH * expected:
        return f"last lesson was much slower than usual ({last.wpm:.0f} vs {expected:.0f} wpm)"
    if len(sitting) >= 2 and all(r.accuracy < MEH_ACCURACY for r in sitting[-2:]):
        return "two tough lessons in a row"
    return None


def unsolid_keys(inp: BrainInput) -> list[tuple[str, str]]:
    """(key, why) for each taught key not yet solid enough to move on."""
    bar = solid_bar(inp.learn_vs_practice)
    out = []
    for key in sorted(inp.taught_keys):
        record = inp.keys.get(key, KeyRecord())
        if record.recent_attempts < MIN_RECENT_ATTEMPTS:
            if key in inp.placement_keys and record.recent_attempts == 0:
                continue
            out.append((key, f"{record.recent_attempts}/{MIN_RECENT_ATTEMPTS} tries"))
        elif record.recent_accuracy < bar:
            out.append((key, f"{record.recent_accuracy:.0%} < {bar:.0%}"))
    return out


def practices_since_learn(history: list[LessonRecord]) -> int:
    count = 0
    for record in reversed(history):
        if record.kind == "learn":
            break
        count += record.kind == "practice"
    return count


def learn_blocker(inp: BrainInput) -> str | None:
    """Why the next new lesson has to wait, or None when it's time."""
    if inp.learns_today >= MAX_LEARNS_PER_DAY:
        return "already learned something new today"
    since = practices_since_learn(inp.history)
    if since < MIN_PRACTICES_SINCE_LEARN and any(r.kind == "learn" for r in inp.history):
        return f"{since}/{MIN_PRACTICES_SINCE_LEARN} practices since the last new lesson"
    blockers = unsolid_keys(inp)
    if blockers:
        shown = ", ".join(f"{_keyname(k)} ({why})" for k, why in blockers[:4])
        more = f" and {len(blockers) - 4} more" if len(blockers) > 4 else ""
        return f"not solid yet: {shown}{more}"
    return None


def _keyname(key: str) -> str:
    return "space" if key == " " else key


def regressions(inp: BrainInput) -> list[str]:
    """Keys whose recent accuracy fell clearly below their own earlier level."""
    out = []
    for key in inp.taught_keys:
        r = inp.keys.get(key)
        if (
            r
            and key != " "
            and r.recent_attempts >= REGRESSION_MIN_RECENT
            and r.older_attempts >= REGRESSION_MIN_OLDER
            and r.recent_accuracy <= r.older_accuracy - REGRESSION_DROP
            and r.recent_accuracy < GREAT_ACCURACY
        ):
            out.append(key)
    return sorted(out, key=lambda k: inp.keys[k].recent_accuracy - inp.keys[k].older_accuracy)


def weak_keys(inp: BrainInput) -> list[str]:
    bar = solid_bar(inp.learn_vs_practice)
    out = [
        k
        for k in inp.taught_keys
        if k != " "
        and (r := inp.keys.get(k)) is not None
        and r.recent_attempts >= WEAK_KEY_MIN_ATTEMPTS
        and r.recent_accuracy < bar
    ]
    return sorted(out, key=lambda k: (inp.keys[k].recent_accuracy, k))


def weak_bigrams(inp: BrainInput) -> list[str]:
    """Exceptionally weak letter pairs: low accuracy AND well below the
    learner's own average pair, so a generally shaky day doesn't flag
    every pair."""
    usable = [
        b
        for b in inp.bigrams
        if " " not in (b.key1, b.key2)
        and b.key1 != b.key2
        and b.key1 in inp.taught_keys
        and b.key2 in inp.taught_keys
        and b.accuracy_rolling is not None
        and b.sample_count >= WEAK_BIGRAM_MIN_SAMPLES
    ]
    if not usable:
        return []
    mean = sum(b.accuracy_rolling for b in usable) / len(usable)
    weak = [
        b
        for b in usable
        if b.accuracy_rolling < WEAK_BIGRAM_ACCURACY and b.accuracy_rolling <= mean - WEAK_BIGRAM_BELOW_MEAN
    ]
    weak.sort(key=lambda b: b.accuracy_rolling)
    return [b.key1 + b.key2 for b in weak[:MAX_FOCUS_BIGRAMS]]


def pick_theme(history: list[LessonRecord], rng: random.Random) -> str:
    recent = {r.activity_id for r in history[-THEME_MEMORY:]}
    fresh = [m.id for m in PRACTICE_MODULES if m.id not in recent] or [m.id for m in PRACTICE_MODULES]
    return rng.choice(fresh)


def next_difficulty(history: list[LessonRecord], wpm: float) -> tuple[float, str]:
    """Walk the last practice lesson's difficulty up after a great one, down
    after a shaky or slow one."""
    last = next((r for r in reversed(history) if r.kind == "practice" and r.difficulty is not None), None)
    if last is None:
        return START_DIFFICULTY, "starting difficulty"
    expected = last.predicted_wpm or wpm
    if last.accuracy >= GREAT_ACCURACY and last.wpm >= expected * 0.95:
        value, why = last.difficulty + DIFFICULTY_STEP, "last practice went great: a bit harder"
    elif last.accuracy < MEH_ACCURACY or last.wpm < expected * 0.8:
        value, why = last.difficulty - DIFFICULTY_STEP, "last practice was shaky: a bit easier"
    else:
        value, why = last.difficulty, "same difficulty as last time"
    return round(max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, value)), 2), why


def _letters(keys) -> list[str]:
    return [k for k in keys if k != " "]


def _ordered(keys) -> tuple[str, ...]:
    return tuple(sorted(keys, key=lambda k: KEY_ORDER.index(k) if k in KEY_ORDER else len(KEY_ORDER)))


def _fit_to_goal(seconds: int, inp: BrainInput) -> tuple[int, str | None]:
    """Trim a lesson so the goal (or the bonus) lands at its end instead of
    needing a whole extra lesson for the last few seconds."""
    for target, name in ((inp.goal_seconds, "goal"), (inp.goal_seconds * 1.5, "bonus")):
        left = target - inp.practiced_seconds
        if 0 < left < seconds + MIN_LESSON_SECONDS:
            return max(MIN_LESSON_SECONDS, round(left)), name
    return seconds, None


def plan_next_lesson(inp: BrainInput, rng: random.Random | None = None) -> LessonPlan:
    rng = rng or random.Random()
    wpm = predicted_wpm(inp)
    sitting = current_sitting(inp)
    upcoming = next_curriculum_lesson(inp.taught_lessons)
    letters = _letters(inp.taught_keys)
    allowed = _ordered(inp.taught_keys | {" "})

    def learn(reasons: list[str]) -> LessonPlan:
        return LessonPlan(
            "learn", upcoming["module"], tuple(reasons), predicted_wpm=wpm,
            teach_keys=upcoming["keys"], duration_s=120,
        )

    # 1. Nothing to practice with yet.
    if upcoming and not letters:
        return learn([f"no letters taught yet: {upcoming['title']}"])

    # 2. Warmup to open a sitting.
    if not sitting:
        return LessonPlan(
            "warmup", pick_theme(inp.history, rng), ("first lesson of this sitting: easy warmup",),
            allowed_keys=allowed, difficulty=WARMUP_DIFFICULTY, duration_s=WARMUP_SECONDS, predicted_wpm=wpm,
        )

    # 3. Frustrated: an easy, short comfort lesson.
    upset = frustration(inp, sitting, wpm)
    if upset:
        weak = set(weak_keys(inp)) | set(regressions(inp))
        strong = [k for k in letters if k not in weak]
        comfort_keys = strong if len(strong) >= MIN_COMFORT_LETTERS else letters
        return LessonPlan(
            "practice", pick_theme(inp.history, rng), (upset, "easy comfort lesson with strong keys"),
            allowed_keys=_ordered(set(comfort_keys) | {" "}), difficulty=COMFORT_DIFFICULTY,
            duration_s=COMFORT_SECONDS, predicted_wpm=wpm, comfort=True,
        )

    # 4. Learn the next lesson once everything taught is solid.
    reasons: list[str] = []
    if upcoming:
        waiting = learn_blocker(inp)
        if waiting is None:
            bar = solid_bar(inp.learn_vs_practice)
            return learn([f"every taught key is above {bar:.0%}", f"next up: {upcoming['title']}"])
        reasons.append(f"not learning {upcoming['title']} yet: {waiting}")

    # 5. Practice.
    focus: list[str] = []

    def add_focus(keys, why: str) -> None:
        new = [k for k in keys if k not in focus and k in inp.taught_keys][: MAX_FOCUS_KEYS - len(focus)]
        if new:
            focus.extend(new)
            reasons.append(f"{why}: {', '.join(_keyname(k) for k in new)}")

    add_focus(regressions(inp), "slipping")
    fresh = [k for k in inp.newest_keys if (inp.keys.get(k) or KeyRecord()).recent_attempts < MIN_RECENT_ATTEMPTS * 2]
    add_focus(fresh, "new")
    add_focus(weak_keys(inp), "weak")
    bigrams = weak_bigrams(inp)
    if bigrams:
        reasons.append(f"tricky pairs: {', '.join(bigrams)}")
        add_focus([k for b in bigrams for k in b], "in tricky pairs")
    if not focus and not bigrams:
        reasons.append("everything looks even: general practice")

    difficulty, why = next_difficulty(inp.history, wpm)
    reasons.append(why)
    seconds, landing = _fit_to_goal(practice_seconds(wpm), inp)
    if landing:
        difficulty = round(max(0.0, difficulty - EASE_OFF), 2)
        reasons.append(f"the daily {landing} lands after this one: ending on an easier note")
    reasons.append(f"predicted speed {wpm:.0f} wpm: {seconds}s lesson")

    return LessonPlan(
        "practice", pick_theme(inp.history, rng), tuple(reasons),
        focus_keys=_ordered(focus), allowed_keys=allowed, focus_bigrams=tuple(bigrams),
        difficulty=difficulty, duration_s=seconds, predicted_wpm=wpm,
    )
