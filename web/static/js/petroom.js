// The pet room: every pet you own wandering around a little yard, plus a
// card per pet to name, feed (once a day, grows it up), and choose who
// comes along on your avatar. Rules live in app/pets.py.

const STAGE_LABEL = { baby: "Baby", young: "Young", grown: "All grown up!" };

const yard = document.getElementById("pet-yard");
const cardsEl = document.getElementById("pet-cards");
const hintEl = document.getElementById("pets-hint");
const messageEl = document.getElementById("pets-message");

let state = null; // latest /api/pets response
let walkers = []; // yard animation state, one per pet

async function load() {
  const r = await fetch("/api/pets");
  if (r.status === 403) return new Promise(() => {}); // still a mystery: header.js shows why
  if (!r.ok) throw new Error(`/api/pets returned ${r.status}`);
  setState(await r.json());
}

function setState(data) {
  state = data;
  Header.update(data);
  // keep walkers for pets we already had, so the yard doesn't jump
  const old = new Map(walkers.map((w) => [w.pet.id, w]));
  walkers = data.pets.map((pet, i) => {
    const w = old.get(pet.id) || { x: 8 + ((i * 23) % 72), dir: i % 2 ? -1 : 1, lane: i % 3 };
    return { ...w, pet };
  });
  render();
}

// --- the yard: 96x48 pixel scene at 6x ---------------------------------------

const YARD_W = 96;
const YARD_H = 48;

function drawYard() {
  const ctx = yard.getContext("2d");
  const scale = yard.width / YARD_W;
  const px = (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(x * scale, y * scale, w * scale, h * scale);
  };
  px(0, 0, YARD_W, YARD_H, "#a8d5e2"); // sky
  px(0, 0, YARD_W, 5, "#c4e3ec");
  px(60, 6, 30, 18, "#b8432f"); // little barn
  px(58, 4, 34, 3, "#8e3418");
  px(70, 14, 10, 10, "#5c3a1a");
  px(74, 14, 2, 10, "#3b2417");
  px(0, 20, YARD_W, 2, "#e8d3a8"); // fence
  for (let x = 2; x < YARD_W; x += 8) px(x, 16, 2, 8, "#e8d3a8");
  px(0, 24, YARD_W, 24, "#7fa346"); // grass
  px(0, 24, YARD_W, 1, "#94c25c");
  for (const [x, y] of [[6, 30], [22, 40], [41, 33], [55, 44], [83, 37], [90, 29]]) px(x, y, 2, 1, "#5a7a2e");

  for (const w of walkers) {
    const rows = PET_ROWS[w.pet.species][w.pet.stage];
    const sprite = petSprite(w.pet, { x: Math.round(w.x), y: 30 + w.lane * 5 - rows.length + 10, faceLeft: w.dir < 0 });
    drawGrid(px, sprite, 0);
  }
}

function step() {
  for (const w of walkers) {
    const width = PET_ROWS[w.pet.species][w.pet.stage][0].length;
    w.x += w.dir * 0.5;
    if (w.x < 1 || w.x > YARD_W - width - 1) w.dir *= -1;
    if (Math.random() < 0.01) w.dir *= -1; // the occasional change of mind
  }
  drawYard();
}

// --- cards -------------------------------------------------------------------

function render() {
  drawYard();
  const along = state.pets.filter((p) => p.slot !== null).length;
  hintEl.textContent = state.pets.length
    ? `Feed each pet once a day (${state.food_price} coins) to help it grow. Up to ${state.max_along} can come along with you.`
    : "";
  if (!state.pets.length) {
    cardsEl.innerHTML = state.unlocks.free_pet
      ? `<p class="free-pet">🎁 You learned the home row! Your first pet is free.</p>
         <p><a class="button button-gold big-button" href="/store?tab=pets">Pick your pet</a></p>`
      : `<p>No pets yet! Adopt one in the <a href="/store?tab=pets">store</a> (Pets tab).</p>`;
    return;
  }
  cardsEl.replaceChildren(...state.pets.map((pet) => petCard(pet, along)));
}

function petCard(pet, alongCount) {
  const card = document.createElement("article");
  card.className = "pet-card" + (pet.slot !== null ? " along" : "");
  card.dataset.petId = pet.id;

  const portrait = makeAvatarCanvas(144);
  const rows = PET_ROWS[pet.species][pet.stage];
  const ctx = portrait.getContext("2d");
  const scale = portrait.width / 48;
  const px = (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(x * scale, y * scale, w * scale, h * scale);
  };
  px(0, 0, 48, 48, "#cfe6c4");
  px(0, 36, 48, 12, "#9cc46a");
  // scale small pets up in the portrait so babies aren't specks
  const zoom = rows.length <= 8 ? 2 : 1.5;
  const zpx = (x, y, w, h, c) => px(x * zoom, y * zoom, w * zoom, h * zoom, c);
  const w = rows[0].length;
  drawGrid(zpx, petSprite(pet, { x: Math.round((48 / zoom - w) / 2), y: Math.round(40 / zoom - rows.length), faceLeft: false }), 0);

  const growth = `<div class="growth-bar" title="${pet.growth} of ${pet.max_growth}"><div style="width:${(pet.growth / pet.max_growth) * 100}%"></div></div>`;
  const info = document.createElement("div");
  info.className = "pet-info";
  info.innerHTML = `
    <form class="pet-name-form">
      <input class="pet-name" maxlength="16" value="${pet.name.replace(/"/g, "&quot;")}" aria-label="Pet name" />
      <button type="submit" class="small-button">Rename</button>
    </form>
    <p class="pet-meta">${pet.species_name} · ${STAGE_LABEL[pet.stage]}</p>
    ${growth}`;
  info.querySelector("form").addEventListener("submit", (e) => {
    e.preventDefault();
    act(`/api/pets/${pet.id}/name`, "PUT", { name: info.querySelector(".pet-name").value });
  });

  const actions = document.createElement("div");
  actions.className = "pet-actions";
  const feed = document.createElement("button");
  if (pet.stage === "grown") {
    feed.textContent = "All grown!";
    feed.disabled = true;
  } else if (pet.fed_today) {
    feed.textContent = "Fed today ✓";
    feed.disabled = true;
  } else {
    feed.textContent = `Feed (${state.food_price})`;
    feed.className = "button-gold";
    feed.disabled = state.coins < state.food_price;
    feed.onclick = () => act(`/api/pets/${pet.id}/feed`, "POST");
  }
  actions.appendChild(feed);

  if (pet.slot !== null) {
    const home = document.createElement("button");
    home.textContent = "Stay home";
    home.onclick = () => act(`/api/pets/${pet.id}/along`, "PUT", { slot: null });
    actions.appendChild(home);
  } else {
    for (const [slot, label] of [[2, "Come along (left)"], [1, "Come along (right)"]]) {
      const btn = document.createElement("button");
      btn.textContent = label;
      btn.className = "button-go";
      btn.title = alongCount >= state.max_along ? "Swaps with the pet on that side" : "";
      btn.onclick = () => act(`/api/pets/${pet.id}/along`, "PUT", { slot });
      actions.appendChild(btn);
    }
  }

  card.append(portrait, info, actions);
  return card;
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
    return;
  }
  setState(data);
}

load()
  .then(() => setInterval(step, 120))
  .catch((err) => {
    console.error(err);
    messageEl.textContent = `Couldn't load your pets (${err.message}). Try reloading.`;
  });
