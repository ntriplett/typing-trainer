"""Wanderpaw's shops and items (app/wanderpaw/shop.py and save.py's use_item)."""

from __future__ import annotations

import pytest

from app.wanderpaw import battle as bt
from app.wanderpaw import critters as cr
from app.wanderpaw import pets as wp
from app.wanderpaw import save as sv
from app.wanderpaw import shop as sh
from app.wanderpaw import story as st
from app.wanderpaw import world as wd


def _trip(*items, team=None, **extra):
    team = team or [{**wp.starter("ember", 13), "id": 1}, {**wp.starter("leaf", 13), "id": 2}]
    save = sv.start_trip({**sv.new_save(5), "team": team, "items": {i: 1 for i in items}, **extra})
    return save


def _battle(save, tier="", species="dog", kind="splash", level=5):
    return sv._start_battle(save, cr.Critter("g:0,0:0,0", (0, 0), (0, 0), species, kind, level, False, 3, None, tier))


def test_the_catalog_is_what_was_agreed():
    i = sh.ITEMS
    assert (i[sh.MANA_DROP].price, i[sh.FULL_MANA].price) == (500, 2000)
    assert (i[sh.TOKEN].price, i[sh.TOKEN].limit) == (1000, 1)
    assert (i[sh.TOME].price, i[sh.TOME].limit, i[sh.WEIGHT].price, i[sh.WEIGHT].limit) == (2000, 3, 2000, 3)
    assert i[sh.WAY_HOME].price == 2000 and i[sh.WAY_HOME].keep


def test_each_towns_shop_has_a_flavor_and_the_things_every_shop_has():
    assert set(sh.SHOP_FLAVOR) == set(wd.REGIONS) == set(sh.KEEPERS)
    assert len(set(sh.SHOP_FLAVOR.values())) == len(wd.REGIONS)  # all different
    shelves = {r: {x["name"] for x in sh.stock(r, {}, {}, False)} for r in wd.REGIONS}
    assert len({frozenset(s) for s in shelves.values()}) == len(wd.REGIONS)
    for shelf in shelves.values():
        assert set(sh.EVERY_SHOP) <= shelf
    assert set().union(*shelves.values()) == set(sh.ITEMS)  # everything is sold somewhere


def test_every_item_says_what_it_does():
    assert all(st.describe(name) == item.about for name, item in sh.ITEMS.items())


def test_limited_stock_runs_out_and_tokens_restock_once_after_the_game():
    left = lambda bought, finished=False, name=sh.TOKEN: next(x for x in sh.stock("leaf", bought, {}, finished) if x["name"] == name)  # noqa: E731
    assert left({})["left"] == 1 and not left({})["sold_out"]
    assert left({sh.TOKEN: 1})["sold_out"]
    assert left({sh.TOKEN: 1}, True)["left"] == 1  # beat the game: one more
    assert left({sh.TOKEN: 2}, True)["sold_out"]
    assert left({sh.TOME: 2}, name=sh.TOME)["left"] == 1 and left({sh.TOME: 3}, name=sh.TOME)["sold_out"]
    assert left({}, name=sh.MANA_DROP)["left"] is None  # always restocks
    kept = next(x for x in sh.stock("ember", {}, {sh.WAY_HOME: 1}, False) if x["name"] == sh.WAY_HOME)
    assert kept["sold_out"]  # you only need one


def test_mana_potions_work_mid_fight_without_using_a_turn():
    save = _battle(_trip(sh.MANA_DROP, sh.FULL_MANA))
    save = {**save, "trip": {**save["trip"], "mana": [3, 3, *save["trip"]["mana"][2:]]}}
    who = save["battle"]["fighters"]
    round_before = save["battle"]["round"]
    after = sv.use_item(save, sh.MANA_DROP)
    assert [after["trip"]["mana"][i] for i in who] == [13, 13]
    assert after["items"][sh.MANA_DROP] == 0 and after["battle"]["round"] == round_before
    full = sv.use_item(after, sh.FULL_MANA)
    assert [full["trip"]["mana"][i] for i in who] == [save["team"][i]["mana"] for i in who]
    with pytest.raises(sv.WanderError):
        sv.use_item({**full, "items": {sh.MANA_DROP: 1}}, sh.MANA_DROP)  # already full


