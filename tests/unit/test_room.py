"""Unit tests for decoratable rooms (PLAN.md 11c-2, phase 5)."""

import pytest

from app import db, room, store


@pytest.fixture()
def conn():
    with db.open_db(":memory:") as c:
        yield c


@pytest.fixture()
def learner_id(conn):
    lid = db.create_learner(conn, "Sam").id
    store.grant_starters(conn, lid)
    db.add_coins(conn, lid, 50_000, "test")
    return lid


def _buy(conn, learner_id, item_id):
    store.buy(conn, learner_id, item_id)


def test_new_room_has_starter_surfaces_and_nothing_placed(conn, learner_id):
    state = room.state(conn, learner_id)
    assert (state["wallpaper"], state["flooring"]) == ("wallpaper_cream", "flooring_planks")
    assert state["items"] == [] and state["inventory"] == []


def test_every_furniture_piece_has_a_zone():
    for item in store.CATALOG.values():
        if item.slot == "furniture":
            assert item.group in room.DEFAULT_SPOT


def test_buying_furniture_puts_it_in_inventory_then_place_move_put_away(conn, learner_id):
    _buy(conn, learner_id, "furniture_desk")
    assert [i["item_id"] for i in room.state(conn, learner_id)["inventory"]] == ["furniture_desk"]
    placed_id = room.place(conn, learner_id, "furniture_desk")
    state = room.state(conn, learner_id)
    assert state["inventory"] == [] and state["items"][0]["item_id"] == "furniture_desk"
    room.move(conn, learner_id, placed_id, 10, 70)
    assert (room.state(conn, learner_id)["items"][0]["x"], room.state(conn, learner_id)["items"][0]["y"]) == (10, 70)
    room.put_away(conn, learner_id, placed_id)
    assert room.state(conn, learner_id)["items"] == []


def test_each_piece_places_once_and_must_be_owned(conn, learner_id):
    with pytest.raises(room.RoomError, match="own"):
        room.place(conn, learner_id, "furniture_lamp")
    _buy(conn, learner_id, "furniture_lamp")
    room.place(conn, learner_id, "furniture_lamp")
    with pytest.raises(room.RoomError, match="already"):
        room.place(conn, learner_id, "furniture_lamp")


def test_positions_are_clamped_to_the_room(conn, learner_id):
    _buy(conn, learner_id, "furniture_plant")
    placed_id = room.place(conn, learner_id, "furniture_plant", x=-20, y=500)
    item = room.state(conn, learner_id)["items"][0]
    assert (item["x"], item["y"]) == (0, room.ROOM_H - 1)
    room.move(conn, learner_id, placed_id, 300, -5)
    item = room.state(conn, learner_id)["items"][0]
    assert (item["x"], item["y"]) == (room.ROOM_W - 1, 0)


def test_furniture_from_the_old_square_room_moves_over_once(conn, learner_id):
    """The room grew from 96x96 to 160x90: old pieces shift right 32 (to stay
    centered) and up 6 (the wall got shorter), and only the first time."""
    _buy(conn, learner_id, "furniture_plant")
    conn.execute(
        "INSERT INTO room_item (learner_id, room, item_id, x, y, wide) VALUES (?, 'bedroom', 'furniture_plant', 10, 70, 0)",
        (learner_id,),
    )
    db.init_schema(conn)
    db.init_schema(conn)
    item = room.state(conn, learner_id)["items"][0]
    assert (item["x"], item["y"]) == (42, 64)


def test_surfaces_need_ownership_except_starters(conn, learner_id):
    with pytest.raises(room.RoomError, match="own"):
        room.set_surface(conn, learner_id, "wallpaper_stars")
    _buy(conn, learner_id, "wallpaper_stars")
    store.equip(conn, learner_id, "wallpaper_stars")  # store "Use" sets the surface
    assert room.state(conn, learner_id)["wallpaper"] == "wallpaper_stars"
    room.set_surface(conn, learner_id, "wallpaper_cream")
    assert room.state(conn, learner_id)["wallpaper"] == "wallpaper_cream"


def test_store_use_on_furniture_places_it(conn, learner_id):
    _buy(conn, learner_id, "furniture_window")
    store.equip(conn, learner_id, "furniture_window")
    store.equip(conn, learner_id, "furniture_window")  # second time is a no-op
    assert [i["item_id"] for i in room.state(conn, learner_id)["items"]] == ["furniture_window"]


def test_rooms_never_mix_between_learners(conn, learner_id):
    alex = db.create_learner(conn, "Alex").id
    _buy(conn, learner_id, "furniture_teddy")
    placed_id = room.place(conn, learner_id, "furniture_teddy")
    assert room.state(conn, alex)["items"] == []
    with pytest.raises(room.RoomError):
        room.move(conn, alex, placed_id, 1, 1)
    with pytest.raises(room.RoomError):
        room.put_away(conn, alex, placed_id)
