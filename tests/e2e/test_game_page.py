"""Real-browser e2e tests for the games: the lab, and playing each game by
keyboard (through window.game to find the words on screen)."""

from __future__ import annotations

from playwright.sync_api import Page, expect

CROWS = "game_crow_patrol_v1"
BATTLE = "game_pet_battle_v1"


def open_game(page: Page, live_server: str, module: str, state: str, query: str = "?keys=home_top") -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/game/{module}{query}")
    page.wait_for_function(f"window.game && window.game.state === '{state}'")
    return errors


def test_lab_lists_every_game_with_options(page: Page, live_server):
    page.goto(f"{live_server}/game-lab")
    expect(page.locator(".lab-card")).to_have_count(3)
    page.select_option("#opt-difficulty", "hard")
    href = page.locator(".lab-card").first.get_attribute("href")
    assert href.startswith("/game/") and "difficulty=hard" in href


# --- Crow Patrol ---------------------------------------------------------------------


def start_crows(page: Page, live_server: str) -> list[str]:
    errors = open_game(page, live_server, CROWS, "intro")
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'play'")
    return errors


def test_crow_patrol_shoo_a_crow_by_typing_its_word(page: Page, live_server):
    errors = start_crows(page, live_server)
    expect(page.locator(".game-screen")).to_be_hidden()
    page.evaluate("game.spawnCrow('crow')")
    word = page.evaluate("game.targets()[0].word")
    page.keyboard.type(word)
    page.wait_for_function("game.roundPoints === 20")
    expect(page.locator(".game-score")).to_have_text("20")
    assert errors == []


def test_crow_patrol_slip_calls_a_friend_once(page: Page, live_server):
    start_crows(page, live_server)
    page.evaluate("game.spawnCrow('crow')")
    word = page.evaluate("game.targets()[0].word")
    page.keyboard.press(word[0])
    page.keyboard.press("z")  # never in a word from home + top rows
    expect(page.locator(".crow-bubble")).to_have_text("CAW! Help!")
    assert page.evaluate("game.flying().length") == 2
    page.keyboard.press("z")  # a second slip on the same crow: no more friends
    assert page.evaluate("game.flying().length") == 2


def test_long_words_stay_fully_inside_the_field(page: Page, live_server):
    start_crows(page, live_server)
    for x in (-10, 250):
        page.evaluate(
            f"""(() => {{ const c = game.spawnCrow('big'); c.word = 'sandwich'; c.shown = -1;
                c.sx = c.x = {x}; c.sy = c.y = 10; }})()"""
        )
    page.wait_for_timeout(100)
    area = page.locator(".game-area").bounding_box()
    for i in range(2):
        box = page.locator(".crow-word").nth(i).bounding_box()
        assert box["x"] >= area["x"] and box["x"] + box["width"] <= area["x"] + area["width"]
        assert box["y"] >= area["y"]


def test_the_word_being_typed_is_always_on_top(page: Page, live_server):
    start_crows(page, live_server)
    page.evaluate("game.spawnCrow('crow'); game.spawnCrow('crow')")
    first = page.evaluate("game.targets()[0].word")
    # stack both labels in the same place, the second one drawn later
    page.evaluate("game.targets().forEach(c => { c.sx = c.x = 120; c.sy = c.y = 40; c.dur = 1e6; })")
    page.keyboard.press(first[0])
    page.wait_for_timeout(100)
    page.keyboard.press("z")  # a slip: a speech bubble and a friend crow join
    page.wait_for_timeout(100)
    z = page.evaluate(
        """(() => {
          const z = (el) => Number(getComputedStyle(el).zIndex) || 0;
          const locked = document.querySelector('.crow-word.locked');
          const others = [...document.querySelectorAll('.crow-word:not(.locked), .crow-bubble')];
          return { locked: z(locked), others: others.map(z), count: others.length };
        })()"""
    )
    assert z["count"] >= 3
    assert all(z["locked"] > o for o in z["others"])


