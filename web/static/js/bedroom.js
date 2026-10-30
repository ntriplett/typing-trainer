// The Home: three rooms you walk between, like the Pet Shop's halls.
//   bedroom   decorate it: drag furniture around (or click + arrow keys), put
//             pieces away, place ones from the inventory, pick wallpaper and
//             floor. The pets that come along live here (pet_motion.js): cats
//             and bunnies nap on the bed, everyone naps in pet beds and on
//             beanbags and rugs, and plays by the toys.
//   dressing  the Dressing Room: a closet, a hat stand, an accessory corner and
//             a vanity mirror to change your look at.
//   nook      the Window Nook: postcards of your places to travel to, and a
//             day & night switch.
// Drawing lives in room.js (the bedroom) and house_scenes.js (the rest);
// rules in app/room.py.

const $ = (id) => document.getElementById(id);
const SCENE_PX = 6; // the 160x90 grid on a 960x540 canvas
const canvas = $("room-canvas");
const selectedNameEl = $("selected-name");
const putAwayBtn = $("put-away");
const inventoryEl = $("inventory");
const wallpapersEl = $("wallpapers");
const flooringsEl = $("floorings");
const messageEl = $("room-message");

const ctx = canvas.getContext("2d");
ctx.imageSmoothingEnabled = false;
const px = (x, y, w, h, c) => {
  ctx.fillStyle = c;
  ctx.fillRect(Math.round(x * SCENE_PX), Math.round(y * SCENE_PX), Math.ceil(w * SCENE_PX), Math.ceil(h * SCENE_PX));
};

// Every place in the Home is a view: {title, hint, back (the view a
// "back" signpost goes to), nav (signposts onward: [text, view or /page],
// or a function giving them), enter() (loads what it needs), draw(), spots()}. The close-ups come from house_dressing.js and
// house_nook.js (HOUSE_VIEWS); the three rooms are here.
const VIEWS = {
  bedroom: {
    title: "My Bedroom",
    hint: "Drag things to move them. Click something, then use the arrow keys to nudge it.",
    nav: [["Dressing Room", "dressing"], ["Window Nook", "nook"]],
    draw() {
      const ledges = world.area.terrain.ledges;
      const extras = world.walkers.map((w) => ({
        bottom: w.ledge === null ? w.y : ledges[w.ledge].z, // on the bed: in front of it
        draw: () => PetMotion.drawOne(world, w, px, { ctx, unit: SCENE_PX }),
      }));
      paintRoom(px, state.room, { avatar: state.avatar, extras, selected, shell: (r) => drawBedroomDoors(r, state.avatar) });
    },
    spots: () => [
      spot("Dressing Room", BEDROOM_DOORS.dressing, () => go("dressing"), "dressing"),
      spot("Window Nook", BEDROOM_DOORS.nook, () => go("nook"), "nook"),
    ],
  },
  dressing: {
    title: "Dressing Room",
    hint: "Look around! The closet, the hats, the accessories and the mirror are all yours to try.",
    back: "bedroom",
    draw: () => drawDressingRoom(px, frame),
    spots() {
      const s = DRESSING_SPOTS;
      return [
        spot("Bedroom", s.bedroom, () => go("bedroom"), "bedroom"),
        spot("Closet", s.closet, () => go("closet"), "closet"),
        spot("Hats", s.hats, () => go("hats"), "hats"),
        spot("Accessories", s.accessories, () => go("accessories"), "accessories"),
        spot("Mirror", s.mirror, () => go("mirror"), "mirror"),
      ];
    },
  },
  nook: {
    title: "Window Nook",
    hint: "Your postcards: click a board to travel somewhere new. The switch by the window turns night on and off.",
    back: "bedroom",
    enter: () => House.loadPlaces(),
    draw: () => drawWindowNook(px, state.avatar, House.places || {}),
    spots: () => nookSpots(),
  },
  ...HOUSE_VIEWS,
};

