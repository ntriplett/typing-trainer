// The Pet Shop (PLAN.md 11h): department signs across the top, then that
// department's pets as cards. Click a pet for a close-up: as a baby and
// all grown up, its colors, what's rare about it, and Buy / Save for me.
// Special Orders swaps the stock for an order form (species, colors, a
// sample pet) and, once they arrive, the ordered pets.
// Rules live in app/pet_shop.py; pets are drawn by pet_render.js.

const $ = (id) => document.getElementById(id);
const TICK_MS = 400;
const BABY = 0;
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
const DEPT_ICON = { fish: "🐠", household: "🐱", farm: "🐐", reptiles: "🐢", mythical: "🐉", orders: "📋", habitats: "🌳", supplies: "🦴" };

let front = null; // /api/pets/shop
let dept = null; // /api/pets/shop/{id}
let deptId = null;
let detailIndex = null; // the slot in the close-up
let confirming = false; // the Buy button asks "Are you sure?" first
let frame = 0;
let cardScale = 3;
let pick = null; // the order form: {species, primary, secondary}
let preview = null; // a sample pet for the order form
let confirmOrder = false;

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
  if (sample && preview) paint(sample, preview, BABY, Number(sample.dataset.scale));
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
  renderDepts();
  renderBanners();
}

async function openDept(id) {
  say("");
  deptId = id;
  history.replaceState(null, "", `?dept=${id}`);
  renderDepts();
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
  const pets = data.slots.filter((s) => !s.sold).map((s) => s.genes);
  cardScale = fitScale(pets, BABY, 150, 110, 5);
  renderBanners();
  renderFloor();
  if (detailIndex !== null) renderDetail();
}

// --- department signs and banners ----------------------------------------------------

function renderDepts() {
  const nav = $("shop-depts");
  nav.replaceChildren(
    ...front.departments.map((d) => {
      const btn = document.createElement("button");
      btn.className = "dept-sign" + (d.id === deptId ? " current" : "") + (d.open ? "" : " closed");
      btn.dataset.dept = d.id;
      const lock = d.soon ? "Coming soon" : `Learn ${d.missing.toUpperCase().split("").join(" ")}`;
      btn.innerHTML = `<span class="dept-icon">${DEPT_ICON[d.id] || "🐾"}</span>
        <span class="dept-name">${d.name}</span>${d.open ? "" : `<span class="dept-lock">🔒 ${lock}</span>`}`;
      btn.onclick = () => (d.open ? openDept(d.id) : say(d.soon ? `${d.name} is coming soon!` : `${d.name} opens when you learn ${lock.slice(6)}.`));
      return btn;
    })
  );
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
  if (d.id === "orders") return renderOrders();
  if (d.id === "habitats") return renderHabitats();
  $("dept-title").textContent = d.name;
  $("dept-hint").textContent = dept.coupon
    ? "Use your coupon on any pet here, or buy with coins. Click a pet to meet it!"
    : "New pets arrive every night. Click a pet to meet it!";
  const grid = $("shop-grid");
  grid.className = `shop-grid dept-${d.id}`;
  grid.replaceChildren(...dept.slots.map(card));
}

function card(slot) {
  const el = document.createElement("article");
  el.className = "shop-card";
  el.dataset.index = slot.index;
  if (slot.sold) {
    el.classList.add("sold");
    el.innerHTML = `<div class="sold-sign">Adopted!</div><p class="card-note">A new pet comes tomorrow.</p>`;
    return el;
  }
  if (slot.saved) el.classList.add("saved");
  el.tabIndex = 0;
  el.setAttribute("role", "button");
  el.setAttribute("aria-label", `${speciesName(slot.species)}, ${slot.price} coins`);
  // zoomed in up to 2x past the department's shared scale: sizes still compare,
  // and the smallest pets aren't specks
  el.appendChild(petCanvas(slot, BABY, 150, 110, Math.min(fitScale([slot.genes], BABY, 150, 110, 6), cardScale * 2)));
  const info = document.createElement("div");
  info.className = "card-info";
  info.innerHTML = `<h3>${speciesName(slot.species)}</h3><p class="card-price">${dept.coupon ? "<b>Free with coupon!</b>" : coins(slot.price)}</p>${badges(slot)}`;
  el.appendChild(info);
  if (slot.saved) el.insertAdjacentHTML("beforeend", `<div class="ribbon ribbon-saved">Saved!</div>`);
  else if (slot.last_day) el.insertAdjacentHTML("beforeend", `<div class="ribbon ribbon-last">Last day!</div>`);
  el.onclick = () => showDetail(slot.index);
  el.onkeydown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      showDetail(slot.index);
    }
  };
  return el;
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

let habitatConfirm = null; // the kind whose Buy button asks "Are you sure?"

