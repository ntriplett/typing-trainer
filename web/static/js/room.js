// Room drawing (PLAN.md 11c-2, phase 5): wallpapers, floors, and
// furniture on a 160x90 pixel grid, plus the avatar and wandering pets.
// Original placeholder art. Keyed by app/catalog.py's wallpaper_*,
// flooring_*, and furniture_* ids. The bedroom page (bedroom.js) adds
// dragging; the store uses drawRoomThumb() for item thumbnails.
//
// Needs sprites.js, backgrounds.js, wardrobe.js, pet_render.js, avatar.js.

const ROOM_W = 160;
const ROOM_H = 90;
const WALL_BOTTOM = 54; // wall is y 0..53, baseboard 54..55, floor 56..89
const FLOOR_TOP = 56;

// Little flecks scattered over a floor (carpet fibers, pink fluff).
const FLOOR_FLECKS = Array.from({ length: 14 }, (_, i) => [(i * 37 + 6) % ROOM_W, FLOOR_TOP + 2 + ((i * 13) % 30)]);

// outlined box: the basic furniture brush
function box(px, x, y, w, h, fill, outline = INK) {
  px(x, y, w, h, outline);
  px(x + 1, y + 1, w - 2, h - 2, fill);
}

// --- surfaces -------------------------------------------------------------------

const WALLPAPERS = {
  wallpaper_cream(px) {
    px(0, 0, ROOM_W, WALL_BOTTOM, "#f4ead2");
    for (let x = 2; x < ROOM_W; x += 8) px(x, 0, 3, WALL_BOTTOM, "#ead8b4");
  },
  wallpaper_floral(px) {
    px(0, 0, ROOM_W, WALL_BOTTOM, "#f6e2dc");
    for (let y = 3; y < WALL_BOTTOM; y += 10) {
      for (let x = (y / 10) % 2 ? 8 : 3; x < ROOM_W; x += 10) {
        px(x, y, 3, 1, "#e87aa8");
        px(x + 1, y - 1, 1, 3, "#e87aa8");
        px(x + 1, y, 1, 1, "#e8b33e");
        px(x + 3, y + 2, 1, 1, "#7fae4a");
      }
    }
  },
  wallpaper_wood(px) {
    px(0, 0, ROOM_W, WALL_BOTTOM, "#b07a43");
    for (let x = 0; x < ROOM_W; x += 8) px(x, 0, 1, WALL_BOTTOM, "#7a5228");
    for (const [x, y] of [[4, 12], [21, 38], [44, 20], [60, 46], [75, 8], [90, 30], [108, 16], [124, 40], [141, 10], [155, 34]]) px(x, y, 2, 2, "#8b5a2b");
  },
  wallpaper_mint(px) {
    px(0, 0, ROOM_W, WALL_BOTTOM, "#d4efe4");
    for (let y = 4; y < WALL_BOTTOM; y += 8) {
      for (let x = (y / 8) % 2 ? 8 : 4; x < ROOM_W; x += 8) px(x, y, 2, 2, "#a8dcc4");
    }
  },
  wallpaper_stars(px) {
    px(0, 0, ROOM_W, WALL_BOTTOM, "#2a2c50");
    for (const [x, y] of [[5, 6], [18, 20], [30, 8], [44, 30], [57, 12], [70, 40], [83, 18], [91, 46], [12, 44], [38, 48], [64, 2], [104, 10], [117, 32], [130, 4], [142, 24], [153, 44]]) {
      px(x, y + 1, 3, 1, "#f6e27a");
      px(x + 1, y, 1, 3, "#f6e27a");
    }
  },
  wallpaper_ocean(px) {
    px(0, 0, ROOM_W, WALL_BOTTOM, "#a8dcf0");
    for (let y = 6; y < WALL_BOTTOM; y += 8) {
      for (let x = 0; x < ROOM_W; x += 6) {
        px(x, y, 3, 1, "#7cc0dc");
        px(x + 3, y - 1, 3, 1, "#7cc0dc");
      }
    }
  },
};

