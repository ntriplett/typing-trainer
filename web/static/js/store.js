// The store page: tabs of shelves, each item shown on the player's own
// avatar ("try it on"), with buy / wear / take-off buttons. A clothing
// style sold in several colors is one card with color swatches.
// All rules live server-side (app/store.py); this page just reflects
// /api/store and posts actions.

const TABS = [
  {
    id: "clothes",
    title: "Clothes",
    shelves: [
      { title: "Shirts & dresses", match: (i) => i.slot === "shirt" },
      { title: "Pants & skirts", match: (i) => i.slot === "pants" },
      { title: "Shoes", match: (i) => i.slot === "shoes" },
    ],
  },
  { id: "hats", title: "Hats", shelves: [{ title: "Hats", match: (i) => i.slot === "hat" }] },
  {
    id: "accessories",
    title: "Accessories",
    shelves: [{ title: "Accessories", match: (i) => i.slot === "accessory" }],
  },
  { id: "pets", title: "Pets", shelves: [] }, // adoption: rendered from /api/pets
  {
    id: "places",
    title: "Places",
    shelves: [
      { title: "Fields & forests", match: (i) => i.slot === "background" && i.group === "forests" },
      { title: "By the water", match: (i) => i.slot === "background" && i.group === "water" },
      { title: "Wild lands", match: (i) => i.slot === "background" && i.group === "wild" },
      { title: "Outer space", match: (i) => i.slot === "background" && i.group === "space" },
    ],
  },
  { id: "night", title: "Night", shelves: [{ title: "Night time", match: (i) => i.slot === "night" }] },
  {
    id: "bedroom",
    title: "Bedroom",
    shelves: [
      { title: "Furniture & toys", match: (i) => i.slot === "furniture" && i.group === "floor" },
      { title: "Wall decorations", match: (i) => i.slot === "furniture" && i.group === "wall" },
      { title: "Wallpaper", match: (i) => i.slot === "wallpaper" },
      { title: "Floors", match: (i) => i.slot === "flooring" },
    ],
  },
  { id: "hair", title: "Hair dye", shelves: [{ title: "Hair dye", match: (i) => i.slot === "hair_dye" }] },
];

const ROOM_KINDS = ["furniture", "wallpaper", "flooring"]; // shown as room thumbnails, not on you

// A night unlock's thumbnail: every place it works in, side by side, at
// night -- so it reads as "night for these places", not a new place.
function drawNightCollage(canvas, placeIds) {
  const ctx = canvas.getContext("2d");
  const scale = canvas.width / AVATAR_SIZE;
  const strip = AVATAR_SIZE / placeIds.length;
  placeIds.forEach((id, i) => {
    const left = i * strip;
    const shift = left - (AVATAR_SIZE - strip) / 2; // show each scene's middle
    const clip = (x, y, w, h, c) => {
      const x0 = Math.max(x + shift, left), x1 = Math.min(x + shift + w, left + strip);
      if (x1 <= x0) return;
      ctx.fillStyle = c;
      ctx.fillRect(x0 * scale, y * scale, (x1 - x0) * scale, h * scale);
    };
    spriteFor(id).draw(clip, true);
    if (i) {
      ctx.fillStyle = INK;
      ctx.fillRect(left * scale, 0, scale, canvas.height);
    }
  });
}

const tabsEl = document.getElementById("store-tabs");
const itemsEl = document.getElementById("store-items");
const messageEl = document.getElementById("store-message");
const previewCanvas = document.getElementById("preview-avatar");
const previewLabel = document.getElementById("preview-label");
const previewReset = document.getElementById("preview-reset");

let state = null; // latest /api/store response
let petState = null; // latest /api/pets response (adoption shelf)
let tryingOn = null; // item being previewed, or null
let currentTab = loadTab();
const shownVariant = {}; // family key -> item id the card is showing

previewReset.addEventListener("click", () => {
  tryingOn = null;
  renderPreview();
});

