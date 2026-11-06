"""Real-browser e2e test for sharing a pet with another player here
(app/pet_share.py): Share with a friend in the Pet Care Center, then the
friend adopts it from Special Orders' "From a friend" shelf."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from app import db
from app import pet_genes as g

from .conftest import place_on_home_row


def test_share_a_pet_and_the_friend_adopts_it(page: Page, live_server, tmp_path):
    place_on_home_row(page, live_server)  # Tester (1)
    assert page.request.post(f"{live_server}/api/profiles", data={"name": "Alex"}).ok  # now playing as Alex (2)
    place_on_home_row(page, live_server)
    assert page.request.post(f"{live_server}/api/profiles/1/select").ok
    with db.open_db(tmp_path / "e2e.db") as conn:
        cat = db.add_v3_pet(conn, 1, g.roll("cat", None, None, 21), "Mittens", "shop")
        conn.commit()

    page.goto(f"{live_server}/pets/care?pet={cat}")
    page.get_by_role("button", name="💌 Share with a friend").click()
    expect(page.locator(".share-ask")).to_contain_text("Share Mittens with Alex?")
    page.get_by_role("button", name="💌 Alex").click()
    expect(page.locator("#care-message")).to_contain_text("Tomorrow Alex will find a baby like Mittens")
    page.get_by_role("button", name="💌 Share with a friend").click()
    expect(page.locator(".share-why")).to_contain_text("still waiting")
    expect(page.get_by_role("button", name="💌 Alex")).to_be_disabled()

    with db.open_db(tmp_path / "e2e.db") as conn:  # a day goes by
        conn.execute("UPDATE pet_share SET sent_on = '2000-01-01'")
        db.add_coins(conn, 2, 5000, "test")
        conn.commit()
    assert page.request.post(f"{live_server}/api/profiles/2/select").ok
    page.goto(f"{live_server}/pets/shop")
    expect(page.locator(".shop-spot[data-dept='orders']")).to_contain_text("A pet from a friend!")
    page.goto(f"{live_server}/pets/shop?dept=orders")
    shelf = page.locator(".friend-shelf")
    expect(shelf).to_contain_text("Tester shared a cat with you!")
    shelf.locator(".friend-pet").click()
    expect(page.locator("#detail-body")).to_contain_text("Shared by Tester")
    page.locator("#detail-body").get_by_role("button", name="Buy for").click()
    expect(page.locator("#detail-body")).to_contain_text("Welcome home")
    page.locator("#detail-body").get_by_role("button", name="Yay!").click()
    expect(page.locator(".friend-shelf")).to_have_count(0)

    with db.open_db(tmp_path / "e2e.db") as conn:
        [copy] = db.list_v3_pets(conn, 2)
    page.goto(f"{live_server}/pets/care?pet={copy['id']}")
    expect(page.locator(".detail-facts")).to_contain_text("shared by Tester")
