"""Practice v1: randomized pseudo-word drilling, balanced between the
current focus keys and the broader allowed set -- the "fold the new
key into real use" phase that follows teach, per PLAN.md Section 6.
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
    default_coins,
    score_attempt,
)

# Balanced -- practice is where new keys get folded into general use,
# not drilled in isolation (that's teach's job) or ignored (that's why
# this isn't 0).
FOCUS_RATIO = 0.5


@dataclass(frozen=True, slots=True)
class PracticeRandomKeys:
    id: str = "practice_random_keys_v1"
    kind: str = "practice"

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
            instructions=f"Practice: {focus_label}, mixed up this time.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        return default_coins(content, result)
