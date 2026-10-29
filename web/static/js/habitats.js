// Habitat looks (PLAN.md 11i), shared by the Pet Shop, the Trailhead, and
// the habitat view. Each look draws itself on a 160x90 grid through a
// painter r(x, y, w, h, color), and lists its props: things curious pets
// walk over to look at (pet_motion.js). Pets' feet stay between groundTop
// and groundBottom. New looks (mountain, ...) go in HABITAT_LOOKS.

const HABITAT_W = 160;
const HABITAT_H = 90;

function habitatPainter(ctx, px) {
  return (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x * px), Math.round(y * px), Math.ceil(w * px), Math.ceil(h * px));
  };
}

// --- shared bits -------------------------------------------------------------------

function habitatSeeded(n) {
  let a = n * 9301 + 49297;
  return () => {
    a = (a * 9301 + 49297) % 233280;
    return a / 233280;
  };
}

function drawHabitatSky(r, top, bottom, light = "#c4e3ec", sky = "#a8d5e2") {
  r(0, top, HABITAT_W, bottom - top, sky);
  r(0, top, HABITAT_W, Math.min(8, bottom - top), light);
}

function drawHabitatCloud(r, x, y) {
  r(x, y + 2, 16, 3, "#ffffff");
  r(x + 3, y, 9, 2, "#ffffff");
}

function drawHabitatPine(r, x, y, size, shade = 0) {
  for (let i = 0; i < size; i++) {
    const w = 1 + i;
    r(x - w / 2, y + i * 2, w, 2, (i + shade) % 2 ? "#2e5a32" : "#3a6a3a");
  }
  r(x - 0.5, y + size * 2, 1.5, 2 + size / 3, "#5c3a1a");
}

// A rocky ledge: a grassy top at `y` from x0 to x1, its face down to `base`.
function drawHabitatLedge(r, x0, x1, y, base, rock = "#8a8478", dark = "#6a645a", top = "#7fa346") {
  const rand = habitatSeeded(x0 + y);
  for (let x = x0; x < x1; x++) {
    const edge = x === x0 || x === x1 - 1 ? 1 : 0;
    r(x, y + edge, 1, base - y - edge, rand() < 0.15 ? dark : rock);
  }
  r(x0, y, x1 - x0, 2, top);
  r(x0 + 1, y - 0.5, x1 - x0 - 2, 0.5, top);
  for (let k = 0; k < (x1 - x0) / 6; k++) r(x0 + 2 + rand() * (x1 - x0 - 4), y + 3 + rand() * Math.max(1, base - y - 5), 2, 1, dark); // cracks
}

function drawHabitatDisc(r, cx, cy, rx, ry, color) {
  for (let dy = -ry; dy <= ry; dy++) {
    const half = rx * Math.sqrt(Math.max(0, 1 - (dy * dy) / (ry * ry)));
    if (half >= 0.5) r(cx - half, cy + dy, half * 2, 1, color);
  }
}

// Rolling hills along `y`, filled down to `base`.
function drawHabitatHills(r, y, base, amp, color, phase = 0) {
  for (let x = 0; x < HABITAT_W; x++) {
    const top = Math.round(y + amp * Math.sin(x / 13 + phase) + (amp / 2) * Math.sin(x / 5 + phase * 2));
    r(x, top, 1, base - top, color);
  }
}

// Ground from `top` down, with scattered specks.
function drawHabitatGround(r, top, color, specks, seed = 1, count = 70) {
  r(0, top, HABITAT_W, HABITAT_H - top, color);
  const rand = habitatSeeded(seed);
  for (let i = 0; i < count; i++) r(rand() * HABITAT_W, top + 2 + rand() * (HABITAT_H - top - 2), 1, 1, specks[i % specks.length]);
}

// A round-topped tree: trunk base at (x, y).
function drawHabitatTree(r, x, y, trunk, crown, leaf = "#4a8a4a", dark = "#3a6a3a", bark = "#6e4a2a") {
  r(x - 1.5, y - trunk, 3, trunk, bark);
  r(x - 1.5, y - trunk, 1, trunk, "#8b5a2b");
  drawHabitatDisc(r, x, y - trunk - crown * 0.4, crown, crown * 0.75, dark);
  drawHabitatDisc(r, x - 1, y - trunk - crown * 0.5, crown - 1.5, crown * 0.65, leaf);
}

