"""Wanderpaw's story (LORE.md): Pip's tutorial, and each temple's Keeper, letter and gifts."""

import pytest

from app.wanderpaw import critters as cr
from app.wanderpaw import local as lc
from app.wanderpaw import lore
from app.wanderpaw import pets as wp
from app.wanderpaw import save as sv
from app.wanderpaw import shop as sh
from app.wanderpaw import story as st
from app.wanderpaw import world as wd

SEED = 11
WORLD = wd.generate(SEED)


@pytest.fixture(autouse=True)
def no_creatures(monkeypatch):
    monkeypatch.setattr(sv.cr, "at", lambda *a: {})


def _team():
    return [wp.starter(k, 5) for k in wd.REGIONS]


def _new():
    return {**sv.new_save(SEED), "team": _team(), "tutorial": "intro"}


def _temple(region="splash", **changes):
    big = WORLD.temples()[region]
    door = next(h for h, kind in lc.generate(SEED, big).tiles.items() if kind == "temple")
    save = sv.start_trip({**sv.new_save(SEED), "team": _team()})
    return {**save, "at": list(big), "spot": list(door), "items": {st.STORIES[region].key: 1}, **changes}


def _read(save, region="splash"):
    for at in range(len(lore.KEEPERS[region].letter)):
        save = sv.act(save, "letter_line", arg=at)
    return save


def test_camp_has_pips_house_and_a_clear_yard_in_every_world():
    for seed in range(40):
        camp = lc.generate(seed, sv.CAMP)
        assert camp.buildings[lc.PIP_HOUSE] == lc.PIP_ROLE
        assert lc.PIP_YARD in lc.reachable(camp.tiles, camp.campfire)
        assert lc.PIP_HOUSE in lc.reachable(camp.tiles, camp.campfire)


def test_a_new_game_opens_on_pips_pages_and_old_saves_dont():
    assert sv.tutorial_view(_new())["pages"] == list(lore.INTRO_PAGES)
    assert sv.tutorial_view({**sv.new_save(SEED), "team": _team()}) is None


def test_the_tutorial_goes_from_reading_to_a_first_fight():
    save = sv.tutorial_seen(_new(), "intro")
    assert save["tutorial"] == "party" and "hint" in sv.tutorial_view(save)
    save = sv.start_trip(save)
    assert save["tutorial"] == "walk"
    for spot in ((0, 1), (0, 0), (0, 1)):
        save = sv.apply_walk(save, spot)
    assert save["tutorial"] == "door"
    save = {**save, "spot": list(lc.PIP_HOUSE)}
    assert sv.screen(save)["action"] == "pip_in"
    save = sv.act(save, "pip_in")
    assert save["tutorial"] == "map"
    save = sv.tutorial_seen(sv.tutorial_seen(save, "map"), "guide")
    assert save["tutorial"] == "fight"
    assert sv.critter_at(save, sv.CAMP, lc.PIP_YARD).level == 1
    save = sv.apply_walk(save, lc.PIP_YARD)
    assert save["battle"]["critter"] == sv.TUTORIAL_CRITTER
    assert "hint" in sv.tutorial_view(save)


def test_a_tutorial_step_only_moves_on_from_where_you_are():
    save = _new()
    assert sv.tutorial_seen(save, "guide")["tutorial"] == "intro"
    assert sv.tutorial_seen(save, "fight")["tutorial"] == "intro"  # that one's earned by walking
    assert sv.tutorial_seen(save, "skip")["tutorial"] == "done"


def test_the_creature_is_only_there_during_the_tutorial():
    save = sv.start_trip({**sv.new_save(SEED), "team": _team()})
    assert sv.critter_at(save, sv.CAMP, lc.PIP_YARD) is None


def test_pip_tells_the_story_again_and_restarts_the_tutorial():
    save = {**sv.start_trip({**sv.new_save(SEED), "team": _team()}), "spot": list(lc.PIP_HOUSE)}
    told = sv.act(save, "pip_talk", arg="story")
    assert sv.view(told)["pages"] == list(lore.INTRO_PAGES)
    fought = {**save, "trip": {**save["trip"], "beaten": [sv.TUTORIAL_CRITTER]}}
    again = sv.act(fought, "pip_talk", arg="tutorial")
    assert again["tutorial"] == "walk" and sv.TUTORIAL_CRITTER not in again["trip"]["beaten"]
    assert lore.PIP_NEXT[0] in sv.screen(sv.act(save, "pip_talk", arg="next"))["text"]


