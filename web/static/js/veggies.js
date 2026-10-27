// Pixel art for the garden (app/garden.py), drawn in code like sprites.js:
// each veggie kind is one tiny shape. On a plant it shows pale green while
// it's a baby and its real colors once ripe; on its own (the basket, the
// pantry, toasts) it's drawn bigger with an outline.
//
// drawPlant(px, x, y, spot, frame) draws one garden spot (empty soil or a
// plant with its 5 veggies); drawVeggie(px, x, y, kind, scale) one veggie.
// drawWateringCan(px, x, y, tilt) the can that waters after practice.
//
// Needs sprites.js (INK) loaded first.

const VEGGIE_SHAPES = {
  carrot: { rows: ["g.g", "ooo", "ooo", ".o."], colors: { g: "#6b8e3a", o: "#e8822b" } },
  tomato: { rows: [".g.", "rrr", "rrr", ".r."], colors: { g: "#4a7f2a", r: "#d8283a" } },
  pepper: { rows: [".g.", "yyy", "yyy", "yy."], colors: { g: "#4a7f2a", y: "#f0a020" } },
  zucchini: { rows: ["...g", "..zz", ".zz.", "zz.."], colors: { g: "#9fd07a", z: "#1f4a1c" } },
  corn: { rows: ["gyg", "gyg", "gyg", ".y."], colors: { g: "#7fbf4a", y: "#f6d465" } },
  pumpkin: { rows: [".s.", "ppp", "ppp"], colors: { s: "#5c3a1a", p: "#e8822b" } },
  peas: { rows: ["lll", "glg", "lll"], colors: { l: "#9fd07a", g: "#4a7f2a" } },
  radish: { rows: [".g.", "rrr", "rrr", ".w."], colors: { g: "#6b8e3a", r: "#d6457a", w: "#fbf1dc" } },
  eggplant: { rows: [".g.", "ppp", "ppp", ".p."], colors: { g: "#6b8e3a", p: "#6a3c8a" } },
  broccoli: { rows: ["bbb", "bbb", ".s."], colors: { b: "#1f5a3a", s: "#9fd07a" } },
};

const BABY_GREEN = "#d4eca0";
const BABY_OUTLINE = "#2f5a1a";
const SOIL = "#6b4423";
const SOIL_LIGHT = "#8b5a2b";
const LEAF = "#5e8f34";
const LEAF_DARK = "#3f6b24";

const PLANT_W = 20;
const PLANT_H = 20;

// The bush: a leafy mound the veggies hang on.
const BUSH_ROWS = [
  ".......oooooo.......",
  ".....ooLLLLLLoo.....",
  "....oLLLlLLLLLLo....",
  "...oLLlLLLLLlLLLo...",
  "..oLLLLLLLlLLLLLLo..",
  ".oLLlLLLLLLLLLlLLLo.",
  ".oLLLLLlLLLLLLLLLLo.",
  "oLLLLLLLLLLLlLLLLLLo",
  "oLLlLLLLLLLLLLLLlLLo",
  "oLLLLLLLlLLLLLLLLLLo",
  ".oLLLLLLLLLLLLLLLLo.",
  ".oLLLLlLLLLLLlLLLLo.",
  "..ooLLLLLLLLLLLLoo..",
  "....ooooLLLLoooo....",
  "........oLLo........",
];

// Where each of a plant's 5 veggies hangs (top-left of its outline).
const FRUIT_SPOTS = [
  [2, 2],
  [13, 1],
  [7, 5],
  [1, 8],
  [14, 8],
];

// One veggie shape at (x, y), `scale` pixels per dot, with a 1-pixel
// outline around it (`outline` color) so it stands out from the leaves.
function drawShape(px, x, y, shape, colorOf, outline = INK, scale = 1) {
  const filled = (dx, dy) => (shape.rows[dy] || "")[dx] !== undefined && shape.rows[dy][dx] !== ".";
  shape.rows.forEach((row, dy) =>
    [...row].forEach((c, dx) => {
      if (c === ".") return;
      const left = x + 1 + dx * scale;
      const top = y + 1 + dy * scale;
      if (!filled(dx - 1, dy)) px(left - 1, top, 1, scale, outline);
      if (!filled(dx + 1, dy)) px(left + scale, top, 1, scale, outline);
      if (!filled(dx, dy - 1)) px(left, top - 1, scale, 1, outline);
      if (!filled(dx, dy + 1)) px(left, top + scale, scale, 1, outline);
    })
  );
  shape.rows.forEach((row, dy) =>
    [...row].forEach((c, dx) => c !== "." && px(x + 1 + dx * scale, y + 1 + dy * scale, scale, scale, colorOf(c)))
  );
}

