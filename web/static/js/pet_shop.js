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
// The row of keys each locked department waits for (app/pet_shop.py needs).
const DEPT_ROW = { companions: "numbers", household: "home row", orders: "home row", farm: "top row", reptiles: "bottom row", mythical: "numbers" };
const TIER_NAME = { everyday: "Outdoors", cozy: "Cozy", magical: "Magical" };
const DEPT_ICON = { fish: "🐠", household: "🐱", farm: "🐐", reptiles: "🐢", mythical: "🐉", companions: "✉️", orders: "📋", habitats: "🌳", aqua: "🌊", supplies: "🦴" };

let front = null; // /api/pets/shop
let dept = null; // /api/pets/shop/{id}
let deptId = null; // null: a hall (the entrance, or upstairs)
let floor = 0; // 0 the entrance hall, 1 upstairs (Homes & Supplies)
let page = 0; // which of a department's rooms
let scene = null; // what's drawn: {bg, front, pets: [{slot, world}]}
let detailIndex = null; // the slot in the close-up
let frame = 0;
let pick = null; // the order form: {species, primary, secondary}
let preview = null; // a sample pet for the order form

const PLURAL = { bunny: "bunnies", fish: "fish", fox: "foxes", sheep: "sheep", phoenix: "phoenixes", flower_fairy: "flower fairies" };
const speciesName = petSpeciesName;
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
  if (id === "companions") {
    goEntrance(0); // the desk is right here in the hall
    return openLetter();
  }
  deptId = id;
  floor = SHOP_UPSTAIRS.has(id) ? 1 : 0;
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

function goEntrance(toFloor = floor) {
  say("");
  deptId = null;
  dept = null;
  floor = toFloor;
  history.replaceState(null, "", floor ? "?floor=up" : location.pathname);
  renderEntrance();
  renderBanners();
}

function renderEntrance() {
  $("room-nav").replaceChildren();
  $("dept-title").textContent = floor ? "Upstairs: Fish, Homes & Supplies" : "Welcome to the Pet Shop!";
  $("dept-hint").textContent = floor
    ? "Fish, homes for your pets, and everything for your fish tanks."
    : "Click a department to look around. New pets arrive every night. Fish, homes and supplies are up the stairs, and friends leave letters on the desk!";
  $("shop-grid").replaceChildren();
  $("shop-scene").hidden = false;
  const open = { ...Object.fromEntries(front.departments.map((d) => [d.id, d.open])), friend: front.friend };
  const bg = sceneCanvas();
  (floor ? drawShopUpstairs : drawShopEntrance)(habitatPainter(bg.getContext("2d"), SCENE_PX), open);
  scene = { bg, front: null, pets: [] };
  drawScene();
  const stairs = document.createElement("button");
  stairs.className = "shop-spot";
  stairs.dataset.stairs = floor ? "down" : "up";
  place(stairs, SHOP_SPOTS[floor ? "down" : "stairs"]);
  stairs.innerHTML = `<span class="spot-sign">${floor ? "⬇ <span class=\"spot-name\">Downstairs</span>" : "⬆ <span class=\"spot-name\">Upstairs</span><small>Fish, Homes & Supplies</small>"}</span>`;
  stairs.setAttribute("aria-label", floor ? "Go downstairs" : "Go upstairs to Fish, Homes & Supplies");
  stairs.onclick = () => goEntrance(floor ? 0 : 1);
  $("shop-spots").replaceChildren(
    stairs,
    ...front.departments.filter((d) => SHOP_UPSTAIRS.has(d.id) === Boolean(floor)).map((d) => {
      const spot = SHOP_SPOTS[d.id];
      const btn = document.createElement("button");
      btn.className = "shop-spot" + (d.open ? "" : " closed") + (SHOP_TOP_SIGNS.has(d.id) ? " top-sign" : "");
      btn.dataset.dept = d.id;
      place(btn, spot);
      const keys = d.missing.toUpperCase().split("").join(" ");
      const lock = d.soon ? "Coming soon" : `🔒 Learn the ${DEPT_ROW[d.id] || "keys"}`;
      btn.setAttribute("aria-label", d.open ? d.name : `${d.name}: ${lock}`);
      btn.innerHTML = `<span class="spot-sign">${DEPT_ICON[d.id] || "🐾"} <span class="spot-name">${d.name}</span>${d.open ? "" : `<small>${lock}</small>`}</span>`;
      if (d.id === "companions" && d.open) btn.querySelector(".spot-sign").insertAdjacentHTML("beforeend", `<small>${front.friend ? "A letter for you!" : "No letters today"}</small>`);
      btn.onclick = () =>
        d.open ? openDept(d.id) : say(d.soon ? `${d.name} is coming soon!` : `${d.name} opens when you learn ${keys}.`);
      return btn;
    })
  );
}

