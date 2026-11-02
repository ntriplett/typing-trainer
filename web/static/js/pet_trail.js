// The Trailhead (PLAN.md 11i): walk up and down a forest trail past your 10
// habitat spots. Each stop shows a small live view of its habitat (click it
// to go in) or an empty lot; the map shows the whole trail like a zoo map.
// Scenes are drawn on a 160x90 grid at 6x; the window and sign are real
// elements laid over the scene, so the keyboard works too.

const $ = (id) => document.getElementById(id);
const SCENE_W = 160;
const SCENE_H = 90;
const SCENE_PX = 6;
const MINI_PX = 3; // the window's habitat view: 480x270
const MINI_PET_SCALE = 2 / 3;
const TICK_MS = 120;
const WINDOW = { w: 62, h: 35, y: 14 }; // the habitat window, on the left or the right
const MAP_W = 160;
const MAP_H = 180;
const MAP_PX = 4;
const PLOT = { w: 54, h: 30 };

let trail = null; // /api/trail
let at = 0; // the stop we're at
let mini = null; // {world, background} for this stop's habitat
let backgrounds = {};

// A little seeded random, so each stop's trees stay put.
function seeded(n) {
  let a = n * 9301 + 49297;
  return () => {
    a = (a * 9301 + 49297) % 233280;
    return a / 233280;
  };
}

const windowSide = (spot) => (spot % 2 ? "right" : "left");
const windowX = (spot) => (windowSide(spot) === "left" ? 8 : SCENE_W - 8 - WINDOW.w);

// --- the trail scene ------------------------------------------------------------------

function pathCenter(y, spot) {
  const depth = (y - 40) / 50; // 0 at the horizon, 1 at the bottom
  return 80 + Math.sin(y / 9 + spot * 1.3) * 7 * depth;
}

function drawPine(r, x, y, size, dark) {
  for (let i = 0; i < size; i++) {
    const w = 1 + i;
    r(x - w / 2, y + i * 2, w, 2, (i + dark) % 2 ? "#3a6a3a" : "#4a8a4a");
  }
  r(x - 0.5, y + size * 2, 1, 2 + size / 3, "#5c3a1a");
}

function drawTrailScene(spot) {
  const canvas = document.createElement("canvas");
  canvas.width = SCENE_W * SCENE_PX;
  canvas.height = SCENE_H * SCENE_PX;
  const r = habitatPainter(canvas.getContext("2d"), SCENE_PX);
  const rand = seeded(spot + 1);
  r(0, 0, SCENE_W, 40, "#a8d5e2"); // sky
  r(0, 0, SCENE_W, 10, "#c4e3ec");
  for (let x = 0; x < SCENE_W; x++) {
    const peak = Math.round(22 + 6 * Math.sin(x / 11 + spot) + 3 * Math.sin(x / 4 + spot * 2)); // mountains
    r(x, peak, 1, 40 - peak, "#8aa4b8");
    if (peak < 22) r(x, peak, 1, 2, "#eef4f6");
    const hill = Math.round(33 + 3 * Math.sin(x / 9 + spot * 3)); // the forest line
    r(x, hill, 1, 41 - hill, "#4a7a3a");
  }
  r(0, 40, SCENE_W, SCENE_H - 40, "#7fa346"); // the forest floor
  for (let i = 0; i < 80; i++) {
    const x = rand() * SCENE_W;
    const y = 42 + rand() * 48;
    r(x, y, 1, 1, rand() < 0.5 ? "#6d9440" : "#94c25c");
  }
  for (let y = 40; y < SCENE_H; y++) {
    const half = 2 + (y - 40) * 0.36; // the trail, wider up close
    const cx = pathCenter(y, spot);
    r(cx - half, y, half * 2, 1, "#e8d3a8");
    r(cx - half, y, 1, 1, "#d8c090");
    r(cx + half - 1, y, 1, 1, "#d8c090");
    if (rand() < 0.15) r(cx - half / 2 + rand() * half, y, 1, 1, "#d8c090"); // pebbles
  }
  // trees: small far ones, then big ones on the side away from the window
  for (let i = 0; i < 14; i++) drawPine(r, rand() * SCENE_W, 30 + rand() * 8, 4, i);
  const away = windowSide(spot) === "left" ? [104, 156] : [4, 56];
  for (let i = 0; i < 5; i++) {
    const x = away[0] + rand() * (away[1] - away[0]);
    if (Math.abs(x - pathCenter(80, spot)) > 18) drawPine(r, x, 44 + rand() * 18, 8 + Math.floor(rand() * 5), i);
  }
  // a post under the habitat window, holding its sign
  const wx = windowX(spot);
  r(wx + WINDOW.w / 2 - 1.5, WINDOW.y + WINDOW.h, 3, 22, "#8b5a2b");
  r(wx + WINDOW.w / 2 - 1.5, WINDOW.y + WINDOW.h, 1, 22, "#a87a44");
  return canvas;
}

