"""Unit tests for pet genes (app/pet_genes.py): deterministic rolls, coat
shares, the color pool and unlock rules, and the hook for future stats."""

import collections

import pytest

from app import pet_genes as g


def test_the_color_pool_is_90_plus_flames_and_metals_with_about_45_per_species():
    assert len(g.COLORS) == 90 + 24 + 8 + 5  # shared, phoenix flames, fish neons, treasure metals
    for species, starters in g.STARTER_COLORS.items():
        eligible = g.eligible_colors(species)
        assert set(starters) <= set(eligible)
        if species in g.SPECIAL_PALETTE:
            assert all(g.COLORS[c].family.startswith("fire") for c in eligible)
        elif species != "fish":  # fish wear the whole pool
            assert 40 <= len(eligible) <= 55, species


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
        g.roll("nosuchpet", "orange", "ash", 1)
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
    flames = {c for c in start if g.COLORS[c].family.startswith(("fire", "neon"))}
    assert len(catalog) == 90 and sum(c["unlocked"] for c in catalog) == len(start - flames)


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


def test_lizards_roll_breeds_and_lizard_patterns():
    import collections

    lizards = [g.roll("lizard", "fern", "sand", seed) for seed in range(2000)]
    assert {x["shape"]["breed"] for x in lizards} == set(g.BREEDS["lizard"])
    assert all(set(x["shape"]["mix"]) <= {"crest", "dewlap", "head"} for x in lizards)
    pats = collections.Counter(x["coat"]["pattern"] for x in lizards)
    assert set(pats) == {"plain", "banded", "striped", "spotted", "chameleon", "twotone", "speckled"}


def test_snakes_roll_breeds_and_snake_patterns():
    import collections

    snakes = [g.roll("snake", "moss", "rust", seed) for seed in range(2000)]
    assert {x["shape"]["breed"] for x in snakes} == set(g.BREEDS["snake"])
    assert all(set(x["shape"]["mix"]) <= {"viper", "rattle", "hood"} for x in snakes)
    pats = collections.Counter(x["coat"]["pattern"] for x in snakes)
    assert set(pats) == {"diamondback", "banded", "saddles", "striped", "speckled", "plain"}
    assert pats["diamondback"] > pats["speckled"]


def test_snakes_often_roll_a_third_color_banded_half_the_time():
    snakes = [g.roll("snake", "moss", "rust", seed)["coat"] for seed in range(4000)]
    banded = [c for c in snakes if c["pattern"] == "banded"]
    share = sum(1 for c in banded if c["colors"][2]) / len(banded)
    assert 0.42 < share < 0.58
    overall = sum(1 for c in snakes if c["colors"][2]) / len(snakes)
    assert overall > 0.3


def test_dragons_roll_breeds_and_mixes():
    dragons = [g.roll("dragon", "fern", "crimson", seed) for seed in range(2000)]
    assert {x["shape"]["breed"] for x in dragons} == set(g.BREEDS["dragon"])
    assert all(set(x["shape"]["mix"]) <= {"fire", "horns", "wings", "head"} for x in dragons)
    assert any(x["shape"]["mix"] for x in dragons)


def test_the_game_picks_a_dragons_colors_mostly_close_together():
    import collections

    tiers = collections.Counter()
    for seed in range(4000):
        a, b, _ = g.roll("dragon", None, None, seed)["coat"]["colors"]
        fa, fb = g.COLORS[a].family, g.COLORS[b].family
        tiers["same" if fa == fb else "near" if fb in g.NEAR_FAMILIES["dragon"][fa] else "far"] += 1
    assert 0.55 < tiers["same"] / 4000 < 0.65
    assert 0.25 < tiers["near"] / 4000 < 0.35
    assert 0.07 < tiers["far"] / 4000 < 0.13
    # a picked main color keeps the rule for the second
    pals = [g.roll("dragon", "crimson", None, seed, {"crimson"})["coat"]["colors"] for seed in range(500)]
    assert all(c[0] == "crimson" and c[1] != "crimson" for c in pals)
    assert sum(g.COLORS[c[1]].family == "red" for c in pals) > 250


