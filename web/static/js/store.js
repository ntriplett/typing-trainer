// The store page: shelves of items grouped by slot, each shown on the
// player's own avatar ("try it on"), with buy / wear / take-off buttons.
// All rules live server-side (app/store.py); this page just reflects
// /api/store and posts actions.

const SHELVES = [
  { title: "Hats", match: (i) => i.slot === "hat" },
  { title: "Clothes", match: (i) => ["shirt", "pants", "shoes"].includes(i.slot) },
  { title: "Pets", match: (i) => i.slot === "pet" },
  { title: "Places: fields & forests", match: (i) => i.slot === "background" && i.group === "forests" },
  { title: "Places: by the water", match: (i) => i.slot === "background" && i.group === "water" },
  { title: "Places: wild lands", match: (i) => i.slot === "background" && i.group === "wild" },
  { title: "Places: outer space", match: (i) => i.slot === "background" && i.group === "space" },
  { title: "Night time", match: (i) => i.slot === "night" },
  { title: "Hair dye", match: (i) => i.slot === "hair_dye" },
];

// A night unlock's thumbnail shows one of its own places at night.
const NIGHT_PREVIEW_PLACE = { forests: "bg_meadow", water: "bg_beach", wild: "bg_desert", space: "bg_moon" };

const itemsEl = document.getElementById("store-items");
const messageEl = document.getElementById("store-message");
const previewCanvas = document.getElementById("preview-avatar");
const previewLabel = document.getElementById("preview-label");
const previewReset = document.getElementById("preview-reset");

let state = null; // latest /api/store response
let tryingOn = null; // item being previewed, or null

previewReset.addEventListener("click", () => {
  tryingOn = null;
  renderPreview();
});

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

function renderPreview() {
  drawAvatar(previewCanvas, withItem(state.avatar, tryingOn));
  previewLabel.textContent = tryingOn ? `Trying on: ${tryingOn.name}` : "This is you!";
  previewReset.hidden = !tryingOn;
}

function render() {
  renderPreview();
  itemsEl.innerHTML = "";
  for (const shelf of SHELVES) {
    const items = state.items.filter(shelf.match);
    if (!items.length) continue;
    const section = document.createElement("section");
    section.className = "panel shelf";
    section.innerHTML = `<h2 class="panel-title">${shelf.title}</h2><div class="item-grid"></div>`;
    const grid = section.querySelector(".item-grid");
    items.forEach((item) => grid.appendChild(itemCard(item)));
    itemsEl.appendChild(section);
  }
}

function itemCard(item) {
  const card = document.createElement("article");
  card.className = "item-card" + (item.equipped ? " equipped" : "");
  card.dataset.itemId = item.id;

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

  card.append(thumb, info, actionButton(item));
  return card;
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

// After buying, wear it straight away -- that's what a kid wants.
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
