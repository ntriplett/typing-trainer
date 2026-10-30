// The Home's scenes (bedroom.js): the bedroom's doorways, the Dressing Room
// and the Window Nook. Everything is drawn on the 160x90 grid through a
// painter r(x, y, w, h, color) (habitats.js habitatPainter, or room.js
// canvasPx: both take grid pixels, fractions allowed).
//
// A spot is {x, y, w, h}: a clickable box, its sign on top (bedroom.js lays
// buttons over it). Rooms draw their stations; pets are drawn on top by
// bedroom.js, and you show up in the close-ups' mirrors.
//
// Needs sprites.js and backgrounds.js (the places in the Nook's window and
// postcards).

const HOUSE_W = 160;
const HOUSE_H = 90;
const HOUSE_INK = "#3b2417";

function houseBox(r, x, y, w, h, fill, edge = HOUSE_INK) {
  r(x, y, w, h, edge);
  r(x + 1, y + 1, w - 2, h - 2, fill);
}

function housePlanks(r, top, light, dark) {
  r(0, top, HOUSE_W, HOUSE_H - top, light);
  for (let y = top + 5, row = 0; y < HOUSE_H; y += 6, row++) {
    r(0, y, HOUSE_W, 1, dark);
    for (let x = row % 2 ? 10 : 24; x < HOUSE_W; x += 28) r(x, y - 5, 1, 5, dark);
  }
}

// A doorway into another room: a frame, the room beyond (`beyond(r, inner)`),
// and the door swung open against the frame.
function houseDoorway(r, { x, y, w, h }, beyond, door = "#a0703a") {
  r(x - 1, y - 2, w + 2, h + 2, HOUSE_INK);
  r(x, y - 1, w, h + 1, "#8b5a2b");
  r(x, y - 1, w, 1, "#b07a43");
  const inner = { x: x + 2, y: y + 1, w: w - 4, h: h - 1 };
  beyond(r, inner);
  r(inner.x, inner.y, inner.w, 1, "rgba(0, 0, 0, 0.25)"); // shadow under the lintel
  // the door, open toward us against the left of the frame
  r(inner.x, inner.y, 5, inner.h, HOUSE_INK);
  r(inner.x, inner.y + 1, 4, inner.h - 1, door);
  r(inner.x + 1, inner.y + 3, 2, 10, "rgba(0, 0, 0, 0.15)");
  r(inner.x + 1, inner.y + 16, 2, 10, "rgba(0, 0, 0, 0.15)");
  r(inner.x + 3, inner.y + Math.round(inner.h / 2), 1, 2, "#e8b33e");
}

// --- the bedroom: two doorways in the back wall ------------------------------------

const BEDROOM_DOORS = {
  dressing: { x: 110, y: 15, w: 22, h: 41 },
  nook: { x: 135, y: 15, w: 22, h: 41 },
};
// Wall pieces stay left of the doorways.
const BEDROOM_WALL_SPAN = [0, 108];

// A peek into the Dressing Room: lavender walls, a rail of shirts.
function glimpseDressing(r, { x, y, w, h }) {
  r(x, y, w, h, "#efe0f2");
  for (let k = x + 2; k < x + w; k += 6) r(k, y, 2, h, "#e6d2ec");
  r(x, y + h - 8, w, 8, "#c89a60");
  r(x + 5, y + 8, w - 7, 1, "#8b5a2b");
  ["#c8423a", "#4a7ec8", "#e8b33e"].forEach((c, i) => {
    const sx = x + 7 + i * 4;
    r(sx + 1, y + 9, 1, 1, HOUSE_INK);
    r(sx, y + 10, 3, 7, c);
  });
  r(x + w - 6, y + h - 16, 4, 8, "#c8a030"); // the mirror's gold edge
}

// A peek into the Window Nook: a sunny window over a cushioned seat.
function glimpseNook(r, { x, y, w, h }, avatar) {
  r(x, y, w, h, "#dfe8cc");
  r(x, y + h - 8, w, 8, "#d0a46a");
  const win = { x: x + 7, y: y + 6, w: w - 9, h: 14 };
  r(win.x - 1, win.y - 1, win.w + 2, win.h + 2, "#f4f0e8");
  housePlaceView(r, win, avatar, 1 / 3);
  r(x + 6, y + h - 16, w - 7, 6, "#a0703a");
  r(x + 6, y + h - 18, w - 7, 3, "#5a8fc8");
}

function drawBedroomDoors(r, avatar) {
  houseDoorway(r, BEDROOM_DOORS.dressing, glimpseDressing);
  houseDoorway(r, BEDROOM_DOORS.nook, (rr, inner) => glimpseNook(rr, inner, avatar), "#8b5a2b");
}

