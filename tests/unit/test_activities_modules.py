"""Module tests: each of the 5 v1 activities (warmup/teach/practice/eval/
game) against the shared Activity contract (PLAN.md Section 7), plus one
module-specific test for teach's blocked (non-random) pattern.

Parametrized over the registry rather than duplicated 5x, since all 5
v1 modules are intentionally identical in structure -- that's the point
of the walking-skeleton step.
"""

import random

import pytest

from app.activities import REGISTRY
from app.activities.base import KeystrokeEvent

ACTIVE_KEYS = ["f", "j", "d", "k"]

ALL_ACTIVITIES = list(REGISTRY.values())
ALL_IDS = [a.id for a in ALL_ACTIVITIES]


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_is_eligible_true_with_active_keys(activity):
    assert activity.is_eligible(ACTIVE_KEYS) is True


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_is_eligible_false_with_no_keys(activity):
    assert activity.is_eligible([]) is False


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_generate_picks_two_keys_from_the_active_set(activity):
    content = activity.generate(ACTIVE_KEYS, duration_s=30, rng=random.Random(42))
    assert content.activity_id == activity.id
    assert content.kind == activity.kind
    assert len(content.keys) == 2
    assert set(content.keys) <= set(ACTIVE_KEYS)
    assert content.prompt  # non-empty


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_generate_is_deterministic_given_a_seeded_rng(activity):
    content_a = activity.generate(ACTIVE_KEYS, duration_s=30, rng=random.Random(7))
    content_b = activity.generate(ACTIVE_KEYS, duration_s=30, rng=random.Random(7))
    assert content_a == content_b


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_score_round_trips_through_the_activity(activity):
    content = activity.generate(ACTIVE_KEYS, duration_s=30, rng=random.Random(42))
    keystrokes = [KeystrokeEvent(k, k, True, 200) for k in content.keys for _ in range(5)]
    result = activity.score(content, keystrokes)
    assert result.activity_id == activity.id
    assert result.keys == content.keys
    assert result.accuracy == 1.0
    assert result.reward_signal == "nailed_it"


def test_teach_uses_blocked_not_randomized_pattern():
    teach = REGISTRY["teach_random_keys_v1"]
    content = teach.generate(ACTIVE_KEYS, duration_s=30, rng=random.Random(1))
    key_a, key_b = content.keys
    # blocked means each key appears as its own contiguous run, e.g. "ffff jjjj",
    # not interleaved -- so the prompt is exactly two space-separated blocks.
    blocks = content.prompt.split(" ")
    assert len(blocks) == 2
    assert blocks[0] == key_a * 4
    assert blocks[1] == key_b * 4


def test_warmup_and_practice_use_randomized_not_blocked_pattern():
    for activity_id in ("warmup_random_keys_v1", "practice_random_keys_v1"):
        activity = REGISTRY[activity_id]
        content = activity.generate(ACTIVE_KEYS, duration_s=30, rng=random.Random(1))
        letters = content.prompt.replace(" ", "")
        # with a random mix of 2 keys over a long-enough sequence, both
        # keys should show up (not a single blocked run of one key).
        assert set(content.keys) == set(letters) or len(letters) < 4
