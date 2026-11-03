// Pictures for Wanderpaw's shop items and whatever else is in your bag, on a
// 16x16 grid through a painter r(x, y, w, h, color), as cached images for
// lists and pop-ups. Things without a picture of their own get a little bundle.

function itemDisc(r, cx, cy, rad, color) {
  for (let dy = -rad; dy <= rad; dy++) {
    const half = Math.sqrt(Math.max(0, rad * rad - dy * dy));
    if (half >= 0.4) r(cx - half, cy + dy, half * 2, 1, color);
  }
}

function itemBottle(r, color, light, tall = false) {
  const top = tall ? 2 : 4;
  r(6, top, 4, 2, "#c8a878"); // the cork
  r(6.5, top + 2, 3, 2, "#d8e8f0");
  itemDisc(r, 8, tall ? 10 : 11, tall ? 5 : 4, color);
  itemDisc(r, 7, tall ? 9 : 10, 1.5, light);
  r(5, tall ? 7 : 9, 1, 1, "#ffffff");
}

const ITEM_ART = {
  "Mana Drop": (r) => {
    for (let k = 0; k < 5; k++) r(8 - k * 0.5, 2 + k, k + 1, 1, "#3a7fc8");
    itemDisc(r, 8, 10, 4, "#3a7fc8");
    itemDisc(r, 7, 9, 1.5, "#8ac0f0");
  },
  "Full Mana Potion": (r) => itemBottle(r, "#2a5fb8", "#6aa8f0", true),
  "Ward Potion": (r) => {
    r(7, 1, 2, 14, "#b8c8d8");
    itemDisc(r, 8, 7, 5.5, "#7ac8a8");
    itemDisc(r, 8, 7, 4, "#a8e8c8");
    r(7, 4, 2, 6, "#ffffff");
    r(5, 6, 6, 2, "#ffffff");
  },
  "Mender's Feather": (r) => {
    for (let k = 0; k < 11; k++) {
      const w = Math.sin((k / 11) * Math.PI) * 5 + 1;
      r(9 - k * 0.4 - w / 2, 1 + k, w, 1, k % 3 ? "#f4a0b8" : "#f8c8d4");
    }
    for (let k = 0; k < 5; k++) r(5.4 - k * 0.3, 11 + k, 1, 1, "#8b5a2b");
  },
  "Energy Tonic": (r) => {
    itemBottle(r, "#4f8f2a", "#a8d870");
    r(7, 9, 2, 1, "#f8e08a");
    r(8, 10, 2, 1, "#f8e08a");
    r(7, 11, 2, 1, "#f8e08a");
  },
  "Sneak Cloak": (r) => {
    for (let k = 0; k < 11; k++) r(8 - (2 + k * 0.45), 3 + k, 2 * (2 + k * 0.45), 1, k % 4 === 3 ? "#3a3a5a" : "#4a4a78");
    itemDisc(r, 8, 3, 2.5, "#3a3a5a");
    r(7, 3, 2, 1, "#14141e");
  },
  "Treasure Map": (r) => {
    r(2, 3, 12, 10, "#e8d4a0");
    r(2, 3, 1, 10, "#c8a878");
    r(13, 3, 1, 10, "#c8a878");
    for (const [x, y] of [[4, 11], [6, 10], [8, 9], [9, 7]]) r(x, y, 1, 1, "#8b5a2b");
    r(10, 4, 1, 1, "#c8382a");
    r(12, 4, 1, 1, "#c8382a");
    r(11, 5, 1, 1, "#c8382a");
    r(10, 6, 1, 1, "#c8382a");
    r(12, 6, 1, 1, "#c8382a");
  },
  "Lucky Charm": (r) => {
    for (const [x, y] of [[5.5, 5.5], [10.5, 5.5], [5.5, 9.5], [10.5, 9.5]]) itemDisc(r, x, y, 2.5, "#4faf4a");
    itemDisc(r, 8, 7.5, 1.5, "#2a7f2a");
    r(8, 9, 1, 6, "#2a7f2a");
  },
  "Forager's Satchel": (r) => {
    r(3, 7, 10, 7, "#a87a44");
    r(3, 7, 10, 3, "#8b5a2b");
    r(7, 9, 2, 2, "#e8b33e");
    for (let k = 0; k < 8; k++) r(4 + k * 1, 6 - Math.sin((k / 7) * Math.PI) * 4, 1, 1, "#6e4420");
  },
  "Fine Fishing Rod": (r) => {
    for (let k = 0; k < 12; k++) r(2 + k, 14 - k, 1, 1, k < 4 ? "#6e4420" : "#a87a44");
    r(13, 3, 1, 8, "#d8e8f0");
    r(12, 10, 3, 2, "#e84a4a");
    r(12, 12, 3, 1, "#ffffff");
  },
  "Sturdy Boots": (r) => {
    r(4, 3, 5, 9, "#8b5a2b");
    r(4, 10, 9, 3, "#8b5a2b");
    r(4, 13, 10, 1, "#3b2417");
    r(4, 3, 5, 1, "#a87a44");
    for (const y of [5, 7, 9]) r(5, y, 3, 0.7, "#e8d4a0");
  },
  "Way-Home Charm": (r) => {
    itemDisc(r, 8, 9, 5, "#e8b33e");
    itemDisc(r, 8, 9, 3.5, "#f8e08a");
    r(7, 2, 2, 2, "#c89428");
    for (let k = 0; k < 3; k++) r(8 - k, 6 + k, 2 * k + 1, 1, "#b8432f"); // a little roof
    r(6, 9, 5, 3, "#8b5a2b");
    r(8, 10, 1, 2, "#3b2417");
  },
  "Type Tome": (r) => {
    r(3, 2, 10, 12, "#7a3ab8");
    r(3, 2, 2, 12, "#5a2a8a");
    r(5, 13, 8, 1, "#e8dcc0");
    itemDisc(r, 9, 7, 2.5, "#f8e08a");
    r(8.5, 5, 1, 4, "#ffffff");
  },
  "Training Weight": (r) => {
    r(3, 7, 10, 2, "#8a94a4");
    r(1, 4, 2, 8, "#3b3b4a");
    r(13, 4, 2, 8, "#3b3b4a");
    r(3, 5, 2, 6, "#5a5a6a");
    r(11, 5, 2, 6, "#5a5a6a");
  },
  "Friendship Token": (r) => {
    itemDisc(r, 8, 8, 6, "#e8b33e");
    itemDisc(r, 8, 8, 4.5, "#f8d870");
    for (const [x, y, w] of [[5, 6, 2], [9, 6, 2], [5, 7, 6], [6, 8, 4], [7, 9, 2]]) r(x, y, w, 1, "#e84a6a");
  },
};

