// The everyday ("Outdoors") habitats past the first four (PLAN.md 11j):
// Farmyard, Backyard, Beach, Desert, Jungle, Snowy Tundra, Autumn Orchard,
// Pond & Marsh, Savanna. Each look draws on the 160x90 grid and describes
// its terrain for pet_motion.js; shared helpers are in habitats.js.

// --- Farmyard -----------------------------------------------------------------------

function drawFarmyardHabitat(r) {
  drawHabitatSky(r, 0, 44);
  drawHabitatCloud(r, 70, 6);
  drawHabitatHills(r, 34, 44, 3, "#8fb85a", 1);
  r(6, 14, 40, 32, "#a8362a"); // the barn
  for (let k = 0; k < 10; k++) r(6 + (9 - k) * 2, 4 + k, 40 - (9 - k) * 4, 1, k % 2 ? "#8e2a20" : "#7a2418"); // the gable roof
  r(18, 28, 16, 18, "#fbf1dc");
  r(19, 29, 14, 17, "#6e2a1a");
  for (let k = 0; k < 14; k++) {
    r(19 + k, 29 + k * 1.2, 1, 1, "#fbf1dc");
    r(32 - k, 29 + k * 1.2, 1, 1, "#fbf1dc");
  }
  r(22, 16, 8, 6, "#fbf1dc");
  r(23, 17, 6, 4, "#3b2417");
  drawHabitatGround(r, 44, "#8aa846", ["#7a9440", "#a0b85a", "#c8a85a"], 4);
  for (let x = 50; x < HABITAT_W; x += 10) r(x, 38, 2, 8, "#8b5a2b"); // fence
  r(48, 40, HABITAT_W - 48, 1, "#a87a44");
  r(48, 43, HABITAT_W - 48, 1, "#a87a44");
  for (const fx of [132, 140, 148]) {
    r(fx, 26, 1, 14, "#4a7a2e"); // sunflowers
    drawHabitatDisc(r, fx + 0.5, 26, 3, 3, "#f4c430");
    drawHabitatDisc(r, fx + 0.5, 26, 1.5, 1.5, "#6e4420");
  }
  // hay bales, stacked: pets climb them
  for (const [hx, hy] of [[98, 60], [108, 60], [103, 54]]) {
    r(hx, hy, 10, 6, "#e8c84a");
    r(hx, hy + 2, 10, 1, "#c8a030");
    r(hx, hy, 10, 1, "#f4d870");
  }
  // the water trough
  r(56, 66, 20, 6, "#8b5a2b");
  r(57, 66, 18, 2, "#4a8ab0");
  // a mud puddle
  drawHabitatDisc(r, 30, 80, 9, 3, "#6e4a2a");
  drawHabitatDisc(r, 29, 79, 6, 1.5, "#8b5a2b");
}

// --- Backyard -----------------------------------------------------------------------

function drawBackyardHabitat(r) {
  drawHabitatSky(r, 0, 40);
  r(0, 8, 56, 36, "#e8d3a8"); // the house
  for (let y = 10; y < 44; y += 3) r(0, y, 56, 1, "#d8c090");
  r(-2, 4, 60, 5, "#8e3418");
  drawHabitatWindow(r, 8, 16, 14, 12, "#bfe6f0", "#fbf1dc");
  r(34, 20, 12, 24, "#6e4a2a");
  r(43, 32, 1, 1, "#e8b33e");
  drawHabitatGround(r, 44, "#7fa346", ["#6d9440", "#94c25c"], 6);
  for (let x = 58; x < HABITAT_W; x += 5) {
    r(x, 36, 3, 9, "#fbf1dc"); // a picket fence
    r(x + 1, 35, 1, 1, "#fbf1dc");
  }
  r(58, 39, HABITAT_W - 58, 1, "#e0d8c8");
  drawHabitatTree(r, 140, 64, 18, 12);
  r(132, 46, 0.6, 14, "#5c3a1a"); // the tree swing
  r(140, 46, 0.6, 14, "#5c3a1a");
  r(131, 60, 10, 1.5, "#8b5a2b");
  // the doghouse
  r(18, 58, 18, 12, "#b8432f");
  for (let k = 0; k < 6; k++) r(16 + (5 - k) * 1.5, 52 + k, 22 - (5 - k) * 3, 1, "#5c3a1a");
  r(24, 63, 6, 7, "#2a1a10");
  // flower beds, a sandbox, a ball
  r(64, 46, 40, 4, "#6e4a2a");
  [[68, 45, "#e86a8a"], [76, 45, "#f4d35e"], [84, 45, "#9a7ae0"], [92, 45, "#e86a8a"], [100, 45, "#fbf1dc"]].forEach(([x, y, c]) =>
    drawHabitatFlower(r, x, y, c)
  );
  r(84, 76, 24, 9, "#8b5a2b");
  r(85, 77, 22, 7, "#e8d4a0");
  drawHabitatDisc(r, 58, 72, 2.5, 2.5, "#d8483a");
  r(56.5, 71, 1, 1, "#fbf1dc");
}

