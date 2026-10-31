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
// rests and ends the trip. The keys you can use right now sit in the map's
// top-right corner (glowing when something new is ready); what just
// happened shows in the top box.
//
// Between trips you pick who's coming (up to five pets; starters fill the
// types you're missing): up/down move, Space adds or takes a pet off, S
// stars one, left/right picks a level 5 pet's second type, Enter sets off.
//
// Books (1-4, or click): the Bag (what things are for), the Journal
// (quests and clues, lit up on a big map), the Party (stats), and the Log
// (the last ten things that happened). Esc or "Go home" asks: end the day
// and go home, go home and come back to this trip, or keep playing.
//
// A trip has energy (the party's, pooled); out of energy you nap and wake at the
// nearest campfire you've found. The server keeps the fog (GET /api/wander
// only returns what you've seen) and all the rules, down to where you can
// step (caves and glades only from their doors).

const REGION_NAMES = {
  camp: "Heartland", ember: "Ember", splash: "Splash", leaf: "Leaf", dream: "Dream", shock: "Shock",
};

const localCanvas = document.getElementById("wander-local");
const bigCanvas = document.getElementById("wander-map");
const message = document.getElementById("wander-message");
const screenBox = document.getElementById("screen");
const typer = new Typer();
let state = null;
let targets = [];
let busy = false;
let mode = "walk"; // walk | screen | line | menu | credits (the picker shows between trips)
let menu = null; // an open book or the go-home question: {name, at}
let lastReady = null; // what Enter offered last render, so a new offer glows
let pets = null; // the picker's list (GET /api/wander/pets)
let cursor = 0;
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
  message.classList.remove("pop");
  void message.offsetWidth; // restart the pop
  if (text) message.classList.add("pop");
}

function onCampfire() {
  return same(state.local.spot, state.local.campfire);
}

// The places you can step to (the server says): walkable hexes, gates,
// and a cave or glade if you're at its door; each with how long its word
// is (a letter for paths, longer for rough ground and gates).
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
  const pools = Object.fromEntries(Object.entries(state.words).map(([k, v]) => [k, [...v].sort(() => Math.random() - 0.5)]));
  const order = ["letter", "short", "medium", "long"];
  targets = steps().map(([q, r, size]) => {
    // the right length, else the nearest length that has a fresh first letter
    const tries = [size, ...order.filter((k) => k !== size).sort((a, b) => Math.abs(order.indexOf(a) - order.indexOf(size)) - Math.abs(order.indexOf(b) - order.indexOf(size)))];
    let word = null;
    for (const k of tries) {
      word = (pools[k] || []).find((w) => !used.has(w[0]));
      if (word) break;
    }
    word = word || state.words.short[0];
    used.add(word[0]);
    return { word, typed: 0, hex: [q, r] };
  });
}

function render() {
  const labels = {};
  if (mode === "walk") {
    targets.forEach((t) => {
      labels[WanderMap.key(...t.hex)] = { word: t.word, typed: typer.target === t ? t.typed : 0 };
    });
  }
  WanderMap.drawLocal(localCanvas, state.local, { size: 28, labels, focus: state.local.spot, camera, time: performance.now() });
  animateHalls();
  WanderMap.draw(bigCanvas, state.big, { size: 44, trail: true, simple: true, straight: true, focus: state.big.at, view: 1.2 });

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
    // green: the pets'; gold: your own walking energy, used first, at the
    // end, so the bar empties from the right
    const walk = state.trip.walk ?? state.trip.energy;
    document.getElementById("energy-fill").style.width = `${(100 * walk) / state.trip.max}%`;
    document.getElementById("energy-pets").style.width = `${(100 * (state.trip.energy - walk)) / state.trip.max}%`;
    document.getElementById("energy-text").textContent = `${state.trip.energy}`;
  }
  renderKeys();
  renderScreen();
  renderPicker();
  renderMenu();
}

