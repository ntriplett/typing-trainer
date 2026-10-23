"""Teach demo variant 1: "Hand Anchor."

Sequence: diagram (show the reach) -> home-row anchor check -> short
isolated drill on the new key -> combo practice with 2 known keys.
The straightforward, textbook micro-lesson structure -- the baseline
to compare the other 2 demo variants against.

Demo-only: registered in app/activities/teach_demos.py, NOT in the
main activity REGISTRY, so it doesn't touch the live scheduler or the
"exactly one activity per kind" assumption production code relies on.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent, default_coins, score_attempt
from app.activities.micro_lesson import (
    build_anchor_check_step,
    build_combo_step,
    build_isolated_drill_step,
    build_diagram_step,
)


@dataclass(frozen=True, slots=True)
class TeachHandAnchorDemo:
    id: str = "teach_hand_anchor_demo_v1"
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
            build_anchor_check_step(rng),
            build_isolated_drill_step(key, repeats=8),
            build_combo_step(key, combo_keys, duration_chars=24, rng=rng),
        ]
        prompt = " | ".join(s["prompt"] for s in micro_steps if s["prompt"])
        keys = sorted(set([key, *combo_keys]))

        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys,
            prompt=prompt,
            instructions=f"Learning {key.upper()}: diagram, home-row check, drill, then combo.",
            micro_steps=micro_steps,
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        return default_coins(content, result)
