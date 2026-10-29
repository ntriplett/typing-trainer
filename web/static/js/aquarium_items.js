// Aquarium art (PLAN.md 11k): tank backgrounds, substrates, and the pieces
// (plants, rocks, decorations) from app/aquarium.py's CATALOG. A tank is
// TANK_W x TANK_H units; the substrate is the bottom SUBSTRATE_H.
//
// Pieces draw in their own box: local (0, 0) is the top-left of a w x h
// box, so drawAquaPiece() can place and flip any of them. `t` is a tick
// count for swaying plants and rising bubbles; `top` is how far above the
// box the water's surface is (bubbles rise to it).

const TANK_W = 160;
const TANK_H = 70;
const SUBSTRATE_H = 8;

function aquaSeeded(n) {
  let a = n * 9301 + 49297;
  return () => {
    a = (a * 9301 + 49297) % 233280;
    return a / 233280;
  };
}

function aquaDisc(r, cx, cy, rx, ry, color) {
  for (let dy = -ry; dy <= ry; dy += 1) {
    const half = rx * Math.sqrt(Math.max(0, 1 - (dy * dy) / (ry * ry)));
    if (half >= 0.4) r(cx - half, cy + dy, half * 2, 1, color);
  }
}

function aquaWater(r, top, bottom) {
  for (let y = 0; y < TANK_H; y++) {
    const t = y / TANK_H;
    r(0, y, TANK_W, 1, `rgb(${Math.round(top[0] + (bottom[0] - top[0]) * t)}, ${Math.round(top[1] + (bottom[1] - top[1]) * t)}, ${Math.round(top[2] + (bottom[2] - top[2]) * t)})`);
  }
}

function aquaRays(r, color) {
  for (const [x, w] of [[14, 8], [52, 12], [96, 7], [130, 10]]) for (let y = 0; y < 40; y += 2) r(x + y * 0.4, y, w - y * 0.12, 2, color);
}

// --- backgrounds --------------------------------------------------------------------

const AQUA_BACKGROUNDS = {
  bg_blue(r) {
    aquaWater(r, [120, 196, 224], [36, 92, 140]);
    aquaRays(r, "rgba(255, 255, 255, 0.05)");
  },
  bg_night(r) {
    aquaWater(r, [26, 34, 56], [8, 10, 20]);
    const rand = aquaSeeded(3);
    for (let i = 0; i < 30; i++) r(rand() * TANK_W, rand() * TANK_H, 0.5, 0.5, "rgba(160, 200, 255, 0.35)");
  },
  bg_stones(r) {
    aquaWater(r, [140, 190, 200], [60, 110, 120]);
    const rand = aquaSeeded(5);
    for (let i = 0; i < 70; i++) {
      const x = rand() * TANK_W;
      const y = 28 + rand() * 36;
      aquaDisc(r, x, y, 4 + rand() * 5, 2.5 + rand() * 2.5, ["#7a7a6a", "#8a8070", "#6a6a60", "#9a9080"][i % 4]);
    }
    r(0, 26, TANK_W, 40, "rgba(80, 140, 160, 0.35)"); // far away, under water
  },
  bg_sunset(r) {
    aquaWater(r, [248, 176, 120], [120, 60, 110]);
    aquaRays(r, "rgba(255, 230, 180, 0.08)");
  },
  bg_coral(r) {
    aquaWater(r, [110, 190, 224], [40, 96, 150]);
    const rand = aquaSeeded(7);
    for (let i = 0; i < 14; i++) {
      const x = rand() * TANK_W;
      const h = 14 + rand() * 18;
      const c = ["#d86a8a", "#e8944a", "#9a6ac8", "#e86a6a"][i % 4];
      r(x, 64 - h, 2, h, c); // branching coral
      for (let k = 4; k < h; k += 5) r(x + (k % 10 ? 2 : -3), 64 - k, 3, 1.5, c);
      aquaDisc(r, x + 1, 64 - h, 2.5, 1.5, c);
    }
    r(0, 30, TANK_W, 36, "rgba(60, 120, 170, 0.35)");
  },
  bg_roots(r) {
    aquaWater(r, [120, 160, 110], [40, 70, 50]);
    const rand = aquaSeeded(11);
    for (let i = 0; i < 12; i++) {
      let x = rand() * TANK_W; // roots reaching down from the top
      for (let y = 0; y < 20 + rand() * 30; y++) {
        x += Math.sin(y / 4 + i) * 0.4;
        r(x, y, 2 - y / 40, 1, "#3a2a1a");
      }
    }
    r(0, 0, TANK_W, TANK_H, "rgba(60, 90, 60, 0.25)");
  },
};

// --- substrates ---------------------------------------------------------------------

