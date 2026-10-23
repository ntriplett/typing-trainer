"""Game v1: a placeholder "game" that is really just the same random-key
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
    build_random_sequence,
    pick_two_keys,
    score_attempt,
)


@dataclass(frozen=True, slots=True)
class GameRandomKeys:
    id: str = "game_random_keys_v1"
    kind: str = "game"

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
            instructions=f"Game placeholder: type {' and '.join(sorted(set(keys)))} as they show up.",
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)
