"""Teach demo variant 3: "Staged Combo Builder."

Sequence: diagram -> short isolated drill -> combo with just 1 known
key -> combo widened to up to 3 known keys. Instead of jumping straight
from "isolated" to "mixed with everything," the combo pool grows one
key at a time.

Bet being tested: a graduated widening ("then tries with in combo with
a few other keys," read literally as incremental) gives each new
transition a smaller jump in difficulty than diagram -> isolated ->
full combo in one step, while still reaching full interleaved practice
(the contextual-interference-backed goal) by the end.

Demo-only -- see teach_hand_anchor_demo.py's module docstring for why
this isn't in the main activity REGISTRY.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent, score_attempt
from app.activities.micro_lesson import build_combo_step, build_diagram_step, build_isolated_drill_step


@dataclass(frozen=True, slots=True)
class TeachStagedComboDemo:
    id: str = "teach_staged_combo_demo_v1"
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
        others = [k for k in allowed_keys if k != key]

        micro_steps = [build_diagram_step(key), build_isolated_drill_step(key, repeats=6)]
        pool_sizes_used: list[int] = []
        for pool_size in (1, 2, 3):
            combo_keys = others[:pool_size]
            if not combo_keys:
                break
            micro_steps.append(build_combo_step(key, combo_keys, duration_chars=16, rng=rng))
            pool_sizes_used.append(pool_size)

        prompt = " | ".join(s["prompt"] for s in micro_steps if s["prompt"])
        widest_pool = others[: pool_sizes_used[-1]] if pool_sizes_used else []
        keys = sorted(set([key, *widest_pool]))

        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys,
            prompt=prompt,
            instructions=f"Learning {key.upper()}: drill, then combo -- one more key each round.",
            micro_steps=micro_steps,
        )

    def score(
        self, content: ActivityContent, keystrokes: list[KeystrokeEvent]
    ) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)
