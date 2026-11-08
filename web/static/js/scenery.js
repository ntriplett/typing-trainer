// Page scenery (themes.js): the place you've picked, drawn big behind the
// page in pixel art. A banded sky with clouds and a sun (or stars and a moon
// at night), far hills or mountains, the place's own things down both sides
// of the page (trees for the forests, palms on the beach, cliffs and
// waterfalls, kelp under the sea, cacti, giant mushrooms, planets...), and a
// ground you could walk on along the bottom. Clouds drift and a few things
// sway; particles (themes.js) still fall in front.
//
// On every page that loads this file, typing pages too (particles stay off those:
// they drift in front of the words). Its helpers stay private, since other scripts
// have their own SCENES, pine and the like. Everything is drawn on a grid of SCENERY_PX css pixels: the static part once per place
// and size, the moving part a few times a second.
//
// Needs themes.js (PLACE_GROUP) loaded first.

(() => {
const SCENERY_PX = 4; // css pixels per scenery pixel
const SCENERY_TICK_MS = 200;
const CONTENT_W = 1060; // the page's widest column, in css pixels

// --- little painters ----------------------------------------------------------------

function sceneRand(seed) {
  let a = seed * 9301 + 49297;
  return () => {
    a = (a * 9301 + 49297) % 233280;
    return a / 233280;
  };
}

function mix(a, b, t) {
  const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
  const ch = (s) => Math.round(((pa >> s) & 255) * (1 - t) + ((pb >> s) & 255) * t);
  return `rgb(${ch(16)}, ${ch(8)}, ${ch(0)})`;
}

// An ellipse, filled row by row.
function blob(r, cx, cy, rx, ry, color) {
  for (let dy = -ry; dy <= ry; dy++) {
    const hw = Math.round(rx * Math.sqrt(Math.max(0, 1 - (dy / ry) ** 2)));
    r(cx - hw, cy + dy, hw * 2 + 1, 1, color);
  }
}

// Sky from `top` to `bottom` color in flat bands, the way pixel skies go.
function skyBands(r, W, h, top, bottom, bands = 9) {
  const step = Math.ceil(h / bands);
  for (let i = 0; i < bands; i++) r(0, i * step, W, step + 1, mix(top, bottom, i / (bands - 1)));
}

function cloud(r, x, y, s, color, shade) {
  blob(r, x + 6 * s, y + 4 * s, 6 * s, 3 * s, color);
  blob(r, x + 12 * s, y + 3 * s, 5 * s, 3 * s, color);
  blob(r, x + 9 * s, y + 1 * s, 4 * s, 2 * s, color);
  r(x + 2 * s, y + 6 * s, 15 * s, 1, shade);
}

function sun(r, x, y, color, glow) {
  blob(r, x, y, 9, 9, glow);
  blob(r, x, y, 6, 6, color);
  r(x - 3, y - 4, 2, 2, "#ffffff");
}

function moon(r, x, y) {
  blob(r, x, y, 6, 6, "#f4ecc8");
  r(x - 2, y - 1, 2, 2, "#d8cfa8");
  r(x + 1, y + 2, 3, 2, "#d8cfa8");
}

function stars(r, W, h, rand, count, colors = ["#fff6d8"]) {
  for (let i = 0; i < count; i++) {
    const x = Math.floor(rand() * W), y = Math.floor(rand() * h);
    const c = colors[i % colors.length];
    if (i % 5 === 0) {
      r(x - 1, y, 3, 1, c);
      r(x, y - 1, 1, 3, c);
    } else r(x, y, 1, 1, c);
  }
}

// A rolling silhouette: hills (smooth) or mountains (peaks, snow on top).
function hills(r, W, base, amp, color, phase = 0, freq = 0.035) {
  for (let x = 0; x < W; x++) {
    const h = amp * (0.55 + 0.25 * Math.sin(x * freq + phase) + 0.2 * Math.sin(x * freq * 2.3 + phase * 1.7));
    r(x, Math.round(base - h), 1, Math.ceil(h) + 1, color);
  }
}

function mountains(r, W, base, peaks, color, light, snow) {
  for (const [px, ph, pw] of peaks) {
    for (let i = -pw; i <= pw; i++) {
      const x = Math.round(px * W + i);
      const h = Math.round(ph * (1 - Math.abs(i) / pw));
      r(x, base - h, 1, h + 1, i < 0 ? light : color);
      if (snow && h > ph * 0.72) r(x, base - h, 1, Math.ceil((h - ph * 0.72) * 1.2) + 1, snow);
    }
  }
}

// --- the ground --------------------------------------------------------------------------

function groundBand(r, W, top, H, fill, edge, dark) {
  r(0, top, W, H - top, fill);
  r(0, top, W, 2, edge);
  for (let y = top + 6; y < H; y += 7) r(0, y, W, 1, dark); // soft layers going back
}

function grassTufts(r, W, top, H, rand, color, flowers = []) {
  for (let i = 0; i < W / 3; i++) {
    const x = Math.floor(rand() * W), y = top + 2 + Math.floor(rand() * (H - top - 3));
    r(x, y - 2, 1, 2, color);
    r(x + 2, y - 1, 1, 1, color);
    if (flowers.length && i % 4 === 0) {
      const c = flowers[i % flowers.length];
      r(x + 4, y - 2, 1, 1, c);
      r(x + 3, y - 1, 3, 1, c);
      r(x + 4, y, 1, 1, c);
      r(x + 4, y - 1, 1, 1, "#f6d465");
    }
  }
  for (let x = 0; x < W; x += 2) if (rand() < 0.5) r(x, top - 1, 1, 1, color); // blades along the edge
}

function speckles(r, W, top, H, rand, colors, n = W / 2, w = 1, h = 1) {
  for (let i = 0; i < n; i++) r(Math.floor(rand() * W), top + 2 + Math.floor(rand() * (H - top - 2)), w, h, colors[i % colors.length]);
}

function ripples(r, W, top, H, rand, color) {
  for (let y = top + 4; y < H; y += 5) {
    for (let x = Math.floor(rand() * 9); x < W; x += 14 + Math.floor(rand() * 8)) r(x, y, 5 + Math.floor(rand() * 4), 1, color);
  }
}

// --- things down the sides ------------------------------------------------------------------

function roundTree(r, x, base, h, crown, light, dark, trunk = "#6b4423") {
  const cr = Math.round(h * 0.34);
  r(x - 2, base - h * 0.5, 5, h * 0.5, trunk);
  r(x + 1, base - h * 0.5, 1, h * 0.5, "rgba(0, 0, 0, 0.2)");
  blob(r, x, base - h + cr, cr + 1, cr, dark);
  blob(r, x - 1, base - h + cr - 1, cr, cr - 1, crown);
  blob(r, x - cr * 0.4, base - h + cr * 0.6, cr * 0.45, cr * 0.35, light);
  return cr;
}

function dotsOn(r, x, base, h, rand, colors, n = 10) {
  const cr = Math.round(h * 0.34);
  for (let i = 0; i < n; i++) {
    const a = rand() * Math.PI * 2, d = rand() * (cr - 2);
    r(Math.round(x + Math.cos(a) * d), Math.round(base - h + cr + Math.sin(a) * d * 0.9), 2, 2, colors[i % colors.length]);
  }
}

function pine(r, x, base, h, green, dark, snow = null, trunk = "#5c3a1a") {
  r(x - 1, base - 6, 3, 6, trunk);
  const tiers = 4;
  for (let t = 0; t < tiers; t++) {
    const tb = base - 4 - t * (h - 6) / tiers;
    const tw = Math.round((h * 0.32) * (1 - t * 0.18));
    for (let i = 0; i < tw; i++) {
      r(x - tw + i, tb - i * 0.9, 1, i * 0.9 + 2, i % 3 ? green : dark);
      r(x + tw - i, tb - i * 0.9, 1, i * 0.9 + 2, dark);
    }
    if (snow) r(x - Math.round(tw * 0.5), tb - tw * 0.9 + 1, tw + 1, 2, snow);
  }
  r(x, base - h, 1, 3, green);
}

function palm(r, x, base, h, lean, t = 0) {
  for (let i = 0; i < h; i++) {
    const tx = x + Math.round(lean * (i / h) ** 2);
    r(tx - 1, base - i, 3, 1, i % 4 === 0 ? "#8a6a3a" : "#a8834a");
  }
  const top = [x + lean, base - h];
  const sway = Math.round(Math.sin(t) * 1);
  for (const [dx, dy] of [[-11, 3], [-8, 6], [11, 3], [8, 6], [-4, 7], [4, 7]]) {
    const n = Math.abs(dx) + 2;
    for (let i = 0; i <= n; i++) {
      const fx = top[0] + Math.round((dx * i) / n), fy = top[1] + Math.round((dy * i * i) / (n * n)) + (i > n / 2 ? sway : 0);
      r(fx, fy, 2, 2, i % 2 ? "#3f8a3a" : "#5aa845");
    }
  }
  r(top[0] - 2, top[1] + 1, 2, 2, "#6b4a2a"); // coconuts
  r(top[0] + 1, top[1] + 2, 2, 2, "#6b4a2a");
}

function cactus(r, x, base, h) {
  r(x - 2, base - h, 5, h, "#4f8a3a");
  r(x - 1, base - h - 1, 3, 1, "#4f8a3a");
  r(x + 1, base - h, 1, h, "#6aa84f");
  r(x - 7, base - h * 0.6, 5, 3, "#4f8a3a"); // arms
  r(x - 7, base - h * 0.85, 3, h * 0.25 + 1, "#4f8a3a");
  r(x + 3, base - h * 0.45, 5, 3, "#4f8a3a");
  r(x + 6, base - h * 0.75, 3, h * 0.3 + 1, "#4f8a3a");
  r(x, base - h - 2, 1, 1, "#f08ab0"); // a flower
  for (let y = base - h + 3; y < base; y += 4) r(x - 3, y, 1, 1, "#e8e0b0");
}

function kelp(r, x, base, h, t, color, dark) {
  for (let i = 0; i < h; i++) {
    const sx = x + Math.round(Math.sin(i * 0.18 + t) * 2);
    r(sx, base - i, 2, 1, i % 6 < 3 ? color : dark);
    if (i % 7 === 3) r(sx + (i % 14 < 7 ? 2 : -2), base - i, 2, 2, color);
  }
}

function coral(r, x, base, color) {
  r(x, base - 8, 2, 8, color);
  r(x - 3, base - 6, 3, 2, color);
  r(x - 3, base - 10, 2, 4, color);
  r(x + 2, base - 5, 3, 2, color);
  r(x + 4, base - 9, 2, 4, color);
}

function reeds(r, x, base, rand, color, head = "#6b4423") {
  for (let i = 0; i < 6; i++) {
    const rx = x + i * 2 + Math.floor(rand() * 2), h = 10 + Math.floor(rand() * 10);
    r(rx, base - h, 1, h, color);
    if (i % 2 === 0) r(rx, base - h - 2, 1, 4, head);
  }
}

function rock(r, x, base, w, h, color, light) {
  blob(r, x + w / 2, base - h / 2, w / 2, h / 2, color);
  r(x + w * 0.25, base - h + 1, w * 0.3, 1, light);
  r(x, base, w, 1, "rgba(0, 0, 0, 0.2)");
}

function willow(r, x, base, h, rand) {
  r(x - 2, base - h * 0.55, 4, h * 0.55, "#6b4a2a");
  blob(r, x, base - h * 0.75, h * 0.3, h * 0.22, "#6a9a4a");
  for (let i = -h * 0.32; i < h * 0.32; i += 2) {
    const len = h * 0.3 + rand() * h * 0.2;
    r(x + i, base - h * 0.75, 1, len, i % 4 ? "#7aae55" : "#5a8a3a");
  }
}

function mossyTree(r, x, base, h, rand) {
  r(x - 3, base - h, 6, h, "#5a4a32");
  r(x - 6, base - 3, 12, 3, "#5a4a32"); // roots
  blob(r, x, base - h, h * 0.35, h * 0.16, "#5a6e3a");
  for (let i = -h * 0.3; i < h * 0.3; i += 3) r(x + i, base - h + 2, 1, 5 + rand() * 10, "#8aa070"); // hanging moss
}

function planet(r, x, y, rad, color, light, ring) {
  blob(r, x, y, rad, rad, color);
  blob(r, x - rad * 0.3, y - rad * 0.3, rad * 0.4, rad * 0.35, light);
  if (ring) {
    for (let i = -rad - 5; i <= rad + 5; i++) r(x + i, y + Math.round(i * 0.25), 1, 1, ring);
  }
}

function crater(r, x, y, w, color, light) {
  blob(r, x, y, w, Math.max(1, Math.round(w * 0.35)), color);
  r(x - w + 1, y - 1, w * 2 - 2, 1, light);
}

// --- more things: forests ---------------------------------------------------------------

// A short wooden fence running in from the edge.
function fence(r, x0, d, len, y) {
  for (let i = 0; i <= len; i += 7) r(x0 + d * i - 1, y - 8, 2, 9, "#a87a44");
  r(Math.min(x0, x0 + d * len), y - 6, len, 1, "#c89a60");
  r(Math.min(x0, x0 + d * len), y - 3, len, 1, "#c89a60");
}

// A redwood: a huge red-brown trunk from the ground off the top of the
// screen, furrowed bark, a flared foot, and a few branch stubs.
function redwood(r, x, w, base, bark, dark, light) {
  r(x, 0, w, base, bark);
  for (let i = 2; i < w - 1; i += 3) r(x + i, 0, 1, base, dark); // furrows
  r(x + 1, 0, 1, base, light);
  for (let i = 0; i < 5; i++) r(x - i, base - 5 + i, w + i * 2, 1, i % 2 ? dark : bark); // its flared foot
  for (let y = 30; y < base * 0.55; y += 23) r(x + (y % 2 ? -4 : w), y, 4, 2, dark); // branch stubs
}

function fern(r, x, base, k, color) {
  for (let i = -3; i <= 3; i++) {
    const len = (5 - Math.abs(i)) * k;
    for (let j = 0; j < len; j++) r(x + i * j * 0.6, base - j * 0.8, 1, 1, color);
  }
}

// A cherry tree: a bent trunk, branches spreading wide, and flat clouds of
// blossom along them (wider than tall, the way cherry trees go).
function cherryTree(r, x, base, h, d, rand) {
  const k = h / 50;
  const trunk = "#5c3a2a";
  for (let i = 0; i < h * 0.5; i++) r(x + Math.round(Math.sin(i / 9) * 2 * k) * d, base - i, 4 * k, 1, trunk);
  const top = [x + Math.round(Math.sin((h * 0.5) / 9) * 2 * k) * d, base - h * 0.5];
  const ends = [[d * 22, -14], [d * 10, -24], [-d * 12, -18], [d * 30, -4]].map(([dx, dy]) => [top[0] + dx * k, top[1] + dy * k]);
  for (const [ex, ey] of ends) {
    const n = Math.ceil(Math.hypot(ex - top[0], ey - top[1]));
    for (let i = 0; i <= n; i++) r(top[0] + ((ex - top[0]) * i) / n, top[1] + ((ey - top[1]) * i) / n, 2 * k, 2 * k, trunk);
  }
  for (const [ex, ey] of ends) {
    blob(r, ex, ey + 2 * k, 11 * k, 5 * k, "#d880a0"); // the blossom's shade
    blob(r, ex, ey, 11 * k, 5 * k, "#f2a6c0");
    blob(r, ex - 3 * k, ey - 2 * k, 6 * k, 3 * k, "#fbd0de");
    for (let i = 0; i < 6; i++) r(ex + (rand() - 0.5) * 18 * k, ey + (rand() - 0.5) * 8 * k, 1, 1, "#ffffff");
  }
}

function stoneLantern(r, x, base, k) {
  r(x - 2 * k, base - 4 * k, 5 * k, 4 * k, "#9a948a");
  r(x - 1 * k, base - 9 * k, 3 * k, 5 * k, "#b0aaa0");
  r(x - 3 * k, base - 11 * k, 7 * k, 2 * k, "#9a948a");
  r(x - 1 * k, base - 10 * k, 3 * k, 1 * k, "#f6d465");
  r(x - 4 * k, base - 13 * k, 9 * k, 2 * k, "#8a847a");
}

function roseBush(r, x, base, w, k, rand, colors) {
  blob(r, x, base - w * 0.4, w, w * 0.45, "#2f6a32");
  blob(r, x - w * 0.3, base - w * 0.55, w * 0.5, w * 0.3, "#3f7a3a");
  for (let i = 0; i < w * 0.8; i++) {
    const fx = x + (rand() - 0.5) * w * 1.6, fy = base - w * 0.4 + (rand() - 0.5) * w * 0.7;
    const c = colors[i % colors.length];
    r(fx, fy, 2 * k, 2 * k, c);
    r(fx + k * 0.5, fy + k * 0.5, k, k, "rgba(0, 0, 0, 0.2)"); // the rose's swirl
  }
}

function sunflower(r, x, base, h, k) {
  r(x, base - h, 1 * k, h, "#4f8a3a");
  r(x - 3 * k, base - h * 0.5, 3 * k, 2 * k, "#5aa845");
  blob(r, x, base - h, 4 * k, 4 * k, "#f6c430");
  blob(r, x, base - h, 2 * k, 2 * k, "#7a4a2a");
}

function tulip(r, x, base, h, k, color) {
  r(x, base - h, 1 * k, h, "#4f8a3a");
  r(x - 1.5 * k, base - h - 4 * k, 4 * k, 4 * k, color);
  r(x - 1.5 * k, base - h - 5 * k, 1 * k, 1 * k, color);
  r(x + 1.5 * k, base - h - 5 * k, 1 * k, 1 * k, color);
}

function foxglove(r, x, base, h, k, color) {
  r(x, base - h, 1 * k, h, "#4f8a3a");
  for (let y = base - h; y < base - h * 0.4; y += 2.5 * k) r(x - 1 * k, y, 3 * k, 2 * k, color);
}

// Flowering vines hanging from the top of the screen.
function hangingVines(r, x0, d, n, len, k, colors, t = 0) {
  for (let i = 0; i < n; i++) {
    const vx = x0 + d * (2 + i * 7) * k;
    const vl = len * (0.5 + ((i * 37) % 10) / 20);
    for (let y = 0; y < vl; y++) {
      const sx = vx + Math.round(Math.sin(y * 0.15 + t + i) * 1.2);
      r(sx, y, 1, 1, "#3f7a3a");
      if (y % 4 === 2) r(sx - 1, y, 3 * k * 0.6, 2 * k * 0.6, colors[(i + y) % colors.length]);
    }
  }
}

// --- jungle -------------------------------------------------------------------------------

function leafMass(r, W, top, bottom, rand, colors, n, size) {
  for (let i = 0; i < n; i++) {
    const x = rand() * W, y = top + rand() * (bottom - top);
    blob(r, x, y, size * (0.6 + rand() * 0.8), size * (0.4 + rand() * 0.5), colors[i % colors.length]);
  }
}

function bigLeaf(r, x, y, len, d, k, color, vein) {
  for (let i = 0; i < len; i++) {
    const wd = Math.round(Math.sin((i / len) * Math.PI) * 5 * k);
    r(x + d * i, y - wd + i * 0.3, 1, wd * 2 + 1, color);
    if (i % 4 === 2) r(x + d * i, y + i * 0.3 - wd, 1, wd * 0.6, "rgba(0, 0, 0, 0.15)"); // splits in the leaf
  }
  for (let i = 0; i < len; i++) r(x + d * i, y + i * 0.3, 1, 1, vein);
}

// --- wild places -------------------------------------------------------------------------

// A mushroom made of blocks: a square stem, a wide flat cap with a stepped
// underside, square spots.
function blockMushroom(r, x, base, w, h, cap, spot, stem = "#f4ead2") {
  const sw = Math.max(3, Math.round(w * 0.32));
  r(x - sw / 2, base - h, sw, h, stem);
  r(x + sw / 2 - 1, base - h, 1, h, "#d8c7a0");
  const ch = Math.max(4, Math.round(w * 0.42));
  r(x - w / 2, base - h - ch, w, ch, cap);
  r(x - w / 2 + 2, base - h - ch - 2, w - 4, 2, cap);
  r(x - w / 2 + 1, base - h, w - 2, 1, "rgba(0, 0, 0, 0.25)"); // the gills' shadow
  r(x - w / 2 + 3, base - h + 1, w - 6, 1, "rgba(0, 0, 0, 0.15)");
  if (spot) {
    for (const [fx, fy] of [[0.15, 0.25], [0.55, 0.15], [0.35, 0.6], [0.75, 0.55]]) r(x - w / 2 + fx * w, base - h - ch + fy * ch, Math.max(2, w * 0.12), Math.max(2, w * 0.12), spot);
  }
}

function iceShard(r, x, base, h, w) {
  for (let i = 0; i < h; i++) {
    const half = Math.round(w * (1 - i / h) * 0.5);
    r(x - half, base - i, half, 1, "#bfe6f4");
    r(x, base - i, half + 1, 1, "#e8f6fc");
  }
  r(x, base - h, 1, h * 0.6, "#ffffff");
}

function iceberg(r, x, base, w, h) {
  for (let i = 0; i < h; i++) {
    const half = Math.round((w / 2) * (0.5 + 0.5 * (1 - i / h)) + Math.sin(i * 0.7) * 2);
    r(x - half, base - i, half * 2, 1, i % 5 === 0 ? "#cfe8f4" : "#e8f6fc");
  }
  r(x - w / 2, base, w, 2, "#7ab8d8"); // the waterline
}

// A butte: a flat-topped tower of banded rock over a slope of rubble.
function butte(r, x, base, w, h, bands) {
  for (let i = 0; i < h * 0.3; i++) r(x - w * 0.5 - (h * 0.3 - i) * 0.9, base - i, w + (h * 0.3 - i) * 1.8, 1, mix(bands[0], "#000000", 0.1));
  for (let y = 0; y < h; y++) r(x - w / 2 + (y < 3 ? 2 - y : 0), base - h + y, w - (y < 3 ? (2 - y) * 2 : 0), 1, bands[Math.floor(y / 5) % bands.length]);
  r(x + w / 2 - 3, base - h + 2, 3, h * 0.7, "rgba(0, 0, 0, 0.18)"); // the shady side
}

function rockArch(r, x, base, w, h, color, dark) {
  const leg = Math.max(4, Math.round(w * 0.18));
  r(x - w / 2, base - h, leg, h, color);
  r(x + w / 2 - leg, base - h, leg, h, dark);
  for (let i = 0; i < w; i++) {
    const lift = Math.round(Math.sin((i / w) * Math.PI) * h * 0.25);
    r(x - w / 2 + i, base - h - lift, 1, leg + 2, i < w / 2 ? color : dark);
  }
  r(x - w / 2 - 3, base, w + 6, 2, dark);
}

function juniper(r, x, base, k) {
  blob(r, x, base - 2 * k, 4 * k, 2.5 * k, "#4a6a3a");
  r(x, base - 1, 1, 2, "#5c3a1a");
}

// --- space and Mars -----------------------------------------------------------------------

function nebula(r, x, y, rx, ry, color) {
  blob(r, x, y, rx, ry, color);
  blob(r, x + rx * 0.4, y - ry * 0.3, rx * 0.6, ry * 0.6, color);
}

function satellite(r, x, y) {
  r(x - 7, y - 1, 5, 3, "#4a7ec8"); // solar panels
  r(x + 3, y - 1, 5, 3, "#4a7ec8");
  r(x - 7, y, 5, 1, "#6aa0e8");
  r(x + 3, y, 5, 1, "#6aa0e8");
  r(x - 2, y - 2, 5, 5, "#d0d0d8");
  r(x - 1, y - 1, 2, 2, "#f6d465");
  r(x + 1, y - 4, 1, 2, "#9a9aa4");
}

// A little six-wheeled rover with a camera mast and a solar deck.
function rover(r, x, base, k) {
  r(x - 9 * k, base - 8 * k, 18 * k, 2 * k, "#4a6aa0"); // solar deck
  r(x - 7 * k, base - 6 * k, 14 * k, 3 * k, "#e8e0d0"); // body
  r(x + 4 * k, base - 14 * k, 1 * k, 6 * k, "#b0aaa0"); // mast
  r(x + 3 * k, base - 16 * k, 4 * k, 2 * k, "#e8e0d0"); // camera head
  r(x + 6 * k, base - 16 * k, 1 * k, 1 * k, "#3b2417");
  for (const wx of [-7, -1, 5]) {
    r(x + wx * k, base - 3 * k, 3 * k, 3 * k, "#3a3640");
    r(x + (wx + 1) * k, base - 2 * k, 1 * k, 1 * k, "#7a7a84");
  }
  r(x - 7 * k, base - 3.5 * k, 15 * k, 0.6 * k, "#7a7a84");
  for (let i = 1; i < 14; i += 2) r(x - 16 * k - i * k, base - 0.5 * k, 1 * k, 0.6 * k, "#8e3f22"); // tracks behind it
}

// --- each place ----------------------------------------------------------------------------
// sky: [top, bottom]; ground: [fill, edge, dark]; far(r, s): distant hills;
// side(r, s, edge, dir, rand): the things down one side (edge: that side's
// x, dir: 1 going in from the left, -1 from the right); floor(r, s, rand):
// the ground's texture; anim(r, s, t): what moves; near: a nearer, darker row
// of hills; fliers: "birds" or "fish" crossing the sky; full(r, s, rand): a
// place that isn't the same on both sides draws across the whole width
// instead; noGround: just sky (space); inkLight: the page's own words turn
// light (a dark scene); aurora: northern lights at night. s = {W, H, gt (where
// the ground starts), margin (the page's side margins), k (how big things down
// the sides are drawn)}.

const SCENES = {
  bg_meadow: {
    near: "#8cbf5e", fliers: "birds",
    sky: ["#8cc8e8", "#e2f2ec"], sun: true, clouds: true,
    ground: ["#7fa346", "#94b85a", "#6e9240"],
    far: (r, s) => hills(r, s.W, s.gt, 18, "#a8cf7a", 1),
    // lots of little trees, a fence, bushes
    side(r, s, e, d) {
      const k = s.k;
      fence(r, e, d, 52 * k, s.gt + 5 * k);
      [[5, 26, 2], [15, 18, 7], [25, 22, 3], [35, 16, 8], [45, 20, 4]].forEach(([o, h, b], i) => {
        const greens = i % 2 ? ["#6aaa4f", "#8fcc66", "#4a8a3a"] : ["#5a9a45", "#7fbe5a", "#3f7a33"];
        roundTree(r, e + d * o * k, s.gt + b * k, h * k, ...greens);
      });
      blob(r, e + d * 20 * k, s.gt + 9 * k, 5 * k, 3 * k, "#4f8a3a");
      blob(r, e + d * 40 * k, s.gt + 10 * k, 4 * k, 3 * k, "#5a9a45");
    },
    floor: (r, s, rand) => grassTufts(r, s.W, s.gt, s.H, rand, "#5f8a34", ["#f6d465", "#ffffff", "#f6aacb"]),
  },
  bg_flower_forest: {
    near: "#9cca6e", fliers: "birds",
    sky: ["#9ad0ec", "#f0f4e4"], sun: true, clouds: true,
    ground: ["#86b44c", "#9cc85e", "#76a240"],
    far: (r, s) => hills(r, s.W, s.gt, 16, "#b4d888", 2.2),
    // a wisteria tree, rose bushes, sunflowers, tulips and foxgloves, and
    // flowering vines hanging down from the top
    side(r, s, e, d, rand) {
      const k = s.k;
      const wx = e + d * 12 * k, wb = s.gt + 3 * k;
      r(wx - 3 * k, wb - 34 * k, 6 * k, 34 * k, "#6b4423");
      blob(r, wx, wb - 40 * k, 18 * k, 10 * k, "#4f8a3a");
      blob(r, wx - 4 * k, wb - 43 * k, 12 * k, 6 * k, "#6aaa4f");
      for (let i = 0; i < 26; i++) {
        const hx = wx + (rand() - 0.5) * 34 * k, len = (5 + rand() * 10) * k;
        for (let y = 0; y < len; y += 1.5 * k) r(hx - (1 - y / len) * k, wb - 34 * k + y, (2 - y / len) * k, 1.2 * k, i % 3 ? "#b48ae6" : "#d8b8f4");
      }
      roseBush(r, e + d * 30 * k, s.gt + 8 * k, 9 * k, k, rand, ["#d8283a", "#f6aacb", "#ffffff", "#f6d465"]);
      roseBush(r, e + d * 6 * k, s.gt + 10 * k, 7 * k, k, rand, ["#e84a6a", "#ffffff"]);
      sunflower(r, e + d * 40 * k, s.gt + 6 * k, 24 * k, k);
      sunflower(r, e + d * 45 * k, s.gt + 8 * k, 18 * k, k);
      [["#e84a6a", 20], ["#f6d465", 23], ["#b48ae6", 26], ["#ff8a3a", 36]].forEach(([c, o]) => tulip(r, e + d * o * k, s.gt + 11 * k, 7 * k, k, c));
      foxglove(r, e + d * 2 * k, s.gt + 8 * k, 16 * k, k, "#d880c8");
      foxglove(r, e + d * 50 * k, s.gt + 9 * k, 13 * k, k, "#f6aacb");
      hangingVines(r, e, d, 5, s.gt * 0.35, k, ["#f6aacb", "#b48ae6", "#ffffff", "#f6d465"]);
    },
    floor: (r, s, rand) => {
      grassTufts(r, s.W, s.gt, s.H, rand, "#5f8a34", ["#f6aacb", "#ffffff", "#f6d465", "#b48ae6", "#e84a6a", "#ff8a3a"]);
      for (let i = 0; i < s.W / 4; i++) {
        const x = Math.floor(rand() * s.W), y = s.gt + 3 + Math.floor(rand() * (s.H - s.gt - 4));
        const c = ["#f6aacb", "#ffffff", "#f6d465", "#b48ae6", "#e84a6a", "#ff8a3a", "#6aa0e8"][i % 7];
        r(x, y, 3, 1, c); // bigger flowers all over
        r(x + 1, y - 1, 1, 3, c);
        r(x + 1, y, 1, 1, i % 2 ? "#f6d465" : "#7a4a2a");
      }
    },
  },
  bg_autumn_forest: {
    near: "#c07a44", fliers: "birds",
    sky: ["#f2b878", "#fbe8c8"], sun: true, clouds: true, cloudColor: ["#fff4e0", "#f0d8b8"],
    ground: ["#7a5a32", "#9a7442", "#6a4c2a"],
    far: (r, s) => hills(r, s.W, s.gt, 18, "#d8925a", 0.5),
    side(r, s, e, d) {
      roundTree(r, e + d * 10 * s.k, s.gt + 4 * s.k, 48 * s.k, "#d9822b", "#f0a858", "#b8582a");
      roundTree(r, e + d * 27 * s.k, s.gt + 8 * s.k, 36 * s.k, "#c8423a", "#e06a50", "#962a24");
      roundTree(r, e + d * 40 * s.k, s.gt + 10 * s.k, 26 * s.k, "#e8b33e", "#f6d465", "#c8902a");
    },
    floor: (r, s, rand) => speckles(r, s.W, s.gt, s.H, rand, ["#d9822b", "#c8423a", "#e8b33e", "#8a5a2c"], s.W / 1.5, 2, 1),
  },
  bg_pine_forest: {
    sky: ["#b4c8b0", "#e2e8d8"],
    ground: ["#4a5a32", "#5a6a3a", "#3e4c2a"],
    // a redwood grove: trunks at two depths fading into the mist, a dark
    // canopy closing over the top
    far(r, s) {
      const rand = sceneRand(17);
      for (const [color, edge, gap, wmin, wmax] of [["#c0b6a4", "#ccc2b0", 9, 2, 4], ["#a08a72", "#b09a80", 16, 4, 7]]) {
        for (let x = rand() * gap; x < s.W; x += gap * (0.6 + rand() * 0.9)) {
          const w = wmin + Math.floor(rand() * (wmax - wmin + 1));
          r(x, 0, w, s.gt, color);
          r(x, 0, 1, s.gt, edge);
        }
        r(0, s.gt * 0.55, s.W, s.gt * 0.45, "rgba(226, 232, 216, 0.25)"); // mist between the rows
      }
      for (let i = 0; i < s.W / 8; i++) blob(r, rand() * s.W, rand() * s.H * 0.08, 10 + rand() * 8, 4 + rand() * 4, i % 2 ? "#2f4a2a" : "#3a5a32");
      r(0, s.gt - 12, s.W, 12, "rgba(226, 232, 216, 0.5)"); // mist low down
    },
    side(r, s, e, d) {
      const k = s.k;
      [[34, 5, "#8a5a40", "#6e4430", "#a06a4a"], [20, 8, "#7a4a30", "#5e3420", "#9a5a3a"], [4, 14, "#8a4a2e", "#6a3420", "#a8603a"]].forEach(([o, w, bark, dark, light], i) => {
        const tw = w * k;
        redwood(r, d > 0 ? e + o * k : e - o * k - tw, tw, s.gt + (2 + i * 3) * k, bark, dark, light);
      });
      for (let i = 0; i < 8; i++) blob(r, e + d * i * 7 * k, 4 * k + (i % 3) * 4, 12 * k, 7 * k, i % 2 ? "#2f4a2a" : "#3a5a32"); // the canopy
      fern(r, e + d * 12 * k, s.gt + 10 * k, k, "#5a8a3a");
      fern(r, e + d * 30 * k, s.gt + 12 * k, k, "#4a7a32");
    },
    anim(r, s, t) {
      for (let i = 0; i < 4; i++) {
        const x = s.W * (0.15 + i * 0.22) + Math.sin(t * 0.3 + i) * 3;
        for (let y = 0; y < s.gt; y += 2) r(x + y * 0.35, y, 6, 2, "rgba(255, 250, 220, 0.07)"); // light through the trees
      }
    },
    floor: (r, s, rand) => {
      speckles(r, s.W, s.gt, s.H, rand, ["#7a5636", "#2f4a2a", "#6b8a4a", "#8a5a40"], s.W / 1.2, 2, 1);
      for (let i = 0; i < s.W / 40; i++) fern(r, Math.floor(rand() * s.W), s.gt + 6 + Math.floor(rand() * (s.H - s.gt - 8)), 1, "#5a8a3a");
    },
  },
  bg_cherry_grove: {
    near: "#a8d07a", fliers: "birds",
    sky: ["#f2c8d8", "#fdf0f2"], sun: true, clouds: true,
    ground: ["#9cc46a", "#b0d47e", "#8ab45a"],
    far: (r, s) => hills(r, s.W, s.gt, 16, "#c4e09a", 1.4),
    side(r, s, e, d, rand) {
      const k = s.k;
      cherryTree(r, e + d * 6 * k, s.gt + 4 * k, 56 * k, d, rand);
      cherryTree(r, e + d * 36 * k, s.gt + 8 * k, 34 * k, -d, rand);
      stoneLantern(r, e + d * 24 * k, s.gt + 10 * k, k);
    },
    floor: (r, s, rand) => {
      grassTufts(r, s.W, s.gt, s.H, rand, "#7fa84f");
      speckles(r, s.W, s.gt, s.H, rand, ["#f2a6c0", "#fbd0de", "#ffffff"], s.W / 1.5, 2, 1);
    },
  },
  bg_jungle: {
    sky: ["#2f5a2a", "#3a6a32"], inkLight: true,
    ground: ["#3e2a18", "#4f7a32", "#33220f"],
    // no sky: leaves from floor to roof, trunks all the way up, vines
    far(r, s) {
      const rand = sceneRand(41);
      leafMass(r, s.W, 0, s.gt, rand, ["#2a4e26", "#34602e", "#3e6a32"], s.W * 0.6, 9);
      for (let x = 8; x < s.W; x += 27) r(x, 0, 4 + (x % 3), s.gt, "#4a3a28"); // trunks far back
      leafMass(r, s.W, 0, s.gt, rand, ["#4a7a38", "#5a8a3e", "#3f6a32"], s.W * 0.35, 6);
      for (let i = 0; i < s.W * 0.4; i++) r(rand() * s.W, rand() * s.gt, 1, 1, "#c8e07a"); // sun flecks
      leafMass(r, s.W, 0, s.H * 0.1, rand, ["#1f3a1c", "#2a4a24"], s.W * 0.25, 10); // the canopy
    },
    side(r, s, e, d, rand) {
      const k = s.k;
      for (const [o, w] of [[16, 6], [3, 11]]) {
        const tw = w * k, tx = d > 0 ? e + o * k : e - o * k - tw;
        r(tx, 0, tw, s.gt + 4 * k, "#5a4630");
        r(tx + 1, 0, 1, s.gt + 4 * k, "#6e5a3e");
        for (let y = 0; y < s.gt; y += 6 * k) r(tx, y, tw, 2 * k, "#3f7a32"); // vines wrapped round
      }
      for (let i = 0; i < 5; i++) bigLeaf(r, e + d * (2 + i * 6) * k, s.gt - (i % 2 ? 4 : 12) * k, 16 * k, d, k, i % 2 ? "#3f8a3a" : "#5aa845", "#2a5a24");
      bigLeaf(r, e + d * 8 * k, s.gt * 0.55, 14 * k, d, k, "#4f9a3a", "#2a5a24");
    },
    anim(r, s, t) {
      for (const [e, d] of [[0, 1], [s.W, -1]]) {
        for (let i = 0; i < 7; i++) {
          const vx = e + d * (4 + i * 7) * s.k, len = s.gt * (0.3 + ((i * 13) % 10) / 20);
          for (let y = 0; y < len; y++) r(vx + Math.round(Math.sin(y * 0.15 + t + i) * 1.5), y, 1, 1, y % 5 ? "#3f8a3a" : "#7fbe5a");
          r(vx - 1, len, 3, 2, "#5aa845");
        }
      }
    },
    floor: (r, s, rand) => {
      speckles(r, s.W, s.gt + 2, s.H, rand, ["#5aa845", "#3f8a3a", "#6b4a2a", "#8a5a2c"], s.W / 1.5, 2, 2);
      for (let i = 0; i < s.W / 18; i++) fern(r, Math.floor(rand() * s.W), s.gt + 4 + Math.floor(rand() * (s.H - s.gt - 6)), 1.2, "#4f9a3a");
    },
  },
  bg_beach: {
    fliers: "birds",
    sky: ["#7cc4e8", "#e2f4fa"], sun: true, clouds: true,
    ground: ["#ecd49c", "#fbf1dc", "#e0c48a"],
    far(r, s) {
      r(0, s.gt - 12, s.W, 12, "#4aa0d0"); // the sea
      r(0, s.gt - 12, s.W, 2, "#3a88b8");
      r(0, s.gt - 2, s.W, 2, "#fbf1dc"); // surf
    },
    side(r, s, e, d) {
      palm(r, e + d * 10 * s.k, s.gt + 6 * s.k, 50 * s.k, d * 10);
      palm(r, e + d * 28 * s.k, s.gt + 10 * s.k, 36 * s.k, d * 6);
    },
    anim(r, s, t) {
      for (let x = Math.floor(t * 3) % 16; x < s.W; x += 16) r(x, s.gt - 8 + ((x / 16) % 3) * 2, 4, 1, "#bfe6f8"); // sparkles on the sea
    },
    floor(r, s, rand) {
      ripples(r, s.W, s.gt, s.H, rand, "#e0c48a");
      for (let i = 0; i < s.W / 30; i++) {
        const x = Math.floor(rand() * s.W), y = s.gt + 6 + Math.floor(rand() * (s.H - s.gt - 8));
        if (i % 2) r(x, y, 3, 2, "#f6aacb"); // shells
        else {
          r(x + 1, y, 1, 3, "#e8823a"); // a starfish
          r(x, y + 1, 3, 1, "#e8823a");
        }
      }
    },
  },
  bg_river: {
    near: "#8cbf5e", fliers: "birds",
    sky: ["#9ad0ec", "#eef6f0"], sun: true, clouds: true,
    ground: ["#7fa346", "#94b85a", "#6e9240"],
    far: (r, s) => hills(r, s.W, s.gt, 16, "#a8cf7a", 3),
    side(r, s, e, d, rand) {
      willow(r, e + d * 12 * s.k, s.gt + 4 * s.k, 48 * s.k, rand);
      reeds(r, e + d * (d > 0 ? 28 : 40), s.gt + 6 * s.k, rand, "#5f8a34");
    },
    anim(r, s, t) {
      const y = s.gt + Math.round((s.H - s.gt) * 0.45);
      r(0, y, s.W, 7, "#5aa8d0"); // the river
      r(0, y, s.W, 1, "#a8dcf0");
      for (let x = Math.floor(t * 4) % 12; x < s.W; x += 12) r(x, y + 3, 4, 1, "#a8dcf0");
      for (let x = 30; x < s.W; x += 70) rock(r, x, y + 5, 6, 3, "#9a948a", "#b8b2a8"); // stepping stones
    },
    floor: (r, s, rand) => grassTufts(r, s.W, s.gt, s.H, rand, "#5f8a34", ["#ffffff", "#f6d465"]),
  },
  bg_waterfall: {
    fliers: "birds",
    sky: ["#94c8e2", "#e8f4f0"], clouds: true,
    ground: ["#5a8a3a", "#6aa845", "#4a7a32"],
    far: (r, s) => mountains(r, s.W, s.gt, [[0.62, 30, 36], [0.86, 42, 40]], "#8aa0a8", "#a0b4bc", "#eef4f6"),
    // one tall cliff on the left with a waterfall pouring off it into a
    // river that rushes away to the right; a rocky bank and pines across it
    full(r, s, rand) {
      const k = s.k;
      const { cw, top } = fallsAt(s);
      for (let y = top; y < s.gt + 8; y++) {
        const w = cw + Math.round((y - top) * 0.1 + Math.sin(y * 0.3) * 1.5);
        r(0, y, w, 1, (y - top) % 9 === 0 ? "#5a564e" : "#7a7468");
      }
      for (let i = 0; i < (cw * (s.gt - top)) / 60; i++) r(rand() * cw * 0.95, top + rand() * (s.gt - top), 3, 1, "#948e80");
      for (let y = top + 10; y < s.gt; y += 14) r(0, y, cw * (0.5 + ((y * 7) % 5) / 10), 2, "#5aa845"); // mossy ledges
      r(0, top - 2, cw + 2, 3, "#5aa845");
      pine(r, cw * 0.3, top + 1, 26 * k, "#3f6a3a", "#2a4a2a");
      pine(r, cw * 0.7, top + 1, 18 * k, "#4a7a42", "#2f5a2f");
      // a rainbow in the spray
      ["#e84a4a", "#f0a040", "#f6e27a", "#6ac86a", "#6aa0e8", "#9a6ad8"].forEach((c, i) => {
        const rad = (30 - i) * k;
        for (let a = Math.PI; a < Math.PI * 1.55; a += 0.02) r(cw + 8 * k + Math.cos(a) * -rad, s.gt + Math.sin(a) * rad, 1, 1, c + "66");
      });
      rock(r, s.W - 34 * k, s.gt + 9 * k, 18 * k, 9 * k, "#7a7468", "#948e80");
      rock(r, s.W - 14 * k, s.gt + 11 * k, 10 * k, 6 * k, "#68625a", "#948e80");
      pine(r, s.W - 10 * k, s.gt + 4 * k, 54 * k, "#3f6a3a", "#2a4a2a");
      pine(r, s.W - 26 * k, s.gt + 2 * k, 38 * k, "#4a7a42", "#2f5a2f");
    },
    anim(r, s, t) {
      const k = s.k;
      const { cw, top } = fallsAt(s);
      const fw = 12 * k;
      for (let y = top; y < s.gt + 6; y++) {
        const spread = (y - top) * 0.04;
        r(cw - 1, y, fw + spread, 1, "#a8dcf0");
        r(cw - 1 + ((y * 3 + Math.floor(t * 12)) % Math.max(2, fw)), y, 2, 1, "#ffffff"); // falling streaks
        r(cw - 1 + ((y * 7 + Math.floor(t * 9)) % Math.max(2, fw)), y, 1, 1, "#e8f6fc");
      }
      // the river: from the pool at the foot of the falls, widening off to the right
      for (let y = s.gt + 3; y < s.H; y++) {
        const f = (y - s.gt) / (s.H - s.gt);
        const x0 = cw - 4 + f * (s.W - cw) * 0.5, w = (16 + f * 50) * k;
        r(x0, y, w, 1, y % 3 ? "#5aa8d0" : "#4a98c0");
        r(x0 + ((y * 11 + Math.floor(t * 20)) % Math.max(4, w)), y, 4, 1, "#e8f6fc"); // rapids
      }
      for (let i = 0; i < 5; i++) blob(r, cw + fw / 2 + Math.sin(t * 2 + i) * 4, s.gt + 2 - i * 2, (7 - i) * k, 2 * k, "rgba(240, 250, 255, 0.55)"); // spray
    },
    floor: (r, s, rand) => grassTufts(r, s.W, s.gt, s.H, rand, "#4a7a32", ["#ffffff", "#f6d465"]),
  },
  bg_under_sea: {
    fliers: "fish",
    sky: ["#5aa8d0", "#bfe6f0"],
    ground: ["#e0c890", "#f0d79c", "#d0b880"],
    far: (r, s) => hills(r, s.W, s.gt, 14, "#7ab8c8", 2, 0.03),
    side(r, s, e, d) {
      coral(r, e + d * 16 * s.k, s.gt + 4 * s.k, "#f08068");
      coral(r, e + d * 32 * s.k, s.gt + 6 * s.k, "#f0a8c8");
      rock(r, e + d * 24 * s.k - 5, s.gt + 6 * s.k, 12 * s.k, 6 * s.k, "#8a8a94", "#a8a8b0");
    },
    anim(r, s, t) {
      for (let i = 0; i < 6; i++) r(20 + i * (s.W / 6), 0, 3, s.gt * 0.7, "rgba(255, 255, 255, 0.08)"); // light from above
      for (const [e, d] of [[0, 1], [s.W, -1]]) {
        kelp(r, e + d * 4, s.gt + 4, s.gt * 0.75, t, "#4f9a5a", "#3f7a4a");
        kelp(r, e + d * 10, s.gt + 6, s.gt * 0.55, t + 1, "#5aa86a", "#3f7a4a");
      }
    },
    floor(r, s, rand) {
      ripples(r, s.W, s.gt, s.H, rand, "#d0b880");
      speckles(r, s.W, s.gt, s.H, rand, ["#f6aacb", "#ffffff"], s.W / 25, 2, 2);
    },
  },
  bg_swamp: {
    near: "#6e7e58",
    sky: ["#b8c8a0", "#e6ead6"], clouds: true, cloudColor: ["#eef0e2", "#d4d8c4"],
    ground: ["#5a5236", "#6a6240", "#4a442c"],
    far(r, s) {
      hills(r, s.W, s.gt, 14, "#8a9a72", 1.1);
      for (let x = 6; x < s.W; x += 19) { // a hazy row of trees far back
        const h = 18 + ((x * 13) % 14);
        r(x, s.gt - h, 2, h, "#9aa888");
        blob(r, x + 1, s.gt - h, 6, 3, "#a4b294");
      }
    },
    side(r, s, e, d, rand) {
      const k = s.k;
      [[8, 54], [20, 38], [31, 46], [43, 26]].forEach(([o, h], i) => mossyTree(r, e + d * o * k, s.gt + (3 + i * 2) * k, h * k, rand));
      reeds(r, e + d * (d > 0 ? 24 : 36) * k, s.gt + 10 * k, rand, "#6a7a3a", "#5c3a1a");
      reeds(r, e + d * (d > 0 ? 48 : 60) * k, s.gt + 12 * k, rand, "#7a8a4a", "#5c3a1a");
    },
    anim(r, s, t) {
      const y = s.gt + 6;
      r(0, y, s.W, 8, "#4f6a4a"); // murky water
      r(0, y, s.W, 1, "#6a8a5a");
      for (let x = 14; x < s.W; x += 37) {
        blob(r, x, y + 3, 3, 1, "#6aaa4f"); // lily pads
        if (x % 3 === 0) r(x, y + 2, 1, 1, "#f6aacb");
      }
      for (let i = 0; i < 3; i++) r(((t * (2 + i)) % (s.W + 80)) - 80 + i * 40, s.gt - 6 + i * 5, 80, 3, "rgba(240, 244, 230, 0.35)"); // fog drifting
    },
    floor: (r, s, rand) => speckles(r, s.W, s.gt + 14, s.H, rand, ["#6a7a3a", "#4a442c"], s.W / 2, 2, 1),
  },
  bg_desert: {
    near: "#e8b060",
    sky: ["#88c4e4", "#f8ead0"], sun: true, sunColor: ["#fff4c0", "rgba(255, 240, 180, 0.5)"],
    ground: ["#e8b868", "#f0c880", "#d8a458"],
    far: (r, s) => hills(r, s.W, s.gt, 14, "#f0c878", 0.6, 0.025),
    side(r, s, e, d) {
      cactus(r, e + d * 12 * s.k, s.gt + 4 * s.k, 34 * s.k);
      cactus(r, e + d * 30 * s.k, s.gt + 8 * s.k, 22 * s.k);
      rock(r, e + d * 40 * s.k - 4, s.gt + 8 * s.k, 8 * s.k, 4 * s.k, "#c8913f", "#e0aa58");
    },
    floor: (r, s, rand) => ripples(r, s.W, s.gt, s.H, rand, "#d8a458"),
  },
  bg_badlands: {
    sky: ["#f2b48a", "#fbe6cc"], sun: true,
    ground: ["#b8602e", "#c87a48", "#a8502a"],
    // painted desert stripes far off, a butte and its spire on the left, an
    // arch on the right
    far(r, s) {
      butte(r, s.W * 0.42, s.gt - 6, 14, 18, ["#c48a70", "#b87a62"]);
      butte(r, s.W * 0.6, s.gt - 6, 9, 12, ["#c89078", "#bc8068"]);
      [[22, "#c8a0b0", 0.4], [17, "#e8b098", 1.9], [13, "#f0d0b0", 3.1], [9, "#d88060", 4.4], [5, "#c8a0b0", 5.2]].forEach(([amp, c, ph]) => hills(r, s.W, s.gt, amp, c, ph, 0.05));
    },
    full(r, s, rand) {
      const k = s.k;
      const reds = ["#c4673a", "#b8582e", "#d88a50", "#a8502a", "#e0a070"];
      const bx = Math.max(14 * k, s.margin * 0.45);
      butte(r, bx, s.gt + 4 * k, 26 * k, s.gt * 0.5, reds);
      butte(r, bx + 22 * k, s.gt + 4 * k, 6 * k, s.gt * 0.4, reds);
      rockArch(r, s.W - Math.max(22 * k, s.margin * 0.5), s.gt + 6 * k, 30 * k, 24 * k, "#d88a50", "#b8602e");
      butte(r, s.W - 4 * k, s.gt + 8 * k, 30 * k, 9 * k, ["#c4673a", "#e0a070"]);
      for (let i = 0; i < 6; i++) juniper(r, rand() * s.W, s.gt + (4 + rand() * 12) * k, k);
    },
    floor: (r, s, rand) => {
      speckles(r, s.W, s.gt, s.H, rand, ["#a8502a", "#d88a50"], s.W / 2, 2, 1);
      for (let i = 0; i < s.W / 25; i++) {
        const x = rand() * s.W, y = s.gt + 4 + rand() * (s.H - s.gt - 6);
        r(x, y, 4, 1, "#9a4a24"); // cracks in the dry ground
        r(x + 3, y + 1, 3, 1, "#9a4a24");
      }
    },
  },
  bg_tundra: {
    near: "#dce8f2", aurora: true,
    sky: ["#bcd4e8", "#f4f8fb"], clouds: true,
    ground: ["#ffffff", "#e2eef8", "#dce8f2"],
    far: (r, s) => mountains(r, s.W, s.gt, [[0.18, 36, 32], [0.5, 28, 28], [0.8, 40, 36]], "#9ab0c4", "#b4c8d8", "#ffffff"),
    // ice: shards, icebergs in a frozen lake, drifts; one little pine
    side(r, s, e, d) {
      const k = s.k;
      iceberg(r, e + d * 14 * k, s.gt + 10 * k, 24 * k, 20 * k);
      [[30, 22, 7], [35, 14, 5], [26, 10, 4], [4, 16, 6]].forEach(([o, h, w]) => iceShard(r, e + d * o * k, s.gt + 6 * k, h * k, w * k));
      if (d > 0) pine(r, e + 44 * k, s.gt + 4 * k, 22 * k, "#3f6a5a", "#2a4a42", "#ffffff");
      blob(r, e + d * 40 * k, s.gt + 10 * k, 10 * k, 3 * k, "#f4f8fb"); // a snowdrift
    },
    floor(r, s, rand) {
      const y = s.gt + 6;
      r(0, y, s.W, (s.H - y) * 0.55, "#cfe8f4"); // the frozen lake
      r(0, y, s.W, 1, "#e8f6fc");
      for (let i = 0; i < s.W / 14; i++) {
        const x = rand() * s.W, cy = y + 2 + rand() * (s.H - y) * 0.45;
        r(x, cy, 5, 1, "#a8d0e4"); // cracks in the ice
        r(x + 4, cy + 1, 3, 1, "#a8d0e4");
        if (i % 3 === 0) r(x + 8, cy - 1, 2, 1, "#ffffff");
      }
      speckles(r, s.W, y + (s.H - y) * 0.55, s.H, rand, ["#dce8f2", "#bcd4e8"], s.W / 3, 3, 1);
    },
  },
  bg_mushroom_island: {
    near: "#9a88ac",
    sky: ["#d8bce4", "#f8eef4"], clouds: true, cloudColor: ["#fff4fa", "#ead8ea"],
    ground: ["#8a7a9a", "#a898b8", "#7a6a8a"],
    far: (r, s) => hills(r, s.W, s.gt, 16, "#b8a4c8", 2.6),
    // blocky mushrooms, lots of them, all sizes and colors
    side(r, s, e, d) {
      const k = s.k;
      [
        [30, 18, 40, "#c8783a", "#f4ead2"], [4, 24, 30, "#d8483a", "#ffffff"], [18, 14, 18, "#8a55c4", "#f6d465"],
        [44, 10, 14, "#3fb8a8", "#e8fff8"], [12, 8, 8, "#d8483a", "#ffffff"], [52, 7, 9, "#e8b33e", null], [38, 6, 6, "#8a55c4", "#ffffff"],
      ].forEach(([o, w, h, cap, spot], i) => blockMushroom(r, e + d * o * k, s.gt + (3 + (i % 3) * 3) * k, w * k, h * k, cap, spot));
    },
    floor: (r, s, rand) => {
      for (let i = 0; i < s.W / 9; i++) {
        const x = Math.floor(rand() * s.W), y = s.gt + 4 + Math.floor(rand() * (s.H - s.gt - 6));
        r(x, y - 2, 1, 2, "#f4ead2");
        r(x - 1, y - 4, 3, 2, ["#d8483a", "#f6d465", "#8a55c4", "#3fb8a8"][i % 4]); // little square mushrooms
      }
    },
  },
  bg_space: {
    sky: ["#14162e", "#3a2c62"], dark: true, starCount: 140, noGround: true,
    ground: ["#000000", "#000000", "#000000"],
    // nothing to stand on: nebulae, planets, satellites going by, shooting stars
    far(r, s) {
      nebula(r, s.W * 0.2, s.H * 0.35, 40, 18, "rgba(200, 120, 220, 0.12)");
      nebula(r, s.W * 0.75, s.H * 0.7, 46, 20, "rgba(110, 160, 240, 0.12)");
      nebula(r, s.W * 0.5, s.H * 0.15, 30, 12, "rgba(240, 140, 170, 0.1)");
    },
    side(r, s, e, d) {
      const k = s.k;
      if (d > 0) {
        planet(r, e + 16 * k, s.H * 0.22, 10 * k, "#e8823a", "#f6b070", "#f6d465");
        planet(r, e + 10 * k, s.H * 0.78, 6 * k, "#6ac8a8", "#a8f0d8");
      } else {
        planet(r, e - 18 * k, s.H * 0.5, 14 * k, "#5a7ad8", "#9ab8f0");
        planet(r, e - 10 * k, s.H * 0.15, 4 * k, "#d8d0c0", "#ffffff");
      }
      for (let i = 0; i < 5; i++) blob(r, e + d * (6 + i * 9) * k, s.H * (0.6 + (i % 3) * 0.1), (1 + (i % 3)) * k, (1 + (i % 2)) * k, "#7a7484"); // asteroids
    },
    anim(r, s, t) {
      const span = s.W + 60;
      satellite(r, ((t * 4) % span) - 30, s.H * 0.3 + Math.sin(t * 0.2) * 4);
      satellite(r, s.W - (((t * 2.5 + 140) % span) - 30), s.H * 0.62);
      const shot = t % 7; // a shooting star every few seconds
      if (shot < 1.2) {
        const p = shot / 1.2, x = s.W * (0.15 + p * 0.5), y = s.H * (0.08 + p * 0.25);
        for (let i = 0; i < 12; i++) r(x - i * 2, y - i * 0.8, 2, 1, `rgba(255, 246, 216, ${(1 - i / 12).toFixed(2)})`);
      }
    },
    floor() {},
  },
  bg_moon: {
    sky: ["#14162a", "#2c2e4a"], dark: true, starCount: 110,
    ground: ["#b0b0b4", "#d0d0d4", "#9a9a9e"],
    far(r, s) {
      planet(r, Math.round(s.W * 0.82), Math.round(s.H * 0.18), 10, "#4a8ac8", "#7ab8e8"); // home, far away
      r(Math.round(s.W * 0.82) - 4, Math.round(s.H * 0.18) - 2, 5, 3, "#5aa845");
    },
    side(r, s, e, d) {
      rock(r, e + d * 10 * s.k - 9, s.gt + 6 * s.k, 18 * s.k, 10 * s.k, "#9a9a9e", "#c0c0c4");
      rock(r, e + d * 26 * s.k - 4, s.gt + 9 * s.k, 9 * s.k, 5 * s.k, "#8a8a8e", "#b0b0b4");
      if (d > 0) {
        const fx = e + 36 * s.k, fy = s.gt + 6 * s.k; // a flag someone left
        r(fx, fy - 18 * s.k, 1, 18 * s.k, "#d0d0d4");
        r(fx + 1, fy - 18 * s.k, 9 * s.k, 6 * s.k, "#e8b33e");
        r(fx + 3 * s.k, fy - 16 * s.k, 3 * s.k, 2 * s.k, "#c8423a");
      }
    },
    floor: (r, s, rand) => {
      for (let i = 0; i < s.W / 20; i++) crater(r, Math.floor(rand() * s.W), s.gt + 5 + Math.floor(rand() * (s.H - s.gt - 8)), 3 + Math.floor(rand() * 6), "#9a9a9e", "#e0e0e4");
    },
  },
  bg_mars: {
    sky: ["#d8a07a", "#f2d6b8"], sun: true, sunColor: ["#e8f0f8", "rgba(220, 230, 240, 0.35)"],
    ground: ["#b8623a", "#c87648", "#a85430"],
    // a wide flat plain under a butterscotch sky, low hills, a rover rolling along
    far(r, s) {
      hills(r, s.W, s.gt, 7, "#c88a62", 0.7, 0.02);
      hills(r, s.W, s.gt, 4, "#c07850", 2.6, 0.04);
      blob(r, s.W * 0.3, s.H * 0.1, 3, 2, "#c8a890"); // its two little moons
      blob(r, s.W * 0.62, s.H * 0.16, 2, 2, "#b89a84");
    },
    full(r, s, rand) {
      const k = s.k;
      rover(r, s.W - Math.max(26 * k, s.margin * 0.55), s.gt + 12 * k, k);
      for (let i = 0; i < 14; i++) rock(r, rand() * s.W, s.gt + (4 + rand() * 18) * k, (2 + rand() * 5) * k, (1 + rand() * 3) * k, "#8e3f22", "#c86a38");
    },
    anim(r, s, t) {
      const x = Math.max(12, s.margin * 0.4) + Math.sin(t * 0.3) * 6; // a dust devil
      for (let i = 0; i < 26; i++) r(x + Math.sin(t * 3 + i * 0.5) * (i * 0.25), s.gt - i * 1.2, 2 + i * 0.25, 1, "rgba(220, 160, 120, 0.35)");
    },
    floor: (r, s, rand) => {
      ripples(r, s.W, s.gt, s.H, rand, "#a85430");
      speckles(r, s.W, s.gt, s.H, rand, ["#8e3f22", "#d88050"], s.W / 2, 2, 1);
    },
  },
};

// --- putting it on the page -------------------------------------------------------------------

const Scenery = { canvas: null, still: null, place: null, night: false, t: 0, timer: null };

function sceneSize() {
  // in screen px: the canvas isn't zoomed with the page (ui_scale.js), but
  // the page's column is, so it's wider here
  const zoom = typeof UIScale === "undefined" ? 1 : UIScale.zoom();
  const W = Math.ceil(window.innerWidth / SCENERY_PX);
  const H = Math.ceil(window.innerHeight / SCENERY_PX);
  const gt = H - Math.max(24, Math.round(H * 0.18));
  // how far in from each edge the page's column starts (things down the
  // sides peek out here; on narrow screens they hide behind the page)
  const margin = Math.max(0, (W - (CONTENT_W * zoom) / SCENERY_PX) / 2);
  // things down the sides grow with the screen: a front tree is about a
  // third of it tall
  const k = Math.max(1, gt / 110);
  return { W, H, gt, margin, k };
}

// The part that doesn't move: sky, far hills, the sides and the ground.
function paintStill(ctx, s, scene, night, seed) {
  const r = (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x), Math.round(y), Math.ceil(w), Math.ceil(h));
  };
  const rand = sceneRand(seed);
  skyBands(r, s.W, s.gt, ...scene.sky);
  if (scene.sun && !night) {
    const [c, g] = scene.sunColor || ["#fff2b0", "rgba(255, 242, 176, 0.45)"];
    sun(r, Math.round(s.W - Math.max(16, s.margin * 0.6)), Math.round(s.H * 0.12), c, g);
  }
  scene.far(r, s);
  if (scene.near) hills(r, s.W, s.gt, 9, scene.near, 4.1, 0.06);
  if (!scene.noGround) {
    groundBand(r, s.W, s.gt, s.H, ...scene.ground);
    scene.floor(r, s, rand);
  }
  // the sides: in from each edge, a little into the page's margin
  const inset = Math.max(0, Math.min(14, s.margin - 40));
  if (scene.side) {
    scene.side(r, s, inset, 1, rand);
    scene.side(r, s, s.W - inset, -1, rand);
  }
  if (scene.full) scene.full(r, s, rand); // places that aren't the same on both sides
}

