"""Wanderpaw battles and wild creatures (PLAN.md 11n phase 5a)."""

import random
import statistics

import pytest

from app.wanderpaw import battle as bt
from app.wanderpaw import critters as cr
from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app.wanderpaw import save as sv
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


@pytest.mark.parametrize("level", [1, 3, 6])
def test_a_fair_fight_takes_about_three_rounds_and_a_tenth_of_each_fighter(level):
    rounds, costs = [], []
    for s in range(200):
        rng = random.Random(s)
        team = [wp.starter("leaf", level), wp.starter("leaf", level)]
        b, energy = bt.start(_critter(level), [0, 1]), [m["energy"] for m in team]
        while not b["over"]:
            b, energy, _ = bt.turn(b, team, energy, [{"move": "attack", "slips": rng.choice([0, 0, 1, 2])}] * 2, rng)
        assert b["over"] == "won"
        rounds.append(b["round"])
        costs += [(team[i]["energy"] - energy[i]) / team[i]["energy"] for i in (0, 1)]
    assert 2.5 <= statistics.mean(rounds) <= 3.6
    assert 0.05 <= statistics.mean(costs) <= 0.15


def _round(b, team, picks, energy=None, mana=None, seed=1):
    return bt.turn(b, team, energy or [99] * len(team), picks, random.Random(seed), mana)


def test_strong_types_hit_harder():
    team = [wp.starter("splash", 3), wp.starter("splash", 3)]
    ember, shock = _critter(3, "ember", "fox"), _critter(3, "shock", "cat")
    hit = lambda c: _round(bt.start(c, [0, 1]), team, [{"move": "attack", "slips": 0}] * 2)[0]  # noqa: E731
    assert hit(ember)["max"] - hit(ember)["energy"] > hit(shock)["max"] - hit(shock)["energy"]
    with pytest.raises(ValueError):
        _round(bt.start(ember, [0, 1]), team, [{"move": "brace", "slips": 0}] * 2)


def test_six_moves_each_with_a_note():
    pet = wp.starter("ember", 3)
    moves = bt.moves(pet, "dream", mana=2)
    assert [m["id"] for m in moves] == ["attack", "big", "guard", "focus", "cheer", "rest"]
    assert all(m["note"] and len(m["note"]) <= 26 for m in moves) and "Super strong" in moves[0]["note"]
    assert "First" in moves[1]["note"]
    assert moves[1]["can"] is False  # not enough mana
    with pytest.raises(ValueError, match="mana"):
        _round(bt.start(_critter(3), [0, 1]), [pet, pet], [{"move": "big", "slips": 0}] * 2, mana=[2, 2])
    # a pet with two types attacks with the better one
    dragon = {**pet, "types": {"shock": 3, "ember": 3}}
    assert bt.best_type(dragon, "splash") == "shock" and bt.best_type(dragon, "dream") == "ember"


def test_guard_takes_the_hit_for_a_partner_at_half():
    team = [wp.starter("leaf", 3), wp.starter("leaf", 3)]
    b = bt.start(_critter(3, "shock", "cat"), [0, 1])
    for seed in range(20):
        _, energy, _ = _round(b, team, [{"move": "guard", "slips": 0}, {"move": "rest", "slips": 0}], energy=[20, 20], seed=seed)
        assert energy[1] > 20 and energy[0] < 20  # the guard takes the hit; the guarded one only rests


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
    b = {**bt.start(_critter(5, foe_kind, "goat"), [0, 1]), "marks": dict(marks or {}), "effects": dict(effects or {})}
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


def test_the_heartland_has_enough_to_level_a_party():
    heart = [b for b, h in WORLD.hexes.items() if h.region == wd.HEARTLAND]
    today = [c for b in heart for c in cr.at(SEED, b, 1).values()]
    team = [wp.starter(t) for t in wd.REGIONS]
    xp = sum(2 * bt.xp(bt.start(c, [0, 1]), team) for c in today)  # two fighters each
    assert xp >= 5 * wp.XP_PER_LEVEL and all(c.level <= 2 for c in today)


def _beside_a_creature():
    """A save standing next to a creature, on a trip."""
    save = sv.start_trip({**sv.new_save(SEED), "team": [wp.starter(t, 3) for t in wd.REGIONS]})
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
