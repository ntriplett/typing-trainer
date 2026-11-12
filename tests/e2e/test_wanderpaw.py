"""Real-browser e2e tests for Wanderpaw (PLAN.md 11n): setting off on a
trip and walking by typing, and the lab's small maps and gallery."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(autouse=True)
def no_tutorial(page: Page, live_server):
    """These tests are about the game itself (test_wanderpaw_story.py has Pip's tutorial)."""
    page.request.post(f"{live_server}/api/wander/tutorial", data={"step": "skip"})


def test_set_off_and_walk_by_typing(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#where-name")).to_have_text("Camp")
    page.click("#day-go")  # good morning!
    # between trips: pick a party (no pets yet, so starters come)
    expect(page.locator("#picker")).to_be_visible()
    expect(page.locator("#picker-keys")).to_contain_text("Starters coming")
    page.keyboard.press("Enter")
    expect(page.locator("#energy")).to_be_visible()
    expect(page.locator("#picker")).to_be_hidden()
    full = page.locator("#energy-text").inner_text()
    page.wait_for_function("targets.length > 0")
    word = page.evaluate("targets[0].word")
    to = page.evaluate("targets[0].hex")
    page.keyboard.type(word)
    page.wait_for_function(f"state.local.spot[0] === {to[0]} && state.local.spot[1] === {to[1]}")
    expect(page.locator("#energy-text")).not_to_have_text(full)


def test_lab_opens_small_maps_and_the_gallery(page: Page, live_server):
    page.goto(f"{live_server}/wander-lab")
    expect(page.locator("#local-section")).to_be_visible()  # opens on your own place
    page.click("#gallery-button")
    expect(page.locator("#gallery figure").first).to_be_visible()
    assert page.locator("#gallery figure").count() >= 15


def test_go_in_to_a_quest_giver_and_take_the_quest(page: Page, live_server):
    from app.wanderpaw import quests as qs

    page.goto(f"{live_server}/wanderpaw")
    seed = page.request.get(f"{live_server}/api/wander-lab/world").json()["seed"]
    g = qs.plan(seed).givers["leaf:leaf"]
    page.request.post(f"{live_server}/api/wander/trip/start", data={})
    page.request.post(f"{live_server}/api/wander-lab/teleport", data={"q": g.town[0], "r": g.town[1], "spot": list(g.house)})
    page.reload()
    page.wait_for_function("state && state.screen")
    page.keyboard.press("Enter")
    expect(page.locator("#screen-title")).to_have_text("Nanny Bramble")
    expect(page.locator("#screen-text")).to_contain_text("Mind the turnips")  # just a greeting
    expect(page.locator("#screen-portrait")).to_be_visible()
    page.keyboard.press("2")  # who are you?
    expect(page.locator("#screen-text")).to_contain_text("I keep the hedges")
    page.keyboard.press("1")  # can I help?
    expect(page.locator("#screen-text")).to_contain_text("Garden Shears")
    expect(page.locator("#screen-text .wander-quest-item")).to_have_text("Garden Shears")
    page.keyboard.press("1")  # I'll find them
    page.wait_for_function("state.quests.length === 1")
    page.keyboard.press("Escape")
    expect(page.locator("#keys")).to_contain_text("Go in: Nanny Bramble")
    page.keyboard.press("2")  # the journal
    expect(page.locator("#menu-body")).to_contain_text("Garden Shears")
    page.keyboard.press("Escape")
    expect(page.locator("#menu")).to_be_hidden()
    page.keyboard.press("Escape")  # go home?
    expect(page.locator("#menu-title")).to_have_text("Heading home?")


def test_tough_creatures_show_both_types_and_the_party_book_shows_this_levels_xp(page: Page, live_server, tmp_path):
    from app import db, pet_genes
    from app.wanderpaw import critters as cr
    from app.wanderpaw import hexes as hx
    from app.wanderpaw import local as lc
    from app.wanderpaw import pets as wp
    from app.wanderpaw import world as wd

    page.goto(f"{live_server}/wanderpaw")
    with db.open_db(tmp_path / "e2e.db") as conn:
        fox = db.add_v3_pet(conn, 1, pet_genes.roll("fox", None, None, 1), "Rusty", "shop")
    # the lab's level button goes by this level's real cost
    assert page.request.post(f"{live_server}/api/wander-lab/xp", data={"pet_id": fox, "xp": wp.xp_for(3) + 10}).ok
    page.goto(f"{live_server}/wander-lab")
    expect(page.locator(f'#lab-pets [data-xp="{fox}"]').first).to_have_attribute("data-n", str(wp.xp_for(4) - wp.xp_for(3) - 10))

    page.goto(f"{live_server}/wanderpaw")
    page.request.post(f"{live_server}/api/wander/levelup", data={})  # the lab's level 2 pop-up
    page.request.post(f"{live_server}/api/wander/levelup", data={"choice": "healer"})  # and level 3's
    page.reload()
    seed = page.request.get(f"{live_server}/api/wander-lab/world").json()["seed"]
    day = page.request.post(f"{live_server}/api/wander/trip/start", data={}).json()["stats"]["trips"]
    world = wd.generate(seed)
    spots = ((big, h, c) for big in sorted(world.hexes) for h, c in sorted(cr.at(seed, big, day).items()) if c.second)
    big, h, c = next(spots)
    local = lc.generate(seed, big)
    beside = next(n for n in hx.neighbors(h) if n in lc.CELL_SET and local.walkable(n) and n not in cr.at(seed, big, day))
    page.request.post(f"{live_server}/api/wander-lab/teleport", data={"q": big[0], "r": big[1], "spot": list(beside)})
    page.reload()
    page.wait_for_function("state && state.trip")
    page.keyboard.press("3")
    expect(page.locator("#party-scene")).to_be_visible()  # the whole party first
    expect(page.locator("#wander-local")).to_be_hidden()
    page.keyboard.press("ArrowDown")
    detail = page.locator("#party-detail")
    expect(detail).to_contain_text(f"10 / {wp.xp_for(4) - wp.xp_for(3)}")
    expect(detail.locator(".wander-level")).to_have_text("Level 3")
    expect(detail.locator(".wander-move")).to_have_count(6)
    page.keyboard.press("Escape")
    expect(page.locator("#party")).to_be_hidden()

    g = lc.to_world(big, h)
    page.request.post(f"{live_server}/api/wander/walk", data={"q": g[0], "r": g[1]})
    page.reload()
    foe = page.locator("#battle-foe-info")
    expect(foe).to_contain_text(f"level {c.level}")
    expect(foe.locator(".type-chip")).to_have_count(2)
    expect(page.locator("#battle-team .wander-move")).to_have_count(12)  # six each, the same cards as the party's
    # words for the one picking now: Rusty's Healer focus just works, so it has one less
    expect(page.locator("#battle-team .wander-word")).to_have_count(5)
    expect(page.locator('#battle-team [data-move="healer"]')).to_contain_text("Always on")


def test_level_ups_pop_up_in_turn_and_level_five_asks_for_a_type(page: Page, live_server, tmp_path):
    from app import db, pet_genes
    from app.wanderpaw import pets as wp

    page.goto(f"{live_server}/wanderpaw")
    with db.open_db(tmp_path / "e2e.db") as conn:
        fox = db.add_v3_pet(conn, 1, pet_genes.roll("fox", None, None, 1), "Rusty", "shop")
    page.request.post(f"{live_server}/api/wander-lab/xp", data={"pet_id": fox, "xp": wp.xp_for(5)})
    page.reload()
    level, keys, choice = page.locator("#levelup-detail .wander-level"), page.locator("#levelup-keys"), page.locator("#levelup-choice")
    expect(page.locator("#wander-local")).to_be_hidden()  # a whole screen, like the party book's
    expect(level).to_have_text("Level 2")
    expect(page.locator("#levelup-stats")).to_contain_text("Power")
    expect(page.locator("#levelup-detail .wander-move")).to_have_count(6)
    expect(keys).to_contain_text("more to celebrate")
    page.keyboard.press("Enter")
    # level 3: four focuses in its own type, and it has to choose
    expect(level).to_have_text("Level 3")
    expect(choice.locator(".wander-levelup-option")).to_have_count(4)
    expect(choice).to_contain_text("Cozy Hearth")
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    expect(level).to_have_text("Level 3")
    # a number shows it in the six moves; Enter makes it so
    page.keyboard.press("1")
    expect(page.locator('#levelup-detail [data-move="healer"].fresh')).to_contain_text("Always on")
    expect(page.locator('#levelup-detail [data-move="guard"]')).to_have_count(0)
    page.keyboard.press("Enter")
    expect(level).to_have_text("Level 4")
    expect(page.locator('#levelup-detail [data-move="healer"]')).to_have_count(1)  # it shows on later pop-ups
    page.keyboard.press("Enter")
    expect(level).to_have_text("Level 5")
    expect(choice.locator(".wander-levelup-option")).to_have_count(2)
    page.keyboard.press("Enter")
    expect(level).to_have_text("Level 5")
    page.keyboard.press("2")
    expect(page.locator("#levelup-detail .type-chip")).to_have_count(2)  # the preview
    page.keyboard.press("Enter")
    # the same level goes on: what does the new attack replace? Healer's already taken guard
    expect(level).to_have_text("Level 5")
    expect(choice.locator(".wander-levelup-option")).to_have_count(3)
    expect(choice).to_contain_text("Cheer")
    page.keyboard.press("Enter")
    expect(page.locator('#levelup-detail [data-move="attack2"]')).to_have_count(0)
    page.keyboard.press("3")
    expect(page.locator('#levelup-detail [data-move="attack2"].fresh')).to_be_visible()
    expect(page.locator('#levelup-detail [data-move="rest"]')).to_have_count(0)
    page.keyboard.press("Enter")
    expect(page.locator("#levelup")).to_be_hidden()
    expect(page.locator("#day-scene")).to_be_visible()
    me = next(p for p in page.request.get(f"{live_server}/api/wander/pets").json()["pets"] if p["id"] == fox)
    assert len(me["types"]) == 2 and me["choices"] is None and me["focus"] == "healer" and me["swaps"] == {"rest": "attack2"}
    # the party book shows it too
    page.keyboard.press("3")
    page.keyboard.press("ArrowDown")
    expect(page.locator('#party-detail [data-move="healer"]')).to_contain_text("Cozy Hearth")

    # type names in text: all caps, in the type's color
    word = page.locator('#party-detail [data-move="attack"] .type-word').first
    expect(word).to_have_text("EMBER")
    expect(word).to_have_css("color", "rgb(200, 67, 47)")
    expect(page.locator('#party-detail [data-move="attack2"]')).to_be_visible()


def test_level_seven_shows_the_mix_and_lets_it_replace_any_move(page: Page, live_server, tmp_path):
    from app import db, pet_genes
    from app.wanderpaw import pets as wp

    page.goto(f"{live_server}/wanderpaw")
    with db.open_db(tmp_path / "e2e.db") as conn:
        fox = db.add_v3_pet(conn, 1, pet_genes.roll("fox", None, None, 1), "Rusty", "shop")
    page.request.post(f"{live_server}/api/wander-lab/xp", data={"pet_id": fox, "xp": wp.xp_for(7)})
    finish = lambda choice=None: page.request.post(f"{live_server}/api/wander/levelup", data={"choice": choice}).json()  # noqa: E731
    finish()
    data = finish("healer")
    data = finish()
    data = finish(data["levelups"][0]["choose"]["options"][0]["id"])
    data = finish("rest")
    data = finish()
    assert data["levelups"][0]["choose"]["kind"] == "mix"
    page.reload()
    choice = page.locator("#levelup-choice")
    expect(choice.locator(".wander-levelup-new [data-move='mix']")).to_be_visible()
    expect(choice.locator(".wander-levelup-option")).to_have_count(6)
    page.keyboard.press("Enter")  # it has to be chosen
    expect(page.locator("#levelup")).to_be_visible()
    page.keyboard.press("1")
    expect(page.locator("#levelup-detail [data-move='mix'].fresh")).to_be_visible()
    expect(page.locator("#levelup-detail [data-move='attack']")).to_have_count(0)
    page.keyboard.press("3")  # changed its mind: a different slot
    expect(page.locator("#levelup-detail [data-move='attack']")).to_have_count(1)
    page.keyboard.press("Enter")
    expect(page.locator("#levelup")).to_be_hidden()
    me = next(p for p in page.request.get(f"{live_server}/api/wander/pets").json()["pets"] if p["id"] == fox)
    assert "mix" in me["swaps"].values()


def test_level_nine_shows_plus_names_and_lets_a_move_upgrade(page: Page, live_server, tmp_path):
    from app import db, pet_genes
    from app.wanderpaw import pets as wp

    page.goto(f"{live_server}/wanderpaw")
    with db.open_db(tmp_path / "e2e.db") as conn:
        fox = db.add_v3_pet(conn, 1, pet_genes.roll("fox", None, None, 1), "Rusty", "shop")
    page.request.post(f"{live_server}/api/wander-lab/xp", data={"pet_id": fox, "xp": wp.xp_for(9)})
    finish = lambda choice=None: page.request.post(f"{live_server}/api/wander/levelup", data={"choice": choice}).json()  # noqa: E731
    finish()
    finish("healer")
    data = finish()
    data = finish(data["levelups"][0]["choose"]["options"][0]["id"])
    finish("rest")
    finish()
    finish("attack2")
    finish()
    page.reload()
    choice = page.locator("#levelup-choice")
    expect(page.locator("#levelup-detail .wander-level")).to_have_text("Level 9")
    expect(page.locator('#levelup-detail [data-move="healer"]')).to_contain_text("Cozy Hearth+")
    expect(choice).to_contain_text("grew stronger")
    page.keyboard.press("Enter")  # it has to be chosen
    expect(page.locator("#levelup")).to_be_visible()
    page.keyboard.press("1")
    expect(page.locator('#levelup-detail [data-move="attack"].fresh')).to_contain_text("EMBER attack+")
    page.keyboard.press("Enter")
    expect(page.locator("#levelup")).to_be_hidden()
    me = next(p for p in page.request.get(f"{live_server}/api/wander/pets").json()["pets"] if p["id"] == fox)
    assert me["upgrades"] == ["attack"]


def test_move_cards_show_icons_with_tooltips(page: Page, live_server, tmp_path):
    from app import db, pet_genes

    page.goto(f"{live_server}/wanderpaw")
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_v3_pet(conn, 1, pet_genes.roll("fox", None, None, 1), "Rusty", "shop")
    page.reload()
    page.wait_for_function("state")
    page.keyboard.press("3")
    page.keyboard.press("ArrowDown")
    detail = page.locator("#party-detail")
    expect(detail.locator('[data-move="attack"] .wander-icon-dot')).to_have_count(2)
    big = detail.locator('[data-move="big"]')
    expect(big.locator(".wander-icon-dot")).to_have_count(4)
    expect(big.locator('[data-icon="haste"]')).to_have_attribute("title", "Fast: goes first.")
    expect(big.locator('[data-icon="hit"]')).to_have_attribute("title", "Very high damage.")
    expect(big.locator('[data-icon="mark"]')).to_have_attribute("title", "Leaves Enemy Glowing.")
    expect(big.locator(".wander-move-cost")).to_have_text("6")
    expect(big.locator('[data-icon="mana"]')).to_have_attribute("title", "Mana cost.")
    expect(detail.locator('[data-move="guard"] [data-icon="shield"]')).to_be_visible()
    expect(detail.locator('[data-move="focus"] .wander-move-icons')).to_have_count(0)


def test_the_move_lab_draws_every_tile(page: Page, live_server):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/move-lab")
    tiles = page.locator("#lab-groups .wander-moves > li")
    expect(page.locator("#lab-count")).to_contain_text("tiles")
    every = page.request.get(f"{live_server}/api/move-lab").json()["groups"]
    count = sum(len(g["tiles"]) for g in every)
    assert tiles.count() == count > 130
    for view in ("party", "battle", "choice"):
        for across in ("3", "4"):
            page.select_option("#opt-view", view)
            page.select_option("#opt-across", across)
            expect(tiles).to_have_count(count)
            expect(page.locator("#lab-count")).to_contain_text("tiles")
            assert not errors, (view, across, errors)
    # today's sizes all fit: anything flagged here is a tile to fix
    for view in ("party", "battle", "choice"):
        page.select_option("#opt-view", view)
        page.select_option("#opt-across", "3")
        expect(page.locator("#lab-count")).to_contain_text("They all fit")


def test_level_eleven_opens_a_seventh_slot_four_across(page: Page, live_server, tmp_path):
    from app import db, pet_genes
    from app.wanderpaw import pets as wp

    page.goto(f"{live_server}/wanderpaw")
    with db.open_db(tmp_path / "e2e.db") as conn:
        fox = db.add_v3_pet(conn, 1, pet_genes.roll("fox", None, None, 1), "Rusty", "shop")
        db.save_wander_pet(conn, 1, fox, {"xp": wp.xp_for(10), "second": "leaf", "second_at": 5, "partners": {}, "starred": False,
                                          "focus": "healer", "swaps": {"rest": "attack2", "attack2": "mix"}, "upgrades": ["big"], "extra": []})
    page.request.post(f"{live_server}/api/wander-lab/xp", data={"pet_id": fox, "xp": wp.xp_for(11) - wp.xp_for(10)})
    page.reload()
    choice = page.locator("#levelup-choice")
    expect(choice).to_contain_text("7th slot")
    expect(choice.locator(".wander-levelup-option")).to_have_count(3)
    page.keyboard.press("Enter")  # it has to be chosen
    expect(choice).to_contain_text("7th slot")
    page.keyboard.press("1")
    moves = page.locator("#levelup-detail .wander-moves")
    expect(moves.locator(".wander-move")).to_have_count(7)
    expect(moves).to_have_class(re.compile("wide"))
    page.keyboard.press("Enter")
    expect(choice).to_contain_text("can upgrade a move")
    page.keyboard.press("1")
    page.keyboard.press("Enter")
    expect(page.locator("#levelup")).to_be_hidden()
    page.keyboard.press("3")
    page.keyboard.press("ArrowDown")
    expect(page.locator("#party-detail .wander-move")).to_have_count(7)


def test_mix_moves_are_two_colored_as_level_up_choices(page: Page, live_server):
    page.goto(f"{live_server}/move-lab")
    page.select_option("#opt-view", "choice")
    mixes = page.locator(".move-lab-group", has_text="Mixes").first
    style = mixes.locator(".wander-levelup-option").first.get_attribute("style")
    assert "linear-gradient" in style


def test_a_guardian_wall_shows_used_up_once_it_has_worn_off(page: Page, live_server, tmp_path):
    from app import db, pet_genes
    from app.wanderpaw import critters as cr
    from app.wanderpaw import hexes as hx
    from app.wanderpaw import local as lc
    from app.wanderpaw import pets as wp
    from app.wanderpaw import world as wd

    page.goto(f"{live_server}/wanderpaw")
    with db.open_db(tmp_path / "e2e.db") as conn:
        fox = db.add_v3_pet(conn, 1, pet_genes.roll("fox", None, None, 1), "Rusty", "shop")
        db.add_v3_pet(conn, 1, pet_genes.roll("bunny", None, None, 2), "Clover", "shop")
        db.save_wander_pet(conn, 1, fox, {"xp": wp.xp_for(4), "second": None, "second_at": None, "partners": {}, "starred": False, "focus": "guardian"})
    seed = page.request.get(f"{live_server}/api/wander-lab/world").json()["seed"]
    day = page.request.post(f"{live_server}/api/wander/trip/start", data={}).json()["stats"]["trips"]
    world = wd.generate(seed)
    big, h = next((b, h) for b in sorted(world.hexes) if world.hexes[b].region == wd.HEARTLAND for h in sorted(cr.at(seed, b, day)))
    local = lc.generate(seed, big)
    beside = next(n for n in hx.neighbors(h) if n in lc.CELL_SET and local.walkable(n) and n not in cr.at(seed, big, day))
    page.request.post(f"{live_server}/api/wander-lab/teleport", data={"q": big[0], "r": big[1], "spot": list(beside)})
    g = lc.to_world(big, h)
    page.request.post(f"{live_server}/api/wander/walk", data={"q": g[0], "r": g[1]})
    wall = page.locator('#battle-team [data-move="guardian"]')
    # Guarding, the fight lasts: past round 2 its wall is used up
    for _ in range(2):
        moves = [{"move": "guard", "slips": 0}] * 2
        page.request.post(f"{live_server}/api/wander/battle/turn", data={"moves": [{"move": "guard", "slips": 0}, {"move": "focus", "slips": 0}]})
    page.goto(f"{live_server}/wanderpaw")
    expect(wall.locator("s")).to_be_visible()
    expect(wall).to_contain_text("Used up")


def test_the_creature_shows_its_next_move_and_is_drawn_on_a_clean_canvas(page: Page, live_server, tmp_path):
    from app import db, pet_genes
    from app.wanderpaw import critters as cr
    from app.wanderpaw import hexes as hx
    from app.wanderpaw import local as lc
    from app.wanderpaw import world as wd

    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/wanderpaw")
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_v3_pet(conn, 1, pet_genes.roll("fox", None, None, 1), "Rusty", "shop")
    seed = page.request.get(f"{live_server}/api/wander-lab/world").json()["seed"]
    day = page.request.post(f"{live_server}/api/wander/trip/start", data={}).json()["stats"]["trips"]
    world = wd.generate(seed)
    big, h = next((b, h) for b in sorted(world.hexes) if world.hexes[b].region == wd.HEARTLAND for h in sorted(cr.at(seed, b, day)))
    local = lc.generate(seed, big)
    beside = next(n for n in hx.neighbors(h) if n in lc.CELL_SET and local.walkable(n) and n not in cr.at(seed, big, day))
    page.request.post(f"{live_server}/api/wander-lab/teleport", data={"q": big[0], "r": big[1], "spot": list(beside)})
    g = lc.to_world(big, h)
    page.request.post(f"{live_server}/api/wander/walk", data={"q": g[0], "r": g[1]})
    page.reload()
    intent = page.locator("#battle-intent")
    expect(intent).to_be_visible()
    expect(intent).to_have_attribute("title", re.compile("Enemy will attack"))
    assert intent.locator(".wander-icon-dot").count() >= 1
    # an old creature doesn't stay on the canvas underneath a new one
    cleared = page.evaluate("""() => {
      const c = document.getElementById("battle-foe");
      const ctx = c.getContext("2d");
      ctx.fillStyle = "#ff0000";
      ctx.fillRect(0, 0, c.width, c.height);
      paintPet(c, { genes: state.battle.looks, growth: 10 }, 5, true);
      return ctx.getImageData(0, 0, 1, 1).data[3];
    }""")
    assert cleared == 0
    assert not errors


def _set_up(page, live_server, tmp_path, items=None, coins=20000):
    from app import db
    from app.wanderpaw import save as sv
    page.goto(f"{live_server}/wanderpaw")
    page.wait_for_function("state && state.local")
    page.request.post(f"{live_server}/api/wander/trip/start", data={})
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, coins - db.get_coin_balance(conn, 1), "test")
        save = sv.load(conn, 1)
        world = sv.world_of(save)
        big, spot = next((h, s) for h, x in world.hexes.items() if x.special == "town" and x.region == "dream" for s, role in sv.local_of(save, h).buildings.items() if role == "shop")
        sv.teleport(conn, 1, big, spot)
        if items:
            save = sv.load(conn, 1)
            db.save_wander(conn, 1, {**save, "items": items})


def test_buy_at_a_town_shop(page: Page, live_server, tmp_path):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _set_up(page, live_server, tmp_path)
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#keys")).to_contain_text("Go in", timeout=5000)
    page.keyboard.press("Enter")
    expect(page.locator("#screen")).to_contain_text("Alchemist")
    page.keyboard.press("Enter")
    expect(page.locator("#menu-body")).to_contain_text("Mana Drop")
    expect(page.locator("#menu-body")).to_contain_text("Friendship Token")
    page.keyboard.press("Enter")  # the first thing on the shelf
    expect(page.locator("#menu-body")).to_contain_text("19,500")
    expect(page.locator("#menu-body")).to_contain_text("you have 1")
    expect(page.locator("#coin-count")).to_have_text("19,500")  # the top bar's coins drop too
    expect(page.locator("#news #wander-message")).to_contain_text("You bought a Mana Drop")  # notes go in the news bar
    page.keyboard.press("Escape")
    expect(page.locator("#screen")).to_contain_text("Alchemist")
    assert not errors


def _in_a_fight(page, live_server, tmp_path, items):
    from app import db
    from app.wanderpaw import critters as cr
    from app.wanderpaw import save as sv
    _set_up(page, live_server, tmp_path, items=items)
    with db.open_db(tmp_path / "e2e.db") as conn:
        save = sv.load(conn, 1)
        c = cr.Critter("g:0,0:0,0", (0, 0), (0, 0), "dog", "splash", 3, False, 7, None, "")
        save = sv._start_battle(save, c)
        db.save_wander(conn, 1, {**save, "trip": {**save["trip"], "mana": [1 for _ in save["trip"]["mana"]]}, "events": []})


def test_the_bag_and_guidebook_open_mid_fight_and_dont_cost_a_turn(page: Page, live_server, tmp_path):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _in_a_fight(page, live_server, tmp_path, {"Mana Drop": 2})
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#battle")).to_be_visible()
    expect(page.locator("#battle-bag")).to_be_visible()
    expect(page.locator("#battle-guide")).to_be_visible()
    page.keyboard.press("1")
    expect(page.locator("#menu-body")).to_contain_text("Mana Drop")
    page.keyboard.press("1")  # the first thing in the bag
    expect(page.locator("#battle")).to_be_visible()
    expect(page.locator(".wander-mana").first).to_contain_text("11")
    page.keyboard.press("2")
    expect(page.locator("#menu-title")).to_have_text("Guidebook")
    expect(page.locator(".wander-type-ring")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#battle")).to_be_visible()
    assert not errors


def test_backspace_spends_a_do_over_token_to_drop_the_word_and_its_slips(page: Page, live_server, tmp_path):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _in_a_fight(page, live_server, tmp_path, {"Do-Over Token": 2})
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#battle")).to_be_visible()
    counter = page.locator("#battle-do-over")
    expect(counter).to_be_visible()
    expect(counter).to_contain_text("2")
    page.keyboard.press("Backspace")  # no word started: nothing to undo, nothing spent
    expect(counter).to_contain_text("2")
    word = page.evaluate("fight.targets[0].word")
    page.keyboard.press(word[0])
    wrong = next(c for c in "zqxj" if c != word[1])
    page.keyboard.press(wrong)
    assert page.evaluate("typer.target && typer.target.slips") == 1
    page.keyboard.press("Backspace")
    expect(counter).to_contain_text("1")
    assert page.evaluate("typer.target") is None
    assert page.evaluate("fight.targets[0].slips") == 0 and page.evaluate("fight.targets[0].typed") == 0
    expect(page.locator("#battle-bag")).to_be_disabled()  # it's not a thing to pick from the bag
    page.keyboard.press(word[0])
    page.keyboard.press("Backspace")  # the last one
    expect(counter).to_be_hidden()
    page.keyboard.press(word[0])
    page.keyboard.press("Backspace")  # none left: the word stays
    expect(page.locator("#news #wander-message")).to_contain_text("No Do-Over Tokens")
    assert page.evaluate("typer.target !== null")
    assert not errors


def test_the_guidebook_turns_pages_and_shows_match_ups(page: Page, live_server, tmp_path):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _set_up(page, live_server, tmp_path)
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#keys")).to_contain_text("Go in", timeout=5000)
    page.keyboard.press("6")
    expect(page.locator("#menu-title")).to_have_text("Guidebook")
    expect(page.locator(".wander-type-chart")).to_contain_text("0.7x")
    page.keyboard.press("ArrowRight")
    result = page.locator(".wander-guide-result")
    expect(result).to_contain_text("2x")  # splash on ember, the page's opening pair
    page.locator("[data-guide-me='shock']").click()
    expect(result).to_contain_text("1.5x")  # shock is strong against ember
    page.keyboard.press("j")
    for _ in range(6):
        page.keyboard.press("ArrowRight")
        expect(page.locator(".wander-guide-page")).not_to_be_empty()
    page.keyboard.press("ArrowRight")
    expect(page.locator(".wander-type-chart")).to_be_visible()  # back round to the start
    assert not errors


def test_using_something_from_the_bag_while_walking(page: Page, live_server, tmp_path):
    _set_up(page, live_server, tmp_path, items={"Way-Home Charm": 1})
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#keys")).to_contain_text("Go in", timeout=5000)
    page.keyboard.press("1")
    expect(page.locator("#menu-body")).to_contain_text("Way-Home Charm")
    page.keyboard.press("Enter")
    expect(page.locator("#menu")).to_be_hidden()
    expect(page.locator("#where-name")).to_contain_text("Camp")


def test_befriending_button_calls_out_the_cost_on_the_win_page(page: Page, live_server, tmp_path):
    from app import db
    from app.wanderpaw import save as sv
    _in_a_fight(page, live_server, tmp_path, {})
    with db.open_db(tmp_path / "e2e.db") as conn:
        save = sv.load(conn, 1)
        db.save_wander(conn, 1, {**save, "battle": {**save["battle"], "over": "won"}, "trip": {**save["trip"], "mana": [50 for _ in save["trip"]["mana"]]}})
    page.goto(f"{live_server}/wanderpaw")
    button = page.locator("#befriend-button")
    expect(button).to_contain_text("Befriend")
    expect(button).to_contain_text("3")  # the level 3 creature's mana, from each fighter
    button.click()
    expect(button).to_have_count(0)
    expect(page.locator("#battle-log")).to_contain_text("wait for you at Camp")


def test_friends_wait_at_camp_and_can_be_asked_to_leave(page: Page, live_server, tmp_path):
    from app import db
    from app import pet_genes as g
    from app.wanderpaw import save as sv
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _set_up(page, live_server, tmp_path, items={"Friendship Token": 1})
    with db.open_db(tmp_path / "e2e.db") as conn:
        save = sv.load(conn, 1)
        friends = [{"id": "a", "species": "goat", "name": "Goat", "level": 4, "genes": g.roll("goat", None, None, 1)},
                   {"id": "b", "species": "dog", "name": "Dog", "level": 2, "genes": g.roll("dog", None, None, 2)}]
        db.save_wander(conn, 1, {**save, "camp_friends": friends})
        sv.teleport(conn, 1, (0, 0), (0, 0))
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#keys")).to_contain_text("Rest by the fire", timeout=5000)
    page.keyboard.press("Enter")
    page.get_by_role("button", name="Visit your friends").click()
    menu = page.locator("#menu-body")
    expect(menu).to_contain_text("Goat")
    expect(menu).to_contain_text("Dog")
    page.get_by_role("button", name="Ask them to leave").click()
    expect(menu).not_to_contain_text("Goat")
    page.get_by_role("button", name="Give a Friendship Token").click()
    expect(page.locator("#levelup")).to_be_visible()
    assert not errors


def test_guidebook_tabs_and_shop_rows_work_with_the_mouse(page: Page, live_server, tmp_path):
    _set_up(page, live_server, tmp_path)
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#keys")).to_contain_text("Go in", timeout=5000)
    page.locator("[data-menu='guide']").click()
    page.get_by_role("button", name="Match-ups").click()
    expect(page.locator(".wander-guide-result")).to_be_visible()
    page.get_by_role("button", name="Next page").click()
    expect(page.locator(".wander-guide-page")).to_contain_text("Found")
    page.get_by_role("button", name="Previous page").click()
    expect(page.locator(".wander-guide-result")).to_be_visible()
    page.locator("#menu-close").click()
    expect(page.locator("#menu")).to_be_hidden()
    page.keyboard.press("Enter")
    expect(page.locator("#screen")).to_contain_text("Alchemist")
    page.keyboard.press("Enter")
    page.locator("#menu-body li[data-i='2']").click()
    page.get_by_role("button", name="Buy").click()
    expect(page.locator("#menu-body")).to_contain_text("19,200")
    expect(page.locator("#menu-body img.wander-item-icon").first).to_be_visible()


def test_the_guidebook_page_isnt_rebuilt_while_you_read_it(page: Page, live_server, tmp_path):
    _set_up(page, live_server, tmp_path)
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#keys")).to_contain_text("Go in", timeout=5000)
    page.keyboard.press("6")
    expect(page.locator(".wander-guide-tabs")).to_be_visible()
    page.evaluate("document.querySelector('.wander-guide-page').dataset.same = 'yes'")
    page.wait_for_timeout(400)  # the map's animating under it
    assert page.evaluate("document.querySelector('.wander-guide-page').dataset.same") == "yes"


def test_every_shop_item_has_a_picture(page: Page, live_server, tmp_path):
    from app.wanderpaw import shop as sh
    page.goto(f"{live_server}/wanderpaw")
    missing = page.evaluate("(names) => names.filter((n) => !ITEM_ART[n])", list(sh.ITEMS))
    assert missing == []


EMOJI = re.compile("[\u2600-\u27bf\U0001f000-\U0001faff]")


def test_the_guidebook_uses_the_games_own_icons_not_emoji(page: Page, live_server, tmp_path):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _set_up(page, live_server, tmp_path)
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#keys")).to_contain_text("Go in", timeout=5000)
    page.keyboard.press("6")
    expect(page.locator(".wander-guide-tabs")).to_be_visible()
    for tab in ("Types", "Match-ups", "Combo chart", "Combos found", "Marks", "Effects", "How fights work", "The lands"):
        page.get_by_role("button", name=tab).click()
        assert not EMOJI.search(page.locator("#menu-body").inner_text()), tab
    page.get_by_role("button", name="Marks", exact=True).click()
    expect(page.locator(".wander-guide-card .wander-icon-burst")).to_have_count(5)  # a mark looks like it does on a move
    page.get_by_role("button", name="How fights work").click()
    expect(page.locator(".wander-guide-card .wander-icon-mix").first).to_be_visible()
    assert not errors


def test_every_effect_has_a_picture_in_battle_and_the_guidebook(page: Page, live_server):
    from app.wanderpaw import terms
    page.goto(f"{live_server}/wanderpaw")
    names = [n.lower() for n in terms.EFFECTS]
    assert page.evaluate("(names) => names.filter((n) => !EFFECT_ICONS[n])", names) == []
    in_battle = page.evaluate("Object.values(EFFECT_NAMES).filter((n) => !EFFECT_ICONS[n])")
    assert in_battle == []


def test_marks_and_effects_show_their_icons_on_the_enemy_in_battle(page: Page, live_server, tmp_path):
    from app import db
    from app.wanderpaw import save as sv
    _in_a_fight(page, live_server, tmp_path, {})
    with db.open_db(tmp_path / "e2e.db") as conn:
        save = sv.load(conn, 1)
        db.save_wander(conn, 1, {**save, "battle": {**save["battle"], "marks": {"soaked": 2}, "effects": {"thorns": 2, "hardened": 1}}})
    page.goto(f"{live_server}/wanderpaw")
    info = page.locator("#battle-foe-info")
    expect(info.locator(".wander-mark .wander-icon-burst")).to_have_count(1)
    expect(info.locator(".wander-mark .wander-icon-dot")).to_have_count(1)  # thorns: it gets hurt
    expect(info.locator(".wander-mark .wander-icon-shield")).to_have_count(1)  # braced


def test_the_guidebook_fits_without_scrolling_and_the_bag_stays_red(page: Page, live_server):
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{live_server}/wanderpaw")
    page.wait_for_function("state && pets")
    page.keyboard.press("Enter")  # good morning
    page.keyboard.press("Enter")  # set off
    page.wait_for_function("state.trip && !busy")
    assert page.evaluate("""getComputedStyle(document.querySelector('[data-menu="bag"]')).getPropertyValue('--book').trim()""") == "#b8432f"
    page.keyboard.press("6")
    page.wait_for_selector(".wander-guide-page")
    for at in range(page.evaluate("GUIDE_PAGES.length")):
        page.wait_for_function(f"menu.page === {at} && document.querySelector('.wander-guide-tab.on').textContent === GUIDE_PAGES[{at}]")
        sizes = page.evaluate("""(() => {
            const g = document.querySelector('.wander-guide-page');
            const m = document.getElementById('menu').getBoundingClientRect();
            return {over: g.scrollHeight - g.clientHeight, wide: g.scrollWidth - g.clientWidth, top: m.top, bottom: m.bottom};
        })()""")
        assert sizes["over"] <= 0 and sizes["wide"] <= 0, (at, sizes)
        assert sizes["top"] >= 0 and sizes["bottom"] <= 800
        page.keyboard.press("ArrowRight")


def test_a_place_paints_the_same_every_time_and_water_is_where_the_mermaid_swims(page: Page, live_server):
    from app.wanderpaw import pets as wp

    mermaid = {"species": "mermaid", "name": "Mira", "growth": 10, "genes": wp.looks("mermaid", 1)}
    page.goto(f"{live_server}/wanderpaw")
    page.wait_for_function("state && state.local")
    out = page.evaluate(
        """async (mermaid) => {
          const { scenes } = await (await fetch("/api/scene-lab?seed=3")).json();
          const seen = { same: true, wet: 0, dry: 0, kinds: new Set() };
          for (const s of scenes) {
            const a = WanderScene.build(s.spec, 2);
            seen.same &&= a.background.toDataURL() === WanderScene.build(s.spec, 2).background.toDataURL();
            seen.kinds.add(a.background.toDataURL());
            const swimmer = PetMotion.create([mermaid], a.area, 2 / 3).walkers[0];
            if (a.area.terrain.water.length) seen.wet += swimmer.pool ? 1 : 0;
            else seen.dry += swimmer.pool ? 0 : 1;
            seen.wetTotal = (seen.wetTotal || 0) + (a.area.terrain.water.length ? 1 : 0);
            seen.dryTotal = (seen.dryTotal || 0) + (a.area.terrain.water.length ? 0 : 1);
          }
          return { ...seen, kinds: seen.kinds.size, total: scenes.length };
        }""",
        mermaid,
    )
    assert out["same"]
    assert out["kinds"] == out["total"]  # every place its own picture
    assert out["wet"] == out["wetTotal"] > 0  # water: she swims
    assert out["dry"] == out["dryTotal"] > 0  # none: she just sits


def _home_for_the_evening(page):
    page.click("#go-home")
    page.keyboard.press("1")  # end the day
    expect(page.locator("#day-scene")).to_be_visible()
    page.wait_for_function("liveScene && liveScene.canvasId === 'day-scene' && liveScene.scene.night")


def test_a_new_day_starts_with_the_morning_picture_then_the_picker(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#day-scene")).to_be_visible()
    expect(page.locator("#picker")).to_be_hidden()
    expect(page.locator("#wander-local")).to_be_hidden()  # a whole screen
    expect(page.locator("#day-go")).to_contain_text("Start playing a new day")
    expect(page.locator("#day-stay")).to_be_hidden()
    page.wait_for_function("liveScene && liveScene.canvasId === 'day-scene' && sceneAvatar && !liveScene.scene.night")
    assert page.evaluate("liveScene.scene.spec.setting") == "camp"
    page.click("#day-go")
    expect(page.locator("#day")).to_be_hidden()
    expect(page.locator("#picker")).to_be_visible()
    page.keyboard.press("Escape")  # back a step
    expect(page.locator("#day-scene")).to_be_visible()
    page.keyboard.press("Enter")
    expect(page.locator("#picker")).to_be_visible()
    page.keyboard.press("Enter")
    expect(page.locator("#energy")).to_be_visible()
    page.keyboard.press("Enter")  # Camp's campfire: the picture's here too, by day
    expect(page.locator("#screen-scene")).to_be_visible()
    page.wait_for_function("liveScene.canvasId === 'screen-scene' && !liveScene.scene.night")
    page.keyboard.press("Escape")
    page.keyboard.press("3")
    expect(page.locator("#party-scene")).to_be_visible()


def test_ending_the_day_shows_the_evening_and_you_can_change_your_mind(page: Page, live_server):
    from app.wanderpaw import save as sv

    page.request.post(f"{live_server}/api/wander/trip/start", data={})
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#energy")).to_be_visible()
    _home_for_the_evening(page)
    assert page.evaluate("liveScene.scene.spec.setting") == "camp"
    assert page.evaluate("state.trip !== null")  # nothing's changed yet
    expect(page.locator("#day-go")).to_contain_text("Exit game")
    page.click("#day-stay")  # wait! still playing: right where you were
    expect(page.locator("#day")).to_be_hidden()
    expect(page.locator("#wander-local")).to_be_visible()
    expect(page.locator("#energy")).to_be_visible()
    assert page.evaluate("state.trip !== null")
    _home_for_the_evening(page)
    page.keyboard.press("Enter")  # exit
    page.wait_for_url(f"{live_server}/")
    assert page.request.get(f"{live_server}/api/wander").json()["trip"] is None
    # back another time: morning
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#day-go")).to_contain_text("Start playing a new day")
    page.wait_for_function("liveScene && liveScene.canvasId === 'day-scene' && !liveScene.scene.night")


def test_out_of_energy_shows_the_evening_and_still_playing_keeps_the_books_open(page: Page, live_server, tmp_path):
    from app import db
    from app.wanderpaw import save as sv

    page.goto(f"{live_server}/wanderpaw")
    page.wait_for_function("state && state.local")
    page.request.post(f"{live_server}/api/wander/trip/start", data={})
    with db.open_db(tmp_path / "e2e.db") as conn:
        save = sv.load(conn, 1)
        tired = {**save["trip"], "walk": 1, "pets": [0] * len(save["team"]), "energy": 1}
        db.save_wander(conn, 1, {**save, "trip": tired})
    page.reload()
    page.wait_for_function("targets.length > 0 && !busy")
    # one last step, typed for real
    page.keyboard.type(page.evaluate("targets.find((t) => t.hex).word"))
    page.wait_for_function("state.note === 'napped'")
    expect(page.locator("#wander-message")).to_contain_text("All tired out")
    expect(page.locator("#day-text")).to_contain_text("ready for sleep")
    expect(page.locator("#day-go")).to_contain_text("Exit game")
    page.wait_for_function("liveScene && liveScene.canvasId === 'day-scene' && liveScene.scene.night")
    page.keyboard.press("Escape")  # wait! I still want to play
    expect(page.locator("#day")).to_be_hidden()
    expect(page.locator("#picker")).to_be_hidden()  # no new day from here
    expect(page.locator("#wander-local")).to_be_visible()
    page.keyboard.press("2")
    expect(page.locator("#menu-title")).to_have_text("Journal")
    page.keyboard.press("Escape")
    page.keyboard.press("6")
    expect(page.locator("#menu-title")).to_have_text("Guidebook")
    page.keyboard.press("Escape")
    expect(page.locator("#menu")).to_be_hidden()
    expect(page.locator("#day")).to_be_hidden()
    page.keyboard.press("3")  # still night in the picture
    expect(page.locator("#party-scene")).to_be_visible()
    page.wait_for_function("liveScene.canvasId === 'party-scene' && liveScene.scene.night")
    page.keyboard.press("Escape")
    page.click("#go-home")  # and now home: the same evening
    expect(page.locator("#day-go")).to_contain_text("Exit game")
    page.click("#day-go")
    page.wait_for_url(f"{live_server}/")


def test_camp_friends_are_only_in_the_picture_at_camp(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw")
    page.wait_for_function("state && state.local")
    friend = {"id": "f1", "name": "Buddy", "species": "cat", "genes": {"species": "cat"}}
    names = page.evaluate(
        """(friend) => {
          state.camp_friends = [friend];
          return [scenePets({ special: "camp" }).map((p) => p.name), scenePets({ special: null }).map((p) => p.name)];
        }""",
        friend,
    )
    assert "Buddy" in names[0] and "Buddy" not in names[1]


def test_with_no_day_paid_for_the_morning_points_to_the_arcade(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw")
    page.wait_for_function("state && state.local")
    page.evaluate("state.can_start_day = false; render()")  # (the tests run with free days)
    expect(page.locator("#day-go")).to_contain_text("Go to the arcade")
    expect(page.locator("#day-text")).to_contain_text("2 tokens")
    page.keyboard.press("Enter")
    page.wait_for_url(f"{live_server}/arcade")


def test_a_picture_still_on_its_way_doesnt_replace_a_newer_one(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw?lab=1&ending=1")
    page.wait_for_function("mode === 'ending' && liveScene && liveScene.key.startsWith('ending')")
    page.wait_for_timeout(500)  # anything still on its way has landed
    assert page.evaluate("liveScene.key.startsWith('ending') && liveScene.scene.spec.setting") == "heartstone"


def test_waking_whats_asleep_in_a_cave_starts_a_fight_with_no_go_home_button(page: Page, live_server, tmp_path):
    from app import db
    from app.wanderpaw import save as sv
    from app.wanderpaw import story as st

    page.goto(f"{live_server}/wanderpaw")
    page.wait_for_function("state && state.local")
    page.request.post(f"{live_server}/api/wander/trip/start", data={})
    with db.open_db(tmp_path / "e2e.db") as conn:
        save = sv.load(conn, 1)
        big, h = next((b, s) for b in sv.world_of(save).hexes for s, n in sorted(sv.local_of(save, b).nooks.items())
                      if "creature" in n.finds and not n.need)
        sv.teleport(conn, 1, big, h)
    page.reload()
    page.wait_for_function("state && state.screen")
    expect(page.locator("#go-home")).to_be_visible()
    page.keyboard.press("Enter")
    expect(page.locator("#screen-text")).to_contain_text("asleep in here")
    expect(page.locator("#screen-keys")).to_contain_text(st.WAKE_LABEL)
    n = page.evaluate("(state.screen.options || []).length")
    page.keyboard.press("2" if n > 1 else "Enter")
    expect(page.locator("#battle")).to_be_visible()
    expect(page.locator("#go-home")).to_be_hidden()  # you run away instead
    assert page.evaluate("state.battle.tier") == "champion"
    expect(page.locator("#battle-keys")).to_contain_text("run away")
    page.keyboard.press("Escape")
    expect(page.locator("#battle")).to_be_hidden()
    expect(page.locator("#go-home")).to_be_visible()
    page.keyboard.press("Enter")
    expect(page.locator("#screen-text")).to_contain_text("asleep in here")  # back to sleep



def test_change_the_party_on_a_trip_while_everyone_is_fresh(page: Page, live_server, tmp_path):
    from app import db, pet_genes
    from app.wanderpaw import save as sv

    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/wanderpaw")
    with db.open_db(tmp_path / "e2e.db") as conn:
        fox = db.add_v3_pet(conn, 1, pet_genes.roll("fox", None, None, 1), "Rusty", "shop")
        bunny = db.add_v3_pet(conn, 1, pet_genes.roll("bunny", None, None, 2), "Clover", "shop")
    page.request.post(f"{live_server}/api/wander/party", data={"pets": [fox]})
    page.request.post(f"{live_server}/api/wander/trip/start", data={})
    page.reload()
    page.wait_for_function("state && state.trip && !busy")
    page.keyboard.press("3")  # the party book
    expect(page.locator("#party-change")).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator("#picker")).to_be_visible()
    expect(page.locator("#picker-keys")).to_contain_text("done")
    page.locator("#picker-pets li", has_text="Clover").click()  # add Clover
    page.wait_for_function(f"state.team.some((m) => m.id === {bunny})")
    page.keyboard.press("Enter")
    expect(page.locator("#picker")).to_be_hidden()
    expect(page.locator("#wander-message")).to_contain_text("party's ready")
    page.wait_for_function("targets.length > 0")  # walking again by typing
    assert page.evaluate(f"state.team.slice(0, 2).map((m) => m.id)") == [fox, bunny]

    with db.open_db(tmp_path / "e2e.db") as conn:  # a pet gets tired: the party's set for today
        save = sv.load(conn, 1)
        pets = [save["trip"]["pets"][0] - 1, *save["trip"]["pets"][1:]]
        db.save_wander(conn, 1, {**save, "trip": {**save["trip"], "pets": pets, "energy": save["trip"]["energy"] - 1}})
    page.reload()
    page.wait_for_function("state && state.trip && !busy")
    page.keyboard.press("3")
    expect(page.locator("#party")).to_be_visible()
    expect(page.locator("#party-change")).to_be_hidden()
    assert not errors