def test_a_ward_is_used_up_first_and_fades_after_the_battle():
    save = _battle(_trip(sh.WARD))
    who = save["battle"]["fighters"]
    before = [save["trip"]["pets"][i] for i in who]
    warded = sv.use_item(save, sh.WARD)
    extra = [round(save["team"][i]["energy"] * sh.WARD_SHARE) for i in who]
    assert [warded["trip"]["pets"][i] for i in who] == [a + e for a, e in zip(before, extra)]
    assert [f["ward"] for f in sv.battle_view(warded)["fighters"]] == extra
    # a hit that doesn't get through the ward costs nothing real
    pets = list(warded["trip"]["pets"])
    pets[who[0]] -= extra[0] - 1
    hit = {**warded, "trip": {**warded["trip"], "pets": pets}, "battle": {**warded["battle"], "over": "won"}}
    done = sv._ward_fades(hit, hit["battle"])
    assert [done["trip"]["pets"][i] for i in who] == before
    # one that gets through does
    pets = list(warded["trip"]["pets"])
    pets[who[0]] = before[0] - 5
    done = sv._ward_fades({**warded, "trip": {**warded["trip"], "pets": pets}}, warded["battle"])
    assert done["trip"]["pets"][who[0]] == before[0] - 5


def test_running_from_a_fight_loses_the_ward_too():
    save = _battle(_trip(sh.WARD))
    who = save["battle"]["fighters"]
    before = [save["trip"]["pets"][i] for i in who]
    gone = sv.flee(sv.use_item(save, sh.WARD))
    assert [gone["trip"]["pets"][i] for i in who] == before


def test_a_feather_brings_back_a_worn_out_fighter():
    save = _battle(_trip(sh.FEATHER))
    i = save["battle"]["fighters"][0]
    with pytest.raises(sv.WanderError):
        sv.use_item(save, sh.FEATHER)  # nobody needs it
    pets = list(save["trip"]["pets"])
    pets[i] = 0
    back = sv.use_item({**save, "trip": {**save["trip"], "pets": pets}}, sh.FEATHER)
    assert back["trip"]["pets"][i] == round(save["team"][i]["energy"] * sh.FEATHER_SHARE)


def test_a_tonic_refills_your_walking_energy_only():
    save = _trip(sh.TONIC)
    pets = [e - 3 for e in save["trip"]["pets"]]
    tired = {**save, "trip": {**save["trip"], "walk": 2, "pets": pets, "energy": 2 + sum(pets)}}
    after = sv.use_item(tired, sh.TONIC)
    assert after["trip"]["walk"] == sv.WALK_ENERGY and after["trip"]["pets"] == pets
    assert after["trip"]["energy"] == sv.WALK_ENERGY + sum(pets)
    with pytest.raises(sv.WanderError):
        sv.use_item(_trip(sh.TONIC), sh.TONIC)  # not tired


def test_the_way_home_charm_is_kept_and_takes_you_to_the_center_of_camp():
    save = _trip(sh.WAY_HOME)
    away = {**save, "at": [2, 0], "spot": sv.local_of(save, (2, 0)).campfire}
    home = sv.use_item(away, sh.WAY_HOME)
    assert home["at"] == list(sv.CAMP) and home["spot"] == [0, 0]
    assert home["items"][sh.WAY_HOME] == 1
    with pytest.raises(sv.WanderError):
        sv.use_item(_battle(save), sh.WAY_HOME)  # not mid-fight


def test_treasure_maps_mark_keys_you_dont_know_about():
    save = _trip(sh.MAP)
    marked = sv.use_item(save, sh.MAP)
    assert len(marked["rumors"]) == 1 and marked["items"][sh.MAP] == 0
    every = {**save, "rumors": list(wd.REGIONS)}
    with pytest.raises(sv.WanderError):
        sv.use_item(every, sh.MAP)


def test_boots_mean_more_walking_energy_every_trip():
    save = _trip(sh.BOOTS)
    assert save["trip"]["walk"] == sv.WALK_ENERGY + sh.BOOTS_WALK


