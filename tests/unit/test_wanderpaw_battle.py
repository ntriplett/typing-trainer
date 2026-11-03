"""Wanderpaw battles and wild creatures (PLAN.md 11n phase 5a)."""

import json
import random
import re
from collections import Counter
from dataclasses import replace
import statistics

import pytest

from app.wanderpaw import battle as bt
from app.wanderpaw import critters as cr
from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app import pet_genes
from app.wanderpaw import save as sv
from app.wanderpaw import terms
from app.wanderpaw import world as wd

SEED = 102
WORLD = wd.generate(SEED)


def _critter(level=1, kind="leaf", species="bunny"):
    return cr.Critter("x", (0, 0), (0, 0), species, kind, level, False, 1)


def test_the_type_ring():
    assert bt.matchup("splash", "ember") == 2 and bt.matchup("splash", "dream") == 1.5
    assert bt.matchup("splash", "leaf") == pytest.approx(2 / 3) and bt.matchup("splash", "shock") == 0.5
    assert bt.matchup("ember", "ember") == 1
    assert bt.accuracy(0) == 1 and bt.accuracy(3) == pytest.approx(0.7) and bt.accuracy(20) == bt.FLOOR


def test_creatures_level_like_pets_faster_and_a_bit_weaker():
    assert [bt.enemy_energy(n) for n in (1, 7, 14, 21)] == [34, 126, 252, 320]
    assert bt.enemy_energy(8) == round((126 + 179) / 2) and bt.enemy_energy(30) > bt.enemy_energy(21)
    for level in (1, 7, 14, 21):
        pet = wp.starter("leaf", level)
        b = bt.start(_critter(level), [0, 1])
        assert b["energy"] == bt.enemy_energy(level) and b["speed"] > pet["speed"]
        assert bt.enemy_hit(level) < bt.pet_hit(pet["power"]) / 3 and bt.enemy_hit(level) < pet["energy"] * 0.12  # no one-shots
    assert bt.enemy_hit(14) > bt.enemy_hit(7)


def _round(b, team, picks, energy=None, mana=None, seed=1):
    return bt.turn(b, team, energy or [99] * len(team), picks, random.Random(seed), mana)


def test_strong_types_hit_harder():
    team = [wp.starter("splash", 3), wp.starter("splash", 3)]
    ember, shock = _critter(3, "ember", "fox"), _critter(3, "shock", "cat")
    hit = lambda c: _round(bt.start(c, [0, 1]), team, [{"move": "attack", "slips": 0}] * 2)[0]  # noqa: E731
    assert hit(ember)["max"] - hit(ember)["energy"] > hit(shock)["max"] - hit(shock)["energy"]
    with pytest.raises(ValueError):
        _round(bt.start(ember, [0, 1]), team, [{"move": "brace", "slips": 0}] * 2)


# --- focuses ---------------------------------------------------------------------


def _focused(kind, focus, level=3):
    return {**wp.starter(kind, level), "mana": 30, "focus": focus}


def _ids(member):
    return [m["id"] for m in bt.moves(member)]


def test_every_type_names_every_focus_and_each_takes_one_grey_move():
    for t in wd.REGIONS:
        assert set(bt.FOCUS_NAMES[t]) == set(bt.FOCUSES) and t in bt.GUARD_NAMES
    assert len(set(bt.FOCUS_REPLACES.values())) == 4
    for focus in bt.FOCUSES:
        ids = _ids(_focused("ember", focus))
        assert len(ids) == 6 and bt.FOCUS_MOVES[focus] in ids and bt.FOCUS_REPLACES[focus] not in ids
        option = bt.focus_option(wp.starter("ember", 3), focus)
        assert option["type"] == "ember" and len(option["moves"]) == 6
    assert bt.strong_against("ember") == ("dream", "leaf") and bt.beaten_by("ember") == "splash"


def test_a_passive_move_cant_be_picked():
    team = [_focused("ember", "healer"), _pet("leaf")]
    with pytest.raises(ValueError, match="just works"):
        _round(bt.start(_critter(3), [0, 1]), team, [{"move": "healer", "slips": 0}, {"move": "attack", "slips": 0}], energy=[25, 25])
    with pytest.raises(ValueError, match="moves"):  # guard is gone
        _round(bt.start(_critter(3), [0, 1]), team, [{"move": "guard", "slips": 0}, {"move": "attack", "slips": 0}], energy=[25, 25])


def test_a_healer_gives_its_partner_energy_and_mana_up_to_the_most():
    team = [_focused("ember", "healer"), _pet("leaf")]
    plain = [_pet("ember"), _pet("leaf")]
    picks = [{"move": "guard" if False else "attack", "slips": 0}] * 2
    b = {**bt.start(_critter(21), [0, 1]), "energy": 9999, "max": 9999}
    energy, mana = [25, 10], [30, 5]
    given = 0
    for _ in range(8):
        b, energy, mana = bt.turn(b, team, energy, picks, random.Random(1), mana)
        energy[1] = 10  # (whatever hit it, it stays hurt: just the healing to see)
        given += sum(s["act"] == "heal" for s in b["log"])
    assert b["healed"]["0:energy"] == bt.HEAL_MAX_ENERGY and b["healed"]["0:mana"] == bt.HEAL_MAX_MANA
    assert mana[1] == 5 + bt.HEAL_MAX_MANA and given == bt.HEAL_MAX_ENERGY
    heal = bt.turn({**bt.start(_critter(21), [0, 1]), "energy": 9999}, team, [25, 10], picks, random.Random(1), [30, 5])[0]["log"]
    step = next(s for s in heal if s["act"] == "heal")
    assert step["target"] == 1 and step["flash"] == [0, "healer"] and "+1 {energy}" in step["text"] and "+1 {mana}" in step["text"]
    assert not any(s["act"] == "heal" for s in bt.turn({**bt.start(_critter(21), [0, 1]), "energy": 9999}, plain, [25, 10], picks, random.Random(1), [30, 5])[0]["log"])


def test_an_elementalist_marks_first_so_its_partner_can_set_off_a_combo():
    team = [_focused("shock", "elementalist"), {**_pet("splash"), "speed": 999}]  # however fast the partner
    b, _, mana = _round(bt.start(_critter(3, "leaf", "bunny"), [0, 1]), team,
                        [{"move": "mark", "slips": 0}, {"move": "attack", "slips": 0}], energy=[25, 25], mana=[30, 30])
    assert b["log"][0]["act"] == "mark" and mana[0] == 30 - bt.MARK_MANA
    assert b["log"][0]["damage"] == 0
    assert any(s.get("combo") == "Thunderstorm" for s in b["log"])
    with pytest.raises(ValueError, match="mana"):
        _round(bt.start(_critter(3), [0, 1]), team, [{"move": "mark", "slips": 0}, {"move": "attack", "slips": 0}], energy=[25, 25], mana=[0, 30])


def test_a_daredevil_hits_twice_as_hard_for_energy_but_never_its_last():
    plain = [_pet("ember"), _pet("ember")]
    bold = [_focused("ember", "daredevil"), _pet("ember")]
    picks = [{"move": "attack", "slips": 0}, {"move": "attack", "slips": 0}]
    damage = lambda team, energy: next(s["damage"] for s in _round(bt.start(_critter(9, "leaf", "bunny"), [0, 1]), team, picks, energy=energy)[0]["log"] if s["who"] == 0)  # noqa: E731
    assert damage(bold, [25, 25]) == pytest.approx(bt.DAREDEVIL * damage(plain, [25, 25]), abs=1)
    step = next(s for s in _round(bt.start(_critter(9, "leaf", "bunny"), [0, 1]), bold, picks, energy=[25, 25])[0]["log"] if s["who"] == 0)
    assert step["flash"] == [0, "daredevil"] and "1.5x" in step["text"]
    # only its own type: a second type's hit is plain
    assert bt._daredevil_cost(wp.starter("ember", 3)) == 1 and bt._daredevil_cost(wp.starter("ember", 21)) == 3
    b = {**bt.start(_critter(1, "leaf", "bunny"), [0, 1]), "skip": 5}  # it can't hit back
    _, energy, _ = bt.turn(b, bold, [1, 25], picks, random.Random(1), [30, 30])
    assert energy[0] == 1


def test_a_guardian_keeps_two_types_off_its_partner_for_two_rounds():
    team = [_focused("ember", "guardian"), _pet("leaf")]  # ember stops dream and leaf
    picks = [{"move": "attack", "slips": 0}] * 2
    foe = lambda: {**bt.start(_critter(3, "dream", "sheep"), [0, 1]), "energy": 9999}  # noqa: E731
    for seed in range(40):
        b = foe()
        energy = [25, 25]
        for r in (1, 2):
            b, energy, _ = bt.turn(b, team, energy, picks, random.Random(seed + r), [30, 30])
        assert energy[1] == 25  # nothing got through to the partner: it goes for the Guardian instead
        assert energy[0] < 25
    # the third round it's over, and it goes right for the pet it's strongest against
    _, energy, _ = bt.turn({**foe(), "round": bt.GUARDIAN_ROUNDS}, team, [25, 25], picks, random.Random(1), [30, 30])
    assert energy[1] < 25
    # with no one else to hit, it's blocked outright
    alone = [{**_focused("ember", "guardian"), "energy": 25}, _pet("leaf")]
    both = [_focused("ember", "guardian"), _focused("splash", "guardian")]  # stop dream, leaf; ember, dream
    log = bt.turn(foe(), both, [25, 25], picks, random.Random(1), [30, 30])[0]["log"]
    assert any(s["act"] == "blocked" for s in log) and alone
    # other types get through, and a creature with a second type uses it
    b = bt.start(_critter(3, "splash", "dog"), [0, 1])
    assert any(sum(bt.turn(b, team, [25, 25], picks, random.Random(s), [30, 30])[1]) < 50 for s in range(40))
    two = {**foe(), "second": "shock"}
    assert bt.foe_type(two, "leaf", bt.strong_against("ember")) == "shock"
    assert bt.foe_type(foe(), "leaf", bt.strong_against("ember")) is None


def test_a_guardians_guard_is_best_against_what_beats_it():
    team = [_focused("ember", "guardian"), _pet("ember")]
    plain = [_pet("ember"), _pet("ember")]
    picks = [{"move": "guard", "slips": 0}, {"move": "attack", "slips": 0}]

    def taken(members, kind, species):
        total = 0
        for seed in range(60):
            b = {**bt.start(_critter(40, kind, species), [0, 1]), "energy": 9999}
            _, energy, _ = bt.turn(b, members, [60, 50], picks, random.Random(seed), [30, 30])  # it goes for the weaker
            total += 60 - energy[0]
        return total

    assert taken(team, "splash", "dog") < taken(plain, "splash", "dog")  # splash beats ember
    assert taken(team, "shock", "cat") == pytest.approx(taken(plain, "shock", "cat"), rel=0.5)


def test_two_guardians_guarding_never_trip_over_each_other():
    team = [_focused("ember", "guardian"), _focused("dream", "guardian")]  # ember stops dream, leaf; dream stops leaf, shock
    for seed in range(40):
        b = bt.start(_critter(3, "leaf", "bunny"), [0, 1])
        b, energy, _ = bt.turn(b, team, [25, 25], [{"move": "guard", "slips": 0}] * 2, random.Random(seed), [30, 30])
        assert energy == [25, 25]


def test_moves_away_from_battle_say_just_what_they_do():
    pet = wp.starter("ember", 3)
    moves = {m["id"]: m for m in bt.described_moves(pet, mana=2)}
    assert list(moves) == ["attack", "big", "guard", "focus", "cheer", "rest"]
    assert moves["attack"]["label"] == "{ember} attack" and moves["attack"]["icons"]["hit"]["tip"] == "Medium damage."
    assert moves["big"]["icons"]["hit"]["tip"] == "Very high damage." and "Glowing" in moves["big"]["icons"]["marks"][0]["tip"]
    assert moves["big"]["can"] is False  # not enough mana
    both = {m["id"]: m for m in bt.described_moves({**pet, "types": {"shock": 3, "ember": 3}})}
    assert both["attack"]["label"] == "{shock} attack" and [m["tip"] for m in both["big"]["icons"]["marks"]] == ["Leaves Enemy Static."]
    assert both["big"]["label"] == "Big {shock}"


def test_six_moves_each_with_a_note():
    pet = wp.starter("ember", 3)
    moves = bt.moves(pet, "dream", mana=2)
    assert [m["id"] for m in moves] == ["attack", "big", "guard", "focus", "cheer", "rest"]
    assert all(len(m["note"]) <= 30 for m in moves) and "Super strong" in moves[0]["note"]
    assert moves[1]["icons"]["haste"]
    assert moves[1]["can"] is False  # not enough mana
    with pytest.raises(ValueError, match="mana"):
        _round(bt.start(_critter(3), [0, 1]), [pet, pet], [{"move": "big", "slips": 0}] * 2, mana=[2, 2])
    # with two types, its Attack and Big stay its first
    dragon = {**pet, "types": {"shock": 3, "ember": 3}}
    by_id = {m["id"]: m for m in bt.moves(dragon, "dream")}
    assert by_id["big"]["type"] == "shock" and by_id["attack"]["type"] == "shock"
    assert by_id["big"]["label"] == "Big {shock}" and by_id["big"]["icons"]["marks"][0]["type"] == "shock"


def test_a_second_attack_takes_a_grey_moves_slot_and_hits_in_its_type():
    pet = {**wp.starter("ember", 5), "types": {"ember": 5, "splash": 1}, "swaps": {"rest": "attack2"}, "mana": 30}
    moves = bt.moves(pet, "ember")
    assert [m["id"] for m in moves] == ["attack", "big", "guard", "focus", "cheer", "attack2"]
    second = moves[-1]
    assert second["type"] == "splash" and second["label"] == "{splash} attack" and second["size"] == "medium" and "Super strong" in second["note"]
    assert moves[0]["type"] == "ember"
    assert bt.described_moves(pet)[-1]["label"] == "{splash} attack"
    team = [pet, _pet("leaf")]
    damage = lambda move: next(s for s in _round(bt.start(_critter(5, "ember", "fox"), [0, 1]), team, [{"move": move, "slips": 0}, {"move": "guard", "slips": 0}], energy=[30, 30])[0]["log"] if s["who"] == 0)  # noqa: E731
    two, one = damage("attack2"), damage("attack")
    assert two["type"] == "splash" and one["type"] == "ember" and two["damage"] > one["damage"]  # splash beats ember
    with pytest.raises(ValueError, match="moves"):  # rest is gone
        damage("rest")


