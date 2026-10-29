// The cozy habitats (PLAN.md 11j): Cozy Cottage, Greenhouse, Treehouse
// Village, Library Nook, Playroom, Hay Loft, Attic Hideaway, Sunny Porch.
// Mostly indoors: a wall, a floor, and furniture pets climb on, nap in, and
// play in. Shared helpers are in habitats.js.

// --- Cozy Cottage --------------------------------------------------------------------

function drawCottageHabitat(r) {
  drawHabitatWall(r, 46, "#e8c8a0", "#e0bc90");
  r(0, 0, HABITAT_W, 3, "#6e4a2a"); // beams
  for (const bx of [30, 90, 150]) r(bx, 0, 3, 41, "#8b5a2b");
  drawHabitatWindow(r, 98, 10, 22, 18);
  r(96, 28, 26, 3, "#a87a44"); // the window seat
  r(97, 31, 24, 9, "#b8432f");
  // the fireplace
  r(40, 12, 34, 34, "#9a8a7a");
  for (let y = 14; y < 46; y += 4) for (let x = 40 + ((y / 4) % 2) * 3; x < 74; x += 6) r(x, y, 5, 3, "#8a7a6a");
  r(38, 10, 38, 3, "#6e4a2a");
  r(47, 28, 20, 18, "#2a1a10");
  drawHabitatDisc(r, 57, 42, 7, 4, "#e8822a");
  drawHabitatDisc(r, 57, 41, 4, 3, "#f4c430");
  r(50, 44, 14, 2, "#5c3a1a");
  drawHabitatFloor(r, 46, "#b88a50", "#a07440");
  drawHabitatRug(r, 34, 60, 46, 16, "#b8432f", "#8e2a20");
  for (let x = 38; x < 78; x += 6) r(x, 66, 3, 3, "#e8b33e");
  // the armchair
  r(126, 50, 26, 18, "#4a6aa0");
  r(126, 46, 26, 6, "#3a5a8a");
  r(124, 52, 4, 16, "#3a5a8a");
  r(150, 52, 4, 16, "#3a5a8a");
  r(128, 58, 22, 3, "#5a7ab0");
  // the cat tree
  r(12, 24, 3, 46, "#d8b070");
  r(4, 24, 18, 3, "#8b5a2b");
  r(6, 44, 16, 3, "#8b5a2b");
  r(2, 66, 24, 4, "#8b5a2b");
  // a yarn basket
  r(90, 76, 12, 6, "#a87a44");
  drawHabitatDisc(r, 94, 75, 3, 2, "#e86a8a");
  drawHabitatDisc(r, 99, 75, 2.5, 2, "#7ab0e0");
}

// --- Greenhouse ---------------------------------------------------------------------

function drawPotPlant(r, x, y, leaf = "#4a8a4a") {
  r(x - 4, y - 6, 8, 6, "#c8643a");
  r(x - 5, y - 7, 10, 2, "#d8744a");
  drawHabitatDisc(r, x, y - 11, 6, 5, leaf);
  drawHabitatDisc(r, x - 1, y - 12, 3, 2, "#6aaa5a");
}

function drawGreenhouseHabitat(r) {
  r(0, 0, HABITAT_W, 48, "#cfe8e0"); // glass and light
  for (let x = 0; x < HABITAT_W; x += 20) r(x, 0, 1.5, 48, "#e8f4f0");
  for (let y = 0; y < 48; y += 12) r(0, y, HABITAT_W, 1, "#e8f4f0");
  for (let k = 0; k < 6; k++) r(k * 30, 0, 12, 48, "rgba(255, 255, 230, 0.18)"); // sunbeams
  // shelves of seedlings (pets climb up)
  r(6, 30, 50, 3, "#8b5a2b");
  for (let x = 10; x < 54; x += 8) {
    r(x, 26, 4, 4, "#c8643a");
    r(x + 1, 23, 2, 3, "#6aaa5a");
  }
  r(8, 33, 2, 15, "#6e4a2a");
  r(52, 33, 2, 15, "#6e4a2a");
  drawHabitatFloor(r, 48, "#a8a090", "#968e80");
  // the fountain
  drawHabitatDisc(r, 82, 72, 16, 5, "#9a948a");
  drawHabitatDisc(r, 82, 71, 14, 3.5, "#6ab0d0");
  r(80, 58, 4, 12, "#9a948a");
  drawHabitatDisc(r, 82, 58, 5, 2, "#b8b2a6");
  r(81.5, 52, 1, 6, "#bfe6f0");
  // pots and a warm lamp
  drawPotPlant(r, 20, 80);
  drawPotPlant(r, 140, 64, "#3a7a3a");
  drawPotPlant(r, 150, 84);
  r(122, 0, 1, 26, "#3b2417");
  r(116, 26, 13, 4, "#5c3a1a");
  r(118, 30, 9, 1, "#f8e08a");
  for (let k = 0; k < 6; k++) r(114 - k, 31 + k * 4, 17 + k * 2, 4, "rgba(248, 224, 138, 0.06)");
  // hanging vines
  for (const vx of [40, 70, 100]) for (let k = 0; k < 14; k += 3) r(vx + (k % 2), k, 2, 2, "#4a8a4a");
}

