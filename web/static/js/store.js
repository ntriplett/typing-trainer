// The store page: shelves of items grouped by slot, each shown on the
// player's own avatar ("try it on"), with buy / wear / take-off buttons.
// All rules live server-side (app/store.py); this page just reflects
// /api/store and posts actions.

const SHELVES = [
  { slot: "hat", title: "Hats" },
  { slot: "shirt", title: "Clothes" },
  { slot: "pet", title: "Pets" },
  { slot: "background", title: "Places" },
];

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
  return item ? { ...avatar, [item.slot]: item.id } : avatar;
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
    const items = state.items.filter((i) => i.slot === shelf.slot);
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
  if (item.equipped) {
    btn.textContent = "Take off";
    btn.onclick = () => act(`/api/store/unequip/${item.slot}`);
  } else if (item.owned) {
    btn.textContent = "Wear";
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
async function act(url, boughtItem = null) {
  messageEl.textContent = "";
  let r = await fetch(url, { method: "POST" });
  if (r.ok && boughtItem) {
    r = await fetch(`/api/store/equip/${boughtItem.id}`, { method: "POST" });
  }
  const data = await r.json();
  if (!r.ok) {
    messageEl.textContent = data.detail || "Something went wrong.";
    return;
  }
  Header.setCoins(data.coins);
  Header.setAvatar(data.avatar);
  tryingOn = null;
  await load();
}

load().catch((err) => {
  console.error(err);
  messageEl.textContent = `Couldn't load the store (${err.message}). Try reloading.`;
});
