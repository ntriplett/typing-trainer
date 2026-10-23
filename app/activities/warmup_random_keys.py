"""Warmup v1: a quick, low-stakes repetition drill on 2 random keys.

Deliberately dumb (random keys, not yet the scheduler's actual weakest
keys) -- this exists to prove the module contract end to end. Once the
scheduler exists, it'll pass in the real weakest-keys list instead.
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
class WarmupRandomKeys:
    id: str = "warmup_random_keys_v1"
    kind: str = "warmup"

    def is_eligible(self, active_keys: list[str]) -> bool:
        return len(active_keys) >= 1

    def generate(
        self, active_keys: list[str], duration_s: int, rng: random.Random | None = None
    ) -> ActivityContent:
        keys = pick_two_keys(active_keys, rng)
        prompt = build_random_sequence(keys, duration_s, rng)
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys,
            prompt=prompt,
            instructions=f"Quick warmup on {' and '.join(sorted(set(keys)))} -- just get your fingers moving.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)