// --- the letter desk: a friend writes to ask if she can visit ----------------------------

async function openLetter() {
  try {
    const data = await call("/api/pets/shop/companions");
    const slot = data.slots[0];
    showLetter(slot && !slot.sold ? slot : null, data.coins);
  } catch (err) {
    say(err.message);
  }
}

function letterPortrait(body, genes) {
  const canvas = document.createElement("canvas");
  canvas.width = 220;
  canvas.height = 160;
  body.querySelector(".letter-portrait").appendChild(canvas);
  paint(canvas, genes, GROWN, fitScale([genes], GROWN, 220, 160, 6));
}

function showLetter(slot, coinsLeft) {
  const body = $("detail-body");
  detailIndex = null;
  if (!slot) {
    body.innerHTML = `<h2 class="panel-title">✉️ No letters today</h2><p>Nobody has written just now. Check back tomorrow!</p>`;
    $("pet-detail").showModal();
    return;
  }
  const { name, lines } = slot.letter;
  const colors = slot.genes.color_names
    .map((n, i) => (n ? `<li><span class="swatch" style="background:${slot.genes.hex[i]}"></span>${n}</li>` : ""))
    .join("");
  body.innerHTML = `
    <h2 class="panel-title">✉️ A friend would like to visit you</h2>
    <div class="friend-letter">
      <div class="letter-portrait"></div>
      <p>Dear friend,</p>
      ${lines.map((line) => `<p>${line}</p>`).join("")}
      <p class="letter-sign">Your friend,<br><b>${name}</b>, a ${speciesName(slot.species).toLowerCase()}</p>
    </div>
    <ul class="detail-colors">${colors}</ul>
    <p class="hint">Getting a place ready for a guest costs ${coins(slot.price)}.
      ${slot.last_day ? `This is her last day to hear from you.` : `She'll wait ${slot.days_left} days for your answer.`}</p>
    <div class="detail-actions"></div>`;
  letterPortrait(body, slot.genes);
  const short = coinsLeft < slot.price;
  const invite = document.createElement("button");
  invite.className = "button-gold big-button";
  invite.textContent = short ? `Need ${(slot.price - coinsLeft).toLocaleString()} more coins` : `Invite ${name} for ${slot.price.toLocaleString()} coins`;
  invite.disabled = short;
  invite.onclick = () => inviteFriend(slot);
  const later = document.createElement("button");
  later.textContent = "Maybe another time";
  later.onclick = () => $("pet-detail").close();
  body.querySelector(".detail-actions").append(invite, later);
  if (!$("pet-detail").open) $("pet-detail").showModal();
}

async function inviteFriend(slot) {
  try {
    const data = await call(`/api/pets/shop/companions/${slot.index}/buy`, "POST", { coupon: false });
    const friend = data.bought;
    await loadFront();
    renderEntrance();
    const body = $("detail-body");
    body.innerHTML = `
      <h2 class="panel-title">🎉 ${friend.name} is here!</h2>
      <div class="letter-portrait"></div>
      <p>She's waiting for you at the <b>Pet Care Center</b>, ready to choose a home${friend.species === "mermaid" ? " with plenty of water" : ""}.</p>
      <div class="detail-actions"><button class="button-go big-button">Welcome, ${friend.name}!</button></div>`;
    letterPortrait(body, friend.genes);
    body.querySelector("button").onclick = () => $("pet-detail").close();
  } catch (err) {
    $("pet-detail").close();
    say(err.message);
  }
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
  if (d.id === "aqua") return renderAquaSupplies();
  if (d.id === "supplies") return renderPetSupplies();
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
// Signposts above the scene: back to the hall, and to the department's
// other rooms. (Returns nothing for the scene itself.)
function roomSigns(names) {
  const signs = [signpost(floor ? "Upstairs" : "Entrance", () => goEntrance())];
  if (page > 0) signs.push(signpost(names[page - 1], () => openRoomPage(page - 1)));
  if (page < names.length - 1) signs.push(signpost(names[page + 1], () => openRoomPage(page + 1), true));
  $("room-nav").replaceChildren(...signs);
  return [];
}

function signpost(text, onclick, forward = false) {
  const b = document.createElement("button");
  b.className = "signpost" + (forward ? " forward" : "");
  b.textContent = text;
  b.onclick = onclick;
  return b;
}

function openRoomPage(n) {
  page = n;
  history.replaceState(null, "", `?dept=${deptId}${page ? `&page=${page}` : ""}`);
  renderFloor();
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

// --- Aquarium Supplies (app/aquarium.py; art in aquarium_items.js) ---------------------

// Supplies rooms, 8 items at most each: by kind, and plants and rocks by size.
const AQUA_ROOMS = [
  { name: "Tanks & Backdrops", has: (i) => i.kind === "tank" || i.kind === "background" },
  { name: "Sand & Gravel", has: (i) => i.kind === "substrate" },
  { name: "Little Plants", has: (i) => i.kind === "plant" && i.h <= 10 },
  { name: "Plants", has: (i) => i.kind === "plant" && i.h > 10 && i.h <= 30 },
  { name: "Tall Plants", has: (i) => i.kind === "plant" && i.h > 30 },
  { name: "Driftwood", has: (i) => i.kind === "wood" && i.h <= 30 },
  { name: "Big Driftwood", has: (i) => i.kind === "wood" && i.h > 30 },
  { name: "Little Rocks", has: (i) => i.kind === "rock" && i.h <= 10 },
  { name: "Big Rocks", has: (i) => i.kind === "rock" && i.h > 10 },
  { name: "Decorations", has: (i) => i.kind === "decor" },
];
const AQUA_SEES = {
  hide: "Shy fish hide in it.",
  explore: "Curious fish love to explore it.",
  through: "Fish can swim right through it.",
  bubbles: "It makes bubbles fish play in.",
};

// The shop's items, with the tank itself as an item.
function aquaItems() {
  const a = dept.aqua;
  const tank = { id: "tank", name: "75-Gallon Tank", kind: "tank", price: a.tank_price, owned: a.tanks, sees: [] };
  return [tank, ...a.items];
}

function renderAquaSupplies() {
  page = Math.min(page, AQUA_ROOMS.length - 1);
  const room = AQUA_ROOMS[page];
  const items = aquaItems().filter(room.has);
  $("dept-title").textContent = `Aquarium Supplies: ${room.name}`;
  $("dept-hint").textContent = "Build your own tanks! Pieces you buy wait in your Aquarium until you place them. Click anything to look closer.";
  $("shop-scene").hidden = false;
  const bg = sceneCanvas();
  const ctx = bg.getContext("2d");
  drawAquaShopRoom(habitatPainter(ctx, SCENE_PX));
  const displays = aquaDisplays();
  items.forEach((item, i) => {
    const f = displays[i];
    drawAquaDisplay(habitatPainter(ctx, SCENE_PX), f);
    drawAquaPreview(ctx, item, f.x * SCENE_PX, f.y * SCENE_PX, f.w * SCENE_PX, f.h * SCENE_PX);
  });
  scene = { bg, front: null, pets: [] };
  drawScene();
  $("shop-spots").replaceChildren(...items.map((item, i) => aquaButton(item, displays[i])), ...roomSigns(AQUA_ROOMS.map((r) => r.name)));
}

// An item in a little tank: a backdrop or substrate fills it; a tank is the
// starter look; a piece stands on sand, zoomed to fit.
function drawAquaPreview(ctx, item, X, Y, W, H, t = 40) {
  ctx.save();
  ctx.beginPath();
  ctx.rect(X, Y, W, H);
  ctx.clip();
  const px = W / TANK_W;
  const tank = (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(X + x * px, Y + y * px, w * px, h * px);
  };
  if (item.kind === "tank") {
    drawShopTank(ctx, X, Y, W, H);
    ctx.restore();
    return;
  }
  const looks = { background: [item.id, "sand"], substrate: ["bg_blue", item.id] };
  const [bg, sub] = looks[item.kind] || ["bg_blue", "sand"];
  drawAquaLook(tank, bg, sub);
  if (AQUA_PIECES[item.id]) {
    const s = Math.min((W * 0.8) / item.w, (H * 0.72) / item.h, 6);
    const ox = X + (W - item.w * s) / 2;
    const floor = Y + H - (SUBSTRATE_H / 2) * px;
    const piece = (x, y, w, h, c) => {
      ctx.fillStyle = c;
      ctx.fillRect(ox + x * s, floor + (y - item.h) * s, w * s, h * s);
    };
    drawAquaPiece(piece, item, 0, item.h, false, t);
  }
  ctx.restore();
}

// The tank for sale: a real glass tank on a stand, not just water.
function drawShopTank(ctx, X, Y, W, H) {
  const box = (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(X + x * W, Y + y * H, w * W, h * H);
  };
  box(0, 0, 1, 1, "#2a3446"); // the shop wall behind it
  box(0, 0.82, 1, 0.18, "#5c3a1a"); // a wooden stand
  box(0, 0.82, 1, 0.03, "#8b5a2b");
  box(0.1, 0.88, 0.2, 0.12, "#3b2417");
  box(0.7, 0.88, 0.2, 0.12, "#3b2417");
  const tx = 0.08;
  const tw = 0.84;
  box(tx - 0.02, 0.06, tw + 0.04, 0.08, "#1a1a1e"); // the hood
  box(tx, 0.08, tw, 0.02, "#f8f0c8");
  const inner = (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(X + (tx + (x / TANK_W) * tw) * W, Y + (0.14 + (y / TANK_H) * 0.66) * H, (w / TANK_W) * tw * W, (h / TANK_H) * 0.66 * H);
  };
  drawAquaLook(inner, "bg_blue", "sand");
  box(tx - 0.02, 0.14, 0.02, 0.68, "#1a1a1e"); // the frame
  box(tx + tw, 0.14, 0.02, 0.68, "#1a1a1e");
  box(tx - 0.02, 0.79, tw + 0.04, 0.03, "#1a1a1e");
  ctx.fillStyle = "rgba(255, 255, 255, 0.22)"; // glare on the glass
  ctx.beginPath();
  ctx.moveTo(X + (tx + 0.1) * W, Y + 0.16 * H);
  ctx.lineTo(X + (tx + 0.18) * W, Y + 0.16 * H);
  ctx.lineTo(X + (tx + 0.08) * W, Y + 0.78 * H);
  ctx.lineTo(X + tx * W, Y + 0.78 * H);
  ctx.fill();
}

function aquaButton(item, f) {
  const btn = document.createElement("button");
  btn.className = "shop-slot gallery-frame";
  btn.dataset.item = item.id;
  place(btn, { x: f.x - 2, y: f.y - 2, w: f.w + 4, h: f.h + 11 });
  btn.setAttribute("aria-label", `${item.name}, ${item.price} coins`);
  const yours = item.kind === "background" || item.kind === "substrate" ? (item.owned ? " ✓" : "") : item.owned ? ` ×${item.owned}` : "";
  const price = item.price ? coins(item.price) : "Free";
  btn.innerHTML = `<span class="slot-tag gallery-plaque">${item.name} · ${item.owned === true ? "Yours!" : price}${item.owned === true ? "" : yours}</span>`;
  btn.onclick = () => showAquaItem(item.id);
  return btn;
}

function aquaAbout(item) {
  if (item.kind === "tank") return `A 75-gallon tank for up to 10 fish. It comes with Deep Blue water and Sand. You have ${item.owned} of ${dept.aqua.spots}.`;
  if (item.kind === "background") return "A backdrop for your tanks. Buy it once and use it in every tank.";
  if (item.kind === "substrate") return "The bottom of your tank. Buy it once and use it in every tank.";
  const sees = item.sees.map((k) => AQUA_SEES[k]).join(" ");
  return `Goes in your Aquarium. Place it in any tank, in front of or behind your fish. ${sees}${item.owned ? ` You have ${item.owned}.` : ""}`;
}

function showAquaItem(id) {
  const item = aquaItems().find((i) => i.id === id);
  const body = $("detail-body");
  body.innerHTML = `
    <h2 class="panel-title">${item.name}</h2>
    <div class="aqua-preview"><canvas width="480" height="210"></canvas></div>
    <p>${aquaAbout(item)}</p>
    <div class="detail-actions"></div>`;
  drawAquaPreview(body.querySelector("canvas").getContext("2d"), item, 0, 0, 480, 210);
  const owned = item.owned === true;
  const full = item.kind === "tank" && item.owned >= dept.aqua.spots;
  const short = dept.coins < item.price;
  const btn = document.createElement("button");
  btn.className = "button-gold big-button";
  btn.disabled = owned || full || short;
  btn.textContent = owned
    ? "Yours!"
    : full
      ? "Your Aquarium is full"
      : short
        ? `Need ${(item.price - dept.coins).toLocaleString()} more coins`
        : `Buy for ${item.price.toLocaleString()} coins`;
  btn.onclick = () => buyAqua(item);
  body.querySelector(".detail-actions").appendChild(btn);
  const dialog = $("pet-detail");
  if (!dialog.open) dialog.showModal();
}

async function buyAqua(item) {
  try {
    const data = await call(item.kind === "tank" ? "/api/aquarium-shop/tank" : `/api/aquarium-shop/${item.id}`, "POST");
    dept.aqua = { items: data.items, tank_price: data.tank_price, tanks: data.tanks, spots: data.spots };
    dept.coins = data.coins;
    renderAquaSupplies();
    showAquaItem(item.id); // stays open: buy another, or close
    const note = document.createElement("p");
    note.className = "unlocked-colors";
    note.innerHTML =
      item.kind === "tank"
        ? `🎉 ${data.bought.name} is ready in your <a href="/pets/aquarium">Aquarium</a>!`
        : item.kind === "background" || item.kind === "substrate"
          ? `🎉 Use it in any tank from your <a href="/pets/aquarium">Aquarium</a>.`
          : `🎉 It's waiting in your <a href="/pets/aquarium">Aquarium</a>.`;
    $("detail-body").appendChild(note);
  } catch (err) {
    closeDetail();
    say(err.message);
  }
}

