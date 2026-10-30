// Pixel art for the home page's tiles, drawn in code like sprites.js.
// Each icon is {w, h, draw(px, frame, me)}; drawHomeIcon() centers it on a
// canvas at a whole-pixel scale. `frame` ticks for small idle animations
// (blinking keys, an arcade screen); `me` is /api/me (the pet tile draws
// your own pet when one comes along).
//
// Needs sprites.js (INK, sym), avatar.js (drawGrid), pet_render.js, and (for the
// garden) veggies.js loaded first.

const HOME_INK = INK;

function gridIcon(rows, palette) {
  return (px, dx = 0, dy = 0) => drawGrid(px, { x: dx, y: dy, rows, palette }, 0);
}

// An outlined box: ink edge, `fill` inside.
function box(px, x, y, w, h, fill) {
  px(x, y, w, h, HOME_INK);
  px(x + 1, y + 1, w - 2, h - 2, fill);
}

const BIG_QUESTION = [
  "..oooo..",
  ".oooooo.",
  "oo....oo",
  "......oo",
  ".....oo.",
  "....oo..",
  "...oo...",
  "...oo...",
  "........",
  "...oo...",
  "...oo...",
];

const ARCADE_ROWS = [
  "..oooooooooooo..",
  ".oyyyyyyyyyyyyo.",
  ".oyYyYyYyYyYyyo.",
  ".oooooooooooooo.",
  ".oppppppppppppo.",
  ".opoooooooooopo.",
  ".oponnnnnnnnopo.",
  ".oponnnnnnnnopo.",
  ".oponnnnnnnnopo.",
  ".oponnnnnnnnopo.",
  ".oponnnnnnnnopo.",
  ".opoooooooooopo.",
  ".oppppppppppppo.",
  "oooooooooooooooo",
  "oPPPoPPPPPrPPbPo",
  "oPPPoPPPPPPPPPPo",
  "oooooooooooooooo",
  ".oppppppppppppo.",
  ".oppppPyyPppppo.",
  ".oppppppppppppo.",
  ".oppppppppppppo.",
  ".oooooooooooooo.",
];

// 3x5 pixel letters that float up off the keyboard.
const TINY_LETTERS = {
  f: ["ooo", "o..", "oo.", "o..", "o.."],
  j: ["..o", "..o", "..o", "o.o", ".o."],
  d: ["oo.", "o.o", "o.o", "o.o", "oo."],
  k: ["o.o", "oo.", "o..", "oo.", "o.o"],
};

function tinyLetter(px, letter, x, y, color) {
  TINY_LETTERS[letter].forEach((row, dy) => {
    [...row].forEach((c, dx) => c === "o" && px(x + dx, y + dy, 1, 1, color));
  });
}

// The home tile's row of machines: body colors, left to right.
const ARCADE_ROW = [
  { p: "#d9822b", P: "#8b4a1a" },
  { p: "#3f9a8a", P: "#26685c" },
  {},
  { p: "#b8432f", P: "#7a2a1a" },
  { p: "#3f7fd0", P: "#2a5a9a" },
];

// An arcade cabinet; `colors` recolors the body, `screen()` draws on its screen.
function cabinet(px, frame, colors, screen) {
  const blink = frame % 2 === 0;
  gridIcon(ARCADE_ROWS, {
    o: HOME_INK, y: "#f6d465", Y: blink ? "#e8b33e" : "#fbf1dc", p: "#8a55c4", P: "#5c3594",
    n: "#22202e", r: "#b8432f", b: "#3f7fd0", ...colors,
  })(px);
  screen();
}