// --- the Dressing Room ---------------------------------------------------------------

const DRESSING_SPOTS = {
  bedroom: { x: 3, y: 15, w: 18, h: 41 },
  closet: { x: 22, y: 4, w: 44, h: 52 },
  hats: { x: 67, y: 10, w: 18, h: 46 },
  accessories: { x: 87, y: 8, w: 28, h: 48 },
  mirror: { x: 120, y: 4, w: 37, h: 52 },
};

function drawDressingRoom(r, frame = 0) {
  // lavender stripes, a chair rail, plank floor and a round rug
  r(0, 0, HOUSE_W, 54, "#efe0f2");
  for (let x = 3; x < HOUSE_W; x += 10) r(x, 0, 4, 40, "#e6d2ec");
  r(0, 40, HOUSE_W, 14, "#dcc2e2");
  for (let x = 6; x < HOUSE_W; x += 20) {
    r(x, 43, 14, 8, "#d2b4da");
    r(x + 1, 44, 12, 6, "#dcc2e2");
  }
  r(0, 39, HOUSE_W, 2, "#b07a43");
  r(0, 0, HOUSE_W, 3, "#8b5a2b");
  r(0, 54, HOUSE_W, 2, "#8b5a2b");
  r(0, 55, HOUSE_W, 1, "#5c3a1a");
  housePlanks(r, 56, "#c89a60", "#b0844c");
  r(46, 72, 68, 14, "#a8406e");
  r(42, 75, 76, 8, "#a8406e");
  r(48, 73, 64, 12, "#d0608a");
  r(44, 76, 72, 6, "#d0608a");
  r(56, 77, 48, 4, "#e895ae");

  // the way back
  houseDoorway(r, DRESSING_SPOTS.bedroom, (rr, { x, y, w, h }) => {
    rr(x, y, w, h, "#f4ead2");
    for (let k = x + 1; k < x + w; k += 8) rr(k, y, 3, h, "#ead8b4");
    rr(x, y + h - 8, w, 8, "#a0703a");
    rr(x + 6, y + h - 15, w - 6, 8, "#4a7ec8"); // the end of your bed
    rr(x + 6, y + h - 15, w - 6, 2, "#6aa0e8");
  });

  // the closet, both doors open: shirts on a rail, shoes and folded pants below
  r(23, 3, 42, 3, HOUSE_INK);
  r(24, 3, 40, 2, "#b07a43");
  houseBox(r, 25, 6, 38, 50, "#a0703a");
  r(28, 9, 32, 44, "#4a2e18");
  r(28, 9, 32, 2, "#3a2210");
  r(28, 12, 32, 1, "#d8d0c0");
  ["#c8423a", "#4a7ec8", "#e8b33e", "#5a9a45", "#e87aa8", "#f4f0e8"].forEach((c, i) => {
    const x = 29 + i * 5;
    r(x + 1, 12, 2, 1, "#8a8278");
    r(x, 13, 5, 2, c);
    r(x + 1, 15, 3, 9 + (i % 2) * 2, c);
    r(x + 2, 13, 1, 1, HOUSE_INK);
    r(x + 3, 15, 1, 9 + (i % 2) * 2, "rgba(0, 0, 0, 0.15)");
  });
  r(28, 33, 32, 1, "#8b5a2b");
  [["#c8423a", 30], ["#3b2417", 41], ["#e8c03a", 51]].forEach(([c, x]) => {
    r(x, 30, 3, 3, c);
    r(x + 4, 30, 3, 3, c);
    r(x, 32, 7, 1, "rgba(0, 0, 0, 0.2)");
  });
  r(28, 44, 32, 1, "#8b5a2b");
  [["#4a6aa0", 29], ["#6b4a2e", 39], ["#3a3640", 49]].forEach(([c, x]) => {
    r(x, 38, 9, 6, c);
    r(x, 40, 9, 1, "rgba(0, 0, 0, 0.2)");
  });
  [["#d8b070", 30], ["#8a55c4", 42]].forEach(([c, x]) => r(x, 47, 10, 6, c)); // a basket, a box
  r(30, 47, 10, 1, "#b88a50");
  r(22, 8, 4, 46, HOUSE_INK); // the open doors
  r(22, 9, 3, 44, "#b07a43");
  r(22, 12, 2, 16, "#a0703a");
  r(22, 32, 2, 16, "#a0703a");
  r(62, 8, 4, 46, HOUSE_INK);
  r(63, 9, 3, 44, "#b07a43");
  r(64, 12, 2, 16, "#a0703a");
  r(64, 32, 2, 16, "#a0703a");
  r(24, 54, 2, 2, HOUSE_INK);
  r(62, 54, 2, 2, HOUSE_INK);

  // the hat stand: a straw hat, a beanie, a cap and a top hat on its pegs
  r(75, 13, 2, 41, "#5c3a1a");
  r(74, 11, 4, 3, "#8b5a2b");
  r(71, 53, 10, 2, "#5c3a1a");
  r(72, 52, 8, 1, "#8b5a2b");
  r(70, 20, 12, 1, "#5c3a1a");
  r(70, 32, 12, 1, "#5c3a1a");
  r(67, 19, 9, 1, "#c8a030");
  r(69, 15, 5, 4, "#f0d470");
  r(69, 17, 5, 1, "#c8423a");
  r(78, 15, 6, 5, "#4a7ec8");
  r(78, 17, 6, 1, "#f4f0e8");
  r(80, 13, 2, 2, "#f4f0e8");
  r(68, 28, 6, 4, "#c8423a");
  r(66, 31, 4, 1, "#a83030");
  r(69, 28, 1, 1, "#f4f0e8");
  r(79, 25, 4, 6, "#3a3640");
  r(77, 31, 8, 1, "#3a3640");
  r(79, 29, 4, 1, "#8a55c4");

  // the accessory corner: a pegboard of things to carry, a jewelry box on a chest
  houseBox(r, 88, 9, 26, 24, "#e8d3a8", "#8b5a2b");
  for (let y = 12; y < 32; y += 4) for (let x = 91; x < 112; x += 4) r(x, y, 1, 1, "#c8b088");
  for (let y = 0; y < 14; y++) r(91, 12 + y, 3, 1, y % 4 < 2 ? "#c8423a" : "#f4f0e8"); // a striped scarf
  r(91, 26, 1, 2, "#c8423a");
  r(93, 26, 1, 2, "#f4f0e8");
  r(98, 13, 1, 14, HOUSE_INK); // an umbrella
  r(96, 12, 5, 3, "#4a7ec8");
  r(95, 14, 7, 2, "#4a7ec8");
  r(98, 27, 2, 1, HOUSE_INK);
  for (let i = 0; i < 7; i++) r(103 + i, 13 + Math.round(Math.sin((i / 6) * Math.PI) * 4), 1, 1, "#e8b33e"); // a necklace
  r(106, 18, 1, 2, "#e8b33e");
  r(108, 22, 4, 6, HOUSE_INK); // a lantern
  r(109, 23, 2, 4, frame % 2 ? "#f6d465" : "#f0c030");
  r(109, 21, 2, 1, HOUSE_INK);
  r(102, 24, 4, 6, "#8a55c4"); // a storybook
  r(102, 24, 1, 6, "#5c3594");
  houseBox(r, 89, 40, 24, 15, "#b07a43");
  r(90, 46, 22, 1, HOUSE_INK);
  r(99, 43, 4, 1, "#e8b33e");
  r(99, 49, 4, 1, "#e8b33e");
  r(90, 55, 2, 1, HOUSE_INK);
  r(110, 55, 2, 1, HOUSE_INK);
  houseBox(r, 95, 35, 12, 6, "#c8423a");
  r(95, 32, 12, 4, HOUSE_INK); // its lid, propped open
  r(96, 33, 10, 2, "#a83030");
  r(97, 36, 8, 2, "#5a1a30");
  r(98, 36, 2, 1, "#e8b33e");
  r(102, 36, 1, 1, frame % 3 ? "#f4f0e8" : "#e8b33e");

  // the vanity: an oval gold mirror, dyes and a brush, and a pink stool
  r(130, 4, 16, 34, "#8a6418");
  r(128, 6, 20, 30, "#8a6418");
  r(131, 5, 14, 32, "#c8a030");
  r(129, 7, 18, 28, "#c8a030");
  r(132, 7, 12, 28, "#cfe6ee");
  r(131, 9, 14, 24, "#cfe6ee");
  r(134, 10, 1, 7, "#ffffff");
  r(136, 9, 1, 3, "#ffffff");
  r(131, 26, 14, 7, "#bcd8e2"); // the room reflected
  houseBox(r, 121, 37, 36, 4, "#a0703a");
  r(122, 37, 34, 1, "#c48a50");
  r(123, 41, 2, 14, HOUSE_INK);
  r(153, 41, 2, 14, HOUSE_INK);
  houseBox(r, 130, 41, 18, 6, "#8b5a2b");
  r(138, 43, 3, 1, "#e8b33e");
  [["#e87aa8", 138], ["#4a7ec8", 141], ["#9a5aff", 144], ["#5a9a45", 147]].forEach(([c, x], i) => {
    r(x, 32 + (i % 2), 2, 5 - (i % 2), c); // hair dyes
    r(x, 31 + (i % 2), 2, 1, HOUSE_INK);
  });
  r(123, 34, 6, 2, "#8b5a2b"); // a brush
  r(129, 35, 3, 1, "#5c3a1a");
  r(150, 34, 4, 3, "#f4f0e8"); // a little pot of cream
  r(150, 33, 4, 1, "#e87aa8");
  r(132, 49, 14, 3, HOUSE_INK);
  r(133, 49, 12, 2, "#e87aa8");
  r(133, 49, 12, 1, "#f5b8d0");
  r(134, 52, 1, 4, HOUSE_INK);
  r(143, 52, 1, 4, HOUSE_INK);
}

