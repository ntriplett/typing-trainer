// The Aquarium (PLAN.md 11k): a dim hall of glowing tanks. Four tanks
// stand in the main hall; archways lead to the Reef Room and the River
// Room, three tanks each. Every tank is live (fish_motion.js); click one to
// go up close and decorate it. Empty stands wait for a tank from the shop.
// Drawn on a 160x90 grid at 6x with real buttons laid over it.

const $ = (id) => document.getElementById(id);
const HALL_W = 160;
const HALL_H = 90;
const HALL_PX = 6;
const HALL_TICK_MS = 100;
const MINI_FISH_SCALE = 0.4; // the same as tank.js: tank units per fish pixel

// Rooms: which tank spots stand where (tank windows are 2.29:1 like the tanks).
const HALL_ROOMS = {
  main: {
    name: "Aquarium",
    wall: ["#141e30", "#18243a"],
    glow: "rgba(90, 170, 230, 0.05)",
    stands: [
      { spot: 0, x: 18, y: 8, w: 60 },
      { spot: 1, x: 84, y: 8, w: 60 },
      { spot: 2, x: 18, y: 48, w: 60 },
      { spot: 3, x: 84, y: 48, w: 60 },
    ],
    doors: [
      { room: "reef", x: 1, y: 30, w: 14, h: 46, label: "Reef Room" },
      { room: "river", x: 145, y: 30, w: 14, h: 46, label: "River Room" },
    ],
  },
  reef: {
    name: "Reef Room",
    wall: ["#2a1a34", "#341e3e"],
    glow: "rgba(240, 130, 170, 0.05)",
    stands: [
      { spot: 4, x: 18, y: 8, w: 60 },
      { spot: 5, x: 84, y: 8, w: 60 },
      { spot: 6, x: 51, y: 48, w: 60 },
    ],
    doors: [{ room: "main", x: 145, y: 30, w: 14, h: 46, label: "Main Hall" }],
  },
  river: {
    name: "River Room",
    wall: ["#142a22", "#18322a"],
    glow: "rgba(120, 220, 160, 0.05)",
    stands: [
      { spot: 7, x: 18, y: 8, w: 60 },
      { spot: 8, x: 84, y: 8, w: 60 },
      { spot: 9, x: 51, y: 48, w: 60 },
    ],
    doors: [{ room: "main", x: 1, y: 30, w: 14, h: 46, label: "Main Hall" }],
  },
};

let hall = null; // /api/aquarium
let roomId = "main";
let live = []; // [{stand, tank, world, canvas, cache}]
let bg = null;
let t = 0;

const standH = (s) => Math.round((s.w * TANK_H) / TANK_W);

function painter(ctx, px = HALL_PX) {
  return (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(x * px, y * px, w * px, h * px);
  };
}

function drawRoom(room) {
  const canvas = document.createElement("canvas");
  canvas.width = HALL_W * HALL_PX;
  canvas.height = HALL_H * HALL_PX;
  const r = painter(canvas.getContext("2d"));
  r(0, 0, HALL_W, HALL_H, room.wall[0]);
  for (let x = 0; x < HALL_W; x += 8) r(x, 0, 4, 84, room.wall[1]);
  r(0, 84, HALL_W, 6, "#0c121c"); // the floor
  r(0, 84, HALL_W, 0.6, "#2a3a52");
  for (let i = 0; i < 30; i++) r((i * 53) % HALL_W, (i * 29) % 80, 0.6, 0.6, "rgba(160, 210, 255, 0.25)"); // drifting motes
  for (const s of room.stands) {
    const h = standH(s);
    for (let k = 1; k <= 6; k++) r(s.x - k, s.y - k, s.w + 2 * k, h + 2 * k, room.glow); // the glow
    r(s.x - 1.5, s.y - 1.5, s.w + 3, h + 3, "#0a0e14"); // the tank's rim
    r(s.x - 1.5, s.y - 1.5, s.w + 3, 1, "#3a4a5a");
    r(s.x + 2, s.y + h + 1.5, s.w - 4, 3, "#2a1e16"); // its stand
    r(s.x + 2, s.y + h + 1.5, s.w - 4, 0.6, "#5c3a1a");
  }
  for (const d of room.doors) {
    r(d.x, d.y, d.w, d.h, "#06090e"); // an archway into the next room
    r(d.x, d.y, d.w, 2, "#3a2a1a");
    r(d.x + 2, d.y + 3, d.w - 4, d.h - 3, d.room === "reef" ? "#3a1e3a" : d.room === "river" ? "#16302a" : "#141e30");
    for (let k = 0; k < 4; k++) r(d.x + 3 + k * 2.5, d.y + 10 + (k % 2) * 6, 1.5, 1.5, "rgba(160, 210, 255, 0.4)");
  }
  return canvas;
}

