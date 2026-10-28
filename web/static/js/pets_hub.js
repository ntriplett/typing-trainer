// The Pets hub (PLAN.md 11h): a field where your pets wander (fish wait for
// the Aquarium), with buildings to visit: the Pet Shop, the Pet Care
// Center, the Aquarium, and the Trailhead out to your habitats. Only the
// shop is open so far. A new player's field fills up with visitors.
//
// The scene is drawn on a 160x90 grid at 6x; each building has a real
// link (or "coming soon" button) laid over it, so the keyboard works too.

const $ = (id) => document.getElementById(id);
const SCENE_W = 160;
const SCENE_H = 90;
const SCENE_PX = 6;
const FIELD_TOP = 70; // where pets' feet can be (below the signs)
const FIELD_BOTTOM = 88;
const PET_SCALE = 0.5; // pets are drawn at twice the scene's pixel density
const TICK_MS = 120;
const FRAME_EVERY = 3; // ticks per animation frame

const BUILDINGS = [
  { id: "shop", name: "Pet Shop", href: "/pets/shop", x: 5, y: 18, w: 36, h: 32, draw: drawShop },
  { id: "care", name: "Pet Care Center", href: "/pets/care", x: 45, y: 18, w: 34, h: 32, draw: drawCare },
  { id: "aquarium", name: "Aquarium", soon: true, x: 83, y: 18, w: 36, h: 32, draw: drawAquarium },
  { id: "trailhead", name: "Trailhead", soon: true, x: 124, y: 18, w: 32, h: 32, draw: drawTrailhead },
];
const SIGN_H = 8; // the sign plank under each building

let hub = null; // /api/pets/hub
let walkers = [];
let background = null;
let ticks = 0;

// --- the scene ---------------------------------------------------------------------

function painter(ctx) {
  return (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x * SCENE_PX), Math.round(y * SCENE_PX), Math.ceil(w * SCENE_PX), Math.ceil(h * SCENE_PX));
  };
}

function drawShop(r, { x, y, w, h }) {
  r(x + 8, y, w - 16, 4, "#8b5a2b"); // sign board on the roof
  r(x + 9, y + 1, w - 18, 2, "#e8b33e");
  r(x - 1, y + 4, w + 2, 3, "#8e3418"); // roof
  r(x, y + 4, w, 1, "#b8432f");
  r(x + 1, y + 7, w - 2, h - 7, "#e8c88a"); // walls
  for (let k = y + 11; k < y + h; k += 4) r(x + 1, k, w - 2, 1, "#d8b070");
  for (let i = 0; i < w - 2; i += 3) {
    // striped awning with a scalloped edge
    const c = (i / 3) % 2 ? "#fbf1dc" : "#b8432f";
    r(x + 1 + i, y + 7, 3, 3, c);
    if ((i / 3) % 2 === 0) r(x + 2 + i, y + 10, 1, 1, c);
  }
  r(x + 4, y + 13, 14, 11, "#5c3a1a"); // window, with a paw print
  r(x + 5, y + 14, 12, 9, "#bfe6f0");
  r(x + 5, y + 14, 12, 2, "#e0f2f6");
  r(x + 9, y + 18, 4, 3, "#8b5a2b");
  for (const dx of [8, 10, 12, 14]) r(x + dx - (dx > 11 ? 1 : 0), y + 16, 1, 1, "#8b5a2b");
  r(x + w - 13, y + 13, 10, h - 13, "#5c3a1a"); // door
  r(x + w - 12, y + 14, 8, h - 14, "#8b5a2b");
  r(x + w - 11, y + 15, 6, 4, "#bfe6f0");
  r(x + w - 6, y + 23, 1, 1, "#e8b33e");
}

function drawCare(r, { x, y, w, h }) {
  for (let i = 0; i < 9; i++) r(x - 1 + i * 2, y + 8 - i, w + 2 - i * 4, 1, i % 2 ? "#4a6627" : "#5a7a2e"); // roof
  r(x + 1, y + 9, w - 2, h - 9, "#f6ead2"); // walls
  r(x + 1, y + h - 2, w - 2, 2, "#d8c7a0");
  const heart = [".XX.XX.", "XXXXXXX", "XXXXXXX", ".XXXXX.", "..XXX..", "...X..."];
  const hx = x + Math.floor(w / 2) - 3;
  heart.forEach((row, j) => [...row].forEach((c, i) => c === "X" && r(hx + i, y + 10 + j, 1, 1, "#d84a5a")));
  r(x + w / 2 - 4, y + 18, 8, h - 18, "#2e3a6a"); // door
  r(x + w / 2 - 3, y + 19, 6, h - 19, "#4a6aa0");
  r(x + w / 2 - 2, y + 20, 4, 3, "#bfe6f0");
  for (const wx of [x + 3, x + w - 10]) {
    r(wx, y + 17, 7, 7, "#5c3a1a");
    r(wx + 1, y + 18, 5, 5, "#bfe6f0");
    r(wx + 3, y + 18, 1, 5, "#5c3a1a");
  }
}

