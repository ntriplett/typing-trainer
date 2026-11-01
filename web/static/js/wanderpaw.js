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
// rests there a while: a new day can then start there (the day itself only
// ends when you run out of energy or go home and end it). The keys you can use right now sit in the map's
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
let mode = "walk"; // walk | screen | line | menu | battle | credits (the picker shows between trips)
let fight = null; // this round: {round, picks, able, targets}
// A round playing back, step by step: {steps, i, cur: what the bars show}.
let replay = null;
const STEP_MS = 1600;
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
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);

function say(text, good = false) {
  message.textContent = text || "";
  message.classList.toggle("good", good);
  message.classList.remove("pop");
  void message.offsetWidth; // restart the pop
  if (text) message.classList.add("pop");
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
  WanderMap.draw(bigCanvas, state.big, { size: 44, trail: true, simple: true, focus: state.big.at, view: 1.2 });

  const here = state.local;
  const chip = document.getElementById("where-chip");
  chip.textContent = REGION_NAMES[here.region];
  chip.style.background = WanderMap.TYPE_COLORS[here.region];
  document.getElementById("where-name").textContent = here.name;
  document.getElementById("where-land").textContent = here.special ? "" : `(${words(here.biome)})`;
  document.getElementById("campfires").textContent = `Campfires rested at: ${state.campfires}`;

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
  renderBattle();
}

// --- battles -----------------------------------------------------------------------
// Each round, each fighter (with energy) picks a move by typing its word;
// slips weaken it. Then the round is sent and played out.

// The fighter picking now gets a word for each of its moves, each starting
// with a different letter (a big move's is three short words). Fighters
// pick one after the other.
function fightWords() {
  const k = fight.picks.findIndex((p) => !p);
  if (k < 0) return [];
  const used = new Set();
  const take = (size) => {
    const pool = [...(state.words[size] || state.words.short)].sort(() => Math.random() - 0.5);
    const word = pool.find((w) => !used.has(w[0])) || state.words.letter.find((w) => !used.has(w)) || pool[0];
    used.add(word[0]);
    return word;
  };
  return fight.able[k].moves
    .filter((m) => m.can !== false)
    .map((m) => {
      let word;
      if (m.size === "phrase") {
        const first = take("short");
        const rest = [...state.words.short].sort(() => Math.random() - 0.5).slice(0, 2);
        word = [first, ...rest].join(" ");
      } else {
        word = take(m.size);
      }
      return { word, typed: 0, slips: 0, move: m, fighter: k };
    });
}

function startRound() {
  const able = state.battle.fighters.filter((f) => f.energy > 0);
  fight = { round: state.battle.round, picks: able.map(() => null), able, targets: [] };
  fight.targets = fightWords();
}

const TYPE_TINT = { ember: "#f6d5cf", splash: "#d4e5f6", leaf: "#dcecd0", dream: "#e6d8f1", shock: "#f9e5c6" };