const HOME_ICONS = {
  // A cozy desk by the window: a monitor typing away, the keyboard with F
  // and J glowing, cocoa, a lamp, a sticker chart, and letters drifting up
  // out of the screen. Leaves fall past the window.
  practice: {
    w: 96,
    h: 72,
    draw(px, frame) {
      const glow = frame % 2 === 0;
      // window: sky, a hill, an autumn tree, falling leaves
      box(px, 4, 4, 28, 27, "#a8d5e2");
      px(21, 8, 6, 2, "#fbf1dc");
      px(22, 7, 3, 1, "#fbf1dc");
      px(5, 24, 26, 6, "#8fb85a");
      px(9, 23, 18, 1, "#8fb85a");
      px(5, 28, 26, 2, "#6b8e3a");
      px(11, 17, 2, 8, "#6b4423");
      px(7, 10, 10, 7, "#d9822b");
      px(8, 9, 8, 1, "#d9822b");
      px(8, 17, 8, 1, "#d9822b");
      px(9, 11, 3, 2, "#f0a050");
      px(13, 14, 3, 2, "#b8432f");
      [[22, 0, "#e8822b"], [26, 5, "#b8432f"], [9, 3, "#e8b33e"]].forEach(([x, phase, color]) => {
        const t = (frame + phase) % 10;
        px(x + (t % 2), 11 + t * 2, 1, 1, color);
      });
      px(17, 5, 2, 25, "#fbf1dc");
      px(5, 17, 26, 2, "#fbf1dc");
      px(2, 31, 32, 3, HOME_INK);
      px(3, 32, 30, 1, "#e8dcc0");
      // curtains on a rod
      px(0, 1, 36, 2, HOME_INK);
      px(1, 1, 34, 1, "#b07a43");
      for (const x of [1, 30]) {
        px(x, 3, 5, 26, HOME_INK);
        px(x + 1, 3, 3, 25, "#d8604a");
        px(x + 2, 3, 1, 25, "#b8432f");
      }
      // sticker chart, a shelf of books, a little plant
      box(px, 71, 2, 15, 13, "#fbf1dc");
      px(72, 3, 13, 2, "#3f9a8a");
      for (let i = 0; i < 12; i++) {
        px(73 + (i % 4) * 3, 6 + Math.floor(i / 4) * 3, 2, 2, i < 7 ? "#e8b33e" : "#e8dcc0");
      }
      px(66, 26, 28, 1, HOME_INK);
      px(66, 27, 28, 2, "#b07a43");
      px(66, 29, 28, 1, HOME_INK);
      px(69, 30, 2, 3, HOME_INK);
      px(89, 30, 2, 3, HOME_INK);
      let bx = 67;
      for (const [color, h] of [["#3f7fd0", 8], ["#d8483a", 10], ["#e8b33e", 7], ["#3f9a8a", 9], ["#8a55c4", 8]]) {
        px(bx, 26 - h, 4, h, HOME_INK);
        px(bx + 1, 27 - h, 2, h - 1, color);
        px(bx + 1, 28 - h, 2, 1, "#fbf1dc");
        bx += 3;
      }
      px(85, 20, 7, 6, HOME_INK);
      px(86, 21, 5, 5, "#d9822b");
      px(86, 21, 5, 1, "#f0a050");
      px(87, 14, 2, 6, "#6b8e3a");
      px(84, 16, 3, 3, "#8fb85a");
      px(89, 15, 3, 3, "#6b8e3a");
      // the monitor: letters appear one by one, then float up and away
      box(px, 36, 12, 26, 21, "#e8dcc0");
      box(px, 38, 14, 22, 15, "#22303a");
      const typed = frame % 5;
      ["f", "j", "d", "k"].slice(0, typed).forEach((letter, i) => tinyLetter(px, letter, 40 + i * 4, 17, "#9fd07a"));
      if (typed < 4) px(40 + typed * 4, 17, 2, 5, glow ? "#9fd07a" : "#22303a");
      px(40, 24, 14, 1, "#3e5a50");
      px(37, 29, 24, 3, "#d8c7a0");
      px(57, 30, 2, 1, glow ? "#9fd07a" : "#4a6627");
      px(46, 33, 6, 10, HOME_INK);
      px(47, 33, 4, 10, "#d8c7a0");
      px(40, 41, 18, 5, HOME_INK);
      px(41, 42, 16, 3, "#d8c7a0");
      [["f", 39, 0, "#d9822b"], ["j", 47, 2, "#d8483a"], ["k", 55, 4, "#3f7fd0"]].forEach(([letter, x, phase, color]) => {
        const y = 7 - ((frame + phase) % 6) * 2;
        if (y >= 0) tinyLetter(px, letter, x + ((frame + phase) % 2), y, color);
      });
      // the keyboard, home row keys F and J glowing
      box(px, 24, 37, 48, 9, "#6b4a2e");
      const key = (x, y, w, top = "#fbf1dc", side = "#d8c7a0") => {
        px(x, y, w, 1, top);
        px(x, y + 1, w, 1, side);
      };
      for (let i = 0; i < 11; i++) key(26 + i * 4, 38, 3);
      for (let i = 0; i < 10; i++) {
        if (i === 3) key(28 + i * 4, 40, 3, glow ? "#f6d465" : "#e8b33e", "#b5862a");
        else if (i === 6) key(28 + i * 4, 40, 3, glow ? "#e8b33e" : "#f6d465", "#b5862a");
        else key(28 + i * 4, 40, 3);
      }
      key(27, 42, 7);
      key(36, 42, 24);
      key(62, 42, 7);
      // cocoa (steaming) and a cup of pencils
      px(8, 38, 7, 8, HOME_INK);
      px(9, 39, 5, 6, "#3f9a8a");
      px(9, 39, 5, 1, "#7a4a2a");
      px(11, 42, 1, 1, "#fbf1dc");
      px(15, 40, 2, 1, HOME_INK);
      px(16, 40, 1, 4, HOME_INK);
      px(15, 43, 2, 1, HOME_INK);
      px(10 + (frame % 2), 35, 1, 2, "#fbf1dc");
      px(12 - (frame % 2), 34, 1, 1, "#fbf1dc");
      px(18, 36, 1, 4, "#e8b33e");
      px(18, 35, 1, 1, "#5c3a1a");
      px(20, 37, 1, 3, "#3f7fd0");
      px(17, 40, 5, 6, HOME_INK);
      px(18, 41, 3, 4, "#d8483a");
      // the lamp
      px(77, 32, 11, 5, HOME_INK);
      px(78, 33, 9, 3, "#e8b33e");
      px(78, 33, 9, 1, "#f6d465");
      px(78, 37, 9, 1, glow ? "#f6d465" : "#fbf1dc");
      px(81, 37, 2, 7, HOME_INK);
      px(77, 44, 11, 2, HOME_INK);
      px(78, 44, 9, 1, "#b5862a");
      // the desk: top, drawers on the left, a leg on the right
      px(0, 46, 96, 1, HOME_INK);
      px(0, 47, 96, 2, "#c48a50");
      px(0, 49, 96, 1, "#8b5a2b");
      px(0, 50, 96, 1, HOME_INK);
      px(4, 51, 20, 17, HOME_INK);
      px(5, 51, 18, 16, "#b07a43");
      px(5, 58, 18, 1, HOME_INK);
      px(13, 54, 3, 1, HOME_INK);
      px(13, 62, 3, 1, HOME_INK);
      px(84, 51, 4, 17, HOME_INK);
      px(85, 51, 2, 16, "#8b5a2b");
      // a rug on the floor
      px(30, 63, 46, 6, HOME_INK);
      px(31, 64, 44, 4, "#d8604a");
      px(31, 65, 44, 1, "#e8b33e");
      px(31, 67, 44, 1, "#b8432f");
    },
  },
  // A row of five machines, each its own color and game.
  arcade: {
    w: 84,
    h: 22,
    draw(px, frame) {
      ARCADE_ROW.forEach((colors, i) => {
        const dx = i * 17;
        const at = (x, y, w, h, c) => px(x + dx, y, w, h, c);
        cabinet(at, frame + i, colors, () => {
          const f = frame + i * 2;
          at(4, 10, 8, 1, "#4a6627");
          at(4 + (f % 6), 9, 1, 1, "#9fd07a");
          at(4 + ((f + 3) % 6), 6 + (i % 3), 1, 1, i % 2 ? "#f6d465" : "#ff9a7a");
        });
      });
    },
  },
  // A "?" block: a room that opens once enough letters are learned.
  mystery: {
    w: 22,
    h: 23,
    draw(px, frame) {
      const dy = frame % 2;
      const at = (x, y, w, h, c) => px(x, y + dy, w, h, c);
      at(0, 0, 22, 22, HOME_INK);
      at(1, 1, 20, 20, "#e8b33e");
      at(1, 1, 20, 2, "#f6d465");
      at(1, 1, 2, 20, "#f6d465");
      at(1, 19, 20, 2, "#b5862a");
      at(19, 1, 2, 20, "#b5862a");
      for (const [x, y] of [[3, 3], [18, 3], [3, 18], [18, 18]]) at(x, y, 1, 1, HOME_INK);
      for (const [color, off] of [["#5c3a1a", 1], ["#ffffff", 0]]) {
        BIG_QUESTION.forEach((row, y) =>
          [...row].forEach((c, x) => c === "o" && at(7 + x + off, 5 + y + off, 1, 1, color))
        );
      }
    },
  },
  // The arcade page's game cabinets, one per game.
  game_crow_patrol_v1: {
    w: 16,
    h: 22,
    draw(px, frame) {
      cabinet(px, frame, { p: "#d9822b", P: "#8b4a1a" }, () => {
        px(4, 10, 8, 1, "#4a6627");
        px(5, 9, 2, 1, "#e8822b");
        px(9, 9, 2, 1, "#e8822b");
        const x = 4 + (frame % 7);
        px(x, 6 + (frame % 2), 2, 1, "#f1e6cf");
      });
    },
  },
  game_pet_battle_v1: {
    w: 16,
    h: 22,
    draw(px, frame) {
      cabinet(px, frame, { p: "#3f9a8a", P: "#26685c" }, () => {
        px(4, 10, 8, 1, "#4a6627");
        px(5, 8 + (frame % 2), 2, 2, "#e8b33e");
        px(9, 8 + ((frame + 1) % 2), 2, 2, "#e87aa8");
        if (frame % 3 === 0) px(7, 7, 2, 1, "#fbf1dc");
      });
    },
  },
  game_farm_stand_v1: {
    w: 16,
    h: 22,
    draw(px, frame) {
      cabinet(px, frame, { p: "#b8432f", P: "#7a2a1f" }, () => {
        // a little stand: striped roof, counter, a veggie hopping on it
        for (let i = 0; i < 4; i++) px(4 + i * 2, 5, 2, 1, i % 2 ? "#fbf1dc" : "#d8283a");
        px(4, 9, 8, 2, "#8b5a2b");
        px(5, 8 - (frame % 2), 2, 1, "#e8822b");
        px(9, 8, 2, 1, "#4a7f2a");
      });
    },
  },
  // A market stall: striped awning, a hat, a flower, a jar of coins, and
  // apples on the counter.
  store: {
    w: 40,
    h: 28,
    draw(px, frame) {
      // posts
      px(2, 6, 4, 22, HOME_INK);
      px(3, 6, 2, 22, "#b07a43");
      px(34, 6, 4, 22, HOME_INK);
      px(35, 6, 2, 22, "#b07a43");
      // awning with scalloped edge
      px(0, 0, 40, 6, HOME_INK);
      for (let i = 0; i < 10; i++) {
        const red = i % 2 === 0;
        const x = i * 4;
        px(Math.max(1, x), 1, i === 0 || i === 9 ? 3 : 4, 4, red ? "#d8483a" : "#fbf1dc");
        px(Math.max(1, x), 4, i === 0 || i === 9 ? 3 : 4, 1, red ? "#a8302a" : "#e0cfae");
        px(x + 1, 6, 2, 1, red ? "#a8302a" : "#e0cfae");
        px(x, 6, 1, 1, HOME_INK);
        px(x + 3, 6, 1, 1, HOME_INK);
        px(x + 1, 7, 2, 1, HOME_INK);
      }
      // goods on a back shelf
      px(6, 15, 28, 1, HOME_INK);
      px(6, 16, 28, 1, "#8b5a2b");
      px(10, 8, 4, 5, HOME_INK);
      px(11, 9, 2, 4, "#5c3594");
      px(11, 11, 2, 1, "#e8b33e");
      px(8, 13, 8, 2, HOME_INK);
      px(9, 13, 6, 1, "#8a55c4");
      px(19, 9, 3, 3, "#e87aa8");
      px(20, 10, 1, 1, "#f6d465");
      px(20, 12, 1, 1, "#4a7f2a");
      px(18, 13, 5, 2, HOME_INK);
      px(19, 13, 3, 1, "#d9822b");
      px(25, 9, 6, 6, HOME_INK);
      px(26, 10, 4, 4, "#d8eef2");
      px(26, 12, 4, 2, "#e8b33e");
      px(27 + (frame % 2), 12, 1, 1, "#fbf1dc");
      px(26, 9, 4, 1, "#b07a43");
      // counter with apples on top and a coin sign
      for (const x of [9, 14]) {
        px(x, 16, 4, 3, HOME_INK);
        px(x + 1, 17, 2, 2, "#d8283a");
        px(x + 1, 17, 1, 1, "#ff8a7a");
        px(x + 2, 15, 1, 1, "#4a7f2a");
      }
      px(1, 19, 38, 9, HOME_INK);
      px(2, 20, 36, 2, "#c48a50");
      px(2, 22, 36, 5, "#8b5a2b");
      px(2, 24, 36, 1, "#6b4423");
      box(px, 17, 21, 6, 6, "#e8b33e");
      px(18, 22, 2, 1, "#f6d465");
      px(19, 23, 2, 2, "#b5862a");
    },
  },
  // The pets that come along napping on their cushions, a food bowl and a
  // ball between them (paw prints on the cushions until a pet comes home).
  pets: {
    w: 84,
    h: 28,
    draw(px, frame, me) {
      const cushion = (x, color, light, dark) => {
        px(x + 1, 21, 26, 7, HOME_INK);
        px(x, 22, 28, 5, HOME_INK);
        px(x + 2, 22, 24, 5, color);
        px(x + 1, 23, 26, 3, color);
        px(x + 2, 22, 24, 1, light);
        px(x + 5, 24, 18, 2, dark);
      };
      cushion(2, "#e87aa8", "#f5b8d0", "#c85a88");
      cushion(54, "#5fbfae", "#9adccf", "#3f9a8a");
      // food bowl
      px(33, 22, 9, 6, HOME_INK);
      px(34, 23, 7, 4, "#3f7fd0");
      px(34, 23, 7, 1, "#6aa0e8");
      px(35, 21, 5, 1, HOME_INK);
      px(35, 22, 5, 1, "#b07a43");
      // a ball, rolling a little
      const bx = 45 + (frame % 2);
      px(bx, 22, 6, 6, HOME_INK);
      px(bx + 1, 23, 4, 4, "#e8b33e");
      px(bx + 1, 25, 4, 1, "#d8483a");
      const pets = ((me && me.avatar && me.avatar.pets) || []).slice(0, 2);
      [2, 54].forEach((x, i) => {
        const pet = pets[i];
        if (pet) {
          // a v3 pet (pet_render.js); full size when it fits, half otherwise
          const { w, h } = petSize(pet.genes, pet.growth);
          const scale = w <= 34 && h <= 26 ? 1 : 0.5;
          drawPet(px, Math.round(x + 14 - (w * scale) / 2), 25, pet.genes, pet.growth, { frame, scale, shadow: false, faceLeft: i === 1 });
          return;
        }
        for (const [dx, dy] of [[5, 4], [8, 2], [12, 2], [15, 4]]) px(x + dx, 10 + dy, 2, 2, "#b07a43");
        px(x + 7, 15, 8, 4, "#b07a43");
        px(x + 8, 14, 6, 1, "#b07a43");
      });
    },
  },
  // A bed with a patchwork quilt, a nightstand lamp, and a picture above.
  bedroom: {
    w: 40,
    h: 26,
    draw(px, frame) {
      // picture on the wall
      box(px, 22, 1, 10, 8, "#a8d5e2");
      px(23, 6, 8, 2, "#6b8e3a");
      px(25, 4, 3, 2, "#8fb85a");
      px(29, 2, 2, 2, "#f6d465");
      // nightstand and lamp
      box(px, 0, 15, 9, 11, "#b07a43");
      px(1, 20, 7, 1, HOME_INK);
      px(4, 17, 1, 1, HOME_INK);
      px(4, 22, 1, 1, HOME_INK);
      px(1, 7, 7, 5, HOME_INK);
      px(2, 8, 5, 3, "#e87aa8");
      px(2, 8, 5, 1, "#f5b8d0");
      px(2, 11, 5, 1, frame % 4 === 0 ? "#fbf1dc" : "#f6d465");
      px(4, 12, 1, 3, HOME_INK);
      // headboard and footboard
      px(11, 5, 4, 1, HOME_INK);
      box(px, 10, 6, 6, 20, "#8b5a2b");
      px(11, 7, 1, 18, "#b07a43");
      px(36, 12, 3, 1, HOME_INK);
      box(px, 35, 13, 5, 13, "#8b5a2b");
      px(36, 14, 1, 11, "#b07a43");
      // pillow and patchwork quilt
      px(16, 12, 8, 5, HOME_INK);
      px(17, 13, 6, 3, "#fbf1dc");
      px(16, 15, 19, 8, HOME_INK);
      const patches = ["#3f9a8a", "#e8b33e", "#d8604a", "#5fbfae", "#f0a050", "#3f7fd0"];
      for (let i = 0; i < 6; i++) {
        for (let j = 0; j < 2; j++) px(22 + i * 2, 17 + j * 3, 2, 3, patches[(i + j * 3) % 6]);
      }
      px(17, 16, 5, 6, "#fbf1dc");
      px(22, 16, 13, 1, "#fbf1dc");
      // bed frame
      px(16, 23, 19, 2, HOME_INK);
      px(16, 23, 19, 1, "#b07a43");
    },
  },
  // Three plants behind a little fence; as many ripe veggies as are
  // waiting to be picked (me.garden), or empty soil before any planting.
  garden: {
    w: 42,
    h: 24,
    draw(px, frame, me) {
      const g = (me && me.garden) || { ready: 0, growing: 0 };
      const kinds = ["tomato", "carrot"];
      let ready = Math.min(10, g.ready);
      kinds.forEach((kind, i) => {
        if (i >= Math.max(g.growing, g.ready ? 1 : 0)) return drawPlant(px, i * 22, 0, null, frame);
        const here = i === 1 ? ready : Math.min(ready, 3);
        ready -= here;
        drawPlant(px, i * 22, 0, { kind, picked: 0, ready: Math.min(5, here) }, frame + i);
      });
      // the fence in front
      px(0, 21, 42, 1, HOME_INK);
      px(0, 22, 42, 1, "#d8b98a");
      for (let x = 1; x < 42; x += 6) {
        px(x, 18, 3, 6, HOME_INK);
        px(x + 1, 19, 1, 4, "#f1dcb0");
      }
    },
  },
  // An easel chart with bars climbing, a star, and a trophy beside it.
  progress: {
    w: 40,
    h: 26,
    draw(px, frame) {
      box(px, 1, 0, 27, 21, "#fbf1dc");
      for (const y of [5, 9, 13]) px(2, y, 25, 1, "#efe2c4");
      px(4, 17, 22, 1, "#8b5a2b");
      px(4, 3, 1, 15, "#8b5a2b");
      [[6, 4, "#5fbfae"], [11, 7, "#8fb85a"], [16, 10, "#e8b33e"], [21, 12, "#d9822b"]].forEach(([x, h, color], i) => {
        const grow = i === 3 && frame % 2 ? 1 : 0;
        px(x - 1, 16 - h - grow, 5, h + grow + 1, HOME_INK);
        px(x, 17 - h - grow, 3, h + grow, color);
        px(x, 17 - h - grow, 1, h + grow, "#fbf1dc80");
      });
      ["..y..", ".yyy.", "yyyyy", ".yyy.", ".y.y."].forEach((row, y) =>
        [...row].forEach((c, x) => c === "y" && px(6 + x, 3 + y - (frame % 2), 1, 1, "#e8b33e"))
      );
      for (const x of [4, 22]) {
        px(x, 21, 3, 5, HOME_INK);
        px(x + 1, 21, 1, 4, "#b07a43");
      }
      // trophy
      px(28, 12, 2, 1, HOME_INK);
      px(28, 12, 1, 4, HOME_INK);
      px(28, 15, 2, 1, HOME_INK);
      px(38, 12, 2, 1, HOME_INK);
      px(39, 12, 1, 4, HOME_INK);
      px(38, 15, 2, 1, HOME_INK);
      px(30, 11, 8, 8, HOME_INK);
      px(31, 12, 6, 6, "#e8b33e");
      px(31, 12, 2, 5, "#f6d465");
      px(36, 12, 1, 6, "#b5862a");
      px(33, 19, 2, 3, HOME_INK);
      px(30, 22, 8, 4, HOME_INK);
      px(31, 23, 6, 2, "#8b5a2b");
      px(33, 23, 2, 1, "#f6d465");
      if (frame % 3 === 0) px(35, 9, 1, 1, "#ffffff");
    },
  },
};

// Draws icon `name` centered on `canvas`, as big as fits in whole pixels
// (never bigger than `maxScale`, so a page can keep one pixel size across
// its tiles). The canvas is resized to its on-screen size first, so pixels
// stay square however the tile stretches.
function drawHomeIcon(canvas, name, frame = 0, me = null, maxScale = Infinity) {
  const icon = HOME_ICONS[name];
  const w = Math.round(canvas.clientWidth) || canvas.width;
  const h = Math.round(canvas.clientHeight) || canvas.height;
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const fit = Math.floor(Math.min(canvas.width / (icon.w + 2), canvas.height / (icon.h + 2)));
  const scale = Math.max(1, Math.min(maxScale, fit));
  const ox = Math.floor((canvas.width - icon.w * scale) / 2);
  const oy = Math.floor((canvas.height - icon.h * scale) / 2);
  icon.draw(
    (x, y, w, h, color) => {
      ctx.fillStyle = color;
      ctx.fillRect(ox + x * scale, oy + y * scale, w * scale, h * scale);
    },
    frame,
    me
  );
}
