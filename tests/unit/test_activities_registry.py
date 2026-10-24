"""Tests for the activity registry itself (PLAN.md Section 7): the
scheduler will only ever go through get_activity()/activities_by_kind(),
so this is the seam that matters for "adding an activity is one line."
"""

import pytest

from app.activities import activities_by_kind, get_activity
from app.activities.base import Activity


def test_get_activity_returns_the_right_module():
    activity = get_activity("teach_random_keys_v1")
    assert activity.id == "teach_random_keys_v1"
    assert activity.kind == "teach"


def test_get_activity_raises_for_unknown_id():
    with pytest.raises(KeyError):
        get_activity("does_not_exist")


@pytest.mark.parametrize("kind", ["teach", "game"])
def test_exactly_one_v1_activity_per_kind(kind):
    matches = activities_by_kind(kind)
    assert len(matches) == 1
    assert matches[0].kind == kind


def test_practice_has_the_plain_module_plus_ten_themes():
    practice = activities_by_kind("practice")
    assert len(practice) == 11
    assert sum(1 for a in practice if a.scene) == 10


def test_no_eval_or_separate_warmup_modules():
    assert activities_by_kind("eval") == []
    assert activities_by_kind("warmup") == []


def test_every_registered_activity_satisfies_the_protocol():
    from app.activities import REGISTRY

    for activity in REGISTRY.values():
        assert isinstance(activity, Activity)
