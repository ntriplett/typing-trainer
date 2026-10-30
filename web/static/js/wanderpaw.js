// Wanderpaw (PLAN.md 11n), phase 1: walk the big map by typing the word on
// a place next to you. Walls (rivers, cliffs, thickets, rocks) get no word.
// The server keeps the fog (GET /api/wander only returns what you've seen).

const REGION_NAMES = {
  camp: "Heartland", ember: "Ember", splash: "Splash", leaf: "Leaf", dream: "Dream", shock: "Shock",
};

const canvas = document.getElementById("wander-map");
const message = document.getElementById("wander-message");
const typer = new Typer();
let state = null;
let targets = [];
let busy = false;

const words = (name) => name.replace(/_/g, " ");
const at = () => state.at;

function exits() {
  const [q, r] = at();
  const known = new Set(state.hexes.map((h) => WanderMap.key(h.q, h.r)));
  return state.edges
    .filter((e) => e.kind === "open")
    .map((e) => (e.a[0] === q && e.a[1] === r ? e.b : e.b[0] === q && e.b[1] === r ? e.a : null))
    .filter((n) => n && known.has(WanderMap.key(...n)));
}

// One word per exit, each starting with a different letter.
function pickTargets() {
  const used = new Set();
  const pool = [...state.words].sort(() => Math.random() - 0.5);
  targets = exits().map((hex) => {
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
  WanderMap.draw(canvas, state, { size: 40, labels, trail: true });
  const here = state.hexes.find((h) => h.q === at()[0] && h.r === at()[1]);
  const chip = document.getElementById("where-chip");
  chip.textContent = REGION_NAMES[here.region];
  chip.style.background = WanderMap.TYPE_COLORS[here.region];
  document.getElementById("where-name").textContent = here.name;
  document.getElementById("where-land").textContent = here.special ? "" : `(${words(here.biome)})`;
}

async function load() {
  const res = await fetch("/api/wander");
  if (!res.ok) {
    message.textContent = (await res.json()).detail || "Couldn't load the map.";
    return;
  }
  state = await res.json();
  pickTargets();
  render();
}

async function walk(hex) {
  busy = true;
  const res = await fetch("/api/wander/step", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q: hex[0], r: hex[1] }),
  });
  const data = await res.json();
  busy = false;
  if (!res.ok) {
    message.textContent = data.detail;
    return;
  }
  message.textContent = "";
  state = data;
  pickTargets();
  render();
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
  if (e.key.length !== 1) return;
  e.preventDefault();
  const r = typer.press(e.key.toLowerCase(), targets);
  if (r.kind === "done") walk(r.target.hex);
  else render();
});

load();
