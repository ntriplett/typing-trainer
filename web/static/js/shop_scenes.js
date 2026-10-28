// The Pet Shop's scenes (pet_shop.js): the entrance hall, where each
// department is a doorway or a corner, and a themed room per department
// where the pets for sale wait at their stations (a basket, a stall, a
// tank, a terrarium, a pedestal, a crate). Everything is drawn on a 160x90
// grid through a painter r(x, y, w, h, color) (habitats.js habitatPainter).
//
// A station is {x, y, w, h, floor}: its box, and where a pet's feet go.
// Rooms draw a station's back before the pet and its front after (a tank's
// glass, a stall's fence), so pets sit inside them.

const SHOP_W = 160;
const SHOP_H = 90;

// --- little helpers ---------------------------------------------------------------------

function shopRand(seed) {
  let a = seed * 9301 + 49297;
  return () => {
    a = (a * 9301 + 49297) % 233280;
    return a / 233280;
  };
}

function shopPlanks(r, y, h, light, dark) {
  r(0, y, SHOP_W, h, light);
  for (let k = y + 4; k < y + h; k += 5) r(0, k, SHOP_W, 1, dark);
  const rand = shopRand(y);
  for (let k = y; k < y + h; k += 5) for (let i = 0; i < 4; i++) r(Math.floor(rand() * SHOP_W), k, 1, 4, dark);
}

function shopLamp(r, x, glow) {
  r(x, 0, 1, 5, "#3b2417");
  r(x - 3, 5, 7, 2, "#5c3a1a");
  r(x - 2, 7, 5, 1, glow);
}

// --- the entrance hall ------------------------------------------------------------------

// Where each department is in the hall (its clickable area; the sign hangs
// at the bottom). Archways along the back wall, corners on the floor.
const SHOP_SPOTS = {
  fish: { x: 4, y: 12, w: 28, h: 34 },
  household: { x: 35, y: 12, w: 28, h: 34 },
  farm: { x: 66, y: 12, w: 28, h: 34 },
  reptiles: { x: 97, y: 12, w: 28, h: 34 },
  mythical: { x: 128, y: 12, w: 28, h: 34 },
  orders: { x: 6, y: 56, w: 46, h: 26 },
  habitats: { x: 58, y: 58, w: 44, h: 24 },
  supplies: { x: 108, y: 54, w: 46, h: 28 },
};

// What you glimpse through each department's archway.
const SHOP_GLIMPSE = {
  fish(r, { x, y, w, h }) {
    r(x, y, w, h, "#2e6a8a");
    r(x, y + h - 6, w, 6, "#d8c28a");
    for (const [bx, by] of [[5, 6], [9, 12], [18, 8], [22, 15]]) r(x + bx, y + by, 1, 1, "#bfe6f0");
    r(x + 6, y + 17, 4, 2, "#f0a040");
    r(x + 16, y + 22, 4, 2, "#f0d070");
    r(x + 4, y + h - 12, 1, 6, "#4a8a4a");
    r(x + w - 6, y + h - 14, 1, 8, "#4a8a4a");
  },
  household(r, { x, y, w, h }) {
    r(x, y, w, h, "#e8c8a0");
    r(x + 4, y + 5, 10, 8, "#bfe6f0");
    r(x + 8, y + 5, 1, 8, "#fbf1dc");
    r(x, y + h - 8, w, 8, "#c88a5a");
    r(x + 6, y + h - 6, w - 12, 4, "#b8432f");
    r(x + 14, y + h - 12, 8, 5, "#8b5a2b");
    r(x + 15, y + h - 13, 6, 2, "#e86a8a");
  },
  farm(r, { x, y, w, h }) {
    r(x, y, w, h, "#8e3a26");
    for (let k = x + 3; k < x + w; k += 5) r(k, y, 1, h, "#6e2a1a");
    r(x, y + h - 7, w, 7, "#e0c060");
    r(x + 3, y + h - 12, 9, 6, "#e8c84a");
    r(x + 3, y + h - 10, 9, 1, "#c8a030");
    r(x + w - 10, y + 6, 6, 6, "#fbf1dc");
  },
  reptiles(r, { x, y, w, h }) {
    r(x, y, w, h, "#e8d098");
    r(x, y + h - 7, w, 7, "#d8b070");
    for (const [lx, ly] of [[2, 4], [16, 2], [8, 14], [20, 12]]) {
      r(x + lx, y + ly, 6, 3, "#4a8a4a");
      r(x + lx + 2, y + ly + 3, 2, 3, "#3a6a3a");
    }
    r(x + 10, y + h - 11, 8, 4, "#9a948a");
  },
  mythical(r, { x, y, w, h }) {
    r(x, y, w, h, "#3a2a6a");
    const rand = shopRand(7);
    for (let i = 0; i < 14; i++) r(x + rand() * w, y + rand() * (h - 8), 1, 1, i % 3 ? "#fbf1dc" : "#f8e08a");
    r(x + 9, y + h - 9, 10, 9, "#8a7ab8");
    r(x + 8, y + h - 10, 12, 2, "#b8a8e0");
    r(x + 12, y + h - 13, 4, 3, "#f8e08a");
  },
};