def test_crows_come_from_every_side(page: Page, live_server):
    start_crows(page, live_server)
    sides = page.evaluate(
        """[...Array(60)].map(() => game.entryPoint()).map(p => p.y < 0 ? 'top' : p.x < 0 ? 'left' : 'right')"""
    )
    assert set(sides) == {"top", "left", "right"}


def test_squirrel_crow_drops_a_squirrel_you_can_shoo(page: Page, live_server):
    start_crows(page, live_server)
    page.evaluate("const c = game.spawnCrow('squirrel'); c.t = 0.69")
    page.wait_for_function("game.flying().some(c => c.kind === 'runner')")
    word = page.evaluate("game.flying().find(c => c.kind === 'runner').word")
    page.keyboard.type(word)
    page.wait_for_function("game.shooed.runner === 1")


def test_round_end_tally_pays_then_upgrade_then_new_crow(page: Page, live_server):
    errors = start_crows(page, live_server)
    page.evaluate("game.shooed = {little: 2, crow: 1}; game.timeLeft = 0.01")
    expect(page.locator(".game-card h2")).to_have_text("Morning done!")
    page.keyboard.press(" ")  # speed up the count
    # 2x10 + 1x20 + 6 pumpkins x 100 + perfect patch 200 = 840 -> 42 coins
    expect(page.locator(".tally-total b")).to_have_text("840")
    expect(page.locator(".game-card .teach-coins")).to_have_text("+42 coins!")
    expect(page.locator(".tally-row")).to_have_count(4)
    page.keyboard.press(" ")
    expect(page.locator(".choice-card")).to_have_count(3)
    choice = page.evaluate("game.choices[0]")
    page.keyboard.type(choice["word"])
    page.wait_for_function(f"game.upgrades['{choice['id']}'] === 1 && game.levelIndex === 1")
    expect(page.locator(".crow-intro")).to_contain_text("NEW! Big crow")
    assert errors == []


def test_losing_every_pumpkin_ends_the_round_and_moves_on(page: Page, live_server):
    start_crows(page, live_server)
    page.evaluate("game.pumpkins.forEach(p => p.taken = true); game.lostThisRound = 6")
    expect(page.locator(".game-card h2")).to_have_text("The crows got every pumpkin!")
    expect(page.locator(".tally-row .tally-count")).to_have_text(["0 × 100"])
    expect(page.locator(".tally-row .tally-points")).to_have_text(["0"])
    expect(page.locator(".tally-go")).to_be_visible()
    page.keyboard.press(" ")
    expect(page.locator(".choice-card")).to_have_count(3)


def test_pie_makes_saved_pumpkins_worth_250(page: Page, live_server):
    start_crows(page, live_server)
    page.evaluate("game.upgrades.pie = 1; game.pumpkins[0].taken = true; game.lostThisRound = 1; game.timeLeft = 0.01")
    page.keyboard.press(" ")
    expect(page.locator(".tally-total b")).to_have_text("1,250")


def test_crow_game_over_shows_final_score(page: Page, live_server):
    open_game(page, live_server, CROWS, "intro")
    page.evaluate("game.shell.total = 3210; game.shell.coins = 160; game.gameOver()")
    expect(page.locator(".tally-total b")).to_have_text("3,210")
    expect(page.locator(".game-card .teach-coins")).to_have_text("160 coins earned this game!")


# --- Pet Battles ---------------------------------------------------------------------


def start_battle(page: Page, live_server: str, partner: int = 0) -> list[str]:
    """Partners for a learner with no pets: 0 Clover (Leaf), 1 Pip (Ember), 2 Puddle (Splash)."""
    errors = open_game(page, live_server, BATTLE, "pick")
    page.keyboard.type(page.evaluate(f"game.choices[{partner}].word"))
    page.wait_for_function("game.state === 'turn'")
    page.evaluate("game.intent = 'nibble'; game.renderHud()")  # so nothing dodges in the tests
    return errors


def card_word(page: Page, move_id: str) -> str:
    return page.evaluate(f"game.cards.find(c => c.move.id === '{move_id}').word")