// --- Treehouse Village ---------------------------------------------------------------

const TREEHOUSE_LEDGES = [
  { x0: 6, x1: 46, y: 36 },
  { x0: 60, x1: 100, y: 24 },
  { x0: 112, x1: 154, y: 40 },
  { x0: 46, x1: 60, y: 31 },
  { x0: 100, x1: 112, y: 33 },
];

function drawTreehouseHabitat(r) {
  r(0, 0, HABITAT_W, 60, "#b8dca8"); // light through the leaves
  const rand = habitatSeeded(31);
  for (let i = 0; i < 50; i++) drawHabitatDisc(r, rand() * HABITAT_W, rand() * 20, 6 + rand() * 6, 4, i % 2 ? "#4a8a4a" : "#3a7a3a");
  for (const tx of [22, 80, 134]) {
    r(tx - 4, 0, 8, 70, "#6e4a2a"); // big trunks
    r(tx - 4, 0, 2, 70, "#8b5a2b");
  }
  drawHabitatGround(r, 64, "#5e7a34", ["#6d9440", "#4e6a2a", "#a86a2e"], 32);
  // platforms with little huts
  for (const [x0, x1, y] of [[6, 46, 36], [60, 100, 24], [112, 154, 40]]) {
    r(x0, y, x1 - x0, 3, "#a87a44");
    for (let x = x0; x < x1; x += 3) r(x, y, 1, 3, "#8b5a2b");
    r(x0 + 2, y + 3, 1.5, 6, "#6e4a2a");
    r(x1 - 4, y + 3, 1.5, 6, "#6e4a2a");
  }
  r(64, 10, 16, 14, "#c89a60");
  for (let k = 0; k < 6; k++) r(62 + k * 1.5, 4 + k, 20 - k * 3, 1, "#8e3418");
  r(70, 16, 5, 8, "#5c3a1a");
  r(118, 28, 14, 12, "#c89a60");
  for (let k = 0; k < 5; k++) r(116 + (4 - k) * 1.5, 23 + k, 18 - (4 - k) * 3, 1, "#4a6aa0");
  // rope bridges between them
  for (const [ax, ay, bx, by] of [[46, 36, 60, 24], [100, 24, 112, 40]]) {
    for (let k = 0; k <= 14; k++) {
      const t = k / 14;
      const x = ax + (bx - ax) * t;
      const y = ay + (by - ay) * t + Math.sin(Math.PI * t) * 3;
      r(x, y, 1.2, 1.2, "#c8a060");
      r(x, y - 4, 0.6, 0.6, "#8b5a2b");
    }
  }
  // ladders down to the ground
  for (const lx of [36, 140]) {
    r(lx, 40, 1, 26, "#8b5a2b");
    r(lx + 5, 40, 1, 26, "#8b5a2b");
    for (let y = 42; y < 66; y += 4) r(lx, y, 6, 1, "#a87a44");
  }
}

// --- Library Nook --------------------------------------------------------------------

function drawBookshelf(r, x, y, w, h) {
  r(x, y, w, h, "#6e4a2a");
  const rand = habitatSeeded(x + y);
  for (let sy = y + 2; sy < y + h - 4; sy += 9) {
    r(x + 1, sy + 7, w - 2, 2, "#5c3a1a");
    for (let bx = x + 2; bx < x + w - 2; bx += 2.5) {
      const bh = 5 + rand() * 2;
      r(bx, sy + 7 - bh, 2, bh, ["#b8432f", "#4a6aa0", "#6b8e3a", "#e8b33e", "#8a5a9a", "#d8c090"][Math.floor(rand() * 6)]);
    }
  }
}