function drawHabitatWater(r, x, y, w, h, color = "#4a8ab0", light = "#8cc4dc") {
  r(x, y, w, h, color);
  for (let i = 0; i < w; i += 7) r(x + i + 2, y + 1 + ((i / 7) % 3) * (h / 4), 3, 0.6, light);
}

// --- indoor rooms ---

function drawHabitatWall(r, base, color, stripe) {
  r(0, 0, HABITAT_W, base, color);
  if (stripe) for (let x = 3; x < HABITAT_W; x += 10) r(x, 0, 3, base, stripe);
  r(0, base - 5, HABITAT_W, 5, "#a87a44"); // wainscot
  r(0, base - 5, HABITAT_W, 1, "#c89a60");
}

function drawHabitatFloor(r, top, light = "#c89a60", dark = "#b0844c") {
  r(0, top, HABITAT_W, HABITAT_H - top, light);
  for (let y = top + 4; y < HABITAT_H; y += 5) r(0, y, HABITAT_W, 1, dark);
  const rand = habitatSeeded(top);
  for (let y = top; y < HABITAT_H; y += 5) for (let i = 0; i < 4; i++) r(Math.floor(rand() * HABITAT_W), y, 1, 4, dark);
}

function drawHabitatWindow(r, x, y, w, h, sky = "#bfe6f0", frame = "#8b5a2b") {
  r(x, y, w, h, frame);
  r(x + 1.5, y + 1.5, w - 3, h - 3, sky);
  r(x + w / 2 - 0.5, y + 1, 1, h - 2, frame);
  r(x + 1, y + h / 2 - 0.5, w - 2, 1, frame);
}

function drawHabitatRug(r, x, y, w, h, color, edge) {
  r(x, y, w, h, edge);
  r(x + 1.5, y + 1, w - 3, h - 2, color);
}

// --- the Meadow ---------------------------------------------------------------------

function drawHabitatFlower(r, x, y, petal, middle = "#f4d35e") {
  r(x, y + 1, 1, 3, "#4a7a2e");
  r(x - 1, y, 3, 1, petal);
  r(x, y - 1, 1, 3, petal);
  r(x, y, 1, 1, middle);
}

function drawMeadowHabitat(r) {
  r(0, 0, HABITAT_W, 40, "#a8d5e2"); // sky
  r(0, 0, HABITAT_W, 8, "#c4e3ec");
  r(130, 6, 8, 8, "#f8e08a"); // sun
  r(131, 7, 6, 6, "#fbeeb0");
  for (const [cx, cy] of [[14, 8], [62, 4], [98, 11]]) {
    r(cx, cy + 2, 16, 3, "#ffffff");
    r(cx + 3, cy, 9, 2, "#ffffff");
  }
  for (let x = 0; x < HABITAT_W; x++) {
    const far = Math.round(28 + 5 * Math.sin(x / 17 + 2) + 2 * Math.sin(x / 6)); // far hills
    r(x, far, 1, 40 - far, "#9cc46a");
    const near = Math.round(36 + 3 * Math.sin(x / 11) + Math.sin(x / 4 + 1)); // near hills
    r(x, near, 1, 44 - near, "#8fb85a");
  }
  r(0, 42, HABITAT_W, HABITAT_H - 42, "#7fa346"); // the meadow
  r(0, 42, HABITAT_W, 1, "#94c25c");
  for (let i = 0; i < 70; i++) {
    const x = (i * 37) % HABITAT_W;
    const y = 46 + ((i * 53) % 42);
    r(x, y, 1, 1, i % 3 ? "#6d9440" : "#94c25c"); // grass texture
    if (i % 2) r(x + 2, y - 1, 1, 2, "#5a7a2e");
  }
  // a fence along the back
  for (let x = 2; x < HABITAT_W; x += 12) r(x, 38, 2, 7, "#8b5a2b");
  r(0, 39, HABITAT_W, 1, "#a87a44");
  r(0, 42, HABITAT_W, 1, "#a87a44");
  // a pond
  r(118, 52, 26, 7, "#4a8ab0");
  r(116, 53, 30, 5, "#4a8ab0");
  r(120, 53, 10, 1, "#8cc4dc");
  r(115, 54, 1, 3, "#6d9440");
  // the stump
  r(20, 54, 10, 6, "#8b5a2b");
  r(20, 53, 10, 2, "#d8b070");
  r(22, 53, 6, 1, "#b88a50");
  r(19, 59, 12, 1, "#5c3a1a");
  // rocks
  r(70, 78, 8, 4, "#9a948a");
  r(71, 77, 5, 1, "#b8b2a6");
  r(78, 80, 4, 2, "#8a8478");
  // flowers
  const petals = ["#e86a8a", "#fbf1dc", "#9a7ae0", "#f4a24a", "#e86a8a", "#fbf1dc"];
  [[10, 70], [44, 58], [52, 84], [96, 66], [104, 86], [150, 74], [36, 76], [88, 50], [140, 84]].forEach(([x, y], i) =>
    drawHabitatFlower(r, x, y, petals[i % petals.length])
  );
  // a butterfly bush
  r(56, 47, 9, 5, "#5a8a3a");
  r(57, 46, 7, 1, "#6d9440");
  drawHabitatFlower(r, 58, 47, "#e86a8a");
  drawHabitatFlower(r, 62, 48, "#fbf1dc");
}