// --- the Window Nook -------------------------------------------------------------------

// Postcard boards, one per place group, two each side of the window.
const NOOK_BOARDS = {
  forests: { x: 22, y: 6, w: 34, h: 23 },
  water: { x: 22, y: 31, w: 34, h: 23 },
  wild: { x: 104, y: 6, w: 34, h: 23 },
  space: { x: 104, y: 31, w: 34, h: 23 },
};
const NOOK_SPOTS = {
  bedroom: { x: 3, y: 15, w: 16, h: 41 },
  ...NOOK_BOARDS,
  window: { x: 58, y: 3, w: 44, h: 52 },
  daynight: { x: 141, y: 10, w: 17, h: 30 },
};

// The place you're at (or `bg`), seen through a window or on a postcard:
// the middle of its 48x48 scene scaled by `scale`, clipped to `box`.
function housePlaceView(r, box, avatar, scale, bg = null) {
  const id = bg || (avatar && avatar.background) || "bg_meadow";
  const place = spriteFor(id);
  const night = !bg && Boolean(avatar && avatar.night);
  const ox = box.x + (box.w - 48 * scale) / 2;
  const oy = box.y + (box.h - 48 * scale) / 2;
  const clip = (x, y, w, h, c) => {
    const x0 = Math.max(ox + x * scale, box.x), y0 = Math.max(oy + y * scale, box.y);
    const x1 = Math.min(ox + (x + w) * scale, box.x + box.w), y1 = Math.min(oy + (y + h) * scale, box.y + box.h);
    if (x1 > x0 && y1 > y0) r(x0, y0, x1 - x0, y1 - y0, c);
  };
  r(box.x, box.y, box.w, box.h, "#a8d5e2");
  if (place && place.draw) place.draw(clip, night);
}