function drawLibraryHabitat(r) {
  drawHabitatWall(r, 46, "#4a3a5a", "#463654");
  drawBookshelf(r, 4, 6, 40, 40);
  drawBookshelf(r, 116, 6, 40, 40);
  r(44, 4, 72, 3, "#6e4a2a"); // a high shelf across the top
  drawHabitatWindow(r, 64, 12, 32, 24, "#2a3a6a", "#6e4a2a");
  r(84, 16, 3, 3, "#f8f0d0");
  r(60, 36, 40, 4, "#8b5a2b"); // the window seat
  r(61, 40, 38, 6, "#8a5a9a");
  // the rolling ladder
  r(30, 6, 1.5, 44, "#a87a44");
  r(37, 6, 1.5, 44, "#a87a44");
  for (let y = 10; y < 48; y += 5) r(30, y, 9, 1, "#c89a60");
  drawHabitatFloor(r, 46, "#8b5a2b", "#7a4e24");
  drawHabitatRug(r, 46, 62, 66, 18, "#8e2a20", "#6e4420");
  for (let x = 50; x < 110; x += 8) r(x, 70, 4, 2, "#e8b33e");
  // reading cushions and a lamp
  drawHabitatDisc(r, 30, 80, 10, 4, "#4a6aa0");
  drawHabitatDisc(r, 28, 78, 6, 2, "#6a8ac0");
  drawHabitatDisc(r, 132, 80, 10, 4, "#6b8e3a");
  r(146, 50, 1.5, 22, "#3b2417");
  r(141, 46, 11, 5, "#e8b33e");
  for (let k = 0; k < 5; k++) r(138 - k * 2, 51 + k * 5, 17 + k * 4, 5, "rgba(248, 224, 138, 0.06)");
  // a stack of books
  for (let k = 0; k < 4; k++) r(100 + (k % 2), 82 - k * 2, 10, 2, ["#b8432f", "#4a6aa0", "#e8b33e", "#6b8e3a"][k]);
}

// --- Playroom -----------------------------------------------------------------------

function drawPlayroomHabitat(r) {
  drawHabitatWall(r, 46, "#f4e0b0", "#f8d8c0");
  for (let x = 6; x < HABITAT_W; x += 18) drawHabitatDisc(r, x, 12 + (x % 3) * 4, 2, 2, ["#e86a8a", "#7ab0e0", "#f4c430"][x % 3]); // painted dots
  drawHabitatWindow(r, 64, 8, 26, 20);
  drawHabitatFloor(r, 46, "#d8b880", "#c8a470");
  drawHabitatRug(r, 30, 64, 70, 20, "#7ab0e0", "#4a80b0");
  r(32, 73, 66, 1.5, "#9a948a"); // a play-road
  for (let x = 34; x < 96; x += 6) r(x, 73.5, 3, 0.5, "#fbf1dc");
  // the pillow fort
  r(4, 42, 30, 20, "#e86a8a");
  for (let k = 0; k < 8; k++) r(2 + (7 - k) * 2, 34 + k, 34 - (7 - k) * 4, 1, k % 2 ? "#fbf1dc" : "#f0e4d0"); // a sheet roof
  r(12, 50, 12, 12, "#5a2a3a");
  // the toy block tower (pets climb)
  for (const [bx, by, c] of [[110, 56, "#d8483a"], [118, 56, "#4a80b0"], [114, 48, "#f4c430"]]) {
    r(bx, by, 8, 8, c);
    r(bx + 2, by + 2, 4, 4, "#fbf1dc");
  }
  // the slide
  r(132, 30, 3, 34, "#e8b33e");
  r(150, 30, 3, 34, "#e8b33e");
  r(132, 30, 21, 3, "#f4c430");
  for (let k = 0; k < 24; k++) r(132 - k * 1.2, 33 + k * 1.2, 4, 1.5, "#d8483a");
  // the ball pit
  r(52, 80, 36, 8, "#4a80b0");
  const rand = habitatSeeded(41);
  for (let i = 0; i < 40; i++) drawHabitatDisc(r, 54 + rand() * 32, 79 + rand() * 4, 1.2, 1.2, ["#d8483a", "#f4c430", "#7ab0e0", "#6b8e3a", "#e86a8a"][i % 5]);
}

// --- Hay Loft -----------------------------------------------------------------------

