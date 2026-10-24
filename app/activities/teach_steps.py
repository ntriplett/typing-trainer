"""Shared step builders for the keyboard-driven teach modules (the intro,
then home/top/bottom/number rows and capitals).

A teach module is a list of plain-dict steps (ActivityContent.micro_steps)
that the front-end player (web/static/js/teach_player.js) runs with the
keyboard only -- the learner's hands never leave home to reach for the
mouse. There are two kinds:

  - "show": explain something on the ghost-hand keyboard, then wait for
    one specific key ("press Space with your thumb when you're ready").
    That key press IS the "continue" button.
  - "type": type a short prompt. The player highlights the finger and key
    for each character as it comes up.

Text may mark keys as [F] or [Space]; the player draws those as keycaps.
"""

from __future__ import annotations

from app.finger_map import KEY_TO_FINGER

# Finger names the ghost hands understand. KEY_TO_FINGER says "thumb" for
# space (either thumb); the hands can also highlight one thumb at a time.
HAND_FINGERS: frozenset[str] = frozenset(
    {f for f in KEY_TO_FINGER.values() if f != "thumb"} | {"left_thumb", "right_thumb", "thumb"}
)
# Keys the ghost keyboard can highlight beyond the typeable characters.
EXTRA_KEYS: frozenset[str] = frozenset({"shift_l", "shift_r"})


def _check_keys(keys: list[str]) -> None:
    for key in keys:
        if key not in KEY_TO_FINGER and key not in EXTRA_KEYS:
            raise ValueError(f"Unknown key {key!r}")


def _check_fingers(fingers: list[str]) -> None:
    for finger in fingers:
        if finger not in HAND_FINGERS:
            raise ValueError(f"Unknown finger {finger!r}")


def show_step(
    title: str,
    text: str,
    advance_key: str,
    fingers: list[str] | None = None,
    keys: list[str] | None = None,
    reach: dict[str, str] | None = None,
) -> dict:
    """Explain, then wait for `advance_key`. `fingers`/`keys` are lit up on
    the ghost hands; `reach` moves a finger off home onto a key, e.g.
    {"left_index": "r"}. The advance key's own finger is always lit, so
    "press J" can never point at the wrong finger.
    """
    if advance_key not in KEY_TO_FINGER:
        raise ValueError(f"Unknown advance key {advance_key!r}")
    keys = list(keys) if keys is not None else [advance_key]
    fingers = list(fingers or [])
    advance_finger = KEY_TO_FINGER[advance_key]
    if advance_finger not in fingers and not (
        advance_finger == "thumb" and {"left_thumb", "right_thumb"} & set(fingers)
    ):
        fingers.append(advance_finger)
    reach = dict(reach or {})
    _check_keys(keys + list(reach.values()))
    _check_fingers(fingers + list(reach))
    return {
        "kind": "show",
        "title": title,
        "text": text,
        "advance_key": advance_key,
        "fingers": fingers,
        "keys": keys,
        "reach": reach,
        "prompt": "",
    }


def type_step(title: str, text: str, prompt: str) -> dict:
    """Type `prompt`; a wrong key doesn't move on (the learner retries it),
    so a finished step always means every character was typed right once.
    """
    if not prompt:
        raise ValueError("A type step needs a prompt")
    _check_keys(sorted(set(prompt)))
    return {"kind": "type", "title": title, "text": text, "prompt": prompt}


def keys_in_steps(steps: list[dict]) -> list[str]:
    """Every typeable key a lesson asks for, for scoring (ActivityContent.keys)."""
    keys: set[str] = set()
    for step in steps:
        if step["kind"] == "show":
            keys.add(step["advance_key"])
        keys.update(step["prompt"])
    return sorted(keys)
