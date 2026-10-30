"""Fast unit tests for launcher logic — no real server process.

The real single-instance guard is: "only call spawn_server() when the
port is free." That's tested deterministically here with monkeypatching.
The real end-to-end version (actually spawning uvicorn) lives in
tests/e2e/test_launcher_smoke.py since it's slow and touches real sockets.
"""

import socket
from unittest.mock import MagicMock

from launcher import start as launcher


def test_port_in_use_false_when_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    # probe's context manager closed the socket, so the port is free again.
    assert launcher.port_in_use("127.0.0.1", free_port) is False


def test_port_in_use_true_when_bound():
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    port = holder.getsockname()[1]
    try:
        assert launcher.port_in_use("127.0.0.1", port) is True
    finally:
        holder.close()


def test_main_does_not_spawn_when_already_running(monkeypatch):
    monkeypatch.setattr(launcher, "port_in_use", lambda host, port: True)
    monkeypatch.setattr(launcher, "wait_for_health", lambda timeout_s=10.0: True)
    spawn = MagicMock()
    monkeypatch.setattr(launcher, "spawn_server", spawn)

    ok = launcher.main(open_browser=False)

    assert ok is True
    spawn.assert_not_called()


def test_main_spawns_when_not_running(monkeypatch):
    monkeypatch.setattr(launcher, "port_in_use", lambda host, port: False)
    monkeypatch.setattr(launcher, "wait_for_health", lambda timeout_s=10.0: True)
    spawn = MagicMock()
    monkeypatch.setattr(launcher, "spawn_server", spawn)

    ok = launcher.main(open_browser=False)

    assert ok is True
    spawn.assert_called_once()


def test_main_reports_failure_if_server_never_becomes_healthy(monkeypatch):
    monkeypatch.setattr(launcher, "port_in_use", lambda host, port: False)
    monkeypatch.setattr(launcher, "wait_for_health", lambda timeout_s=10.0: False)
    monkeypatch.setattr(launcher, "spawn_server", MagicMock())

    ok = launcher.main(open_browser=False)

    assert ok is False


# --- The installed Windows copy ---------------------------------------------

from pathlib import Path


class FakeProc:
    """poll() answers None until `exits_after` calls, then 0."""

    def __init__(self, exits_after=None):
        self.exits_after, self.polls, self.terminated = exits_after, 0, False

    def poll(self):
        self.polls += 1
        if self.terminated or (self.exits_after is not None and self.polls > self.exits_after):
            return 0
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


def _clock(step):
    t = [0.0]

    def clock():
        t[0] += step
        return t[0]

    return clock


def test_find_browser_prefers_chrome_then_edge(tmp_path):
    env = {"PROGRAMFILES": str(tmp_path / "pf"), "PROGRAMFILES(X86)": str(tmp_path / "pf86"),
           "LOCALAPPDATA": str(tmp_path / "local")}
    assert launcher.find_browser(env) is None
    edge = tmp_path / "pf86" / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.touch()
    assert launcher.find_browser(env) == edge
    chrome = tmp_path / "local" / "Google" / "Chrome" / "Application" / "chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.touch()
    assert launcher.find_browser(env) == chrome


def test_app_window_uses_app_mode_and_its_own_profile():
    args = launcher.app_window_args(Path("chrome.exe"), Path("data/browser"))
    assert f"--app={launcher.APP_URL}" in args
    assert f"--user-data-dir={Path('data/browser')}" in args


def test_installed_env_points_at_the_data_folder(tmp_path):
    env = launcher.installed_env(tmp_path)
    assert env["TYPING_TRAINER_HOME"] == str(tmp_path)
    assert env["TYPING_TRAINER_DB_PATH"] == str(tmp_path / "data" / "typing.db")
    assert env["TYPING_TRAINER_DEV_START_COINS"] == "0"


def test_closing_the_window_stops_the_server():
    server, window = FakeProc(), FakeProc(exits_after=3)
    launcher.wait_for_close(server, window, clock=_clock(10), sleep=lambda s: None)
    assert server.terminated


def test_window_handed_off_leaves_the_server_to_its_idle_watch():
    server, window = FakeProc(exits_after=20), FakeProc(exits_after=0)
    launcher.wait_for_close(server, window, clock=_clock(0.1), sleep=lambda s: None)
    assert not server.terminated  # it quit by itself


def test_server_quitting_to_update_closes_the_window():
    server, window = FakeProc(exits_after=2), FakeProc()
    launcher.wait_for_close(server, window, clock=_clock(10), sleep=lambda s: None)
    assert window.terminated
