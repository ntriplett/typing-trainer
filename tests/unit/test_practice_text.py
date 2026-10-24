"""Unit tests for practice text: focus weighting, allowed-only letters,
length, difficulty (weak letters/pairs in a row), and the weak-spot snapshot.
"""

from __future__ import annotations

import random
from collections import Counter
from datetime import UTC, datetime

import pytest

from app.activities.practice_modules import PRACTICE_MODULES
from app.activities.practice_text import (
    SkillSnapshot,
    build_practice_text,
    focus_callout,
    max_weak_run,
    snapshot_from_stats,
)
from app.models import BigramStat, KeyStat

FOCUS = ["e", "i"]
ALLOWED = list("asdfjkl") + [" "]
NOW = datetime(2026, 10, 24, tzinfo=UTC)


def letters(text: str) -> Counter:
    return Counter(text.replace(" ", ""))


def test_focus_letters_come_up_about_three_times_as_often():
    text = build_practice_text(FOCUS, ALLOWED, 6000, difficulty=0.0, rng=random.Random(1), real_word_share=0)
    counts = letters(text)
    focus_avg = sum(counts[k] for k in FOCUS) / len(FOCUS)
    other_avg = sum(counts[k] for k in "asdfjkl") / 7
    assert 2.5 < focus_avg / other_avg < 3.5


def test_only_taught_letters_appear():
    for seed in range(5):
        text = build_practice_text(FOCUS, ALLOWED, 300, rng=random.Random(seed))
        assert set(text) <= set(ALLOWED) | set(FOCUS)


def test_length_is_about_what_was_asked():
    text = build_practice_text(FOCUS, ALLOWED, 200, rng=random.Random(2))
    assert 200 <= len(text) <= 215
    assert not text.startswith(" ") and not text.endswith(" ")


def test_no_triple_letters():
    text = build_practice_text(["f"], ["f", "j"], 500, rng=random.Random(3), real_word_share=0)
    assert "fff" not in text and "jjj" not in text


def test_max_weak_run_grows_with_difficulty():
    assert max_weak_run(0.0) == 1
    assert max_weak_run(0.5) == 3
    assert max_weak_run(1.0) == 5


def _longest_weak_run(text: str, weak: set[str]) -> int:
    best = run = 0
    for ch in text:
        run = run + 1 if ch in weak else 0
        best = max(best, run)
    return best


def test_easy_never_puts_two_weak_letters_together():
    skill = SkillSnapshot(weak_keys=("d", "k"))
    text = build_practice_text([], ALLOWED, 2000, difficulty=0.0, skill=skill, rng=random.Random(4), real_word_share=0)
    assert _longest_weak_run(text, {"d", "k"}) == 1


def test_hard_strings_weak_letters_and_pairs_together():
    skill = SkillSnapshot(weak_keys=("d", "k"), weak_bigrams=("dk", "kd", "ds"))
    easy = build_practice_text([], ALLOWED, 2000, difficulty=0.0, skill=skill, rng=random.Random(5))
    hard = build_practice_text([], ALLOWED, 2000, difficulty=1.0, skill=skill, rng=random.Random(5))
    assert hard.count("dk") + hard.count("kd") > 3 * (easy.count("dk") + easy.count("kd") + 1)
    assert _longest_weak_run(hard, {"d", "k"}) >= 3


def test_weak_pairs_outside_taught_letters_are_ignored():
    skill = SkillSnapshot(weak_bigrams=("qz",))
    text = build_practice_text([], ALLOWED, 500, difficulty=1.0, skill=skill, rng=random.Random(6))
    assert "q" not in text


def test_snapshot_picks_weak_keys_and_pairs_with_enough_samples():
    def key(k, acc, n):
        return KeyStat(1, k, 300.0, 1.0, acc, n, NOW, None)

    def pair(a, b, acc, n):
        return BigramStat(1, a, b, 300.0, acc, n)

    snap = snapshot_from_stats(
        {"d": key("d", 0.6, 20), "k": key("k", 0.8, 20), "f": key("f", 0.99, 20), "s": key("s", 0.1, 2)},
        [pair("d", "k", 0.5, 10), pair("f", "j", 0.99, 10), pair("d", " ", 0.1, 10)],
    )
    assert snap.weak_keys == ("d", "k")
    assert snap.weak_bigrams == ("dk",)


def test_focus_callout():
    assert focus_callout([]) == ""
    assert focus_callout(["e"]) == "Focus letter: [e]."
    assert focus_callout(["e", "i", " "]) == "Focus letters: [e] and [i]."
    assert focus_callout(["a", "b", "c"]) == "Focus letters: [a], [b] and [c]."


@pytest.mark.parametrize("module", PRACTICE_MODULES, ids=[m.id for m in PRACTICE_MODULES])
def test_every_practice_module_builds_with_its_theme(module):
    content = module.generate(FOCUS, ALLOWED, 60, rng=random.Random(7), difficulty=0.7)
    assert content.title and content.prompt
    assert content.scene == module.scene
    assert "Focus letters" in content.instructions
    assert set(content.prompt) <= set(ALLOWED) | set(FOCUS)
