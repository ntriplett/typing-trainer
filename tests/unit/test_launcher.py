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
