"""Teach module: the intro. Where hands live on the keyboard (home row),
the F/J bumps, and thumbs on the space bar.

Every step moves on from a key press, never a mouse click: once the
fingers are on home they stay there for the whole lesson.

Not in the live scheduler yet: registered in app/activities/teach_modules.py
until teach modules are strung together into lessons.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.activities.base import ActivityContent, ActivityResult, KeystrokeEvent, default_coins, score_attempt
from app.activities.teach_steps import keys_in_steps, show_step, type_step

LEFT_FINGERS = ["left_pinky", "left_ring", "left_middle", "left_index"]
RIGHT_FINGERS = ["right_index", "right_middle", "right_ring", "right_pinky"]

# Real words made only of home-row letters, so the last step feels like
# actual typing. Two are picked per lesson.
HOME_ROW_PHRASES = (
    "a sad lad",
    "ask dad",
    "all fall",
    "a flask",
    "add salad",
    "dad falls",
    "a lass asks",
    "alfalfa",
)


def build_intro_steps(rng: random.Random) -> list[dict]:
    phrases = rng.sample(HOME_ROW_PHRASES, 2)
    return [
        show_step(
            "Welcome!",
            "Your hands have a home on the keyboard. Let's find it! "
            "Press [Space] with your thumb to start.",
            advance_key=" ",
            fingers=["left_thumb", "right_thumb"],
        ),
        show_step(
            "Find the bumps",
            "Feel the little bumps on [F] and [J]? Your pointer fingers live there. "
            "Put your left pointer finger on [F] and press it.",
            advance_key="f",
            keys=["f", "j"],
        ),
        show_step(
            "Right pointer finger",
            "Now your right pointer finger goes on the other bump, [J]. Press [J].",
            advance_key="j",
        ),
        show_step(
            "Left hand home",
            "Let your other left fingers fall in a row: middle on [D], ring on [S], "
            "pinky on [A]. Press [A] with your pinky.",
            advance_key="a",
            fingers=LEFT_FINGERS,
            keys=["a", "s", "d", "f"],
        ),
        type_step(
            "Say hi, left hand",
            "Each finger presses its own key. Watch which finger lights up.",
            "a s d f",
        ),
        show_step(
            "Right hand home",
            "Same on the right: middle on [K], ring on [L], pinky on [;]. "
            "Press [;] with your right pinky.",
            advance_key=";",
            fingers=RIGHT_FINGERS,
            keys=["j", "k", "l", ";"],
        ),
        type_step(
            "Say hi, right hand",
            "One finger, one key.",
            "j k l ;",
        ),
        show_step(
            "Thumbs on the space bar",
            "Your thumbs float just above the long [Space] bar. Tap it with either thumb, "
            "whichever feels best. Keep your fingers resting on home.",
            advance_key=" ",
            fingers=["left_thumb", "right_thumb"],
        ),
        type_step(
            "Letter, then space",
            "Type a letter, then tap [Space] with your thumb.",
            "f j f j d k d k",
        ),
        show_step(
            "No peeking!",
            "Lift your hands off the keyboard. Now put them back without looking: "
            "feel for the bumps on [F] and [J]. Press [J] when you're home.",
            advance_key="j",
            keys=["f", "j"],
            fingers=LEFT_FINGERS + RIGHT_FINGERS,
        ),
        type_step(
            "The whole home row",
            "Left hand, then right hand.",
            "asdf jkl; asdf jkl;",
        ),
        type_step(
            "Partner fingers",
            "Each finger and its partner on the other hand.",
            "fj dk sl a; fj dk sl a;",
        ),
        type_step(
            "Real words!",
            "Home-row letters make real words.",
            " ".join(phrases),
        ),
        show_step(
            "You did it!",
            "Your hands know their home now. Press [Space] to finish.",
            advance_key=" ",
            fingers=["left_thumb", "right_thumb"],
        ),
    ]


@dataclass(frozen=True, slots=True)
class TeachIntroHomeRow:
    id: str = "teach_intro_home_row_v1"
    kind: str = "teach"
    title: str = "Hands on home"
    description: str = "Where your fingers rest on the home row, the F and J bumps, and thumbs on space."

    def is_eligible(self, focus_keys: list[str], allowed_keys: list[str]) -> bool:
        # The very first lesson: nothing needs to be known beforehand.
        return True

    def generate(
        self,
        focus_keys: list[str],
        allowed_keys: list[str],
        duration_s: int,
        rng: random.Random | None = None,
        chars_per_second: float = 2.0,
    ) -> ActivityContent:
        steps = build_intro_steps(rng or random.Random())
        return ActivityContent(
            activity_id=self.id,
            kind=self.kind,
            keys=keys_in_steps(steps),
            prompt=" | ".join(s["prompt"] for s in steps if s["prompt"]),
            instructions=self.description,
            micro_steps=steps,
        )

    def score(self, content: ActivityContent, keystrokes: list[KeystrokeEvent]) -> ActivityResult:
        return score_attempt(self.id, content.keys, keystrokes)

    def coins(self, content: ActivityContent, result: ActivityResult) -> int:
        return default_coins(content, result)