def test_only_grey_moves_can_make_room():
    plain = wp.starter("ember", 5)
    assert [m["id"] for m in bt.grey_moves(plain)] == ["guard", "focus", "cheer", "rest"]
    for focus, left in (("healer", ["focus", "cheer", "rest"]), ("elementalist", ["guard", "focus", "rest"]),
                        ("daredevil", ["guard", "focus", "cheer"]), ("guardian", ["cheer", "rest"])):
        assert [m["id"] for m in bt.grey_moves({**plain, "focus": focus})] == left


def test_a_daredevils_second_attack_is_plain():
    bold = {**_focused("ember", "daredevil", 5), "types": {"ember": 5, "splash": 1}, "swaps": {"focus": "attack2"}}
    step = next(s for s in _round(bt.start(_critter(5, "leaf", "bunny"), [0, 1]), [bold, _pet("leaf")],
                                  [{"move": "attack2", "slips": 0}, {"move": "guard", "slips": 0}], energy=[30, 30])[0]["log"] if s["who"] == 0)
    assert step["flash"] is None and "double" not in step["text"]


def test_guard_takes_the_hit_for_a_partner_at_half():
    team = [wp.starter("leaf", 3), wp.starter("leaf", 3)]
    b = bt.start(_critter(3, "shock", "cat"), [0, 1])
    for seed in range(20):
        _, energy, _ = _round(b, team, [{"move": "guard", "slips": 0}, {"move": "rest", "slips": 0}], energy=[20, 20], seed=seed)
        assert energy[1] == 20 - bt.REST_COST and energy[0] < 20  # the guard takes the hit; the guarded one only rests


def test_focus_and_cheer_make_moves_stronger_and_rest_gives_back():
    team = [wp.starter("leaf", 3), wp.starter("leaf", 3)]
    b = bt.start(_critter(3), [0, 1])
    plain = _round(b, team, [{"move": "attack", "slips": 0}, {"move": "rest", "slips": 0}])[0]
    cheered = _round(b, team, [{"move": "attack", "slips": 0}, {"move": "cheer", "slips": 0}])[0]
    assert cheered["energy"] < plain["energy"]
    focused = _round(b, team, [{"move": "focus", "slips": 0}, {"move": "rest", "slips": 0}])[0]
    assert focused["focus"] == [0]
    after = _round(focused, team, [{"move": "attack", "slips": 0}, {"move": "rest", "slips": 0}])[0]
    assert focused["energy"] - after["energy"] > b["energy"] - plain["energy"]
    _, energy, mana = _round(b, team, [{"move": "rest", "slips": 0}] * 2, energy=[10, 10], mana=[0, 0])
    assert mana == [bt.REST_MANA] * 2 and max(energy) > 10 - 4


def _pet(kind, level=3):
    return {**wp.starter(kind, level), "mana": 30}


def _hit_with(kind, marks=None, effects=None, move="attack", foe_kind="leaf", seed=1, energy=None):
    """One round: a `kind` pet's move (its partner guards) on a creature with these marks."""
    b = {**bt.start(_critter(5, foe_kind, "goat"), [0, 1]), "marks": dict(marks or {}), "effects": dict(effects or {}), "start_energy": {"0": 40, "1": 40}}
    team = [_pet(kind), _pet("leaf")]
    return _round(b, team, [{"move": move, "slips": 0}, {"move": "guard", "slips": 0}], energy=energy or [20, 20],
                  mana=[30, 30], seed=seed)


def test_the_combo_grid_has_a_gap_in_every_row_and_column():
    order = ["splash", "ember", "dream", "shock", "leaf"]
    marks = [bt.MARKS[t] for t in order]
    assert len(bt.COMBOS) == 20 and len({c.name for c in bt.COMBOS.values()}) == 20
    for r, mark in enumerate(marks):
        gaps = [c for c, kind in enumerate(order) if (mark, kind) not in bt.COMBOS]
        assert gaps == [(r - 1) % 5]  # just under the diagonal


def test_big_moves_go_first_and_marks_last_two_rounds():
    b, *_ = _hit_with("splash", move="big")
    assert b["log"][0]["who"] == 0 and b["log"][0]["big"]  # before the (fast) creature
    assert b["marks"] == {"soaked": 1}  # this round, and the next
    b2 = _round(b, [_pet("splash"), _pet("leaf")], [{"move": "guard", "slips": 0}] * 2, energy=[20, 20])[0]
    assert "soaked" not in b2["marks"]


def test_combos_hit_harder_and_use_up_the_mark():
    plain = _hit_with("shock")[0]
    zapped = _hit_with("shock", {"soaked": 2})[0]
    hit = lambda b: next(e for e in b["log"] if e["who"] == 0)  # noqa: E731
    assert hit(zapped)["damage"] >= 2 * hit(plain)["damage"] - 1 and hit(zapped)["combo"] == "Chain Zap"
    assert "soaked" not in zapped["marks"]
    assert hit(_hit_with("shock", {"static": 2})[0])["combo"] == "Overcharge"


def test_combos_that_cost_it_turns():
    for mark, kind, turns in (("drowsy", "dream", 2), ("soaked", "ember", 1), ("tangled", "leaf", 1)):
        b = _hit_with(kind, {mark: 2})[0]
        lost = b["skip"] + sum(e["act"] == "skip" for e in b["log"])
        assert lost == turns, (mark, kind)


def test_combos_that_weaken_it_hurt_it_or_help_you():
    # drenched: it hits for half; thorns: it hurts itself
    for seed in range(5):
        plain = _hit_with("leaf", seed=seed)
        wet = _hit_with("leaf", effects={"drenched": 3}, seed=seed)
        foe_hit = lambda b: sum(e["damage"] for e in b[0]["log"] if e["who"] == "foe" and e["target"] != "foe")  # noqa: E731
        assert foe_hit(wet) <= foe_hit(plain)
    thorny = _hit_with("leaf", effects={"thorns": 2})[0]
    assert any("thorns" in e["text"] for e in thorny["log"])
    dizzy = _hit_with("leaf", effects={"confused": 3})[0]
    assert any("hits itself" in e["text"] for e in dizzy["log"]) and "confused" not in dizzy["effects"]
    # the pets' combos
    _, energy, _ = _hit_with("leaf", {"drowsy": 2}, energy=[10, 10])
    assert energy[1] > 10  # meadow nap
    _, _, mana = _round({**bt.start(_critter(5), [0, 1]), "marks": {"static": 2}}, [_pet("leaf"), _pet("leaf")],
                        [{"move": "attack", "slips": 0}, {"move": "guard", "slips": 0}], energy=[20, 20], mana=[0, 0])
    assert mana == [3, 3]  # lightning rod
    # ones that leave a new mark, burn, or set up the next hit
    assert "soaked" in _hit_with("splash", {"static": 2})[0]["marks"]  # thunderstorm
    assert "glowing" in _hit_with("ember", {"static": 2})[0]["marks"]  # sparkler
    hot = _hit_with("ember", {"glowing": 2})[0]
    plain_burn = _hit_with("splash", {"glowing": 2})[0]  # Splash: the gap under Glowing
    burn = lambda b: sum(e["damage"] for e in b["log"] if e["act"] == "burn")  # noqa: E731
    assert "burn" in hot["effects"] and burn(plain_burn) > 0 and burn(hot) >= 2 * burn(plain_burn) - 1  # blaze
    bubble = _hit_with("dream", {"soaked": 2})[0]
    assert bubble["skip"] >= 0 and "popped" in bubble["effects"]
    sleepy = _hit_with("splash", {"drowsy": 2})[0]
    assert "drowsy" in sleepy["marks"]


def foe_dmg(b):
    return b["max"] - b["energy"]


def test_creatures_stand_where_you_can_see_them():
    for big, b in WORLD.hexes.items():
        local = lc.generate(SEED, big)
        today = cr.at(SEED, big, 1)
        if b.special in ("camp", "town", "temple", "final"):
            assert not today
        for h, c in today.items():
            assert local.walkable(h) and h not in local.exits and h not in local.pois
            assert hx.distance(h, local.campfire) > cr.KEEP_CLEAR
            assert c.kind == wp.SPECIES_TYPES[c.species][0] and c.level >= 1
    # guardians stay put; wanderers move day to day
    big = next(b for b, h in WORLD.hexes.items() if not h.special and cr.wanderers(SEED, b, 1))
    assert cr.guardians(SEED, big) == cr.guardians(SEED, big)
    assert any(cr.wanderers(SEED, b, 1) != cr.wanderers(SEED, b, 2) for b in WORLD.hexes)


def test_creatures_get_tougher_with_each_ring():
    depth = cr._depth(SEED)
    out_there = {}
    for big, b in WORLD.hexes.items():
        if b.region == wd.HEARTLAND:
            continue
        for c in cr.at(SEED, big, 1).values():
            middle = depth[big] - 1 + cr.RING_LEVELS * (b.ring - 1)
            bump = cr.TIER_LEVELS.get(c.tier, 0)
            assert max(1, middle - cr.WIGGLE) + bump <= c.level <= min(wp.MAX_LEVEL, middle + cr.WIGGLE + bump) or c.level == wp.MAX_LEVEL
            out_there.setdefault(b.ring, []).append(c.level)
    means = [sum(v) / len(v) for _, v in sorted(out_there.items())]
    assert means == sorted(means) and max(max(v) for v in out_there.values()) > 8


def test_relics_grow_every_creature_up_to_the_cap():
    big = next(b for b, h in WORLD.hexes.items() if h.region == wd.HEARTLAND and cr.at(SEED, b, 1))
    for h, c in cr.at(SEED, big, 1).items():
        assert cr.at(SEED, big, 1, relics=2)[h].level == c.level + 2 * cr.RELIC_LEVELS
        assert cr.at(SEED, big, 1, relics=50)[h].level == wp.MAX_LEVEL
    save = sv.new_save(SEED)
    h, c = next(iter(cr.at(SEED, big, sv.day(save)).items()))
    assert sv.critter_at({**save, "temples": ["ember", "leaf"]}, big, h).level == c.level + 2 * cr.RELIC_LEVELS


def test_only_creatures_above_five_have_a_second_type():
    big = next(b for b, h in WORLD.hexes.items() if h.region == wd.HEARTLAND and cr.at(SEED, b, 1))
    for relics in range(6):
        for c in cr.at(SEED, big, 1, relics).values():
            assert (c.second is not None) == (c.level > cr.SECOND_TYPE_ABOVE) and c.second != c.kind
    # the same second type however strong it gets
    h = next(iter(cr.at(SEED, big, 1)))
    assert cr.at(SEED, big, 1, 4)[h].second == cr.at(SEED, big, 1, 5)[h].second


def test_a_creature_hits_with_its_better_type():
    one = {**bt.start(_critter(6, "shock", "cat"), [0, 1]), "second": None}
    assert bt.foe_type(one, "ember") == "shock"
    two = {**one, "second": "splash"}  # splash is very strong against ember; shock isn't
    assert bt.foe_type(two, "ember") == "splash" and bt.matchup("splash", "ember") > bt.matchup("shock", "ember")
    b, energy, _ = _round(two, [_pet("ember"), _pet("ember")], [{"move": "guard", "slips": 0}] * 2)
    assert any(line["act"] == "hit" and line["type"] == "splash" for line in b["log"] if line["who"] == "foe")


def test_the_heartland_has_enough_to_level_a_party():
    heart = [b for b, h in WORLD.hexes.items() if h.region == wd.HEARTLAND]
    today = [c for b in heart for c in cr.at(SEED, b, 1).values()]
    team = [wp.starter(t) for t in wd.REGIONS]
    xp = sum(2 * bt.xp(bt.start(c, [0, 1]), team) for c in today)  # two fighters each
    assert xp >= 5 * wp.XP_FIRST_LEVEL and all(c.level <= 2 for c in today)


def _beside_a_creature():
    """A save standing next to a creature, on a trip."""
    save = sv.start_trip({**sv.new_save(SEED), "team": [wp.starter(t, wp.MAX_LEVEL) for t in wd.REGIONS]})
    for big, b in sorted(WORLD.hexes.items()):
        local = lc.generate(SEED, big)
        for h, c in sorted(cr.at(SEED, big, sv.day(save)).items()):
            for n in hx.neighbors(h):
                if n in lc.CELL_SET and local.walkable(n) and not cr.at(SEED, big, sv.day(save)).get(n):
                    return sv._see({**save, "at": list(big), "spot": list(n)}, big, n), big, h, c
    raise AssertionError


def test_walking_into_a_creature_starts_a_battle_and_winning_walks_on():
    save, big, h, c = _beside_a_creature()
    assert sv.step_word(save, lc.to_world(big, h)) == "long"
    assert any(t.get("critter") for t in sv.local_view(save)["tiles"])
    met = sv.apply_walk(save, h)
    assert met["spot"] == save["spot"] and met["battle"]["critter"] == c.id
    with pytest.raises(sv.WanderError, match="battle"):
        sv.apply_walk(met, h)
    view = sv.battle_view(met)
    assert len(view["fighters"]) == 2 and view["looks"]["species"] == c.species
    rng = random.Random(3)
    while not met["battle"]["over"]:
        kinds = [next(iter(f["types"])) for f in sv.battle_view(met)["fighters"]]
        met = sv.battle_turn(met, [{"move": "attack", "slips": 0} for k in kinds], rng)
    assert met["battle"]["over"] == "won"
    assert c.id in met["trip"]["beaten"] and "won" in [e["kind"] for e in met["events"]]
    on = sv.end_battle(met)
    assert on["battle"] is None and on["spot"] == list(h)
    assert not sv.critter_at(on, big, h)  # beaten for the rest of the trip
    assert sv.critter_at(sv.next_day(on), big, h) or not c.guardian  # guardians are back tomorrow