def test_pick_screen_shows_the_critter_and_three_partners(page: Page, live_server):
    open_game(page, live_server, BATTLE, "pick")
    expect(page.locator(".game-card h2")).to_have_text("A wild bunny wants to play!")
    expect(page.locator(".game-card")).to_contain_text("Weak to Ember")
    expect(page.locator(".choice-card h3")).to_have_text(["Clover Leaf", "Pip Ember", "Puddle Splash"])


def test_pet_battle_a_move_by_typing_its_word(page: Page, live_server):
    errors = start_battle(page, live_server, partner=0)
    expect(page.locator(".move-cards .move-card")).to_have_count(4)
    expect(page.locator(".item-card")).to_have_count(3)
    expect(page.locator(".foe-intent")).to_contain_text("Next: Nibble")
    hp = page.evaluate("game.foe.hp")
    page.keyboard.type(card_word(page, "pounce"))
    page.wait_for_function(f"game.foe.hp === {hp - 2}")
    page.wait_for_function("game.state === 'turn'")  # the critter went, and it's our turn again
    assert page.evaluate("game.stars") == 2
    assert errors == []


def test_super_effective_hits_double(page: Page, live_server):
    start_battle(page, live_server, partner=1)  # Ember vs a Leaf bunny
    hp = page.evaluate("game.foe.hp")
    page.keyboard.type(card_word(page, "ember"))
    page.wait_for_function(f"game.foe.hp === {hp - 6}")
    expect(page.locator(".float-text.super")).to_have_text("Super!")


def test_hop_makes_a_hit_miss_but_big_wave_lands(page: Page, live_server):
    start_battle(page, live_server, partner=2)
    page.evaluate("game.intent = 'hop'; game.stars = 3; game.renderCards()")
    hp = page.evaluate("game.foe.hp")
    page.keyboard.type(card_word(page, "wave"))  # Splash vs Leaf: half of 4
    page.wait_for_function(f"game.foe.hp === {hp - 2}")


def test_slips_weaken_a_move(page: Page, live_server):
    start_battle(page, live_server, partner=0)
    word = card_word(page, "pounce")
    page.keyboard.press(word[0])
    page.keyboard.press("z")
    expect(page.locator(".move-card.locked .move-slips")).to_have_text("−1")
    hp = page.evaluate("game.foe.hp")
    page.keyboard.type(word[1:])
    page.wait_for_function(f"game.foe.hp === {hp - 1}")


def test_items_from_the_bag(page: Page, live_server):
    start_battle(page, live_server, partner=0)
    page.evaluate("game.hp = 5; game.renderHud()")
    page.keyboard.type(page.evaluate("game.bag.find(c => c.item === 'berry').word"))
    page.wait_for_function("game.hp === 10 && game.items.berry === 1")


def test_win_tally_pays_coins_then_next_critter(page: Page, live_server):
    errors = start_battle(page, live_server, partner=1)
    page.evaluate("game.foe.hp = 1")
    page.keyboard.type(card_word(page, "pounce"))
    expect(page.locator(".game-card h2")).to_contain_text("You won! Found a")
    page.keyboard.press(" ")
    # 200 + 14 HP x 10 + 1 clean move x 20 = 360 -> 54 coins
    expect(page.locator(".tally-total b")).to_have_text("360")
    expect(page.locator(".game-card .teach-coins")).to_have_text("+54 coins!")
    page.keyboard.press(" ")
    expect(page.locator(".game-card h2")).to_have_text("A wild lizard wants to play!")
    assert errors == []


def test_losing_naps_then_pick_again(page: Page, live_server):
    start_battle(page, live_server, partner=0)
    page.evaluate("game.hp = 1; game.intent = 'tackle'")
    page.keyboard.type(card_word(page, "pounce"))
    expect(page.locator(".game-card h2")).to_have_text("Clover needs a nap!")
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'pick' && game.levelIndex === 0")


# --- Farm Stand ----------------------------------------------------------------------

FARM = "game_farm_stand_v1"


