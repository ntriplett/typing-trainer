"""Unit tests for the key-pair teach module, its shared lesson pieces,
the word bank, and the teach curriculum.
"""

from __future__ import annotations

import random

import pytest

from app.activities.teach_curriculum import PAIR_ID, known_before, lessons
from app.activities.teach_key_pair import TeachKeyPair
from app.activities.teach_steps import home_key, meet_key_steps, mix_prompt, reach_phrase, take_turns_prompt
from app.activities.word_bank import WORDS, words_for
from app.finger_map import KEY_TO_FINGER
from app.skill_model import KEY_ORDER

PAIRS = [list(l["keys"]) for l in lessons() if l["module"] == PAIR_ID]


def pair_steps(keys: list[str], seed: int = 0) -> list[dict]:
    return TeachKeyPair().generate(keys, known_before(keys), 120, rng=random.Random(seed)).micro_steps


# --- shared pieces ----------------------------------------------------------------


@pytest.mark.parametrize(
    "key,phrase",
    [
        ("r", "reaches up"),
        ("t", "reaches up and to the right"),
        ("y", "reaches up and to the left"),
        ("g", "stretches over to the right"),
        ("h", "stretches over to the left"),
        ("m", "reaches down"),
        ("b", "reaches down and to the right"),
        ("5", "reaches way up"),
        ("1", "reaches way up and to the left"),
    ],
)
def test_reach_phrase(key, phrase):
    assert reach_phrase(key) == phrase


def test_home_key_meet_steps_are_a_page_and_a_drill():
    steps = meet_key_steps("d")
    assert [s["kind"] for s in steps] == ["show", "type"]
    assert steps[0]["advance_key"] == "d" and not steps[0]["reach"]
    assert set(steps[1]["prompt"]) == {"d", " "}


def test_reach_key_meet_steps_reach_go_home_then_drill_the_reach():
    steps = meet_key_steps("r")
    assert [s["kind"] for s in steps] == ["show", "show", "type"]
    assert steps[0]["reach"] == {"left_index": "r"}
    assert steps[1]["advance_key"] == "f"
    assert steps[2]["prompt"].startswith("fr fr")


def test_take_turns_uses_only_the_pair():
    assert set(take_turns_prompt("e", "i")) == {"e", "i", " "}


def test_mix_prompt_uses_new_and_known_keys_only():
    prompt = mix_prompt(["e", "i"], ["f", "j", " "], random.Random(1), groups=20)
    assert set(prompt) <= {"e", "i", "f", "j", " "}
    assert {"e", "i"} & set(prompt) and {"f", "j"} & set(prompt)


def test_words_for_only_spells_with_taught_keys_and_uses_a_new_key():
    words = words_for(["g", "h"], list("fjdksla;"), 10, random.Random(0))
    assert words
    for w in words:
        assert set(w) <= set("fjdksla;gh") and set(w) & {"g", "h"}


def test_word_bank_is_lowercase_letters():
    assert all(w.isalpha() and w.islower() for w in WORDS)


# --- curriculum ---------------------------------------------------------------------


def test_curriculum_starts_with_the_intro_then_pairs_in_key_order():
    all_lessons = lessons()
    assert all_lessons[0]["module"] == "teach_intro_home_row_v1"
    taught = "".join(l["keys"] for l in all_lessons[1:])
    assert taught == "".join(k for k in KEY_ORDER if k != " ")
    assert all(len(p) == 2 for p in PAIRS)


def test_known_before_is_everything_earlier():
    assert known_before(["f", "j"]) == [" "]
    assert known_before(["e", "i"]) == [" ", *"fjdksla;ghru"]


# --- the module ---------------------------------------------------------------------


@pytest.mark.parametrize("keys", PAIRS, ids=["".join(p) for p in PAIRS])
def test_every_lesson_builds_and_only_uses_taught_keys(keys):
    steps = pair_steps(keys)
    allowed = set(known_before(keys)) | set(keys)
    for step in steps:
        assert set(step["prompt"]) <= allowed
        if step["kind"] == "show":
            assert step["advance_key"] in allowed | {home_key(k) for k in keys}
    assert steps[0]["advance_key"] == steps[-1]["advance_key"] == " "
    # each new key gets its own "Meet" page that lights the right finger
    for key in keys:
        meet = next(s for s in steps if s["kind"] == "show" and s["advance_key"] == key)
        assert KEY_TO_FINGER[key] in meet["fingers"]


def test_one_key_lesson_skips_take_turns():
    titles = [s["title"] for s in pair_steps(["g"])]
    assert "Take turns" not in titles
    assert titles[0] == "A new key!"


def test_real_words_page_appears_once_letters_allow():
    assert "Real words!" not in [s["title"] for s in pair_steps(["f", "j"])]
    assert "Real words!" in [s["title"] for s in pair_steps(["e", "i"])]


@pytest.mark.parametrize("keys", [[], ["a", "b", "c"], ["f", "f"], [" "], ["€"]])
def test_rejects_bad_key_sets(keys):
    assert not TeachKeyPair().is_eligible(keys, [])
    with pytest.raises(ValueError):
        TeachKeyPair().generate(keys, [], 60)