def test_losing_rests_the_fighters_and_fleeing_costs_walking_energy():
    save, big, h, c = _beside_a_creature()
    met = sv.apply_walk(save, h)
    ran = sv.flee(met)
    assert ran["battle"] is None and ran["trip"]["walk"] == met["trip"]["walk"] - sv.st.FLEE_ENERGY
    # a fight you can't win
    tough = {**met, "battle": {**met["battle"], "level": 30, "energy": 999, "max": 999}}
    rng = random.Random(1)
    while not tough["battle"]["over"]:
        able = [i for i in tough["battle"]["fighters"] if tough["trip"]["pets"][i] > 0]
        tough = sv.battle_turn(tough, [{"move": "guard", "slips": 0}] * len(able), rng)
    assert tough["battle"]["over"] == "lost"
    assert all(tough["trip"]["pets"][i] == 0 for i in tough["battle"]["fighters"])
    after = sv.end_battle(tough)
    assert after["spot"] == save["spot"]
    # the next fight is the next two with energy
    assert set(sv.fighters(after)).isdisjoint(tough["battle"]["fighters"])


def test_picking_fighters():
    save = sv.start_trip({**sv.new_save(SEED), "team": [wp.starter(t) for t in wd.REGIONS]})
    assert sv.fighters(save) == [0, 1]
    picked = sv.pick_fighters(save, [3, 1])
    assert sv.fighters(picked) == [3, 1]
    tired = {**picked, "trip": {**picked["trip"], "pets": [5, 0, 5, 5, 5]}}
    assert sv.fighters(tired) == [3, 0]
    with pytest.raises(sv.WanderError):
        sv.pick_fighters(save, [0, 1, 2])


def test_a_worn_out_fighter_sits_and_the_other_picks_alone():
    team = [wp.starter("leaf", 3), wp.starter("ember", 3)]
    b = bt.start(_critter(3), [0, 1])
    with pytest.raises(ValueError, match="each fighter"):
        bt.turn(b, team, [0, 20], [{"move": "attack", "slips": 0}] * 2, random.Random(1))
    b, energy, _ = bt.turn(b, team, [0, 20], [{"move": "attack", "slips": 0}], random.Random(1))
    assert b["max"] - b["energy"] > 0 and energy[0] == 0


def test_a_trip_from_before_battles_can_still_win(monkeypatch):
    save, big, h, c = _beside_a_creature()
    met = sv.apply_walk(save, h)
    old = {**met, "trip": {k: v for k, v in met["trip"].items() if k != "beaten"}}
    won = {**old, "battle": {**old["battle"], "energy": 1}}
    kinds = [next(iter(f["types"])) for f in sv.battle_view(won)["fighters"]]
    done = sv.battle_turn(won, [{"move": "attack", "slips": 0} for k in kinds], random.Random(1))
    assert done["battle"]["over"] == "won" and c.id in done["trip"]["beaten"]


def test_each_step_says_who_did_what_and_where_everyone_stands():
    team = [wp.starter("ember", 3), wp.starter("leaf", 3)]
    b, energy, mana = _round(bt.start(_critter(3, "dream", "sheep"), [0, 1]), team,
                             [{"move": "attack", "slips": 0}, {"move": "rest", "slips": 0}], energy=[20, 20])
    acts = {(e["who"], e["act"]) for e in b["log"]}
    assert (0, "hit") in acts and (1, "rest") in acts and ("foe", "hit") in acts
    hit = next(e for e in b["log"] if e["who"] == 0)
    assert hit["target"] == "foe" and hit["type"] == "ember" and hit["damage"] > 0
    last = b["log"][-1]
    assert last["foe"] == b["energy"] and last["pets"] == {0: energy[0], 1: energy[1]} and last["mana"] == {0: mana[0], 1: mana[1]}


def test_a_new_combo_goes_in_the_combo_book_once():
    save, big, h, c = _beside_a_creature()
    met = sv.apply_walk(save, h)
    met = {**met, "battle": {**met["battle"], "energy": 999, "max": 999, "marks": {"soaked": 2}}}
    team = met["team"]
    picks = [{"move": "attack", "slips": 0}] * 2
    shock = {**met, "team": [{**m, "types": {"shock": m["level"]}} for m in team]}
    once = sv.battle_turn(shock, picks, random.Random(1))
    assert "Chain Zap" in once["combos"] and any(e["kind"] == "combo" for e in once["events"])
    again = sv.battle_turn({**once, "battle": {**once["battle"], "marks": {"soaked": 2}}}, picks, random.Random(1))
    assert not any(e["kind"] == "combo" for e in again["events"])
    book = sv.combo_book(once)
    assert len(book) == 20 and sum(1 for e in book if e["name"]) == 1


# --- level 7: mixed moves ---------------------------------------------------------


def _mixer(first="ember", second="leaf", species=None, swap="rest", level=7):
    m = {**wp.starter(first, level), "types": {first: level, second: 3}, "swaps": {swap: "mix"}, "mana": 30}
    return {**m, "species": species} if species else m


def _mix_round(pet, foe=None, partner_move="guard", energy=None, mana=None, seed=1, b=None, partner=None):
    team = [pet, partner or _pet("leaf", 7)]
    b = b or {**bt.start(foe or _critter(7, "dream", "sheep"), [0, 1]), "energy": 9999, "max": 9999}
    return _round(b, team, [{"move": "mix", "slips": 0}, {"move": partner_move, "slips": 0}], energy=energy or [40, 40], mana=mana or [30, 30], seed=seed)


def test_every_pair_and_mythical_has_a_move_at_one_price():
    pairs = {(a, b) for a in wd.REGIONS for b in wd.REGIONS if a != b}
    assert set(bt.MIX_MOVES) == pairs and len(pairs) == 20
    assert set(bt.MYTHICAL_MOVES) == set(wp.MYTHICAL)
    every = [*bt.MIX_MOVES.values(), *bt.MYTHICAL_MOVES.values()]
    assert len({m.name for m in every}) == 25 and all(len(re.sub(r"\{\w+\}", "#", m.short)) <= 28 for m in every)
    assert not {m.name for m in every} & {c.name for c in bt.COMBOS.values()}
    # a mythical uses its own, though others can have its type pair
    assert bt.mix_move(_mixer("shock", "ember")).name == "Ball Lightning"
    assert bt.mix_move(_mixer("shock", "ember", "dragon")).name == "Stormfire Breath"


@pytest.mark.parametrize("pair", sorted(bt.MIX_MOVES))
def test_every_mix_plays_through_a_whole_battle(pair):
    _plays_through(_mixer(*pair))


@pytest.mark.parametrize("species", sorted(bt.MYTHICAL_MOVES))
def test_every_mythical_mix_plays_through_a_whole_battle(species):
    first, second = wp.SPECIES_TYPES[species]
    _plays_through(_mixer(first, second, species))


def _plays_through(pet):
    for seed in range(12):
        rng = random.Random(seed)
        b = bt.start(_critter(7, rng.choice(wd.REGIONS), "sheep"), [0, 1])
        team, energy, mana = [pet, _pet("leaf", 7)], [40, 40], [30, 30]
        for _ in range(40):
            if b["over"]:
                break
            picks = [{"move": "mix" if i == 0 and mana[0] >= bt.MIX_MANA else "attack", "slips": 0} for i in b["fighters"] if energy[i] > 0]
            if energy[0] <= 0:
                picks = [{"move": "attack", "slips": 0}]
            b, energy, mana = bt.turn(b, team, energy, picks, rng, mana)
            assert 0 <= b["energy"] <= b["max"] and all(0 <= e <= 40 for e in energy)
            json.dumps(b)  # the save keeps it
        assert b["over"]


def test_a_mix_is_a_slot_with_a_card_costing_mana_and_hits_with_its_better_type():
    pet = _mixer("ember", "leaf")
    card = next(m for m in bt.moves(pet, "shock") if m["id"] == "mix")
    assert card["type"] == "ember" and card["type2"] == "leaf" and card["cost"] == bt.MIX_MANA and card["label"] == "Fire Seed"
    assert "rest" not in [m["id"] for m in bt.moves(pet)]
    with pytest.raises(ValueError, match="mana"):
        _mix_round(pet, mana=[3, 30])
    _, _, mana = _mix_round(pet)
    assert mana[0] == 30 - bt.MIX_MANA
    assert bt._mix_kind(_mixer("shock", "splash"), "ember") == "splash" and bt._mix_kind(_mixer("shock", "splash"), "splash") == "shock"
    # a mix can set off a combo for either of its types; a daredevil doesn't double it
    marked = {**bt.start(_critter(7, "dream", "sheep"), [0, 1]), "energy": 9999, "marks": {"soaked": 2}}
    step = next(s for s in _mix_round(_mixer("shock", "leaf"), b=marked)[0]["log"] if s["who"] == 0)
    assert step["combo"] == "Chain Zap"
    bold = {**_mixer("shock", "leaf", swap="guard"), "focus": "daredevil"}
    assert bt.focus_active(bold, "daredevil")
    plain_hit = next(s for s in _mix_round(_mixer("shock", "leaf"))[0]["log"] if s["who"] == 0)["damage"]
    assert next(s for s in _mix_round(bold, partner_move="attack")[0]["log"] if s["who"] == 0)["damage"] == plain_hit


def test_a_slot_can_change_hands_and_giving_up_a_focus_ends_it():
    pet = {**_mixer("ember", "leaf"), "swaps": {"rest": "attack2", "attack2": "mix"}}
    assert [m["id"] for m in bt.moves(pet)] == ["attack", "big", "guard", "focus", "cheer", "mix"]
    healer = {**_mixer("ember", "leaf", swap="healer"), "focus": "healer"}
    assert "healer" not in [m["id"] for m in bt.moves(healer)] and not bt.focus_active(healer, "healer")
    b, energy, _ = _mix_round(healer, energy=[40, 10])
    assert not any(s["act"] == "heal" and s.get("flash") for s in b["log"])
    keeps = {**wp.starter("ember", 7), "focus": "healer", "mana": 30}
    assert bt.focus_active(keeps, "healer")


def test_fire_seed_bursts_at_the_start_of_next_round():
    pet = _mixer("ember", "leaf")
    b, energy, mana = _mix_round(pet)
    assert b["energy"] == 9999 - sum(s["damage"] for s in b["log"] if s["who"] == 1) and b["later"]
    b2, _, _ = _round(b, [pet, _pet("leaf", 7)], [{"move": "guard", "slips": 0}, {"move": "guard", "slips": 0}], energy=[40, 40], mana=[26, 30])
    burst = b2["log"][0]
    assert "bursts" in burst["text"] and burst["damage"] == round(bt.pet_hit(pet["power"]) * bt.matchup("ember", "dream") * 3.5) and not b2["later"]


def test_ball_lightning_hits_again_at_the_end_of_the_round_and_goes_first():
    b = _mix_round(_mixer("shock", "ember"), foe=_critter(99, "dream", "sheep"))[0]
    mine = [s for s in b["log"] if s["who"] == 0 and s["act"] == "hit"]
    assert len(mine) == 2 and "bursts" in mine[1]["text"] and b["log"][0]["who"] == 0
    assert mine[1]["damage"] == pytest.approx(mine[0]["damage"] * 0.8, abs=1)


def test_flashfire_is_big_and_costs_energy_but_never_its_last():
    pet = _mixer("ember", "shock")
    _, energy, _ = _mix_round(pet, foe=_critter(1, "dream", "sheep"), energy=[40, 40], seed=3)
    assert energy[0] <= 40 - round(pet["energy"] * 0.08)
    b = {**bt.start(_critter(1, "dream", "sheep"), [0, 1]), "energy": 9999, "skip": 5}
    assert _mix_round(pet, b=b, energy=[1, 40])[1][0] == 1


def test_power_sprout_and_spring_shower_give_energy_back():
    b = {**bt.start(_critter(1, "dream", "sheep"), [0, 1]), "energy": 9999, "skip": 5, "start_energy": {"0": 40, "1": 40}}
    assert _mix_round(_mixer("shock", "leaf"), b=b, energy=[10, 10])[1][0] == 10 + round(40 * 0.05)
    assert _mix_round(_mixer("leaf", "splash"), b=b, energy=[10, 10], partner=_pet("leaf", 7))[1][1] == 10 + round(40 * 0.15)


def test_moon_tide_gives_both_pets_mana():
    b = {**bt.start(_critter(1, "dream", "sheep"), [0, 1]), "energy": 9999, "skip": 5}
    _, _, mana = _mix_round(_mixer("splash", "dream"), b=b, mana=[10, 10])
    assert mana == [10 - bt.MIX_MANA + 2, 12]


def test_steam_veil_makes_the_next_attack_miss():
    b = _mix_round(_mixer("splash", "ember"))[0]
    assert b["skip"] == 1 or any(s["act"] == "skip" for s in b["log"])


def test_scald_softens_its_hits():
    def taken(pet):
        total = 0
        for seed in range(40):
            # a slow, strong creature, so the Scald lands first and it shows
            b = {**bt.start(_critter(40, "dream", "sheep"), [0, 1]), "energy": 9999, "speed": 1}
            total += 66 - sum(_mix_round(pet, b=b, energy=[33, 33], seed=seed, partner_move="attack")[1])
        return total
    assert taken(_mixer("ember", "splash")) < taken(_mixer("ember", "leaf"))


def test_will_o_wisp_poppy_patch_and_living_wire_can_stop_its_attack():
    for pair, word in ((("ember", "dream"), "wisp"), (("leaf", "dream"), "poppies"), (("leaf", "shock"), "wire")):
        seen = 0
        for seed in range(30):
            b = _mix_round(_mixer(*pair), seed=seed)[0]
            if not any(word in s["text"] for s in b["log"]):
                b = _round(b, [_mixer(*pair), _pet("leaf", 7)], [{"move": "guard", "slips": 0}] * 2 if False else [{"move": "attack", "slips": 0}] * 2, energy=[40, 40], mana=[26, 30], seed=seed)[0]
            seen += any(word in s["text"] for s in b["log"])
        assert 5 < seed + 1 and seen > 5, word