def start_farm(page: Page, live_server: str, query: str = "?keys=home_top") -> list[str]:
    errors = open_game(page, live_server, FARM, "start", query)
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'ready'")
    return errors


def type_word(page: Page, js: str) -> None:
    page.keyboard.type(page.evaluate(js))


def plant(page: Page, crop: str = "radish") -> None:
    type_word(page, f"game.packets.find((p) => p.crop.id === '{crop}').word")


def test_farm_stand_opens_when_you_plant(page: Page, live_server):
    errors = start_farm(page, live_server)
    expect(page.locator(".seed-packet:not(.coming-seed)")).to_have_count(3)
    expect(page.locator(".coming-seed")).to_contain_text("Tomato")  # more veggies are coming
    expect(page.locator(".farm-delivery")).to_have_count(2)  # in the sky
    expect(page.locator(".farm-next")).to_have_count(4)  # the orders coming, in the sky
    page.wait_for_timeout(300)
    assert page.evaluate("game.clock") == 0  # nothing moves before the first seed
    plant(page)
    page.wait_for_function("game.state === 'hour' && game.hour === 1")
    assert page.evaluate("game.plots[0].crop") == "radish" and page.evaluate("game.money") == 19
    assert page.evaluate("game.arriveIn") > 9  # the first animal comes 10s after
    assert errors == []


def test_farm_stand_word_groups_share_a_first_letter(page: Page, live_server):
    start_farm(page, live_server)
    plant(page)
    page.evaluate("game.arrive(); game.arrive()")
    firsts = page.evaluate(
        """[game.packets, game.deliveries, game.waiting()].map((g) => [...new Set(g.map((t) => t.word[0]))])"""
    )
    assert all(len(f) == 1 for f in firsts) and len({f[0] for f in firsts}) == 3
    # the first key lights up the whole group
    page.keyboard.press(firsts[1][0])
    expect(page.locator(".farm-delivery.locked")).to_have_count(2)


def test_farm_stand_works_with_only_four_letters(page: Page, live_server):
    errors = open_game(page, live_server, FARM, "start")
    # words from just j, d, k, f, like a brand-new learner's
    page.evaluate(
        """(() => {
          const make = (n) => Array.from({length: 60}, () => Array.from({length: n}, () => 'jdkf'[Math.floor(Math.random() * 4)]).join(''));
          game.game.words = {short: [...make(2), ...make(3)], medium: make(4), long: make(6)};
          game.letters = game.groupLetters();
        })()"""
    )
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'ready'")
    plant(page)
    page.evaluate("game.shelf = {radish: 2, peas: 2}; game.arrive(); game.arrive(); game.arrive()")
    words = page.evaluate("game.worded().map((t) => t.word)")
    assert all(words) and len(words) == 3 + 2 + 3  # every seed, delivery and customer has a word
    type_word(page, "game.customers[0].word")  # while it's still walking up
    page.wait_for_function("game.day.served === 1")
    assert errors == []


def test_farm_stand_line_fills_itself_and_icons_keep_their_shape(page: Page, live_server):
    start_farm(page, live_server)
    plant(page)
    page.evaluate("game.arriveIn = 0")
    page.wait_for_function("game.waiting().length === 3", timeout=10000)  # a new animal as soon as there's room
    page.wait_for_timeout(600)
    # ticket icons are drawn at their real size even while the ticket was hidden
    sizes = page.evaluate("[...document.querySelectorAll('.farm-ticket .veggie-icon')].map((c) => [c.width, c.height])")
    assert sizes and all(w * 28 == h * 24 for w, h in sizes), sizes
    assert page.evaluate("game.customers[0].max") > 50  # they wait a long time


def test_farm_stand_seeds_go_on_credit(page: Page, live_server):
    start_farm(page, live_server)
    page.evaluate("game.money = 0")
    plant(page, "carrot")
    assert page.evaluate("game.money") == -3
    assert page.evaluate("game.plots[0].crop") == "carrot"


