// The magical habitats (PLAN.md 11j), open with the Mythical department:
// Crystal Cave, Cloud Kingdom, Volcano Rim, Enchanted Grove, Starry
// Observatory, Foggy Lagoon. Shared helpers are in habitats.js.

function drawCrystal(r, x, y, h, color, light) {
  for (let k = 0; k < h; k++) {
    const w = Math.max(1, Math.min(k + 1, (h - k) * 0.6 + 1));
    r(x - w / 2, y - h + k, w, 1, k % 3 ? color : light);
  }
  r(x - 0.5, y - h + 1, 0.6, h * 0.6, "rgba(255, 255, 255, 0.5)");
}

function drawStars(r, seed, count, top, bottom) {
  const rand = habitatSeeded(seed);
  for (let i = 0; i < count; i++) r(rand() * HABITAT_W, top + rand() * (bottom - top), i % 5 ? 0.6 : 1, i % 5 ? 0.6 : 1, i % 4 ? "#fbf1dc" : "#f8e08a");
}

// --- Crystal Cave --------------------------------------------------------------------

function drawCrystalCaveHabitat(r) {
  r(0, 0, HABITAT_W, HABITAT_H, "#2a2238");
  const rand = habitatSeeded(51);
  for (let i = 0; i < 40; i++) drawHabitatDisc(r, rand() * HABITAT_W, rand() * 50, 6 + rand() * 8, 4 + rand() * 4, i % 2 ? "#342a46" : "#3a3050");
  for (let x = 4; x < HABITAT_W; x += 11) {
    const len = 4 + ((x * 7) % 10); // stalactites
    for (let k = 0; k < len; k++) r(x - (len - k) / 6, k, ((len - k) / 3) | 1, 1, "#4a405e");
  }
  drawHabitatGround(r, 50, "#3a3050", ["#4a405e", "#2e2640", "#6a5a8a"], 52);
  drawHabitatLedge(r, 8, 44, 46, 56, "#4a405e", "#3a3050", "#6a5a8a");
  drawHabitatLedge(r, 116, 154, 40, 56, "#4a405e", "#3a3050", "#6a5a8a");
  // glowing crystals
  for (const [cx, cy, h, c, l] of [
    [20, 46, 10, "#9a6ae0", "#c8a8f8"],
    [26, 46, 6, "#6ac8e0", "#a8e8f8"],
    [130, 40, 12, "#e06ab8", "#f8a8e0"],
    [140, 40, 7, "#9a6ae0", "#c8a8f8"],
    [70, 86, 8, "#6ac8e0", "#a8e8f8"],
    [150, 84, 9, "#9a6ae0", "#c8a8f8"],
    [8, 86, 6, "#e06ab8", "#f8a8e0"],
  ]) {
    for (let k = 0; k < 4; k++) drawHabitatDisc(r, cx, cy - h / 2, h * (0.8 + k * 0.25), h * 0.6, `rgba(180, 140, 255, ${0.05})`);
    drawCrystal(r, cx, cy, h, c, l);
  }
  // the underground pool
  drawHabitatDisc(r, 100, 72, 24, 6, "#2a6a8a");
  drawHabitatDisc(r, 98, 71, 18, 3, "#4a9ac0");
  for (let x = 82; x < 118; x += 6) r(x, 72, 2, 0.6, "#a8e8f8");
}

// --- Cloud Kingdom -------------------------------------------------------------------

function drawCloudPuff(r, x, y, w, h, color = "#ffffff", shade = "#e8eef8") {
  drawHabitatDisc(r, x + w / 2, y + h / 2 + 1, w / 2, h / 2, shade);
  for (let k = 0; k < w; k += h) drawHabitatDisc(r, x + k + h / 2, y + h / 2, h / 1.6, h / 2, color);
}