function drawShopArch(r, spot, id, open) {
  const { x, y, w, h } = spot;
  SHOP_GLIMPSE[id](r, { x: x + 3, y: y + 4, w: w - 6, h: h - 4 });
  r(x, y + 4, 3, h - 4, "#8b5a2b"); // the frame
  r(x + w - 3, y + 4, 3, h - 4, "#8b5a2b");
  r(x, y + 2, w, 3, "#8b5a2b");
  r(x + 2, y, w - 4, 2, "#8b5a2b");
  r(x + 1, y + 4, 1, h - 4, "#a87a44");
  r(x + 3, y + 5, w - 6, 1, "rgba(0, 0, 0, 0.25)");
  if (!open) {
    r(x + 3, y + 4, w - 6, h - 4, "rgba(40, 30, 20, 0.45)"); // dim, roped off
    for (let i = 0; i < w - 6; i++) r(x + 3 + i, y + h - 12 + Math.round(Math.sin((i / (w - 6)) * Math.PI) * 3), 1, 1, "#b8432f");
    r(x + 2, y + h - 14, 2, 14, "#c8a030");
    r(x + w - 4, y + h - 14, 2, 14, "#c8a030");
  }
}

function drawOrdersCorner(r, { x, y, w, h }) {
  r(x, y + 8, w, h - 8, "#8b5a2b"); // the counter
  r(x - 1, y + 6, w + 2, 3, "#a87a44");
  r(x + 2, y + 12, w - 4, 1, "#6e4420");
  r(x + 3, y + 1, 12, 6, "#5c5c66"); // a register
  r(x + 4, y + 2, 10, 2, "#9fd0a0");
  r(x + 24, y + 2, 8, 5, "#e8d3a8"); // boxes waiting to go out
  r(x + 24, y + 4, 8, 1, "#b88a50");
  r(x + 33, y - 2, 9, 9, "#d8b070");
  r(x + 33, y + 2, 9, 1, "#b88a50");
  r(x + 37, y - 2, 1, 9, "#b88a50");
}

function drawHabitatsCorner(r, { x, y, w, h }) {
  r(x + 2, y + 6, w - 4, 8, "#7fa346"); // a little meadow diorama
  r(x + 2, y + 2, w - 4, 4, "#a8d5e2");
  for (let i = 4; i < w - 4; i += 6) r(x + i, y + 8, 1, 3, "#8b5a2b");
  r(x + w - 14, y + 9, 6, 2, "#4a8ab0");
  r(x + 8, y + 7, 1, 1, "#e86a8a");
  r(x, y + 14, w, 3, "#a87a44"); // on a table
  r(x + 3, y + 17, 2, h - 17, "#8b5a2b");
  r(x + w - 5, y + 17, 2, h - 17, "#8b5a2b");
}

function drawSuppliesCorner(r, { x, y, w, h }, open) {
  r(x, y, w, h - 4, "#8b5a2b"); // shelves
  for (let k = y + 7; k < y + h - 4; k += 8) r(x, k, w, 2, "#5c3a1a");
  const rand = shopRand(11);
  for (let k = y + 1; k < y + h - 8; k += 8)
    for (let i = x + 2; i < x + w - 4; i += 5) r(i, k + 2, 3, 4, ["#e86a8a", "#f0a040", "#9a7ae0", "#6d9440"][Math.floor(rand() * 4)]);
  if (!open) {
    r(x, y, w, h - 4, "rgba(40, 30, 20, 0.35)");
    for (let i = 0; i < w; i++) r(x + i, y + h - 10 + Math.round(Math.sin((i / w) * Math.PI) * 3), 1, 1, "#b8432f");
  }
}