// Night: dusk over everything, then stars and the moon (space has its
// stars by day too).
function paintNightSky(r, s, scene, night, seed, t = 0) {
  if (night) r(0, 0, s.W, s.H, "rgba(16, 20, 52, 0.55)");
  if (night && scene.aurora) aurora(r, s, t);
  if (scene.dark || night) stars(r, s.W, s.gt * 0.8, sceneRand(seed + 1), scene.starCount || 60, ["#fff6d8", "#9ae6f0", "#ffffff"]);
  if (night && !scene.dark) moon(r, Math.round(s.W - Math.max(14, s.margin * 0.6)), Math.round(s.H * 0.11));
}

// The moving part: drifting clouds and whatever the place animates.
function paintMoving(ctx, s, scene, night, t) {
  const r = (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x), Math.round(y), Math.ceil(w), Math.ceil(h));
  };
  if (scene.clouds && !night) {
    const [c, shade] = scene.cloudColor || ["#ffffff", "#e2eef2"];
    const span = s.W + 60;
    [[0.05, 0.08, 2, 0.6], [0.45, 0.2, 1, 1], [0.75, 0.05, 2, 0.4], [0.25, 0.32, 1, 0.8]].forEach(([x0, y0, sc, speed]) => {
      const x = ((x0 * span + t * speed * 1.5) % span) - 40;
      cloud(r, x, Math.round(s.gt * y0), sc, c, shade);
    });
  }
  if (scene.fliers === "birds" && !night) birds(r, s, t);
  if (scene.fliers === "fish") fishies(r, s, t);
  if (scene.anim) scene.anim(r, s, t);
}

