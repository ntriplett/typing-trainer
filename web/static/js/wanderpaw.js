// Wanderpaw (PLAN.md 11n): walk by typing the word on a hex next to you.
// You stay in the middle and the world moves around you: the small maps
// join into one grid (world hexes), so you just walk on into the next big
// hex wherever the land lets you. You see your hex and the six touching
// it; what you've seen stays on the map. Gates (a dark tunnel, a gap, ...)
// get a word too: typing it uses your party's field skill, if it has one.
// The campfire's smoke shows from anywhere in its big hex.
//
// Enter goes in where you stand (a town building, a shrine, a nook, a
// temple, the Heartstone) and shows its screen; Enter again does what it
// offers, Esc leaves. At a shrine you type the line on the stone for
// energy; at a fishing spot, the line reels one in. At a campfire, Enter
// rests and ends the trip.
//
// A trip has energy (steps for now); out of energy you nap and wake at the
// nearest campfire you've found. The server keeps the fog (GET /api/wander
// only returns what you've seen) and all the rules, down to where you can
// step (caves and glades only from their doors).

const REGION_NAMES = {
  camp: "Heartland", ember: "Ember", splash: "Splash", leaf: "Leaf", dream: "Dream", shock: "Shock",
};

const localCanvas = document.getElementById("wander-local");
const bigCanvas = document.getElementById("wander-map");
const message = document.getElementById("wander-message");
const help = document.getElementById("help");
const screenBox = document.getElementById("screen");
const typer = new Typer();
let state = null;
let targets = [];
let busy = false;
let mode = "walk"; // walk | screen | line | credits
let typing = null; // a line to type: {action, line, at, slips, wrong}
// Where the view is centered (fractional while sliding to a new hex).
let camera = null;
let slide = null; // {from, to, start}
const SLIDE_MS = 220;

const words = (name) => name.replace(/_/g, " ");
const same = (a, b) => a[0] === b[0] && a[1] === b[1];
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);

function say(text, good = false) {
  message.textContent = text || "";
  message.classList.toggle("good", good);
}

function onCampfire() {
  return same(state.local.spot, state.local.campfire);
}

// The places you can step to (the server says): walkable hexes, gates,
// and a cave or glade if you're at its door.
function steps() {
  return state.local.steps;
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
  if (mode === "walk") {
    targets.forEach((t) => {
      labels[WanderMap.key(...t.hex)] = { word: t.word, typed: typer.target === t ? t.typed : 0 };
    });
  }
  WanderMap.drawLocal(localCanvas, state.local, { size: 28, labels, focus: state.local.spot, camera });
  WanderMap.draw(bigCanvas, state.big, { size: 22, trail: true, simple: true, focus: state.big.at, view: 3 });

  const here = state.local;
  const chip = document.getElementById("where-chip");
  chip.textContent = REGION_NAMES[here.region];
  chip.style.background = WanderMap.TYPE_COLORS[here.region];
  document.getElementById("where-name").textContent = here.name;
  document.getElementById("where-land").textContent = here.special ? "" : `(${words(here.biome)})`;
  document.getElementById("campfires").textContent = `Campfires found: ${state.campfires}`;

  const energy = document.getElementById("energy");
  energy.hidden = !state.trip;
  if (state.trip) {
    document.getElementById("energy-fill").style.width = `${(100 * state.trip.energy) / state.trip.max}%`;
    document.getElementById("energy-text").textContent = `${state.trip.energy}`;
  }
  renderHelp();
  renderBag();
  renderScreen();
}

