"""Real-browser e2e tests for coins + store (PLAN.md Section 11c): the
shared header shows coins and the avatar, a finished step pays coins
visibly, and the store can buy + wear an item.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from app import db, store

from .conftest import start_practice_lesson, type_current_lesson


def _give_coins(tmp_path, amount: int) -> None:
    # live_server's DB lives at tmp_path / "e2e.db" (same function-scoped tmp_path)
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, amount, "test")


def test_header_shows_coins_and_avatar_on_home(page: Page, live_server):
    page.goto(live_server)
    expect(page.locator("#coin-count")).to_have_text("0")
    expect(page.locator(".topbar-avatar canvas")).to_be_visible()


def test_finishing_a_lesson_pays_coins_in_the_header(page: Page, live_server):
    start_practice_lesson(page, live_server)
    type_current_lesson(page)
    expect(page.locator("#result-rewards")).to_contain_text("+100")
    expect(page.locator("#coin-count")).not_to_have_text("0")


def test_buying_puts_it_on_and_points_to_the_home(page: Page, live_server, tmp_path):
    item = min((i for i in store.CATALOG.values() if not i.starter), key=lambda i: i.price)
    page.goto(live_server)  # creates learner 1 before we add coins
    expect(page.locator("#coin-count")).to_have_text("0")
    _give_coins(tmp_path, item.price)

    page.goto(f"{live_server}/store")
    card = page.locator(f'.item-card[data-item-id="{item.id}"]')
    card.get_by_role("button", name="Buy").click()

    expect(card).to_have_class("item-card equipped")
    expect(card.get_by_role("button", name=re.compile("✓"))).to_be_visible()  # changed in your Home from now on
    expect(page.locator("#coin-count")).to_have_text("0")


def test_unaffordable_items_say_how_many_more_coins(page: Page, live_server):
    page.goto(f"{live_server}/store")
    expect(page.locator(".item-card button:disabled").first).to_contain_text("more")


def test_every_catalog_item_has_a_sprite(page: Page, live_server):
    page.goto(f"{live_server}/store")
    expect(page.locator(".item-card").first).to_be_visible()
    ids = [i.id for i in store.CATALOG.values() if i.slot in store.SLOTS]
    assert page.evaluate("ids => missingSprites(ids)", ids) == []


def test_color_swatches_switch_the_card(page: Page, live_server):
    page.goto(f"{live_server}/store")
    card = page.locator('.item-card[data-family="shirt_tee"]')
    expect(card).to_have_attribute("data-item-id", "shirt_tee_red")
    card.locator(".color-swatch").nth(1).click()
    expect(page.locator('.item-card[data-family="shirt_tee"]')).to_have_attribute("data-item-id", "shirt_tee_blue")
    expect(page.locator("#preview-label")).to_contain_text("Blue T-Shirt")
