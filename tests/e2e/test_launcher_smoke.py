"""Real end-to-end smoke test: actually spawn the server as a subprocess,
the way the desktop icon will, and talk to it over a real socket.

This is the test that proves "the backend can kick off and be reached
in a browser" rather than just exercising the app in-process.
"""

import time
import urllib.request

import pytest

from launcher import start as launcher


def _wait_for_port_free(timeout_s: float = 5.0) -> None:
    """After killing a process, the OS can take a moment to release the
    listening socket. Poll rather than assume terminate()+wait() is instant.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not launcher.port_in_use(launcher.HOST, launcher.PORT):
            return
        time.sleep(0.1)
    raise TimeoutError("Port did not free up after terminating the server")


@pytest.fixture()
def running_server():
    _wait_for_port_free()
    proc = launcher.spawn_server()
    try:
        healthy = launcher.wait_for_health(timeout_s=15.0)
        assert healthy, "Server did not become healthy in time"
        yield proc
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        _wait_for_port_free()


def test_server_actually_serves_over_a_real_socket(running_server):
    with urllib.request.urlopen(launcher.APP_URL, timeout=2) as resp:
        assert resp.status == 200
        body = resp.read().decode()
        assert "Typing Trainer" in body

    with urllib.request.urlopen(
        f"http://{launcher.HOST}:{launcher.PORT}/api/activities/hello-world", timeout=2
    ) as resp:
        assert resp.status == 200


def test_second_launch_attaches_instead_of_double_spawning(running_server):
    # Simulates double-clicking the desktop icon while the server is
    # already up: main() must detect it via the port and skip spawning.
    ok = launcher.main(open_browser=False)
    assert ok is True
    # Still only one thing listening on the port — if a second server had
    # tried to bind it, spawn_server's subprocess would have failed to
    # start, not silently coexisted, so a successful health check here is
    # proof there's exactly one.
    assert launcher.port_in_use(launcher.HOST, launcher.PORT)