function renderHelp() {
  const lines = [];
  if (!state.trip) {
    lines.push(`<p><kbd class="keycap">Enter</kbd> set off from here</p>`);
    if (!state.at_camp) lines.push(`<p><kbd class="keycap">C</kbd> set off from Camp</p>`);
  } else if (mode === "walk") {
    lines.push(`<p>Type a word to walk there.</p>`);
    if (state.screen) lines.push(`<p><kbd class="keycap">Enter</kbd> go in</p>`);
    else if (onCampfire()) lines.push(`<p><kbd class="keycap">Enter</kbd> rest here and head home</p>`);
  }
  if (mode === "walk") lines.push(`<p><kbd class="keycap">Esc</kbd> ${typer.target ? "lets go of a word" : "goes home"}</p>`);
  help.innerHTML = lines.join("");
  help.hidden = !lines.length;
}

function renderBag() {
  const items = Object.entries(state.items);
  document.getElementById("bag").innerHTML = items.length
    ? `<ul>${items.map(([k, v]) => `<li>${esc(k)}${v > 1 ? ` x${v}` : ""}</li>`).join("")}</ul>`
    : `<p class="hint">Empty.</p>`;
  const quests = state.quests.map((q) => {
    const where = q.state === "done" ? "done!" : q.found ? `bring it to ${esc(q.town)}` : `look in ${esc(q.lost_at)}`;
    return `<li>${esc(q.elder)}'s ${esc(q.lost)}: ${where}</li>`;
  });
  document.getElementById("story").innerHTML = `
    <p>Relics: ${state.temples.length} of 5${state.charms ? `, charms: ${state.charms}` : ""}</p>
    ${quests.length ? `<ul>${quests.join("")}</ul>` : `<p class="hint">Visit a town and talk to its elder.</p>`}`;
  document.getElementById("party").innerHTML = Object.entries(state.levels)
    .map(([t, n]) => `<span class="type-chip" style="background:${WanderMap.TYPE_COLORS[t]}">${REGION_NAMES[t]} ${n}</span>`)
    .join(" ");
}

function renderScreen() {
  screenBox.hidden = mode === "walk";
  if (mode === "walk") return;
  const title = document.getElementById("screen-title");
  const text = document.getElementById("screen-text");
  const line = document.getElementById("screen-line");
  const keys = document.getElementById("screen-keys");
  line.hidden = mode !== "line";
  screenBox.classList.toggle("wander-credits", mode === "credits");
  if (mode === "credits") {
    title.textContent = "The End";
    text.innerHTML = state.credits.map((l) => esc(l) || "&nbsp;").join("<br>");
    keys.innerHTML = `<kbd class="keycap">Enter</kbd> back to the map`;
    return;
  }
  const s = state.screen;
  if (!s) {
    mode = "walk";
    screenBox.hidden = true;
    return;
  }
  title.textContent = s.title;
  text.textContent = s.text;
  if (mode === "line") {
    const chars = [...typing.line];
    line.innerHTML = chars
      .map((ch, i) => {
        const cls = i < typing.at ? "done" : i === typing.at ? (typing.wrong ? "wrong" : "next") : "";
        return `<span class="${cls}">${ch === " " ? "&nbsp;" : esc(ch)}</span>`;
      })
      .join("");
    keys.innerHTML = `Type the line. <kbd class="keycap">Esc</kbd> stop`;
    return;
  }
  keys.innerHTML = s.action
    ? `<kbd class="keycap">Enter</kbd> ${esc(s.label)} &nbsp; <kbd class="keycap">Esc</kbd> leave`
    : `<kbd class="keycap">Enter</kbd> leave`;
}

function noteFor(data) {
  const texts = (data.events || []).filter((e) => e.text).map((e) => e.text);
  if (data.note === "napped" && (data.events || []).some((e) => e.kind === "nap")) {
    texts.push("All tired out! You curl up for a nap by the nearest campfire you've found.");
  }
  if (data.note === "rested" && !data.trip) texts.push("You rest by the campfire. Next time you can set off from here.");
  if (data.note === "new_day") texts.push("A new day! You're full of energy.");
  return texts.join(" ");
}

