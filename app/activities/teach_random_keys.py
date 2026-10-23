"""Teach v1: introduce the focus key(s) -- normally just 1 at a time now
that the scheduler picks real "next untaught key" targets -- with a
blocked (non-randomized) repetition pattern. Isolate one motion at a
time rather than mixing keys immediately, per PLAN.md Section 2's
"technique before throughput."

Deliberately ignores allowed_keys: "a teaching session should really
just work on [the focus letters]" (your words) -- the point of this
lesson is 100% attention on what's new.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import (
    ActivityContent,
    ActivityResult,
    KeystrokeEvent,
    build_blocked_sequence,
    score_attempt,
)


@dataclass(frozen=True, slots=True)
class TeachRandomKeys:
    id: str = "teach_random_keys_v1"
    kind: str = "teach"

    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool:
        return len(focus_keys) >= 1

    def generate(
        self,
        focus_keys: list[str],
        allowed_keys: list[str],
        duration_s: int,
        rng: random.Random | None = None,
        chars_per_second: float = 2.0,
    ) -> ActivityContent:
        prompt = build_blocked_sequence(focus_keys, duration_s, chars_per_second=chars_per_second)
        label = " and ".join(sorted(set(focus_keys)))
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=list(focus_keys),
            prompt=prompt,
            instructions=f"New key{'s' if len(set(focus_keys)) > 1 else ''}: {label}. Type each block slowly and watch your fingers.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)
