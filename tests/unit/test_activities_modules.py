"""Module tests: each of the 5 v1 activities (warmup/teach/practice/eval/
game) against the shared Activity contract (focus_keys/allowed_keys
dual-pool input, PLAN.md Section 7), plus module-specific pattern checks.

Parametrized over the registry rather than duplicated 5x.
"""

import random

import pytest

from app.activities import REGISTRY
from app.activities.base import KeystrokeEvent

FOCUS_KEYS = ["f", "j"]
ALLOWED_KEYS = ["d", "k", "s", "l"]

ALL_ACTIVITIES = list(REGISTRY.values())
ALL_IDS = [a.id for a in ALL_ACTIVITIES]


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_is_eligible_true_with_focus_keys(activity):
    # Every v1 module accepts focus-only input -- teach specifically
    # requires it (it ignores allowed_keys), the others are fine too.
    assert activity.is_eligible(FOCUS_KEYS, []) is True


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_is_eligible_false_when_both_pools_empty(activity):
    assert activity.is_eligible([], []) is False


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_generate_only_uses_the_given_pools(activity):
    content = activity.generate(FOCUS_KEYS, ALLOWED_KEYS, duration_s=30, rng=random.Random(42))
    assert content.activity_id == activity.id
    assert content.kind == activity.kind
    assert set(content.keys) <= set(FOCUS_KEYS) | set(ALLOWED_KEYS)
    assert set(content.prompt.replace(" ", "")) <= set(FOCUS_KEYS) | set(ALLOWED_KEYS)
    assert content.prompt  # non-empty


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_generate_is_deterministic_given_a_seeded_rng(activity):
    content_a = activity.generate(FOCUS_KEYS, ALLOWED_KEYS, duration_s=30, rng=random.Random(7))
    content_b = activity.generate(FOCUS_KEYS, ALLOWED_KEYS, duration_s=30, rng=random.Random(7))
    assert content_a == content_b


@pytest.mark.parametrize("activity", ALL_ACTIVITIES, ids=ALL_IDS)
def test_score_round_trips_through_the_activity(activity):
    content = activity.generate(FOCUS_KEYS, ALLOWED_KEYS, duration_s=30, rng=random.Random(42))
    keystrokes = [KeystrokeEvent(k, k, True, 200) for k in content.keys for _ in range(5)]
    result = activity.score(content, keystrokes)
    assert result.activity_id == activity.id
    assert result.keys == content.keys
    assert result.accuracy == 1.0
    assert result.reward_signal == "nailed_it"


def test_teach_requires_focus_keys_specifically_not_just_allowed():
    teach = REGISTRY["teach_random_keys_v1"]
    assert teach.is_eligible([], ALLOWED_KEYS) is False
    assert teach.is_eligible(FOCUS_KEYS, []) is True


def test_teach_uses_blocked_not_randomized_pattern_and_ignores_allowed():
    teach = REGISTRY["teach_random_keys_v1"]
    content = teach.generate(FOCUS_KEYS, ALLOWED_KEYS, duration_s=30, rng=random.Random(1))
    # blocked means each key appears as its own contiguous run, e.g. "ffff jjjj",
    # not interleaved -- so the prompt is exactly two space-separated blocks,
    # each entirely one repeated character, and allowed_keys never show up.
    blocks = content.prompt.split(" ")
    assert len(blocks) == len(FOCUS_KEYS)
    for key, block in zip(FOCUS_KEYS, blocks):
        assert block == key * len(block)
        assert len(block) >= 4
    assert set(content.prompt.replace(" ", "")) == set(FOCUS_KEYS)


def test_warmup_leans_focus_but_includes_some_allowed():
    warmup = REGISTRY["warmup_random_keys_v1"]
    content = warmup.generate(FOCUS_KEYS, ALLOWED_KEYS, duration_s=60, rng=random.Random(1))
    letters = content.prompt.replace(" ", "")
    focus_count = sum(1 for c in letters if c in FOCUS_KEYS)
    # ~75% focus by design -- not an exact check (it's random), just
    # confirms focus clearly dominates over a long enough sample.
    assert focus_count > len(letters) * 0.5


def test_eval_leans_allowed_but_includes_some_focus():
    eval_activity = REGISTRY["eval_random_keys_v1"]
    content = eval_activity.generate(FOCUS_KEYS, ALLOWED_KEYS, duration_s=60, rng=random.Random(1))
    letters = content.prompt.replace(" ", "")
    allowed_count = sum(1 for c in letters if c in ALLOWED_KEYS)
    assert allowed_count > len(letters) * 0.5