// The postcards on a board: owned places show their picture, the rest a
// faint "?". `places` is [{id, owned, current}].
function drawNookBoard(r, b, places) {
  houseBox(r, b.x, b.y, b.w, b.h, "#d8a868", "#6b4423");
  r(b.x + 1, b.y + 1, b.w - 2, 1, "#8b5a2b");
  for (const [x, y] of [[4, 5], [12, 18], [22, 9], [29, 20], [17, 3], [7, 14], [26, 15]]) r(b.x + x, b.y + y, 1, 1, "#c08a50");
  places.forEach((p, i) => {
    const x = b.x + 2 + (i % 3) * 10;
    const y = b.y + 6 + Math.floor(i / 3) * 8.5; // under a band for the board's sign
    r(x + 0.5, y + 0.5, 10, 8, "rgba(0, 0, 0, 0.25)"); // its shadow
    r(x, y, 10, 8, p.current ? "#f6d465" : "#fbf1dc");
    if (p.owned) housePlaceView(r, { x: x + 1, y: y + 1, w: 8, h: 6 }, null, 1 / 6, p.id);
    else {
      r(x + 1, y + 1, 8, 6, "#e8dcc0");
      r(x + 4, y + 2, 2, 1, "#c8b896");
      r(x + 5, y + 3, 1, 1, "#c8b896");
      r(x + 4, y + 4, 1, 1, "#c8b896");
      r(x + 4, y + 6, 1, 0.8, "#c8b896");
    }
    r(x + 4, y - 1, 2, 2, ["#c8423a", "#4a7ec8", "#e8b33e"][i % 3]); // a pin
  });
}