function drawHayLoftHabitat(r) {
  r(0, 0, HABITAT_W, 50, "#8e3a26"); // barn boards under the roof
  for (let x = 3; x < HABITAT_W; x += 6) r(x, 0, 1, 50, "#6e2a1a");
  for (let k = 0; k < 16; k++) {
    r(k * 5, 16 - k, 6, 2, "#5c2a1a"); // roof beams sloping in
    r(HABITAT_W - 6 - k * 5, 16 - k, 6, 2, "#5c2a1a");
  }
  r(0, 30, HABITAT_W, 3, "#5c2a1a");
  drawHabitatDisc(r, 80, 18, 10, 10, "#5c2a1a"); // the round window
  drawHabitatDisc(r, 80, 18, 8.5, 8.5, "#a8d5e2");
  r(79.5, 9.5, 1, 17, "#5c2a1a");
  r(71.5, 17.5, 17, 1, "#5c2a1a");
  for (let k = 0; k < 6; k++) r(70 - k * 3, 28 + k * 4, 20 + k * 6, 4, "rgba(255, 244, 200, 0.07)"); // light
  drawHabitatFloor(r, 50, "#c8a050", "#b08c40");
  const rand = habitatSeeded(43);
  for (let i = 0; i < 120; i++) r(rand() * HABITAT_W, 50 + rand() * 40, 2, 0.6, i % 2 ? "#e8d070" : "#d8b850");
  // hay bales stacked (ledges) and loose piles (jump in)
  for (const [hx, hy] of [[10, 58], [26, 58], [18, 48]]) {
    r(hx, hy, 16, 10, "#e8c84a");
    r(hx, hy + 3, 16, 1, "#c8a030");
    r(hx, hy + 7, 16, 1, "#c8a030");
    r(hx, hy, 16, 1, "#f4d870");
  }
  drawHabitatDisc(r, 116, 80, 14, 5, "#e8c84a");
  drawHabitatDisc(r, 114, 78, 9, 3, "#f4d870");
  // the rope swing
  r(140, 0, 0.8, 58, "#c8a060");
  r(152, 0, 0.8, 58, "#c8a060");
  r(138, 58, 16, 2, "#8b5a2b");
}

// --- Attic Hideaway -----------------------------------------------------------------

function drawAtticHabitat(r) {
  r(0, 0, HABITAT_W, 50, "#a88a6a"); // the sloped ceiling
  for (let k = 0; k < 30; k++) {
    r(0, k, 50 - k * 1.6, 1, "#7a5a3a");
    r(110 + k * 1.6, k, 50 - k * 1.6, 1, "#7a5a3a");
  }
  for (let x = 0; x < HABITAT_W; x += 12) r(x, 0, 1, 50, "#98785a");
  // the rainy round window
  drawHabitatDisc(r, 80, 20, 10, 10, "#5c3a1a");
  drawHabitatDisc(r, 80, 20, 8.5, 8.5, "#6a7a8a");
  for (const [dx, dy] of [[-4, -3], [2, -5], [5, 1], [-2, 3], [0, 6]]) r(80 + dx, 20 + dy, 0.6, 2, "#a8c0d0");
  // string lights
  for (let x = 4; x < 156; x += 2) r(x, 8 + Math.sin(x / 12) * 3, 1, 0.5, "#3b2417");
  for (let x = 8; x < 156; x += 10) drawHabitatDisc(r, x, 9.5 + Math.sin(x / 12) * 3, 1, 1, ["#f8e08a", "#e86a8a", "#7ab0e0"][(x / 10) % 3 | 0]);
  drawHabitatFloor(r, 50, "#9a7a50", "#866844");
  drawHabitatRug(r, 50, 66, 60, 16, "#6b8e3a", "#4a6627");
  // the old trunk (pets climb)
  r(10, 56, 30, 14, "#6e4a2a");
  r(10, 56, 30, 3, "#8b5a2b");
  r(10, 62, 30, 1, "#c8a030");
  r(23, 60, 4, 4, "#c8a030");
  // boxes to hide in
  r(118, 58, 20, 14, "#d8b070");
  r(118, 58, 20, 2, "#e8c890");
  r(126, 58, 1, 14, "#b88a50");
  r(136, 66, 18, 14, "#c8a060");
  r(140, 70, 10, 10, "#2a1a10"); // an open one
  // an old lamp
  r(96, 46, 1.5, 20, "#3b2417");
  r(91, 42, 11, 5, "#e8a03a");
}

