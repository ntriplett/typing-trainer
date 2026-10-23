"""Practice v1: randomized pseudo-word drilling on 2 random keys -- the
"fold the new key into the mix" phase that follows teach, per
PLAN.md Section 6.
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
class PracticeRandomKeys:
    id: str = "practice_random_keys_v1"
    kind: str = "practice"

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
            instructions=f"Practice: {' and '.join(sorted(set(keys)))}, mixed up this time.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)