const FLOORINGS = {
  flooring_planks(px) {
    px(0, FLOOR_TOP, ROOM_W, ROOM_H - FLOOR_TOP, "#a0703a");
    for (let y = FLOOR_TOP + 5, row = 0; y < ROOM_H; y += 6, row++) {
      px(0, y, ROOM_W, 1, "#7a5228");
      for (let x = row % 2 ? 10 : 24; x < ROOM_W; x += 28) px(x, y - 5, 1, 5, "#7a5228");
    }
  },
  flooring_checker(px) {
    for (let y = FLOOR_TOP; y < ROOM_H; y += 8) {
      for (let x = 0; x < ROOM_W; x += 8) {
        px(x, y, 8, 8, ((x + y) / 8) % 2 ? "#3a3640" : "#f4f0e8");
      }
    }
  },
  flooring_carpet(px) {
    px(0, FLOOR_TOP, ROOM_W, ROOM_H - FLOOR_TOP, "#6b9a4a");
    for (const [x, y] of FLOOR_FLECKS) px(x, y, 2, 1, "#5a8a3a");
  },
  flooring_stone(px) {
    px(0, FLOOR_TOP, ROOM_W, ROOM_H - FLOOR_TOP, "#7a7a74");
    for (let y = FLOOR_TOP, row = 0; y < ROOM_H; y += 8, row++) {
      for (let x = row % 2 ? -6 : 0; x < ROOM_W; x += 12) px(x + 1, y + 1, 10, 6, "#9a9a94");
    }
  },
  flooring_pink(px) {
    px(0, FLOOR_TOP, ROOM_W, ROOM_H - FLOOR_TOP, "#f2b8cc");
    for (const [x, y] of FLOOR_FLECKS) px(x, y, 2, 1, "#e698b4");
  },
};

// --- furniture ------------------------------------------------------------------
// Each: {w, h, draw(px, x, y, ctx)} -- (x, y) is the top-left; ctx has
// {colors} for recolorable pieces and {avatar} for the window's view.
// flat: true draws underneath everything else on the floor (rugs).

