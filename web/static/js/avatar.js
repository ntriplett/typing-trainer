// Standalone avatar renderer (PLAN.md Section 11c). Page-agnostic on
// purpose: the header, the store, and future games all call
// drawAvatar() with the same {slot: item_id} shape /api/me returns, so a
// game can show the player's dressed avatar without knowing anything
// about the store.
//
// Needs sprites.js, backgrounds.js, wardrobe.js, and pets.js loaded first.

// Back-to-front draw order. Worn slots match app/catalog.py's
// WEARABLE_SLOTS; the hair_back/body/hair_front/bow layers come from the
// learner's appearance rather than an item.
const AVATAR_LAYERS = ["background", "hair_back", "body", "shoes", "pants", "shirt", "hair_front", "bow", "accessory", "hat", "pet"];
const APPEARANCE_LAYERS = { hair_back: hairBackSprite, body: bodySprite, hair_front: hairFrontSprite, bow: bowSprite };
const DEFAULT_APPEARANCE = { gender: "boy", skin: "light", hair_color: "brown", hair_style: "short", eye_color: "brown" };

// Draws `equipped` (/api/me's avatar: {slot: item_id, appearance: {...}})
// onto `canvas` (any size; it's scaled from the 48x48
// pixel grid, so give it a multiple of 48 for crisp pixels).
//
// opts.pose: only "idle" exists today. Games will add poses (e.g.
//   "casting") by offsetting/swapping per-layer sprites here.
// opts.frame: animation frame; idle bobs the character 1px on odd frames.
// opts.background: false to skip the background layer (e.g. drawing the
//   avatar into a game scene that has its own).
function drawAvatar(canvas, equipped, opts = {}) {
  const ctx = canvas.getContext("2d");
  const scale = canvas.width / AVATAR_SIZE;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const px = (x, y, w, h, color) => {
    ctx.fillStyle = color;
    ctx.fillRect(x * scale, y * scale, w * scale, h * scale);
  };
  paintAvatar(px, equipped, opts);
}

// The same drawing through any pixel-fill function, so other scenes (the
// bedroom, future games) can paint the avatar wherever they like.
// opts.pets: false to leave pets out (a scene that draws them itself).
function paintAvatar(px, equipped, opts = {}) {
  const { pose = "idle", frame = 0, background = true, pets = true } = opts;
  const bob = pose === "idle" && frame % 2 === 1 ? 1 : 0;

  const look = equipped.appearance || DEFAULT_APPEARANCE;
  for (const slot of AVATAR_LAYERS) {
    if (slot === "background" && !background) continue;
    if (slot === "pet") {
      // pets stay planted while the character bobs
      if (pets) for (const pet of equipped.pets || []) drawGrid(px, petSprite(pet), 0);
      continue;
    }
    const sprite = APPEARANCE_LAYERS[slot] ? APPEARANCE_LAYERS[slot](look) : spriteFor(equipped[slot]);
    if (!sprite) continue;
    if (sprite.draw) {
      sprite.draw(px, Boolean(equipped.night));
    } else {
      drawGrid(px, sprite, slot === "background" ? 0 : bob);
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