function aquaGround(r, base, specks, round = false) {
  const top = TANK_H - SUBSTRATE_H;
  for (let x = 0; x < TANK_W; x++) {
    const bump = Math.round(Math.sin(x / 11) + Math.sin(x / 4.3) * 0.6);
    r(x, top + bump, 1, TANK_H - top - bump, base);
  }
  const rand = aquaSeeded(base.length + specks.length);
  for (let i = 0; i < (round ? 90 : 160); i++) {
    const x = rand() * TANK_W;
    const y = top + 1 + rand() * (SUBSTRATE_H - 1);
    if (round) aquaDisc(r, x, y, 1.5, 0.8, specks[i % specks.length]);
    else r(x, y, 0.8, 0.8, specks[i % specks.length]);
  }
}

const AQUA_SUBSTRATES = {
  sand: (r) => aquaGround(r, "#d8c28a", ["#c8b078", "#e8d4a0", "#b8a068"]),
  sand_white: (r) => aquaGround(r, "#ece6d8", ["#ddd6c6", "#f8f4ec", "#c8c0b0"]),
  sand_black: (r) => aquaGround(r, "#2e2a2a", ["#3e3838", "#1e1a1a", "#5a5050"]),
  gravel_mix: (r) => aquaGround(r, "#8a7a6a", ["#b8432f", "#e8b33e", "#6b8e3a", "#4a6aa0", "#d8c090", "#5c3a1a"], true),
  gravel_blue: (r) => aquaGround(r, "#3a5a9a", ["#4a7ac8", "#6a9ae0", "#2a4a8a"], true),
  gravel_pink: (r) => aquaGround(r, "#c86a9a", ["#e88ab8", "#f8aad0", "#a85a8a"], true),
  pebbles: (r) => aquaGround(r, "#7a6a5a", ["#9a8a7a", "#5a4a3a", "#b0a090", "#6a6a60"], true),
};

// --- pieces (local coordinates: 0..w by 0..h, bottom at h) ---------------------------

function aquaBubbles(r, x, h, top, t, seed, count = 3) {
  for (let i = 0; i < count; i++) {
    const rise = (t * 0.6 + i * 23 + seed * 7) % (top + h);
    const y = h - rise;
    r(x + Math.sin((t + i * 9) / 6) * 1.2, y, 1, 1, "rgba(220, 240, 255, 0.75)");
  }
}

function aquaSway(t, k, amount = 1) {
  return Math.sin(t / 10 + k / 6) * amount * (k / 20);
}