const FURNITURE = {
  furniture_rug_round: {
    w: 30, h: 8, flat: true,
    draw(px, x, y) {
      px(x + 3, y, 24, 8, INK);
      px(x, y + 2, 30, 4, INK);
      px(x + 4, y + 1, 22, 6, "#c8423a");
      px(x + 1, y + 3, 28, 2, "#c8423a");
      px(x + 8, y + 3, 14, 2, "#e8b33e");
    },
  },
  furniture_rug_rainbow: {
    w: 32, h: 8, flat: true,
    draw(px, x, y) {
      px(x, y, 32, 8, INK);
      ["#c8423a", "#e07a2e", "#e8c03a", "#5a9a45", "#4a7ec8", "#8a55c4"].forEach((c, i) => px(x + 1, y + 1 + i, 30, 1, c));
    },
  },
  furniture_bed: {
    w: 30, h: 20,
    draw(px, x, y, { colors: [a, A] }) {
      box(px, x, y, 5, 20, "#8b5a2b"); // headboard
      box(px, x + 4, y + 8, 26, 10, a); // blanket
      px(x + 5, y + 9, 24, 2, A);
      box(px, x + 4, y + 6, 8, 5, "#f4f0e8"); // pillow
      px(x + 4, y + 17, 26, 3, "#8b5a2b"); // frame
      px(x + 4, y + 19, 2, 1, INK);
      px(x + 28, y + 19, 2, 1, INK);
    },
  },
  furniture_desk: {
    w: 24, h: 18,
    draw(px, x, y) {
      box(px, x, y + 4, 24, 4, "#a0703a"); // top
      box(px, x + 1, y + 7, 9, 11, "#8b5a2b"); // drawers
      px(x + 4, y + 10, 3, 1, INK);
      px(x + 4, y + 14, 3, 1, INK);
      px(x + 21, y + 7, 2, 11, INK); // leg
      box(px, x + 13, y, 8, 5, "#3a3640"); // little computer
      px(x + 14, y + 1, 6, 3, "#6fe0f0");
    },
  },
  furniture_chair: {
    w: 10, h: 18,
    draw(px, x, y) {
      box(px, x + 1, y, 8, 9, "#a0703a");
      box(px, x, y + 8, 10, 3, "#8b5a2b");
      px(x + 1, y + 11, 2, 7, INK);
      px(x + 7, y + 11, 2, 7, INK);
    },
  },
  furniture_bookshelf: {
    w: 18, h: 28,
    draw(px, x, y) {
      box(px, x, y, 18, 28, "#8b5a2b");
      for (const sy of [8, 17]) px(x + 1, y + sy, 16, 1, INK);
      const books = ["#c8423a", "#4a7ec8", "#e8c03a", "#5a9a45", "#8a55c4", "#e07a2e"];
      for (const [sy, n] of [[2, 6], [11, 5], [20, 6]]) {
        for (let i = 0; i < n; i++) px(x + 2 + i * 2 + (i > 2 ? 1 : 0), y + sy + (i % 2), 2, 6 - (i % 2), books[(i + sy) % books.length]);
      }
    },
  },
  furniture_dresser: {
    w: 20, h: 20,
    draw(px, x, y) {
      box(px, x, y, 20, 18, "#b07a43");
      for (const dy of [5, 11]) px(x + 1, y + dy, 18, 1, INK);
      for (const dy of [2, 8, 14]) px(x + 8, y + dy, 4, 1, "#e8b33e");
      px(x + 1, y + 18, 2, 2, INK);
      px(x + 17, y + 18, 2, 2, INK);
    },
  },
  furniture_toy_chest: {
    w: 18, h: 12,
    draw(px, x, y) {
      box(px, x, y, 18, 4, "#c8423a");
      box(px, x, y + 3, 18, 9, "#4a7ec8");
      px(x + 7, y + 3, 4, 3, "#e8b33e");
      px(x + 3, y - 2, 3, 2, "#e8c03a"); // a peeking ball
    },
  },
  furniture_lamp: {
    w: 8, h: 22,
    draw(px, x, y) {
      box(px, x, y, 8, 6, "#f6d465");
      px(x + 3, y + 6, 2, 14, INK);
      box(px, x + 1, y + 19, 6, 3, "#8b5a2b");
    },
  },
  furniture_plant: {
    w: 10, h: 16,
    draw(px, x, y) {
      for (const [lx, ly, w, h] of [[1, 0, 3, 7], [6, 1, 3, 6], [3, 2, 4, 6]]) px(x + lx, y + ly, w, h, "#5a9a45");
      px(x + 4, y + 3, 1, 5, "#3f7030");
      box(px, x + 1, y + 8, 8, 8, "#c4673a");
      px(x + 2, y + 9, 6, 1, "#a8502a");
    },
  },
  furniture_teddy: {
    w: 10, h: 11,
    draw(px, x, y) {
      box(px, x + 1, y, 3, 3, "#a0703a"); // ears
      box(px, x + 6, y, 3, 3, "#a0703a");
      box(px, x + 2, y + 1, 6, 5, "#a0703a"); // head
      px(x + 3, y + 3, 1, 1, INK);
      px(x + 6, y + 3, 1, 1, INK);
      box(px, x + 1, y + 5, 8, 6, "#a0703a"); // body
      px(x + 3, y + 7, 4, 3, "#e8c79a");
    },
  },
  furniture_beanbag: {
    w: 16, h: 11,
    draw(px, x, y) {
      px(x + 3, y, 10, 11, INK);
      px(x, y + 4, 16, 7, INK);
      px(x + 4, y + 1, 8, 9, "#8a55c4");
      px(x + 1, y + 5, 14, 5, "#8a55c4");
      px(x + 5, y + 2, 3, 2, "#b48ae6");
    },
  },
  furniture_pet_bed: {
    w: 18, h: 7,
    draw(px, x, y) {
      box(px, x, y, 18, 7, "#c8423a");
      px(x + 2, y + 1, 14, 3, "#f4f0e8");
    },
  },
  furniture_aquarium: {
    w: 20, h: 22,
    draw(px, x, y) {
      box(px, x, y, 20, 13, "#6fc0e0");
      px(x + 1, y + 1, 18, 2, "#a8dcf0");
      px(x + 4, y + 6, 3, 2, "#e07a2e"); // fish
      px(x + 12, y + 8, 3, 2, "#e8c03a");
      px(x + 15, y + 4, 1, 8, "#3f9a5a"); // weed
      px(x + 1, y + 11, 18, 1, "#e0c890");
      box(px, x + 1, y + 12, 18, 10, "#8b5a2b"); // stand
    },
  },
  furniture_rocket: {
    w: 10, h: 18,
    draw(px, x, y) {
      px(x + 4, y, 2, 2, INK);
      box(px, x + 2, y + 1, 6, 13, "#f4f0e8");
      px(x + 4, y + 4, 2, 2, "#4a7ec8"); // porthole
      px(x + 3, y + 2, 4, 2, "#c8423a");
      box(px, x, y + 10, 3, 6, "#c8423a"); // fins
      box(px, x + 7, y + 10, 3, 6, "#c8423a");
      px(x + 3, y + 14, 4, 2, "#e07a2e"); // flame
      px(x + 4, y + 16, 2, 2, "#e8c03a");
    },
  },
  furniture_train: {
    w: 22, h: 8,
    draw(px, x, y) {
      box(px, x, y, 8, 6, "#c8423a"); // engine
      px(x + 1, y - 2, 2, 2, INK); // chimney
      box(px, x + 8, y + 1, 7, 5, "#4a7ec8");
      box(px, x + 15, y + 1, 7, 5, "#5a9a45");
      for (const wx of [1, 5, 9, 13, 16, 20]) px(x + wx, y + 6, 2, 2, INK);
    },
  },

  // --- wall pieces ---
  furniture_window: {
    w: 22, h: 18,
    draw(px, x, y, { avatar }) {
      box(px, x, y, 22, 18, "#f4f0e8");
      // the view: a slice of your current place, clipped to the glass
      const place = spriteFor((avatar && avatar.background) || "bg_meadow");
      const gx = x + 2, gy = y + 2, gw = 18, gh = 14;
      const clip = (cx, cy, w, h, c) => {
        const x0 = Math.max(cx + gx - 15, gx), y0 = Math.max(cy + gy - 6, gy);
        const x1 = Math.min(cx + gx - 15 + w, gx + gw), y1 = Math.min(cy + gy - 6 + h, gy + gh);
        if (x1 > x0 && y1 > y0) px(x0, y0, x1 - x0, y1 - y0, c);
      };
      if (place && place.draw) place.draw(clip, Boolean(avatar && avatar.night));
      px(x + 10, y + 2, 2, 14, "#f4f0e8"); // frame cross
      px(x + 2, y + 8, 18, 2, "#f4f0e8");
      px(x - 1, y + 17, 24, 2, "#b07a43"); // sill
    },
  },
  furniture_poster_star: {
    w: 12, h: 16,
    draw(px, x, y) {
      box(px, x, y, 12, 16, "#4a7ec8");
      px(x + 5, y + 3, 2, 8, "#f6d465");
      px(x + 2, y + 6, 8, 2, "#f6d465");
      px(x + 3, y + 4, 6, 6, "#f6d465");
      px(x + 2, y + 12, 8, 1, "#f4f0e8");
    },
  },
  furniture_painting: {
    w: 20, h: 14,
    draw(px, x, y) {
      box(px, x, y, 20, 14, "#e8b33e");
      px(x + 2, y + 2, 16, 10, "#a8d5e2");
      px(x + 2, y + 8, 16, 4, "#7fae4a");
      px(x + 4, y + 6, 7, 3, "#9cbf63");
      box(px, x + 12, y + 5, 4, 4, "#f4ead2"); // little house
      px(x + 12, y + 4, 4, 1, "#c8423a");
    },
  },
  furniture_clock: {
    w: 10, h: 10,
    draw(px, x, y) {
      px(x + 2, y, 6, 10, INK);
      px(x, y + 2, 10, 6, INK);
      px(x + 2, y + 1, 6, 8, "#f4f0e8");
      px(x + 1, y + 2, 8, 6, "#f4f0e8");
      px(x + 5, y + 2, 1, 4, INK); // hands
      px(x + 5, y + 5, 3, 1, INK);
    },
  },
  furniture_shelf: {
    w: 20, h: 10,
    draw(px, x, y) {
      for (const [sx, c] of [[1, "#c4673a"], [8, "#4a7ec8"], [15, "#e8c03a"]]) {
        px(x + sx + 1, y, 3, 4, "#5a9a45");
        box(px, x + sx, y + 3, 5, 5, c);
      }
      box(px, x, y + 7, 20, 3, "#8b5a2b");
    },
  },
  furniture_lights: {
    w: 44, h: 6,
    draw(px, x, y) {
      for (let i = 0; i < 44; i++) px(x + i, y + Math.round(Math.abs(Math.sin(i / 7)) * 3), 1, 1, INK);
      ["#f6d465", "#e87aa8", "#6fe0f0", "#9fd07a"].forEach((c, i) => {
        for (let lx = 3 + i * 3; lx < 44; lx += 12) {
          px(x + lx, y + Math.round(Math.abs(Math.sin(lx / 7)) * 3) + 1, 2, 2, c);
        }
      });
    },
  },
  furniture_map: {
    w: 18, h: 13,
    draw(px, x, y) {
      box(px, x, y, 18, 13, "#e8d3a8");
      px(x + 3, y + 3, 1, 1, "#8b5a2b");
      for (let i = 0; i < 8; i++) px(x + 3 + i, y + 3 + (i % 3), 1, 1, "#8b5a2b");
      px(x + 12, y + 7, 3, 1, "#c8423a"); // X
      px(x + 13, y + 6, 1, 3, "#c8423a");
    },
  },
  furniture_pennant: {
    w: 18, h: 9,
    draw(px, x, y) {
      px(x, y, 2, 9, INK);
      for (let i = 0; i < 16; i++) {
        const h = Math.max(1, 8 - Math.floor(i / 2));
        px(x + 2 + i, y + (8 - h) / 2, 1, h, i < 1 ? INK : "#c8423a");
      }
      px(x + 5, y + 4, 6, 1, "#f4f0e8");
    },
  },
};

