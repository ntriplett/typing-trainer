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
  { id: "pets", title: "Pets", shelves: [{ title: "Pets", match: (i) => i.slot === "pet" }] },
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
  { id: "hair", title: "Hair dye", shelves: [{ title: "Hair dye", match: (i) => i.slot === "hair_dye" }] },
];

// A night unlock's thumbnail shows one of its own places at night.
const NIGHT_PREVIEW_PLACE = { forests: "bg_meadow", water: "bg_beach", wild: "bg_desert", space: "bg_moon" };

const tabsEl = document.getElementById("store-tabs");
const itemsEl = document.getElementById("store-items");
const messageEl = document.getElementById("store-message");
const previewCanvas = document.getElementById("preview-avatar");
const previewLabel = document.getElementById("preview-label");
const previewReset = document.getElementById("preview-reset");

let state = null; // latest /api/store response
let tryingOn = null; // item being previewed, or null
let currentTab = loadTab();
const shownVariant = {}; // family key -> item id the card is showing

previewReset.addEventListener("click", () => {
  tryingOn = null;
  renderPreview();
});

function loadTab() {
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
  const r = await fetch("/api/store");
  if (!r.ok) throw new Error(`/api/store returned ${r.status}`);
  state = await r.json();
  render();
}

function withItem(avatar, item) {
  if (!item) return avatar;
  if (item.slot === "night") {
    return { ...avatar, background: NIGHT_PREVIEW_PLACE[item.group], night: true };
  }
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
  tabsEl.replaceChildren(
    ...TABS.map((tab) => {
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
  drawAvatar(thumb, withItem(state.avatar, item));
  thumb.title = `Try on the ${item.name}`;
  thumb.addEventListener("click", () => {
    tryingOn = item;
    renderPreview();
  });

  const info = document.createElement("div");
  info.className = "item-info";
  info.innerHTML = `
    <h3>${item.name}</h3>
    <p class="item-desc">${item.description}</p>
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
  const usable = item.slot === "hair_dye"; // used, not worn
  if (item.slot === "night" && item.equipped) {
    btn.textContent = "Turn off";
    btn.onclick = () => act("/api/me/night", null, "PUT", { on: false });
  } else if (item.slot === "night" && item.owned) {
    btn.textContent = "Turn on";
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
  let r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : null,
  });
  // Buying wears it straight away (a night unlock only if you're in one of its places).
  if (r.ok && boughtItem && !(boughtItem.slot === "night" && state.night.group !== boughtItem.group)) {
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
