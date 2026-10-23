"""Unit tests for the coin rule (PLAN.md Section 11c): every activity
pays round(accuracy * 100 * fraction_of_prompt_completed).
"""

import pytest

from app.activities import REGISTRY
from app.activities.base import ActivityContent, ActivityResult, default_coins


def _content(prompt: str) -> ActivityContent:
    return ActivityContent(activity_id="x", kind="practice", keys=["f"], prompt=prompt)


def _result(attempts: int, correct: int) -> ActivityResult:
    return ActivityResult(
        activity_id="x",
        keys=["f"],
        attempts=attempts,
        correct=correct,
        accuracy=correct / attempts if attempts else 0.0,
        wpm=10.0,
        avg_latency_ms=200.0,
        reward_signal="solid",
    )


def test_finished_step_pays_accuracy_percent():
    # 20-char prompt fully typed at 85% accuracy -> 85 coins
    assert default_coins(_content("f" * 20), _result(attempts=20, correct=17)) == 85


def test_perfect_finished_step_pays_100():
    assert default_coins(_content("ffff jjjj"), _result(attempts=9, correct=9)) == 100


def test_ending_early_pays_proportionally():
    # half the prompt at 100% -> 50, not 100
    assert default_coins(_content("f" * 20), _result(attempts=10, correct=10)) == 50


def test_nothing_typed_pays_nothing():
    assert default_coins(_content("f" * 20), _result(attempts=0, correct=0)) == 0


def test_completion_is_capped_at_one():
    assert default_coins(_content("f" * 10), _result(attempts=12, correct=12)) == 100


def test_empty_prompt_counts_as_complete():
    # micro-step lessons may carry no flat prompt
    assert default_coins(_content(""), _result(attempts=10, correct=9)) == 90


@pytest.mark.parametrize("activity", REGISTRY.values(), ids=lambda a: a.id)
def test_every_registered_activity_has_a_coin_rule(activity):
    paid = activity.coins(_content("f" * 20), _result(attempts=20, correct=19))
    assert isinstance(paid, int)
    assert 0 <= paid <= 100
