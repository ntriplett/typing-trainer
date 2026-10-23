"""The session scheduler (PLAN.md Section 6): a pure function from skill-model
state to an ordered session plan.

v1 scope: there's exactly one registered activity per kind (PLAN.md's
"only one choice, but it's still a good test" step), so the scheduler's
job right now is phase *sequencing* and *content focus* (which keys each
phase targets, whether teach/eval even run today) rather than picking
among several alternatives per kind. Swapping in multiple candidates per
kind later is a change inside this module, not to its callers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime

from app.activities import activities_by_kind
from app.activities.base import ActivityContent
from app.models import BigramStat, KeyStat
from app.recommender import recommend_warmup_keys
from app.skill_model import KEY_ORDER, active_keys

# A learner is considered to have "enough practice" on a key for an eval
# to be meaningful once it's been attempted this many times. Deliberately
# low for now; this is the first thing to tune once real usage exists.
EVAL_MIN_SAMPLES = 5

# Default phase lengths. These intentionally don't sum to a strict 15:00 --
# transitions between phases eat the rest. Callers (tests, or a "just
# prove it works" manual run) can override any of these via
# `phase_seconds` to make a short end-to-end smoke session.
DEFAULT_PHASE_SECONDS: dict[str, int] = {
    "warmup": 90,
    "teach": 120,
    "practice": 300,
    "eval": 90,
    "game": 180,
}


@dataclass(frozen=True, slots=True)
class SessionStep:
    phase: str  # "warmup" | "teach" | "practice" | "eval" | "game"
    activity_id: str
    focus_keys: list[str]
    duration_s: int
    content: ActivityContent


@dataclass(frozen=True, slots=True)
class SessionPlan:
    steps: list[SessionStep]
    active_keys: list[str]
    # All registered games, so the front-end can eventually offer a pick
    # of 2-4 (PLAN.md Section 6) even though v1 only has one to offer.
    game_options: list[str] = field(default_factory=list)
    ran_teach: bool = False
    ran_eval: bool = False


def _build_step(
    phase: str, activity, focus_keys: list[str], duration_s: int, rng: random.Random
) -> SessionStep:
    content = activity.generate(focus_keys, duration_s, rng)
    return SessionStep(
        phase=phase,
        activity_id=activity.id,
        focus_keys=focus_keys,
        duration_s=duration_s,
        content=content,
    )


def _should_run_eval(key_stats: dict[str, KeyStat], keys: list[str]) -> bool:
    """Only worth checking once there's fresh practice on the active set.

    Pure function of skill-model state, per PLAN.md Section 6 -- no
    session-history lookup yet (that's a real refinement for later:
    e.g. "don't eval two days running"), just "has this been drilled
    enough that a check would mean something."
    """
    if not keys:
        return False
    return all(
        key_stats.get(k) is not None and key_stats[k].sample_count >= EVAL_MIN_SAMPLES
        for k in keys
    )


def build_session_plan(
    key_stats: dict[str, KeyStat],
    now: datetime,
    rng: random.Random | None = None,
    phase_seconds: dict[str, int] | None = None,
    bigram_stats: list[BigramStat] | None = None,
) -> SessionPlan:
    """The fixed arc (warmup -> teach/practice[/eval] -> game) with dynamic
    content, per PLAN.md Section 6:
      - warmup always runs, focused on keys the recommender ranks weakest
        right now (key + finger weakness, bumped by known-weak bigrams)
      - teach runs only if there's a next key still to unlock
      - practice always runs, focused on the full active set
      - eval runs only when the active set has had enough fresh practice
      - game always runs (one choice today; a real pick later)
    """
    rng = rng or random.Random()
    seconds = {**DEFAULT_PHASE_SECONDS, **(phase_seconds or {})}

    active = active_keys(key_stats)
    weakest = recommend_warmup_keys(
        key_stats, active, n=min(2, len(active)), bigram_stats=bigram_stats
    )
    has_room_to_grow = len(active) < len(KEY_ORDER)
    run_teach = has_room_to_grow
    run_eval = _should_run_eval(key_stats, active)

    steps: list[SessionStep] = []

    warmup_activity = activities_by_kind("warmup")[0]
    steps.append(_build_step("warmup", warmup_activity, weakest, seconds["warmup"], rng))

    if run_teach:
        teach_activity = activities_by_kind("teach")[0]
        steps.append(_build_step("teach", teach_activity, active, seconds["teach"], rng))

    practice_activity = activities_by_kind("practice")[0]
    steps.append(_build_step("practice", practice_activity, active, seconds["practice"], rng))

    if run_eval:
        eval_activity = activities_by_kind("eval")[0]
        steps.append(_build_step("eval", eval_activity, active, seconds["eval"], rng))

    game_candidates = activities_by_kind("game")
    game_options = [g.id for g in game_candidates]
    if game_candidates:
        chosen_game = rng.choice(game_candidates)
        steps.append(_build_step("game", chosen_game, active, seconds["game"], rng))

    return SessionPlan(
        steps=steps,
        active_keys=active,
        game_options=game_options,
        ran_teach=run_teach,
        ran_eval=run_eval,
    )