function drawAquarium(r, { x, y, w, h }) {
  for (let i = 0; i < 7; i++) {
    const wid = 14 + i * 3; // a dome
    r(x + w / 2 - wid / 2, y + i, wid, 1, i % 2 ? "#2a7a8a" : "#3a8a9a");
  }
  r(x + 2, y + 7, w - 4, h - 7, "#3a9a9a"); // walls
  r(x + 2, y + 7, w - 4, 1, "#70d0d8");
  r(x + 6, y + 10, w - 12, 15, "#1e3a4a"); // the big window
  r(x + 7, y + 11, w - 14, 13, "#5aa8c8");
  r(x + 7, y + 11, w - 14, 3, "#7ec4dc");
  r(x + 7, y + 22, w - 14, 2, "#d8c28a");
  r(x + 10, y + 16, 1, 2, "#e0882e"); // fish
  r(x + 11, y + 16, 3, 2, "#f0a040");
  r(x + 22, y + 19, 3, 2, "#f0d070");
  r(x + 25, y + 19, 1, 2, "#d8b040");
  r(x + 17, y + 13, 1, 1, "#e6f6fa"); // bubbles
  r(x + 18, y + 15, 1, 1, "#e6f6fa");
  r(x + w / 2 - 3, y + 26, 6, h - 26, "#1e3a4a"); // door
}

function drawTrailhead(r, { x, y, w, h }) {
  r(x + 13, y + 3, 6, 6, "#d8c090"); // the trail heads off into the hills
  r(x + 10, y + 9, 12, h - 9, "#e8d3a8");
  for (const tx of [x - 1, x + w - 6]) {
    // little pines
    for (let i = 0; i < 6; i++) r(tx + 3 - i / 2, y + 14 + i * 2, 1 + i, 2, i % 2 ? "#3a6a3a" : "#4a8a4a");
    r(tx + 3, y + 26, 1, 4, "#5c3a1a");
  }
  r(x + 6, y + 9, 3, h - 9, "#8b5a2b"); // the gate
  r(x + w - 9, y + 9, 3, h - 9, "#8b5a2b");
  r(x + 4, y + 7, w - 8, 3, "#5c3a1a");
  r(x + 3, y + 5, 6, 3, "#4a8a4a"); // leaves on the beam
  r(x + w - 9, y + 5, 6, 3, "#4a8a4a");
  r(x + 12, y + 6, 8, 2, "#6b8e3a");
}

function drawBackground() {
  const canvas = document.createElement("canvas");
  canvas.width = SCENE_W * SCENE_PX;
  canvas.height = SCENE_H * SCENE_PX;
  const r = painter(canvas.getContext("2d"));
  r(0, 0, SCENE_W, 44, "#a8d5e2"); // sky
  r(0, 0, SCENE_W, 8, "#c4e3ec");
  for (const [cx, cy] of [[18, 7], [70, 4], [110, 9]]) {
    r(cx, cy + 2, 16, 3, "#ffffff");
    r(cx + 3, cy, 9, 2, "#ffffff");
  }
  for (let x = 0; x < SCENE_W; x++) {
    const top = Math.round(34 + 4 * Math.sin(x / 13) + 2 * Math.sin(x / 5 + 1)); // hills
    r(x, top, 1, 44 - top, "#8fb85a");
  }
  r(0, 44, SCENE_W, SCENE_H - 44, "#7fa346"); // grass
  r(0, 44, SCENE_W, 1, "#94c25c");
  r(0, 50, SCENE_W, 5, "#e8d3a8"); // the path past every door
  r(0, 50, SCENE_W, 1, "#d8c090");
  r(0, 54, SCENE_W, 1, "#d8c090");
  for (const [tx, ty] of [[8, 62], [30, 80], [52, 70], [77, 85], [96, 64], [118, 76], [140, 68], [152, 84], [64, 59]]) {
    r(tx, ty, 1, 1, "#5a7a2e");
    r(tx + 2, ty - 1, 1, 2, "#5a7a2e");
  }
  for (const b of BUILDINGS) b.draw(r, b);
  return canvas;
}

// --- pets in the field ------------------------------------------------------------

const isEgg = (p) => p.growth === 0 && (p.species === "dragon" || p.species === "phoenix");

