"""Real-browser tests for Wanderpaw's story (LORE.md): Pip's opening and tutorial, and reading a Keeper's letter."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app.wanderpaw import local as lc
from app.wanderpaw import lore


def _enter_until_gone(page: Page, count: int):
    for _ in range(count):
        page.keyboard.press("Enter")


def test_pip_opens_a_new_game_and_teaches_the_basics(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#screen-title")).to_have_text("Pip")
    expect(page.locator("#screen-text")).to_contain_text("Hello there")
    expect(page.locator("#screen-portrait")).to_be_visible()
    expect(page.locator("#picker")).to_be_hidden()
    _enter_until_gone(page, len(lore.INTRO_PAGES))  # just reading: nothing typed
    expect(page.locator("#day-scene")).to_be_visible()  # good morning!
    page.keyboard.press("Enter")
    expect(page.locator("#picker")).to_be_visible()
    expect(page.locator("#pip-hint")).to_contain_text("Enter sets off")

    page.keyboard.press("Enter")
    expect(page.locator("#pip-hint")).to_contain_text("Type one to walk")
    for _ in range(3):
        page.wait_for_function("targets.length > 0 && !busy")
        before = page.evaluate("state.stats.steps")
        page.keyboard.type(page.evaluate("targets.find((t) => t.hex).word"))
        page.wait_for_function(f"state.stats.steps > {before} && !busy")
    expect(page.locator("#pip-hint")).to_contain_text("my house")

    page.request.post(f"{live_server}/api/wander-lab/teleport", data={"q": 0, "r": 0, "spot": list(lc.PIP_HOUSE)})
    page.reload()
    page.wait_for_function("state && state.screen")
    page.keyboard.press("Enter")
    expect(page.locator("#screen-title")).to_have_text("Pip")
    page.keyboard.press("Enter")
    expect(page.locator("#pip-hint")).to_contain_text("press 5")
    page.keyboard.press("5")
    page.wait_for_function("state.tutorial.step === 'guide'")
    page.keyboard.press("Escape")
    expect(page.locator("#pip-hint")).to_contain_text("press 6")
    page.keyboard.press("6")
    page.wait_for_function("state.tutorial.step === 'fight'")
    page.keyboard.press("Escape")
    expect(page.locator("#pip-hint")).to_contain_text("past my door")


def test_esc_skips_the_tutorial(page: Page, live_server):
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#screen-title")).to_have_text("Pip")
    page.keyboard.press("Escape")
    expect(page.locator("#day-scene")).to_be_visible()
    expect(page.locator("#pip-hint")).to_be_hidden()


def _at_the_letter(page: Page, live_server):
    """At the splash temple's door with its Keeper already beaten."""
    page.request.post(f"{live_server}/api/wander/tutorial", data={"step": "skip"})
    page.goto(f"{live_server}/wanderpaw")
    page.request.post(f"{live_server}/api/wander-lab/keeper-beaten", data={"region": "splash"})
    page.reload()
    page.wait_for_function("state && state.screen && state.screen.letter")
    page.keyboard.press("Enter")
    expect(page.locator("#screen-text")).to_contain_text("What's in that old bag")
    page.keyboard.press("Enter")
    expect(page.locator("#letter-to")).to_have_text("Dear Nerissa,")


def _type_prompt_line(page: Page):
    """Everything the current prompt wants, one key at a time, until the server has the line."""
    at = page.evaluate("reading.letter.at")
    for _ in range(200):
        if page.evaluate(f"!reading || reading.letter.at !== {at}"):
            return
        key = page.evaluate("reading && reading.view.expected")
        if key is None:
            page.wait_for_timeout(50)
            continue
        page.keyboard.press("Space" if key == " " else key)


def test_reading_a_letter_fills_in_untaught_letters_saves_and_pays(page: Page, live_server):
    _at_the_letter(page, live_server)
    # a new learner knows only the home row: the capital M and the rest are ink
    page.wait_for_function("reading.view && document.querySelectorAll('#letter-prompt .ink').length > 0")
    assert page.evaluate("[...'asdfghjkl '].includes(reading.view.expected)")
    # a wrong key waits
    was = page.evaluate("reading.view.typed")
    page.keyboard.press("q" if page.evaluate("reading.view.expected") != "q" else "w")
    assert page.evaluate("reading.view.typed") == was

    _type_prompt_line(page)
    page.wait_for_function("reading && reading.letter.at === 1")
    # leave and come back: the same line
    page.keyboard.press("Escape")
    page.reload()
    page.wait_for_function("state && state.screen && state.screen.letter")
    page.keyboard.press("Enter")
    expect(page.locator("#screen-text")).to_contain_text("1 of 3")
    page.keyboard.press("Enter")
    page.wait_for_function("reading && reading.view && reading.letter.at === 1")
    _type_prompt_line(page)
    page.wait_for_function("reading && reading.letter.at === 2")
    _type_prompt_line(page)
    page.wait_for_function("mode === 'screen' && state.screen.action === 'temple'")
    expect(page.locator("#screen-text")).to_contain_text("Rippling Pearl")
    coins = page.evaluate("state.coin_balance")
    page.keyboard.press("Enter")
    page.wait_for_function("state.temples.includes('splash')")
    assert page.evaluate("state.coin_balance") == coins + lore.KEEPER_COINS
    # now a friend, with a relative who'd like to join you
    page.wait_for_function("state.screen.action === 'keeper_talk'")
    expect(page.locator("#screen-text")).to_contain_text(lore.KEEPERS["splash"].kin)
    labels = page.evaluate("state.screen.options.map((o) => o.action)")
    page.keyboard.press(str(labels.index("kin_join") + 1))
    page.wait_for_function("state.camp_friends.length === 1")


def test_starting_over_shows_pip_straight_away(page: Page, live_server):
    page.request.post(f"{live_server}/api/wander/tutorial", data={"step": "skip"})
    page.request.post(f"{live_server}/api/wander-lab/reset", data={})
    page.goto(f"{live_server}/wanderpaw")
    expect(page.locator("#screen-title")).to_have_text("Pip")
    expect(page.locator("#screen-text")).to_contain_text("Hello there")


def test_a_shopkeeper_talks_and_still_sells(page: Page, live_server):
    page.request.post(f"{live_server}/api/wander/tutorial", data={"step": "skip"})
    page.goto(f"{live_server}/wanderpaw")
    world = page.request.get(f"{live_server}/api/wander-lab/world").json()
    from app.wanderpaw import local as lc
    from app.wanderpaw import world as wd
    w = wd.generate(world["seed"])
    town = w.quests["dream"].town
    shop = next(h for h, r in lc.generate(world["seed"], town).buildings.items() if r == "shop")
    page.request.post(f"{live_server}/api/wander/trip/start", data={})
    page.request.post(f"{live_server}/api/wander-lab/teleport", data={"q": town[0], "r": town[1], "spot": list(shop)})
    page.reload()
    page.wait_for_function("state && state.screen")
    page.keyboard.press("Enter")
    expect(page.locator("#screen-portrait")).to_be_visible()
    expect(page.locator("#screen-text")).to_contain_text("Bottles, bottles")
    page.keyboard.press("2")
    expect(page.locator("#screen-text")).to_contain_text("Madame Morrow")
    page.keyboard.press("1")  # see what's for sale
    expect(page.locator("#menu")).to_be_visible()
