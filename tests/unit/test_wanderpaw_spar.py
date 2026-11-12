"""Sparring in a town's ring (app/wanderpaw/spar.py): the lower pet learns
from the higher one, fast across a big gap and slowly across a small one."""

import pytest

from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app.wanderpaw import save as sv
from app.wanderpaw import spar as sp
from app.wanderpaw import battle as bt

SEED = 11


def pet(lv, pid=1, name="Pet", species="bunny"):
    m = wp.starter(wp.SPECIES_TYPES[species][0], lv)
    return {**m, "id": pid, "name": name, "species": species}


def test_the_learner_gains_a_share_of_its_next_level_for_each_level_between():
    learner = pet(3)
    step = wp.progress(learner["xp"])[1]
    assert sp.xp(pet(4), learner) == round(step * sp.RATE)
    assert sp.xp(pet(8), learner) == round(step * sp.RATE * 5)
    assert sp.xp(pet(21), learner) == step  # never more than a level a spar


def test_nothing_to_learn_from_the_same_level_or_lower():
    assert sp.xp(pet(5), pet(5)) == 0
    assert sp.xp(pet(4), pet(5)) == 0


def test_a_big_gap_beats_battles_and_a_small_one_is_slower():
    assert sp.xp(pet(15), pet(3)) > 3 * bt.XP_EVEN
    assert sp.xp(pet(4), pet(3)) < bt.XP_EVEN


def test_a_new_pet_catches_up_in_a_few_dozen_spars_not_a_hundred_battles():
    teacher, learner, spars = pet(15), pet(1), 0
    while learner["level"] < 14:
        xp = learner["xp"] + sp.xp(teacher, learner)
        learner = {**learner, "xp": xp, "level": wp.level(xp)}
        spars += 1
    assert 20 <= spars <= 45


def test_a_spar_costs_a_tenth_of_full_energy_and_never_the_last():
    m = pet(10)
    assert sp.cost(m) == round(m["energy"] * 0.1)
    assert sp.can_afford(m, sp.cost(m) + 1) and not sp.can_afford(m, sp.cost(m))


def test_pairs_are_real_pets_with_a_gap_and_energy_best_first():
    team = [pet(12, 1, "Big"), pet(2, 2, "Small"), pet(6, 3, "Mid"), wp.starter("ember")]
    energy = [m["energy"] for m in team]
    got = sp.pairs(team, energy)
    assert [(t, l) for t, l, _ in got] == [(0, 1), (0, 2), (2, 1)]  # 12 teaching 6 pays more than 6 teaching 2
    assert got[0][2] > got[1][2]
    energy[1] = 1  # Small is nearly worn out
    assert [(t, l) for t, l, _ in sp.pairs(team, energy)] == [(0, 2)]


# --- in the save ----------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_creatures(monkeypatch):
    monkeypatch.setattr(sv.cr, "at", lambda *a: {})


def at_a_ring(team):
    save = sv.start_trip({**sv.new_save(SEED), "team": team})
    big = next(b for b, h in sv.world_of(save).hexes.items() if h.special == "town")
    local = sv.local_of(save, big)
    ring = next(h for h, k in local.pois.items() if k == lc.ARENA)
    return {**save, "at": list(big), "spot": list(ring)}


def test_every_town_has_a_ring_you_can_walk_to():
    save = sv.new_save(SEED)
    for big, here in sv.world_of(save).hexes.items():
        if here.special == "town":
            local = sv.local_of(save, big)
            rings = [h for h, k in local.pois.items() if k == lc.ARENA]
            assert len(rings) == 1 and rings[0] in lc.reachable(local.tiles, local.campfire)


def test_the_ring_offers_each_spar_and_sparring_pays_the_learner():
    save = at_a_ring([pet(12, 1, "Kindle", "fox"), pet(2, 2, "Clover")])
    shown = sv.screen(save)
    assert shown["title"] == "Sparring Ring" and [o["arg"] for o in shown["options"]] == ["0,1"]
    gain = sp.xp(save["team"][0], save["team"][1])
    assert f"+{gain}" in shown["options"][0]["label"]
    before = list(save["trip"]["pets"])
    after = sv.act(save, "spar", arg="0,1")
    pets = after["trip"]["pets"]
    assert pets[0] == before[0] - sp.cost(save["team"][0]) and pets[1] == before[1] - sp.cost(save["team"][1])
    assert after["trip"]["energy"] == after["trip"]["walk"] + sum(pets)
    xp = [e for e in after["events"] if e["kind"] == "xp"]
    assert xp == [{"kind": "xp", "amount": gain, "pets": [2]}]
    spar = next(e for e in after["events"] if e["kind"] == "spar")
    assert spar["shots"] == ["ember", "leaf"] and spar["learner"] == 1


def test_the_ring_says_why_when_there_is_no_spar():
    shown = sv.screen(at_a_ring([pet(5, 1), pet(5, 2)]))
    assert shown["action"] is None and "higher in level" in shown["text"]
    save = at_a_ring([pet(12, 1), pet(2, 2)])
    save = {**save, "trip": {**save["trip"], "pets": [1, 1]}}
    assert "too tired" in sv.screen(save)["text"]
    with pytest.raises(sv.WanderError):
        sv.act(save, "spar", arg="0,1")


def test_the_ring_shows_between_trips_too():
    save = {**at_a_ring([pet(12, 1), pet(2, 2)]), "trip": None}
    assert sv.screen(save)["title"] == "Sparring Ring"
