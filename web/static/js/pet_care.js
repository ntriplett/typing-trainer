// The Pet Care Center (app/pet_care.py, PLAN.md 11i): a book of your pets.
// The left page shows 12 at a time (sort, filter, turn pages); the right
// page is one pet: rename it, feed it a garden veggie, move it into a
// habitat, bring it along. New things to do with pets go on the right page.

const $ = (id) => document.getElementById(id);
const PER_PAGE = 12;
const TICK_MS = 400;
const RARE_SHOWN = 1.2;
const SUPER_RARE = 1.4;
const RARE_LABEL = {
  coat: "Three colors",
  pattern: "Rare pattern",
  fins: "Rare fins",
  mix: "Mixed breed",
  eyes: "Rare eyes",
  "odd eyes": "Odd eyes",
  "main color": "Rare color",
};
const TRAITS = [
  ["energy", "Energy"],
  ["friendly", "Friendly"],
  ["curious", "Curious"],
  ["playful", "Playful"],
  ["sleepy", "Sleepy"],
];
const SIDE = { 1: "right", 2: "left" };

const speciesName = petSpeciesName;
const grownSize = (p) => {
  const s = petSize(p.genes, 10);
  return s.w * s.h;
};

const SORTS = {
  newest: { label: "Newest first", order: (a, b) => b.id - a.id },
  oldest: { label: "Had longest", order: (a, b) => a.id - b.id },
  name: { label: "Name", order: (a, b) => a.name.localeCompare(b.name) },
  kind: { label: "Kind of pet", order: (a, b) => a.species.localeCompare(b.species) || a.name.localeCompare(b.name) },
  age: { label: "Most grown", order: (a, b) => b.growth - a.growth || b.id - a.id },
  rarity: { label: "Rarest", order: (a, b) => b.rarity - a.rarity || b.id - a.id },
  size: { label: "Biggest", order: (a, b) => grownSize(b) - grownSize(a) || b.id - a.id },
  energy: { label: "Most energy", order: (a, b) => b.genes.personality.energy - a.genes.personality.energy },
};

let care = null; // /api/care
let sortKey = remembered("care-sort", "newest");
let filterKey = "all";
let page = 0;
let selectedId = null;
let mode = null; // the right page's open picker: "rename", "feed", "move", "along"
let frame = 0;

function remembered(key, fallback) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

function remember(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* a private window: fine */
  }
}

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

function say(text, good = false) {
  $("care-message").className = good ? "error-text ok" : "error-text";
  $("care-message").textContent = text || "";
}

// --- drawing ------------------------------------------------------------------------

function paint(canvas, p, most) {
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const { w, h } = petSize(p.genes, p.growth);
  const scale = Math.max(1, Math.min(most, Math.floor((canvas.width - 8) / w), Math.floor((canvas.height - 10) / h)));
  const px = (x, y, pw, ph, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x), Math.round(y), Math.ceil(pw), Math.ceil(ph));
  };
  const bottom = p.species === "fish" ? Math.round((canvas.height + h * scale) / 2) : canvas.height - 6;
  drawPet(px, Math.round((canvas.width - w * scale) / 2), bottom, p.genes, p.growth, { frame, scale });
}

function petCanvas(p, w, h, most) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.dataset.pet = p.id;
  canvas.dataset.most = most;
  paint(canvas, p, most);
  return canvas;
}

function tick() {
  frame += 1;
  for (const canvas of document.querySelectorAll("canvas[data-pet]")) {
    const p = petById(Number(canvas.dataset.pet));
    if (p && !isPetEgg(p)) paint(canvas, p, Number(canvas.dataset.most));
  }
}

// --- the left page -----------------------------------------------------------------

const petById = (id) => care.pets.find((p) => p.id === id);

function filters() {
  const out = [
    ["all", "All pets"],
    ["waiting", "Waiting for a home"],
    ["along", "Coming along"],
  ];
  for (const h of care.habitats) out.push([`spot:${h.spot}`, `In ${h.name}`]);
  if (care.pets.some((p) => p.water)) out.push(["water", "Fish"]);
  return out;
}

function shown() {
  const keep = {
    all: () => true,
    waiting: (p) => p.spot === null && p.tank === null,
    along: (p) => p.along,
    water: (p) => p.water,
  }[filterKey] || ((p) => `spot:${p.spot}` === filterKey);
  return care.pets.filter(keep).sort(SORTS[sortKey].order);
}

