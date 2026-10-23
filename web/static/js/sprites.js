// Pixel-art sprites for the avatar and store items (PLAN.md Section 11c).
// Placeholder art drawn in code until real art (open-licensed or
// AI-made) replaces it. Keyed by the same ids as app/store.py's CATALOG.
//
// Every sprite lives on a shared 48x48 avatar canvas. A grid sprite is
// {x, y, palette, rows}: each character in `rows` is one pixel, looked up
// in `palette` ("." is transparent). A background is {draw(px)} instead,
// since a full scene is easier to describe as shapes than as a grid.
//
// Layers are separate on purpose (see avatar.js): future games redraw the
// same dressed avatar in other poses, one layer at a time.

const AVATAR_SIZE = 48;

const INK = "#3b2417"; // shared dark-brown outline

// Most of the character is left/right symmetric: write the left half,
// mirror it. `sym("..oh")` -> "..ohho..".
function sym(...halves) {
  return halves.map((h) => h + [...h].reverse().join(""));
}

// --- bodies -------------------------------------------------------------------
// One shared 24x38 grid in plain underclothes (u/U); shirts, pants, and
// shoes are separate layers drawn over it. The starter bodies differ only
// in palette. h/H/L hair, s/S skin, c cheeks, e/w eyes, m mouth.

const BODY_X = 12;
const BODY_Y = 6;

const BODY_ROWS = sym(
  "........oooo", //  0 hair
  "......oohhhh",
  ".....ohhhhhh",
  "....ohhhLLhh",
  "...ohhhLhhhh",
  "...ohhhhhhhh", //  5
  "..ohhhhhhhhh",
  "..ohhhhhhhHH",
  "..ohhhHsHsss", //    fringe
  "..ohhHssssss",
  "..ohHsssssss", // 10
  "..ohHsswesss", //    eyes (highlight on top)
  "..ohHsseesss",
  "..ohHsseesss",
  "..oHscccssss", //    cheeks
  "...oSssssmss", // 15 smile corners
  "....oSssssmm", //    smile
  ".....oosssss",
  ".......ooooo", //    chin
  "........osss", //    neck
  ".....ooouuuu", // 20 shoulders
  "...oouuuuuuu",
  "..osouuuuuuu", //    arms
  "..osouuuuuuu",
  "..osouuuuuuu",
  "..osoUuuuuuu", // 25
  "..osoUuuuuuu",
  ".ossoUUUUUUU", //    hands
  "..oo.ouuuuuu", //    shorts
  ".....ouuuuuu",
  ".....ouuuuuo", // 30
  ".....osssso.", //    legs
  ".....osssso.",
  ".....osssso.",
  ".....osssso.",
  "....ossssso.", // 35 feet
  "....ossssso.",
  "....ooooooo."
);

function bodyPalette(hair, hairShadow, hairLight, skin, skinShadow) {
  return {
    o: INK,
    h: hair,
    H: hairShadow,
    L: hairLight,
    s: skin,
    S: skinShadow,
    c: "#e8907a",
    e: INK,
    w: "#ffffff",
    m: "#9a3b2b",
    u: "#efe6d2",
    U: "#d3c6a8",
  };
}

// Clothing rows line up with BODY_ROWS: a layer starting at body row N
// sits at y = BODY_Y + N.
const SHIRT_Y = BODY_Y + 20;
const PANTS_Y = BODY_Y + 28;
const SHOES_Y = BODY_Y + 34;

// --- the sprite table ---------------------------------------------------------