// A few birds flapping across the sky, now and then.
function birds(r, s, t) {
  const span = s.W + 80;
  [[0, 0.18, 6], [0.4, 0.26, 5], [0.7, 0.14, 7]].forEach(([x0, y0, speed], i) => {
    const x = ((x0 * span + t * speed) % span) - 40;
    const y = Math.round(s.gt * y0 + Math.sin(t * 0.8 + i) * 2);
    const up = Math.floor(t * 4 + i) % 2;
    r(x, y + up, 2, 1, "#3b2417");
    r(x + 2, y + 1, 1, 1, "#3b2417");
    r(x + 3, y + up, 2, 1, "#3b2417");
  });
}

// Little fish swimming by under the sea.
function fishies(r, s, t) {
  const span = s.W + 60;
  [[0.1, 0.3, 5, "#f0a040"], [0.5, 0.5, 4, "#f6d465"], [0.8, 0.2, 6, "#f08068"], [0.3, 0.65, 3, "#9ad0f0"]].forEach(([x0, y0, speed, c]) => {
    const x = ((x0 * span + t * speed) % span) - 30;
    const y = Math.round(s.gt * y0);
    r(x, y, 5, 3, c);
    r(x - 2, y - 1, 2, 1, c);
    r(x - 2, y + 3, 2, 1, c);
    r(x - 1, y + 1, 1, 1, c);
    r(x + 3, y + 1, 1, 1, "#3b2417");
  });
}