def test_farm_stand_line_steps_up_when_someone_leaves(page: Page, live_server):
    start_farm(page, live_server)
    plant(page)
    page.evaluate("game.arrive(); game.arrive(); game.arrive()")
    first, second = page.evaluate("[game.customers[1].word, game.customers[2].word]")
    page.evaluate("game.leave(game.customers[0], false)")
    assert page.evaluate("game.waiting().map((c) => c.slot)") == [0, 1]
    assert page.evaluate("game.waiting().map((c) => c.word)") == [first, second]


def test_farm_stand_fancy_customers_pay_double(page: Page, live_server):
    start_farm(page, live_server)
    plant(page)
    page.evaluate("game.farm.max_tip = 0; game.shelf = {peas: 4}")
    page.evaluate("game.line[0].order = {peas: 2}; game.line[0].fancy = true; game.arrive()")
    type_word(page, "game.customers[0].word")
    page.wait_for_function("game.day.served === 1")
    assert page.evaluate("game.day.earned") == 2 * 3 * 2


def test_farm_stand_robot_and_pet_plots(page: Page, live_server):
    errors = open_game(page, live_server, FARM, "start")
    page.evaluate(
        """(() => {
          const pet = {...game.game.customers[0], name: 'Pip'};
          game.pets = [{...pet, x: 150, tx: null, rest: 0, dir: 1, trip: null, joy: 0, hop: 0}];
          game.courier = game.gardener = game.pets[0];
          game.petPlots = [0, 1].map(() => ({crop: null, grown: 0, left: 0, kind: 'pet'}));
          game.robotPlots = [{crop: null, grown: 0, left: 0, kind: 'robot'}];
          game.layoutPlots();
        })()"""
    )
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'ready'")
    plant(page, "peas")
    page.wait_for_function("game.robotPlots[0].crop === 'peas'")  # the robot copies your first seed
    page.wait_for_function("game.petPlots.every((p) => p.crop)")  # the gardener's plots fill themselves
    assert page.evaluate("game.day.spent") == 4  # yours and the robot's seed; the pet's are free
    assert errors == []


def test_farm_stand_swaps_when_out_and_says_what_is_missing(page: Page, live_server):
    start_farm(page, live_server)
    plant(page)
    page.evaluate("game.line[0].order = {carrot: 2}; game.arrive()")
    type_word(page, "game.customers[0].word")
    expect(page.locator(".crow-bubble")).to_have_text("Need Carrot!")
    page.evaluate("game.shelf = {peas: 3}")
    expect(page.locator(".swap-tag")).to_be_visible()
    type_word(page, "game.customers[0].word")
    page.wait_for_function("game.day.served === 1")
    assert page.evaluate("game.shelf.peas") == 1


def test_farm_stand_sends_a_delivery(page: Page, live_server):
    start_farm(page, live_server)
    plant(page)
    page.evaluate("game.shelf = {...game.deliveries[0].order}")
    pay = page.evaluate("game.deliveries[0].pay")
    type_word(page, "game.deliveries[0].word")
    page.wait_for_function("game.deliveries[0].done")
    assert page.evaluate("game.day.earned") == pay  # no pet along: no tip


def test_farm_stand_a_whole_day_ends_in_the_evening_and_shop(page: Page, live_server):
    errors = start_farm(page, live_server)
    plant(page)
    for hour in range(1, 5):
        page.wait_for_function(f"game.state === 'hour' && game.hour === {hour}")
        page.evaluate("game.clock = 999")
        page.wait_for_function("game.state === 'tally'")
        expect(page.locator(".tally-go")).to_be_visible(timeout=10000)
        page.keyboard.press(" ")
    page.wait_for_function("game.state === 'evening'")
    expect(page.locator(".game-card")).to_contain_text("practice day")  # a lab play isn't saved
    expect(page.locator(".game-card")).to_contain_text("2 missed")  # the deliveries
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'shop'")
    expect(page.locator(".game-card h2")).to_have_text("Farm Shop")
    page.keyboard.press("Enter")
    expect(page.locator(".game-card")).to_contain_text("Final score")
    assert errors == []


# --- Crow Patrol's cards ------------------------------------------------------------