// The keys you can use right now, in the map's corner. What Enter does
// glows when it's new.
// A temple or the Heartstone in view: keep redrawing so its magic moves.
let hallTimer = null;
const HALL_FPS = 15;

function animateHalls() {
  const magic = state.local.tiles.some((t) => t.accent && (t.kind === "temple" || t.kind === "stone" || t.lit || t.kind.startsWith("feature_")));
  if (magic && !hallTimer) {
    hallTimer = setInterval(() => {
      if (!slide) render();
    }, 1000 / HALL_FPS);
  } else if (!magic && hallTimer) {
    clearInterval(hallTimer);
    hallTimer = null;
  }
}

function renderKeys() {
  const box = document.getElementById("keys");
  const lines = [];
  let ready = null;
  if (state.trip && mode === "walk") {
    if (state.screen) ready = `Go in: ${state.screen.title}`;
    else if (onCampfire()) ready = "Rest by the fire";
    if (ready) lines.push(`<p class="wander-ready ${ready !== lastReady ? "fresh" : ""}"><kbd class="keycap">Enter</kbd> ${esc(ready)}</p>`);
  }
  if (ready !== lastReady) {
    lastReady = ready;
    box.innerHTML = lines.join("");
  }
  box.hidden = !lines.length;
}

// --- books and the go-home question ----------------------------------------------------

const BOOKS = ["bag", "journal", "party", "log", "map"];

function openMenu(name) {
  if (mode === "line" || mode === "credits") return;
  typer.release();
  menu = { name, at: 0, picked: name === "map" ? state.big.at : null };
  mode = "menu";
  if (name === "party" && !pets) loadPets();
  render();
}

function closeMenu() {
  menu = null;
  mode = "walk";
  render();
}

function menuRows() {
  switch (menu.name) {
    case "bag":
      return Object.keys(state.items);
    case "journal":
      return [...state.quests.map((q) => ({ quest: q })), ...state.clues.map((c) => ({ clue: c }))];
    case "party":
      return state.team;
    case "log":
      return state.log;
    case "home":
      return HOME_CHOICES;
    case "map":
      return [];
    default:
      return [];
  }
}

const HOME_CHOICES = [
  { label: "Go home and end the day", go: "end" },
  { label: "Go home, and pick up this trip later", go: "leave" },
  { label: "Keep playing", go: "stay" },
];

