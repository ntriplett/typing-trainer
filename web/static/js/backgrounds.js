// Place backgrounds for the 48x48 avatar canvas (PLAN.md 11c-2): one
// draw function per place, keyed by app/catalog.py's bg_* ids. Original
// placeholder art.
//
// Each is draw(px, night): `px(x, y, w, h, color)` fills avatar pixels.
// The character stands on y ~= 43 in the middle (x 12..35) and pets sit
// bottom-right, so scenery stays mostly to the sides and the back.
// Night is applied the same way everywhere (nightOver): darken, then
// stars/moon in the sky, with a per-place extra (fireflies, glow...).
//
// Needs sprites.js loaded first (registers into SPRITES).

function dots(px, list, w = 1, h = 1) {
  for (const [x, y, c] of list) px(x, y, w, h, c);
}

const STARS = [[3, 2], [9, 7], [15, 3], [22, 1], [27, 6], [34, 2], [40, 8], [45, 3], [6, 12], [19, 10], [31, 11], [43, 14]];

// skyBottom: stars only above this row. extra(px): drawn after the dark
// overlay (fireflies, glowing windows...).
function nightOver(px, { skyBottom = 18, moon = [38, 3], shade = "rgba(16, 20, 52, 0.55)", extra } = {}) {
  px(0, 0, 48, 48, shade);
  for (const [x, y] of STARS) if (y < skyBottom) px(x, y, 1, 1, "#fff6d8");
  if (moon) {
    const [mx, my] = moon;
    px(mx, my + 1, 6, 4, "#f4ecc8");
    px(mx + 1, my, 4, 6, "#f4ecc8");
    px(mx + 3, my + 1, 2, 2, "#d8cfa8"); // crater
  }
  if (extra) extra(px);
}

const FIREFLIES = (px) => dots(px, [[5, 30, "#f6e27a"], [41, 27, "#f6e27a"], [9, 38, "#f6e27a"], [44, 35, "#f6e27a"], [27, 24, "#f6e27a"]]);

function roundTree(px, x, top, crown, light, trunk = "#5c3a1a") {
  px(x + 4, top + 9, 3, 34 - top - 9, trunk);
  px(x, top, 11, 10, crown);
  px(x - 2, top + 3, 15, 5, crown);
  px(x + 2, top, 3, 2, light);
}

function pine(px, cx, top, height, color, dark, trunk = "#4a301c") {
  for (let i = 0; i < height; i++) {
    const half = Math.floor(i / 2) + 1;
    px(cx - half, top + i, half * 2, 1, i % 4 === 3 ? dark : color);
  }
  px(cx - 1, top + height, 2, 3, trunk);
}

// --- fields & forests ---------------------------------------------------------

function drawMeadow(px, night) {
  px(0, 0, 48, 48, "#a8d5e2"); // sky
  px(0, 0, 48, 6, "#c4e3ec");
  if (!night) {
    px(5, 4, 6, 6, "#f6d465"); // sun
    px(3, 6, 10, 2, "#f6d465");
    px(7, 2, 2, 10, "#f6d465");
  }
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
  if (night) nightOver(px, { skyBottom: 22, extra: FIREFLIES });
}

function drawFlowerForest(px, night) {
  px(0, 0, 48, 48, "#b8e0d8");
  px(0, 0, 48, 5, "#d4ece6");
  roundTree(px, 1, 6, "#5f9a45", "#86c46a");
  roundTree(px, 36, 8, "#5f9a45", "#86c46a");
  dots(px, [[3, 8, "#f6aacb"], [7, 10, "#ffffff"], [10, 7, "#f6d465"], [38, 10, "#ffffff"], [42, 12, "#f6aacb"], [45, 9, "#f6d465"]], 2, 2);
  px(0, 33, 48, 15, "#7fae4a");
  px(0, 33, 48, 1, "#94c25c");
  dots(px, [[2, 37, "#f6aacb"], [8, 42, "#ffffff"], [14, 39, "#f6d465"], [20, 46, "#c08ae6"], [28, 45, "#f6aacb"], [40, 38, "#f6d465"], [45, 43, "#ffffff"], [33, 40, "#c08ae6"]], 2, 2);
  if (night) nightOver(px, { skyBottom: 8, extra: FIREFLIES });
}