def _to_cards(page, live_server, before_round=1):
    """At the card pick before round `before_round`."""
    start_crows(page, live_server)
    page.evaluate(f"game.levelIndex = {before_round - 1}; game.chooseUpgrade()")
    expect(page.locator(".choice-card")).to_have_count(3)


def test_a_round_card_is_offered_just_before_its_crow(page: Page, live_server):
    for before, card in ((1, "slingshot"), (2, "earmuffs"), (3, "acorns"), (4, "net")):
        _to_cards(page, live_server, before)
        assert card in page.evaluate("game.choices.map((c) => c.id)")


def test_sunny_and_rainy_come_together_and_only_one_can_be_taken(page: Page, live_server):
    _to_cards(page, live_server)
    offers = page.evaluate("Array.from({length: 200}, () => game.offerCards())")
    assert all(("sunny" in o) == ("rainy" in o) for o in offers)
    assert any("sunny" in o for o in offers)
    assert all(len(o) == 3 and len(set(o)) == 3 for o in offers)
    after = page.evaluate("game.upgrades.rainy = 1; Array.from({length: 100}, () => game.offerCards())")
    assert not any("sunny" in o or "rainy" in o for o in after)


def test_one_time_cards_arent_offered_twice_but_others_can_stack(page: Page, live_server):
    _to_cards(page, live_server)
    offers = page.evaluate("game.upgrades.calm = 1; game.upgrades.fence = 1; Array.from({length: 200}, () => game.offerCards())")
    assert not any("calm" in o for o in offers)
    assert any("fence" in o for o in offers)


def test_king_crow_is_only_a_chance_before_the_last_round(page: Page, live_server):
    _to_cards(page, live_server, 4)
    seen = page.evaluate("game.kingChance = 0.5; Array.from({length: 400}, () => game.offerCards().includes('king'))")
    assert 120 < sum(seen) < 280  # about half
    page.evaluate("game.levelIndex = 2")
    assert not any(page.evaluate("game.kingChance = 1; Array.from({length: 50}, () => game.offerCards().includes('king'))"))
    page.evaluate("game.levelIndex = 3; game.game.king_ready = false")
    assert not any(page.evaluate("Array.from({length: 50}, () => game.offerCards().includes('king'))"))


def test_king_crow_comes_halfway_with_two_guards_and_pays_a_token_once(page: Page, live_server):
    errors = start_crows(page, live_server)
    page.evaluate("""game.levelIndex = 4; game.upgrades.king = 1; game.resetPatch(); game.resetRound(); game.state = 'play';
                     game.spawnIn = 99""")
    assert page.evaluate("game.flying().length") == 0
    page.evaluate("game.timeLeft = game.roundSeconds / 2")
    page.wait_for_function("game.flying().filter((c) => c.kind === 'king').length === 1")
    assert page.evaluate("game.flying().filter((c) => c.kind === 'squirrel').length") == 2
    assert page.evaluate("CROW_KINDS.king.size") == 2 * page.evaluate("CROW_KINDS.crow.size")
    page.evaluate("game.ringBell.call(Object.assign(game, {bellLeft: 1}))")
    assert page.evaluate("game.flying().filter((c) => c.kind === 'king').length") == 1  # the bell won't do it
    word = page.evaluate("game.flying().find((c) => c.kind === 'king').word")
    page.keyboard.type(word)
    page.wait_for_function("document.querySelector('#token-count').textContent === '1'")
    # another game today: he's not ready, and caught can't pay again
    assert page.request.post(f"{live_server}/api/crow-king/caught").json()["paid"] is False
    assert page.request.post(f"{live_server}/api/crow-king/appear").json()["ok"] is False
    game = page.request.get(f"{live_server}/api/game/{CROWS}/content", params={"keys": "home"}).json()["game"]
    assert game["king_ready"] is False
    assert errors == []