def test_mirror_pool_bounces_a_hit_back_once():
    pet = _mixer("dream", "splash")
    # though it's stronger against the partner, the pool draws its next attack
    b, energy, _ = _mix_round(pet, partner_move="attack", energy=[33, 33], foe=_critter(3, "dream", "sheep"))
    assert any("bounces" in s["text"] for s in b["log"]) and energy == [33, 33] and b["mirror"] is None
    assert _mix_round(pet, partner_move="attack", seed=1)[0]["log"][0]["who"] == 0


def test_deja_vu_makes_its_partners_attack_happen_twice():
    pet = _mixer("dream", "shock")
    b = _mix_round(pet, partner_move="attack")[0]
    theirs = [s for s in b["log"] if s["who"] == 1 and s["act"] == "hit"]
    assert len(theirs) == 2 and "again" in theirs[1]["text"] and theirs[0]["damage"] == theirs[1]["damage"]
    assert b["log"][0]["who"] == 0
    big = _mix_round(pet, partner_move="big", mana=[30, 30])
    assert big[2][1] == 30 - bt.BIG_MANA  # the repeat is free
    assert len([s for s in big[0]["log"] if s["who"] == 1 and s["act"] == "hit"]) == 2
    guard = _mix_round(pet, partner_move="guard")[0]
    assert not [s for s in guard["log"] if s["who"] == 1 and s["act"] == "hit"]


def test_thunder_patter_is_three_hits_and_only_the_first_sets_off_a_combo():
    b = {**bt.start(_critter(7, "dream", "sheep"), [0, 1]), "energy": 9999, "marks": {"static": 2, "soaked": 2}}
    hits = [s for s in _mix_round(_mixer("shock", "splash"), b=b)[0]["log"] if s["who"] == 0 and s["act"] == "hit"]
    assert len(hits) == 3 and hits[0]["combo"] and not hits[1]["combo"] and not hits[2]["combo"]


def test_burning_brambles_burn_and_drain_for_three_rounds():
    pet = _mixer("leaf", "ember")
    team = [pet, _pet("leaf", 7)]
    b, energy, mana = _mix_round(pet, b={**bt.start(_critter(1, "dream", "sheep"), [0, 1]), "start_energy": {"0": 40, "1": 40}}, energy=[10, 40])
    burns = 1
    for _ in range(4):
        before = energy[0]
        b, energy, mana = _round(b, team, [{"move": "guard", "slips": 0}] * 2, energy=energy, mana=mana)
        step = [s for s in b["log"] if "brambles" in s["text"]]
        burns += bool(step)
        if step:
            burn = max(1, round(bt.pet_hit(5 + 1) * bt.BRAMBLES_BURN))
            assert step[0]["damage"] == burn and "drains" in step[0]["text"]
    assert burns == 3


def test_lucid_spark_and_rainbow_blessing_lift_next_round():
    spark = _mixer("shock", "dream")
    b = _mix_round(spark, foe=_critter(99, "dream", "sheep"))[0]
    team = [spark, _pet("leaf", 7)]
    next_round = _round(b, team, [{"move": "attack", "slips": 0}] * 2, energy=[40, 40], mana=[26, 30])[0]
    assert next_round["log"][0]["who"] in (0, 1)  # before even a very fast creature
    plain = _round({**b, "boost": None}, team, [{"move": "attack", "slips": 0}] * 2, energy=[40, 40], mana=[26, 30])[0]
    assert plain["log"][0]["who"] == "foe"
    damage = lambda r: next(s["damage"] for s in r["log"] if s["who"] == 0)  # noqa: E731
    assert damage(next_round) == pytest.approx(damage(plain) * 1.25, abs=1)
    blessing = _mixer("dream", "leaf", "unicorn")
    b, energy, mana = _mix_round(blessing, b={**bt.start(_critter(1, "dream", "sheep"), [0, 1]), "energy": 9999, "skip": 5, "start_energy": {"0": 40, "1": 40}}, energy=[10, 10], mana=[10, 10])
    assert energy[0] == 10 + round(40 * 0.1) and mana == [8, 12] and b["boost"]["first"] is False


def test_sleep_spores_leave_drowsy_and_tangled():
    b = {**bt.start(_critter(7, "dream", "sheep"), [0, 1]), "energy": 9999, "skip": 5}
    after = _mix_round(_mixer("dream", "leaf"), b=b)[0]
    assert after["marks"] == {"drowsy": 1, "tangled": 1}  # each with a round to go


def test_stormfire_breath_leaves_two_marks():
    b = _mix_round(_mixer("shock", "ember", "dragon"))[0]
    assert {"static", "glowing"} <= set(b["marks"])


def test_rising_ash_brings_back_a_worn_out_partner_or_else_hits_hard():
    pet = _mixer("ember", "dream", "phoenix")
    team = [pet, _pet("leaf", 7)]
    b = {**bt.start(_critter(1, "dream", "sheep"), [0, 1]), "energy": 9999, "skip": 5, "start_energy": {"0": 40, "1": 30}}
    back, energy, _ = bt.turn(b, team, [40, 0], [{"move": "mix", "slips": 0}], random.Random(1), [30, 30])
    assert energy[1] == round(30 * bt.REVIVE) and "back on its feet" in back["log"][0]["text"]
    assert back["energy"] < 9999  # and it still hits
    # and it fights on
    _round(back, team, [{"move": "attack", "slips": 0}] * 2, energy=energy, mana=[26, 30])
    hit = next(s for s in _mix_round(pet, b=b)[0]["log"] if s["who"] == 0)
    assert hit["damage"] == round(bt.pet_hit(pet["power"]) * bt.matchup("ember", "dream") * 2)


def test_siren_song_makes_it_hit_itself():
    pet = _mixer("splash", "shock", "mermaid")
    b = _mix_round(pet, foe=_critter(1, "dream", "sheep"))[0]
    assert "soaked" in b["marks"] and any("hits itself" in s["text"] for s in b["log"])


def test_blooming_circle_and_rain_garden_mend_both_pets_for_three_rounds():
    for pet in (_mixer("leaf", "splash", "flower_fairy"), _mixer("splash", "leaf")):
        team = [pet, _pet("leaf", 7)]
        foe = bt.start(_critter(1, "dream", "sheep"), [0, 1])
        b, energy, mana = _mix_round(pet, b={**foe, "energy": 9999, "skip": 9, "start_energy": {"0": 40, "1": 40}}, energy=[10, 10])
        rounds = 1
        for _ in range(4):
            b, energy, mana = _round(b, team, [{"move": "guard", "slips": 0}] * 2, energy=energy, mana=mana)
            rounds += any("mending" in s["text"] for s in b["log"])
        assert rounds == 3
        assert energy[0] > 10 and energy[1] > 10
    tangled = _mix_round(_mixer("leaf", "splash", "flower_fairy"))[0]
    assert tangled["marks"]["tangled"] >= 2


# --- level 9: focuses grow, one move upgrades ------------------------------------


def _nine(first="ember", focus=None, upgrades=(), second="leaf", swaps=None):
    return {**wp.starter(first, 9), "types": {first: 9, second: 5}, "focus": focus, "upgrades": list(upgrades), "swaps": swaps or {}, "mana": 30}


def _label(member, move):
    return next(m["label"] for m in bt.described_moves(member) if m["id"] == move)


def test_plus_names_for_grown_focuses_and_upgraded_moves():
    for focus in bt.FOCUSES:
        move = bt.FOCUS_MOVES[focus]
        assert _label(_nine(focus=focus), move) == bt.FOCUS_NAMES["ember"][focus] + "+"
        below = {**wp.starter("ember", 8), "types": {"ember": 8, "leaf": 4}, "focus": focus, "mana": 30}
        assert not _label(below, move).endswith("+")
    assert _label(_nine(upgrades=["attack"]), "attack") == "{ember} attack+"
    assert next(m["label"] for m in bt.moves(_nine(upgrades=["attack"]), "dream") if m["id"] == "attack") == "{ember} attack+"
    assert _label(_nine(upgrades=["big"]), "big") == "Big {ember}+"
    assert _label(_nine(upgrades=["rest"]), "rest") == "Rest+"
    mixer = _nine(upgrades=["mix"], swaps={"rest": "mix"}, second="leaf")
    assert _label(mixer, "mix") == "Fire Seed+"
    assert _label(_nine(focus="guardian"), "guard") == "Flame Guard+"
    # a focus given up doesn't grow
    assert not bt.focus_plus(_nine(focus="healer", swaps={"healer": "mix"}), "healer")


def test_attack_big_and_mix_upgrades():
    pet, plus = _nine(), _nine(upgrades=["attack", "big", "attack2"], swaps={"rest": "attack2"})
    assert [m["cost"] for m in bt.moves(plus) if m["id"] == "big"] == [bt.BIG_PLUS_MANA]
    team = lambda p: [p, _pet("leaf", 9)]  # noqa: E731
    hit = lambda p, move: next(s["damage"] for s in _round({**bt.start(_critter(9, "dream", "sheep"), [0, 1]), "energy": 9999}, team(p), [{"move": move, "slips": 0}, {"move": "guard", "slips": 0}], energy=[40, 40], mana=[30, 30])[0]["log"] if s["who"] == 0)  # noqa: E731
    assert hit(plus, "attack") == pytest.approx(hit(pet, "attack") * bt.ATTACK_PLUS, abs=1)
    assert hit(plus, "big") == pytest.approx(hit(pet, "big") * bt.BIG_PLUS / bt.BIG, abs=1)
    _, _, mana = _round(bt.start(_critter(99, "dream", "sheep"), [0, 1]), team(plus), [{"move": "big", "slips": 0}, {"move": "guard", "slips": 0}], energy=[40, 40], mana=[30, 30])
    assert mana[0] == 30 - bt.BIG_PLUS_MANA
    mixer = _nine(upgrades=["mix"], swaps={"rest": "mix"})
    card = next(m for m in bt.moves(mixer, None, 3) if m["id"] == "mix")
    assert card["cost"] == bt.MIX_PLUS_MANA and card["can"] is True
    assert _mix_round(mixer, foe=_critter(99, "dream", "sheep"))[2][0] == 30 - bt.MIX_PLUS_MANA


def test_rest_focus_cheer_and_guard_upgrades():
    assert bt.rest_cost(_nine()) == bt.REST_COST and bt.rest_cost(_nine(upgrades=["rest"])) == 0
    assert bt.focus_strength(_nine(upgrades=["focus"])) == bt.FOCUS_PLUS == bt.cheer_strength(_nine(upgrades=["cheer"]))
    b = {**bt.start(_critter(99, "dream", "sheep"), [0, 1]), "energy": 9999, "skip": 5}
    plus = [_nine(upgrades=["rest", "cheer", "focus"]), _pet("leaf", 9)]
    _, energy, mana = _round(b, plus, [{"move": "rest", "slips": 0}, {"move": "guard", "slips": 0}], energy=[1, 40], mana=[1, 30])
    assert energy[0] == 1 and mana[0] == 1 + bt.REST_PLUS_MANA
    plain_team = [_nine(), _pet("leaf", 9)]
    partner_hit = lambda team: next(s["damage"] for s in _round(b, team, [{"move": "cheer", "slips": 0}, {"move": "attack", "slips": 0}], energy=[40, 40], mana=[30, 30])[0]["log"] if s["who"] == 1)  # noqa: E731
    assert partner_hit(plus) == pytest.approx(partner_hit(plain_team) * bt.CHEER_PLUS / bt.CHEER, abs=1)
    assert bt.guard_share(_nine(upgrades=["guard"]), "dream") == bt.GUARD_PLUS
    assert bt.guard_share(_nine(), "dream") == bt.GUARD
    assert bt.guard_share(_nine(focus="guardian"), "dream") == bt.GUARD_STRONG  # guardian+: from everything


def test_healer_plus_heals_more_up_to_a_higher_limit():
    team = [_nine(focus="healer"), {**_pet("leaf", 9), "energy": 60}]
    b = {**bt.start(_critter(9, "dream", "sheep"), [0, 1]), "energy": 9999, "skip": 99, "start_energy": {"0": 37, "1": 60}}
    b, energy, mana = _round(b, team, [{"move": "attack", "slips": 0}] * 2, energy=[37, 10], mana=[30, 0])
    assert energy[1] == 10 + bt.HEAL_PLUS_ENERGY and mana[1] == bt.HEAL_PLUS_MANA
    assert (bt.HEAL_ENERGY, bt.HEAL_MANA, bt.HEAL_MAX_ENERGY, bt.HEAL_MAX_MANA) == (1, 1, 3, 3)
    assert (bt.HEAL_PLUS_ENERGY, bt.HEAL_PLUS_MANA, bt.HEAL_PLUS_MAX_ENERGY, bt.HEAL_PLUS_MAX_MANA) == (2, 2, 6, 6)
    for _ in range(9):
        b, energy, mana = _round(b, team, [{"move": "attack", "slips": 0}] * 2, energy=energy, mana=mana)
    assert energy[1] == 10 + bt.HEAL_PLUS_MAX_ENERGY and mana[1] == bt.HEAL_PLUS_MAX_MANA


def test_elementalist_plus_leaves_both_marks_for_energy_and_does_no_damage():
    pet = _nine("shock", "elementalist", second="dream")
    team = [pet, {**_pet("leaf", 9), "speed": 1}]
    b = {**bt.start(_critter(99, "ember", "fox"), [0, 1]), "energy": 9999, "skip": 5}
    after, energy, mana = _round(b, team, [{"move": "mark", "slips": 0}, {"move": "guard", "slips": 0}], energy=[40, 40], mana=[30, 30])
    step = after["log"][0]
    assert step["act"] == "mark" and step["damage"] == 0 and "static and drowsy" in step["text"]
    assert {"static", "drowsy"} <= set(after["marks"]) and after["energy"] == 9999
    assert mana[0] == 30 - bt.MARK_MANA and energy[0] == 40 - round(pet["energy"] * bt.MARK_PLUS_ENERGY)
    assert _round(b, team, [{"move": "mark", "slips": 0}, {"move": "guard", "slips": 0}], energy=[1, 40], mana=[30, 30])[1][0] == 1  # never its last
    cost = next(m for m in bt.moves(pet) if m["id"] == "mark")["icons"]["cost"]
    assert cost == {"mana": bt.MARK_MANA, "energy": bt.mark_energy(pet)}
    below = {**_nine("shock", "elementalist", second="dream"), "level": 8}
    assert bt.mark_kinds(below) == ["shock"] and bt.mark_energy(below) == 0