// --- Beach --------------------------------------------------------------------------

function drawBeachHabitat(r) {
  drawHabitatSky(r, 0, 34, "#d4f0f8", "#9ed8ee");
  drawHabitatCloud(r, 30, 8);
  drawHabitatCloud(r, 110, 4);
  r(0, 30, HABITAT_W, 18, "#3a8ab8"); // the sea
  for (let x = 0; x < HABITAT_W; x += 9) r(x + ((x / 9) % 2) * 3, 34 + ((x / 9) % 3) * 3, 4, 0.7, "#8cc4dc");
  r(0, 46, HABITAT_W, 6, "#6ab0d0"); // shallow water
  for (let x = 0; x < HABITAT_W; x++) r(x, 51 + Math.round(Math.sin(x / 6)), 1, 1, "#fbf1dc"); // foam
  r(0, 53, HABITAT_W, 6, "#d8c08a"); // wet sand
  drawHabitatGround(r, 58, "#ecd8a8", ["#d8c08a", "#f4e4c0", "#c8b080"], 8);
  // the palm tree
  for (let k = 0; k < 30; k++) r(14 + k * 0.25, 74 - k, 2.5, 1, k % 3 ? "#8b5a2b" : "#6e4420");
  for (const [dx, dy] of [[-10, 2], [-6, -2], [4, -2], [9, 2], [0, -4]]) {
    for (let k = 0; k < 8; k++) r(21 + (dx * k) / 8, 44 + (dy * k) / 8 + (k * k) / 12, 2, 1, "#3a8a3a");
  }
  // a sandcastle
  r(64, 68, 16, 8, "#d8b070");
  r(66, 62, 4, 6, "#d8b070");
  r(74, 62, 4, 6, "#d8b070");
  r(66, 61, 1, 1, "#d8b070");
  r(69, 61, 1, 1, "#d8b070");
  r(70, 54, 0.6, 8, "#5c3a1a");
  r(70.6, 54, 3, 2, "#d8483a");
  // the umbrella and towel
  r(120, 54, 0.8, 20, "#fbf1dc");
  for (let k = 0; k < 5; k++) r(110 + k * 2, 50 + k, 21 - k * 4, 1, k % 2 ? "#fbf1dc" : "#d8483a");
  r(112, 74, 18, 7, "#3a7ab8");
  for (let i = 0; i < 18; i += 4) r(112 + i, 74, 2, 7, "#fbf1dc");
  // a tide pool and shells
  drawHabitatDisc(r, 40, 82, 7, 2.5, "#6ab0d0");
  r(98, 84, 2, 1, "#f6aacb");
  r(140, 66, 2, 1, "#fbf1dc");
  r(150, 80, 6, 3, "#9a948a");
  r(151, 79, 4, 1, "#b8b2a6");
}

// --- Desert -------------------------------------------------------------------------

function drawCactus(r, x, y, h) {
  r(x, y - h, 3, h, "#4a8a4a");
  r(x, y - h, 1, h, "#5aa05a");
  r(x - 3, y - h * 0.6, 3, 2, "#4a8a4a");
  r(x - 3, y - h * 0.6 - 4, 2, 4, "#4a8a4a");
  r(x + 3, y - h * 0.45, 3, 2, "#4a8a4a");
  r(x + 4, y - h * 0.45 - 5, 2, 5, "#4a8a4a");
}

