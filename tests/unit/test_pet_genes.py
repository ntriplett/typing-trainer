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


def test_coats_are_mostly_one_color_with_a_highlight():
    import collections

    styles = collections.Counter(g.roll("cat", "orange", "ash", seed)["coat"]["style"] for seed in range(3000))
    assert styles["highlight"] > styles["mix"] > styles["accent"] > 0
    for seed in range(300):
        coat = g.roll("cat", "orange", "ash", seed)["coat"]
        if coat["style"] == "highlight":
            assert coat["shares"][0] >= 0.78 and coat["shares"][2] == 0
        if coat["style"] == "accent":
            assert coat["shares"][2] >= g.MIN_THIRD_SHARE and coat["colors"][2]


def test_the_palette_is_muted():
    # every natural color is softer than its raw version
    assert g.mute("#e46a28", "orange") != "#e46a28"
    r, gg, b = (int(g.COLORS["flame"].hex[i : i + 2], 16) for i in (1, 3, 5))
    assert max(r, gg, b) - min(r, gg, b) < 150  # no longer fully saturated


def test_dogs_roll_a_breed_and_sometimes_a_mix():
    import collections

    dogs = [g.roll("dog", "golden", "chestnut", seed)["shape"] for seed in range(2000)]
    breeds = collections.Counter(d["breed"] for d in dogs)
    assert set(breeds) == set(g.BREEDS["dog"])
    mixes = [d["mix"] for d in dogs if d["mix"]]
    assert 0.15 < len(mixes) / len(dogs) < 0.35
    for d in dogs:
        for part, donor in d["mix"].items():
            assert part in g.MIX_PARTS["dog"] and donor != d["breed"]
    assert all("breed" in g.roll(sp, *g.STARTER_COLORS[sp][:2], 1)["shape"] for sp in g.BREEDS)


def test_dogs_have_their_own_pattern_odds():
    import collections

    dogs = collections.Counter(g.roll("dog", "golden", "chestnut", seed)["coat"]["pattern"] for seed in range(3000))
    assert dogs["belly"] > dogs["stripes"] * 4
    assert dogs["mask"] > 0
    cats = collections.Counter(g.roll("cat", "orange", "ash", seed)["coat"]["pattern"] for seed in range(500))
    assert "mask" not in cats


def test_bunnies_roll_a_breed_and_only_swap_ears():
    bunnies = [g.roll("bunny", "snow", "chestnut", seed)["shape"] for seed in range(1000)]
    assert {b["breed"] for b in bunnies} == set(g.BREEDS["bunny"])
    assert all(set(b["mix"]) <= {"ears"} for b in bunnies)


def test_bunnies_wear_rabbit_patterns():
    import collections

    pats = collections.Counter(g.roll("bunny", "snow", "chestnut", seed)["coat"]["pattern"] for seed in range(3000))
    assert set(pats) == {"self", "agouti", "broken", "dutch", "himalayan", "tan", "english"}
    assert pats["self"] > pats["english"] * 5


def test_unlocked_colors_are_shared_by_every_species():
    start = g.starting_unlocks()
    assert set(g.STARTER_COLORS["cat"]) | set(g.STARTER_COLORS["bunny"]) <= start
    # a dog's starter color can be picked for a cat
    assert g.roll("cat", "golden", "snow", 1)["coat"]["colors"][:2] == ["golden", "snow"]
    catalog = g.color_catalog(start)
    assert len(catalog) == 90 and sum(c["unlocked"] for c in catalog) == len(start)


def test_foxes_roll_breeds_and_fox_coats():
    import collections

    foxes = [g.roll("fox", "flame", "snow", seed) for seed in range(2000)]
    assert {f["shape"]["breed"] for f in foxes} == set(g.BREEDS["fox"])
    assert all(set(f["shape"]["mix"]) <= {"ears", "head"} for f in foxes)
    pats = collections.Counter(f["coat"]["pattern"] for f in foxes)
    assert set(pats) == {"red", "cross", "silver", "arctic", "marble"}
    assert pats["red"] > pats["marble"]


def test_sheep_roll_breeds_mixes_and_sheep_coats():
    import collections

    sheep = [g.roll("sheep", "snow", "charcoal", seed) for seed in range(2000)]
    assert {x["shape"]["breed"] for x in sheep} == set(g.BREEDS["sheep"])
    assert all(set(x["shape"]["mix"]) <= {"ears", "ramHorns", "tuft"} for x in sheep)
    pats = collections.Counter(x["coat"]["pattern"] for x in sheep)
    assert set(pats) == {"whiteface", "blackface", "self", "speckled", "jacob", "badger", "valais"}
    assert "wool" in sheep[0]["shape"]


def test_cats_roll_breeds_and_cat_coats():
    import collections

    cats = [g.roll("cat", "orange", "snow", seed) for seed in range(2000)]
    assert {c["shape"]["breed"] for c in cats} == set(g.BREEDS["cat"])
    assert all(set(c["shape"]["mix"]) <= {"ears", "head", "cheeks"} for c in cats)
    pats = collections.Counter(c["coat"]["pattern"] for c in cats)
    assert set(pats) == set(g.CAT_PATTERNS)
    assert pats["tabby"] > pats["van"]


def test_goats_roll_breeds_mixes_and_goat_coats():
    import collections

    goats = [g.roll("goat", "snow", "chestnut", seed) for seed in range(2000)]
    assert {x["shape"]["breed"] for x in goats} == set(g.BREEDS["goat"])
    assert all(set(x["shape"]["mix"]) <= {"ears", "goatHorns", "beard"} for x in goats)
    pats = collections.Counter(x["coat"]["pattern"] for x in goats)
    assert set(pats) == {"solid", "swiss", "chamoisee", "coublanc", "sundgau", "blacktan", "spotted", "boer"}


def test_llamas_roll_breeds_mixes_and_llama_coats():
    import collections

    llamas = [g.roll("llama", "ivory", "cocoa", seed) for seed in range(2000)]
    assert {x["shape"]["breed"] for x in llamas} == set(g.BREEDS["llama"])
    assert all(set(x["shape"]["mix"]) <= {"ears", "head", "tuft"} for x in llamas)
    pats = collections.Counter(x["coat"]["pattern"] for x in llamas)
    assert set(pats) == {"solid", "paint", "guanaco", "twotone", "appaloosa", "tuxedo", "roan", "saddle"}


def test_turtles_roll_breeds_and_shell_patterns():
    import collections

    turtles = [g.roll("turtle", "moss", "khaki", seed) for seed in range(2000)]
    assert {x["shape"]["breed"] for x in turtles} == set(g.BREEDS["turtle"])
    assert all(set(x["shape"]["mix"]) <= {"head", "ridges", "tailLen"} for x in turtles)
    pats = collections.Counter(x["coat"]["pattern"] for x in turtles)
    assert set(pats) == {"plain", "flecks", "rings", "star", "mottled", "checker", "keel"}