def test_dragons_third_color_is_a_treasure_metal_never_picked_or_unlocked():
    import collections

    dragons = [g.roll("dragon", None, None, seed) for seed in range(3000)]
    thirds = [d["coat"]["colors"][2] for d in dragons if d["coat"]["colors"][2]]
    assert 0.35 < len(thirds) / 3000 < 0.45
    assert set(thirds) == set(g.METALS)
    assert all(not set(g.new_colors(d, set())) & set(g.METALS) for d in dragons)
    with pytest.raises(g.GeneError):
        g.roll("dragon", "gilt", None, 1, {"gilt"})
    with pytest.raises(g.GeneError):
        g.roll("dragon", None, "crimson", 1)
    pats = collections.Counter(d["coat"]["pattern"] for d in dragons)
    assert set(pats) == {"storybook", "ombre", "ridgeback", "scaled", "tiger", "jeweled", "shadow"}


def test_unicorns_are_often_white_with_an_accent_else_close_colors():
    import collections

    tiers = collections.Counter()
    unicorns = [g.roll("unicorn", None, None, seed) for seed in range(4000)]
    for u in unicorns:
        a, b, _ = u["coat"]["colors"]
        fa, fb = g.COLORS[a].family, g.COLORS[b].family
        if fa == "white":
            assert fb != "white"
            tiers["white"] += 1
        else:
            tiers["same" if fa == fb else "near" if fb in g.NEAR_FAMILIES["unicorn"][fa] else "far"] += 1
    assert 0.45 < tiers["white"] / 4000 < 0.55
    assert tiers["same"] > tiers["near"] > tiers["far"]
    assert {u["shape"]["breed"] for u in unicorns} == set(g.BREEDS["unicorn"])
    assert all(set(u["shape"]["mix"]) <= {"wings", "horn", "neck"} for u in unicorns)
    thirds = [u["coat"]["colors"][2] for u in unicorns if u["coat"]["colors"][2]]
    assert set(thirds) == set(g.METALS) and 0.35 < len(thirds) / 4000 < 0.45
    pats = collections.Counter(u["coat"]["pattern"] for u in unicorns)
    assert set(pats) == {"solid", "blaze", "dapple", "pinto", "appaloosa", "rainbow", "starry"}


def test_phoenixes_burn_bright_flames_with_a_lighter_glow():
    import collections

    birds = [g.roll("phoenix", None, None, seed) for seed in range(4000)]
    fams = collections.Counter(g.COLORS[b["coat"]["colors"][0]].family for b in birds)
    assert fams["fire_orange"] > fams["fire_red"] > fams["fire_blue"]
    rare = fams["fire_blue"] + fams["fire_green"] + fams["fire_violet"]
    assert 0.06 < rare / 4000 < 0.14
    for b in birds:
        flame, glow, _ = b["coat"]["colors"]
        assert flame not in g.GLOW_ONLY
        assert g.COLORS[glow].family in g.GLOW_FAMILIES[g.COLORS[flame].family]
        assert g._lum(glow) > g._lum(flame)
    assert {b["shape"]["breed"] for b in birds} == set(g.BREEDS["phoenix"])
    assert {b["coat"]["pattern"] for b in birds} == {"pure", "wingtips", "embers", "starburst", "smoke"}
    assert not any(b["coat"]["colors"][2] for b in birds)  # no treasure metal
    # flames are only for phoenixes, and phoenixes only wear flames
    with pytest.raises(g.GeneError):
        g.roll("cat", "blaze", None, 1)
    with pytest.raises(g.GeneError):
        g.roll("phoenix", "golden", None, 1)
    assert len(g.color_catalog(g.starting_unlocks(), "phoenix")) == 24


def test_fish_roll_every_part_on_its_own():
    fish = [g.roll("fish", None, None, seed) for seed in range(800)]
    for part, options in g.PARTS["fish"].items():
        assert {f["shape"][part] for f in fish} == set(options), part
    # the parts mix freely: plenty of different body + head pairs
    assert len({(f["shape"]["body"], f["shape"]["head"]) for f in fish}) > 50


