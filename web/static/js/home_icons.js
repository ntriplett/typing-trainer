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

const KEYBOARD_ROWS = [
  ".oooooooooooooooooooooo.",
  "okkkkkkkkkkkkkkkkkkkkkko",
  "okwwkwwkwwkwwkwwkwwkwwko",
  "okssksskssksskssksskssko",
  "okwwkwwkFFkwwkJJkwwkwwko",
  "okssksskffksskjjksskssko",
  "okkkkwwwwwwwwwwwwwwkkkko",
  "okkkksssssssssssssskkkko",
  "okkkkkkkkkkkkkkkkkkkkkko",
  ".oooooooooooooooooooooo.",
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

const STALL_ROWS = [
  ".oooooooooooooooooo.",
  "orrwwrrwwrrwwrrwwrro",
  "orrwwrrwwrrwwrrwwrro",
  "orrwwrrwwrrwwrrwwrro",
  "oooooooooooooooooooo",
  "..o..............o..",
  "..o..aa..cc..gg..o..",
  "..o.aaaa.cc.gggg.o..",
  "..o.aaaa.cc.gggg.o..",
  "oooooooooooooooooooo",
  "obbbbbbbbbbbbbbbbbbo",
  "obBBbbbbbbbbbbbbBBbo",
  "obbbbbbbbbbbbbbbbbbo",
  "oooooooooooooooooooo",
  "ob................bo",
  "oo................oo",
];

const PAW_ROWS = [
  "....oo....oo....",
  "...oppo..oppo...",
  "...oppo..oppo...",
  "....oo....oo....",
  ".oo..........oo.",
  "oppo........oppo",
  "oppo..oooo..oppo",
  ".oo..oppppo..oo.",
  "....oppppppo....",
  "...oppppppppo...",
  "...oppppppppo...",
  "....oppppppo....",
  ".....oooooo.....",
];

const BED_ROWS = [
  "oooo................",
  "obbo................",
  "obbo.oooooo.........",
  "obbooWWWWWWooooooooo",
  "obboWWWWWWWoRRRRRRRo",
  "obboRRRRRRRRRRRRRRRo",
  "obboRrRrRrRrRrRrRrRo",
  "obboRRRRRRRRRRRRRRRo",
  "obbooooooooooooooooo",
  "obbbbbbbbbbbbbbbbbbo",
  "oooooooooooooooooooo",
  "ob................bo",
  "oo................oo",
];

const SHIRT_ROWS = sym(
  ".......o",
  "......o.",
  "....oo..",
  "..oo....",
  ".ooooooo",
  "otttttnn",
  "ottttttn",
  "ottttttt",
  "ooottttt",
  "..ottttt",
  "..oTTTTT",
  "..ottttt",
  "..ottttt",
  "..oooooo"
);

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
  // A desk by the window: keyboard (F and J glowing), a lamp, a mug, and
  // letters drifting up like leaves.
  practice: {
    w: 44,
    h: 26,
    draw(px, frame) {
      const glow = frame % 2 === 0;
      // desk
      px(0, 20, 44, 1, HOME_INK);
      px(0, 21, 44, 2, "#b07a43");
      px(0, 23, 44, 1, "#8b5a2b");
      px(3, 24, 3, 2, "#5c3a1a");
      px(38, 24, 3, 2, "#5c3a1a");
      // keyboard, resting on the desk
      gridIcon(KEYBOARD_ROWS, {
        o: HOME_INK, k: "#6b4a2e", w: "#fbf1dc", s: "#d8c7a0",
        F: glow ? "#f6d465" : "#e8b33e", f: "#b5862a",
        J: glow ? "#e8b33e" : "#f6d465", j: "#b5862a",
      })(px, 10, 11);
      // mug with steam
      px(2, 15, 6, 5, HOME_INK);
      px(3, 16, 4, 4, "#d9822b");
      px(8, 16, 1, 3, HOME_INK);
      px(3, 16, 4, 1, "#5c3a1a");
      px(4 + (frame % 2), 12, 1, 2, "#fbf1dc");
      px(5 - (frame % 2), 10, 1, 2, "#fbf1dc");
      // lamp
      px(37, 19, 6, 1, HOME_INK);
      px(39, 11, 1, 8, HOME_INK);
      px(36, 7, 7, 4, HOME_INK);
      px(37, 8, 5, 2, "#e8b33e");
      px(37, 11, 5, 1, glow ? "#f6d465" : "#fbf1dc");
      // letters drifting up
      [["f", 12, 0, "#d9822b"], ["j", 20, 2, "#b8432f"], ["d", 27, 1, "#6b8e3a"], ["k", 33, 3, "#8b5a2b"]].forEach(
        ([letter, x, phase, color]) => {
          const y = 7 - ((frame + phase) % 6);
          if (y >= 0) tinyLetter(px, letter, x + ((frame + phase) % 2), y, color);
        }
      );
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
    w: 16,
    h: 17,
    draw(px, frame) {
      const dy = frame % 2;
      const at = (x, y, w, h, c) => px(x, y + dy, w, h, c);
      at(0, 0, 16, 16, HOME_INK);
      at(1, 1, 14, 14, "#e8b33e");
      at(1, 1, 14, 1, "#f6d465");
      at(1, 1, 1, 14, "#f6d465");
      at(1, 14, 14, 1, "#b5862a");
      at(14, 1, 1, 14, "#b5862a");
      for (const [x, y] of [[2, 2], [13, 2], [2, 13], [13, 13]]) at(x, y, 1, 1, HOME_INK);
      const glyph = [".www.", "ww.ww", "...ww", "..ww.", ".ww..", ".ww..", ".....", ".ww..", ".ww.."];
      for (const [color, off] of [["#5c3a1a", 1], ["#ffffff", 0]]) {
        glyph.forEach((row, y) => [...row].forEach((c, x) => c === "w" && at(5 + x + off, 3 + y + off, 1, 1, color)));
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
  store: {
    w: 20,
    h: 16,
    draw(px) {
      gridIcon(STALL_ROWS, {
        o: HOME_INK, r: "#b8432f", w: "#fbf1dc", a: "#d8283a", c: "#e8b33e", g: "#6b8e3a",
        b: "#b07a43", B: "#8b5a2b",
      })(px);
    },
  },
  pets: {
    w: 16,
    h: 13,
    draw(px, frame, me) {
      const pet = me && me.avatar && (me.avatar.pets || [])[0];
      if (pet) {
        // a v3 pet (pet_render.js), shrunk to fit the 16x13 icon
        const { w, h } = petSize(pet.genes, pet.growth);
        const scale = Math.min(16 / w, 13 / h, 0.5);
        drawPet(px, (16 - w * scale) / 2, 13, pet.genes, pet.growth, { frame, scale, shadow: false });
        return;
      }
      gridIcon(PAW_ROWS, { o: HOME_INK, p: "#b07a43" })(px);
    },
  },
  bedroom: {
    w: 20,
    h: 13,
    draw(px) {
      gridIcon(BED_ROWS, { o: HOME_INK, b: "#8b5a2b", W: "#fbf1dc", R: "#d9822b", r: "#e8b33e" })(px);
    },
  },
  wardrobe: {
    w: 16,
    h: 14,
    draw(px) {
      gridIcon(SHIRT_ROWS, { o: HOME_INK, t: "#3f7fd0", n: "#2a5a9a", T: "#fbf1dc" })(px);
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
  progress: {
    w: 20,
    h: 16,
    draw(px, frame) {
      // a little board with bars climbing, and a star on top
      px(0, 0, 20, 16, HOME_INK);
      px(1, 1, 18, 14, "#fbf1dc");
      px(2, 13, 16, 1, "#d8c7a0");
      [[3, 3, "#a8d5e2"], [7, 5, "#6b8e3a"], [11, 7, "#e8b33e"], [15, 10, "#d9822b"]].forEach(([x, h, color], i) => {
        const grow = i === 3 && frame % 2 ? 1 : 0;
        px(x - 1, 13 - h - grow - 1, 4, h + grow + 1, HOME_INK);
        px(x, 13 - h - grow, 2, h + grow, color);
      });
      px(3, 2, 1, 3, "#f6d465");
      px(2, 3, 3, 1, "#f6d465");
    },
  },
};

// Draws icon `name` centered on `canvas`, as big as fits in whole pixels.
// The canvas is resized to its on-screen size first, so pixels stay square
// however the tile stretches.
function drawHomeIcon(canvas, name, frame = 0, me = null) {
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
  const scale = Math.max(1, Math.floor(Math.min(canvas.width / (icon.w + 2), canvas.height / (icon.h + 2))));
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