function drawDesertHabitat(r) {
  for (let y = 0; y < 44; y++) r(0, y, HABITAT_W, 1, y < 14 ? "#f8d8a0" : y < 28 ? "#f4c890" : "#f0b880"); // a warm sky
  drawHabitatDisc(r, 128, 14, 6, 6, "#fbeeb0");
  r(10, 22, 30, 22, "#c8743a"); // mesas
  r(8, 20, 34, 3, "#d8844a");
  r(58, 28, 20, 16, "#b8643a");
  r(56, 26, 24, 3, "#c8743a");
  drawHabitatHills(r, 40, 48, 3, "#e8b870", 2);
  drawHabitatGround(r, 46, "#ecc890", ["#d8b070", "#f4dcaa", "#c8a060"], 11);
  for (let x = 0; x < HABITAT_W; x += 23) r(x, 60 + ((x / 23) % 3) * 8, 14, 1, "#d8b070"); // dune ripples
  drawCactus(r, 30, 74, 18);
  drawCactus(r, 142, 66, 14);
  // the flat sun-baked rock (pets climb up)
  r(98, 56, 32, 8, "#b86a3a");
  r(98, 56, 32, 2, "#d8844a");
  r(100, 60, 4, 1, "#8e4a2a");
  // a little oasis
  drawHabitatDisc(r, 66, 80, 10, 3, "#4a9ac0");
  drawHabitatDisc(r, 65, 79, 6, 1.5, "#7ec4dc");
  r(54, 78, 1, 4, "#4a8a4a");
  r(78, 77, 1, 5, "#4a8a4a");
}

// --- Jungle -------------------------------------------------------------------------

function drawJungleLeaf(r, x, y, w, color) {
  for (let k = 0; k < w; k++) r(x + k, y - Math.sin((k / w) * Math.PI) * 2, 1, 3 - Math.abs(k - w / 2) / (w / 2), color);
}

function drawJungleHabitat(r) {
  r(0, 0, HABITAT_W, 52, "#5a9a4a");
  const rand = habitatSeeded(13);
  for (let i = 0; i < 60; i++) drawJungleLeaf(r, rand() * HABITAT_W, rand() * 48, 6 + rand() * 6, ["#3a7a3a", "#2e6a32", "#4a8a3a"][i % 3]);
  for (const [vx, len] of [[12, 30], [40, 22], [64, 34], [100, 26], [128, 18]]) {
    r(vx, 0, 1, len, "#2e5a28"); // vines
    for (let k = 3; k < len; k += 4) r(vx + (k % 8 ? 1 : -2), k, 2, 1.5, "#4a9a3a");
  }
  // the waterfall into a pool
  r(126, 6, 16, 52, "#7a7468");
  r(130, 6, 8, 54, "#8cc4dc");
  for (let y = 8; y < 58; y += 4) r(131 + (y % 8) / 2, y, 1, 2, "#e0f2f6");
  drawHabitatGround(r, 52, "#4e6a2a", ["#5e7a34", "#3e5a22", "#6e4a2a"], 14);
  drawHabitatWater(r, 116, 58, 40, 12, "#3a8aa0", "#8cc4dc");
  r(114, 57, 44, 1, "#6e6458");
  // the fallen tree over the mud
  drawHabitatDisc(r, 40, 76, 16, 3, "#5e3e1e");
  r(18, 64, 46, 6, "#6e4a2a");
  r(18, 64, 46, 2, "#8b5a2b");
  r(16, 64, 3, 6, "#d8b070");
  // bright flowers
  for (const [fx, fy, c] of [[80, 60, "#e8483a"], [92, 82, "#f4a24a"], [104, 66, "#e86ab8"], [8, 84, "#f4d35e"]]) {
    drawHabitatDisc(r, fx, fy, 2, 1.5, c);
    r(fx - 0.5, fy - 0.5, 1, 1, "#f4d35e");
  }
}

// --- Snowy Tundra -------------------------------------------------------------------

function drawSnowyPine(r, x, y, size) {
  drawHabitatPine(r, x, y, size);
  for (let i = 1; i < size; i += 2) r(x - i / 2, y + i * 2, Math.max(1, i / 2), 0.8, "#f4f8fa");
}

