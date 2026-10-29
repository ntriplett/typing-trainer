// The Pet Shop (PLAN.md 11h): you walk in to the entrance hall and click a
// department's doorway or corner; each department is a themed room
// (shop_scenes.js) where its pets wait at their stations, moving about
// (pet_motion.js), with price tags. Big departments have two rooms. Click a
// pet for a close-up: as a baby and all grown up, its colors, what's rare
// about it, and Buy / Save for me. Special Orders adds an order form
// (species, colors, a sample pet); Habitats sells habitats instead of pets.
// Rules live in app/pet_shop.py; pets are drawn by pet_render.js.

const $ = (id) => document.getElementById(id);
const TICK_MS = 400;
const SCENE_PX = 6; // the 160x90 scenes on a 960x540 canvas
const SCENE_TICK_MS = 120;
// Room pet scales to try, biggest first: whole screen pixels per pet pixel.
const ROOM_SCALES = [1, 5 / 6, 2 / 3, 1 / 2, 1 / 3];
const BABY = 0;
const ORDER_SAMPLE_GROWTH = 10; // the order form's sample shows what the pets grow into
const GROWN = 10;
// rare_features() multipliers worth a badge, and the "super rare" ones
const RARE_SHOWN = 1.2;
const SUPER_RARE = 1.4;
const RARE_LABEL = {
  coat: "Three colors",
  pattern: "Rare pattern",
  fins: "Rare fins",
  mix: "Mixed breed",
  eyes: "Rare eyes",
  "odd eyes": "Odd eyes",
  sparkle: "Sparkly eyes",
  "main color": "Rare color",
};
const TIER_NAME = { everyday: "Outdoors", cozy: "Cozy", magical: "Magical" };
const DEPT_ICON = { fish: "🐠", household: "🐱", farm: "🐐", reptiles: "🐢", mythical: "🐉", orders: "📋", habitats: "🌳", supplies: "🦴" };

let front = null; // /api/pets/shop
let dept = null; // /api/pets/shop/{id}
let deptId = null; // null: the entrance hall
let page = 0; // which of a department's rooms
let scene = null; // what's drawn: {bg, front, pets: [{slot, world}]}
let detailIndex = null; // the slot in the close-up
let frame = 0;
let pick = null; // the order form: {species, primary, secondary}
let preview = null; // a sample pet for the order form

const PLURAL = { bunny: "bunnies", fish: "fish", fox: "foxes", sheep: "sheep", phoenix: "phoenixes" };
const speciesName = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const plural = (s) => PLURAL[s] || `${s}s`;
const slotAt = (index) => dept && dept.slots.find((s) => s.index === index);
const coins = (n) => `<span class="coins-inline"><span class="coin-icon"></span>${n.toLocaleString()}</span>`;

// --- drawing -----------------------------------------------------------------------

function paint(canvas, genes, growth, scale) {
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const px = (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x), Math.round(y), Math.ceil(w), Math.ceil(h));
  };
  const { w, h } = petSize(genes, growth);
  // fish swim in the middle of the water; everyone else stands on the ground
  const bottom = genes.species === "fish" ? Math.round((canvas.height + h * scale) / 2) : canvas.height - 8;
  drawPet(px, Math.round((canvas.width - w * scale) / 2), bottom, genes, growth, { frame, scale });
}

// The biggest whole-pixel scale that fits every one of these pets, so the
// shop shows their sizes truthfully.
function fitScale(pets, growth, w, h, most) {
  let scale = most;
  for (const genes of pets) {
    const size = petSize(genes, growth);
    scale = Math.min(scale, Math.floor((w - 8) / size.w), Math.floor((h - 12) / size.h));
  }
  return Math.max(1, scale);
}

function tick() {
  frame += 1;
  for (const canvas of document.querySelectorAll("canvas[data-index]")) {
    const slot = slotAt(Number(canvas.dataset.index));
    if (slot && !slot.sold) paint(canvas, slot.genes, Number(canvas.dataset.growth), Number(canvas.dataset.scale));
  }
  const sample = $("order-preview");
  if (sample && preview) paint(sample, preview, ORDER_SAMPLE_GROWTH, Number(sample.dataset.scale));
}