def test_the_keeper_comes_before_the_letter_and_the_letter_before_the_relic():
    save = _temple()
    assert sv.screen(save)["action"] == "boss"
    with pytest.raises(sv.WanderError):
        sv.act(save, "letter_line", arg=0)
    beaten = {**save, "bosses": ["splash"]}
    with pytest.raises(sv.WanderError):
        sv.act(beaten, "temple")
    assert sv.screen(beaten)["letter"]["at"] == 0


def test_a_letter_is_saved_line_by_line_and_cant_skip_ahead():
    save = {**_temple(), "bosses": ["splash"]}
    with pytest.raises(sv.WanderError):
        sv.act(save, "letter_line", arg=2)
    once = sv.act(save, "letter_line", arg=0)
    assert once["letters"]["splash"] == 1
    assert sv.screen(once)["letter"]["at"] == 1  # come back any time: same place
    assert "1 of 3" in sv.screen(once)["text"]


def test_lifting_the_relic_is_what_makes_the_world_harder():
    save = _read({**_temple(), "bosses": ["splash"]})
    assert sv.relics_out(save) == 0  # the letter hasn't changed a thing
    shown = sv.screen(save)
    assert shown["action"] == "temple" and "2 levels" in shown["text"] and lore.KEEPERS["splash"].keepsake in shown["text"]
    taken = sv.act(save, "temple")
    assert sv.relics_out(taken) == 1


def test_the_reward_is_big():
    team = [{**m, "id": i + 1} for i, m in enumerate(_team())]
    taken = sv.act(_read({**_temple(), "bosses": ["splash"], "team": team}), "temple")
    k = lore.KEEPERS["splash"]
    assert taken["items"][st.STORIES["splash"].relic] == 1
    assert taken["items"][k.keepsake] == 1
    assert sum(e["amount"] for e in taken["events"] if e["kind"] == "coins") == lore.KEEPER_COINS
    assert sum(e["amount"] for e in taken["events"] if e["kind"] == "xp") == lore.KEEPER_XP


def test_winning_lets_you_wake_up_at_the_temple(monkeypatch):
    big = WORLD.temples()["splash"]
    fought = sv.act(_temple(), "boss")
    assert big not in sv.campfires_rested(fought)

    def won(b, team, pets, picks, rng, mana):
        return {**b, "over": "won", "log": []}, pets, mana

    monkeypatch.setattr(sv.bt, "turn", won)
    done = sv.battle_turn(fought, [])
    assert "splash" in done["bosses"]
    assert big in sv.campfires_rested(done)
    assert any("Nerissa" in (e.get("text") or "") for e in done["events"])


def test_after_the_relic_the_keeper_is_a_friend_to_talk_to():
    taken = sv.act(_read({**_temple(), "bosses": ["splash"]}), "temple")
    shown = sv.screen(taken)
    assert {o["arg"] for o in shown["options"]} >= set(lore.KEEPER_TALKS)
    said = sv.act(taken, "keeper_talk", arg="tumble")
    assert sv.screen(said)["text"] == lore.KEEPERS["splash"].on_tumble


def test_the_keepers_relative_joins_camp_free_and_you_can_ask_again():
    taken = sv.act(_read({**_temple(), "bosses": ["splash"]}), "temple")
    k = lore.KEEPERS["splash"]
    assert k.kin in sv.screen(taken)["text"]
    joined = sv.act(taken, "kin_join")
    friend = joined["camp_friends"][0]
    assert friend["name"] == k.kin and friend["species"] == "mermaid" and friend["kin"] == "splash"
    assert not sv.kin_available(joined, "splash")
    assert "kin_join" not in [o["action"] for o in sv.screen(joined)["options"]]
    # they left Camp: ask again, and it's the same one
    left = {**joined, "camp_friends": []}
    assert sv.kin_available(left, "splash")
    assert sv.act(left, "kin_join")["camp_friends"][0]["genes"] == friend["genes"]


def test_camp_full_means_ask_again_later():
    taken = sv.act(_read({**_temple(), "bosses": ["splash"]}), "temple")
    full = {**taken, "camp_friends": [{"id": str(i), "species": "goat", "name": "x", "level": 1, "genes": {}} for i in range(sh.CAMP_SPOTS)]}
    shown = sv.screen(full)
    assert "Camp is full" in shown["text"]
    assert "kin_join" not in [o["action"] for o in shown["options"]]