// Small pictures for the rest of the game's ideas: one picture for one idea,
// everywhere it shows. The move cards' own icons are in wander_moves.js.
const IDEA_ART = {
  Bag: (r) => {
    r(6, 2, 4, 2, "#7a2a1e");
    r(5, 3, 1, 3, "#7a2a1e");
    r(10, 3, 1, 3, "#7a2a1e");
    r(3, 5, 10, 9, "#b8432f");
    r(3, 5, 10, 1, "#7a2a1e");
    r(5, 8, 6, 4, "#d8604a");
    r(7, 9, 2, 1, "#f8d870");
    r(3, 13, 10, 1, "#7a2a1e");
  },
  Book: (r) => {
    r(2, 1, 12, 14, "#d8f4ee");
    r(2, 1, 3, 14, "#14504e");
    r(2, 13, 12, 2, "#14504e");
    r(7, 4, 5, 2, "#14504e");
    r(7, 8, 5, 2, "#14504e");
  },
  "Lost turn": (r) => {
    // a big Z and a little one
    for (const [x, y, w] of [[1, 6, 9], [1, 7, 9], [6, 8, 4], [4, 10, 4], [2, 12, 4], [1, 14, 9], [1, 15, 9]]) r(x, y, w, x === 6 || x === 4 || x === 2 ? 2 : 1, "#7a3ab8");
    for (const [x, y, w] of [[10, 1, 6], [13, 2, 3], [12, 3, 2], [11, 4, 2], [10, 5, 6]]) r(x, y, w, 1, "#7a3ab8");
  },
  Softer: (r) => {
    r(7, 2, 2, 8, "#3a7fc8");
    for (let k = 0; k < 4; k++) r(4 + k, 9 + k, 8 - 2 * k, 1, "#3a7fc8");
  },
  Focus: (r) => {
    itemDisc(r, 8, 8, 6, "#c8382a");
    itemDisc(r, 8, 8, 4, "#fbf1dc");
    itemDisc(r, 8, 8, 2, "#c8382a");
  },
  Boss: (r) => {
    r(2, 8, 12, 6, "#e8b33e");
    r(2, 12, 12, 2, "#b8842a");
    for (const x of [2, 7, 12]) r(x, 4, 2, 5, "#e8b33e");
    for (const x of [4, 10]) r(x, 6, 2, 3, "#e8b33e");
    for (const x of [2, 7, 12]) r(x, 3, 2, 1, "#f8e08a");
    r(7, 9, 2, 2, "#c8382a");
  },
  First: (r) => {
    itemDisc(r, 8, 9, 5, "#e8b33e");
    itemDisc(r, 8, 9, 3.5, "#f8d870");
    r(7, 6, 2, 6, "#8b5a2b");
    r(6, 7, 1, 1, "#8b5a2b");
    r(4, 1, 3, 3, "#3a7fc8");
    r(9, 1, 3, 3, "#c8382a");
  },
  Key: (r) => {
    r(2, 4, 12, 9, "#d8d0c0");
    r(2, 4, 12, 1, "#fbf1dc");
    r(2, 12, 12, 1, "#8a8478");
    r(6, 7, 4, 3, "#55504a");
  },
  Round: (r) => {
    for (let k = 0; k < 28; k++) {
      const a = (k / 28) * Math.PI * 1.7;
      r(8 + Math.cos(a) * 5, 8 + Math.sin(a) * 5, 1.5, 1.5, "#2a8a8a");
    }
    r(11, 2, 3, 3, "#2a8a8a");
  },
  Tired: (r) => {
    r(3, 7, 9, 5, "#9a948a");
    r(12, 8, 1, 3, "#9a948a");
    r(4, 8, 2, 3, "#c8382a");
  },
};

function itemFallback(r) {
  itemDisc(r, 8, 10, 5, "#c8a878");
  r(6, 3, 4, 3, "#c8a878");
  r(6, 6, 4, 1, "#8b5a2b");
  itemDisc(r, 7, 9, 1.5, "#e0c8a0");
}

const ITEM_ICONS = new Map();

// An <img> tag for a thing in your bag or on a shop's shelf.
function itemIcon(name, size = 32) {
  if (!ITEM_ICONS.has(name)) {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const ctx = c.getContext("2d");
    (ITEM_ART[name] || IDEA_ART[name] || itemFallback)((x, y, w, h, color) => {
      ctx.fillStyle = color;
      ctx.fillRect(Math.round(x * 4), Math.round(y * 4), Math.ceil(w * 4), Math.ceil(h * 4));
    });
    ITEM_ICONS.set(name, c.toDataURL());
  }
  return `<img class="wander-item-icon" src="${ITEM_ICONS.get(name)}" width="${size}" height="${size}" alt="">`;
}
