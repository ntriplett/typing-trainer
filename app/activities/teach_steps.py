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
Capital letters are typeable too: the player expects Shift on the other
hand from the letter (shift_focus below).
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


def is_capital(ch: str) -> bool:
    return ch.isupper() and ch.lower() in KEY_TO_FINGER


def _finger(ch: str) -> str:
    return KEY_TO_FINGER[ch.lower()]


def _check_keys(keys: list[str]) -> None:
    for key in keys:
        if key not in KEY_TO_FINGER and key not in EXTRA_KEYS and not is_capital(key):
            raise ValueError(f"Unknown key {key!r}")


def shift_for(letter: str) -> tuple[str, str]:
    """The Shift key and pinky for a capital: always the other hand's."""
    if _finger(letter).startswith("left"):
        return "shift_r", "right_pinky"
    return "shift_l", "left_pinky"


def shift_focus(letter: str) -> dict:
    """show_step fingers/keys/reach for a capital: the letter's finger and
    key, plus the other hand's pinky reaching onto its Shift."""
    key = letter.lower()
    shift_key, pinky = shift_for(key)
    finger = _finger(key)
    reach = {pinky: shift_key}
    if HOME_FOR_FINGER[finger] != key:
        reach[finger] = key
    return {"fingers": [finger, pinky], "keys": [shift_key, key], "reach": reach}


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
    if advance_key not in KEY_TO_FINGER and not is_capital(advance_key):
        raise ValueError(f"Unknown advance key {advance_key!r}")
    keys = list(keys) if keys is not None else [advance_key.lower()]
    fingers = list(fingers or [])
    advance_finger = _finger(advance_key)
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


# --- shared lesson pieces (any row: home, top, bottom, numbers) ----------------

FINGER_NAMES: dict[str, str] = {
    "left_pinky": "left pinky", "left_ring": "left ring finger",
    "left_middle": "left middle finger", "left_index": "left pointer finger",
    "right_index": "right pointer finger", "right_middle": "right middle finger",
    "right_ring": "right ring finger", "right_pinky": "right pinky", "thumb": "thumb",
}
HOME_FOR_FINGER: dict[str, str] = {KEY_TO_FINGER[k]: k for k in "asdfjkl;"}

# Where each key sits, in key widths from the keyboard's left edge
# (each row is shifted right a bit more than the one above it).
_ROWS = ("1234567890", "qwertyuiop", "asdfghjkl;", "zxcvbnm,./")
_ROW_START = (1.0, 1.5, 1.75, 2.25)
_KEY_SPOT: dict[str, tuple[int, float]] = {
    key: (row, _ROW_START[row] + col) for row, keys in enumerate(_ROWS) for col, key in enumerate(keys)
}


def finger_name(key: str) -> str:
    return FINGER_NAMES[KEY_TO_FINGER[key]]


def home_key(key: str) -> str:
    """The home-row key the finger for `key` rests on."""
    return HOME_FOR_FINGER[KEY_TO_FINGER[key]]


def reach_phrase(key: str) -> str:
    """How the finger gets from its home key to `key`: "reaches up",
    "reaches way up and to the left", "stretches over to the right"...
    """
    home_row, home_x = _KEY_SPOT[home_key(key)]
    row, x = _KEY_SPOT[key]
    rows, dx = row - home_row, x - home_x
    side = "" if abs(dx) < 0.6 else ("to the right" if dx > 0 else "to the left")
    if rows == 0:
        return f"stretches over {side}"
    way = {-2: "reaches way up", -1: "reaches up", 1: "reaches down"}[rows]
    return f"{way} and {side}" if side else way


def meet_key_steps(key: str) -> list[dict]:
    """The pages that introduce one key: where it is and which finger
    presses it, then a quick drill. A reach key also gets a "back home"
    page and a reach-and-return drill (home, key, home, key...).
    """
    finger = KEY_TO_FINGER[key]
    home = home_key(key)
    if key == home:
        return [
            show_step(
                f"Meet [{key}]",
                f"[{key}] is home for your {finger_name(key)}. Press [{key}].",
                advance_key=key,
            ),
            type_step(f"Just [{key}]", "Tap, tap, then a thumb on [Space].", f"{key * 2} {key * 2} {key * 3}"),
        ]
    return [
        show_step(
            f"Meet [{key}]",
            f"Your {finger_name(key)} {reach_phrase(key)} from [{home}] to [{key}]. Press [{key}].",
            advance_key=key,
            reach={finger: key},
        ),
        show_step(
            "Back home",
            f"Now slide back home to [{home}]. Press [{home}].",
            advance_key=home,
        ),
        type_step(
            "Reach and come back",
            f"Out to [{key}], back to [{home}].",
            " ".join([f"{home}{key}"] * 3 + [f"{key}{home}{key}"]),
        ),
    ]


def take_turns_prompt(a: str, b: str) -> str:
    return " ".join([a + b, a + b, b + a, b + a, a + a + b, b + b + a])


def mix_prompt(new_keys: list[str], known_keys: list[str], rng, groups: int = 6) -> str:
    """Short pseudo-words, about half new keys and half keys already known."""
    known = [k for k in known_keys if k not in new_keys and k != " "]
    words = []
    for _ in range(groups):
        length = rng.choice((3, 4))
        words.append(
            "".join(rng.choice(new_keys if not known or rng.random() < 0.5 else known) for _ in range(length))
        )
    return " ".join(words)
