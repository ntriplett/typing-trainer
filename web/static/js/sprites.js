// Pixel-art sprites for the avatar and store items (PLAN.md Section 11c).
// Placeholder art drawn in code until real art (open-licensed or
// AI-made) replaces it. Keyed by the same ids as app/store.py's CATALOG.
//
// Every sprite lives on a shared 32x32 avatar canvas. A grid sprite is
// {x, y, palette, rows}: each character in `rows` is one pixel, looked up
// in `palette` ("." is transparent). A background is {draw(px)} instead,
// since a full scene is easier to describe as shapes than as a grid.
//
// Layers are separate on purpose (see avatar.js): future games redraw the
// same dressed avatar in other poses, one layer at a time.

const AVATAR_SIZE = 32;

const INK = "#3b2417"; // shared dark-brown outline

// --- bodies -------------------------------------------------------------------
// One shared 16x25 grid; the starter bodies differ only in palette.
// h/H hair, s skin, c cheeks, e eyes, m mouth, t/T default tunic,
// p pants, b boots.

const BODY_ROWS = [
  "....oooooooo....",
  "...ohhhhhhhho...",
  "..ohhhhhhhhhho..",
  "..ohhhhhhhhhho..",
  ".ohhhHssssHhhho.",
  ".ohhHssssssHhho.",
  ".ohHsessssesHho.",
  ".ohHsessssesHho.",
  ".ohHcssssssCHho.",
  "..ossssmmsssso..",
  "...osssssssso...",
  "....oossssoo....",
  "..otttttttttto..",
  ".otttttttttttto.",
  ".ottTttttttTtto.",
  ".ottTttttttTtto.",
  ".ottTttttttTtto.",
  ".ossTttttttTsso.",
  "..ooTTTTTTTToo..",
  "....oppppppo....",
  "....oppppppo....",
  "....oppooppo....",
  "....obboobbo....",
  "...obbboobbbo...",
  "...oooooooooo...",
];

function bodyPalette(hair, hairShadow, skin) {
  return {
    o: INK,
    h: hair,
    H: hairShadow,
    s: skin,
    c: "#e8907a",
    C: "#e8907a",
    e: INK,
    m: "#9a3b2b",
    t: "#f4ead2",
    T: "#d8c7a0",
    p: "#6b4a2e",
    b: "#4a301c",
  };
}

const BODY_X = 8;
const BODY_Y = 5;

// --- shirts (drawn over the body's torso rows; "." lets hands show) ------------

const SHIRT_Y = BODY_Y + 12;

// --- the sprite table ---------------------------------------------------------

const SPRITES = {
  body_sprout: { x: BODY_X, y: BODY_Y, rows: BODY_ROWS, palette: bodyPalette("#8a5a2c", "#5e3c1c", "#f2c79b") },
  body_ember: { x: BODY_X, y: BODY_Y, rows: BODY_ROWS, palette: bodyPalette("#c4502a", "#8e3418", "#f5d6b4") },
  body_moss: { x: BODY_X, y: BODY_Y, rows: BODY_ROWS, palette: bodyPalette("#2e2016", "#1a120c", "#a86b45") },

  shirt_sweater: {
    x: BODY_X,
    y: SHIRT_Y,
    palette: { o: INK, q: "#d9822b", Q: "#a85e1a", w: "#f4ead2" },
    rows: [
      "..oqqqqqqqqqqo..",
      ".oqqqqqqqqqqqqo.",
      ".oqqQqqqqqqQqqo.",
      ".oQwQwQwQwQwQQo.",
      ".oqqQqqqqqqQqqo.",
      ".o..QqqqqqqQ..o.",
      "..ooQQQQQQQQoo..",
    ],
  },
  shirt_overalls: {
    x: BODY_X,
    y: SHIRT_Y,
    palette: { o: INK, d: "#4f7fa8", D: "#355a7a", y: "#e8b33e" },
    rows: [
      "....d......d....",
      "....d......d....",
      "....dddddddd....",
      "....dddyyddd....",
      "....dddddddd....",
      "....dddddddd....",
      "..ooDDDDDDDDoo..",
      "....oddddddo....",
      "....oddddddo....",
      "....oddooddo....",
    ],
  },

  hat_straw: {
    x: 7,
    y: 3,
    palette: { o: INK, y: "#e8c25a", Y: "#c99b35", r: "#b8432f" },
    rows: [
      "......oooooo......",
      ".....oyyyyyyo.....",
      ".....oyYyyYyo.....",
      ".....orrrrrro.....",
      "ooyyyyyyyyyyyyyyoo",
      ".oooooooooooooooo.",
    ],
  },
  hat_acorn: {
    x: 10,
    y: 1,
    palette: { o: INK, n: "#5c3a1a", a: "#a0703a", A: "#6b4220" },
    rows: [
      ".....oo.....",
      ".....on.....",
      "...oooooo...",
      ".oaAaAaAaAo.",
      "oaAaAaAaAaAo",
      "oaaaaaaaaaao",
      ".oooooooooo.",
    ],
  },
  hat_leaf_crown: {
    x: 9,
    y: 3,
    palette: { R: "#b8432f", G: "#e8b33e", O: "#d9822b", n: "#5c3a1a" },
    rows: [
      "..R..G..O..R..",
      ".RRRGGGOOORRR.",
      "nnnnnnnnnnnnnn",
    ],
  },

  pet_hedgehog: {
    x: 22,
    y: 23,
    palette: { n: INK, b: "#7a5636", B: "#4a301c", f: "#e8c79a", e: INK },
    rows: [
      "..nBnBn..",
      ".nBbBbBn.",
      "nBbBbBffn",
      "nbBbBbfef",
      "nBbBbBffn",
      ".nnnnnnn.",
      "..n...n..",
    ],
  },
  pet_fox: {
    x: 20,
    y: 22,
    palette: { n: INK, O: "#d9682b", W: "#fbf1dc", e: INK, k: INK },
    rows: [
      "........n.n.",
      ".......nOnOn",
      ".......nOOOn",
      "n......nOeOk",
      "nW.nnnnOWWWn",
      "nWnOOOOOOnn.",
      ".nOOOOOOOn..",
      "..nOnnnOn...",
    ],
  },

  bg_meadow: { draw: drawMeadow },
  bg_autumn_forest: { draw: drawAutumnForest },
  bg_beach: { draw: drawBeach },
};