// The hall: `open` is {departmentId: true} for the open ones.
function drawShopEntrance(r, open) {
  r(0, 0, SHOP_W, 46, "#f3e2bf"); // wallpaper
  for (let x = 2; x < SHOP_W; x += 8) r(x, 0, 3, 46, "#ecd6aa");
  r(0, 0, SHOP_W, 3, "#8b5a2b"); // ceiling beam
  r(0, 40, SHOP_W, 6, "#a87a44"); // wainscot
  r(0, 40, SHOP_W, 1, "#c89a60");
  shopPlanks(r, 46, 44, "#c89a60", "#b0844c");
  r(0, 46, SHOP_W, 1, "#8b5a2b");
  r(54, 52, 52, 36, "#b8432f"); // a welcome rug
  r(56, 54, 48, 32, "#c85a3a");
  r(58, 56, 44, 28, "#b8432f");
  for (const x of [20, 80, 140]) shopLamp(r, x, "#f8e08a");
  for (const id of ["fish", "household", "farm", "reptiles", "mythical"]) drawShopArch(r, SHOP_SPOTS[id], id, open[id]);
  drawOrdersCorner(r, SHOP_SPOTS.orders);
  drawHabitatsCorner(r, SHOP_SPOTS.habitats);
  drawSuppliesCorner(r, SHOP_SPOTS.supplies, open.supplies);
}

// --- department rooms ---------------------------------------------------------------

// Stations in rows: `rows` is a list of [count, floor y]; stations are w x h.
function shopRows(rows, w, h) {
  const out = [];
  for (const [count, floor] of rows) {
    const gap = (SHOP_W - count * w) / (count + 1);
    for (let i = 0; i < count; i++) out.push({ x: Math.round(gap + i * (w + gap)), y: floor - h, w, h, floor });
  }
  return out;
}

