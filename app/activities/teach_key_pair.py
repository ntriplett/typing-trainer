"""Teach module: one or two new keys, on any row. A run of short pages,
all moved through by key presses like the intro:

  new keys -> meet each key (reach keys: reach, back home, reach-and-return
  drill) -> take turns -> eyes up -> mix with known keys -> real words
  (when the known letters can spell some) -> done.

`focus_keys` are the new keys; `allowed_keys` are keys already taught,
used for the mix and words pages. Pairs come from teach_curriculum.py.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent, default_coins, score_attempt
from app.activities.teach_steps import (
    keys_in_steps,
    meet_key_steps,
    mix_prompt,
    show_step,
    take_turns_prompt,
    type_step,
)
from app.activities.word_bank import words_for
from app.finger_map import KEY_TO_FINGER


def _caps(keys: list[str]) -> str:
    return " and ".join(f"[{k}]" for k in keys)


def build_key_pair_steps(new_keys: list[str], known_keys: list[str], rng: random.Random) -> list[dict]:
    fingers = [KEY_TO_FINGER[k] for k in new_keys]
    one = len(new_keys) == 1
    steps = [
        show_step(
            "A new key!" if one else "Two new keys!",
            f"Today: {_caps(new_keys)}. Fingers on home, then press [Space].",
            advance_key=" ",
            fingers=fingers + ["left_thumb", "right_thumb"],
            keys=list(new_keys),
        )
    ]
    for key in new_keys:
        steps += meet_key_steps(key)
    if not one:
        steps.append(type_step("Take turns", f"Back and forth: {_caps(new_keys)}.", take_turns_prompt(*new_keys)))
    steps.append(
        show_step(
            "Eyes up!",
            "Try not to look at your hands. The orange finger shows the way. Press [Space].",
            advance_key=" ",
            fingers=["left_thumb", "right_thumb"],
        )
    )
    known = [k for k in known_keys if k not in new_keys and k != " "]
    steps.append(
        type_step(
            "Mix it up",
            "New keys and keys you know." if known else f"Just {_caps(new_keys)}, all mixed up.",
            mix_prompt(list(new_keys), known, rng),
        )
    )
    words = words_for(list(new_keys), known, 4, rng)
    if len(words) >= 2:
        steps.append(type_step("Real words!", "You can type real words now.", " ".join(words)))
    steps.append(
        show_step(
            "You learned " + ("a new key!" if one else "two new keys!"),
            f"{_caps(new_keys)} are yours now. Press [Space] to finish.",
            advance_key=" ",
            fingers=["left_thumb", "right_thumb"],
        )
    )
    return steps


@dataclass(frozen=True, slots=True)
class TeachKeyPair:
    id: str = "teach_key_pair_v1"
    kind: str = "teach"
    title: str = "Two new keys"
    description: str = "Meet one or two new keys: where they are, which finger, then practice."
    first_finish_coins: int = 0

    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool:
        return (
            1 <= len(focus_keys) <= 2
            and len(set(focus_keys)) == len(focus_keys)
            and all(k in KEY_TO_FINGER and k != " " for k in focus_keys)
        )

    def generate(
        self,
        focus_keys: list[str],
        allowed_keys: list[str],
        duration_s: int,
        rng: random.Random | None = None,
        chars_per_second: float = 2.0,
    ) -> ActivityContent:
        if not self.is_eligible(focus_keys, allowed_keys):
            raise ValueError(f"Need 1-2 different letter/number keys, got {focus_keys!r}")
        steps = build_key_pair_steps(list(focus_keys), allowed_keys, rng or random.Random())
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys_in_steps(steps),
            prompt=" | ".join(s["prompt"] for s in steps if s["prompt"]),
            instructions=f"Learning {' and '.join(k.upper() for k in focus_keys)}.",
            micro_steps=steps,
        )

    def score(self, content: ActivityContent, keystrokes: list[KeystrokeEvent]) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        return default_coins(content, result)