def test_a_satchel_and_a_rod_find_more():
    assert sv._forage_count(_trip()) == 1
    assert sv._forage_count(_trip(sh.SATCHEL)) == 2


def test_a_cloak_slips_past_a_plain_creature_only():
    assert sh.ITEMS[sh.CLOAK].when == "walk"
    save = sv.use_item(_trip(sh.CLOAK), sh.CLOAK)
    assert save["trip"]["cloak"] == 1 and save["items"][sh.CLOAK] == 0


def test_a_tome_and_a_weight_ask_which_pet():
    save = _trip(sh.TOME, sh.WEIGHT)
    uses = sv.item_uses(save)
    assert "1:ember" in [c["arg"] for c in uses[sh.TOME]["choices"]]
    assert "2:power" in [c["arg"] for c in uses[sh.WEIGHT]["choices"]]
    with pytest.raises(sv.WanderError):
        sv.use_item(save, sh.TOME, "99:ember")
    after = sv.use_item(save, sh.TOME, "1:ember")
    assert {"kind": "bonus", "pet": 1, "bonus": "type", "name": "ember"} in after["events"]


def test_type_and_stat_bonuses_count_but_arent_real_levels():
    rec = wp.Record(xp=wp.xp_for(10))
    book = wp.with_bonus(rec, "type", "ember")
    assert wp.type_levels("fox", book)["ember"] == wp.type_levels("fox", rec)["ember"] + 1
    assert wp.level(book.xp) == wp.level(rec.xp)
    plain = wp.stats("fox", wp.STARTER_STATS, rec)
    for stat in sh.STATS:
        assert wp.stats("fox", wp.STARTER_STATS, wp.with_bonus(rec, "stat", stat))[stat] == plain[stat] + 1
    assert wp.record_from(wp.record_json(book)) == book


def test_befriending_is_offered_after_a_win_for_mana_and_never_for_bosses():
    won = lambda save, **b: {**save, "battle": {**save["battle"], "over": "won", **b}}  # noqa: E731
    save = _battle(_trip(), level=5)
    assert sv._befriend_offer(save, save["battle"]) is None  # not over yet
    done = won(save)
    assert sv._befriend_offer(done, done["battle"]) == {"cost": 5, "can": True, "why": None}  # no token needed yet
    tough = won(_battle(_trip(), tier="tough", level=5))
    assert sv._befriend_offer(tough, tough["battle"])["cost"] == 5 + sh.BEFRIEND_EXTRA_MANA["tough"]
    champ = won(_battle(_trip(), tier="champion", level=5))
    assert sv._befriend_offer(champ, champ["battle"])["cost"] == 5 + sh.BEFRIEND_EXTRA_MANA["champion"]
    boss = won(_battle(_trip(), tier="boss", species="dragon", kind="shock", level=13))
    assert sv._befriend_offer(boss, boss["battle"]) is None
    poor = {**done, "trip": {**done["trip"], "mana": [0] * len(done["trip"]["mana"])}}
    assert not sv._befriend_offer(poor, poor["battle"])["can"]


def test_befriending_brings_them_to_camp_and_costs_each_fighter_mana():
    save = _battle(_trip(), level=5, species="goat", kind="leaf")
    save = {**save, "battle": {**save["battle"], "over": "won"}}
    who = save["battle"]["fighters"]
    before = [save["trip"]["mana"][i] for i in who]
    after = sv.befriend(save)
    assert [after["trip"]["mana"][i] for i in who] == [m - 5 for m in before]
    friend = after["camp_friends"][0]
    assert (friend["species"], friend["level"]) == ("goat", 5)
    assert sv._befriend_offer(after, after["battle"]) is None  # just the once
    with pytest.raises(sv.WanderError):
        sv.befriend(after)


def test_camp_holds_five_friends():
    friends = [{"id": str(i), "species": "dog", "name": "Dog", "level": 1, "genes": {}} for i in range(sh.CAMP_SPOTS)]
    save = _battle(_trip(camp_friends=friends), level=3)
    full = {**save, "battle": {**save["battle"], "over": "won"}}
    offer = sv._befriend_offer(full, full["battle"])
    assert not offer["can"] and "Camp is full" in offer["why"]


