"""Shared helpers for driving brain-picked lessons through the API."""

from datetime import UTC, datetime, timedelta

from app import main


class Clock:
    """Stands in for main.now so tests can move time forward."""

    def __init__(self):
        self.t = datetime.now(UTC)

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def keystrokes_for(prompt: str, correct: bool = True) -> list[dict]:
    return [
        {"expected_char": ch, "typed_char": ch if correct else "?", "correct": correct, "latency_ms": 200}
        for ch in prompt
    ]


def run_lesson(client, clock: Clock | None = None, seconds: int = 60, correct: bool = True, **extra) -> dict:
    """Ask for the next lesson, 'type' all of it, finish it. Returns
    {"lesson", "content", "done"} (done = the completion response)."""
    nxt = client.post("/api/lesson/next")
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    if clock:
        clock.advance(seconds=seconds)
    done = client.post(
        f"/api/lesson/{body['lesson']['lesson_id']}/complete",
        json={"keystrokes": keystrokes_for(body["content"]["prompt"], correct), "active_ms": seconds * 1000, **extra},
    )
    assert done.status_code == 200, done.text
    return {**body, "done": done.json()}


def use_clock(monkeypatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(main, "now", clock)
    return clock