def test_your_pet_runs_out_for_its_long_word_then_comes_back(page: Page, live_server):
    errors = start_crows(page, live_server)
    page.evaluate("game.upgrades.guard = 1; game.resetRound(); game.state = 'play'; game.spawnIn = 99")
    guard = page.evaluate("({word: game.guard.word, state: game.guard.state})")
    assert guard["state"] == "ready" and len(guard["word"]) >= 4
    expect(page.locator(".crow-word.kind-guard")).to_be_visible()
    page.evaluate("game.spawnCrow('crow')")
    page.keyboard.type(guard["word"])
    page.wait_for_function("game.guard.state !== 'ready'")
    page.wait_for_function("game.flying().length === 0")  # it scared the crow off
    assert page.evaluate("game.shooed.crow") == 1
    page.wait_for_function("game.guard.state === 'ready' && game.guard.word.length > 0")  # back, with a new word
    assert page.evaluate("Math.round(game.guard.x)") == page.evaluate("GUARD_HOME.x")
    assert errors == []


def test_hot_streak_triples_after_five_clean_crows_and_a_slip_breaks_it(page: Page, live_server):
    start_crows(page, live_server)
    page.evaluate("game.upgrades.hot = 1; game.spawnIn = 99")
    for _ in range(5):
        page.evaluate("game.countStreak({kind: 'crow', x: 50, y: 50})")
    assert page.evaluate("game.streakHot") is True
    page.evaluate("game.countStreak({kind: 'crow', x: 50, y: 50})")
    assert page.evaluate("game.streakBonus") == 40  # the crow's 20, twice more
    page.evaluate("for (let i = 0; i < 4; i++) game.countStreak({kind: 'crow', x: 50, y: 50})")
    page.evaluate("game.spawnCrow('crow'); game.flying()[0].word = 'fff'; game.flying()[0].shown = -1")
    page.keyboard.press("f")
    page.keyboard.press("z")
    assert page.evaluate("game.streak") == 0


def test_points_follow_your_cards(page: Page, live_server):
    start_crows(page, live_server)
    assert page.evaluate("game.pointsFor('crow')") == 20
    assert page.evaluate("game.upgrades.whistle = 1; game.pointsFor('crow')") == 40
    assert page.evaluate("game.upgrades.shiny = 1; game.pointsFor('crow')") == 60
    assert page.evaluate("game.upgrades.whistle = 0; game.upgrades.shiny = 0; game.upgrades.net = 1; game.pointsFor('golden')") == 200


def test_calm_crows_stop_the_call_and_weather_changes_the_round(page: Page, live_server):
    start_crows(page, live_server)
    assert page.evaluate("game.upgrades.sunny = 1; game.roundSeconds") == 70
    assert page.evaluate("game.upgrades.sunny = 0; game.upgrades.rainy = 1; game.roundSeconds") == 50
    page.evaluate("game.upgrades.calm = 1; game.spawnIn = 99; game.spawnCrow('crow'); game.flying()[0].word = 'fff'; game.flying()[0].shown = -1")
    page.keyboard.press("f")
    page.keyboard.press("z")
    expect(page.locator(".crow-bubble")).to_have_count(0)
    assert page.evaluate("game.flying().length") == 1


def test_compost_grows_a_pumpkin_back_and_a_decoy_goes_first(page: Page, live_server):
    start_crows(page, live_server)
    page.evaluate("game.upgrades.compost = 1; game.pumpkins[0].taken = true; game.spawnIn = 99")
    page.evaluate("for (let i = 0; i < 7; i++) game.growCompost()")
    assert page.evaluate("game.pumpkins[0].taken") is True
    page.evaluate("game.growCompost()")
    assert page.evaluate("game.pumpkins[0].taken") is False
    page.evaluate("game.upgrades.decoy = 1; game.resetRound(); game.spawnIn = 99; game.state = 'play'")
    fake = page.evaluate("const c = game.spawnCrow('crow'); c.t = 0.999; c.pumpkin.fake === true")
    assert fake is True
    page.wait_for_function("game.decoy.taken")
    assert page.evaluate("game.pumpkins.every((p) => !p.taken) && game.flying()[0].pumpkin.fake !== true")