def _icons(member, move):
    return next(m["icons"] for m in bt.moves(member) if m["id"] == move)


def test_icons_show_at_a_glance_what_a_move_does():
    pet = _nine()
    # circles: one for each half of a plain attack, in the move's type
    assert _icons(pet, "attack")["hit"]["count"] == 2 and _icons(pet, "attack")["hit"]["types"] == ["ember"]
    assert _icons(pet, "big")["hit"]["count"] == 4
    assert _icons(_nine(upgrades=["attack"]), "attack")["hit"]["count"] == 3
    half = _icons(_mixer("dream", "leaf"), "mix")
    assert half["hit"]["count"] == 1 and half["hit"]["types"] == ["dream", "leaf"]
    # no hit, no circles
    assert "hit" not in _icons(pet, "focus") and "hit" not in _icons(_mixer("dream", "splash"), "mix")
    # haste and marks
    big = _icons(pet, "big")
    assert big["haste"] == "Fast: goes first." and big["marks"] == [{"type": "ember", "tip": "Leaves Enemy Glowing."}]
    assert "haste" not in _icons(pet, "attack")
    stormfire = _icons(_mixer("shock", "ember", "dragon"), "mix")
    assert stormfire["haste"] and {m["type"] for m in stormfire["marks"]} == {"shock", "ember"}
    # shields: colored for certain types, two for immunity, for you, your partner or both
    guard = _icons(pet, "guard")["shield"]
    assert guard["who"] == "partner" and not guard["double"] and guard["types"] == []
    wall = _icons(_nine(focus="guardian"), "guardian")["shield"]
    assert wall["double"] and wall["who"] == "partner" and wall["types"] == ["dream", "leaf"]
    veil = _icons(_mixer("splash", "ember"), "mix")["shield"]
    assert veil["who"] == "both" and veil["double"] and veil["tip"] == "Both can't be hurt."
    assert guard["tip"] == "Partner takes less damage."
    assert wall["tip"] == "Partner can't be hurt by {dream} or {leaf}."
    assert _icons(_mixer("ember", "splash"), "mix")["shield"]["who"] == "both"
    below = {**_focused("ember", "guardian", 7), "types": {"ember": 7}}
    assert _icons(below, "guard")["shield"]["types"] == ["splash"]
    mirror = _icons(_mixer("dream", "splash"), "mix")["shield"]
    assert mirror["double"] and mirror["who"] == "you"
    # costs
    assert _icons(pet, "attack")["cost"] == {} and _icons(pet, "big")["cost"] == {"mana": bt.BIG_MANA}
    assert _icons(_nine(upgrades=["big"]), "big")["cost"] == {"mana": bt.BIG_PLUS_MANA}
    flash = _mixer("ember", "shock")
    assert _icons(flash, "mix")["cost"] == {"mana": bt.MIX_MANA, "energy": round(flash["energy"] * 0.08)}
    bold = _nine(focus="daredevil")
    assert _icons(bold, "attack")["cost"] == {"energy": bt._daredevil_cost(bold)} and _icons(bold, "attack")["hit"]["count"] == 3


def _every_text():
    for group in bt.move_catalog():
        for tile in group["tiles"]:
            yield tile["name"], tile["party"]["note"]
            yield tile["name"], tile["battle"]["note"]
    for focus in bt.FOCUSES:
        for m in bt.described_moves(_focused("ember", focus)):
            yield focus, m["note"]
    for combo in bt.COMBOS.values():
        yield combo.name, combo.says


def test_text_uses_the_game_terms():
    """One word for one idea (terms.py): who's who is never just "it"."""
    banned = re.compile(r"\b(It|Its|its partner|gets? back|both pets|Both pets|creature|moves x2|No combo)\b|\b(energy|mana)\b(?![^{]*\})")
    for name, text in _every_text():
        assert not banned.search(re.sub(r"\{\w+\}", "#", text)), (name, text)
    assert {"You", "Partner", "Both", "Enemy", "Gain", "Drain", "Bounce", "Mark"} <= set(terms.TERMS)


def test_the_dictionary_covers_types_marks_and_the_map():
    assert set(terms.TYPES) == set(wd.REGIONS)
    for kind, says in terms.TYPES.items():
        a, b = bt.strong_against(kind)
        assert f"{{{a}}}" in says and f"{{{b}}}" in says  # the same as the battle's ring
    assert {m.lower() for m in terms.MARKS} == set(bt.MARKS.values())
    assert set(terms.LANDS) == {b for lands in wd.BIOMES.values() for b, _, _ in lands}
    tiles = {t for t in lc.WALKABLE | lc.BLOCKED | set(lc.GATE_TILES.values()) if not t.startswith(("pillar_", "feature_"))}
    assert tiles <= set(terms.TERRAIN), tiles - set(terms.TERRAIN)
    # what a battle's effects are called
    assert {"Asleep", "Rooted", "Scalded", "Wired", "Mending", "Brambles", "Burning", "Drenched", "Thorns", "Dizzy", "Bubble", "Sleepy"} <= set(terms.EFFECTS)


def test_one_tooltip_for_one_icon():
    """The same icon always says the same: anything more goes in the move's text."""
    seen: dict[tuple, set] = {}
    for group in bt.move_catalog():
        for tile in group["tiles"]:
            icons = tile["party"]["icons"]
            if "hit" in icons:
                seen.setdefault(("hit", icons["hit"]["count"]), set()).add(icons["hit"]["tip"])
            if "haste" in icons:
                seen.setdefault(("haste",), set()).add(icons["haste"])
            for mark in icons.get("marks", []):
                seen.setdefault(("mark", mark["type"]), set()).add(mark["tip"])
            if "shield" in icons:
                s = icons["shield"]
                seen.setdefault(("shield", s["who"], s["double"], tuple(s["types"])), set()).add(s["tip"])
    assert all(len(tips) == 1 for tips in seen.values()), seen
    assert seen[("hit", 1)] == {"Low damage."} and seen[("hit", 5)] == {"Massive damage."}


def test_poppy_patch_and_living_wire_do_the_same():
    poppy, wire = bt.MIX_MOVES["leaf", "dream"], bt.MIX_MOVES["leaf", "shock"]
    assert poppy.says == wire.says and poppy.short == wire.short and poppy.hit == wire.hit
    assert dict(poppy.effects).keys() != dict(wire.effects).keys() and list(dict(poppy.effects).values()) == list(dict(wire.effects).values())


def test_every_move_gets_icons_that_the_text_doesnt_repeat():
    for pair in bt.MIX_MOVES:
        pet = _mixer(*pair)
        for m in bt.described_moves(pet):
            assert "Costs" not in m["note"] and "Hits for" not in m["note"] and "Goes first" not in m["note"], m["label"]
            assert "cost" in m["icons"]


def test_daredevil_plus_doubles_both_types():
    assert bt._doubles(_nine(focus="daredevil"), "leaf") and bt._doubles(_nine(focus="daredevil"), "ember")
    below = {**wp.starter("ember", 8), "types": {"ember": 8, "leaf": 4}, "focus": "daredevil"}
    assert not bt._doubles(below, "leaf") and bt._doubles(below, "ember")


def test_guardian_plus_lasts_longer_and_softens_other_types():
    team = [_nine(focus="guardian"), _pet("leaf", 9)]  # ember: stops dream, leaf
    picks = [{"move": "attack", "slips": 0}] * 2
    assert bt.guardian_rounds(team[0]) == bt.GUARDIAN_PLUS_ROUNDS
    for seed in range(30):
        b = {**bt.start(_critter(9, "dream", "sheep"), [0, 1]), "energy": 9999, "round": 2}
        _, energy, _ = bt.turn(b, team, [40, 40], picks, random.Random(seed), [30, 30])
        assert energy[1] == 40  # a third round of it

    def partner_takes(guard):
        total = 0
        for seed in range(80):
            b = {**bt.start(_critter(30, "ember", "fox"), [0, 1]), "energy": 9999}  # it goes for leaf, not stopped by ember's wall
            _, energy, _ = bt.turn(b, [guard, _pet("leaf", 9)], [40, 40], picks, random.Random(seed), [30, 30])
            total += 40 - energy[1]
        return total
    assert partner_takes(team[0]) < partner_takes(_nine())


# --- level 11: a 7th slot ---------------------------------------------------------


def _eleven(focus="healer", swaps=None, extra=(), upgrades=()):
    swaps = {"rest": "attack2", "attack2": "mix"} if swaps is None else swaps
    return {**wp.starter("ember", 11), "types": {"ember": 11, "leaf": 7}, "focus": focus, "swaps": swaps, "extra": list(extra), "upgrades": list(upgrades), "mana": 30}


def test_what_can_come_back_is_everything_it_gave_up():
    pet = _eleven()  # Healer took guard's slot; rest went for attack2, which went for its mix
    assert set(bt.given_up(pet)) == {"guard", "rest", "attack2"}
    back = _eleven(extra=["rest"])
    assert set(bt.given_up(back)) == {"guard", "attack2"}
    assert bt.given_up({**wp.starter("ember", 1), "mana": 11}) == []


def test_a_seventh_slot_holds_a_move_that_works_in_battle():
    pet = _eleven(extra=["attack2"])
    ids = [m["id"] for m in bt.moves(pet)]
    assert len(ids) == 7 and ids[-1] == "attack2"
    assert len(bt.described_moves(pet)) == 7
    b = {**bt.start(_critter(11, "dream", "sheep"), [0, 1]), "energy": 9999}
    team = [pet, _pet("leaf", 11)]
    step = next(s for s in _round(b, team, [{"move": "attack2", "slips": 0}, {"move": "guard", "slips": 0}], energy=[40, 40], mana=[30, 30])[0]["log"] if s["who"] == 0)
    assert step["type"] == "leaf" and step["damage"] > 0


def test_a_move_coming_back_keeps_its_plus_and_a_focus_works_again():
    pet = _eleven(swaps={"rest": "attack2", "guard": "mix"}, extra=["guard"], upgrades=["guard"], focus=None)
    guard = next(m for m in bt.described_moves(pet) if m["id"] == "guard")
    assert guard["label"] == "Guard+"
    gone = _eleven(swaps={"healer": "mix"})
    assert not bt.focus_active(gone, "healer")
    back = _eleven(swaps={"healer": "mix"}, extra=["healer"])
    assert bt.focus_active(back, "healer") and bt.focus_plus(back, "healer")
    assert next(m for m in bt.described_moves(back) if m["id"] == "healer")["label"].endswith("+")


def test_only_moves_with_no_plus_can_upgrade():
    pet = _eleven(upgrades=["big"])
    ids = {m["id"] for m in bt.can_upgrade(pet)}
    assert "big" not in ids and "healer" not in ids  # its focus grew at level 9
    assert {"attack", "mix"} <= ids


# --- level 13: the mix the other way around ---------------------------------------


def _thirteen(first="splash", second="ember", species=None, **rest):
    base = {**wp.starter(first, 13), "types": {first: 13, second: 9}, "swaps": {"rest": "attack2", "attack2": "mix", "cheer": "mix2"}, "mana": 30}
    return {**base, **({"species": species} if species else {}), **rest}


def test_mix2_is_the_pairs_move_the_other_way_around_at_its_usual_price():
    pet = _thirteen()
    by_id = {m["id"]: m for m in bt.described_moves(pet)}
    assert by_id["mix"]["label"] == "Steam Veil" and by_id["mix2"]["label"] == "Scald"
    assert by_id["mix2"]["type"] == "ember" and by_id["mix2"]["type2"] == "splash"
    assert by_id["mix2"]["cost"] == bt.MIX_MANA and by_id["mix2"]["icons"]["cost"]["mana"] == bt.MIX_MANA
    assert by_id["mix"]["cost"] == bt.MIX_MANA
    # it can still be upgraded later on, like any other
    assert bt.mix_mana({**pet, "upgrades": ["mix2"]}, "mix2") == bt.MIX_PLUS_MANA
    # a mythical has its own both ways around
    assert bt.mix_move(_thirteen("shock", "ember", "dragon"), "mix2").name == "Golden Flame"
    assert bt.mix_move(_thirteen("shock", "ember", "dragon")).name == "Stormfire Breath"
    assert set(bt.MYTHICAL_REVERSE) == set(wp.MYTHICAL)


def test_mix2_works_in_battle():
    pet = _thirteen()
    b = {**bt.start(_critter(13, "dream", "sheep"), [0, 1]), "energy": 9999}
    after, _, mana = _round(b, [pet, _pet("leaf", 13)], [{"move": "mix2", "slips": 0}, {"move": "guard", "slips": 0}], energy=[40, 40], mana=[30, 30])
    step = next(s for s in after["log"] if s["who"] == 0)
    assert "Scald" in step["text"] and "scalded" in after["effects"] and mana[0] == 30 - bt.MIX_MANA


@pytest.mark.parametrize("pair", sorted(bt.MIX_MOVES))
def test_every_reverse_mix_plays_through_a_whole_battle(pair):
    pet = _thirteen(*pair)
    for seed in range(6):
        rng = random.Random(seed)
        b = bt.start(_critter(13, rng.choice(wd.REGIONS), "sheep"), [0, 1])
        team, energy, mana = [pet, _pet("leaf", 13)], [40, 40], [30, 30]
        for _ in range(40):
            if b["over"]:
                break
            picks = [{"move": "mix2" if i == 0 and mana[0] >= bt.MIX_MANA else "attack", "slips": 0} for i in b["fighters"] if energy[i] > 0]
            if energy[0] <= 0:
                picks = [{"move": "attack", "slips": 0}]
            b, energy, mana = bt.turn(b, team, energy, picks, rng, mana)
            json.dumps(b)
        assert b["over"]


