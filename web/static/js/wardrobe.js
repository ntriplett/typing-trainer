// Wardrobe sprites (PLAN.md 11c-2, phase 3): hats, accessories, and
// recolorable clothing styles. Original placeholder art.
//
// Recolorable styles are drawn once using palette keys a (main) and A
// (shadow); spriteFor("shirt_tee_blue") fills them from CLOTH_COLORS.
// Clothing rows line up with sprites.js's body grid (a layer starting at
// body row N sits at y = BODY_Y + N); held accessories sit at the
// character's left hand (canvas ~x 13, y 33), clear of pets on the right.
//
// Needs sprites.js loaded first.

// Keyed by app/catalog.py's COLORS: [main, shadow].
const CLOTH_COLORS = {
  red: ["#c8423a", "#962a24"],
  orange: ["#e07a2e", "#a85a1e"],
  yellow: ["#e8c03a", "#b8922a"],
  green: ["#5a9a45", "#3f7030"],
  blue: ["#4a7ec8", "#335a96"],
  navy: ["#34477a", "#232f56"],
  purple: ["#8a55c4", "#623a96"],
  pink: ["#e87aa8", "#c0507e"],
  brown: ["#8a5a2c", "#5e3c1c"],
  black: ["#3a3640", "#24212a"],
  white: ["#f4f0e8", "#cfc8bc"],
  tan: ["#c8a874", "#a0844f"],
  gray: ["#9a9aa4", "#74747e"],
};

const W = "#f4f0e8"; // white trim
const GOLD = "#e8b33e";

