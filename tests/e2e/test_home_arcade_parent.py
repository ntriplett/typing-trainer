"""Real-browser e2e tests for the home hub, the arcade, and the parent page."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from app import db

from .conftest import place_on_home_row


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
    expect(page.locator("[data-play='game_pet_battle_v1']")).to_be_disabled()  # costs 2
    page.click("[data-play='game_crow_patrol_v1']")
    expect(page).to_have_url(re.compile(r"/game/game_crow_patrol_v1\?arcade=1"))
    expect(page.locator("#token-count")).to_have_text("0")
    page.wait_for_function("window.game")
    page.evaluate("game.shell.finish({ line: 'Game over' })")
    expect(page.locator(".game-screen")).to_contain_text("back to the arcade")
    page.keyboard.press("Enter")
    expect(page).to_have_url(f"{live_server}/arcade")


def test_arcade_games_wait_for_enough_letters(page: Page, live_server, tmp_path):
    give_tokens(tmp_path, 3)
    page.goto(f"{live_server}/arcade")
    expect(page.locator("[data-play='game_crow_patrol_v1']")).to_be_disabled()
    expect(page.locator(".game-card").first).to_contain_text("Learn a few more letters")


def test_parent_page_saves_settings_and_explains_the_next_lesson(page: Page, live_server):
    page.goto(f"{live_server}/parent")
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
