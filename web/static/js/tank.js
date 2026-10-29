// One tank up close (PLAN.md 11k): fish swimming (fish_motion.js), and
// Decorate mode, like the bedroom: pick the background and bottom you own,
// put pieces from storage into the tank, drag them about, flip them, set
// them behind or in front of the fish, or put them away. The Fish panel
// moves fish in and out (10 at most).

const $ = (id) => document.getElementById(id);
const UNIT = 6; // screen pixels per tank unit: 160x70 on 960x420
const TICK_MS = 100;
const FISH_SCALE = 0.4; // tank units per fish pixel: a grown fish is a few inches in a 48" tank
const LAYER_NAMES = { back: "Behind fish", middle: "Fish swim around", front: "In front of fish" };

let state = null; // /api/aquarium/{spot}
let spot = 0;
let world = null;
let cache = {};
let t = 0;
let mode = null; // "decorate" | "fish" | null
let selected = null; // a placed piece's id
let drag = null; // {id, dx, dy}

async function call(url, method = "GET", body = null) {
  const r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : null,
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || "Something went wrong.");
  Header.update(data);
  return data;
}

function say(text) {
  $("tank-message").textContent = text || "";
}

async function act(url, method, body) {
  try {
    setState(await call(url, method, body));
    say("");
  } catch (err) {
    say(err.message);
  }
}

const itemOf = (id) => ({ id, ...state.items[id] });
const pieceById = (id) => state.tank.pieces.find((p) => p.id === id);

function setState(data) {
  const old = world;
  state = data;
  $("tank-name").textContent = state.tank.name;
  document.title = `Typing Trainer — ${state.tank.name}`;
  world = FishMotion.create(state.tank.fish, state.tank, state.items, FISH_SCALE);
  if (old) {
    // keep fish where they were when the tank changes
    for (const f of world.fish) {
      const was = old.fish.find((o) => o.f.id === f.f.id);
      if (was) Object.assign(f, { x: was.x, y: was.y, z: was.z, vx: was.vx, vy: was.vy, dir: was.dir });
    }
  }
  if (selected && !pieceById(selected)) selected = null;
  $("fish-button").textContent = `🐠 Fish (${state.tank.fish.length}/${state.tank.capacity})`;
  renderPanels();
  draw();
}

// --- drawing ------------------------------------------------------------------------

function draw() {
  const ctx = $("tank-canvas").getContext("2d");
  drawTankScene(ctx, UNIT, world, state.tank, t, cache);
  if (mode === "decorate" && selected) {
    const p = pieceById(selected);
    const [w, h] = aquaSize(itemOf(p.item_id), p.rot);
    ctx.strokeStyle = "#e8b33e";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(p.x * UNIT - 2, (p.y - h) * UNIT - 2, w * UNIT + 4, h * UNIT + 4);
    ctx.setLineDash([]);
  }
}

function tick() {
  t += 1;
  FishMotion.step(world);
  draw();
}

// --- panels ------------------------------------------------------------------------

function renderPanels() {
  $("decorate-panel").hidden = mode !== "decorate";
  $("fish-panel").hidden = mode !== "fish";
  $("decorate").classList.toggle("active", mode === "decorate");
  $("decorate").textContent = mode === "decorate" ? "✓ Done decorating" : "🎨 Decorate";
  if (mode === "decorate") renderDecorate();
  if (mode === "fish") renderFish();
}

function swatch(kind, id, current) {
  const b = document.createElement("button");
  b.className = "look-pick" + (id === current ? " current" : "");
  b.dataset[kind] = id;
  const c = document.createElement("canvas");
  c.width = 96;
  c.height = 42;
  const ctx = c.getContext("2d");
  const u = c.width / TANK_W;
  drawAquaLook((x, y, w, h, col) => {
    ctx.fillStyle = col;
    ctx.fillRect(x * u, y * u, w * u, h * u);
  }, kind === "background" ? id : "sand", kind === "substrate" ? id : "bg_blue");
  b.append(c, Object.assign(document.createElement("span"), { textContent: state.items[id].name }));
  b.onclick = () => act(`/api/aquarium/${spot}/look`, "PUT", { [kind]: id });
  return b;
}