def test_a_mix_upgrade_lowers_its_cost_and_not_its_hit():
    plain, plus = _mixer("ember", "shock"), {**_mixer("ember", "shock"), "upgrades": ["mix"]}
    damage = lambda p: next(s["damage"] for s in _mix_round(p, seed=2)[0]["log"] if s["who"] == 0)  # noqa: E731
    assert damage(plain) == damage(plus)


def test_a_new_move_can_take_the_seventh_slot():
    rec = wp.Record(swaps={"rest": "attack2"}, extra=["rest"])
    moved = wp.learn_move(rec, "rest", "mix2")
    assert moved.extra == ["mix2"] and moved.swaps == {"rest": "attack2"}
    assert wp.learn_move(rec, "cheer", "mix2").swaps == {"rest": "attack2", "cheer": "mix2"}


def _myth(species, **rest):
    first, second = wp.SPECIES_TYPES[species]
    return _thirteen(first, second, species, **rest)


def _myth_round(species, b=None, foe=None, partner_move="guard", energy=None, mana=None, seed=1, team=None):
    team = team or [_myth(species), {**_pet("leaf", 13), "progress": (100, 1000)}]
    b = b or {**bt.start(foe or _critter(13, "dream", "sheep"), [0, 1]), "energy": 9999, "max": 9999}
    return _round(b, team, [{"move": "mix2", "slips": 0}, {"move": partner_move, "slips": 0}], energy=energy or [40, 40], mana=mana or [30, 30], seed=seed)


@pytest.mark.parametrize("species", sorted(set(bt.MYTHICAL_REVERSE) - {"phoenix"}))
def test_every_typed_mythical_reverse_plays_through_a_battle(species):
    for seed in range(6):
        rng = random.Random(seed)
        pet = _myth(species)
        b = bt.start(_critter(13, rng.choice(wd.REGIONS), "sheep"), [0, 1])
        team, energy, mana = [pet, _pet("leaf", 13)], [40, 40], [30, 30]
        for _ in range(40):
            if b["over"]:
                break
            use = not bt.used_up(b, 0, pet, "mix2") and mana[0] >= bt.MIX_MANA
            picks = [{"move": "mix2" if i == 0 and use else "attack", "slips": 0} for i in b["fighters"] if energy[i] > 0]
            if energy[0] <= 0:
                picks = [{"move": "attack", "slips": 0}]
            b, energy, mana = bt.turn(b, team, energy, picks, rng, mana)
            json.dumps(b)
        assert b["over"]


def test_golden_flame_pays_coins_only_when_it_wins():
    alive = _myth_round("dragon")[0]
    assert not alive.get("coins")
    b = {**bt.start(_critter(13, "dream", "sheep"), [0, 1]), "energy": 1, "max": 34}
    won = _myth_round("dragon", b=b)[0]
    assert won["over"] == "won" and won["coins"] == bt.GOLDEN_COINS + 13


def test_undertow_is_fast_and_both_drain_half_the_damage():
    team = [_myth("mermaid"), _pet("leaf", 13)]
    b = {**bt.start(_critter(99, "dream", "sheep"), [0, 1]), "energy": 9999, "skip": 5, "start_energy": {"0": 60, "1": 60}}
    after, energy, _ = _myth_round("mermaid", b=b, team=team, energy=[10, 10])
    step = after["log"][0]
    assert step["who"] == 0 and "drain" in step["text"]
    each = round(step["damage"] * 0.5) // 2
    assert energy == [10 + each, 10 + each]


def test_sanctuary_keeps_both_safe_two_rounds_and_is_once_a_battle():
    team = [_myth("unicorn"), _pet("leaf", 13)]
    picks = [{"move": "attack", "slips": 0}] * 2
    for seed in range(20):
        b, energy, mana = _myth_round("unicorn", foe=_critter(30, "dream", "sheep"), team=team, seed=seed)
        assert energy == [40, 40]
        b, energy, mana = _round(b, team, picks, energy=energy, mana=mana, seed=seed)
        assert energy == [40, 40]
    with pytest.raises(ValueError, match="once a battle"):
        _round(b, team, [{"move": "mix2", "slips": 0}, {"move": "attack", "slips": 0}], energy=energy, mana=mana)
    assert next(m for m in bt.battle_moves(b, 0, team[0], 30) if m["id"] == "mix2")["can"] is False


def test_nectar_gifts_partner_xp_once_a_battle():
    team = [_myth("flower_fairy"), {**_pet("leaf", 13), "progress": (100, 1000)}]
    after = _myth_round("flower_fairy", team=team)[0]
    assert after["gift_xp"] == [1, 100]
    with pytest.raises(ValueError, match="once a battle"):
        _round(after, team, [{"move": "mix2", "slips": 0}, {"move": "attack", "slips": 0}], energy=[40, 40], mana=[30, 30])
    # a fully leveled partner has nothing to gain
    full = [_myth("flower_fairy"), {**_pet("leaf", 13), "progress": None}]
    assert "gift_xp" not in _myth_round("flower_fairy", team=full)[0]


def test_reborn_is_passive_and_brings_a_worn_out_pet_back_once():
    pet = _myth("phoenix")
    card = next(m for m in bt.moves(pet) if m["id"] == "mix2")
    assert card["passive"] and card["icons"]["cost"] == {} and bt.has_reborn(pet)
    assert "mix2" not in {m["id"] for m in bt.can_upgrade(pet)}
    team = [pet, _pet("leaf", 13)]
    picks = [{"move": "attack", "slips": 0}] * 2
    back = False
    for seed in range(40):
        b = {**bt.start(_critter(50, "splash", "dog"), [0, 1]), "energy": 9999, "reborn": [0], "start_energy": {"0": 40, "1": 40}}
        after, energy, _ = bt.turn(b, team, [1, 1], picks, random.Random(seed), [30, 30])
        if "reborn_used" in after:
            back = True
            assert energy[0] == 40 and after["reborn"] == [] and after["over"] != "lost"
        # with no second chance left, it stays down
        again = {**b, "reborn": []}
        assert "reborn_used" not in bt.turn(again, team, [1, 1], picks, random.Random(seed), [30, 30])[0]
    assert back


# --- energy in battles ------------------------------------------------------------


def _full_of(b, **rest):
    return {**b, "energy": 9999, "skip": 99, **rest}


def test_a_pets_energy_going_in_is_the_most_it_can_have_in_that_battle():
    team = [_mixer("shock", "leaf"), _pet("leaf", 7)]
    picks = [{"move": "mix", "slips": 0}, {"move": "guard", "slips": 0}]
    b = _full_of(bt.start(_critter(1, "dream", "sheep"), [0, 1]))
    # coming in at 10 of its full energy: 10 is as high as it goes
    after, energy, _ = bt.turn(b, team, [10, 12], picks, random.Random(1), [30, 30])
    assert after["start_energy"] == {"0": 10, "1": 12} and energy[0] == 10
    # hurt in this battle, it can gain back: a percentage of what it came in with
    hurt = {**after, "start_energy": {"0": 40, "1": 12}}
    _, energy, _ = bt.turn(hurt, team, [20, 12], picks, random.Random(1), [30, 30])
    assert energy[0] == 20 + round(40 * 0.05)
    # and no further than it came in with
    near = {**after, "start_energy": {"0": 21, "1": 12}}
    assert bt.turn(near, team, [20, 12], picks, random.Random(1), [30, 30])[1][0] == 21


def test_every_energy_gain_stops_at_battle_energy():
    """No way to come out of a fight with more than you went in with."""
    for pair in [*bt.MIX_MOVES]:
        pet = _mixer(*pair)
        team = [pet, _pet("leaf", 7)]
        b = bt.start(_critter(1, "dream", "sheep"), [0, 1])
        energy, mana = [8, 8], [30, 30]
        for _ in range(12):
            if b["over"]:
                break
            picks = [{"move": "mix" if i == 0 and mana[0] >= 4 else "guard", "slips": 0} for i in b["fighters"] if energy[i] > 0]
            if energy[0] <= 0:
                picks = [{"move": "attack", "slips": 0}]
            b, energy, mana = bt.turn({**b, "energy": 9999, "over": None}, team, energy, picks, random.Random(1), mana)
            assert energy[0] <= 8 and energy[1] <= 8, pair
    healer = [_nine(focus="healer"), _pet("leaf", 9)]
    b = bt.start(_critter(1, "dream", "sheep"), [0, 1])
    _, energy, _ = bt.turn(b, healer, [5, 5], [{"move": "attack", "slips": 0}] * 2, random.Random(1), [30, 30])
    assert energy[1] <= 5


def test_mana_can_still_rise_above_where_it_started():
    team = [_pet("ember", 7), _pet("leaf", 7)]
    b = _full_of(bt.start(_critter(1, "dream", "sheep"), [0, 1]))
    _, _, mana = bt.turn(b, team, [20, 20], [{"move": "rest", "slips": 0}, {"move": "guard", "slips": 0}], random.Random(1), [1, 1])
    assert mana[0] == 1 + bt.REST_MANA


def test_rest_costs_energy_for_mana_and_rest_plus_is_free():
    team = [_pet("ember", 7), _pet("leaf", 7)]
    b = _full_of(bt.start(_critter(1, "dream", "sheep"), [0, 1]))
    picks = [{"move": "rest", "slips": 0}, {"move": "guard", "slips": 0}]
    _, energy, mana = bt.turn(b, team, [20, 20], picks, random.Random(1), [1, 1])
    assert energy[0] == 20 - bt.REST_COST and mana[0] == 1 + bt.REST_MANA
    assert bt.turn(b, team, [1, 20], picks, random.Random(1), [1, 1])[1][0] == 1  # never its last
    plus = [{**_pet("ember", 7), "upgrades": ["rest"]}, _pet("leaf", 7)]
    _, energy, mana = bt.turn(b, plus, [20, 20], picks, random.Random(1), [1, 1])
    assert energy[0] == 20 and mana[0] == 1 + bt.REST_PLUS_MANA
    assert _icons(_pet("ember", 7), "rest")["cost"] == {"energy": bt.REST_COST} and _icons(plus[0], "rest")["cost"] == {}
    assert next(m for m in bt.described_moves(plus[0]) if m["id"] == "rest")["label"] == "Rest+"


# --- levels 15 to 19: a third type, and mixes of any pair -----------------------------


def _triple(extra=(), swaps=None, upgrades=(), level=19):
    base = wp.starter("ember", level)
    return {**base, "types": {"ember": level, "leaf": level - 4, "shock": level - 14}, "swaps": swaps or {"cheer": "attack2", "focus": "mix"},
            "extra": list(extra), "upgrades": list(upgrades), "mana": 40}


def test_a_third_attack_hits_in_its_type():
    pet = _triple(swaps={"cheer": "attack2", "focus": "mix", "rest": "attack3"}, upgrades=["attack3"])
    card = next(m for m in bt.described_moves(pet) if m["id"] == "attack3")
    assert card["label"] == "{shock} attack+" and card["icons"]["hit"]["count"] == 3 and card["icons"]["hit"]["types"] == ["shock"]
    b = {**bt.start(_critter(19, "splash", "dog"), [0, 1]), "energy": 9999}
    step = next(s for s in _round(b, [pet, _pet("leaf", 19)], [{"move": "attack3", "slips": 0}, {"move": "guard", "slips": 0}], energy=[60, 60], mana=[40, 40])[0]["log"] if s["who"] == 0)
    assert step["type"] == "shock"


def test_any_pair_of_its_types_can_be_a_mix():
    assert bt.mix_id(("ember", "shock")) == "mix:ember:shock" and bt.is_mix("mix:ember:shock") and bt.is_mix("mix2") and not bt.is_mix("attack")
    pet = _triple(extra=["mix:shock:leaf"])
    by_id = {m["id"]: m for m in bt.described_moves(pet)}
    assert by_id["mix:shock:leaf"]["label"] == bt.MIX_MOVES["shock", "leaf"].name
    assert by_id["mix:shock:leaf"]["type"] == "shock" and by_id["mix:shock:leaf"]["type2"] == "leaf"
    assert by_id["mix:shock:leaf"]["icons"]["hit"]["types"] == ["shock", "leaf"]
    assert bt._mix_kind(pet, "ember", "mix:shock:leaf") == bt._mix_kind(pet, "ember", "mix:shock:leaf")
    b = {**bt.start(_critter(19, "dream", "sheep"), [0, 1]), "energy": 9999}
    team = [pet, _pet("leaf", 19)]
    after, _, mana = _round(b, team, [{"move": "mix:shock:leaf", "slips": 0}, {"move": "guard", "slips": 0}], energy=[60, 60], mana=[40, 40])
    assert mana[0] == 40 - bt.MIX_MANA and any(bt.MIX_MOVES["shock", "leaf"].name in s["text"] for s in after["log"])


def test_what_mixes_are_missing():
    pet = {**_triple(), "swaps": {"cheer": "attack2", "focus": "mix", "guard": "mix2"}}
    assert set(bt.mixes_missing(pet, "shock")) == {"mix:ember:shock", "mix:shock:ember", "mix:leaf:shock", "mix:shock:leaf"}
    assert len(bt.mixes_missing(pet)) == 4
    has_one = {**pet, "extra": ["mix:ember:shock"]}
    assert len(bt.mixes_missing(has_one)) == 3 and "mix:ember:shock" not in bt.mixes_missing(has_one)


def test_every_slot_shows_eight_moves_and_they_all_work():
    pet = _triple(extra=["guard", "mix:shock:ember"], swaps={"cheer": "attack2", "focus": "mix", "rest": "attack3"}, upgrades=["attack3"])
    assert len(bt.moves(pet)) == 8 and len(bt.described_moves(pet)) == 8
    for m in bt.moves(pet, "dream"):
        if m.get("can") is False or m.get("passive"):
            continue
        b = {**bt.start(_critter(19, "dream", "sheep"), [0, 1]), "energy": 9999}
        bt.turn(b, [pet, _pet("leaf", 19)], [60, 60], [{"move": m["id"], "slips": 0}, {"move": "guard", "slips": 0}], random.Random(1), [40, 40])


# --- level 21: capstones ---------------------------------------------------------