function renderMenu() {
  const box = document.getElementById("menu");
  box.hidden = mode !== "menu" || menu.name === "map";
  renderAtlas();
  if (box.hidden) return;
  const rows = menuRows();
  menu.at = Math.max(0, Math.min(menu.at, rows.length - 1));
  const title = document.getElementById("menu-title");
  const body = document.getElementById("menu-body");
  const keys = document.getElementById("menu-keys");
  const list = (items, fn) =>
    `<ul class="wander-menu-list">${items.map((x, i) => `<li class="${i === menu.at ? "on" : ""}" data-i="${i}">${fn(x, i)}</li>`).join("")}</ul>`;
  keys.innerHTML = `<kbd class="keycap">&uarr;</kbd><kbd class="keycap">&darr;</kbd> look &nbsp; <kbd class="keycap">Esc</kbd> close`;
  if (menu.name === "bag") {
    title.textContent = "Bag";
    const item = rows[menu.at];
    body.innerHTML = rows.length
      ? `<div class="wander-menu-split">${list(rows, (k) => `${esc(k)}${state.items[k] > 1 ? ` x${state.items[k]}` : ""}`)}
          <p class="wander-menu-detail"><b>${esc(item)}</b><br>${esc(state.about[item] || "")}</p></div>`
      : `<p class="hint">Nothing yet. Things you find go here.</p>`;
  } else if (menu.name === "journal") {
    title.textContent = "Journal";
    const row = rows[menu.at];
    const lit = !row ? [] : row.quest ? row.quest.hexes : [row.clue.hex];
    body.innerHTML = `
      <p>Relics: ${state.temples.length} of 5${state.charms ? ` &nbsp; Befriending charms: ${state.charms}` : ""}</p>
      <div class="wander-menu-split">
        ${rows.length ? list(rows, (r) => (r.quest ? questLine(r.quest) : clueLine(r.clue))) : `<p class="hint">Visit a town and see who needs help.</p>`}
        <canvas id="journal-map" class="wander-map"></canvas>
      </div>`;
    WanderMap.draw(document.getElementById("journal-map"), state.big, {
      size: 40, trail: true, simple: true, straight: true, highlight: lit, ...around(lit.length ? lit : [state.big.at]),
    });
  } else if (menu.name === "party") {
    title.textContent = "Party";
    const m = rows[menu.at];
    body.innerHTML = `<div class="wander-menu-split">
        ${list(rows, (x) => `${esc(x.name)} <small>${x.id ? `lv ${x.level}` : "starter"}</small>`)}
        <div class="wander-menu-detail">
          <canvas id="party-pet" width="96" height="80"></canvas><br>
          <b>${esc(m.name)}</b> <small>(${words(m.species)}${m.id ? "" : ", a starter: doesn't level up"})</small>
          <p>${chips(m.types)}</p>
          <dl class="wander-stats-list">
            <dt>Level</dt><dd>${m.level}${m.id ? ` <small>(${m.xp % 500} / 500 xp)</small>` : ""}</dd>
            <dt>Energy</dt><dd>${state.trip && state.trip.pets ? `${state.trip.pets[menu.at]} / ${m.energy}` : m.energy}</dd>
            <dt>Power</dt><dd>${m.power}</dd>
            <dt>Speed</dt><dd>${m.speed}</dd>
            <dt>Mana</dt><dd>${m.mana}</dd>
          </dl>
          <p class="hint">Power, speed and mana matter in battles (coming soon).</p>
        </div></div>`;
    const pet = m.id && pets && pets.pets.find((x) => x.id === m.id);
    if (pet) paintPet(document.getElementById("party-pet"), pet);
    else document.getElementById("party-pet").hidden = true;
  } else if (menu.name === "log") {
    title.textContent = "Log";
    body.innerHTML = rows.length ? list([...rows].reverse(), (t) => esc(t)) : `<p class="hint">Nothing has happened yet.</p>`;
    keys.innerHTML = `<kbd class="keycap">Esc</kbd> close`;
  } else if (menu.name === "home") {
    title.textContent = "Heading home?";
    body.innerHTML = list(rows, (c, i) => `<kbd class="keycap">${i + 1}</kbd> ${esc(c.label)}`);
    keys.innerHTML = `<kbd class="keycap">Enter</kbd> choose &nbsp; <kbd class="keycap">Esc</kbd> keep playing`;
  }
  body.querySelectorAll("li[data-i]").forEach((li) => {
    li.onclick = () => {
      menu.at = Number(li.dataset.i);
      if (menu.name === "home") chooseHome(menu.at);
      else render();
    };
  });
}

// The map window: everywhere you've found, over the whole play area, with
// the land still to find in gray and a legend in the margin. Click a place
// to read about it (a little box, top right).
const atlasOpts = () => ({
  size: menu.size || 40, trail: true, straight: true, names: true, shape: true, paper: true, legend: LEGEND, selected: menu.picked,
});

