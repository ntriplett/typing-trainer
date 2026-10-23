"""Shared building blocks for the "teach" demo variants (PLAN.md's call
for a real teach experience: hand/finger diagrams, a home-row anchor
check, a short isolated drill, then combo practice with known keys --
not just "hit this key a bunch").

Research basis (see the research summary given alongside these demos):
  - Software can't sense physical hand position, so "checking fingers
    are on the home row" means a strong VISUAL anchor (diagram +
    highlighted finger/key) plus a home-row anchor-check EXERCISE
    (type the home row in the expected finger pattern) -- not literal
    sensing. This matches how RapidTyping/Dance Mat Typing/TypingClub
    all do it: virtual keyboard + finger highlight, never hardware
    detection.
  - Each new key is taught as a "reach" from its home-row finger --
    label which finger moves and from where, not just flash the letter.
  - Keep the brand-new key's ISOLATED blocked repetition short. The
    contextual interference literature (blocked vs. random motor
    practice) shows blocked practice is easier/faster during
    acquisition but produces worse retention than quickly moving to
    randomized/interleaved practice -- so combo practice (mixing the
    new key with already-known ones, shuffled) should start soon
    after the isolated drill, not after a long isolated block.
  - Review before new: combo practice reinforces existing keys while
    introducing the new one, rather than teaching in total isolation.

Every builder here returns a plain dict (not a nested dataclass) for
ActivityContent.micro_steps -- kept maximally flexible since these are
explicitly experimental/demo content shapes.
"""

from __future__ import annotations

import random

from app.finger_map import HOME_KEY_FOR_FINGER, HOME_ROW_KEYS, KEY_TO_FINGER

# Home row in physical left-to-right order, for the anchor-check step.
HOME_ROW_ORDER = HOME_ROW_KEYS


def finger_for_key(key: str) -> str:
    finger = KEY_TO_FINGER.get(key)
    if finger is None:
        raise ValueError(f"No finger assignment for key {key!r}")
    return finger


def home_key_for(key: str) -> str:
    return HOME_KEY_FOR_FINGER[finger_for_key(key)]


def finger_label(finger: str) -> str:
    """'left_index' -> 'left index finger'."""
    return finger.replace("_", " ") + " finger"


def build_diagram_step(key: str) -> dict:
    """Pure visual intro: no typing, just "here's the reach" (PLAN.md's
    call for "shows where your hand should be on the keys").
    """
    finger = finger_for_key(key)
    home = home_key_for(key)
    if home == key:
        text = f"Rest your {finger_label(finger)} on {key.upper()} -- that's its home key."
    else:
        text = (
            f"Your {finger_label(finger)} rests on {home.upper()}. "
            f"To type {key.upper()}, it reaches over and comes right back."
        )
    return {
        "kind": "diagram",
        "instructions": text,
        "highlight_key": key,
        "home_key": home,
        "finger": finger,
        "prompt": "",
    }


def build_anchor_check_step(rng: random.Random | None = None) -> dict:
    """Type the home row in order -- confirms the resting-position
    pattern before introducing anything new. This is the practical,
    software-feasible stand-in for "checking fingers are on home row":
    we can't sense hands, but a clean run through the home row in
    order is a reasonable proxy that the pattern is still there.
    """
    return {
        "kind": "anchor_check",
        "instructions": "Fingers on the home row. Type each key in order, left to right.",
        "highlight_key": None,
        "prompt": " ".join(HOME_ROW_ORDER),
    }


def build_isolated_drill_step(key: str, repeats: int = 8) -> dict:
    """A SHORT blocked repetition of just the new key -- kept brief on
    purpose (see module docstring re: contextual interference).
    """
    finger = finger_for_key(key)
    return {
        "kind": "drill",
        "instructions": f"Just {key.upper()} for now. Use your {finger_label(finger)}.",
        "highlight_key": key,
        "prompt": " ".join([key * 4] * (repeats // 4 or 1)),
    }


def build_reach_return_drill_step(key: str, repeats: int = 6) -> dict:
    """Drill the REACH itself, not just the new key in isolation: the
    finger alternates between its home key and the new key, mirroring
    the actual motion ("leave home, press new key, return home")
    rather than treating the new key as if it had no relationship to
    the resting position.
    """
    home = home_key_for(key)
    finger = finger_for_key(key)
    pair = f"{home}{key}" * 2
    return {
        "kind": "drill",
        "instructions": (
            f"Feel the reach: your {finger_label(finger)} leaves {home.upper()}, "
            f"taps {key.upper()}, and comes right back."
        ),
        "highlight_key": key,
        "home_key": home,
        "prompt": " ".join([pair] * (repeats // 2 or 1)),
    }


def build_combo_step(
    key: str, combo_keys: list[str], duration_chars: int = 24, rng: random.Random | None = None
) -> dict:
    """Interleaved practice mixing the new key with already-known ones
    -- the "tries it in combo with a few other keys" step, and the
    part the contextual-interference research says matters for
    retention more than more isolated drilling would.
    """
    rng = rng or random.Random()
    pool = [key] + list(combo_keys)
    chars = [rng.choice(pool) for _ in range(duration_chars)]
    chunks = ["".join(chars[i : i + 4]) for i in range(0, len(chars), 4)]
    return {
        "kind": "combo",
        "instructions": f"Mix it in with {', '.join(k.upper() for k in combo_keys)}.",
        "highlight_key": key,
        "prompt": " ".join(chunks),
    }