def test_friends_are_only_sent_off_from_the_fire_at_camp():
    friend = {"id": "a", "species": "dog", "name": "Dog", "level": 1, "genes": {}}
    save = _trip(camp_friends=[friend])
    gone = sv.friend_leaves(save, "a")
    assert gone["camp_friends"] == []
    away = {**save, "at": [2, 0], "spot": list(sv.local_of(save, (2, 0)).campfire)}
    with pytest.raises(sv.WanderError):
        sv.friend_leaves(away, "a")
    with pytest.raises(sv.WanderError):
        sv.friend_leaves(save, "nobody")


def test_only_the_fire_at_camp_offers_your_friends():
    save = _trip()
    assert sv.screen(save)["friends"]
    away = {**save, "at": [2, 0], "spot": list(sv.local_of(save, (2, 0)).campfire)}
    assert "friends" not in sv.screen(away)


def test_a_worn_cloak_gets_you_past_a_plain_creature_but_not_a_tough_one(monkeypatch):
    save = sv.use_item(_trip(sh.CLOAK), sh.CLOAK)
    plain = cr.Critter("c", (0, 0), (1, 0), "dog", "splash", 3, False, 1)
    tough = cr.Critter("c", (0, 0), (1, 0), "dog", "splash", 3, False, 1, None, "tough")
    target = (1, 0)
    assert sv.standable(save, sv.local_of(save, (0, 0)), target)
    monkeypatch.setattr(sv, "_blocked", lambda *_: "critter")
    monkeypatch.setattr(sv, "critter_at", lambda *_: plain)
    past = sv.apply_walk(save, target)
    assert not past.get("battle") and past["spot"] == list(target) and past["trip"]["cloak"] == 0
    assert any("slip past" in e.get("text", "") for e in past["events"])
    monkeypatch.setattr(sv, "critter_at", lambda *_: tough)
    assert sv.apply_walk(save, target)["battle"]  # a tough one sees you
    monkeypatch.setattr(sv, "critter_at", lambda *_: plain)
    assert sv.apply_walk(_trip(), target)["battle"]  # and with no cloak on, you fight


def _a_gate(save):
    world = sv.world_of(save)
    for big in world.hexes:
        local = sv.local_of(save, big)
        for h, edge in local.gates.items():
            gate = world.gates[edge]
            if gate.kind != "quest" and gate.level >= 2:
                return local, h, gate
    raise AssertionError("no gate")


@pytest.mark.parametrize("short, works", [(1, True), (3, True), (4, False)])
def test_a_lucky_charm_carries_you_over_a_gate_you_nearly_qualify_for(short, works):
    save = _trip(sh.LUCKY)
    local, h, gate = _a_gate(save)
    have = max(0, gate.level - short)
    team = [{**wp.starter(gate.kind, 1), "id": 1, "types": {gate.kind: have}}]
    close = {**save, "team": team}
    if gate.level - have != short:
        pytest.skip("this gate's too low to be that far short")
    if works:
        through = sv._try_gate(close, local, h)
        assert through["items"][sh.LUCKY] == 0 and len(through["cleared"]) == len(save["cleared"]) + 1
    else:
        with pytest.raises(sv.WanderError):
            sv._try_gate(close, local, h)


def test_a_gate_you_can_pass_anyway_keeps_your_charm():
    save = _trip(sh.LUCKY)
    local, h, gate = _a_gate(save)
    through = sv._try_gate({**save, "team": [{**wp.starter(gate.kind, 1), "id": 1, "types": {gate.kind: gate.level}}]}, local, h)
    assert through["items"][sh.LUCKY] == 1


def test_a_satchel_doubles_a_forage_spot():
    save = _trip()
    big, spot = next((b, s) for b in sv.world_of(save).hexes for s, poi in sv.local_of(save, b).pois.items() if poi == "forage")
    item = st.FORAGE[sv.world_of(save).hexes[big].region]
    there = {**save, "at": list(big), "spot": list(spot)}
    assert sv._arrive(there)["items"][item] == 1
    assert sv._arrive({**there, "items": {sh.SATCHEL: 1}})["items"][item] == 2
