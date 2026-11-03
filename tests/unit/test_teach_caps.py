"""Unit tests for the capital-letter teach modules and the Shift rule
(always the other hand's Shift).
"""

from __future__ import annotations

import random

import pytest

from app.activities.teach_caps import TeachCapsGroup, TeachCapsIntro, capital_words
from app.activities.teach_curriculum import CAPS_GROUPS, CAPS_ID, CAPS_INTRO_ID, lessons
from app.activities.teach_steps import is_capital, shift_focus, shift_for, show_step, type_step


@pytest.mark.parametrize(
    "letter,shift",
    [("a", ("shift_r", "right_pinky")), ("t", ("shift_r", "right_pinky")), ("j", ("shift_l", "left_pinky")),
     ("y", ("shift_l", "left_pinky"))],
)
def test_shift_is_always_the_other_hand(letter, shift):
    assert shift_for(letter) == shift


def test_shift_focus_reaches_the_pinky_and_any_off_home_finger():
    assert shift_focus("f") == {"fingers": ["left_index", "right_pinky"], "keys": ["shift_r", "f"], "reach": {"right_pinky": "shift_r"}}
    assert shift_focus("u")["reach"] == {"left_pinky": "shift_l", "right_index": "u"}


def test_capitals_are_typeable_in_steps():
    assert is_capital("J") and not is_capital("j") and not is_capital(":")
    assert show_step("t", "x", advance_key="J")["keys"] == ["j"]
    assert type_step("t", "x", "Dad Sal")["prompt"] == "Dad Sal"


def test_caps_groups_cover_the_alphabet_and_use_one_shift_each():
    assert sorted("".join(CAPS_GROUPS)) == list("abcdefghijklmnopqrstuvwxyz")
    for group in CAPS_GROUPS:
        assert len({shift_for(k)[0] for k in group}) == 1
        assert TeachCapsGroup().is_eligible(list(group), [])


def test_curriculum_puts_capitals_last():
    titles = [l["title"] for l in lessons()]
    assert titles.index("B and N") < titles.index("1 and 2") < titles.index("9 and 0") < titles.index("Big letters") < titles.index("A S D F")
    caps = [l for l in lessons() if l["group"] == "Capitals"]
    assert caps[0]["module"] == CAPS_INTRO_ID
    assert all(l["module"] == CAPS_ID for l in caps[1:])


def test_caps_intro_teaches_both_shifts():
    steps = TeachCapsIntro().generate([], [], 60).micro_steps
    advance = [s["advance_key"] for s in steps if s["kind"] == "show"]
    assert "J" in advance and "F" in advance
    big_j = next(s for s in steps if s.get("advance_key") == "J")
    assert big_j["reach"] == {"left_pinky": "shift_l"}


@pytest.mark.parametrize("group", CAPS_GROUPS)
def test_every_caps_group_builds(group):
    steps = TeachCapsGroup().generate(list(group), [], 60, rng=random.Random(0)).micro_steps
    for letter in group:
        assert any(s.get("advance_key") == letter.upper() for s in steps)
    typed = "".join(s["prompt"] for s in steps if s["kind"] == "type")
    assert {c for c in typed if c.isupper()} <= set(group.upper())
    assert steps[-1]["advance_key"] == " "


@pytest.mark.parametrize("keys", [[], list("asdfg" + "q"), ["a", "j"], ["A"], ["1"], ["a", "a"]])
def test_caps_group_rejects_bad_sets(keys):
    assert not TeachCapsGroup().is_eligible(keys, [])


def test_capital_words_start_with_the_group():
    words = capital_words(list("qwer"), 4, random.Random(0))
    assert words and all(w[0] in "QWER" and w[1:].islower() for w in words)
