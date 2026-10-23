"""The session scheduler (PLAN.md Section 6): builds the day's plan from
skill-model state plus the learner's pre-session choices (duration,
learn-vs-practice, focus-vs-general), then generates each step's actual
typing content lazily, one step at a time.

Split into two stages on purpose:
  - build_session_skeleton(): pure, decides the phase *sequence* and
    each phase's *time budget and key focus* -- no typing content yet.
    This is what the progress bar shows up front (the shape of the
    whole session), and it doesn't depend on how fast anyone types.
  - generate_step_content(): turns one skeleton step into actual
    ActivityContent, using the CURRENT estimated typing speed. Calling
    this separately, just before each step starts rather than for all
    steps up front, is what lets later steps' content length adapt as
    the session's actual WPM becomes clearer (PLAN.md: "the number of
    characters in the later lessons might adapt if things speed up or
    down") -- the skeleton's `duration_s` time budgets don't change
    mid-session, but how much text fills that time does.

v1 scope: there's exactly one registered activity per kind (PLAN.md's
"only one choice, but it's still a good test" step), so the scheduler's
job right now is phase sequencing and content focus rather than
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
from app.skill_model import KEY_ORDER, active_keys

# A learner is considered to have "enough practice" on a key for an eval
# to be meaningful once it's been attempted this many times. Deliberately
# low for now; this is the first thing to tune once real usage exists.
EVAL_MIN_SAMPLES = 5

# 5 chars/word convention (same as score_attempt's WPM calc) -- used to
# turn a WPM estimate into "how many characters fit the time budget."
CHARS_PER_WORD = 5

# Share of the total session time each phase gets when it runs, before
# learn_vs_practice adjusts teach's share. These intentionally don't
# all run every day (teach/eval are conditional) and the leftover from
# whichever ones are skipped flows into practice.
BASE_PHASE_SHARE: dict[str, float] = {"warmup": 0.10, "eval": 0.10, "game": 0.25}
# teach's share scales between these two ends as learn_vs_practice goes 0 -> 1.
TEACH_SHARE_RANGE = (0.08, 0.30)
# Below this, the learner has dialed all the way to "practice" and no
# new key gets introduced today, regardless of how much room there is
# to grow.
LEARN_VS_PRACTICE_TEACH_FLOOR = 0.05

MIN_PHASE_SECONDS = 10  # floor so a very short session doesn't zero out a phase


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
    """One phase's slot in the day's plan: sequence, time budget, and
    which keys it focuses on -- everything decided up front, before
    any typing content exists.
    """

    phase: str  # "warmup" | "teach" | "practice" | "eval" | "game"
    activity_id: str
    focus_keys: list[str]
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
    (that's a real refinement for later: e.g. "don't eval two days
    running"), just "has this been drilled enough that a check would
    mean something." Not slider-dependent: readiness for a check is
    about mastery progress, not today's practice-vs-learn preference.
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


def _phase_time_budget(
    config: SessionConfig, run_teach: bool, run_eval: bool
) -> dict[str, int]:
    """Split the total session time across the phases that are actually
    running today. Skipped phases contribute 0 and their share flows
    into practice, which always runs and absorbs whatever's left.
    """
    total_s = config.duration_minutes * 60

    teach_share = _lerp(*TEACH_SHARE_RANGE, config.learn_vs_practice) if run_teach else 0.0
    eval_share = BASE_PHASE_SHARE["eval"] if run_eval else 0.0
    warmup_share = BASE_PHASE_SHARE["warmup"]
    game_share = BASE_PHASE_SHARE["game"]
    practice_share = max(0.0, 1.0 - warmup_share - teach_share - eval_share - game_share)

    shares = {
        "warmup": warmup_share,
        "teach": teach_share,
        "practice": practice_share,
        "eval": eval_share,
        "game": game_share,
    }
    return {phase: max(MIN_PHASE_SECONDS, round(total_s * share)) for phase, share in shares.items() if share > 0}


def build_session_skeleton(
    key_stats: dict[str, KeyStat],
    config: SessionConfig,
    now: datetime,
    rng: random.Random | None = None,
    bigram_stats: list[BigramStat] | None = None,
) -> SessionSkeleton:
    """The fixed arc (warmup -> teach/practice[/eval] -> game), with the
    learner's slider choices deciding how much room each phase gets and
    how tightly practice focuses on weak keys -- but no typing content
    generated yet (see module docstring).
    """
    rng = rng or random.Random()

    active = active_keys(key_stats)
    has_room_to_grow = len(active) < len(KEY_ORDER)
    run_teach = has_room_to_grow and config.learn_vs_practice > LEARN_VS_PRACTICE_TEACH_FLOOR
    run_eval = _should_run_eval(key_stats, active)

    seconds = _phase_time_budget(config, run_teach, run_eval)

    warmup_keys = recommend_warmup_keys(
        key_stats, active, n=min(2, len(active)), bigram_stats=bigram_stats
    )
    # focus_vs_general sizes the key pool practice draws from: the full
    # active set at 0.0 (general coverage), shrinking toward just the
    # weakest 2 at 1.0 (narrow focus on problem keys). Reuses the same
    # weakest-first ranking the warmup phase uses, just with a bigger n.
    practice_pool_size = round(_lerp(len(active), min(2, len(active)), config.focus_vs_general))
    practice_keys = recommend_warmup_keys(
        key_stats, active, n=max(1, practice_pool_size), bigram_stats=bigram_stats
    )

    steps: list[StepPlan] = []
    steps.append(
        StepPlan("warmup", activities_by_kind("warmup")[0].id, warmup_keys, seconds["warmup"])
    )
    if run_teach:
        steps.append(
            StepPlan("teach", activities_by_kind("teach")[0].id, active, seconds["teach"])
        )
    steps.append(
        StepPlan("practice", activities_by_kind("practice")[0].id, practice_keys, seconds["practice"])
    )
    if run_eval:
        steps.append(
            StepPlan("eval", activities_by_kind("eval")[0].id, active, seconds["eval"])
        )

    game_candidates = activities_by_kind("game")
    game_options = [g.id for g in game_candidates]
    if game_candidates:
        chosen_game = rng.choice(game_candidates)
        steps.append(StepPlan("game", chosen_game.id, active, seconds["game"]))

    return SessionSkeleton(
        steps=steps,
        active_keys=active,
        game_options=game_options,
        ran_teach=run_teach,
        ran_eval=run_eval,
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
        step.duration_s,
        rng,
        chars_per_second=chars_per_second_for_wpm(estimated_wpm),
    )