function emptyStand(ctx, s) {
  const r = painter(ctx);
  const h = standH(s);
  r(s.x, s.y, s.w, h, "#0e1620");
  for (let k = 0; k < s.w; k += 6) r(s.x + k, s.y + h / 2, 3, 0.5, "#24303e");
}

function openRoom(id) {
  roomId = id;
  history.replaceState(null, "", id === "main" ? location.pathname : `?room=${id}`);
  const room = HALL_ROOMS[id];
  $("hall-title").textContent = room.name;
  bg = drawRoom(room);
  live = room.stands.map((stand) => {
    const tank = hall.spots[stand.spot];
    if (!tank) return { stand, tank: null };
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(stand.w * HALL_PX);
    canvas.height = Math.round(standH(stand) * HALL_PX);
    return { stand, tank, canvas, cache: {}, world: FishMotion.create(tank.fish, tank, hall.items, MINI_FISH_SCALE) };
  });
  const owned = hall.spots.filter(Boolean).length;
  $("hall-hint").textContent = `${owned} of ${hall.spots.length} tanks. Click a tank to visit it and decorate it. Buy tanks and decorations upstairs at the Pet Shop.`;
  renderSpots(room);
  draw();
}

function renderSpots(room) {
  const place = (el, x, y, w, h) =>
    Object.assign(el.style, { left: `${(x / HALL_W) * 100}%`, top: `${(y / HALL_H) * 100}%`, width: `${(w / HALL_W) * 100}%`, height: `${(h / HALL_H) * 100}%` });
  const spots = live.map(({ stand, tank }) => {
    const a = document.createElement("a");
    a.className = "hall-tank" + (tank ? "" : " empty");
    a.dataset.spot = stand.spot;
    place(a, stand.x - 1.5, stand.y - 1.5, stand.w + 3, standH(stand) + 8);
    if (tank) {
      a.href = `/pets/aquarium/${stand.spot}`;
      a.innerHTML = `<span class="hall-plaque">${escapeHtml(tank.name)} · ${tank.fish.length} 🐠</span>`;
    } else {
      a.href = "/pets/shop?dept=aqua";
      a.innerHTML = `<span class="hall-plaque">Empty stand: get a tank</span>`;
    }
    return a;
  });
  for (const d of room.doors) {
    const b = document.createElement("button");
    b.className = "hall-door";
    b.dataset.room = d.room;
    place(b, d.x, d.y, d.w, d.h);
    b.innerHTML = `<span class="hall-plaque">${d.room === "main" ? "⬅ " : ""}${d.label}${d.room === "main" ? "" : " ➜"}</span>`;
    b.onclick = () => openRoom(d.room);
    spots.push(b);
  }
  $("hall-spots").replaceChildren(...spots);
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

function draw() {
  const ctx = $("hall-canvas").getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(bg, 0, 0);
  for (const l of live) {
    if (!l.tank) {
      emptyStand(ctx, l.stand);
      continue;
    }
    const tctx = l.canvas.getContext("2d");
    drawTankScene(tctx, l.canvas.width / TANK_W, l.world, l.tank, t, l.cache);
    ctx.drawImage(l.canvas, l.stand.x * HALL_PX, l.stand.y * HALL_PX);
  }
}

function tick() {
  t += 1;
  for (const l of live) if (l.world) FishMotion.step(l.world);
  draw();
}

async function load() {
  const r = await fetch("/api/aquarium");
  if (!r.ok) throw new Error(`/api/aquarium returned ${r.status}`);
  hall = await r.json();
  Header.update(hall);
  const asked = new URLSearchParams(location.search).get("room");
  openRoom(HALL_ROOMS[asked] ? asked : "main");
}

load()
  .then(() => setInterval(tick, HALL_TICK_MS))
  .catch((err) => {
    console.error(err);
    $("hall-message").textContent = `Couldn't open the Aquarium (${err.message}). Try reloading.`;
  });