let state = null; // latest /api/room response
let viewId = new URLSearchParams(location.search).get("room") || "bedroom";
if (!VIEWS[viewId]) viewId = "bedroom";
let selected = null; // placed piece id
let drag = null; // {id, dx, dy, moved}
let frame = 0;
let world = null; // the pets, moving about the bedroom (PetMotion)
let shown = null; // the view on screen (the one being walked to may still be loading)

async function load() {
  const r = await fetch("/api/room");
  if (r.status === 403) return new Promise(() => {}); // still a mystery: header.js shows why
  if (!r.ok) throw new Error(`/api/room returned ${r.status}`);
  setState(await r.json());
  await go(viewId);
}

function setState(data) {
  state = data;
  Header.update(data);
  world = petWorld(data, world);
  if (!state.room.items.some((p) => p.id === selected)) selected = null;
  renderSide();
  draw();
}

// --- views ------------------------------------------------------------------------

async function go(id) {
  viewId = id;
  const view = VIEWS[id];
  history.replaceState(null, "", id === "bedroom" ? location.pathname : `?room=${id}`);
  messageEl.textContent = "";
  $("decorate").hidden = id !== "bedroom";
  canvas.classList.toggle("editing", id === "bedroom");
  if (view.enter) {
    try {
      await view.enter();
    } catch (err) {
      messageEl.textContent = err.message;
    }
    if (viewId !== id) return; // walked on while it loaded
  }
  refresh();
}

// Redraws the current view's words, signposts and spots (after a change).
function refresh() {
  shown = viewId;
  const view = VIEWS[viewId];
  $("room-title").textContent = typeof view.title === "function" ? view.title() : view.title;
  $("room-hint").textContent = view.hint;
  const nav = [];
  if (view.back) nav.push(signpost(VIEWS[view.back].title, () => go(view.back)));
  const onward = typeof view.nav === "function" ? view.nav() : view.nav || [];
  for (const [text, to] of onward) nav.push(signpost(text, () => (to.startsWith("/") ? (location.href = to) : go(to)), true));
  $("room-nav").replaceChildren(...nav);
  $("house-spots").replaceChildren(...view.spots());
  draw();
}

// A clickable spot over the scene. No sign: you find things by exploring,
// and its name shows when you point at it. `id` names it for tests.
function spot(name, box, onclick, id = null) {
  const b = document.createElement("button");
  b.className = "shop-spot top-sign tip-only";
  if (id) b.dataset.spot = id;
  b.setAttribute("aria-label", name);
  Object.assign(b.style, {
    left: `${(box.x / HOUSE_W) * 100}%`,
    top: `${(box.y / HOUSE_H) * 100}%`,
    width: `${(box.w / HOUSE_W) * 100}%`,
    height: `${(box.h / HOUSE_H) * 100}%`,
  });
  b.innerHTML = `<span class="spot-sign"><span class="spot-name">${name}</span></span>`;
  b.onclick = onclick;
  return b;
}

function signpost(text, onclick, forward = false) {
  const b = document.createElement("button");
  b.className = "signpost" + (forward ? " forward" : "");
  b.textContent = text;
  b.onclick = onclick;
  return b;
}

function draw() {
  if (state && shown) VIEWS[shown].draw();
}

// What the close-ups (house_dressing.js, house_nook.js) use.
const House = {
  px,
  ctx,
  spot,
  go,
  refresh,
  get avatar() {
    return state.avatar;
  },
  get frame() {
    return frame;
  },
  say(text) {
    messageEl.textContent = text;
  },
  // A JSON call; on success the header and avatar take the new /api/me.
  async call(url, method = "GET", body = null) {
    const r = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : null,
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "Something went wrong.");
    if (data.avatar && method !== "GET") {
      state.avatar = data.avatar;
      Header.update(data);
      world = petWorld(state, world);
    }
    return data;
  },
  // The places in each group, which you own, and night (the store lists
  // them with its night unlocks): {group: [{id, name, owned, current}]}.
  places: null,
  night: null, // {group: unlocked} for the night unlocks you own
  async loadPlaces() {
    const data = await House.call("/api/store");
    const current = data.avatar.background;
    House.places = {};
    House.night = {};
    for (const item of data.items.filter((i) => i.slot === "night")) {
      House.places[item.group] = item.places.map((p) => ({ ...p, current: p.id === current }));
      House.night[item.group] = item.owned;
    }
  },
};

