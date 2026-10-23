"""Unit tests for the finger/key reference data -- previously only
exercised indirectly through analytics/recommender tests; now also
load-bearing for the teach-demo modules (micro_lesson.py), so it gets
its own direct coverage.
"""

from app import finger_map as fm
from app.skill_model import KEY_ORDER


def test_every_key_in_key_order_has_a_finger_assignment():
    for key in KEY_ORDER:
        assert fm.finger_for_key(key) in fm.ALL_FINGERS


def test_finger_for_key_returns_none_for_unknown_key():
    assert fm.finger_for_key("not-a-key") is None


def test_home_key_for_finger_covers_every_finger():
    assert set(fm.HOME_KEY_FOR_FINGER.keys()) == set(fm.ALL_FINGERS)


def test_home_key_for_finger_round_trips_through_key_to_finger():
    # Every home key should map back to the finger it's listed under --
    # this is what keeps HOME_KEY_FOR_FINGER from drifting out of sync
    # with KEY_TO_FINGER, since it's derived rather than hand-maintained.
    for finger, home_key in fm.HOME_KEY_FOR_FINGER.items():
        assert fm.KEY_TO_FINGER[home_key] == finger


def test_home_row_keys_are_exactly_the_home_key_for_finger_values():
    # plus the space bar, where the thumbs rest
    assert set(fm.HOME_ROW_KEYS) | {" "} == set(fm.HOME_KEY_FOR_FINGER.values())
