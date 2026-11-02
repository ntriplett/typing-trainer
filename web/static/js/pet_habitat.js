// One habitat, full size (PLAN.md 11i): its look from habitats.js and the
// pets living there, moving by their personality (pet_motion.js).
// Playing (PLAN.md 11l): click a treat or toy on the shelf, then type one of
// three words in the scene to throw it there; pets that like it run over
// and get happy (hearts). Treats get eaten; toys come back to the shelf.

const $ = (id) => document.getElementById(id);
const SCENE_PX = 6; // the 160x90 grid on a 960x540 canvas
const PET_SCALE = 2 / 3; // 4 screen pixels per pet pixel
const TICK_MS = 120;

const THROW_SPOTS = [0.2, 0.5, 0.8]; // across the scene, left to right
const TOY_STAYS = 70; // ticks a toy lies there being played with

let habitat = null; // /api/trail/{spot}
let world = null;
let background = null;
let shelf = [];
let words = [];
let aiming = null; // {item, choices: [{word, x, y}], typed}
let thrown = null; // {item, from, to, t, landed, stay}
let spot = 0;

function painter(ctx) {
  return habitatPainter(ctx, SCENE_PX);
}

function step() {
  PetMotion.step(world);
  if (thrown) flyStep();
  const ctx = $("habitat-canvas").getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(background, 0, 0);
  if (thrown && thrown.landed) drawThrown(ctx); // on the ground: behind the pets
  PetMotion.draw(world, painter(ctx), { ctx, unit: SCENE_PX, tags: true });
  if (thrown && !thrown.landed) drawThrown(ctx); // in the air: in front
}

// --- throwing treats and toys ----------------------------------------------------------

function renderShelf() {
  const box = $("shelf");
  $("play-hint").textContent = shelf.length ? "Click one, then type a word to send it there! Treats and toys get thrown; gifts float down gently." : "";
  if (!shelf.length) {
    box.innerHTML = `<p>No treats or toys yet. Find them upstairs in the <a href="/pets/shop?dept=supplies">Pet Shop</a>!</p>`;
    return;
  }
  box.replaceChildren(
    ...shelf.map((item) => {
      const b = document.createElement("button");
      b.className = "shelf-item" + (aiming && aiming.item.id === item.id ? " current" : "");
      b.dataset.item = item.id;
      b.disabled = Boolean(thrown);
      const c = document.createElement("canvas");
      c.width = 48;
      c.height = 48;
      supplyCanvas(c, (r) => drawSupply(r, item.id));
      const fans = habitat.pets.filter((p) => item.likes.includes(p.species)).length;
      b.title = item.gift ? (fans ? "Someone here would love this" : "This is for someone who isn't here") : fans ? `${fans} of your pets here love it` : "Nobody here likes this one";
      b.append(c, Object.assign(document.createElement("span"), { textContent: item.kind === "toy" ? item.name : `${item.name} ×${item.have}` }));
      b.onclick = () => aim(item);
      return b;
    })
  );
}

function pickWords() {
  const pool = [...words];
  const out = [];
  while (out.length < THROW_SPOTS.length && pool.length) {
    const w = pool.splice(Math.floor(Math.random() * pool.length), 1)[0];
    if (!out.some((o) => o[0] === w[0])) out.push(w); // different first letters: no mix-ups
  }
  while (out.length < THROW_SPOTS.length) out.push(["go", "toss", "fetch"][out.length]);
  return out;
}

function aim(item) {
  if (thrown) return;
  const look = HABITAT_LOOKS[habitat.kind];
  const y = (look.groundTop + look.groundBottom) / 2 + 4;
  aiming = { item, typed: "", choices: pickWords().map((word, i) => ({ word, x: HABITAT_W * THROW_SPOTS[i], y })) };
  renderShelf();
  renderWords();
}

function renderWords() {
  const box = $("throw-words");
  if (!aiming) {
    box.replaceChildren();
    return;
  }
  box.replaceChildren(
    ...aiming.choices.map((c) => {
      const el = document.createElement("span");
      el.className = "throw-word";
      Object.assign(el.style, { left: `${(c.x / HABITAT_W) * 100}%`, top: `${(c.y / HABITAT_H) * 100}%` });
      const done = c.word.startsWith(aiming.typed) ? aiming.typed.length : 0;
      el.innerHTML = `<span class="typed">${c.word.slice(0, done)}</span>${c.word.slice(done)}`;
      el.classList.toggle("locked", done > 0);
      return el;
    })
  );
}