def test_fish_wear_the_shared_pool_plus_rare_neons_and_a_fin_pattern():
    import collections

    fish = [g.roll("fish", None, None, seed) for seed in range(4000)]
    fams = collections.Counter(g.COLORS[c].family for f in fish for c in f["coat"]["colors"][:2])
    assert len(fams) >= 14
    assert 0 < fams["neon"] < 0.08 * 8000
    bodies = collections.Counter(f["coat"]["pattern"] for f in fish)
    fins = collections.Counter(f["coat"]["fins"] for f in fish)
    assert set(bodies) == set(g.SPECIES_PATTERNS["fish"]) and bodies["solid"] > bodies["scaled"]
    assert set(fins) == set(g.FIN_PATTERNS["fish"]) and fins["clear"] > fins["rayed"]
    # neons are only for fish
    with pytest.raises(g.GeneError):
        g.roll("cat", "neon_blue", None, 1, {"neon_blue"})
    assert g.roll("fish", "neon_blue", "snow", 1, {"neon_blue", "snow"})
    assert len(g.color_catalog(set(), "fish")) == 90 + 8
    assert len(g.color_catalog(set(), "cat")) == 90


def test_fish_prefer_a_height_by_their_mouth_and_small_ones_school():
    fish = [g.roll("fish", None, None, seed) for seed in range(3000)]
    assert all(0 <= f["behavior"]["height"] <= 1 and 0 <= f["behavior"]["schooling"] <= 1 for f in fish)
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    up = mean([f["behavior"]["height"] for f in fish if f["shape"]["head"] in ("upturned", "beak")])
    down = mean([f["behavior"]["height"] for f in fish if f["shape"]["head"] in ("sucker", "whiskers")])
    assert up > 0.65 and down < 0.35
    small = mean([f["behavior"]["schooling"] for f in fish if f["shape"]["size"] < -0.3])
    big = mean([f["behavior"]["schooling"] for f in fish if f["shape"]["size"] > 0.3])
    assert small > big + 0.1
    # stable, and only fish have it
    assert g.roll("fish", None, None, 7)["behavior"] == g.roll("fish", None, None, 7)["behavior"]
    assert "behavior" not in g.roll("cat", "orange", "ash", 7)
    old = {k: v for k, v in fish[0].items() if k != "behavior"}
    assert g.fill_missing(old)["behavior"] == fish[0]["behavior"]  # fills in for older fish


# --- the pet shop's rolls (PLAN.md 11h) -------------------------------------------

SHOP_SEEDS = range(3000)


def _picked(genes):
    return genes["coat"]["colors"][:2]


def test_available_colors_are_the_starters_plus_unlocked_ones_that_suit_the_species():
    assert g.available_colors("cat", set()) == [c for c in g.eligible_colors("cat") if c in g.STARTER_COLORS["cat"]]
    assert "ginger" in g.available_colors("cat", {"ginger"})
    assert "moss" not in g.available_colors("cat", {"moss"})  # green isn't a cat family


def test_shop_rolls_are_deterministic():
    assert g.shop_roll("dog", {"rose"}, 7) == g.shop_roll("dog", {"rose"}, 7)
    with pytest.raises(g.GeneError):
        g.shop_roll("nosuchpet", set(), 1)


def test_a_new_player_sees_starter_colors_and_about_8_percent_unusual_ones():
    starters = set(g.STARTER_COLORS["cat"])
    pets = [g.shop_roll("cat", set(), s) for s in SHOP_SEEDS]
    unusual = [p for p in pets if not set(_picked(p)) <= starters]
    assert 0.06 <= len(unusual) / len(pets) <= 0.10
    assert all(len(set(_picked(p)) - starters) == 1 for p in unusual)  # one swapped color at most
    new = [next(c for c in _picked(p) if c not in starters) for p in unusual]
    natural = sum(g.realism("cat", c) >= g.NATURAL for c in new)
    assert 0.55 <= natural / len(new) <= 0.78  # natural 2x as likely as rare


def test_at_least_half_keep_a_traditional_color_however_many_fancy_ones_are_unlocked():
    fancy = {c for c in g.eligible_colors("bunny") if not g.traditional("bunny", c)}
    pets = [g.shop_roll("bunny", fancy, s) for s in SHOP_SEEDS]
    with_trad = sum(any(g.traditional("bunny", c) for c in _picked(p)) for p in pets)
    fancy_main = sum(not g.traditional("bunny", _picked(p)[0]) for p in pets)
    assert with_trad / len(pets) >= 0.5
    assert 0.4 <= fancy_main / len(pets) <= 0.6  # fancy unlocks really do show up