function renderDecorate() {
  const looks = state.looks.map((id) => ({ id, ...state.items[id] }));
  $("look-backgrounds").replaceChildren(...looks.filter((l) => l.kind === "background").map((l) => swatch("background", l.id, state.tank.background)));
  $("look-substrates").replaceChildren(...looks.filter((l) => l.kind === "substrate").map((l) => swatch("substrate", l.id, state.tank.substrate)));
  // storage: one button per kind of piece, with how many are waiting
  const groups = new Map();
  for (const p of state.storage) groups.set(p.item_id, [...(groups.get(p.item_id) || []), p]);
  $("storage").replaceChildren(
    ...[...groups].map(([id, copies]) => {
      const b = document.createElement("button");
      b.className = "storage-piece";
      b.dataset.item = id;
      const c = document.createElement("canvas");
      c.width = 64;
      c.height = 56;
      pieceIcon(c, itemOf(id));
      b.append(c, Object.assign(document.createElement("span"), { textContent: `${state.items[id].name} ×${copies.length}` }));
      b.onclick = async () => {
        await act(`/api/aquarium/${spot}/pieces`, "POST", { piece: copies[0].id });
        selected = copies[0].id;
        renderPieceTools();
        draw();
        $("tank-canvas").scrollIntoView({ block: "nearest", behavior: "smooth" }); // see where it went
      };
      return b;
    })
  );
  if (!groups.size) $("storage").innerHTML = `<p class="hint">Nothing in storage.</p>`;
  renderPieceTools();
}

function pieceIcon(canvas, item) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const s = Math.min((canvas.width - 6) / item.w, (canvas.height - 6) / item.h, 6);
  const ox = (canvas.width - item.w * s) / 2;
  const oy = canvas.height - 3 - item.h * s;
  drawAquaPiece((x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(ox + x * s, oy + (y - 0) * s, w * s, h * s);
  }, item, 0, item.h, false, 40);
}

function renderPieceTools() {
  const box = $("piece-tools");
  const p = selected && pieceById(selected);
  box.hidden = !p;
  if (!p) return;
  const item = state.items[p.item_id];
  box.innerHTML = `<b>${item.name}</b>`;
  const button = (text, onclick, cls = "") => {
    const b = document.createElement("button");
    b.textContent = text;
    b.className = cls;
    b.onclick = onclick;
    box.appendChild(b);
    return b;
  };
  button("↔ Flip", () => act(`/api/aquarium/${spot}/pieces/${p.id}`, "PUT", { x: p.x, y: p.y, flip: !p.flip }));
  if (item.turns) button("⟳ Turn", () => act(`/api/aquarium/${spot}/pieces/${p.id}`, "PUT", { x: p.x, y: p.y, rot: (p.rot + 90) % 360 }));
  for (const layer of state.layers) {
    button(LAYER_NAMES[layer], () => act(`/api/aquarium/${spot}/pieces/${p.id}`, "PUT", { x: p.x, y: p.y, layer }), p.layer === layer ? "button-go" : "");
  }
  button("📦 Put away", () => {
    selected = null;
    act(`/api/aquarium/${spot}/pieces/${p.id}`, "DELETE");
  });
}

function fishCard(f, action, label) {
  const b = document.createElement("button");
  b.className = "fish-card";
  b.dataset.fish = f.id;
  const c = document.createElement("canvas");
  c.width = 72;
  c.height = 44;
  const ctx = c.getContext("2d");
  const { w, h } = petSize(f.genes, f.growth);
  const s = Math.min(1.5, (c.width - 6) / w, (c.height - 6) / h);
  drawPet((x, y, ww, hh, col) => {
    ctx.fillStyle = col;
    ctx.fillRect(x, y, ww, hh);
  }, (c.width - w * s) / 2, (c.height + h * s) / 2, f.genes, f.growth, { scale: s, shadow: false });
  b.append(c, Object.assign(document.createElement("span"), { textContent: `${f.name}: ${label}` }));
  b.onclick = action;
  return b;
}