function drawAutumnForest(px, night) {
  px(0, 0, 48, 48, "#f2c48d");
  px(0, 0, 48, 8, "#f6d4a6");
  for (const [x, crown, light] of [[1, "#b8432f", "#d9684a"], [17, "#e8b33e", "#f6d465"], [36, "#d9822b", "#efa55a"]]) {
    roundTree(px, x, 6, crown, light);
  }
  px(0, 34, 48, 14, "#8a6a3a");
  px(0, 34, 48, 1, "#a07a42");
  dots(px, [[4, 39, "#b8432f"], [13, 44, "#e8b33e"], [27, 40, "#d9822b"], [41, 45, "#b8432f"], [33, 37, "#e8b33e"], [19, 37, "#d9822b"]], 3, 1);
  if (night) nightOver(px, { skyBottom: 6, moon: [24, 1], extra: FIREFLIES });
}

function drawPineForest(px, night) {
  px(0, 0, 48, 48, "#cfe3e0");
  px(0, 0, 48, 6, "#e2efec");
  for (const [cx, top, h] of [[5, 8, 24], [16, 14, 18], [32, 12, 20], [43, 6, 26]]) {
    pine(px, cx, top, h, "#2f5e3a", "#244a2d");
  }
  px(0, 34, 48, 14, "#4f6b3a");
  px(0, 34, 48, 1, "#5f7e45");
  dots(px, [[6, 40, "#7a5636"], [20, 45, "#7a5636"], [39, 41, "#7a5636"], [29, 38, "#3e5a2e"]], 3, 1);
  if (night) nightOver(px, { skyBottom: 8, moon: [22, 1], extra: FIREFLIES });
}

function drawCherryGrove(px, night) {
  px(0, 0, 48, 48, "#cfe6f2");
  px(0, 0, 48, 5, "#e4f1f8");
  roundTree(px, 0, 5, "#f2a6c0", "#fbd0de", "#6b4a3a");
  roundTree(px, 37, 7, "#f2a6c0", "#fbd0de", "#6b4a3a");
  px(0, 34, 48, 14, "#9cc46a");
  px(0, 34, 48, 1, "#b0d47e");
  dots(px, [[5, 38, "#fbd0de"], [12, 44, "#f2a6c0"], [22, 40, "#fbd0de"], [30, 46, "#f2a6c0"], [41, 39, "#fbd0de"], [17, 22, "#f2a6c0"], [27, 16, "#fbd0de"], [31, 26, "#f2a6c0"]], 1, 1);
  if (night) nightOver(px, { skyBottom: 6, moon: [21, 1] });
}

function drawJungle(px, night) {
  px(0, 0, 48, 48, "#8fc49a");
  px(0, 0, 48, 10, "#a8d6ae");
  px(0, 0, 10, 48, "#3f7a3a");
  px(38, 0, 10, 48, "#3f7a3a");
  for (const x of [11, 15, 34]) px(x, 0, 1, 14 + (x % 7), "#2f6a2a"); // vines
  dots(px, [[13, 15, "#4f9a3a"], [33, 20, "#4f9a3a"], [16, 21, "#4f9a3a"]], 3, 2);
  dots(px, [[1, 6, "#5fb04a"], [4, 14, "#2f6a2a"], [40, 8, "#5fb04a"], [44, 18, "#2f6a2a"], [2, 24, "#5fb04a"], [42, 28, "#5fb04a"]], 6, 3);
  dots(px, [[6, 20, "#e8507a"], [41, 13, "#f6d465"]], 2, 2); // flowers
  px(0, 35, 48, 13, "#6b4a2e");
  px(0, 35, 48, 1, "#4f9a3a");
  dots(px, [[8, 40, "#4f9a3a"], [24, 44, "#4f9a3a"], [40, 41, "#4f9a3a"]], 4, 1);
  if (night) nightOver(px, { skyBottom: 9, moon: null, shade: "rgba(10, 30, 30, 0.6)", extra: FIREFLIES });
}

// --- water --------------------------------------------------------------------

function drawBeach(px, night) {
  px(0, 0, 48, 48, "#9fd3e8");
  if (!night) px(36, 4, 6, 6, "#f6d465"); // sun
  px(0, 21, 48, 10, "#4fa3c7"); // sea
  px(0, 21, 48, 1, "#7cc0dc");
  px(4, 25, 6, 1, "#ffffff");
  px(22, 28, 8, 1, "#ffffff");
  px(37, 24, 6, 1, "#ffffff");
  px(0, 31, 48, 17, "#f0d79c"); // sand
  px(0, 31, 48, 1, "#fbf1dc");
  dots(px, [[6, 40, "#e8907a"], [18, 45, "#fbf1dc"], [40, 39, "#d9822b"]], 3, 1);
  if (night) nightOver(px, { skyBottom: 20, moon: [8, 4], extra: (p) => dots(p, [[9, 24, "#f4ecc8"], [8, 27, "#f4ecc8"]], 4, 1) });
}

