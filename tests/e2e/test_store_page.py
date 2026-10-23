"""Real-browser e2e tests for coins + store (PLAN.md Section 11c): the
shared header shows coins and the avatar, a finished step pays coins
visibly, and the store can buy + wear an item.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db, store

from .conftest import start_quick_session, type_current_step_prompt


def _give_coins(tmp_path, amount: int) -> None:
    # live_server's DB lives at tmp_path / "e2e.db" (same function-scoped tmp_path)
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, amount, "test")


def test_header_shows_coins_and_avatar_on_home(page: Page, live_server):
    page.goto(live_server)
    expect(page.locator("#coin-count")).to_have_text("0")
    expect(page.locator(".topbar-avatar canvas")).to_be_visible()


def test_finishing_a_step_pays_coins_in_the_header(page: Page, live_server):
    start_quick_session(page, live_server)
    type_current_step_prompt(page)
    expect(page.locator("#result-coins")).to_contain_text("+100")
    expect(page.locator("#coin-count")).not_to_have_text("0")


def test_buy_and_wear_an_item(page: Page, live_server, tmp_path):
    item = min((i for i in store.CATALOG.values() if not i.starter), key=lambda i: i.price)
    page.goto(live_server)  # creates learner 1 before we add coins
    expect(page.locator("#coin-count")).to_have_text("0")
    _give_coins(tmp_path, item.price)

    page.goto(f"{live_server}/store")
    card = page.locator(f'.item-card[data-item-id="{item.id}"]')
    card.get_by_role("button", name="Buy").click()

    expect(card).to_have_class("item-card equipped")
    expect(card.get_by_role("button", name="Take off")).to_be_visible()
    expect(page.locator("#coin-count")).to_have_text("0")


def test_unaffordable_items_say_how_many_more_coins(page: Page, live_server):
    page.goto(f"{live_server}/store")
    expect(page.locator(".item-card button:disabled").first).to_contain_text("more")
