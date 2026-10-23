"""Teach demo variant 2: "Reach & Return."

Sequence: diagram -> a drill that alternates the new key with its OWN
home key (f r f r f r...), drilling the actual reach-and-return motion
rather than the new key in isolation -> combo practice.

Bet being tested: explicitly practicing the motion relative to the
resting position (not just the destination key alone) builds a
cleaner motor pattern, since the reach always starts and ends at the
same anchor.

Demo-only -- see teach_hand_anchor_demo.py's module docstring for why
this isn't in the main activity REGISTRY.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent, default_coins, score_attempt
from app.activities.micro_lesson import (
    build_combo_step,
    build_diagram_step,
    build_reach_return_drill_step,
)


@dataclass(frozen=True, slots=True)
class TeachReachReturnDemo:
    id: str = "teach_reach_return_demo_v1"
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
        rng = rng or random.Random()
        key = focus_keys[0]
        combo_keys = [k for k in allowed_keys if k != key][:2] or [key]

        micro_steps = [
            build_diagram_step(key),
            build_reach_return_drill_step(key, repeats=6),
            build_combo_step(key, combo_keys, duration_chars=24, rng=rng),
        ]
        prompt = " | ".join(s["prompt"] for s in micro_steps if s["prompt"])
        keys = sorted(set([key, *combo_keys]))

        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys,
            prompt=prompt,
            instructions=f"Learning {key.upper()}: feel the reach, then combo.",
            micro_steps=micro_steps,
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        return default_coins(content, result)