const SHOP_ROOMS = {
  fish: {
    perPage: 8,
    pages: ["Tank Wall", "Deep Tanks"],
    stations: () => shopRows([[4, 46], [4, 82]], 30, 26),
    water: true,
    drawRoom(r) {
      r(0, 0, SHOP_W, SHOP_H, "#2a4a62");
      for (let x = 0; x < SHOP_W; x += 10) r(x, 0, 1, SHOP_H, "#26445a");
      for (const y of [46, 82]) {
        r(0, y, SHOP_W, 4, "#8b5a2b"); // shelves
        r(0, y, SHOP_W, 1, "#a87a44");
      }
      r(0, 86, SHOP_W, 4, "#5c3a1a");
    },
    back(r, s) {
      r(s.x - 1, s.y - 1, s.w + 2, s.h + 1, "#1e2a34"); // the tank
      r(s.x, s.y + 2, s.w, s.h - 2, "#4a9ac0");
      r(s.x, s.y + 2, s.w, 2, "#7ec4dc");
      r(s.x, s.floor - 3, s.w, 3, "#d8c28a");
      r(s.x + 3, s.floor - 9, 1, 6, "#4a8a4a");
      r(s.x + 5, s.floor - 7, 1, 4, "#5a9a4a");
      r(s.x + s.w - 6, s.floor - 6, 4, 3, "#9a948a");
    },
    front(r, s) {
      r(s.x + 1, s.y + 4, 1, s.h - 8, "rgba(255, 255, 255, 0.35)"); // glass shine
      r(s.x + 2, s.y + 4, 1, 3, "rgba(255, 255, 255, 0.35)");
      r(s.x - 1, s.y - 1, s.w + 2, 2, "#1e2a34");
    },
    area: (s) => ({ left: s.x + 1, right: s.x + s.w - 1, top: s.y + 12, bottom: s.floor - 4 }),
  },
  household: {
    perPage: 8,
    pages: ["Living Room", "Sun Room"],
    stations: () => shopRows([[4, 50], [4, 84]], 32, 24),
    drawRoom(r, page) {
      r(0, 0, SHOP_W, 40, page ? "#e8e0b0" : "#e8c8a0"); // wallpaper
      for (let x = 4; x < SHOP_W; x += 12) for (let y = 4; y < 40; y += 10) r(x, y, 2, 2, page ? "#d8cc90" : "#dcb68a");
      for (const wx of [20, 112]) {
        r(wx, 6, 28, 18, "#8b5a2b"); // windows
        r(wx + 2, 8, 24, 14, "#bfe6f0");
        r(wx + 13, 8, 2, 14, "#8b5a2b");
        r(wx + 2, 14, 24, 1, "#8b5a2b");
      }
      r(0, 34, SHOP_W, 6, "#a87a44");
      shopPlanks(r, 40, 50, "#d8a870", "#c0905a");
      r(10, 56, 140, 30, page ? "#6d9440" : "#b8432f"); // the rug
      r(12, 58, 136, 26, page ? "#7fa346" : "#c85a3a");
    },
    back(r, s) {
      r(s.x + 2, s.floor - 5, s.w - 4, 5, "#8b5a2b"); // a basket bed
      r(s.x + 1, s.floor - 6, s.w - 2, 2, "#a87a44");
      r(s.x + 4, s.floor - 4, s.w - 8, 2, "#f0dcb0");
    },
    front(r, s) {
      for (let i = s.x + 3; i < s.x + s.w - 3; i += 3) r(i, s.floor - 3, 1, 3, "#6e4420");
    },
    area: (s) => ({ left: s.x + 2, right: s.x + s.w - 2, top: s.floor - 4, bottom: s.floor - 2 }),
  },
  farm: {
    perPage: 6,
    pages: ["The Barn", "Back Barn"],
    stations: () => shopRows([[3, 50], [3, 84]], 42, 26),
    drawRoom(r) {
      r(0, 0, SHOP_W, 44, "#8e3a26"); // barn boards
      for (let x = 3; x < SHOP_W; x += 6) r(x, 0, 1, 44, "#6e2a1a");
      r(0, 0, SHOP_W, 4, "#5c2a1a");
      for (const bx of [30, 120]) {
        r(bx, 8, 14, 14, "#fbf1dc"); // windows with an X
        r(bx + 1, 9, 12, 12, "#bfe6f0");
        for (let i = 0; i < 12; i++) {
          r(bx + 1 + i, 9 + i, 1, 1, "#fbf1dc");
          r(bx + 12 - i, 9 + i, 1, 1, "#fbf1dc");
        }
      }
      r(0, 44, SHOP_W, 46, "#d8b850"); // a hay floor
      const rand = shopRand(3);
      for (let i = 0; i < 160; i++) r(rand() * SHOP_W, 44 + rand() * 46, 2, 1, i % 2 ? "#c8a030" : "#e8d070");
    },
    back(r, s) {
      r(s.x, s.y + 4, 2, s.h - 4, "#8b5a2b"); // stall posts and back rail
      r(s.x + s.w - 2, s.y + 4, 2, s.h - 4, "#8b5a2b");
      r(s.x, s.y + 8, s.w, 2, "#a87a44");
      r(s.x + s.w - 12, s.floor - 6, 9, 5, "#e8c84a"); // a hay bale
      r(s.x + s.w - 12, s.floor - 4, 9, 1, "#c8a030");
    },
    front(r, s) {
      r(s.x, s.floor - 6, s.w, 2, "#a87a44"); // the low front rail
      r(s.x, s.floor - 2, s.w, 2, "#8b5a2b");
      for (let i = s.x + 6; i < s.x + s.w; i += 10) r(i, s.floor - 6, 2, 6, "#8b5a2b");
    },
    area: (s) => ({ left: s.x + 3, right: s.x + s.w - 3, top: s.floor - 3, bottom: s.floor - 1 }),
  },
  reptiles: {
    perPage: 8,
    pages: ["Terrariums"],
    stations: () => shopRows([[4, 48], [4, 84]], 32, 26),
    drawRoom(r) {
      r(0, 0, SHOP_W, SHOP_H, "#e8d8a8"); // a warm greenhouse
      for (let x = 0; x < SHOP_W; x += 16) r(x, 0, 1, 50, "#d0bc88");
      for (const [vx, len] of [[8, 14], [30, 9], [52, 16], [86, 11], [104, 15], [128, 8], [150, 13]]) {
        r(vx, 0, 1, len, "#3a6a3a"); // hanging vines with leaves
        for (let k = 2; k < len; k += 3) r(vx + (k % 2 ? 1 : -2), k, 2, 1, "#4a8a4a");
      }
      for (const y of [48, 84]) {
        r(0, y, SHOP_W, 4, "#8b5a2b");
        r(0, y, SHOP_W, 1, "#a87a44");
      }
    },
    back(r, s) {
      r(s.x - 1, s.y - 1, s.w + 2, s.h + 1, "#3b2417"); // the terrarium
      r(s.x, s.y, s.w, s.h, "#f0e0b0");
      r(s.x, s.floor - 4, s.w, 4, "#d8b070");
      r(s.x + s.w - 9, s.floor - 7, 7, 4, "#9a948a"); // a basking rock
      r(s.x + s.w - 8, s.floor - 8, 5, 1, "#b8b2a6");
      r(s.x + 3, s.floor - 10, 1, 6, "#6d9440");
      r(s.x + s.w / 2 - 3, s.y + 1, 6, 2, "#f8e08a"); // the heat lamp
    },
    front(r, s) {
      r(s.x + 1, s.y + 3, 1, s.h - 6, "rgba(255, 255, 255, 0.5)");
      r(s.x - 1, s.y - 1, s.w + 2, 2, "#3b2417");
    },
    area: (s) => ({ left: s.x + 1, right: s.x + s.w - 1, top: s.floor - 3, bottom: s.floor - 1 }),
  },
  mythical: {
    perPage: 2,
    pages: ["The Starry Hall"],
    stations: () => shopRows([[2, 80]], 50, 40),
    drawRoom(r) {
      r(0, 0, SHOP_W, SHOP_H, "#2a1e52");
      const rand = shopRand(5);
      for (let i = 0; i < 60; i++) r(rand() * SHOP_W, rand() * 60, 1, 1, i % 4 ? "#fbf1dc" : "#f8e08a");
      for (let dy = -5; dy <= 5; dy++) {
        // a crescent moon: a disc with a sky-colored disc over it
        const half = Math.round(Math.sqrt(25 - dy * dy));
        r(125 - half, 13 + dy, half * 2, 1, "#f8f0d0");
        const cut = Math.round(Math.sqrt(Math.max(0, 16 - (dy + 1) * (dy + 1))));
        if (cut) r(128 - cut, 13 + dy, cut * 2, 1, "#2a1e52");
      }
      r(0, 62, SHOP_W, 28, "#3a2a6a");
      for (let x = 0; x < SHOP_W; x += 12) r(x, 62, 6, 28, "#44327a");
    },
    back(r, s) {
      r(s.x + 8, s.floor, s.w - 16, 8, "#8a7ab8"); // a glowing pedestal
      r(s.x + 6, s.floor - 1, s.w - 12, 2, "#b8a8e0");
      for (let k = 0; k < 6; k++) r(s.x + 12 + k, s.floor - 26 + k * 4, s.w - 24 - 2 * k, 4, "rgba(248, 224, 138, 0.05)"); // a soft glow
    },
    front() {},
    area: (s) => ({ left: s.x + 6, right: s.x + s.w - 6, top: s.floor - 2, bottom: s.floor - 1 }),
  },
  orders: {
    perPage: 4,
    pages: ["The Order Desk"],
    stations: () => shopRows([[4, 80]], 30, 22),
    drawRoom(r) {
      r(0, 0, SHOP_W, 50, "#e8d8b8"); // the back room
      r(0, 44, SHOP_W, 6, "#a87a44");
      shopPlanks(r, 50, 40, "#c89a60", "#b0844c");
      for (const [bx, by, bw] of [[6, 26, 16], [24, 30, 12], [130, 24, 18], [118, 32, 10]]) {
        r(bx, by, bw, 44 - by, "#d8b070"); // stacked parcels
        r(bx, by + 4, bw, 1, "#b88a50");
      }
      r(50, 10, 60, 24, "#8b5a2b"); // a notice board
      r(52, 12, 56, 20, "#c89a60");
      for (const [nx, ny] of [[56, 15], [72, 14], [88, 16]]) {
        r(nx, ny, 12, 14, "#fbf1dc");
        r(nx + 5, ny, 2, 2, "#b8432f");
        for (let k = ny + 4; k < ny + 13; k += 3) r(nx + 2, k, 8, 1, "#c8b898");
      }
    },
    back(r, s) {
      r(s.x + 1, s.floor - 8, s.w - 2, 8, "#d8b070"); // an open crate with straw
      r(s.x + 3, s.floor - 9, s.w - 6, 2, "#e8d070");
    },
    front(r, s) {
      r(s.x, s.floor - 6, s.w, 6, "#b88a50");
      r(s.x, s.floor - 6, s.w, 1, "#d8b070");
      r(s.x + s.w / 2 - 4, s.floor - 4, 8, 2, "#8b5a2b");
    },
    area: (s) => ({ left: s.x + 2, right: s.x + s.w - 2, top: s.floor - 5, bottom: s.floor - 4 }),
  },
};
