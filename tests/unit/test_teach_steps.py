"""Unit tests for the keyboard-driven teach step builders and the intro
(home row + space) module built from them.
"""

from __future__ import annotations

import random

import pytest

from app.activities.base import KeystrokeEvent
from app.activities.teach_intro_home_row import HOME_ROW_PHRASES, TeachIntroHomeRow
from app.activities.teach_modules import TEACH_REGISTRY, get_teach_module, list_teach_modules
from app.activities.teach_steps import keys_in_steps, show_step, type_step
from app.finger_map import HOME_ROW_KEYS, KEY_TO_FINGER

# --- builders -----------------------------------------------------------------


def test_show_step_lights_the_advance_keys_own_finger():
    step = show_step("t", "x", advance_key="j")
    assert step["kind"] == "show"
    assert step["fingers"] == ["right_index"]
    assert step["keys"] == ["j"]
    assert step["prompt"] == ""


def test_show_step_space_accepts_either_named_thumb_without_adding_generic_thumb():
    step = show_step("t", "x", advance_key=" ", fingers=["left_thumb", "right_thumb"])
    assert step["fingers"] == ["left_thumb", "right_thumb"]


def test_show_step_keeps_extra_fingers_and_reach():
    step = show_step("t", "x", advance_key="r", fingers=["left_index"], reach={"left_index": "r"})
    assert step["reach"] == {"left_index": "r"}
    assert step["fingers"] == ["left_index"]


def test_show_step_can_light_shift_for_capitals_later():
    step = show_step("t", "x", advance_key="j", keys=["shift_l", "j"], fingers=["left_pinky"])
    assert step["keys"] == ["shift_l", "j"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"advance_key": "é"},
        {"advance_key": "f", "keys": ["nope"]},
        {"advance_key": "f", "fingers": ["left_toe"]},
        {"advance_key": "f", "reach": {"left_index": "nope"}},
    ],
)
def test_show_step_rejects_unknown_keys_and_fingers(kwargs):
    with pytest.raises(ValueError):
        show_step("t", "x", **kwargs)


def test_type_step_needs_a_known_prompt():
    assert type_step("t", "x", "f j")["prompt"] == "f j"
    with pytest.raises(ValueError):
        type_step("t", "x", "")
    with pytest.raises(ValueError):
        type_step("t", "x", "f€")


def test_keys_in_steps_collects_advance_keys_and_prompt_keys():
    steps = [show_step("t", "x", advance_key=" "), type_step("t", "x", "fj")]
    assert keys_in_steps(steps) == [" ", "f", "j"]


# --- the intro module -----------------------------------------------------------


def intro_steps(seed: int = 0) -> list[dict]:
    return TeachIntroHomeRow().generate([], [], 120, rng=random.Random(seed)).micro_steps


def test_intro_only_uses_home_row_and_space():
    allowed = set(HOME_ROW_KEYS) | {" "}
    for step in intro_steps():
        assert set(step["prompt"]) <= allowed
        if step["kind"] == "show":
            assert step["advance_key"] in allowed


def test_intro_starts_and_ends_on_a_space_press():
    steps = intro_steps()
    assert steps[0]["kind"] == steps[-1]["kind"] == "show"
    assert steps[0]["advance_key"] == steps[-1]["advance_key"] == " "


def test_intro_every_show_step_lights_the_finger_it_asks_for():
    for step in intro_steps():
        if step["kind"] != "show":
            continue
        finger = KEY_TO_FINGER[step["advance_key"]]
        if finger == "thumb":
            assert {"left_thumb", "right_thumb"} & set(step["fingers"]) or "thumb" in step["fingers"]
        else:
            assert finger in step["fingers"]


def test_intro_has_typing_practice_and_real_words():
    steps = intro_steps()
    assert sum(s["kind"] == "type" for s in steps) >= 4
    last_typed = [s for s in steps if s["kind"] == "type"][-1]["prompt"]
    assert any(phrase in last_typed for phrase in HOME_ROW_PHRASES)


def test_intro_is_deterministic_for_a_seed():
    assert intro_steps(3) == intro_steps(3)


def test_intro_content_keys_and_scoring():
    activity = TeachIntroHomeRow()
    content = activity.generate([], [], 120, rng=random.Random(0))
    assert content.keys == sorted(set(HOME_ROW_KEYS) | {" "})
    assert activity.is_eligible([], [])
    strokes = [KeystrokeEvent("f", "f", True, 200), KeystrokeEvent("j", "k", False, 200)]
    result = activity.score(content, strokes)
    assert result.accuracy == 0.5


def test_teach_registry_lists_the_intro():
    assert "teach_intro_home_row_v1" in TEACH_REGISTRY
    assert get_teach_module("teach_intro_home_row_v1").kind == "teach"
    assert list_teach_modules()[0]["title"] == "Hands on home"


def test_teach_modules_are_not_in_the_live_scheduler_registry():
    from app.activities import REGISTRY

    assert not set(TEACH_REGISTRY) & set(REGISTRY)
