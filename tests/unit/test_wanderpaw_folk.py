"""Wanderpaw's people: everyone greets you, answers questions and has a picture; hermits live out in the wilds."""

import pytest

from app import pet_genes
from app.wanderpaw import folk
from app.wanderpaw import hexes as hx
from app.wanderpaw import local as lc
from app.wanderpaw import pets as wp
from app.wanderpaw import save as sv
from app.wanderpaw import shop as sh
from app.wanderpaw import story as st
from app.wanderpaw import world as wd

SEED = 11
WORLD = wd.generate(SEED)
SEEDS = range(12)


@pytest.fixture(autouse=True)
def no_creatures(monkeypatch):
    monkeypatch.setattr(sv.cr, "at", lambda *a: {})


def _trip():
    return sv.start_trip({**sv.new_save(SEED), "team": [wp.starter(k, 5) for k in wd.REGIONS]})


def _at(save, big, spot):
    return sv._see({**save, "at": list(big), "spot": list(spot)}, big, spot)


def _in_town(role, region="splash", save=None):
    town = WORLD.quests[region].town
    spot = next(h for h, r in lc.generate(SEED, town).buildings.items() if r == role)
    return _at(save or _trip(), town, spot)


def _hermit(hid, save=None):
    big = next(b for b, h in lc.hermit_homes(SEED).items() if h == hid)
    spot = next(h for h, r in lc.generate(SEED, big).buildings.items() if r == f"hermit:{hid}")
    return _at(save or _trip(), big, spot)


def _people():
    for r in wd.REGIONS:
        yield folk.INNKEEPERS[r]
        yield folk.SHOPKEEPERS[r]
        yield from folk.HOUSES[r]
    yield from folk.GIVERS.values()
    yield from (h.person for h in folk.HERMITS.values())


def test_everyone_has_a_unique_name_real_species_and_words():
    people = list(_people())
    names = [p.name for p in people]
    assert len(names) == len(set(names))
    for p in people:
        assert p.species in wp.SPECIES_TYPES and p.who
        assert wp.looks(p.species, folk.seed_of(p.name))["species"] == p.species


def test_every_quest_giver_has_a_person():
    assert set(folk.GIVERS) == set(st.NPCS)
    assert all(folk.GIVERS[k].name == st.NPCS[k].name and folk.GIVERS[k].species == st.NPCS[k].species for k in st.NPCS)


def test_every_hermit_wants_something_you_can_find_and_gives_something_real():
    finds = set(st.FORAGE.values())
    for hid, h in folk.HERMITS.items():
        assert h.want in finds and h.count >= 1 and (h.coins or h.item)
        assert h.want == st.FORAGE[hid.split(":")[0]]  # found near where they live
        assert not h.item or h.item in sh.ITEMS


@pytest.mark.parametrize("seed", SEEDS)
def test_every_world_has_every_hermit_in_a_reachable_house_in_their_region(seed):
    world = wd.generate(seed)
    homes = lc.hermit_homes(seed)
    assert set(homes.values()) == set(folk.HERMITS)
    for big, hid in homes.items():
        assert world.hexes[big].region == hid.split(":")[0] and not world.hexes[big].special
        local = lc.generate(seed, big)
        house = next(h for h, r in local.buildings.items() if r == f"hermit:{hid}")
        assert house in lc.reachable(local.tiles, local.campfire)


@pytest.mark.parametrize("seed", SEEDS)
def test_towns_are_bigger_and_every_gate_still_has_a_way_in(seed):
    for region in wd.REGIONS:
        town = wd.generate(seed).quests[region].town
        local = lc.generate(seed, town)
        assert len(local.buildings) >= 7
        assert sum(hx.distance(h, local.campfire) == 1 for h in local.buildings) <= lc.TOWN_TOUCHING
        for h in local.buildings:
            assert h in lc.reachable(local.tiles, local.campfire)
        for h in local.gates:
            assert any(local.walkable(n) for n in hx.neighbors(h) if n in lc.CELL_SET)


@pytest.mark.parametrize("role", ["inn", "shop", "house"])
def test_townsfolk_greet_you_with_a_picture_and_answer_questions(role):
    save = _in_town(role)
    shown = sv.screen(save)
    assert shown["portrait"]["genes"]
    topics = {o["arg"] for o in shown["options"] if o["action"] == "folk"}
    assert {"who", "town", "rumors", "keeper"} <= topics
    for topic in ("who", "town", "keeper", "rumors"):
        said = sv.screen(sv.act(save, "folk", arg=topic))["text"]
        assert said and said != shown["text"]
        assert "{town}" not in said


def test_a_house_keeps_the_same_person_and_different_houses_differ():
    town = WORLD.quests["leaf"].town
    houses = sorted(h for h, r in lc.generate(SEED, town).buildings.items() if r == "house")
    assert len(houses) >= 2
    names = [sv.screen(_at(_trip(), town, h))["title"] for h in houses]
    assert len(set(names)) == len(names)
    assert names == [sv.screen(_at(_trip(), town, h))["title"] for h in houses]


