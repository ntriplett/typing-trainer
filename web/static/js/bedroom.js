// The bedroom editor: drag furniture around (or click + arrow keys),
// put pieces away, place ones from the inventory, and pick wallpaper and
// floor. Your avatar stands in the room and the pets that come along
// wander the floor. Drawing lives in room.js; rules in app/room.py.

const canvas = document.getElementById("room-canvas");
const selectedNameEl = document.getElementById("selected-name");
const putAwayBtn = document.getElementById("put-away");
const inventoryEl = document.getElementById("inventory");
const wallpapersEl = document.getElementById("wallpapers");
const flooringsEl = document.getElementById("floorings");
const messageEl = document.getElementById("room-message");

const px = canvasPx(canvas, ROOM);
let state = null; // latest /api/room response
let selected = null; // placed piece id
let drag = null; // {id, dx, dy, moved}
let frame = 0;
let walkers = [];

async function load() {
  const r = await fetch("/api/room");
  if (!r.ok) throw new Error(`/api/room returned ${r.status}`);
  setState(await r.json());
}

function setState(data) {
  state = data;
  Header.update(data);
  const old = new Map(walkers.map((w) => [w.pet.id, w]));
  walkers = (data.avatar.pets || []).map((pet, i) => {
    const w = old.get(pet.id) || { x: 10 + i * 50, y: 80 + i * 8, dir: i ? -1 : 1 };
    return { ...w, pet };
  });
  if (!state.room.items.some((p) => p.id === selected)) selected = null;
  renderSide();
  draw();
}

function draw() {
  paintRoom(px, state.room, { avatar: state.avatar, walkers, frame, selected });
}

// --- geometry -------------------------------------------------------------------

function pieceAt(rx, ry) {
  // topmost first: standing floor pieces (front to back), rugs, wall pieces
  const pieces = state.room.items.map((p) => ({ ...p, f: furnitureFor(p.item_id) })).filter((p) => p.f);
  const wall = (p) => isWallPiece(p.item_id, state.room.zones);
  const order = [
    ...pieces.filter((p) => !wall(p) && !p.f.def.flat).sort((a, b) => b.y + b.f.def.h - (a.y + a.f.def.h)),
    ...pieces.filter((p) => !wall(p) && p.f.def.flat),
    ...pieces.filter(wall),
  ];
  return order.find((p) => rx >= p.x && rx < p.x + p.f.def.w && ry >= p.y && ry < p.y + p.f.def.h);
}

// Keep wall pieces on the wall and floor pieces standing on the floor.
function clampPosition(itemId, x, y) {
  const { def } = furnitureFor(itemId);
  const cx = Math.max(0, Math.min(ROOM - def.w, Math.round(x)));
  let cy;
  if (isWallPiece(itemId, state.room.zones)) cy = Math.max(1, Math.min(WALL_BOTTOM - def.h - 1, y));
  else if (def.flat) cy = Math.max(FLOOR_TOP, Math.min(ROOM - def.h, y));
  else cy = Math.max(FLOOR_TOP + 4 - def.h, Math.min(ROOM - def.h, y));
  return [cx, Math.round(cy)];
}

function toRoom(e) {
  const rect = canvas.getBoundingClientRect();
  return [((e.clientX - rect.left) / rect.width) * ROOM, ((e.clientY - rect.top) / rect.height) * ROOM];
}

// --- interaction ------------------------------------------------------------------

canvas.addEventListener("pointerdown", (e) => {
  const [rx, ry] = toRoom(e);
  const piece = pieceAt(rx, ry);
  selected = piece ? piece.id : null;
  if (piece) {
    drag = { id: piece.id, dx: rx - piece.x, dy: ry - piece.y, moved: false };
    canvas.setPointerCapture(e.pointerId);
  }
  renderSide();
  draw();
});

canvas.addEventListener("pointermove", (e) => {
  if (!drag) return;
  const [rx, ry] = toRoom(e);
  const piece = state.room.items.find((p) => p.id === drag.id);
  [piece.x, piece.y] = clampPosition(piece.item_id, rx - drag.dx, ry - drag.dy);
  drag.moved = true;
  draw();
});

