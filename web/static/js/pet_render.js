// Pets drawn in code from their genes (app/pet_genes.py). A species is a
// recipe of parts -- body, legs, head, snout, ears, tail, and extras like
// wool, horns, a long neck -- and the growth stage sets the proportions
// (babies: big heads, short legs). Each species slightly exaggerates what
// makes it that animal (fox: white tail tip and dark socks; sheep: a cloud
// of wool with a dark face; goat: long face, beard, sideways pupils).
//
// Parts are rasterized into a grid of cells {l: label, nx, ny}, where
// (nx, ny) is where the pixel sits on its part's surface (-1..1). That
// gives real lighting: light comes from the upper left, and each pixel
// lands in one of 4 bands (highlight, base, shade, deep shade), drawn as
// an alpha tint over its color -- warm white for light, cool purple for
// shadow. The silhouette gets a near-black outline; where a front part
// covers another (head over body), the line is a darker shade of the fur
// instead, so the inside stays readable.
//
// The coat: a pattern field (patches, spots, stripes, belly, points) is
// ranked over the fur pixels so each color gets exactly its share.
//
// Pets are drawn at twice the avatar's pixel density: drawPet() takes a
// `scale` in the caller's px units per pet pixel (0.5 on the avatar grid).

const PET_STAGES = [
  { id: "baby", min: 0, body: 0.45, head: 0.82, leg: 0.4 },
  { id: "small", min: 1, body: 0.58, head: 0.86, leg: 0.56 },
  { id: "mid", min: 4, body: 0.73, head: 0.9, leg: 0.73 },
  { id: "big", min: 7, body: 0.87, head: 0.94, leg: 0.87 },
  { id: "grown", min: 10, body: 1, head: 1, leg: 1 },
];

function petStage(growth) {
  return [...PET_STAGES].reverse().find((s) => growth >= s.min);
}

// Sizes in pet pixels for a grown pet. head: rx/ry and an offset from the
// front-top of the body; leg.min keeps legs readable on babies.
const PET_RECIPES = {
  fox: {
    body: { rx: 9, ry: 4.5 }, leg: { len: 6, w: 2, min: 3 }, head: { rx: 5, ry: 4.5, dx: 1, dy: 0 },
    snout: { len: 6, r: 2, pointy: true }, ears: { type: "pointy", size: 6.5, w: 1.2, tips: true },
    tail: { type: "bushy", len: 13, w: 4.5, tip: true }, eye: "round", socks: true,
  },
  bunny: {
    body: { rx: 8.5, ry: 6 }, leg: { len: 2, w: 3, min: 2 }, head: { rx: 5, ry: 4.8, dx: 2, dy: 2 },
    snout: { len: 1, r: 1.6 }, ears: { type: "long", size: 12 }, tail: { type: "cotton", len: 3, w: 3 },
    eye: "round", hindFoot: true, pinkNose: true,
  },
  sheep: {
    body: { rx: 10, ry: 6.5 }, leg: { len: 7, w: 2, min: 5 }, head: { rx: 3.6, ry: 4.6, dx: 5, dy: 1 },
    snout: { len: 2, r: 2.2 }, ears: { type: "side", size: 4 }, tail: { type: "stub", len: 2, w: 3 },
    eye: "round", wool: true, face: true, hooves: true,
  },
  goat: {
    body: { rx: 9, ry: 5 }, leg: { len: 7, w: 2, min: 4 }, head: { rx: 5, ry: 3.6, dx: 3, dy: -1 },
    snout: { len: 4, r: 2, square: true }, ears: { type: "side", size: 4.5 }, tail: { type: "flag", len: 4, w: 2 },
    eye: "goat", horns: true, beard: true, hooves: true,
  },
  llama: {
    body: { rx: 9, ry: 5 }, leg: { len: 8, w: 2, min: 4 }, head: { rx: 3.8, ry: 4.2, dx: 0, dy: 0 }, neck: { len: 11, w: 4 },
    snout: { len: 3, r: 2.2 }, ears: { type: "banana", size: 5 }, tail: { type: "cotton", len: 2, w: 2.5 },
    eye: "round", hooves: true, chestFluff: true,
  },
};


// Labels painted with the coat. The rest have their own colors (PET_FIXED
// or, for "face" and "skin", a shade of the coat).
const FUR = new Set(["thin", "coilbase", "hood", "farleg", "limb", "tail", "body", "wool", "leg", "neck", "head", "farear", "ear", "snout", "beard", "cap", "chest", "fold", "flop", "mane", "fluff", "tuft", "shell", "rim", "spine", "dewlap", "frill", "fin"]);
// Parts that cover what's behind them with a line (inside the silhouette).
const FRONT = new Set(["body", "wool", "head", "face", "cap", "neck", "chest", "shell", "rim", "fbody", "fhead", "lip", "pectoral", "belly", "egg", "eggspot", "eggspot2", "breast", "pegg", "ash"]);
// Parts in front of the body that grow out of it (no line where they meet).
const BLENDS_IN = new Set(["thin", "leg", "skin", "beard", "sock", "hoof", "ear", "farear", "eartip", "fold", "fluff", "belly", "eggspot", "eggspot2", "breast", "crack", "crack2", "gill", "fhead"]);
// The head stands apart from the body with a shade line and a chin shadow.
const HEADISH = new Set(["head", "face", "snout", "cap"]);
const BODYISH = new Set(["thin", "body", "wool", "chest", "neck", "leg", "tail", "fluff"]);
// Parts drawn behind the body: darker, like they're in shadow.
const FAR = new Set(["farleg", "farear", "farskin", "farsock", "farhoof", "farwing", "farbone", "farhorn", "farclaw", "farfeather", "farpfeather", "farbirdleg"]);
const PET_FIXED = {
  hoof: "#5a4030", farhoof: "#5a4030", horn: "#c8aa7a", innerear: "#f4a8b8", nose: "#2a1a14", pinknose: "#f08aa0",
  hole: "#24170e", rattle: "#d8c08a", tip: "#fbf6ec", eartip: "#3a2a24", sock: "#3a2a24", farsock: "#3a2a24", cotton: "#fbf8f2", tongue: "#f07890",
  farhorn: "#c8aa7a", claw: "#f2e6c8", farclaw: "#f2e6c8", uhorn: "#f6e6b8", uhornline: "#d8b878", beak: "#f0c050", birdleg: "#c8963c", farbirdleg: "#c8963c", ash: "#8e8680", ember: "#ffb040", egg: "#f4ecd8", eggback: "#d8ccb0",
};
// Parts colored from the coat: a dragon's pale belly and wing membranes.
const DERIVED = {
  belly: (hex) => blend(hex[0], "#f6e2a8", 0.55),
  wing: (hex) => blend(hex[0], "#f4d8b0", 0.5),
  farwing: (hex) => blend(hex[0], "#f4d8b0", 0.5),
  wingbone: (hex) => blend(hex[0], SHADOW_TINT, 0.4),
  farbone: (hex) => blend(hex[0], SHADOW_TINT, 0.4),
  dspine: (hex) => blend(hex[0], "#f6e2a8", 0.45),
  spade: (hex) => blend(hex[0], "#f6e2a8", 0.45),
  eggspot: (hex) => hex[0],
  eggspot2: (hex) => hex[1] || hex[0],
  umane: (hex) => hex[1] || hex[0],
  utail: (hex) => hex[1] || hex[0],
  feather: (hex) => blend(hex[0], "#ffffff", 0.25),
  pfeather: (hex) => hex[0],
  fhead: (hex) => hex[0],
  gill: (hex) => blend(hex[0], SHADOW_TINT, 0.22),
  lip: (hex) => blend(hex[0], "#f8a8a0", 0.7),
  mouthline: (hex) => blend(hex[0], SHADOW_TINT, 0.5),
  barbel: (hex) => blend(hex[0], "#f0e0c0", 0.4),
  caudal: (hex) => blend(hex[1] || hex[0], "#ffffff", 0.3),
  dorsal: (hex) => blend(hex[1] || hex[0], "#ffffff", 0.3),
  anal: (hex) => blend(hex[1] || hex[0], "#ffffff", 0.3),
  pelvic: (hex) => blend(hex[1] || hex[0], "#ffffff", 0.3),
  pectoral: (hex) => blend(hex[1] || hex[0], "#ffffff", 0.45),
  cray: (hex) => blend(hex[1] || hex[0], SHADOW_TINT, 0.12),
  dray: (hex) => blend(hex[1] || hex[0], SHADOW_TINT, 0.12),
  aray: (hex) => blend(hex[1] || hex[0], SHADOW_TINT, 0.12),
  pfeather2: (hex) => blend(hex[0], SHADOW_TINT, 0.15),
  farpfeather: (hex) => hex[0],
  breast: (hex) => blend(hex[0], "#f8e0a0", 0.35),
  plume: (hex) => hex[1] || hex[0],
  plumetip: (hex) => blend(hex[1] || hex[0], "#fff0b0", 0.45),
  pegg: (hex) => blend(hex[0], "#1e1210", 0.72),
  crack: (hex) => blend(hex[1] || hex[0], "#fff4c0", 0.25),
  crack2: (hex) => blend(hex[1] || hex[0], "#fffbe8", 0.6),
  feather2: (hex) => blend(hex[0], SHADOW_TINT, 0.12),
  farfeather: (hex) => blend(hex[0], "#ffffff", 0.15),
  flame: () => "#f07830",
  flamecore: () => "#fbe070",
};
const PET_OUTLINE = "#1a0f08";
const LIGHT_TINT = "#fff4d8";
const SHADOW_TINT = "#2a1840";
const LIGHT = (() => {
  const v = [-0.45, -0.62, 0.64];
  const n = Math.hypot(...v);
  return v.map((c) => c / n);
})();

// --- little helpers ---------------------------------------------------------------

function mulberry32(a) {
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function valueNoise(seed) {
  const rnd = mulberry32(seed);
  const table = Array.from({ length: 256 }, () => rnd());
  const at = (i, j) => table[((Math.imul(i, 73856093) ^ Math.imul(j, 19349663)) >>> 0) & 255];
  const smooth = (t) => t * t * (3 - 2 * t);
  return (x, y) => {
    const xi = Math.floor(x);
    const yi = Math.floor(y);
    const u = smooth(x - xi);
    const v = smooth(y - yi);
    const top = at(xi, yi) * (1 - u) + at(xi + 1, yi) * u;
    const bottom = at(xi, yi + 1) * (1 - u) + at(xi + 1, yi + 1) * u;
    return top * (1 - v) + bottom * v;
  };
}

function hexRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbHex(rgb) {
  return `#${rgb.map((c) => Math.max(0, Math.min(255, Math.round(c))).toString(16).padStart(2, "0")).join("")}`;
}

// Lay `tint` over `hex` at `alpha`.
function blend(hex, tint, alpha) {
  const a = hexRgb(hex);
  const b = hexRgb(tint);
  return rgbHex(a.map((c, i) => c + (b[i] - c) * alpha));
}

function luminance(hex) {
  const [r, g, b] = hexRgb(hex);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

// Very dark coats are lifted a little so the outline still shows.
function liftDark(hex) {
  const l = luminance(hex);
  return l < 0.2 ? blend(hex, "#9a90a0", (0.2 - l) * 2.2) : hex;
}

// --- building the shape -------------------------------------------------------------

const GRID_W = 96; // wide enough for a grown dragon
const GRID_H = 60;
const GROUND = 56;

function makeGrid() {
  return Array.from({ length: GRID_H }, () => new Array(GRID_W).fill(null));
}

function put(grid, x, y, cell) {
  if (y >= 0 && y < GRID_H && x >= 0 && x < GRID_W) grid[y][x] = cell;
}

function fillEllipse(grid, cx, cy, rx, ry, label) {
  for (let y = Math.floor(cy - ry - 1); y <= Math.ceil(cy + ry + 1); y++) {
    for (let x = Math.floor(cx - rx - 1); x <= Math.ceil(cx + rx + 1); x++) {
      const nx = (x + 0.5 - cx) / rx;
      const ny = (y + 0.5 - cy) / ry;
      if (nx * nx + ny * ny <= 1) put(grid, x, y, { l: label, nx, ny });
    }
  }
}

// Legs and other boxes: rounded across their width, flat top to bottom.
function fillRect(grid, x, y, w, h, label) {
  const x0 = Math.round(x);
  const y0 = Math.round(y);
  const x1 = Math.round(x + w);
  const y1 = Math.round(y + h);
  for (let j = y0; j < y1; j++) {
    for (let i = x0; i < x1; i++) {
      const nx = x1 - x0 > 1 ? ((i + 0.5 - x0) / (x1 - x0)) * 2 - 1 : 0;
      put(grid, i, j, { l: label, nx: nx * 0.8, ny: 0 });
    }
  }
}

// A filled triangle from three points; lit as one rounded piece.
function fillTri(grid, pts, label) {
  const [a, b, c] = pts;
  const minY = Math.floor(Math.min(a[1], b[1], c[1]));
  const maxY = Math.ceil(Math.max(a[1], b[1], c[1]));
  const minX = Math.floor(Math.min(a[0], b[0], c[0]));
  const maxX = Math.ceil(Math.max(a[0], b[0], c[0]));
  const mx = (a[0] + b[0] + c[0]) / 3;
  const my = (a[1] + b[1] + c[1]) / 3;
  const half = Math.max(1, (maxX - minX) / 2);
  const halfY = Math.max(1, (maxY - minY) / 2);
  const side = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  for (let y = minY; y <= maxY; y++) {
    for (let x = minX; x <= maxX; x++) {
      const p = [x + 0.5, y + 0.5];
      const s1 = side(a, b, p);
      const s2 = side(b, c, p);
      const s3 = side(c, a, p);
      if ((s1 >= 0 && s2 >= 0 && s3 >= 0) || (s1 <= 0 && s2 <= 0 && s3 <= 0)) {
        put(grid, x, y, { l: label, nx: (p[0] - mx) / half, ny: (p[1] - my) / halfY });
      }
    }
  }
}

// A thick line (a row of circles): tails, horns. Lit like a tube.
function fillStroke(grid, points, r, label) {
  for (let k = 0; k < points.length - 1; k++) {
    const [x1, y1] = points[k];
    const [x2, y2] = points[k + 1];
    const steps = Math.max(1, Math.ceil(Math.hypot(x2 - x1, y2 - y1) * 2));
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      fillEllipse(grid, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r, r, label);
    }
  }
}

// Relabel cells of `from` inside a test (for tips, socks, hooves).
function relabel(grid, from, to, test) {
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (c && from.includes(c.l) && test(x, y, c)) c.l = to;
    }
  }
}

// Tidy the silhouette: fill one-pixel notches and shave one-pixel bumps off
// the big round parts, so outlines run smooth instead of lumpy. Thin parts
// (legs, tails, ears) are left alone.
const SMOOTHED = new Set(["body", "head", "wool", "chest", "face", "neck", "cap", "shell"]);
function smoothEdges(grid) {
  const at = (x, y) => (grid[y] && grid[y][x]) || null;
  for (let pass = 0; pass < 2; pass++) {
    const fills = [];
    const shaves = [];
    for (let y = 1; y < GRID_H - 1; y++) {
      for (let x = 1; x < GRID_W - 1; x++) {
        const near = [at(x - 1, y), at(x + 1, y), at(x, y - 1), at(x, y + 1)];
        const filled = near.filter(Boolean);
        const c = grid[y][x];
        if (!c && filled.length >= 3) {
          const donor = filled.find((n) => SMOOTHED.has(n.l));
          if (donor) fills.push([x, y, { ...donor }]);
        } else if (c && SMOOTHED.has(c.l) && filled.length <= 1) {
          shaves.push([x, y]);
        }
      }
    }
    for (const [x, y, cell] of fills) grid[y][x] = cell;
    for (const [x, y] of shaves) grid[y][x] = null;
  }
}

// Re-light every `label` cell as one rounded shape (its bounding box), so a
// body built from several overlapping ellipses doesn't show their seams.
function relight(grid, label) {
  let minX = GRID_W;
  let maxX = -1;
  let minY = GRID_H;
  let maxY = -1;
  grid.forEach((row, y) =>
    row.forEach((c, x) => {
      if (!c || c.l !== label) return;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    })
  );
  if (maxX < 0) return;
  const cx = (minX + maxX + 1) / 2;
  const cy = (minY + maxY + 1) / 2;
  const rx = Math.max(1, (maxX - minX + 1) / 2);
  const ry = Math.max(1, (maxY - minY + 1) / 2);
  grid.forEach((row, y) =>
    row.forEach((c, x) => {
      if (!c || c.l !== label) return;
      c.nx = (x + 0.5 - cx) / rx;
      c.ny = (y + 0.5 - cy) / ry;
    })
  );
}

// The ears gene (-1..1) as a size: the smallest ears are the recipe's size,
// the biggest 40% bigger.
function earScale(shape) {
  return 1 + ((shape.ears || 0) + 1) * 0.2;
}

const half = (v) => Math.round(v * 2) / 2;

// Lays out every part for one pet at one stage. Returns the grid plus the
// spots the face needs.
function buildPet(genes, stage, frame) {
  const R = PET_RECIPES[genes.species] || PET_RECIPES.fox;
  const shape = genes.shape || { length: 0, height: 0, ears: 0, tail: 0 };
  const grid = makeGrid();
  const s = stage.body;
  const hs = stage.head;
  const ls = stage.leg;
  const skin = R.face ? "skin" : null; // sheep: legs and face aren't wool

  const rx = R.body.rx * s + shape.length / 2;
  const ry = R.body.ry * s + shape.height / 4;
  const legLen = Math.max(R.leg.min, Math.round(R.leg.len * ls + shape.height / 2));
  const legW = R.leg.w === 1 ? 1 : Math.max(R.leg.w > 2 ? 2 : 1, Math.round(R.leg.w * Math.max(s, 0.75)));
  const farOffset = R.leg.gap ? legW + 1 : 1.5; // gap: the far leg shows on its own
  const cx = 32;
  const cy = GROUND - legLen - ry * 0.55;
  const step = frame % 2; // walking: legs take turns lifting

  // legs: a far pair (behind the body) and a near pair
  const backX = cx - rx * 0.62;
  const frontX = cx + rx * 0.45;
  const legTop = cy;
  const leg = (x, lift, label) => fillRect(grid, x, legTop - lift, legW, GROUND - legTop, label);
  const farLeg = skin ? "farskin" : "farleg";
  const nearLeg = skin || "leg";
  leg(backX + farOffset, step ? 0 : 1, farLeg);
  leg(frontX + farOffset, step ? 1 : 0, farLeg);

  // tail, behind the body
  const tailLen = R.tail.len * s * (1 + shape.tail * 0.25);
  const tw = Math.max(0.8, (R.tail.w * Math.max(s, 0.6)) / 2);
  const tx = cx - rx + 1;
  const ty = cy - ry * 0.35;
  const wag = frame % 2;
  if (R.tail.type === "s") {
    fillStroke(grid, [[tx, ty], [tx - tailLen * 0.35, ty + tailLen * 0.05], [tx - tailLen * 0.5, ty - tailLen * 0.4], [tx - tailLen * 0.35 - wag, ty - tailLen * 0.8]], tw, "tail");
  } else if (R.tail.type === "up" || R.tail.type === "flag") {
    const lean = R.tail.type === "flag" ? 0.2 : 0.5;
    fillStroke(grid, [[tx, ty], [tx - tailLen * lean - wag, ty - tailLen * 0.85]], tw, "tail");
  } else if (R.tail.type === "bushy") {
    const tcx = tx - tailLen * 0.5;
    const tcy = ty + 1.5 - wag;
    fillEllipse(grid, tcx, tcy, tailLen * 0.58, Math.max(1.6, R.tail.w * Math.max(s, 0.6) * 0.75), "tail");
    if (R.tail.tip) relabel(grid, ["tail"], "tip", (x) => x < tcx - tailLen * 0.3);
  } else if (R.tail.type === "cotton" || R.tail.type === "stub") {
    const r = Math.max(1.4, R.tail.w * Math.max(s, 0.6) * 0.7);
    fillEllipse(grid, tx - 0.5, ty - 0.5, r, r, R.tail.type === "cotton" ? "cotton" : "tail");
  }

  // body, then wool on top of it
  fillEllipse(grid, cx, cy, rx, ry, R.wool ? "wool" : "body");
  if (R.wool) {
    const r = 2.6 * Math.max(s, 0.62);
    const n = Math.max(5, Math.round(rx / 1.8));
    for (let i = 0; i <= n; i++) {
      const a = Math.PI * (-0.05 + (1.1 * i) / n);
      fillEllipse(grid, cx - Math.cos(a) * rx * 0.92, cy - Math.sin(a) * ry * 0.92, r, r, "wool");
    }
    for (const t of [0.25, 0.5, 0.75]) fillEllipse(grid, cx - rx + 2 * rx * t, cy + ry * 0.75, r * 0.9, r * 0.8, "wool");
  }

  // near legs, in front of the body
  leg(backX - 0.5, step ? 1 : 0, nearLeg);
  leg(frontX - 0.5, step ? 0 : 1, nearLeg);
  if (R.hindFoot) {
    fillEllipse(grid, backX + 1.5, GROUND - 1.2, Math.max(2, 3.2 * s), 1.4, "leg"); // the big bunny foot
  }
  // hooves and socks: the bottom of each leg
  const hoofH = Math.max(1, Math.round(legLen * 0.2));
  if (R.hooves) {
    relabel(grid, ["leg", "skin"], "hoof", (x, y) => y >= GROUND - hoofH);
    relabel(grid, ["farleg", "farskin"], "farhoof", (x, y) => y >= GROUND - hoofH);
  }
  if (R.socks) {
    const sockH = Math.max(1, Math.round(legLen * 0.45));
    relabel(grid, ["leg"], "sock", (x, y) => y >= GROUND - sockH);
    relabel(grid, ["farleg"], "farsock", (x, y) => y >= GROUND - sockH);
  }

  // neck and head
  const hrx = R.head.rx * hs;
  const hry = R.head.ry * hs;
  const hx = cx + rx * 0.8 + R.head.dx * s;
  let hy = cy - ry * 0.6 - hry * 0.3 + R.head.dy * s;
  if (R.neck) {
    const nl = R.neck.len * s;
    const nw = Math.max(2.5, R.neck.w * Math.max(s, 0.7));
    fillRect(grid, hx - nw / 2 - 0.5, hy - nl, nw, nl + ry * 0.7, "neck");
    hy -= nl;
  }
  if (R.chestFluff) fillEllipse(grid, hx - 0.5, cy - ry * 0.3, Math.max(2, 2.8 * s), Math.max(2, 3.2 * s), "chest");
  const headLabel = R.face ? "face" : "head";

  // ears: the far one first, behind the head
  const es = R.ears.size * hs * earScale(shape);
  const ear = (offset, label) => {
    const ex = hx + offset;
    const top = hy - hry * 0.6;
    if (R.ears.type === "pointy") {
      const w = es * 0.5 * (R.ears.w || 1);
      fillTri(grid, [[ex - w, top + 1], [ex + w, top + 1], [ex - w * 0.15, top - es]], label);
    } else if (R.ears.type === "long") {
      fillEllipse(grid, ex - 0.8, top - es * 0.45, Math.max(1.3, 1.8 * hs), es * 0.6, label);
    } else if (R.ears.type === "banana") {
      fillStroke(grid, [[ex, top + 1], [ex - 0.6, top - es * 0.5], [ex + 0.6, top - es]], Math.max(0.9, 1.1 * hs), label);
    } else if (R.ears.type === "floppy") {
      fillEllipse(grid, ex - hrx * 0.45, hy + es * 0.1, Math.max(1.4, es * 0.33), es * 0.62, label);
    } else if (R.ears.type === "side") {
      fillEllipse(grid, ex - hrx * 0.7, hy - hry * 0.35, es * 0.6, Math.max(1, es * 0.28), label);
    }
  };
  const earLabel = R.face ? "face" : "ear";
  if (R.ears.type !== "floppy" && R.ears.type !== "side") ear(-hrx * 0.5, R.face ? "face" : "farear");

  if (R.head.heart) {
    fillEllipse(grid, hx, hy - hry * 0.15, hrx, hry * 0.78, headLabel);
    fillTri(grid, [[hx - hrx * 0.92, hy - hry * 0.1], [hx + hrx * 0.98, hy - hry * 0.1], [hx + hrx * 0.3, hy + hry * 0.95]], headLabel);
  } else {
    fillEllipse(grid, hx, hy, hrx, hry, headLabel);
  }
  // the snout: a point (fox), a box (dog, goat), or a little round muzzle
  const sl = R.snout.len * hs;
  const sr = Math.max(1.3, R.snout.r * hs);
  const sy = hy + hry * 0.3;
  const snoutLabel = R.face ? "face" : "snout";
  let noseAt;
  if (R.snout.pointy) {
    fillTri(grid, [[hx + hrx * 0.4, sy - sr], [hx + hrx * 0.4, sy + sr], [hx + hrx * 0.8 + sl, sy + sr * 0.5]], snoutLabel);
    noseAt = [Math.round(hx + hrx * 0.8 + sl - 1), Math.round(sy + sr * 0.3)];
  } else if (R.snout.square) {
    fillRect(grid, hx + hrx * 0.3, sy - sr, hrx * 0.6 + sl, sr * 2, snoutLabel);
    noseAt = [Math.round(hx + hrx * 0.9 + sl - 1), Math.round(sy - sr)];
  } else {
    fillEllipse(grid, hx + hrx * 0.65 + sl * 0.4, sy, sl * 0.5 + sr * 0.7, sr, snoutLabel);
    noseAt = [Math.round(hx + hrx * 0.65 + sl * 0.9 + sr * 0.5), Math.round(sy - sr * 0.4)];
  }
  if (R.beard) fillTri(grid, [[hx + hrx * 0.3, sy + sr - 0.5], [hx + hrx * 0.9, sy + sr - 0.5], [hx + hrx * 0.4, sy + sr + 3.5 * hs]], "beard");
  ear(hrx * 0.05, earLabel);
  if (R.wool) {
    // the wool cap on top of the head
    const r = 2.2 * Math.max(hs, 0.7);
    fillEllipse(grid, hx - hrx * 0.5, hy - hry * 0.75, r, r * 0.9, "cap");
    fillEllipse(grid, hx + hrx * 0.15, hy - hry * 0.95, r * 0.9, r * 0.8, "cap");
  }
  if (R.horns) {
    const hl = 3.6 * hs;
    fillStroke(grid, [[hx - hrx * 0.1, hy - hry * 0.8], [hx - hrx * 0.1 - hl * 0.5, hy - hry * 0.8 - hl * 0.75], [hx - hrx * 0.1 - hl, hy - hry * 0.8 - hl * 0.6]], 0.55, "horn");
  }
  if (R.ears.tips) relabel(grid, ["ear", "farear"], "eartip", (x, y) => y < hy - hry * 0.6 - es * 0.72);

  return {
    grid,
    R,
    headX: hx,
    eye: [Math.round(hx + hrx * 0.25), Math.round(hy - hry * 0.2)],
    nose: noseAt,
    mouth: [Math.round(hx + hrx * 0.9 + sl * 0.6), Math.round(sy + sr * 0.6)],
    center: [cx, cy],
    scale: s,
  };
}

// --- painting --------------------------------------------------------------------------

// Each fur pixel's place in the pattern (lower = primary).
function patternField(genes, built) {
  const coat = genes.coat;
  const noise = valueNoise(genes.seed);
  const noise2 = valueNoise(genes.seed ^ 0x5bd1e995);
  const [cx, cy] = built.center;
  const s = built.scale;
  // splotch: lower -> smaller dots (faster noise), 1 -> big patches
  const freq = 0.32 - 0.24 * coat.splotch;
  return (x, y) => {
    // markings live in grown-up coordinates so they grow with the pet
    const u = (x - cx) / s;
    const v = (y - cy) / s;
    const n = noise(u * freq + 100, v * freq + 100) * 0.7 + noise2(u * freq * 2.1, v * freq * 2.1) * 0.3;
    switch (coat.pattern) {
      case "spots":
        return n * 0.6 + noise2(u * freq * 2.2, v * freq * 2.2) * 0.6;
      case "stripes":
        return Math.sin((u * 0.9 + n * 6) * (0.35 + 0.5 * (1 - coat.splotch))) * 0.5 + n * 0.5;
      case "belly":
        return v / 12 + n * (0.15 + 0.5 * (1 - coat.splotch));
      case "points":
        return Math.hypot(u / 1.3, v) / 12 + n * 0.25;
      default:
        return n;
    }
  };
}

// Lighting band for a cell: 1 highlight, 0 base, -1 shade, -2 deep shade.
function band(cell, below) {
  const nx = Math.max(-1, Math.min(1, cell.nx));
  const ny = Math.max(-1, Math.min(1, cell.ny));
  const nz = Math.sqrt(Math.max(0, 1 - nx * nx - ny * ny));
  const d = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2];
  let b = d > 0.82 ? 1 : d > 0.38 ? 0 : d > 0.02 ? -1 : -2;
  if (FAR.has(cell.l)) b -= 1;
  if (!below) b = Math.min(b, -1); // underneath: always in shade
  return Math.max(-2, b);
}

function applyBand(hex, b) {
  const dark = luminance(hex) < 0.3;
  if (b === 1) return blend(hex, LIGHT_TINT, dark ? 0.16 : 0.13);
  if (b === -1) return blend(hex, SHADOW_TINT, dark ? 0.08 : 0.1);
  if (b === -2) return blend(hex, SHADOW_TINT, dark ? 0.15 : 0.19);
  return hex;
}

// --- coats that follow the body (designs) -----------------------------------------
// Each pattern places the second (and third) color by body region instead of
// pure noise: belly/tuxedo on the chest, belly and paws; points on the ears,
// paws and tail; tabby stripes around the body, legs and tail; patches big
// and spread out; spots on the back and sides; a mask (dogs) a dark cap
// and back over a light face, chest and legs. The body, legs and tail are
// ranked together so each color still gets its share. The head is painted
// on its own and the face (eyes to mouth) stays one clean color, apart from
// a tidy muzzle on belly and points coats; stripes and patches may mark the
// forehead, but never right up against the eyes.

const HEAD_PARTS = new Set(["head", "ear", "farear", "fold", "snout", "cap", "flop", "mane", "tuft"]);

function coatValue(pattern, label, x, y, geo, n, splotch) {
  const u = (x - geo.cx) / geo.rx;
  const v = (y - geo.cy) / geo.ry;
  const t = Math.max(0, Math.min(1, (y - geo.legTop) / Math.max(1, GROUND - geo.legTop)));
  const [tx, ty, tl] = geo.tail;
  const d = Math.max(0, Math.min(1, Math.hypot(x - tx, y - ty) / Math.max(1, tl)));
  const leg = label === "leg" || label === "farleg";
  const tail = label === "tail";
  switch (pattern) {
    case "belly":
      if (leg) return 0.3 + t;
      if (tail) return -0.6 + d * 0.2;
      return v + Math.max(0, u - 0.35) * 1.2 + n * 0.12;
    case "points":
      if (leg) return t * 1.2;
      if (tail) return 0.1 + d;
      return -0.6 + Math.hypot(u * 0.6, v * 0.4) + n * 0.1;
    case "stripes": {
      const k = 2.2 + (1 - splotch) * 3;
      if (leg) return Math.sin(t * Math.PI * 2.5);
      if (tail) return Math.sin(d * Math.PI * 4.5);
      return Math.sin((u * k + v * 0.35 + n * 0.6) * Math.PI);
    }
    case "spots":
      if (leg || tail || v > 0.35) return -1 + n * 0.1;
      return n;
    case "mask": // a dark cap, back and tail; a light chest, belly and legs
      if (leg) return 0.5 + t;
      if (tail) return -0.5 + Math.max(0, (y - ty) / Math.max(1, tl)) * 0.5;
      return v * 1.1 + Math.max(0, u - 0.2) * 1.4 + n * 0.1;
    default: // patches
      return n;
  }
}

function paintCoat(out, grid, genes, built, hex) {
  if (built.fire) return paintFire(out, grid, genes, built, hex);
  if (built.fish) return paintFish(out, grid, genes, built, hex);
  // species with their own real-life coats paint them (patterns can share names)
  const own = {
    cat: [CAT_PATTERNS, paintCat], bunny: [BUNNY_PATTERNS, paintBunny], fox: [FOX_PATTERNS, paintFox],
    sheep: [SHEEP_PATTERNS, paintSheep], goat: [GOAT_PATTERNS, paintGoat], llama: [LLAMA_PATTERNS, paintLlama],
    turtle: [TURTLE_PATTERNS, paintTurtle], lizard: [LIZARD_PATTERNS, paintLizard], snake: [SNAKE_PATTERNS, paintSnake],
    dragon: [DRAGON_PATTERNS, paintDragon], unicorn: [UNICORN_PATTERNS, paintUnicorn],
  }[genes.species];
  if (own && own[0].has(genes.coat.pattern)) return own[1](out, grid, genes, built, hex);
  const geo = built.geo;
  const coat = genes.coat;
  const pattern = coat.pattern;
  const noise = valueNoise(genes.seed);
  const noise2 = valueNoise(genes.seed ^ 0x5bd1e995);
  const s = built.scale;
  const freq = 0.32 - 0.24 * coat.splotch;
  const spotsFreq = freq * 4.5; // many small spots, not a few blobs
  const n = (x, y) => {
    const u = (x - geo.cx) / s;
    const v = (y - geo.cy) / s;
    if (pattern === "spots") return noise2(u * spotsFreq, v * spotsFreq);
    return noise(u * freq + 100, v * freq + 100) * 0.75 + noise2(u * freq * 2, v * freq * 2) * 0.25;
  };
  const second = hex[1] && coat.shares[1] > 0 ? hex[1] : hex[0];

  // the body, legs and tail, ranked together
  const pool = [];
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (c && FUR.has(c.l) && !HEAD_PARTS.has(c.l)) pool.push([coatValue(pattern, c.l, x, y, geo, n(x, y), coat.splotch), x, y]);
    }
  }
  pool.sort((a, b) => a[0] - b[0]);
  const cut1 = Math.round(pool.length * coat.shares[0]);
  const cut2 = cut1 + Math.round(pool.length * coat.shares[1]);
  const colorAt = (i) => (i < cut1 ? hex[0] : i < cut2 || !hex[2] ? second : hex[2]);
  pool.forEach(([, x, y], i) => (out[y][x] = colorAt(i)));
  const t1 = cut1 < pool.length ? pool[cut1][0] : Infinity;
  const t2 = cut2 < pool.length ? pool[cut2][0] : Infinity;
  const byValue = (v) => (v >= t2 && hex[2] ? hex[2] : v >= t1 ? second : hex[0]);

  // the head: the face stays clean
  const fb = geo.faceBox;
  const [hx] = geo.head;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !HEAD_PARTS.has(c.l)) continue;
      const inFace = fb && x >= fb.x0 && x <= fb.x1 && y >= fb.y0 && y <= fb.y1;
      const forehead = fb && y < fb.y0 - 1;
      const ear = c.l !== "head";
      let color = hex[0];
      const m = geo.muzzle;
      const muzzle = (m && y >= m.top && Math.abs(x - m.c) <= 3) || c.l === "snout";
      if (pattern === "belly") {
        if (muzzle || (fb && y > fb.y1)) color = second;
      } else if (pattern === "points") {
        if (muzzle || ear) color = second;
      } else if (pattern === "mask") {
        if (!ear && fb && y >= fb.y0) color = second; // the light face below a dark cap
      } else if (pattern === "stripes") {
        // a cat's tabby "M" on the forehead
        if (genes.species === "cat" && forehead && !ear && Math.sin((x - hx) * 1.4) > 0.55) color = second;
      } else if (pattern === "patches") {
        if ((forehead || ear) && !inFace) color = byValue(n(x, y));
      }
      out[y][x] = color;
    }
  }
}

// A species' chosen design. Breed species assemble it: the pet's breed,
// with any part a mix borrowed from another breed.
function speciesDesign(genes) {
  const design = PET_DESIGNS[genes.species];
  if (design && design.fromGenes) return design.fromGenes(genes);
  if (!design || !design.breeds) return design;
  const shape = genes.shape || {};
  const breeds = design.breeds;
  const base = breeds[shape.breed] || Object.values(breeds)[0];
  const mixed = { ...base };
  for (const [part, donor] of Object.entries(shape.mix || {})) if (breeds[donor]) mixed[part] = breeds[donor][part];
  return mixed;
}

// --- bunny coats: real rabbit patterns -----------------------------------------------
// Painted in three separate passes so each stays clean:
//   1. body (body, haunch, legs, feet, cotton tail): the only pass with patches
//   2. head: fixed shapes only -- butterfly, blaze, eye rings, nose smudge, chin
//   3. ears: solid, to suit the pattern
// The lighter of the two picked colors plays the light part (band, blaze,
// underside) and the darker the color, whichever was picked first. The rolled
// shares only nudge how much shows (patch size, band width). A rare third
// color makes tri-color patches on broken coats.

const BUNNY_PATTERNS = new Set(["self", "agouti", "broken", "dutch", "himalayan", "tan", "english"]);
const BUNNY_BODY = new Set(["body", "fluff", "leg", "farleg", "cotton"]);
const BUNNY_HEAD = new Set(["head", "snout", "mane"]);
const BUNNY_EARS = new Set(["ear", "farear", "flop", "fold"]);

function paintBunny(out, grid, genes, built, hex) {
  const coat = genes.coat;
  const pattern = coat.pattern;
  const geo = built.geo;
  const face = built.face;
  const at = (x, y) => (grid[y] && grid[y][x]) || null;
  const [c0, c1] = [hex[0], hex[1] || hex[0]];
  const light = luminance(c0) >= luminance(c1) ? c0 : c1;
  const dark = light === c0 ? c1 : c0;
  const accent = hex[2];
  const main = pattern === "self" ? c0 : dark;
  const amount = coat.shares[1] || 0; // nudges patch size and band width
  const noise = valueNoise(genes.seed);
  const noise2 = valueNoise(genes.seed ^ 0x5bd1e995);
  const s = built.scale;
  built.coatDone = true; // the cotton tail is painted here, not a fixed white
  const tick = (x, y) => ((Math.imul(x * 31 + y * 977, 2654435761) ^ genes.seed) >>> 0) % 1000 / 1000;

  // body extents (it faces right: the front is at maxX)
  let minX = GRID_W;
  let maxX = -1;
  let minY = GRID_H;
  let maxY = -1;
  const topAt = {};
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || c.l !== "body") continue;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
      if (topAt[x] === undefined) topAt[x] = y;
    }
  }
  const bw = Math.max(1, maxX - minX);
  const bh = Math.max(1, maxY - minY);

  // 1. the body
  const patchCut = 0.62 - amount * 0.5; // more second color -> bigger patches
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !BUNNY_BODY.has(c.l)) continue;
      const fx = (x - minX) / bw; // 0 rump .. 1 chest
      const fy = (y - minY) / bh; // 0 back .. 1 belly
      const leg = c.l === "leg" || c.l === "farleg";
      const spine = topAt[x] !== undefined && y - topAt[x] <= 1 && c.l === "body";
      let color = main;
      switch (pattern) {
        case "agouti":
          if (c.l === "cotton" || (fy > 0.82 && fx > 0.35 && !leg)) color = light;
          else if (tick(x, y) < 0.07) color = blend(dark, light, 0.35); // ticking
          break;
        case "tan":
          if (c.l === "cotton" || (fy > 0.75 && !leg)) color = light;
          break;
        case "broken": {
          const u = (x - geo.cx) / s;
          const v = (y - geo.cy) / s;
          const n = noise(u * 0.16 + 50, v * 0.16 + 50) * 0.75 + noise2(u * 0.3, v * 0.3) * 0.25;
          color = light;
          if (spine || (c.l !== "cotton" && !leg && n > patchCut)) color = accent && noise2(u * 0.12 + 9, v * 0.12) > 0.55 ? accent : dark;
          break;
        }
        case "dutch": {
          const band = 0.42 + Math.max(-0.08, Math.min(0.12, (amount - 0.25) * 0.4)); // front share that's white
          color = fx > 1 - band || (leg && fx > 0.55) ? light : dark;
          if (c.l === "leg" && y >= GROUND - 1 && fx < 0.55) color = light; // white "stops" on the hind feet
          break;
        }
        case "himalayan":
          color = leg || c.l === "cotton" ? dark : light;
          break;
        case "english": {
          color = light;
          const chain = Math.abs(fy - 0.55) < 0.12 && Math.floor((fx * bw) / 3) % 2 === 0 && fx > 0.15 && fx < 0.85;
          if (spine || chain) color = dark;
          break;
        }
        default: // self
          if (c.l === "cotton") color = blend(main, "#ffffff", 0.25);
      }
      out[y][x] = color;
    }
  }

  // 2. the head: clean, fixed shapes only
  const eyeCells = new Set();
  for (const e of face.eyes) {
    const rows = EYE_SHAPES[e.size] || EYE_SHAPES.duo;
    rows.forEach((row, j) => [...row].forEach((ch, i) => ch !== "." && eyeCells.add(`${e.x + i},${e.y + j}`)));
  }
  const nearEye = (x, y) => {
    if (eyeCells.has(`${x},${y}`)) return false;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) if (eyeCells.has(`${x + dx},${y + dy}`)) return true;
    return false;
  };
  const noses = face.pink.length ? face.pink : face.nose ? [[face.nose.x, face.nose.y]] : [[Math.round(geo.head[0]), Math.round(geo.head[1])]];
  const nx = noses.reduce((a, [x]) => a + x, 0) / noses.length;
  const ny = Math.min(...noses.map(([, y]) => y));
  const eyeTop = face.eyes.length ? Math.min(...face.eyes.map((e) => e.y)) : ny - 3;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !BUNNY_HEAD.has(c.l)) continue;
      const dx = Math.abs(x - nx);
      const butterfly = (y >= ny - 2 && y <= ny + 1 && dx <= 2 + (ny - y) * 0.7) || (y >= ny - 3 && y <= ny && dx <= 1);
      let color = main;
      switch (pattern) {
        case "agouti":
        case "tan":
          if (y > ny + 2) color = light; // a light chin
          else if (nearEye(x, y)) color = blend(main, light, pattern === "tan" ? 0.6 : 0.45); // soft eye rings
          if (pattern === "tan" && dx <= 2 && y >= ny - 1 && y <= ny + 1) color = light; // around the nostrils
          if (pattern === "agouti" && color === main && tick(x, y) < 0.05 && !nearEye(x, y)) color = blend(dark, light, 0.35);
          break;
        case "broken":
          color = butterfly || nearEye(x, y) ? dark : light;
          break;
        case "english":
          color = butterfly || nearEye(x, y) ? dark : light;
          if (Math.abs(x - (nx - 4)) <= 0.5 && y === ny + 1) color = dark; // the cheek spot
          break;
        case "dutch": {
          // a white blaze up the nose between colored cheeks, a white muzzle
          const blaze = (y >= eyeTop - 2 && dx <= 1) || (y >= ny - 1 && dx <= 2.5) || y > ny + 1;
          color = blaze ? light : dark;
          break;
        }
        case "himalayan": {
          const smudge = ((x - nx) / 2.6) ** 2 + ((y - ny - 0.5) / 1.8) ** 2 <= 1;
          color = smudge ? dark : light;
          break;
        }
        default:
          break;
      }
      out[y][x] = color;
    }
  }

  // 3. the ears: solid, to suit the pattern (the pink stripe goes on later)
  const earColor = pattern === "self" ? main : pattern === "tan" || pattern === "agouti" ? dark : dark;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !BUNNY_EARS.has(c.l)) continue;
      let color = earColor;
      if (pattern === "agouti") {
        // dark rims along the top and outer edge
        const isEar = (n) => n && BUNNY_EARS.has(n.l);
        if (!isEar(at(x, y - 1)) || !isEar(at(x - 1, y)) || !isEar(at(x + 1, y))) color = blend(dark, PET_OUTLINE, 0.3);
      }
      out[y][x] = color;
    }
  }
}

// --- fox coats: real fox patterns ---------------------------------------------------
// Three passes like bunnies (body, head, ears), and the fox marks -- socks,
// ear tips, the tail tip -- colored to suit the coat. Red and cross foxes
// wear the first pick as their coat (the second for the light bib or the dark
// cross, or a shade of the coat if it doesn't fit); silver and marble go by
// light and dark; arctic foxes wear the first pick all over.
//   red: a light bib, belly, cheeks and muzzle
//   cross: a dark cross over the shoulders and down the back, dark legs
//   silver: dark, frosted with light tips
//   arctic: one color all over, marks only a shade off
//   marble: light, with dark streaks and a dark mask round the eyes

const FOX_PATTERNS = new Set(["red", "cross", "silver", "arctic", "marble"]);
const FOX_BODY = new Set(["body", "chest", "leg", "farleg", "sock", "farsock", "tail", "tip"]);
const FOX_HEAD = new Set(["head", "snout"]);
const FOX_EARS = new Set(["ear", "farear", "eartip"]);
// Fixed-color marks a species painter may color itself.
const PAINTED_MARKS = new Set(["cotton", "sock", "farsock", "tip", "eartip", "face", "skin", "farskin"]);

function paintFox(out, grid, genes, built, hex) {
  built.coatDone = true;
  const pattern = genes.coat.pattern;
  const geo = built.geo;
  const face = built.face;
  const [c0, c1] = [hex[0], hex[1] || hex[0]];
  const lightC = luminance(c0) >= luminance(c1) ? c0 : c1;
  const darkC = lightC === c0 ? c1 : c0;
  const arctic = pattern === "arctic";
  const cream = blend(c0, "#fbf6ec", 0.7);
  let main = c0;
  let light = luminance(c1) > luminance(c0) ? c1 : cream; // red and cross: the first pick is the coat
  let dark = luminance(c1) < luminance(c0) ? c1 : blend(c0, PET_OUTLINE, 0.55);
  if (pattern === "silver" || pattern === "marble") {
    // these two go by light and dark: silver is dark with light frost, marble the reverse
    main = pattern === "silver" ? darkC : lightC;
    light = lightC;
    dark = pattern === "silver" ? blend(darkC, PET_OUTLINE, 0.35) : darkC;
  } else if (arctic) {
    light = blend(c0, "#ffffff", 0.35);
    dark = blend(c0, PET_OUTLINE, 0.25);
  }
  const accent = hex[2];
  const noise = valueNoise(genes.seed);
  const s = built.scale;
  const tick = (x, y) => ((Math.imul(x * 31 + y * 977, 2654435761) ^ genes.seed) >>> 0) % 1000 / 1000;

  let minX = GRID_W;
  let maxX = -1;
  let minY = GRID_H;
  let maxY = -1;
  const topAt = {};
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || c.l !== "body") continue;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
      if (topAt[x] === undefined) topAt[x] = y;
    }
  }
  const bw = Math.max(1, maxX - minX);
  const bh = Math.max(1, maxY - minY);
  const shoulder = minX + bw * 0.68;

  // 1. the body, legs and tail
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !FOX_BODY.has(c.l)) continue;
      const fx = (x - minX) / bw;
      const fy = (y - minY) / bh;
      const sock = c.l === "sock" || c.l === "farsock";
      const leg = c.l === "leg" || c.l === "farleg" || sock;
      const bib = c.l === "body" && ((fx > 0.6 && fy > 0.35) || (fy > 0.8 && fx > 0.3));
      const spine = c.l === "body" && topAt[x] !== undefined && y - topAt[x] <= 1;
      let color = main;
      if (c.l === "tip") color = light;
      else if (sock) color = dark;
      else switch (pattern) {
        case "red":
          if (bib) color = light;
          break;
        case "cross":
          if (leg || spine || (c.l === "body" && Math.abs(x - shoulder) <= 1)) color = accent || dark;
          else if (bib) color = light;
          break;
        case "silver":
          if (bib) color = blend(main, light, 0.4);
          else if (tick(x, y) < 0.16) color = blend(main, light, 0.6); // frost
          break;
        case "marble": {
          const u = (x - geo.cx) / s;
          const v = (y - geo.cy) / s;
          const streak = Math.sin(u * 0.9 + noise(u * 0.2 + 30, v * 0.2) * 5) > 0.55;
          if ((streak && !bib && !leg) || spine) color = dark;
          if (leg) color = blend(dark, main, 0.4);
          break;
        }
        default: // arctic
          if (bib) color = light;
      }
      out[y][x] = color;
    }
  }

  // 2. the head: white cheeks and muzzle on most coats, never across the eyes
  const [hx, hy, hrx, hry] = geo.head;
  const eyeRows = face.eyes.length ? [Math.min(...face.eyes.map((e) => e.y)), Math.max(...face.eyes.map((e) => e.y + 1))] : [0, 0];
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !FOX_HEAD.has(c.l)) continue;
      const cheek = y > eyeRows[1] + 1 && Math.abs(x - hx) > hrx * 0.45;
      const muzzle = c.l === "snout" && y > eyeRows[1];
      let color = main;
      if (pattern === "marble") {
        const mask = y >= eyeRows[0] - 1 && y <= eyeRows[1] + 1 && Math.abs(x - hx) > 1;
        color = mask ? dark : light;
      } else if (pattern === "silver") {
        color = cheek || muzzle ? blend(main, light, 0.4) : main;
      } else if (cheek || muzzle) {
        color = light;
      }
      out[y][x] = color;
    }
  }

  // 3. the ears: the coat color, with dark tips (just a shade off on arctic foxes)
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !FOX_EARS.has(c.l)) continue;
      out[y][x] = c.l === "eartip" ? dark : pattern === "marble" ? dark : main;
    }
  }
}

// --- sheep coats: wool color plus real breeds' face and leg markings ---------------
// Three passes: the wool body and legs, the head (bare face and the wool
// tuft), the ears. The first pick is the wool; the face takes the second
// pick when it suits (darker for black faces, lighter for pale ones) or a
// shade of the wool. Jacob and badger coats go by light and dark.

// Wool texture for fleecy coats: rows of little curls, each a touch darker
// on its lower right and lighter on its upper left, over the cells with the
// given labels. `strength` scales it (1 for sheep). Returns the curl lookup
// (-1 shadow, 1 highlight, 0 neither) for parts painted later.
function woolCurls(out, grid, s, minY, labels, strength) {
  const cs = Math.max(3, Math.round(4 * s + 0.5));
  const rowH = cs * 0.8;
  const curl = (x, y) => {
    const row = Math.floor((y - minY) / rowH);
    const off = (row % 2) * cs * 0.5;
    const col = Math.floor((x - off) / cs);
    const dx = (x + 0.5 - (col * cs + off + cs / 2)) / (cs / 2);
    const dy = (y + 0.5 - (minY + row * rowH + rowH / 2)) / (rowH / 2);
    const d = Math.hypot(dx, dy);
    if (d > 0.8 && dx + dy > 0.2) return -1;
    if (d < 0.5 && dx + dy < -0.3) return 1;
    return 0;
  };
  const set = new Set(labels);
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !set.has(c.l) || !out[y][x]) continue;
      const k = curl(x, y);
      if (k < 0) out[y][x] = blend(out[y][x], SHADOW_TINT, 0.17 * strength);
      else if (k > 0) out[y][x] = blend(out[y][x], LIGHT_TINT, 0.22 * strength);
    }
  }
  return curl;
}

const SHEEP_PATTERNS = new Set(["whiteface", "blackface", "self", "speckled", "jacob", "badger", "valais"]);

function paintSheep(out, grid, genes, built, hex) {
  built.coatDone = true;
  const pattern = genes.coat.pattern;
  const geo = built.geo;
  const face = built.face;
  const [c0, c1] = [hex[0], hex[1] || hex[0]];
  const lightC = luminance(c0) >= luminance(c1) ? c0 : c1;
  const darkC = lightC === c0 ? c1 : c0;
  const darkFace = luminance(c1) < luminance(c0) - 0.15 ? c1 : blend(c0, PET_OUTLINE, 0.62);
  const paleFace = luminance(c1) > luminance(c0) ? blend(c1, "#f4dcd0", 0.3) : blend(c0, "#f4dcd0", 0.55);
  const jacobOrBadger = pattern === "jacob" || pattern === "badger";
  const wool = jacobOrBadger ? lightC : c0;
  const spotC = jacobOrBadger ? (luminance(darkC) < luminance(lightC) - 0.15 ? darkC : blend(lightC, PET_OUTLINE, 0.62)) : darkFace;
  const faceColor = {
    whiteface: paleFace, blackface: darkFace, self: blend(c0, PET_OUTLINE, 0.35), speckled: paleFace,
    jacob: spotC, badger: paleFace, valais: blend(darkFace, PET_OUTLINE, 0.3),
  }[pattern];
  const legColor = { jacob: paleFace, badger: spotC, valais: paleFace }[pattern] || faceColor;
  const noise = valueNoise(genes.seed);
  const s = built.scale;
  const tick = (x, y) => ((Math.imul(x * 31 + y * 977, 2654435761) ^ genes.seed) >>> 0) % 1000 / 1000;

  let minY = GRID_H;
  let maxY = -1;
  let legTop = GRID_H;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c) continue;
      if (c.l === "body") {
        minY = Math.min(minY, y);
        maxY = Math.max(maxY, y);
      }
      if (c.l === "skin" || c.l === "farskin") legTop = Math.min(legTop, y);
    }
  }

  // 1. wool and legs
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c) continue;
      if (c.l === "body" || c.l === "fluff" || c.l === "tail") {
        let color = wool;
        if (pattern === "jacob") {
          const u = (x - geo.cx) / s;
          const v = (y - geo.cy) / s;
          if (noise(u * 0.17 + 40, v * 0.17 + 40) > 0.6) color = spotC;
        } else if (pattern === "badger" && (y - minY) / Math.max(1, maxY - minY) > 0.72) {
          color = spotC; // the dark belly
        }
        out[y][x] = color;
      } else if (c.l === "skin" || c.l === "farskin") {
        let color = legColor;
        const t = (y - legTop) / Math.max(1, GROUND - legTop);
        if (pattern === "valais" && t < 0.5) color = faceColor; // the dark knees
        if ((pattern === "speckled" || pattern === "jacob") && tick(x, y) < 0.3) color = spotC;
        out[y][x] = color;
      }
    }
  }

  const curl = woolCurls(out, grid, s, minY, ["body", "fluff", "tuft", "tail"], 1);

  // 2. the head: the bare face, and the tuft (wool)
  const eyes = face.eyes;
  const eyeTop = eyes.length ? Math.min(...eyes.map((e) => e.y)) : 0;
  const eyeBottom = eyes.length ? Math.max(...eyes.map((e) => e.y + 1)) : 0;
  const eyeCols = eyes.flatMap((e) => [e.x, e.x + 1]);
  const [hx] = geo.head;
  let chin = 0;
  grid.forEach((row, y) => row.forEach((c) => c && c.l === "face" && !c.isEar && (chin = Math.max(chin, y))));
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c) continue;
      if (c.l === "tuft") {
        out[y][x] = curl(x, y) < 0 ? blend(wool, SHADOW_TINT, 0.17) : curl(x, y) > 0 ? blend(wool, LIGHT_TINT, 0.22) : wool;
        continue;
      }
      if (c.l !== "face" || c.isEar) continue;
      let color = faceColor;
      const nearEyes = eyes.some((e) => Math.abs(x - e.x - 0.5) <= 2 && Math.abs(y - e.y - 0.5) <= 2);
      switch (pattern) {
        case "speckled":
          if (nearEyes && tick(x, y) < 0.35) color = spotC;
          else if (y > eyeBottom + 1 && tick(x, y) < 0.18) color = spotC;
          break;
        case "jacob":
          if (Math.abs(x - hx) <= 1 && y >= eyeTop - 2) color = paleFace; // the white blaze
          break;
        case "badger": {
          // dark stripes from the forehead down over each eye, and a dark chin
          const stripe = eyeCols.some((ex) => Math.abs(x - ex) <= 0.5) && y <= eyeBottom + 2;
          if (stripe || y >= chin - 1) color = spotC;
          break;
        }
        default:
          break;
      }
      out[y][x] = color;
    }
  }

  // 3. the ears
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !c.isEar) continue;
      let color = faceColor;
      if (pattern === "jacob" || pattern === "badger") color = spotC;
      if (pattern === "speckled" && tick(x, y) < 0.4) color = spotC;
      out[y][x] = color;
    }
  }
}

// --- cat coats: real cat patterns ---------------------------------------------------
// Three passes (body, head, ears). The face stays clean: at most a small
// white chin, a thin blaze, or a colorpoint's mask -- never a block over
// the muzzle. The first pick is the coat; white parts take the second pick
// if it's lighter (else a cream of the coat), stripes the second if darker
// (else a deep shade of the coat).

const CAT_PATTERNS = new Set(["tabby", "solid", "tuxedo", "bicolor", "calico", "tortie", "colorpoint", "van"]);
const CAT_BODY = new Set(["body", "fluff", "chest", "leg", "farleg", "tail"]);
const CAT_HEAD = new Set(["head", "snout", "cap", "tuft"]);
const CAT_EARS = new Set(["ear", "farear", "fold"]);

function paintCat(out, grid, genes, built, hex) {
  built.coatDone = true;
  const pattern = genes.coat.pattern;
  const geo = built.geo;
  const face = built.face;
  const [c0, c1] = [hex[0], hex[1] || hex[0]];
  const main = c0;
  const white = luminance(c1) > luminance(c0) + 0.1 ? c1 : blend(c0, "#fbf6ec", 0.72);
  const stripe = luminance(c1) < luminance(c0) - 0.1 ? c1 : blend(c0, PET_OUTLINE, 0.42);
  const second = c1 !== c0 ? c1 : stripe; // calico and tortie's other color
  const accent = hex[2];
  const noise = valueNoise(genes.seed);
  const noise2 = valueNoise(genes.seed ^ 0x5bd1e995);
  const s = built.scale;
  const splotch = genes.coat.splotch || 0.8;

  let minX = GRID_W;
  let maxX = -1;
  let minY = GRID_H;
  let maxY = -1;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || c.l !== "body") continue;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
  }
  const bw = Math.max(1, maxX - minX);
  const bh = Math.max(1, maxY - minY);
  const [tx, ty, tl] = geo.tail;

  // 1. the body, legs and tail
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !CAT_BODY.has(c.l)) continue;
      const fx = (x - minX) / bw; // 0 rump .. 1 chest
      const fy = (y - minY) / bh; // 0 back .. 1 belly
      const u = (x - geo.cx) / s;
      const v = (y - geo.cy) / s;
      const leg = c.l === "leg" || c.l === "farleg";
      const tail = c.l === "tail";
      const paw = leg && y >= GROUND - 2;
      const d = Math.hypot(x - tx, y - ty) / Math.max(1, tl);
      let color = main;
      switch (pattern) {
        case "tabby": {
          const k = 2.2 + (1 - splotch) * 2.5;
          const band = leg ? Math.sin(((y - geo.legTop) / 2.2) * Math.PI) : tail ? Math.sin(d * Math.PI * 5) : Math.sin((u * k * 0.25 + v * 0.08 + noise(u * 0.2, v * 0.2) * 0.5) * Math.PI);
          if (band > 0.45) color = stripe;
          break;
        }
        case "tuxedo":
          if (paw || (!leg && !tail && ((fx > 0.6 && fy > 0.3) || fy > 0.78))) color = white;
          break;
        case "bicolor":
          if (paw || (!tail && !leg && fy > 0.6) || (!tail && noise(u * 0.18 + 20, v * 0.18) > 0.72)) color = white;
          break;
        case "calico": {
          color = white;
          if (noise(u * 0.17 + 7, v * 0.17) > 0.55) color = main;
          else if (noise2(u * 0.17 + 3, v * 0.17 + 9) > 0.58) color = accent || second;
          if (paw) color = white;
          break;
        }
        case "tortie":
          if (noise2(u * 0.45 + 11, v * 0.45) > 0.5) color = second;
          break;
        case "colorpoint":
          color = blend(white, main, Math.max(0, Math.min(0.3, (0.5 - fy) * 0.5))); // a touch darker along the back
          if (leg && y >= geo.legTop + (GROUND - geo.legTop) * 0.35) color = main;
          if (tail) color = d > 0.25 ? main : blend(white, main, 0.5);
          break;
        case "van":
          color = tail ? main : white;
          break;
        default: // solid
          break;
      }
      out[y][x] = color;
    }
  }

  // 2. the head: a clean face
  const [hx, hy, hrx, hry] = geo.head;
  const eyes = face.eyes;
  const eyeTop = eyes.length ? Math.min(...eyes.map((e) => e.y)) : hy - 2;
  const eyeBottom = eyes.length ? Math.max(...eyes.map((e) => e.y + (EYE_SHAPES[e.size] || ["", ""]).length - 1)) : hy;
  const mouthRows = [...face.smile, ...face.pink, ...face.noseDark].map(([, y]) => y);
  const mouthBottom = mouthRows.length ? Math.max(...mouthRows) : (face.nose ? face.nose.y : eyeBottom + 2);
  const noseTop = mouthRows.length ? Math.min(...mouthRows) : (face.nose ? face.nose.y : eyeBottom + 1);
  const front = Math.round(hx);
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !CAT_HEAD.has(c.l)) continue;
      const dx = Math.abs(x - front);
      const chin = y > mouthBottom && dx <= hrx * 0.5;
      const forehead = y < eyeTop - 1;
      const u = (x - geo.cx) / s;
      const v = (y - geo.cy) / s;
      let color = main;
      switch (pattern) {
        case "tabby":
          // the "M": short stripes on the forehead, a row of fur clear of the eyes
          if (forehead && y < eyeTop - 1 && (dx === 0 || Math.abs(dx - 2) < 0.6) && y >= eyeTop - 4) color = stripe;
          if (chin) color = white;
          break;
        case "tuxedo":
          if (chin) color = white;
          break;
        case "bicolor":
          if (chin || (dx <= 0.6 && y >= eyeTop - 2 && y < noseTop)) color = white; // a thin blaze
          break;
        case "calico":
          if (forehead) color = noise(u * 0.17 + 7, v * 0.17) > 0.55 ? main : noise2(u * 0.17 + 3, v * 0.17 + 9) > 0.58 ? accent || second : white;
          else if (chin) color = white;
          break;
        case "tortie":
          if (forehead && noise2(u * 0.45 + 11, v * 0.45) > 0.5) color = second;
          break;
        case "colorpoint": {
          // a dark mask around the eyes, nose and mouth; the rest light
          const mask = ((x - hx) / (hrx * 0.7)) ** 2 + ((y - (eyeTop + mouthBottom) / 2) / (hry * 0.62)) ** 2 <= 1;
          color = mask ? main : white;
          break;
        }
        case "van":
          color = forehead && dx > 1 ? main : white; // a colored cap split by a white blaze
          break;
        default:
          break;
      }
      out[y][x] = color;
    }
  }

  // 3. the ears
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !CAT_EARS.has(c.l)) continue;
      const u = (x - geo.cx) / s;
      const v = (y - geo.cy) / s;
      let color = main;
      if (pattern === "calico") color = noise(u * 0.17 + 7, v * 0.17) > 0.5 ? main : accent || second;
      out[y][x] = color;
    }
  }
}

// --- goat coats: real goat markings -------------------------------------------------
// Three passes (body and neck, head and beard, ears). Face stripes run in
// the fur just inside the eyes, never across them. The first pick is the
// coat; light parts take the second pick if it's lighter (else a cream of
// the coat), dark parts the second if darker (else a deep shade), and black
// and tan points the second pick.

const GOAT_PATTERNS = new Set(["solid", "swiss", "chamoisee", "coublanc", "sundgau", "blacktan", "spotted", "boer"]);
const GOAT_BODY = new Set(["body", "neck", "leg", "farleg", "tail", "fluff"]);
const GOAT_HEAD = new Set(["head", "snout", "beard"]);
const GOAT_EARS = new Set(["ear", "farear", "flop"]);

function paintGoat(out, grid, genes, built, hex) {
  built.coatDone = true;
  const pattern = genes.coat.pattern;
  const geo = built.geo;
  const face = built.face;
  const [c0, c1] = [hex[0], hex[1] || hex[0]];
  const main = c0;
  const light = luminance(c1) > luminance(c0) + 0.1 ? c1 : blend(c0, "#fbf6ec", 0.72);
  const dark = luminance(c1) < luminance(c0) - 0.1 ? c1 : blend(c0, PET_OUTLINE, 0.5);
  const tan = c1 !== c0 ? c1 : blend(c0, "#c8a06a", 0.6);
  const noise2 = valueNoise(genes.seed ^ 0x5bd1e995);
  const s = built.scale;

  let minX = GRID_W;
  let maxX = -1;
  let minY = GRID_H;
  let maxY = -1;
  const topAt = {};
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || c.l !== "body") continue;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
      if (topAt[x] === undefined) topAt[x] = y;
    }
  }
  const bw = Math.max(1, maxX - minX);
  const bh = Math.max(1, maxY - minY);
  const legTop = geo.legTop;

  // 1. the body, neck, legs and tail
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !GOAT_BODY.has(c.l)) continue;
      const fx = (x - minX) / bw; // 0 rump .. 1 chest
      const fy = (y - minY) / bh;
      const leg = c.l === "leg" || c.l === "farleg";
      const lowLeg = leg && y >= legTop + (GROUND - legTop) * 0.45;
      const belly = c.l === "body" && fy > 0.78;
      const spine = c.l === "body" && topAt[x] !== undefined && y - topAt[x] <= 1;
      const front = c.l === "neck" || (c.l === "body" && fx > 0.55) || (leg && x > geo.cx);
      let color = main;
      switch (pattern) {
        case "swiss":
          if (lowLeg) color = light;
          break;
        case "chamoisee":
          if (spine || belly || lowLeg) color = dark;
          break;
        case "coublanc":
          color = front ? light : main;
          break;
        case "sundgau":
          if (lowLeg || belly) color = light;
          break;
        case "blacktan":
          if (lowLeg || belly) color = tan;
          break;
        case "spotted": {
          const u = (x - geo.cx) / s;
          const v = (y - geo.cy) / s;
          if (!leg && noise2(u * 0.5 + 5, v * 0.5) > 0.7) color = light;
          break;
        }
        case "boer":
          color = c.l === "neck" ? main : light;
          break;
        default:
          break;
      }
      out[y][x] = color;
    }
  }

  // 2. the head and beard
  const [hx] = geo.head;
  const eyes = face.eyes;
  const eyeTop = eyes.length ? Math.min(...eyes.map((e) => e.y)) : 0;
  const eyeBottom = eyes.length ? Math.max(...eyes.map((e) => e.y + 1)) : 0;
  const c = Math.round(hx);
  // front: the fur columns just inside each eye; side: a line above the eye running forward
  const stripeCols = built.geo.faceBox && V_FRONT(face) ? eyes.map((e) => (e.x < c ? e.x + 2 : e.x - 1)) : [];
  const sideEyeX = eyes.length ? eyes[0].x : c;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const cell = grid[y][x];
      if (!cell || !GOAT_HEAD.has(cell.l)) continue;
      const stripe = stripeCols.length
        ? stripeCols.includes(x) && y >= eyeTop - 3
        : y === eyeTop - 1 && x >= sideEyeX - 1;
      const muzzle = cell.l === "snout" && y > eyeBottom;
      const eyebrow = eyes.some((e) => y === e.y - 1 && x >= e.x && x <= e.x + 1);
      let color = main;
      switch (pattern) {
        case "swiss":
        case "sundgau":
          if (stripe || muzzle) color = light;
          break;
        case "chamoisee":
          if (muzzle || (stripeCols.length && Math.abs(x - c) <= 0.6 && y >= eyeTop - 3)) color = dark;
          break;
        case "coublanc":
          color = light;
          break;
        case "blacktan":
          if (muzzle || eyebrow) color = tan;
          break;
        case "boer":
          color = main;
          break;
        default:
          break;
      }
      out[y][x] = color;
    }
  }

  // 3. the ears
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const cell = grid[y][x];
      if (!cell || !GOAT_EARS.has(cell.l)) continue;
      const isEar = (n) => n && GOAT_EARS.has(n.l);
      const rim = !isEar(grid[y - 1] && grid[y - 1][x]) || !isEar(grid[y + 1] && grid[y + 1][x]);
      let color = pattern === "coublanc" ? light : main;
      if (pattern === "swiss" && rim) color = light;
      out[y][x] = color;
    }
  }
}

// --- llama coats: real llama and alpaca coats ----------------------------------------
// Three passes (body, neck and legs; head and topknot; ears), then wool curls
// over the fleece (stronger on woolly alpacas). The face stays clean.

const LLAMA_PATTERNS = new Set(["solid", "paint", "guanaco", "twotone", "appaloosa", "tuxedo", "roan", "saddle"]);
const LLAMA_BODY = new Set(["body", "fluff", "neck", "leg", "farleg", "tail"]);
const LLAMA_HEAD = new Set(["head", "snout", "tuft"]);
const LLAMA_EARS = new Set(["ear", "farear"]);

function paintLlama(out, grid, genes, built, hex) {
  built.coatDone = true;
  const pattern = genes.coat.pattern;
  const geo = built.geo;
  const face = built.face;
  const [c0, c1] = [hex[0], hex[1] || hex[0]];
  const main = c0;
  const light = luminance(c1) > luminance(c0) + 0.1 ? c1 : blend(c0, "#fbf6ec", 0.72);
  const dark = luminance(c1) < luminance(c0) - 0.1 ? c1 : blend(c0, PET_OUTLINE, 0.5);
  const noise = valueNoise(genes.seed);
  const noise2 = valueNoise(genes.seed ^ 0x5bd1e995);
  const s = built.scale;
  // an even scatter (a simple hash of the pixel), with no lines in it
  const tick = (x, y) => {
    let h = (Math.imul(x, 374761393) + Math.imul(y, 668265263) + genes.seed) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  };

  let minX = GRID_W;
  let maxX = -1;
  let minY = GRID_H;
  let maxY = -1;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || c.l !== "body") continue;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
  }
  const bh = Math.max(1, maxY - minY);
  const legTop = geo.legTop;
  // the neck's front edge, per row (for a tuxedo's bib)
  const neckFront = {};
  grid.forEach((row, y) => row.forEach((c, x) => c && c.l === "neck" && (neckFront[y] = Math.max(neckFront[y] ?? -1, x))));

  // 1. body, neck, legs, tail
  let topY = GRID_H;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !LLAMA_BODY.has(c.l)) continue;
      topY = Math.min(topY, y);
      const fy = (y - minY) / bh;
      const u = (x - geo.cx) / s;
      const v = (y - geo.cy) / s;
      const leg = c.l === "leg" || c.l === "farleg";
      const lowLeg = leg && y >= legTop + (GROUND - legTop) * 0.45;
      const barrel = c.l === "body" || c.l === "fluff";
      let color = main;
      switch (pattern) {
        case "paint":
          if (noise(u * 0.13 + 30, v * 0.13) > 0.56) color = light;
          break;
        case "guanaco":
          if ((barrel && fy > 0.7) || lowLeg) color = light;
          break;
        case "twotone":
          if (barrel) color = light;
          break;
        case "appaloosa":
          color = light;
          if (!leg && noise2(u * 0.55 + 4, v * 0.55) > 0.72) color = main;
          break;
        case "tuxedo":
          if (lowLeg || (c.l === "neck" && x >= (neckFront[y] ?? 0) - 1) || (barrel && fy > 0.25 && x > geo.cx + geo.rx * 0.55)) color = light;
          break;
        case "roan":
          if (tick(x, y) < 0.3) color = blend(main, light, 0.7);
          break;
        case "saddle":
          color = barrel && fy < 0.45 ? main : light;
          break;
        default:
          break;
      }
      out[y][x] = color;
    }
  }

  // 2. head and topknot: a clean face
  const [hx] = geo.head;
  const eyes = face.eyes;
  const eyeBottom = eyes.length ? Math.max(...eyes.map((e) => e.y + 1)) : 0;
  const front = eyes.length > 1;
  const headBase = { appaloosa: light, saddle: light, guanaco: dark }[pattern] || main;
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !LLAMA_HEAD.has(c.l)) continue;
      let color = c.l === "tuft" ? blend(headBase, light, 0.25) : headBase;
      if (pattern === "guanaco" && c.l === "snout" && y > eyeBottom + 1) color = light; // light lips
      if (pattern === "tuxedo" && (front ? Math.abs(x - hx) <= 0.6 && c.l !== "tuft" : c.l === "snout")) color = light; // a blaze
      if (pattern === "roan" && c.l !== "snout" && tick(x, y) < 0.3) color = blend(main, light, 0.7);
      out[y][x] = color;
    }
  }

  // 3. the ears
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || !LLAMA_EARS.has(c.l)) continue;
      out[y][x] = pattern === "paint" || pattern === "appaloosa" ? main : headBase;
    }
  }

  // wool ripples over the fleece: light on llamas, stronger on woolly alpacas
  const fleecy = built.geo.woolly ? 1 : 0.6;
  woolCurls(out, grid, s, topY, ["body", "fluff", "neck", "tail", "tuft"], fleecy);
}

// --- turtle coats: patterns over the shell's plates ----------------------------------
// Both picks (and a rare third color) go into the shell, laid out in rows of
// plates with seams; the pattern decides how each plate is colored. The skin
// is its own olive-to-gray shade worked out from the shell, with markings to
// suit the pattern (speckles or light stripes on the head, neck and legs).
//   plain    plates in the coat color, darker seams
//   flecks   dark plates with light flecks (box turtle)
//   rings    a light ring round each plate's darker middle
//   star     dark plates with light rays from each middle (star tortoise)
//   mottled  irregular two-tone marbling
//   checker  plates alternating the two colors
//   keel     a dark stripe down the middle of the shell, a bright rim

const TURTLE_PATTERNS = new Set(["plain", "flecks", "rings", "star", "mottled", "checker", "keel"]);
const TURTLE_SKIN = new Set(["head", "neck", "leg", "farleg", "tail"]);

function paintTurtle(out, grid, genes, built, hex) {
  built.coatDone = true;
  const pattern = genes.coat.pattern;
  const geo = built.geo;
  const [c0, c1] = [hex[0], hex[1] || hex[0]];
  const lightC = luminance(c1) > luminance(c0) + 0.08 ? c1 : blend(c0, "#f0e0a0", 0.6);
  const darkC = luminance(c1) < luminance(c0) - 0.08 ? c1 : blend(c0, PET_OUTLINE, 0.45);
  const accent = hex[2];
  const noise = valueNoise(genes.seed);
  const tick = (x, y) => {
    let h = (Math.imul(x, 374761393) + Math.imul(y, 668265263) + genes.seed) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  };
  // star and ring plates need room for their rays and rings
  const roomy = pattern === "star" || pattern === "rings" ? 1.45 : 1;
  const ps = Math.max(3, Math.round(geo.plate * built.scale * roomy + 0.5));
  const rowH = ps * 0.8;
  const top = geo.base - geo.ry;
  const plateAt = (x, y) => {
    const row = Math.floor((y - top) / rowH);
    const off = (row % 2) * ps * 0.5;
    const col = Math.floor((x - geo.cx - off) / ps);
    const dx = (x + 0.5 - (geo.cx + off + col * ps + ps / 2)) / (ps / 2);
    const dy = (y + 0.5 - (top + row * rowH + rowH / 2)) / (rowH / 2);
    return { row, col, dx, dy, seam: Math.abs(dx) > 0.78 || dy > 0.72, d: Math.hypot(dx, dy) };
  };
  const darkShell = { flecks: darkC, star: darkC }[pattern] || c0;
  const seamOf = (base) => blend(base, PET_OUTLINE, 0.4);

  // the shell
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c || c.l !== "shell") continue;
      const p = plateAt(x, y);
      let base = darkShell;
      if (pattern === "checker") base = (p.row + p.col) % 2 ? c1 : c0;
      if (pattern === "mottled") base = noise((x - geo.cx) * 0.3 + 50, (y - top) * 0.3) > 0.52 ? lightC : c0;
      if (pattern === "keel" && Math.abs(x + 0.5 - geo.cx) <= Math.max(1, ps * 0.3)) base = darkC;
      let color = base;
      if (p.seam) color = seamOf(base);
      else {
        switch (pattern) {
          case "flecks":
            if (tick(x, y) < 0.22) color = lightC;
            break;
          case "rings":
            color = p.d > 0.42 ? blend(c0, lightC, 0.55) : blend(c0, PET_OUTLINE, 0.2);
            break;
          case "star": {
            // rays out from each plate's middle at 0, 60 and 120 degrees
            const a = Math.atan2(p.dy, p.dx);
            const ray = [0, Math.PI / 3, (2 * Math.PI) / 3].some((r) => Math.abs(Math.sin(a - r)) * p.d < 0.18);
            if (ray || p.d < 0.2) color = accent || lightC;
            break;
          }
          default:
            if (p.d < 0.42 && pattern !== "mottled") color = blend(base, LIGHT_TINT, 0.18);
        }
      }
      out[y][x] = color;
    }
  }

  // the rim, and the skin
  const rim = pattern === "checker" ? c1 : pattern === "keel" ? blend(lightC, "#fff4d8", 0.3) : blend(c0, "#e8d8a0", 0.45);
  const skinBase = blend(luminance(c0) < luminance(c1) ? c0 : c1, "#8a8660", 0.55);
  const skinMark = blend(skinBase, "#f0e0a0", 0.6);
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c) continue;
      if (c.l === "rim") {
        out[y][x] = rim;
      } else if (TURTLE_SKIN.has(c.l)) {
        let color = skinBase;
        if ((pattern === "flecks" || pattern === "star") && tick(x, y) < 0.18) color = skinMark; // speckles
        if ((pattern === "rings" || pattern === "keel") && y % 3 === 0 && c.l !== "tail") color = skinMark; // light stripes
        out[y][x] = color;
      }
    }
  }
}

// --- lizard coats -----------------------------------------------------------------
// Passes: body and tail, then head and legs, then the crest and dewlap. The
// first pick is the coat and the second the markings; the crest spines and a
// dewlap take the third color if there is one, else a bright second.
//   plain     the coat, a lighter belly (side views)
//   banded    dark rings round the tail, faint bands on the body (iguana)
//   striped   light stripes along the body, a bright tail (skink)
//   spotted   rows of light spots with dark middles (monitor)
//   chameleon broad bands of the two colors across the body
//   twotone   head, neck and shoulders in the second color
//   speckled  fine light and dark speckles

const LIZARD_PATTERNS = new Set(["plain", "banded", "striped", "spotted", "chameleon", "twotone", "speckled"]);

function paintLizard(out, grid, genes, built, hex) {
  built.coatDone = true;
  const pattern = genes.coat.pattern;
  const geo = built.geo;
  const top = !!geo.fromAbove;
  const [c0, c1] = [hex[0], hex[1] || hex[0]];
  const main = c0;
  const mark = c1 !== c0 ? c1 : blend(c0, "#f0e0a0", 0.55);
  const light = blend(main, "#f0e8c8", 0.5);
  const dark = blend(main, PET_OUTLINE, 0.45);
  const bright = hex[2] || blend(mark, "#ffffff", 0.15);
  const noise = valueNoise(genes.seed);
  const tick = (x, y) => {
    let h = (Math.imul(x, 374761393) + Math.imul(y, 668265263) + genes.seed) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  };
  const [tx, ty, tl] = geo.tail;
  const s = built.scale;
  const { cx, cy, rx, ry } = geo;

  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c) continue;
      const l = c.l;
      if (l !== "body" && l !== "tail" && l !== "neck" && l !== "head" && l !== "limb" && l !== "leg" && l !== "farleg") continue;
      const d = Math.hypot(x + 0.5 - tx, y + 0.5 - ty) / Math.max(1, tl); // along the tail
      const across = (y + 0.5 - cy) / Math.max(1, ry); // -1 .. 1 across the body
      const along = (x + 0.5 - cx) / Math.max(1, rx); // -1 rump .. 1 shoulders
      let color = main;
      if (l === "tail") {
        if (pattern === "banded" || pattern === "chameleon") color = Math.sin(d * Math.PI * 9) > 0.35 ? dark : main;
        else if (pattern === "striped") color = mark; // a bright tail
        else if (pattern === "spotted" && noise(x * 0.5, y * 0.5) > 0.66) color = light;
        else if (pattern === "speckled" && tick(x, y) < 0.25) color = tick(y, x) < 0.5 ? light : dark;
      } else if (l === "body" || l === "neck") {
        switch (pattern) {
          case "plain":
            if (!top && across > 0.55) color = light; // a lighter belly
            break;
          case "banded":
            if (Math.sin(along * Math.PI * 3) > 0.7) color = blend(main, PET_OUTLINE, 0.2);
            break;
          case "striped": {
            // light stripes along the body: above, either side of the spine; from the side, two rows
            const stripes = top ? [-0.45, 0.45] : [-0.35, 0.25];
            if (stripes.some((st) => Math.abs(across - st) < 0.14)) color = light;
            break;
          }
          case "spotted": {
            const sx = Math.round((x - cx) / (3 * s));
            const sy = Math.round((y - cy) / (2.4 * s));
            const dd = Math.hypot(x - (cx + sx * 3 * s), y - (cy + sy * 2.4 * s));
            if ((sx + sy) % 2 === 0 && dd < 1.2 * s) color = dd < 0.5 ? dark : light;
            break;
          }
          case "chameleon":
            if (Math.floor((along + 1) * 2.5) % 2) color = mark;
            break;
          case "twotone":
            if (l === "neck" || along > 0.2) color = blend(mark, main, Math.max(0, Math.min(1, (0.6 - along) * 1.5)));
            break;
          case "speckled":
            if (tick(x, y) < 0.25) color = tick(y, x) < 0.5 ? light : dark;
            break;
          default:
            break;
        }
      } else if (l === "head") {
        color = pattern === "twotone" ? mark : main;
      } else {
        color = blend(main, PET_OUTLINE, l === "farleg" ? 0.12 : 0.05); // legs a touch darker
      }
      out[y][x] = color;
    }
  }
  // the crest and dewlap: a pop of color
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (c && (c.l === "spine" || c.l === "dewlap" || c.l === "frill")) out[y][x] = bright;
    }
  }
}

// --- snake coats -------------------------------------------------------------------
// Markings follow the body: the builder notes on each pixel how far down the
// body it is (along, in pixels from the head) and which side of the tube it
// sits on (across: -1 back .. +1 belly). The first pick is the base, the
// second the markings; a third color edges them. The neck right behind the
// head stays clean, and side-on snakes get a lighter belly band.
//   diamondback  a chain of dark diamonds down the back, edged in light
//   banded       king snake rings: wide base bands split by light and dark rings
//   saddles      corn snake blotches across the back, darker-edged
//   striped      garter stripes: a dark back, a light stripe down the side
//   speckled     fine speckles
//   plain        one color

const SNAKE_PATTERNS = new Set(["diamondback", "banded", "saddles", "striped", "speckled", "plain"]);
const SNAKE_TUBE = new Set(["body", "tail", "thin", "neck"]);

function paintSnake(out, grid, genes, built, hex) {
  built.coatDone = true;
  const pattern = genes.coat.pattern;
  const fromAbove = built.geo.fromAbove;
  const [c0, c1] = [hex[0], hex[1] || hex[0]];
  const markC = c1 !== c0 ? c1 : blend(c0, PET_OUTLINE, 0.45);
  const edge = hex[2] || blend(c0, "#f6ecc8", 0.6);
  const darkMark = blend(markC, PET_OUTLINE, 0.3);
  // a plain snake shows a third color on its belly
  const belly = hex[2] && pattern === "plain" ? hex[2] : blend(c0, "#f0e2b8", 0.55);
  const P = Math.max(6, built.geo.ry * 4.2); // the length of one repeat of the pattern, in pixels
  const tick = (x, y) => {
    let h = (Math.imul(x, 374761393) + Math.imul(y, 668265263) + genes.seed) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  };
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c) continue;
      if (FUR.has(c.l)) out[y][x] = c0;
      if (c.l === "head") {
        continue;
      }
      if (c.l === "hood") {
        out[y][x] = blend(c0, "#f6ecc8", 0.25);
        continue;
      }
      if (!SNAKE_TUBE.has(c.l) || c.along === undefined) continue;
      const u = (c.along % P) / P; // 0..1 within one repeat
      const a = c.across; // -1 back .. +1 belly
      let color = c0;
      const neck = c.along < P * 0.7; // the neck just behind the head stays clean
      const third = !!hex[2]; // a rolled third color gets more room
      switch (neck ? "plain" : pattern) {
        case "diamondback": {
          // diamonds centered a little above the middle of the side
          const dd = Math.abs(u - 0.5) * 2 + Math.abs(a + 0.15) * 0.6;
          if (dd < (third ? 0.5 : 0.6)) color = markC;
          else if (dd < (third ? 0.98 : 0.86)) color = edge;
          break;
        }
        case "banded":
          // with a third color: king snake rings (base, edge, marking, edge)
          if (third) color = u < 0.4 ? c0 : u < 0.6 ? edge : u < 0.8 ? markC : edge;
          else color = u < 0.55 ? c0 : u < 0.68 ? edge : u < 0.88 ? darkMark : edge;
          break;
        case "saddles":
          // square blotches over the back, edged darker (or in the third
          // color), belly left clear
          if (a < 0.45 && Math.abs(u - 0.5) < (third ? 0.34 : 0.3)) {
            const rim = Math.abs(u - 0.5) > (third ? 0.2 : 0.2) || a < -0.75;
            color = rim ? (third ? edge : darkMark) : markC;
          }
          break;
        case "striped":
          // a dark back with a light stripe running down the side
          if (Math.abs(a - 0.05) < (third ? 0.36 : 0.28)) color = edge;
          else if (a < -0.3) color = markC;
          break;
        case "speckled":
          if (tick(x, y) < (third ? 0.3 : 0.22)) color = tick(y, x) < (third ? 0.75 : 0.5) ? edge : darkMark;
          break;
        default:
          break;
      }
      // a lighter belly band along the underside (side-on snakes); the third
      // color stays bright through it
      if (!fromAbove && pattern === "plain" && third && !neck) {
        if (a > 0.3) color = belly;
      } else if (!fromAbove && a > 0.6 && pattern !== "banded" && !(third && color === edge)) color = blend(color, belly, 0.7);
      out[y][x] = color;
    }
  }
}

// A face drawn front-on has two eyes.
function V_FRONT(face) {
  return face.eyes.length > 1;
}

const petCache = new Map();

// The finished pixels: {w, h, pix: rows of hex or null}. Cached per pet,
// growth stage, and animation frame.
// The finished pixels for one frame, cropped with a box shared by all of a
// pet's frames (see stableBox), so the pet doesn't shift as it animates.
function petPixels(genes, growth, frame = 0) {
  const stage = petStage(growth);
  const anim = genes.face && genes.face.sparkle ? frame % 36 : `${frame % 2}${frame % 9 === 8}${frame % 4 < 2}`;
  const base = `${genes.seed}|${genes.species}|${genes.variant}|${stage.id}|${JSON.stringify(genes.coat)}|${JSON.stringify(genes.shape)}|${genes.hex}`;
  const key = `${base}|${anim}`;
  if (petCache.has(key)) return petCache.get(key);
  const { out, noShadow } = petFrame(genes, growth, frame);
  const { minX, maxX, minY } = stableBox(base, genes, growth);
  const pix = out.slice(minY, GROUND + 1).map((row) => row.slice(minX, maxX + 1));
  const result = { w: maxX - minX + 1, h: GROUND + 1 - minY, pix, noShadow };
  if (petCache.size > 2000) petCache.clear();
  petCache.set(key, result);
  return result;
}

// The outline box covering a pet's walking frames (0-3), so every frame is
// cropped the same way.
const boxCache = new Map();
function stableBox(base, genes, growth) {
  if (boxCache.has(base)) return boxCache.get(base);
  let minX = GRID_W;
  let maxX = -1;
  let minY = GRID_H;
  for (const f of [0, 1, 2, 3]) {
    petFrame(genes, growth, f).out.forEach((row, y) =>
      row.forEach((c, x) => {
        if (!c) return;
        minX = Math.min(minX, x);
        maxX = Math.max(maxX, x);
        minY = Math.min(minY, y);
      })
    );
  }
  const box = { minX, maxX, minY };
  if (boxCache.size > 2000) boxCache.clear();
  boxCache.set(base, box);
  return box;
}

// One frame, uncropped: the full grid of colors.
function petFrame(genes, growth, frame) {
  const stage = petStage(growth);
  const design = (genes.variant && (PET_VARIANTS[genes.species] || [])[genes.variant - 1]) || speciesDesign(genes);
  const built = design ? buildVariant(genes, stage, frame, design) : buildPet(genes, stage, frame);
  smoothEdges(built.grid);
  const { grid, R } = built;
  const at = (x, y) => (grid[y] && grid[y][x]) || null;
  const out = Array.from({ length: GRID_H }, () => new Array(GRID_W).fill(null));
  const hex = genes.hex.map((h) => h && liftDark(h));

  // coat colors by rank: each color gets exactly its share of fur pixels
  if (built.geo) paintCoat(out, grid, genes, built, hex);
  else {
  const field = patternField(genes, built);
  const fur = [];
  for (let y = 0; y < GRID_H; y++) for (let x = 0; x < GRID_W; x++) if (grid[y][x] && FUR.has(grid[y][x].l)) fur.push([field(x, y), x, y]);
  fur.sort((a, b) => a[0] - b[0]);
  const shares = genes.coat.shares;
  const cut1 = Math.round(fur.length * shares[0]);
  const cut2 = cut1 + Math.round(fur.length * shares[1]);
  fur.forEach(([, x, y], i) => {
    out[y][x] = i < cut1 ? hex[0] : i < cut2 || !hex[2] ? hex[1] : hex[2];
  });
  }

  // a sheep's face and legs: a darker (or, on dark wool, lighter) shade of its wool
  const skinColor = luminance(hex[0]) > 0.45 ? blend(hex[0], "#3a2a28", 0.62) : blend(hex[0], "#f0e0d0", 0.35);

  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const cell = grid[y][x];
      if (!cell) continue;
      if (!FUR.has(cell.l) && !(built.coatDone && (PAINTED_MARKS.has(cell.l) || (built.painted && built.painted.has(cell.l))))) {
        out[y][x] = cell.l === "face" || cell.l === "skin" || cell.l === "farskin" ? skinColor : DERIVED[cell.l] ? DERIVED[cell.l](hex) : PET_FIXED[cell.l] || hex[0];
      }
      out[y][x] = applyBand(out[y][x], band(cell, at(x, y + 1)));
    }
  }

  // inner ears (pointy and long ones)
  if (built.innerEars || (!built.face && (R.ears.type === "pointy" || R.ears.type === "long"))) {
    for (let y = 0; y < GRID_H; y++) {
      for (let x = 0; x < GRID_W; x++) {
        const c = at(x, y);
        if (!c || c.l !== "ear") continue;
        // the rim on the side away from the face stays fur, and so does the very tip
        const isEar = (n) => n && n.l === "ear";
        const outward = x < built.headX ? -1 : 1;
        const single = !isEar(at(x - 1, y)) && !isEar(at(x + 1, y));
        const rim = (!isEar(at(x + outward, y)) && !single) || (built.earStripe && !(isEar(at(x - 1, y)) && isEar(at(x + 1, y))));
        const low = !isEar(at(x, y + 1)) || !isEar(at(x, y + 2));
        if (!rim && !low) out[y][x] = PET_FIXED.innerear;
      }
    }
  }

  // the head over the body: a soft shadow just under the chin
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = at(x, y);
      if (!built.softNeck && c && BODYISH.has(c.l) && [at(x, y - 2), at(x - 1, y - 2), at(x + 1, y - 2)].some((n) => n && HEADISH.has(n.l))) {
        out[y][x] = blend(out[y][x], SHADOW_TINT, 0.18);
      }
    }
  }

  // outlines: near-black around the silhouette; a dark shade of the fur
  // where a front part covers something behind it
  const lines = [];
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const cell = grid[y][x];
      const near = [at(x - 1, y), at(x + 1, y), at(x, y - 1), at(x, y + 1)];
      if (!cell) {
        if (near.some(Boolean)) {
          // a soft outline is a deep shade of the fur next to it; otherwise near-black
          const by = [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]].find(([i, j]) => at(i, j));
          lines.push([x, y, built.softOutline ? blend(out[by[1]][by[0]], PET_OUTLINE, built.fire ? 0.55 : 0.72) : PET_OUTLINE]);
        }
      } else if (built.fire) {
        // fire: no lines inside, it glows as one shape
      } else if (cell.l === "snout" && near.some((n) => n && n.l === "head")) {
        lines.push([x, y, blend(out[y][x], SHADOW_TINT, 0.22)]); // the muzzle: a soft edge
      } else if (!FRONT.has(cell.l) && !BLENDS_IN.has(cell.l) && near.some((n) => n && n.l !== cell.l && FRONT.has(n.l))) {
        lines.push([x, y, blend(out[y][x], SHADOW_TINT, 0.62)]);
      } else if (cell.l === "coilbase" && near.some((n) => n && n.l === "body")) {
        lines.push([x, y, blend(out[y][x], PET_OUTLINE, 0.7)]); // a snake's coils: the top tier sits on the bottom
      } else if (HEADISH.has(cell.l) && near.some((n) => n && n.l === "flop")) {
        lines.push([x, y, blend(out[y][x], SHADOW_TINT, 0.45)]); // a floppy ear over the head
      } else if (BODYISH.has(cell.l) && near.some((n) => n && HEADISH.has(n.l))) {
        lines.push([x, y, blend(out[y][x], SHADOW_TINT, built.softNeck ? 0.28 : 0.45)]);
      } else if (cell.l !== "face" && near.some((n) => n && n.l === "face")) {
        lines.push([x, y, blend(out[y][x], SHADOW_TINT, 0.55)]);
      }
    }
  }
  for (const [x, y, c] of lines) out[y][x] = c;

  // the face
  const dot = (x, y, c) => {
    if (out[y] && x >= 0 && x < GRID_W) out[y][x] = c;
  };
  const outline = (x, y) => (built.softOutline && out[y] && out[y][x] ? blend(out[y][x], PET_OUTLINE, 0.72) : PET_OUTLINE);
  if (built.face) drawFace(dot, at, built.face, genes, frame, outline);
  else {
  const [ex, ey] = built.eye;
  const iris = (genes.face && genes.face.eyes) || "#2a1c14";
  const blink = frame % 9 === 8;
  if (blink) {
    dot(ex, ey + 1, PET_OUTLINE);
    dot(ex + 1, ey + 1, PET_OUTLINE);
  } else if (R.eye === "goat") {
    // a goat's sideways pupil: a bar across a pale eye
    dot(ex - 1, ey, "#e8c060");
    dot(ex, ey, "#e8c060");
    dot(ex + 1, ey, "#e8c060");
    dot(ex - 1, ey + 1, PET_OUTLINE);
    dot(ex, ey + 1, PET_OUTLINE);
    dot(ex + 1, ey + 1, PET_OUTLINE);
  } else if (R.eye === "cat") {
    // a taller eye: dark lid, then glint and iris, then iris and pupil
    dot(ex, ey - 1, PET_OUTLINE);
    dot(ex + 1, ey - 1, PET_OUTLINE);
    dot(ex, ey, "#ffffff");
    dot(ex + 1, ey, iris);
    dot(ex, ey + 1, iris);
    dot(ex + 1, ey + 1, PET_OUTLINE);
  } else {
    dot(ex, ey, "#ffffff");
    dot(ex + 1, ey, PET_OUTLINE);
    dot(ex, ey + 1, iris);
    dot(ex + 1, ey + 1, PET_OUTLINE);
  }
  const [nx, ny] = built.nose;
  const noseColor = R.pinkNose ? PET_FIXED.pinknose : PET_FIXED.nose;
  dot(nx, ny, noseColor);
  if (R.bigNose) {
    dot(nx - 1, ny, noseColor);
    dot(nx, ny + 1, noseColor);
  }
  if (R.tongue && frame % 4 < 2) {
    const [mx, my] = built.mouth;
    dot(mx, my, PET_FIXED.tongue);
    dot(mx, my + 1, PET_FIXED.tongue);
    dot(mx - 1, my + 1, PET_FIXED.tongue);
  }

  }

  // sparkly pets glint now and then
  if (genes.face && genes.face.sparkle && frame % 4 < 2) {
    const fx = Math.round(built.center[0] + ((frame * 7) % 9) - 4);
    const fy = Math.round(built.center[1] - 2 - ((frame * 3) % 4));
    for (const [dx, dy] of [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]) {
      if (at(fx + dx, fy + dy)) dot(fx + dx, fy + dy, dx || dy ? "#fff6c8" : "#ffffff");
    }
  }

  return { out, noShadow: !!built.noShadow };
}

// Draws a pet with its feet at (x, bottom) and its left edge at x, `scale`
// px units per pet pixel, with a soft shadow on the ground. faceLeft mirrors it.
function drawPet(px, x, bottom, genes, growth, { frame = 0, faceLeft = false, scale = 1, shadow = true } = {}) {
  const { w, h, pix, noShadow } = petPixels(genes, growth, frame);
  const top = bottom - h * scale;
  if (shadow && !noShadow) {
    const sw = Math.round(w * 0.8);
    const sx = x + Math.round((w - sw) / 2) * scale;
    px(sx + scale, bottom - scale, (sw - 2) * scale, scale, "rgba(40, 24, 16, 0.28)");
    px(sx + 3 * scale, bottom, (sw - 6) * scale, scale, "rgba(40, 24, 16, 0.18)");
  }
  pix.forEach((row, j) =>
    row.forEach((c, i) => {
      if (c) px(x + (faceLeft ? w - 1 - i : i) * scale, top + j * scale, scale, scale, c);
    })
  );
}

function petSize(genes, growth) {
  const { w, h } = petPixels(genes, growth, 0);
  return { w, h };
}

// --- dragon coats: storybook looks built on real reptile markings --------------------
// The first color is the body; the second goes where the pattern says:
//   storybook  belly, wing skin, spines and spade
//   ombre      the body fades from the first color at the head to the second at
//              the tail tip, in dithered steps
//   ridgeback  a stripe down the back and tail, and the spines
//   scaled     little scale marks all over, like a monitor's beadwork
//   tiger      bands across the back and tail
//   jeweled    round gem spots along the sides, each with a shine (leopard gecko)
//   shadow     dark wings, spines and horn tips (the darker of the two colors)
// A third color is always a treasure metal: horns, spines, spade and claws, with a
// shine where the light hits. The head and face stay the first color.

const DRAGON_PATTERNS = new Set(["storybook", "ombre", "ridgeback", "scaled", "tiger", "jeweled", "shadow"]);
const DRAGON_TUBE = new Set(["body", "neck", "tail", "belly"]);
const DRAGON_SKIN = new Set(["body", "neck", "tail", "leg", "farleg", "limb", "fin"]);
const DRAGON_PAINTED = new Set(["belly", "wing", "farwing", "wingbone", "farbone", "dspine", "spade", "horn", "farhorn", "claw", "farclaw"]);
const CREAM = "#f6e2a8";

function paintDragon(out, grid, genes, built, hex) {
  built.coatDone = true;
  built.painted = DRAGON_PAINTED;
  const c1 = hex[0];
  const metal = hex[2];
  const pattern = genes.coat.pattern;
  const geo = built.geo;
  // dragons' two colors are often close: nudge the second away from the
  // first (lighter or darker, whichever it already leans) so marks still show
  let c2 = hex[1] || hex[0];
  const gap = luminance(c2) - luminance(c1);
  if (Math.abs(gap) < 0.12) c2 = blend(c2, gap >= 0 && luminance(c1) < 0.75 ? "#fff4d8" : SHADOW_TINT, 0.3 - Math.abs(gap));
  const dark = luminance(c1) < luminance(c2) ? c1 : c2;
  const s = built.scale;
  const tick = (x, y) => ((Math.imul(x * 31 + y * 977, 2654435761) ^ genes.seed) >>> 0) % 1000 / 1000;
  // each column's top and bottom of the body tube, for depth from the back
  const top = {};
  const bot = {};
  grid.forEach((row, y) =>
    row.forEach((c, x) => {
      if (!c || !DRAGON_TUBE.has(c.l)) return;
      top[x] = Math.min(top[x] ?? y, y);
      bot[x] = Math.max(bot[x] ?? y, y);
    })
  );
  const depth = (x, y) => (top[x] === undefined ? 1 : (y - top[x]) / Math.max(1, bot[x] - top[x]));
  // how far along from the head (0) to the tail tip (1)
  const [hx, hy] = geo.head;
  const tail = geo.tailEnd || [geo.cx - geo.rx * 2, GROUND];
  const along = (x, y) => Math.max(0, Math.min(1, geo.front ? (y - hy) / Math.max(1, GROUND - hy) : (hx - x) / Math.max(1, hx - tail[0])));
  const ombre = (x, y) => {
    const v = along(x, y) * 4 + ((x + y) & 1 ? 0.25 : -0.25);
    return blend(c1, c2, Math.max(0, Math.min(4, Math.floor(v))) / 4);
  };
  const pale = (c) => blend(c, CREAM, 0.5);
  // horn tips: the top part of each horn
  let hornTop = GRID_H;
  let hornBot = 0;
  grid.forEach((row, y) => row.forEach((c) => c && (c.l === "horn" || c.l === "farhorn") && ((hornTop = Math.min(hornTop, y)), (hornBot = Math.max(hornBot, y)))));
  const shine = (c, cell) => (cell.ny < -0.25 ? blend(c, "#ffffff", 0.35) : c);

  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const cell = grid[y][x];
      if (!cell) continue;
      const l = cell.l;
      const local = pattern === "ombre" ? ombre(x, y) : c1;
      const d = depth(x, y);
      let color = null;
      if (l === "head" || l === "snout") color = c1;
      else if (DRAGON_SKIN.has(l)) {
        color = local;
        const side = l !== "leg" && l !== "farleg" && l !== "limb";
        if (pattern === "ridgeback" && side && d < 0.38) color = c2;
        if (pattern === "scaled") {
          // tiny "u" scale marks in staggered rows
          const row = Math.floor(y / 3);
          const u = (x + (row % 2) * 2) % 4;
          if ((y % 3 === 0 && (u === 0 || u === 2)) || (y % 3 === 1 && u === 1)) color = blend(c1, c2, 0.85);
        }
        if (pattern === "tiger" && side && d < 0.7) {
          const P = Math.max(4, Math.round(4.5 * s));
          const phase = x + Math.round((y - (top[x] ?? y)) * 0.6);
          if (((phase % P) + P) % P < (P > 5 ? 2 : 1)) color = c2;
        }
        if (pattern === "jeweled" && side && d > 0.15 && d < 0.7) {
          const gx = Math.floor(x / 5);
          const gy = Math.floor(y / 4);
          const sx = gx * 5 + 2 + (gy % 2) * 2;
          const sy = gy * 4 + 2;
          const r = Math.hypot(x - sx, y - sy);
          if (tick(gx, gy) < 0.65 && r <= 1.2) color = r < 0.5 ? blend(c2, "#ffffff", 0.45) : c2;
        }
      } else if (l === "belly") color = pattern === "storybook" ? blend(c2, CREAM, 0.25) : pale(local);
      else if (l === "wing" || l === "farwing") {
        color = pattern === "storybook" ? blend(c2, CREAM, 0.3) : pattern === "shadow" ? blend(dark, SHADOW_TINT, 0.35) : pattern === "ombre" ? blend(c2, CREAM, 0.4) : blend(c1, CREAM, 0.45);
      } else if (l === "wingbone" || l === "farbone") color = blend(pattern === "shadow" ? dark : c1, SHADOW_TINT, pattern === "shadow" ? 0.55 : 0.4);
      else if (l === "dspine" || l === "spade") {
        color = pattern === "storybook" || pattern === "ridgeback" ? c2 : pattern === "shadow" ? blend(dark, SHADOW_TINT, 0.3) : pale(local);
        if (l === "spade" && pattern === "ombre") color = pale(c2);
        if (metal) color = shine(metal, cell);
      } else if (l === "horn" || l === "farhorn") {
        color = PET_FIXED.horn;
        if (pattern === "shadow" && y < hornTop + (hornBot - hornTop) * 0.45) color = blend(dark, SHADOW_TINT, 0.3);
        if (metal) color = shine(metal, cell);
      } else if (l === "claw" || l === "farclaw") color = metal || PET_FIXED.claw;
      if (color) out[y][x] = color;
    }
  }
}

// --- fire: a phoenix glows ------------------------------------------------------------
// Every part of the bird made of fire is shaded by how deep inside the shape it
// is: the deep flame color at the edge, the flame color, then the glow color,
// and a white-hot core where it's thickest. The depths shimmer a little from
// frame to frame. The beak, legs, eyes, ashes and egg keep their colors.
// Patterns are subtle touches on top:
//   pure       just the fire
//   wingtips   the far ends of the wings and plumes burn bright
//   embers     sparks flicker here and there across the body and wings
//   starburst  a white-hot burst with four rays on the chest
//   smoke      sooty, smoky tips on the wings and plumes

const PHOENIX_PATTERNS = new Set(["pure", "wingtips", "embers", "starburst", "smoke"]);
const FIRE_WING = new Set(["pfeather", "pfeather2", "farpfeather", "plume", "plumetip"]);
const FIRE_PARTS = new Set(["body", "breast", "head", "neck", "pfeather", "pfeather2", "farpfeather", "plume", "plumetip", "flame", "flamecore", "lick"]);

function paintFire(out, grid, genes, built, hex) {
  built.coatDone = true;
  built.painted = FIRE_PARTS;
  const flame = hex[0];
  const glow = hex[1] || blend(hex[0], "#fff0a0", 0.6);
  const frame = built.frame || 0;
  const tick = (x, y) => ((Math.imul(x * 31 + y * 977, 2654435761) ^ (genes.seed + frame * 7919)) >>> 0) % 1000 / 1000;
  const isFire = (x, y) => grid[y] && grid[y][x] && FIRE_PARTS.has(grid[y][x].l);
  // depth: steps to the nearest pixel that isn't fire (or isn't anything)
  const depth = Array.from({ length: GRID_H }, () => new Array(GRID_W).fill(0));
  let edge = [];
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      if (!isFire(x, y)) continue;
      const open = [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]].some(([i, j]) => !(grid[j] && grid[j][i]));
      if (open) {
        depth[y][x] = 1;
        edge.push([x, y]);
      }
    }
  }
  for (let d = 2; edge.length; d++) {
    const next = [];
    for (const [x, y] of edge) {
      for (const [i, j] of [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]]) {
        if (isFire(i, j) && !depth[j][i]) {
          depth[j][i] = d;
          next.push([i, j]);
        }
      }
    }
    edge = next;
  }
  const deep = blend(flame, "#160a14", 0.4);
  const hot = blend(glow, "#fffbe8", 0.55);
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      if (!isFire(x, y)) continue;
      // thin parts (no deeper pixel beside them) burn in the flame color, not
      // the deep edge; plume tips glow; deeper in, it shimmers now and then
      const d0 = depth[y][x] || 6;
      const thin = d0 === 1 && ![[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]].some(([i, j]) => depth[j] && depth[j][i] >= 2);
      const d = d0 + (d0 >= 2 && tick(x, y) < 0.1 ? 1 : 0);
      out[y][x] = grid[y][x].l === "plumetip" ? glow : thin ? flame : d <= 1 ? deep : d === 2 ? flame : d === 3 ? blend(flame, glow, 0.5) : d <= 5 ? glow : hot;
    }
  }

  const pattern = genes.coat.pattern;
  const geo = built.geo;
  if (pattern === "wingtips" || pattern === "smoke") {
    // the tips: the wing and plume pixels farthest out from the body
    const far = (x, y) => Math.hypot(x - geo.cx, (y - geo.cy) * 1.2);
    let reach = 0;
    grid.forEach((row, y) => row.forEach((c, x) => c && FIRE_WING.has(c.l) && (reach = Math.max(reach, far(x, y)))));
    grid.forEach((row, y) =>
      row.forEach((c, x) => {
        if (!c || !FIRE_WING.has(c.l) || far(x, y) < reach * 0.72) return;
        out[y][x] = pattern === "smoke" ? blend(out[y][x], "#2a2028", 0.5) : blend(glow, "#ffffff", 0.4);
      })
    );
  }
  if (pattern === "embers") {
    // bright sparks on the darker flame (they'd vanish in the glow), a new
    // scatter each frame
    for (let y = 0; y < GRID_H; y++) for (let x = 0; x < GRID_W; x++) if (isFire(x, y) && depth[y][x] >= 2 && depth[y][x] <= 3 && tick(x * 3, y) < 0.14) out[y][x] = "#fffbe8";
  }
  if (pattern === "starburst" && geo.chest) {
    // a white-hot core on the chest with four short rays
    const [sx, sy] = geo.chest;
    // a four-point star of pure white, its rays reaching into the flame
    const r = Math.max(1, 1.2 * built.scale);
    const reach = r * 3.5;
    for (let y = Math.floor(sy - reach); y <= sy + reach; y++) {
      for (let x = Math.floor(sx - reach); x <= sx + reach; x++) {
        if (!isFire(x, y)) continue;
        const dx = Math.abs(x + 0.5 - sx);
        const dy = Math.abs(y + 0.5 - sy);
        // the rays taper: wide near the middle, one pixel out at the ends
        const ray = (dx < 0.6 && dy <= reach) || (dy < 0.6 && dx <= reach) || (dx < 1.6 && dy < 1.6);
        if (ray) out[y][x] = "#ffffff";
        else if (dx + dy <= reach * 0.6) out[y][x] = blend(out[y][x], "#ffffff", 0.45);
      }
    }
  }
}

// Flames licking up off the top of a fire shape: every few columns a tongue
// of fire rises from the topmost fire pixel, its height flickering with the
// frame. `lean` tips them back (negative: to the left).
function addLicks(grid, frame, s, lean) {
  const tops = {};
  grid.forEach((row, y) => row.forEach((c, x) => c && FIRE_PARTS.has(c.l) && c.l !== "lick" && tops[x] === undefined && (tops[x] = y)));
  const xs = Object.keys(tops).map(Number).sort((a, b) => a - b);
  xs.forEach((x, i) => {
    if ((x + frame) % 3) return;
    const h = (1.6 + ((x * 7 + frame * 3) % 4) * 0.55) * Math.max(0.8, s);
    const y = tops[x];
    fillTri(grid, [[x - 0.8, y + 1], [x + 1.8, y + 1], [x + 0.5 + lean * h * 0.5, y + 1 - h]], "lick");
  });
}

// --- fish coats: a body pattern and a fin pattern -----------------------------------
// The body is the first color, its pattern in the second (and a third when one
// was rolled); the belly a touch paler; around the eye stays clean.
//   solid     one color
//   twotone   dark above, the second color below, a wavy line between
//   gradient  the first color at the head fading to the second at the tail
//   stripe    a bright band along the side from eye to tail (neon tetra; a
//             third color below it toward the tail)
//   bars      bands across the body (tiger barb, angelfish, clown loach)
//   spots     little round spots (cory, leopard danio)
//   marbled   big soft blotches (marble angel; a third color in the middle)
//   scaled    a net of scale lines (reticulated)
// All of a fish's fins wear one pattern, laid out from where each fin meets the
// body (its base) to its tip:
//   clear     pale and see-through-looking, a tint of the body
//   solid     the second color
//   edged     clear with a rim of the third color (or the second)
//   tipped    clear at the base, the second color at the tips
//   gradient  the body color at the base to the second color at the tips
//   striped   bands of the second color running across the fins
//   spotted   dots of the second color
//   rayed     pale, the rays picked out in the second color

const FISH_PATTERNS = new Set(["solid", "twotone", "gradient", "stripe", "bars", "spots", "marbled", "scaled"]);
const FISH_SKIN = new Set(["fbody", "fhead", "gill"]);
const FISH_FIN = { caudal: "caudal", cray: "caudal", dorsal: "dorsal", dray: "dorsal", anal: "anal", aray: "anal", pelvic: "pelvic", pectoral: "pectoral" };
const FISH_PAINTED = new Set([...FISH_SKIN, ...Object.keys(FISH_FIN)]);

function paintFish(out, grid, genes, built, hex) {
  built.coatDone = true;
  built.painted = FISH_PAINTED;
  const c1 = hex[0];
  const c2 = hex[1] || blend(hex[0], "#ffffff", 0.4);
  const c3 = hex[2];
  const body = genes.coat.pattern;
  const finPat = genes.coat.fins || "clear";
  const { x0, L, eye, pec } = built.fish;
  const tick = (x, y) => ((Math.imul(x * 31 + y * 977, 2654435761) ^ genes.seed) >>> 0) % 1000 / 1000;
  const noise = valueNoise(genes.seed);
  const at = (x, y) => (grid[y] && grid[y][x]) || null;
  const isSkin = (x, y) => at(x, y) && FISH_SKIN.has(at(x, y).l);
  // each column's top and bottom of the body
  const top = {};
  const bot = {};
  grid.forEach((row, y) => row.forEach((c, x) => c && FISH_SKIN.has(c.l) && ((top[x] = Math.min(top[x] ?? y, y)), (bot[x] = Math.max(bot[x] ?? y, y)))));

  const skin = (x, y) => {
    const t = Math.max(0, Math.min(1, (x + 0.5 - x0) / L)); // tail 0 .. nose 1
    const v = (y - top[x]) / Math.max(1, bot[x] - top[x]); // back 0 .. belly 1
    let c = c1;
    if (body === "twotone" && v > 0.55 + Math.sin(x * 0.8) * 0.06) c = c2;
    else if (body === "gradient") c = blend(c2, c1, Math.max(0, Math.min(4, Math.floor(t * 4 + ((x + y) & 1 ? 0.25 : -0.25)))) / 4);
    else if (body === "stripe") {
      if (v >= 0.32 && v <= 0.5 && t < 0.86) c = c2;
      else if (c3 && v > 0.5 && v <= 0.75 && t < 0.55) c = c3;
    } else if (body === "bars") {
      const P = Math.max(4, Math.round(L / 5));
      if (((x - Math.round(x0)) % P + P) % P < Math.max(1.5, P * 0.35)) c = c2;
    } else if (body === "spots") {
      // one spot per little cell, at a random spot in it, so they scatter
      const gx = Math.floor(x / 4);
      const gy = Math.floor(y / 3);
      if (x === gx * 4 + Math.floor(tick(gx, gy + 50) * 4) && y === gy * 3 + Math.floor(tick(gx + 50, gy) * 3) && tick(gx, gy) < 0.8) c = c2;
    } else if (body === "marbled") {
      const n = noise(x * 0.22 + 7, y * 0.3 + 7);
      if (n > 0.55) c = c3 && n > 0.78 ? c3 : c2;
    } else if (body === "scaled") {
      if ((((x + y) % 4) + 4) % 4 === 0 || (((x - y) % 4) + 4) % 4 === 0) c = blend(c1, c2, 0.6);
    }
    if (Math.hypot(x - eye[0], y - eye[1]) < 2.6) c = c1; // the face stays clean round the eye
    if (v > 0.72) c = blend(c, "#ffffff", 0.16); // a paler belly
    return c;
  };

  // fins: how far each fin pixel is from the body (steps through the fin)
  const dist = new Map();
  let edge = [];
  grid.forEach((row, y) => row.forEach((c, x) => c && FISH_SKIN.has(c.l) && edge.push([x, y])));
  for (let d = 1; edge.length; d++) {
    const next = [];
    for (const [x, y] of edge) {
      for (const [i, j] of [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]]) {
        const c = at(i, j);
        if (c && FISH_FIN[c.l] && FISH_FIN[c.l] !== "pectoral" && !dist.has(j * GRID_W + i)) {
          dist.set(j * GRID_W + i, d);
          next.push([i, j]);
        }
      }
    }
    edge = next;
  }
  const far = {};
  grid.forEach((row, y) =>
    row.forEach((c, x) => {
      if (!c || !FISH_FIN[c.l]) return;
      const f = FISH_FIN[c.l];
      const d = f === "pectoral" ? Math.hypot(x - pec[0], y - pec[1]) : dist.get(y * GRID_W + x) || 1;
      far[f] = Math.max(far[f] || 1, d);
    })
  );
  const membrane = blend(c1, "#ffffff", 0.5);
  const fin = (x, y, c) => {
    const f = FISH_FIN[c.l];
    const d = f === "pectoral" ? Math.hypot(x - pec[0], y - pec[1]) : dist.get(y * GRID_W + x) || 1;
    const u = d / far[f]; // base 0 .. tip 1
    const ray = c.l.endsWith("ray");
    const rim = [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]].some(([i, j]) => !at(i, j));
    let col = membrane;
    if (finPat === "solid") col = c2;
    else if (finPat === "edged") col = rim ? c3 || c2 : membrane;
    else if (finPat === "tipped") col = u > 0.6 ? c2 : membrane;
    else if (finPat === "gradient") col = blend(c1, c2, Math.min(1, Math.floor(u * 3 + ((x + y) & 1 ? 0.3 : 0)) / 3));
    else if (finPat === "striped") col = Math.round(d) % 3 === 0 ? c2 : membrane;
    else if (finPat === "spotted") col = (x + 2 * y) % 4 === 0 && tick(x, y) < 0.6 ? c2 : membrane;
    else if (finPat === "rayed") col = ray ? c2 : blend(c1, "#ffffff", 0.65);
    if (ray && finPat !== "rayed") col = blend(col, SHADOW_TINT, 0.15);
    return col;
  };

  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const c = grid[y][x];
      if (!c) continue;
      if (c.l === "gill") out[y][x] = blend(skin(x, y), SHADOW_TINT, 0.22);
      else if (FISH_SKIN.has(c.l)) out[y][x] = skin(x, y);
      else if (FISH_FIN[c.l]) out[y][x] = fin(x, y, c);
    }
  }
}

// --- unicorn coats: real horse markings, and a little magic --------------------------
// The body is the first color and the mane and tail the second, except:
//   solid      just that
//   blaze      a white stripe down the front of the face and white socks
//   dapple     light dapples over the body, legs darkening toward the hooves
//   pinto      big patches of the second color
//   appaloosa  a light blanket over the hindquarters, with dark leopard spots
//   rainbow    the mane and tail in bands of color, starting from the second
//   starry     tiny stars scattered over the body
// On a light coat the "white" marks take a pale tint of the second color. A
// third color is a treasure metal: the horn and the hooves.

const UNICORN_PATTERNS = new Set(["solid", "blaze", "dapple", "pinto", "appaloosa", "rainbow", "starry"]);
const UNICORN_COAT = new Set(["body", "neck", "leg", "farleg", "ear", "farear"]);
const UNICORN_PAINTED = new Set(["umane", "utail", "uhorn", "uhornline", "hoof", "farhoof", "feather", "feather2", "farfeather"]);

// A color with its hue turned by `deg` (rainbow manes).
function hueTurn(hex, deg) {
  const [r, g, b] = hexRgb(hex).map((v) => v / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  const sat = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  let h = d === 0 ? 0 : max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  h = (((h * 60 + deg) % 360) + 360) % 360;
  const sat2 = Math.max(sat, 0.45); // even a grey mane gets real colors
  const c = (1 - Math.abs(2 * l - 1)) * sat2;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  const [r1, g1, b1] = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x] : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x];
  return rgbHex([r1 + m, g1 + m, b1 + m].map((v) => Math.round(Math.max(0, Math.min(1, v)) * 255)));
}

function paintUnicorn(out, grid, genes, built, hex) {
  built.coatDone = true;
  built.painted = UNICORN_PAINTED;
  const c1 = hex[0];
  const c2 = hex[1] || hex[0];
  const metal = hex[2];
  const pattern = genes.coat.pattern;
  const geo = built.geo;
  const tick = (x, y) => ((Math.imul(x * 31 + y * 977, 2654435761) ^ genes.seed) >>> 0) % 1000 / 1000;
  const noise = valueNoise(genes.seed);
  const white = luminance(c1) > 0.7 ? blend(c2, "#ffffff", 0.5) : "#f8f4ec";
  const sockTop = GROUND - Math.max(2, geo.legH * 0.38);
  // the front of the face, row by row (for a blaze)
  const front = {};
  grid.forEach((row, y) => row.forEach((c, x) => c && (c.l === "head" || c.l === "snout") && (front[y] = Math.max(front[y] ?? -1, x))));
  const rainbow = [0, 45, 100, 160, 220, 290].map((d) => hueTurn(c2, d));

  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const cell = grid[y][x];
      if (!cell) continue;
      const l = cell.l;
      let color = null;
      if (l === "head" || l === "snout") {
        color = c1;
        if (pattern === "blaze" && x >= front[y] - 1 && y > geo.head[1] - geo.head[3] * 0.9) color = white;
      } else if (UNICORN_COAT.has(l)) {
        color = c1;
        const isLeg = l === "leg" || l === "farleg";
        const u = (x - geo.cx) / geo.rx;
        if (pattern === "blaze" && isLeg && y >= sockTop) color = white;
        if (pattern === "dapple" && !isLeg) {
          const gx = Math.floor(x / 4);
          const gy = Math.floor(y / 3);
          const r = Math.hypot(x - (gx * 4 + 1.5 + (gy % 2) * 2), y - (gy * 3 + 1));
          if (r < 1.1 && tick(gx, gy) < 0.8) color = blend(c1, "#ffffff", 0.32);
        }
        if (pattern === "dapple" && isLeg && y >= sockTop) color = blend(c1, SHADOW_TINT, 0.22);
        if (pattern === "pinto" && noise(x * 0.16 + 50, y * 0.2 + 50) > 0.58) color = c2;
        if (pattern === "appaloosa" && !isLeg && u < -0.05 && y < geo.cy + geo.ry * 0.6) {
          // the blanket is white on a dark coat, pale on a light one; its
          // spots are whichever color is darker
          color = luminance(c1) > 0.6 ? "#fbf8f2" : white;
          if (tick(x >> 1, y >> 1) < 0.2) color = luminance(c1) > luminance(c2) ? c2 : c1;
        }
        if (pattern === "starry") {
          // little four-point stars on a loose grid, and a few single sparkles
          const gx = Math.floor(x / 6);
          const gy = Math.floor(y / 5);
          const sx = gx * 6 + 2 + Math.floor(tick(gx, gy + 99) * 3);
          const sy = gy * 5 + 2;
          const star = tick(gx, gy) < 0.45 && ((x === sx && Math.abs(y - sy) <= 1) || (y === sy && Math.abs(x - sx) <= 1));
          if (star) color = x === sx && y === sy ? "#fffbe8" : blend(c2, "#ffffff", 0.4);
          else if (tick(x, y) < 0.015) color = blend(c2, "#ffffff", 0.6);
        }
      } else if (l === "umane" || l === "utail") {
        color = c2;
        if (pattern === "rainbow") color = rainbow[Math.floor((((x + y) % 12) + 12) % 12 / 2)];
      } else if (l === "uhorn") color = metal ? (cell.ny < -0.2 ? blend(metal, "#ffffff", 0.35) : metal) : PET_FIXED.uhorn;
      else if (l === "uhornline") color = metal ? blend(metal, SHADOW_TINT, 0.3) : PET_FIXED.uhornline;
      else if (l === "hoof" || l === "farhoof") color = metal || PET_FIXED.hoof;
      else if (l === "feather" || l === "farfeather") color = blend(c1, "#ffffff", l === "feather" ? 0.25 : 0.15);
      else if (l === "feather2") color = pattern === "rainbow" ? blend(c2, "#ffffff", 0.3) : blend(c1, SHADOW_TINT, 0.12);
      if (color) out[y][x] = color;
    }
  }
}

// --- designs ---------------------------------------------------------------------
// A species with an entry in PET_DESIGNS is drawn by buildVariant: a head
// that faces front, three-quarter, or side; a pose (walk, sit, stalk,
// loaf); a chest-and-hips body with a tucked waist whose belly follows the
// `weight` gene; thin legs with paws; and a face of eyes, a pink nose, and
// a mouth. Species without one still use PET_RECIPES and buildPet.
//
// PET_VARIANTS holds trial designs while a species is being worked on in
// the pet lab (genes.variant picks one, 1-based).

const PET_DESIGNS = {
  // fish are built from parts the pet rolled (shape.body, shape.head, ...)
  fish: {
    fromGenes: () => ({ fish: true }),
  },
  // chosen in the pet lab, 2026-10-27: four phoenix breeds, ember egg to
  // grown; a mix borrows another breed's flame tail, tail or crest
  phoenix: {
    get breeds() {
      return PHOENIX_BREEDS;
    },
  },
  // chosen in the pet lab, 2026-10-27: seven unicorn breeds, foal to grown;
  // a mix borrows another breed's wings, horn or neck
  unicorn: {
    get breeds() {
      return UNICORN_BREEDS;
    },
  },
  // chosen in the pet lab, 2026-10-27: five dragon breeds, each hatching from
  // a spotted egg; a mix borrows another breed's fire, horns, wings or head
  dragon: {
    get breeds() {
      return DRAGON_BREEDS;
    },
  },
  // chosen in the pet lab, 2026-10-27: eight snake breeds; a mix borrows
  // another breed's viper head, rattle or hood
  snake: {
    get breeds() {
      return SNAKE_BREEDS;
    },
  },
  // chosen in the pet lab, 2026-10-27: five lizard breeds (iguanas and the
  // skink seen from above, the monitor and chameleon from the side); a mix
  // borrows another breed's crest, dewlap or head
  lizard: {
    get breeds() {
      return LIZARD_BREEDS;
    },
  },
  // chosen in the pet lab, 2026-10-27: five turtle breeds; a mix borrows
  // another breed's head, ridges or tail
  turtle: {
    get breeds() {
      return TURTLE_BREEDS;
    },
  },
  // chosen in the pet lab, 2026-10-27: seven llama breeds on 1b's build; a
  // mix borrows another breed's ears, head or topknot
  llama: {
    get breeds() {
      return LLAMA_BREEDS;
    },
  },
  // chosen in the pet lab, 2026-10-27: six goat breeds; a mix borrows
  // another breed's ears, horns or beard
  goat: {
    breeds: {
      horned: {
        name: "Face to us: horns, beard, ears out", facing: "front", pose: "walk", mouth: "goat", beard: true, goatHorns: 4.5,
        softOutline: true, softNeck: true, hooves: true, eye: "duo",
        body: { rx: 9, ry: 4.2 }, leg: { len: 7, w: 1, min: 4 }, head: { rx: 4.2, ry: 5.2 },
        ears: { type: "out", size: 4.5, w: 1 }, tail: { type: "flag", len: 4, w: 2 },
      },
      nubian: {
        name: "Nubian: long floppy ears, Roman nose, side view", facing: "side", pose: "walk", snout: "goat", roman: true, beard: true, neck: { len: 5, w: 3.2 },
        softOutline: true, softNeck: true, hooves: true, eye: "duo",
        body: { rx: 9, ry: 4.2 }, leg: { len: 7.5, w: 1, min: 4 }, head: { rx: 4.3, ry: 4 },
        ears: { type: "floppy", size: 7, w: 1 }, tail: { type: "flag", len: 4, w: 2 },
      },
      pygmy: {
        name: "Pygmy: stout, short legs, little horns, face to us", facing: "front", pose: "walk", mouth: "goat", beard: true, goatHorns: 2.6,
        softOutline: true, softNeck: true, hooves: true, eye: "duo",
        body: { rx: 8.6, ry: 4.7 }, leg: { len: 4.5, w: 1, min: 3 }, head: { rx: 4.4, ry: 5 },
        ears: { type: "out", size: 4, w: 1 }, tail: { type: "flag", len: 4, w: 2 },
      },
      ibex: {
        name: "Ibex: huge swept horns, side view", facing: "side", pose: "walk", snout: "goat", beard: true, goatHorns: 8, neck: { len: 5, w: 3.4 },
        softOutline: true, softNeck: true, hooves: true, eye: "duo",
        body: { rx: 9.5, ry: 4.4 }, leg: { len: 7, w: 1, min: 4 }, head: { rx: 4.4, ry: 3.9 },
        ears: { type: "out", size: 3.5, w: 1 }, tail: { type: "flag", len: 4, w: 2 },
      },
      saanen: {
        name: "Saanen: white dairy goat, no horns, tall neck, side view", facing: "side", pose: "walk", snout: "goat", beard: true, neck: { len: 6, w: 3.2 },
        softOutline: true, softNeck: true, hooves: true, eye: "duo",
        body: { rx: 9.2, ry: 4.2 }, leg: { len: 7.5, w: 1, min: 4 }, head: { rx: 4.3, ry: 3.9 },
        ears: { type: "out", size: 4.8, w: 1 }, tail: { type: "flag", len: 4, w: 2 },
      },
      dwarf: {
        name: "Nigerian Dwarf: small and compact, little horns, side view", facing: "side", pose: "walk", snout: "goat", beard: true, goatHorns: 2.8, neck: { len: 4, w: 3 },
        softOutline: true, softNeck: true, hooves: true, eye: "duo",
        body: { rx: 7.8, ry: 4 }, leg: { len: 5, w: 1, min: 3 }, head: { rx: 4.2, ry: 3.9 },
        ears: { type: "out", size: 4.2, w: 1 }, tail: { type: "flag", len: 4, w: 2 },
      },
    },
  },
  // chosen in the pet lab, 2026-10-27: five sheep breeds; a mix borrows
  // another breed's ears, horns or forehead tuft
  sheep: {
    breeds: {
      fluffy: {
        name: "Fluffy, face to us, ears out", facing: "front", pose: "walk", mouth: "sheep", tuft: 1,
        softOutline: true, softNeck: true, eye: "duo", woolly: 1, bareFace: true, hooves: true,
        body: { rx: 9, ry: 4.6 }, leg: { len: 6, w: 1, min: 4 }, head: { rx: 3.8, ry: 4.6 },
        ears: { type: "out", size: 4.5, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
      merino: {
        name: "Merino: extra woolly, short legs, side view", facing: "side", pose: "walk", snout: "sheep", tuft: 1.2,
        softOutline: true, softNeck: true, eye: "duo", woolly: 1, bareFace: true, hooves: true,
        body: { rx: 10, ry: 5.2 }, leg: { len: 4.5, w: 1, min: 3 }, head: { rx: 3.6, ry: 3.9 },
        ears: { type: "out", size: 4, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
      ram: {
        name: "Ram: curled horns, side view", facing: "side", pose: "walk", snout: "sheep", ramHorns: "curl",
        softOutline: true, softNeck: true, eye: "duo", woolly: 1, bareFace: true, hooves: true,
        body: { rx: 9.5, ry: 4.7 }, leg: { len: 6, w: 1, min: 4 }, head: { rx: 3.9, ry: 4.1 },
        ears: { type: "out", size: 3.5, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
      ramfront: {
        name: "Ram, face to us: curled horns", facing: "front", pose: "walk", mouth: "sheep", tuft: 0.9, ramHorns: "curl",
        softOutline: true, softNeck: true, eye: "duo", woolly: 1, bareFace: true, hooves: true,
        body: { rx: 9.3, ry: 4.7 }, leg: { len: 6, w: 1, min: 4 }, head: { rx: 3.9, ry: 4.7 },
        ears: { type: "out", size: 3.6, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
      longwool: {
        name: "Longwool: shaggy fringe over the forehead, face to us", facing: "front", pose: "walk", mouth: "sheep", tuft: 1.7,
        softOutline: true, softNeck: true, eye: "duo", woolly: 1.2, bareFace: true, hooves: true,
        body: { rx: 9.5, ry: 4.9 }, leg: { len: 5.5, w: 1, min: 4 }, head: { rx: 3.9, ry: 4.7 },
        ears: { type: "out", size: 4.2, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
    },
  },
  // chosen in the pet lab, 2026-10-27: four fox breeds; a mix borrows
  // another breed's ears or head
  fox: {
    breeds: {
      red: {
        name: "Red fox: face to us", facing: "front", pose: "walk", mouth: "fox", heart: true, cheeks: 1.1,
        softOutline: true, softNeck: true, eye: "duo", socks: true, tailTip: true, earTips: true,
        body: { rx: 9.2, ry: 3.9 }, leg: { len: 6.5, w: 1, min: 3 }, head: { rx: 5.6, ry: 4.9 },
        ears: { size: 6.5, w: 1.15 }, tail: { type: "brush", len: 13, w: 4.5 },
      },
      sitting: {
        name: "Sitting, face to us, tail wrapped round", facing: "front", pose: "sit", mouth: "fox", heart: true, cheeks: 1.1,
        softOutline: true, softNeck: true, eye: "duo", socks: true, tailTip: true, earTips: true,
        body: { rx: 8.5, ry: 4 }, leg: { len: 7, w: 1, min: 4 }, head: { rx: 5.6, ry: 4.9 },
        ears: { size: 6.5, w: 1.15 }, tail: { type: "wrap", len: 16, w: 5 },
      },
      kit: {
        name: "Kit: big head, face to us", facing: "front", pose: "walk", mouth: "fox", heart: true, cheeks: 1.08,
        softOutline: true, softNeck: true, eye: "duo", socks: true, tailTip: true, earTips: true,
        body: { rx: 8, ry: 3.7 }, leg: { len: 5, w: 1, min: 3 }, head: { rx: 6.3, ry: 5.4 },
        ears: { size: 6, w: 1.1 }, tail: { type: "brushup", len: 10, w: 3.8 },
      },
      curled: {
        name: "Curled up, face to us, tail round", facing: "front", pose: "loaf", mouth: "fox", heart: true, cheeks: 1.1,
        softOutline: true, softNeck: true, eye: "duo", socks: true, tailTip: true, earTips: true,
        body: { rx: 9, ry: 4.2 }, leg: { len: 6, w: 1, min: 3 }, head: { rx: 5.5, ry: 4.8 },
        ears: { size: 6.2, w: 1.15 }, tail: { type: "wrap", len: 16, w: 5 },
      },
    },
  },
  // chosen in the pet lab, 2026-10-27: every bunny crouches side-on; it rolls
  // one of these breeds, and a mix borrows another breed's ears
  bunny: {
    breeds: {
      classic: {
        name: "Classic: crouched, side view, long ears", facing: "side", pose: "crouch", snout: "bunny",
        softOutline: true, softNeck: true, eye: "duo",
        body: { rx: 8, ry: 4.8 }, leg: { len: 3, w: 2, min: 2 }, head: { rx: 4.6, ry: 4.3 },
        ears: { type: "long", size: 10, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
      front: {
        name: "Crouched, face to us, long ears", facing: "front", pose: "crouch", mouth: "bunny", cheeks: 1.08,
        softOutline: true, softNeck: true, eye: "duo",
        body: { rx: 8, ry: 4.8 }, leg: { len: 3, w: 2, min: 2 }, head: { rx: 5.6, ry: 4.9 },
        ears: { type: "long", size: 10, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
      dwarf: {
        name: "Dwarf: round, big head, short ears", facing: "front", pose: "crouch", mouth: "bunny", cheeks: 1.12,
        softOutline: true, softNeck: true, eye: "duo",
        body: { rx: 7, ry: 4.6 }, leg: { len: 3, w: 2, min: 2 }, head: { rx: 6.2, ry: 5.4 },
        ears: { type: "long", size: 6.5, w: 1.05 }, tail: { type: "none", len: 0, w: 1 },
      },
      sidelop: {
        name: "Side lop", facing: "side", pose: "crouch", snout: "bunny",
        softOutline: true, softNeck: true, eye: "duo",
        body: { rx: 8, ry: 4.8 }, leg: { len: 3, w: 2, min: 2 }, head: { rx: 4.8, ry: 4.4 },
        ears: { type: "lop", size: 9, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
      holland: {
        name: "Holland lop: big round head, short body, lop ears", facing: "side", pose: "crouch", snout: "bunny",
        softOutline: true, softNeck: true, eye: "duo",
        body: { rx: 7, ry: 4.6 }, leg: { len: 3, w: 2, min: 2 }, head: { rx: 5.6, ry: 5.2 },
        ears: { type: "lop", size: 8.5, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
      halflop: {
        name: "Half-lop: one ear up, one ear down", facing: "side", pose: "crouch", snout: "bunny",
        softOutline: true, softNeck: true, eye: "duo",
        body: { rx: 8, ry: 4.8 }, leg: { len: 3, w: 2, min: 2 }, head: { rx: 4.8, ry: 4.4 },
        ears: { type: "half", size: 10, w: 1 }, tail: { type: "none", len: 0, w: 1 },
      },
      wild: {
        name: "Old world rabbit: lean, alert, tall ears, side view", facing: "side", pose: "crouch", snout: "bunny", alert: true,
        softOutline: true, softNeck: true, eye: "duo",
        body: { rx: 8.6, ry: 4.4 }, leg: { len: 3, w: 2, min: 2 }, head: { rx: 4.8, ry: 4.1 },
        ears: { type: "long", size: 11, w: 0.95 }, tail: { type: "none", len: 0, w: 1 },
      },
      dwarfside: {
        name: "Dwarf, side view: round, big head, short ears", facing: "side", pose: "crouch", snout: "bunny",
        softOutline: true, softNeck: true, eye: "duo",
        body: { rx: 7, ry: 4.6 }, leg: { len: 3, w: 2, min: 2 }, head: { rx: 5.6, ry: 5.2 },
        ears: { type: "long", size: 6.5, w: 1.05 }, tail: { type: "none", len: 0, w: 1 },
      },
    },
  },
  // chosen in the pet lab, 2026-10-27: each dog rolls one of these breeds
  // (genes.shape.breed), and a mix borrows its tail or ears from another
  // (genes.shape.mix, e.g. {tail: "husky"})
  dog: {
    breeds: {
    classic: {
      name: "Classic: side view, boxy snout, floppy ears, tail up", facing: "side", pose: "walk", snout: "square", snoutLen: 3.5, snoutR: 2.3,
      softOutline: true, softNeck: true, eye: "duo",
      body: { rx: 10, ry: 5 }, leg: { len: 6, w: 3, min: 3 }, head: { rx: 5.3, ry: 4.9 },
      ears: { type: "floppy", size: 6.5, w: 1 }, tail: { type: "sickle", len: 7, w: 2 },
    },
    hound: {
      name: "Hound: side view, long snout, floppy ear", facing: "side", pose: "walk", snout: "square", snoutLen: 4, snoutR: 1.9,
      softOutline: true, softNeck: true, eye: "duo",
      body: { rx: 10, ry: 4.2 }, leg: { len: 7, w: 2, min: 3 }, head: { rx: 4.6, ry: 4.4 },
      ears: { type: "floppy", size: 6.5, w: 1 }, tail: { type: "sickle", len: 9, w: 1.8 },
    },
    shiba: {
      name: "Shiba: pointed ears, curled tail", facing: "front", pose: "walk", mouth: "dog",
      softOutline: true, softNeck: true, eye: "duo",
      body: { rx: 9, ry: 4 }, leg: { len: 6, w: 2, min: 3 }, head: { rx: 5.8, ry: 5 },
      ears: { size: 5.2, w: 1 }, tail: { type: "curl", len: 9, w: 2.6 },
    },
    dachshund: {
      name: "Dachshund: side view, long body, tiny legs", facing: "side", pose: "walk", snout: "square", snoutLen: 5, snoutR: 1.7,
      softOutline: true, softNeck: true, eye: "duo",
      body: { rx: 11.5, ry: 3.6 }, leg: { len: 2.5, w: 2, min: 2 }, head: { rx: 4.4, ry: 4.2 },
      ears: { type: "floppy", size: 6, w: 1 }, tail: { type: "whip", len: 9, w: 1.4 },
    },
    husky: {
      name: "Husky: side view, pointed ears, curled tail", facing: "side", pose: "walk", snout: "square", snoutLen: 3.5, snoutR: 1.8,
      softOutline: true, softNeck: true, eye: "duo",
      body: { rx: 9.5, ry: 4.2 }, leg: { len: 7, w: 2, min: 3 }, head: { rx: 4.8, ry: 4.4 },
      ears: { size: 5, w: 0.95 }, tail: { type: "curl", len: 10, w: 2.6 },
    },
    },
  },
  // chosen in the pet lab, 2026-10-27 (the second round of cats): seven
  // breeds built on CAT_BASE; a mix borrows another breed's ears, head or cheeks
  cat: {
    get breeds() {
      return CAT_BREEDS;
    },
  },
};

// The cat's shared face and build (the first round's pick); each breed
// changes only what it needs.
const CAT_BASE = {
  name: "Cat", facing: "front", pose: "walk", mouth: "w", eyesLow: true, softOutline: true, softNeck: true,
  body: { rx: 8.4, ry: 3.9 }, leg: { len: 5.5, w: 1, min: 3 }, head: { rx: 6.3, ry: 5.4 },
  ears: { size: 5, w: 0.85 }, tail: { type: "question", len: 13, w: 2.4 }, eye: "duo",
};

function catBreed(over) {
  return { ...CAT_BASE, leg: { len: 6, w: 1, min: 3 }, ...over, ears: { ...CAT_BASE.ears, ...(over.ears || {}) } };
}

const CAT_BREEDS = {
  shorthair: catBreed({ name: "Shorthair, side view", facing: "side", pose: "walk", snout: "round", body: { rx: 9, ry: 3.9 }, head: { rx: 4.8, ry: 4.4 }, ears: { size: 5.5, w: 0.9 }, tail: { type: "question", len: 12, w: 1.8 } }),
  sitting: catBreed({ name: "Sitting, face to us, tail wrapped round", pose: "sit", body: { rx: 8.2, ry: 3.8 }, leg: { len: 7, w: 1, min: 4 }, tail: { type: "wrap", len: 14, w: 3 } }),
  loaf: catBreed({ name: "Loaf: tucked in, paws peeking out", pose: "loaf", body: { rx: 8.8, ry: 4.2 }, tail: { type: "wrap", len: 12, w: 2 } }),
  kitten: catBreed({ name: "Kitten: big head, short legs", body: { rx: 7.6, ry: 3.6 }, leg: { len: 4.5, w: 1, min: 3 }, head: { rx: 6.6, ry: 5.6 }, tail: { type: "question", len: 10, w: 2 } }),
  mainecoon: catBreed({ name: "Maine Coon: big, ear tufts, chest ruff, plume tail", body: { rx: 10, ry: 4.4 }, leg: { len: 6.5, w: 1, min: 3 }, head: { rx: 6.2, ry: 5.2 }, cheeks: 1.12, ruff: true, fluffy: true, ears: { size: 5.6, w: 0.95, tufts: true }, tail: { type: "plume", len: 13, w: 3.4 } }),
  persian: catBreed({ name: "Persian: flat round face, small ears, fluffy, short legs", body: { rx: 9, ry: 4.4 }, leg: { len: 4.5, w: 1, min: 3 }, head: { rx: 6.6, ry: 5.3 }, cheeks: 1.18, fluffy: true, ears: { size: 3.6, w: 1.1 }, tail: { type: "plume", len: 10, w: 3.4 } }),
  sleeping: catBreed({ name: "Sleeping curl: curled up, eyes closed", pose: "loaf", eye: "closed", body: { rx: 9, ry: 4 }, tail: { type: "wrap", len: 14, w: 2.2 } }),
};

// The llama's build (1b, chosen in the pet lab, 2026-10-27): a thick neck
// growing out of the chest and leaning forward, a long barrel body whose back
// slopes gently down to the tail, a long muzzle, and clean spike ears.
const LLAMA_BASE = {
  name: "Llama", facing: "side", pose: "walk", slope: 0.16, snout: "llama", snoutLen: 3.4,
  softOutline: true, softNeck: true, hooves: true, eye: "duo",
  neck: { len: 12, w: 3.4, lean: 1.0, thick: true },
  body: { rx: 11.4, ry: 5.1 }, leg: { len: 8, w: 2, min: 4 }, head: { rx: 4, ry: 3.4 },
  ears: { type: "banana", size: 6.5, w: 1, thick: 0.9, plain: true }, tail: { type: "pom", len: 3, w: 2.4 },
};

function llamaBreed(over) {
  return { ...LLAMA_BASE, ...over, ears: { ...LLAMA_BASE.ears, ...(over.ears || {}) } };
}

const LLAMA_BREEDS = {
  llama: llamaBreed({ name: "Llama (1b)" }),
  front: llamaBreed({ name: "Llama, face to us", facing: "front", mouth: "llama", head: { rx: 4.2, ry: 4.6 } }),
  alpaca: llamaBreed({ name: "Alpaca: woolly, topknot, shorter neck and ears, side view", woolly: 1, tuft: 1.2, snoutLen: 2.6, neck: { len: 8, w: 4, lean: 0.95, thick: true }, body: { rx: 10, ry: 5 }, leg: { len: 6.5, w: 2, min: 4 }, ears: { size: 4.6 } }),
  cria: llamaBreed({ name: "Cria: baby llama, big head, long legs, side view", neck: { len: 9, w: 3.2, lean: 0.95, thick: true }, body: { rx: 9, ry: 4.4 }, leg: { len: 9, w: 2, min: 5 }, head: { rx: 4.5, ry: 3.9 }, ears: { size: 6 } }),
  guanaco: llamaBreed({ name: "Guanaco: wild, sleek and lean, side view", slope: 0.2, neck: { len: 12, w: 3, lean: 1.02, thick: true }, body: { rx: 11.4, ry: 4.4 }, leg: { len: 8.5, w: 2, min: 4 }, head: { rx: 3.8, ry: 3.2 }, tail: { type: "flag", len: 4, w: 2 } }),
  kushed: llamaBreed({ name: "Kushed: lying down, neck up, side view", pose: "loaf", neck: { len: 10, w: 3.6, thick: true }, body: { rx: 11, ry: 4.6 } }),
  suri: llamaBreed({ name: "Suri alpaca: long drapey fleece, side view", woolly: 1.3, tuft: 1.4, snoutLen: 2.6, neck: { len: 8, w: 4.2, lean: 0.95, thick: true }, body: { rx: 10.4, ry: 5.2 }, leg: { len: 6, w: 2, min: 4 }, ears: { size: 4.6 } }),
};

// Turtle trial designs start from a box turtle.
function TURTLE(over) {
  return {
    shell: true, facing: "side", softOutline: true,
    body: { rx: 10, ry: 7.4 }, leg: { len: 3.4, w: 3.4 }, head: { rx: 3.6, ry: 3.1 }, plate: 4.6,
    ...over,
  };
}

const TURTLE_BREEDS = {
  box: TURTLE({ name: "Box turtle: domed shell, side view" }),
  tortoise: TURTLE({ name: "Tortoise: tall dome, thick legs, side view", body: { rx: 10.6, ry: 9.2 }, leg: { len: 4.2, w: 4.4 }, plate: 5.4 }),
  baby: TURTLE({ name: "Baby turtle: big head, little round shell, face to us", facing: "front", body: { rx: 8, ry: 6.2 }, leg: { len: 2.7, w: 3.2 }, head: { rx: 5, ry: 4.4 }, plate: 4 }),
  snapper: TURTLE({ name: "Snapping turtle: ridged shell, big head, long tail, side view", ridges: true, body: { rx: 11.4, ry: 6.6 }, head: { rx: 4.5, ry: 3.7 }, tailLen: 6 }),
  shy: TURTLE({ name: "Shy: hiding in its shell, eyes peeking", tucked: true, leg: { len: 1.8, w: 3.2 } }),
};

// Lizard trial designs start from a green iguana's build.
function LIZARD(over) {
  return {
    lizard: true, facing: "side", softOutline: true,
    body: { rx: 9, ry: 3.2 }, leg: { len: 3.6, w: 2.2 }, head: { rx: 3.2, ry: 2.6 }, tail: { type: "long", len: 17 },
    ...over,
  };
}

const LIZARD_BREEDS = {
  iguana: LIZARD({ name: "Iguana: thick shoulders tapering back, question-mark tail curling under", view: "top", taper: true, crest: 2.2, dewlap: true, body: { rx: 9, ry: 3.4 }, tail: { type: "question", len: 18 } }),
  iguana_s: LIZARD({ name: "Iguana, tapering body, S-curved tail", view: "top", taper: true, crest: 2.2, dewlap: true, body: { rx: 9, ry: 3.4 } }),
  monitor: LIZARD({ name: "Monitor: long neck and body, forked tongue (side view)", stance: "stand", tongue: true, neck: 3.4, body: { rx: 10, ry: 3 }, tail: { type: "long", len: 20 }, head: { rx: 3, ry: 2.2 }, snout: 3 }),
  skink: LIZARD({ name: "Skink: long and smooth, tiny legs (from above)", view: "top", body: { rx: 10, ry: 2.4 }, leg: { len: 2.4, w: 1.6 }, tail: { type: "long", len: 15 }, head: { rx: 2.8, ry: 2.2 }, snout: 1.6 }),
  chameleon: LIZARD({ name: "Chameleon: helmet, spiral tail (side view)", stance: "stand", chameleon: true, casque: true, crest: 0.6, body: { rx: 6.4, ry: 3.2 }, leg: { len: 4.2, w: 1.6 }, tail: { type: "curl", len: 11 }, head: { rx: 3, ry: 2.8 }, snout: 1.4, headUp: 1.5 }),
};

// Snake trial designs start from the classic "2".
function SNAKE(over) {
  return { snake: true, facing: "side", softOutline: true, pose: "two", height: 17, body: { w: 2.2 }, split: 0.55, ...over };
}

const SNAKE_BREEDS = {
  classic: SNAKE({ name: "Classic: a coil rising in a 2, head up, side view" }),
  cobra: SNAKE({ name: "Cobra: raised, hood flared, face to us", pose: "cobra", hood: true, facing: "front", height: 20 }),
  wave: SNAKE({ name: "Side-on wave, head held up", pose: "wave", body: { w: 1.8 }, split: 1 }),
  diamondback: SNAKE({ name: "Diamondback slither: low waves, viper head, rattle raised", pose: "slide", viper: true, rattle: true, body: { w: 2 }, split: 1 }),
  strike: SNAKE({ name: "Diamondback ready to strike: front pulled back in an S", pose: "strike", viper: true, rattle: true, body: { w: 2 }, split: 0.35 }),
  slider: SNAKE({ name: "Long slider, head up", pose: "wave", body: { w: 1.6 }, split: 1, height: 20 }),
  rattler: SNAKE({ name: "Rattler 2: the classic pose with a viper head and rattle", viper: true, rattle: true }),
  baby: SNAKE({ name: "Baby slither", pose: "slide", body: { w: 2.2 }, split: 1 }),
};

// Dragon trial designs start from a classic western dragon walking.
function DRAGON(over) {
  return {
    dragon: true, facing: "side", pose: "walk", softOutline: true, horns: 4, spines: 1, neck: 4, snout: 2.3,
    body: { rx: 9, ry: 4.2 }, leg: { len: 5, w: 2.4 }, head: { rx: 3.6, ry: 3.2 }, tail: { len: 16 }, wings: { type: "up", span: 14 },
    ...over,
  };
}

const DRAGON_BREEDS = {
  classic: DRAGON({ name: "Classic: walking, wings up, horns and spines", head: { rx: 4.2, ry: 3.6 } }),
  wyvern: DRAGON({ name: "Wyvern: up on two legs, long neck, big wings", pose: "wyvern", neck: 7, leg: { len: 7, w: 2.6 }, body: { rx: 8, ry: 4.4 }, wings: { type: "up", span: 13 } }),
  flying: DRAGON({ name: "Flying: wings spread and flapping, legs tucked", pose: "fly", wings: { type: "spread", span: 12 }, tail: { len: 15 } }),
  fire: DRAGON({ name: "Fire breather: head up, a puff of flame", fire: true, headUp: 1.5, head: { rx: 4.2, ry: 3.6 }, wings: { type: "half", span: 13 } }),
  chubby: DRAGON({ name: "Chubby: round belly, big head, stubby legs, tiny wings", body: { rx: 8, ry: 5.8 }, leg: { len: 3.5, w: 2.8 }, head: { rx: 4.8, ry: 4.2 }, neck: 2.5, horns: 3, snout: 1.8, tail: { len: 11 }, wings: { type: "up", span: 8 } }),
};

// Unicorn trial designs start from a horse standing side-on.
function UNICORN(over) {
  return {
    unicorn: true, facing: "side", pose: "stand", softOutline: true, horn: 6, neck: 6, snout: 4.4,
    body: { rx: 10, ry: 4.4 }, leg: { len: 9, w: 2 }, head: { rx: 3, ry: 2.8 },
    ...over,
  };
}

const UNICORN_BREEDS = {
  classic: UNICORN({ name: "Classic: standing side-on, flowing mane and tail" }),
  prance: UNICORN({ name: "Prancing: a front hoof raised, head high", pose: "prance", neck: 7 }),
  rear: UNICORN({ name: "Rearing up on its hind legs", pose: "rear", neck: 5 }),
  gallop: UNICORN({ name: "Galloping: legs stretched out, mane and tail streaming", pose: "gallop" }),
  pony: UNICORN({ name: "Pony: round and fluffy, short legs, big head", body: { rx: 8, ry: 4.8 }, leg: { len: 5.5, w: 2.4 }, head: { rx: 3.6, ry: 3.3 }, neck: 4, snout: 3, horn: 4.5 }),
  lying: UNICORN({ name: "Lying down, legs tucked, head up", pose: "lie", neck: 5 }),
  alicorn: UNICORN({ name: "Alicorn: feathered wings", wings: 13 }),
};

// Phoenix trial designs start from a firebird perched side-on.
function PHOENIX(over) {
  return {
    phoenix: true, facing: "side", pose: "perch", softOutline: true, crest: 4.5, head: 3.4, legs: 6, tail: 22, plumes: 3, fold: true,
    body: { rx: 7, ry: 5.2 },
    ...over,
  };
}

const PHOENIX_BREEDS = {
  classic: PHOENIX({ name: "Classic firebird: wings raised, long flaming plumes", fold: false, wings: 13 }),
  rising: PHOENIX({ name: "Rising: wings raised, a tail of pure fire", fold: false, wings: 14, flame: true, tail: 18 }),
  flying: PHOENIX({ name: "Flying: wings beating, plumes streaming", pose: "fly", fold: false, wings: 13, tail: 18 }),
  emblem: PHOENIX({ name: "Emblem: facing us, wings spread wide, tail fanned", facing: "front", fold: false, wings: 12, tail: 14, head: 3.2 }),
};

const PET_VARIANTS = {
  // the breeds, one lab row each
  dog: Object.values(PET_DESIGNS.dog.breeds),
  bunny: Object.values(PET_DESIGNS.bunny.breeds),
  fox: Object.values(PET_DESIGNS.fox.breeds),
  sheep: Object.values(PET_DESIGNS.sheep.breeds),
  cat: Object.values(CAT_BREEDS),
  goat: Object.values(PET_DESIGNS.goat.breeds),
  llama: Object.values(LLAMA_BREEDS),
  turtle: Object.values(TURTLE_BREEDS),
  lizard: Object.values(LIZARD_BREEDS),
  snake: Object.values(SNAKE_BREEDS),
  dragon: Object.values(DRAGON_BREEDS),
  unicorn: Object.values(UNICORN_BREEDS),
  phoenix: Object.values(PHOENIX_BREEDS),
  // fish: the eight bodies, each with stand-in fins
  // (a getter: FISH_BODIES is defined further down); the rest of the fish
  // comes from its own rolled parts
  get fish() {
    return Object.entries(FISH_BODIES).map(([body, b]) => ({ fish: true, body, name: b.name }));
  },
};

function buildVariant(genes, stage, frame, V) {
  if (V.shell) return buildTurtle(genes, stage, frame, V);
  if (V.snake) return buildSnake(genes, stage, frame, V);
  if (V.dragon) return buildDragon(genes, stage, frame, V);
  if (V.unicorn) return buildUnicorn(genes, stage, frame, V);
  if (V.phoenix) return buildPhoenix(genes, stage, frame, V);
  if (V.fish) return buildFish(genes, stage, frame, V);
  if (V.lizard && V.view === "top") return buildLizardTop(genes, stage, frame, V);
  if (V.lizard) return buildLizard(genes, stage, frame, V);
  const shape = genes.shape || {};
  const grid = makeGrid();
  const s = stage.body;
  const hs = Math.max(stage.head, V.headMin ? Math.min(1, V.headMin + (stage.head - 0.82)) : 0);
  const ls = stage.leg;
  const weight = shape.weight || 0;
  const step = frame % 2;
  const wag = frame % 2;

  const stalk = V.pose === "stalk";
  const sit = V.pose === "sit";
  const loaf = V.pose === "loaf";
  const rx = half(V.body.rx * s + (shape.length || 0) / 2);
  const ry = half(V.body.ry * s * (1 + 0.28 * weight) + (shape.height || 0) / 5);
  const legLen = Math.max(V.leg.min, Math.round(V.leg.len * ls * (stalk ? 0.75 : 1) * (1 + (shape.legs || 0) * 0.3) + (shape.height || 0) / 2));
  const snoutSize = (V.muzzle || 1) * (1 + (shape.snout || 0) * 0.35); // dogs: the snout gene
  const legW = V.leg.w > 1 && s > 0.55 ? V.leg.w : 1;
  const farOffset = legW + 1; // the far legs stand a little behind, on their own
  const cx = 32;
  const cy = GROUND - legLen - ry * 0.5;

  // a leg with a little paw that sticks out forward at the bottom
  const leg = (x, top, lift, label) => {
    fillRect(grid, x, top - lift, legW, GROUND - top, label);
    fillRect(grid, x + legW - 1, GROUND - 1 - lift, 2, 1, label);
  };

  const tailLen = V.tail.len * s * (1 + (shape.tail || 0) * 0.2);
  const tw = Math.max(0.7, (V.tail.w * Math.max(s, 0.6)) / 2);
  let tailEnd = null;
  const tail = (tx, ty) => {
    const L = tailLen;
    const pts = {
      // foxes: a big brush, held out and a little up, or curving up behind
      brush: [[tx, ty], [tx - L * 0.45, ty + L * 0.12], [tx - L * 0.8, ty + L * 0.02], [tx - L - wag * 0.5, ty - L * 0.2]],
      brushup: [[tx, ty], [tx - L * 0.35, ty - L * 0.1], [tx - L * 0.6, ty - L * 0.5], [tx - L * 0.5 - wag, ty - L * 0.85]],
      question: [[tx, ty], [tx - L * 0.2, ty - L * 0.4], [tx - L * 0.15, ty - L * 0.8], [tx + L * 0.15 - wag, ty - L * 0.95]],
      whip: [[tx, ty], [tx - L * 0.25, ty - L * 0.5], [tx - L * 0.2 - wag, ty - L * 0.95]],
      plume: [[tx, ty], [tx - L * 0.35, ty - L * 0.45], [tx - L * 0.25 - wag, ty - L * 0.85]],
      thick: [[tx, ty], [tx - L * 0.4, ty - L * 0.6], [tx - L * 0.35 - wag, ty - L * 0.9]],
      low: [[tx, ty], [tx - L * 0.55, ty + 0.5], [tx - L * 0.9, ty - L * 0.25 - wag]],
      s: [[tx, ty], [tx - L * 0.35, ty + L * 0.05], [tx - L * 0.5, ty - L * 0.4], [tx - L * 0.35 - wag, ty - L * 0.8]],
      // dogs
      otter: [[tx, ty], [tx - L * 0.5, ty + L * 0.05], [tx - L - wag * 0.6, ty - L * 0.3]],
      sickle: [[tx, ty], [tx - L * 0.3, ty - L * 0.4], [tx - L * 0.15 - wag, ty - L * 0.9]],
      curl: [[tx, ty], [tx - L * 0.15, ty - L * 0.55], [tx + L * 0.2, ty - L * 0.8], [tx + L * 0.45 + wag * 0.3, ty - L * 0.45]],
    }[V.tail.type];
    if (pts) {
      // a brush is fat: thin where it leaves the body, widest in the middle, a
      // rounded tip
      if (V.tail.type.startsWith("brush")) {
        const widths = [0.55, 1.25, 1.35, 1.0];
        pts.slice(1).forEach((p, i) => {
          const steps = 6;
          for (let k = 0; k <= steps; k++) {
            const t = k / steps;
            const r = tw * (widths[i] + (widths[i + 1] - widths[i]) * t);
            fillEllipse(grid, pts[i][0] + (p[0] - pts[i][0]) * t, pts[i][1] + (p[1] - pts[i][1]) * t, r, r, "tail");
          }
        });
      }
      else fillStroke(grid, pts, tw, "tail");
      tailEnd = pts[pts.length - 1];
      relight(grid, "tail");
    }
    if (V.tail.type === "pom") fillEllipse(grid, tx - 0.5, ty - 1 - wag * 0.4, Math.max(1.4, tw * 1.3), Math.max(1.6, tw * 1.5), "tail");
    if (V.tail.type === "stub") fillEllipse(grid, tx - 0.5, ty - 0.5 - wag * 0.4, Math.max(1.3, tw * 1.2), Math.max(1.3, tw * 1.1), "tail");
  };

  // a body: a deeper chest, a tucked waist, the hips, and a belly from `weight`
  const slope = (V.slope || 0) * ry;
  const body = (bx, by) => {
    fillEllipse(grid, bx, by - ry * 0.12, rx * 0.92, ry * 0.9, "body");
    fillEllipse(grid, bx + rx * 0.38, by - slope, rx * 0.6, ry * 1.05, "body");
    fillEllipse(grid, bx - rx * 0.42, by - ry * 0.08 + slope, rx * 0.55, ry * 0.95, "body");
    if (weight > 0) fillEllipse(grid, bx, by + ry * 0.35, rx * 0.62, ry * (0.35 + weight * 0.4), "body");
  };

  let hx;
  let hy;
  const hrx = V.head.rx * hs;
  const hry = (V.head.ry + (V.mouth ? 0.5 : 0)) * hs;
  const crouch = V.pose === "crouch";
  const upright = V.pose === "upright";
  if (crouch || upright) {
    // a bunny: an egg of a body with a high round rump, a big flat hind foot,
    // little front paws, and a white cotton tail. Upright: sitting up tall.
    const by = GROUND - ry * (upright ? 1.7 : 1.1);
    const bry = ry * (upright ? 1.7 : 1.12);
    const brx = upright ? rx * 0.62 : rx;
    fillRect(grid, cx + brx * 0.45 + farOffset - 1, GROUND - ry * 0.9, legW, ry * 0.9, "farleg");
    if (upright) {
      fillEllipse(grid, cx, by, brx, bry, "body");
    } else {
      fillEllipse(grid, cx - brx * 0.28, GROUND - ry * 1.18, brx * 0.78, ry * 1.18, "body"); // the high rump
      const chestY = GROUND - ry * (V.alert ? 1.15 : 0.82);
      fillEllipse(grid, cx + brx * 0.38, chestY, brx * 0.55, ry * 0.82, "body"); // the lower chest
    }
    fillEllipse(grid, cx - brx * 0.45, GROUND - ry * 0.8, Math.max(2.5, rx * 0.5), ry * 0.85, "body"); // the haunch
    if (V.fluff) {
      // angora: tufts of fluff all over the back and sides
      // tufts sit out past the edge so the outline turns bumpy
      const r = Math.max(1.7, 2.3 * Math.max(s, 0.6));
      for (let i = 0; i <= 6; i++) {
        const a = Math.PI * (0.02 + (0.96 * i) / 6);
        fillEllipse(grid, cx - brx * 0.12 - Math.cos(a) * (brx * 0.98 + r * 0.55), GROUND - ry * 1.02 - Math.sin(a) * (ry * 1.12 + r * 0.55), r, r, "fluff");
      }
    }
    const tr = Math.max(1.4, 2.2 * Math.max(s, 0.6));
    fillEllipse(grid, cx - brx * (upright ? 0.95 : 1.02), (upright ? by - bry * 0.2 : GROUND - ry * 1.5) - wag * 0.4, tr, tr, "cotton");
    fillEllipse(grid, cx - brx * 0.1, GROUND - 1.2, Math.max(2.2, rx * 0.5), 1.4, "leg"); // the hind foot
    if (upright) {
      fillEllipse(grid, cx + brx * 0.75, by - bry * 0.15, Math.max(1.2, 1.6 * s), Math.max(1.2, 1.8 * s), "leg"); // paws held up
    } else {
      const legTopY = GROUND - ry * (V.alert ? 1.3 : 0.9);
      fillRect(grid, cx + brx * 0.45 - 1, legTopY, legW, GROUND - legTopY, "leg");
    }
    hx = cx + brx * (upright ? 0.25 : 0.72);
    hy = upright ? by - bry * 0.95 - hry * 0.45 : GROUND - ry * (V.alert ? 1.95 : 1.55) - hry * 0.4;
  } else if (loaf) {
    // lying down: a round loaf of a body, two front paws peeking out, the tail along the side
    const ly = GROUND - ry * 1.05;
    fillEllipse(grid, cx, ly, rx, ry * 1.1, "body");
    const L = tailLen;
    if (V.tail.type === "pom") {
      fillEllipse(grid, cx - rx * 0.95, ly - ry * 0.7 - wag * 0.4, Math.max(1.4, tw * 1.3), Math.max(1.4, tw * 1.3), "tail");
    } else {
      const wrap = [[cx - rx * 0.9, GROUND - 2], [cx - rx * 0.4, GROUND - 1.2], [cx - rx * 0.4 + L * 0.5, GROUND - 1.2 - wag * 0.5]];
      fillStroke(grid, wrap, tw, "tail");
      tailEnd = wrap[wrap.length - 1];
    }
    for (const dx of [0.55, 0.85]) fillEllipse(grid, cx + rx * dx, GROUND - 1, Math.max(1.2, 1.6 * s), 1.1, "leg");
    hx = cx + rx * 0.55;
    hy = ly - ry * 0.9 - hry * 0.35;
    if (V.neck) {
      const nl = V.neck.len * s * (1 + (shape.neck || 0) * 0.25);
      const nw = Math.max(2.5, V.neck.w * Math.max(s, 0.7));
      hx = cx + rx * 0.7;
      hy = ly - ry * 0.9 - nl;
      fillStroke(grid, [[cx + rx * 0.55, ly - ry * 0.3], [hx - 0.5, hy + hry * 0.4]], V.neck.thick ? nw * 0.85 : nw / 2, "neck");
    }
  } else if (sit) {
    // sitting: a round haunch, an upright chest, straight front legs, the tail wrapped round
    const rh = Math.max(3, ry * 1.25);
    const hcx = cx - rx * 0.25;
    const chx = cx + rx * 0.2;
    const chy = GROUND - legLen - ry * 0.6;
    fillRect(grid, chx + farOffset - 1, chy, legW, GROUND - chy, "farleg");
    fillEllipse(grid, hcx, GROUND - rh, rh, rh, "body");
    fillEllipse(grid, chx, chy, Math.max(2.5, rx * 0.42), ry * 1.5, "body");
    fillRect(grid, chx - 1, chy, legW, GROUND - chy, "leg");
    fillRect(grid, chx - 1 + legW - 1, GROUND - 1, 2, 1, "leg");
    fillEllipse(grid, hcx + rh * 0.55, GROUND - 1, Math.max(1.6, 2.4 * s), 1.2, "leg");
    const L = tailLen;
    const wrap = [[hcx - rh * 0.7, GROUND - 3], [hcx - rh * 0.9, GROUND - 1.8], [hcx + rh * 0.2, GROUND - 1.6], [hcx + rh * 0.2 + L * 0.35, GROUND - 2.2 - wag]];
    fillStroke(grid, wrap, tw, "tail");
    if (V.tailTip) fillEllipse(grid, hcx - rh * 0.3, GROUND - tw, rh * 0.9, tw * 1.1, "tail"); // a fox's brush is fat
    tailEnd = wrap[wrap.length - 1];
    hx = chx + 0.5;
    hy = chy - ry * 1.2 - hry * 0.45;
  } else {
    const backX = cx - rx * 0.55;
    const frontX = cx + rx * 0.45;
    leg(backX + farOffset, cy, step ? 0 : 1, "farleg");
    leg(frontX + farOffset, cy, step ? 1 : 0, "farleg");
    tail(cx - rx + 1, cy - ry * 0.4);
    if (V.woolly) {
      // sheep: an oval with bumps of wool all the way round; the bumps keep
      // their own label so the outline stays scalloped
      const wool = 1 + (shape.wool || 0) * 0.25;
      fillEllipse(grid, cx, cy - ry * 0.1, rx, ry * 1.05, "body");
      // many small bumps close to the edge: a gentle scallop, not big mounds
      // (the wool's texture comes from shading in paintSheep)
      const r = Math.max(1.2, 1.5 * Math.max(s, 0.6) * wool * (V.woolly || 1));
      const n = Math.max(10, Math.round((rx + ry) / 1.05));
      for (let i = 0; i < n; i++) {
        const a = (Math.PI * 2 * i) / n;
        if (Math.sin(a) > 0.55) continue; // no bumps along the belly, so the legs show
        fillEllipse(grid, cx + Math.cos(a) * (rx - r * 0.2), cy - ry * 0.1 + Math.sin(a) * (ry * 1.05 - r * 0.2), r, r, "fluff");
      }
    } else {
      body(cx, cy);
      if (V.fluffy) {
        // long hair: soft bumps along the back, chest and rump (no inner lines)
        // small and set just inside the edge, so the back ripples instead of humping
        const r = Math.max(1.1, 1.3 * Math.max(s, 0.6));
        const n = Math.max(10, Math.round(rx / 0.8));
        for (let i = 0; i <= n; i++) {
          const a = Math.PI * (-0.15 + (1.3 * i) / n);
          fillEllipse(grid, cx - Math.cos(a) * (rx * 0.92 - r * 0.35), cy - ry * 0.1 - Math.sin(a) * (ry * 0.95 - r * 0.35), r, r, "fluff");
        }
      }
    }
    if (V.ruff) {
      fillEllipse(grid, cx + rx * 0.62, cy - ry * 0.1, Math.max(2, rx * 0.3), ry * 1.05, "chest");
      for (const dy of [0.5, 0.95]) fillEllipse(grid, cx + rx * 0.62, cy + ry * dy, Math.max(1.3, rx * 0.2), 1.3, "chest");
    }
    leg(backX - 0.5, cy, step ? 1 : 0, "leg");
    leg(frontX - 0.5, cy, step ? 0 : 1, "leg");
    hx = cx + rx * (stalk ? 0.95 : V.headMin ? 0.9 : V.woolly ? 1.02 : 0.78);
    hy = stalk ? cy - ry * 0.4 : V.woolly ? cy - ry * 0.55 - hry * 0.25 : cy - ry * (V.headMin ? 1 : 0.75) - hry * (V.headMin ? 0.7 : 0.45);
    if (V.neck) {
      // a goat holds its head up on a short neck
      const nl = V.neck.len * s * (1 + (shape.neck || 0) * 0.25);
      const nw = Math.max(2.5, V.neck.w * Math.max(s, 0.7));
      hx = cx + rx * (V.neck.lean || 0.92);
      hy = cy - ry * 0.75 - nl;
      if (V.neck.thick) {
        // a llama's neck: wide where it leaves the chest, tapering up into the
        // head, its front one line from chest to chin
        const base = [[cx + rx * 0.3, cy - ry * 0.85], [cx + rx * 1.02, cy + ry * 0.15]];
        const top = [[hx - hrx * 0.75, hy - hry * 0.1], [hx + hrx * 0.15, hy + hry * 0.85]];
        fillTri(grid, [base[0], base[1], top[1]], "neck");
        fillTri(grid, [base[0], top[1], top[0]], "neck");
        relight(grid, "neck");
      } else {
        // angled forward: from the top of the chest up to under the head
        fillStroke(grid, [[cx + rx * 0.62, cy - ry * 0.2], [hx - 0.5, hy + hry * 0.4]], nw / 2, "neck");
      }
    }
  }

  // the head
  const es = V.ears.size * hs * earScale(shape);
  const ew = es * 0.55 * V.ears.w;
  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [] };
  const eyeSize = V.eye;
  const odd = genes.face && genes.face.odd_eye;
  const iris = (genes.face && genes.face.eyes) || "#7ab84a";

  if (V.facing === "front") {
    for (const side of [-1, 1]) {
      const base = hx + side * hrx * 0.55;
      if (V.ears.type === "half" && side > 0) fillEllipse(grid, hx + side * hrx * 0.95, hy + hry * 0.25, Math.max(1.4, es * 0.2), es * 0.55, "flop");
      if (V.ears.type === "long" || (V.ears.type === "half" && side < 0)) {
        // long standing ears, leaning out a little, behind the head
        const top = hy - hry * 0.55;
        fillStroke(grid, [[base * 0.6 + hx * 0.4, top + 1], [base + side * es * 0.12, top - es * 0.55], [base + side * es * 0.2, top - es]], Math.max(0.9, ew * 0.21), "ear");
      }
      if (!V.ears.fold && !V.ears.type) fillTri(grid, [[base - ew, hy - hry * 0.35], [base + ew, hy - hry * 0.6], [base + side * ew * 0.25, hy - hry * 0.75 - es]], "ear");
    }
    if (V.mane) {
      for (let i = 0; i < 9; i++) {
        const a = (Math.PI * 2 * i) / 9;
        fillEllipse(grid, hx + Math.cos(a) * hrx * 0.95, hy + 0.5 + Math.sin(a) * hry * 0.9, Math.max(1.6, hrx * 0.38), Math.max(1.6, hry * 0.38), "mane");
      }
    }
    if (V.heart) {
      fillEllipse(grid, hx, hy - hry * 0.12, hrx, hry * 0.8, "head");
      fillTri(grid, [[hx - hrx * 0.95, hy - hry * 0.05], [hx + hrx * 0.95, hy - hry * 0.05], [hx, hy + hry]], "head");
    } else {
      fillEllipse(grid, hx, hy, hrx, hry, "head");
    }
    if (V.cheeks) fillEllipse(grid, hx, hy + hry * 0.3, hrx * V.cheeks, hry * 0.6, "head");
    for (const side of [-1, 1]) {
      // dogs: floppy ears hang down the sides of the head; button ears fold over at the top
      const base = hx + side * hrx * 0.55;
      if (V.ears.type === "floppy") fillEllipse(grid, hx + side * hrx * 0.95, hy + hry * 0.15, Math.max(1.3, es * 0.26), es * 0.52, "flop");
      if (V.ears.type === "banana") {
        const top = hy - hry * 0.55;
        // up, with just the tips curling in -- they never meet over the head
        if (V.ears.plain) fillStroke(grid, [[base + side * 0.5, top + 1], [base + side * es * 0.18, top - es]], Math.max(0.8, (V.ears.thick || 0.8) * hs), "ear");
        else fillStroke(grid, [[base + side * 0.5, top + 1], [base + side * es * 0.22, top - es * 0.55], [base + side * es * 0.1, top - es]], Math.max(0.7, ew * 0.2), "ear");
      }
      if (V.ears.type === "out") fillEllipse(grid, hx + side * (hrx + es * 0.3), hy - hry * 0.3, es * 0.5, Math.max(1, es * 0.22), "flop");
      if (V.ears.type === "lop") fillEllipse(grid, hx + side * hrx * 0.95, hy + hry * 0.25, Math.max(1.4, es * 0.2), es * 0.55, "flop");
      if (V.ears.type === "button") fillTri(grid, [[base - ew, hy - hry * 0.78], [base + ew, hy - hry * 0.62], [base + side * ew * 0.7, hy - hry * 0.3]], "flop");
    }
    if (V.tuft) {
      // a sheep's tuft of wool on the forehead
      const r = Math.max(1.5, 1.9 * hs * V.tuft);
      for (const dx of [-0.55, 0, 0.55]) fillEllipse(grid, hx + dx * hrx, hy - hry * 0.88 + Math.abs(dx) * 1.2, r, r, "tuft");
    }
    if (V.ears.fold) {
      // folded ears: small round flaps poking up from the head's top corners
      for (const side of [-1, 1]) {
        fillEllipse(grid, hx + side * hrx * 0.58, hy - hry * 0.88, Math.max(1.5, ew * 0.85), Math.max(1.4, es * 0.32), "fold");
      }
    }
    const c = Math.round(hx);
    const gap = Math.max(1, Math.round(hrx * 0.2)) + (V.eyesWide ? 1 : 0);
    const w = EYE_SHAPES[eyeSize][0].length;
    const eh = EYE_SHAPES[eyeSize].length;
    let ey;
    let ny;
    if (V.mouth === "w") {
      // a 7x4 nose and mouth, centered on column c (p pink, b dark):
      //   . . p p p . .
      //   . . . p . . .
      //   b . . b . . b
      //   . b b . b b .
      // Built up from its bottom row, which sits inside the lower face; the
      // eyes go above it (one row of fur between, two unless eyes are low).
      // never lower than a row of fur above the chin
      const isHead = (x, y) => grid[y] && grid[y][x] && grid[y][x].l === "head";
      let chin = Math.round(hy);
      while (isHead(c, chin + 1)) chin++;
      const bottom = Math.min(Math.round(hy + hry * 0.55), chin - 1);
      const top = bottom - 3;
      ey = top - eh - (V.eyesLow ? 1 : 2);
      // eyes step in toward the middle if they'd touch the edge of the head
      let g = gap;
      const fits = (x0) => [...Array(w + 2).keys()].every((i) => isHead(x0 - 1 + i, ey) && isHead(x0 - 1 + i, ey + eh - 1));
      while (g > 1 && !(fits(c - g - w) && fits(c + g + 1))) g--;
      face.eyes.push({ x: c - g - w, y: ey, size: eyeSize, iris });
      face.eyes.push({ x: c + g + 1, y: ey, size: eyeSize, iris: odd || iris });
      face.pink = [[c - 1, top], [c, top], [c + 1, top], [c, top + 1]];
      face.smile.push([c - 3, top + 2], [c, top + 2], [c + 3, top + 2]);
      face.smile.push([c - 2, top + 3], [c - 1, top + 3], [c + 1, top + 3], [c + 2, top + 3]);
    } else if (V.mouth === "bunny") {
      //   . p p p .
      //   . . p . .
      //   . . b . .
      //   . b . b .
      const isHead = (x, y) => grid[y] && grid[y][x] && grid[y][x].l === "head";
      let chin = Math.round(hy);
      while (isHead(c, chin + 1)) chin++;
      const bottom = Math.min(Math.round(hy + hry * 0.5), chin - 1);
      const top = bottom - 3;
      ey = top - eh - 1;
      let g = gap;
      const fits = (x0) => [...Array(w + 2).keys()].every((i) => isHead(x0 - 1 + i, ey) && isHead(x0 - 1 + i, ey + eh - 1));
      while (g > 1 && !(fits(c - g - w) && fits(c + g + 1))) g--;
      face.eyes.push({ x: c - g - w, y: ey, size: eyeSize, iris });
      face.eyes.push({ x: c + g + 1, y: ey, size: eyeSize, iris: odd || iris });
      face.pink = [[c - 1, top], [c, top], [c + 1, top], [c, top + 1]];
      face.smile.push([c, top + 2], [c - 1, top + 3], [c + 1, top + 3]);
    } else if (V.mouth === "sheep") {
      //   k . k      nostrils
      //   . k .      the mouth
      const isFace = (x, y) => grid[y] && grid[y][x] && grid[y][x].l === "head";
      let chin = Math.round(hy);
      while (isFace(c, chin + 1)) chin++;
      ny = chin - 2;
      face.smile.push([c - 1, ny], [c + 1, ny], [c, ny + 1]);
      ey = Math.round(hy - hry * 0.2) - eh + 1;
      let g = gap;
      const fits = (x0) => [...Array(w + 2).keys()].every((i) => isFace(x0 - 1 + i, ey) && isFace(x0 - 1 + i, ey + eh - 1));
      while (g > 1 && !(fits(c - g - w) && fits(c + g + 1))) g--;
      face.eyes.push({ x: c - g - w, y: ey, size: eyeSize, iris });
      face.eyes.push({ x: c + g + 1, y: ey, size: eyeSize, iris: odd || iris });
    } else if (V.mouth === "llama") {
      //   k . k      nostrils
      //   . . .
      //   . k .      a little mouth
      const isFace = (x, y) => grid[y] && grid[y][x] && (grid[y][x].l === "head" || grid[y][x].l === "snout");
      fillEllipse(grid, hx, hy + hry * 0.5, Math.max(2.2, hrx * 0.6), Math.max(1.8, hry * 0.48), "snout");
      let chin = Math.round(hy);
      while (isFace(c, chin + 1)) chin++;
      ny = chin - 3;
      face.smile.push([c - 1, ny], [c + 1, ny], [c, ny + 2]);
      ey = Math.round(hy - hry * (V.tuft ? 0.05 : 0.3)) - eh + 1; // below a topknot, never under its edge
      let g = gap;
      const fits = (x0) => [...Array(w + 2).keys()].every((i) => isFace(x0 - 1 + i, ey) && isFace(x0 - 1 + i, ey + eh - 1));
      while (g > 1 && !(fits(c - g - w) && fits(c + g + 1))) g--;
      face.eyes.push({ x: c - g - w, y: ey, size: eyeSize, iris });
      face.eyes.push({ x: c + g + 1, y: ey, size: eyeSize, iris: odd || iris });
    } else if (V.mouth === "goat") {
      // a long face: eyes high, nostrils low on the muzzle, a beard below
      const isFace = (x, y) => grid[y] && grid[y][x] && (grid[y][x].l === "head" || grid[y][x].l === "snout");
      fillEllipse(grid, hx, hy + hry * 0.55, Math.max(2.2, hrx * 0.62), Math.max(1.8, hry * 0.45), "snout");
      let chin = Math.round(hy);
      while (isFace(c, chin + 1)) chin++;
      ny = chin - 2;
      face.smile.push([c - 1, ny], [c + 1, ny], [c, ny + 1]);
      if (V.beard) fillTri(grid, [[c - 1.5, chin + 0.5], [c + 2.5, chin + 0.5], [c + 0.5, chin + 0.5 + 4.2 * hs]], "beard");
      ey = Math.round(hy - hry * 0.35) - eh + 1;
      let g = gap;
      const fits = (x0) => [...Array(w + 2).keys()].every((i) => isFace(x0 - 1 + i, ey) && isFace(x0 - 1 + i, ey + eh - 1));
      while (g > 1 && !(fits(c - g - w) && fits(c + g + 1))) g--;
      face.eyes.push({ x: c - g - w, y: ey, size: eyeSize, iris });
      face.eyes.push({ x: c + g + 1, y: ey, size: eyeSize, iris: odd || iris });
    } else if (V.mouth === "fox") {
      fillTri(grid, [[hx - hrx * 0.5, hy - hry * 0.05], [hx + hrx * 0.5, hy - hry * 0.05], [hx, hy + hry * 1.02]], "snout");
      const isFace = (x, y) => grid[y] && grid[y][x] && (grid[y][x].l === "head" || grid[y][x].l === "snout");
      let chin = Math.round(hy);
      while (isFace(c, chin + 1)) chin++;
      ny = chin - 1;
      face.noseDark.push([c - 1, ny], [c, ny], [c + 1, ny], [c, ny + 1]);
      ey = Math.round(hy - hry * 0.25) - eh + 1;
      let g = gap;
      const fits = (x0) => [...Array(w + 2).keys()].every((i) => isFace(x0 - 1 + i, ey) && isFace(x0 - 1 + i, ey + eh - 1));
      while (g > 1 && !(fits(c - g - w) && fits(c + g + 1))) g--;
      face.eyes.push({ x: c - g - w, y: ey, size: eyeSize, iris });
      face.eyes.push({ x: c + g + 1, y: ey, size: eyeSize, iris: odd || iris });
    } else if (V.mouth === "dog") {
      // a muzzle with a big dark nose on top, a mouth under it, and a
      // tongue that comes and goes; the eyes a row of fur above the muzzle
      //   . k k k .
      //   . . k . .
      //   b b t b b     (t: the tongue, some frames)
      ny = Math.round(hy + hry * 0.12);
      fillEllipse(grid, hx, ny + 1.3, Math.max(2.5, 3.1 * hs * snoutSize), Math.max(1.8, 2.2 * hs * Math.sqrt(snoutSize)), "snout");
      const isHead = (x, y) => grid[y] && grid[y][x] && (grid[y][x].l === "head" || grid[y][x].l === "snout");
      ey = ny - eh - 2;
      let g = gap;
      const fits = (x0) => [...Array(w + 2).keys()].every((i) => isHead(x0 - 1 + i, ey) && isHead(x0 - 1 + i, ey + eh - 1));
      while (g > 1 && !(fits(c - g - w) && fits(c + g + 1))) g--;
      face.eyes.push({ x: c - g - w, y: ey, size: eyeSize, iris });
      face.eyes.push({ x: c + g + 1, y: ey, size: eyeSize, iris: odd || iris });
      face.noseDark.push([c - 1, ny], [c, ny], [c + 1, ny], [c, ny + 1]);
      face.smile.push([c - 2, ny + 2], [c - 1, ny + 2], [c + 1, ny + 2], [c + 2, ny + 2]);
      face.tongue.push([c, ny + 2], [c, ny + 3]);
    } else {
      const eyeTop = Math.round(hy - hry * 0.3) - 1; // eyes sit a pixel high...
      ey = eyeTop + (V.eyesLow ? 1 : 0); // ...unless this design sets them lower
      ny = ey + eh + 1;
      if (hry > 4) face.mouth.push([c - 2, ny + 1], [c + 1, ny + 1]);
      face.eyes.push({ x: c - gap - w, y: ey, size: eyeSize, iris });
      face.eyes.push({ x: c + gap, y: ey, size: eyeSize, iris: odd || iris });
      face.nose = { x: c - 1, y: ny, w: 2 };
    }
    if (V.ears.tufts) for (const side of [-1, 1]) face.tufts.push([Math.round(hx + side * hrx * 0.55 + side * ew * 0.25), Math.round(hy - hry * 0.75 - es) - 1]);
  } else if (V.facing === "three") {
    fillTri(grid, [[hx - hrx * 0.95, hy - hry * 0.2], [hx - hrx * 0.15, hy - hry * 0.85], [hx - hrx * 0.85, hy - hry * 0.85 - es * 0.85]], "farear");
    fillTri(grid, [[hx - hrx * 0.15, hy - hry * 0.9], [hx + hrx * 0.85, hy - hry * 0.55], [hx + hrx * 0.25, hy - hry * 0.9 - es]], "ear");
    fillEllipse(grid, hx, hy, hrx, hry, "head");
    if (V.cheeks) fillEllipse(grid, hx + hrx * 0.1, hy + hry * 0.3, hrx * V.cheeks, hry * 0.6, "head");
    fillEllipse(grid, hx + hrx * 0.62, hy + hry * 0.35, hrx * 0.45, hry * 0.36, "snout");
    const ey = Math.round(hy - hry * 0.3);
    const w = EYE_SHAPES[eyeSize][0].length;
    face.eyes.push({ x: Math.round(hx - hrx * 0.55), y: ey, size: eyeSize, iris, narrow: true });
    face.eyes.push({ x: Math.round(hx + hrx * 0.12), y: ey, size: eyeSize, iris: odd || iris });
    const nx = Math.round(hx + hrx * 0.12) + w + 1;
    const ny = ey + EYE_SHAPES[eyeSize].length;
    face.nose = { x: nx - 1, y: ny, w: 2 };
    if (hry > 4) face.mouth.push([nx - 1, ny + 1]);
    if (V.ears.tufts) {
      face.tufts.push([Math.round(hx + hrx * 0.25), Math.round(hy - hry * 0.9 - es) - 1]);
      face.tufts.push([Math.round(hx - hrx * 0.85), Math.round(hy - hry * 0.85 - es * 0.85) - 1]);
    }
  } else {
    // side view: one eye, a snout pointing ahead
    const floppy = V.ears.type === "floppy" || V.ears.type === "lop" || V.ears.type === "half" || V.ears.type === "out";
    const banana = V.ears.type === "banana";
    const longEars = V.ears.type === "long" || V.ears.type === "half";
    const earTop = hy - hry * 0.6;
    if (longEars) {
      // two long ears swept back a little, the far one behind and darker
      fillStroke(grid, [[hx - hrx * 0.45, earTop + 1], [hx - hrx * 0.75, earTop - es * 0.5], [hx - hrx * 0.95, earTop - es]], Math.max(0.9, ew * 0.21), "farear");
    }
    if (!floppy && !longEars && !banana) fillTri(grid, [[hx - hrx * 0.9, hy - hry * 0.3], [hx - hrx * 0.05, hy - hry * 0.85], [hx - hrx * 0.75, hy - hry * 0.75 - es * 0.9]], "farear");
    if (V.heart) {
      fillEllipse(grid, hx, hy - hry * 0.15, hrx, hry * 0.78, "head");
      fillTri(grid, [[hx - hrx * 0.92, hy - hry * 0.1], [hx + hrx * 0.98, hy - hry * 0.1], [hx + hrx * 0.3, hy + hry * 0.95]], "head");
    } else {
      fillEllipse(grid, hx, hy, hrx, hry, "head");
    }
    const sr = Math.max(1.3, (V.snoutR || 1.8) * hs);
    const sy = hy + hry * 0.3;
    const sl = (V.snoutLen || 0) * hs * snoutSize;
    if (V.snout === "llama") {
      fillEllipse(grid, hx + hrx * 0.85, sy + 0.3, Math.max(2, (V.snoutLen || 2.5) * hs * snoutSize), Math.max(1.5, 1.8 * hs), "snout");
    } else if (V.snout === "goat") {
      // a long face tapering to the muzzle; a Roman nose bulges along the top
      fillEllipse(grid, hx + hrx * 0.9, sy, Math.max(2.4, 3.1 * hs * snoutSize), Math.max(1.4, 1.7 * hs), "snout");
      if (V.roman) fillEllipse(grid, hx + hrx * 0.75, sy - 1.2 * hs, Math.max(1.8, 2.4 * hs), Math.max(1.2, 1.3 * hs), "snout");
    } else if (V.snout === "sheep") fillEllipse(grid, hx + hrx * 0.7, sy + 0.5, Math.max(1.8, 2.3 * hs), Math.max(1.6, 1.9 * hs), "snout");
    else if (V.snout === "bunny") fillEllipse(grid, hx + hrx * 0.75, sy, Math.max(1.4, 1.7 * hs), Math.max(1.3, 1.6 * hs), "snout");
    else if (V.snout === "square") fillRect(grid, hx + hrx * 0.3, sy - sr, hrx * 0.7 + sl, sr * 2, "snout");
    else if (V.snout === "wedge") fillTri(grid, [[hx + hrx * 0.3, sy - sr], [hx + hrx * 0.3, sy + sr], [hx + hrx + (V.snoutLen || 2.5) * hs * snoutSize, sy + sr * 0.3]], "snout");
    else fillEllipse(grid, hx + hrx * 0.8, sy, 1.8 * hs + 0.6, sr, "snout");
    if (V.tuft) {
      const r = Math.max(1.5, 1.9 * hs * V.tuft);
      for (const dx of [-0.6, -0.1]) fillEllipse(grid, hx + dx * hrx, hy - hry * 0.85, r, r, "tuft");
    }
    if (banana) {
      // two banana ears, the far one behind and darker, tips curving forward
      const top = hy - hry * 0.6;
      const thick = V.ears.thick || 0;
      const r = thick ? Math.max(0.9, thick * hs) : Math.max(0.7, ew * 0.2);
      const ear = (bx, label) =>
        V.ears.plain
          ? fillStroke(grid, [[bx, top + 1], [bx + es * 0.12, top - es]], r, label) // a clean spike, leaning a little forward
          : fillStroke(grid, [[bx, top + 1], [bx - es * (thick ? 0.05 : 0.15), top - es * 0.5], [bx + es * (thick ? 0.08 : 0.12), top - es]], r, label);
      ear(hx - hrx * (thick ? 0.75 : 0.8), "farear"); // spaced apart so the two read as two
      ear(hx + hrx * (thick ? 0.3 : -0.05), "ear");
    } else if (V.ears.type === "out") fillEllipse(grid, hx - hrx * 0.75, hy - hry * 0.2, es * 0.55, Math.max(1, es * 0.24), "flop");
    else if (V.ears.type === "lop" || V.ears.type === "half") fillEllipse(grid, hx - hrx * 0.35, hy + es * 0.18, Math.max(1.4, es * 0.22), es * 0.55, "flop");
    else if (floppy) fillEllipse(grid, hx - hrx * 0.3, hy + es * 0.08, Math.max(1.4, es * 0.32), es * 0.6, "flop");
    else if (banana) {
      // drawn above
    } else if (longEars) fillStroke(grid, [[hx - hrx * 0.1, earTop + 1], [hx - hrx * 0.3, earTop - es * 0.55], [hx - hrx * 0.45, earTop - es]], Math.max(0.9, ew * 0.21), "ear");
    else fillTri(grid, [[hx - hrx * 0.45, hy - hry * 0.8], [hx + hrx * 0.45, hy - hry * 0.75], [hx - hrx * 0.05, hy - hry * 0.75 - es]], "ear");
    const ey = Math.round(hy - hry * 0.35);
    const ex = Math.round(hx + hrx * 0.1);
    face.eyes.push({ x: ex, y: ey, size: eyeSize, iris: odd || iris });
    if (V.snout === "square") {
      // a dog's snout: a big dark nose on the tip, the mouth along the bottom, a tongue
      const nx = Math.round(hx + hrx + sl) - 1;
      const ny = Math.round(sy - sr);
      face.noseDark.push([nx, ny], [nx - 1, ny], [nx, ny + 1]);
      const my = Math.round(sy + sr) - 1;
      face.smile.push([nx, my], [nx - 1, my], [nx - 2, my]);
      face.tongue.push([nx - 2, my + 1], [nx - 2, my + 2], [nx - 3, my + 1]);
    } else if (V.snout === "bunny") {
      // a pink nose on the tip of the little muzzle, a tiny mouth under it
      const nx = Math.round(hx + hrx * 0.75 + 1.7 * hs);
      const ny = Math.round(sy - 1);
      face.pink.push([nx - 1, ny], [nx, ny]);
      face.smile.push([nx - 1, ny + 2]);
    } else if (V.snout === "llama") {
      // a nostril near the tip and the split lip under it
      const tipX = Math.round(hx + hrx * 0.85 + Math.max(2, (V.snoutLen || 2.5) * hs * snoutSize)) - 1;
      const ny = Math.round(sy - 0.5);
      face.smile.push([tipX - 1, ny], [tipX, ny + 2], [tipX - 1, ny + 2], [tipX - 2, ny + 1]);
    } else if (V.snout === "goat") {
      // a nostril at the tip, a short mouth line, a beard under the chin
      const tipX = Math.round(hx + hrx * 0.9 + Math.max(2.4, 3.1 * hs * snoutSize)) - 1;
      const ny = Math.round(sy - 0.5);
      face.smile.push([tipX - 1, ny], [tipX - 1, ny + 2], [tipX - 2, ny + 2]);
      if (V.beard) {
        const bx = hx + hrx * 0.95;
        const by = sy + Math.max(1.4, 1.7 * hs) - 0.5;
        fillTri(grid, [[bx - 1.8, by - 0.5], [bx + 1.2, by - 0.5], [bx - 1, by + 4.2 * hs]], "beard");
      }
    } else if (V.snout === "sheep") {
      // a long round muzzle: nostrils near the front, a mouth line under
      const tipX = Math.round(hx + hrx * 0.7 + 2.3 * hs);
      const ny = Math.round(sy);
      face.smile.push([tipX - 1, ny], [tipX - 2, ny + 2], [tipX - 1, ny + 2]);
    } else if (V.darkNose && V.snout === "wedge") {
      // a fox: a small dark nose on the point of the snout
      const tipX = Math.round(hx + hrx + (V.snoutLen || 2.5) * hs * snoutSize) - 1;
      const tipY = Math.round(sy + sr * 0.3) - 1;
      face.noseDark.push([tipX, tipY], [tipX - 1, tipY]);
    } else {
      const nx = Math.round(hx + hrx + (V.snout === "wedge" ? 2 * hs : 1.6 * hs));
      const ny = Math.round(sy - sr * 0.5);
      face.nose = { x: nx - 1, y: ny, w: 2 };
    }
  }

  if (V.ramHorns) {
    const r = Math.max(0.8, 1.1 * hs);
    const curl = (bx, by, dir, size) => {
      const pts = [];
      for (let k = 0; k <= 10; k++) {
        const a = -Math.PI * 0.6 + (k / 10) * Math.PI * 1.7;
        const rr = size * (1 - k * 0.055);
        pts.push([bx + dir * Math.cos(a) * rr, by + Math.sin(a) * rr]);
      }
      fillStroke(grid, pts, r, "horn");
    };
    const size = 3.4 * hs * (V.hornSize || 1);
    // from the front the curls sit out beside the head, clear of the eyes
    if (V.facing === "front") for (const side of [-1, 1]) curl(hx + side * (hrx + size * 0.55), hy - hry * 0.15, side, size * 0.85);
    else curl(hx - hrx * 0.3, hy - hry * 0.1, -1, size);
    if (V.ramHorns === "jacob") {
      // Jacob sheep: a second pair standing up off the top of the head
      for (const side of V.facing === "front" ? [-1, 1] : [-1]) {
        const bx = hx + side * hrx * (V.facing === "front" ? 0.35 : 0.15);
        fillStroke(grid, [[bx, hy - hry * 0.8], [bx + side * 0.8, hy - hry * 0.8 - 3 * hs], [bx + side * 1.8, hy - hry * 0.8 - 4.2 * hs]], r, "horn");
      }
    }
  }
  if (V.goatHorns) {
    const L = V.goatHorns * hs * (1 + (shape.horns || 0) * 0.3);
    const top = hy - hry * 0.8;
    const horn = (bx, dir) => {
      // thick at the base, curving up then back, a thin point
      const pts = [[bx, top + 0.5], [bx + dir * L * 0.25, top - L * 0.65], [bx + dir * L * 0.7, top - L * 0.9], [bx + dir * L * 1.05, top - L * 0.65]];
      pts.slice(1).forEach((p, i) => fillStroke(grid, [pts[i], p], Math.max(0.55, (1.15 - i * 0.28) * hs), "horn"));
    };
    if (V.facing === "front") for (const side of [-1, 1]) horn(hx + side * hrx * 0.38, side * 0.55);
    else horn(hx - hrx * 0.1, -1);
  }
  if (V.hooves) {
    relabel(grid, ["leg"], "hoof", (x, y) => y >= GROUND - 1);
    relabel(grid, ["farleg"], "farhoof", (x, y) => y >= GROUND - 1);
  }
  if (V.earTips) {
    let top = GRID_H;
    grid.forEach((row, y) => row.forEach((c) => c && (c.l === "ear" || c.l === "farear") && (top = Math.min(top, y))));
    relabel(grid, ["ear", "farear"], "eartip", (x, y) => y < top + Math.max(1.5, es * 0.32));
  }
  if (V.socks) {
    const sockTop = GROUND - Math.max(1, Math.round(legLen * 0.45));
    relabel(grid, ["leg"], "sock", (x, y) => y >= sockTop);
    relabel(grid, ["farleg"], "farsock", (x, y) => y >= sockTop);
  }
  if (V.tailTip && tailEnd) {
    const r = Math.max(1.6, tw * 1.5);
    relabel(grid, ["tail"], "tip", (x, y) => Math.hypot(x + 0.5 - tailEnd[0], y + 0.5 - tailEnd[1]) <= r);
  }
  if (V.bareFace) {
    // a sheep's face, ears and legs aren't wool: they wear the skin color
    relabel(grid, ["flop", "ear", "farear"], "face", (x, y, c) => (c.isEar = true));
    relabel(grid, ["head", "snout"], "face", () => true);
    relabel(grid, ["leg"], "skin", () => true);
    relabel(grid, ["farleg"], "farskin", () => true);
    relight(grid, "face");
  }
  relight(grid, "body");
  relight(grid, "head");
  relight(grid, "snout");
  // where everything is, for painting the coat by body region
  let faceBox = null;
  if (face.eyes.length) {
    const xs = face.eyes.map((e) => e.x);
    const ew2 = EYE_SHAPES[eyeSize][0].length;
    const lowest = Math.max(...[...face.smile, ...face.pink, ...face.noseDark, ...face.mouth].map(([, y]) => y), face.nose ? face.nose.y : 0, face.eyes[0].y + 1);
    faceBox = { x0: Math.min(...xs) - 1, x1: Math.max(...xs) + ew2, y0: face.eyes[0].y - 1, y1: lowest + 1 };
  }
  const noses = [...face.pink, ...face.noseDark];
  const noseTop = noses.length ? Math.min(...noses.map(([, y]) => y)) : face.nose ? face.nose.y : null;
  const geo = {
    cx, cy, rx, ry, legTop: sit ? GROUND - legLen - ry * 0.6 : crouch || upright ? GROUND - ry * 0.9 : cy,
    tail: [cx - rx + 1, cy - ry * 0.4, tailLen], head: [hx, hy, hrx, hry],
    faceBox, muzzle: noseTop === null ? null : { top: noseTop, c: Math.round(hx) }, woolly: !!V.woolly,
  };
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: !V.ears.fold && !V.ears.plain, headX: hx, face, center: [cx, cy], scale: s,
    softOutline: V.softOutline, softNeck: V.softNeck, geo, earStripe: V.ears.type === "long",
  };
}

// --- turtles ----------------------------------------------------------------------
// A domed shell (plates painted by paintTurtle) with a rim along the bottom,
// four stubby legs (or flippers) under it, a tiny tail, and a head poking out
// on a neck -- side-on, facing us, or tucked in with just the eyes peeking.

function buildTurtle(genes, stage, frame, V) {
  const shape = genes.shape || {};
  const grid = makeGrid();
  // turtles stay readable as babies: they shrink less than furry pets
  const s = 0.62 + stage.body * 0.38;
  const hs = 0.75 + stage.head * 0.25;
  const step = frame % 2;
  const rx = half(V.body.rx * s + (shape.length || 0) / 2);
  const ry = half(V.body.ry * s * (1 + (shape.dome || 0) * 0.2));
  const legLen = Math.max(1.5, V.leg.len * stage.leg);
  const base = GROUND - legLen; // the bottom of the shell
  const cx = 30;
  const legW = Math.max(2, V.leg.w * Math.max(s, 0.7));
  const frontX = cx + rx * 0.55;
  const backX = cx - rx * 0.55;

  const leg = (x, lift, label) => fillEllipse(grid, x, (base + GROUND) / 2 - lift * 0.6, legW / 2, (GROUND - base) / 2 + 1, label);
  // a sea turtle's flipper reaches forward and down from under the shell
  const flipper = (x, len, lift, label) =>
    fillTri(grid, [[x - 2, base - 1.5], [x + 2, base - 1.5], [x + len * 0.7, base + 2.8 - lift]], label);

  // far legs, then the tail
  if (V.flippers) {
    flipper(frontX + 2, 9 * s, step, "farleg");
  } else {
    leg(backX + 2, step ? 0 : 1, "farleg");
    leg(frontX + 2, step ? 1 : 0, "farleg");
  }
  const tl = (V.tailLen || 2.2) * s + 0.8;
  fillTri(grid, [[cx - rx + 1, base - 1.6], [cx - rx + 1, base + 0.4], [cx - rx - tl, base]], "tail");

  // the neck and head (side view: behind the shell's front edge)
  const hrx = V.head.rx * hs;
  const hry = V.head.ry * hs;
  const neckLen = (V.neck || 2.2) * s * (1 + (shape.neck || 0) * 0.35);
  let hx = cx + rx + neckLen + hrx * 0.55;
  let hy = base - ry * 0.3 - (V.headUp || 0) * s;
  if (V.facing === "front") {
    hx = cx + rx * 0.85;
    hy = base - ry * 0.12;
  }
  if (!V.tucked && V.facing !== "front") {
    fillStroke(grid, [[cx + rx - 1.5, base - 1.2], [hx - hrx * 0.5, hy + hry * 0.25]], Math.max(1.1, hry * 0.55), "neck");
  }

  // the shell: a dome over a rim
  for (let y = Math.floor(base - ry - 1); y < base; y++) {
    for (let x = Math.floor(cx - rx - 1); x <= Math.ceil(cx + rx + 1); x++) {
      const nx = (x + 0.5 - cx) / rx;
      const ny = (y + 0.5 - base) / ry;
      if (nx * nx + ny * ny <= 1) put(grid, x, y, { l: "shell", nx, ny: ny * 0.9 + 0.1 });
    }
  }
  if (V.ridges) {
    // a snapper's ridged shell: three little peaks along the top
    for (const t of [-0.45, 0, 0.45]) {
      const px = cx + t * rx;
      const top = base - ry * Math.sqrt(Math.max(0, 1 - t * t));
      fillTri(grid, [[px - 1.6, top + 1.2], [px + 1.6, top + 1.2], [px, top - 1.6 * s - 0.5]], "shell");
    }
  }
  fillRect(grid, cx - rx * 0.97, base - 1, rx * 1.94, 1.6, "rim");
  relight(grid, "shell");

  // near legs (or flippers) in front of the rim
  if (V.flippers) {
    flipper(frontX, 11 * s, step, "leg");
    fillEllipse(grid, backX - 2, base + 0.8, Math.max(2, 3 * s), 1.5, "leg");
  } else {
    leg(backX, step ? 1 : 0, "leg");
    leg(frontX, step ? 0 : 1, "leg");
  }

  // the face
  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [], glints: [] };
  const iris = (genes.face && genes.face.eyes) || "#c8861e";
  if (V.tucked) {
    // hiding: a dark opening at the front of the shell, two eyes peeking out
    const ox = cx + rx * 0.78;
    const oy = base - ry * 0.32;
    fillEllipse(grid, ox, oy, Math.max(1.6, 2.4 * s), Math.max(1.3, 1.7 * s), "hole");
    const c = Math.round(ox);
    const ey = Math.round(oy) - 1;
    face.glints.push([c - 1, ey, iris], [c + 1, ey, iris]);
  } else {
    fillEllipse(grid, hx, hy, hrx, hry, "head");
    relight(grid, "head");
    const c = Math.round(hx);
    if (V.facing === "front") {
      const ey = Math.round(hy - hry * 0.35);
      const g = Math.max(1, Math.round(hrx * 0.22));
      face.eyes.push({ x: c - g - 2, y: ey, size: "duo", iris }, { x: c + g + 1, y: ey, size: "duo", iris });
      const my = ey + 3;
      face.smile.push([c - 2, my], [c - 1, my + 1], [c, my + 1], [c + 1, my + 1], [c + 2, my]);
    } else {
      const ex = Math.round(hx + hrx * 0.05);
      const ey = Math.round(hy - hry * 0.5);
      face.eyes.push({ x: ex, y: ey, size: "duo", iris });
      const my = Math.round(hy + hry * 0.4);
      face.smile.push([c + 1, my], [Math.round(hx + hrx) - 1, my], [Math.round(hx + hrx) - 2, my]);
      face.noseDark.push([Math.round(hx + hrx) - 1, Math.round(hy - hry * 0.2)]);
    }
  }

  const geo = {
    cx, cy: base - ry * 0.5, rx, ry, base, legTop: base - 1, tail: [cx - rx, base, tl], head: [hx, hy, hrx, hry],
    faceBox: null, muzzle: null, plate: V.plate || 3.6,
  };
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: hx, face, center: [cx, base - ry * 0.5], scale: s,
    softOutline: true, softNeck: false, geo,
  };
}

// --- lizards ----------------------------------------------------------------------
// A long, low body on four sprawled, bent legs with splayed toes; a long
// tapering tail (or a fat gecko tail, or a chameleon's curl); a wedge of a
// head with a jaw line, on a short neck. Extras make the breeds: a crest of
// spines, a dewlap, a spiky beard, a neck frill, a chameleon's helmet, head
// horns, a forked tongue.

function buildLizard(genes, stage, frame, V) {
  const shape = genes.shape || {};
  const grid = makeGrid();
  const s = 0.6 + stage.body * 0.4; // lizards stay readable as babies too
  const hs = 0.72 + stage.head * 0.28;
  const step = frame % 2;
  const wag = frame % 2;
  const rx = half(V.body.rx * s + (shape.length || 0) / 2);
  const ry = half(V.body.ry * s + (shape.height || 0) / 5);
  const legH = Math.max(3, V.leg.len * 1.4 * (0.7 + stage.leg * 0.3) * (1 + (shape.legs || 0) * 0.3));
  const cx = 34;
  const sprawl = V.stance !== "stand";
  // sprawled: the belly just off the ground, so the short legs show beneath
  const by = sprawl ? GROUND - ry - 2.2 - (V.chestUp || 0) * 0.4 : GROUND - legH - ry * 0.55;
  const lw = sprawl ? Math.max(1.05, V.leg.w * s * 0.55) : Math.max(0.8, (V.leg.w * s) / 2);
  const hipX = cx - rx * 0.6;
  const shoulderX = cx + rx * 0.55;

  // sprawled: a rounded shoulder (or hip) on the body's side, and a short,
  // thick leg angling out from under the body to a foot with splayed toes
  const sprawlLeg = (x, dir, lift, label) => {
    const l = label === "leg" ? "limb" : label; // near legs get a line where they cross the body
    const bottom = by + ry * 0.85;
    const foot = [x + dir * 3 * s + lift * dir * 0.7, GROUND - 1.1];
    fillStroke(grid, [[x, bottom - 0.5], [x + dir * 1.6 * s, bottom + 0.6 - lift * 0.4], foot], lw, l);
    if (l === "limb") fillEllipse(grid, x + dir * 0.6, by + ry * 0.35, Math.max(1.6, 2 * s), Math.max(1.4, 1.6 * s), l);
    fillRect(grid, dir > 0 ? foot[0] - 0.5 : foot[0] - 2.5, GROUND - 1, 3, 1, l); // splayed toes
  };
  // standing (a monitor): the leg bends out at the elbow and ends in a splayed foot
  const leg = (x, dir, lift, label) => {
    if (sprawl) return sprawlLeg(x, dir, lift, label);
    const knee = [x + dir * 2.4 * s, GROUND - legH * 0.6 - lift];
    fillStroke(grid, [[x, by + ry * 0.3], knee, [x + dir * 0.8, GROUND - 1.2 - lift * 0.5]], lw, label);
    fillRect(grid, x + dir * 0.4 - 1, GROUND - 1 - lift * 0.5, 3, 1, label); // the toes
  };
  leg(hipX + 2, -1, step ? 0 : 1, "farleg");
  leg(shoulderX + 2, 1, step ? 1 : 0, "farleg");

  // the tail
  const L = V.tail.len * s * (1 + (shape.tail || 0) * 0.25);
  const tx = cx - rx + 1;
  const ty = by + ry * 0.1;
  let tailEnd;
  if (V.tail.type === "chunky") {
    fillEllipse(grid, tx - L * 0.45, ty + 0.5, L * 0.55, Math.max(1.6, ry * 0.75), "tail"); // a gecko's fat tail
    tailEnd = [tx - L, ty];
  } else if (V.tail.type === "under") {
    // drawn after the body (below) so it lies in front of it
    tailEnd = null;
  } else if (V.tail.type === "curl") {
    // a chameleon's tail: back and down, then a spiral curling under
    const cxT = tx - L * 0.5;
    const cyT = ty + L * 0.22;
    const pts = [[tx, ty], [tx - L * 0.25, ty + 0.4]];
    for (let k = 0; k <= 14; k++) {
      const a = -Math.PI / 2 - (k / 14) * Math.PI * 1.6; // from the top, round to the left and under
      const r = L * 0.24 * (1 - k * 0.045);
      pts.push([cxT + Math.cos(a) * r, cyT + Math.sin(a) * r]);
    }
    pts.slice(1).forEach((p, i) => fillStroke(grid, [pts[i], p], Math.max(0.6, ry * 0.42 * (1 - i * 0.045)), "tail"));
    tailEnd = pts[pts.length - 1];
  } else {
    // long and tapering, sweeping down to the ground and up at the tip
    const pts = [[tx, ty], [tx - L * 0.35, ty + ry * 0.6], [tx - L * 0.7, GROUND - 1.8], [tx - L, GROUND - 2.4 - wag]];
    const widths = [ry * 0.75, ry * 0.5, ry * 0.3, 0.55];
    pts.slice(1).forEach((p, i) => {
      for (let k = 0; k <= 6; k++) {
        const t = k / 6;
        const r = Math.max(0.55, widths[i] + (widths[i + 1] - widths[i]) * t);
        fillEllipse(grid, pts[i][0] + (p[0] - pts[i][0]) * t, pts[i][1] + (p[1] - pts[i][1]) * t, r, r, "tail");
      }
    });
    tailEnd = pts[pts.length - 1];
  }

  // the neck frill sits behind the head
  const hrx = V.head.rx * hs;
  const hry = V.head.ry * hs;
  const hx = cx + rx + (V.neck || 1.6) * s + hrx * 0.4;
  const hy = by - ry * (sprawl ? 0.15 : 0.4) - (V.headUp || 0) * s;
  if (V.frill) {
    // a fan standing up around the neck, wider than the head, with a scalloped edge
    const fr = hry * 2.6;
    fillEllipse(grid, hx - hrx * 0.5, hy - 0.5, fr * 0.62, fr, "frill");
    for (let k = 0; k < 7; k++) {
      const a = -Math.PI * 0.85 + (k / 6) * Math.PI * 1.7;
      fillEllipse(grid, hx - hrx * 0.5 + Math.cos(a) * fr * 0.55, hy - 0.5 + Math.sin(a) * fr * 0.92, 1.2, 1.2, "frill");
    }
  }

  // the body
  fillEllipse(grid, cx, by, rx, ry, "body");
  if (V.chameleon) fillEllipse(grid, cx - rx * 0.05, by - ry * 0.45, rx * 0.85, ry * 1.15, "body"); // a chameleon: tall and flattened
  // the neck and head: a wedge with a jaw line
  fillStroke(grid, [[cx + rx - 1, by - ry * 0.2], [hx - hrx * 0.4, hy + hry * 0.2]], Math.max(1.2, ry * 0.65), "neck");
  fillEllipse(grid, hx, hy, hrx, hry, "head");
  const sl = (V.snout || 2.2) * hs;
  fillTri(grid, [[hx, hy - hry * 0.75], [hx, hy + hry * 0.8], [hx + hrx + sl, hy + hry * 0.25]], "head");
  if (V.casque) fillTri(grid, [[hx - hrx * 0.9, hy - hry * 0.4], [hx + hrx * 0.4, hy - hry * 0.9], [hx - hrx * 1.1, hy - hry * 2.1]], "head");

  if (V.tail.type === "under") {
    // a tail that curls down behind and comes forward along the ground,
    // in front of the body (an outline keeps the two apart)
    const pts = [[tx + 1, ty], [tx - L * 0.4, ty + ry * 0.1], [tx - L * 0.52, GROUND - 1.6], [tx - L * 0.2, GROUND - 0.8], [cx - rx * 0.2 + wag, GROUND - 1]];
    const widths = [ry * 0.75, ry * 0.55, ry * 0.42, ry * 0.32, 0.55];
    pts.slice(1).forEach((p, i) => {
      for (let k = 0; k <= 6; k++) {
        const t = k / 6;
        const r = Math.max(0.55, widths[i] + (widths[i + 1] - widths[i]) * t);
        fillEllipse(grid, pts[i][0] + (p[0] - pts[i][0]) * t, pts[i][1] + (p[1] - pts[i][1]) * t, r, r, "tail");
      }
    });
    tailEnd = pts[pts.length - 1];
  }

  // near legs
  leg(hipX, -1, step ? 1 : 0, "leg");
  leg(shoulderX, 1, step ? 0 : 1, "leg");

  // extras
  const crest = (V.crest || 0) * s * (1 + (shape.crest || 0) * 0.35);
  if (crest) {
    // a row of spines from behind the head down the back and onto the tail
    const n = Math.max(5, Math.round(rx / 1.3));
    for (let k = 0; k < n; k++) {
      const t = k / (n - 1);
      const x = cx + rx * 0.85 - t * rx * 2;
      const top = by - ry * Math.sqrt(Math.max(0, 1 - ((x - cx) / rx) ** 2)) + 0.3;
      const h = crest * (1 - Math.abs(t - 0.3) * 0.8);
      fillTri(grid, [[x - 0.9, top + 0.5], [x + 0.9, top + 0.5], [x - 0.3, top - Math.max(0.8, h)]], "spine");
    }
  }
  if (V.dewlap) fillEllipse(grid, hx - hrx * 0.1, hy + hry + 1.4 * hs, Math.max(1.4, hrx * 0.55), Math.max(1.2, 1.8 * hs), "dewlap");
  if (V.beard) {
    for (const dx of [-0.6, 0, 0.6]) {
      const bx = hx + dx * hrx;
      fillTri(grid, [[bx - 1, hy + hry * 0.6], [bx + 1, hy + hry * 0.6], [bx - 0.8, hy + hry + 2.2 * hs]], "spine");
    }
  }
  if (V.horns) {
    for (const dx of [-0.8, -0.3, 0.2]) {
      const bx = hx + dx * hrx;
      fillTri(grid, [[bx - 0.8, hy - hry * 0.6], [bx + 0.8, hy - hry * 0.6], [bx - 1.2, hy - hry - 1.8 * hs]], "spine");
    }
  }
  relight(grid, "body");
  relight(grid, "head");

  // the face
  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [], glints: [] };
  const iris = (genes.face && genes.face.eyes) || "#e0a828";
  const eyeSize = V.eye || "duo";
  const tipX = Math.round(hx + hrx + sl) - 1;
  if (V.facing === "front") {
    const c = Math.round(hx);
    const ey = Math.round(hy - hry * 0.55);
    face.eyes.push({ x: c - 4, y: ey, size: eyeSize, iris }, { x: c + 2, y: ey, size: eyeSize, iris });
    const my = Math.round(hy + hry * 0.45);
    for (let k = -2; k <= 2; k++) face.smile.push([c + k, my + (Math.abs(k) === 2 ? 0 : 1)]);
  } else {
    face.eyes.push({ x: Math.round(hx - hrx * 0.1), y: Math.round(hy - hry * 0.55), size: eyeSize, iris });
    const my = Math.round(hy + hry * 0.4);
    for (let x = Math.round(hx); x <= tipX; x++) face.smile.push([x, my]); // the jaw line
    face.noseDark.push([tipX - 1, Math.round(hy - hry * 0.05)]);
    if (V.tongue) face.tongue.push([tipX + 1, my], [tipX + 2, my - 1], [tipX + 2, my + 1]);
  }

  const geo = {
    cx, cy: by, rx, ry, legTop: by + ry * 0.2, tail: [tx, ty, L], head: [hx, hy, hrx, hry],
    faceBox: null, muzzle: null, tailEnd,
  };
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: hx, face, center: [cx, by], scale: s,
    softOutline: true, softNeck: true, geo, noShadow: true,
  };
}

// --- lizards seen from above (about 45 degrees) ------------------------------------
// The back is a long oval with a bright spine (where the crest runs); the
// near legs splay down toward us and the far legs up behind, each bending out
// at the elbow to splayed toes; the tail curves across the ground in an S (or
// curls into a spiral); the head shows its top, with both eyes on its sides.

function buildLizardTop(genes, stage, frame, V) {
  const shape = genes.shape || {};
  const grid = makeGrid();
  const s = 0.6 + stage.body * 0.4;
  const hs = 0.72 + stage.head * 0.28;
  const step = frame % 2;
  const wag = frame % 2;
  const rx = half(V.body.rx * s + (shape.length || 0) / 2);
  const ry = half(V.body.ry * s + (shape.height || 0) / 5); // half the body's width, as seen from above
  const legLen = V.leg.len * (0.8 + stage.leg * 0.2) * (1 + (shape.legs || 0) * 0.3);
  const lw = Math.max(1, V.leg.w * s * 0.5);
  const cx = 34;
  const under = V.tail.type === "question";
  const cy = GROUND - Math.max(ry + legLen + 1.5, under ? ry * 3.2 + 1.5 : 0); // the middle of the back
  const hipX = cx - rx * 0.55;
  const shoulderX = cx + rx * 0.5;

  // a leg: out from the body's edge, a bend at the elbow, then splayed toes
  const leg = (x, side, dir, lift, label) => {
    const y0 = cy + side * ry * 0.75;
    const elbow = [x + dir * 1.6 * s, y0 + side * legLen * 0.55 - lift * side * 0.4];
    const foot = [x + dir * 2.8 * s + dir * lift * 0.6, y0 + side * legLen];
    fillStroke(grid, [[x, y0], elbow, foot], lw, label);
    for (const t of [-1, 0, 1]) fillRect(grid, foot[0] + dir * 1 + t * 0.2, foot[1] + t, 1.4, 1, label); // toes fanning out
  };
  // far legs splay up, behind the body
  leg(hipX + 1, -1, -1, step ? 1 : 0, "farleg");
  leg(shoulderX + 1, -1, 1, step ? 0 : 1, "farleg");
  // a tail that curls under lies over the near feet, so draw those legs first
  // (else a stepping foot cuts the tail in two)
  if (under) {
    leg(hipX, 1, -1, step ? 0 : 1, "limb");
    leg(shoulderX, 1, 1, step ? 1 : 0, "limb");
  }

  // the tail: an S across the ground, or a spiral
  const L = V.tail.len * s * (1 + (shape.tail || 0) * 0.25);
  const tx = cx - rx + 1.5;
  const ty = cy;
  let pts;
  if (under) {
    // a big sideways question mark: back from the rump, round and down under
    // the body, then forward along the bottom, pointing at the head
    pts = [[tx, ty], [tx - L * 0.2, ty + ry * 0.25], [tx - L * 0.3, ty + ry * 1.3], [tx - L * 0.18, ty + ry * 2.3], [tx + L * 0.12, ty + ry * 2.7], [tx + L * 0.38, ty + ry * 2.75 - wag * 0.4]];
  } else if (V.tail.type === "curl") {
    const ccx = tx - L * 0.42;
    const ccy = ty + ry * 0.2;
    pts = [[tx, ty], [tx - L * 0.2, ty + ry * 0.6]];
    for (let k = 0; k <= 16; k++) {
      const a = Math.PI * 0.5 + (k / 16) * Math.PI * 1.8; // round to the left and up, curling inward
      const r = L * 0.26 * (1 - k * 0.045);
      pts.push([ccx + Math.cos(a) * r * 1.2, ccy + Math.sin(a) * r * 0.75]);
    }
  } else {
    const sway = wag * 0.6;
    pts = [[tx, ty], [tx - L * 0.28, ty + ry * 1.1], [tx - L * 0.58, ty + ry * 0.3 + sway], [tx - L * 0.82, ty - ry * 0.7], [tx - L, ty - ry * 0.2 - sway]];
  }
  const thick = V.tail.type === "chunky" ? 1.25 : V.taper ? 0.8 : 1;
  pts.slice(1).forEach((p, i) => {
    const r0 = Math.max(0.55, ry * 0.7 * thick * (1 - i / (pts.length - 1)));
    const r1 = Math.max(0.55, ry * 0.7 * thick * (1 - (i + 1) / (pts.length - 1)));
    for (let k = 0; k <= 5; k++) {
      const t = k / 5;
      const r = r0 + (r1 - r0) * t;
      fillEllipse(grid, pts[i][0] + (p[0] - pts[i][0]) * t, pts[i][1] + (p[1] - pts[i][1]) * t, r, r, "tail");
    }
  });

  // the back (an iguana's is thickest at the shoulders, narrowing to the tail)
  if (V.taper) {
    fillEllipse(grid, cx + rx * 0.25, cy, rx * 0.75, ry * 1.15, "body");
    fillEllipse(grid, cx - rx * 0.45, cy, rx * 0.6, ry * 0.68, "body");
  } else {
    fillEllipse(grid, cx, cy, rx, ry, "body");
  }
  // the neck and head, seen from above: a wedge pointing ahead
  const hrx = V.head.rx * hs;
  const hry = V.head.ry * hs;
  const hx = cx + rx + (V.neck || 1.2) * s + hrx * 0.45;
  const hy = cy - (V.headUp || 0) * s;
  fillStroke(grid, [[cx + rx - 1.5, cy], [hx - hrx * 0.5, hy]], Math.max(1.2, ry * (V.taper ? 0.95 : 0.65)), "neck");
  if (V.frill) fillEllipse(grid, hx - hrx * 0.6, hy, hrx * 0.7, hry * 2.2, "frill");
  fillEllipse(grid, hx, hy, hrx, hry, "head");
  const sl = (V.snout || 2) * hs;
  fillTri(grid, [[hx, hy - hry * 0.85], [hx, hy + hry * 0.85], [hx + hrx + sl, hy]], "head");
  if (V.casque) fillTri(grid, [[hx - hrx * 0.9, hy - hry * 0.5], [hx + hrx * 0.3, hy - hry * 0.7], [hx - hrx * 1.2, hy - hry * 1.9]], "head");
  if (V.dewlap) fillEllipse(grid, hx - hrx * 0.1, hy + hry + 1.2 * hs, Math.max(1.3, hrx * 0.5), Math.max(1.1, 1.5 * hs), "dewlap");

  // near legs splay down, in front
  if (!under) {
    leg(hipX, 1, -1, step ? 0 : 1, "limb");
    leg(shoulderX, 1, 1, step ? 1 : 0, "limb");
  }

  // a crest of spines along the spine
  const crest = (V.crest || 0) * s * (1 + (shape.crest || 0) * 0.35);
  if (crest) {
    const n = Math.max(5, Math.round(rx / 1.2));
    for (let k = 0; k < n; k++) {
      const t = k / (n - 1);
      const x = cx + rx * 0.9 - t * rx * 2.1;
      const h = Math.max(0.8, crest * (1 - Math.abs(t - 0.3) * 0.9));
      fillTri(grid, [[x - 0.8, cy - ry * 0.15], [x + 0.8, cy - ry * 0.15], [x - 0.4, cy - ry * 0.15 - h]], "spine");
    }
  }
  relight(grid, "body");
  relight(grid, "head");

  // the face: both eyes on the head's sides, nostrils at the tip, a mouth line
  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [], glints: [] };
  const iris = (genes.face && genes.face.eyes) || "#e0a828";
  const eyeSize = V.eye || "duo";
  const ex = Math.round(hx - hrx * 0.05);
  face.eyes.push({ x: ex, y: Math.round(hy - hry * 0.85), size: eyeSize, iris }, { x: ex, y: Math.round(hy + hry * 0.3), size: eyeSize, iris });
  const tipX = Math.round(hx + hrx + sl) - 1;
  face.noseDark.push([tipX - 1, Math.round(hy) - 1], [tipX - 1, Math.round(hy) + 1]);
  if (V.tongue) face.tongue.push([tipX + 1, Math.round(hy)], [tipX + 2, Math.round(hy) - 1], [tipX + 2, Math.round(hy) + 1]);

  const geo = {
    cx, cy, rx, ry, legTop: cy + ry * 0.75, tail: [tx, ty, L], head: [hx, hy, hrx, hry],
    faceBox: null, muzzle: null, fromAbove: true,
  };
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: hx, face, center: [cx, cy], scale: s,
    softOutline: true, softNeck: true, geo, noShadow: true,
  };
}

// --- snakes ------------------------------------------------------------------------
// A tapering tube laid along a smooth path, head end first. Each pose is a
// path: the classic "2" (a coil on the ground rising to the head), a cobra
// with its hood, a stack of coils, a slither seen from above, a ball, a
// side-on wave. Where the body crosses itself, the front part (nearer the
// head) gets an outline so the coils read.

// A smooth curve through points (Catmull-Rom), `n` samples per span.
function smoothPath(pts, n = 6) {
  const out = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    for (let k = 0; k < n; k++) {
      const t = k / n;
      const t2 = t * t;
      const t3 = t2 * t;
      const f = (a, b, c, d) => 0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
      out.push([f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1])]);
    }
  }
  out.push(pts[pts.length - 1]);
  return out;
}

function snakePath(V, cx, s, frame) {
  const B = GROUND - 1.5;
  const H = V.height * s;
  const wv = (frame % 2) * 0.6;
  switch (V.pose) {
    case "cobra": // the tail in an S on the ground, the front raised with the hood
      return [[cx + 4 * s, B - H], [cx + 4.5 * s, B - H * 0.75], [cx + 3.5 * s, B - H * 0.4], [cx + 1 * s, B - 1], [cx - 5 * s, B - 1.5], [cx - 9 * s, B - 3 - wv], [cx - 12 * s, B - 1]];
    case "stack": { // two coils stacked, the neck rising to the head
      const pts = [[cx + 3 * s, B - H], [cx + 4 * s, B - H * 0.78], [cx + 1 * s, B - H * 0.6]];
      // rounder rings, so the hole in each shows
      for (const [rr, yc] of [[6.2 * s, B - H * 0.55], [8 * s, B - 3.8 * s]]) {
        for (let k = 0; k <= 10; k++) {
          const a = Math.PI * 0.5 + (k / 10) * Math.PI * 2;
          pts.push([cx + Math.cos(a) * rr, yc + Math.sin(a) * rr * 0.55]);
        }
      }
      pts.push([cx - 9 * s, B - 1]);
      return pts;
    }
    case "slither": { // seen from above: an S across the ground
      const pts = [];
      for (let k = 0; k <= 8; k++) {
        const t = k / 8;
        pts.push([cx + 13 * s - t * 26 * s, B - 6 * s + Math.sin(t * Math.PI * 2.2 + (frame % 2) * 0.5) * 4 * s * (1 - t * 0.3)]);
      }
      return pts;
    }
    case "ball": { // curled into a ball, seen from above, the head resting on top
      const pts = [[cx + 3 * s, B - 7 * s], [cx - 1 * s, B - 7.5 * s]];
      for (let k = 0; k <= 14; k++) {
        const a = Math.PI + (k / 14) * Math.PI * 3.2;
        const r = (3 + k * 0.42) * s;
        pts.push([cx + Math.cos(a) * r, B - 6 * s + Math.sin(a) * r * 0.75]);
      }
      return pts;
    }
    case "wave": { // side-on, waving along the ground, the head held up
      // a smooth wave rolling along the body (the ends stay put), so the thin
      // tail never pinches off
      const roll = (frame % 2) * Math.PI * 0.5;
      const pts = [[cx + 12 * s, B - 7 * s], [cx + 10 * s, B - 4 * s]];
      for (let k = 0; k <= 9; k++) {
        const t = k / 9;
        const env = Math.sin(t * Math.PI); // no movement at either end
        pts.push([cx + 8 * s - t * 22 * s, B - 1.5 - (0.5 + 0.5 * Math.sin(t * Math.PI * 3 + roll)) * 2.2 * s * env]);
      }
      return pts;
    }
    case "slide": { // a diamondback slithering: low waves, head a little up, the tail tip raised for the rattle
      const roll = (frame % 2) * Math.PI * 0.5;
      const pts = [[cx + 13 * s, B - 4.5 * s], [cx + 10.5 * s, B - 2.5 * s]];
      for (let k = 0; k <= 9; k++) {
        const t = k / 9;
        const env = Math.sin(t * Math.PI);
        pts.push([cx + 8 * s - t * 22 * s, B - 1.5 - (0.5 + 0.5 * Math.sin(t * Math.PI * 3 + roll)) * 1.6 * s * env]);
      }
      pts.push([cx - 15.5 * s, B - 4 * s]);
      return pts;
    }
    case "strike": { // ready to strike: the front pulled back in an S, the rest low on the ground
      const roll = (frame % 2) * Math.PI * 0.5;
      const pts = [[cx + 11 * s, B - 11 * s], [cx + 8 * s, B - 12 * s], [cx + 5 * s, B - 9 * s], [cx + 7 * s, B - 5 * s], [cx + 4 * s, B - 2 * s]];
      for (let k = 1; k <= 7; k++) {
        const t = k / 7;
        pts.push([cx + 4 * s - t * 18 * s, B - 1.5 - (0.5 + 0.5 * Math.sin(t * Math.PI * 2.5 + roll)) * 1.4 * s * Math.sin(t * Math.PI)]);
      }
      pts.push([cx - 15.5 * s, B - 4 * s]);
      return pts;
    }
    case "long": // a "2" with an extra bend in the neck
      return [[cx + 2 * s, B - H], [cx + 5.5 * s, B - H * 0.88], [cx + 4 * s, B - H * 0.68], [cx - 1 * s, B - H * 0.56], [cx + 3 * s, B - H * 0.36], [cx + 2 * s, B - H * 0.16], [cx - 3 * s, B - 2], [cx + 4 * s, B - 1], [cx + 11 * s, B - 1.5], [cx + 13 * s, B - 3.5 - wv]];
    default: // the classic "2": the head up top, the neck curving down to a coil on the ground
      return [[cx + 2 * s, B - H], [cx + 5.5 * s, B - H * 0.82], [cx + 4.5 * s, B - H * 0.55], [cx - 1 * s, B - H * 0.3], [cx - 3 * s, B - 2.5], [cx + 3 * s, B - 1], [cx + 9 * s, B - 1.5], [cx + 11 * s, B - 3.5 - wv]];
  }
}

// A coiled snake, seen from a little above: two stacked rings (a wider one
// below, a smaller one on top) drawn solid, with an outline between the
// tiers; the neck rises from the middle of the top ring to the head, a light
// belly stripe up its front; the tail tip pokes out from the bottom ring.
function buildCoiledSnake(genes, stage, frame, V, { s, hs, w, len, cx, grid }) {
  const t = Math.max(2.2, w * 2.2); // how tall each ring is (the tube's thickness, seen from the side)
  const R1 = 8 * len * 0.85; // the bottom ring
  const R2 = R1 * 0.56; // the top ring: clearly smaller, sitting inside the bottom one
  const y1 = GROUND - t * 0.5 - 0.5;
  const y2 = y1 - t * 0.9;
  const ring = (cy, R, label) => {
    // a slab: the ring's flat top face and its side, as one solid shape
    fillEllipse(grid, cx, cy, R, R * 0.3, label);
    fillEllipse(grid, cx, cy + t * 0.5, R, R * 0.3, label);
    fillRect(grid, cx - R, cy, R * 2, t * 0.5, label);
  };
  // the tail tip pokes out at the back of the bottom ring
  fillStroke(grid, [[cx - R1 * 0.7, y1 + t * 0.3], [cx - R1 - 1.5 * s, y1 + t * 0.6 - (frame % 2) * 0.5]], Math.max(0.6, w * 0.4), "tail");
  ring(y1, R1, "coilbase"); // a strong line where the top tier sits on it
  ring(y2, R2, "body");
  // the neck: up from the top ring, an S on the way to the head
  const H = V.height * len;
  const neck = smoothPath([[cx - R2 * 0.1, y2], [cx + 1.5 * s, y2 - H * 0.35], [cx - 0.5 * s, y2 - H * 0.65], [cx + 1.5 * s, y2 - H]], 5);
  if (V.hood) fillEllipse(grid, neck[neck.length - 1][0], neck[neck.length - 1][1] + w * 2.4, w * 3.1, w * 2.3, "hood");
  neck.forEach(([x, y], i) => fillEllipse(grid, x, y, w * (0.85 - i / neck.length * 0.05), w * (0.85 - i / neck.length * 0.05), "neck"));
  // the head
  const [hx0, hy0] = neck[neck.length - 1];
  const front = V.facing === "front";
  const hrx = w * 1.35 * hs;
  const hry = w * 1.1 * hs;
  const hx = front ? hx0 : hx0 + hrx * 0.45;
  const hy = hy0;
  fillEllipse(grid, hx, hy, hrx, hry, "head");
  relight(grid, "coilbase");
  relight(grid, "body");
  relight(grid, "head");

  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [], glints: [] };
  const iris = (genes.face && genes.face.eyes) || "#e0a828";
  const c = Math.round(hx);
  if (front) {
    const ey = Math.round(hy - hry * 0.3);
    face.eyes.push({ x: c - 3, y: ey, size: "duo", iris }, { x: c + 2, y: ey, size: "duo", iris });
    face.smile.push([c - 2, ey + 3], [c - 1, ey + 4], [c, ey + 4], [c + 1, ey + 4], [c + 2, ey + 3]);
    face.tongue.push([c, ey + 5], [c, ey + 6], [c - 1, ey + 7], [c + 1, ey + 7]);
  } else {
    face.eyes.push({ x: c, y: Math.round(hy - hry * 0.45), size: "duo", iris });
    const tip = Math.round(hx + hrx) - 1;
    const my = Math.round(hy + hry * 0.4);
    face.smile.push([c, my], [c + 1, my], [tip, my]);
    face.tongue.push([tip + 1, my], [tip + 2, my], [tip + 3, my - 1], [tip + 3, my + 1]);
  }
  const geo = {
    cx, cy: y2, rx: R1, ry: w, legTop: GROUND, tail: [cx - R1, y1, R1], head: [hx, hy, hrx, hry],
    faceBox: null, muzzle: null, neckPath: neck, coil: true,
  };
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: hx, face, center: [cx, y2], scale: s,
    softOutline: true, softNeck: true, geo,
  };
}

function buildSnake(genes, stage, frame, V) {
  const shape = genes.shape || {};
  const grid = makeGrid();
  const s = 0.62 + stage.body * 0.38;
  const hs = 0.75 + stage.head * 0.25;
  const w = V.body.w * (0.7 + stage.body * 0.22) * (1 + (shape.thick || 0) * 0.25); // the tube's radius at its thickest
  const len = s * (1 + stage.body * 0.35); // grown snakes are much longer for their width
  const cx = 32;
  if (V.pose === "coil") return buildCoiledSnake(genes, stage, frame, V, { s, hs, w, len, cx, grid });
  const path = smoothPath(snakePath(V, cx, len, frame), 6);
  const n = path.length;
  const radius = (i) => {
    const t = i / (n - 1); // 0 head .. 1 tail tip
    // never thinner than ~1.6 pixels across, so the tip's pixels always touch side to side
    return Math.max(0.8, t < 0.18 ? w * (0.78 + t * 1.2) : w * Math.max(0.3, 1 - (t - 0.18) * 1.05));
  };
  // tail first, so the parts nearer the head lie on top; the far end is "tail"
  // (no outline of its own where the front part crosses it)
  const split = Math.round(n * (V.split || 0.5));
  // arc length along the path (head = 0), for markings that follow the body
  const arc = [0];
  for (let i = 1; i < n; i++) arc.push(arc[i - 1] + Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]));
  // for each pixel, the stamp whose center is nearest says how far down the
  // body it is (along) and which side of the tube it sits on (across: +1 belly
  // side, -1 back); fillEllipse replaces cells, so this is kept aside and laid
  // on once the tube is done
  const track = new Map();
  const mark = (x, y, r, i, along) => {
    const a = path[Math.min(n - 1, i + 1)];
    const b = path[Math.max(0, i - 1)];
    let px = -(a[1] - b[1]);
    let py = a[0] - b[0];
    const d = Math.hypot(px, py) || 1;
    px /= d;
    py /= d;
    if (py < 0 || (py === 0 && px < 0)) {
      px = -px;
      py = -py;
    }
    for (let yy = Math.floor(y - r - 1); yy <= Math.ceil(y + r + 1); yy++) {
      for (let xx = Math.floor(x - r - 1); xx <= Math.ceil(x + r + 1); xx++) {
        const dist = Math.hypot(xx + 0.5 - x, yy + 0.5 - y) / r;
        const key = yy * GRID_W + xx;
        const was = track.get(key);
        if (dist > 1.05 || (was && was.dist <= dist)) continue;
        track.set(key, { dist, along, across: ((xx + 0.5 - x) * px + (yy + 0.5 - y) * py) / r });
      }
    }
  };
  for (let i = n - 1; i >= 0; i--) {
    const r = radius(i);
    // the thin end is "thin": outline smoothing leaves it alone (it would
    // shave a thin diagonal line apart) and it blends into the body, no seam
    const label = i >= split ? "tail" : r < 1.3 ? "thin" : "body";
    fillEllipse(grid, path[i][0], path[i][1], r, r, label);
    mark(path[i][0], path[i][1], r, i, arc[i]);
    // fill in between points that a long snake stretches far apart
    if (i > 0) {
      const [x0, y0] = path[i];
      const [x1, y1] = path[i - 1];
      const steps = Math.ceil(Math.hypot(x1 - x0, y1 - y0) / Math.max(0.5, r * 0.6));
      for (let k = 1; k < steps; k++) {
        const x = x0 + ((x1 - x0) * k) / steps;
        const y = y0 + ((y1 - y0) * k) / steps;
        fillEllipse(grid, x, y, r, r, label);
        mark(x, y, r, i, arc[i] + ((arc[i - 1] - arc[i]) * k) / steps);
      }
    }
  }
  for (const [key, t] of track) {
    const c = grid[Math.floor(key / GRID_W)] && grid[Math.floor(key / GRID_W)][key % GRID_W];
    if (c) {
      c.along = t.along;
      c.across = Math.max(-1, Math.min(1, t.across));
    }
  }
  // the cobra's hood, behind the head
  const [hx0, hy0] = path[0];
  // a cobra's hood: flared wide beside the neck, just below the head
  if (V.hood) fillEllipse(grid, hx0, hy0 + w * 2.4, w * 3.1, w * 2.3, "hood");
  // the head: a little wider than the neck, pointing the way the snake faces
  const hrx = w * 1.35 * hs;
  const hry = w * 1.1 * hs;
  const front = V.facing === "front";
  const hx = front ? hx0 : hx0 + hrx * 0.45;
  const hy = hy0;
  if (V.hood) {
    // re-lay the neck over the hood so it reads in front
    for (let i = Math.round(n * 0.18); i >= 0; i--) fillEllipse(grid, path[i][0], path[i][1], radius(i), radius(i), "body");
  }
  fillEllipse(grid, hx, hy, hrx, hry, "head");
  // a viper's head: wide at the jaws, narrowing to the snout -- a triangle
  if (V.viper && !front) fillEllipse(grid, hx - hrx * 0.4, hy + hry * 0.1, hrx * 0.75, hry * 1.3, "head");
  if (V.rattle) {
    // a rattle: tan segments on the tail tip, carrying on the way the tail points
    const [ax, ay] = path[n - 2];
    const [bx, by] = path[n - 1];
    const d = Math.hypot(bx - ax, by - ay) || 1;
    const r = Math.max(0.9, w * 0.5);
    for (let k = 1; k <= 3; k++) fillEllipse(grid, bx + ((bx - ax) / d) * r * 1.4 * k, by + ((by - ay) / d) * r * 1.4 * k - (frame % 2) * 0.4 * k, r * (1 - k * 0.12), r * (1 - k * 0.12), "rattle");
  }
  relight(grid, "body");
  relight(grid, "head");

  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [], glints: [] };
  const iris = (genes.face && genes.face.eyes) || "#e0a828";
  const c = Math.round(hx);
  if (front) {
    const ey = Math.round(hy - hry * 0.3);
    face.eyes.push({ x: c - 3, y: ey, size: "duo", iris }, { x: c + 2, y: ey, size: "duo", iris });
    face.smile.push([c - 2, ey + 3], [c - 1, ey + 4], [c, ey + 4], [c + 1, ey + 4], [c + 2, ey + 3]);
    face.tongue.push([c, ey + 5], [c, ey + 6], [c - 1, ey + 7], [c + 1, ey + 7]);
  } else if (V.view === "top") {
    face.eyes.push({ x: c, y: Math.round(hy - hry * 0.85), size: "duo", iris }, { x: c, y: Math.round(hy + hry * 0.3), size: "duo", iris });
    const tip = Math.round(hx + hrx);
    face.tongue.push([tip, Math.round(hy)], [tip + 1, Math.round(hy)], [tip + 2, Math.round(hy) - 1], [tip + 2, Math.round(hy) + 1]);
  } else {
    face.eyes.push({ x: c, y: Math.round(hy - hry * 0.45), size: "duo", iris });
    const tip = Math.round(hx + hrx) - 1;
    const my = Math.round(hy + hry * 0.4);
    face.smile.push([c, my], [c + 1, my], [tip, my]);
    face.tongue.push([tip + 1, my], [tip + 2, my], [tip + 3, my - 1], [tip + 3, my + 1]);
  }

  const tailEnd = path[n - 1];
  const geo = {
    cx, cy: GROUND - 6, rx: 12 * s, ry: w, legTop: GROUND, tail: [path[Math.min(split, n - 1)][0], path[Math.min(split, n - 1)][1], 20 * s], head: [hx, hy, hrx, hry],
    faceBox: null, muzzle: null, path, tailEnd, fromAbove: V.view === "top",
  };
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: hx, face, center: [cx, GROUND - 6], scale: s,
    softOutline: true, softNeck: true, geo, noShadow: V.view === "top",
  };
}

// Eye shapes, rows top to bottom: K lash/outline, W glint, I iris, P pupil.
// --- dragons ------------------------------------------------------------------------
// A storybook dragon: a chunky body with a pale plated belly, bat wings
// (bones fanning from the wrist, the membrane scalloped between the finger
// tips), swept-back horns, a row of spines down the back, and a long tail
// ending in a spade. Side-on it walks, breathes fire, stands like a wyvern,
// or flies. Every breed starts as a spotted egg, then
// hatches (peeking out of the broken shell), then grows a lot: small, normal,
// and finally bigger than any other pet.

// Dragon sizes by growth stage (baby is the egg, small the hatchling).
const DRAGON_GROWTH = {
  mid: { body: 0.62, head: 0.82, leg: 0.65 },
  big: { body: 0.86, head: 0.94, leg: 0.88 },
  grown: { body: 1.4, head: 1.22, leg: 1.32 },
  hatch: { body: 1, head: 1, leg: 1 },
};
// The hatchling peeking out of its shell, whatever its breed.
const DRAGON_HATCHLING = {
  facing: "front", pose: "sit", egg: true, horns: 2.8, body: { rx: 7, ry: 4 }, head: { rx: 5.6, ry: 4.8 }, tail: { len: 8 }, wings: { type: "half", span: 6.5 }, eye: "duo",
};

// The egg: tall and spotted in the dragon's colors, rocking now and then.
function buildDragonEgg(genes, frame) {
  const grid = makeGrid();
  const cx = 46;
  const rx = 6;
  const ry = 7.6;
  const cy = GROUND - ry;
  const rock = frame % 4 === 1 ? 1 : frame % 4 === 3 ? -1 : 0;
  for (let y = Math.floor(cy - ry); y < GROUND; y++) {
    // narrower at the top; the top half leans as it rocks
    const ny = (y + 0.5 - cy) / ry;
    const w = rx * Math.sqrt(Math.max(0, 1 - ny * ny)) * (ny < 0 ? 1 + ny * 0.18 : 1);
    const dx = ny < -0.2 ? rock : 0;
    for (let x = Math.floor(cx - w - 1); x <= Math.ceil(cx + w + 1); x++) {
      const nx = (x + 0.5 - cx - dx) / Math.max(1, w);
      if (Math.abs(nx) <= 1) put(grid, x, y, { l: "egg", nx, ny });
    }
  }
  // spots: big ones in the first color, small ones in the second
  const spots = [[-2.5, -4.5, 1.6], [2.2, -1.8, 1.9], [-3, 2.2, 1.4], [1.5, 4.2, 1.2], [3.6, -5.5, 0.9], [-0.5, 0.2, 0.8]];
  for (const [sx, sy, r] of spots) {
    for (let y = Math.floor(cy + sy - r - 1); y <= Math.ceil(cy + sy + r + 1); y++) {
      for (let x = Math.floor(cx + sx - r - 1); x <= Math.ceil(cx + sx + r + 1); x++) {
        const c = grid[y] && grid[y][x];
        const dx = y + 0.5 - cy < -0.2 * ry ? rock : 0;
        if (c && Math.hypot(x + 0.5 - cx - sx - dx, y + 0.5 - cy - sy) <= r) c.l = r < 1.3 ? "eggspot2" : "eggspot";
      }
    }
  }
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: cx, face: { eyes: [], pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [] },
    center: [cx, cy], scale: 1, softOutline: true, softNeck: true,
    geo: { cx, cy, rx, ry, legTop: GROUND, tail: [cx, cy, 0], head: [cx, cy - ry, 1, 1], faceBox: null, muzzle: null },
  };
}

const DRAGON_WINGS = {
  // the wrist, then the finger tips from the front of the wing to the back,
  // as offsets from the shoulder in spans (x back, y up)
  up: { wrist: [0.15, 0.95], tips: [[0.55, 0.9], [0.9, 0.55], [0.85, 0.12]] },
  half: { wrist: [0.35, 0.7], tips: [[0.8, 0.6], [1.0, 0.3], [0.85, 0.02]] },
  spread: { wrist: [0.3, 1.0], tips: [[0.85, 1.05], [1.25, 0.65], [1.15, 0.15]] },
  down: { wrist: [0.55, 0.25], tips: [[1.1, 0.05], [1.05, -0.35], [0.7, -0.5]] },
  folded: { wrist: [0.4, 0.4], tips: [[0.95, 0.25], [1.0, 0.0], [0.75, -0.12]] },
};

function buildDragon(genes, stage, frame, V) {
  if (stage.id === "baby") return buildDragonEgg(genes, frame);
  if (stage.id === "small") return buildDragon(genes, { id: "hatch" }, frame, { ...V, ...DRAGON_HATCHLING });
  const G = DRAGON_GROWTH[stage.id];
  const shape = genes.shape || {};
  const grid = makeGrid();
  const s = G.body;
  const hs = G.head;
  const ls = G.leg;
  const step = frame % 2;
  const flap = frame % 2;
  const front = V.facing === "front";
  const rx = half(V.body.rx * s + (shape.length || 0) / 2);
  const ry = half(V.body.ry * s);
  const legH = Math.max(2, V.leg.len * ls * (1 + (shape.legs || 0) * 0.3));
  const lw = Math.max(1, V.leg.w * s * 0.5);
  const cx = V.pose === "wyvern" ? 41 : 46;
  const hrx = V.head.rx * hs;
  const hry = V.head.ry * hs;
  const hornL = (V.horns || 0) * hs * (1 + (shape.horns || 0) * 0.3);
  const span = V.wings ? V.wings.span * s * (1 + (shape.wings || 0) * 0.25) : 0;
  const lift = V.pose === "fly" ? Math.min(16, 16 * s) + flap : 0;
  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [], glints: [] };
  const iris = (genes.face && genes.face.eyes) || "#e0a828";
  const eye = V.eye || "duo";

  // a tapering tube through points, radius by point
  const tube = (pts, widths, label) => {
    pts.slice(1).forEach((p, i) => {
      const steps = Math.max(2, Math.ceil(Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]) * 1.5));
      for (let k = 0; k <= steps; k++) {
        const t = k / steps;
        const r = Math.max(0.55, widths[i] + (widths[i + 1] - widths[i]) * t);
        fillEllipse(grid, pts[i][0] + (p[0] - pts[i][0]) * t, pts[i][1] + (p[1] - pts[i][1]) * t, r, r, label);
      }
    });
  };
  // the spade on the tail tip, pointing on the way the tail goes
  const spade = (a, b, size) => {
    const d = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const ux = (b[0] - a[0]) / d;
    const uy = (b[1] - a[1]) / d;
    const px = -uy;
    const py = ux;
    const r = Math.max(1.4, size);
    const base = [b[0] - ux * r * 0.3, b[1] - uy * r * 0.3];
    fillTri(grid, [[base[0] + px * r, base[1] + py * r], [base[0] - px * r, base[1] - py * r], [b[0] + ux * r * 1.6, b[1] + uy * r * 1.6]], "spade");
    fillTri(grid, [[base[0] + px * r, base[1] + py * r], [base[0] - px * r, base[1] - py * r], [b[0] - ux * r * 0.6, b[1] - uy * r * 0.6]], "spade");
  };
  // a bat wing from the shoulder; dir -1 sweeps back to the left (side views)
  const wing = (sx, sy, dir, mode, size, far) => {
    const W = DRAGON_WINGS[mode];
    const up = 0;
    const at = ([u, v], k = 1) => [sx + dir * u * size, sy - (v + up * k) * size];
    const wr = at(W.wrist, 0.5);
    const tips = W.tips.map((t, i) => at(t, 1 - i * 0.3));
    const mem = far ? "farwing" : "wing";
    const bone = far ? "farbone" : "wingbone";
    const shoulder = [sx, sy];
    const back = [sx + dir * size * 0.3, sy + size * 0.05];
    // the outline: shoulder, wrist, then the finger tips with the edge
    // between each two bowing in toward the wrist, then back to the body;
    // filled as a fan from the wrist so the scallops stay open
    const edge = [...tips, back];
    for (let i = 0; i < edge.length - 1; i++) {
      const m = [(edge[i][0] + edge[i + 1][0]) / 2, (edge[i][1] + edge[i + 1][1]) / 2];
      const bow = [m[0] + (wr[0] - m[0]) * 0.3, m[1] + (wr[1] - m[1]) * 0.3];
      fillTri(grid, [wr, edge[i], bow], mem);
      fillTri(grid, [wr, bow, edge[i + 1]], mem);
    }
    fillTri(grid, [wr, back, shoulder], mem);
    fillStroke(grid, [shoulder, wr], Math.max(0.6, 0.75 * s), bone);
    for (const t of tips) line(grid, wr, t, bone);
    put(grid, Math.round(wr[0] - dir * 0.5), Math.round(wr[1] - 1), { l: "claw", nx: 0, ny: -1 }); // the thumb claw
  };
  // a row of spines along the top edge of these labels, from x0 to x1
  const spines = (x0, x1, h, labels) => {
    if (!V.spines) return;
    const n = Math.max(3, Math.round(Math.abs(x1 - x0) / 2.6));
    for (let k = 0; k < n; k++) {
      const x = Math.round(x0 + ((x1 - x0) * k) / (n - 1));
      let top = -1;
      for (let y = 0; y < GRID_H; y++) if (grid[y][x] && labels.includes(grid[y][x].l)) { top = y; break; }
      if (top < 0) continue;
      const hh = Math.max(1, h * (1 - Math.abs(k / (n - 1) - 0.35)));
      fillTri(grid, [[x - 0.9, top + 1], [x + 1.1, top + 1], [x - 0.6, top + 0.5 - hh]], "dspine");
    }
  };
  const horns = (bx, by, dir, far) => {
    if (!hornL) return;
    const pts = [[bx, by], [bx + dir * hornL * 0.3, by - hornL * 0.7], [bx + dir * hornL * 0.9, by - hornL * 0.95]];
    const label = far ? "farhorn" : "horn";
    fillStroke(grid, [pts[0], pts[1]], Math.max(0.55, 0.7 * hs), label);
    fillStroke(grid, [pts[1], pts[2]], 0.45, label);
  };
  // a clawed foot: three toes on the ground, a light claw at the front
  const foot = (x, dir, label, liftY = 0) => {
    fillRect(grid, x - (dir > 0 ? 0 : 2), GROUND - 1 - liftY, 3, 1, label);
    put(grid, Math.round(x + dir * 2 - (dir > 0 ? 0 : 0)), GROUND - 1 - liftY, { l: label === "farleg" ? "farclaw" : "claw", nx: 0, ny: 0 });
  };

  let hx;
  let hy;
  let tailEnd = null;
  if (front) {
    // sitting up, facing us: an egg of a body, the belly plates down the
    // front, haunches and feet at the bottom, little arms, the wings behind
    const by = GROUND - ry * 1.55;
    const brx = rx * 0.62;
    const bry = ry * 1.55;
    if (V.egg) {
      // the back half of the broken shell, behind the hatchling
      fillEllipse(grid, cx, GROUND - 6 * s, 8.5 * s, 7.5 * s, "eggback");
    }
    if (span) for (const dir of [-1, 1]) wing(cx + dir * brx * 0.45, by - bry * 0.45, dir, V.wings.type, span, false);
    // the tail: out to the side along the ground, curling forward to a spade
    const L = V.tail.len * s;
    const tp = [[cx - brx * 0.5, GROUND - 2.5], [cx - brx - L * 0.35, GROUND - 1.8], [cx - brx - L * 0.6, GROUND - 3.5 - step * 0.5], [cx - brx - L * 0.55, GROUND - 6 - step * 0.5]];
    if (!V.egg) {
      tube(tp, [ry * 0.55, ry * 0.4, ry * 0.25, 0.6], "tail");
      spade(tp[2], tp[3], 1.5 * s);
      tailEnd = tp[3];
    }
    fillEllipse(grid, cx, by, brx, bry, "body");
    for (const dir of [-1, 1]) fillEllipse(grid, cx + dir * brx * 0.7, GROUND - ry * 0.75, Math.max(2, brx * 0.42), ry * 0.8, "body"); // haunches
    // the belly: a light oval down the front
    fillEllipse(grid, cx, by + bry * 0.12, brx * 0.55, bry * 0.78, "belly");
    if (!V.egg) for (const dir of [-1, 1]) fillEllipse(grid, cx + dir * brx * 0.75, GROUND - 1, Math.max(1.6, 2 * s), 1.2, "leg"); // feet
    if (!V.egg) for (const dir of [-1, 1]) foot(cx + dir * (brx * 0.75 + 1), dir, "leg");
    // arms, held in front of the chest
    for (const dir of [-1, 1]) {
      const px = cx + dir * brx * 0.5;
      const py = by - bry * 0.05;
      fillEllipse(grid, px, py, Math.max(1.2, 1.5 * s), Math.max(1.2, 1.4 * s), "leg");
      put(grid, Math.round(px - 0.5), Math.round(py + 1.4 * s), { l: "claw", nx: 0, ny: 0 });
    }
    if (V.egg) {
      // the front half of the shell, with a zigzag broken rim
      const er = 8.5 * s;
      const top = GROUND - 6 * s;
      for (let x = Math.floor(cx - er); x <= Math.ceil(cx + er); x++) {
        const zig = (Math.abs(x) % 3) - 1;
        for (let y = Math.round(top + zig); y < GROUND; y++) {
          const nx = (x + 0.5 - cx) / er;
          const ny = (y + 0.5 - (GROUND - 6 * s)) / (7.5 * s);
          const spot = [[-4, 3, 1.6], [3.5, 2, 1.8], [0.5, 5, 1.2]].find(([sx, sy, r]) => Math.hypot(x + 0.5 - cx - sx, y + 0.5 - top - sy) <= r);
          if (nx * nx + ny * ny <= 1) put(grid, x, y, { l: !spot ? "egg" : spot[2] < 1.3 ? "eggspot2" : "eggspot", nx, ny });
        }
      }
    }
    hx = cx;
    hy = by - bry * 0.95 - hry * 0.45;
    // horns sweep up and out behind the head
    for (const dir of [-1, 1]) horns(hx + dir * hrx * 0.45, hy - hry * 0.65, dir * 0.7, false);
    // little fin ears at the sides
    for (const dir of [-1, 1]) fillTri(grid, [[hx + dir * hrx * 0.8, hy - hry * 0.45], [hx + dir * hrx * 0.95, hy + hry * 0.05], [hx + dir * (hrx + 2.4 * hs), hy - hry * 0.55]], "fin");
    fillEllipse(grid, hx, hy, hrx, hry, "head");
    // a wide muzzle in the lower face
    const my = hy + hry * 0.42;
    fillEllipse(grid, hx, my, hrx * 0.62, Math.max(1.8, hry * 0.42), "snout");
    const c = Math.round(hx);
    const ey = Math.round(hy - hry * 0.3) - 1;
    const g = Math.max(1, Math.round(hrx * 0.28));
    face.eyes.push({ x: c - g - 2, y: ey, size: eye, iris }, { x: c + g, y: ey, size: eye, iris });
    const ny = Math.round(my - 0.5);
    face.noseDark.push([c - 2, ny], [c + 1, ny]);
    face.smile.push([c - 2, ny + 2], [c - 1, ny + 2], [c, ny + 2], [c + 1, ny + 2]);
    face.glints.push([c + 1, ny + 3, "#fbf6ec"]); // a little fang
  } else {
    // side view, facing right
    const stand = V.pose === "wyvern";
    const by = GROUND - legH - ry * 0.6 - lift;
    const hipX = cx - rx * 0.5;
    const shoulderX = cx + rx * 0.5;
    const walkLeg = (x, lifted, label, hind) => {
      if (V.pose === "fly") {
        // tucked up under the body
        fillStroke(grid, [[x, by + ry * 0.4], [x - 1.5 * s, by + ry + 1.5 * s]], lw, label);
        return;
      }
      if (hind) fillEllipse(grid, x, by + ry * 0.15, Math.max(2, ry * 0.7), Math.max(2, ry * 0.75), label); // the thigh
      const knee = [x + (hind ? 1.2 : 0.4) * s, GROUND - legH * 0.5 - lifted];
      fillStroke(grid, [[x, by + ry * 0.5], knee, [x - (hind ? 0.4 : 0), GROUND - 1.5 - lifted]], lw, label);
      foot(Math.round(x - (hind ? 0.4 : 0)), 1, label, lifted);
    };
    // far side first
    if (!stand) {
      walkLeg(hipX + 2, step ? 0 : 1, "farleg", true);
      walkLeg(shoulderX + 2, step ? 1 : 0, "farleg", false);
    }
    if (stand) walkLeg(hipX + 2.5, step ? 0 : 1, "farleg", true);
    // the neck: up and forward from the chest
    const nl = (V.neck || 4) * s;
    hx = cx + rx * 0.95 + nl * 0.55 + hrx * 0.3;
    hy = by - ry * (stand ? 1.2 : 0.55) - nl - (V.headUp || 0) * s;
    if (span) wing(cx + rx * 0.25 + 1.5, by - ry * 0.7 - 0.5, -1, V.pose === "fly" ? (flap ? "half" : "up") : V.wings.type, span * 0.9, true);
    // the tail: sweeping back, down to the ground and up at the spade
    const L = V.tail.len * s * (1 + (shape.tail || 0) * 0.25);
    const tx = cx - rx + 1;
    const ty = by + ry * 0.05;
    let tp;
    if (V.pose === "fly") tp = [[tx, ty], [tx - L * 0.35, ty + ry * 0.5], [tx - L * 0.7, ty + ry * 0.2 + step], [tx - L, ty - ry * 0.5 + step]];
    else tp = [[tx, ty], [tx - L * 0.35, ty + ry * 0.7], [tx - L * 0.7, GROUND - 2], [tx - L * 0.95, GROUND - 4.5 - step]];
    tube(tp, [ry * 0.7, ry * 0.45, ry * 0.28, 0.55], "tail");
    spade(tp[2], tp[3], 1.6 * s);
    tailEnd = tp[3];
    // the body
    if (stand) {
      // upright: chest high and forward, hips low
      fillEllipse(grid, cx + rx * 0.3, by - ry * 0.7, rx * 0.55, ry * 1.15, "body");
      fillEllipse(grid, cx - rx * 0.3, by + ry * 0.1, rx * 0.6, ry * 0.95, "body");
    } else {
      fillEllipse(grid, cx, by, rx, ry, "body");
      fillEllipse(grid, cx + rx * 0.4, by - ry * 0.1, rx * 0.55, ry * 1.08, "body"); // a deep chest
    }
    // the belly plates along the underside
    relabel(grid, ["body"], "belly", (x, y) => y > by + ry * (stand ? 0.05 : 0.35) && x > cx - rx * 0.75);
    const neckBase = [cx + rx * 0.75, by - ry * 0.25];
    tube([neckBase, [hx - hrx * 0.9, hy + nl * 0.45], [hx - hrx * 0.4, hy + hry * 0.2]], [ry * 0.72, ry * 0.5, Math.max(1.2, hry * 0.7)], "neck");
    // the head: a rounded skull and a long muzzle, horns swept back
    horns(hx - hrx * 0.1, hy - hry * 0.7, -1, true);
    fillEllipse(grid, hx, hy, hrx, hry, "head");
    const sl = (V.snout || 3) * hs;
    fillEllipse(grid, hx + hrx * 0.55 + sl * 0.5, hy + hry * 0.3, sl * 0.75 + 0.6, Math.max(1.5, hry * 0.6), "snout");
    horns(hx - hrx * 0.45, hy - hry * 0.6, -1, false);
    // spines down the neck, back and tail
    spines(Math.round(tx - L * 0.2), Math.round(cx + rx * 0.9), 1.8 * s * (V.spines || 1), ["body", "tail", "neck"]);
    // near legs
    walkLeg(hipX, step ? 1 : 0, "leg", true);
    if (!stand) walkLeg(shoulderX, step ? 0 : 1, "leg", false);
    if (span) wing(cx + rx * 0.3, by - ry * 0.9, -1, V.pose === "fly" && flap ? "down" : V.wings.type, span, false);
    if (stand) fillStroke(grid, [[cx + rx * 0.55, by - ry * 0.1], [cx + rx * 0.85, by + ry * 0.45]], Math.max(0.7, lw * 0.8), "limb"); // a little arm
    // the face
    const ex = Math.round(hx + hrx * 0.05);
    const ey = Math.round(hy - hry * 0.45);
    face.eyes.push({ x: ex, y: ey, size: eye, iris });
    const tipX = Math.round(hx + hrx * 0.55 + sl * 1.25 + 0.6) - 1;
    const my = Math.round(hy + hry * 0.55);
    face.noseDark.push([tipX - 1, Math.round(hy + hry * 0.05)]);
    for (let x = ex + 2; x <= tipX - 1; x++) face.smile.push([x, my]);
    face.glints.push([tipX - 2, my + 1, "#fbf6ec"]); // a little fang
    if (V.fire) {
      // a puff of fire out ahead of the snout, flickering
      const fy = hy + hry * 0.35;
      const f = frame % 2;
      // a cone of fire widening as it goes, licks curling up off the top,
      // a yellow heart inside
      [[1.5, 1.1], [3.5, 2], [6, 2.9 + f * 0.3], [8.3 + f * 0.5, 2.3]].forEach(([d, r]) => fillEllipse(grid, tipX + 1 + d * hs, fy - d * 0.15, r * hs, r * hs, "flame"));
      for (const [d, h] of [[4.5, 3.2 - f], [7, 3.8 + f], [9.6, 2.6]]) fillTri(grid, [[tipX + (d - 1.2) * hs, fy - d * 0.15 - 1], [tipX + (d + 1.2) * hs, fy - d * 0.15 - 1], [tipX + (d - 0.6 + f * 0.6) * hs, fy - d * 0.15 - (2 + h) * hs]], "flame");
      [[2, 0.7], [4, 1.2], [6.2, 1.6]].forEach(([d, r]) => fillEllipse(grid, tipX + 1 + d * hs, fy - d * 0.15 + 0.3, r * hs, r * hs, "flamecore"));
    }
  }

  relight(grid, "body");
  relight(grid, "head");
  relight(grid, "snout");
  relight(grid, "belly");
  const geo = {
    cx, cy: GROUND - 8, rx, ry, legTop: GROUND - legH, tail: [cx - rx, GROUND - 8, V.tail.len * s], head: [hx, hy, hrx, hry],
    faceBox: null, muzzle: null, tailEnd, front,
  };
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: hx, face, center: [cx, GROUND - 8 - lift], scale: s,
    softOutline: true, softNeck: true, geo,
  };
}

// --- unicorns ------------------------------------------------------------------------
// A horse built for a storybook: a deep chest and round rump on long legs with
// dark hooves, an arched neck under a flowing mane, a long face drooping to a
// soft muzzle, small ears, a forelock, and a spiral horn on the forehead. The
// mane and tail wear the second color. Poses: standing, prancing (a front leg
// raised), rearing, galloping, lying down; an alicorn adds feathered wings.

// Unicorn sizes by growth stage: a foal is small with long legs, a big head
// and a nub of a horn; a grown unicorn is bigger than other pets.
const UNICORN_GROWTH = {
  baby: { body: 0.45, head: 0.78, leg: 0.72, horn: 0.25 },
  small: { body: 0.6, head: 0.84, leg: 0.8, horn: 0.45 },
  mid: { body: 0.76, head: 0.9, leg: 0.87, horn: 0.65 },
  big: { body: 0.94, head: 0.98, leg: 0.96, horn: 0.85 },
  grown: { body: 1.18, head: 1.1, leg: 1.15, horn: 1.1 },
};

function buildUnicorn(genes, stage, frame, V) {
  const shape = genes.shape || {};
  const grid = makeGrid();
  const G = UNICORN_GROWTH[stage.id];
  const s = G.body;
  const hs = G.head;
  const ls = G.leg;
  const step = frame % 2;
  const rx = half(V.body.rx * s + (shape.length || 0) / 2);
  const ry = half(V.body.ry * s);
  const legH = Math.max(3, V.leg.len * ls * (1 + (shape.legs || 0) * 0.25));
  const lw = Math.max(0.8, V.leg.w * s * 0.5);
  const cx = 46;
  const hrx = V.head.rx * hs;
  const hry = V.head.ry * hs;
  const hornL = Math.max(1.5, (V.horn || 6) * G.horn * (1 + (shape.horns || 0) * 0.3));
  const pose = V.pose || "stand";
  const lying = pose === "lie";
  const rear = pose === "rear";
  const gallop = pose === "gallop";
  const lift = gallop ? 2 * s : 0;
  const by = lying ? GROUND - ry * 1.05 : rear ? GROUND - legH * 0.85 - ry * 0.4 : GROUND - legH - ry * 0.55 - lift;
  const chest = [cx + rx * 0.3, by - rx * 0.85]; // rearing: where the chest rises to
  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [], glints: [] };
  const iris = (genes.face && genes.face.eyes) || "#5a3a8a";
  const eye = V.eye || "duo";

  const tube = (pts, widths, label) => {
    pts.slice(1).forEach((p, i) => {
      const steps = Math.max(2, Math.ceil(Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]) * 1.5));
      for (let k = 0; k <= steps; k++) {
        const t = k / steps;
        const r = Math.max(0.55, widths[i] + (widths[i + 1] - widths[i]) * t);
        fillEllipse(grid, pts[i][0] + (p[0] - pts[i][0]) * t, pts[i][1] + (p[1] - pts[i][1]) * t, r, r, label);
      }
    });
  };
  // a leg through its joints, the bottom rows a hoof
  const leg = (pts, label) => {
    tube(pts, pts.map((_, i) => (i === 0 ? lw * 1.25 : lw)), label);
    const [fx, fy] = pts[pts.length - 1];
    const hoof = label === "farleg" ? "farhoof" : "hoof";
    fillRect(grid, fx - lw, fy - 0.5, lw * 2 + 0.6, 1.6, hoof);
  };
  // standing legs: straight down from the body, a little bend at the knee
  const standLeg = (x, lifted, label, hind) => {
    const top = by + ry * 0.4;
    if (hind) fillEllipse(grid, x + 0.5, by + ry * 0.05, Math.max(2, rx * 0.32), ry * 0.85, label === "farleg" ? "farleg" : "body");
    const knee = [x + (hind ? -0.6 : 0.3) * s, top + (GROUND - top) * 0.5 - lifted];
    leg([[x, top], knee, [x + (hind ? 0.3 : 0) - lifted * 0.4, GROUND - 1 - lifted]], label);
  };
  // a front leg raised: the knee up and forward, the hoof tucked back under
  const raised = (x, label, up = 1) => {
    const top = by + ry * 0.35;
    // the forearm reaches forward past the chest, the cannon hangs down
    const knee = [x + rx * 0.5 + 2 * s * up, top + 0.5];
    leg([[x, top], knee, [knee[0] + 0.5 * s, knee[1] + legH * 0.45]], label);
  };

  let hx;
  let hy;
  // the wings sit behind on the far side, in front on the near side
  {
    // side-on, facing right
    const backX = cx - rx * 0.55;
    const frontX = cx + rx * 0.5;
    // far legs
    if (lying) {
      fillEllipse(grid, frontX + 1.5, GROUND - 1.2, 2.6 * s, 1.2, "farleg");
    } else if (rear) {
      leg([[backX + 2, by + ry * 0.4], [backX + 3.5 * s, by + ry + legH * 0.25], [backX + 1, GROUND - 1]], "farleg");
      const t = [chest[0] + 1.5, chest[1] + ry * 0.6];
      leg([t, [t[0] + 3 * s, t[1] + 1 * s + step], [t[0] + 2.4 * s, t[1] + legH * 0.5 + step]], "farleg");
    } else if (gallop) {
      leg([[backX + 2, by + ry * 0.4], [backX - 1 * s, by + ry + legH * 0.4], [backX - 3.5 * s - step, GROUND - 2 - lift]], "farleg");
      leg([[frontX + 2, by + ry * 0.4], [frontX + 4 * s, by + ry + legH * 0.3], [frontX + 6 * s + step, by + ry + legH * 0.55]], "farleg");
    } else {
      standLeg(backX + 2, step ? 0 : 1, "farleg", false);
      standLeg(frontX + 2, step ? 1 : 0, "farleg", false);
    }
    // where the head goes: up on an arched neck
    const nl = (V.neck || 6) * s;
    hx = cx + rx * 0.85 + nl * 0.45;
    hy = by - ry * 0.7 - nl;
    if (rear) {
      hx = chest[0] + nl * 0.45 + hrx * 0.4;
      hy = chest[1] - ry * 0.6 - nl;
    }
    if (gallop) {
      hx += nl * 0.25;
      hy += nl * 0.25;
    }
    const shoulder = rear ? [chest[0] - rx * 0.15, chest[1] - ry * 0.5] : [cx + rx * 0.2, by - ry * 0.85];
    if (V.wings) featherWing(grid, frame, s, shoulder[0] + 2, shoulder[1] + 0.5, V.wings * s * 0.9, -1, "farfeather", "farfeather");
    // the tail: a fall of hair from the top of the rump, rippling
    const tx = cx - rx * 1.0;
    const ty = by - ry * 0.55 + (rear ? ry * 0.6 : 0);
    const w = step * 0.6;
    const flow = gallop ? [[tx, ty], [tx - 4 * s, ty - 0.5], [tx - 8 * s, ty + 1 + w], [tx - 12 * s, ty + 0.5]] : lying ? [[tx, ty], [tx - 3 * s, ty + 1.5], [tx - 4.5 * s, GROUND - 2], [tx - 1 * s, GROUND - 1]] : [[tx, ty], [tx - 3 * s, ty + 1], [tx - 4 * s + w, ty + legH * 0.5], [tx - 3 * s, GROUND - 2 - legH * 0.15]];
    tube(flow, [1.4 * s, 2.1 * s, 2 * s, 1.2 * s], "utail");
    // the body: barrel, chest and rump (rearing: tipped up at the front)
    if (rear) {
      const rump = [cx - rx * 0.5, by];
      for (let k = 0; k <= 6; k++) {
        const t = k / 6;
        fillEllipse(grid, rump[0] + (chest[0] - rump[0]) * t, rump[1] + (chest[1] - rump[1]) * t, ry * 1.02, ry * 1.02, "body");
      }
      fillEllipse(grid, rump[0], rump[1], rx * 0.45, ry * 1.05, "body");
    } else {
      fillEllipse(grid, cx, by + ry * 0.05, rx * 0.92, ry * 0.88, "body");
      fillEllipse(grid, cx - rx * 0.55, by - ry * 0.1, rx * 0.5, ry * 1.02, "body");
      fillEllipse(grid, cx + rx * 0.5, by, rx * 0.5, ry * 1.05, "body");
    }
    // the neck: wide at the chest, arching up to the head
    const base = rear ? [chest[0] + ry * 0.3, chest[1] - ry * 0.3] : [cx + rx * 0.62, by - ry * 0.45];
    const mid = [base[0] + (hx - base[0]) * 0.35, hy + (base[1] - hy) * 0.35 - 0.5];
    tube([base, mid, [hx - hrx * 0.4, hy + hry * 0.1]], [ry * 0.85, ry * 0.6, hry * 0.7], "neck");
    // near legs
    if (lying) {
      fillEllipse(grid, backX + 1, GROUND - 1.2, 3 * s, 1.2, "leg"); // folded under
      leg([[frontX + 1, by + ry * 0.2], [frontX + 4 * s, GROUND - 1.5], [frontX + 7 * s, GROUND - 1]], "leg");
    } else if (rear) {
      leg([[backX, by + ry * 0.4], [backX + 3 * s, by + ry + legH * 0.25], [backX - 0.5, GROUND - 1]], "leg");
      const t = [chest[0], chest[1] + ry * 0.7];
      leg([t, [t[0] + 3.4 * s, t[1] - 0.5 * s - step], [t[0] + 3 * s, t[1] + legH * 0.45 - step]], "leg");
    } else if (gallop) {
      leg([[backX, by + ry * 0.4], [backX - 2 * s, by + ry + legH * 0.4], [backX - 5 * s + step, GROUND - 1.5 - lift]], "leg");
      leg([[frontX, by + ry * 0.4], [frontX + 3 * s, by + ry + legH * 0.4], [frontX + 7 * s - step, by + ry + legH * 0.4]], "leg");
    } else if (pose === "prance") {
      standLeg(backX, 0, "leg", true);
      raised(frontX, "leg", 1);
    } else {
      standLeg(backX, step ? 1 : 0, "leg", true);
      standLeg(frontX, step ? 0 : 1, "leg", false);
    }
    // the head: a skull, a long face sloping down, a soft muzzle
    fillTri(grid, [[hx - hrx * 0.7, hy - hry * 0.9], [hx - hrx * 0.2, hy - hry * 0.95], [hx - hrx * 0.55, hy - hry * 0.95 - 3 * hs]], "farear");
    fillEllipse(grid, hx, hy, hrx, hry, "head");
    const sl = (V.snout || 4) * hs;
    const mx = hx + hrx * 0.4 + sl * 0.6;
    const myy = hy + hry * 0.3 + sl * 0.3;
    const mr = Math.max(1.6, hry * 0.66);
    tube([[hx + hrx * 0.2, hy + hry * 0.05], [mx, myy]], [hry * 0.8, mr], "snout");
    fillEllipse(grid, mx + 0.3, myy, mr * 1.1, mr, "snout"); // a blunt, rounded muzzle
    fillTri(grid, [[hx - hrx * 0.45, hy - hry * 0.85], [hx + hrx * 0.05, hy - hry * 0.95], [hx - hrx * 0.3, hy - hry * 0.95 - 3.2 * hs]], "ear");
    // the mane: a crest along the top of the neck, locks falling back over it
    const m0 = [hx - hrx * 0.55, hy - hry * 0.75];
    const m1 = [mid[0] - 1, mid[1] - ry * 0.55];
    const m2 = [base[0] - ry * 0.5, base[1] - ry * 0.55];
    tube([m0, m1, m2], [1.3 * hs, 1.6 * s, 1.4 * s], "umane");
    for (let k = 0; k < 4; k++) {
      const t = (k + 0.5) / 4;
      const px = m0[0] + (m2[0] - m0[0]) * t;
      const py = m0[1] + (m2[1] - m0[1]) * t + Math.sin(t * Math.PI) * (m1[1] - (m0[1] + m2[1]) / 2);
      const sway = gallop ? -2.5 * s : 0;
      tube([[px, py], [px - 1.5 * s + sway, py + 2.5 * s], [px - 1.2 * s + sway + (step && k % 2 ? 0.6 : 0), py + 4.2 * s]], [1.2 * s, 1 * s, 0.6], "umane");
    }
    // the forelock, falling over the forehead
    tube([[hx - hrx * 0.1, hy - hry * 0.95], [hx + hrx * 0.45, hy - hry * 0.5], [hx + hrx * 0.5, hy - hry * 0.05]], [1.1 * hs, 1 * hs, 0.6], "umane");
    if (V.wings) featherWing(grid, frame, s, shoulder[0], shoulder[1], V.wings * s, -1, "feather", "feather2");
    // the horn: from the forehead, leaning forward
    const hb = [hx + hrx * 0.3, hy - hry * 0.8];
    hornAt(grid, hb, [hb[0] + hornL * 0.4, hb[1] - hornL * 0.92], hs);
    // the face
    face.eyes.push({ x: Math.round(hx - hrx * 0.05), y: Math.round(hy - hry * 0.3), size: eye, iris });
    // a nostril on the front of the muzzle, a short mouth line low on it
    face.noseDark.push([Math.round(mx + mr * 0.45), Math.round(myy - mr * 0.3)]);
    const mouthY = Math.round(myy + mr) - 1;
    face.smile.push([Math.round(mx + mr * 0.7), mouthY], [Math.round(mx + mr * 0.7) - 1, mouthY]);
  }

  relight(grid, "body");
  relight(grid, "head");
  relight(grid, "neck");
  relight(grid, "snout");
  const geo = {
    cx, cy: by, rx, ry, legTop: by + ry * 0.4, legH, tail: [cx - rx, by - ry * 0.5, 10 * s], head: [hx, hy, hrx, hry],
    faceBox: null, muzzle: null,
  };
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: hx, face, center: [cx, by], scale: s,
    softOutline: true, softNeck: true, geo,
  };
}

// A tapering tube through points, its radius running through `widths`.
function taper(grid, pts, widths, label) {
  pts.slice(1).forEach((p, i) => {
    const steps = Math.max(2, Math.ceil(Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]) * 1.5));
    for (let k = 0; k <= steps; k++) {
      const t = k / steps;
      const r = Math.max(0.55, widths[i] + (widths[i + 1] - widths[i]) * t);
      fillEllipse(grid, pts[i][0] + (p[0] - pts[i][0]) * t, pts[i][1] + (p[1] - pts[i][1]) * t, r, r, label);
    }
  });
}

// A feathered wing from the shoulder, raised up with long feathers fanning
// from the arm (dir -1 sweeps back to the left, +1 to the right); every other
// feather wears `alt`, so they read one by one. It flaps with the frame.
function featherWing(grid, frame, s, sx, sy, size, dir, label, alt) {
  const flap = frame % 2;
  const mx = (x) => sx + (x - sx) * -dir; // drawn sweeping left, mirrored for +1
  // the arm: up and back to the wrist (the wing's top corner)
  const wrist = [sx - size * 0.3, sy - size * (0.95 - flap * 0.12)];
  // the feathers: longest at the wrist, rounded tips
  const n = 6;
  for (let k = n - 1; k >= 0; k--) {
    const t = k / (n - 1); // 0 at the shoulder .. 1 at the wrist
    const root = [sx + (wrist[0] - sx) * t, sy + (wrist[1] - sy) * t];
    const a = Math.PI * (0.62 + t * 0.38); // down-back at the shoulder, straight back at the wrist
    const len = size * (0.45 + t * 0.55);
    const tip = [root[0] + Math.cos(a) * len, root[1] + Math.sin(a) * len * -1 * (t > 0.5 ? 0.15 : -0.3) + (t > 0.5 ? 0 : len * 0.2)];
    taper(grid, [[mx(root[0]), root[1]], [mx(tip[0]), tip[1]]], [Math.max(1, 1.25 * s), Math.max(0.8, 1.05 * s)], k % 2 ? alt : label);
  }
  fillStroke(grid, [[sx, sy], [mx(wrist[0]), wrist[1]]], Math.max(1, 1.4 * s), label); // the arm, over the feather roots
}

// A unicorn's horn: a tapering cone from base to tip with a spiral groove
// winding round it.
function hornAt(grid, a, b, hs) {
  const n = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) * 2);
  const r0 = Math.max(0.9, 1.2 * hs);
  for (let k = 0; k <= n; k++) {
    const t = k / n;
    fillEllipse(grid, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, Math.max(0.5, r0 * (1 - t * 0.85)), Math.max(0.5, r0 * (1 - t * 0.85)), "uhorn");
  }
  // the groove: short slanted marks every couple of pixels up the horn
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
  for (let d = 1.5; d < len - 1; d += 2) {
    const t = d / len;
    const x = Math.round(a[0] + (b[0] - a[0]) * t);
    const y = Math.round(a[1] + (b[1] - a[1]) * t);
    const c = grid[y] && grid[y][x];
    if (c && c.l === "uhorn") c.l = "uhornline";
  }
}

// --- phoenixes -------------------------------------------------------------------------
// A firebird: a round-breasted bird standing tall on thin gold legs, a small
// hooked beak, a crest of plumes curling back off the head, wings folded along
// the side (or raised, or spread in flight), and long tail plumes that sweep
// back and curl up at their tips -- or a tail made of flame. Side-on unless it
// faces us with its wings spread like an emblem. It's made of fire: painted by
// paintFire, with flames licking off its top. Reborn from ashes: it starts as
// a dark egg with glowing cracks in a pile of ash, hatches into a round flame
// chick sitting in the ashes, then grows to bigger than other pets.

const PHOENIX_GROWTH = {
  hatch: { body: 0.78, head: 0.95 },
  mid: { body: 0.7, head: 0.86 },
  big: { body: 0.92, head: 0.96 },
  grown: { body: 1.2, head: 1.1 },
};
const PHOENIX_CHICK = { facing: "side", pose: "chick", body: { rx: 6.4, ry: 6 }, head: 4, legs: 0, tail: 9, crest: 3, plumes: 2, fold: true, wings: 0, flame: false };

// A mound of grey ash with embers glowing in it.
function ashPile(grid, cx, rx, frame) {
  fillEllipse(grid, cx, GROUND - 0.5, rx, 2.4, "ash");
  for (let k = -3; k <= 3; k++) if ((k + frame) % 2) put(grid, Math.round(cx + k * rx * 0.28), GROUND - 1 - (k % 2 ? 1 : 0), { l: "ember", nx: 0, ny: -0.5 });
}

// The egg: dark as a coal, glowing cracks running round it, sitting in ash.
function buildPhoenixEgg(genes, frame) {
  const grid = makeGrid();
  const cx = 46;
  const rx = 6;
  const ry = 7.6;
  const cy = GROUND - 1.5 - ry;
  for (let y = Math.floor(cy - ry); y < GROUND; y++) {
    const ny = (y + 0.5 - cy) / ry;
    const w = rx * Math.sqrt(Math.max(0, 1 - ny * ny)) * (ny < 0 ? 1 + ny * 0.18 : 1);
    for (let x = Math.floor(cx - w - 1); x <= Math.ceil(cx + w + 1); x++) {
      const nx = (x + 0.5 - cx) / Math.max(1, w);
      if (Math.abs(nx) <= 1) put(grid, x, y, { l: "pegg", nx, ny });
    }
  }
  // the cracks: a zigzag round the middle, branches up and down from it
  // the glow pulses: on odd frames the cracks burn brighter
  const crack = (pts) => pts.slice(1).forEach((p, i) => line(grid, pts[i], p, frame % 2 ? "crack2" : "crack"));
  crack([[cx - rx, cy + 0.5], [cx - 3, cy - 1], [cx - 1, cy + 1], [cx + 1, cy - 1], [cx + 3, cy + 1], [cx + rx, cy - 0.5]]);
  crack([[cx - 1, cy + 1], [cx - 2, cy + 3], [cx - 1.5, cy + 4.5]]);
  crack([[cx + 1, cy - 1], [cx + 2, cy - 3], [cx + 1, cy - 4.5]]);
  ashPile(grid, cx, 9, frame);
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: cx, face: { eyes: [], pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [] },
    center: [cx, cy], scale: 1, softOutline: true, softNeck: true,
    geo: { cx, cy, rx, ry, legTop: GROUND, tail: [cx, cy, 0], head: [cx, cy - ry, 1, 1], faceBox: null, muzzle: null },
  };
}

function buildPhoenix(genes, stage, frame, V) {
  if (stage.id === "baby") return buildPhoenixEgg(genes, frame);
  if (stage.id === "small") return buildPhoenix(genes, { id: "hatch" }, frame, { ...V, ...PHOENIX_CHICK });
  const grid = makeGrid();
  const shape = genes.shape || {};
  const G = PHOENIX_GROWTH[stage.id];
  const s = G.body;
  const hs = G.head;
  const step = frame % 2;
  const pose = V.pose || "perch";
  const front = V.facing === "front";
  const fly = pose === "fly";
  const sitting = pose === "chick"; // a hatchling sits in the ashes
  const rx = V.body.rx * s + (shape.length || 0) / 2;
  const ry = V.body.ry * s + (shape.height || 0) / 5;
  const legH = sitting ? 0 : Math.max(2, V.legs * s * (1 + (shape.legs || 0) * 0.35) + (shape.height || 0) / 3);
  const cx = 46;
  const lift = fly ? 12 * s + step : 0;
  const by = GROUND - legH - ry * 0.95 - lift - (sitting ? 2 * s : 0);
  const hr = V.head * hs;
  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [], glints: [] };
  const iris = (genes.face && genes.face.eyes) || "#e0a828";
  const eye = V.eye || "duo";
  const L = V.tail * s * (1 + (shape.tail || 0) * 0.3);
  const wings = (V.wings || 0) * (1 + (shape.wings || 0) * 0.25);
  const sway = step * 0.6;

  // a plume: a thin quill sweeping along `pts`, ending in a teardrop tip
  const plume = (pts, w, tipR) => {
    taper(grid, pts, pts.map((_, i) => (i === pts.length - 1 ? w * 0.7 : w)), "plume");
    const [ex, ey] = pts[pts.length - 1];
    fillEllipse(grid, ex, ey, tipR, tipR * 1.15, "plumetip");
  };
  // a crest of plumes off the back of the head, curling back
  const crest = (x, y, dir, n) => {
    for (let k = 0; k < n; k++) {
      const a = -Math.PI / 2 - dir * (0.35 + k * 0.32);
      const len = (V.crest || 4) * hs * (1 + (shape.crest || 0) * 0.4) * (1 - k * 0.12);
      const mid = [x + Math.cos(a) * len * 0.6, y + Math.sin(a) * len * 0.6];
      const end = [x + Math.cos(a - dir * 0.35) * len, y + Math.sin(a - dir * 0.35) * len - step * 0.4 * (k % 2)];
      plume([[x, y], mid, end], 0.5, Math.max(0.6, 0.7 * hs));
    }
  };
  // a flame tail: tongues of fire streaming back from the rump, flickering
  const flameTail = (x, y, dir) => {
    // one big tongue of fire: wide at the rump, sweeping back and tapering,
    // with smaller tongues splitting off it, all flickering
    const pts = [[x, y], [x + dir * L * 0.35, y + L * 0.12], [x + dir * L * 0.7, y + L * 0.05 - step * 0.6], [x + dir * L, y - L * 0.15 + step * 0.6]];
    taper(grid, pts, [3 * s, 2.6 * s, 1.6 * s, 0.6], "flame");
    for (let k = 0; k < 3; k++) {
      const t = 0.3 + k * 0.22;
      const bx = x + dir * L * t;
      const byy = y + L * 0.1;
      const up = k % 2 ? -1 : 1;
      taper(grid, [[bx, byy], [bx + dir * L * 0.2, byy + up * L * 0.18 + (k % 2 ? step : -step) * 0.5]], [1.3 * s, 0.55], "flame");
    }
  };

  let hx;
  let hy;
  let chest = [cx + rx * 0.45, by];
  if (front) {
    // facing us, wings spread wide and up like an emblem, the tail fanned below
    const fy = GROUND - legH - ry - 1;
    for (const dir of [-1, 1]) {
      for (let k = 0; k < 3; k++) {
        const a = Math.PI / 2 + dir * (0.25 + k * 0.3);
        const len = L * (0.75 - k * 0.12);
        plume([[cx + dir * 1, fy + ry * 0.4], [cx + Math.cos(a) * len * 0.6, fy + ry * 0.4 + Math.sin(a) * len * 0.35], [cx + Math.cos(a) * len + dir * sway, Math.min(GROUND - 2, fy + ry * 0.4 + Math.sin(a) * len * 0.45)]], 0.6, Math.max(0.9, 1.1 * s));
      }
      featherWing(grid, frame, s, cx + dir * rx * 0.55, fy - ry * 0.4, wings * s, dir, "pfeather", "pfeather2");
    }
    for (const dir of [-1, 1]) {
      fillRect(grid, cx + dir * rx * 0.35 - 0.5, fy + ry * 0.7, 1, GROUND - fy - ry * 0.7, "birdleg");
      fillRect(grid, cx + dir * rx * 0.35 - 1.5, GROUND - 1, 3, 1, "birdleg");
    }
    fillEllipse(grid, cx, fy, rx * 0.75, ry, "body");
    fillEllipse(grid, cx, fy + ry * 0.25, rx * 0.45, ry * 0.65, "breast");
    hx = cx;
    hy = fy - ry * 0.95 - hr * 0.55;
    chest = [cx, fy + ry * 0.15];
    crest(hx, hy - hr * 0.6, 1, 2);
    crest(hx, hy - hr * 0.6, -1, 2);
    fillEllipse(grid, hx, hy, hr, hr * 0.95, "head");
    // the beak: a little hooked triangle pointing down from between the eyes
    const c = Math.round(hx);
    fillTri(grid, [[c - 1, hy + 0.2], [c + 2, hy + 0.2], [c + 0.5, hy + 2.6 * hs]], "beak");
    const ey = Math.round(hy - hr * 0.35);
    face.eyes.push({ x: c - 3, y: ey, size: eye, iris }, { x: c + 2, y: ey, size: eye, iris });
  } else {
    // side-on, facing right; a little upright, the breast forward
    const tx = cx - rx * 0.75;
    const ty = by + ry * 0.3;
    // the far leg, the tail (behind everything)
    if (!sitting && !fly) {
      fillRect(grid, cx + 1, by + ry * 0.6, 1, GROUND - by - ry * 0.6, "farbirdleg");
      fillRect(grid, cx + 1, GROUND - 1, 3, 1, "farbirdleg");
    }
    if (V.flame) {
      flameTail(tx, ty, -1);
    } else {
      // long ribbons of plumes arcing back from the rump, spread apart,
      // each drooping and then curling up at its tip
      const n = V.plumes || 3;
      const low = (y) => Math.min(GROUND - 2, y);
      for (let k = n - 1; k >= 0; k--) {
        const d = (k - (n - 1) / 2) * (fly ? 0.1 : 0.14) + (fly ? 0 : 0.02); // fanned: up, level, down
        const w = (k % 2 ? sway : -sway) * (fly ? 1.5 : 1);
        const pts = [[tx + 1, ty - 0.5], [tx - L * 0.3, low(ty + L * d * 0.6)], [tx - L * 0.65, low(ty + L * d * 1.1) + w * 0.5], [tx - L * (0.92 - k * 0.07), low(ty + L * d) - 2 * s + w]];
        taper(grid, pts, [0.95 * s, 0.8 * s, 0.65 * s, 0.55], "plume");
        const [ex, ey] = pts[3];
        fillEllipse(grid, ex, ey, Math.max(1, 1.2 * s), Math.max(1.1, 1.4 * s), "plumetip");
      }
    }
    if (V.wings && !fly) featherWing(grid, frame, s, cx + rx * 0.1 + 1.5, by - ry * 0.5, wings * s * 0.85, -1, "farpfeather", "farpfeather");
    if (fly) featherWing(grid, frame, s, cx + 1.5, by - ry * 0.4, wings * s * 0.9, -1, "farpfeather", "farpfeather");
    // the body: upright, the breast high and forward, tapering down and back
    fillEllipse(grid, cx + rx * 0.2, by - ry * 0.15, rx * 0.75, ry, "body");
    fillEllipse(grid, cx - rx * 0.45, by + ry * 0.3, rx * 0.6, ry * 0.65, "body");
    fillEllipse(grid, cx + rx * 0.5, by - ry * 0.05, rx * 0.42, ry * 0.8, "breast");
    if (sitting) ashPile(grid, cx, rx * 1.4, frame);
    // the near leg
    if (!sitting && !fly) {
      fillRect(grid, cx - 0.5, by + ry * 0.6, 1, GROUND - by - ry * 0.6, "birdleg");
      fillRect(grid, cx - 0.5, GROUND - 1, 3, 1, "birdleg");
      put(grid, Math.round(cx - 1.5), GROUND - 1, { l: "birdleg", nx: 0, ny: 0 }); // the back toe
    }
    if (fly) taper(grid, [[cx - 1, by + ry * 0.7], [cx - 3 * s, by + ry + 1.5 * s]], [0.6, 0.5], "birdleg"); // tucked
    // the folded wing along the side: a long teardrop, the long feathers at the back
    if (V.fold) {
      const w0 = [cx + rx * 0.45, by - ry * 0.35];
      const w1 = [cx - rx * 0.9, by + ry * 0.25];
      taper(grid, [w0, [cx - rx * 0.1, by - ry * 0.05], w1], [ry * 0.55, ry * 0.6, 0.8], "pfeather");
      for (let k = 0; k < 3; k++) taper(grid, [[cx - rx * (0.1 + k * 0.25), by + ry * (0.15 + k * 0.08)], [w1[0] - k * 1.2 * s - 1, w1[1] + k * 0.8]], [0.7, 0.55], k % 2 ? "pfeather2" : "pfeather");
    }
    // the head and neck
    hx = cx + rx * 0.75 + hr * 0.3;
    hy = by - ry * 0.85 - hr * 0.5 + (fly ? ry * 0.5 : 0);
    if (fly) hx += hr * 0.5;
    taper(grid, [[cx + rx * 0.45, by - ry * 0.3], [hx - hr * 0.2, hy + hr * 0.2]], [ry * 0.55, hr * 0.7], "neck");
    crest(hx - hr * 0.35, hy - hr * 0.55, 1, V.crestN || 3);
    fillEllipse(grid, hx, hy, hr, hr * 0.92, "head");
    // the beak: short and hooked, pointing forward
    const bx = hx + hr * 0.85;
    const byy = hy + hr * 0.1;
    fillTri(grid, [[bx - 0.5, byy - 1.2 * hs], [bx - 0.5, byy + 1 * hs], [bx + 2.6 * hs, byy + 0.6 * hs]], "beak");
    face.eyes.push({ x: Math.round(hx), y: Math.round(hy - hr * 0.35), size: eye, iris });
    if (V.wings && !fly) featherWing(grid, frame, s, cx + rx * 0.1, by - ry * 0.55, wings * s, -1, "pfeather", "pfeather2");
    if (fly) featherWing(grid, frame, s, cx, by - ry * 0.45, wings * s, -1, "pfeather", "pfeather2");
  }

  addLicks(grid, frame, s, fly ? -1.4 : -0.5);
  relight(grid, "body");
  relight(grid, "head");
  relight(grid, "breast");
  const geo = {
    cx, cy: by, rx, ry, legTop: GROUND - legH, tail: [cx - rx, by, L], head: [hx, hy, hr, hr],
    faceBox: null, muzzle: null, front, chest,
  };
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: hx, face, center: [cx, by], scale: s,
    softOutline: true, softNeck: true, geo, fire: true, frame,
  };
}

// --- fish ---------------------------------------------------------------------------
// Tropical freshwater fish, built from parts so every fish can differ: a body
// (its outline as top and bottom heights from tail to nose), a head, and
// fins -- dorsal (top), caudal (tail), anal (bottom), pectoral (front side) and
// pelvic. Side-on, facing right, swimming at its feeding level: bottom
// feeders just off the floor, top feeders high. Fish don't grow: every fish is
// a grown fish.

// Body outlines: half-heights above (top) and below (bot) the center line at
// FISH_T along the body, tail end (0) to nose (1); `len` is the length.
const FISH_T = [0, 0.12, 0.3, 0.5, 0.7, 0.85, 0.95, 1];
const FISH_BODIES = {
  tetra: { name: "Tetra: slim spindle, mid-water", zone: "mid", len: 22, top: [1.3, 1.6, 3.2, 4.2, 4.0, 3.2, 2.0, 0.6], bot: [1.3, 1.5, 3.0, 3.8, 3.6, 2.8, 1.6, 0.4] },
  discus: { name: "Discus: a round disc, mid-water", zone: "mid", len: 18, top: [1.5, 2.5, 6.5, 8.5, 8.5, 7.0, 4.5, 1.2], bot: [1.5, 2.5, 6.5, 8.5, 8.0, 6.5, 4.0, 1.0] },
  angel: { name: "Angelfish: a tall diamond, mid-water", zone: "mid", len: 16, top: [1.4, 2.6, 6.0, 8.8, 7.0, 4.6, 2.6, 0.8], bot: [1.4, 2.6, 6.0, 8.8, 6.6, 4.2, 2.0, 0.6] },
  gourami: { name: "Gourami/barb: a deep oval, mid-water", zone: "mid", len: 20, top: [1.6, 2.5, 5.0, 6.0, 5.6, 4.4, 2.8, 0.8], bot: [1.6, 2.4, 4.6, 5.6, 5.2, 4.0, 2.4, 0.6] },
  cory: { name: "Corydoras: arched back, flat belly, bottom feeder", zone: "bottom", len: 18, top: [1.4, 2.0, 4.5, 6.0, 6.2, 5.5, 4.0, 2.0], bot: [1.2, 1.4, 2.2, 2.6, 2.6, 2.4, 2.0, 1.4] },
  loach: { name: "Loach: long and slender, bottom feeder", zone: "bottom", len: 30, top: [1.0, 1.4, 2.2, 2.6, 2.6, 2.4, 2.0, 1.2], bot: [1.0, 1.3, 2.0, 2.4, 2.4, 2.2, 1.8, 1.0] },
  hatchet: { name: "Hatchetfish: straight back, deep keel belly, top feeder", zone: "top", len: 16, top: [1.2, 1.4, 1.8, 2.0, 2.0, 1.8, 1.4, 0.8], bot: [1.2, 2.0, 5.0, 8.0, 8.5, 6.5, 3.5, 1.0] },
  killi: { name: "Killifish/guppy: flat back, upturned mouth, top feeder", zone: "top", len: 22, top: [1.2, 1.5, 2.4, 2.8, 2.8, 2.6, 2.2, 1.4], bot: [1.2, 1.8, 3.4, 4.0, 3.6, 2.8, 1.8, 0.6] },
};

// Heads: how the front of the fish ends. `mouth` is where the mouth sits
// (up for surface feeders, down for bottom feeders).
const FISH_HEADS = {
  terminal: { name: "Plain: mouth straight ahead", mouth: "mid" },
  upturned: { name: "Upturned: jutting chin, mouth on top (surface feeder)", mouth: "up" },
  sucker: { name: "Sucker mouth: round lips underneath (pleco)", mouth: "down" },
  whiskers: { name: "Whiskers: barbels hanging from the mouth (cory, catfish)", mouth: "down" },
  snout: { name: "Long snout: a pointed nose", mouth: "mid" },
  hump: { name: "Hump: a bump on the forehead (cichlid)", mouth: "mid" },
  beak: { name: "Beak: a long needle of a lower jaw (halfbeak)", mouth: "up" },
  kisser: { name: "Kisser: big puckered lips (kissing gourami)", mouth: "mid" },
};

// Fins. Each is an outline of [u, v] points: dorsal and anal fins sit on a
// stretch of the body's edge (`at`: from-to along the body, tail end 0 to nose
// 1) with u along that base (0 at its back end, 1 at its front; below 0 trails
// back past it) and v outward from the edge in units of the fin's height `h`.
// The caudal (tail) has u back from the tail end in tail lengths and v up/down
// in tail heights. The pectoral has u back from just behind the gill and v
// down, in units of its size. `rays`: draw fin rays. Points with u past `flow`
// sway as the fish swims.
const FISH_CAUDAL = {
  forked: { name: "Forked (tetra)", pts: [[0, -0.3], [1, -1], [0.5, 0], [1, 1], [0, 0.3]], rays: true },
  round: { name: "Round fan (gourami)", pts: [[0, -0.3], [0.4, -0.85], [0.8, -0.75], [1, -0.3], [1.05, 0], [1, 0.3], [0.8, 0.75], [0.4, 0.85], [0, 0.3]], rays: true },
  lyre: { name: "Lyre: long curved points top and bottom", pts: [[0, -0.3], [0.6, -0.8], [1.45, -1.3], [0.9, -0.6], [0.55, 0], [0.9, 0.6], [1.45, 1.3], [0.6, 0.8], [0, 0.3]], rays: true, flow: 1 },
  veil: { name: "Veil: long and drooping (betta, fancy guppy)", pts: [[0, -0.35], [0.5, -0.75], [1.1, -0.45], [1.6, 0.4], [1.5, 1.35], [0.9, 1.1], [0.4, 0.5], [0, 0.35]], rays: true, flow: 0.8 },
  sword: { name: "Sword: a long point off the bottom (swordtail)", pts: [[0, -0.35], [0.5, -0.9], [0.95, -0.85], [0.9, -0.1], [0.85, 0.3], [2, 0.62], [1.9, 0.95], [0.5, 0.85], [0, 0.35]], rays: false, flow: 1.4 },
  delta: { name: "Delta: a wide triangle (guppy)", pts: [[0, -0.25], [1.2, -1.1], [1.25, 0], [1.2, 1.1], [0, 0.25]], rays: true, flow: 1 },
  spade: { name: "Spade: one rounded point", pts: [[0, -0.3], [0.6, -0.7], [1.3, 0], [0.6, 0.7], [0, 0.3]], rays: true },
  square: { name: "Square: a straight back edge (platy, cory)", pts: [[0, -0.35], [0.15, -0.85], [0.85, -0.9], [0.85, 0.9], [0.15, 0.85], [0, 0.35]], rays: true },
};
const FISH_DORSAL = {
  small: { name: "Small triangle", at: [0.42, 0.62], h: 4, pts: [[0, -1], [-0.15, 1], [1, -1]], rays: false },
  sail: { name: "Sail: tall and long (sailfin molly)", at: [0.2, 0.75], h: 7, pts: [[0, -1], [-0.05, 0.9], [0.3, 1], [0.7, 0.85], [1, -1]], rays: true },
  spiny: { name: "Spiny: a row of spines (cichlid)", at: [0.35, 0.72], h: 5, pts: [[0, -1], [0, 0.55], [0.12, 0.3], [0.25, 1], [0.4, 0.45], [0.55, 0.95], [0.7, 0.4], [0.85, 0.8], [1, -1]], rays: false },
  flowing: { name: "Flowing: trailing back over the tail (betta)", at: [0.3, 0.62], h: 5, pts: [[1, -1], [0.85, 0.7], [0.4, 1], [-0.5, 0.9], [-1.1, 0.25], [-0.6, 0.05], [0, -1]], rays: true, flow: -0.2 },
  round: { name: "Round fan", at: [0.4, 0.66], h: 4.5, pts: [[0, -1], [-0.05, 0.5], [0.15, 0.95], [0.5, 1.1], [0.85, 0.9], [1, 0.3], [1, -1]], rays: true },
  ridge: { name: "Low ridge: long and low (loach, knifefish)", at: [0.1, 0.8], h: 2.2, pts: [[0, -1], [0, 0.6], [0.2, 1], [0.8, 1], [1, 0.3], [1, -1]], rays: false },
  angel: { name: "Angel: a tall swept-back crescent", at: [0.4, 0.66], h: 9, pts: [[1, -1], [0.5, 0.6], [-0.3, 1], [-0.95, 1.05], [-0.45, 0.5], [0, -1]], rays: true, flow: -0.4 },
  twin: { name: "Twin: a fin and a little fatty fin behind (catfish)", at: [0.55, 0.7], h: 4, pts: [[0, -1], [-0.1, 1], [1, -1]], rays: false, adipose: [0.14, 0.24] },
};
const FISH_ANAL = {
  small: { name: "Small triangle", at: [0.18, 0.36], h: 3.5, pts: [[0, -1], [-0.1, 1], [1, -1]], rays: false },
  long: { name: "Long and low along the belly (tetra, knifefish)", at: [0.1, 0.5], h: 2.6, pts: [[0, -1], [0, 0.9], [0.5, 1], [1, 0.2], [1, -1]], rays: true },
  flowing: { name: "Flowing: trailing back (betta)", at: [0.15, 0.5], h: 4.5, pts: [[1, -1], [0.8, 0.7], [0.3, 1], [-0.5, 0.9], [-0.9, 0.4], [-0.3, 0.2], [0, -1]], rays: true, flow: -0.2 },
  angel: { name: "Angel streamer: tall, swept back", at: [0.3, 0.55], h: 8, pts: [[1, -1], [0.4, 0.55], [-0.5, 1], [-1.1, 1.05], [-0.4, 0.4], [0, -1]], rays: true, flow: -0.2 },
  round: { name: "Round", at: [0.2, 0.4], h: 3.5, pts: [[0, -1], [0, 0.5], [0.25, 1], [0.6, 1], [0.95, 0.5], [1, -1]], rays: true },
  spike: { name: "Spike: thin and pointed (livebearer)", at: [0.32, 0.42], h: 4, pts: [[0, -1], [-0.6, 1], [1, -1]], rays: false },
  fringe: { name: "Fringe: long with a scalloped edge", at: [0.12, 0.45], h: 3.5, pts: [[0, -1], [0, 1], [0.15, 0.6], [0.3, 1], [0.45, 0.6], [0.6, 1], [0.75, 0.6], [0.9, 0.9], [1, -1]], rays: false },
  nub: { name: "Nub: barely there", at: [0.2, 0.3], h: 1.6, pts: [[0, -1], [0.2, 1], [0.8, 1], [1, -1]], rays: false },
};
const FISH_PECTORAL = {
  small: { name: "Small teardrop", pts: [[0, -0.3], [1.1, 0.2], [0.9, 0.6], [0, 0.3]] },
  wing: { name: "Wing: long, swept back (hatchetfish)", pts: [[0, -0.4], [2.3, -0.05], [2.2, 0.45], [0, 0.4]] },
  fan: { name: "Round fan", pts: [[0, -0.3], [0.7, -0.6], [1.2, -0.2], [1.2, 0.4], [0.7, 0.8], [0, 0.3]] },
  feelers: { name: "Feelers: long threads (gourami)", pts: [[0, -0.25], [0.7, 0.1], [0, 0.3]], threads: true },
  spine: { name: "Spine: a stiff spike (cory)", pts: [[0, -0.2], [1.7, 0.5], [0, 0.2]] },
  flowing: { name: "Flowing: big and soft (betta)", pts: [[0, -0.3], [1.2, 0.3], [1.8, 1.3], [1.2, 1.45], [0.4, 0.7], [0, 0.3]], flow: 1 },
  nub: { name: "Nub: tiny", pts: [[0, -0.25], [0.5, 0.1], [0, 0.3]] },
  butterfly: { name: "Butterfly: broad and spread (hillstream loach)", pts: [[0, -0.4], [0.4, -0.95], [1.2, -0.65], [1.4, 0.4], [0.8, 1.05], [0, 0.4]] },
};

// A filled polygon (fins).
function fillPoly(grid, pts, label) {
  const ys = pts.map((p) => p[1]);
  for (let y = Math.floor(Math.min(...ys)); y <= Math.ceil(Math.max(...ys)); y++) {
    const yc = y + 0.5;
    const xs = [];
    pts.forEach((a, i) => {
      const b = pts[(i + 1) % pts.length];
      if ((a[1] <= yc) !== (b[1] <= yc)) xs.push(a[0] + ((yc - a[1]) / (b[1] - a[1])) * (b[0] - a[0]));
    });
    xs.sort((m, n) => m - n);
    for (let k = 0; k + 1 < xs.length; k += 2) for (let x = Math.round(xs[k]); x < Math.round(xs[k + 1]); x++) put(grid, x, y, { l: label, nx: 0, ny: -0.3 });
  }
}

// Every part a fish is built from and its options, for rolling and the lab.
const FISH_PARTS = {
  get body() {
    return FISH_BODIES;
  },
  get head() {
    return FISH_HEADS;
  },
  get caudal() {
    return FISH_CAUDAL;
  },
  get dorsal() {
    return FISH_DORSAL;
  },
  get anal() {
    return FISH_ANAL;
  },
  get pectoral() {
    return FISH_PECTORAL;
  },
};

// a body outline's half-height at t, eased smoothly between the samples
function fishHalf(arr, t) {
  const i = Math.max(0, Math.min(FISH_T.length - 2, FISH_T.findIndex((v, k) => t <= FISH_T[k + 1])));
  const u = (t - FISH_T[i]) / (FISH_T[i + 1] - FISH_T[i]);
  const e = (1 - Math.cos(Math.PI * Math.max(0, Math.min(1, u)))) / 2;
  return arr[i] + (arr[i + 1] - arr[i]) * e;
}

function buildFish(genes, stage, frame, V) {
  const shape = genes.shape || {};
  const grid = makeGrid();
  const B = FISH_BODIES[V.body || shape.body] || FISH_BODIES.tetra;
  const headKey = V.head || shape.head;
  const H = FISH_HEADS[headKey] || FISH_HEADS.terminal;
  const swish = frame % 2;
  const size = 1 + (shape.size || 0) * 0.25; // the whole fish, bigger or smaller
  const sx = 1.3 * size * (1 + (shape.length || 0) * 0.08); // stretch along the length
  const sy = 1.3 * size * (1 + (shape.height || 0) * 0.08); // and up and down
  const L = B.len * sx;
  const maxBot = Math.max(...B.bot) * sy;
  const maxTop = Math.max(...B.top) * sy;
  const finRoom = 6; // room for the fins above and below
  const cy = B.zone === "bottom" ? GROUND - 2 - maxBot - (V.finsBelow ? 3 : 1) : B.zone === "top" ? GROUND - 30 - maxBot : GROUND - 16 - maxBot;
  const x0 = 46 - L / 2; // the tail end; the nose at x0 + L
  const top = (x) => fishHalf(B.top, (x - x0) / L) * sy;
  const bot = (x) => fishHalf(B.bot, (x - x0) / L) * sy;
  const edgeTop = (t) => [x0 + L * t, cy - fishHalf(B.top, t) * sy];
  const edgeBot = (t) => [x0 + L * t, cy + fishHalf(B.bot, t) * sy];

  // fins behind the body first: the tail, the dorsal, the anal, the pelvic
  const fs = size * (1 + (shape.fins || 0) * 0.3); // the fins knob: all fins bigger or smaller
  const sway = swish ? 1 : -1;
  const bodyH = (maxTop + maxBot) / 2;
  const rays = (base, outer, label) => outer.forEach((p) => line(grid, base, p, label));
  // the tail: back from the tail end
  const C = FISH_CAUDAL[V.caudal || shape.caudal] || FISH_CAUDAL.forked;
  // the tail knob sets its length, tailh its height: each half again or half as much
  const tl = 7 * fs * (1 + (shape.tail || 0) * 0.5);
  const th = Math.max(3.5, bodyH * 0.75) * Math.sqrt(fs) * (1 + (shape.tailh || 0) * 0.5);
  const tailPts = C.pts.map(([u, v]) => [x0 + 1 - u * tl, cy + v * th + (u > (C.flow || 0.6) ? sway * 0.8 : 0)]);
  fillPoly(grid, tailPts, "caudal");
  if (C.rays) rays([x0 + 0.5, cy], tailPts.filter((_, i) => C.pts[i][0] > 0.5), "cray");
  // a fin on the back or belly: its base laid along the body's edge
  const edgeFin = (F, side, label) => {
    const [a, b] = F.at;
    const h = F.h * fs * (side < 0 ? 1 : 0.9);
    const at = (u, v) => {
      const t = a + (b - a) * u;
      const x = x0 + L * Math.max(0, Math.min(1, t)) + (t < 0 ? t * L : 0);
      const edge = side < 0 ? cy - fishHalf(B.top, Math.max(0, Math.min(1, t))) * sy : cy + fishHalf(B.bot, Math.max(0, Math.min(1, t))) * sy;
      // v below 0 tucks the base a pixel or so into the body, whatever the
      // fin's height (a tall fin on a thin body mustn't poke out the far side)
      return [x, edge + side * (v < 0 ? v * 1.2 : v * h) + (F.flow !== undefined && u < F.flow ? sway * 0.6 : 0)];
    };
    const pts = F.pts.map(([u, v]) => at(u, v));
    fillPoly(grid, pts, label);
    if (F.rays) rays(at(0.5, -0.5), pts.filter((_, i) => F.pts[i][1] > 0.6), label === "dorsal" ? "dray" : "aray");
    if (F.adipose) {
      // a small rounded fatty fin near the tail
      const [m, n] = F.adipose;
      fillPoly(grid, [[x0 + L * m, cy - fishHalf(B.top, m) * sy + 1], [x0 + L * m, cy - fishHalf(B.top, m) * sy - 1.4 * fs], [x0 + L * n, cy - fishHalf(B.top, n) * sy - 1.6 * fs], [x0 + L * n, cy - fishHalf(B.top, n) * sy + 1]], label);
    }
  };
  edgeFin(FISH_DORSAL[V.dorsal || shape.dorsal] || FISH_DORSAL.small, -1, "dorsal");
  edgeFin(FISH_ANAL[V.anal || shape.anal] || FISH_ANAL.small, 1, "anal");
  const pv = edgeBot(0.55);
  fillTri(grid, [[pv[0] - 1, pv[1] - 1], [pv[0] + 1.5, pv[1] - 1], [pv[0] - 2.5, pv[1] + 2.5]], "pelvic");

  // the body, and the head (the front of it, from the gill line forward)
  const gillT = V.gill || 0.76;
  for (let x = Math.floor(x0); x <= Math.ceil(x0 + L); x++) {
    const xc = x + 0.5;
    if (xc < x0 || xc > x0 + L) continue;
    const t = (xc - x0) / L;
    const up = top(xc);
    const dn = bot(xc);
    for (let y = Math.floor(cy - up); y <= Math.ceil(cy + dn); y++) {
      const yc = y + 0.5;
      if (yc < cy - up || yc > cy + dn) continue;
      const ny = yc < cy ? (yc - cy) / Math.max(1, up) : (yc - cy) / Math.max(1, dn);
      put(grid, x, y, { l: t > gillT ? "fhead" : "fbody", nx: (t - 0.6) * 1.4, ny });
    }
  }
  // the head's own shape at the nose
  const nx = x0 + L; // the tip of the nose
  const nt = top(nx - 1.5);
  const nb = bot(nx - 1.5);
  let mouth = [Math.round(nx) - 1, H.mouth === "up" ? Math.round(cy - nt + 1) : H.mouth === "down" ? Math.round(cy + nb - 1) : Math.round(cy + 0.5)];
  if (headKey === "upturned") {
    // the lower jaw juts forward and up past the nose, the mouth a slanted
    // line along its top
    fillTri(grid, [[nx - 4, cy + nb * 0.6], [nx - 3, cy - nt * 0.1], [nx + 2.6, cy - nt - 0.6]], "fhead");
    fillTri(grid, [[nx - 4, cy + nb * 0.6], [nx + 2.6, cy - nt - 0.6], [nx + 0.5, cy + nb * 0.2]], "fhead");
    line(grid, [nx + 1.6, cy - nt], [nx - 1.5, cy - nt * 0.3], "mouthline");
    mouth = [Math.round(nx + 1.6), Math.round(cy - nt)];
  } else if (headKey === "sucker") {
    // a round snout bending down to a wide sucker disc of lips underneath
    fillEllipse(grid, nx - 1, cy + nb * 0.4, 2.8, Math.max(2.4, nb * 0.85), "fhead");
    fillEllipse(grid, nx - 2, cy + nb + 1.2, 3.2, 1.7, "lip");
    mouth = [Math.round(nx - 2), Math.round(cy + nb + 1.5)];
  } else if (headKey === "whiskers") {
    // two barbels hanging forward and down from under the mouth
    for (const k of [0, 1]) line(grid, [nx - 1.5 - k * 1.5, cy + nb - 0.5], [nx + 1 - k * 1.8, cy + nb + 3 + swish * 0.5 - k * 0.5], "barbel");
  } else if (headKey === "snout") {
    // a long tapering nose
    taper(grid, [[nx - 2, cy - 0.3], [nx + 4, cy + 0.2]], [Math.max(1, Math.min(nt, nb) * 0.7), 0.55], "fhead");
    mouth = [Math.round(nx + 3), Math.round(cy + 0.5)];
  } else if (headKey === "hump") {
    // a big bulging forehead rising above the eye
    const hx2 = nx - L * 0.14;
    fillEllipse(grid, hx2, cy - top(hx2) + 0.2, Math.max(3, L * 0.12), Math.max(2.6, top(hx2) * 0.6), "fhead");
  } else if (headKey === "beak") {
    // the lower jaw: a long thin needle out ahead
    taper(grid, [[nx - 2, cy + nb * 0.3], [nx + 6, cy + nb * 0.3]], [0.9, 0.5], "fhead");
    mouth = [Math.round(nx), Math.round(cy)];
  } else if (headKey === "kisser") {
    // big puckered lips sticking out, a dark line between them
    fillEllipse(grid, nx + 1, cy - 0.2, 2.2, Math.max(2, Math.min(nt, nb) * 0.75), "lip");
    mouth = [Math.round(nx + 2.4), Math.round(cy)];
  }

  // the near pectoral fin, just behind the gill, lying over the body
  const P = FISH_PECTORAL[V.pectoral || shape.pectoral] || FISH_PECTORAL.small;
  // low on the side, angled down and back so it reaches past the belly
  const pc = [x0 + L * (gillT - 0.03), cy + bot(x0 + L * gillT) * 0.35];
  const ps = 4.2 * fs * Math.max(0.85, Math.min(1.3, bodyH / 4.5));
  const ang = 0.45;
  const pecAt = (u, v) => [pc[0] - u * ps * Math.cos(ang) + v * ps * Math.sin(ang), pc[1] + u * ps * Math.sin(ang) + v * ps * Math.cos(ang)];
  const pecPts = P.pts.map(([u, v]) => {
    const [x, y] = pecAt(u, v);
    return [x, y + (P.flow !== undefined && u >= P.flow ? sway * 0.6 : 0)];
  });
  fillPoly(grid, pecPts, "pectoral");
  if (P.threads) {
    // long threads trailing down and back
    for (const k of [0, 1]) line(grid, pecAt(0.3, 0.1 + k * 0.2), [pc[0] - 2.2 * ps - k * 1.5, pc[1] + 2.2 * ps + sway * 0.6 + k], "pectoral");
  }

  // the face: an eye up front, the mouth at the nose, a gill line
  const face = { eyes: [], nose: null, pink: [], noseDark: [], mouth: [], smile: [], tongue: [], tufts: [], glints: [] };
  // a dark eye color would melt into the pupil, so those fish get a bright
  // gold or silver ring instead (real fish eyes shine like that); silver
  // would vanish on a pale fish, so those get gold
  const lum = (hex) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
    return 0.299 * r + 0.587 * g + 0.114 * b;
  };
  let iris = (genes.face && genes.face.eyes) || "#e0a828";
  const body = (genes.hex || [])[0];
  if (lum(iris) < 90) iris = genes.seed % 2 && !(body && lum(body) > 170) ? "#d8dce8" : "#e8c050";
  const eyeX = x0 + L * 0.9;
  const big = top(eyeX) + bot(eyeX) >= 6;
  face.eyes.push({ x: Math.round(eyeX) - (big ? 2 : 1), y: Math.round(cy - top(eyeX) * 0.45) - (big ? 1 : 0), size: big ? "fish" : "fishsmall", iris });
  face.smile.push(mouth, [mouth[0] - 1, mouth[1]]);
  // the gill cover's edge: a curve bowing back toward the tail
  const gx = x0 + L * gillT;
  const gt = top(gx) * 0.7;
  const gb = bot(gx) * 0.7;
  for (let y = Math.round(cy - gt); y <= Math.round(cy + gb); y++) {
    const u = (y - cy) / Math.max(1, y < cy ? gt : gb);
    put(grid, Math.round(gx - (1 - u * u) * 1.6), y, { l: "gill", nx: 0, ny: 0 });
  }

  relight(grid, "fbody");
  const geo = { cx: 46, cy, rx: L / 2, ry: (maxTop + maxBot) / 2, legTop: GROUND, tail: [x0, cy, tl], head: [x0 + L * 0.9, cy, 3, 3], faceBox: null, muzzle: null };
  const eye = face.eyes[0];
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: false, headX: x0 + L, face, center: [46, cy], scale: 1,
    softOutline: true, softNeck: true, geo, noShadow: true,
    // for paintFish: where the body runs, the eye, the pectoral's root
    fish: { x0, L, eye: [eye.x + 1, eye.y + 1], pec: pc },
  };
}

// A one-pixel line between two points (wing bones).
function line(grid, a, b, label) {
  const n = Math.max(1, Math.ceil(Math.max(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1]))));
  for (let k = 0; k <= n; k++) put(grid, Math.floor(a[0] + ((b[0] - a[0]) * k) / n), Math.floor(a[1] + ((b[1] - a[1]) * k) / n), { l: label, nx: 0, ny: -0.5 });
}

const EYE_SHAPES = {
  s: ["WK", "IK"],
  m: ["KK", "IW", "IP", "KP"],
  l: ["KKK", "IIW", "IPI", "KPK"],
  // friendly: a dark eye with a little color low down
  f: ["PP", "IP", "PP"],
  // eye styles being compared in the pet lab ("." leaves the fur showing)
  slit: ["IPI", "IPI"], // colored eye, slit pupil
  big: ["III", "IPI", "III"], // all color, a dot of pupil
  shine: ["IP", "PP"], // small and dark, a fleck of color
  tall: ["IP", "IP", "IP"], // color beside a tall pupil
  lidded: ["KKK", "IPI"], // content, half-closed
  dark: ["PP", "PP"], // plain dark dot
  almond: [".II", "IPI", "II."], // slanted cat eye
  duo: ["IP", "IP"], // color on the left, dark on the right
  fish: ["IIW", "IPI", "III"], // a fish eye: a ring of color, a dark pupil, a glint
  fishsmall: ["IW", "IP"], // a little fish's eye: color, pupil, a glint
  closed: ["..", "KK"], // asleep: just a lash line
  goat: ["III", "PPP"], // a goat's sideways bar pupil
};

// Draws a variant's face: eyes (with blinks), nose, mouth, ear tufts.
function drawFace(dot, at, face, genes, frame, outline) {
  const blink = frame % 9 === 8;
  for (const eye of face.eyes) {
    let rows = EYE_SHAPES[eye.size] || EYE_SHAPES.m;
    if (eye.narrow) rows = rows.map((r) => r.slice(1));
    if (blink) {
      // a closed eye: just the lash line, one row down
      [...rows[0]].forEach((_, i) => dot(eye.x + i, eye.y + 2, PET_OUTLINE));
      continue;
    }
    rows.forEach((row, j) =>
      [...row].forEach((c, i) => {
        const color = { K: PET_OUTLINE, W: "#ffffff", I: eye.iris, P: "#120a06" }[c];
        if (color) dot(eye.x + i, eye.y + j, color);
      })
    );
  }
  if (face.nose) for (let i = 0; i < face.nose.w; i++) dot(face.nose.x + i, face.nose.y, PET_FIXED.pinknose);
  for (const [x, y] of face.mouth) dot(x, y, PET_OUTLINE);
  for (const [x, y] of face.pink) dot(x, y, PET_FIXED.pinknose);
  for (const [x, y] of face.smile) dot(x, y, outline(x, y));
  for (const [x, y] of face.noseDark) dot(x, y, PET_FIXED.nose);
  if (frame % 4 < 2) for (const [x, y] of face.tongue) dot(x, y, PET_FIXED.tongue);
  for (const [x, y, c] of face.glints || []) dot(x, y, c);
  for (const [x, y] of face.tufts) {
    dot(x, y, PET_OUTLINE);
    dot(x, y - 1, PET_OUTLINE);
  }
}