// --- Pet Supplies (app/pet_supplies.py; art in supply_art.js) -------------------------

const SUPPLY_ROOMS = [
  { name: "Treats & Fish Food", has: (i) => !i.gift && (i.kind === "treat" || i.kind === "fish_food") },
  { name: "Toys", has: (i) => !i.gift && i.kind === "toy" },
  { name: "Magic Potions", potions: true },
  { name: "Gifts for Friends", gifts: true, has: (i) => i.gift },
];
const POTION_TIER = {
  mystery: { name: "Mystery Potion", about: "Nobody knows what colors are inside!" },
  second: { name: "Half-Mystery Potion", about: "You can see its second color. The main color is a mystery!" },
  main: { name: "Half-Mystery Potion", about: "You can see its main color. The second color is a mystery!" },
  clear: { name: "Clear Potion", about: "You can see both of its colors." },
};

function likesText(likes) {
  const names = likes.map((sp) => speciesName(plural(sp)));
  return names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names.at(-1)}` : names[0];
}

function renderPetSupplies() {
  page = Math.min(page, SUPPLY_ROOMS.length - 1);
  const room = SUPPLY_ROOMS[page];
  const sup = dept.supplies;
  $("dept-title").textContent = `Pet Supplies: ${room.name}`;
  $("dept-hint").textContent = room.gifts
    ? "For the mermaids and fairies who come to stay. Offer one in their habitat: type a word and it floats down to them."
    : room.potions
    ? "A potion repaints a pet in its colors, one time. New potions every day! Use them at the Pet Care Center."
    : "Throw treats and toys for your pets in their habitats: type a word to throw! Treats get eaten; toys you keep.";
  $("shop-scene").hidden = false;
  const bg = sceneCanvas();
  const ctx = bg.getContext("2d");
  drawSuppliesRoom(habitatPainter(ctx, SCENE_PX), room.potions);
  const slots = supplySlots();
  const entries = room.potions ? sup.potions.stock : sup.items.filter(room.has);
  entries.forEach((e, i) => {
    const f = slots[i];
    const px = Math.floor((Math.min(f.w, f.h) * SCENE_PX) / SUPPLY_GRID);
    const ox = (f.x + f.w / 2) * SCENE_PX - (SUPPLY_GRID * px) / 2;
    const oy = (f.y + f.h) * SCENE_PX - SUPPLY_GRID * px;
    const r = (x, y, w, h, c) => {
      ctx.fillStyle = c;
      ctx.fillRect(ox + x * px, oy + y * px, w * px, h * px);
    };
    if (room.potions) {
      if (!e.sold) drawPotion(r, e.shown);
    } else drawSupply(r, e.id);
  });
  scene = { bg, front: null, pets: [] };
  drawScene();
  $("shop-spots").replaceChildren(...entries.map((e, i) => supplyButton(e, slots[i], room.potions)), ...roomSigns(SUPPLY_ROOMS.map((r) => r.name)));
}

function supplyButton(e, f, potion) {
  const btn = document.createElement("button");
  btn.className = "shop-slot gallery-frame" + (potion && e.sold ? " sold" : "");
  place(btn, { x: f.x - 1, y: f.y - 1, w: f.w + 2, h: f.h + 8 });
  if (potion) {
    btn.dataset.potion = e.index;
    btn.disabled = e.sold;
    btn.setAttribute("aria-label", `${POTION_TIER[e.tier].name}, ${e.price} coins`);
    btn.innerHTML = `<span class="slot-tag gallery-plaque">${e.sold ? "Sold!" : coins(e.price)}</span>`;
    btn.onclick = () => showPotion(e.index);
  } else {
    btn.dataset.item = e.id;
    btn.setAttribute("aria-label", `${e.name}, ${e.price} coins`);
    const have = e.kind === "toy" ? (e.have ? " ✓" : "") : e.have ? ` ×${e.have}` : "";
    btn.innerHTML = `<span class="slot-tag gallery-plaque">${e.name} · ${coins(e.price)}${have}</span>`;
    btn.onclick = () => showSupply(e.id);
  }
  return btn;
}

function supplyDialog(title, draw, about, buy) {
  const body = $("detail-body");
  body.innerHTML = `<h2 class="panel-title">${title}</h2>
    <div class="supply-preview"><canvas width="160" height="160"></canvas></div>
    <p>${about}</p><div class="detail-actions"></div>`;
  supplyCanvas(body.querySelector("canvas"), draw);
  body.querySelector(".detail-actions").appendChild(buy);
  const dialog = $("pet-detail");
  if (!dialog.open) dialog.showModal();
}

function buyButton(price, done, onclick, doneText = "Yours!") {
  const btn = document.createElement("button");
  btn.className = "button-gold big-button";
  const short = dept.coins < price;
  btn.disabled = done || short;
  btn.textContent = done ? doneText : short ? `Need ${(price - dept.coins).toLocaleString()} more coins` : `Buy for ${price.toLocaleString()} coins`;
  btn.onclick = onclick;
  return btn;
}

function showSupply(id) {
  const item = dept.supplies.items.find((i) => i.id === id);
  const kind = { treat: "A treat: gets eaten.", toy: "A toy: you keep it and throw it again and again.", fish_food: item.sinks ? "Sinks to the bottom for the bottom feeders." : "Floats down slowly from the top." }[item.kind];
  const who = item.kind === "fish_food" ? "Fish swim over to eat it in your tanks." : `${likesText(item.likes)} love it!`;
  const have = item.have ? ` You have ${item.kind === "toy" ? "it" : item.have}.` : "";
  const about = item.gift ? `${item.kind === "toy" ? "A keepsake: you keep it and can offer it again and again." : "A little sweet to share: it's gone once she has it."} A gift for a ${speciesName(item.likes[0]).toLowerCase()}.` : `${kind} ${who}`;
  supplyDialog(item.name, (r) => drawSupply(r, id), `${about}${have}`, buyButton(item.price, item.kind === "toy" && item.have > 0, () => buySupply(item)));
}

function showPotion(index) {
  const p = dept.supplies.potions.stock[index];
  const tier = POTION_TIER[p.tier];
  const colors = p.shown.map((c) => (c ? `<b>${c.name}</b>` : "<b>?</b>")).join(" and ");
  supplyDialog(tier.name, (r) => drawPotion(r, p.shown), `${tier.about} Colors: ${colors}. Use it on a pet at the Pet Care Center.`, buyButton(p.price, p.sold, () => buyPotion(p), "Sold!"));
}

async function refreshSupplies(data) {
  dept.supplies = data.supplies;
  dept.coins = data.coins;
  renderPetSupplies();
}

async function buySupply(item) {
  try {
    await refreshSupplies(await call(`/api/supplies/${item.id}`, "POST"));
    showSupply(item.id); // stays open: buy another
  } catch (err) {
    closeDetail();
    say(err.message);
  }
}

async function buyPotion(p) {
  try {
    await refreshSupplies(await call(`/api/supplies/potions/${p.index}`, "POST"));
    showPotion(p.index);
    const note = document.createElement("p");
    note.className = "unlocked-colors";
    note.innerHTML = `🧪 It's yours! Pick a pet at the <a href="/pets/care">Pet Care Center</a> and use it.`;
    $("detail-body").appendChild(note);
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
    <p>Your new ${speciesName(pet.species).toLowerCase()} is waiting for you at the <b>Pet Care Center</b>.</p>
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
    return asked ? openDept(asked.id, Number(q.get("page")) || 0) : goEntrance(q.get("floor") === "up" ? 1 : 0);
  })
  .then(() => {
    setInterval(tick, TICK_MS);
    setInterval(sceneTick, SCENE_TICK_MS);
  })
  .catch((err) => {
    console.error(err);
    say(`Couldn't open the shop (${err.message}). Try reloading.`);
  });
