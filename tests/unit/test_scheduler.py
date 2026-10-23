"""Unit tests for the scheduler: skeleton building (sequencing + time
budgets + key focus, driven by skill-model state and the learner's
slider choices) and lazy content generation. No DB, no clock side
effects, no UI.
"""

import random
from datetime import UTC, datetime

from app import scheduler
from app.models import KeyStat
from app.scheduler import SessionConfig
from app.skill_model import KEY_ORDER, INITIAL_ACTIVE_KEY_COUNT

NOW = datetime(2026, 10, 23, tzinfo=UTC)
DEFAULT_CONFIG = SessionConfig(duration_minutes=15, learn_vs_practice=0.5, focus_vs_general=0.3)


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


def stat_with_samples(key: str, sample_count: int) -> KeyStat:
    return KeyStat(
        learner_id=1,
        key=key,
        ema_time_ms=500.0,
        confidence=0.8,
        accuracy_rolling=0.9,
        sample_count=sample_count,
        unlocked_at=NOW,
        mastered_at=None,
    )


def test_brand_new_learner_gets_warmup_teach_practice_game_but_no_eval():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))

    phases = [step.phase for step in skeleton.steps]
    assert phases == ["warmup", "teach", "practice", "game"]
    assert skeleton.ran_teach is True
    assert skeleton.ran_eval is False
    assert skeleton.active_keys == list(KEY_ORDER[:INITIAL_ACTIVE_KEY_COUNT])


def test_eval_runs_once_active_keys_have_enough_samples():
    key_stats = {
        key: stat_with_samples(key, scheduler.EVAL_MIN_SAMPLES)
        for key in KEY_ORDER[:INITIAL_ACTIVE_KEY_COUNT]
    }
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert skeleton.ran_eval is True
    assert "eval" in [s.phase for s in skeleton.steps]


def test_eval_skipped_when_samples_too_low():
    key_stats = {key: stat_with_samples(key, 1) for key in KEY_ORDER[:INITIAL_ACTIVE_KEY_COUNT]}
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert skeleton.ran_eval is False
    assert "eval" not in [s.phase for s in skeleton.steps]


def test_teach_skipped_once_every_key_is_unlocked():
    key_stats = {key: mastered_stat(key) for key in KEY_ORDER}
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert skeleton.ran_teach is False
    assert "teach" not in [s.phase for s in skeleton.steps]
    assert skeleton.active_keys == list(KEY_ORDER)


def test_teach_skipped_when_slider_is_all_the_way_to_practice():
    config = SessionConfig(duration_minutes=15, learn_vs_practice=0.0, focus_vs_general=0.3)
    skeleton = scheduler.build_session_skeleton({}, config, now=NOW, rng=random.Random(1))
    assert skeleton.ran_teach is False
    assert "teach" not in [s.phase for s in skeleton.steps]


def test_teach_gets_a_bigger_time_share_the_more_learn_biased_the_slider_is():
    practice_config = SessionConfig(duration_minutes=15, learn_vs_practice=0.1, focus_vs_general=0.3)
    learn_config = SessionConfig(duration_minutes=15, learn_vs_practice=1.0, focus_vs_general=0.3)

    practice_skeleton = scheduler.build_session_skeleton({}, practice_config, now=NOW, rng=random.Random(1))
    learn_skeleton = scheduler.build_session_skeleton({}, learn_config, now=NOW, rng=random.Random(1))

    practice_teach_s = next(s.duration_s for s in practice_skeleton.steps if s.phase == "teach")
    learn_teach_s = next(s.duration_s for s in learn_skeleton.steps if s.phase == "teach")
    assert learn_teach_s > practice_teach_s


def test_game_always_included_and_uses_a_registered_game():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    game_steps = [s for s in skeleton.steps if s.phase == "game"]
    assert len(game_steps) == 1
    assert game_steps[0].activity_id in skeleton.game_options


