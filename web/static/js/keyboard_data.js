// Shared keyboard/finger reference data for the front-end -- used by
// both analysis.js (keyboard heatmap, finger bars) and teach_keyboard.js
// (the hand/keyboard diagram). Previously each page hardcoded its own
// copy; this is the one JS source of truth, mirroring the backend's
// app/finger_map.py (necessarily a separate copy across the language
// boundary, but no longer duplicated between pages on this side of it).

const KEYBOARD_ROWS = [
  ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";"],
  ["z", "x", "c", "v", "b", "n", "m", ",", ".", "/"],
  [" "],
];

const KEY_TO_FINGER = {
  a: "left_pinky", q: "left_pinky", z: "left_pinky", "1": "left_pinky",
  s: "left_ring", w: "left_ring", x: "left_ring", "2": "left_ring",
  d: "left_middle", e: "left_middle", c: "left_middle", "3": "left_middle",
  f: "left_index", g: "left_index", r: "left_index", t: "left_index", v: "left_index", b: "left_index", "4": "left_index", "5": "left_index",
  j: "right_index", h: "right_index", y: "right_index", u: "right_index", n: "right_index", m: "right_index", "6": "right_index", "7": "right_index",
  k: "right_middle", i: "right_middle", ",": "right_middle", "8": "right_middle",
  l: "right_ring", o: "right_ring", ".": "right_ring", "9": "right_ring",
  ";": "right_pinky", p: "right_pinky", "/": "right_pinky", "0": "right_pinky",
};

const HOME_KEY_FOR_FINGER = {
  left_pinky: "a", left_ring: "s", left_middle: "d", left_index: "f",
  right_index: "j", right_middle: "k", right_ring: "l", right_pinky: ";",
};

const FINGER_LABELS = {
  left_pinky: "Left pinky",
  left_ring: "Left ring",
  left_middle: "Left middle",
  left_index: "Left index",
  right_index: "Right index",
  right_middle: "Right middle",
  right_ring: "Right ring",
  right_pinky: "Right pinky",
  thumb: "Thumbs (space)",
};
const FINGER_ORDER = Object.keys(FINGER_LABELS);
