// Pet Supplies art (PLAN.md 11l): treats, toys, fish food and color potions,
// each on a 16x16 grid through a painter r(x, y, w, h, color). Used by the
// Pet Shop, the habitat shelf (and the thrown item), the tank shelf, and the
// Pet Care Center's potions.

const SUPPLY_GRID = 16;
const SUPPLY_INK = "#3b2417";

function supplyDisc(r, cx, cy, rad, color) {
  for (let dy = -rad; dy <= rad; dy++) {
    const half = Math.sqrt(Math.max(0, rad * rad - dy * dy));
    if (half >= 0.4) r(cx - half, cy + dy, half * 2, 1, color);
  }
}

const SUPPLY_ART = {
  bone_biscuit(r) {
    r(4, 7, 8, 3, "#d8a860");
    for (const [x, y] of [[2, 5], [2, 9], [12, 5], [12, 9]]) supplyDisc(r, x + 1, y + 1, 2, "#d8a860");
    r(5, 8, 6, 1, "#b88a40");
  },
  fishy_cracker(r) {
    r(3, 6, 8, 5, "#e8b860");
    r(11, 5, 3, 7, "#e8b860");
    r(4, 7, 1, 1, SUPPLY_INK);
    r(6, 9, 4, 1, "#c89040");
  },
  carrot_stick(r) {
    for (let k = 0; k < 10; k++) r(4 + k * 0.8, 3 + k, 3 - k * 0.2, 1.4, "#e8822a");
    r(2, 1, 2, 3, "#5aa04a");
    r(4, 0, 1, 3, "#4a9040");
  },
  apple_slice(r) {
    supplyDisc(r, 8, 9, 5, "#d8382a");
    supplyDisc(r, 8, 9, 4, "#f8f0c8");
    r(7, 8, 1, 2, "#5c3a1a");
    r(9, 8, 1, 2, "#5c3a1a");
  },
  cricket_crunch(r) {
    r(3, 7, 9, 4, "#8a7a3a");
    r(11, 6, 3, 3, "#6a5a2a");
    r(4, 11, 1, 3, "#5a4a2a");
    r(9, 11, 1, 3, "#5a4a2a");
    r(13, 4, 2, 1, "#5a4a2a");
  },
  berry_bites(r) {
    for (const [x, y, c] of [[5, 9, "#7a3ab8"], [10, 9, "#d8384a"], [7.5, 5, "#4a5ac8"]]) {
      supplyDisc(r, x, y, 2.6, c);
      r(x - 1, y - 1.5, 1, 1, "#ffffff");
    }
  },
  ember_candy(r) {
    supplyDisc(r, 8, 9, 4, "#e8582a");
    supplyDisc(r, 8, 9, 2.5, "#f8c84a");
    r(4, 9, 1, 1, "#f8e08a");
    r(1, 8, 3, 2, "#e8582a");
    r(12, 8, 3, 2, "#e8582a");
  },
  star_sugar(r) {
    const star = ["...X...", "...X...", "XXXXXXX", ".XXXXX.", "..XXX..", ".XX.XX.", "X.....X"];
    star.forEach((row, j) => [...row].forEach((c, i) => c === "X" && r(4.5 + i, 4 + j, 1, 1, j % 2 ? "#f8d8f0" : "#fbe8a8")));
  },
  ball(r) {
    supplyDisc(r, 8, 8, 5, "#d8382a");
    r(3, 7.5, 10, 1.2, "#f8f0e0");
    r(6, 4, 2, 1, "#f88a7a");
  },
  frisbee(r) {
    for (let y = -2; y <= 2; y++) r(8 - (7 - Math.abs(y) * 1.5), 8 + y, (7 - Math.abs(y) * 1.5) * 2, 1, y < 0 ? "#4a9ae0" : "#3a7ab8");
    r(5, 7, 6, 0.6, "#a8d8f8");
  },
  feather_wand(r) {
    for (let k = 0; k < 10; k++) r(2 + k, 14 - k, 1, 1, "#8b5a2b");
    for (let k = 0; k < 5; k++) {
      r(11 + k * 0.4, 4 - k * 0.6, 3, 1, k % 2 ? "#e86a8a" : "#f4a24a");
      r(10 - k * 0.2, 2 + k * 0.4, 1, 3, "#9a7ae0");
    }
  },
  yarn_ball(r) {
    supplyDisc(r, 8, 9, 5, "#e86a8a");
    for (let k = -4; k <= 4; k += 2) r(8 + k * 0.3 - 3, 9 + k, 6, 0.6, "#c8486a");
    for (let k = 0; k < 4; k++) r(12 + k, 13 + (k % 2), 1, 1, "#e86a8a");
  },
  jolly_ball(r) {
    supplyDisc(r, 8, 9, 5.5, "#4ab84a");
    r(7, 2, 2, 3, "#3a9a3a"); // a handle
    r(5, 1, 6, 1.5, "#3a9a3a");
    r(5, 6, 2, 1, "#8ad87a");
  },
  hay_ball(r) {
    supplyDisc(r, 8, 9, 5, "#d8b850");
    for (let k = 0; k < 8; k++) r(4 + ((k * 5) % 8), 5 + k, 3, 0.6, "#b89830");
  },
  wiggle_worm(r) {
    for (let k = 0; k < 12; k++) r(2 + k, 9 + Math.sin(k / 1.6) * 2.5, 1.4, 2, k % 3 ? "#e8784a" : "#c8583a");
    r(13, 8 + Math.sin(11 / 1.6) * 2.5, 1, 1, SUPPLY_INK);
  },
  treasure_orb(r) {
    supplyDisc(r, 8, 8, 5, "#e8b33e");
    supplyDisc(r, 8, 8, 3.5, "#f8d870");
    r(6, 5, 2, 2, "#ffffff");
    for (const [x, y] of [[1, 3], [14, 4], [2, 13], [13, 13]]) r(x, y, 1, 1, "#f8e08a");
  },
  rainbow_ribbon(r) {
    ["#e86a6a", "#f4a24a", "#f4d35e", "#7ac87a", "#7ab0e0", "#9a7ae0"].forEach((c, i) => {
      for (let k = 0; k < 13; k++) r(1.5 + k, 4 + i + Math.sin(k / 2) * 1.5, 1, 1, c);
    });
  },
  flame_feather(r) {
    for (let k = 0; k < 12; k++) {
      const w = Math.sin((k / 12) * Math.PI) * 4;
      r(8 - w / 2 + (k - 6) * 0.2, 2 + k, w, 1, k < 4 ? "#f8d870" : k < 8 ? "#f4a24a" : "#d8482a");
    }
    r(8, 13, 1, 3, "#8b5a2b");
  },
  honey_drop(r) {
    for (let k = 0; k < 4; k++) r(8 - k * 0.5, 3 + k, k + 1, 1, "#e8a82a"); // the tip of the drop
    supplyDisc(r, 8, 10, 4, "#e8a82a");
    supplyDisc(r, 8, 10, 2.6, "#f4c850");
    r(6, 8, 1.5, 1.5, "#fff4c8");
  },
  nectar_drop(r) {
    for (const [x, y] of [[3, 11], [13, 11], [8, 13]]) supplyDisc(r, x, y, 2.5, "#f09ac0"); // a petal cup
    supplyDisc(r, 8, 11, 3.5, "#e87aa8");
    for (let k = 0; k < 3; k++) r(8 - k * 0.5, 2 + k, k + 1, 1, "#8ad8e8");
    supplyDisc(r, 8, 7, 2.5, "#8ad8e8");
    r(7, 6, 1, 1, "#ffffff");
  },
  pearl_comb(r) {
    r(3, 5, 10, 3, "#e8b33e");
    r(4, 4, 8, 1, "#f8d870");
    for (let x = 3; x < 13; x += 2) r(x, 8, 1, 5, "#c89428");
    supplyDisc(r, 8, 4, 2, "#f4ecf8");
    r(7, 3, 1, 1, "#ffffff");
  },
  silver_thimble(r) {
    supplyDisc(r, 8, 6, 4, "#c8d0dc"); // the rounded top
    r(4, 6, 8, 7, "#c8d0dc");
    r(3, 12, 10, 2, "#8a94a4"); // the rim
    r(3, 12, 10, 0.6, "#e8eef4");
    for (let y = 4; y < 12; y += 2) for (let x = 5 + (y % 4 ? 1 : 0); x < 12; x += 2) r(x, y, 0.8, 0.8, "#9aa4b4"); // the dimples
    r(5, 4, 1, 6, "#f4f8fc");
  },
  fish_flakes(r) {
    r(4, 3, 8, 11, "#4a8ab0"); // a shaker can
    r(4, 3, 8, 2, "#d8d8e0");
    r(5, 7, 6, 4, "#f8f0e0");
    for (const [x, y, c] of [[6, 8, "#e8582a"], [8, 9, "#f4c430"], [9, 8, "#4ab84a"]]) r(x, y, 1, 1, c);
  },
  sinking_pellets(r) {
    r(4, 3, 8, 11, "#6a5aa0");
    r(4, 3, 8, 2, "#d8d8e0");
    for (const [x, y] of [[6, 8], [8, 10], [9, 7], [6, 11]]) supplyDisc(r, x, y, 0.9, "#8a5a2a");
  },
};