const SPRITES = {
  body_sprout: { x: BODY_X, y: BODY_Y, rows: BODY_ROWS, palette: bodyPalette("#8a5a2c", "#5e3c1c", "#b07a43", "#f2c79b", "#d9a57a") },
  body_ember: { x: BODY_X, y: BODY_Y, rows: BODY_ROWS, palette: bodyPalette("#c4502a", "#8e3418", "#e07a4a", "#f5d6b4", "#e0b48e") },
  body_moss: { x: BODY_X, y: BODY_Y, rows: BODY_ROWS, palette: bodyPalette("#2e2016", "#1a120c", "#4a3626", "#a86b45", "#8a5434") },

  // --- shirts (body rows 20-27) ---
  shirt_tunic: {
    x: BODY_X,
    y: SHIRT_Y,
    palette: { o: INK, t: "#f4ead2", T: "#d8c7a0", b: "#8b5a2b" },
    rows: sym(
      ".....ooottTt",
      "...oottttttt",
      "..otottttttb",
      "..otottttttt",
      "..oooTtttttt",
      ".....Ttttttb",
      ".....Ttttttt",
      ".....TTTTTTT"
    ),
  },
  shirt_sweater: {
    x: BODY_X,
    y: SHIRT_Y,
    palette: { o: INK, q: "#d9822b", Q: "#a85e1a", w: "#f4ead2" },
    rows: sym(
      ".....oooqqQQ",
      "...ooqqqqqqq",
      "..oqoqqqqqqq",
      "..oqoqwqwqwq",
      "..oqoQqqqqqq",
      "..oqoQqqqqqq",
      "..oQoQqqqqqq",
      ".....QQQQQQQ"
    ),
  },
  // A full outfit: bib + straps over a cream shirt, and the legs too.
  shirt_overalls: {
    x: BODY_X,
    y: SHIRT_Y,
    palette: { o: INK, t: "#f4ead2", T: "#d8c7a0", d: "#4f7fa8", D: "#355a7a", y: "#e8b33e" },
    rows: sym(
      ".....oootdtt",
      "...ootttdttt",
      "..otottttdtt",
      "..otottddddy",
      "..oooTtddddd",
      ".....Tdddddd",
      ".....Tdddddd",
      ".....DDDDDDD",
      ".....odddddd",
      ".....odddddd",
      ".....odddddo",
      ".....oddddo.",
      ".....oddddo.",
      ".....oDDDDo."
    ),
  },

  // --- pants (body rows 28-34) ---
  pants_trousers: {
    x: BODY_X,
    y: PANTS_Y,
    palette: { o: INK, p: "#7a5636", P: "#5c3a1a" },
    rows: sym(
      ".....opppppp",
      ".....opppppp",
      ".....oppppPo",
      ".....oppppo.",
      ".....oppppo.",
      ".....oPPPPo."
    ),
  },

  // --- shoes (body rows 34-37) ---
  shoes_boots: {
    x: BODY_X,
    y: SHOES_Y,
    palette: { o: INK, b: "#4a301c", B: "#6b4a2e" },
    rows: sym(".....oBBBBo.", "....obbbbbo.", "....obbbbbo.", "....ooooooo."),
  },

  // --- hats ---
  hat_straw: {
    x: 10,
    y: 5,
    palette: { o: INK, y: "#e8c25a", Y: "#c99b35", r: "#b8432f" },
    rows: sym(
      ".........ooooo",
      "........oyyyyy",
      "........oyYyyy",
      "........oyyyyy",
      "........orrrrr",
      "..oooooooyyyyy",
      "ooyyyyyyyyyYyy",
      ".ooooooooooooo"
    ),
  },
  hat_acorn: {
    x: 13,
    y: 4,
    palette: { o: INK, n: "#5c3a1a", a: "#a0703a", A: "#6b4220" },
    rows: sym(
      ".........oo",
      ".........on",
      ".....oooooo",
      "...ooaAaAaA",
      "..oaAaAaAaA",
      ".oaAaAaAaAa",
      "oaAaAaAaAaA",
      "oaaaaaaaaaa",
      ".oooooooooo"
    ),
  },
  hat_leaf_crown: {
    x: 14,
    y: 6,
    palette: { R: "#b8432f", G: "#e8b33e", O: "#d9822b", n: "#5c3a1a" },
    rows: sym("..R...O...", ".RRR.OOO.G", "RRRRROOOOG", "nnnnnnnnnn"),
  },

  // --- pets (bottom right, in front of the character) ---
  pet_hedgehog: {
    x: 33,
    y: 36,
    palette: { n: INK, b: "#7a5636", B: "#4a301c", f: "#e8c79a", e: INK, k: INK },
    rows: [
      "....n.n.n.....",
      "...nBnBnBn....",
      "..nBbBbBbBnn..",
      ".nBbBbBbBbffn.",
      "nBbBbBbBbffefn",
      "nbBbBbBbBffffk",
      "nBbBbBbBbfffn.",
      ".nBbBbBbBnnn..",
      "..nnnnnnnn....",
      "...nf..nf.....",
    ],
  },
  pet_fox: {
    x: 29,
    y: 34,
    palette: { n: INK, O: "#d9682b", W: "#fbf1dc", e: INK, k: INK },
    rows: [
      "............n..n..",
      "...........nOnnOn.",
      "...........nOOOOOn",
      "nnn........nOOOeOO",
      "nWWn.......nOOOOOk",
      "nWOOn....nnnOOWWWn",
      ".nOOOnnnnOOOOOWWn.",
      "..nOOOOOOOOOOOWn..",
      "...nOOOOOOOOOOOn..",
      "...nOWWOOOOOOWWn..",
      "....nOn....nOn....",
      "....nkn....nkn....",
    ],
  },

  bg_meadow: { draw: drawMeadow },
  bg_autumn_forest: { draw: drawAutumnForest },
  bg_beach: { draw: drawBeach },
};