function renderAtlas() {
  const box = document.getElementById("atlas");
  const open = mode === "menu" && menu.name === "map";
  box.hidden = !open;
  if (!open) return;
  const canvas = document.getElementById("world-map");
  if (!menu.size) {
    // as big as fits across the window
    WanderMap.draw(canvas, state.big, atlasOpts());
    const room = canvas.parentElement.clientWidth - 6;
    menu.size = Math.max(30, Math.min(80, Math.floor((40 * room) / canvas.width)));
  }
  const opts = atlasOpts();
  WanderMap.draw(canvas, state.big, opts);
  document.getElementById("atlas-info").innerHTML = placeInfo(menu.picked);
  if (!menu.centered) {
    // open with you in the middle of the view
    menu.centered = true;
    const scroller = canvas.parentElement;
    const [x, y] = WanderMap.pointAt(canvas, state.big, opts, ...state.big.at);
    scroller.scrollLeft = x - scroller.clientWidth / 2;
    scroller.scrollTop = y - scroller.clientHeight / 2;
  }
  canvas.onclick = (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) * canvas.width) / rect.width;
    const y = ((e.clientY - rect.top) * canvas.height) / rect.height;
    const hex = WanderMap.hexAt(canvas, state.big, opts, x, y);
    menu.picked = state.big.hexes.some((h) => h.q === hex[0] && h.r === hex[1]) ? hex : null;
    renderAtlas();
  };
}

// Focus and zoom for a big map that shows all these hexes.
function around(hexes) {
  const n = hexes.length;
  const mid = [Math.round(hexes.reduce((a, h) => a + h[0], 0) / n), Math.round(hexes.reduce((a, h) => a + h[1], 0) / n)];
  const far = Math.max(...hexes.map(([q, r]) => (Math.abs(q - mid[0]) + Math.abs(r - mid[1]) + Math.abs(q + r - mid[0] - mid[1])) / 2));
  return { focus: mid, view: far + 0.8 };
}

const LEGEND = [
  ["you", "You"], ["camp", "Camp"], ["town", "Town"], ["temple", "Temple"], ["final", "The Heartstone"],
  ["mark", "Quest or clue"], ["trail", "Trail"], ["river", "River"], ["cliff", "Cliff"], ["thicket", "Thicket"],
  ["rocks", "Rocks"], ["gate", "Gate"], ["shortcut", "Broken shortcut"],
];
const SPECIAL_NAMES = { camp: "Camp", town: "Town", temple: "Temple", final: "The Heartstone" };

// What you know about a big hex on the map.
function placeInfo(hex) {
  const h = hex && state.big.hexes.find((x) => x.q === hex[0] && x.r === hex[1]);
  if (!h) return `<p class="hint">Click a place you've found.</p>`;
  return `<b>${h.name ? esc(h.name) : "Not visited yet"}</b>
    <dl class="wander-stats-list">
      <dt>Region</dt><dd><span class="type-chip" style="background:${WanderMap.TYPE_COLORS[h.region]}">${REGION_NAMES[h.region]}</span></dd>
      <dt>Land</dt><dd>${words(h.biome)}</dd>
      ${h.special ? `<dt>Here</dt><dd>${SPECIAL_NAMES[h.special]}${h.name && h.special !== "camp" ? `: ${esc(h.name)}` : ""}</dd>` : ""}
    </dl>`;
}

const questLine = (q) => `<b>${esc(q.title)}</b>: ${q.done ? "done!" : esc(q.text)}`;
const clueLine = (c) => `Clue from ${esc(c.from)}: dig in ${esc(c.to)}${c.found ? " (dug up!)" : ""}`;

async function chooseHome(i) {
  const go = HOME_CHOICES[i].go;
  if (go === "stay") return closeMenu();
  if (go === "end" && state.trip) {
    const res = await fetch("/api/wander/trip/end", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ anywhere: true }),
    });
    if (!res.ok) return say((await res.json()).detail);
  }
  location.href = "/";
}

function askHome() {
  if (!state.trip) {
    location.href = "/";
    return;
  }
  openMenu("home");
}

function menuKey(e) {
  if (e.key === "Escape") return closeMenu();
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    menu.at += e.key === "ArrowDown" ? 1 : -1;
    render();
  } else if (menu.name === "home" && e.key === "Enter") {
    chooseHome(menu.at);
  } else if (menu.name === "home" && ["1", "2", "3"].includes(e.key)) {
    chooseHome(Number(e.key) - 1);
  } else if (BOOKS[Number(e.key) - 1] && menu.name !== "home") {
    const name = BOOKS[Number(e.key) - 1];
    if (name === menu.name) closeMenu();
    else openMenu(name);
  } else if (e.key === "Enter" && menu.name !== "home") {
    closeMenu();
  }
}

