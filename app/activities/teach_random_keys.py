"""Teach v1: introduce 2 random keys with a blocked (non-randomized)
repetition pattern -- isolate one motion at a time rather than mixing
keys immediately, per PLAN.md Section 2's "technique before throughput."

Same v1 caveat as the other modules: picks random keys for now rather
than the scheduler's actual "next key to introduce." Swapping that in
later is a one-line change at the call site, not a module rewrite.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import (
    ActivityContent,
    ActivityResult,
    KeystrokeEvent,
    build_blocked_sequence,
    pick_two_keys,
    score_attempt,
)


@dataclass(frozen=True, slots=True)
class TeachRandomKeys:
    id: str = "teach_random_keys_v1"
    kind: str = "teach"

    def is_eligible(self, active_keys: list[str]) -> bool:
        return len(active_keys) >= 1

    def generate(
        self,
        active_keys: list[str],
        duration_s: int,
        rng: random.Random | None = None,
        chars_per_second: float = 2.0,
    ) -> ActivityContent:
        keys = pick_two_keys(active_keys, rng)
        prompt = build_blocked_sequence(keys, duration_s, chars_per_second=chars_per_second)
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys,
            prompt=prompt,
            instructions=f"New keys: {' and '.join(sorted(set(keys)))}. Type each block slowly and watch your fingers.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)