function onKey(e) {
  if (!aiming || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "Escape") {
    aiming = null;
    renderShelf();
    renderWords();
    return;
  }
  if (e.key === "Backspace") {
    aiming.typed = aiming.typed.slice(0, -1);
    renderWords();
    e.preventDefault();
    return;
  }
  if (e.key.length !== 1) return;
  e.preventDefault();
  const next = aiming.typed + e.key.toLowerCase();
  if (!aiming.choices.some((c) => c.word.startsWith(next))) {
    $("throw-words").classList.remove("oops");
    void $("throw-words").offsetWidth;
    $("throw-words").classList.add("oops"); // a little shake: not that letter
    return;
  }
  aiming.typed = next;
  const hit = aiming.choices.find((c) => c.word === next);
  renderWords();
  if (hit) throwAt(aiming.item, hit);
}

function throwAt(item, target) {
  aiming = null;
  renderWords();
  const from = item.gift ? [target.x, -8] : [HABITAT_W / 2, HABITAT_H + 4]; // a gift floats down
  thrown = { item, from, to: [target.x, target.y], t: 0, landed: false, stay: TOY_STAYS };
  renderShelf();
}

function flyStep() {
  if (!thrown.landed) {
    thrown.t = Math.min(1, thrown.t + (thrown.item.gift ? 0.025 : 0.05));
    if (thrown.t >= 1) land();
    return;
  }
  if (thrown.item.kind === "toy" && thrown.eaten !== undefined && --thrown.stay <= 0) thrown = null;
  if (!thrown) renderShelf();
}

async function land() {
  thrown.landed = true;
  const item = thrown.item;
  const [x, y] = thrown.to;
  try {
    const r = await fetch(`/api/trail/${spot}/play`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item: item.id }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "Couldn't throw it.");
    shelf = data.shelf;
    const fans = Object.keys(data.likers).map(Number);
    say(fans.length ? "" : item.gift ? `The ${item.name} is for someone who isn't here.` : `Nobody here likes the ${item.name}. Try another!`);
    thrown.eaten = false;
    if (!fans.length) thrown.stay = 20;
    PetMotion.attract(world, fans, x, y, () => {
      if (item.kind === "treat" && thrown) {
        thrown = null; // gobbled up!
        renderShelf();
      }
    });
    for (const p of habitat.pets) if (data.likers[p.id]) p.joy = data.likers[p.id];
    renderResidents();
    if (!fans.length && item.kind === "treat") setTimeout(() => {
      thrown = null;
      renderShelf();
    }, 1500);
  } catch (err) {
    say(err.message);
    thrown = null;
    renderShelf();
  }
}

function drawThrown(ctx) {
  const t = thrown.t;
  const x = thrown.from[0] + (thrown.to[0] - thrown.from[0]) * t;
  const y = thrown.from[1] + (thrown.to[1] - thrown.from[1]) * t - (thrown.item.gift ? 0 : Math.sin(Math.PI * t) * 30); // an arc
  const size = 6; // scene units
  const unit = (size / SUPPLY_GRID) * SCENE_PX;
  drawSupply((sx, sy, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect((x - size / 2) * SCENE_PX + sx * unit, (y - size) * SCENE_PX + sy * unit, w * unit, h * unit);
  }, thrown.item.id);
}

function say(text) {
  $("habitat-message").textContent = text || "";
}

function renderResidents() {
  const pets = habitat.pets;
  $("habitat-count").textContent = `Living here: ${pets.length} of ${habitat.capacity}`;
  const list = $("habitat-pets");
  if (!pets.length) {
    list.innerHTML = `<p>No one lives here yet. Move pets in at the <a href="/pets/care">Pet Care Center</a>!</p>`;
    return;
  }
  list.replaceChildren(
    ...pets.map((p) => {
      const a = document.createElement("a");
      a.className = "habitat-pet";
      a.href = `/pets/care?pet=${p.id}`;
      a.textContent = p.name + (p.joy ? ` ${"♥".repeat(p.joy)}` : "");
      return a;
    })
  );
}

async function load() {
  spot = Number(location.pathname.split("/").pop());
  $("habitat-back").href = $("habitat-gate").href = `/pets/trail?at=${spot}`;
  const r = await fetch(`/api/trail/${spot}`);
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || `/api/trail/${spot} returned ${r.status}`);
  Header.update(data);
  habitat = data.habitat;
  document.title = `Typing Trainer — ${habitat.name}`;
  $("habitat-name").textContent = habitat.name;
  const look = HABITAT_LOOKS[habitat.kind];
  background = habitatBackground(habitat.kind, SCENE_PX);
  const area = { left: 2, right: HABITAT_W - 2, top: look.groundTop, bottom: look.groundBottom, sky: true, props: look.props, terrain: look.terrain };
  world = PetMotion.create(habitat.pets, area, PET_SCALE);
  shelf = data.shelf || [];
  renderResidents();
  renderShelf();
  document.addEventListener("keydown", onKey);
  fetch("/api/play/words")
    .then((r) => r.json())
    .then((d) => (words = d.words || []))
    .catch(() => {});
  step();
}

load()
  .then(() => setInterval(step, TICK_MS))
  .catch((err) => {
    console.error(err);
    $("habitat-message").textContent = `${err.message} Head back to the Trailhead.`;
  });