def test_species_with_their_own_color_rules_ignore_the_shop_rules():
    for species in g.GAME_PICKED:
        assert g.shop_roll(species, set(), 5)["coat"]["colors"][:2] == g.roll(species, None, None, 5)["coat"]["colors"][:2]


def test_new_to_player_counts_starters_as_known():
    pet = g.roll("cat", "orange", "lilac", 1, unlocked={"orange", "lilac"})
    assert g.new_to_player(pet, set()) == ["lilac"] + [c for c in pet["coat"]["colors"][2:] if c and c not in g.STARTER_COLORS["cat"]]
    assert "lilac" not in g.new_to_player(pet, {"lilac"})


def test_rare_multiplier_runs_from_1_to_1_5_on_a_log_scale():
    assert g.rare_multiplier({"a": 50, "b": 1}, "a") == 1.0
    assert g.rare_multiplier({"a": 50, "b": 1}, "b") == pytest.approx(1.5)
    assert g.rare_multiplier({"a": 5000, "b": 1}, "b") == pytest.approx(1.5)  # capped
    assert 1.1 < g.rare_multiplier({True: 0.25, False: 0.75}, True) < 1.2  # a mix
    assert g.rare_multiplier({"a": 1, "b": 1}, "b") == 1.0  # even tables never count
    assert g.rare_multiplier({"a": 1, "b": 0}, "b") == 1.0  # impossible outcomes don't either


def test_every_rare_feature_finds_each_pets_outcome_in_its_table():
    """Guards new RARE_FEATURES entries: the odds table must match what the rollers roll."""
    for species in g.SPECIES_COLORS:
        for seed in range(150):
            genes = g.shop_roll(species, set(), seed)
            for feature in g.RARE_FEATURES:
                odds = feature.odds(species)
                if odds is not None:
                    assert feature.outcome(genes) in odds, (species, feature.name)
            assert 1.0 <= g.rarity(genes) <= g.RARE_TOP ** len(g.RARE_FEATURES)


def test_rare_looks_are_priced_up_and_common_ones_are_not():
    pets = [g.shop_roll("cat", set(), s) for s in SHOP_SEEDS]
    sparkly = next(p for p in pets if p["face"]["sparkle"])
    assert g.rare_features(sparkly)["sparkle"] == pytest.approx(1.5, abs=0.01)
    plain = [p for p in pets if not g.rare_features(p)]
    assert plain and all(g.rarity(p) == 1.0 for p in plain)
    assert 1.3 < sorted(g.rarity(p) for p in pets)[-len(pets) // 20] < 4  # the top 5% stand out, not absurdly


def test_special_orders_get_the_asked_for_colors():
    for seed in range(200):
        pet = g.order_roll("dog", "golden", None, set(), seed)
        assert pet["coat"]["colors"][0] == "golden"
        assert pet["coat"]["colors"][1] in g.available_colors("dog", set())
    assert g.order_roll("cat", "black", "orange", set(), 3)["coat"]["colors"][:2] == ["black", "orange"]
    assert g.order_roll("cat", "lilac", None, {"lilac"}, 3)["coat"]["colors"][0] == "lilac"


def test_special_orders_only_use_unlocked_colors():
    with pytest.raises(g.GeneError, match="unlocked"):
        g.order_roll("cat", "lilac", None, set(), 1)
    with pytest.raises(g.GeneError, match="unlocked"):
        g.order_roll("cat", "orange", "lilac", set(), 1)
    with pytest.raises(g.GeneError, match="different"):
        g.order_roll("cat", "orange", "orange", set(), 1)
    assert "white_gold" not in g.order_primaries("phoenix", {"white_gold"})  # a glow, never the main color
    for seed in range(100):  # game-picked species too
        pet = g.order_roll("phoenix", "blaze", None, set(), seed)
        assert pet["coat"]["colors"][1] in g.available_colors("phoenix", set())