function petCanvas(slot, growth, w, h, scale) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.dataset.index = slot.index;
  canvas.dataset.growth = growth;
  canvas.dataset.scale = scale;
  paint(canvas, slot.genes, growth, scale);
  return canvas;
}

// --- loading -----------------------------------------------------------------------

async function call(url, method = "GET", body = null) {
  const r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : null,
  });
  const data = await r.json();
  if (!r.ok) throw Object.assign(new Error(data.detail || "Something went wrong."), { status: r.status });
  Header.update(data);
  return data;
}

function say(text) {
  $("shop-message").textContent = text || "";
}

async function loadFront() {
  front = await call("/api/pets/shop");
  renderBanners();
}

async function openDept(id, toPage = 0) {
  say("");
  deptId = id;
  page = toPage;
  history.replaceState(null, "", `?dept=${id}${page ? `&page=${page}` : ""}`);
  try {
    setDept(await call(`/api/pets/shop/${id}`));
  } catch (err) {
    say(err.message);
  }
}

function setDept(data) {
  dept = data;
  front.saved = data.saved;
  front.coupon = deptId === "household" ? data.coupon : front.coupon;
  renderBanners();
  renderFloor();
  if (detailIndex !== null) renderDetail();
}

// --- the entrance hall --------------------------------------------------------------

function goEntrance() {
  say("");
  deptId = null;
  dept = null;
  history.replaceState(null, "", location.pathname);
  renderEntrance();
  renderBanners();
}

function renderEntrance() {
  $("dept-title").textContent = "Welcome to the Pet Shop!";
  $("dept-hint").textContent = "Click a department to look around. New pets arrive every night.";
  $("shop-grid").replaceChildren();
  $("shop-scene").hidden = false;
  const open = Object.fromEntries(front.departments.map((d) => [d.id, d.open]));
  const bg = sceneCanvas();
  drawShopEntrance(habitatPainter(bg.getContext("2d"), SCENE_PX), open);
  scene = { bg, front: null, pets: [] };
  drawScene();
  $("shop-spots").replaceChildren(
    ...front.departments.map((d) => {
      const spot = SHOP_SPOTS[d.id];
      const btn = document.createElement("button");
      btn.className = "shop-spot" + (d.open ? "" : " closed");
      btn.dataset.dept = d.id;
      place(btn, spot);
      const lock = d.soon ? "Coming soon" : `🔒 Learn ${d.missing.toUpperCase().split("").join(" ")}`;
      btn.setAttribute("aria-label", d.open ? d.name : `${d.name}: ${lock}`);
      btn.innerHTML = `<span class="spot-sign">${DEPT_ICON[d.id] || "🐾"} <span class="spot-name">${d.name}</span>${d.open ? "" : `<small>${lock}</small>`}</span>`;
      btn.onclick = () =>
        d.open ? openDept(d.id) : say(d.soon ? `${d.name} is coming soon!` : `${d.name} opens when you learn ${lock.slice(9)}.`);
      return btn;
    })
  );
}

// Lays an element over the scene at a 160x90 box.
function place(el, { x, y, w, h }) {
  Object.assign(el.style, {
    left: `${(x / SHOP_W) * 100}%`,
    top: `${(y / SHOP_H) * 100}%`,
    width: `${(w / SHOP_W) * 100}%`,
    height: `${(h / SHOP_H) * 100}%`,
  });
}

function sceneCanvas() {
  const c = document.createElement("canvas");
  c.width = SHOP_W * SCENE_PX;
  c.height = SHOP_H * SCENE_PX;
  return c;
}

function drawScene() {
  if (!scene) return;
  const ctx = $("shop-canvas").getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(scene.bg, 0, 0);
  const px = habitatPainter(ctx, SCENE_PX);
  for (const { world } of scene.pets) PetMotion.draw(world, px);
  if (scene.front) ctx.drawImage(scene.front, 0, 0);
}

