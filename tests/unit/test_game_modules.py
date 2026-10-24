"""Unit tests for the game modules' content (app/activities/game_modules.py)."""

import random

import pytest

from app.activities.game_modules import (
    CROW_PATROL,
    GAME_MODULES,
    PET_BATTLE,
    WORD_LENGTHS,
    scale_level,
    word_groups,
)
from app.activities.practice_text import SkillSnapshot

HOME = list(" asdfghjkl")


@pytest.mark.parametrize("module", GAME_MODULES, ids=lambda m: m.id)
def test_generate_gives_levels_and_word_groups_in_allowed_letters(module):
    content = module.generate([], HOME, rng=random.Random(1))
    game = content.game
    assert content.kind == "game" and content.title == module.title
    assert game["game"] == module.game
    assert len(game["levels"]) == 5
    for name, (lo, hi) in WORD_LENGTHS.items():
        words = game["words"][name]
        assert len(words) >= 50
        assert all(lo <= len(w) <= hi and set(w) <= set("asdfghjkl") for w in words)
    # enough different first letters to keep on-screen words apart
    assert len({w[0] for w in game["words"]["short"]}) >= 4


def test_focus_letters_are_called_out_and_common():
    content = CROW_PATROL.generate(["d", "k"], HOME, rng=random.Random(2))
    assert "[d] and [k]" in content.instructions
    letters = "".join(content.game["words"]["medium"])
    assert letters.count("d") > letters.count("s")


def test_weak_pairs_show_up_more_when_hard():
    skill = SkillSnapshot(weak_keys=("g", "h"), weak_bigrams=("gh",))
    rng = random.Random(3)

    def gh_count(difficulty):
        groups = word_groups([], HOME, difficulty, skill, rng)
        return sum(w.count("gh") for w in groups["long"])

    assert gh_count(0.9) > gh_count(0.1)


def test_needs_four_letters():
    assert not PET_BATTLE.is_eligible([], [" ", "f", "j"])
    assert PET_BATTLE.is_eligible([], [" ", "f", "j", "d", "k"])
    assert not PET_BATTLE.is_eligible([], [])


def test_difficulty_scales_speed_and_foe_hp():
    assert scale_level({"speed": 1.0}, 0.0)["speed"] == 0.8
    assert scale_level({"speed": 1.0}, 1.0)["speed"] == 1.2
    assert scale_level({"foe_hp": 10}, 1.0)["foe_hp"] == 12
    assert scale_level({"foe_hp": 3}, 0.0)["foe_hp"] == 3  # never below 3
    assert scale_level({"name": "x"}, 1.0) == {"name": "x"}


def test_coins_are_per_success():
    assert CROW_PATROL.coins_for(10) == 10 * CROW_PATROL.coins_per_success
    assert PET_BATTLE.coins_for(0) == 0
    assert PET_BATTLE.coins_for(-3) == 0