function drawSupply(r, id) {
  (SUPPLY_ART[id] || SUPPLY_ART.ball)(r);
}

// A potion bottle: its liquid shows the colors you can see; a hidden color
// is a swirling mystery with a "?".
function drawPotion(r, shown) {
  r(6, 0, 4, 2, "#8b5a2b"); // the cork
  r(6.5, 2, 3, 2, "#d8e8f0"); // the neck
  supplyDisc(r, 8, 10, 5.5, "#e8f4f8"); // the glass
  const [a, b] = shown;
  const fill = (y0, y1, color) => {
    for (let y = y0; y < y1; y++) {
      const half = Math.sqrt(Math.max(0, 22 - (y - 10) * (y - 10)));
      if (half > 0.4) r(8 - half, y, half * 2, 1, color);
    }
  };
  const mystery = (y0, y1) => {
    for (let y = y0; y < y1; y++) {
      const half = Math.sqrt(Math.max(0, 22 - (y - 10) * (y - 10)));
      for (let x = -half; x < half; x += 1) r(8 + x, y, 1, 1, (Math.floor(x + y * 2) % 3 + 3) % 3 === 0 ? "#b88af8" : (Math.floor(x + y) % 2 + 2) % 2 ? "#6a5ab0" : "#8a6ad0");
    }
  };
  if (a) fill(6, 10, a.hex);
  else mystery(6, 10);
  if (b) fill(10, 16, b.hex);
  else mystery(10, 16);
  if (!a || !b) {
    const q = [".XX.", "X..X", "..X.", ".X..", "....", ".X.."];
    q.forEach((row, j) => [...row].forEach((c, i) => c === "X" && r(6 + i, (a ? 10 : 6) + j * 0.9, 1, 0.9, "#fbf1dc")));
  }
  r(4.5, 8, 1, 3, "rgba(255, 255, 255, 0.6)"); // a shine
}

// Draws onto a canvas, centered and as big as fits in whole pixels.
function supplyCanvas(canvas, draw) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const s = Math.max(1, Math.floor(Math.min(canvas.width, canvas.height) / SUPPLY_GRID));
  const ox = (canvas.width - SUPPLY_GRID * s) / 2;
  const oy = (canvas.height - SUPPLY_GRID * s) / 2;
  draw((x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(ox + x * s, oy + y * s, w * s, h * s);
  });
}