function sceneTick() {
  if (!scene || !scene.pets.length) return;
  for (const { world } of scene.pets) PetMotion.step(world);
  drawScene();
}

function renderBanners() {
  const coupon = $("shop-coupon");
  coupon.hidden = !front.coupon;
  coupon.innerHTML = `<span class="banner-icon">🎟️</span>
    <span><b>You have a pet coupon!</b> Pick any Household pet for free.</span>`;
  if (deptId !== "household") {
    const go = document.createElement("button");
    go.className = "button-gold";
    go.textContent = "Go to Household Pets";
    go.onclick = () => openDept("household");
    coupon.appendChild(go);
  }

  const saved = $("shop-saved");
  const s = front.saved;
  saved.hidden = !s;
  if (!s) return;
  const where = front.departments.find((d) => d.id === s.dept).name;
  saved.innerHTML = `<span class="banner-icon">🎀</span>
    <span><b>Saved for you:</b> a ${speciesName(s.species).toLowerCase()} in ${where}, ${coins(s.price)}</span>`;
  const see = document.createElement("button");
  see.textContent = "See it";
  see.onclick = async () => {
    if (deptId !== s.dept) await openDept(s.dept);
    showDetail(s.index);
  };
  saved.appendChild(see);
}

// --- the shop floor ------------------------------------------------------------------

function renderFloor() {
  const d = dept.department;
  $("shop-grid").replaceChildren();
  $("shop-grid").className = "shop-grid";
  if (d.id === "habitats") return renderHabitats();
  renderRoom();
  if (d.id === "orders") return renderOrders();
  $("dept-hint").textContent = dept.coupon
    ? "Use your coupon on any pet here, or buy with coins. Click a pet to meet it!"
    : "New pets arrive every night. Click a pet to meet it!";
}

// --- a department's room ----------------------------------------------------------

function roomPages(def) {
  return Math.max(1, Math.ceil(dept.slots.length / def.perPage));
}

// The biggest of ROOM_SCALES that fits every pet on this page in its
// station, so sizes compare truthfully.
function roomScale(def, slots, stations) {
  return (
    ROOM_SCALES.find((sc) =>
      slots.every((slot, i) => {
        const a = def.area(stations[i]);
        const { w, h } = petSize(slot.genes, BABY);
        return w * sc <= a.right - a.left && h * sc <= stations[i].h - 2;
      })
    ) || ROOM_SCALES[ROOM_SCALES.length - 1]
  );
}

function renderRoom() {
  const id = dept.department.id;
  const def = SHOP_ROOMS[id];
  const pages = roomPages(def);
  page = Math.min(page, pages - 1);
  const slots = dept.slots.slice(page * def.perPage, (page + 1) * def.perPage);
  const stations = def.stations();
  $("dept-title").textContent = dept.department.name + (pages > 1 ? `: ${def.pages[page]}` : "");
  $("shop-scene").hidden = false;

  const bg = sceneCanvas();
  const front = sceneCanvas();
  const r = habitatPainter(bg.getContext("2d"), SCENE_PX);
  const f = habitatPainter(front.getContext("2d"), SCENE_PX);
  def.drawRoom(r, page);
  stations.forEach((st) => def.back(r, st));
  stations.forEach((st) => def.front(f, st));
  const scale = roomScale(def, slots.filter((sl) => !sl.sold), stations);
  const pets = [];
  slots.forEach((slot, i) => {
    if (slot.sold) return;
    const area = def.area(stations[i]);
    const world = PetMotion.create([{ genes: slot.genes, growth: BABY, species: slot.species }], area, scale);
    const w = world.walkers[0];
    area.top = Math.min(area.bottom, Math.max(area.top, stations[i].y + 3 + w.height)); // keep heads inside
    w.x = area.left + Math.random() * Math.max(0, area.right - area.left - w.width);
    w.y = area.top + Math.random() * (area.bottom - area.top);
    pets.push({ slot, world });
  });
  scene = { bg, front, pets };
  drawScene();

  const spots = slots.map((slot, i) => stationButton(slot, stations[i]));
  spots.push(...roomSigns(def.pages.slice(0, pages)));
  $("shop-spots").replaceChildren(...spots);
}