function drawCloudKingdomHabitat(r) {
  for (let y = 0; y < HABITAT_H; y++) r(0, y, HABITAT_W, 1, y < 30 ? "#c8d8f8" : y < 60 ? "#e0d0f4" : "#f4d8ec");
  // a rainbow
  ["#e86a6a", "#f4a24a", "#f4d35e", "#7ac87a", "#7ab0e0", "#9a7ae0"].forEach((c, i) => {
    for (let a = 0; a <= 40; a++) {
      const t = Math.PI * (a / 40);
      r(80 - Math.cos(t) * (60 - i * 2), 52 - Math.sin(t) * (40 - i * 2), 1.2, 1.2, c);
    }
  });
  // the floating castle far away
  drawCloudPuff(r, 116, 20, 26, 6);
  r(122, 8, 16, 12, "#f4f0fa");
  for (const tx of [120, 128, 136]) {
    r(tx, 4, 4, 16, "#e8e0f4");
    for (let k = 0; k < 4; k++) r(tx + (3 - k) / 2, k, k + 1, 1, "#b8a0e0"); // pointed roofs
  }
  // cloud islands (ledges) and the big cloud below
  drawCloudPuff(r, 8, 40, 36, 8);
  drawCloudPuff(r, 62, 30, 30, 7);
  drawCloudPuff(r, 112, 44, 40, 8);
  r(0, 56, HABITAT_W, HABITAT_H - 56, "#ffffff");
  for (let x = 0; x < HABITAT_W; x += 10) drawHabitatDisc(r, x + 5, 56, 7, 4, "#ffffff");
  const rand = habitatSeeded(61);
  for (let i = 0; i < 30; i++) r(rand() * HABITAT_W, 60 + rand() * 28, 3, 1, "#eef0f8");
  // sparkles
  for (let i = 0; i < 14; i++) r(rand() * HABITAT_W, rand() * 50, 0.6, 0.6, "#ffffff");
}

// --- Volcano Rim ---------------------------------------------------------------------

function drawVolcanoHabitat(r) {
  for (let y = 0; y < 50; y++) r(0, y, HABITAT_W, 1, y < 16 ? "#5a1a1a" : y < 32 ? "#8a2a1a" : "#b8402a");
  // the volcano, glowing
  for (let k = 0; k < 34; k++) r(50 - k * 1.6, 16 + k, 60 + k * 3.2, 1, k % 4 ? "#3a2a2a" : "#2e2222");
  r(66, 14, 28, 3, "#f4a24a");
  r(70, 13, 20, 2, "#f8d870");
  for (let k = 0; k < 4; k++) r(74 + k * 4, 17 + k * 6, 2, 6, "#e8582a"); // a lava trail
  drawHabitatGround(r, 50, "#3a2a2a", ["#2a1e1e", "#5a3a2a", "#e8582a"], 71, 80);
  // obsidian rocks (ledges)
  drawHabitatLedge(r, 6, 40, 52, 62, "#2a2230", "#1a1620", "#4a3a4a");
  drawHabitatLedge(r, 120, 154, 48, 60, "#2a2230", "#1a1620", "#4a3a4a");
  // the lava pool (too hot: pets go around it)
  drawHabitatDisc(r, 90, 76, 20, 6, "#a8301a");
  drawHabitatDisc(r, 90, 76, 18, 5, "#e8582a");
  drawHabitatDisc(r, 88, 75, 10, 2.5, "#f8a83a");
  r(84, 75, 3, 0.8, "#f8e08a");
  // warm vents
  for (const vx of [34, 140]) {
    drawHabitatDisc(r, vx, 82, 5, 2, "#5a3a2a");
    drawHabitatDisc(r, vx, 82, 2.5, 1, "#f8a83a");
    for (let k = 0; k < 4; k++) r(vx - 1 + (k % 2), 78 - k * 3, 2, 2, "rgba(220, 200, 200, 0.25)");
  }
  // ash sparkles
  const rand = habitatSeeded(73);
  for (let i = 0; i < 24; i++) r(rand() * HABITAT_W, rand() * 50, 0.6, 0.6, i % 3 ? "#f8a83a" : "#f8e08a");
}

// --- Enchanted Grove -----------------------------------------------------------------