function drawTundraHabitat(r) {
  drawHabitatSky(r, 0, 42, "#eef4f8", "#d4e4ee");
  drawHabitatHills(r, 30, 46, 4, "#e4eef4", 0.5);
  drawHabitatHills(r, 38, 50, 3, "#f0f6f8", 2);
  for (const [px, py, sz] of [[10, 26, 8], [24, 30, 6], [118, 24, 9], [150, 30, 6]]) drawSnowyPine(r, px, py, sz);
  drawHabitatGround(r, 48, "#f4f8fa", ["#dce8f0", "#e8f0f4", "#ffffff"], 15, 90);
  // a snow mound to climb
  drawHabitatDisc(r, 42, 66, 14, 6, "#e4eef4");
  drawHabitatDisc(r, 41, 64, 11, 4, "#ffffff");
  // the igloo
  drawHabitatDisc(r, 120, 64, 13, 10, "#e8f0f6");
  for (let k = 56; k < 64; k += 3) r(108, k, 24, 0.6, "#c8d8e4");
  r(108, 64, 25, 2, "#f4f8fa");
  drawHabitatDisc(r, 120, 62, 4, 4, "#5a6a7a");
  r(116, 62, 8, 4, "#5a6a7a");
  // the frozen pond
  drawHabitatDisc(r, 80, 80, 18, 4, "#a8d0e4");
  r(68, 79, 10, 0.6, "#e0f2f6");
  r(86, 81, 6, 0.6, "#e0f2f6");
}

// --- Autumn Orchard -----------------------------------------------------------------

function drawOrchardHabitat(r) {
  drawHabitatSky(r, 0, 40, "#f4e4c8", "#e8d0b0");
  drawHabitatHills(r, 32, 46, 4, "#c8a050", 1.5);
  drawHabitatGround(r, 46, "#a89a48", ["#c8582a", "#e8a03a", "#8a7a38", "#a8402a"], 17, 110);
  for (const [tx, ty] of [[14, 52], [52, 50], [96, 52], [140, 50]]) {
    drawHabitatTree(r, tx, ty, 12, 11, "#d8782a", "#b8582a");
    for (let k = 0; k < 6; k++) drawHabitatDisc(r, tx - 7 + ((k * 5) % 14), ty - 18 + ((k * 3) % 8), 1, 1, "#c8282a"); // apples
  }
  // leaf piles to jump in
  for (const [lx, ly] of [[30, 74], [118, 80]]) {
    drawHabitatDisc(r, lx, ly, 9, 3.5, "#c8582a");
    drawHabitatDisc(r, lx - 1, ly - 1, 6, 2, "#e8a03a");
  }
  // pumpkins
  for (const [px, py] of [[72, 82], [80, 84], [150, 70]]) {
    drawHabitatDisc(r, px, py, 3.5, 2.5, "#e8822a");
    r(px - 0.5, py - 3.5, 1, 1.5, "#4a7a2e");
  }
  // the cider barrel
  r(64, 58, 12, 10, "#8b5a2b");
  r(64, 58, 12, 1, "#a87a44");
  r(64, 61, 12, 1, "#5c3a1a");
  r(64, 65, 12, 1, "#5c3a1a");
}

// --- Pond & Marsh -------------------------------------------------------------------

function drawPondHabitat(r) {
  drawHabitatSky(r, 0, 38);
  drawHabitatCloud(r, 90, 6);
  drawHabitatHills(r, 30, 42, 3, "#8fb85a", 0.8);
  drawHabitatGround(r, 42, "#6e9440", ["#5e8436", "#7fa346", "#6e4a2a"], 19);
  drawHabitatDisc(r, 82, 66, 46, 13, "#c8b080"); // the pond and its muddy edge
  drawHabitatDisc(r, 82, 66, 44, 11.5, "#3a7a90");
  for (const [lx, ly] of [[60, 62], [72, 72], [100, 60], [110, 70], [86, 76]]) {
    drawHabitatDisc(r, lx, ly, 3, 1.5, "#4a8a3a"); // lily pads
    r(lx + 1, ly - 1, 1, 1, "#3a7a90");
  }
  drawHabitatDisc(r, 72, 71, 1, 1, "#f6aacb");
  for (let x = 4; x < 36; x += 3) {
    r(x, 46 + (x % 5), 1, 12, "#5a8a3a"); // reeds
    if (x % 2) r(x - 0.5, 44 + (x % 5), 2, 3, "#6e4420");
  }
  for (let x = 132; x < 158; x += 3) r(x, 48 + (x % 4), 1, 14, "#5a8a3a");
  // a little dock out over the water
  r(96, 64, 30, 5, "#a87a44");
  for (let k = 96; k < 126; k += 3) r(k, 64, 1, 5, "#8b5a2b");
  r(97, 69, 1.5, 5, "#5c3a1a");
  r(122, 69, 1.5, 5, "#5c3a1a");
  // dragonflies
  r(50, 50, 3, 0.6, "#4ab0c8");
  r(51, 49.5, 1, 1.5, "#a8e0f0");
  r(140, 40, 3, 0.6, "#4ab0c8");
}