function drawRiver(px, night) {
  px(0, 0, 48, 48, "#b4dcea");
  px(0, 16, 48, 10, "#86b85a"); // far bank
  px(0, 16, 48, 1, "#9ccc6e");
  px(0, 26, 48, 8, "#5aa8d0"); // river
  dots(px, [[3, 28, "#a8dcf0"], [17, 30, "#a8dcf0"], [30, 27, "#a8dcf0"], [41, 31, "#a8dcf0"]], 5, 1);
  dots(px, [[10, 31, "#9a9a8a"], [36, 28, "#9a9a8a"]], 3, 2); // stones
  px(0, 34, 48, 14, "#6b9a3a"); // near bank
  px(0, 34, 48, 1, "#7fae4a");
  dots(px, [[4, 18, "#5f9a45"], [40, 17, "#5f9a45"]], 5, 4); // bushes
  if (night) nightOver(px, { skyBottom: 15, moon: [30, 3], extra: (p) => dots(p, [[31, 29, "#f4ecc8"]], 4, 1) });
}

function drawWaterfall(px, night) {
  px(0, 0, 48, 48, "#b8dcea");
  px(0, 4, 16, 32, "#8a8378"); // cliffs
  px(32, 4, 16, 32, "#8a8378");
  px(0, 4, 16, 2, "#6b9a3a");
  px(32, 4, 16, 2, "#6b9a3a");
  px(16, 4, 16, 28, "#7cc0dc"); // falling water
  dots(px, [[18, 6, "#e8f6fc"], [23, 10, "#e8f6fc"], [28, 7, "#e8f6fc"], [20, 16, "#e8f6fc"], [26, 20, "#e8f6fc"], [19, 25, "#e8f6fc"]], 1, 5);
  dots(px, [[4, 14, "#6f685e"], [37, 20, "#6f685e"], [9, 26, "#6f685e"]], 4, 2);
  px(0, 32, 48, 4, "#5aa8d0"); // pool
  px(14, 31, 20, 2, "#e8f6fc"); // splash
  px(0, 36, 48, 12, "#7a7468"); // rocky ground
  px(0, 36, 48, 1, "#948e80");
  dots(px, [[5, 41, "#6b9a3a"], [41, 43, "#6b9a3a"]], 4, 1);
  if (night) nightOver(px, { skyBottom: 4, moon: null });
}

function drawUnderSea(px, night) {
  px(0, 0, 48, 48, "#2f7fb0");
  px(0, 0, 48, 8, "#4fa3c7");
  px(0, 8, 48, 8, "#3f90bd");
  dots(px, [[8, 0, "rgba(255,255,255,0.15)"], [28, 0, "rgba(255,255,255,0.15)"]], 4, 30); // light rays
  for (const [x, h] of [[3, 16], [7, 11], [40, 18], [44, 12]]) {
    for (let i = 0; i < h; i++) px(x + (i % 4 < 2 ? 0 : 1), 38 - i, 1, 1, "#3f9a5a"); // seaweed
  }
  dots(px, [[2, 10, "#f2a65a"], [38, 16, "#f6d465"]], 3, 2); // fish
  dots(px, [[5, 10, "#f2a65a"], [41, 16, "#f6d465"]], 1, 1);
  px(0, 38, 48, 10, "#e0c890"); // sand
  px(0, 38, 48, 1, "#f0d79c");
  dots(px, [[9, 42, "#e8907a"], [37, 44, "#fbf1dc"], [24, 46, "#c08ae6"]], 2, 1);
  if (night) nightOver(px, { skyBottom: 0, moon: null, shade: "rgba(4, 10, 40, 0.6)", extra: (p) => dots(p, [[6, 20, "#9ae6f0"], [40, 26, "#9ae6f0"], [30, 8, "#9ae6f0"]], 2, 2) });
}

function drawSwamp(px, night) {
  px(0, 0, 48, 48, "#b8c8a0");
  px(0, 0, 48, 10, "#ccd8b6");
  px(0, 12, 48, 3, "rgba(255,255,255,0.35)"); // mist
  px(2, 4, 3, 30, "#4a3f2a"); // dead trees
  px(0, 8, 8, 2, "#4a3f2a");
  px(43, 6, 3, 28, "#4a3f2a");
  px(40, 12, 8, 2, "#4a3f2a");
  px(0, 30, 48, 6, "#4f6a4a"); // murky water
  dots(px, [[6, 32, "#6f9a4a"], [33, 31, "#6f9a4a"], [40, 34, "#6f9a4a"]], 4, 1); // lily pads
  dots(px, [[10, 25, "#6b4a2e"], [37, 24, "#6b4a2e"]], 1, 8); // cattails
  dots(px, [[10, 23, "#4a301c"], [37, 22, "#4a301c"]], 1, 3);
  px(0, 36, 48, 12, "#5a5236"); // mud
  px(0, 36, 48, 1, "#6b6340");
  if (night) nightOver(px, { skyBottom: 11, moon: [22, 2], shade: "rgba(10, 24, 20, 0.6)", extra: FIREFLIES });
}