// The way back to the entrance, and arrows to a department's other rooms.
function roomSigns(names) {
  const signs = [sceneSign("⬅ Entrance", "sign-left", goEntrance)];
  if (names.length === 2) {
    const other = 1 - page;
    signs.push(sceneSign(other ? `${names[other]} ▶` : `◀ ${names[other]}`, "sign-right", () => openRoomPage(other)));
  } else if (names.length > 2) {
    if (page < names.length - 1) signs.push(sceneSign(`${names[page + 1]} ▶`, "sign-right", () => openRoomPage(page + 1)));
    if (page > 0) signs.push(sceneSign(`◀ ${names[page - 1]}`, "sign-left sign-second", () => openRoomPage(page - 1)));
  }
  return signs;
}

function openRoomPage(n) {
  page = n;
  history.replaceState(null, "", `?dept=${deptId}${page ? `&page=${page}` : ""}`);
  renderFloor();
}

function sceneSign(text, cls, onclick) {
  const b = document.createElement("button");
  b.className = `scene-nav ${cls}`;
  b.textContent = text;
  b.onclick = onclick;
  return b;
}

// A pet's station: click it to meet the pet; its price tag hangs below.
function stationButton(slot, st) {
  const btn = document.createElement("button");
  btn.className = "shop-slot" + (slot.sold ? " sold" : "") + (slot.saved ? " saved" : "");
  btn.dataset.index = slot.index;
  place(btn, { x: st.x, y: st.y, w: st.w, h: st.h + 5 });
  if (slot.sold) {
    btn.disabled = true;
    btn.innerHTML = `<span class="slot-tag">Adopted!</span>`;
    btn.title = "A new pet comes tomorrow.";
    return btn;
  }
  btn.setAttribute("aria-label", `${speciesName(slot.species)}, ${slot.price} coins`);
  const ribbon = slot.saved ? `<span class="slot-ribbon saved">Saved!</span>` : slot.last_day ? `<span class="slot-ribbon">Last day!</span>` : "";
  const price = dept.coupon ? "🎟️ Free" : coins(slot.price);
  btn.innerHTML = `${ribbon}<span class="slot-tag">${price}${tagBadges(slot)}</span>`;
  btn.onclick = () => showDetail(slot.index);
  return btn;
}

function tagBadges(slot) {
  const rare = rareList(slot);
  const marks = [];
  if (slot.new_colors.length) marks.push(`<span title="New color" class="tag-mark">✨</span>`);
  if (rare.some((x) => x.superRare)) marks.push(`<span title="Super rare" class="tag-mark">🌟</span>`);
  else if (rare.length) marks.push(`<span title="Rare" class="tag-mark">⭐</span>`);
  return marks.join("");
}

function rareList(slot) {
  return Object.entries(slot.rare)
    .filter(([, mult]) => mult >= RARE_SHOWN)
    .sort((a, b) => b[1] - a[1])
    .map(([name, mult]) => ({ label: RARE_LABEL[name] || name, superRare: mult >= SUPER_RARE }));
}

function badges(slot) {
  const out = [];
  if (slot.new_colors.length) out.push(`<span class="badge badge-new">✨ New color</span>`);
  const rare = rareList(slot);
  if (rare.some((r) => r.superRare)) out.push(`<span class="badge badge-super">★ Super rare</span>`);
  else if (rare.length) out.push(`<span class="badge badge-rare">★ Rare</span>`);
  return out.length ? `<p class="card-badges">${out.join("")}</p>` : "";
}

// --- habitats (app/pet_care.py, looks in habitats.js) -----------------------------------