function drawScenery() {
  const sc = Scenery;
  if (!sc.canvas) return;
  const s = sceneSize();
  const scene = SCENES[sc.place] || SCENES.bg_meadow;
  if (scene.noGround) s.gt = s.H;
  const key = `${sc.place}:${sc.night}:${s.W}x${s.H}`;
  if (sc.key !== key) {
    sc.key = key;
    sc.canvas.width = s.W;
    sc.canvas.height = s.H;
    sc.canvas.style.width = `${s.W * SCENERY_PX}px`;
    sc.canvas.style.height = `${s.H * SCENERY_PX}px`;
    sc.still = document.createElement("canvas");
    sc.still.width = s.W;
    sc.still.height = s.H;
    paintStill(sc.still.getContext("2d"), s, scene, sc.night, sc.place.length * 7919);
  }
  const ctx = sc.canvas.getContext("2d");
  ctx.drawImage(sc.still, 0, 0);
  paintMoving(ctx, s, scene, sc.night, sc.t);
  paintNightSky((x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x), Math.round(y), Math.ceil(w), Math.ceil(h));
  }, s, scene, sc.night, sc.place.length * 7919, sc.t);
}

// Northern lights rippling over the tundra at night.
function aurora(r, s, t) {
  [["rgba(120, 240, 170, 0.38)", 0.12, 0], ["rgba(170, 120, 240, 0.3)", 0.2, 2], ["rgba(120, 220, 240, 0.26)", 0.28, 4]].forEach(([c, y0, ph]) => {
    for (let x = 0; x < s.W; x += 2) {
      const y = s.H * y0 + Math.sin(x * 0.04 + t * 0.5 + ph) * 6 + Math.sin(x * 0.11 + ph) * 3;
      r(x, y, 2, 10 + Math.sin(x * 0.07 + t + ph) * 4, c);
    }
  });
}

