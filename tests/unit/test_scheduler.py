"""Unit tests for the scheduler: a pure function of skill-model state to
a session plan. No DB, no clock side effects, no UI.
"""

import random
from datetime import UTC, datetime

from app import scheduler
from app.models import KeyStat
from app.skill_model import KEY_ORDER

NOW = datetime(2026, 10, 23, tzinfo=UTC)


def mastered_stat(key: str, sample_count: int = 50) -> KeyStat:
    return KeyStat(
        learner_id=1,
        key=key,
        ema_time_ms=350.0,
        confidence=1.1,
        accuracy_rolling=0.97,
        sample_count=sample_count,
        unlocked_at=NOW,
        mastered_at=NOW,
    )


def test_brand_new_learner_gets_warmup_teach_practice_game_but_no_eval():
    plan = scheduler.build_session_plan({}, now=NOW, rng=random.Random(1))

    phases = [step.phase for step in plan.steps]
    assert phases == ["warmup", "teach", "practice", "game"]
    assert plan.ran_teach is True
    assert plan.ran_eval is False
    assert plan.active_keys == list(KEY_ORDER[: scheduler_initial_count()])


def scheduler_initial_count():
    from app.skill_model import INITIAL_ACTIVE_KEY_COUNT

    return INITIAL_ACTIVE_KEY_COUNT


def test_eval_runs_once_active_keys_have_enough_samples():
    active = scheduler_initial_count()
    key_stats = {
        key: KeyStat(
            learner_id=1,
            key=key,
            ema_time_ms=500.0,
            confidence=0.8,
            accuracy_rolling=0.9,
            sample_count=scheduler.EVAL_MIN_SAMPLES,
            unlocked_at=NOW,
            mastered_at=None,
        )
        for key in KEY_ORDER[:active]
    }
    plan = scheduler.build_session_plan(key_stats, now=NOW, rng=random.Random(1))
    assert plan.ran_eval is True
    assert "eval" in [s.phase for s in plan.steps]


def test_eval_skipped_when_samples_too_low():
    active = scheduler_initial_count()
    key_stats = {
        key: KeyStat(
            learner_id=1,
            key=key,
            ema_time_ms=500.0,
            confidence=0.8,
            accuracy_rolling=0.9,
            sample_count=1,
            unlocked_at=NOW,
            mastered_at=None,
        )
        for key in KEY_ORDER[:active]
    }
    plan = scheduler.build_session_plan(key_stats, now=NOW, rng=random.Random(1))
    assert plan.ran_eval is False
    assert "eval" not in [s.phase for s in plan.steps]


def test_teach_skipped_once_every_key_is_unlocked():
    key_stats = {key: mastered_stat(key) for key in KEY_ORDER}
    plan = scheduler.build_session_plan(key_stats, now=NOW, rng=random.Random(1))
    assert plan.ran_teach is False
    assert "teach" not in [s.phase for s in plan.steps]
    assert plan.active_keys == list(KEY_ORDER)


def test_game_always_included_and_uses_a_registered_game():
    plan = scheduler.build_session_plan({}, now=NOW, rng=random.Random(1))
    game_steps = [s for s in plan.steps if s.phase == "game"]
    assert len(game_steps) == 1
    assert game_steps[0].activity_id in plan.game_options


def test_warmup_focuses_on_weakest_keys_not_full_active_set():
    key_stats = {
        KEY_ORDER[0]: mastered_stat(KEY_ORDER[0]),  # strong
        KEY_ORDER[1]: KeyStat(  # weak
            learner_id=1,
            key=KEY_ORDER[1],
            ema_time_ms=900.0,
            confidence=0.3,
            accuracy_rolling=0.6,
            sample_count=3,
            unlocked_at=NOW,
            mastered_at=None,
        ),
    }
    plan = scheduler.build_session_plan(key_stats, now=NOW, rng=random.Random(1))
    warmup_step = next(s for s in plan.steps if s.phase == "warmup")
    assert KEY_ORDER[1] in warmup_step.focus_keys


def test_phase_seconds_override_is_respected():
    plan = scheduler.build_session_plan(
        {}, now=NOW, rng=random.Random(1), phase_seconds={"warmup": 5, "teach": 5, "practice": 5, "game": 5}
    )
    for step in plan.steps:
        assert step.duration_s == 5


def test_steps_always_in_fixed_phase_order():
    active = scheduler_initial_count()
    key_stats = {
        key: KeyStat(
            learner_id=1,
            key=key,
            ema_time_ms=500.0,
            confidence=0.8,
            accuracy_rolling=0.9,
            sample_count=scheduler.EVAL_MIN_SAMPLES,
            unlocked_at=NOW,
            mastered_at=None,
        )
        for key in KEY_ORDER[:active]
    }
    plan = scheduler.build_session_plan(key_stats, now=NOW, rng=random.Random(1))
    phases = [s.phase for s in plan.steps]
    canonical_order = ["warmup", "teach", "practice", "eval", "game"]
    assert phases == [p for p in canonical_order if p in phases]


def test_plan_is_deterministic_given_a_seeded_rng():
    plan_a = scheduler.build_session_plan({}, now=NOW, rng=random.Random(99))
    plan_b = scheduler.build_session_plan({}, now=NOW, rng=random.Random(99))
    assert [s.content.prompt for s in plan_a.steps] == [s.content.prompt for s in plan_b.steps]