function renderBattle() {
  const box = document.getElementById("battle");
  box.hidden = mode !== "battle" || !state.battle;
  box.parentElement.classList.toggle("battling", !box.hidden); // it takes the map's place
  if (box.hidden) return;
  const b = state.battle;
  if (!fight || fight.round !== b.round) startRound();
  const bar = (e, m, cls = "") => `<span class="wander-hp ${cls}"><span style="width:${(100 * e) / m}%"></span></span>`;
  // during a replay, the bars show where everyone stands at that step
  const foeEnergy = replay ? replay.cur.foe : b.energy;
  const petEnergy = (f) => (replay ? replay.cur.pets[f.place] : f.energy);
  const petMana = (f) => (replay ? replay.cur.mana[f.place] : f.mana);
  // the creature, on the right
  paintPet(document.getElementById("battle-foe"), { genes: b.looks, growth: 10 }, 5, true); // facing your pets
  const marks = [
    ...Object.entries(b.marks || {}).map(([m, rounds]) => {
      const color = WanderMap.TYPE_COLORS[MARK_TYPE[m]];
      return `<span class="wander-mark" style="border-color:${color};color:${color}">${esc(m)} <small>(${rounds})</small></span>`;
    }),
    ...Object.entries(b.effects || {}).map(([e, rounds]) => `<span class="wander-mark effect">${esc(EFFECT_NAMES[e] || e)} <small>(${rounds})</small></span>`),
    ...(b.skip ? [`<span class="wander-mark effect">can't move <small>(${b.skip})</small></span>`] : []),
  ].join(" ");
  animateMarks();
  document.getElementById("battle-foe-info").innerHTML = `
    <b>Wild ${esc(b.species)}</b> <small>level ${b.level}</small> ${chips({ [b.kind]: "", ...(b.second ? { [b.second]: "" } : {}) })}<br>
    ${bar(foeEnergy, b.max)} <small>${foeEnergy} / ${b.max}</small>
    ${marks ? `<p>${marks}</p>` : ""}`;
  // what happened last round (during a replay: so far)
  const lines = replay
    ? replay.steps.slice(0, replay.i + 1).map((e) => e.text)
    : (state.events || []).filter((e) => e.text).map((e) => e.text);
  document.getElementById("battle-log").innerHTML = lines.length
    ? lines.map((l) => `<li>${esc(l)}</li>`).join("")
    : `<li class="hint">${esc(`A wild ${b.species} blocks the way!`)}</li>`;
  // your fighters, on the left, each with its moves under it
  const team = document.getElementById("battle-team");
  team.innerHTML = b.fighters
    .map((f, i) => {
      const k = fight.able.indexOf(f);
      const picked = k >= 0 ? fight.picks[k] : null;
      const picking = k >= 0 && k === fight.picks.findIndex((p) => !p);
      const card = (m, word) => {
        const color = m.type ? WanderMap.TYPE_COLORS[m.type] : "#8b7a5c";
        const tint = m.type ? TYPE_TINT[m.type] : "#efe6d2";
        return `<li class="wander-move ${m.can === false ? "off" : ""}" style="border-color:${color};background:${tint}">
          <b style="color:${color}">${esc(m.label)}</b>
          <span class="wander-move-word">${word ? labelHtml(word) : "&nbsp;"}</span>
          <span class="wander-move-note">${esc(m.note)}</span></li>`;
      };
      const moves = replay
        ? `<ul class="wander-moves waiting">${f.moves.map((m) => card(m, null)).join("")}</ul>` // dimmed while the round plays
        : b.over || k < 0
          ? ""
          : picked
            ? `<p class="wander-picked">Ready: <b>${esc(picked.label)}</b></p>`
            : `<ul class="wander-moves ${picking ? "" : "waiting"}">${f.moves
                .map((m) => card(m, picking && fight.targets.find((t) => t.move.id === m.id)))
                .join("")}</ul>`;
      return `<div class="wander-fighter ${petEnergy(f) ? "" : "out"}">
        <div class="wander-fighter-head">
          <canvas width="110" height="86" data-fighter="${i}" data-place="${f.place}"></canvas>
          <div><b>${esc(f.name)}</b> <small>lv ${f.level}</small> ${chips(f.types)}<br>
          ${bar(petEnergy(f), f.max)} <small>${petEnergy(f)} / ${f.max}</small><br>
          ${bar(petMana(f), f.max_mana, "mana")} <small class="wander-mana">${petMana(f)} / ${f.max_mana} mana</small>
          ${f.focused ? `<span class="wander-mark">focused</span>` : ""}${f.energy ? "" : "<br><small>Worn out</small>"}</div>
        </div>
        ${moves}
      </div>`;
    })
    .join("");
  team.querySelectorAll("canvas[data-fighter]").forEach((c) => {
    const f = b.fighters[Number(c.dataset.fighter)];
    if (f.genes) paintPet(c, f);
  });
  const keys = document.getElementById("battle-keys");
  if (replay) {
    keys.innerHTML = "&nbsp;";
    return;
  }
  if (b.over) {
    keys.innerHTML = `<span class="wander-battle-over">${b.over === "won" ? "You won!" : "Your fighters are worn out."}</span>
      <kbd class="keycap">Enter</kbd> ${b.over === "won" ? "walk on" : "back away"}`;
    return;
  }
  keys.innerHTML = `Type a word to pick that move. <kbd class="keycap">Esc</kbd> run away`;
}