def test_every_keeper_has_their_own_letter_from_the_friend_who_hurt_them():
    assert {k.from_name for k in lore.KEEPERS.values()} == {k.name for k in lore.KEEPERS.values()}
    assert all(k.from_name != k.name and len(k.letter) == 3 for k in lore.KEEPERS.values())
    assert len(lore.KEEPSAKES) == 5
    assert all(st.describe(name) == about for name, about in lore.KEEPSAKES.items())


def test_keepsakes_do_what_they_say():
    with_all = {"items": {k.keepsake: 1 for k in lore.KEEPERS.values()}}
    assert sv.walk_max(with_all) == sv.WALK_ENERGY + lore.PILLOW_WALK
    assert sv._forage_count(with_all) == 2


def test_a_relic_taken_before_letters_catches_up():
    old = {"temples": ["leaf"], "items": {"Evergreen Leaf": 1}}
    new = sv._catch_up(old)
    assert new["letters"]["leaf"] == 3
    assert new["items"][lore.KEEPERS["leaf"].keepsake] == 1
    assert sv._catch_up(new) is new


# --- what sleeps in the caves -----------------------------------------------------------


def _sleeper_nook(save):
    """A nook with something asleep in it, walkable with no levels needed."""
    for big in sv.world_of(save).hexes:
        local = sv.local_of(save, big)
        for h, nook in sorted(local.nooks.items()):
            if "creature" in nook.finds and not nook.need:
                return big, h, nook
    raise AssertionError("no sleeper in this world")


def _beside_sleeper():
    save = sv.start_trip(_new())
    big, h, nook = _sleeper_nook(save)
    return {**save, "at": list(big), "spot": list(h)}, big, h, nook


def test_a_sleeper_is_its_lands_mythical_champion_and_always_the_same():
    save, big, h, _ = _beside_sleeper()
    c = cr.sleeper(save["seed"], big, h)
    assert c == cr.sleeper(save["seed"], big, h)
    assert c.tier == "champion" and c.species in wp.MYTHICAL and c.level >= cr.SLEEPER_LEAST
    region = sv.world_of(save).hexes[big].region
    if region in wd.REGIONS:
        assert wp.SPECIES_TYPES[c.species][0] == region
    assert cr.sleeper(save["seed"], big, h, 2).level >= c.level  # relics stir it too


def test_you_can_wake_a_sleeper_and_running_lets_it_sleep_again():
    save, big, h, _ = _beside_sleeper()
    shown = sv.screen(save)
    assert "asleep in here" in shown["text"]
    labels = [o["label"] for o in shown.get("options", [])] or [shown["label"]]
    assert st.WAKE_LABEL in labels
    fight = sv.act(save, "wake")
    assert fight["battle"]["tier"] == "champion"
    assert sv.view(fight)["battle"]["looks"]
    ran = sv.flee(fight)
    assert not ran["battle"] and "asleep in here" in sv.screen(ran)["text"]


def test_beating_a_sleeper_pays_its_hoard_once_and_leaves_you_in_the_nook(monkeypatch):
    save, big, h, _ = _beside_sleeper()
    fight = sv.act(save, "wake")
    before = dict(fight["items"])
    monkeypatch.setattr(sv.bt, "turn", lambda b, team, pets, picks, rng, mana: ({**b, "over": "won", "log": []}, pets, mana))
    done = sv.battle_turn(fight, [])
    got = {k: v - before.get(k, 0) for k, v in done["items"].items() if v != before.get(k, 0)}
    assert sum(got.values()) == 3 and len(got) == 2
    assert any(k in sh.LOOT_BIG for k in got) and any(k in sh.LOOT_PAIRS for k in got)
    assert any(e["kind"] == "coins" and e["amount"] == sh.LOOT_COINS_PER_LEVEL * fight["battle"]["level"] for e in done["events"])
    left = sv.end_battle(done)
    assert left["at"] == list(big) and left["spot"] == list(h)
    shown = sv.screen(left)
    assert "hollow" in shown["text"] and shown["action"] != "wake"
    with pytest.raises(sv.WanderError):
        sv.act(left, "wake")