// A furniture id -> its definition (recolorable beds: furniture_bed_<color>).
function furnitureFor(id) {
  if (FURNITURE[id]) return { def: FURNITURE[id], colors: null };
  const color = id.split("_").pop();
  const def = FURNITURE[id.slice(0, -(color.length + 1))];
  return def && CLOTH_COLORS[color] ? { def, colors: CLOTH_COLORS[color] } : null;
}

function isWallPiece(id, zones) {
  return zones ? zones[id] === "wall" : id === "furniture_window" || /poster|painting|clock|shelf|lights|map|pennant/.test(id);
}

// --- the whole room ------------------------------------------------------------

// room: /api/room's room object. scene: {avatar (the window's view, and
// night), extras: [{bottom, draw()}] (pets: drawn among the furniture by
// where their feet are), selected: placed id, shell(px): drawn on the bare
// walls before any furniture (the Home's doorways)}. Draws through `px`
// (room pixels).
function paintRoom(px, room, scene = {}) {
  (WALLPAPERS[room.wallpaper] || WALLPAPERS.wallpaper_cream)(px);
  (FLOORINGS[room.flooring] || FLOORINGS.flooring_planks)(px);
  px(0, WALL_BOTTOM, ROOM_W, 2, "#8b5a2b"); // baseboard
  px(0, WALL_BOTTOM + 1, ROOM_W, 1, "#5c3a1a");
  if (scene.shell) scene.shell(px);

  const zones = room.zones;
  const pieces = room.items.map((p) => ({ ...p, f: furnitureFor(p.item_id) })).filter((p) => p.f);
  const wall = pieces.filter((p) => isWallPiece(p.item_id, zones));
  const floor = pieces.filter((p) => !isWallPiece(p.item_id, zones));
  const ctxFor = (p) => ({ colors: p.f.colors, avatar: scene.avatar });

  for (const p of wall) p.f.def.draw(px, p.x, p.y, ctxFor(p));
  for (const p of floor.filter((p) => p.f.def.flat)) p.f.def.draw(px, p.x, p.y, ctxFor(p));

  // everything standing on the floor, back to front by where its feet are
  const standing = floor
    .filter((p) => !p.f.def.flat)
    .map((p) => ({ bottom: p.y + p.f.def.h, draw: () => p.f.def.draw(px, p.x, p.y, ctxFor(p)) }));
  standing.push(...(scene.extras || []));
  standing.sort((a, b) => a.bottom - b.bottom).forEach((s) => s.draw());

  if (scene.avatar && scene.avatar.night) px(0, 0, ROOM_W, ROOM_H, "rgba(16, 20, 52, 0.35)");

  const sel = pieces.find((p) => p.id === scene.selected);
  if (sel) {
    const { w, h } = sel.f.def;
    px(sel.x - 1, sel.y - 1, w + 2, 1, "#f6d465");
    px(sel.x - 1, sel.y + h, w + 2, 1, "#f6d465");
    px(sel.x - 1, sel.y - 1, 1, h + 2, "#f6d465");
    px(sel.x + w, sel.y - 1, 1, h + 2, "#f6d465");
  }
}