// Glide the view from where it was to your new hex, so the land slides by.
function slideTo(spot) {
  const from = camera || spot;
  camera = from;
  if (from[0] === spot[0] && from[1] === spot[1]) return;
  if (Math.abs(from[0] - spot[0]) + Math.abs(from[1] - spot[1]) > 4) {
    camera = spot; // a nap or a long jump: no slide
    return;
  }
  slide = { from, to: spot, start: performance.now() };
  requestAnimationFrame(tick);
}

function tick(now) {
  if (!slide) return;
  const t = Math.min(1, (now - slide.start) / SLIDE_MS);
  const ease = 1 - (1 - t) * (1 - t);
  camera = slide.from.map((v, i) => v + (slide.to[i] - v) * ease);
  if (t === 1) {
    camera = slide.to;
    slide = null;
  } else {
    requestAnimationFrame(tick);
  }
  render();
}

function apply(data) {
  state = data;
  slideTo(data.local.spot);
  typer.release();
  pickTargets();
  if (data.credits) mode = "credits";
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
  say(noteFor(data), true);
  const coins = (data.events || []).filter((e) => e.kind === "coins");
  if (coins.length && window.Header) Header.celebrate(coins.map((e) => ({ amount: e.amount, reason: "game" })), data.coin_balance);
  return data;
}

async function load() {
  const res = await fetch("/api/wander");
  if (!res.ok) {
    say((await res.json()).detail || "Couldn't load the map.");
    return;
  }
  apply(await res.json());
  if (!state.trip) say(noteFor(state) || "Ready for an adventure?", true);
}

async function walk(hex) {
  const data = await send("/api/wander/walk", { q: hex[0], r: hex[1] });
  if (data) apply(data);
}

async function startTrip(fromCamp) {
  const data = await send("/api/wander/trip/start", { from_camp: fromCamp });
  if (!data) return;
  say("Off you go!", true);
  apply(data);
}

async function endTrip() {
  const data = await send("/api/wander/trip/end");
  if (data) apply(data);
}

async function nextDay() {
  const data = await send("/api/wander/day");
  if (data) apply(data);
}

document.getElementById("next-day").addEventListener("click", (e) => {
  e.currentTarget.blur(); // keep Enter for the map
  if (!busy) nextDay();
});

async function act(action, accuracy = 1) {
  const data = await send("/api/wander/act", { action, accuracy });
  if (data) apply(data);
}

function walkKey(e) {
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
    if (typer.target) return;
    if (state.screen) {
      mode = "screen";
      say("");
      render();
    } else if (onCampfire()) {
      endTrip();
    }
    return;
  }
  if (e.key.length !== 1) return;
  e.preventDefault();
  const r = typer.press(e.key.toLowerCase(), targets);
  if (r.kind === "done") walk(r.target.hex);
  else render();
}

function screenKey(e) {
  if (e.key === "Escape") {
    mode = "walk";
    render();
    return;
  }
  if (e.key !== "Enter") return;
  const s = state.screen;
  if (mode === "credits" || !s || !s.action) {
    mode = "walk";
    render();
  } else if (s.line) {
    typing = { action: s.action, line: s.line, at: 0, slips: 0, wrong: false };
    mode = "line";
    render();
  } else {
    act(s.action);
  }
}

function lineKey(e) {
  if (e.key === "Escape") {
    mode = "screen";
    render();
    return;
  }
  if (e.key.length !== 1) return;
  e.preventDefault();
  if (e.key === typing.line[typing.at]) {
    typing.at += 1;
    typing.wrong = false;
  } else {
    typing.slips += 1;
    typing.wrong = true;
  }
  if (typing.at === typing.line.length) {
    const accuracy = typing.line.length / (typing.line.length + typing.slips);
    mode = "screen";
    act(typing.action, accuracy);
    return;
  }
  render();
}

document.addEventListener("keydown", (e) => {
  if (!state || busy || e.ctrlKey || e.metaKey || e.altKey) return;
  if (mode === "walk") walkKey(e);
  else if (mode === "line") lineKey(e);
  else screenKey(e);
});

load();