const chips = (types) =>
  Object.entries(types)
    .map(([t, n]) => `<span class="type-chip" style="background:${WanderMap.TYPE_COLORS[t]}">${REGION_NAMES[t]} ${n}</span>`)
    .join(" ");

// --- the party picker --------------------------------------------------------------

async function loadPets() {
  const res = await fetch("/api/wander/pets");
  if (res.ok) pets = await res.json();
  render();
}

function inParty(id) {
  return state.team.some((m) => m.id === id);
}

function renderPicker() {
  const box = document.getElementById("picker");
  box.hidden = !!state.trip || mode !== "walk" || !pets;
  document.getElementById("keys").hidden = !box.hidden || !state.trip;
  if (box.hidden) return;
  const list = document.getElementById("picker-pets");
  cursor = Math.max(0, Math.min(cursor, pets.pets.length - 1));
  list.innerHTML = pets.pets.length
    ? pets.pets
        .map((p, i) => {
          const pick = p.choices
            ? `<span class="wander-pick">New type! <kbd class="keycap">&larr;</kbd> ${REGION_NAMES[p.choices[0]]} &nbsp; <kbd class="keycap">&rarr;</kbd> ${REGION_NAMES[p.choices[1]]}</span>`
            : "";
          return `<li class="${i === cursor ? "on" : ""} ${inParty(p.id) ? "going" : ""}" data-i="${i}">
            <canvas width="56" height="48" data-pet="${i}"></canvas>
            <span class="wander-pet-name">${p.starred ? "★ " : ""}${esc(p.name)} <small>lv ${p.level}</small></span>
            ${chips(p.types)} <small>energy ${p.energy}</small> ${pick}
          </li>`;
        })
        .join("")
    : `<li class="hint">No pets yet. Starters will come along.</li>`;
  list.querySelectorAll("canvas[data-pet]").forEach((c) => paintPet(c, pets.pets[Number(c.dataset.pet)]));
  list.querySelectorAll("li[data-i]").forEach((li) => {
    li.onclick = () => {
      cursor = Number(li.dataset.i);
      toggle();
    };
  });
  const starters = state.team.filter((m) => !m.id).map((m) => esc(m.name));
  document.getElementById("picker-keys").innerHTML = `
    ${starters.length ? `<span class="hint">Starters coming: ${starters.join(", ")}.</span><br>` : ""}
    <kbd class="keycap">Space</kbd> add / take off &nbsp; <kbd class="keycap">S</kbd> star &nbsp;
    <kbd class="keycap">Enter</kbd> set off${state.at_camp ? "" : ` &nbsp; <kbd class="keycap">C</kbd> set off from Camp`}`;
}

function paintPet(canvas, p) {
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const { w, h } = petSize(p.genes, p.growth);
  const scale = Math.max(1, Math.min(3, Math.floor((canvas.width - 4) / w), Math.floor((canvas.height - 4) / h)));
  const px = (x, y, pw, ph, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x), Math.round(y), Math.ceil(pw), Math.ceil(ph));
  };
  drawPet(px, Math.round((canvas.width - w * scale) / 2), canvas.height - 3, p.genes, p.growth, { scale, shadow: false });
}

async function toggle() {
  const p = pets.pets[cursor];
  if (!p) return;
  const ids = state.team.filter((m) => m.id).map((m) => m.id);
  const next = inParty(p.id) ? ids.filter((id) => id !== p.id) : [...ids, p.id];
  if (next.length > 5) {
    say("Five pets is a full party.");
    return;
  }
  const data = await send("/api/wander/party", { pets: next });
  if (data) apply(data);
}