// --- Sunny Porch --------------------------------------------------------------------

function drawPorchHabitat(r) {
  drawHabitatSky(r, 0, 26);
  drawHabitatHills(r, 16, 30, 3, "#8fb85a", 2);
  r(0, 26, HABITAT_W, 8, "#7fa346"); // the yard beyond
  r(0, 30, HABITAT_W, 22, "#e8d3a8"); // the house wall
  for (let y = 32; y < 52; y += 3) r(0, y, HABITAT_W, 1, "#d8c090");
  r(0, 0, HABITAT_W, 4, "#8e3418"); // porch roof edge
  for (const px of [4, 54, 104, 154]) r(px, 4, 3, 48, "#fbf1dc"); // posts
  drawHabitatWindow(r, 16, 34, 18, 14, "#bfe6f0", "#fbf1dc");
  r(66, 32, 14, 20, "#4a6aa0"); // the door
  r(77, 42, 1, 1, "#e8b33e");
  drawHabitatFloor(r, 52, "#c8b090", "#b09a7a");
  // the porch swing (hangs from the roof)
  r(96, 4, 0.6, 36, "#5c3a1a");
  r(124, 4, 0.6, 36, "#5c3a1a");
  r(94, 40, 32, 3, "#a87a44");
  r(94, 32, 32, 2, "#a87a44");
  for (let x = 96; x < 126; x += 4) r(x, 34, 1, 6, "#8b5a2b");
  // the rocking chair
  r(136, 58, 14, 3, "#8b5a2b");
  r(146, 44, 3, 17, "#8b5a2b");
  r(136, 61, 2, 8, "#8b5a2b");
  r(148, 61, 2, 8, "#8b5a2b");
  for (let k = 0; k < 18; k++) r(132 + k, 69 - Math.sin((k / 18) * Math.PI) * 1.5, 1, 1, "#6e4420");
  // potted flowers and wind chimes
  for (const [fx, c] of [[10, "#e86a8a"], [44, "#f4c430"], [88, "#9a7ae0"]]) {
    r(fx - 4, 74, 8, 6, "#c8643a");
    drawHabitatFlower(r, fx - 2, 71, c);
    drawHabitatFlower(r, fx + 2, 70, c);
  }
  for (const cx of [60, 62, 64]) r(cx, 4, 0.5, 8 + (cx % 3) * 2, "#b8b2a6");
  // a sunbeam on the boards
  for (let k = 0; k < 5; k++) r(40 + k * 4, 60 + k * 4, 30, 4, "rgba(255, 240, 180, 0.18)");
}

