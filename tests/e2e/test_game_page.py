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


def test_lab_lists_both_games_with_options(page: Page, live_server):
    page.goto(f"{live_server}/game-lab")
    expect(page.locator(".lab-card")).to_have_count(2)
    page.select_option("#opt-difficulty", "hard")
    href = page.locator(".lab-card").first.get_attribute("href")
    assert href.startswith("/game/") and "difficulty=hard" in href


def test_parent_page_links_to_game_lab(page: Page, live_server):
    page.goto(f"{live_server}/parent")
    expect(page.get_by_role("link", name="Games")).to_have_attribute("href", "/game-lab")


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
    expect(page.locator(".game-card h2")).to_have_text("A wild hedgehog wants to play!")
    assert errors == []


def test_losing_naps_then_pick_again(page: Page, live_server):
    start_battle(page, live_server, partner=0)
    page.evaluate("game.hp = 1; game.intent = 'tackle'")
    page.keyboard.type(card_word(page, "pounce"))
    expect(page.locator(".game-card h2")).to_have_text("Clover needs a nap!")
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'pick' && game.levelIndex === 0")