async function petAction(url, body) {
  busy = true;
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  busy = false;
  const data = await res.json();
  if (!res.ok) return say(data.detail);
  pets = data;
  await load();
}

function pickerKey(e) {
  const p = pets && pets.pets[cursor];
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    cursor += e.key === "ArrowDown" ? 1 : -1;
    render();
  } else if (e.key === " ") {
    e.preventDefault();
    toggle();
  } else if ((e.key === "s" || e.key === "S") && p) {
    petAction(`/api/wander/pets/${p.id}/star`);
  } else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && p && p.choices) {
    e.preventDefault();
    petAction(`/api/wander/pets/${p.id}/second`, { type: p.choices[e.key === "ArrowLeft" ? 0 : 1] });
  } else if (BOOKS[Number(e.key) - 1]) {
    openMenu(BOOKS[Number(e.key) - 1]);
  } else if (e.key === "Enter") {
    startTrip(false);
  } else if ((e.key === "c" || e.key === "C") && !state.at_camp) {
    startTrip(true);
  } else if (e.key === "Escape") {
    askHome();
  }
}

function renderScreen() {
  screenBox.hidden = !["screen", "line", "credits"].includes(mode);
  if (screenBox.hidden) return;
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
  if (s.options && s.options.length > 1) {
    keys.innerHTML = `${s.options.map((o, i) => `<kbd class="keycap">${i + 1}</kbd> ${esc(o.label)}`).join("<br>")}<br><kbd class="keycap">Esc</kbd> leave`;
    return;
  }
  keys.innerHTML = s.action
    ? `<kbd class="keycap">Enter</kbd> ${esc(s.label)} &nbsp; <kbd class="keycap">Esc</kbd> leave`
    : `<kbd class="keycap">Enter</kbd> leave`;
}

function noteFor(data) {
  const texts = (data.events || []).filter((e) => e.text).map((e) => e.text);
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
  if (!data.trip && (!pets || state?.trip)) loadPets(); // back between trips: levels may have changed
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
  if (!state.trip) {
    say(noteFor(state) || "Ready for an adventure?", true);
    if (!pets) loadPets();
  }
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

document.getElementById("go-home").addEventListener("click", (e) => {
  e.currentTarget.blur(); // keep Enter for the map
  if (!busy) askHome();
});
document.querySelectorAll("[data-menu]").forEach((b) => {
  b.addEventListener("click", (e) => {
    e.currentTarget.blur();
    if (state && !busy) openMenu(b.dataset.menu);
  });
});

async function act(action, accuracy = 1, arg = null) {
  const data = await send("/api/wander/act", { action, accuracy, arg });
  if (data) apply(data);
}

function walkKey(e) {
  if (e.key === "Escape" || e.key === "Backspace") {
    e.preventDefault();
    if (typer.target) {
      typer.release();
      render();
    } else if (e.key === "Escape") {
      askHome();
    }
    return;
  }
  if (BOOKS[Number(e.key) - 1] && !typer.target) {
    openMenu(BOOKS[Number(e.key) - 1]);
    return;
  }
  if (!state.trip) {
    pickerKey(e);
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
  const s = state.screen;
  // several choices: a number picks one
  const pick = s && s.options && s.options.length > 1 ? s.options[Number(e.key) - 1] : null;
  if (pick) {
    act(pick.action, 1, pick.arg);
    return;
  }
  if (e.key !== "Enter") return;
  if (mode === "credits" || !s || !s.action) {
    mode = "walk";
    render();
  } else if (s.line) {
    typing = { action: s.action, line: s.line, at: 0, slips: 0, wrong: false };
    mode = "line";
    render();
  } else if (s.options && s.options.length > 1) {
    // Enter alone does nothing when there's a choice to make
  } else {
    act(s.action, 1, s.options ? s.options[0].arg : null);
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
  else if (mode === "menu") menuKey(e);
  else if (mode === "line") lineKey(e);
  else screenKey(e);
});

load();
