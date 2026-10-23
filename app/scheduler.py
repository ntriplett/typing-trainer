"""The session scheduler (PLAN.md Section 6): builds the day's plan from
skill-model state plus the learner's pre-session choices (duration,
learn-vs-practice, focus-vs-general), then generates each step's actual
typing content lazily, one step at a time.

Each step is a short (1-2 minute) sub-lesson now, not one long block per
phase kind -- a 15-minute session ends up with roughly 10 of them, and
the sequence of kinds is decided step by step as the session is built,
not fixed up front: "warmup, teach, practice, teach, game, practice,
eval, practice, game" is as valid a shape as any other, depending on
what the skill-model state and the slider choices call for.

Split into two stages on purpose:
  - build_session_skeleton(): pure, decides the step sequence, each
    step's time budget, and its two key pools (focus_keys: what this
    step should actively work on; allowed_keys: everything introduced
    so far, safe as filler) -- no typing content yet. This is what the
    progress bar shows up front.
  - generate_step_content(): turns one skeleton step into actual
    ActivityContent, using the CURRENT estimated typing speed. Called
    once per step, lazily, so later steps' content length adapts to
    how fast the session is actually going.

v1 scope: there's exactly one registered activity per kind (PLAN.md's
"only one choice, but it's still a good test" step), so the scheduler's
job right now is step sequencing and key-pool selection rather than
picking among several alternatives per kind.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime

from app.activities import activities_by_kind, get_activity
from app.activities.base import ActivityContent
from app.models import BigramStat, KeyStat
from app.recommender import recommend_warmup_keys
from app.skill_model import KEY_ORDER, active_keys, next_keys_to_teach

# A learner is considered to have "enough practice" on a key for an eval
# to be meaningful once it's been attempted this many times. Deliberately
# low for now; this is the first thing to tune once real usage exists.
EVAL_MIN_SAMPLES = 5

# 5 chars/word convention (same as score_attempt's WPM calc) -- used to
# turn a WPM estimate into "how many characters fit the time budget."
CHARS_PER_WORD = 5

# ~1-2 minutes per sub-lesson, per your call -- a 15-minute session ends
# up with roughly 10 of these instead of 4-5 long blocks.
SHORT_STEP_SECONDS: dict[str, int] = {
    "warmup": 75,
    "teach": 75,
    "practice": 100,
    "eval": 75,
    "game": 90,
}

# How many OTHER steps must happen between two teach steps / two game
# steps, so the session doesn't front-load all its teaching or all its
# fun in one burst.
TEACH_COOLDOWN_STEPS = 2
GAME_COOLDOWN_STEPS = 3

# Below this, the learner has dialed all the way to "practice" and no
# new key gets introduced today, regardless of how much room there is
# to grow.
LEARN_VS_PRACTICE_TEACH_FLOOR = 0.05

MAX_STEPS = 14
MIN_REMAINING_SECONDS_TO_ADD_STEP = 45


@dataclass(frozen=True, slots=True)
class SessionConfig:
    """The pre-session choices (PLAN.md's slider screen)."""

    duration_minutes: int = 15
    # 0.0 = max practice (fewest/no new keys), 1.0 = max learn (push new keys hard).
    learn_vs_practice: float = 0.5
    # 0.0 = broad coverage of every active key, 1.0 = narrow focus on the weakest few.
    focus_vs_general: float = 0.3


@dataclass(frozen=True, slots=True)
class StepPlan:
    """One short sub-lesson's slot in the day's plan.

    `focus_keys` is what this step should actively work on (new or
    weak keys); `allowed_keys` is everything introduced so far, safe
    as filler -- "it shouldn't use any letters in other lessons that
    weren't taught yet" (your words). Every activity module mixes the
    two in its own ratio; teach ignores allowed_keys entirely.
    """

    phase: str  # "warmup" | "teach" | "practice" | "eval" | "game"
    activity_id: str
    focus_keys: list[str]
    allowed_keys: list[str]
    duration_s: int


@dataclass(frozen=True, slots=True)
class SessionSkeleton:
    steps: list[StepPlan]
    active_keys: list[str]
    # All registered games, so the front-end can eventually offer a pick
    # of 2-4 (PLAN.md Section 6) even though v1 only has one to offer.
    game_options: list[str] = field(default_factory=list)
    ran_teach: bool = False
    ran_eval: bool = False


def _should_run_eval(key_stats: dict[str, KeyStat], keys: list[str]) -> bool:
    """Only worth checking once there's fresh practice on the active set.

    Pure function of skill-model state -- no session-history lookup yet
    (e.g. "don't eval two days running"), just "has this been drilled
    enough that a check would mean something." Not slider-dependent:
    readiness for a check is about mastery progress, not today's
    practice-vs-learn preference.
    """
    if not keys:
        return False
    return all(
        key_stats.get(k) is not None and key_stats[k].sample_count >= EVAL_MIN_SAMPLES
        for k in keys
    )


def _lerp(lo: float, hi: float, t: float) -> float:
    t = max(0.0, min(1.0, t))
    return lo + (hi - lo) * t


def build_session_skeleton(
    key_stats: dict[str, KeyStat],
    config: SessionConfig,
    now: datetime,
    rng: random.Random | None = None,
    bigram_stats: list[BigramStat] | None = None,
    step_seconds_scale: float = 1.0,
) -> SessionSkeleton:
    """Build the day's plan one short step at a time.

    Always opens with a warmup. After that, each iteration picks the
    next step's kind by priority -- eval (if ready and not done yet)
    > teach (if there's room, the slider allows it, and we're not
    teaching back-to-back) > game (if it's been a few steps) >
    practice (the default) -- until the time budget runs out or
    MAX_STEPS is hit.

    `step_seconds_scale` shrinks every step's length (and the
    min-remaining floor) proportionally -- a dev/testing convenience
    (PLAN.md's "quick session") so a short smoke test isn't just fewer
    steps at the normal ~1-2 minutes each.
    """
    rng = rng or random.Random()
    # `known_allowed` is the real, persisted truth (used for eligibility
    # checks -- eval readiness, "active_keys" in the result). `planned`
    # starts as a copy and grows each time this plan decides to teach a
    # new key, so a LATER teach step in the same session targets the
    # NEXT key, not the same one over and over -- without this, every
    # teach slot re-picked whatever was "next" against the pre-session
    # snapshot, which never changed during planning.
    known_allowed = active_keys(key_stats)
    planned = list(known_allowed)

    step_seconds = {
        phase: max(5, round(seconds * step_seconds_scale))
        for phase, seconds in SHORT_STEP_SECONDS.items()
    }
    min_remaining = max(5, round(MIN_REMAINING_SECONDS_TO_ADD_STEP * step_seconds_scale))

    warmup_activity = activities_by_kind("warmup")[0]
    teach_activity = activities_by_kind("teach")[0]
    practice_activity = activities_by_kind("practice")[0]
    eval_activity = activities_by_kind("eval")[0]
    game_candidates = activities_by_kind("game")
    game_options = [g.id for g in game_candidates]

    def weakest_focus_keys() -> list[str]:
        return recommend_warmup_keys(
            key_stats, planned, n=min(2, len(planned)), bigram_stats=bigram_stats
        )

    def practice_focus_keys() -> list[str]:
        pool_size = round(_lerp(len(planned), min(2, len(planned)), config.focus_vs_general))
        return recommend_warmup_keys(
            key_stats, planned, n=max(1, pool_size), bigram_stats=bigram_stats
        )

    steps: list[StepPlan] = []
    remaining = config.duration_minutes * 60
    steps_since_teach = TEACH_COOLDOWN_STEPS
    steps_since_game = GAME_COOLDOWN_STEPS
    eval_done = False
    ran_teach = False
    ran_eval = False

    # The space bar is taught before anything else: if it's never had a
    # teach step (no unlocked_at yet), the session opens with one.
    space_stat = key_stats.get(" ")
    space_untaught = space_stat is None or space_stat.unlocked_at is None
    if " " in planned and space_untaught and config.learn_vs_practice > LEARN_VS_PRACTICE_TEACH_FLOOR:
        step_len = min(step_seconds["teach"], remaining)
        steps.append(StepPlan("teach", teach_activity.id, [" "], list(planned), step_len))
        remaining -= step_len
        steps_since_teach = 0
        ran_teach = True

    step_len = min(step_seconds["warmup"], remaining)
    steps.append(StepPlan("warmup", warmup_activity.id, weakest_focus_keys(), list(planned), step_len))
    remaining -= step_len
    steps_since_teach += 1
    steps_since_game += 1

    while remaining >= min_remaining and len(steps) < MAX_STEPS:
        has_room = len(planned) < len(KEY_ORDER)
        can_teach = (
            has_room
            and config.learn_vs_practice > LEARN_VS_PRACTICE_TEACH_FLOOR
            and steps_since_teach >= TEACH_COOLDOWN_STEPS
        )
        can_eval = not eval_done and _should_run_eval(key_stats, known_allowed)
        can_game = bool(game_candidates) and steps_since_game >= GAME_COOLDOWN_STEPS

        if can_eval:
            phase, activity_id, focus = "eval", eval_activity.id, list(planned)
        elif can_teach:
            phase, activity_id, focus = "teach", teach_activity.id, next_keys_to_teach(planned, n=1)
        elif can_game:
            phase, activity_id, focus = "game", rng.choice(game_candidates).id, list(planned)
        else:
            phase, activity_id, focus = "practice", practice_activity.id, practice_focus_keys()

        step_len = min(step_seconds[phase], remaining)
        steps.append(StepPlan(phase, activity_id, focus, list(planned), step_len))
        remaining -= step_len

        steps_since_teach = 0 if phase == "teach" else steps_since_teach + 1
        steps_since_game = 0 if phase == "game" else steps_since_game + 1
        ran_teach = ran_teach or phase == "teach"
        if phase == "teach":
            planned.extend(focus)
        if phase == "eval":
            ran_eval = True
            eval_done = True

    return SessionSkeleton(
        steps=steps,
        active_keys=known_allowed,
        game_options=game_options,
        ran_teach=ran_teach,
        ran_eval=ran_eval,
    )


def chars_per_second_for_wpm(wpm: float) -> float:
    return max(0.5, wpm) * CHARS_PER_WORD / 60


def generate_step_content(
    step: StepPlan, estimated_wpm: float, rng: random.Random | None = None
) -> ActivityContent:
    """Fill in one skeleton step's actual typing content, sized to the
    current best guess at typing speed. Called once per step, just
    before that step is served to the learner -- not all up front --
    so a step near the end of the session reflects how fast today has
    actually gone rather than the pre-session estimate.
    """
    activity = get_activity(step.activity_id)
    return activity.generate(
        step.focus_keys,
        step.allowed_keys,
        step.duration_s,
        rng,
        chars_per_second=chars_per_second_for_wpm(estimated_wpm),
    )