Object.assign(STYLE_SPRITES, {
  // --- shirts (body rows 20-27; dresses run to row 31) ---
  shirt_tee: {
    x: BODY_X,
    y: SHIRT_Y,
    palette: { o: INK, b: W },
    rows: sym(
      ".....oooaaaA",
      "...ooaaaaaaa",
      "..oaoaaaaaaa",
      "..oAoaaaaaab",
      "..oooaaaaaaa",
      ".....Aaaaaaa",
      ".....Aaaaaaa",
      ".....AAAAAAA"
    ),
  },
  shirt_hoodie: {
    x: BODY_X,
    y: SHIRT_Y,
    palette: { o: INK, b: W },
    rows: sym(
      ".....oAAAAaa",
      "...ooaaaaaba",
      "..oaoaaaaaba",
      "..oaoaaaaaaa",
      "..oaoaaAAAAA",
      "..oaoaaAaaaa",
      "..oAoAaAaaaa",
      ".....AAAAAAA"
    ),
  },
  shirt_flannel: {
    x: BODY_X,
    y: SHIRT_Y,
    palette: { o: INK, b: "#2a2420", w: W },
    rows: sym(
      ".....oooabaa",
      "...ooaabaaba",
      "..oboaabaabw",
      "..obobbbbbbb",
      "..oaoaabaaba",
      "..oaoaabaabw",
      "..oAoaabaaba",
      ".....AAAAAAA"
    ),
  },
  shirt_dress: {
    x: BODY_X,
    y: SHIRT_Y,
    palette: { o: INK, b: W },
    rows: sym(
      ".....oooaaaa",
      "...ooaaaaaaa",
      "..oaoaaaaaaa",
      "..oooaaaaaaa",
      ".....Aaaaaaa",
      ".....bbbbbbb",
      ".....oaaaaaa",
      "....oaaaaaaa",
      "....oaaaaaaa",
      "...oaaaaaaaa",
      "...oaAaaAaaa",
      "...ooooooooo"
    ),
  },

  // --- pants (body rows 28-33) ---
  pants_trousers: {
    x: BODY_X,
    y: PANTS_Y,
    palette: { o: INK },
    rows: sym(".....oaaaaaa", ".....oaaaaaa", ".....oaaaaAo", ".....oaaaao.", ".....oaaaao.", ".....oAAAAo."),
  },
  pants_jeans: {
    x: BODY_X,
    y: PANTS_Y,
    palette: { o: INK, b: "#b8cce8" },
    rows: sym(".....oaaaaaa", ".....oaaaaaa", ".....oaaaaAo", ".....oaaaAo.", ".....oaaaAo.", ".....obbbbo."),
  },
  pants_shorts: {
    x: BODY_X,
    y: PANTS_Y,
    palette: { o: INK },
    rows: sym(".....oaaaaaa", ".....oaaaaaa", ".....oAAAAAo"),
  },
  pants_skirt: {
    x: BODY_X,
    y: PANTS_Y,
    palette: { o: INK },
    rows: sym(".....oaaaaaa", "....oaaaaaaa", "....oaAaaAaa", "...ooooooooo"),
  },

  // --- shoes (body rows 34-37; rain boots start higher) ---
  shoes_boots: {
    x: BODY_X,
    y: SHOES_Y,
    palette: { o: INK },
    rows: sym(".....oAAAAo.", "....oaaaaao.", "....oaaaaao.", "....ooooooo."),
  },
  shoes_sneakers: {
    x: BODY_X,
    y: SHOES_Y,
    palette: { o: INK, w: W },
    rows: sym(".....oaaaao.", "....oaaaaao.", "....owwwwwo.", "....ooooooo."),
  },
  shoes_rainboots: {
    x: BODY_X,
    y: BODY_Y + 31,
    palette: { o: INK, b: W },
    rows: sym(".....oaaaao.", ".....oaaaao.", ".....obbbbo.", ".....oaaaao.", "....oaaaaao.", "....oAAAAAo.", "....ooooooo."),
  },
  shoes_sandals: {
    x: BODY_X,
    y: BODY_Y + 35,
    palette: { o: INK },
    rows: sym("....oa.a.ao.", "....o.....o.", "....oAAAAAo."),
  },

  // --- recolorable accessories ---
  accessory_scarf: {
    x: BODY_X,
    y: BODY_Y + 19,
    palette: { o: INK, b: W },
    rows: [
      ...sym("......oaaaaa", ".....oaAabaa"),
      "..............oaao......",
      "..............oaAo......",
      "..............obao......",
      "..............obbo......",
      "...............bb.......",
    ],
  },
  accessory_mittens: {
    x: BODY_X,
    y: BODY_Y + 26,
    palette: { o: INK },
    rows: sym("..oao.......", ".oaao.......", "..oo........"),
  },
  accessory_umbrella: {
    // a dome held over the left shoulder; shaft down to the hand
    draw(px) {
      const [a, A] = this.colors;
      const rows = [[9, 6], [6, 12], [4, 16], [3, 18], [2, 20]]; // [x, width] per row, top down
      rows.forEach(([x, w], i) => {
        px(x - 1, 2 + i, w + 2, 1, INK);
        px(x, 2 + i, w, 1, i % 2 ? A : a);
      });
      px(1, 7, 22, 1, INK);
      for (const x of [2, 8, 14, 20]) px(x, 6, 2, 1, A); // scalloped edge
      px(12, 0, 1, 2, INK); // tip
      px(12, 8, 1, 25, INK); // shaft
      px(12, 33, 2, 1, INK);
    },
  },

  // --- recolorable hats ---
  hat_beanie: {
    x: 14,
    y: 3,
    palette: { o: INK, b: W },
    rows: sym("........bb", ".....ooooo", "...ooaaaaa", "..oaaAaaAa", ".oaaaaaaaa", ".oAAAAAAAA", ".oAAAAAAAA", ".ooooooooo"),
  },
  hat_cap: {
    x: 13,
    y: 4,
    palette: { o: INK, b: W },
    rows: sym(".......oooo", ".....ooaaaa", "....oaaaaaa", "...oaaaaaab", "..oaaaaaaaa", ".oAAAAAAAAA", "ooooooooooo"),
  },
});