function makeWalkers(data) {
  const pets = [
    ...data.field.map((p) => ({ ...p, owned: true })),
    ...data.visitors.map((p) => ({ ...p, owned: false })),
  ];
  return pets.map((p, i) => {
    const energy = (p.genes.personality || {}).energy ?? 0.5;
    const width = petSize(p.genes, p.growth).w * PET_SCALE;
    return {
      p,
      width,
      x: 6 + ((i * 41) % Math.max(1, SCENE_W - 12 - width)),
      y: FIELD_TOP + ((i * 13) % (FIELD_BOTTOM - FIELD_TOP)),
      dir: i % 2 ? -1 : 1,
      speed: isEgg(p) ? 0 : 0.1 + energy * 0.3,
      rest: 0,
    };
  });
}

function step() {
  for (const w of walkers) {
    if (!w.speed) continue;
    if (w.rest > 0) {
      w.rest -= 1;
      continue;
    }
    w.x += w.dir * w.speed;
    if (w.x < 2 || w.x > SCENE_W - w.width - 2) w.dir *= -1;
    else if (Math.random() < 0.006) w.dir *= -1;
    if (Math.random() < 0.01) w.rest = 10 + Math.floor(Math.random() * 30 * (1 + ((w.p.genes.personality || {}).sleepy || 0)));
  }
  ticks += 1;
  draw();
}

function draw() {
  const canvas = $("hub-canvas");
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(background, 0, 0);
  const px = painter(ctx);
  const frame = Math.floor(ticks / FRAME_EVERY);
  for (const w of [...walkers].sort((a, b) => a.y - b.y)) {
    const moving = w.speed && !w.rest;
    drawPet(px, w.x, w.y, w.p.genes, w.p.growth, { frame: moving ? frame : 0, faceLeft: w.dir < 0, scale: PET_SCALE });
    if (w.p.owned) nameTag(ctx, w);
  }
}

function nameTag(ctx, w) {
  const h = petSize(w.p.genes, w.p.growth).h * PET_SCALE;
  const cx = (w.x + w.width / 2) * SCENE_PX;
  const top = (w.y - h - 1) * SCENE_PX;
  ctx.font = "22px 'Jersey 10', sans-serif";
  ctx.textAlign = "center";
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#3b2417";
  ctx.strokeText(w.p.name, cx, top);
  ctx.fillStyle = "#fbf1dc";
  ctx.fillText(w.p.name, cx, top);
}

// --- buildings: links over the scene ------------------------------------------------

function renderBuildings() {
  const nav = $("hub-buildings");
  nav.replaceChildren(
    ...BUILDINGS.map((b) => {
      const el = document.createElement(b.soon ? "button" : "a");
      el.className = "hub-building" + (b.soon ? " soon" : "");
      el.dataset.building = b.id;
      Object.assign(el.style, {
        left: `${(b.x / SCENE_W) * 100}%`,
        top: `${(b.y / SCENE_H) * 100}%`,
        width: `${(b.w / SCENE_W) * 100}%`,
        height: `${((b.h + SIGN_H) / SCENE_H) * 100}%`,
      });
      el.innerHTML = `${news(b)}<span class="hub-sign">${b.name}${b.soon ? "<small>Coming soon</small>" : ""}</span>`;
      if (b.soon) el.onclick = () => ($("hub-message").textContent = `The ${b.name} is still being built. Coming soon!`);
      else el.href = b.href;
      return el;
    })
  );
}

// A bubble over the shop's door when something's waiting there.
function news(b) {
  if (b.id !== "shop") return "";
  if (hub.coupon) return `<span class="hub-news">🎟️ A free pet!</span>`;
  if (hub.order && hub.order.status === "ready") return `<span class="hub-news">📦 Your order is here!</span>`;
  return "";
}

function renderPets() {
  const n = hub.pets.length;
  const fish = hub.pets.filter((p) => p.species === "fish").length;
  $("hub-pets").textContent = !n
    ? "No pets yet! Visit the Pet Shop to find one."
    : `You have ${n} pet${n > 1 ? "s" : ""}.` + (fish ? ` ${fish === n ? "They're" : `${fish} of them are`} fish, waiting for the Aquarium to open.` : "");
}

// --- start --------------------------------------------------------------------------

async function load() {
  const r = await fetch("/api/pets/hub");
  if (!r.ok) throw new Error(`/api/pets/hub returned ${r.status}`);
  hub = await r.json();
  Header.update(hub);
  background = drawBackground();
  walkers = makeWalkers(hub);
  renderBuildings();
  renderPets();
  draw();
}

load()
  .then(() => setInterval(step, TICK_MS))
  .catch((err) => {
    console.error(err);
    $("hub-message").textContent = `Couldn't open the Pets page (${err.message}). Try reloading.`;
  });
