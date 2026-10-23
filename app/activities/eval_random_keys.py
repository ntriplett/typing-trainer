"""Eval v1: a timed check on 2 random keys.

v1 uses the same scoring as the other modules -- accuracy/WPM/reward
tier. What makes an eval different (deciding whether skills are solid
enough, feeding "should we even run an eval today" in the scheduler)
is scheduler-level logic that doesn't exist yet (PLAN.md Section 6);
this module just proves an eval-shaped activity can run end to end.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import (
    ActivityContent,
    ActivityResult,
    KeystrokeEvent,
    build_random_sequence,
    pick_two_keys,
    score_attempt,
)


@dataclass(frozen=True, slots=True)
class EvalRandomKeys:
    id: str = "eval_random_keys_v1"
    kind: str = "eval"

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
        prompt = build_random_sequence(keys, duration_s, rng, chars_per_second=chars_per_second)
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys,
            prompt=prompt,
            instructions=f"Quick check on {' and '.join(sorted(set(keys)))} -- just do your best, no pressure.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)