// The gallery's rooms: each tier's habitats, GALLERY_PER_ROOM at a time.
function galleryRooms() {
  const rooms = [];
  for (const tier of Object.keys(GALLERY_ROOMS)) {
    const kinds = dept.habitats.kinds.filter((k) => k.tier === tier);
    for (let i = 0; i * GALLERY_PER_ROOM < kinds.length; i++) {
      rooms.push({ tier, name: GALLERY_ROOMS[tier][i] || `${TIER_NAME[tier]} ${i + 1}`, kinds: kinds.slice(i * GALLERY_PER_ROOM, (i + 1) * GALLERY_PER_ROOM) });
    }
  }
  return rooms;
}

function renderHabitats() {
  const h = dept.habitats;
  const rooms = galleryRooms();
  page = Math.min(page, rooms.length - 1);
  const room = rooms[page];
  $("dept-title").textContent = `Habitats: ${room.name}`;
  $("dept-hint").textContent = `A habitat is a home on the Trailhead where ${h.capacity} of your pets can live and play. You have ${h.owned} of ${h.spots}. Click a picture to look closer!`;
  $("shop-scene").hidden = false;

  const bg = sceneCanvas();
  const ctx = bg.getContext("2d");
  const r = habitatPainter(ctx, SCENE_PX);
  drawGalleryRoom(r, room.tier);
  const frames = galleryFrames();
  room.kinds.forEach((kind, i) => {
    const f = frames[i];
    drawGalleryFrame(r, f, !kind.open);
    ctx.drawImage(habitatBackground(kind.id, (f.w / HABITAT_W) * SCENE_PX), f.x * SCENE_PX, f.y * SCENE_PX);
    if (!kind.open) r(f.x, f.y, f.w, f.h, "rgba(30, 20, 50, 0.45)");
  });
  scene = { bg, front: null, pets: [] };
  drawScene();
  $("shop-spots").replaceChildren(...room.kinds.map((kind, i) => galleryButton(kind, frames[i])), ...roomSigns(rooms.map((x) => x.name)));
}

function galleryButton(kind, f) {
  const btn = document.createElement("button");
  btn.className = "shop-slot gallery-frame" + (kind.open ? "" : " locked");
  btn.dataset.kind = kind.id;
  place(btn, { x: f.x - 2, y: f.y - 2, w: f.w + 4, h: f.h + 10 });
  btn.setAttribute("aria-label", `${kind.name}, ${kind.open ? (kind.price ? `${kind.price} coins` : "free") : "opens with Mythical Pets"}`);
  const price = !kind.open ? "🔒" : kind.price ? coins(kind.price) : "Free!";
  btn.innerHTML = `<span class="slot-tag gallery-plaque">${kind.name} · ${price}</span>`;
  btn.onclick = () => showHabitat(kind);
  return btn;
}

// The close-up: the habitat big, and Buy.
function showHabitat(kind) {
  const h = dept.habitats;
  const body = $("detail-body");
  body.innerHTML = `
    <h2 class="panel-title">${kind.name} <small class="habitat-tier">${TIER_NAME[kind.tier]}</small></h2>
    <div class="habitat-preview"></div>
    <p>A home on your Trailhead for up to ${h.capacity} pets.${kind.price ? "" : " Your first habitat is free!"}</p>
    <div class="detail-actions"></div>`;
  body.querySelector(".habitat-preview").appendChild(habitatBackground(kind.id, 3));
  const full = h.owned >= h.spots;
  const short = dept.coins < kind.price;
  const btn = document.createElement("button");
  btn.className = "button-gold big-button";
  btn.disabled = full || short || !kind.open;
  btn.textContent = !kind.open
    ? "Opens with Mythical Pets"
    : full
      ? "Your trail is full"
      : short
        ? `Need ${(kind.price - dept.coins).toLocaleString()} more coins`
        : kind.price
          ? `Buy for ${kind.price.toLocaleString()} coins`
          : "Get it free!";
  btn.onclick = () => buyHabitat(kind);
  body.querySelector(".detail-actions").appendChild(btn);
  const dialog = $("pet-detail");
  if (!dialog.open) dialog.showModal();
}

