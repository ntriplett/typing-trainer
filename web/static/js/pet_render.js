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
  dog: {
    body: { rx: 10, ry: 5.5 }, leg: { len: 6, w: 3, min: 3 }, head: { rx: 5.5, ry: 5, dx: 1, dy: -1 },
    snout: { len: 5, r: 2.5, square: true }, ears: { type: "floppy", size: 6 }, tail: { type: "up", len: 7, w: 2 },
    eye: "round", tongue: true, bigNose: true,
  },
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
const FUR = new Set(["farleg", "tail", "body", "wool", "leg", "neck", "head", "farear", "ear", "snout", "beard", "cap", "chest", "fold"]);
// Parts that cover what's behind them with a line (inside the silhouette).
const FRONT = new Set(["body", "wool", "head", "face", "cap", "neck", "chest"]);
// Parts in front of the body that grow out of it (no line where they meet).
const BLENDS_IN = new Set(["leg", "skin", "beard", "sock", "hoof", "ear", "farear", "eartip", "fold"]);
// The head stands apart from the body with a shade line and a chin shadow.
const HEADISH = new Set(["head", "face", "snout", "cap"]);
const BODYISH = new Set(["body", "wool", "chest", "neck", "leg", "tail"]);
// Parts drawn behind the body: darker, like they're in shadow.
const FAR = new Set(["farleg", "farear", "farskin", "farsock", "farhoof"]);
const PET_FIXED = {
  hoof: "#5a4030", farhoof: "#5a4030", horn: "#e2d2b0", innerear: "#f4a8b8", nose: "#2a1a14", pinknose: "#f08aa0",
  tip: "#fbf6ec", eartip: "#3a2a24", sock: "#3a2a24", farsock: "#3a2a24", cotton: "#fbf8f2", tongue: "#f07890",
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

const GRID_W = 72;
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
const SMOOTHED = new Set(["body", "head", "wool", "chest", "face", "neck", "cap"]);
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
  const R = PET_RECIPES[genes.species] || PET_RECIPES.dog;
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

const petCache = new Map();

// The finished pixels: {w, h, pix: rows of hex or null}. Cached per pet,
// growth stage, and animation frame.
function petPixels(genes, growth, frame = 0) {
  const stage = petStage(growth);
  const anim = genes.face && genes.face.sparkle ? frame % 36 : `${frame % 2}${frame % 9 === 8}${frame % 4 < 2}`;
  const key = `${genes.seed}|${genes.species}|${genes.variant}|${stage.id}|${anim}|${JSON.stringify(genes.coat)}|${JSON.stringify(genes.shape)}|${genes.hex}`;
  if (petCache.has(key)) return petCache.get(key);
  const design = (genes.variant && (PET_VARIANTS[genes.species] || [])[genes.variant - 1]) || PET_DESIGNS[genes.species];
  const built = design ? buildVariant(genes, stage, frame, design) : buildPet(genes, stage, frame);
  smoothEdges(built.grid);
  const { grid, R } = built;
  const at = (x, y) => (grid[y] && grid[y][x]) || null;
  const out = Array.from({ length: GRID_H }, () => new Array(GRID_W).fill(null));
  const hex = genes.hex.map((h) => h && liftDark(h));

  // coat colors by rank: each color gets exactly its share of fur pixels
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

  // a sheep's face and legs: a darker (or, on dark wool, lighter) shade of its wool
  const skinColor = luminance(hex[0]) > 0.45 ? blend(hex[0], "#3a2a28", 0.62) : blend(hex[0], "#f0e0d0", 0.35);

  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const cell = grid[y][x];
      if (!cell) continue;
      if (!FUR.has(cell.l)) {
        out[y][x] = cell.l === "face" || cell.l === "skin" || cell.l === "farskin" ? skinColor : PET_FIXED[cell.l] || hex[0];
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
        const rim = !isEar(at(x + outward, y)) && !single;
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
          lines.push([x, y, built.softOutline ? blend(out[by[1]][by[0]], PET_OUTLINE, 0.72) : PET_OUTLINE]);
        }
      } else if (!FRONT.has(cell.l) && !BLENDS_IN.has(cell.l) && near.some((n) => n && n.l !== cell.l && FRONT.has(n.l))) {
        lines.push([x, y, blend(out[y][x], SHADOW_TINT, 0.62)]);
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

  // crop to the pet; the feet always sit on the bottom row
  let minX = GRID_W;
  let maxX = -1;
  let minY = GRID_H;
  out.forEach((row, y) =>
    row.forEach((c, x) => {
      if (!c) return;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
    })
  );
  const pix = out.slice(minY, GROUND + 1).map((row) => row.slice(minX, maxX + 1));
  const result = { w: maxX - minX + 1, h: GROUND + 1 - minY, pix };
  if (petCache.size > 2000) petCache.clear();
  petCache.set(key, result);
  return result;
}

// Draws a pet with its feet at (x, bottom) and its left edge at x, `scale`
// px units per pet pixel, with a soft shadow on the ground. faceLeft mirrors it.
function drawPet(px, x, bottom, genes, growth, { frame = 0, faceLeft = false, scale = 1, shadow = true } = {}) {
  const { w, h, pix } = petPixels(genes, growth, frame);
  const top = bottom - h * scale;
  if (shadow) {
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
  // chosen in the pet lab, 2026-10-27: front-facing face with a 7x4 nose and
  // mouth, duo eyes, soft outline, cute proportions
  cat: {
    name: "Cat", facing: "front", pose: "walk", mouth: "w", eyesLow: true, softOutline: true, softNeck: true,
    body: { rx: 8.4, ry: 3.9 }, leg: { len: 5.5, w: 1, min: 3 }, head: { rx: 6.3, ry: 5.4 },
    ears: { size: 5, w: 0.85 }, tail: { type: "question", len: 13, w: 2.4 }, eye: "duo",
  },
};

const PET_VARIANTS = {};

function buildVariant(genes, stage, frame, V) {
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
  const legLen = Math.max(V.leg.min, Math.round(V.leg.len * ls * (stalk ? 0.75 : 1) + (shape.height || 0) / 2));
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
  const tail = (tx, ty) => {
    const L = tailLen;
    const pts = {
      question: [[tx, ty], [tx - L * 0.2, ty - L * 0.4], [tx - L * 0.15, ty - L * 0.8], [tx + L * 0.15 - wag, ty - L * 0.95]],
      whip: [[tx, ty], [tx - L * 0.25, ty - L * 0.5], [tx - L * 0.2 - wag, ty - L * 0.95]],
      plume: [[tx, ty], [tx - L * 0.35, ty - L * 0.45], [tx - L * 0.25 - wag, ty - L * 0.85]],
      thick: [[tx, ty], [tx - L * 0.4, ty - L * 0.6], [tx - L * 0.35 - wag, ty - L * 0.9]],
      low: [[tx, ty], [tx - L * 0.55, ty + 0.5], [tx - L * 0.9, ty - L * 0.25 - wag]],
      s: [[tx, ty], [tx - L * 0.35, ty + L * 0.05], [tx - L * 0.5, ty - L * 0.4], [tx - L * 0.35 - wag, ty - L * 0.8]],
    }[V.tail.type];
    if (pts) fillStroke(grid, pts, tw, "tail");
  };

  // a body: a deeper chest, a tucked waist, the hips, and a belly from `weight`
  const body = (bx, by) => {
    fillEllipse(grid, bx, by - ry * 0.12, rx * 0.92, ry * 0.9, "body");
    fillEllipse(grid, bx + rx * 0.38, by, rx * 0.6, ry * 1.05, "body");
    fillEllipse(grid, bx - rx * 0.42, by - ry * 0.08, rx * 0.55, ry * 0.95, "body");
    if (weight > 0) fillEllipse(grid, bx, by + ry * 0.35, rx * 0.62, ry * (0.35 + weight * 0.4), "body");
  };

  let hx;
  let hy;
  const hrx = V.head.rx * hs;
  const hry = (V.head.ry + (V.mouth ? 0.5 : 0)) * hs;
  if (loaf) {
    // lying down: a round loaf of a body, two front paws peeking out, the tail along the side
    const ly = GROUND - ry * 1.05;
    fillEllipse(grid, cx, ly, rx, ry * 1.1, "body");
    const L = tailLen;
    fillStroke(grid, [[cx - rx * 0.9, GROUND - 2], [cx - rx * 0.4, GROUND - 1.2], [cx - rx * 0.4 + L * 0.5, GROUND - 1.2 - wag * 0.5]], tw, "tail");
    for (const dx of [0.55, 0.85]) fillEllipse(grid, cx + rx * dx, GROUND - 1, Math.max(1.2, 1.6 * s), 1.1, "leg");
    hx = cx + rx * 0.55;
    hy = ly - ry * 0.9 - hry * 0.35;
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
    fillStroke(grid, [[hcx - rh * 0.7, GROUND - 2.5], [hcx - rh * 0.9, GROUND - 1.2], [hcx + rh * 0.2, GROUND - 1], [hcx + rh * 0.2 + L * 0.35, GROUND - 1.5 - wag]], tw, "tail");
    hx = chx + 0.5;
    hy = chy - ry * 1.2 - hry * 0.45;
  } else {
    const backX = cx - rx * 0.55;
    const frontX = cx + rx * 0.45;
    leg(backX + farOffset, cy, step ? 0 : 1, "farleg");
    leg(frontX + farOffset, cy, step ? 1 : 0, "farleg");
    tail(cx - rx + 1, cy - ry * 0.4);
    body(cx, cy);
    if (V.ruff) {
      fillEllipse(grid, cx + rx * 0.62, cy - ry * 0.1, Math.max(2, rx * 0.3), ry * 1.05, "chest");
      for (const dy of [0.5, 0.95]) fillEllipse(grid, cx + rx * 0.62, cy + ry * dy, Math.max(1.3, rx * 0.2), 1.3, "chest");
    }
    leg(backX - 0.5, cy, step ? 1 : 0, "leg");
    leg(frontX - 0.5, cy, step ? 0 : 1, "leg");
    hx = cx + rx * (stalk ? 0.95 : V.headMin ? 0.9 : 0.78);
    hy = stalk ? cy - ry * 0.4 : cy - ry * (V.headMin ? 1 : 0.75) - hry * (V.headMin ? 0.7 : 0.45);
  }

  // the head
  const es = V.ears.size * hs * earScale(shape);
  const ew = es * 0.55 * V.ears.w;
  const face = { eyes: [], nose: null, pink: [], mouth: [], smile: [], tufts: [] };
  const eyeSize = V.eye;
  const odd = genes.face && genes.face.odd_eye;
  const iris = (genes.face && genes.face.eyes) || "#7ab84a";

  if (V.facing === "front") {
    for (const side of [-1, 1]) {
      const base = hx + side * hrx * 0.55;
      if (!V.ears.fold) fillTri(grid, [[base - ew, hy - hry * 0.35], [base + ew, hy - hry * 0.6], [base + side * ew * 0.25, hy - hry * 0.75 - es]], "ear");
    }
    if (V.heart) {
      fillEllipse(grid, hx, hy - hry * 0.12, hrx, hry * 0.8, "head");
      fillTri(grid, [[hx - hrx * 0.95, hy - hry * 0.05], [hx + hrx * 0.95, hy - hry * 0.05], [hx, hy + hry]], "head");
    } else {
      fillEllipse(grid, hx, hy, hrx, hry, "head");
    }
    if (V.cheeks) fillEllipse(grid, hx, hy + hry * 0.3, hrx * V.cheeks, hry * 0.6, "head");
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
    fillTri(grid, [[hx - hrx * 0.9, hy - hry * 0.3], [hx - hrx * 0.05, hy - hry * 0.85], [hx - hrx * 0.75, hy - hry * 0.75 - es * 0.9]], "farear");
    if (V.heart) {
      fillEllipse(grid, hx, hy - hry * 0.15, hrx, hry * 0.78, "head");
      fillTri(grid, [[hx - hrx * 0.92, hy - hry * 0.1], [hx + hrx * 0.98, hy - hry * 0.1], [hx + hrx * 0.3, hy + hry * 0.95]], "head");
    } else {
      fillEllipse(grid, hx, hy, hrx, hry, "head");
    }
    const sr = Math.max(1.3, 1.8 * hs);
    const sy = hy + hry * 0.3;
    if (V.snout === "wedge") fillTri(grid, [[hx + hrx * 0.3, sy - sr], [hx + hrx * 0.3, sy + sr], [hx + hrx + 2.5 * hs, sy + sr * 0.3]], "snout");
    else fillEllipse(grid, hx + hrx * 0.8, sy, 1.8 * hs + 0.6, sr, "snout");
    fillTri(grid, [[hx - hrx * 0.45, hy - hry * 0.8], [hx + hrx * 0.45, hy - hry * 0.75], [hx - hrx * 0.05, hy - hry * 0.75 - es]], "ear");
    const ey = Math.round(hy - hry * 0.35);
    const ex = Math.round(hx + hrx * 0.1);
    face.eyes.push({ x: ex, y: ey, size: eyeSize, iris: odd || iris });
    const nx = Math.round(hx + hrx + (V.snout === "wedge" ? 2 * hs : 1.6 * hs));
    const ny = Math.round(sy - sr * 0.5);
    face.nose = { x: nx - 1, y: ny, w: 2 };
  }

  relight(grid, "body");
  relight(grid, "head");
  return {
    grid, R: { ears: { type: "variant" } }, innerEars: !V.ears.fold, headX: hx, face, center: [cx, cy], scale: s,
    softOutline: V.softOutline, softNeck: V.softNeck,
  };
}

// Eye shapes, rows top to bottom: K lash/outline, W glint, I iris, P pupil.
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
  for (const [x, y] of face.tufts) {
    dot(x, y, PET_OUTLINE);
    dot(x, y - 1, PET_OUTLINE);
  }
}