def test_warmup_focuses_on_weakest_keys_not_full_active_set():
    key_stats = {
        KEY_ORDER[0]: mastered_stat(KEY_ORDER[0]),  # strong
        KEY_ORDER[1]: KeyStat(  # weak
            learner_id=1, key=KEY_ORDER[1], ema_time_ms=900.0, confidence=0.3,
            accuracy_rolling=0.6, sample_count=3, unlocked_at=NOW, mastered_at=None,
        ),
    }
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    warmup_step = next(s for s in skeleton.steps if s.phase == "warmup")
    assert KEY_ORDER[1] in warmup_step.focus_keys


def test_focus_vs_general_narrows_the_practice_key_pool():
    # Enough active keys that the pool size can meaningfully differ.
    key_stats = {key: mastered_stat(key) for key in KEY_ORDER[:6]}
    general_config = SessionConfig(duration_minutes=15, learn_vs_practice=0.5, focus_vs_general=0.0)
    focus_config = SessionConfig(duration_minutes=15, learn_vs_practice=0.5, focus_vs_general=1.0)

    general_skeleton = scheduler.build_session_skeleton(key_stats, general_config, now=NOW, rng=random.Random(1))
    focus_skeleton = scheduler.build_session_skeleton(key_stats, focus_config, now=NOW, rng=random.Random(1))

    general_practice = next(s for s in general_skeleton.steps if s.phase == "practice")
    focus_practice = next(s for s in focus_skeleton.steps if s.phase == "practice")
    assert len(focus_practice.focus_keys) < len(general_practice.focus_keys)
    assert len(general_practice.focus_keys) == len(general_skeleton.active_keys)


def test_duration_minutes_scales_total_time_budget():
    short = scheduler.build_session_skeleton(
        {}, SessionConfig(duration_minutes=15, learn_vs_practice=0.5, focus_vs_general=0.3), now=NOW, rng=random.Random(1)
    )
    long = scheduler.build_session_skeleton(
        {}, SessionConfig(duration_minutes=30, learn_vs_practice=0.5, focus_vs_general=0.3), now=NOW, rng=random.Random(1)
    )
    short_total = sum(s.duration_s for s in short.steps)
    long_total = sum(s.duration_s for s in long.steps)
    assert long_total > short_total * 1.5  # roughly double, allowing for rounding/floors


def test_steps_always_in_fixed_phase_order():
    key_stats = {
        key: stat_with_samples(key, scheduler.EVAL_MIN_SAMPLES)
        for key in KEY_ORDER[:INITIAL_ACTIVE_KEY_COUNT]
    }
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    phases = [s.phase for s in skeleton.steps]
    canonical_order = ["warmup", "teach", "practice", "eval", "game"]
    assert phases == [p for p in canonical_order if p in phases]


def test_skeleton_is_deterministic_given_a_seeded_rng():
    a = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(99))
    b = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(99))
    assert [s.activity_id for s in a.steps] == [s.activity_id for s in b.steps]


# --- generate_step_content / adaptive length ---------------------------------


def test_chars_per_second_scales_with_wpm():
    slow = scheduler.chars_per_second_for_wpm(10)
    fast = scheduler.chars_per_second_for_wpm(40)
    assert fast > slow
    assert slow == 10 * 5 / 60


def test_chars_per_second_has_a_floor_for_very_low_or_zero_wpm():
    # A learner with 0 completed keystrokes shouldn't generate an
    # empty/near-empty prompt for the next step.
    assert scheduler.chars_per_second_for_wpm(0) > 0


def test_generate_step_content_produces_more_text_for_a_faster_estimate():
    step = scheduler.StepPlan("practice", "practice_random_keys_v1", ["f", "j"], duration_s=60)
    slow_content = scheduler.generate_step_content(step, estimated_wpm=5, rng=random.Random(1))
    fast_content = scheduler.generate_step_content(step, estimated_wpm=40, rng=random.Random(1))
    assert len(fast_content.prompt) > len(slow_content.prompt)


def test_generate_step_content_uses_the_step_focus_keys():
    step = scheduler.StepPlan("warmup", "warmup_random_keys_v1", ["f", "j"], duration_s=30)
    content = scheduler.generate_step_content(step, estimated_wpm=15, rng=random.Random(1))
    assert set(content.keys) <= {"f", "j"}