Object.assign(HABITAT_LOOKS, {
  cottage: {
    name: "Cozy Cottage",
    draw: drawCottageHabitat,
    groundTop: 50,
    groundBottom: 88,
    props: [
      { id: "fireplace", x: 57, y: 54, action: "nap" },
      { id: "yarn", x: 96, y: 84, action: "jump", color: "#e86a8a" },
      { id: "armchair", x: 139, y: 52, action: "nap", ledge: 1 },
      { id: "window seat", x: 109, y: 28, action: "bask", ledge: 2 },
    ],
    terrain: {
      ledges: [
        { x0: 2, x1: 26, y: 66 },
        { x0: 128, x1: 150, y: 58 },
        { x0: 96, x1: 122, y: 28 },
        { x0: 6, x1: 22, y: 44 },
        { x0: 4, x1: 22, y: 24 },
      ],
      blocks: [
        { x: 124, y: 50, w: 30, h: 18 },
        { x: 1, y: 66, w: 26, h: 5 },
        { x: 88, y: 76, w: 16, h: 6 },
      ],
    },
  },
  greenhouse: {
    name: "Greenhouse",
    draw: drawGreenhouseHabitat,
    groundTop: 52,
    groundBottom: 88,
    props: [
      { id: "lamp", x: 122, y: 60, action: "bask" },
      { id: "fern", x: 150, y: 86 },
      { id: "seedlings", x: 30, y: 30, action: "look", ledge: 0 },
    ],
    terrain: {
      water: [{ x: 69, y: 68, w: 26, h: 6, color: "#6ab0d0" }],
      ledges: [{ x0: 6, x1: 56, y: 30 }],
      blocks: [
        { x: 14, y: 72, w: 12, h: 8 },
        { x: 134, y: 56, w: 12, h: 8 },
        { x: 144, y: 76, w: 12, h: 8 },
        { x: 78, y: 58, w: 8, h: 10 },
      ],
    },
  },
  treehouse: {
    name: "Treehouse Village",
    draw: drawTreehouseHabitat,
    groundTop: 68,
    groundBottom: 88,
    props: [
      { id: "hut", x: 72, y: 24, action: "nap", ledge: 1 },
      { id: "lookout", x: 140, y: 40, action: "bask", ledge: 2 },
      { id: "leaves", x: 100, y: 84, action: "jump", color: "#6d9440" },
    ],
    terrain: { ledges: TREEHOUSE_LEDGES },
  },
  library: {
    name: "Library Nook",
    draw: drawLibraryHabitat,
    groundTop: 50,
    groundBottom: 88,
    props: [
      { id: "cushion", x: 30, y: 82, action: "nap" },
      { id: "big cushion", x: 132, y: 82, action: "nap" },
      { id: "books", x: 105, y: 84 },
      { id: "window seat", x: 80, y: 36, action: "bask", ledge: 0 },
    ],
    terrain: {
      ledges: [
        { x0: 60, x1: 100, y: 36 },
        { x0: 44, x1: 116, y: 4 },
      ],
      blocks: [{ x: 98, y: 76, w: 14, h: 8 }],
    },
  },
  playroom: {
    name: "Playroom",
    draw: drawPlayroomHabitat,
    groundTop: 52,
    groundBottom: 88,
    props: [
      { id: "fort", x: 18, y: 64, action: "nap" },
      { id: "ball pit", x: 70, y: 86, action: "jump", color: "#f4c430" },
      { id: "block top", x: 118, y: 48, action: "look", ledge: 1 },
    ],
    terrain: {
      ledges: [
        { x0: 110, x1: 126, y: 56 },
        { x0: 114, x1: 122, y: 48 },
        { x0: 132, x1: 153, y: 30 },
      ],
      blocks: [
        { x: 2, y: 42, w: 34, h: 20 },
        { x: 109, y: 56, w: 18, h: 8 },
        { x: 130, y: 52, w: 25, h: 12 },
      ],
    },
  },
  hayloft: {
    name: "Hay Loft",
    draw: drawHayLoftHabitat,
    groundTop: 56,
    groundBottom: 88,
    props: [
      { id: "hay pile", x: 116, y: 82, action: "jump", color: "#f4d870" },
      { id: "sunny bale", x: 26, y: 48, action: "bask", ledge: 1 },
      { id: "swing", x: 146, y: 60 },
    ],
    terrain: {
      ledges: [
        { x0: 10, x1: 42, y: 58 },
        { x0: 18, x1: 34, y: 48 },
        { x0: 138, x1: 154, y: 58 },
      ],
      blocks: [{ x: 9, y: 58, w: 34, h: 10 }],
    },
  },
  attic: {
    name: "Attic Hideaway",
    draw: drawAtticHabitat,
    groundTop: 56,
    groundBottom: 88,
    props: [
      { id: "box", x: 145, y: 82, action: "nap" },
      { id: "trunk", x: 25, y: 56, action: "look", ledge: 0 },
      { id: "rug", x: 80, y: 76, action: "dig", color: "#6b8e3a" },
    ],
    terrain: {
      ledges: [
        { x0: 10, x1: 40, y: 56 },
        { x0: 118, x1: 138, y: 58 },
      ],
      blocks: [
        { x: 9, y: 56, w: 32, h: 14 },
        { x: 117, y: 58, w: 22, h: 14 },
      ],
    },
  },
  porch: {
    name: "Sunny Porch",
    draw: drawPorchHabitat,
    groundTop: 56,
    groundBottom: 88,
    props: [
      { id: "sunbeam", x: 60, y: 70, action: "bask" },
      { id: "swing", x: 110, y: 40, action: "nap", ledge: 0 },
      { id: "flowers", x: 44, y: 82 },
    ],
    terrain: {
      ledges: [
        { x0: 94, x1: 126, y: 40 },
        { x0: 136, x1: 150, y: 58 },
      ],
      blocks: [
        { x: 135, y: 58, w: 16, h: 11 },
        { x: 5, y: 74, w: 10, h: 6 },
        { x: 39, y: 74, w: 10, h: 6 },
        { x: 83, y: 74, w: 10, h: 6 },
      ],
    },
  },
});