async function buyHabitat(kind) {
  try {
    const data = await call(`/api/pets/shop/habitats/${kind.id}`, "POST");
    closeDetail();
    setDept(data);
    say("");
    $("dept-hint").innerHTML = `🎉 Your <b>${data.bought.name}</b> is ready! Find it on the <a href="/pets/trail">Trailhead</a>, and move pets in at the <a href="/pets/care">Pet Care Center</a>.`;
  } catch (err) {
    closeDetail();
    say(err.message);
  }
}

// --- special orders ------------------------------------------------------------------

function renderOrders() {
  $("dept-title").textContent = "Special Orders";
  $("dept-hint").textContent = "Design your own pet! Pick what kind and its colors, and we'll find some for you.";
  const grid = $("shop-grid");
  grid.className = "shop-grid orders-floor";
  const parts = [];
  const o = dept.order;
  if (o) {
    const colors = [o.primary, o.secondary].filter(Boolean).map((c) => c.name).join(" and ");
    const note = document.createElement("div");
    note.className = "order-status";
    note.innerHTML =
      o.status === "waiting"
        ? `📦 <b>Your order is on its way!</b> 4 ${plural(o.species)} in ${colors} arrive tomorrow.`
        : `📦 <b>Your special order is here!</b> They go home ${o.days_left === 1 ? "after today" : `in ${o.days_left} days`}.`;
    parts.push(note);
  }
  parts.push(orderForm());
  grid.replaceChildren(...parts);
  if (!preview) loadPreview();
}