// Locked rooms (app/unlocks.py) keep their tabs hidden until they open.
function visibleTabs() {
  const open = (state && state.unlocks) || {};
  return TABS.filter((t) => (t.id === "pets" ? open.pets : t.id === "bedroom" ? open.bedroom : true));
}

function loadTab() {
  const asked = new URLSearchParams(location.search).get("tab"); // e.g. /store?tab=pets
  if (asked && TABS.some((t) => t.id === asked)) return asked;
  try {
    const saved = localStorage.getItem("store-tab");
    return TABS.some((t) => t.id === saved) ? saved : TABS[0].id;
  } catch {
    return TABS[0].id;
  }
}

function saveTab(id) {
  try {
    localStorage.setItem("store-tab", id);
  } catch {
    // per-viewer convenience only
  }
}

async function load() {
  const [r, p] = await Promise.all([fetch("/api/store"), fetch("/api/pets")]);
  if (!r.ok) throw new Error(`/api/store returned ${r.status}`);
  if (!p.ok && p.status !== 403) throw new Error(`/api/pets returned ${p.status}`);
  state = await r.json();
  petState = p.ok ? await p.json() : null; // 403: the pet room is still a mystery
  render();
}

function withItem(avatar, item) {
  if (!item) return avatar;
  if (item.slot === "hair_dye") {
    const color = item.id.replace(/^dye_/, "");
    return { ...avatar, appearance: { ...avatar.appearance, hair_color: color } };
  }
  return { ...avatar, [item.slot]: item.id };
}

// Items sold in several colors share a family: "shirt_tee_blue" and
// "shirt_tee_red" both belong to group "shirt_tee".
function familyKey(item) {
  return item.group && item.id.startsWith(`${item.group}_`) ? item.group : item.id;
}

function colorOf(item) {
  return item.id.slice(item.group.length + 1);
}

function renderPreview() {
  drawAvatar(previewCanvas, withItem(state.avatar, tryingOn));
  previewLabel.textContent = tryingOn ? `Trying on: ${tryingOn.name}` : "This is you!";
  previewReset.hidden = !tryingOn;
}

function render() {
  renderPreview();
  const tabs = visibleTabs();
  if (!tabs.some((t) => t.id === currentTab)) currentTab = tabs[0].id;
  tabsEl.replaceChildren(
    ...tabs.map((tab) => {
      const btn = document.createElement("button");
      btn.className = "tab-button" + (tab.id === currentTab ? " active" : "");
      btn.dataset.tab = tab.id;
      btn.textContent = tab.title;
      btn.onclick = () => {
        currentTab = tab.id;
        saveTab(tab.id);
        render();
      };
      return btn;
    })
  );

  itemsEl.innerHTML = "";
  if (currentTab === "pets") {
    renderAdoption();
    return;
  }
  const tab = TABS.find((t) => t.id === currentTab);
  for (const shelf of tab.shelves) {
    const items = state.items.filter(shelf.match);
    if (!items.length) continue;
    const section = document.createElement("section");
    section.className = "panel shelf";
    section.innerHTML = `<h2 class="panel-title">${shelf.title}</h2><div class="item-grid"></div>`;
    const grid = section.querySelector(".item-grid");
    const families = new Map();
    for (const item of items) {
      const key = familyKey(item);
      if (!families.has(key)) families.set(key, []);
      families.get(key).push(item);
    }
    for (const [key, variants] of families) grid.appendChild(familyCard(key, variants));
    itemsEl.appendChild(section);
  }
}

// --- adopting pets ---------------------------------------------------------------

const adoptColor = {}; // species -> coloring shown on its card