def test_leaving_and_walking_back_starts_with_a_greeting_again():
    save = _in_town("house")
    hello = sv.screen(save)["text"]
    asked = sv.act(save, "folk", arg="who")
    assert sv.screen(asked)["text"] != hello
    spot = tuple(asked["spot"])
    step = next(n for n in hx.neighbors(spot) if lc.generate(SEED, tuple(asked["at"])).walkable(n))
    assert "talk" not in sv.apply_walk(asked, step)["trip"]


def test_shop_and_inn_keep_working_from_the_talk_menu():
    shop = sv.screen(_in_town("shop"))
    assert shop["action"] == "shop" and shop["enter"] and shop["stock"]
    inn = _in_town("inn")
    assert sv.screen(inn)["options"][0]["action"] == "inn"
    fed = sv.act(inn, "inn")
    assert sv.screen(fed)["options"][0]["action"] == "folk"  # full for now
    assert sv.screen(sv.act(fed, "folk", arg="soup"))["text"] == "You're full! Come back next trip."


def test_the_keeper_talk_changes_once_their_relic_is_gone():
    save = _in_town("house")
    before = sv.screen(sv.act(save, "folk", arg="keeper"))["text"]
    after = sv.screen(sv.act({**save, "temples": ["splash"]}, "folk", arg="keeper"))["text"]
    assert before != after


def test_rumors_point_to_who_knows_about_the_key_then_to_the_key_itself():
    save = _in_town("house")
    said = sv.act(save, "folk", arg="rumors")
    text = sv.screen(said)["text"]
    tale = st.STORIES["splash"]
    assert tale.key in text and "Captain Biscuit" in text
    assert "splash" not in said["rumors"]
    helped = sv.act({**save, "quests": {"splash:splash": "done"}}, "folk", arg="rumors")
    assert "splash" in helped["rumors"]
    assert sv._place_name(helped, sv._plan(helped).keys["splash"].big) in sv.screen(helped)["text"]


def test_rumors_send_you_to_a_hermit_and_mark_your_map():
    said = sv.act(_in_town("house"), "folk", arg="rumors")
    assert said["heard"] == ["splash:0"]
    name = folk.HERMITS["splash:0"].person.name
    assert name in sv.screen(said)["text"]
    home = next(b for b, h in lc.hermit_homes(SEED).items() if h == "splash:0")
    assert list(home) in sv.big_view(said)["marks"]
    assert any(name in q["title"] for q in sv.quests_view(said))
    again = sv.act(said, "folk", arg="rumors")
    assert again["heard"] == ["splash:0", "splash:1"]


def test_a_hermits_favor_takes_what_they_asked_for_and_pays():
    hid = "leaf:0"
    h = folk.HERMITS[hid]
    save = _hermit(hid)
    assert sv.screen(save)["text"] == h.person.hello
    with pytest.raises(sv.WanderError):
        sv.act(save, "take_favor")
    asked = sv.act(save, "folk", arg="help")
    assert sv.screen(asked)["text"] == h.ask
    taken = sv.act(asked, "take_favor")
    assert taken["favors"][hid] == "asked" and any(h.person.name in q["title"] for q in sv.quests_view(taken))
    with pytest.raises(sv.WanderError):
        sv.act(taken, "give_favor")
    stocked = {**taken, "items": {h.want: h.count + 1}}
    paid = sv.act(stocked, "give_favor")
    assert paid["items"][h.want] == 1 and paid["items"][h.item] == 1 and paid["favors"][hid] == "done"
    assert sum(e["amount"] for e in paid["events"] if e["kind"] == "coins") == h.coins
    assert sv.screen(paid)["text"] == h.thanks
    assert not {"take_favor", "give_favor"} & {o["action"] for o in sv.screen(paid)["options"]}


def test_walking_to_a_hermit_counts_as_meeting_them():
    hid = "camp:0"
    big = next(b for b, h in lc.hermit_homes(SEED).items() if h == hid)
    spot = next(h for h, r in lc.generate(SEED, big).buildings.items() if r == f"hermit:{hid}")
    assert hid in sv._arrive(_at({**_trip(), "heard": [hid]}, big, spot))["met"]


def test_pip_knows_the_neighbors():
    save = _at(_trip(), sv.CAMP, lc.PIP_HOUSE)
    told = sv.act(save, "pip_talk", arg="neighbors")
    assert told["heard"] == ["camp:0"]
    assert folk.HERMITS["camp:0"].person.name in sv.screen(told)["text"]


@pytest.mark.parametrize("key", list(folk.GIVERS))
def test_a_quest_giver_never_sends_you_to_themselves(key):
    region, shortcut = key
    me = folk.GIVERS[key].name
    other = next(p.name for k, p in folk.GIVERS.items() if k[0] == region and k != key)
    said = sv.screen(sv.act(_in_town(f"quest:{shortcut}", region), "folk", arg="rumors"))["text"]
    assert f"{me} might know" not in said and f"{me} or" not in said and f"or {me}" not in said
    assert "I might know" in said and other in said


@pytest.mark.parametrize("hid", list(folk.HERMITS))
def test_a_hermit_never_tells_you_about_themselves(hid):
    said = sv.act(_hermit(hid), "folk", arg="rumors")
    assert hid not in said["heard"]
    assert f"named {folk.HERMITS[hid].person.name}" not in sv.screen(said)["text"]