// `groups`: {forests: [{id, owned, current}], ...}; `night`: night is on.
function drawWindowNook(r, avatar, groups) {
  const night = Boolean(avatar && avatar.night);
  r(0, 0, HOUSE_W, 54, "#dfe8cc");
  for (let x = 5; x < HOUSE_W; x += 12) r(x, 0, 2, 54, "#d6e0c0");
  r(0, 0, HOUSE_W, 3, "#8b5a2b");
  r(0, 54, HOUSE_W, 2, "#8b5a2b");
  r(0, 55, HOUSE_W, 1, "#5c3a1a");
  housePlanks(r, 56, "#d0a46a", "#b88a50");
  r(36, 66, 88, 18, "#3f7a6a"); // a rug
  r(38, 68, 84, 14, "#5aa08a");
  for (let x = 42; x < 120; x += 8) r(x, 74, 4, 2, "#e8b33e");

  houseDoorway(r, NOOK_SPOTS.bedroom, (rr, { x, y, w, h }) => {
    rr(x, y, w, h, "#f4ead2");
    for (let k = x + 1; k < x + w; k += 8) rr(k, y, 3, h, "#ead8b4");
    rr(x, y + h - 8, w, 8, "#a0703a");
    rr(x + 5, y + 10, w - 6, 8, "#e8b33e"); // a string of lights
    rr(x + 5, y + 10, w - 6, 1, HOUSE_INK);
  }, "#8b5a2b");

  for (const [group, b] of Object.entries(NOOK_BOARDS)) drawNookBoard(r, b, groups[group] || []);

  // the big window onto wherever you are, curtains tied back, a seat below
  houseBox(r, 59, 5, 42, 34, "#f4f0e8", "#8b5a2b");
  housePlaceView(r, { x: 61, y: 7, w: 38, h: 30 }, avatar, 5 / 6);
  r(79.5, 7, 1, 30, "#f4f0e8");
  r(61, 21.5, 38, 1, "#f4f0e8");
  r(57, 38, 46, 2, "#b07a43");
  r(55, 2, 50, 2, HOUSE_INK);
  r(56, 2, 48, 1, "#b07a43");
  for (const x of [56, 98]) {
    r(x, 4, 6, 34, "#b8432f");
    r(x + 2, 4, 2, 34, "#d8604a");
    r(x, 22, 6, 2, "#e8b33e"); // tie-back
  }
  houseBox(r, 56, 44, 48, 11, "#a0703a");
  r(57, 48, 46, 1, "#8b5a2b");
  r(70, 50, 4, 1, "#e8b33e");
  r(86, 50, 4, 1, "#e8b33e");
  r(56, 41, 48, 4, HOUSE_INK);
  r(57, 41, 46, 3, "#5a8fc8");
  r(57, 41, 46, 1, "#7aaee0");
  houseBox(r, 59, 36, 9, 6, "#e8b33e");
  houseBox(r, 92, 36, 9, 6, "#e87aa8");

  // the day & night switch: a sun and a moon, the lever pointing at one
  houseBox(r, 142, 12, 15, 26, "#8b5a2b");
  r(144, 15, 11, 11, HOUSE_INK);
  r(145, 16, 9, 9, "#fbf1dc");
  r(145, 16, 4.5, 9, night ? "#e8dcc0" : "#bfe6f0");
  r(149.5, 16, 4.5, 9, night ? "#2a2c50" : "#c8c0d0");
  r(146, 19, 3, 3, "#f0c030");
  r(147, 18, 1, 5, "#f0c030");
  r(145, 20, 5, 1, "#f0c030");
  r(151, 18, 2, 4, "#f4ecc8");
  r(152, 18, 1, 1, night ? "#2a2c50" : "#c8c0d0");
  r(149, 28, 1, 8, HOUSE_INK);
  r(night ? 150 : 146, 28, 3, 2, "#c8423a");
  r(night ? 150 : 146, 28, 3, 1, "#e8604a");

  // a globe and a plant on the floor
  r(128, 72, 2, 10, "#5c3a1a");
  r(125, 82, 8, 2, "#5c3a1a");
  r(124, 61, 10, 11, HOUSE_INK);
  r(125, 62, 8, 9, "#4a8ac8");
  r(126, 63, 3, 3, "#5a9a45");
  r(130, 66, 2, 3, "#5a9a45");
  r(123, 66, 1, 6, "#c8a030");
  r(12, 70, 9, 10, "#c4673a");
  r(13, 71, 7, 1, "#a8502a");
  r(14, 60, 2, 10, "#5a9a45");
  r(17, 58, 2, 12, "#4a8a3a");
  r(11, 63, 3, 4, "#6aaa55");
  r(19, 62, 3, 4, "#6aaa55");
}