function drawGroveHabitat(r) {
  for (let y = 0; y < 50; y++) r(0, y, HABITAT_W, 1, y < 20 ? "#1e2a4a" : y < 36 ? "#2a3a5a" : "#344a5a");
  drawStars(r, 81, 30, 0, 30);
  drawHabitatDisc(r, 30, 12, 6, 6, "#f8f4e0"); // the moon
  for (const [tx, ty, s] of [[12, 52, 14], [60, 48, 12], [150, 52, 15], [110, 46, 11]]) drawHabitatTree(r, tx, ty, 16, s, "#2a5a4a", "#1e4a3a", "#3a2a2a");
  drawHabitatGround(r, 48, "#2e4a3a", ["#3a5a44", "#24402e", "#5a8a6a"], 83);
  // the ancient tree with a hollow
  r(122, 30, 20, 34, "#4a3a2a");
  r(122, 30, 4, 34, "#5a4a3a");
  drawHabitatDisc(r, 132, 56, 5, 7, "#1a1210");
  drawHabitatDisc(r, 132, 22, 22, 12, "#1e4a3a");
  drawHabitatDisc(r, 130, 20, 18, 9, "#2a5a4a");
  // the moonlit pond
  drawHabitatDisc(r, 60, 74, 22, 6, "#2a4a6a");
  drawHabitatDisc(r, 58, 73, 14, 3, "#3a5a8a");
  r(52, 72, 10, 0.6, "#f8f4e0");
  // glowing mushrooms
  for (const [mx, my, c] of [[20, 70, "#6ae0c8"], [26, 74, "#a88af8"], [100, 84, "#6ae0c8"], [96, 80, "#f88ac8"], [148, 76, "#a88af8"]]) {
    drawHabitatDisc(r, mx, my - 1, 6, 3, `${c}22`);
    r(mx - 0.5, my, 1, 3, "#d8e8e0");
    drawHabitatDisc(r, mx, my, 2.5, 1.5, c);
  }
  // fairy lights
  const rand = habitatSeeded(87);
  for (let i = 0; i < 26; i++) {
    const fx = rand() * HABITAT_W;
    const fy = 20 + rand() * 60;
    r(fx - 1, fy - 1, 3, 3, "rgba(248, 240, 160, 0.15)");
    r(fx, fy, 1, 1, "#f8f0a0");
  }
}

// --- Starry Observatory -------------------------------------------------------------

function drawObservatoryHabitat(r) {
  for (let y = 0; y < HABITAT_H; y++) r(0, y, HABITAT_W, 1, y < 30 ? "#141a3a" : y < 55 ? "#1e2a52" : "#2a3a62");
  drawStars(r, 91, 90, 0, 50);
  // a constellation and a shooting star
  const pts = [[20, 10], [30, 14], [38, 8], [46, 16], [56, 12]];
  pts.forEach(([x, y], i) => {
    if (i) for (let k = 0; k <= 8; k++) r(pts[i - 1][0] + ((x - pts[i - 1][0]) * k) / 8, pts[i - 1][1] + ((y - pts[i - 1][1]) * k) / 8, 0.4, 0.4, "rgba(200, 210, 255, 0.5)");
    r(x - 0.5, y - 0.5, 1.5, 1.5, "#f8f4e0");
  });
  for (let k = 0; k < 14; k++) r(96 + k * 1.5, 8 + k * 0.6, 1.5, 0.6, `rgba(248, 244, 224, ${(k / 14).toFixed(2)})`);
  // the hill
  drawHabitatDisc(r, 80, 98, 110, 44, "#2a4a3a");
  drawHabitatGround(r, 62, "#2a4a3a", ["#345a44", "#1e3a2e"], 93, 40);
  // the observatory dome and its steps
  r(110, 34, 34, 22, "#c8c0d8");
  drawHabitatDisc(r, 127, 34, 17, 12, "#d8d0e8");
  r(126, 22, 3, 12, "#2a2a3a");
  r(124, 44, 8, 12, "#3a3a52");
  r(106, 56, 42, 3, "#9a94aa");
  r(102, 59, 50, 3, "#8a849a");
  // the telescope
  r(54, 60, 1, 10, "#5c5c66");
  r(48, 60, 1, 10, "#5c5c66");
  r(60, 60, 1, 10, "#5c5c66");
  for (let k = 0; k < 14; k++) r(48 + k * 0.9, 58 - k * 0.8, 3, 2, "#b8432f");
  r(60, 46, 4, 3, "#e8b33e");
  // a picnic blanket for stargazing
  r(14, 74, 24, 8, "#7a5aa0");
  for (let x = 14; x < 38; x += 4) r(x, 74, 2, 8, "#9a7ac0");
}

