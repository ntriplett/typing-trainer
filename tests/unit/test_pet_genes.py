"""Unit tests for pet genes (app/pet_genes.py): deterministic rolls, coat
shares, the color pool and unlock rules, and the hook for future stats."""

import collections

import pytest

from app import pet_genes as g


def test_the_color_pool_is_90_with_about_45_per_species():
    assert len(g.COLORS) == 90
    for species, starters in g.STARTER_COLORS.items():
        eligible = g.eligible_colors(species)
        assert 40 <= len(eligible) <= 55, species
        assert set(starters) <= set(eligible)


def test_the_same_seed_rolls_the_same_pet():
    assert g.roll("cat", "orange", "ash", 42) == g.roll("cat", "orange", "ash", 42)
    assert g.roll("cat", "orange", "ash", 42) != g.roll("cat", "orange", "ash", 43)


@pytest.mark.parametrize("seed", range(200))
def test_coat_shares_follow_the_rules(seed):
    coat = g.roll("dog", "golden", "chestnut", seed)["coat"]
    primary, secondary, third = coat["shares"]
    assert 0.5 <= primary <= 0.9
    assert abs(primary + secondary + third - 1) < 0.01
    assert secondary <= 0.5 + g.MIN_THIRD_SHARE
    assert (third == 0) == (coat["colors"][2] is None)
    assert coat["colors"][:2] == ["golden", "chestnut"]
    assert coat["colors"][2] not in ("golden", "chestnut")


def test_colors_must_be_unlocked_and_different():
    with pytest.raises(g.GeneError, match="unlocked"):
        g.roll("cat", "orange", "lilac", 1)
    with pytest.raises(g.GeneError, match="different"):
        g.roll("cat", "orange", "orange", 1)
    with pytest.raises(g.GeneError):
        g.roll("dragon", "orange", "ash", 1)
    assert g.roll("cat", "orange", "lilac", 1, unlocked={"orange", "lilac"})


def test_third_colors_lean_natural_and_near_what_is_unlocked():
    weights = g.third_color_weights("cat", {"orange", "ash", "black"}, {"orange", "ash"})
    assert weights["ginger"] > weights["snow"]  # near orange
    assert weights["pink"] < weights["chestnut"]  # rare family
    # unlocking a red-ish color makes pinks likelier
    nearer = g.third_color_weights("cat", {"orange", "ash", "black", "salmon"}, {"orange", "ash"})
    assert nearer["blush"] > weights["blush"]
    assert all(w > 0 for w in weights.values())  # nothing impossible


def test_rare_colors_are_rare_but_happen():
    families = collections.Counter()
    for seed in range(3000):
        third = g.roll("cat", "orange", "ash", seed)["coat"]["colors"][2]
        if third:
            families[g.COLORS[third].family] += 1
    rare = families["pink"] + families["purple"]
    assert 0 < rare < sum(families.values()) * 0.1


def test_new_colors_are_the_ones_not_yet_unlocked():
    genes = {"coat": {"colors": ["orange", "ash", "salmon"]}}
    assert g.new_colors(genes, {"orange", "ash", "black"}) == ["salmon"]


def test_a_stat_group_added_later_fills_in_without_changing_the_rest(monkeypatch):
    genes = g.roll("fox", "flame", "snow", 7)
    monkeypatch.setitem(g.ROLLERS, "magic", lambda seed, species, ctx: {"sparkle_power": seed % 5})
    filled = g.fill_missing(genes)
    assert filled["magic"] == {"sparkle_power": 2}
    assert {k: v for k, v in filled.items() if k != "magic"} == genes
    assert g.fill_missing(filled) == filled


def test_rolls_include_personality_and_battle_hooks():
    genes = g.roll("llama", "ivory", "cocoa", 99)
    p = genes["personality"]
    assert all(0 <= p[k] <= 1 for k in ("energy", "friendly", "curious", "sleepy"))
    assert p["favorite"] in g.VEGGIES
    b = genes["battle"]
    assert all(1 <= b[k] <= 10 for k in ("strength", "speed", "stamina"))
    assert b["element"] == "splash" and b["level"] == 1


def test_resolve_adds_hex_and_names():
    r = g.resolve(g.roll("cat", "orange", "ash", 5, unlocked={"orange", "ash"}))
    assert r["hex"][0] == g.COLORS["orange"].hex
    assert r["color_names"][1] == "Ash"


def test_species_get_their_own_looks():
    cat = g.roll("cat", "orange", "ash", 3)
    assert -1 <= cat["shape"]["weight"] <= 1
    assert cat["face"]["eyes"] in g.SPECIES_EYES["cat"]
    assert "snout" in g.roll("dog", "golden", "chestnut", 3)["shape"]
    assert "weight" not in g.roll("fox", "flame", "snow", 3)["shape"]


def test_cats_lean_skinny_and_odd_eyes_are_rare():
    cats = [g.roll("cat", "orange", "ash", seed) for seed in range(2000)]
    weights = [c["shape"]["weight"] for c in cats]
    assert sum(weights) / len(weights) < -0.1
    odd = sum("odd_eye" in c["face"] for c in cats)
    assert 0 < odd < 150
