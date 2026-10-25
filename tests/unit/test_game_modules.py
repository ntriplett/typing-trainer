"""Unit tests for the game modules' content (app/activities/game_modules.py)."""

import random

import pytest

from app.activities.game_modules import (
    CROW_PATROL,
    GAME_MODULES,
    MAX_ROUND_SCORE,
    PET_BATTLE,
    WORD_LENGTHS,
    scale_level,
    word_groups,
)
from app.activities.word_bank import WORDS
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
    words = content.game["words"]["medium"]
    pool = [w for w in WORDS if 4 <= len(w) <= 5 and set(w) <= set("asdfghjkl")]
    share = lambda ws: sum(bool(set(w) & {"d", "k"}) for w in ws) / len(ws)
    assert share(words) > share(pool) + 0.1


def test_weak_pairs_show_up_more_when_hard():
    skill = SkillSnapshot(weak_keys=("g", "h"), weak_bigrams=("gh",))
    rng = random.Random(3)

    def gh_count(difficulty):
        groups = word_groups([], HOME, difficulty, skill, rng)
        return sum(w.count("gh") for w in groups["long"])  # long home-row words are made up

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


def test_coins_are_by_points_and_capped():
    assert CROW_PATROL.coins_for(400) == 20
    assert PET_BATTLE.coins_for(0) == 0
    assert PET_BATTLE.coins_for(-3) == 0
    assert CROW_PATROL.coins_for(10**9) == CROW_PATROL.coins_for(MAX_ROUND_SCORE)


def test_real_words_once_the_letters_spell_enough():
    rng = random.Random(4)
    groups = word_groups([], list(" asdfghjklrueitywqop"), 0.5, None, rng)
    assert all(w in WORDS for name in ("short", "medium", "long") for w in groups[name])
    # home row spells plenty of short words, but hardly any long ones
    home = word_groups([], HOME, 0.5, None, rng)
    assert all(w in WORDS for w in home["short"])
    assert any(w not in WORDS for w in home["long"])


def test_real_words_favor_focus_letters():
    groups = word_groups(["e"], list(" asdfghjklrueitywqop"), 0.5, None, random.Random(5))
    with_e = sum("e" in w for w in groups["medium"])
    assert with_e > len(groups["medium"]) * 0.5


def test_crow_rounds_add_a_new_kind_each_round():
    kinds = [set(level["types"]) for level in CROW_PATROL.levels]
    assert all(a < b for a, b in zip(kinds, kinds[1:]))
    assert all(level["new"] in level["types"] for level in CROW_PATROL.levels)