canvas.addEventListener("pointerup", () => {
  if (drag && drag.moved) savePosition(drag.id);
  drag = null;
});

canvas.addEventListener("keydown", (e) => {
  const piece = state.room.items.find((p) => p.id === selected);
  const step = e.shiftKey ? 4 : 1;
  const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
  if (!piece || !moves[e.key]) return;
  e.preventDefault();
  const [dx, dy] = moves[e.key];
  [piece.x, piece.y] = clampPosition(piece.item_id, piece.x + dx, piece.y + dy);
  draw();
  clearTimeout(piece.saveTimer);
  piece.saveTimer = setTimeout(() => savePosition(piece.id), 400); // save once the nudging stops
});

function savePosition(id) {
  const piece = state.room.items.find((p) => p.id === id);
  act(`/api/room/items/${id}`, "PUT", { x: piece.x, y: piece.y });
}

putAwayBtn.addEventListener("click", () => {
  if (selected !== null) act(`/api/room/items/${selected}`, "DELETE");
});

// --- side panel ----------------------------------------------------------------

function thumbButton(itemId, label, onClick, active = false) {
  const btn = document.createElement("button");
  btn.className = "thumb-choice" + (active ? " selected" : "");
  btn.title = label;
  btn.dataset.itemId = itemId;
  const c = makeAvatarCanvas(96);
  drawRoomThumb(c, itemId);
  const span = document.createElement("span");
  span.textContent = label;
  btn.append(c, span);
  btn.onclick = onClick;
  return btn;
}

function renderSide() {
  const piece = state.room.items.find((p) => p.id === selected);
  selectedNameEl.textContent = piece ? state.room.names[piece.item_id] : "Nothing yet. Click a piece of furniture!";
  putAwayBtn.hidden = !piece;

  inventoryEl.replaceChildren(
    ...(state.room.inventory.length
      ? state.room.inventory.map((i) => thumbButton(i.item_id, `Place: ${i.name}`, () => place(i.item_id)))
      : [Object.assign(document.createElement("p"), { textContent: "Everything you own is in the room." })])
  );

  const surfaceButtons = (ids, current) =>
    ids.map((id) => thumbButton(id, state.room.names[id] || id, () => act("/api/room/surface", "PUT", { item_id: id }), id === current));
  wallpapersEl.replaceChildren(...surfaceButtons(["wallpaper_cream", ...state.room.wallpapers.filter((w) => w !== "wallpaper_cream")], state.room.wallpaper));
  flooringsEl.replaceChildren(...surfaceButtons(["flooring_planks", ...state.room.floorings.filter((f) => f !== "flooring_planks")], state.room.flooring));
}

// Place from the inventory and select it, ready to drag or nudge.
async function place(itemId) {
  await act("/api/room/items", "POST", { item_id: itemId });
  const placed = state.room.items.find((p) => p.item_id === itemId);
  if (placed) {
    selected = placed.id;
    renderSide();
    draw();
  }
}

async function act(url, method, body = null) {
  messageEl.textContent = "";
  const r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : null,
  });
  const data = await r.json();
  if (!r.ok) {
    messageEl.textContent = data.detail || "Something went wrong.";
    await load(); // put things back where the server has them
    return;
  }
  setState(data);
}

// --- life: pets wander, you bob ---------------------------------------------------

function tick() {
  frame += 1;
  for (const w of walkers) {
    const width = PET_ROWS[w.pet.species][w.pet.stage][0].length;
    w.x += w.dir * 0.4;
    if (w.x < 1 || w.x > ROOM - width - 1) w.dir *= -1;
    if (Math.random() < 0.01) w.dir *= -1;
  }
  if (!drag) draw();
}

load()
  .then(() => setInterval(tick, 150))
  .catch((err) => {
    console.error(err);
    messageEl.textContent = `Couldn't load your room (${err.message}). Try reloading.`;
  });