// --- wild lands -----------------------------------------------------------------

function drawDesert(px, night) {
  px(0, 0, 48, 48, "#f4d9a0");
  px(0, 0, 48, 8, "#f8e6bc");
  if (!night) px(6, 3, 6, 6, "#fbf1dc"); // pale sun
  px(0, 22, 20, 6, "#e8b86a"); // dunes
  px(26, 20, 22, 8, "#e8b86a");
  px(4, 20, 12, 2, "#e8b86a");
  px(41, 14, 3, 20, "#5f9a45"); // cactus
  px(38, 19, 3, 2, "#5f9a45");
  px(38, 16, 2, 4, "#5f9a45");
  px(44, 22, 3, 2, "#5f9a45");
  px(45, 19, 2, 4, "#5f9a45");
  px(0, 28, 48, 20, "#e0aa58");
  px(0, 28, 48, 1, "#ecc078");
  dots(px, [[6, 36, "#c8913f"], [21, 44, "#c8913f"], [35, 39, "#c8913f"]], 4, 1);
  if (night) nightOver(px, { skyBottom: 20, moon: [30, 3] });
}

function drawBadlands(px, night) {
  px(0, 0, 48, 48, "#f2c89a");
  for (const [x, w, top] of [[0, 14, 10], [30, 18, 6]]) {
    const bands = ["#c4673a", "#e8a66a", "#a8502a", "#f0d0a0", "#c4673a", "#8e3f22"];
    bands.forEach((c, i) => px(x, top + i * 4, w, 4, c));
  }
  px(0, 34, 48, 14, "#c47a48");
  px(0, 34, 48, 1, "#d8925e");
  dots(px, [[8, 40, "#a8502a"], [22, 45, "#a8502a"], [40, 41, "#a8502a"]], 4, 1);
  px(19, 30, 2, 4, "#8a7a4a"); // dry shrub
  px(17, 32, 6, 2, "#8a7a4a");
  if (night) nightOver(px, { skyBottom: 8, moon: [18, 3] });
}

function drawTundra(px, night) {
  px(0, 0, 48, 48, "#cfe2f2");
  px(0, 0, 48, 6, "#e2eef8");
  px(0, 22, 22, 8, "#f4f8fc"); // snow hills
  px(24, 20, 24, 10, "#f4f8fc");
  pine(px, 6, 12, 18, "#3f6a5a", "#2f5248");
  pine(px, 42, 10, 20, "#3f6a5a", "#2f5248");
  dots(px, [[2, 16, "#ffffff"], [5, 20, "#ffffff"], [40, 14, "#ffffff"], [44, 22, "#ffffff"]], 3, 1); // snow on pines
  px(0, 30, 48, 18, "#ffffff");
  px(0, 30, 48, 1, "#e2eef8");
  dots(px, [[8, 38, "#cfe2f2"], [24, 44, "#cfe2f2"], [38, 36, "#cfe2f2"]], 5, 1);
  if (night) nightOver(px, { skyBottom: 18, moon: [24, 2], extra: (p) => { p(0, 4, 48, 2, "rgba(120, 240, 180, 0.35)"); p(6, 7, 36, 1, "rgba(160, 120, 240, 0.35)"); } });
}

function drawMushroomIsland(px, night) {
  px(0, 0, 48, 48, "#c8b4e0");
  px(0, 0, 48, 6, "#dccbee");
  px(5, 12, 4, 22, "#efe6d2"); // giant mushroom stalk
  px(0, 5, 14, 8, "#c8283a"); // cap
  px(2, 3, 10, 2, "#c8283a");
  dots(px, [[2, 7, "#ffffff"], [7, 5, "#ffffff"], [10, 9, "#ffffff"]], 2, 2);
  px(40, 22, 3, 12, "#efe6d2"); // small mushroom
  px(36, 18, 11, 5, "#a0703a");
  px(0, 34, 48, 14, "#8a7a9a"); // mycelium ground
  px(0, 34, 48, 1, "#a898b8");
  dots(px, [[10, 38, "#b8a8c8"], [24, 44, "#b8a8c8"], [37, 40, "#b8a8c8"]], 3, 1);
  if (night) nightOver(px, { skyBottom: 16, moon: [30, 3], extra: (p) => dots(p, [[3, 7, "#ff8a9a"], [9, 9, "#ff8a9a"], [38, 19, "#f6d465"]], 1, 1) });
}