const AQUA_PIECES = {
  grass(r, w, h, t) {
    for (const [bx, c] of [[0.5, "#5aa04a"], [1.6, "#4a9040"], [2.7, "#6ab05a"]]) {
      for (let k = 0; k < h - bx * 2; k++) r(bx + aquaSway(t, k + bx * 5, 2), h - k - 1, 0.8, 1, c);
    }
  },
  kelp(r, w, h, t) {
    for (let k = 0; k < h; k++) {
      const x = 2 + aquaSway(t, k, 3);
      r(x, h - k - 1, 1.2, 1, "#5a7a2a");
      if (k % 5 === 2) r(x + (k % 10 ? 1 : -2.5), h - k - 1, 2.5, 1.2, "#7a9a3a");
    }
  },
  moss_ball(r, w, h) {
    aquaDisc(r, w / 2, h / 2, w / 2, h / 2, "#3a7a2a");
    aquaDisc(r, w / 2 - 0.5, h / 2 - 0.5, w / 2 - 1.5, h / 2 - 1.5, "#4a8a3a");
    r(w / 2 - 1, 1, 1, 1, "#6aaa5a");
  },
  java_fern(r, w, h, t) {
    r(1, h - 1.5, w - 2, 1.5, "#4a3a2a");
    for (const [lx, lh, lean] of [[2, 12, -1], [4, 15, -0.4], [6, 14, 0.3], [8, 11, 0.8], [10, 9, 1.2]]) {
      for (let k = 0; k < lh; k++) {
        const x = lx + lean * k * 0.3 + aquaSway(t, k + lx, 1);
        r(x - 1, h - 2 - k, k > 2 && k < lh - 2 ? 2.5 : 1.2, 1, k % 2 ? "#2e6a2a" : "#3a7a32");
      }
    }
  },
  ludwigia(r, w, h, t) {
    for (const sx of [2, 5]) {
      for (let k = 0; k < h - sx; k++) {
        const x = sx + aquaSway(t, k + sx * 3, 1.5);
        r(x, h - k - 1, 0.8, 1, "#6a4a2a");
        if (k % 3 === 0) {
          const c = k > h / 2 ? "#d8483a" : "#a86a3a";
          r(x - 1.6, h - k - 1, 1.6, 0.8, c);
          r(x + 0.8, h - k - 1, 1.6, 0.8, c);
        }
      }
    }
  },
  sword(r, w, h, t) {
    for (let i = 0; i < 9; i++) {
      const lean = (i - 4) / 3;
      const len = h - Math.abs(i - 4) * 3;
      for (let k = 0; k < len; k++) {
        const x = w / 2 + lean * k * 0.45 + aquaSway(t, k + i * 4, 1);
        const wide = k > 3 && k < len - 3 ? 2 : 1;
        r(x - wide / 2, h - k - 1, wide, 1, i % 2 ? "#3a8a3a" : "#4a9a4a");
      }
    }
  },
  lily(r, w, h, t) {
    for (const [sx, lean] of [[w / 2 - 2, -0.08], [w / 2 + 1, 0.1]]) {
      for (let k = 0; k < h - 3; k++) r(sx + lean * k + aquaSway(t, k, 1.5), h - k - 1, 0.6, 1, "#5a8a3a");
    }
    aquaDisc(r, w / 2 - 4, 2, 4, 1.2, "#4a8a3a"); // pads on the surface
    aquaDisc(r, w / 2 + 4, 2.5, 3.5, 1, "#3a7a32");
    aquaDisc(r, w / 2 + 3, 1, 1.5, 1, "#f6aacb"); // a flower
    r(w / 2 + 2.5, 0.5, 1, 0.6, "#f8e08a");
  },
  pebble(r, w, h) {
    aquaDisc(r, w / 2, h / 2 + 0.5, w / 2, h / 2, "#8a8478");
    r(1, 0.6, 2, 0.6, "#b8b2a6");
  },
  flat_stone(r, w, h) {
    aquaDisc(r, w / 2, h / 2 + 0.5, w / 2, h / 2, "#7a7468");
    r(2, 1, w - 4, 1, "#9a948a");
  },
  slate(r, w, h) {
    for (let k = 0; k < 4; k++) {
      const sw = w - k * 3;
      const y = h - (k + 1) * 4;
      r((w - sw) / 2 + (k % 2), y, sw, 3.5, k % 2 ? "#5a6068" : "#4a5058");
      r((w - sw) / 2 + (k % 2), y, sw, 0.8, "#7a8088");
    }
  },
  big_rock(r, w, h) {
    aquaDisc(r, w / 2, h / 2 + 1, w / 2, h / 2, "#6a645a");
    aquaDisc(r, w / 2 - 2, h / 2 - 1, w / 2 - 4, h / 2 - 3, "#8a8478");
    r(w / 2 - 6, 3, 5, 1, "#a8a296");
    r(w / 2 + 2, h / 2 + 2, 6, 0.8, "#4a453e");
  },
  cave_rock(r, w, h) {
    aquaDisc(r, w / 2, h / 2 + 1, w / 2, h / 2, "#5a544a");
    aquaDisc(r, w / 2 - 2, h / 2 - 1, w / 2 - 4, h / 2 - 3, "#7a7468");
    aquaDisc(r, w / 2 + 1, h - 4, 6, 4, "#1e1a16"); // the cave
    r(w / 2 - 5, h - 1, 12, 1, "#1e1a16");
  },
  diver(r, w, h, t, top) {
    r(2, 6, 4, 6, "#d8a030"); // suit
    r(1.5, 12, 2, 2, "#5c3a1a");
    r(4.5, 12, 2, 2, "#5c3a1a");
    aquaDisc(r, 4, 3.5, 3, 3, "#c89a40"); // helmet
    aquaDisc(r, 4.5, 3.5, 1.5, 1.5, "#7ec4dc");
    r(0.5, 7, 1.5, 4, "#d8a030");
    aquaBubbles(r, 4, 1, top, t, 3, 2);
  },
  clam(r, w, h, t) {
    const open = (Math.sin(t / 25) + 1) / 2; // slowly opens and closes
    aquaDisc(r, w / 2, h - 2, w / 2, 2, "#d8a8c8");
    for (let k = 0; k < w; k += 2) r(k, h - 3, 1, 3, "#b888a8");
    const lid = 2 + open * 3;
    aquaDisc(r, w / 2, h - 3 - lid, w / 2, 1.5, "#e8b8d8");
    if (open > 0.4) aquaDisc(r, w / 2, h - 3, 1.2, 1.2, "#fbf8f0"); // a pearl
  },
  bubbler(r, w, h, t, top) {
    aquaDisc(r, w / 2, h - 1.5, w / 2, 1.5, "#5a5a66");
    r(w / 2 - 1, h - 3, 2, 1, "#7a7a88");
    for (let i = 0; i < 8; i++) {
      const rise = (t * 0.9 + i * ((top + h) / 8)) % (top + h);
      const size = 0.6 + (rise / (top + h)) * 1.2;
      r(w / 2 - size / 2 + Math.sin((t + i * 5) / 4), h - 3 - rise, size, size, "rgba(220, 240, 255, 0.8)");
    }
  },
  chest(r, w, h, t, top) {
    const open = Math.max(0, Math.sin(t / 30)); // the lid pops open now and then
    r(1, h - 6, w - 2, 6, "#8b5a2b");
    r(1, h - 6, w - 2, 1, "#c8a030");
    r(1, h - 2, w - 2, 1, "#c8a030");
    r(w / 2 - 1, h - 5, 2, 2, "#e8c84a");
    if (open > 0.3) {
      r(2, h - 7, w - 4, 1, "#e8c84a"); // gold inside
      r(1, h - 6 - 4 * open, w - 2, 2, "#a87a44");
      aquaBubbles(r, w / 2, h - 7, top, t, 5, 4);
    } else r(1, h - 9, w - 2, 3, "#a87a44");
  },
  arch(r, w, h) {
    for (let y = 0; y < h; y++) {
      const outer = w / 2;
      const inner = y < h * 0.3 ? 0 : (w / 2 - 6) * Math.sqrt(Math.min(1, (y - h * 0.3) / (h * 0.5)));
      const c = y % 4 === 0 ? "#6a645a" : "#8a8478";
      r(w / 2 - outer, y, outer - inner, 1, c);
      r(w / 2 + inner, y, outer - inner, 1, c);
    }
    r(0, 0, w, 1.5, "#a8a296");
  },
  castle(r, w, h) {
    r(2, 10, w - 4, h - 10, "#9a948a");
    for (const tx of [0, w - 7]) {
      r(tx, 2, 7, h - 2, "#a8a296"); // towers
      for (let k = 0; k < 7; k += 2) r(tx + k, 0, 1.5, 2, "#a8a296");
      r(tx + 2.5, 8, 2, 3, "#2a2620");
    }
    for (let k = 2; k < w - 2; k += 3) r(k, 8, 1.5, 2, "#9a948a");
    r(w / 2 - 4, h - 10, 8, 10, "#2a2620"); // the door: fish swim in
    aquaDisc(r, w / 2, h - 10, 4, 2, "#2a2620");
    r(w / 2 - 0.5, 0, 1, 6, "#5c3a1a");
    r(w / 2 + 0.5, 0, 4, 2.5, "#d8483a");
  },
  ship(r, w, h) {
    for (let y = 8; y < h; y++) {
      const inset = ((y - 8) / (h - 8)) * 8; // the hull, sitting tilted
      r(inset + (h - y) * 0.15, y, w - inset * 2, 1, y % 3 ? "#6e4a2a" : "#5c3a1a");
    }
    r(6, 8, w - 12, 1.5, "#8b5a2b");
    r(w * 0.4, 0, 1.5, 9, "#5c3a1a"); // a broken mast
    r(w * 0.4 - 6, 3, 10, 0.8, "#5c3a1a");
    for (const px of [12, 22, 32]) aquaDisc(r, px, 14, 1.5, 1.5, "#2a1a10"); // portholes
    r(w - 14, 12, 6, h - 12, "#2a1a10"); // a hole fish swim through
  },
  driftwood(r, w, h) {
    const branch = (x0, y0, x1, y1, thick) => {
      const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0));
      for (let k = 0; k <= n; k++) {
        const t = k / n;
        r(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, thick * (1 - t * 0.5), thick * (1 - t * 0.5), k % 4 ? "#8a6a48" : "#6e5236");
      }
    };
    branch(4, h - 4, w - 6, h - 6, 4);
    branch(14, h - 5, 6, 2, 3);
    branch(24, h - 6, 30, 0, 2.5);
    branch(36, h - 6, w - 2, 6, 2.5);
    branch(30, 8, 22, 4, 1.5);
  },
};

// A piece at x (left) with its bottom at yb, flipped if asked.
function drawAquaPiece(r, item, x, yb, flip, t = 0) {
  const draw = AQUA_PIECES[item.id];
  if (!draw) return;
  const top = yb - item.h;
  const local = (lx, ly, lw, lh, c) => r(flip ? x + item.w - lx - lw : x + lx, top + ly, lw, lh, c);
  draw(local, item.w, item.h, t, top);
}

// A whole tank's back drop: background and substrate.
function drawAquaLook(r, background, substrate) {
  (AQUA_BACKGROUNDS[background] || AQUA_BACKGROUNDS.bg_blue)(r);
  (AQUA_SUBSTRATES[substrate] || AQUA_SUBSTRATES.sand)(r);
}