function renderTools() {
  const sort = $("care-sort");
  sort.innerHTML = Object.entries(SORTS)
    .map(([k, s]) => `<option value="${k}"${k === sortKey ? " selected" : ""}>${s.label}</option>`)
    .join("");
  const list = filters();
  if (!list.some(([k]) => k === filterKey)) filterKey = "all";
  $("care-filter").innerHTML = list
    .map(([k, label]) => `<option value="${k}"${k === filterKey ? " selected" : ""}>${label}</option>`)
    .join("");
}

function renderGrid() {
  const pets = shown();
  const pages = Math.max(1, Math.ceil(pets.length / PER_PAGE));
  page = Math.min(page, pages - 1);
  const grid = $("book-grid");
  if (!care.pets.length) {
    grid.innerHTML = `<p class="book-empty">No pets yet! Visit the <a href="/pets/shop">Pet Shop</a> to find one.</p>`;
  } else if (!pets.length) {
    grid.innerHTML = `<p class="book-empty">No pets here.</p>`;
  } else {
    grid.replaceChildren(
      ...pets.slice(page * PER_PAGE, (page + 1) * PER_PAGE).map((p) => {
        const btn = document.createElement("button");
        btn.className = "book-pet" + (p.id === selectedId ? " current" : "");
        btn.dataset.id = p.id;
        btn.setAttribute("aria-pressed", p.id === selectedId);
        btn.appendChild(petCanvas(p, 96, 72, 3));
        const name = document.createElement("span");
        name.className = "book-pet-name";
        name.textContent = p.name;
        btn.appendChild(name);
        if (p.along) btn.insertAdjacentHTML("beforeend", `<span class="book-pet-badge" title="Coming along">🎒</span>`);
        if (p.school > 1) btn.insertAdjacentHTML("beforeend", `<span class="book-pet-count" title="A school of ${p.school}">×${p.school}</span>`);
        btn.onclick = () => select(p.id);
        return btn;
      })
    );
  }
  $("page-count").textContent = `Page ${page + 1} of ${pages}`;
  $("page-prev").disabled = page === 0;
  $("page-next").disabled = page >= pages - 1;
}

function select(id) {
  selectedId = id;
  mode = null;
  say("");
  history.replaceState(null, "", `?pet=${id}`);
  renderGrid();
  renderDetail();
}

// --- the right page ----------------------------------------------------------------

function stageName(p) {
  if (isPetEgg(p)) return "Egg";
  if (p.growth >= care.max_growth) return "All grown up";
  if (p.growth >= 7) return "Almost grown";
  if (p.growth >= 4) return "Growing";
  if (p.growth >= 1) return "Little";
  return "Baby";
}

function days(iso) {
  const n = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  return n < 1 ? "today" : n === 1 ? "yesterday" : `${n} days ago`;
}