// --- Savanna ------------------------------------------------------------------------

function drawSavannaHabitat(r) {
  for (let y = 0; y < 46; y++) r(0, y, HABITAT_W, 1, y < 16 ? "#f8e4b0" : y < 32 ? "#f4d8a0" : "#ecc890");
  drawHabitatDisc(r, 116, 24, 9, 9, "#f8c870");
  drawHabitatHills(r, 40, 50, 2, "#c8a850", 3);
  drawHabitatGround(r, 48, "#d8b858", ["#c8a040", "#e8cc70", "#b8902e"], 23, 120);
  for (let x = 0; x < HABITAT_W; x += 4) r(x, 48 + ((x * 7) % 40), 1, 2, "#b8902e"); // tall grass
  // the acacia: its flat crown is a branch pets climb
  r(40, 34, 3, 34, "#6e4a2a");
  r(36, 40, 5, 1.5, "#6e4a2a");
  r(42, 38, 8, 1.5, "#6e4a2a");
  r(24, 28, 40, 6, "#5a7a2e");
  r(28, 26, 32, 3, "#6a8a3a");
  r(26, 34, 36, 2, "#4a6a26");
  // the watering hole
  drawHabitatDisc(r, 104, 78, 22, 6, "#8a7048");
  drawHabitatDisc(r, 104, 78, 20, 5, "#5a8ab0");
  // a big boulder
  drawHabitatDisc(r, 140, 62, 13, 7, "#a89a88");
  drawHabitatDisc(r, 138, 59, 9, 3, "#c0b4a0");
}