// --- Foggy Lagoon --------------------------------------------------------------------

function drawLagoonRock(r, x, y, w, h) {
  drawHabitatDisc(r, x + w / 2, y + h / 2 + 1, w / 2 + 1, h / 2 + 1, "#2e3e48");
  drawHabitatDisc(r, x + w / 2, y + h / 2, w / 2, h / 2, "#4a5e68");
  drawHabitatDisc(r, x + w / 2 - 1, y + h / 3, w / 2 - 3, h / 3, "#64787e");
  r(x + 2, y + h, w - 4, 0.8, "#b8dce0"); // where it meets the water
}

function drawLagoonCoral(r, x, y, color, light) {
  for (const [dx, h] of [[-3, 4], [-1, 7], [1, 5], [3, 6]]) {
    r(x + dx, y - h, 1.2, h, color);
    r(x + dx - 0.4, y - h - 0.8, 2, 1, light);
  }
}

function drawLagoonHabitat(r) {
  for (let y = 0; y < 48; y++) r(0, y, HABITAT_W, 1, y < 14 ? "#8a9aac" : y < 30 ? "#a4b4bc" : "#bfcccc");
  for (let k = 0; k < 4; k++) drawHabitatDisc(r, 118, 16, 11 - k * 2, 11 - k * 2, `rgba(248, 244, 224, ${0.25 + k * 0.2})`); // a pale moon in the mist
  // sea stacks fading away
  for (const [x, w, top, color] of [[10, 16, 22, "#8c9ca6"], [46, 10, 30, "#9aaab0"], [132, 20, 18, "#84949e"], [100, 9, 33, "#a0aeb4"]]) {
    for (let y = top; y < 48; y++) r(x + Math.sin(y * 0.7 + x) * 1.2 - (y - top) * 0.08, y, w + (y - top) * 0.16, 1, color);
    drawHabitatDisc(r, x + w / 2, top, w / 2, 2.5, color);
  }
  // the water, lighter toward the shore
  for (let y = 48; y < 75; y++) r(0, y, HABITAT_W, 1, y < 54 ? "#5a98a4" : y < 62 ? "#468a98" : y < 70 ? "#3a7c8c" : "#3f8a94");
  const rand = habitatSeeded(91);
  for (let i = 0; i < 26; i++) r(rand() * HABITAT_W, 50 + rand() * 24, 3 + rand() * 5, 0.5, "#8cc8cc");
  // the sand
  r(0, 75, HABITAT_W, HABITAT_H - 75, "#d0c6a6");
  for (let x = 0; x < HABITAT_W; x += 2) r(x, 74 + Math.sin(x * 0.18) * 0.8, 2, 2, "#e4dcc0");
  for (let i = 0; i < 70; i++) r(rand() * HABITAT_W, 77 + rand() * 12, 0.7, 0.7, i % 3 ? "#b8ae8e" : "#e8e0c8");
  // rocks to sit on
  drawLagoonRock(r, 20, 57, 26, 9);
  drawLagoonRock(r, 112, 52, 30, 10);
  // things that glow
  for (let i = 0; i < 20; i++) r(rand() * HABITAT_W, 52 + rand() * 22, 0.7, 0.7, i % 2 ? "#a8f0e0" : "#c8b0f4");
  drawLagoonCoral(r, 12, 82, "#d0607a", "#f49ab0");
  drawLagoonCoral(r, 146, 85, "#8a60c0", "#c0a0ec");
  drawLagoonCoral(r, 84, 86, "#d8824a", "#f4b47a");
  // shells
  for (const [x, y, c] of [[38, 80, "#f4d8d8"], [64, 85, "#f8ecd0"], [118, 81, "#e8d0f0"]]) {
    drawHabitatDisc(r, x, y, 1.6, 1, c);
    r(x - 0.3, y - 1, 0.6, 2, "#c8a8a8");
  }
  // the fog, lying in bands
  for (const [y, h, a] of [[34, 8, 0.28], [44, 7, 0.4], [51, 4, 0.3], [60, 2, 0.12]]) {
    for (let x = -10; x < HABITAT_W; x += 18) drawHabitatDisc(r, x + (y * 3) % 18, y + h / 2, 14, h / 2, `rgba(236, 242, 242, ${a / 2})`);
  }
}

