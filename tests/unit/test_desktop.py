"""The installed copy's version checks and update request (app/desktop.py)."""

import io
import json

import pytest

from app import desktop


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    monkeypatch.setattr(desktop, "_cache", {"at": None, "latest": None})


def test_parse_version():
    assert desktop.parse_version("v1.2.0") == (1, 2, 0)
    assert desktop.parse_version("0.10") == (0, 10)
    assert desktop.parse_version("v1.0-beta") is None


def test_is_newer_compares_numbers_not_text():
    assert desktop.is_newer("v0.10.0", "0.9.0")
    assert not desktop.is_newer("v0.1.0", "0.1.0")
    assert not desktop.is_newer("nightly", "0.1.0")


def _release(**overrides):
    release = {
        "tag_name": "v9.0.0", "body": "New pets!", "html_url": "https://example/rel",
        "assets": [{"name": "install.ps1", "browser_download_url": "https://x/install.ps1"},
                   {"name": "typing-trainer-v9.0.0.zip", "browser_download_url": "https://x/app.zip"}],
    }
    release.update(overrides)
    return release


def _serve(monkeypatch, release):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        return io.BytesIO(json.dumps(release).encode())

    monkeypatch.setattr(desktop.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_fetch_latest_picks_the_app_zip(monkeypatch):
    _serve(monkeypatch, _release())
    assert desktop.fetch_latest() == {
        "tag": "v9.0.0", "zip_url": "https://x/app.zip", "notes": "New pets!", "page": "https://example/rel",
    }


def test_fetch_latest_none_without_zip_or_offline(monkeypatch):
    _serve(monkeypatch, _release(assets=[]))
    assert desktop.fetch_latest() is None

    def offline(req, timeout):
        raise OSError("no network")

    monkeypatch.setattr(desktop.urllib.request, "urlopen", offline)
    assert desktop.fetch_latest() is None


def test_latest_checks_github_at_most_hourly(monkeypatch):
    calls = _serve(monkeypatch, _release())
    desktop.latest()
    desktop.latest()
    assert len(calls) == 1
    desktop.latest(force=True)
    assert len(calls) == 2


def test_status_is_off_outside_the_installed_app(monkeypatch):
    monkeypatch.delenv("TYPING_TRAINER_HOME", raising=False)
    calls = _serve(monkeypatch, _release())
    assert desktop.status()["installed"] is False
    assert calls == []


def test_status_offers_a_newer_release(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPING_TRAINER_HOME", str(tmp_path))
    _serve(monkeypatch, _release())
    s = desktop.status()
    assert s["available"] is True and s["latest"] == "v9.0.0" and s["notes"] == "New pets!"


def test_request_update_leaves_it_for_the_launcher(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPING_TRAINER_HOME", str(tmp_path))
    _serve(monkeypatch, _release())
    exits = []
    monkeypatch.setattr(desktop, "exit_soon", lambda: exits.append(True))
    assert desktop.request_update() == {"tag": "v9.0.0"}
    assert json.loads((tmp_path / "data" / "update.json").read_text()) == {
        "tag": "v9.0.0", "zip_url": "https://x/app.zip",
    }
    assert exits == [True]


def test_request_update_refuses_when_current(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPING_TRAINER_HOME", str(tmp_path))
    _serve(monkeypatch, _release(tag_name=f"v{desktop.VERSION}"))
    monkeypatch.setattr(desktop, "exit_soon", lambda: pytest.fail("must not exit"))
    with pytest.raises(LookupError):
        desktop.request_update()
    assert not (tmp_path / "data" / "update.json").exists()
