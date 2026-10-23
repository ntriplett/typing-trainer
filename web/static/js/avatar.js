// Standalone avatar renderer (PLAN.md Section 11c). Page-agnostic on
// purpose: the header, the store, and future games all call
// drawAvatar() with the same {slot: item_id} shape /api/me returns, so a
// game can show the player's dressed avatar without knowing anything
// about the store.
//
// Needs sprites.js loaded first.

// Back-to-front draw order -- matches app/store.py's SLOTS.
const AVATAR_SLOTS = ["background", "body", "shoes", "pants", "shirt", "hat", "pet"];

// Draws `equipped` onto `canvas` (any size; it's scaled from the 48x48
// pixel grid, so give it a multiple of 48 for crisp pixels).
//
// opts.pose: only "idle" exists today. Games will add poses (e.g.
//   "casting") by offsetting/swapping per-layer sprites here.
// opts.frame: animation frame; idle bobs the character 1px on odd frames.
// opts.background: false to skip the background layer (e.g. drawing the
//   avatar into a game scene that has its own).
function drawAvatar(canvas, equipped, opts = {}) {
  const { pose = "idle", frame = 0, background = true } = opts;
  const ctx = canvas.getContext("2d");
  const scale = canvas.width / AVATAR_SIZE;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const bob = pose === "idle" && frame % 2 === 1 ? 1 : 0;
  const px = (x, y, w, h, color) => {
    ctx.fillStyle = color;
    ctx.fillRect(x * scale, y * scale, w * scale, h * scale);
  };

  for (const slot of AVATAR_SLOTS) {
    if (slot === "background" && !background) continue;
    const sprite = SPRITES[equipped[slot]];
    if (!sprite) continue;
    if (sprite.draw) {
      sprite.draw(px);
    } else {
      // Pets stay planted; the character (body + clothes) bobs.
      drawGrid(px, sprite, slot === "pet" || slot === "background" ? 0 : bob);
    }
  }
}

function drawGrid(px, sprite, dy) {
  sprite.rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      const color = sprite.palette[row[x]];
      if (color) px(sprite.x + x, sprite.y + y + dy, 1, 1, color);
    }
  });
}

// Convenience for pages: a canvas element already sized and classed.
function makeAvatarCanvas(sizePx, className = "avatar-canvas") {
  const canvas = document.createElement("canvas");
  canvas.width = sizePx;
  canvas.height = sizePx;
  canvas.className = className;
  return canvas;
}
