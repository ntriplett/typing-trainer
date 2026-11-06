"""The three milestones each key pays for, once each (app/lessons.py)."""

import pytest

from app import lessons as ls
from app.brain import MIN_RECENT_ATTEMPTS, KeyRecord
from app.models import KeyStat
from app.skill_model import MIN_SAMPLES_FOR_MASTERY

BAR = 0.9


def stat(ms, accuracy=0.97, samples=MIN_SAMPLES_FOR_MASTERY, key="f"):
    return KeyStat(learner_id=1, key=key, ema_time_ms=ms, confidence=400 / ms, accuracy_rolling=accuracy,
                   sample_count=samples, unlocked_at=None, mastered_at=None)


def good(attempts=MIN_RECENT_ATTEMPTS, right=None):
    return KeyRecord(attempts, attempts if right is None else right, 0, 0)


def reasons(**kw):
    args = {"keys": ["f"], "stats": {}, "records": {}, "bar": BAR, "paid": set(), "practiced": PRACTICED, **kw}
    return [r for _, r, _ in ls.key_bonuses(**args)]


PRACTICED = {k: ls.PRACTICE_LESSONS_FOR_BONUS for k in "fF "}
TYPED = KeyRecord(MIN_SAMPLES_FOR_MASTERY, 0, 0, 0)  # enough real tries, too few for solid


def test_solid_is_the_next_lesson_check():
    assert reasons(records={"f": good()}) == [ls.KEY_SOLID]
    assert reasons(records={"f": good(right=MIN_RECENT_ATTEMPTS - 10)}) == []  # below the bar
    assert reasons(records={"f": good(attempts=MIN_RECENT_ATTEMPTS - 1)}) == []  # not enough tries


def test_the_speed_milestones_pay_at_their_speeds():
    assert reasons(stats={"f": stat(1000)}, records={"f": TYPED}) == []
    assert reasons(stats={"f": stat(700)}, records={"f": TYPED}) == [ls.KEY_HALFWAY]
    assert reasons(stats={"f": stat(350)}, records={"f": TYPED}) == [ls.KEY_HALFWAY, ls.KEY_MASTERED]


def test_speed_needs_accuracy():
    assert reasons(stats={"f": stat(700, accuracy=0.8)}, records={"f": TYPED}) == []


def test_each_pays_once():
    paid = {(ls.KEY_SOLID, "f"), (ls.KEY_HALFWAY, "f")}
    assert reasons(stats={"f": stat(700)}, records={"f": good()}, paid=paid) == []


def test_a_placement_guess_pays_nothing_until_its_really_typed():
    # placement fills in a speed and a sample count, but no real tries
    assert reasons(stats={"f": stat(350)}, records={}) == []
    assert reasons(stats={"f": stat(350)}, records={"f": KeyRecord(MIN_SAMPLES_FOR_MASTERY - 1, 0, 0, 0)}) == []
    assert reasons(stats={"f": stat(350)}, records={"f": TYPED}) == [ls.KEY_HALFWAY, ls.KEY_MASTERED]


def test_only_real_keys_count():
    assert reasons(keys=["F"], records={"F": good()}) == []
    assert reasons(keys=[" "], records={" ": good()}) == [ls.KEY_SOLID]


def test_each_is_worth_five_hundred():
    assert ls.key_bonuses(["f"], {}, {"f": good()}, BAR, set(), PRACTICED) == [(500, ls.KEY_SOLID, "f")]


def test_nothing_pays_until_the_key_is_in_enough_practice_lessons():
    for n in range(ls.PRACTICE_LESSONS_FOR_BONUS):
        assert reasons(stats={"f": stat(350)}, records={"f": good()}, practiced={"f": n}) == []
    assert reasons(stats={"f": stat(350)}, records={"f": good()}) == [ls.KEY_SOLID, ls.KEY_HALFWAY, ls.KEY_MASTERED]