function renderFish() {
  const fish = state.tank.fish;
  $("fish-count").textContent = `In this tank: ${fish.length} of ${state.tank.capacity}`;
  $("tank-fish").replaceChildren(...fish.map((f) => fishCard(f, () => act(`/api/aquarium/${spot}/fish/${f.id}`, "DELETE"), "take out")));
  if (!fish.length) $("tank-fish").innerHTML = `<p class="hint">No fish yet!</p>`;
  const full = fish.length >= state.tank.capacity;
  $("waiting-fish").replaceChildren(
    ...state.waiting_fish.map((f) => {
      const card = fishCard(f, () => act(`/api/aquarium/${spot}/fish/${f.id}`, "PUT"), "put in");
      card.disabled = full;
      return card;
    })
  );
  if (!state.waiting_fish.length) $("waiting-fish").innerHTML = `<p class="hint">Every fish has a home. Find more fish at the <a href="/pets/shop?dept=fish">Pet Shop</a>!</p>`;
}

// --- dragging pieces ----------------------------------------------------------------

function toTank(e) {
  const rect = $("tank-canvas").getBoundingClientRect();
  return [((e.clientX - rect.left) / rect.width) * TANK_W, ((e.clientY - rect.top) / rect.height) * TANK_H];
}

// The piece under a point, front layer first.
function pieceAt(x, y) {
  const order = ["front", "middle", "back"];
  const hits = state.tank.pieces.filter((p) => {
    const [w, h] = aquaSize(state.items[p.item_id], p.rot);
    return x >= p.x && x <= p.x + w && y >= p.y - h && y <= p.y;
  });
  hits.sort((a, b) => order.indexOf(a.layer) - order.indexOf(b.layer) || b.id - a.id);
  return hits[0];
}

function startDrag(e) {
  if (mode !== "decorate") return;
  const [x, y] = toTank(e);
  const p = pieceAt(x, y);
  selected = p ? p.id : null;
  renderPieceTools();
  if (p) {
    drag = { id: p.id, dx: x - p.x, dy: y - p.y, moved: false };
    $("tank-canvas").setPointerCapture(e.pointerId);
  }
  draw();
}

function moveDrag(e) {
  if (!drag) return;
  const [x, y] = toTank(e);
  const p = pieceById(drag.id);
  const [w, h] = aquaSize(state.items[p.item_id], p.rot);
  p.x = Math.min(Math.max(x - drag.dx, 0), TANK_W - w);
  p.y = Math.min(Math.max(y - drag.dy, h), TANK_H);
  drag.moved = true;
  world.feats = FishMotion.features(state.tank.pieces, state.items);
}

function endDrag() {
  if (!drag) return;
  const p = pieceById(drag.id);
  const moved = drag.moved;
  drag = null;
  if (moved) act(`/api/aquarium/${spot}/pieces/${p.id}`, "PUT", { x: p.x, y: p.y });
}

function startRename() {
  const head = document.querySelector(".tank-name");
  const form = document.createElement("form");
  form.className = "rename-form";
  form.innerHTML = `<input id="rename-input" maxlength="20" aria-label="New tank name" />
    <button class="button-go">Save</button><button type="button" class="link-button">Cancel</button>`;
  const input = form.querySelector("input");
  input.value = state.tank.name;
  const done = () => form.replaceWith(head);
  form.onsubmit = async (e) => {
    e.preventDefault();
    await act(`/api/aquarium/${spot}/name`, "PUT", { name: input.value });
    done();
  };
  form.querySelector(".link-button").onclick = done;
  input.onkeydown = (e) => {
    if (e.key === "Escape") done();
  };
  head.replaceWith(form);
  input.focus();
  input.select();
}

// --- start ---------------------------------------------------------------------------

async function load() {
  spot = Number(location.pathname.split("/").pop());
  $("tank-back").href = spot >= 7 ? "/pets/aquarium?room=river" : spot >= 4 ? "/pets/aquarium?room=reef" : "/pets/aquarium";
  const r = await fetch(`/api/aquarium/${spot}`);
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || `/api/aquarium/${spot} returned ${r.status}`);
  Header.update(data);
  setState(data);
  $("decorate").onclick = () => {
    mode = mode === "decorate" ? null : "decorate";
    selected = null;
    renderPanels();
    draw();
  };
  $("fish-button").onclick = () => {
    mode = mode === "fish" ? null : "fish";
    renderPanels();
  };
  $("rename-tank").onclick = startRename;
  const canvas = $("tank-canvas");
  canvas.addEventListener("pointerdown", startDrag);
  canvas.addEventListener("pointermove", moveDrag);
  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);
}

load()
  .then(() => setInterval(tick, TICK_MS))
  .catch((err) => {
    console.error(err);
    say(`${err.message} Head back to the Aquarium.`);
  });