// --- the Forest -----------------------------------------------------------------------

function drawForestHabitat(r) {
  r(0, 0, HABITAT_W, 46, "#cfe0a8"); // light through the leaves
  const rand = habitatSeeded(3);
  for (let x = 0; x < HABITAT_W; x += 1) {
    const top = Math.round(10 + 6 * Math.sin(x / 9) + 3 * Math.sin(x / 3.3));
    r(x, 0, 1, top, x % 7 < 3 ? "#3a6a3a" : "#2e5a32"); // the canopy
  }
  for (const [tx, w] of [[8, 5], [26, 3], [44, 6], [70, 4], [92, 5], [108, 3], [138, 6], [152, 4]]) {
    r(tx, 8, w, 40, "#5c3a1a"); // trunks in the back
    r(tx, 8, 1, 40, "#6e4a2a");
  }
  for (let i = 0; i < 8; i++) drawHabitatPine(r, 6 + i * 21, 24 + (i % 3) * 3, 9, i);
  r(0, 44, HABITAT_W, HABITAT_H - 44, "#5e7a34"); // the forest floor
  r(0, 44, HABITAT_W, 1, "#6d9440");
  for (let i = 0; i < 90; i++) {
    const c = ["#6d9440", "#4e6a2a", "#a86a2e", "#c88a3a", "#8a5a2a"][Math.floor(rand() * 5)];
    r(rand() * HABITAT_W, 46 + rand() * 44, 1, 1, c); // leaf litter
  }
  for (const [lx, ly, lw] of [[20, 56, 14], [86, 72, 18], [120, 82, 12], [60, 50, 10]]) {
    for (let j = 0; j < 4; j++) {
      // dappled sun spots: a dithered oval
      const half = lw / 2 - Math.abs(j - 1.5) * 2;
      for (let i = -half; i < half; i += 1) if ((Math.round(i) + j) % 2 === 0) r(lx + lw / 2 + i, ly + j, 1, 1, "rgba(250, 240, 180, 0.35)");
    }
  }
  // the fallen log (pets can walk on it)
  r(30, 64, 45, 7, "#6e4a2a");
  r(30, 64, 45, 2, "#8b5a2b");
  r(30, 69, 45, 2, "#4e321a");
  r(28, 64, 4, 7, "#d8b070");
  r(29, 66, 2, 3, "#b88a50");
  r(52, 62, 2, 2, "#4a8a4a");
  // a hollow stump to curl up in
  r(118, 50, 16, 14, "#6e4a2a");
  r(118, 50, 16, 2, "#d8b070");
  r(122, 56, 8, 8, "#2a1a10");
  r(116, 63, 20, 1, "#4e321a");
  // a mushroom ring
  for (const [mx, my, c] of [[92, 80, "#d8483a"], [98, 78, "#e8b33e"], [104, 80, "#d8483a"], [97, 84, "#fbf1dc"], [90, 85, "#e8b33e"]]) {
    r(mx, my + 1, 1, 2, "#fbf1dc");
    r(mx - 1, my, 3, 1, c);
  }
  // a leaf pile to jump in
  for (let i = 0; i < 40; i++) r(40 + rand() * 18, 81 + rand() * 5 - Math.abs(i % 9 - 4) * 0.4, 1, 1, ["#c8582a", "#e8a03a", "#a8402a"][i % 3]);
}

// --- the Stream -----------------------------------------------------------------------

const STREAM_Y = (x) => 64 + 5 * Math.sin(x / 22 + 0.6); // the stream's middle at x

