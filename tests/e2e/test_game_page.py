"""Real-browser e2e tests for the games: the lab, and playing each game by
keyboard (through window.game to find the words on screen)."""

from __future__ import annotations

from playwright.sync_api import Page, expect

CROWS = "game_crow_patrol_v1"
BATTLE = "game_pet_battle_v1"


def open_game(page: Page, live_server: str, module: str, query: str = "?keys=home") -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/game/{module}{query}")
    page.wait_for_function("window.game && window.game.state === 'intro'")
    return errors


def test_lab_lists_both_games_with_options(page: Page, live_server):
    page.goto(f"{live_server}/game-lab")
    expect(page.locator(".lab-card")).to_have_count(2)
    page.select_option("#opt-difficulty", "hard")
    href = page.locator(".lab-card").first.get_attribute("href")
    assert href.startswith("/game/") and "difficulty=hard" in href


def test_home_page_links_to_game_lab(page: Page, live_server):
    page.goto(live_server)
    expect(page.get_by_role("link", name="Try games (lab)")).to_have_attribute("href", "/game-lab")


def test_crow_patrol_shoo_a_crow_by_typing_its_word(page: Page, live_server):
    errors = open_game(page, live_server, CROWS)
    expect(page.locator(".stage-title")).to_have_text("Crow Patrol")
    page.keyboard.press(" ")
    page.wait_for_function("game.targets().length > 0", timeout=5000)
    word = page.evaluate("game.targets()[0].word")
    expect(page.locator(".crow-word")).to_have_count(1)
    page.keyboard.press("q")  # matches no crow: nothing happens
    page.keyboard.type(word)
    page.wait_for_function("game.successes === 1")
    expect(page.locator(".game-score")).to_have_text("1")
    assert errors == []


def test_crow_patrol_upgrade_is_picked_by_typing(page: Page, live_server):
    errors = open_game(page, live_server, CROWS)
    page.keyboard.press(" ")
    page.evaluate("game.timeLeft = 0.01")  # skip to the end of the level
    expect(page.locator(".game-card h2")).to_contain_text("done!")
    page.keyboard.press(" ")
    expect(page.locator(".choice-card")).to_have_count(3)
    choice = page.evaluate("game.choices[0]")
    page.keyboard.type(choice["word"])
    page.wait_for_function(f"game.upgrades['{choice['id']}'] === 1 && game.levelIndex === 1")
    expect(page.locator(".stage-label")).to_have_text("Game · Level 2 of 5")
    assert errors == []


def test_crow_patrol_losing_the_patch_lets_you_retry(page: Page, live_server):
    open_game(page, live_server, CROWS)
    page.keyboard.press(" ")
    page.evaluate("game.pumpkins.forEach(p => p.taken = true); game.lostPatch()")
    expect(page.locator(".game-card h2")).to_have_text("The crows got every pumpkin!")
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'play' && game.pumpkins.every(p => !p.taken)")


def test_game_over_pays_per_success(page: Page, live_server):
    open_game(page, live_server, CROWS)
    page.evaluate("game.successes = 4; game.gameOver()")
    expect(page.locator(".game-card h2")).to_have_text("You shooed 4 crows!")
    expect(page.locator(".game-card .teach-coins")).to_have_text("+12 coins!")


def test_pet_battle_a_move_by_typing_its_word(page: Page, live_server):
    errors = open_game(page, live_server, BATTLE)
    expect(page.locator(".stage-title")).to_have_text("Pet Battles")
    expect(page.locator(".game-card h2")).to_have_text("A wild bunny wants to play!")
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'turn'")
    expect(page.locator(".move-card")).to_have_count(4)
    expect(page.locator(".move-card.cant")).to_have_count(1)  # Super pounce needs 2 stars
    expect(page.locator(".foe-intent")).to_contain_text("Next:")
    hp = page.evaluate("game.foe.hp")
    page.evaluate("game.intent = 'nibble'")  # so the hit isn't halved
    page.keyboard.type(page.evaluate("game.cards[0].word"))  # Pounce
    page.wait_for_function(f"game.foe.hp === {hp - 2}")
    page.wait_for_function("game.state === 'turn'")  # the critter went, and it's our turn again
    assert page.evaluate("game.stars") == 2
    assert errors == []


def test_pet_battle_slips_weaken_a_move(page: Page, live_server):
    open_game(page, live_server, BATTLE)
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'turn'")
    page.evaluate("game.intent = 'nibble'")
    word = page.evaluate("game.cards[0].word")
    page.keyboard.press(word[0])
    wrong = next(c for c in "asdfghjkl" if c != word[1 % len(word)]) if len(word) > 1 else None
    if wrong:
        page.keyboard.press(wrong)
        expect(page.locator(".move-card.locked .move-slips")).to_have_text("−1")
    hp = page.evaluate("game.foe.hp")
    page.keyboard.type(word[1:])
    page.wait_for_function(f"game.foe.hp === {hp - (1 if wrong else 2)}")


def test_pet_battle_win_and_lose_screens(page: Page, live_server):
    open_game(page, live_server, BATTLE)
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'turn'")
    page.evaluate("game.foe.hp = 0; game.win()")
    expect(page.locator(".game-card h2")).to_have_text("You won!")
    page.keyboard.press(" ")
    expect(page.locator(".game-card h2")).to_have_text("A wild hedgehog wants to play!")
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'turn'")
    page.evaluate("game.hp = 0; game.lose()")
    expect(page.locator(".game-card h2")).to_have_text("Pip needs a nap!")
    page.keyboard.press(" ")
    page.wait_for_function("game.state === 'turn' && game.hp === 12 && game.levelIndex === 1")