def _bench_round(bench, foe=None, moves=None, energy=None, mana=None, seed=1, team=None):
    team = team or [_pet("ember", 21), _pet("leaf", 21)]
    b = {**bt.start(foe or _critter(21, "dream", "sheep"), [0, 1], bench), "energy": 9999, "max": 9999}
    return bt.turn(b, team, energy or [60, 60], moves or [{"move": "attack", "slips": 0}] * 2, random.Random(seed), mana or [30, 30])


def test_every_ordered_pair_has_a_capstone():
    pairs = {(a, c) for a in wd.REGIONS for c in wd.REGIONS if a != c}
    assert set(bt.CAPSTONES) == pairs and len({c.key for c in bt.CAPSTONES.values()}) == 20
    assert len({c.name for c in bt.CAPSTONES.values()}) == 20
    pet = _triple()
    assert bt.capstone_pairs(pet) == [("ember", "leaf"), ("ember", "shock"), ("leaf", "shock")]


def test_the_bench_helps_when_not_fighting_and_never_twice():
    team = [{**_pet("leaf"), "capstone": None}, {**_pet("ember"), "capstone": "ember:shock"}, {**_pet("dream"), "capstone": "ember:shock"}, {**_pet("shock"), "capstone": "shock:dream"}]
    assert bt.bench_keys(team, [0, 3]) == ["battle_cry"]  # the same one twice counts once
    assert set(bt.bench_keys(team, [0, 1])) == {"battle_cry", "bright_idea"}
    assert bt.bench_keys(team, [1, 2]) == ["bright_idea"]  # a fighter's own doesn't count


def test_capstones_that_start_a_battle_marked():
    for key, mark in bt.CAPSTONE_STARTS.items():
        b = {**bt.start(_critter(21, "ember", "fox"), [0, 1], (key,)), "skip": 5, "energy": 9999}
        after = bt.turn(b, [_pet("leaf", 21), _pet("leaf", 21)], [60, 60], [{"move": "guard", "slips": 0}] * 2, random.Random(1), [30, 30])[0]
        assert mark in after["marks"] or mark == "drowsy" or any(mark in s["text"] for s in after["log"]), key


def test_steam_curtain_and_tide_pool_help_at_the_start():
    assert any(s["act"] == "skip" for s in _bench_round(("steam_curtain",))[0]["log"])
    _, _, mana = _bench_round(("tide_pool",), moves=[{"move": "guard", "slips": 0}] * 2, mana=[10, 10])
    assert mana == [10 + bt.TIDE_POOL_MANA] * 2


def test_clear_spring_and_steady_growth_add_up_to_their_limit():
    team = [_pet("ember", 21), _pet("leaf", 21)]
    picks = [{"move": "guard", "slips": 0}] * 2
    for key in ("clear_spring", "steady_growth"):
        b = {**bt.start(_critter(9, "dream", "sheep"), [0, 1], (key,)), "energy": 9999, "skip": 99, "start_energy": {"0": 60, "1": 60}}
        energy, mana = [10, 10], [10, 10]
        for _ in range(6):
            b, energy, mana = bt.turn(b, team, energy, picks, random.Random(1), mana)
        if key == "clear_spring":
            assert energy == [10 + bt.BENCH_MAX] * 2
        else:
            assert mana == [10 + bt.BENCH_MAX] * 2


def test_battle_cry_and_dry_tinder_hit_harder():
    plain = next(s["damage"] for s in _bench_round(())[0]["log"] if s["who"] == 0)
    cry = next(s["damage"] for s in _bench_round(("battle_cry",))[0]["log"] if s["who"] == 0)
    assert cry == pytest.approx(plain * bt.BATTLE_CRY, abs=1)
    b = {**bt.start(_critter(21, "dream", "sheep"), [0, 1]), "marks": {"glowing": 2}, "energy": 9999, "skip": 9}
    burn = lambda bench: next(s["damage"] for s in bt.turn({**b, "bench": list(bench)}, [_pet("leaf", 21), _pet("leaf", 21)], [60, 60], [{"move": "guard", "slips": 0}] * 2, random.Random(1), [30, 30])[0]["log"] if s["act"] == "burn")  # noqa: E731
    assert burn(("dry_tinder",)) > burn(())


def test_softer_hits_from_the_bench():
    def taken(bench):
        total = 0
        for seed in range(200):
            # (a very strong creature: on small hits a 10% cut can round away)
            _, energy, _ = _bench_round(bench, foe=_critter(60, "splash", "dog"), seed=seed)
            total += 120 - sum(energy)
        return total
    plain = taken(())
    for key in ("deep_roots", "hot_spring", "calm_waters"):
        assert taken((key,)) < plain, key


def test_sweet_dreams_thorn_hedge_second_thought_and_quick_start():
    assert any("sweet dreams" in s["text"] for seed in range(80) for s in _bench_round(("sweet_dreams",), seed=seed)[0]["log"])
    assert any("thorn hedge" in s["text"] for seed in range(40) for s in _bench_round(("thorn_hedge",), seed=seed)[0]["log"])
    assert any("again" in s["text"] for seed in range(80) for s in _bench_round(("second_thought",), seed=seed)[0]["log"])
    fast = _bench_round(("quick_start",), foe=_critter(99, "dream", "sheep"))[0]
    assert fast["log"][0]["who"] in (0, 1)
    assert _bench_round((), foe=_critter(99, "dream", "sheep"))[0]["log"][0]["who"] == "foe"


def test_quick_start_lasts_two_rounds():
    team = [_pet("ember", 21), _pet("leaf", 21)]
    picks = [{"move": "guard", "slips": 0}] * 2
    b = {**bt.start(_critter(99, "dream", "sheep"), [0, 1], ("quick_start",)), "energy": 9999}
    for _ in range(2):
        b, _, _ = bt.turn(b, team, [60, 60], picks, random.Random(1), [30, 30])
        assert b["log"][0]["who"] in (0, 1)
    b, _, _ = bt.turn(b, team, [60, 60], picks, random.Random(1), [30, 30])
    assert b["log"][0]["who"] == "foe"


def test_a_softer_hit_always_takes_off_at_least_one():
    # an even creature's hit on a level 21 pet is small enough for 10% to round away
    def hit(bench, foe_kind="ember"):
        team = [wp.starter("ember", 21), wp.starter("ember", 21)]
        b = {**bt.start(_critter(21, foe_kind, "fox"), [0, 1], bench), "energy": 9999, "effects": {"hot_spring": 2} if "hot_spring" in bench else {}, "round": 1}
        return next(s["damage"] for s in bt.turn(b, team, [60, 60], [{"move": "attack", "slips": 0}] * 2, random.Random(1), [30, 30])[0]["log"] if s["who"] == "foe")
    plain = hit(())
    assert plain > 1 and hit(("deep_roots",)) <= plain - 1
    assert hit(("deep_roots", "hot_spring")) <= plain - 1


def test_bright_idea_lowers_costs():
    pet = {**_pet("ember", 21), "bright": True}
    assert bt.big_mana(pet) == bt.BIG_MANA - 1 and bt.mix_mana(pet) == bt.MIX_MANA - 1


def test_a_used_up_passive_is_marked_as_spent():
    pet = _nine(focus="guardian")
    b = {**bt.start(_critter(9, "dream", "sheep"), [0, 1]), "round": bt.GUARDIAN_PLUS_ROUNDS}
    wall = next(m for m in bt.battle_moves(b, 0, pet, 30) if m["id"] == "guardian")
    assert wall["spent"]
    early = {**b, "round": bt.GUARDIAN_PLUS_ROUNDS - 1}
    assert not next(m for m in bt.battle_moves(early, 0, pet, 30) if m["id"] == "guardian")["spent"]
    healer = _nine(focus="healer")
    done = {**b, "healed": {"0:energy": bt.HEAL_PLUS_MAX_ENERGY, "0:mana": bt.HEAL_PLUS_MAX_MANA}}
    assert next(m for m in bt.battle_moves(done, 0, healer, 30) if m["id"] == "healer")["spent"]
    assert next(m for m in bt.moves(_pet("ember", 7)) if m["id"] == "guard")["note"].startswith("Takes Partner's hits")


def test_a_creature_goes_for_the_pet_its_strongest_against_then_the_weaker():
    team = [_pet("leaf", 7), _pet("ember", 7)]  # splash is strong against ember, weak against leaf
    picks = [{"move": "guard", "slips": 0}, {"move": "guard", "slips": 0}]
    b = {**bt.start(_critter(7, "splash", "dog"), [0, 1]), "energy": 9999}
    assert bt._foe_target(b, team, [30, 30], [0, 1]) == 1
    # even if the other is nearly out
    assert bt._foe_target(b, team, [1, 30], [0, 1]) == 1
    even = [_pet("ember", 7), _pet("ember", 7)]
    assert bt._foe_target(b, even, [30, 10], [0, 1]) == 1 and bt._foe_target(b, even, [10, 30], [0, 1]) == 0
    assert picks


def test_the_creatures_next_move_shows_above_it():
    team = [_pet("leaf", 7), _pet("ember", 7)]
    b = bt.start(_critter(7, "splash", "dog"), [0, 1])
    intent = bt.foe_intent(b, team, [30, 30])
    assert intent["kind"] == "attack" and intent["type"] == "splash" and intent["target"] == 1 and intent["name"] == team[1]["name"]
    assert team[1]["name"] in intent["tip"]
    # a stronger hit shows in the circles
    hard = bt.foe_intent(bt.start(_critter(30, "splash", "dog"), [0, 1]), team, [30, 30])
    assert hard["count"] > intent["count"]
    for stopped in ({**b, "skip": 1}, {**b, "effects": {"doze": 1}}):
        skip = bt.foe_intent(stopped, team, [30, 30])
        assert skip["name"] == "Skipping turn" and "count" not in skip
    # what it tries, not how it turns out: a sanctuary or a mark doesn't change it
    assert bt.foe_intent({**b, "effects": {"sanctuary": 1}}, team, [30, 30])["kind"] == "attack"
    assert bt.foe_intent({**b, "marks": {"drowsy": 1}}, team, [30, 30])["kind"] == "attack"
    assert bt.foe_intent({**b, "over": "won"}, team, [30, 30]) is None
    # it says what will really happen, in a real round
    after, _, _ = bt.turn(b, team, [30, 30], [{"move": "guard", "slips": 0}, {"move": "attack", "slips": 0}], random.Random(1), [30, 30])
    hit = next(s for s in after["log"] if s["who"] == "foe")
    assert hit["target"] == intent["target"] or hit["target"] == 0  # (or whoever guards)


# --- the creature's own moves -----------------------------------------------------


def _script_with(level, move, second=None):
    """A battle whose creature (some seed) tries `move` in its first rounds, and the round."""
    for seed in range(400):
        c = cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", level, False, seed, second)
        b = {**bt.start(c, [0, 1]), "energy": 9999, "max": 9999}
        script = bt.foe_script(b, 8)
        if move in script:
            return b, script.index(move) + 1
    raise AssertionError(move)


def _play_to(b, team, round_no, energy=None):
    """Up to just before a round."""
    energy, mana = energy or [m["energy"] for m in team], [m["mana"] for m in team]
    for _ in range(round_no - 1):
        b, energy, mana = bt.turn(b, team, energy, [{"move": "attack", "slips": 0}] * sum(1 for e in energy if e > 0), random.Random(1), mana)
        b = {**b, "energy": 9999}
    return b, energy, mana