function drawStreamHabitat(r) {
  drawHabitatSky(r, 0, 36);
  drawHabitatCloud(r, 20, 6);
  drawHabitatCloud(r, 100, 10);
  for (let x = 0; x < HABITAT_W; x++) {
    const hill = Math.round(30 + 4 * Math.sin(x / 13 + 1) + 2 * Math.sin(x / 5));
    r(x, hill, 1, 40 - hill, "#8fb85a");
  }
  r(0, 40, HABITAT_W, HABITAT_H - 40, "#7fa346");
  const rand = habitatSeeded(9);
  for (let i = 0; i < 60; i++) r(rand() * HABITAT_W, 42 + rand() * 48, 1, 1, i % 2 ? "#6d9440" : "#94c25c");
  for (let x = 0; x < HABITAT_W; x++) {
    const mid = STREAM_Y(x);
    r(x, mid - 6, 1, 12, "#c8b080"); // muddy banks
    r(x, mid - 5, 1, 10, "#4a8ab0");
    if (x % 9 < 4) r(x, mid - 2 + Math.sin(x) * 2, 1, 0.6, "#8cc4dc"); // ripples
  }
  for (const sx of [96, 103, 110]) {
    const mid = STREAM_Y(sx); // stepping stones
    r(sx, mid - 1 + (sx % 2), 4, 2, "#9a948a");
    r(sx, mid - 1 + (sx % 2), 4, 0.6, "#b8b2a6");
  }
  // a little wooden bridge
  const bm = STREAM_Y(44);
  r(36, bm - 8, 18, 16, "#a87a44");
  for (let k = 0; k < 16; k += 3) r(36, bm - 8 + k, 18, 1, "#8b5a2b");
  r(35, bm - 9, 1, 18, "#5c3a1a");
  r(54, bm - 9, 1, 18, "#5c3a1a");
  // cattails along the banks
  for (const cx of [10, 16, 74, 80, 140, 146, 152]) {
    const top = STREAM_Y(cx) - 12;
    r(cx, top, 1, 7, "#4a7a2e");
    r(cx - 0.5, top - 2, 2, 3, "#6e4420");
  }
  // a flat sunny rock
  r(124, 80, 14, 4, "#9a948a");
  r(125, 79, 12, 1, "#b8b2a6");
  // a sandy spot to dig in
  r(14, 80, 18, 6, "#e0c890");
  r(16, 79, 14, 1, "#e8d4a0");
  [[60, 50, "#e86a8a"], [118, 50, "#fbf1dc"], [88, 84, "#9a7ae0"], [150, 82, "#f4a24a"]].forEach(([x, y, c]) => drawHabitatFlower(r, x, y, c));
}

// The stream as water rects, a short one every 8 units, for pet_motion.js.
function streamWater() {
  const out = [];
  for (let x = 0; x < HABITAT_W; x += 8) {
    const ys = [x, x + 4, x + 8].map(STREAM_Y);
    const y = Math.min(...ys) - 5;
    out.push({ x, y, w: 8, h: Math.max(...ys) + 5 - y, color: "#4a8ab0" });
  }
  return out;
}

// --- the Mountain ----------------------------------------------------------------------

const MOUNTAIN_LEDGES = [
  { x0: 4, x1: 40, y: 54 },
  { x0: 12, x1: 38, y: 42 },
  { x0: 66, x1: 92, y: 58 },
  { x0: 112, x1: 152, y: 52 },
  { x0: 122, x1: 156, y: 38 },
];