Object.assign(HABITAT_LOOKS, {
  lagoon: {
    name: "Foggy Lagoon",
    draw: drawLagoonHabitat,
    groundTop: 48,
    groundBottom: 88,
    props: [
      { id: "warm sand", x: 50, y: 82, action: "dig", color: "#e4dcc0" },
      { id: "coral", x: 12, y: 84 },
      { id: "shell", x: 118, y: 83, action: "bask" },
    ],
    terrain: {
      water: [{ x: 0, y: 48, w: 160, h: 27, color: "#3a7c8c" }],
      // only mermaids climb up here
      ledges: [
        { x0: 22, x1: 44, y: 60, who: ["mermaid"] },
        { x0: 115, x1: 139, y: 56, who: ["mermaid"] },
      ],
    },
  },
  crystalcave: {
    name: "Crystal Cave",
    draw: drawCrystalCaveHabitat,
    groundTop: 56,
    groundBottom: 88,
    props: [
      { id: "crystals", x: 23, y: 46, action: "bask", ledge: 0 },
      { id: "pink crystal", x: 135, y: 40, action: "nap", ledge: 1 },
      { id: "crystal", x: 70, y: 87 },
    ],
    terrain: {
      water: [{ x: 78, y: 67, w: 44, h: 10, color: "#2a6a8a" }],
      ledges: [
        { x0: 8, x1: 44, y: 46 },
        { x0: 116, x1: 154, y: 40 },
      ],
    },
  },
  cloudkingdom: {
    name: "Cloud Kingdom",
    draw: drawCloudKingdomHabitat,
    groundTop: 62,
    groundBottom: 88,
    props: [
      { id: "rainbow end", x: 26, y: 42, action: "bask", ledge: 0 },
      { id: "fluffy cloud", x: 80, y: 80, action: "jump", color: "#ffffff" },
      { id: "high cloud", x: 76, y: 31, action: "nap", ledge: 1 },
    ],
    terrain: {
      ledges: [
        { x0: 6, x1: 46, y: 42 },
        { x0: 60, x1: 94, y: 31 },
        { x0: 110, x1: 154, y: 46 },
      ],
    },
  },
  volcano: {
    name: "Volcano Rim",
    draw: drawVolcanoHabitat,
    groundTop: 64,
    groundBottom: 88,
    props: [
      { id: "vent", x: 34, y: 84, action: "bask" },
      { id: "hot vent", x: 140, y: 84, action: "bask" },
      { id: "obsidian", x: 22, y: 52, action: "nap", ledge: 0 },
    ],
    terrain: {
      ledges: [
        { x0: 6, x1: 40, y: 52 },
        { x0: 120, x1: 154, y: 48 },
      ],
      blocks: [{ x: 70, y: 70, w: 40, h: 12 }],
    },
  },
  grove: {
    name: "Enchanted Grove",
    draw: drawGroveHabitat,
    groundTop: 54,
    groundBottom: 88,
    props: [
      { id: "hollow", x: 132, y: 64, action: "nap" },
      { id: "mushrooms", x: 23, y: 76 },
      { id: "glowshrooms", x: 98, y: 86, action: "dig", color: "#6ae0c8" },
    ],
    terrain: {
      water: [{ x: 40, y: 69, w: 40, h: 10, color: "#2a4a6a" }],
      blocks: [{ x: 121, y: 54, w: 22, h: 10 }],
    },
  },
  observatory: {
    name: "Starry Observatory",
    draw: drawObservatoryHabitat,
    groundTop: 64,
    groundBottom: 88,
    props: [
      { id: "blanket", x: 26, y: 80, action: "nap" },
      { id: "telescope", x: 54, y: 72 },
      { id: "top step", x: 126, y: 56, action: "look", ledge: 0 },
    ],
    terrain: {
      ledges: [
        { x0: 106, x1: 148, y: 56 },
        { x0: 102, x1: 152, y: 59 },
      ],
      blocks: [{ x: 47, y: 62, w: 15, h: 8 }],
    },
  },
});