// --- pets and the furniture ---------------------------------------------------------

// Which pets can curl up on your bed.
const BED_PETS = ["cat", "bunny"];
const TOYS = /toy_chest|train|teddy|rocket/;

// Where pets go in the bedroom, from its furniture: the bed's blanket is a
// ledge (cats and bunnies only) with a nap spot, pet beds, beanbags and rugs
// are nap spots, toys are places to play, and standing furniture blocks feet.
function petArea(room) {
  const area = { left: 0, right: ROOM_W, top: FLOOR_TOP + 3, bottom: ROOM_H - 2, props: [], terrain: { blocks: [], ledges: [] } };
  for (const p of room.items) {
    const f = furnitureFor(p.item_id);
    if (!f || isWallPiece(p.item_id, room.zones)) continue;
    const { w, h } = f.def;
    const mid = p.x + w / 2;
    if (p.item_id.startsWith("furniture_bed_")) {
      const ledge = area.terrain.ledges.push({ x0: p.x + 5, x1: p.x + w - 1, y: p.y + 9, z: p.y + h + 0.5, who: BED_PETS }) - 1;
      area.props.push({ x: p.x + 18, y: p.y + 9, action: "nap", ledge, who: BED_PETS });
    } else if (p.item_id === "furniture_pet_bed") {
      area.props.push({ x: mid, y: p.y + 5, action: "nap" });
      continue;
    } else if (p.item_id === "furniture_beanbag") {
      area.props.push({ x: mid, y: p.y + h + 1, action: "nap" });
    } else if (f.def.flat) {
      area.props.push({ x: mid, y: p.y + h / 2, action: "nap" });
      continue;
    } else if (TOYS.test(p.item_id)) {
      area.props.push({ x: mid, y: p.y + h + 1, action: "jump", color: "#e8b33e" });
    }
    area.terrain.blocks.push({ x: p.x, y: p.y + h - 3, w, h: 3 });
  }
  return area;
}

// A new PetMotion world for the room's furniture, keeping where pets were
// on the floor (anyone up on the bed hops down: the bed may have moved).
function petWorld(data, old) {
  const pets = data.avatar.pets || [];
  const next = PetMotion.create(pets, petArea(data.room), ALONG_PET_SCALE);
  const before = new Map((old ? old.walkers : []).map((w) => [w.p.id, w]));
  for (const w of next.walkers) {
    const was = before.get(w.p.id);
    if (was && was.ledge === null) Object.assign(w, { x: was.x, y: was.y, dir: was.dir });
  }
  return next;
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
  const wall = isWallPiece(itemId, state.room.zones);
  const [left, right] = wall ? BEDROOM_WALL_SPAN : [0, ROOM_W];
  const cx = Math.max(left, Math.min(right - def.w, Math.round(x)));
  let cy;
  if (wall) cy = Math.max(1, Math.min(WALL_BOTTOM - def.h - 1, y));
  else if (def.flat) cy = Math.max(FLOOR_TOP, Math.min(ROOM_H - def.h, y));
  else cy = Math.max(FLOOR_TOP + 4 - def.h, Math.min(ROOM_H - def.h, y));
  return [cx, Math.round(cy)];
}

function toRoom(e) {
  const rect = canvas.getBoundingClientRect();
  return [((e.clientX - rect.left) / rect.width) * ROOM_W, ((e.clientY - rect.top) / rect.height) * ROOM_H];
}

// --- interaction ------------------------------------------------------------------

canvas.addEventListener("pointerdown", (e) => {
  if (viewId !== "bedroom") return;
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
  if (viewId !== "bedroom") return;
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

// --- life: pets move about ---------------------------------------------------

function tick() {
  frame += 1;
  if (world && viewId === "bedroom") PetMotion.step(world);
  if (!drag) draw();
}

load()
  .then(() => setInterval(tick, 150))
  .catch((err) => {
    console.error(err);
    messageEl.textContent = `Couldn't load your room (${err.message}). Try reloading.`;
  });
