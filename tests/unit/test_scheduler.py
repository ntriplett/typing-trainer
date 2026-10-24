"""Unit tests for the scheduler: the step-by-step skeleton builder
(short sub-lessons, sequenced by skill-model state + the learner's
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


def test_fifteen_minute_session_produces_roughly_ten_short_steps():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert 8 <= len(skeleton.steps) <= 12
    for step in skeleton.steps:
        assert 45 <= step.duration_s <= 120  # ~1-2 minutes each, per your call


def test_brand_new_learner_opens_with_a_space_bar_lesson_then_warmup():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert skeleton.steps[0].phase == "teach"
    assert skeleton.steps[0].focus_keys == [" "]
    assert skeleton.steps[1].phase == "warmup"


def test_session_opens_with_warmup_once_space_is_taught():
    key_stats = {" ": scheduler_space_taught()}
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert skeleton.steps[0].phase == "warmup"


def scheduler_space_taught() -> KeyStat:
    return KeyStat(
        learner_id=1, key=" ", ema_time_ms=300.0, confidence=1.0, accuracy_rolling=0.95,
        sample_count=5, unlocked_at=NOW, mastered_at=None,
    )


def test_no_teach_without_room_to_grow():
    key_stats = {key: mastered_stat(key) for key in KEY_ORDER}
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert skeleton.ran_teach is False
    assert "teach" not in [s.phase for s in skeleton.steps]
    assert skeleton.active_keys == list(KEY_ORDER)


def test_no_teach_when_slider_is_all_the_way_to_practice():
    config = SessionConfig(duration_minutes=15, learn_vs_practice=0.0, focus_vs_general=0.3)
    skeleton = scheduler.build_session_skeleton({}, config, now=NOW, rng=random.Random(1))
    assert skeleton.ran_teach is False
    assert "teach" not in [s.phase for s in skeleton.steps]


def test_teach_runs_for_a_new_learner_with_room_to_grow():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert skeleton.ran_teach is True
    assert "teach" in [s.phase for s in skeleton.steps]


def test_teach_steps_are_never_back_to_back():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    phases = [s.phase for s in skeleton.steps]
    teach_indices = [i for i, p in enumerate(phases) if p == "teach"]
    for a, b in zip(teach_indices, teach_indices[1:]):
        assert b - a > scheduler.TEACH_COOLDOWN_STEPS


def test_teach_focus_is_the_single_next_untaught_key_not_a_random_pair():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    # the first teach is the space bar (see above); the next is a letter
    teach_steps = [s for s in skeleton.steps if s.phase == "teach"]
    assert teach_steps[1].focus_keys == [KEY_ORDER[INITIAL_ACTIVE_KEY_COUNT]]


def test_multiple_teach_steps_in_one_session_target_different_keys():
    # Regression: teach steps used to all re-pick the same "next" key
    # because the plan's notion of "allowed" never advanced as earlier
    # teach steps in the SAME plan were inserted.
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    teach_focuses = [tuple(s.focus_keys) for s in skeleton.steps if s.phase == "teach"]
    assert len(teach_focuses) >= 2, "expected at least 2 teach steps for a brand-new learner"
    assert len(set(teach_focuses)) == len(teach_focuses)


def test_earlier_game_steps_do_not_retroactively_gain_later_taught_keys():
    # Regression: game steps' focus_keys used to alias the same
    # mutable list that later teach steps extend, so an EARLIER game
    # step would end up listing a key that hadn't been taught yet by
    # the time it actually runs.
    key_stats = {
        key: stat_with_samples(key, 5)
        for key in KEY_ORDER[:INITIAL_ACTIVE_KEY_COUNT]
    }
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))

    taught_by: dict[str, int] = {}
    for i, step in enumerate(skeleton.steps):
        if step.phase == "teach":
            for key in step.focus_keys:
                taught_by[key] = i

    for i, step in enumerate(skeleton.steps):
        if step.phase == "game":
            for key in step.focus_keys:
                assert taught_by.get(key, -1) <= i, (
                    f"step {i} ({step.phase}) focuses on {key!r}, "
                    f"which isn't taught until step {taught_by.get(key)}"
                )


def test_steps_after_a_teach_step_include_the_newly_taught_key_in_allowed():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    first_teach_index = next(i for i, s in enumerate(skeleton.steps) if s.phase == "teach")
    taught_key = skeleton.steps[first_teach_index].focus_keys[0]
    later_step = skeleton.steps[first_teach_index + 1]
    assert taught_key in later_step.allowed_keys


def test_every_step_carries_at_least_the_known_allowed_set():
    # Each step's allowed_keys is a non-shrinking superset of the real
    # active_keys -- it only ever grows within a plan as teach steps
    # provisionally introduce new ones (see the "different keys" test).
    key_stats = {KEY_ORDER[0]: mastered_stat(KEY_ORDER[0])}
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    for step in skeleton.steps:
        assert set(skeleton.active_keys) <= set(step.allowed_keys)


def test_games_are_spaced_out_not_clustered():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    phases = [s.phase for s in skeleton.steps]
    game_indices = [i for i, p in enumerate(phases) if p == "game"]
    for a, b in zip(game_indices, game_indices[1:]):
        assert b - a >= scheduler.GAME_COOLDOWN_STEPS


def test_warmup_focuses_on_weakest_keys_not_full_active_set():
    key_stats = {
        KEY_ORDER[0]: mastered_stat(KEY_ORDER[0]),  # strong
        KEY_ORDER[1]: KeyStat(  # weak
            learner_id=1, key=KEY_ORDER[1], ema_time_ms=900.0, confidence=0.3,
            accuracy_rolling=0.6, sample_count=3, unlocked_at=NOW, mastered_at=None,
        ),
    }
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert KEY_ORDER[1] in skeleton.steps[0].focus_keys


def test_focus_vs_general_narrows_the_practice_key_pool():
    key_stats = {key: mastered_stat(key) for key in KEY_ORDER[:6]}
    general_config = SessionConfig(duration_minutes=15, learn_vs_practice=0.0, focus_vs_general=0.0)
    focus_config = SessionConfig(duration_minutes=15, learn_vs_practice=0.0, focus_vs_general=1.0)

    general_skeleton = scheduler.build_session_skeleton(key_stats, general_config, now=NOW, rng=random.Random(1))
    focus_skeleton = scheduler.build_session_skeleton(key_stats, focus_config, now=NOW, rng=random.Random(1))

    general_practice = next(s for s in general_skeleton.steps if s.phase == "practice")
    focus_practice = next(s for s in focus_skeleton.steps if s.phase == "practice")
    assert len(focus_practice.focus_keys) < len(general_practice.focus_keys)
    assert len(general_practice.focus_keys) == len(general_skeleton.active_keys)


def test_duration_minutes_scales_total_step_count():
    short = scheduler.build_session_skeleton(
        {}, SessionConfig(duration_minutes=15, learn_vs_practice=0.5, focus_vs_general=0.3), now=NOW, rng=random.Random(1)
    )
    long = scheduler.build_session_skeleton(
        {}, SessionConfig(duration_minutes=30, learn_vs_practice=0.5, focus_vs_general=0.3), now=NOW, rng=random.Random(1)
    )
    assert len(long.steps) > len(short.steps)


def test_skeleton_is_deterministic_given_a_seeded_rng():
    a = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(99))
    b = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(99))
    assert [s.activity_id for s in a.steps] == [s.activity_id for s in b.steps]


def test_stops_at_max_steps_even_with_a_very_long_duration():
    config = SessionConfig(duration_minutes=60, learn_vs_practice=0.5, focus_vs_general=0.3)
    skeleton = scheduler.build_session_skeleton({}, config, now=NOW, rng=random.Random(1))
    assert len(skeleton.steps) <= scheduler.MAX_STEPS


def test_step_seconds_scale_shrinks_every_step_not_just_the_count():
    normal = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    quick = scheduler.build_session_skeleton(
        {}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1), step_seconds_scale=0.15
    )
    assert quick.steps[0].duration_s < normal.steps[0].duration_s


# --- generate_step_content / adaptive length ---------------------------------


def test_chars_per_second_scales_with_wpm():
    slow = scheduler.chars_per_second_for_wpm(10)
    fast = scheduler.chars_per_second_for_wpm(40)
    assert fast > slow
    assert slow == 10 * 5 / 60


def test_chars_per_second_has_a_floor_for_very_low_or_zero_wpm():
    assert scheduler.chars_per_second_for_wpm(0) > 0


def test_generate_step_content_produces_more_text_for_a_faster_estimate():
    step = scheduler.StepPlan("practice", "practice_random_keys_v1", ["f"], ["j"], duration_s=60)
    slow_content = scheduler.generate_step_content(step, estimated_wpm=5, rng=random.Random(1))
    fast_content = scheduler.generate_step_content(step, estimated_wpm=40, rng=random.Random(1))
    assert len(fast_content.prompt) > len(slow_content.prompt)


def test_generate_step_content_uses_the_step_key_pools():
    step = scheduler.StepPlan("warmup", "practice_fishing_v1", ["f"], ["j"], duration_s=30)
    content = scheduler.generate_step_content(step, estimated_wpm=15, rng=random.Random(1))
    assert set(content.keys) <= {"f", "j"}


def test_no_eval_steps_and_warmup_is_short_easy_practice():
    skeleton = scheduler.build_session_skeleton({}, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert "eval" not in [s.phase for s in skeleton.steps]
    warmup = next(s for s in skeleton.steps if s.phase == "warmup")
    assert warmup.activity_id.startswith("practice_")
    assert warmup.difficulty == scheduler.WARMUP_DIFFICULTY < scheduler.PRACTICE_DIFFICULTY
    assert warmup.duration_s < scheduler.SHORT_STEP_SECONDS["practice"]


def test_practice_steps_rotate_through_themes():
    config = SessionConfig(duration_minutes=30, learn_vs_practice=0.0, focus_vs_general=0.3)
    key_stats = {key: mastered_stat(key) for key in KEY_ORDER[:6]}
    skeleton = scheduler.build_session_skeleton(key_stats, config, now=NOW, rng=random.Random(3))
    ids = [s.activity_id for s in skeleton.steps if s.phase in ("warmup", "practice")]
    assert len(ids) >= 5
    assert len(set(ids)) == len(ids)  # fewer than 11 practice steps: no repeats


def test_session_skill_snapshot_carries_weak_keys_into_practice():
    weak = KeyStat(
        learner_id=1, key="d", ema_time_ms=500.0, confidence=0.5,
        accuracy_rolling=0.5, sample_count=20, unlocked_at=NOW, mastered_at=None,
    )
    key_stats = {key: mastered_stat(key) for key in KEY_ORDER[:6]} | {"d": weak}
    skeleton = scheduler.build_session_skeleton(key_stats, DEFAULT_CONFIG, now=NOW, rng=random.Random(1))
    assert skeleton.skill.weak_keys == ("d",)