Object.assign(HABITAT_LOOKS, {
  farmyard: {
    name: "Farmyard",
    draw: drawFarmyardHabitat,
    groundTop: 50,
    groundBottom: 88,
    props: [
      { id: "trough", x: 66, y: 74 },
      { id: "mud", x: 30, y: 82, action: "dig", color: "#6e4a2a" },
      { id: "sunflowers", x: 140, y: 50 },
      { id: "top bale", x: 108, y: 54, action: "bask", ledge: 1 },
    ],
    terrain: {
      ledges: [
        { x0: 98, x1: 118, y: 60 },
        { x0: 103, x1: 113, y: 54 },
      ],
      blocks: [
        { x: 97, y: 60, w: 22, h: 6 },
        { x: 55, y: 66, w: 22, h: 6 },
      ],
    },
  },
  backyard: {
    name: "Backyard",
    draw: drawBackyardHabitat,
    groundTop: 52,
    groundBottom: 88,
    props: [
      { id: "doghouse", x: 27, y: 71, action: "nap" },
      { id: "sandbox", x: 96, y: 82, action: "dig", color: "#e8d4a0" },
      { id: "ball", x: 58, y: 74, action: "jump", color: "#d8483a" },
      { id: "swing", x: 136, y: 66 },
    ],
    terrain: {
      ledges: [{ x0: 18, x1: 36, y: 57 }],
      blocks: [
        { x: 17, y: 58, w: 20, h: 12 },
        { x: 137, y: 58, w: 6, h: 6 },
      ],
    },
  },
  beach: {
    name: "Beach",
    draw: drawBeachHabitat,
    groundTop: 48,
    groundBottom: 88,
    props: [
      { id: "towel", x: 121, y: 79, action: "nap" },
      { id: "sand", x: 90, y: 72, action: "dig", color: "#ecd8a8" },
      { id: "sandcastle", x: 72, y: 78 },
      { id: "rock", x: 153, y: 84, action: "bask" },
    ],
    terrain: {
      water: [
        { x: 0, y: 46, w: 160, h: 7, color: "#6ab0d0" },
        { x: 33, y: 80, w: 14, h: 4, color: "#6ab0d0" },
      ],
      blocks: [
        { x: 63, y: 68, w: 18, h: 8 },
        { x: 13, y: 70, w: 8, h: 5 },
      ],
    },
  },
  desert: {
    name: "Desert",
    draw: drawDesertHabitat,
    groundTop: 50,
    groundBottom: 88,
    props: [
      { id: "hot rock", x: 114, y: 56, action: "bask", ledge: 0 },
      { id: "sand", x: 30, y: 84, action: "dig", color: "#ecc890" },
      { id: "cactus", x: 142, y: 70 },
    ],
    terrain: {
      water: [{ x: 57, y: 77, w: 18, h: 5, color: "#4a9ac0" }],
      ledges: [{ x0: 98, x1: 130, y: 56 }],
      blocks: [
        { x: 97, y: 56, w: 34, h: 8 },
        { x: 26, y: 66, w: 10, h: 8 },
        { x: 138, y: 60, w: 10, h: 6 },
      ],
    },
  },
  jungle: {
    name: "Jungle",
    draw: drawJungleHabitat,
    groundTop: 56,
    groundBottom: 88,
    props: [
      { id: "mud", x: 40, y: 80, action: "dig", color: "#5e3e1e" },
      { id: "flowers", x: 92, y: 84 },
      { id: "sunny log", x: 40, y: 64, action: "bask", ledge: 0 },
    ],
    terrain: {
      water: [{ x: 116, y: 58, w: 40, h: 12, color: "#3a8aa0" }],
      ledges: [{ x0: 19, x1: 63, y: 64 }],
      blocks: [{ x: 17, y: 64, w: 48, h: 6 }],
    },
  },
  tundra: {
    name: "Snowy Tundra",
    draw: drawTundraHabitat,
    groundTop: 54,
    groundBottom: 88,
    props: [
      { id: "igloo", x: 120, y: 68, action: "nap" },
      { id: "snowdrift", x: 22, y: 82, action: "dig", color: "#ffffff" },
      { id: "ice", x: 80, y: 82 },
    ],
    terrain: {
      ledges: [{ x0: 31, x1: 53, y: 61 }],
      blocks: [
        { x: 28, y: 61, w: 28, h: 10 },
        { x: 107, y: 55, w: 26, h: 10 },
      ],
    },
  },
  orchard: {
    name: "Autumn Orchard",
    draw: drawOrchardHabitat,
    groundTop: 54,
    groundBottom: 88,
    props: [
      { id: "leaves", x: 30, y: 76, action: "jump", color: "#e8a03a" },
      { id: "more leaves", x: 118, y: 82, action: "jump", color: "#c8582a" },
      { id: "pumpkins", x: 76, y: 86 },
      { id: "barrel top", x: 70, y: 58, action: "bask", ledge: 0 },
    ],
    terrain: {
      ledges: [{ x0: 64, x1: 76, y: 58 }],
      blocks: [{ x: 63, y: 58, w: 14, h: 10 }],
    },
  },
  pond: {
    name: "Pond & Marsh",
    draw: drawPondHabitat,
    groundTop: 48,
    groundBottom: 88,
    props: [
      { id: "dock end", x: 120, y: 64, action: "bask", ledge: 0 },
      { id: "mud", x: 140, y: 84, action: "dig", color: "#6e4a2a" },
      { id: "reeds", x: 20, y: 60 },
    ],
    terrain: {
      water: [
        { x: 42, y: 57, w: 80, h: 18, color: "#3a7a90" },
        { x: 52, y: 54, w: 60, h: 24, color: "#3a7a90" },
      ],
      ledges: [{ x0: 96, x1: 126, y: 64 }],
    },
  },
  savanna: {
    name: "Savanna",
    draw: drawSavannaHabitat,
    groundTop: 54,
    groundBottom: 88,
    props: [
      { id: "branch", x: 44, y: 28, action: "nap", ledge: 0 },
      { id: "boulder", x: 140, y: 56, action: "bask", ledge: 1 },
      { id: "grass", x: 70, y: 70 },
    ],
    terrain: {
      water: [{ x: 86, y: 73, w: 36, h: 10, color: "#5a8ab0" }],
      ledges: [
        { x0: 26, x1: 62, y: 28 },
        { x0: 130, x1: 150, y: 56 },
      ],
      blocks: [
        { x: 39, y: 54, w: 5, h: 14 },
        { x: 127, y: 56, w: 26, h: 12 },
      ],
    },
  },
});