// --- space --------------------------------------------------------------------

function drawSpace(px, night) {
  px(0, 0, 48, 48, "#1c1e3a");
  px(0, 10, 48, 8, "#2a2450"); // nebula band
  px(6, 12, 14, 4, "#3a2a60");
  dots(px, [[2, 3, "#ffffff"], [12, 6, "#f6e27a"], [20, 2, "#ffffff"], [29, 8, "#ffffff"], [37, 4, "#9ae6f0"], [44, 9, "#ffffff"], [5, 22, "#ffffff"], [43, 25, "#ffffff"], [8, 32, "#f6e27a"], [40, 36, "#ffffff"]]);
  px(36, 14, 9, 9, "#e8a66a"); // ringed planet
  px(33, 18, 15, 1, "#f0d0a0");
  px(38, 15, 3, 2, "#f2c48d");
  px(0, 38, 48, 10, "#6a6a7a"); // asteroid ground
  px(0, 38, 48, 1, "#8a8a9a");
  dots(px, [[7, 42, "#55556a"], [30, 45, "#55556a"]], 4, 2);
  if (night) nightOver(px, { skyBottom: 38, moon: null, shade: "rgba(0, 0, 10, 0.45)", extra: (p) => dots(p, [[16, 20, "#ffffff"], [26, 27, "#9ae6f0"], [3, 15, "#ffffff"]], 1, 1) });
}

function drawMoon(px, night) {
  px(0, 0, 48, 48, "#14162a");
  dots(px, [[4, 4, "#ffffff"], [14, 9, "#ffffff"], [24, 3, "#f6e27a"], [44, 11, "#ffffff"], [9, 17, "#ffffff"], [30, 14, "#ffffff"]]);
  px(36, 3, 8, 8, "#4f8ad0"); // Earth
  px(38, 4, 3, 3, "#5f9a45");
  px(40, 8, 3, 2, "#5f9a45");
  px(0, 30, 48, 18, "#b8b8bc"); // lunar ground
  px(0, 30, 48, 1, "#d0d0d4");
  dots(px, [[5, 34, "#98989c"], [39, 37, "#98989c"], [20, 44, "#98989c"]], 5, 2); // craters
  dots(px, [[5, 34, "#a8a8ac"], [39, 37, "#a8a8ac"]], 5, 1);
  if (night) nightOver(px, { skyBottom: 30, moon: null, shade: "rgba(0, 0, 10, 0.4)" });
}

function drawMars(px, night) {
  px(0, 0, 48, 48, "#e8a070");
  px(0, 0, 48, 10, "#d88a5a");
  if (!night) px(8, 5, 3, 3, "#f4d9b0"); // tiny sun
  px(0, 22, 18, 8, "#b8502a"); // hills
  px(28, 20, 20, 10, "#b8502a");
  px(0, 30, 48, 18, "#c4602e");
  px(0, 30, 48, 1, "#d8784a");
  dots(px, [[6, 36, "#8e3f22"], [19, 44, "#8e3f22"], [39, 38, "#8e3f22"], [28, 41, "#a8502a"]], 4, 2); // rocks
  if (night) nightOver(px, { skyBottom: 20, moon: [36, 3], shade: "rgba(30, 10, 30, 0.55)" });
}

Object.assign(SPRITES, {
  bg_meadow: { draw: drawMeadow },
  bg_flower_forest: { draw: drawFlowerForest },
  bg_autumn_forest: { draw: drawAutumnForest },
  bg_pine_forest: { draw: drawPineForest },
  bg_cherry_grove: { draw: drawCherryGrove },
  bg_jungle: { draw: drawJungle },
  bg_beach: { draw: drawBeach },
  bg_river: { draw: drawRiver },
  bg_waterfall: { draw: drawWaterfall },
  bg_under_sea: { draw: drawUnderSea },
  bg_swamp: { draw: drawSwamp },
  bg_desert: { draw: drawDesert },
  bg_badlands: { draw: drawBadlands },
  bg_tundra: { draw: drawTundra },
  bg_mushroom_island: { draw: drawMushroomIsland },
  bg_space: { draw: drawSpace },
  bg_moon: { draw: drawMoon },
  bg_mars: { draw: drawMars },
});
