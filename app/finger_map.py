"""Standard touch-typing finger assignment for every key in
skill_model.KEY_ORDER (US QWERTY). Used to aggregate per-key stats up
to per-finger stats for the analysis page and recommender -- this is a
pure lookup table, not something that needs its own DB storage; finger
stats are always derived from the already-persisted key_stat rows.
"""

from __future__ import annotations

KEY_TO_FINGER: dict[str, str] = {
    # home row
    "a": "left_pinky", "s": "left_ring", "d": "left_middle", "f": "left_index",
    "j": "right_index", "k": "right_middle", "l": "right_ring", ";": "right_pinky",
    "g": "left_index", "h": "right_index",
    # top row
    "q": "left_pinky", "w": "left_ring", "e": "left_middle", "r": "left_index",
    "t": "left_index", "y": "right_index", "u": "right_index", "i": "right_middle",
    "o": "right_ring", "p": "right_pinky",
    # bottom row
    "z": "left_pinky", "x": "left_ring", "c": "left_middle", "v": "left_index",
    "b": "left_index", "n": "right_index", "m": "right_index", ",": "right_middle",
    ".": "right_ring", "/": "right_pinky",
    # number row
    "1": "left_pinky", "2": "left_ring", "3": "left_middle", "4": "left_index",
    "5": "left_index", "6": "right_index", "7": "right_index", "8": "right_middle",
    "9": "right_ring", "0": "right_pinky",
}

ALL_FINGERS: tuple[str, ...] = (
    "left_pinky", "left_ring", "left_middle", "left_index",
    "right_index", "right_middle", "right_ring", "right_pinky",
)

# Home row, left to right -- each of these 8 keys is exactly the key
# its own finger rests on.
HOME_ROW_KEYS: tuple[str, ...] = ("a", "s", "d", "f", "j", "k", "l", ";")

# Derived from KEY_TO_FINGER + HOME_ROW_KEYS rather than listed again by
# hand, so it can't drift out of sync with the finger assignments above.
HOME_KEY_FOR_FINGER: dict[str, str] = {KEY_TO_FINGER[key]: key for key in HOME_ROW_KEYS}


def finger_for_key(key: str) -> str | None:
    return KEY_TO_FINGER.get(key)