// A word with what's typed so far shown.
function labelHtml(t) {
  const done = esc(t.word.slice(0, t.typed));
  const rest = esc(t.word.slice(t.typed));
  return `<kbd class="wander-word"><span class="done">${done}</span>${rest}</kbd>`;
}

// --- marks on the creature, drawn and moving ---------------------------------------

const MARK_TYPE = { soaked: "splash", glowing: "ember", drowsy: "dream", tangled: "leaf", static: "shock" };
// What a combo leaves on it, as the labels say.
const EFFECT_NAMES = { drenched: "drenched", thorns: "thorns", confused: "dizzy", burn: "burning", popped: "bubble", doze: "sleepy" };
let marksTimer = null;

function animateMarks() {
  const on = mode === "battle" && state.battle && Object.keys(state.battle.marks || {}).length;
  if (on && !marksTimer) marksTimer = setInterval(drawMarks, 1000 / 20);
  if (!on && marksTimer) {
    clearInterval(marksTimer);
    marksTimer = null;
  }
  drawMarks();
}

function drawMarks() {
  const c = document.getElementById("battle-marks");
  if (!c) return;
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  const marks = (state.battle && state.battle.marks) || {};
  const t = performance.now();
  const w = c.width;
  const h = c.height;
  const seeded = (i) => (Math.sin(i * 91.7) * 43758.5) % 1;
  if (marks.soaked) {
    // drips falling round it, and a puddle
    ctx.fillStyle = "rgba(58, 127, 200, 0.85)";
    for (let i = 0; i < 9; i++) {
      const x = w * (0.2 + 0.6 * Math.abs(seeded(i)));
      const y = ((t / 9 + i * 41) % (h * 0.8)) + h * 0.1;
      ctx.fillRect(x, y, 3, 6);
    }
    ctx.fillStyle = "rgba(58, 127, 200, 0.3)";
    ctx.beginPath();
    ctx.ellipse(w / 2, h - 8, w * 0.32, 7, 0, 0, 7);
    ctx.fill();
  }
  if (marks.glowing) {
    // embers rising
    for (let i = 0; i < 16; i++) {
      const life = (t / 1400 + i / 16) % 1;
      const x = w * (0.2 + 0.6 * Math.abs(seeded(i + 3))) + Math.sin(t / 300 + i) * 8;
      const y = h * 0.9 - life * h * 0.85;
      const size = 7 - life * 4;
      ctx.fillStyle = `rgba(${i % 3 ? "232, 140, 40" : "250, 210, 80"}, ${Math.min(1, 1.3 - life)})`;
      ctx.fillRect(x - size / 2, y - size / 2, size, size);
    }
  }
  if (marks.drowsy) {
    // z's floating up
    ctx.font = 'bold 22px "Atkinson Hyperlegible Mono", monospace';
    for (let i = 0; i < 3; i++) {
      const life = ((t / 1800 + i / 3) % 1);
      ctx.fillStyle = `rgba(138, 79, 184, ${1 - life})`;
      ctx.font = `bold ${14 + life * 16}px "Atkinson Hyperlegible Mono", monospace`;
      ctx.fillText("z", w * 0.62 + life * 40, h * 0.35 - life * 50);
    }
  }
  if (marks.tangled) {
    // vines wrapped round its feet
    ctx.strokeStyle = "#4f8f2a";
    ctx.lineWidth = 4;
    for (let k = 0; k < 2; k++) {
      ctx.beginPath();
      for (let x = w * 0.18; x <= w * 0.82; x += 4) {
        const y = h * (0.78 + 0.06 * k) + Math.sin(x / 10 + t / 500 + k * 2) * 6;
        x === w * 0.18 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    ctx.fillStyle = "#77a447";
    for (let i = 0; i < 6; i++) ctx.fillRect(w * (0.2 + i * 0.11), h * 0.76 + Math.sin(t / 400 + i) * 5, 6, 4);
  }
  if (marks.static) {
    // sparks crackling round it
    ctx.strokeStyle = "#e89a2a";
    ctx.lineWidth = 3;
    const flick = Math.floor(t / 120);
    for (let i = 0; i < 4; i++) {
      if ((flick + i) % 3 === 0) continue;
      const a = seeded(flick * 7 + i) * Math.PI * 2;
      const cx = w / 2 + Math.cos(a) * w * 0.32;
      const cy = h * 0.5 + Math.sin(a) * h * 0.32;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + 8, cy + 6);
      ctx.lineTo(cx + 2, cy + 10);
      ctx.lineTo(cx + 10, cy + 18);
      ctx.stroke();
    }
  }
}

// --- playing a round back ----------------------------------------------------------
// Each step in turn: the one acting lunges at its target, a burst in the
// move's type color hits, the target shakes, the number floats up, and
// the bars move.

function startReplay(before, steps) {
  const pets = {};
  const mana = {};
  before.fighters.forEach((f) => {
    pets[f.place] = f.energy;
    mana[f.place] = f.mana;
  });
  replay = { steps, i: -1, cur: { foe: before.energy, pets, mana } };
  setTimeout(nextStep, 400);
}

function nextStep() {
  if (!replay) return;
  replay.i += 1;
  if (replay.i >= replay.steps.length) {
    replay = null;
    render();
    return;
  }
  const s = replay.steps[replay.i];
  replay.cur = { foe: s.foe, pets: s.pets, mana: s.mana };
  render();
  showStep(s);
  setTimeout(nextStep, STEP_MS);
}

function battleCanvas(who) {
  return who === "foe"
    ? document.getElementById("battle-foe")
    : document.querySelector(`#battle-team canvas[data-place="${who}"]`);
}

function retrigger(el, cls) {
  if (!el) return;
  el.classList.remove(cls);
  void el.offsetWidth; // restart the animation
  el.classList.add(cls);
}

function showStep(s) {
  const box = document.getElementById("battle");
  const actor = battleCanvas(s.who);
  const target = s.target === null || s.target === undefined ? null : battleCanvas(s.target);
  const color = s.type ? WanderMap.TYPE_COLORS[s.type] : "#e8b33e";
  if (s.act === "hit") {
    retrigger(actor, s.who === "foe" ? "lunge-left" : "lunge-right");
  } else if (actor && ["guard", "focus", "cheer", "rest"].includes(s.act)) {
    retrigger(actor, "glow-up");
  } else if (actor && ["skip", "doze"].includes(s.act)) {
    retrigger(actor, "sway");
  }
  if (s.combo) {
    // a combo: its name, big, over the creature
    const banner = document.createElement("div");
    banner.className = "wander-combo";
    banner.textContent = `${s.combo}!`;
    banner.style.setProperty("--fx", color);
    document.querySelector(".wander-battle-foe").appendChild(banner);
    setTimeout(() => banner.remove(), 1500);
  }
  if (!target) return;
  const at = target.getBoundingClientRect();
  const home = box.getBoundingClientRect();
  const x = at.left - home.left + at.width / 2;
  const y = at.top - home.top + at.height / 2;
  // a shot in the move's color, from the one acting to its target
  if (s.act === "hit" && actor) {
    const from = actor.getBoundingClientRect();
    const shot = document.createElement("div");
    shot.className = "wander-shot";
    shot.style.setProperty("--fx", color);
    shot.style.left = `${from.left - home.left + from.width / 2}px`;
    shot.style.top = `${from.top - home.top + from.height / 2}px`;
    shot.style.setProperty("--dx", `${x - (from.left - home.left + from.width / 2)}px`);
    shot.style.setProperty("--dy", `${y - (from.top - home.top + from.height / 2)}px`);
    box.appendChild(shot);
    setTimeout(() => shot.remove(), 520);
  }
  setTimeout(
    () => {
      if (s.damage && s.target !== "foe") retrigger(target.closest(".wander-fighter"), "hit-card");
      if (s.damage) {
        // a burst in the move's color, a shake, and the number
        const fx = document.createElement("div");
        fx.className = `wander-fx ${s.big || s.combo ? "big" : ""}`;
        fx.style.left = `${x}px`;
        fx.style.top = `${y}px`;
        fx.style.setProperty("--fx", color);
        box.appendChild(fx);
        setTimeout(() => fx.remove(), 900);
        retrigger(target, "shake");
      }
      const n = s.damage ? `-${s.damage}` : s.gain ? `+${s.gain}` : "";
      if (n) {
        const num = document.createElement("div");
        num.className = `wander-dmg ${s.gain ? "gain" : ""}`;
        num.textContent = n;
        num.style.left = `${x}px`;
        num.style.top = `${y - at.height / 3}px`;
        box.appendChild(num);
        setTimeout(() => num.remove(), 1300);
      }
    },
    s.act === "hit" ? 480 : 0,
  );
}

async function battleKey(e) {
  if (replay) return; // let it play
  const b = state.battle;
  if (e.key === "Escape") {
    e.preventDefault();
    if (!b.over) {
      const data = await send("/api/wander/battle/leave", { run: true });
      if (data) apply(data);
    }
    return;
  }
  if (b.over) {
    if (e.key === "Enter") {
      const data = await send("/api/wander/battle/leave", {});
      if (data) apply(data);
    }
    return;
  }
  if (e.key.length !== 1) return;
  e.preventDefault();
  const r = typer.press(e.key.toLowerCase(), fight.targets);
  if (r.kind === "done") {
    fight.picks[r.target.fighter] = { move: r.target.move.id, slips: r.target.slips || 0, label: r.target.move.label };
    fight.targets = fightWords();
    if (fight.picks.every(Boolean)) {
      const data = await send("/api/wander/battle/turn", { moves: fight.picks.map(({ move, slips }) => ({ move, slips })) });
      if (data) apply(data);
      return;
    }
  }
  render();
}

// The keys you can use right now, in the map's corner. What Enter does
// glows when it's new.
// A temple, the Heartstone or a wild creature in view: keep redrawing so it moves.
let hallTimer = null;
const HALL_FPS = 15;

function animateHalls() {
  const magic = state.local.tiles.some((t) => t.critter || (t.accent && (t.kind === "temple" || t.kind === "stone" || t.lit || t.kind.startsWith("feature_"))));
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
    if (state.screen) ready = state.screen.rest ? "Rest by the fire" : `Go in: ${state.screen.title}`;
    if (ready) lines.push(`<p class="wander-ready ${ready !== lastReady ? "fresh" : ""}"><kbd class="keycap">Enter</kbd> ${esc(ready)}</p>`);
  }
  if (ready !== lastReady) {
    lastReady = ready;
    box.innerHTML = lines.join("");
  }
  box.hidden = !lines.length;
}

