"""Wanderpaw's pets: types, levels, stats, the team (PLAN.md 11n phase 4)."""

from collections import Counter

import pytest

from app.wanderpaw import pets as wp

BATTLE = {"strength": 6, "speed": 4, "stamina": 7}


def test_every_type_has_two_starter_species_and_a_mythical():
    plain = Counter(first for s, (first, second) in wp.SPECIES_TYPES.items() if not second)
    assert plain == {t: 2 for t in wp.TYPES}
    mythic = [wp.SPECIES_TYPES[s] for s in wp.MYTHICAL]
    assert Counter(first for first, _ in mythic) == {t: 1 for t in wp.TYPES}
    assert Counter(second for _, second in mythic) == {t: 1 for t in wp.TYPES}
    assert all(first != second for first, second in mythic)
    assert not wp.can_go("fish")


def test_levels_and_type_levels():
    assert wp.level(0) == 1 and wp.level(499) == 1 and wp.level(500) == 2
    rec = wp.Record(xp=wp.xp_for(7))  # level 7
    assert wp.type_levels("bunny", rec) == {"leaf": 7}
    picked = wp.Record(xp=wp.xp_for(7), second="shock", second_at=5)
    assert wp.type_levels("bunny", picked) == {"leaf": 7, "shock": 3}
    # mythicals have both, equal, from level 1
    assert wp.type_levels("dragon", wp.Record()) == {"shock": 1, "ember": 1}
    assert wp.type_levels("dragon", rec) == {"shock": 7, "ember": 7}


def test_each_level_takes_a_bit_more_xp_up_to_the_cap():
    assert wp.xp_for(1) == 0 and wp.xp_for(2) == 500 and wp.xp_for(3) == 1040
    costs = [wp.xp_for(lv + 1) - wp.xp_for(lv) for lv in range(1, wp.MAX_LEVEL)]
    assert costs == sorted(costs) and all(b / a == pytest.approx(wp.XP_GROWTH, abs=0.02) for a, b in zip(costs, costs[1:]))
    assert wp.level(wp.xp_for(7)) == 7 and wp.level(wp.xp_for(7) - 1) == 6
    assert wp.level(wp.xp_for(wp.MAX_LEVEL) * 2) == wp.MAX_LEVEL
    assert wp.progress(wp.xp_for(4) + 10) == (10, wp.xp_for(5) - wp.xp_for(4))
    assert wp.progress(wp.xp_for(wp.MAX_LEVEL)) is None


def test_second_type_offered_at_five_from_partners():
    young = wp.Record(xp=wp.xp_for(4))
    assert wp.second_choices(1, "bunny", young) is None
    five = wp.Record(xp=wp.xp_for(5))
    offered = wp.second_choices(1, "bunny", five)
    assert len(set(offered)) == 2 and "leaf" not in offered
    fought = wp.note_battle(wp.note_battle(five, ["dream", "leaf"]), ["dream"])
    assert fought.partners == {"dream": 2, "leaf": 1}
    assert wp.second_choices(1, "bunny", fought)[0] == "dream"  # not leaf: its own type
    rec = wp.pick_second(1, "bunny", fought, "dream")
    assert rec.second == "dream" and rec.second_at == 5
    assert wp.second_choices(1, "bunny", rec) is None
    assert wp.type_levels("bunny", wp.gain_xp(rec, wp.xp_for(6) - rec.xp)) == {"leaf": 6, "dream": 2}
    with pytest.raises(ValueError):
        wp.pick_second(1, "bunny", fought, "ember" if "ember" not in wp.second_choices(1, "bunny", fought) else "leaf")
    assert wp.second_choices(1, "unicorn", five) is None  # mythicals are born with theirs


def test_stats_grow_with_level():
    one = wp.stats("fox", BATTLE, wp.Record())
    three = wp.stats("fox", BATTLE, wp.Record(xp=wp.xp_for(3)))
    assert one == {"level": 1, "energy": 23, "power": 7, "speed": 5, "mana": 11}
    assert three["energy"] == one["energy"] + 4 and three["power"] == one["power"] + 2


def test_team_fills_missing_types_with_starters():
    fox = wp.member({"id": 3, "name": "Rusty", "species": "fox", "genes": {"battle": BATTLE}}, wp.Record())
    team = wp.team([fox])
    assert len(team) == 5 and team[0] is fox
    assert {t for m in team for t in m["types"]} == set(wp.TYPES)
    assert all(m["id"] is None and m["level"] == 1 for m in team[1:])
    assert wp.team_levels(team, "ember") == 1 and wp.team_energy(team) == sum(m["energy"] for m in team)
    full = wp.team([fox] * 5)
    assert len(full) == 5 and wp.team_levels(full, "ember") == 5
    assert len(wp.team([])) == 5
    assert wp.starter("dream", 4)["types"] == {"dream": 4}


def test_records_round_trip():
    rec = wp.Record(xp=900, second="leaf", second_at=5, partners={"leaf": 2}, starred=True)
    assert wp.record_from(wp.record_json(rec)) == rec
    assert wp.record_from(None) == wp.Record()