Object.assign(SPRITES, {
  // --- one-off hats ---
  hat_flower: {
    x: 15,
    y: 7,
    palette: { p: "#f4f0e8", y: GOLD, o: INK },
    rows: [".pp.", "pyyp", ".pp."],
  },
  hat_bunny: {
    x: 16,
    y: 0,
    palette: { o: INK, w: "#f4f0e8", p: "#f6aacb" },
    rows: sym("..oo....", ".owwo...", ".owpo...", ".owpo...", ".owpo...", ".owwo...", "oooooooo"),
  },
  hat_chef: {
    x: 15,
    y: 0,
    palette: { o: INK, w: "#f4f0e8", W: "#d8d4cc" },
    rows: sym("..oooo.oo", ".owwwwoww", "owwwwwwww", "owwWwwwww", "owwwwwwww", ".oWWWWWWW", ".owwwwwww", ".oooooooo"),
  },
  hat_cowboy: {
    x: 10,
    y: 3,
    palette: { o: INK, a: "#a0703a", A: "#7a5228", b: "#4a301c" },
    rows: sym(
      ".........ooooo",
      "........oaaaaa",
      "........oaaAaa",
      "........obbbbb",
      "oo......oaaaaa",
      "oaoooooooaaaaa",
      ".oaaaaaaaaaaaa",
      "..oooooooooooo"
    ),
  },
  hat_snorkel: {
    x: 14,
    y: 16,
    palette: { o: INK, b: "#e8507a", v: "rgba(140, 210, 255, 0.45)" },
    rows: sym(".ooooooooo", "obvvvvvvvo", "obvvvvvvvo", "obvvvvvvvo", ".ooooooooo"),
  },
  hat_headphones: {
    x: 12,
    y: 4,
    palette: { o: INK, a: "#3a3640", A: "#e8507a", b: "#f4f0e8" },
    rows: sym(
      "......oooooo",
      "....ooaaaaaa",
      "...oao......",
      "..oao.......",
      "..oao.......",
      "..oao.......",
      "..oao.......",
      "..oao.......",
      "ooAAo.......",
      "oAAAo.......",
      "oAbAo.......",
      "oAAAo.......",
      "ooAAo.......",
      ".ooo........"
    ),
  },
  hat_pirate: {
    x: 12,
    y: 2,
    palette: { o: INK, a: "#2a2630", w: "#f4f0e8", y: GOLD },
    rows: sym("....oooooooo", "..ooaaaaaaaa", ".oaaaaaaaaaw", "oaaaaaaaaaww", "oaaaaaaaaaaa", "oyyyyyyyyyyy", ".ooooooooooo"),
  },
  hat_wizard: {
    x: 12,
    y: 0,
    palette: { o: INK, a: "#5a3a96", A: "#3e2870", b: "#f6d465" },
    rows: sym(
      "...........o",
      "..........oa",
      ".........oaa",
      "........oaaa",
      "........oaba",
      ".......oaaaa",
      ".......oaaaa",
      "......oaaaba",
      "......oaaaaa",
      ".....oAAAAAA",
      "oooooaaaaaaa",
      ".ooooooooooo"
    ),
  },
  hat_top: {
    x: 15,
    y: 0,
    palette: { o: INK, a: "#2a2630", r: "#c8423a" },
    rows: sym("..ooooooo", "..oaaaaaa", "..oaaaaaa", "..oaaaaaa", "..orrrrrr", "..oaaaaaa", "oaaaaaaaa", ".oooooooo"),
  },
  hat_astronaut: {
    x: 11,
    y: 3,
    palette: { o: INK, a: "#f4f0e8", A: "#cfc8bc", v: "rgba(120, 200, 255, 0.35)" },
    rows: sym(
      "........ooooo",
      "......ooaaaaa",
      ".....oaaaaaaa",
      "....oaaaaaaaa",
      "...oaaAoooooo",
      ...Array(14).fill("..oaaaovvvvvv"),
      "..oaaaaoooooo",
      "..oAAAAAAAAAA",
      "...ooooooooo."
    ),
  },
  hat_crown: {
    x: 15,
    y: 1,
    palette: { o: INK, y: GOLD, Y: "#b5862a", r: "#c8423a", b: "#4a7ec8" },
    rows: sym("o....o...", "oo..oyo..", "oyooyyyoo", "oyyyyyyyy", "oyrryybyy", "oYYYYYYYY", "ooooooooo"),
  },

  // --- one-off accessories ---
  accessory_necklace: {
    x: BODY_X,
    y: BODY_Y + 20,
    palette: { b: GOLD, B: "#c8423a" },
    rows: sym(".......b....", "........bbbb", "...........B"),
  },
  accessory_ball: {
    x: 5,
    y: 39,
    palette: { o: INK, a: "#c8423a", w: "#f4f0e8", b: "#4a7ec8" },
    rows: [".oooo.", "oaawao", "oaaaao", "obbbbo", ".oooo."],
  },
  accessory_flowers: {
    x: 10,
    y: 28,
    palette: { r: "#e8507a", y: GOLD, p: "#c08ae6", g: "#5a9a45", o: INK },
    rows: [".r.y..", "rryyp.", ".rpp..", "..gg..", "..gg..", "..gg..", "...gg."],
  },
  accessory_book: {
    x: 8,
    y: 30,
    palette: { o: INK, a: "#4a7ec8", w: "#f4f0e8", y: GOLD },
    rows: ["oooooo", "oaaaao", "oayyao", "oaaaao", "oaaaao", "owwwwo", "oooooo"],
  },
  accessory_lantern: {
    x: 9,
    y: 33,
    palette: { o: INK, y: "#f6d465", Y: "#e8a63a" },
    rows: ["..oo..", ".o..o.", "oooooo", "oyyyyo", "oyYYyo", "oyyyyo", "oooooo"],
  },
  accessory_watering_can: {
    x: 2,
    y: 29,
    palette: { o: INK, a: "#5a9a45", A: "#3f7030" },
    rows: ["....oooo....", "...o....o...", "o..oooooooo.", "oo.oaaaaaaoo", ".oooaaaaaao.", "..ooaAaaaao.", "...oaaaaaao.", "...oooooooo."],
  },
  accessory_portal_gun: {
    x: 2,
    y: 31,
    palette: { o: INK, a: "#e8ecf0", A: "#a8acb4", b: "#6fe0f0", w: "#f2a65a" },
    rows: ["......oooo..", ".oooooawwao.", "obbboaaaaaoo", ".oooooaAAo..", ".....oAo....", ".....oo....."],
  },
  accessory_fishing_rod: {
    draw(px) {
      for (let i = 0; i < 22; i++) px(13 - Math.floor(i / 2), 33 - i, 1, 1, "#7a5228"); // pole up-left
      px(2, 12, 1, 18, "#e8ecf0"); // line
      px(1, 30, 3, 3, "#c8423a"); // bobber
      px(1, 31, 3, 1, "#f4f0e8");
      px(12, 31, 3, 3, INK); // reel
    },
  },
  accessory_net: {
    draw(px) {
      for (let i = 0; i < 16; i++) px(13 - Math.floor(i / 2), 33 - i, 1, 1, "#a0703a"); // handle
      px(1, 9, 10, 1, INK); // hoop
      px(1, 9, 1, 8, INK);
      px(10, 9, 1, 8, INK);
      px(2, 10, 8, 7, "rgba(244, 240, 232, 0.6)"); // mesh
      px(2, 17, 8, 1, INK);
    },
  },
});

// Dev guard: every recolorable grid style, drawn in a sample color.
checkSprites(
  Object.fromEntries(
    Object.keys(STYLE_SPRITES)
      .filter((k) => !STYLE_SPRITES[k].draw)
      .map((k) => [k, spriteFor(`${k}_red`)])
  )
);

// Ids in `ids` that have nothing to draw (the e2e suite checks the
// whole store catalog with this).
function missingSprites(ids) {
  return ids.filter((id) => !spriteFor(id));
}