// Where the waterfall's cliff is: over the left margin, from near the top.
function fallsAt(s) {
  return { cw: Math.round(Math.max(30, s.margin + 4)), top: Math.round(s.H * 0.1) };
}

function renderScenery(place, night) {
  const sc = Scenery;
  if (!sc.canvas) {
    sc.canvas = document.createElement("canvas");
    sc.canvas.className = "scenery";
    sc.canvas.setAttribute("aria-hidden", "true");
    document.body.prepend(sc.canvas);
    window.addEventListener("resize", drawScenery);
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!still) {
      sc.timer = setInterval(() => {
        sc.t += SCENERY_TICK_MS / 1000;
        drawScenery();
      }, SCENERY_TICK_MS);
    }
  }
  sc.place = SCENES[place] ? place : "bg_meadow";
  sc.night = night;
  const dark = SCENES[sc.place].dark || SCENES[sc.place].inkLight;
  document.documentElement.toggleAttribute("data-dark-scenery", Boolean(dark) && !night);
  drawScenery();
}

window.renderScenery = renderScenery;
window.Scenery = Scenery;
})();

// A wrapped-up present (a pet a grown-up gave, app/pet_gift.py): red with a white
// ribbon and bow, 8x8 units with its top-left at (x, y), each unit `s` big.
function drawGiftBox(r, x, y, s = 1) {
  const u = (dx, dy, w, h, c) => r(x + dx * s, y + dy * s, w * s, h * s, c);
  u(0, 3, 8, 5, "#c8302a"); // the box
  u(0, 3, 8, 1, "#e0483a");
  u(0, 7, 8, 1, "#9a2018");
  u(-0.5, 2, 9, 1.5, "#d83a30"); // its lid
  u(3, 2, 2, 6, "#fbf6ec"); // the ribbon, down and across
  u(0, 4.5, 8, 1, "#fbf6ec");
  u(3, 7, 2, 1, "#e8dcc8");
  u(1, 0, 2, 2, "#fbf6ec"); // the bow
  u(5, 0, 2, 2, "#fbf6ec");
  u(1.5, 0.5, 1, 1, "#e8dcc8");
  u(5.5, 0.5, 1, 1, "#e8dcc8");
  u(3, 1, 2, 1, "#fbf6ec");
}