// --- books and the go-home question ----------------------------------------------------

const BOOKS = ["bag", "journal", "party", "log", "map", "combos"];

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
    case "combos":
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
      size: 40, trail: true, simple: true, highlight: lit, ...around(lit.length ? lit : [state.big.at]),
    });
  } else if (menu.name === "party") {
    title.textContent = "Party";
    const m = rows[menu.at];
    body.innerHTML = `<div class="wander-menu-split">
        ${list(rows, (x, i) => `${state.fighters.includes(i) ? "⚔ " : ""}${esc(x.name)} <small>${x.id ? `lv ${x.level}` : "starter"}</small>`)}
        <div class="wander-menu-detail">
          <canvas id="party-pet" width="96" height="80"></canvas><br>
          <b>${esc(m.name)}</b> <small>(${words(m.species)}${m.id ? "" : ", a starter: doesn't level up"})</small>
          <p>${chips(m.types)}</p>
          <dl class="wander-stats-list">
            <dt>Level</dt><dd>${m.level}${m.id && m.progress ? ` <small>(${m.progress[0]} / ${m.progress[1]} xp)</small>` : m.id && m.progress === null ? " <small>(fully leveled)</small>" : ""}</dd>
            <dt>Energy</dt><dd>${state.trip && state.trip.pets ? `${state.trip.pets[menu.at]} / ${m.energy}` : m.energy}</dd>
            <dt>Power</dt><dd>${m.power}</dd>
            <dt>Speed</dt><dd>${m.speed}</dd>
            <dt>Mana</dt><dd>${m.mana}</dd>
          </dl>
          <p class="hint">Power, speed and mana matter in battles (coming soon).</p>
        </div></div>`;
    if (state.trip) keys.innerHTML = `<kbd class="keycap">&uarr;</kbd><kbd class="keycap">&darr;</kbd> look &nbsp; <kbd class="keycap">F</kbd> fight / sit out (⚔ = fights next) &nbsp; <kbd class="keycap">Esc</kbd> close`;
    const pet = m.id && pets && pets.pets.find((x) => x.id === m.id);
    if (pet) paintPet(document.getElementById("party-pet"), pet);
    else document.getElementById("party-pet").hidden = true;
  } else if (menu.name === "log") {
    title.textContent = "Log";
    body.innerHTML = rows.length ? list([...rows].reverse(), (t) => esc(t)) : `<p class="hint">Nothing has happened yet.</p>`;
    keys.innerHTML = `<kbd class="keycap">Esc</kbd> close`;
  } else if (menu.name === "combos") {
    title.textContent = "Combo book";
    const order = ["splash", "ember", "dream", "shock", "leaf"];
    const marks = ["soaked", "glowing", "drowsy", "static", "tangled"];
    const cell = (mark, hit) => state.combo_book.find((c) => c.mark === mark && c.hit === hit);
    const found = state.combo_book.filter((c) => c.name);
    body.innerHTML = `
      <p>A big move leaves a mark; the next hit of the right type sets off a combo. Found ${found.length} of ${state.combo_book.length}.</p>
      <table class="wander-combos">
        <tr><th>mark / hit</th>${order.map((t) => `<th>${chips({ [t]: "" })}</th>`).join("")}</tr>
        ${marks
          .map((m) => `<tr><th style="color:${WanderMap.TYPE_COLORS[MARK_TYPE[m]]}">${m}</th>${order
            .map((t) => {
              const c = cell(m, t);
              return `<td class="${c ? (c.name ? "found" : "") : "gap"}">${c ? (c.name ? esc(c.name) : "???") : ""}</td>`;
            })
            .join("")}</tr>`)
          .join("")}
      </table>
      ${found.length ? `<ul class="wander-combo-list">${found.map((c) => `<li><b>${esc(c.name)}</b> (${c.mark} + ${c.hit}): ${esc(c.says)}</li>`).join("")}</ul>` : ""}`;
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
  size: menu.size || 40, trail: true, names: true, shape: true, paper: true, legend: LEGEND, selected: menu.picked,
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
    const res = await fetch("/api/wander/trip/end", { method: "POST" });
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
  } else if (menu.name === "party" && (e.key === "f" || e.key === "F") && state.trip) {
    // pick who fights next: up to two
    const at = menu.at;
    let slots = state.fighters.includes(at) ? state.fighters.filter((i) => i !== at) : [...state.fighters, at];
    slots = slots.slice(-2);
    send("/api/wander/fighters", { slots }).then((data) => data && apply(data));
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

function paintPet(canvas, p, most = 3, faceLeft = false) {
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const { w, h } = petSize(p.genes, p.growth);
  const scale = Math.max(1, Math.min(most, Math.floor((canvas.width - 4) / w), Math.floor((canvas.height - 4) / h)));
  const px = (x, y, pw, ph, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x), Math.round(y), Math.ceil(pw), Math.ceil(ph));
  };
  drawPet(px, Math.round((canvas.width - w * scale) / 2), canvas.height - 3, p.genes, p.growth, { scale, shadow: false, faceLeft });
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
  // (a battle's blow-by-blow goes in its own log, not up here)
  const texts = (data.events || []).filter((e) => e.text && e.kind !== "hit").map((e) => e.text);
  if (data.note === "rested" && !data.trip) texts.push("You head home for the night. Tomorrow you'll set off from the nearest campfire you've rested at.");
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
  const before = state && state.battle;
  if (data.battle && before && data.battle.round > before.round && data.battle.log.length) {
    startReplay(before, data.battle.log);
  }
  if (data.battle) mode = "battle";
  else if (mode === "battle") mode = "walk";
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
  let res;
  let data;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    data = await res.json();
  } catch {
    say("Something went wrong. Try again?");
    return null;
  } finally {
    busy = false; // never leave the keys locked
  }
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
  else if (mode === "battle") battleKey(e);
  else if (mode === "menu") menuKey(e);
  else if (mode === "line") lineKey(e);
  else screenKey(e);
});

load();