// --- the habitat window -------------------------------------------------------------

function drawEmptyLot() {
  const canvas = $("trail-mini");
  const r = habitatPainter(canvas.getContext("2d"), MINI_PX);
  r(0, 0, HABITAT_W, HABITAT_H, "#8fb85a");
  r(0, 0, HABITAT_W, 30, "#a8d5e2");
  for (let x = 4; x < HABITAT_W; x += 14) r(x, 30, 2, 50, "#8b5a2b"); // an empty fenced lot
  for (const y of [40, 60, 78]) r(0, y, HABITAT_W, 2, "#a87a44");
  r(60, 46, 40, 20, "#fbf1dc"); // a "for sale" board
  r(60, 46, 40, 2, "#b8432f");
  r(78, 66, 4, 14, "#5c3a1a");
}

function setupMini(spot) {
  const h = trail.spots[spot];
  if (!h) {
    mini = null;
    drawEmptyLot();
    return;
  }
  const look = HABITAT_LOOKS[h.kind];
  backgrounds[h.kind] ||= habitatBackground(h.kind, MINI_PX);
  const area = { left: 2, right: HABITAT_W - 2, top: look.groundTop, bottom: look.groundBottom, sky: true, props: look.props, terrain: look.terrain };
  mini = { world: PetMotion.create(h.pets, area, MINI_PET_SCALE), background: backgrounds[h.kind] };
  drawMini();
}

function drawMini() {
  if (!mini) return;
  const ctx = $("trail-mini").getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(mini.background, 0, 0);
  PetMotion.draw(mini.world, habitatPainter(ctx, MINI_PX));
}

function tick() {
  if (!mini) return;
  PetMotion.step(mini.world);
  drawMini();
}

// --- walking the trail ----------------------------------------------------------------

function go(spot) {
  at = Math.max(0, Math.min(trail.spots.length - 1, spot));
  history.replaceState(null, "", `?at=${at}`);
  const h = trail.spots[at];
  const scene = $("trail-scene");
  scene.classList.remove("arrive");
  void scene.offsetWidth; // restart the fade
  scene.classList.add("arrive");

  const ctx = $("trail-canvas").getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(drawTrailScene(at), 0, 0);

  const win = $("trail-window");
  const x = windowX(at);
  Object.assign(win.style, {
    left: `${(x / SCENE_W) * 100}%`,
    top: `${(WINDOW.y / SCENE_H) * 100}%`,
    width: `${(WINDOW.w / SCENE_W) * 100}%`,
  });
  win.href = h ? `/pets/trail/${at}` : "/pets/shop?dept=habitats";
  win.setAttribute("aria-label", h ? `Visit ${h.name}` : "Empty lot: get a habitat at the Pet Shop");
  win.classList.toggle("empty", !h);

  const sign = $("trail-sign");
  Object.assign(sign.style, {
    left: `${((x + WINDOW.w / 2) / SCENE_W) * 100}%`,
    top: `${((WINDOW.y + WINDOW.h + 4) / SCENE_H) * 100}%`,
  });
  sign.innerHTML = h
    ? `${h.name}<small>${h.pets.length} of ${h.capacity} pets</small>`
    : `Empty lot<small>Get a habitat at the Pet Shop</small>`;

  $("trail-stop").textContent = `Stop ${at + 1} of ${trail.spots.length}`;
  // walking down past the first stop takes you back to the Pets hub
  $("trail-down").textContent = at === 0 ? "▼ Back to Pets" : "▼ Down the trail";
  $("trail-up").disabled = at === trail.spots.length - 1;
  setupMini(at);
}

// --- the map --------------------------------------------------------------------------

function plotAt(spot) {
  const y = MAP_H - 36 - spot * 14.5;
  const x = spot % 2 ? MAP_W - 6 - PLOT.w : 6;
  return { x, y };
}

