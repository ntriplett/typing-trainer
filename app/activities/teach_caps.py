"""Teach modules for capital letters: Shift is held by the pinky of the
OTHER hand from the letter (left-hand letter -> right Shift).

  - TeachCapsIntro: the idea, with J (left Shift) and F (right Shift).
  - TeachCapsGroup: a few capitals at a time, one hand on one row (A S D F,
    Q W E R, ...; groups in teach_curriculum.py). A "these use right Shift"
    page, a page per letter, big-and-small, capital words, done.

Capitals come after every letter is taught, so words may use any letter.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent, default_coins, score_attempt
from app.activities.teach_steps import keys_in_steps, shift_focus, shift_for, show_step, type_step
from app.activities.word_bank import WORDS

THUMBS = ["left_thumb", "right_thumb"]
PINKIES = ["left_pinky", "right_pinky"]


def _side(letter: str) -> str:
    return "right" if shift_for(letter)[0] == "shift_r" else "left"


def big_letter_step(letter: str) -> dict:
    side = _side(letter)
    hand = "left" if side == "right" else "right"
    return show_step(
        f"Big [{letter.upper()}]",
        f"[{letter.upper()}] is on your {hand} hand, so hold {side} [Shift] with your {side} pinky. "
        f"Then press [{letter.upper()}].",
        advance_key=letter.upper(),
        **shift_focus(letter),
    )


def capital_words(letters: list[str], count: int, rng: random.Random) -> list[str]:
    """Up to `count` capitalized words that start with one of `letters`."""
    fits = sorted({w for w in WORDS if w[0] in letters and len(w) > 1})
    return [w.capitalize() for w in rng.sample(fits, min(count, len(fits)))]


def _content(activity, steps: list[dict], instructions: str) -> ActivityContent:
    return ActivityContent(
        activity_id=activity.id,
        kind=activity.kind,
        keys=keys_in_steps(steps),
        prompt=" | ".join(s["prompt"] for s in steps if s["prompt"]),
        instructions=instructions,
        micro_steps=steps,
    )


@dataclass(frozen=True, slots=True)
class TeachCapsIntro:
    id: str = "teach_caps_intro_v1"
    kind: str = "teach"
    title: str = "Big letters"
    description: str = "Capitals: hold Shift with the pinky of the other hand."
    first_finish_coins: int = 0

    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool:
        return True

    def generate(self, focus_keys, allowed_keys, duration_s, rng=None, chars_per_second=2.0) -> ActivityContent:
        steps = [
            show_step(
                "Big letters!",
                "To make a capital, hold [Shift] while you press the letter. Press [Space].",
                advance_key=" ",
                fingers=PINKIES + THUMBS,
                keys=["shift_l", "shift_r"],
            ),
            show_step(
                "Two Shift keys",
                "There's a [Shift] by each pinky. Use the one on the other hand from the letter. "
                "Press [Space].",
                advance_key=" ",
                fingers=PINKIES + THUMBS,
                keys=["shift_l", "shift_r"],
                reach={"left_pinky": "shift_l", "right_pinky": "shift_r"},
            ),
            big_letter_step("j"),
            big_letter_step("f"),
            type_step("Switch sides", "Small, then big. Watch which pinky lights up.", "jJ fF jJ fF"),
            type_step("Capital words", "Names and first words get a capital.", "Dad Sal Ask Lad Fall"),
            show_step("You did it!", "Big letters are easy now. Press [Space] to finish.", advance_key=" ", fingers=THUMBS),
        ]
        return _content(self, steps, self.description)

    def score(self, content: ActivityContent, keystrokes: list[KeystrokeEvent]) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        return default_coins(content, result)


@dataclass(frozen=True, slots=True)
class TeachCapsGroup:
    id: str = "teach_caps_v1"
    kind: str = "teach"
    title: str = "Capitals"
    description: str = "A few capital letters at a time, one hand and one row."
    first_finish_coins: int = 0

    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool:
        # 1-5 different letters, all typed by the same hand (so one Shift).
        return (
            1 <= len(focus_keys) <= 5
            and len(set(focus_keys)) == len(focus_keys)
            and all(len(k) == 1 and k.isalpha() and k.islower() for k in focus_keys)
            and len({_side(k) for k in focus_keys}) == 1
        )

    def generate(self, focus_keys, allowed_keys, duration_s, rng=None, chars_per_second=2.0) -> ActivityContent:
        if not self.is_eligible(focus_keys, allowed_keys):
            raise ValueError(f"Need 1-5 letters from one hand, got {focus_keys!r}")
        rng = rng or random.Random()
        letters = list(focus_keys)
        side = _side(letters[0])
        shift_key, pinky = shift_for(letters[0])
        caps = " ".join(f"[{k.upper()}]" for k in letters)
        steps = [
            show_step(
                "New capitals!",
                f"Today: {caps}. They're all on one hand, so they all use {side} [Shift]. Press [Space].",
                advance_key=" ",
                fingers=[pinky, *THUMBS],
                keys=[shift_key, *letters],
                reach={pinky: shift_key},
            ),
            *[big_letter_step(k) for k in letters],
            type_step(
                "Big and small",
                f"Hold {side} [Shift] for the big ones.",
                " ".join(k.upper() + k for k in letters + rng.sample(letters, min(2, len(letters)))),
            ),
            type_step(
                "Mix it up",
                "A big letter, then small ones.",
                " ".join(
                    rng.choice(letters).upper() + "".join(rng.choice(letters) for _ in range(rng.choice((1, 2))))
                    for _ in range(6)
                ),
            ),
        ]
        words = capital_words(letters, 4, rng)
        if len(words) >= 2:
            steps.append(type_step("Capital words", "A big letter starts each word.", " ".join(words)))
        steps.append(
            show_step(
                "You learned new capitals!",
                f"{caps} are yours now. Press [Space] to finish.",
                advance_key=" ",
                fingers=THUMBS,
            )
        )
        return _content(self, steps, f"Capitals {' '.join(k.upper() for k in letters)}.")

    def score(self, content: ActivityContent, keystrokes: list[KeystrokeEvent]) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        return default_coins(content, result)