function renderHabitats() {
  const h = dept.habitats;
  $("dept-title").textContent = "Habitats";
  $("dept-hint").textContent = `A habitat is a home on the Trailhead where ${h.capacity} of your pets can live and play. You have ${h.owned} of ${h.spots}.`;
  const grid = $("shop-grid");
  grid.className = "shop-grid habitats-floor";
  grid.replaceChildren(
    ...h.kinds.map((kind) => {
      const card = document.createElement("div");
      card.className = "habitat-card";
      card.dataset.kind = kind.id;
      const view = habitatBackground(kind.id, 2);
      const full = h.owned >= h.spots;
      const short = dept.coins < kind.price;
      const confirm = habitatConfirm === kind.id;
      card.innerHTML = `<h3>${kind.name}</h3>
        <p class="card-price">${kind.price ? coins(kind.price) : "<b>Free!</b> Your first habitat is on us."}</p>`;
      card.insertBefore(view, card.querySelector(".card-price"));
      const btn = document.createElement("button");
      btn.className = "button-gold big-button";
      btn.disabled = full || short;
      btn.textContent = full
        ? "Your trail is full"
        : short
          ? `Need ${(kind.price - dept.coins).toLocaleString()} more coins`
          : confirm
            ? "Yes, get it!"
            : kind.price
              ? `Buy for ${kind.price.toLocaleString()} coins`
              : "Get it free!";
      btn.onclick = () => buyHabitat(kind);
      card.appendChild(btn);
      return card;
    })
  );
}

async function buyHabitat(kind) {
  if (habitatConfirm !== kind.id) {
    habitatConfirm = kind.id;
    return renderHabitats();
  }
  habitatConfirm = null;
  try {
    const data = await call(`/api/pets/shop/habitats/${kind.id}`, "POST");
    setDept(data);
    say("");
    $("dept-hint").innerHTML = `🎉 Your <b>${data.bought.name}</b> is ready! Find it on the <a href="/pets/trail">Trailhead</a>, and move pets in at the <a href="/pets/care">Pet Care Center</a>.`;
  } catch (err) {
    say(err.message);
    renderHabitats();
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
  const cards = document.createElement("div");
  const orderDept = o && dept.choices.find((c) => c.species === o.species);
  cards.className = `shop-grid order-pets dept-${orderDept ? orderDept.dept : ""}`;
  cards.replaceChildren(...dept.slots.map(card));
  if (dept.slots.length) parts.push(cards);
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
      <figure><canvas id="order-preview" width="220" height="160" data-scale="4"></canvas><figcaption>Something like this</figcaption></figure>
      <button class="link-button" id="order-another">Show me another</button>
    </div>
    <p class="order-explain">Sending the order costs <b>${coins(choice.fee)} coins</b>. Tomorrow, <b>4 ${name}</b> in your colors will be waiting here.
      You can buy the ones you love. If you don't, they go home after 3 days.</p>
    ${replacing}
    <div class="detail-actions"><button id="order-send" class="button-gold big-button"${short ? " disabled" : ""}>${
      short ? `Need ${(choice.fee - dept.coins).toLocaleString()} more coins` : confirmOrder ? "Yes, send it!" : `Send my order`
    }</button></div>`;

  const repick = (changes) => {
    Object.assign(pick, changes);
    confirmOrder = false;
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
  canvas.dataset.scale = fitScale([preview], BABY, canvas.width, canvas.height, 7);
  paint(canvas, preview, BABY, Number(canvas.dataset.scale));
}

async function sendOrder() {
  if (!confirmOrder) {
    confirmOrder = true;
    return renderOrders();
  }
  confirmOrder = false;
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
  confirming = false;
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
    button(confirming === "coupon" ? "Yes, use my coupon!" : "Use my coupon (free!)", "button-gold big-button", () => buy(slot, true));
  }
  const coinsLeft = dept.coins;
  const short = coinsLeft < slot.price;
  button(
    short ? `Need ${(slot.price - coinsLeft).toLocaleString()} more coins` : confirming === "coins" ? "Yes, buy it!" : `Buy for ${slot.price.toLocaleString()} coins`,
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
  const kind = coupon ? "coupon" : "coins";
  if (confirming !== kind) {
    confirming = kind;
    return renderDetail();
  }
  try {
    const data = await call(`/api/pets/shop/${deptId}/${slot.index}/buy`, "POST", { coupon });
    const pet = data.bought;
    setDept(data);
    if (!data.coupon) front.coupon = false;
    renderBanners();
    welcome(pet);
  } catch (err) {
    confirming = false;
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
    const asked = new URLSearchParams(location.search).get("dept");
    const open = front.departments.filter((d) => d.open);
    const pick = open.find((d) => d.id === asked) || (front.coupon && open.find((d) => d.id === "household")) || open[0];
    return openDept(pick.id);
  })
  .then(() => setInterval(tick, TICK_MS))
  .catch((err) => {
    console.error(err);
    say(`Couldn't open the shop (${err.message}). Try reloading.`);
  });
