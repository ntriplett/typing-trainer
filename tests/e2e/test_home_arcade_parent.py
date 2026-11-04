"""Real-browser e2e tests for the home hub, the arcade, and the parent page."""

from __future__ import annotations

import re

import pytest

from playwright.sync_api import Page, expect

from app import db

from .conftest import GROWNUP_PIN, place_on_home_row


def give_tokens(tmp_path, n: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_tokens(conn, 1, n, "test")


def test_home_has_a_tile_for_everything(page: Page, live_server):
    page.goto(live_server)
    # big ones first (practice, arcade, pets), then the four small ones
    hrefs = page.eval_on_selector_all(".home-tile", "tiles => tiles.map(t => t.getAttribute('href'))")
    assert hrefs == ["/session", "/arcade", "/pets", "/bedroom", "/garden", "/store", "/analysis"]
    expect(page.locator("#home-day .day-label")).to_have_text("0 / 10 min")
    expect(page.locator("#practice-sub")).to_have_text("Your next lesson is ready!")
    # the art is drawn
    assert page.evaluate("document.querySelector('.tile-art').toDataURL().length") > 2000


def test_the_greeting_is_a_hello_and_the_goal_chest_holds_two_tokens(page: Page, live_server):
    page.goto(live_server)
    expect(page.locator("#home-greeting")).to_contain_text("Tester")
    expect(page.locator("#home-day .day-chest.stack .token-icon")).to_have_count(2)


def test_token_pill_and_day_tracker_are_in_the_top_bar(page: Page, live_server):
    page.goto(f"{live_server}/store")
    expect(page.locator("#token-count")).to_have_text("0")
    expect(page.locator(".topbar .day-tracker")).to_be_visible()
    expect(page.locator(".topbar .day-chest")).to_have_count(3)  # seed, goal, bonus


def test_arcade_play_spends_tokens_and_opens_the_game(page: Page, live_server, tmp_path):
    place_on_home_row(page, live_server)
    give_tokens(tmp_path, 1)
    page.goto(f"{live_server}/arcade")
    expect(page.locator("#arcade-balance")).to_have_text("1")
    expect(page.locator("[data-play='wanderpaw']")).to_be_disabled()  # costs 2
    expect(page.locator("[data-play='game_pet_battle_v1']")).to_have_count(0)  # Wanderpaw took its place
    page.click("[data-play='game_crow_patrol_v1']")
    expect(page).to_have_url(re.compile(r"/game/game_crow_patrol_v1\?arcade=1"))
    expect(page.locator("#token-count")).to_have_text("0")
    page.wait_for_function("window.game")
    page.evaluate("game.shell.finish({ line: 'Game over' })")
    expect(page.locator(".game-screen")).to_contain_text("back to the arcade")
    page.keyboard.press("Enter")
    expect(page).to_have_url(f"{live_server}/arcade")


def test_two_tokens_open_wanderpaw_at_a_new_morning(page: Page, live_server, tmp_path):
    place_on_home_row(page, live_server)
    give_tokens(tmp_path, 3)
    page.request.post(f"{live_server}/api/wander/tutorial", data={"step": "skip"})
    page.goto(f"{live_server}/arcade")
    page.click("[data-play='wanderpaw']")
    expect(page).to_have_url(f"{live_server}/wanderpaw")
    expect(page.locator("#token-count")).to_have_text("1")
    expect(page.locator("#day-go")).to_contain_text("Start playing a new day")
    # paid for, not started: back to the arcade, it's free to go on
    page.goto(f"{live_server}/arcade")
    expect(page.locator("[data-play='wanderpaw']")).to_have_count(0)
    page.click("[data-keep-playing='wanderpaw']")
    expect(page.locator("#day-go")).to_contain_text("Start playing a new day")


def test_arcade_games_wait_for_enough_letters(page: Page, live_server, tmp_path):
    give_tokens(tmp_path, 3)
    page.goto(f"{live_server}/arcade")
    expect(page.locator("[data-play='game_crow_patrol_v1']")).to_be_disabled()
    expect(page.locator(".game-card").first).to_contain_text("Learn a few more letters")


def _open_grownups(page, live_server):
    page.goto(f"{live_server}/parent")
    page.locator("#pin").fill(GROWNUP_PIN)
    page.keyboard.press("Enter")
    expect(page.locator("#grownups")).to_be_visible()


def test_parent_page_saves_settings_and_explains_the_next_lesson(page: Page, live_server):
    _open_grownups(page, live_server)
    card = page.locator(".player").first
    expect(card).to_contain_text("Tester")
    expect(card.locator(".brain")).to_contain_text("no letters taught yet")
    card.locator(".goal").fill("15")
    card.locator(".goal").dispatch_event("change")
    expect(page.locator(".player").first.locator(".saved")).to_have_text("Saved!")
    expect(page.locator(".player").first.locator(".goal-out")).to_have_text("15")
    page.goto(live_server)
    expect(page.locator("#home-day .day-label")).to_have_text("0 / 15 min")


def test_profile_page_has_no_duplicate_hub(page: Page, live_server):
    page.goto(f"{live_server}/profile")
    expect(page.locator(".hub-grid")).to_have_count(0)


def test_the_pin_guards_for_grownups_and_is_asked_every_visit(page: Page, live_server):
    page.goto(f"{live_server}/parent")
    expect(page.locator("#pin")).to_be_visible()
    expect(page.locator("#grownups")).to_be_hidden()
    assert page.request.get(f"{live_server}/api/parent").status == 403
    assert page.request.put(f"{live_server}/api/parent/settings", data={"goal_minutes": 3, "learn_vs_practice": 0.5}).status == 403
    page.locator("#pin").fill("9999")
    page.keyboard.press("Enter")
    expect(page.locator("#pin-message")).to_have_text("That's not the PIN.")
    expect(page.locator("#grownups")).to_be_hidden()
    page.locator("#pin").fill(GROWNUP_PIN)
    page.keyboard.press("Enter")
    expect(page.locator(".player")).to_have_count(1)  # only the player who's logged in
    expect(page.locator(".player")).to_contain_text("Tester")
    page.goto(live_server)
    page.goto(f"{live_server}/parent")  # back again: locked again
    expect(page.locator("#pin")).to_be_visible()
    assert page.request.get(f"{live_server}/api/parent").status == 403


def test_a_grownup_can_change_the_pin(page: Page, live_server):
    _open_grownups(page, live_server)
    page.click("#change-pin-go")
    page.locator(".pin-one").fill("4321")
    page.locator(".pin-two").fill("4321")
    page.keyboard.press("Enter")
    expect(page.locator("#change-pin .saved")).to_have_text("Saved!")
    page.goto(f"{live_server}/parent")
    page.locator("#pin").fill(GROWNUP_PIN)
    page.keyboard.press("Enter")
    expect(page.locator("#pin-message")).to_have_text("That's not the PIN.")
    page.locator("#pin").fill("4321")
    page.keyboard.press("Enter")
    expect(page.locator("#grownups")).to_be_visible()


def test_the_profile_menu_has_three_things_and_home_has_no_grownups_link(page: Page, live_server):
    page.goto(live_server)
    page.click(".topbar-avatar")
    items = page.locator(".profile-menu a, .profile-menu button")
    expect(items).to_have_text(["My profile", "Switch user", "For grown-ups"])
    assert page.locator('main a[href="/parent"]').count() == 0


@pytest.mark.first_run
@pytest.mark.no_player
def test_the_first_time_the_app_opens_a_grownup_chooses_the_pin(page: Page, live_server):
    page.goto(live_server)
    page.wait_for_url(f"{live_server}/welcome")
    expect(page.locator("#first-pin")).to_be_visible()
    expect(page.locator("#who")).to_be_hidden()
    assert page.request.post(f"{live_server}/api/grownups/pin", data={"pin": "12"}).status == 400
    page.locator(".pin-one").fill("5678")
    page.locator(".pin-two").fill("5679")
    page.keyboard.press("Enter")
    expect(page.locator(".pin-message")).to_have_text("Those don't match. Try again.")
    page.locator(".pin-two").fill("5678")
    page.keyboard.press("Enter")
    expect(page.locator("#first-pin")).to_be_hidden()
    expect(page.locator("#who")).to_be_visible()
    expect(page.locator("#new-player")).to_be_visible()
    # chosen now: nobody can choose another without it
    page.context.clear_cookies()
    assert page.request.post(f"{live_server}/api/grownups/pin", data={"pin": "0000"}).status == 403


@pytest.mark.installed
def test_an_install_has_no_labs_or_free_things(page: Page, live_server):
    for path in ("/labs", "/teach-lab", "/practice-lab", "/game-lab", "/pet-lab", "/wander-lab", "/scene-lab", "/move-lab",
                 "/practice/practice_fishing_v1", "/teach/teach_intro_home_row_v1", "/api/wander-lab/world",
                 "/api/scene-lab", "/api/pet-lab/species", "/api/move-lab", "/api/practice/modules", "/api/teach/modules"):
        assert page.request.get(f"{live_server}{path}").status == 404, path
    for path in ("/api/wander-lab/day-pass", "/api/wander-lab/to-the-end", "/api/wander-lab/refill", "/api/wander-lab/reset"):
        assert page.request.post(f"{live_server}{path}").status == 404, path
    assert page.request.post(f"{live_server}/api/wander/trip/start", data={}).status == 400  # a day costs tokens
    me = page.request.get(f"{live_server}/api/me").json()
    assert me["coins"] == 0  # no free coins


@pytest.mark.installed
def test_an_install_still_plays_its_lessons_and_arcade_games(page: Page, live_server, tmp_path):
    missing = []
    page.on("response", lambda r: missing.append(r.url) if r.status == 404 else None)
    place_on_home_row(page, live_server)
    give_tokens(tmp_path, 3)
    page.goto(f"{live_server}/session")
    expect(page.locator("#coin-count")).to_be_visible()
    page.wait_for_load_state("networkidle")
    # no way into a game but the arcade: a plain link goes there
    page.goto(f"{live_server}/game/game_crow_patrol_v1")
    expect(page).to_have_url(f"{live_server}/arcade")
    page.goto(f"{live_server}/game/game_crow_patrol_v1?arcade=1")  # nor by typing the address, without paying
    expect(page).to_have_url(f"{live_server}/arcade")
    page.click("[data-play='game_crow_patrol_v1']")
    page.wait_for_function("window.game")
    page.request.post(f"{live_server}/api/wander/tutorial", data={"step": "skip"})
    page.goto(f"{live_server}/arcade")
    page.click("[data-play='wanderpaw']")
    expect(page.locator("#day-go")).to_contain_text("Start playing a new day")
    page.wait_for_load_state("networkidle")
    assert missing == []


def test_switch_user_can_be_read_in_the_menu(page: Page, live_server):
    page.goto(live_server)
    page.click(".topbar-avatar")
    item = page.locator(".switch-player")
    expect(item).to_be_visible()
    color, link = page.evaluate(
        """() => [getComputedStyle(document.querySelector('.switch-player')).color,
                  getComputedStyle(document.querySelector('.profile-menu a')).color]"""
    )
    assert color == link  # looks like the links beside it
    assert page.evaluate("document.querySelector('.switch-player').getBoundingClientRect().height") > 10