def test_moves_come_by_level_and_never_two_in_a_row():
    for level, move in ((8, "heavy"), (14, "harden"), (17, "lull"), (20, "sweep")):
        assert move not in {m for s in range(40) for m in bt.foe_script(bt.start(cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", level - 1, False, s), [0, 1]), 12)}
        assert _script_with(level, move)
    assert "mark" not in {m for s in range(40) for m in bt.foe_script(bt.start(cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", 12, False, s), [0, 1]), 12)}  # it has no second type
    assert _script_with(11, "mark", "ember")
    for seed in range(60):
        b = bt.start(cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", 21, False, seed, "ember"), [0, 1])
        script = bt.foe_script(b, 20)
        assert script[0] == "attack" and script == bt.foe_script(b, 20) and script.count("lull") <= 1
        assert all(a == "attack" or b_ == "attack" for a, b_ in zip(script, script[1:]))


def test_heavy_blow_and_sweep():
    team = [_pet("leaf", 21), _pet("leaf", 21)]
    picks = [{"move": "guard", "slips": 0}] * 2
    b, round_no = _script_with(8, "heavy")
    b, energy, mana = _play_to(b, team, round_no, [90, 90])
    intent = bt.foe_intent(b, team, energy)
    assert intent["kind"] == "attack"
    after, _, _ = bt.turn(b, team, energy, [{"move": "attack", "slips": 0}] * 2, random.Random(1), mana)
    step = next(s for s in after["log"] if s["who"] == "foe" and s.get("target") in (0, 1))
    assert "slams" in step["text"] and step["damage"] == max(1, round(bt.enemy_hit(8) * bt.matchup("dream", "leaf") * bt.HEAVY_BLOW))
    b, round_no = _script_with(20, "sweep")
    b, energy, mana = _play_to(b, team, round_no, [90, 90])
    assert bt.foe_intent(b, team, energy)["name"] == "Both"
    after, _, _ = bt.turn(b, team, energy, picks, random.Random(1), mana)
    assert {s["target"] for s in after["log"] if "sweeps" in s["text"]} == {0, 1}
    assert picks


def test_mark_then_a_stronger_hit():
    team = [_pet("leaf", 21), _pet("leaf", 21)]
    b, round_no = _script_with(11, "mark", "ember")
    b, energy, mana = _play_to(b, team, round_no, [90, 90])
    assert bt.foe_intent(b, team, energy)["name"].startswith("Marking")
    after, energy, mana = bt.turn(b, team, energy, [{"move": "attack", "slips": 0}] * 2, random.Random(1), mana)
    assert any(s["act"] == "mark" for s in after["log"]) and after["pet_marks"]
    aim = int(next(iter(after["pet_marks"])))
    energy = [90, 90]
    hit, _, _ = bt.turn({**after, "energy": 9999}, team, energy, [{"move": "attack", "slips": 0}] * 2, random.Random(1), mana)
    step = next((s for s in hit["log"] if "Marked!" in s["text"]), None)
    assert step and step["target"] == aim and not hit["pet_marks"]


def test_harden_halves_hits_that_round():
    team = [_pet("leaf", 21), _pet("leaf", 21)]
    b, round_no = _script_with(14, "harden")
    b, energy, mana = _play_to(b, team, round_no, [90, 90])
    assert bt.foe_intent(b, team, energy)["name"] == "Blocking"
    picks = [{"move": "attack", "slips": 0}] * 2
    hard, _, _ = bt.turn(b, team, energy, picks, random.Random(1), mana)
    soft_plain, _, _ = bt.turn({**b, "seed": b["seed"], "round": 0}, team, energy, picks, random.Random(1), mana)  # round 1: a plain attack
    hit = lambda r: next(s["damage"] for s in r["log"] if s["who"] == 0)  # noqa: E731
    assert hit(hard) == pytest.approx(hit(soft_plain) * bt.HARDENED, abs=1)
    assert any("braces" in s["text"] for s in hard["log"])


def test_lull_puts_a_pet_to_sleep_for_a_round():
    team = [_pet("leaf", 21), _pet("leaf", 21)]
    b, round_no = _script_with(17, "lull")
    b, energy, mana = _play_to(b, team, round_no, [90, 90])
    assert bt.foe_intent(b, team, energy)["name"].startswith("Lulling")
    after, energy, mana = bt.turn(b, team, energy, [{"move": "attack", "slips": 0}] * 2, random.Random(1), mana)
    who = after["lulled"]
    assert who in (0, 1) and bt.asleep_now(after, energy) == who
    other = 1 - who
    hit, _, _ = bt.turn({**after, "energy": 9999}, team, energy, [{"move": "attack", "slips": 0}], random.Random(1), mana)
    assert not [s for s in hit["log"] if s["who"] == who and s["act"] == "hit"] and [s for s in hit["log"] if s["who"] == other and s["act"] == "hit"]
    assert hit["lulled"] is None or hit["lulled"] != who
    # with no one else standing, it wakes rather than leave nothing to do
    assert bt.asleep_now({**after, "lulled": 0}, [10, 0]) is None


def test_strong_creatures_shake_off_losing_turn_after_turn():
    team = [_pet("leaf", 21), _pet("leaf", 21)]
    picks = [{"move": "guard", "slips": 0}] * 2
    weak = {**bt.start(_critter(9, "dream", "sheep"), [0, 1]), "skip": 2, "energy": 9999}
    strong = {**bt.start(_critter(10, "dream", "sheep"), [0, 1]), "skip": 2, "energy": 9999}
    for b, second_lost in ((weak, True), (strong, False)):
        first, energy, mana = bt.turn(b, team, [90, 90], picks, random.Random(1), [30, 30])
        assert any(s["act"] == "skip" for s in first["log"])
        then, _, _ = bt.turn(first, team, energy, picks, random.Random(1), mana)
        assert any(s["act"] == "skip" for s in then["log"]) == second_lost
    assert bt._lost_chance({"level": 14}, 0.5) == 0.5 and bt._lost_chance({"level": 15}, 0.5) == 0.25


# --- XP and tougher creatures ------------------------------------------------------


def test_harder_creatures_pay_more_xp():
    team = [wp.starter("leaf", 7), wp.starter("ember", 7)]
    pay = lambda level, tier="": bt.xp({"level": level, "fighters": [0, 1], "tier": tier}, team)  # noqa: E731
    assert pay(7) == 100 and pay(14) == round(100 * 2 ** bt.XP_STEEPNESS) and pay(3) < 50
    assert pay(7) < pay(8) < pay(10)
    assert pay(7, "tough") == 150 and pay(7, "champion") == 300 and pay(7, "boss") == 500


def test_tiers_are_stronger_rarer_and_keep_their_seed():
    team = [wp.starter("leaf", 14), wp.starter("leaf", 14)]
    plain = cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", 14, False, 1)
    energies = {t: bt.start(cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", 14, False, 1, None, t), [0, 1])["energy"] for t in ("", "tough", "champion", "boss")}
    assert energies[""] < energies["tough"] < energies["champion"] < energies["boss"]
    hits = {t: bt._foe_hit({"level": 14, "tier": t}) for t in ("", "tough", "champion", "boss")}
    assert hits[""] < hits["tough"] < hits["champion"] < hits["boss"]
    assert plain and team
    seen = Counter()
    for seed in range(4000):
        c = cr._grown(cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", 8, False, seed), 0)
        seen[c.tier] += 1
        assert c.level == 8 + cr.TIER_LEVELS.get(c.tier, 0)
    assert 0.1 < seen["tough"] / 4000 < 0.2 and 0.01 < seen["champion"] / 4000 < 0.05
    assert not {cr._grown(cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", 3, False, s), 0).tier for s in range(300)} - {""}  # early going stays easy
    assert bt.tier_coins({"tier": "", "level": 9}) == 0 and bt.tier_coins({"tier": "tough", "level": 9}) == 0
    assert bt.tier_coins({"tier": "champion", "level": 9}) == 19 and bt.tier_coins({"tier": "boss", "level": 9}) == 34


def test_a_temple_boss_guards_the_relic():
    region = "ember"
    temple = next(h for h, b in WORLD.hexes.items() if b.special == "temple" and b.region == region)
    tale = sv.st.STORIES[region]
    team = [{**wp.starter("ember", 21), "energy": 900}, {**wp.starter("leaf", 21), "energy": 900}]
    save = sv.start_trip({**sv.new_save(SEED), "team": team, "items": {tale.key: 1}})
    save = {**save, "at": list(temple)}
    boss = cr.temple_boss(SEED, region, temple, 0)
    assert boss.tier == "boss" and boss.level == cr.BOSS_LEVEL and boss.kind == region
    assert cr.temple_boss(SEED, region, temple, 2).level == cr.BOSS_LEVEL + 2 * cr.RELIC_LEVELS
    assert boss.id.startswith("boss:")
    fight = sv._start_battle(save, boss)
    assert fight["battle"]["tier"] == "boss" and fight["battle"]["energy"] == bt.start(boss, [0, 1])["energy"] > bt.enemy_energy(boss.level) * 4
    assert sv._critter_by_id(save, boss.id) == boss
    b = {**fight["battle"], "energy": 1}
    won = sv.battle_turn({**fight, "battle": b}, [{"move": "attack", "slips": 0}, {"move": "attack", "slips": 0}], random.Random(1))
    assert won["battle"]["over"] == "won" and region in won["bosses"]
    assert any(e["kind"] == "coins" for e in won["events"])
    left = sv.end_battle(won)
    assert left["at"] == list(temple) and left["battle"] is None


def test_mythicals_turn_up_more_among_the_tougher():
    def share(tier):
        c = cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", 8, False, 0)
        return sum(cr._mythical(replace(c, seed=s), tier) is not None for s in range(20000)) / 20000
    assert 0.005 < share("") < 0.015 and 0.04 < share("tough") < 0.06 and 0.17 < share("champion") < 0.23
    for seed in range(4000):
        c = cr._grown(cr.Critter("x", (0, 0), (0, 0), "sheep", "dream", 8, False, seed), 0)
        if c.species != "sheep":
            assert c.species in wp.MYTHICAL and (c.kind, c.second) == wp.SPECIES_TYPES[c.species]
            assert sv.cr_looks({"species": c.species, "seed": seed})


def test_each_temple_boss_is_its_types_mythical_with_a_move_of_its_own():
    seen = set()
    for relics, region in enumerate(wp.TYPES):
        boss = cr.temple_boss(SEED, region, (0, 0), relics)
        assert boss.species in wp.MYTHICAL and wp.SPECIES_TYPES[boss.species] == (boss.kind, boss.second) and boss.kind == region
        assert boss.level == 13 + 2 * relics
        b = bt.start(boss, [0, 1])
        script = bt.foe_script(b, 9)
        own = bt.BOSS_MOVES[b["species"]]
        assert [script[i] for i in (2, 5, 8)] == [own] * 3 and own in terms.BOSS_MOVES
        seen.add(own)
        assert sv.cr_looks(b)["species"] == boss.species  # its own art, not another animal's
    assert len(seen) == len(wp.TYPES)
    assert cr.temple_boss(SEED, "leaf", (0, 0), 4).level == wp.MAX_LEVEL
    plain = bt.start(cr.Critter("x", (0, 0), (0, 0), "dragon", "shock", 13, False, 1, "ember"), [0, 1])
    assert "stormfire" not in bt.foe_script(plain, 30)  # only the boss has it


def _boss_round(species, region, **b_extra):
    boss = cr.temple_boss(SEED, region, (0, 0), 0)
    assert boss.species == species
    team = [wp.starter("leaf", 13), wp.starter("ember", 13)]
    b = {**bt.start(boss, [0, 1]), "round": 2, **b_extra}
    assert bt._foe_plan({**b, "round": 3}, 3) == bt.BOSS_MOVES[b["species"]]
    energy, mana = [m["energy"] for m in team], [m["mana"] for m in team]
    b = {**b, "round": 3, "log": []}
    out = bt._foe_acts(b, team, energy, mana, [0, 1], {}, random.Random(1))
    return b, team, energy, mana, out, bt.foe_intent({**b, "round": 2, "over": None}, team, [m["energy"] for m in team])


def test_stormfire_hits_both_and_guard_cant_stop_it():
    b, team, energy, _, out, intent = _boss_round("dragon", "shock")
    assert all(energy[i] < team[i]["energy"] for i in (0, 1))
    assert intent["name"] == "Stormfire: Both" and intent["count"]


def test_each_boss_has_its_own_energy_at_each_level():
    energy = lambda species, kind, level: bt.start(cr.Critter("x", (0, 0), (0, 0), species, kind, level, True, 1, None, "boss"), [0, 1])["energy"]  # noqa: E731
    assert energy("mermaid", "splash", 15) > energy("unicorn", "dream", 15) > energy("flower_fairy", "leaf", 15)
    lean = energy("unicorn", "dream", 17) / energy("unicorn", "dream", 15)
    full = energy("unicorn", "dream", 19) / energy("unicorn", "dream", 15)
    assert lean < full  # pets gain little at 17, so the boss there holds back
    plain = cr.Critter("x", (0, 0), (0, 0), "mermaid", "splash", 15, False, 1, None, "tough")
    assert bt.start(plain, [0, 1])["energy"] == round(bt.enemy_energy(15) * bt.TIERS["tough"]["energy"])  # only bosses


def test_plain_attacks_grow_with_the_pets_level_in_that_type():
    pet = {"power": 20, "types": {"ember": 13, "leaf": 9}}
    assert bt.type_power(pet, "ember") == 33 and bt.type_power(pet, "leaf") == 29
    assert bt.type_power(pet, "dream") == 20  # not one of its types
    def first_hit(move, types):
        member = {**_pet("ember", 13), "types": types}
        b = bt.start(_critter(9, "shock", "dog"), [0, 1])
        hits = [s for s in _round(b, [member, _pet("leaf", 13)], [{"move": move, "slips": 0}, {"move": "guard", "slips": 0}], energy=[900, 900])[0]["log"] if s.get("who") == 0 and s.get("damage")]
        return hits[0]["damage"]
    assert first_hit("attack", {"ember": 13}) > first_hit("attack", {"ember": 1})  # a plain attack cares
    assert first_hit("big", {"ember": 13}) == first_hit("big", {"ember": 1})  # a big move, spending mana, doesn't


def test_rekindle_gives_energy_back():
    b, team, energy, _, out, intent = _boss_round("phoenix", "ember", energy=100)
    assert b["energy"] == 100 + round(b["max"] * bt.REKINDLE)
    assert sum(energy) < sum(m["energy"] for m in team)  # and it hits you: no boss spends a turn doing nothing to you
    assert intent["kind"] == "boss" and not intent.get("count")


def test_moonlight_washes_off_marks_and_effects():
    b, team, energy, _, out, intent = _boss_round("unicorn", "dream", marks={"tangled": 2}, effects={"scalded": 2})
    assert not b["marks"] and not b["effects"]
    assert sum(energy) < sum(m["energy"] for m in team) and intent["name"].startswith("Moonlight")


def test_siren_song_drains_mana():
    b, team, energy, mana, out, intent = _boss_round("mermaid", "splash")
    assert mana == [m["mana"] - round(m["mana"] * bt.SIREN) for m in team]
    assert sum(energy) < sum(m["energy"] for m in team) and intent["name"].startswith("Siren Song")


def test_wild_bloom_drinks_what_it_deals():
    b, team, energy, _, out, intent = _boss_round("flower_fairy", "leaf", energy=100)
    dealt = sum(m["energy"] for m in team) - sum(energy)
    assert dealt and b["energy"] == 100 + bt.BLOOM * dealt and intent["name"].startswith("Wild Bloom")


def test_every_mythical_can_be_met_in_the_wild_in_its_own_art():
    assert cr.WILD_MYTHICAL == sorted(wp.MYTHICAL)
    for species in wp.MYTHICAL:
        fought = species.replace("_", " ")  # how a battle names it
        assert sv.cr_looks({"species": fought, "seed": 7})["species"] == species
        for tier in wp.TIER_COLORS:
            assert sv.cr_looks({"species": fought, "seed": 7, "tier": tier})["species"] == species
    # a mythical turns up by its first type: in leaf country, that's the fairy
    leaf = next(c for c in (cr.Critter("x", (0, 0), (0, 0), "bunny", "leaf", 5, False, seed) for seed in range(2000)) if cr._mythical(c, "champion"))
    assert cr._mythical(leaf, "champion") == "flower_fairy"


def test_tougher_creatures_wear_rare_colors():
    for species in (*cr.COMMON, *cr.WILD_MYTHICAL):
        for tier, families in wp.TIER_COLORS.items():
            genes = pet_genes.wild_rare(species, 7, families)
            assert pet_genes.resolve(genes) and sv.cr_looks({"species": species, "seed": 7, "tier": tier})
            if species != "phoenix":
                assert pet_genes.COLORS[genes["coat"]["colors"][0]].family in families
