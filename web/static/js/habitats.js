// Habitat looks (PLAN.md 11i), shared by the Pet Shop, the Trailhead, and
// the habitat view. Each look draws itself on a 160x90 grid through a
// painter r(x, y, w, h, color), and lists its props: things curious pets
// walk over to look at (pet_motion.js). Pets' feet stay between groundTop
// and groundBottom. New looks (mountain, ...) go in HABITAT_LOOKS.

const HABITAT_W = 160;
const HABITAT_H = 90;

function habitatPainter(ctx, px) {
  return (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x * px), Math.round(y * px), Math.ceil(w * px), Math.ceil(h * px));
  };
}

function drawHabitatFlower(r, x, y, petal, middle = "#f4d35e") {
  r(x, y + 1, 1, 3, "#4a7a2e");
  r(x - 1, y, 3, 1, petal);
  r(x, y - 1, 1, 3, petal);
  r(x, y, 1, 1, middle);
}

function drawMeadowHabitat(r) {
  r(0, 0, HABITAT_W, 40, "#a8d5e2"); // sky
  r(0, 0, HABITAT_W, 8, "#c4e3ec");
  r(130, 6, 8, 8, "#f8e08a"); // sun
  r(131, 7, 6, 6, "#fbeeb0");
  for (const [cx, cy] of [[14, 8], [62, 4], [98, 11]]) {
    r(cx, cy + 2, 16, 3, "#ffffff");
    r(cx + 3, cy, 9, 2, "#ffffff");
  }
  for (let x = 0; x < HABITAT_W; x++) {
    const far = Math.round(28 + 5 * Math.sin(x / 17 + 2) + 2 * Math.sin(x / 6)); // far hills
    r(x, far, 1, 40 - far, "#9cc46a");
    const near = Math.round(36 + 3 * Math.sin(x / 11) + Math.sin(x / 4 + 1)); // near hills
    r(x, near, 1, 44 - near, "#8fb85a");
  }
  r(0, 42, HABITAT_W, HABITAT_H - 42, "#7fa346"); // the meadow
  r(0, 42, HABITAT_W, 1, "#94c25c");
  for (let i = 0; i < 70; i++) {
    const x = (i * 37) % HABITAT_W;
    const y = 46 + ((i * 53) % 42);
    r(x, y, 1, 1, i % 3 ? "#6d9440" : "#94c25c"); // grass texture
    if (i % 2) r(x + 2, y - 1, 1, 2, "#5a7a2e");
  }
  // a fence along the back
  for (let x = 2; x < HABITAT_W; x += 12) r(x, 38, 2, 7, "#8b5a2b");
  r(0, 39, HABITAT_W, 1, "#a87a44");
  r(0, 42, HABITAT_W, 1, "#a87a44");
  // a pond
  r(118, 52, 26, 7, "#4a8ab0");
  r(116, 53, 30, 5, "#4a8ab0");
  r(120, 53, 10, 1, "#8cc4dc");
  r(115, 54, 1, 3, "#6d9440");
  // the stump
  r(20, 54, 10, 6, "#8b5a2b");
  r(20, 53, 10, 2, "#d8b070");
  r(22, 53, 6, 1, "#b88a50");
  r(19, 59, 12, 1, "#5c3a1a");
  // rocks
  r(70, 78, 8, 4, "#9a948a");
  r(71, 77, 5, 1, "#b8b2a6");
  r(78, 80, 4, 2, "#8a8478");
  // flowers
  const petals = ["#e86a8a", "#fbf1dc", "#9a7ae0", "#f4a24a", "#e86a8a", "#fbf1dc"];
  [[10, 70], [44, 58], [52, 84], [96, 66], [104, 86], [150, 74], [36, 76], [88, 50], [140, 84]].forEach(([x, y], i) =>
    drawHabitatFlower(r, x, y, petals[i % petals.length])
  );
  // a butterfly bush
  r(56, 47, 9, 5, "#5a8a3a");
  r(57, 46, 7, 1, "#6d9440");
  drawHabitatFlower(r, 58, 47, "#e86a8a");
  drawHabitatFlower(r, 62, 48, "#fbf1dc");
}

const HABITAT_LOOKS = {
  meadow: {
    name: "Meadow",
    draw: drawMeadowHabitat,
    groundTop: 50,
    groundBottom: 88,
    props: [
      { id: "stump", x: 25, y: 61 },
      { id: "pond", x: 130, y: 60 },
      { id: "rocks", x: 75, y: 83 },
      { id: "bush", x: 60, y: 53 },
      { id: "flowers", x: 100, y: 68 },
    ],
  },
};

// The habitat's look drawn onto a new canvas at px pixels per grid unit.
function habitatBackground(kind, px) {
  const canvas = document.createElement("canvas");
  canvas.width = HABITAT_W * px;
  canvas.height = HABITAT_H * px;
  HABITAT_LOOKS[kind].draw(habitatPainter(canvas.getContext("2d"), px));
  return canvas;
}
