// The wardrobe page: change into anything you already own, slot by slot.
// (Named closet.js because wardrobe.js holds the clothing sprites.)

const SLOT_TITLES = { hat: "Hats", accessory: "Accessories", shirt: "Shirts & dresses", pants: "Pants & skirts", shoes: "Shoes" };
const OPTIONAL = ["hat", "accessory"]; // can be left empty; the rest fall back to a starter

const preview = document.getElementById("wardrobe-avatar");
const slotsEl = document.getElementById("wardrobe-slots");
const messageEl = document.getElementById("wardrobe-message");
let state = null;

async function load() {
  const r = await fetch("/api/wardrobe");
  if (!r.ok) throw new Error(`/api/wardrobe returned ${r.status}`);
  state = await r.json();
  render();
}

function render() {
  drawAvatar(preview, state.avatar);
  slotsEl.replaceChildren(
    ...Object.entries(SLOT_TITLES).map(([slot, title]) => {
      const section = document.createElement("div");
      section.className = "wardrobe-slot";
      const h = document.createElement("h2");
      h.className = "panel-title";
      h.textContent = title;
      const row = document.createElement("div");
      row.className = "choice-row";
      const items = state.slots[slot];
      if (OPTIONAL.includes(slot)) row.appendChild(option(slot, null, "Nothing"));
      items.forEach((i) => row.appendChild(option(slot, i.id, i.name)));
      if (!items.length) {
        const none = document.createElement("p");
        none.className = "hint";
        none.textContent = "Nothing here yet.";
        row.appendChild(none);
      }
      section.append(h, row);
      return section;
    })
  );
}

function option(slot, itemId, name) {
  const btn = document.createElement("button");
  const worn = (state.avatar[slot] || null) === itemId;
  btn.className = "choice wardrobe-choice" + (worn ? " selected" : "");
  btn.dataset.itemId = itemId || "";
  btn.title = name;
  const c = makeAvatarCanvas(96);
  const look = { ...state.avatar, [slot]: itemId };
  if (!itemId) delete look[slot];
  drawAvatar(c, look);
  const label = document.createElement("span");
  label.textContent = name;
  btn.append(c, label);
  btn.onclick = () => wear(slot, itemId);
  return btn;
}

async function wear(slot, itemId) {
  messageEl.textContent = "";
  const url = itemId ? `/api/store/equip/${itemId}` : `/api/store/unequip/${slot}`;
  const r = await fetch(url, { method: "POST" });
  const data = await r.json();
  if (!r.ok) {
    messageEl.textContent = data.detail || "That didn't work.";
    return;
  }
  Header.update(data);
  state.avatar = data.avatar;
  render();
}

load().catch((err) => {
  console.error(err);
  messageEl.textContent = `Couldn't load your wardrobe (${err.message}).`;
});
