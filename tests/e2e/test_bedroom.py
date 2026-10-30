"""Real-browser e2e tests for the Home: decorating the bedroom (PLAN.md
11c-2, phase 5), walking between its rooms, the Dressing Room's hat stand,
and the Window Nook's postcards and day & night switch."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db, store


def _give_coins(tmp_path, amount: int) -> None:
    with db.open_db(tmp_path / "e2e.db") as conn:
        db.add_coins(conn, 1, amount, "test")


def _room(page: Page, live_server) -> dict:
    # page.request shares the browser's cookies, so it acts as the same player
    return page.request.get(f"{live_server}/api/room").json()["room"]


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
    start = _room(page, live_server)["items"][0]
    box = canvas.bounding_box()
    scale = box["width"] / 160
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
    page.request.post(f"{live_server}/api/store/buy/furniture_clock")

    page.goto(f"{live_server}/bedroom")
    page.locator("#inventory .thumb-choice[data-item-id='furniture_clock']").click()
    expect(page.locator("#selected-name")).to_have_text("Wall Clock")  # placing selects it
    assert _room(page, live_server)["items"][0]["item_id"] == "furniture_clock"

    page.click("#put-away")
    expect(page.locator("#inventory .thumb-choice[data-item-id='furniture_clock']")).to_be_visible()
    assert _room(page, live_server)["items"] == []


def _me(page: Page, live_server) -> dict:
    return page.request.get(f"{live_server}/api/me").json()


def test_walking_between_the_rooms(page: Page, live_server):
    page.goto(f"{live_server}/bedroom")
    expect(page.locator("#room-title")).to_have_text("My Bedroom")
    page.locator("[data-spot='dressing']").click()  # the doorway
    expect(page.locator("#room-title")).to_have_text("Dressing Room")
    expect(page).to_have_url(f"{live_server}/bedroom?room=dressing")
    page.locator("[data-spot='closet']").click()
    expect(page.locator("#room-title")).to_have_text("Closet")
    page.locator("#room-nav").get_by_role("button", name="Dressing Room").click()
    page.locator("[data-spot='bedroom']").click()
    page.locator("[data-spot='nook']").click()
    expect(page.locator("#room-title")).to_have_text("Window Nook")
    expect(page.locator("#decorate")).to_be_hidden()


def test_a_hat_goes_on_and_comes_off_at_the_hat_stand(page: Page, live_server, tmp_path):
    page.goto(live_server)
    _give_coins(tmp_path, store.CATALOG["hat_straw"].price)
    page.request.post(f"{live_server}/api/store/buy/hat_straw")
    page.request.post(f"{live_server}/api/store/unequip/hat")

    page.goto(f"{live_server}/bedroom?room=hats")
    page.locator("[data-spot='hat_straw']").click()
    page.wait_for_function("fetch('/api/me').then(r => r.json()).then(d => d.avatar.hat === 'hat_straw')")
    page.locator("[data-spot='hat_straw']").click()
    page.wait_for_function("fetch('/api/me').then(r => r.json()).then(d => !d.avatar.hat)")


def test_a_postcard_takes_you_there_and_unowned_ones_point_to_the_store(page: Page, live_server, tmp_path):
    page.goto(live_server)
    _give_coins(tmp_path, store.CATALOG["bg_beach"].price)
    page.request.post(f"{live_server}/api/store/buy/bg_beach")
    page.request.post(f"{live_server}/api/store/equip/bg_meadow")

    page.goto(f"{live_server}/bedroom?room=nook")
    page.locator("[data-spot='water']").click()
    expect(page.locator("#room-title")).to_have_text("Water Postcards")
    page.locator("[data-spot='bg_river']").click()
    expect(page.locator("#room-message")).to_contain_text("store")
    page.locator("[data-spot='bg_beach']").click()
    expect(page.locator("#room-message")).to_have_text("Welcome to Sandy Beach!")
    assert _me(page, live_server)["avatar"]["background"] == "bg_beach"


def test_the_day_and_night_switch(page: Page, live_server, tmp_path):
    page.goto(f"{live_server}/bedroom?room=nook")
    page.locator("[data-spot='daynight']").click()
    expect(page.locator("#room-message")).to_contain_text("store")  # no night unlocked yet

    _give_coins(tmp_path, store.CATALOG["night_forests"].price)
    page.request.post(f"{live_server}/api/store/buy/night_forests")
    page.request.put(f"{live_server}/api/me/night", data={"on": False})
    page.goto(f"{live_server}/bedroom?room=nook")
    page.locator("[data-spot='daynight']").click()
    expect(page.locator("#room-message")).to_contain_text("Goodnight")
    assert _me(page, live_server)["avatar"]["night"]


def test_cats_and_bunnies_may_nap_on_the_bed_but_not_others(page: Page, live_server, tmp_path):
    _give_coins(tmp_path, store.CATALOG["furniture_bed_blue"].price)
    page.request.post(f"{live_server}/api/store/buy/furniture_bed_blue")
    page.request.post(f"{live_server}/api/store/equip/furniture_bed_blue")  # into the room
    page.goto(f"{live_server}/bedroom")
    expect(page.locator("#room-canvas")).to_be_visible()
    page.wait_for_function("world !== null")
    area = page.evaluate("petArea(state.room)")
    bed = area["terrain"]["ledges"][0]
    assert bed["who"] == ["cat", "bunny"]
    assert any(p["action"] == "nap" and p.get("ledge") == 0 for p in area["props"])
