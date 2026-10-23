"""Unit tests for the shared micro-lesson builders (diagram, anchor
check, isolated drill, reach-return drill, combo) used by the 3
teach-demo variants.
"""

import random

import pytest

from app.activities import micro_lesson as ml


def test_home_key_for_matches_finger_map_home_row():
    assert ml.home_key_for("f") == "f"  # home key itself
    assert ml.home_key_for("r") == "f"  # left index reach
    assert ml.home_key_for("j") == "j"
    assert ml.home_key_for("u") == "j"  # right index reach


def test_finger_for_key_raises_for_unknown_key():
    with pytest.raises(ValueError):
        ml.finger_for_key("not-a-key")


def test_build_diagram_step_on_a_home_row_key():
    step = ml.build_diagram_step("f")
    assert step["kind"] == "diagram"
    assert step["highlight_key"] == "f"
    assert step["prompt"] == ""
    assert "home key" in step["instructions"]


def test_build_diagram_step_on_a_reach_key_mentions_the_home_key():
    step = ml.build_diagram_step("r")
    assert step["highlight_key"] == "r"
    assert step["home_key"] == "f"
    assert "F" in step["instructions"]
    assert "R" in step["instructions"]


def test_build_anchor_check_step_types_the_home_row_in_order():
    step = ml.build_anchor_check_step(random.Random(1))
    assert step["kind"] == "anchor_check"
    assert step["prompt"] == "a s d f j k l ;"


def test_build_isolated_drill_step_only_contains_the_target_key():
    step = ml.build_isolated_drill_step("r", repeats=8)
    assert step["kind"] == "drill"
    assert set(step["prompt"].replace(" ", "")) == {"r"}
    assert len(step["prompt"].replace(" ", "")) >= 8


def test_build_reach_return_drill_alternates_new_key_and_home_key():
    step = ml.build_reach_return_drill_step("r", repeats=6)
    assert step["kind"] == "drill"
    assert step["home_key"] == "f"
    letters = set(step["prompt"].replace(" ", ""))
    assert letters == {"f", "r"}


def test_build_combo_step_mixes_new_key_with_combo_keys():
    step = ml.build_combo_step("r", ["f", "j"], duration_chars=30, rng=random.Random(1))
    assert step["kind"] == "combo"
    letters = set(step["prompt"].replace(" ", ""))
    assert letters <= {"r", "f", "j"}
    assert "r" in letters  # the new key should actually show up at that length


def test_build_combo_step_is_deterministic_given_a_seeded_rng():
    a = ml.build_combo_step("r", ["f", "j"], duration_chars=20, rng=random.Random(5))
    b = ml.build_combo_step("r", ["f", "j"], duration_chars=20, rng=random.Random(5))
    assert a == b