// The soil every spot sits on; `tilled` shows furrows (an empty spot).
function drawSoil(px, x, y, tilled) {
  px(x + 1, y + 15, PLANT_W - 2, 1, INK);
  px(x, y + 16, PLANT_W, 3, INK);
  px(x + 1, y + 16, PLANT_W - 2, 3, SOIL);
  px(x + 2, y + 16, PLANT_W - 4, 1, SOIL_LIGHT);
  px(x + 1, y + 19, PLANT_W - 2, 1, INK);
  if (tilled) {
    for (let i = 3; i < PLANT_W - 3; i += 4) px(x + i, y + 17, 2, 1, "#4a2e17");
  }
}

// One garden spot: `spot` is a /api/garden spot (or null for empty soil).
function drawPlant(px, x, y, spot, frame = 0) {
  if (!spot) {
    drawSoil(px, x, y, true);
    // a little hole waiting for a seed, bobbing
    px(x + 9, y + 15 - (frame % 2), 2, 1, "#4a2e17");
    return;
  }
  drawSoil(px, x, y, false);
  const sway = frame % 4 === 0 ? 1 : 0;
  BUSH_ROWS.forEach((row, dy) =>
    [...row].forEach((c, dx) => {
      if (c === ".") return;
      const color = c === "o" ? INK : c === "l" ? LEAF_DARK : LEAF;
      px(x + dx + (dy < 6 ? sway : 0), y + dy + 1, 1, 1, color);
    })
  );
  const shape = VEGGIE_SHAPES[spot.kind];
  const ripe = spot.picked + spot.ready;
  FRUIT_SPOTS.forEach(([fx, fy], i) => {
    if (i < spot.picked) return; // already picked
    const isRipe = i < ripe;
    const colorOf = (c) => (isRipe ? shape.colors[c] : BABY_GREEN);
    drawShape(px, x + fx + (fy < 6 ? sway : 0), y + fy + 1, shape, colorOf, isRipe ? INK : BABY_OUTLINE);
    // ripe ones twinkle so they say "pick me"
    if (isRipe && (frame + i) % 5 === 0) px(x + fx + 1, y + fy + 2, 1, 1, "#ffffff");
  });
}

// A single veggie, `scale` pixels per dot, with an ink outline.
function drawVeggie(px, x, y, kind, scale = 2) {
  const shape = VEGGIE_SHAPES[kind];
  drawShape(px, x, y, shape, (c) => shape.colors[c], INK, scale);
}

function veggieSize(kind, scale = 2) {
  const rows = VEGGIE_SHAPES[kind].rows;
  return { w: rows[0].length * scale + 2, h: rows.length * scale + 2 };
}

// The watering can, spout to the left; `tilt` 0..2 pours more.
const CAN_ROWS = [
  "......oooo....",
  ".....o....o...",
  "oo...o....o...",
  "oso.oooooooo..",
  ".oso.bBBBBBBo.",
  "..osobBBBBBBBo",
  "...oobBBBBBBBo",
  "....obBBBBBBBo",
  "....obbbbbbbbo",
  ".....oooooooo.",
];

function drawWateringCan(px, x, y, tilt = 0) {
  const rows = CAN_ROWS;
  const colors = { o: INK, s: "#7a8fa0", b: "#4f7fa8", B: "#6fa0c8" };
  rows.forEach((row, dy) =>
    [...row].forEach((c, dx) => {
      if (c === ".") return;
      // lean the spout end down as it tilts
      const lean = Math.round(((rows[0].length - dx) / rows[0].length) * tilt * 2);
      px(x + dx, y + dy + lean, 1, 1, colors[c]);
    })
  );
}

// Fits a drawing of `w` x `h` dots onto `canvas` at a whole-pixel scale and
// returns its px(x, y, w, h, color) function (cleared, centered).
function veggieCanvas(canvas, w, h) {
  const cw = Math.round(canvas.clientWidth) || canvas.width;
  const ch = Math.round(canvas.clientHeight) || canvas.height;
  if (canvas.width !== cw || canvas.height !== ch) {
    canvas.width = cw;
    canvas.height = ch;
  }
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, cw, ch);
  const scale = Math.max(1, Math.floor(Math.min(cw / w, ch / h)));
  const ox = Math.floor((cw - w * scale) / 2);
  const oy = Math.floor((ch - h * scale) / 2);
  return (x, y, pw, ph, color) => {
    ctx.fillStyle = color;
    ctx.fillRect(ox + x * scale, oy + y * scale, pw * scale, ph * scale);
  };
}

function drawVeggieIcon(canvas, kind) {
  const { w, h } = veggieSize(kind);
  drawVeggie(veggieCanvas(canvas, w, h), 0, 0, kind);
}