function canvasPx(canvas, gridWidth) {
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const scale = canvas.width / gridWidth;
  return (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(x * scale, y * scale, w * scale, h * scale);
  };
}

// Store thumbnails: the piece (or surface) in a little 48x48 room corner.
function drawRoomThumb(canvas, itemId) {
  const px = canvasPx(canvas, 48);
  // room pixels at half size, the floor reaching the bottom edge
  const big = (x, y, w, h, c) => px(x / 2, (y + 6) / 2, w / 2, h / 2, c);
  const wallpaper = WALLPAPERS[itemId] ? itemId : "wallpaper_cream";
  const flooring = FLOORINGS[itemId] ? itemId : "flooring_planks";
  px(0, 0, 48, 48, "#f4ead2");
  WALLPAPERS[wallpaper](big);
  FLOORINGS[flooring](big);
  big(0, WALL_BOTTOM, ROOM_W, 2, "#8b5a2b");
  const f = furnitureFor(itemId);
  if (f) {
    const { w, h } = f.def;
    const wallPiece = isWallPiece(itemId);
    const x = Math.round((48 - w) / 2);
    const y = wallPiece ? Math.round((28 - h) / 2) + 2 : Math.min(45 - h, 34);
    f.def.draw(px, x, y, { colors: f.colors, avatar: null });
  }
}