function drawMap() {
  const canvas = $("map-canvas");
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const r = habitatPainter(ctx, MAP_PX);
  r(0, 0, MAP_W, MAP_H, "#9cc46a");
  const rand = seeded(99);
  for (let i = 0; i < 40; i++) drawPine(r, rand() * MAP_W, rand() * MAP_H, 3, i);
  for (let y = 0; y < MAP_H; y++) {
    const cx = MAP_W / 2 + Math.sin(y / 14) * 8;
    r(cx - 4, y, 8, 1, "#e8d3a8");
    r(cx - 4, y, 1, 1, "#d8c090");
    r(cx + 3, y, 1, 1, "#d8c090");
  }
  trail.spots.forEach((h, spot) => {
    const { x, y } = plotAt(spot);
    r(x - 1, y - 1, PLOT.w + 2, PLOT.h + 2, "#5c3a1a");
    if (h) {
      backgrounds[`map:${h.kind}`] ||= habitatBackground(h.kind, 1);
      ctx.drawImage(backgrounds[`map:${h.kind}`], x * MAP_PX, y * MAP_PX, PLOT.w * MAP_PX, PLOT.h * MAP_PX);
    } else {
      r(x, y, PLOT.w, PLOT.h, "#b8c88a");
      for (let k = 0; k < PLOT.w; k += 4) r(x + k, y + PLOT.h / 2, 2, 1, "#8b5a2b");
    }
    const sx = spot % 2 ? x - 1 : x + PLOT.w; // a little path to the trail
    const tx = MAP_W / 2 + Math.sin((y + PLOT.h / 2) / 14) * 8;
    r(Math.min(sx, tx), y + PLOT.h / 2 - 1, Math.abs(tx - sx), 3, "#e8d3a8");
  });
  // the gate at the bottom
  r(MAP_W / 2 - 14, MAP_H - 6, 3, 6, "#8b5a2b");
  r(MAP_W / 2 + 11, MAP_H - 6, 3, 6, "#8b5a2b");
  r(MAP_W / 2 - 15, MAP_H - 8, 30, 3, "#5c3a1a");
}

function renderMapSpots() {
  $("map-spots").replaceChildren(
    ...trail.spots.map((h, spot) => {
      const { x, y } = plotAt(spot);
      const b = document.createElement("button");
      b.className = "map-spot" + (h ? "" : " empty") + (spot === at ? " current" : "");
      b.dataset.spot = spot;
      Object.assign(b.style, {
        left: `${(x / MAP_W) * 100}%`,
        top: `${(y / MAP_H) * 100}%`,
        width: `${(PLOT.w / MAP_W) * 100}%`,
        height: `${(PLOT.h / MAP_H) * 100}%`,
      });
      b.innerHTML = h
        ? `<span class="map-label">${spot + 1}. ${h.name}<small>${h.pets.length}/${h.capacity} pets</small></span>`
        : `<span class="map-label">${spot + 1}. Empty lot</span>`;
      b.onclick = () => {
        $("trail-map").close();
        go(spot);
      };
      return b;
    })
  );
}

function openMap() {
  drawMap();
  renderMapSpots();
  $("trail-map").showModal();
  const current = document.querySelector(".map-spot.current");
  if (current) current.focus();
}

// --- start ----------------------------------------------------------------------------

async function load() {
  const r = await fetch("/api/trail");
  if (!r.ok) throw new Error(`/api/trail returned ${r.status}`);
  trail = await r.json();
  Header.update(trail);
  const asked = new URLSearchParams(location.search).get("at");
  const first = trail.spots.findIndex(Boolean);
  go(asked !== null ? Number(asked) : Math.max(0, first));
  $("trail-up").onclick = () => go(at + 1);
  $("trail-down").onclick = () => (at === 0 ? (location.href = "/pets") : go(at - 1));
  $("trail-map-open").onclick = openMap;
  document.querySelector(".map-close").onclick = () => $("trail-map").close();
  document.addEventListener("keydown", (e) => {
    if ($("trail-map").open || e.target.closest("input, select, textarea")) return;
    if (e.key === "ArrowUp" && at < trail.spots.length - 1) {
      e.preventDefault();
      go(at + 1);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      $("trail-down").click();
    }
  });
}

load()
  .then(() => setInterval(tick, TICK_MS))
  .catch((err) => {
    console.error(err);
    $("trail-message").textContent = `Couldn't open the Trailhead (${err.message}). Try reloading.`;
  });