// --- backgrounds --------------------------------------------------------------
// `px(x, y, w, h, color)` fills a block of avatar pixels.

function drawMeadow(px) {
  px(0, 0, 32, 32, "#a8d5e2"); // sky
  px(0, 0, 32, 4, "#c4e3ec");
  px(3, 3, 4, 4, "#f6d465"); // sun
  px(2, 4, 6, 2, "#f6d465");
  px(4, 2, 2, 6, "#f6d465");
  px(20, 5, 6, 2, "#ffffff"); // cloud
  px(22, 4, 3, 1, "#ffffff");
  px(0, 17, 32, 6, "#9cbf63"); // far hill
  px(4, 15, 10, 2, "#9cbf63");
  px(20, 16, 9, 1, "#9cbf63");
  px(0, 23, 32, 9, "#6b8e3a"); // grass
  px(0, 23, 32, 1, "#7fa346");
  for (const [x, y, c] of [[2, 26, "#f4ead2"], [6, 29, "#e8b33e"], [28, 25, "#f4ead2"], [25, 30, "#e8907a"], [14, 30, "#e8b33e"]]) {
    px(x, y, 1, 1, c);
  }
}

function drawAutumnForest(px) {
  px(0, 0, 32, 32, "#f2c48d"); // warm sky
  px(0, 0, 32, 5, "#f6d4a6");
  for (const [x, crown] of [[1, "#b8432f"], [11, "#e8b33e"], [24, "#d9822b"]]) {
    px(x + 2, 10, 2, 14, "#5c3a1a"); // trunk
    px(x, 4, 6, 7, crown); // canopy
    px(x - 1, 6, 8, 3, crown);
    px(x + 1, 4, 2, 1, "#fbe3a8"); // highlight
  }
  px(0, 23, 32, 9, "#8a6a3a"); // leafy ground
  px(0, 23, 32, 1, "#a07a42");
  for (const [x, y, c] of [[3, 26, "#b8432f"], [9, 29, "#e8b33e"], [18, 27, "#d9822b"], [27, 30, "#b8432f"], [22, 25, "#e8b33e"], [13, 25, "#d9822b"]]) {
    px(x, y, 2, 1, c);
  }
}

function drawBeach(px) {
  px(0, 0, 32, 32, "#9fd3e8"); // sky
  px(24, 3, 4, 4, "#f6d465"); // sun
  px(0, 14, 32, 7, "#4fa3c7"); // sea
  px(0, 14, 32, 1, "#7cc0dc");
  px(3, 17, 4, 1, "#ffffff"); // foam
  px(15, 19, 5, 1, "#ffffff");
  px(25, 16, 4, 1, "#ffffff");
  px(0, 21, 32, 11, "#f0d79c"); // sand
  px(0, 21, 32, 1, "#fbf1dc");
  for (const [x, y, c] of [[4, 27, "#e8907a"], [12, 30, "#fbf1dc"], [27, 26, "#d9822b"]]) {
    px(x, y, 2, 1, c);
  }
}