// --- backgrounds --------------------------------------------------------------
// `px(x, y, w, h, color)` fills a block of avatar pixels. The character
// stands on y ~= 43, so the ground starts a little above that.

function dots(px, list, w = 1, h = 1) {
  for (const [x, y, c] of list) px(x, y, w, h, c);
}

function drawMeadow(px) {
  px(0, 0, 48, 48, "#a8d5e2"); // sky
  px(0, 0, 48, 6, "#c4e3ec");
  px(5, 4, 6, 6, "#f6d465"); // sun
  px(3, 6, 10, 2, "#f6d465");
  px(7, 2, 2, 10, "#f6d465");
  px(30, 7, 9, 3, "#ffffff"); // cloud
  px(33, 5, 4, 2, "#ffffff");
  px(28, 9, 13, 1, "#e6f2f6");
  px(0, 25, 48, 9, "#9cbf63"); // far hill
  px(5, 22, 16, 3, "#9cbf63");
  px(30, 23, 14, 2, "#9cbf63");
  px(0, 34, 48, 14, "#6b8e3a"); // grass
  px(0, 34, 48, 1, "#7fa346");
  dots(px, [[3, 39, "#f4ead2"], [9, 44, "#e8b33e"], [42, 37, "#f4ead2"], [38, 45, "#e8907a"], [21, 45, "#e8b33e"], [15, 38, "#e8907a"]], 2, 1);
  dots(px, [[6, 36, "#5a7a2e"], [25, 37, "#5a7a2e"], [44, 41, "#5a7a2e"]], 1, 2);
}

function drawAutumnForest(px) {
  px(0, 0, 48, 48, "#f2c48d"); // warm sky
  px(0, 0, 48, 8, "#f6d4a6");
  for (const [x, crown, light] of [[1, "#b8432f", "#d9684a"], [17, "#e8b33e", "#f6d465"], [36, "#d9822b", "#efa55a"]]) {
    px(x + 4, 15, 3, 21, "#5c3a1a"); // trunk
    px(x, 6, 11, 10, crown); // canopy
    px(x - 2, 9, 15, 5, crown);
    px(x + 2, 6, 3, 2, light); // highlight
  }
  px(0, 34, 48, 14, "#8a6a3a"); // leafy ground
  px(0, 34, 48, 1, "#a07a42");
  dots(px, [[4, 39, "#b8432f"], [13, 44, "#e8b33e"], [27, 40, "#d9822b"], [41, 45, "#b8432f"], [33, 37, "#e8b33e"], [19, 37, "#d9822b"]], 3, 1);
}

function drawBeach(px) {
  px(0, 0, 48, 48, "#9fd3e8"); // sky
  px(36, 4, 6, 6, "#f6d465"); // sun
  px(0, 21, 48, 10, "#4fa3c7"); // sea
  px(0, 21, 48, 1, "#7cc0dc");
  px(4, 25, 6, 1, "#ffffff"); // foam
  px(22, 28, 8, 1, "#ffffff");
  px(37, 24, 6, 1, "#ffffff");
  px(0, 31, 48, 17, "#f0d79c"); // sand
  px(0, 31, 48, 1, "#fbf1dc");
  dots(px, [[6, 40, "#e8907a"], [18, 45, "#fbf1dc"], [40, 39, "#d9822b"]], 3, 1);
}

// Dev guard: a malformed grid is easy to make by hand, so say so loudly.
for (const [id, s] of Object.entries(SPRITES)) {
  if (!s.rows) continue;
  const widths = new Set(s.rows.map((r) => r.length));
  const unknown = [...new Set(s.rows.join(""))].filter((c) => c !== "." && !s.palette[c]);
  if (widths.size !== 1 || unknown.length) {
    console.error(`sprite ${id}: row widths ${[...widths]}, unknown palette keys ${unknown}`);
  }
  if (s.x + Math.max(...widths) > AVATAR_SIZE || s.y + s.rows.length > AVATAR_SIZE) {
    console.error(`sprite ${id} runs off the ${AVATAR_SIZE}px canvas`);
  }
}
