"""Game v1: a placeholder "game" that is really just the same mixed-pool
typing drill as the others, tagged kind="game" instead of real game
mechanics.

This is intentional per PLAN.md Section 11a: the module contract and
the scheduler must not care what a game looks like. Content/prompt is
still plain text today; a real game later swaps in a different
ActivityContent shape (positions, timing, sprites) and the front-end
renders it differently based on `kind`/`activity_id` -- nothing here
or in the scheduler has to change for that to happen.
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

# A fun/general reinforcement break, not another drill -- lighter focus
# than practice.
FOCUS_RATIO = 0.4


@dataclass(frozen=True, slots=True)
class GameRandomKeys:
    id: str = "game_random_keys_v1"
    kind: str = "game"

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
            instructions=f"Game placeholder: type {label} as they show up.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        return default_coins(content, result)
