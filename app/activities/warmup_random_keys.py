"""Warmup v1: a quick, low-stakes drill mostly on the current focus
keys, with a bit of the broader allowed set mixed in so it doesn't
feel like an isolated drill.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import (
    ActivityContent,
    ActivityResult,
    KeystrokeEvent,
    combined_pool,
    build_mixed_sequence,
    score_attempt,
)

# Your call: warmup is mostly focus keys, a little general review.
FOCUS_RATIO = 0.75


@dataclass(frozen=True, slots=True)
class WarmupRandomKeys:
    id: str = "warmup_random_keys_v1"
    kind: str = "warmup"

    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool:
        return len(focus_keys) + len(allowed_keys) >= 1

    def generate(
        self,
        focus_keys: list[str],
        allowed_keys: list[str],
        duration_s: int,
        rng: random.Random | None = None,
        chars_per_second: float = 2.0,
    ) -> ActivityContent:
        prompt = build_mixed_sequence(
            focus_keys, allowed_keys, FOCUS_RATIO, duration_s, rng, chars_per_second=chars_per_second
        )
        keys = combined_pool(focus_keys, allowed_keys)
        focus_label = " and ".join(sorted(set(focus_keys))) or " and ".join(sorted(set(allowed_keys)))
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys,
            prompt=prompt,
            instructions=f"Quick warmup on {focus_label} -- just get your fingers moving.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)
