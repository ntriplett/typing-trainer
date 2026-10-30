// Wanderpaw (PLAN.md 11n): walk the small map by typing the word on a hex
// next to you. You see your hex and the six touching it; what you've seen
// stays on the map (dimmed). An exit hex (signpost) shows the land past
// the edge: type its word to cross into the next big hex. The campfire's
// smoke shows from anywhere. A trip has energy (steps for now); out of
// energy you nap and wake at the nearest campfire you've found. The server
// keeps the fog (GET /api/wander only returns what you've seen).

const REGION_NAMES = {
  camp: "Heartland", ember: "Ember", splash: "Splash", leaf: "Leaf", dream: "Dream", shock: "Shock",
};
const WALKABLE = new Set(["grass", "flowers", "path", "sand", "plaza", "bridge", "ford", "building", "campfire", "camp", "temple", "stone"]);

const localCanvas = document.getElementById("wander-local");
const bigCanvas = document.getElementById("wander-map");
const message = document.getElementById("wander-message");
const help = document.getElementById("help");
const typer = new Typer();
let state = null;
let targets = [];
let busy = false;

const words = (name) => name.replace(/_/g, " ");
const same = (a, b) => a[0] === b[0] && a[1] === b[1];

function say(text, good = false) {
  message.textContent = text || "";
  message.classList.toggle("good", good);
}

function onCampfire() {
  return same(state.local.spot, state.local.campfire);
}

// The places you can step to: walkable hexes touching you, and the land
// past an exit you're standing on.
function steps() {
  const [q, r] = state.local.spot;
  const near = new Set(WanderMap.DIRS.map(([dq, dr]) => WanderMap.key(q + dq, r + dr)));
  const out = state.local.tiles
    .filter((t) => near.has(WanderMap.key(t.q, t.r)) && WALKABLE.has(t.kind))
    .map((t) => [t.q, t.r]);
  return out.concat(state.local.ghosts.map((g) => [g.q, g.r]));
}

// One word per step, each starting with a different letter.
function pickTargets() {
  if (!state.trip) {
    targets = [];
    return;
  }
  const used = new Set();
  const pool = [...state.words].sort(() => Math.random() - 0.5);
  targets = steps().map((hex) => {
    const word = pool.find((w) => !used.has(w[0])) || pool[0];
    used.add(word[0]);
    pool.splice(pool.indexOf(word), 1);
    return { word, typed: 0, hex };
  });
}

function render() {
  const labels = {};
  targets.forEach((t) => {
    labels[WanderMap.key(...t.hex)] = { word: t.word, typed: typer.target === t ? t.typed : 0 };
  });
  WanderMap.drawLocal(localCanvas, state.local, { size: 30, labels });
  WanderMap.draw(bigCanvas, state.big, { size: 13, trail: true });

  const here = state.local;
  const chip = document.getElementById("where-chip");
  chip.textContent = REGION_NAMES[here.region];
  chip.style.background = WanderMap.TYPE_COLORS[here.region];
  document.getElementById("where-name").textContent = here.name;
  document.getElementById("where-land").textContent = here.special ? "" : `(${words(here.biome)})`;
  document.getElementById("campfires").textContent =
    `Campfires found: ${state.campfires}`;

  const energy = document.getElementById("energy");
  energy.hidden = !state.trip;
  if (state.trip) {
    document.getElementById("energy-fill").style.width = `${(100 * state.trip.energy) / state.trip.max}%`;
    document.getElementById("energy-text").textContent = `${state.trip.energy}`;
  }
  renderHelp();
}

function renderHelp() {
  const lines = [];
  if (!state.trip) {
    lines.push(`<p><kbd class="keycap">Enter</kbd> set off from here</p>`);
    if (!state.at_camp) lines.push(`<p><kbd class="keycap">C</kbd> set off from Camp</p>`);
  } else {
    lines.push(`<p>Type a word to walk there.</p>`);
    if (state.local.ghosts.length) lines.push(`<p>The dotted hex is the way on to the next place.</p>`);
    if (onCampfire()) lines.push(`<p><kbd class="keycap">Enter</kbd> rest here and head home</p>`);
  }
  lines.push(`<p><kbd class="keycap">Esc</kbd> ${typer.target ? "lets go of a word" : "goes home"}</p>`);
  help.innerHTML = lines.join("");
}

function noteFor(data) {
  if (data.note === "napped") return ["All tired out! You curl up for a nap by the nearest campfire you've found.", true];
  if (data.note === "rested") return ["You rest by the campfire. Next time you can set off from here.", true];
  return ["", false];
}

function apply(data) {
  state = data;
  typer.release();
  pickTargets();
  render();
}

async function send(url, body) {
  busy = true;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  busy = false;
  if (!res.ok) {
    say(data.detail);
    return null;
  }
  return data;
}

async function load() {
  const res = await fetch("/api/wander");
  if (!res.ok) {
    say((await res.json()).detail || "Couldn't load the map.");
    return;
  }
  apply(await res.json());
  if (!state.trip) say(state.note ? noteFor(state)[0] : "Ready for an adventure?", true);
}

async function walk(hex) {
  const data = await send("/api/wander/walk", { q: hex[0], r: hex[1] });
  if (!data) return;
  say(...noteFor(data));
  apply(data);
}

async function startTrip(fromCamp) {
  const data = await send("/api/wander/trip/start", { from_camp: fromCamp });
  if (!data) return;
  say("Off you go!", true);
  apply(data);
}

async function endTrip() {
  const data = await send("/api/wander/trip/end");
  if (!data) return;
  say(...noteFor(data));
  apply(data);
}

document.addEventListener("keydown", (e) => {
  if (!state || busy || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "Escape" || e.key === "Backspace") {
    e.preventDefault();
    if (typer.target) {
      typer.release();
      render();
    } else if (e.key === "Escape") {
      location.href = "/";
    }
    return;
  }
  if (!state.trip) {
    if (e.key === "Enter") startTrip(false);
    else if ((e.key === "c" || e.key === "C") && !state.at_camp) startTrip(true);
    return;
  }
  if (e.key === "Enter") {
    if (onCampfire() && !typer.target) endTrip();
    return;
  }
  if (e.key.length !== 1) return;
  e.preventDefault();
  const r = typer.press(e.key.toLowerCase(), targets);
  if (r.kind === "done") walk(r.target.hex);
  else render();
});

load();
