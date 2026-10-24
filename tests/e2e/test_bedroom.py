"""Real-browser e2e tests for the bedroom editor (PLAN.md 11c-2, phase 5)."""

from __future__ import annotations

import json
import urllib.request

from playwright.sync_api import Page, expect

from app import db, store


def _give_coins(tmp_path, amount: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, amount, "test")


def _room(live_server) -> dict:
    with urllib.request.urlopen(f"{live_server}/api/room") as resp:
        return json.loads(resp.read())["room"]


def test_buying_furniture_puts_it_in_the_room_and_dragging_saves(page: Page, live_server, tmp_path):
    page.goto(live_server)
    expect(page.locator("#coin-count")).to_have_text("0")
    _give_coins(tmp_path, store.CATALOG["furniture_toy_chest"].price)

    page.goto(f"{live_server}/store")
    page.click("[data-tab='bedroom']")
    card = page.locator('.item-card[data-item-id="furniture_toy_chest"]')
    card.get_by_role("button", name="Buy").click()
    expect(page.locator('.item-card[data-item-id="furniture_toy_chest"]').get_by_role("button", name="In your room ✓")).to_be_visible()

    page.goto(f"{live_server}/bedroom")
    canvas = page.locator("#room-canvas")
    expect(canvas).to_be_visible()
    start = _room(live_server)["items"][0]
    box = canvas.bounding_box()
    scale = box["width"] / 96
    # grab the chest's middle and drag it 20 room-pixels left
    gx = box["x"] + (start["x"] + 9) * scale
    gy = box["y"] + (start["y"] + 6) * scale
    page.mouse.move(gx, gy)
    page.mouse.down()
    page.mouse.move(gx - 20 * scale, gy, steps=5)
    page.mouse.up()
    expect(page.locator("#selected-name")).to_have_text("Toy Chest")
    page.wait_for_function(
        "x => fetch('/api/room').then(r => r.json()).then(d => d.room.items[0].x === x)", arg=start["x"] - 20
    )


def test_put_away_moves_it_to_the_inventory(page: Page, live_server, tmp_path):
    page.goto(live_server)
    expect(page.locator("#coin-count")).to_have_text("0")
    _give_coins(tmp_path, store.CATALOG["furniture_clock"].price)
    with urllib.request.urlopen(urllib.request.Request(f"{live_server}/api/store/buy/furniture_clock", method="POST")):
        pass

    page.goto(f"{live_server}/bedroom")
    page.locator("#inventory .thumb-choice[data-item-id='furniture_clock']").click()
    expect(page.locator("#selected-name")).to_have_text("Wall Clock")  # placing selects it
    assert _room(live_server)["items"][0]["item_id"] == "furniture_clock"

    page.click("#put-away")
    expect(page.locator("#inventory .thumb-choice[data-item-id='furniture_clock']")).to_be_visible()
    assert _room(live_server)["items"] == []