function renderDetail() {
  const box = $("book-detail");
  const p = selectedId && petById(selectedId);
  if (!p) {
    box.innerHTML = care.pets.length
      ? `<p class="book-empty">Pick a pet to see all about it.</p>`
      : `<p class="book-empty">Your pets will live in this book.</p>`;
    return;
  }
  const g = p.genes;
  const habitat = p.spot !== null ? care.habitats.find((h) => h.spot === p.spot) : null;
  const tank = p.tank !== null ? care.tanks.find((h) => h.spot === p.tank) : null;
  const colors = g.hex
    .map((hex, i) => (hex ? `<span class="swatch" style="background:${hex}"></span>${g.color_names[i]}` : ""))
    .filter(Boolean)
    .join(" ");
  const rare = Object.entries(p.rare)
    .filter(([, m]) => m >= RARE_SHOWN)
    .map(([k, m]) => `<li>${m >= SUPER_RARE ? "🌟" : "⭐"} ${rareLabel(k, g, RARE_LABEL)}</li>`)
    .join("");
  const traits = TRAITS.map(
    ([k, label]) =>
      `<div class="trait"><span>${label}</span><span class="meter"><span style="width:${Math.round(g.personality[k] * 100)}%"></span></span></div>`
  ).join("");
  box.innerHTML = `
    <div class="detail-name">${mode === "rename" ? renameForm(p) : `<h2>${escapeHtml(p.name)}</h2><button class="link-button" data-act="rename">✏️ Rename</button>`}</div>
    <p class="detail-kind">${speciesName(p.species)}${p.companion ? "" : ` · ${stageName(p)}`}</p>
    <div class="detail-portrait"></div>
    ${p.companion ? "" : `<div class="growth"><span>Growth</span><span class="meter grow"><span style="width:${(p.growth / care.max_growth) * 100}%"></span></span><span>${p.growth}/${care.max_growth}</span></div>`}
    <div class="detail-actions" id="detail-actions"></div>
    <div id="detail-picker"></div>
    <dl class="detail-facts">
      <dt>Home</dt><dd>${p.water ? (tank ? `Swims in <b>${escapeHtml(tank.name)}</b>` : "Waiting for a tank") : habitat ? `Lives in <b>${habitat.name}</b>` : "Here at the Care Center"}${p.along ? ` · 🎒 Comes along on your ${SIDE[p.along]}` : ""}</dd>
      ${p.water ? `<dt>School</dt><dd>${p.school > 1 ? `You have <b>${p.school}</b> of these` : "Just one. Buy more for a school!"}</dd>` : ""}
      ${p.water ? "" : `<dt>${p.companion ? "Friendship" : "Happy"}</dt><dd class="hearts" title="${p.joy} of 5">${"♥".repeat(p.joy)}<span class="empty">${"♡".repeat(5 - p.joy)}</span>${p.joy ? "" : p.companion ? " Bring her a gift in her habitat!" : " Play with it in its habitat!"}</dd>`}
      <dt>Colors</dt><dd class="detail-colors">${colors}</dd>
      ${p.companion ? "" : `<dt>Loves</dt><dd><canvas class="veggie-icon" data-kind="${g.personality.favorite}" width="24" height="30"></canvas> ${care.veggie_names[g.personality.favorite]}</dd>`}
      ${p.companion ? `<dt>Came to stay</dt><dd>${days(p.adopted_at)}</dd>` : `<dt>Got it</dt><dd>${days(p.adopted_at)}, ${p.gift_from ? `a gift from <b>${escapeHtml(p.gift_from)}</b>` : p.from_friend ? `shared by <b>${escapeHtml(p.from_friend)}</b>` : p.source === "order" ? "by special order" : "from the Pet Shop"}</dd>`}
      ${rare ? `<dt>Rare</dt><dd><ul class="detail-rare">${rare}</ul></dd>` : ""}
    </dl>
    <div class="traits">${traits}</div>`;
  box.querySelector(".detail-portrait").appendChild(petCanvas(p, 300, 190, 8));
  for (const c of box.querySelectorAll("canvas.veggie-icon")) drawVeggieIcon(c, c.dataset.kind);
  const rn = box.querySelector("[data-act=rename]");
  if (rn) rn.onclick = () => openMode("rename");
  if (mode === "rename") wireRename(p);
  renderActions(p);
  renderPicker(p);
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

function openMode(m) {
  mode = mode === m ? null : m;
  say("");
  renderDetail();
}

function button(text, cls, onclick, disabled = false) {
  const b = document.createElement("button");
  b.textContent = text;
  b.className = cls;
  b.disabled = disabled;
  b.onclick = onclick;
  return b;
}

function renderActions(p) {
  const out = [];
  if (p.companion) {
    /* nothing to grow: she's herself already */
  } else if (p.grown) out.push(button("All grown up!", "", null, true));
  else if (p.fed_today) out.push(button("Full for today", "", null, true));
  else out.push(button("🥕 Feed", "button-go", () => openMode("feed")));
  if (!p.water) out.push(button(p.spot === null ? "🏡 Move to a habitat" : "🏡 Move", "", () => openMode("move")));
  else {
    const school = p.school > 1 ? " the school" : "";
    out.push(button(p.tank === null ? `🐠 Move${school} to a tank` : `🐠 Move${school}`, "", () => openMode("tank")));
    const short = care.coins < p.copy_price;
    out.push(button(short ? `🐟 Another: need ${(p.copy_price - care.coins).toLocaleString()} more coins` : `🐟 Buy another (${p.copy_price.toLocaleString()} coins)`, "", buyCopy(p), short));
  }
  out.push(button("🧪 Use a potion", "", () => openMode("potion")));
  if (p.along) out.push(button("Stay home", "", () => setAlong(p, null)));
  else if (!p.water) out.push(button("🎒 Bring along", "", () => bringAlong(p)));
  if (!p.companion) out.push(button("💌 Share with a friend", "", () => openMode("share")));
  $("detail-actions").replaceChildren(...out);
}

function renderPicker(p) {
  const box = $("detail-picker");
  box.className = mode && mode !== "rename" ? "picker" : "";
  if (mode === "feed") {
    const kinds = Object.keys(care.veggies);
    if (!kinds.length) {
      box.innerHTML = `<p>No veggies yet! Grow some in the <a href="/garden">garden</a>.</p>`;
      return;
    }
    const fav = p.genes.personality.favorite;
    box.innerHTML = `<p>What should ${escapeHtml(p.name)} eat? ⭐ is its favorite (grows twice as much!)</p><div class="veggie-picks"></div>`;
    box.querySelector(".veggie-picks").replaceChildren(
      ...kinds.map((k) => {
        const b = document.createElement("button");
        b.className = "veggie-pick" + (k === fav ? " favorite" : "");
        b.dataset.veggie = k;
        b.innerHTML = `<canvas class="veggie-icon" data-kind="${k}" width="28" height="34"></canvas><span>${care.veggie_names[k]} ×${care.veggies[k]}${k === fav ? " ⭐" : ""}</span>`;
        drawVeggieIcon(b.querySelector("canvas"), k);
        b.onclick = () => feed(p, k);
        return b;
      })
    );
  } else if (mode === "move") {
    const picks = care.habitats
      .filter((h) => h.spot !== p.spot && (!p.swimmer || h.water))
      .map((h) => {
        const full = h.count >= h.capacity;
        return button(`${h.name} (${h.count}/${h.capacity})${full ? " full" : ""}`, "", () => move(p, h.spot), full);
      });
    if (p.spot !== null) picks.push(button("Back to the Care Center", "", () => move(p, null)));
    if (p.swimmer && !picks.length) picks.push(Object.assign(document.createElement("p"), { textContent: `${p.name} needs a habitat with plenty of water, like a Pond or a Beach.` }));
    box.replaceChildren(...picks);
    if (!care.habitats.length)
      box.innerHTML = `<p>You don't have a habitat yet. Get one in the <a href="/pets/shop?dept=habitats">Pet Shop</a>!</p>`;
  } else if (mode === "potion") {
    box.innerHTML = `<p>Loading your potions…</p>`;
    loadPotions(p, box);
  } else if (mode === "share") {
    box.innerHTML = `<p>Finding your friends…</p>`;
    loadFriends(p, box);
  } else if (mode === "tank") {
    const picks = care.tanks
      .filter((h) => h.spot !== p.tank)
      .map((h) => {
        const full = h.count >= h.capacity;
        return button(`${h.name} (${h.count}/${h.capacity})${full ? " full" : ""}`, "", () => act(`/api/care/${p.id}/tank`, "PUT", { spot: h.spot }), full);
      });
    if (p.tank !== null) picks.push(button("Back to the Care Center", "", () => act(`/api/care/${p.id}/tank`, "PUT", { spot: null })));
    box.replaceChildren(...picks);
  } else if (mode === "along") {
    const along = care.pets.filter((x) => x.along).sort((a, b) => a.along - b.along);
    box.innerHTML = `<p>You can bring ${care.max_along} pets. Who should stay home?</p>`;
    box.append(...along.map((x) => button(`${x.name} stays home`, "", () => setAlong(p, x.along))));
  } else {
    box.replaceChildren();
  }
}

function renameForm(p) {
  return `<form class="rename-form"><input id="rename-input" maxlength="${care.max_name}" value="${escapeHtml(p.name)}" aria-label="New name" />
    <button class="button-go">Save</button><button type="button" class="link-button" data-act="cancel">Cancel</button></form>`;
}

function wireRename(p) {
  const input = $("rename-input");
  input.focus();
  input.select();
  input.onkeydown = (e) => {
    if (e.key === "Escape") openMode("rename");
  };
  document.querySelector("[data-act=cancel]").onclick = () => openMode("rename");
  document.querySelector(".rename-form").onsubmit = (e) => {
    e.preventDefault();
    act(`/api/care/${p.id}/name`, "PUT", { name: input.value });
  };
}

// --- actions ----------------------------------------------------------------------

async function act(url, method, body, after) {
  try {
    care = await call(url, method, body);
    mode = null;
    say("");
    renderTools();
    renderGrid();
    renderDetail();
    if (after) after(care);
  } catch (err) {
    say(err.message);
  }
}

function feed(p, veggie) {
  act(`/api/care/${p.id}/feed`, "POST", { veggie }, (data) => {
    const fed = data.fed;
    const news = fed.favorite ? `Yum, its favorite! ${p.name} grew a lot!` : `Yum! ${p.name} grew!`;
    say(fed.growth >= data.max_growth ? `${news} All grown up now!` : news, true);
  });
}

// Share a copy of this pet's look with another player here (app/pet_share.py):
// it waits in their Special Orders tomorrow, and you keep yours.
async function loadFriends(p, box) {
  const r = await fetch(`/api/care/${p.id}/share`);
  const friends = (await r.json()).friends || [];
  if (mode !== "share" || selectedId !== p.id) return;
  const name = escapeHtml(p.name);
  if (!friends.length) {
    box.innerHTML = `<p>Nobody else plays on this computer yet. When a friend makes a player, you can share ${name} with them!</p>`;
    return;
  }
  const ask = friends.length === 1 ? `Share ${name} with ${escapeHtml(friends[0].name)}?` : "Who are you sharing with?";
  box.innerHTML = `<p class="share-ask"><b>${ask}</b> Tomorrow a baby just like ${name} will wait in their Special Orders for them to adopt. You keep ${name}!</p>`;
  for (const f of friends) {
    const row = document.createElement("div");
    row.className = "share-friend";
    row.append(button(`💌 ${f.name}`, f.why ? "" : "button-go", () => sharePet(p, f), !!f.why));
    if (f.why) row.append(Object.assign(document.createElement("span"), { className: "share-why", textContent: f.why }));
    box.append(row);
  }
}

function sharePet(p, friend) {
  act(`/api/care/${p.id}/share`, "POST", { to: friend.id }, () =>
    say(`💌 Shared! Tomorrow ${friend.name} will find a baby like ${p.name} in their Special Orders.`, true)
  );
}

async function loadPotions(p, box) {
  const r = await fetch(`/api/care/${p.id}/potions`);
  const potions = (await r.json()).potions || [];
  if (mode !== "potion" || selectedId !== p.id) return;
  if (!potions.length) {
    box.innerHTML = `<p>No potions that work on ${escapeHtml(p.name)}. Find new ones every day in the <a href="/pets/shop?dept=supplies&page=2">Pet Shop</a>!</p>`;
    return;
  }
  box.innerHTML = `<p>Pick a potion to repaint ${escapeHtml(p.name)}${p.school > 1 ? " and its whole school" : ""}. A ? is a surprise!</p>`;
  for (const potion of potions) {
    const b = document.createElement("button");
    b.className = "potion-pick";
    b.dataset.potion = potion.id;
    const c = document.createElement("canvas");
    c.width = 48;
    c.height = 48;
    supplyCanvas(c, (r) => drawPotion(r, potion.shown));
    const label = potion.shown.map((col) => (col ? col.name : "?")).join(" + ");
    b.append(c, Object.assign(document.createElement("span"), { textContent: label }));
    b.onclick = () =>
      act(`/api/care/${p.id}/potion`, "POST", { potion: potion.id }, (data) => {
        say(`✨ Ta-da! ${p.name} is now ${data.potion.colors.map((col) => col.name).join(" and ")}!`, true);
      });
    box.appendChild(b);
  }
}

function buyCopy(p) {
  return () =>
    act(`/api/care/${p.id}/copy`, "POST", null, () => {
      const now = petById(p.id);
      say(`Another ${p.name} joined the school! You have ${now.school}.`, true);
    });
}

function move(p, spot) {
  act(`/api/care/${p.id}/home`, "PUT", { spot });
}

function setAlong(p, slot) {
  act(`/api/care/${p.id}/along`, "PUT", { slot });
}

function bringAlong(p) {
  const taken = new Set(care.pets.filter((x) => x.along).map((x) => x.along));
  const free = [1, 2].find((s) => !taken.has(s));
  if (free) setAlong(p, free);
  else openMode("along");
}

// --- start ---------------------------------------------------------------------------

async function load() {
  care = await call("/api/care");
  const asked = Number(new URLSearchParams(location.search).get("pet"));
  if (asked && petById(asked)) {
    selectedId = asked;
    const i = shown().findIndex((p) => p.id === asked);
    page = Math.floor(i / PER_PAGE);
  } else if (care.pets.length) {
    selectedId = shown()[0].id;
  }
  renderTools();
  renderGrid();
  renderDetail();
  $("care-sort").onchange = (e) => {
    sortKey = e.target.value;
    remember("care-sort", sortKey);
    page = 0;
    renderGrid();
  };
  $("care-filter").onchange = (e) => {
    filterKey = e.target.value;
    page = 0;
    renderGrid();
  };
  $("page-prev").onclick = () => {
    page -= 1;
    renderGrid();
  };
  $("page-next").onclick = () => {
    page += 1;
    renderGrid();
  };
}

load()
  .then(() => setInterval(tick, TICK_MS))
  .catch((err) => {
    console.error(err);
    say(`Couldn't open the Pet Care Center (${err.message}). Try reloading.`);
  });
