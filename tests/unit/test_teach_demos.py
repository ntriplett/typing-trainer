"""Unit tests for the 3 teach-demo variants and their registry.
Demo-only modules (not in the main activity REGISTRY) -- see
app/activities/teach_demos.py's module docstring.
"""

import random

import pytest

from app.activities.base import KeystrokeEvent
from app.activities.teach_demos import DEMO_REGISTRY, get_demo_activity, list_demo_activities

FOCUS_KEY = ["r"]
ALLOWED_KEYS = ["f", "j", "d", "k"]

ALL_DEMOS = list(DEMO_REGISTRY.values())
ALL_IDS = [a.id for a in ALL_DEMOS]


def test_list_demo_activities_returns_all_three_with_descriptions():
    demos = list_demo_activities()
    assert len(demos) == 3
    for demo in demos:
        assert demo["id"]
        assert len(demo["description"]) > 10


def test_get_demo_activity_raises_for_unknown_id():
    with pytest.raises(KeyError):
        get_demo_activity("not-a-real-demo")


@pytest.mark.parametrize("activity", ALL_DEMOS, ids=ALL_IDS)
def test_is_eligible_requires_a_focus_key(activity):
    assert activity.is_eligible([], ALLOWED_KEYS) is False
    assert activity.is_eligible(FOCUS_KEY, ALLOWED_KEYS) is True


@pytest.mark.parametrize("activity", ALL_DEMOS, ids=ALL_IDS)
def test_generate_produces_a_nonempty_ordered_micro_lesson(activity):
    content = activity.generate(FOCUS_KEY, ALLOWED_KEYS, duration_s=60, rng=random.Random(1))
    assert content.micro_steps is not None
    assert len(content.micro_steps) >= 3
    # every step has a kind and instructions; the first is always the diagram
    assert content.micro_steps[0]["kind"] == "diagram"
    for step in content.micro_steps:
        assert step["kind"]
        assert step["instructions"]


@pytest.mark.parametrize("activity", ALL_DEMOS, ids=ALL_IDS)
def test_generate_only_ever_uses_the_focus_key_and_allowed_keys(activity):
    content = activity.generate(FOCUS_KEY, ALLOWED_KEYS, duration_s=60, rng=random.Random(1))
    for step in content.micro_steps:
        # anchor_check (home row position review) and a reach-return
        # drill's home-key anchor are deliberate exceptions: physical
        # hand-position practice isn't "letter content" gated by the
        # allowed-keys progression, by design.
        if step["kind"] in ("anchor_check",):
            continue
        letters = set(step["prompt"].replace(" ", ""))
        allowed_for_step = set(FOCUS_KEY) | set(ALLOWED_KEYS) | {step.get("home_key", "")}
        assert letters <= allowed_for_step
    assert set(content.keys) <= set(FOCUS_KEY) | set(ALLOWED_KEYS)
    assert "r" in content.keys  # the new key is always included


@pytest.mark.parametrize("activity", ALL_DEMOS, ids=ALL_IDS)
def test_generate_is_deterministic_given_a_seeded_rng(activity):
    a = activity.generate(FOCUS_KEY, ALLOWED_KEYS, duration_s=60, rng=random.Random(42))
    b = activity.generate(FOCUS_KEY, ALLOWED_KEYS, duration_s=60, rng=random.Random(42))
    assert a == b


@pytest.mark.parametrize("activity", ALL_DEMOS, ids=ALL_IDS)
def test_generate_falls_back_gracefully_with_no_allowed_keys(activity):
    # A brand-new learner with nothing else taught yet -- the combo
    # step(s) should still produce something (falling back to the
    # focus key alone) rather than crashing. anchor_check/reach-return's
    # home-row/home-key content is exempt -- see the test above.
    content = activity.generate(FOCUS_KEY, [], duration_s=60, rng=random.Random(1))
    assert content.micro_steps
    for step in content.micro_steps:
        if step["kind"] == "anchor_check":
            continue
        allowed_for_step = {"r", step.get("home_key", "")}
        assert set(step["prompt"].replace(" ", "")) <= allowed_for_step


@pytest.mark.parametrize("activity", ALL_DEMOS, ids=ALL_IDS)
def test_score_round_trips_through_the_activity(activity):
    content = activity.generate(FOCUS_KEY, ALLOWED_KEYS, duration_s=60, rng=random.Random(1))
    keystrokes = [KeystrokeEvent(k, k, True, 200) for k in content.keys for _ in range(5)]
    result = activity.score(content, keystrokes)
    assert result.activity_id == activity.id
    assert result.accuracy == 1.0
    assert result.reward_signal == "nailed_it"


def test_staged_combo_demo_widens_the_combo_pool_one_key_at_a_time():
    from app.activities.teach_staged_combo_demo import TeachStagedComboDemo

    activity = TeachStagedComboDemo()
    content = activity.generate(FOCUS_KEY, ALLOWED_KEYS, duration_s=60, rng=random.Random(1))
    combo_steps = [s for s in content.micro_steps if s["kind"] == "combo"]
    assert len(combo_steps) == 3  # pool sizes 1, 2, 3
    pool_sizes = [len(set(s["prompt"].replace(" ", "")) - {"r"}) for s in combo_steps]
    assert pool_sizes == sorted(pool_sizes)  # non-decreasing as it widens


def test_reach_return_demo_drill_step_pairs_new_key_with_its_home_key():
    from app.activities.teach_reach_return_demo import TeachReachReturnDemo

    activity = TeachReachReturnDemo()
    content = activity.generate(FOCUS_KEY, ALLOWED_KEYS, duration_s=60, rng=random.Random(1))
    drill_step = next(s for s in content.micro_steps if s["kind"] == "drill")
    assert set(drill_step["prompt"].replace(" ", "")) == {"r", "f"}


def test_hand_anchor_demo_includes_an_anchor_check_step():
    from app.activities.teach_hand_anchor_demo import TeachHandAnchorDemo

    activity = TeachHandAnchorDemo()
    content = activity.generate(FOCUS_KEY, ALLOWED_KEYS, duration_s=60, rng=random.Random(1))
    assert any(s["kind"] == "anchor_check" for s in content.micro_steps)
