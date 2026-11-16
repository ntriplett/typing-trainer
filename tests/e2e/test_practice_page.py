"""Real-browser e2e tests for practice: the lab, a themed module played
through by keyboard, and the fading keyboard hint.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from app import db

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


def set_supports(tmp_path, value: float, keys: str = "asdfghjkl; ") -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        for k in keys:
            db.set_key_hint(conn, 1, k, value)
        conn.commit()


def lit_fingers(page: Page) -> int:
    return page.locator(".stage-keyboard .tk-finger-lit-fill line").count()


def test_new_keys_get_the_full_hint_at_once(page: Page, live_server):
    open_practice(page, live_server)  # nothing taught yet: every key is new
    expect(page.locator(".stage-keyboard")).to_be_visible()
    expect(page.locator(".stage-keyboard .tk-target")).not_to_have_count(0)
    expect(page.locator(".stage-keyboard .tk-label-hidden")).to_have_count(0)
    expect(page.locator(".stage-help")).to_be_visible()


def test_lower_support_hides_letters_and_waits_to_light(page: Page, live_server, tmp_path):
    set_supports(tmp_path, 3.9)  # blank keys, finger after ~1.65 s, key 1 s later
    open_practice(page, live_server)
    expect(page.locator(".stage-keyboard")).to_be_visible()
    expect(page.locator('.stage-keyboard .tk-label-hidden[data-key="d"]')).to_have_count(1)
    expect(page.locator('.stage-keyboard .tk-label[data-key="shift_l"]')).not_to_have_class(re.compile("tk-label-hidden"))
    assert lit_fingers(page) == 0 and page.locator(".stage-keyboard .tk-target").count() == 0
    expect(page.locator(".stage-keyboard .tk-finger-lit-fill line")).not_to_have_count(0, timeout=3000)
    assert page.locator(".stage-keyboard .tk-target").count() == 0  # the finger first...
    expect(page.locator(".stage-keyboard .tk-target")).not_to_have_count(0, timeout=3000)  # ...then the key


def test_typing_before_the_light_is_sent_as_unhelped(page: Page, live_server, tmp_path):
    set_supports(tmp_path, 3.0)
    open_practice(page, live_server)
    page.keyboard.type(page.evaluate("view.typeable")[:3])
    strokes = page.evaluate("stage.keystrokes")
    assert [s["hint_support"] for s in strokes] == [3.0, 3.0, 3.0]
    assert not any(s["solo"] for s in strokes)


def test_no_keyboard_once_every_key_is_learned(page: Page, live_server, tmp_path):
    set_supports(tmp_path, 0.5)
    open_practice(page, live_server)
    expect(page.locator(".stage-keyboard")).to_be_hidden()


def press_expected(page: Page) -> None:
    key = page.evaluate("view.expected")
    page.keyboard.press("Space" if key == " " else key)


def test_the_rescue_brings_help_back_after_a_rough_patch(page: Page, live_server, tmp_path):
    set_supports(tmp_path, 3.0)
    open_practice(page, live_server, query="?keys=home&focus=dk&length=long")
    expect(page.locator('.stage-keyboard .tk-label-hidden[data-key="d"]')).to_have_count(1)
    for _ in range(3):  # 3 misses then a right one: lost, but never the 5-in-a-row lockout
        for _ in range(3):
            page.keyboard.press("q")
        press_expected(page)
    assert page.evaluate("stage.rescue") >= 1
    expect(page.locator('.stage-keyboard .tk-label-hidden[data-key="d"]')).to_have_count(0)
    for _ in range(60):  # then it goes well: the rescue eases back off
        press_expected(page)
    assert page.evaluate("stage.rescue") < 1


def test_more_help_asks_the_server_and_shows_more(page: Page, live_server, tmp_path):
    set_supports(tmp_path, 3.5)
    open_practice(page, live_server)
    expect(page.locator('.stage-keyboard .tk-label-hidden[data-key="d"]')).to_have_count(1)
    page.click(".stage-help-more")  # no history: a whole level
    expect(page.locator(".stage-hint")).to_have_text("A little more help is on the way.")
    expect(page.locator('.stage-keyboard .tk-label-hidden[data-key="d"]')).to_have_count(0)
    page.click(".stage-help-less")
    expect(page.locator(".stage-hint")).to_have_text("Less help. You've got this!")


def test_js_hint_rules_match_the_server(page: Page, live_server):
    from app import hint_model as hm

    open_practice(page, live_server)
    levels = [i / 20 for i in range(0, 101)]
    js = page.evaluate("(levels) => levels.map((s) => HintRules.display(s))", levels)
    for s, d in zip(levels, js):
        py = hm.display(s)
        assert d["letter"] == py.letter, s
        for a, b in ((d["fingerMs"], py.finger_ms), (d["keyMs"], py.key_ms)):
            assert (a is None) == (b is None) and (a is None or abs(a - b) <= 1), s
    p = hm.rescue_params()
    cases = [[False] * 8, [True] * 15, [True] * 4 + [False], [True] * 14 + [False], [False] * 30 + [True] * 15]
    for recent in cases:
        for offset in (0.0, 1.0, 4.9):
            assert page.evaluate("([o, r, p]) => HintRules.rescueStep(o, r, p)", [offset, recent, p]) == pytest.approx(
                hm.rescue_step(offset, recent)
            )


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