function drawMountainHabitat(r) {
  drawHabitatSky(r, 0, 50, "#d4ecf4", "#b4dcea");
  drawHabitatCloud(r, 50, 8);
  for (let x = 0; x < HABITAT_W; x++) {
    const peak = Math.round(18 + 10 * Math.abs(Math.sin(x / 26 + 0.4)) + 3 * Math.sin(x / 7));
    r(x, peak, 1, 60 - peak, "#8aa4b8"); // far peaks with snow
    r(x, peak, 1, 3, "#eef4f6");
    const near = Math.round(36 + 5 * Math.sin(x / 15 + 2));
    r(x, near, 1, 62 - near, "#7a8a78");
  }
  r(0, 60, HABITAT_W, HABITAT_H - 60, "#8aa456"); // the alpine meadow
  const rand = habitatSeeded(21);
  for (let i = 0; i < 70; i++) r(rand() * HABITAT_W, 62 + rand() * 28, 1, 1, i % 3 ? "#7a9448" : "#a8be6a");
  for (let i = 0; i < 12; i++) r(rand() * HABITAT_W, 64 + rand() * 24, 2, 1.5, "#9a948a"); // pebbles
  drawHabitatLedge(r, 12, 38, 42, 62);
  drawHabitatLedge(r, 4, 40, 54, 62);
  drawHabitatLedge(r, 122, 156, 38, 62);
  drawHabitatLedge(r, 112, 152, 52, 62);
  drawHabitatLedge(r, 66, 92, 58, 66); // a big boulder on the meadow
  // a cave in the high rock
  r(140, 26, 10, 12, "#6a645a");
  r(142, 28, 6, 10, "#2a2620");
  // a snow patch up top, alpine flowers below
  r(16, 41, 12, 1.5, "#eef4f6");
  r(18, 40.5, 8, 0.5, "#ffffff");
  [[50, 74, "#9a7ae0"], [58, 80, "#fbf1dc"], [104, 72, "#e86a8a"], [98, 84, "#9a7ae0"], [30, 82, "#f4d35e"]].forEach(([x, y, c]) =>
    drawHabitatFlower(r, x, y, c)
  );
  drawHabitatPine(r, 100, 44, 8);
  drawHabitatPine(r, 56, 46, 7, 1);
}

// --- every look ---------------------------------------------------------------------

const HABITAT_LOOKS = {
  meadow: {
    name: "Meadow",
    draw: drawMeadowHabitat,
    groundTop: 50,
    groundBottom: 88,
    props: [
      { id: "stump", x: 25, y: 61 },
      { id: "rocks", x: 75, y: 83, action: "bask" },
      { id: "bush", x: 60, y: 53 },
      { id: "flowers", x: 100, y: 68 },
    ],
    terrain: {
      water: [
        { x: 117, y: 52, w: 28, h: 7, color: "#4a8ab0" },
        { x: 115, y: 53, w: 31, h: 5, color: "#4a8ab0" },
      ],
      blocks: [{ x: 70, y: 77, w: 12, h: 5 }],
      ledges: [{ x0: 19, x1: 31, y: 53 }],
    },
  },
  forest: {
    name: "Forest",
    draw: drawForestHabitat,
    groundTop: 48,
    groundBottom: 88,
    props: [
      { id: "hollow", x: 126, y: 65, action: "nap" },
      { id: "mushrooms", x: 97, y: 86 },
      { id: "leaves", x: 49, y: 87, action: "jump", color: "#e8a03a" },
      { id: "sunspot", x: 92, y: 74, action: "bask" },
    ],
    terrain: {
      blocks: [
        { x: 29, y: 65, w: 47, h: 6 },
        { x: 117, y: 51, w: 18, h: 13 },
      ],
      ledges: [{ x0: 31, x1: 74, y: 64 }],
    },
  },
  stream: {
    name: "Stream",
    draw: drawStreamHabitat,
    groundTop: 46,
    groundBottom: 88,
    props: [
      { id: "rock", x: 131, y: 82, action: "bask" },
      { id: "sand", x: 23, y: 85, action: "dig", color: "#e0c890" },
      { id: "cattails", x: 78, y: 56 },
      { id: "flowers", x: 60, y: 52 },
    ],
    terrain: { water: streamWater(), blocks: [{ x: 123, y: 79, w: 16, h: 4 }] },
  },
  mountain: {
    name: "Mountain",
    draw: drawMountainHabitat,
    groundTop: 64,
    groundBottom: 88,
    props: [
      { id: "cave", x: 145, y: 38, action: "nap", ledge: 4 },
      { id: "snow", x: 22, y: 42, action: "dig", color: "#ffffff", ledge: 1 },
      { id: "sunny rock", x: 130, y: 52, action: "bask", ledge: 3 },
      { id: "flowers", x: 54, y: 78 },
    ],
    terrain: { ledges: MOUNTAIN_LEDGES, blocks: [{ x: 66, y: 58, w: 26, h: 8 }] },
  },
};

// The habitat's look drawn onto a new canvas at px pixels per grid unit.
function habitatBackground(kind, px) {
  const canvas = document.createElement("canvas");
  canvas.width = HABITAT_W * px;
  canvas.height = HABITAT_H * px;
  HABITAT_LOOKS[kind].draw(habitatPainter(canvas.getContext("2d"), px));
  return canvas;
}