function orderForm() {
  const choices = dept.choices;
  if (!pick || !choices.some((c) => c.species === pick.species)) {
    pick = { species: choices[0].species, primary: choices[0].primaries[0].id, secondary: null };
  }
  const choice = choices.find((c) => c.species === pick.species);
  if (!choice.primaries.some((c) => c.id === pick.primary)) pick.primary = choice.primaries[0].id;
  if (pick.secondary === pick.primary) pick.secondary = null;

  const form = document.createElement("section");
  form.className = "order-form";
  const pets = choices
    .map((c) => `<button class="order-species${c.species === pick.species ? " current" : ""}" data-species="${c.species}">${speciesName(c.species)}<small>${coins(c.fee)}</small></button>`)
    .join("");
  const swatches = (colors, picked, kind) =>
    colors
      .map((c) => `<button class="color-pick${c.id === picked ? " current" : ""}" data-${kind}="${c.id}" title="${c.name}" aria-label="${c.name}"><span class="swatch" style="background:${c.hex}"></span>${c.name}</button>`)
      .join("");
  const seconds = choice.colors.filter((c) => c.id !== pick.primary);
  const name = plural(pick.species);
  const replacing = dept.order ? `<p class="order-warning">Sending a new order sends your last order's ${plural(dept.order.species)} home.</p>` : "";
  const short = dept.coins < choice.fee;
  form.innerHTML = `
    <h3>Order a special pet!</h3>
    <p class="order-step">1. What kind of pet?</p><div class="order-row">${pets}</div>
    <p class="order-step">2. Its main color</p><div class="order-row">${swatches(choice.primaries, pick.primary, "primary")}</div>
    ${
      dept.pick_secondary
        ? `<p class="order-step">3. Its second color</p><div class="order-row">
             <button class="color-pick${pick.secondary ? "" : " current"}" data-secondary="">Shop's choice</button>${swatches(seconds, pick.secondary, "secondary")}</div>`
        : `<p class="hint">Learn your capital letters to pick a second color too!</p>`
    }
    <div class="order-sample dept-${choice.dept}">
      <figure><canvas id="order-preview" width="220" height="160" data-scale="4"></canvas><figcaption>Something like this, all grown up</figcaption></figure>
      <button class="link-button" id="order-another">Show me another</button>
    </div>
    <p class="order-explain">Sending the order costs <b>${coins(choice.fee)} coins</b>. Tomorrow, <b>4 ${name}</b> in your colors will be waiting here.
      You can buy the ones you love. If you don't, they go home after 3 days.</p>
    ${replacing}
    <div class="detail-actions"><button id="order-send" class="button-gold big-button"${short ? " disabled" : ""}>${
      short ? `Need ${(choice.fee - dept.coins).toLocaleString()} more coins` : `Send my order`
    }</button></div>`;

  const repick = (changes) => {
    Object.assign(pick, changes);
    preview = null;
    renderOrders();
  };
  for (const b of form.querySelectorAll("[data-species]")) b.onclick = () => repick({ species: b.dataset.species, secondary: null });
  for (const b of form.querySelectorAll("[data-primary]")) b.onclick = () => repick({ primary: b.dataset.primary });
  for (const b of form.querySelectorAll("[data-secondary]")) b.onclick = () => repick({ secondary: b.dataset.secondary || null });
  form.querySelector("#order-another").onclick = () => loadPreview();
  form.querySelector("#order-send").onclick = sendOrder;
  return form;
}

async function loadPreview() {
  const q = new URLSearchParams({ species: pick.species, primary: pick.primary });
  if (pick.secondary) q.set("secondary", pick.secondary);
  // not call(): the sample isn't a player update for the header
  const r = await fetch(`/api/pets/shop/orders/preview?${q}`);
  const data = await r.json();
  if (!r.ok) return say(data.detail || "Couldn't show a sample pet.");
  preview = data.pet;
  const canvas = $("order-preview");
  if (!canvas) return;
  canvas.dataset.scale = fitScale([preview], ORDER_SAMPLE_GROWTH, canvas.width, canvas.height, 7);
  paint(canvas, preview, ORDER_SAMPLE_GROWTH, Number(canvas.dataset.scale));
}

async function sendOrder() {
  try {
    setDept(await call("/api/pets/shop/orders", "POST", pick));
    say("");
  } catch (err) {
    say(err.message);
    renderOrders();
  }
}

// --- the close-up --------------------------------------------------------------------

function showDetail(index) {
  detailIndex = index;
  renderDetail();
  const dialog = $("pet-detail");
  if (!dialog.open) dialog.showModal();
}

function closeDetail() {
  detailIndex = null;
  $("pet-detail").close();
}

function renderDetail() {
  const slot = slotAt(detailIndex);
  const body = $("detail-body");
  if (!slot || slot.sold) return;
  const name = speciesName(slot.species);
  const colors = slot.genes.color_names
    .map((n, i) => (n ? { name: n, hex: slot.genes.hex[i], id: slot.genes.coat.colors[i] } : null))
    .filter(Boolean)
    .map((c) => `<li><span class="swatch" style="background:${c.hex}"></span>${c.name}${slot.new_colors.includes(c.id) ? ' <span class="badge badge-new">New!</span>' : ""}</li>`)
    .join("");
  const rare = rareList(slot)
    .map((r) => `<span class="badge ${r.superRare ? "badge-super" : "badge-rare"}">★ ${r.label}</span>`)
    .join("");
  body.innerHTML = `
    <h2 class="panel-title">${name}${slot.last_day ? ' <span class="badge badge-last">Last day!</span>' : ""}</h2>
    <div class="detail-pets dept-${slot.dept}">
      <figure><div class="detail-canvas" data-stage="baby"></div><figcaption>Now</figcaption></figure>
      <figure><div class="detail-canvas" data-stage="grown"></div><figcaption>All grown up</figcaption></figure>
    </div>
    <ul class="detail-colors">${colors}</ul>
    ${rare ? `<p class="detail-rare">${rare}</p>` : ""}
    ${slot.new_colors.length ? `<p class="hint">Buy this pet to unlock its new ${slot.new_colors.length > 1 ? "colors" : "color"} for all your pets!</p>` : ""}
    <div class="detail-actions"></div>`;
  const scale = fitScale([slot.genes], GROWN, 220, 160, 6);
  const babyScale = Math.min(fitScale([slot.genes], BABY, 220, 160, 8), scale * 2);
  body.querySelector('[data-stage="baby"]').appendChild(petCanvas(slot, BABY, 220, 160, babyScale));
  body.querySelector('[data-stage="grown"]').appendChild(petCanvas(slot, GROWN, 220, 160, scale));
  body.querySelector(".detail-actions").append(...actions(slot));
}

function actions(slot) {
  const out = [];
  const button = (text, cls, onclick, disabled = false) => {
    const b = document.createElement("button");
    b.textContent = text;
    b.className = cls;
    b.disabled = disabled;
    b.onclick = onclick;
    out.push(b);
    return b;
  };
  if (dept.coupon) {
    button("Use my coupon (free!)", "button-gold big-button", () => buy(slot, true));
  }
  const coinsLeft = dept.coins;
  const short = coinsLeft < slot.price;
  button(
    short ? `Need ${(slot.price - coinsLeft).toLocaleString()} more coins` : `Buy for ${slot.price.toLocaleString()} coins`,
    dept.coupon ? "button-go" : "button-gold big-button",
    () => buy(slot, false),
    short
  );
  const saved = front.saved;
  if (slot.dept === "orders") return out; // they already wait just for you
  if (slot.saved) button("Let it go", "", unsave);
  else if (saved) button("Save for me", "", null, true).title = "You're already saving a pet. Buy it or let it go first.";
  else button("Save for me", "", () => save(slot));
  if (saved && !slot.saved) out.push(Object.assign(document.createElement("p"), { className: "hint", textContent: "You're already saving a pet. Buy it or let it go first." }));
  return out;
}

async function buy(slot, coupon) {
  try {
    const data = await call(`/api/pets/shop/${deptId}/${slot.index}/buy`, "POST", { coupon });
    const pet = data.bought;
    setDept(data);
    if (!data.coupon) front.coupon = false;
    renderBanners();
    welcome(pet);
  } catch (err) {
    say(err.message);
    closeDetail();
  }
}

function welcome(pet) {
  const body = $("detail-body");
  body.innerHTML = `
    <h2 class="panel-title">🎉 Welcome home, ${pet.name}!</h2>
    <div class="detail-pets dept-${deptId}"><figure><div class="detail-canvas"></div></figure></div>
    <p>Your new ${pet.species} is waiting for you at the <b>Pet Care Center</b>.</p>
    ${pet.new_colors.length ? `<p class="unlocked-colors">✨ New ${pet.new_colors.length > 1 ? "colors" : "color"} unlocked: <b>${pet.new_colors.join(", ")}</b></p>` : ""}
    <div class="detail-actions"><button class="button-go big-button">Yay!</button></div>`;
  const genes = pet.genes;
  const canvas = document.createElement("canvas");
  canvas.width = 220;
  canvas.height = 160;
  body.querySelector(".detail-canvas").appendChild(canvas);
  paint(canvas, genes, BABY, fitScale([genes], BABY, 220, 160, 8));
  body.querySelector("button").onclick = closeDetail;
}

async function save(slot) {
  try {
    setDept(await call("/api/pets/shop/save", "PUT", { dept: deptId, index: slot.index }));
  } catch (err) {
    say(err.message);
  }
}

async function unsave() {
  try {
    setDept(await call("/api/pets/shop/save", "DELETE"));
  } catch (err) {
    say(err.message);
  }
}

// --- start ---------------------------------------------------------------------------

$("pet-detail").querySelector(".detail-close").onclick = closeDetail;
$("pet-detail").addEventListener("close", () => (detailIndex = null));

loadFront()
  .then(() => {
    const q = new URLSearchParams(location.search);
    const asked = front.departments.find((d) => d.open && d.id === q.get("dept"));
    return asked ? openDept(asked.id, Number(q.get("page")) || 0) : goEntrance();
  })
  .then(() => {
    setInterval(tick, TICK_MS);
    setInterval(sceneTick, SCENE_TICK_MS);
  })
  .catch((err) => {
    console.error(err);
    say(`Couldn't open the shop (${err.message}). Try reloading.`);
  });