function renderAdoption() {
  const section = document.createElement("section");
  section.className = "panel shelf";
  section.innerHTML = `<h2 class="panel-title">Adopt a pet</h2>
    <p class="hint">${
      state.unlocks.free_pet
        ? "<b>Your first pet is free!</b> A gift for learning the home row. Pick any one you like."
        : 'Pets start as babies. Feed them once a day in the <a href="/pets">pet room</a> to help them grow up!'
    }</p>
    <div class="item-grid"></div>`;
  const grid = section.querySelector(".item-grid");
  for (const kind of petState.species) grid.appendChild(adoptCard(kind));
  itemsEl.appendChild(section);
}

function adoptCard(kind) {
  const color = adoptColor[kind.species] || kind.colors[0];
  const grownPet = { species: kind.species, color, stage: "grown", slot: 1 };
  const card = document.createElement("article");
  card.className = "item-card";
  card.dataset.species = kind.species;

  const thumb = makeAvatarCanvas(144);
  const others = (state.avatar.pets || []).filter((p) => p.slot !== 1);
  drawAvatar(thumb, { ...state.avatar, pets: [...others, grownPet] });

  const info = document.createElement("div");
  info.className = "item-info";
  info.innerHTML = `
    <h3>${kind.name}</h3>
    <p class="item-desc">${kind.description}</p>
    <p class="coins-inline">${
      state.unlocks.free_pet ? "<b>Free!</b>" : `<span class="coin-icon"></span>${kind.price.toLocaleString()}`
    }</p>`;

  const row = document.createElement("div");
  row.className = "swatch-row";
  for (const c of kind.colors) {
    const btn = document.createElement("button");
    btn.className = "color-swatch" + (c === color ? " selected" : "");
    btn.style.background = PET_COLORS[kind.species][c][0];
    btn.title = `${c} ${kind.name.toLowerCase()}`;
    btn.setAttribute("aria-label", btn.title);
    btn.onclick = () => {
      adoptColor[kind.species] = c;
      render();
    };
    row.appendChild(btn);
  }

  const btn = document.createElement("button");
  if (state.unlocks.free_pet || state.coins >= kind.price) {
    btn.textContent = state.unlocks.free_pet ? "Adopt for free" : "Adopt";
    btn.className = "button-gold";
    btn.onclick = () => adopt(kind, color);
  } else {
    btn.textContent = `Need ${(kind.price - state.coins).toLocaleString()} more`;
    btn.disabled = true;
  }
  card.append(thumb, info, row, btn);
  return card;
}

async function adopt(kind, color) {
  messageEl.textContent = "";
  messageEl.classList.remove("ok");
  const r = await fetch("/api/pets/adopt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ species: kind.species, color }),
  });
  const data = await r.json();
  if (!r.ok) {
    messageEl.textContent = data.detail || "Something went wrong.";
    return;
  }
  Header.update(data);
  await load();
  messageEl.classList.add("ok");
  messageEl.innerHTML = `Welcome home, little ${kind.name.toLowerCase()}! Give it a name in the <a href="/pets">pet room</a>.`;
}

function pickVariant(key, variants) {
  const remembered = variants.find((v) => v.id === shownVariant[key]);
  return remembered || variants.find((v) => v.equipped) || variants.find((v) => v.owned) || variants[0];
}

function familyCard(key, variants) {
  const item = pickVariant(key, variants);
  const card = document.createElement("article");
  card.className = "item-card" + (item.equipped ? " equipped" : "");
  card.dataset.itemId = item.id;
  if (variants.length > 1) card.dataset.family = key;

  const thumb = makeAvatarCanvas(144);
  if (ROOM_KINDS.includes(item.slot)) {
    drawRoomThumb(thumb, item.id);
  } else if (item.slot === "night") {
    drawNightCollage(thumb, item.places.map((p) => p.id));
  } else {
    drawAvatar(thumb, withItem(state.avatar, item));
    thumb.title = `Try on the ${item.name}`;
    thumb.addEventListener("click", () => {
      tryingOn = item;
      renderPreview();
    });
  }

  const info = document.createElement("div");
  info.className = "item-info";
  info.innerHTML = `
    <h3>${item.name}</h3>
    <p class="item-desc">${item.description}</p>
    ${item.slot === "night" ? `<p class="item-desc night-places">Turns on night for: ${item.places.map((p) => p.name).join(", ")}</p>` : ""}
    <p class="coins-inline"><span class="coin-icon"></span>${item.price.toLocaleString()}</p>`;

  card.append(thumb, info);
  if (variants.length > 1) card.appendChild(swatches(key, variants, item));
  card.appendChild(actionButton(item));
  return card;
}

