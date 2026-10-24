"""The dev-coins switch (app/config.py)."""

from fastapi.testclient import TestClient

from app import config, db, main


def test_dev_grant_is_given_once(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "DEV_START_COINS", 500)
    client = TestClient(main.app)
    assert client.get("/api/me").json()["coins"] == 500
    assert client.get("/api/me").json()["coins"] == 500  # not again
    with db.open_db(tmp_path / "t.db") as conn:
        assert [e.reason for e in db.list_coin_history(conn, 1)] == ["dev_grant"]


def test_dev_grant_off_in_tests():
    assert config.DEV_START_COINS == 0
