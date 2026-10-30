"""Applying an update in the install folder (launcher/update.py)."""

import json
import os
import sqlite3
import zipfile

from launcher import update


def _root(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "versions" / "v0.1.0").mkdir(parents=True)
    (tmp_path / "current.txt").write_text("v0.1.0")
    return tmp_path


def test_backup_db_copies_progress_and_keeps_ten(tmp_path):
    root = _root(tmp_path)
    with sqlite3.connect(root / "data" / "typing.db") as conn:
        conn.execute("CREATE TABLE t (x)")
        conn.execute("INSERT INTO t VALUES (42)")
    backups = root / "data" / "backups"
    backups.mkdir()
    for i in range(12):
        (backups / f"typing-2020010{i:02d}-000000-before-v0.0.{i}.db").touch()
    dest = update.backup_db(root, "v0.2.0")
    with sqlite3.connect(dest) as conn:
        assert conn.execute("SELECT x FROM t").fetchone() == (42,)
    kept = sorted(backups.glob("typing-*.db"))
    assert len(kept) == update.KEEP_BACKUPS and dest in kept


def test_backup_db_without_a_db_is_fine(tmp_path):
    assert update.backup_db(_root(tmp_path), "v0.2.0") is None


def _release_zip(path, top="typing-trainer/"):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(top + "pyproject.toml", "[project]\nversion = '0.2.0'\n")
        z.writestr(top + "app/main.py", "")
    return path


def test_unpack_strips_the_top_folder(tmp_path):
    root = _root(tmp_path)
    dest = root / "versions" / "v0.2.0"
    update.unpack(_release_zip(tmp_path / "r.zip"), dest)
    assert (dest / "pyproject.toml").exists() and (dest / "app" / "main.py").exists()
    assert [p.name for p in (root / "versions").iterdir() if "tmp" in p.name] == []


def test_unpack_refuses_a_zip_that_isnt_the_app(tmp_path):
    root = _root(tmp_path)
    with zipfile.ZipFile(tmp_path / "bad.zip", "w") as z:
        z.writestr("readme.txt", "hi")
    try:
        update.unpack(tmp_path / "bad.zip", root / "versions" / "v0.2.0")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    assert not (root / "versions" / "v0.2.0").exists()


def test_prune_keeps_current_and_one_previous(tmp_path):
    root = _root(tmp_path)
    for i, tag in enumerate(["v0.0.1", "v0.0.2", "v0.2.0"]):
        d = root / "versions" / tag
        d.mkdir()
        os.utime(d, (1000 + i, 1000 + i))
    os.utime(root / "versions" / "v0.1.0", (1001.5, 1001.5))
    update.prune_versions(root, "v0.2.0")
    assert sorted(p.name for p in (root / "versions").iterdir()) == ["v0.1.0", "v0.2.0"]


def _no_window(work, message):
    work()


def test_apply_switches_version_and_clears_the_request(tmp_path, monkeypatch):
    root = _root(tmp_path)
    (root / "data" / "update.json").write_text("{}")
    zip_path = _release_zip(tmp_path / "r.zip")
    monkeypatch.setattr(update.urllib.request, "urlretrieve", lambda url, dest: dest.write_bytes(zip_path.read_bytes()))
    monkeypatch.setattr(update, "sync_packages", lambda root, d: None)
    monkeypatch.setattr(update, "with_progress_window", _no_window)
    assert update.apply(root, {"tag": "v0.2.0", "zip_url": "https://x/app.zip"}) is True
    assert (root / "current.txt").read_text() == "v0.2.0"
    assert not (root / "data" / "update.json").exists()


def test_failed_update_keeps_the_old_version(tmp_path, monkeypatch):
    root = _root(tmp_path)
    (root / "data" / "update.json").write_text(json.dumps({"tag": "v0.2.0"}))
    zip_path = _release_zip(tmp_path / "r.zip")
    monkeypatch.setattr(update.urllib.request, "urlretrieve", lambda url, dest: dest.write_bytes(zip_path.read_bytes()))

    def broken_sync(root, d):
        raise RuntimeError("uv sync failed")

    monkeypatch.setattr(update, "sync_packages", broken_sync)
    monkeypatch.setattr(update, "with_progress_window", _no_window)
    assert update.apply(root, {"tag": "v0.2.0", "zip_url": "https://x/app.zip"}) is False
    assert (root / "current.txt").read_text() == "v0.1.0"
    assert not (root / "data" / "update.json").exists()
    assert "failed" in (root / "data" / "update.log").read_text()