function swatches(key, variants, shown) {
  const row = document.createElement("div");
  row.className = "swatch-row";
  for (const v of variants) {
    const btn = document.createElement("button");
    btn.className = "color-swatch" + (v.id === shown.id ? " selected" : "") + (v.owned ? " owned" : "");
    btn.style.background = (CLOTH_COLORS[colorOf(v)] || ["#ccc"])[0];
    btn.title = v.name + (v.owned ? " (yours)" : "");
    btn.setAttribute("aria-label", btn.title);
    btn.onclick = () => {
      shownVariant[key] = v.id;
      tryingOn = v;
      render();
    };
    row.appendChild(btn);
  }
  return row;
}

function actionButton(item) {
  const btn = document.createElement("button");
  const usable = ["hair_dye", "wallpaper", "flooring"].includes(item.slot); // used, not worn
  if (item.slot === "furniture" && item.equipped) {
    btn.textContent = "In your room ✓";
    btn.onclick = () => (window.location.href = "/bedroom");
  } else if (item.slot === "furniture" && item.owned) {
    btn.textContent = "Put in room";
    btn.className = "button-go";
    btn.onclick = () => act(`/api/store/equip/${item.id}`);
  } else if (item.slot === "night" && item.equipped) {
    btn.textContent = "Turn off";
    btn.onclick = () => act("/api/me/night", null, "PUT", { on: false });
  } else if (item.slot === "night" && item.owned && !item.places.some((p) => p.owned)) {
    btn.textContent = "Get one of its places";
    btn.onclick = () => {
      currentTab = "places";
      saveTab("places");
      render();
    };
  } else if (item.slot === "night" && item.owned) {
    btn.textContent = "Turn on night";
    btn.className = "button-go";
    btn.onclick = () => act(`/api/store/equip/${item.id}`);
  } else if (item.equipped && usable) {
    btn.textContent = "In use";
    btn.disabled = true;
  } else if (item.equipped) {
    btn.textContent = "Take off";
    btn.onclick = () => act(`/api/store/unequip/${item.slot}`);
  } else if (item.owned) {
    btn.textContent = usable ? "Use" : "Wear";
    btn.className = "button-go";
    btn.onclick = () => act(`/api/store/equip/${item.id}`);
  } else if (item.affordable) {
    btn.textContent = "Buy";
    btn.className = "button-gold";
    btn.onclick = () => act(`/api/store/buy/${item.id}`, item);
  } else {
    btn.textContent = `Need ${(item.price - state.coins).toLocaleString()} more`;
    btn.disabled = true;
  }
  return btn;
}

async function act(url, boughtItem = null, method = "POST", body = null) {
  messageEl.textContent = "";
  messageEl.classList.remove("ok");
  let r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : null,
  });
  // Buying wears it straight away (a night unlock only if you own one of its places).
  const nightWithoutPlace = boughtItem && boughtItem.slot === "night" && !boughtItem.places.some((p) => p.owned);
  if (r.ok && boughtItem && !nightWithoutPlace) {
    r = await fetch(`/api/store/equip/${boughtItem.id}`, { method: "POST" });
  }
  const data = await r.json();
  if (!r.ok) {
    messageEl.textContent = data.detail || "Something went wrong.";
    return;
  }
  Header.update(data);
  tryingOn = null;
  await load();
}

load().catch((err) => {
  console.error(err);
  messageEl.textContent = `Couldn't load the store (${err.message}). Try reloading.`;
});
