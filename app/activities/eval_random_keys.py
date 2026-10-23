"""Eval v1: a timed check mostly across the allowed set (how's
everything learned so far holding up), with a modest dose of the
current focus keys mixed in.

v1 uses the same scoring as the other modules -- accuracy/WPM/reward
tier. What makes an eval different (deciding whether skills are solid
enough, feeding "should we even run an eval today") is scheduler-level
logic (PLAN.md Section 6); this module just proves an eval-shaped
activity can run end to end.
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

# Mostly a broad check across everything learned, not another drill on
# whatever's newest.
FOCUS_RATIO = 0.3


@dataclass(frozen=True, slots=True)
class EvalRandomKeys:
    id: str = "eval_random_keys_v1"
    kind: str = "eval"

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
        label = " and ".join(sorted(set(keys)))
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys,
            prompt=prompt,
            instructions=f"Quick check on {label} -- just do your best, no pressure.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)
