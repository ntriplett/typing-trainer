"""Real-browser e2e tests for practice: the lab, a themed module played
through by keyboard, and buying the keyboard hint.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

FISH = "practice_fishing_v1"


def open_practice(page: Page, live_server: str, module: str = FISH, query: str = "?keys=home&focus=dk&length=short") -> None:
    page.goto(f"{live_server}/practice/{module}{query}")
    page.wait_for_function("stage.active")


def test_lab_lists_every_module_with_live_scenes(page: Page, live_server):
    page.goto(f"{live_server}/practice-lab")
    expect(page.locator(".lab-card")).to_have_count(11)
    expect(page.locator(".lab-card canvas")).to_have_count(10)
    page.fill("#opt-focus", "ei")
    page.select_option("#opt-length", "short")
    href = page.locator(".lab-card").nth(1).get_attribute("href")
    assert href.startswith(f"/practice/{FISH}?") and "focus=ei" in href and "length=short" in href


def test_themed_practice_plays_through_and_pays(page: Page, live_server):
    open_practice(page, live_server)
    expect(page.locator(".stage-title")).to_have_text("Gone fishing")
    expect(page.locator(".stage-text .keycap")).to_have_text(["D", "K"])
    expect(page.locator(".stage-scene")).to_be_visible()
    page.keyboard.type(page.evaluate("view.typeable"))
    expect(page.locator("#practice-done")).to_be_visible()
    expect(page.locator("#teach-coins")).to_have_text("+100 coins!")


def test_every_theme_runs_without_errors(page: Page, live_server):
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server}/practice-lab")
    ids = page.evaluate("cards.map(c => c.id)")
    for module in ids:
        open_practice(page, live_server, module)
        text = page.evaluate("view.typeable")
        page.keyboard.type(text[:6])
        page.keyboard.press("Q")  # a miss
        page.wait_for_timeout(150)
    assert errors == []


def test_keyboard_hint_shows_the_hands_and_costs_coins(page: Page, live_server):
    open_practice(page, live_server)
    page.click(".stage-hint-buy")  # starts with 0 coins in tests
    expect(page.locator(".stage-hint")).to_contain_text("You need 10 coins")
    expect(page.locator(".stage-keyboard")).to_be_hidden()

    page.keyboard.type(page.evaluate("view.typeable"))  # +100 coins
    expect(page.locator("#practice-done")).to_be_visible()
    page.keyboard.press(" ")  # go again
    page.wait_for_function("stage.active")
    page.click(".stage-hint-buy")
    expect(page.locator(".stage-keyboard")).to_be_visible()
    expect(page.locator(".stage-hint-buy")).to_be_hidden()
    expect(page.locator("#coin-count")).to_have_text("90")
    expect(page.locator(".stage-keyboard .tk-finger-lit-fill line")).not_to_have_count(0)


LINES_FIT = """() => {
  const box = document.querySelector('.stage-lines').getBoundingClientRect();
  return [...document.querySelectorAll('.stage-lines .prompt-line')].every((line) => {
    const last = line.lastElementChild;
    return !last || last.getBoundingClientRect().right <= box.right + 0.5;
  });
}"""


def test_lines_rewrap_to_fit_when_the_box_shrinks(page: Page, live_server):
    page.set_viewport_size({"width": 1600, "height": 1000})
    open_practice(page, live_server, query="?keys=home&focus=jf&length=long")
    page.wait_for_function("document.fonts.status === 'loaded' && view.maxChars === view.fitChars()")
    before = page.evaluate("view.maxChars")
    page.keyboard.type(page.evaluate("view.typeable")[:10])
    page.set_viewport_size({"width": 560, "height": 1000})
    page.wait_for_function(f"view.maxChars < {before}")
    page.wait_for_function(LINES_FIT)
    assert page.locator(".stage-lines .correct").count() == 10 or page.evaluate("view.lineIndex") > 0
    while (key := page.evaluate("view.expected")) is not None:  # the box may refit again (a scrollbar), so key by key
        page.keyboard.press("Space" if key == " " else key)
    expect(page.locator("#practice-done")).to_be_visible()
    expect(page.locator("#practice-result")).to_contain_text("100% right")


def test_lines_fit_when_the_typing_font_loads_late(page: Page, live_server):
    page.set_viewport_size({"width": 2560, "height": 1440})
    page.route("**/AtkinsonHyperlegibleMono.ttf", lambda route: (page.wait_for_timeout(1200), route.continue_()))
    open_practice(page, live_server, query="?keys=home&focus=jf&length=long")
    page.wait_for_function("document.fonts.status === 'loaded'")
    page.wait_for_timeout(200)
    assert page.evaluate("view.maxChars === view.fitChars()")  # measured again in the real font
    assert page.evaluate(LINES_FIT)
