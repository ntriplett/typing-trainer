"""Real-browser e2e tests for Wanderpaw (PLAN.md 11n): setting off on a
trip and walking by typing, and the lab's small maps and gallery."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def test_set_off_and_walk_by_typing(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#where-name")).to_have_text("Camp")
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
    page.keyboard.press("Enter")
    expect(page.locator("#screen-text")).to_contain_text("still need the")
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
    expect(page.locator("#picker")).to_be_visible()
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
    page.wait_for_selector("#picker:not([hidden]), #wander-local")
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


def test_the_guidebook_turns_pages_and_shows_match_ups(page: Page, live_server, tmp_path):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _set_up(page, live_server, tmp_path)
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#keys")).to_contain_text("Go in", timeout=5000)
    page.keyboard.press("6")
    expect(page.locator("#menu-title")).to_have_text("Guidebook")
    expect(page.locator(".wander-type-chart")).to_be_visible()
    page.keyboard.press("ArrowRight")
    result = page.locator(".wander-guide-result")
    expect(result).to_contain_text("x2")  # splash on ember, the page's opening pair
    page.locator("[data-guide-me='shock']").click()
    expect(result).to_contain_text("x1.5")  # shock is strong against ember
    page.keyboard.press("j")
    for _ in range(5):
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


def test_befriending_is_offered_when_you_win_with_a_token(page: Page, live_server, tmp_path):
    from app import db
    from app.wanderpaw import save as sv
    _in_a_fight(page, live_server, tmp_path, {"Friendship Token": 1})
    with db.open_db(tmp_path / "e2e.db") as conn:
        save = sv.load(conn, 1)
        db.save_wander(conn, 1, {**save, "battle": {**save["battle"], "over": "won"}, "trip": {**save["trip"], "mana": [50 for _ in save["trip"]["mana"]]}})
    page.goto(f"{live_server}/wanderpaw")
    keys = page.locator("#battle-keys")
    expect(keys).to_contain_text("Befriend it")
    page.keyboard.press("b")
    expect(keys).not_to_contain_text("Befriend it")
    expect(page.locator("#battle-log")).to_contain_text("wants to come with you")
