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
  camp: "Heartland", ember: "EMBER", splash: "SPLASH", leaf: "LEAF", dream: "DREAM", shock: "SHOCK",
};

document.getElementById("energy-label").innerHTML = `Energy ${ENERGY_ICON}`;
const localCanvas = document.getElementById("wander-local");
const bigCanvas = document.getElementById("wander-map");
const message = document.getElementById("wander-message");
const screenBox = document.getElementById("screen");
const typer = new Typer();
let state = null;
let targets = [];
let busy = false;
let mode = "walk"; // walk | screen | line | menu | battle | credits | levelup (the picker shows between trips)
let afterLevelup = "walk"; // where to go back to when the level-up pop-ups are done
let levelupShown = null; // the pop-up on screen, so it only draws (and celebrates) once
let levelPick = null; // which of its choices is being looked at
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
  message.innerHTML = wanderText(text);
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
  renderLevelup();
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
    .filter((m) => m.can !== false && !m.passive)
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
  const able = state.battle.fighters.filter((f) => f.energy > 0 && !f.asleep);
  fight = { round: state.battle.round, picks: able.map(() => null), able, targets: [] };
  fight.targets = fightWords();
}


const FOE_SIZES = { plain: { w: 220, h: 170, most: 5 }, tough: { w: 260, h: 200, most: 6 }, champion: { w: 300, h: 230, most: 7 }, boss: { w: 330, h: 260, most: 8 } };

function renderBattle() {
  const box = document.getElementById("battle");
  box.hidden = mode !== "battle" || !state.battle;
  box.parentElement.classList.toggle("battling", !box.hidden); // it takes the map's place
  if (box.hidden) return;
  const b = state.battle;
  if (!fight || fight.round !== b.round) startRound();
  // during a replay, the bars show where everyone stands at that step
  const foeEnergy = replay ? replay.cur.foe : b.energy;
  const petEnergy = (f) => (replay ? replay.cur.pets[f.place] : f.energy);
  const petMana = (f) => (replay ? replay.cur.mana[f.place] : f.mana);
  // the creature, on the right
  // a tougher creature is drawn bigger, with an outline in its tier's color
  const size = FOE_SIZES[b.tier] || FOE_SIZES.plain;
  const art = document.getElementById("battle-foe");
  [art, document.getElementById("battle-marks")].forEach((c) => {
    if (c.width !== size.w) c.width = size.w;
    if (c.height !== size.h) c.height = size.h;
    c.style.width = `${size.w}px`;
    c.style.height = `${size.h}px`;
  });
  art.closest(".wander-foe-art").dataset.tier = b.tier || "";
  paintPet(art, { genes: b.looks, growth: 10 }, size.most, true); // facing your pets
  const marks = [
    ...Object.entries(b.marks || {}).map(([m, rounds]) => {
      const color = WanderMap.TYPE_COLORS[MARK_TYPE[m]];
      return `<span class="wander-mark" style="border-color:${color};color:${color}">${esc(m)} <small>(${rounds})</small></span>`;
    }),
    ...Object.entries(b.effects || {}).map(([e, rounds]) => `<span class="wander-mark effect">${esc(EFFECT_NAMES[e] || e)} <small>(${rounds})</small></span>`),
    ...(b.skip ? [`<span class="wander-mark effect">can't move <small>(${b.skip})</small></span>`] : []),
  ].join(" ");
  animateMarks();
  const intent = document.getElementById("battle-intent");
  intent.hidden = !b.intent || !!replay || !!b.over;
  intent.innerHTML = b.intent ? intentHtml(b.intent) : "";
  intent.title = b.intent ? wanderPlain(b.intent.tip) : "";
  document.getElementById("battle-bench").innerHTML = (b.bench_helps || []).length
    ? `<small>Helping from the bench:</small> ${b.bench_helps.map((c) => `<span class="wander-mark" title="${wanderPlain(c.says)}">${esc(c.name)}</span>`).join(" ")}`
    : "";
  document.getElementById("battle-foe-info").innerHTML = `
    <b>${b.tier ? `${b.tier[0].toUpperCase()}${b.tier.slice(1)}` : "Wild"} ${esc(b.species)}</b> <small>level ${b.level}</small> ${chips({ [b.kind]: "", ...(b.second ? { [b.second]: "" } : {}) })}<br>
    ${bar(foeEnergy, b.max)} <small>${foeEnergy} / ${b.max}</small>
    ${marks ? `<p>${marks}</p>` : ""}`;
  // what happened last round (during a replay: so far)
  const lines = replay
    ? replay.steps.slice(0, replay.i + 1).map((e) => e.text)
    : (state.events || []).filter((e) => e.text).map((e) => e.text);
  document.getElementById("battle-log").innerHTML = lines.length
    ? lines.map((l) => `<li>${wanderText(l)}</li>`).join("")
    : `<li class="hint">${esc(`A wild ${b.species} blocks the way!`)}</li>`;
  // your fighters, on the left, each with its moves under it
  const team = document.getElementById("battle-team");
  team.innerHTML = b.fighters
    .map((f, i) => {
      const k = fight.able.indexOf(f);
      const picked = k >= 0 ? fight.picks[k] : null;
      const picking = k >= 0 && k === fight.picks.findIndex((p) => !p);
      const moves = replay
        ? `<ul class="wander-moves waiting ${gridSize(f.moves)}">${f.moves.map((m) => moveCard(m, null)).join("")}</ul>` // dimmed while the round plays
        : b.over || k < 0
          ? ""
          : picked
            ? `<p class="wander-picked">Ready: <b>${wanderText(picked.label)}</b></p>`
            : `<ul class="wander-moves ${picking ? "" : "waiting"} ${gridSize(f.moves)}">${f.moves
                .map((m) => moveCard(m, (picking && fight.targets.find((t) => t.move.id === m.id)) || null))
                .join("")}</ul>`;
      return `<div class="wander-fighter ${petEnergy(f) ? "" : "out"}">
        <div class="wander-fighter-head">
          <canvas width="110" height="86" data-fighter="${i}" data-place="${f.place}"></canvas>
          <div><b>${esc(f.name)}</b> <small>lv ${f.level}</small> ${chips(f.types)}<br>
          ${bar(petEnergy(f), f.max)} <small title="Energy">${petEnergy(f)} / ${f.max} ${ENERGY_ICON}</small><br>
          ${bar(petMana(f), f.max_mana, "mana")} <small class="wander-mana" title="Mana">${petMana(f)} / ${f.max_mana} ${MANA_ICON}</small>
          ${f.ward ? `<span class="wander-mark" title="Used up first, and gone when the battle ends">ward +${f.ward}</span>` : ""}${f.focused ? `<span class="wander-mark">focused</span>` : ""}${f.asleep ? `<span class="wander-mark">asleep</span>` : ""}${f.marked ? `<span class="wander-mark">marked</span>` : ""}${f.energy ? "" : "<br><small>Worn out</small>"}</div>
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
      <kbd class="keycap">Enter</kbd> ${b.over === "won" ? "walk on" : "back away"}
      ${b.befriend ? (b.befriend.can ? `&nbsp; <kbd class="keycap">B</kbd> Befriend it (a Friendship Token, and ${b.befriend.cost} ${MANA_ICON} from each fighter)` : `&nbsp; <small>Befriending it takes ${b.befriend.cost} ${MANA_ICON} from each fighter.</small>`) : ""}`;
    return;
  }
  keys.innerHTML = `Type a word to pick that move. <kbd class="keycap">Esc</kbd> run away`;
}

// --- marks on the creature, drawn and moving ---------------------------------------

const MARK_TYPE = { soaked: "splash", glowing: "ember", drowsy: "dream", tangled: "leaf", static: "shock" };
// What a combo leaves on it, as the labels say.
const EFFECT_NAMES = { drenched: "drenched", thorns: "thorns", confused: "dizzy", burn: "burning", popped: "bubble", doze: "sleepy",
  hardened: "braced", mending: "pets mending", brambles: "brambles", scalded: "scalded", wisp: "wisp", wired: "wired", poppies: "poppies", sanctuary: "sanctuary" };
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
  } else if (actor && ["guard", "focus", "cheer", "rest", "mark", "heal", "mix"].includes(s.act)) {
    retrigger(actor, "glow-up");
  } else if (actor && ["skip", "doze"].includes(s.act)) {
    retrigger(actor, "sway");
  }
  if (s.flash) {
    // a passive move at work: its card lights up
    const card = battleCanvas(s.flash[0])?.closest(".wander-fighter")?.querySelector(`[data-move="${s.flash[1]}"]`);
    if (card) {
      card.style.setProperty("--fx", color);
      retrigger(card, "flash");
    }
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
      if (s.act === "heal") {
        // sparkles rising in the healer's color
        for (let i = 0; i < 10; i++) {
          const spark = document.createElement("div");
          spark.className = "wander-heal-spark";
          spark.style.left = `${x + (i - 5) * 9}px`;
          spark.style.top = `${y + (i % 3) * 8}px`;
          spark.style.setProperty("--fx", color);
          spark.style.animationDelay = `${(i % 4) * 90}ms`;
          box.appendChild(spark);
          setTimeout(() => spark.remove(), 1300);
        }
      }
      const n = s.act === "blocked" ? "Blocked!" : s.damage ? `-${s.damage}` : s.gain ? `+${s.gain}` : "";
      if (n) {
        const num = document.createElement("div");
        num.className = `wander-dmg ${s.gain || s.act === "blocked" ? "gain" : ""}`;
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
  if (e.key === "1" || e.key === "2") return openMenu(e.key === "1" ? "bag" : "guide");
  if (b.over && b.befriend && b.befriend.can && (e.key === "b" || e.key === "B")) {
    const data = await send("/api/wander/befriend", {});
    if (data) apply(data);
    return;
  }
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
    if (ready) lines.push(`<p class="wander-ready ${ready !== lastReady ? "fresh" : ""}"><kbd class="keycap">Enter</kbd> ${wanderText(ready)}</p>`);
  }
  if (ready !== lastReady) {
    lastReady = ready;
    box.innerHTML = lines.join("");
  }
  box.hidden = !lines.length;
}

// --- books and the go-home question ----------------------------------------------------

const BOOKS = ["bag", "journal", "party", "log", "map", "guide"];

function openMenu(name) {
  if (mode === "line" || mode === "credits") return;
  typer.release();
  const from = mode === "menu" ? menu.from : mode;
  menu = { name, at: 0, picked: name === "map" ? state.big.at : null, from, page: 0, me: guideSides.me, enemy: guideSides.enemy, picking: null };
  mode = "menu";
  if (name === "guide") loadGuide();
  if (name === "party" && !pets) loadPets();
  render();
}

function closeMenu() {
  const from = menu && menu.from;
  menu = null;
  mode = state.battle ? "battle" : from === "screen" ? "screen" : "walk";
  render();
}

// The guidebook's fixed pages, once, and which match-up it was left on.
let guideData = null;
const guideSides = { me: "splash", enemy: "ember" };
async function loadGuide() {
  if (guideData) return;
  const res = await fetch("/api/wander/guide");
  if (res.ok) guideData = await res.json();
  render();
}

function bagRows() {
  const uses = state.item_uses || {};
  if (menu.picking) return uses[menu.picking].choices;
  const all = Object.keys(state.items);
  return state.battle ? all.filter((k) => uses[k] && !uses[k].why) : all;
}

async function useItem(name, arg = null) {
  const uses = (state.item_uses || {})[name];
  if (!uses) return say("You can't use that.");
  if (uses.why) return say(uses.why);
  if (uses.when === "pick" && !arg) {
    menu.picking = name;
    menu.at = 0;
    return render();
  }
  const data = await send("/api/wander/use", { item: name, arg });
  if (!data) return;
  fight = null; // mana may have changed what they can pick
  menu = null;
  mode = data.battle ? "battle" : "walk";
  apply(data);
}

async function buyItem(name) {
  const data = await send("/api/wander/shop/buy", { item: name });
  if (data) apply(data);
}

function menuRows() {
  switch (menu.name) {
    case "bag":
      return bagRows();
    case "shop":
      return (state.screen && state.screen.stock) || [];
    case "journal":
      return [...state.quests.map((q) => ({ quest: q })), ...state.clues.map((c) => ({ clue: c }))];
    case "log":
      return state.log;
    case "home":
      return HOME_CHOICES;
    case "map":
    case "guide":
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

// Bars and move cards: the battle screen's, and the party book's.
const bar = (e, m, cls = "") => `<span class="wander-hp ${cls}"><span style="width:${(100 * e) / m}%"></span></span>`;

// --- the party book: everyone together, then each pet up close ---------------------

const PARTY_SCENE_PX = 6; // the 160x90 habitat grid on a 960x540 canvas
const PARTY_PET_SCALE = 2 / 3;
const PARTY_TICK_MS = 120;
// The scene for where you are, by biome. Just grass so far; new ones go here.
const PARTY_SCENES = {};
let partyScene = null; // {key, world, background, timer}

function partySceneStart() {
  const kind = PARTY_SCENES[state.local.biome] || "meadow";
  const key = `${kind}:${state.team.map((m) => m.name).join()}`;
  if (!partyScene || partyScene.key !== key) {
    if (partyScene) clearInterval(partyScene.timer);
    const look = HABITAT_LOOKS[kind];
    const area = { left: 2, right: HABITAT_W - 2, top: look.groundTop, bottom: look.groundBottom, props: look.props, terrain: look.terrain };
    partyScene = { key, world: PetMotion.create(state.team.filter((m) => m.genes), area, PARTY_PET_SCALE), background: habitatBackground(kind, PARTY_SCENE_PX), timer: null };
  }
  if (!partyScene.timer) {
    partyScene.timer = setInterval(() => {
      if (!document.getElementById("party-scene")) {
        clearInterval(partyScene.timer);
        partyScene.timer = null;
        return;
      }
      PetMotion.step(partyScene.world);
      partySceneDraw();
    }, PARTY_TICK_MS);
  }
  partySceneDraw();
}

function partySceneDraw() {
  const ctx = document.getElementById("party-scene").getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(partyScene.background, 0, 0);
  PetMotion.draw(partyScene.world, habitatPainter(ctx, PARTY_SCENE_PX), { ctx, unit: PARTY_SCENE_PX, tags: true });
}

function partyPetDetail(m, i) {
  const energy = state.trip?.pets?.[i] ?? m.energy;
  const mana = state.trip?.mana?.[i] ?? m.mana;
  const xp = !m.id
    ? `<small>A starter: doesn't level up</small>`
    : m.progress
      ? `${bar(m.progress[0], m.progress[1], "xp")} <small title="XP">${m.progress[0]} / ${m.progress[1]} ${XP_ICON}</small>`
      : `${bar(1, 1, "xp")} <small>Fully leveled ${XP_ICON}</small>`;
  return `<div class="wander-fighter">
      <div class="wander-fighter-head">
        <canvas id="party-pet" width="150" height="120"></canvas>
        <div>
          <span class="wander-level">Level ${m.level}</span>
          <b class="wander-party-name">${esc(m.name)}</b> <small>${words(m.species)}</small>
          ${chips(m.types)}${state.fighters.includes(i) ? ` <span class="wander-mark">⚔ fights next</span>` : ""}<br>
          ${bar(energy, m.energy)} <small title="Energy">${energy} / ${m.energy} ${ENERGY_ICON}</small><br>
          ${bar(mana, m.mana, "mana")} <small class="wander-mana" title="Mana">${mana} / ${m.mana} ${MANA_ICON}</small><br>
          ${xp}
          <p class="wander-party-stats">Power <b>${m.power}</b> &nbsp; Speed <b>${m.speed}</b></p>
        </div>
      </div>
      <ul class="wander-moves ${gridSize(m.moves)}">${m.moves.map((move) => moveCard(move)).join("")}</ul>
      ${m.capstone_card ? `<p class="wander-capstone-title">Capstone: helps the party when ${esc(m.name)} isn't fighting</p><ul class="wander-moves wander-levelup-new">${moveCard(m.capstone_card)}</ul>` : ""}
    </div>`;
}

function renderParty() {
  const box = document.getElementById("party");
  const on = mode === "menu" && menu.name === "party";
  box.hidden = !on;
  box.parentElement.classList.toggle("partying", on);
  if (!on) return;
  menu.at = Math.max(0, Math.min(menu.at, state.team.length)); // 0: the whole party
  const list = document.getElementById("party-list");
  const row = (i, html) => `<li class="${i === menu.at ? "on" : ""}" data-i="${i}">${html}</li>`;
  list.innerHTML = row(0, "<b>Whole party</b>") + state.team
    .map((m, i) => row(i + 1, `${state.fighters.includes(i) ? "⚔ " : ""}${esc(m.name)} <small>${m.id ? `lv ${m.level}` : "starter"}</small>`))
    .join("");
  list.querySelectorAll("li[data-i]").forEach((li) => {
    li.onclick = () => {
      menu.at = Number(li.dataset.i);
      render();
    };
  });
  const detail = document.getElementById("party-detail");
  const keys = document.getElementById("party-keys");
  const look = `<kbd class="keycap">&uarr;</kbd><kbd class="keycap">&darr;</kbd> look`;
  const close = `<kbd class="keycap">Esc</kbd> close`;
  if (menu.at === 0) {
    detail.innerHTML = `<canvas id="party-scene" class="wander-party-scene" width="960" height="540"></canvas>
      <p class="hint">Your party, taking it easy at ${esc(state.local.name)}.</p>`;
    keys.innerHTML = `${look} &nbsp; ${close}`;
    partySceneStart();
    return;
  }
  const m = state.team[menu.at - 1];
  detail.innerHTML = partyPetDetail(m, menu.at - 1);
  keys.innerHTML = `${look} &nbsp; ${state.trip ? `<kbd class="keycap">F</kbd> fight / sit out (⚔ = fights next) &nbsp; ` : ""}${close}`;
  const canvas = document.getElementById("party-pet");
  canvas.hidden = !m.genes;
  if (m.genes) paintPet(canvas, m, 4);
}

function renderMenu() {
  const box = document.getElementById("menu");
  box.hidden = mode !== "menu" || menu.name === "map" || menu.name === "party";
  renderAtlas();
  renderParty();
  if (box.hidden) return;
  const rows = menuRows();
  menu.at = Math.max(0, Math.min(menu.at, rows.length - 1));
  const title = document.getElementById("menu-title");
  const body = document.getElementById("menu-body");
  const keys = document.getElementById("menu-keys");
  const list = (items, fn) =>
    `<ul class="wander-menu-list">${items.map((x, i) => `<li class="${i === menu.at ? "on" : ""}" data-i="${i}">${fn(x, i)}</li>`).join("")}</ul>`;
  keys.innerHTML = `<kbd class="keycap">&uarr;</kbd><kbd class="keycap">&darr;</kbd> look &nbsp; <kbd class="keycap">Esc</kbd> close`;
  if (menu.name === "bag" && menu.picking) {
    title.textContent = `${menu.picking}: on who?`;
    body.innerHTML = list(rows, (c) => wanderText(c.label));
    keys.innerHTML = `<kbd class="keycap">&uarr;</kbd><kbd class="keycap">&darr;</kbd> look &nbsp; <kbd class="keycap">Enter</kbd> use it &nbsp; <kbd class="keycap">Esc</kbd> back`;
  } else if (menu.name === "bag") {
    title.textContent = "Bag";
    const item = rows[menu.at];
    const use = item && (state.item_uses || {})[item];
    const fighting = Boolean(state.battle);
    body.innerHTML = rows.length
      ? `<div class="wander-menu-split">${list(rows, (k, i) => `${fighting ? `<kbd class="keycap">${i + 1}</kbd> ` : ""}${esc(k)}${state.items[k] > 1 ? ` x${state.items[k]}` : ""}`)}
          <p class="wander-menu-detail"><b>${esc(item)}</b><br>${wanderText(state.about[item] || "")}${use && use.why ? `<br><small>${esc(use.why)}</small>` : ""}</p></div>`
      : `<p class="hint">${fighting ? "Nothing in your bag can help right now." : "Nothing yet. Things you find go here."}</p>`;
    keys.innerHTML = `${fighting ? "Press a number to use it, without losing your turn." : `<kbd class="keycap">&uarr;</kbd><kbd class="keycap">&darr;</kbd> look`} ${use && !use.why ? `&nbsp; <kbd class="keycap">Enter</kbd> use it` : ""} &nbsp; <kbd class="keycap">Esc</kbd> close`;
  } else if (menu.name === "shop") {
    title.innerHTML = wanderText(state.screen ? state.screen.title : "Shop");
    const x = rows[menu.at];
    const coins = state.coin_balance ?? 0;
    const line = (r) => `${esc(r.name)} <small>${r.sold_out ? (r.keep ? "yours" : "sold out") : `${r.price.toLocaleString()} coins${r.left !== null ? `, ${r.left} left` : ""}`}</small>${r.owned && !r.keep ? ` <small>(you have ${r.owned})</small>` : ""}`;
    body.innerHTML = `<p>You have <b>${coins.toLocaleString()}</b> coins.</p>
      <div class="wander-menu-split">${list(rows, line)}
        <p class="wander-menu-detail"><b>${esc(x ? x.name : "")}</b><br>${wanderText(x ? x.about : "")}${x && x.keep ? "<br><small>You keep this one.</small>" : ""}</p></div>`;
    const can = x && !x.sold_out && coins >= x.price;
    keys.innerHTML = `<kbd class="keycap">&uarr;</kbd><kbd class="keycap">&darr;</kbd> look ${can ? `&nbsp; <kbd class="keycap">Enter</kbd> buy` : x && !x.sold_out ? "&nbsp; Not enough coins yet." : ""} &nbsp; <kbd class="keycap">Esc</kbd> leave`;
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
  } else if (menu.name === "log") {
    title.textContent = "Log";
    body.innerHTML = rows.length ? list([...rows].reverse(), (t) => wanderText(t)) : `<p class="hint">Nothing has happened yet.</p>`;
    keys.innerHTML = `<kbd class="keycap">Esc</kbd> close`;
  } else if (menu.name === "guide") {
    title.textContent = "Guidebook";
    renderGuide(body, keys);
  } else if (menu.name === "home") {
    title.textContent = "Heading home?";
    body.innerHTML = list(rows, (c, i) => `<kbd class="keycap">${i + 1}</kbd> ${wanderText(c.label)}`);
    keys.innerHTML = `<kbd class="keycap">Enter</kbd> choose &nbsp; <kbd class="keycap">Esc</kbd> keep playing`;
  }
  body.querySelectorAll("li[data-i]").forEach((li) => {
    li.onclick = () => {
      menu.at = Number(li.dataset.i);
      if (menu.name === "home") chooseHome(menu.at);
      else render();
    };
  });
  body.querySelectorAll("[data-guide-page]").forEach((b) => {
    b.onclick = () => {
      menu.page = Number(b.dataset.guidePage);
      render();
    };
  });
  body.querySelectorAll("[data-guide-me]").forEach((b) => {
    b.onclick = () => {
      menu.me = guideSides.me = b.dataset.guideMe;
      render();
    };
  });
  body.querySelectorAll("[data-guide-enemy]").forEach((b) => {
    b.onclick = () => {
      menu.enemy = guideSides.enemy = b.dataset.guideEnemy;
      render();
    };
  });
}

// --- the guidebook -----------------------------------------------------------------------
// Pages you turn with the arrows, all from the real rules (battle.guide).

const GUIDE_PAGES = ["Types", "Match-ups", "Combo chart", "Combos found", "Marks & effects", "How fights work", "The lands"];
const TIMES = (x) => (x === 0.67 ? "x⅔" : x === 0.5 ? "x½" : `x${x}`);
const STRENGTH_WORD = { 2: "Super strong", 1.5: "Strong", 1: "Even", 0.67: "Weak", 0.5: "Very weak" };

function guideKey(e) {
  const g = guideData;
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    e.preventDefault();
    menu.page = (menu.page + (e.key === "ArrowRight" ? 1 : -1) + GUIDE_PAGES.length) % GUIDE_PAGES.length;
    render();
  } else if (g && menu.page === 1 && "adjl".includes(e.key)) {
    const side = "ad".includes(e.key) ? "me" : "enemy";
    const step = "dl".includes(e.key) ? 1 : -1;
    menu[side] = g.order[(g.order.indexOf(menu[side]) + step + g.order.length) % g.order.length];
    guideSides[side] = menu[side];
    render();
  } else if (e.key === "2" && state.battle) {
    closeMenu();
  } else if (e.key === "1" && state.battle) {
    openMenu("bag");
  } else if (!state.battle && BOOKS[Number(e.key) - 1]) {
    const name = BOOKS[Number(e.key) - 1];
    if (name === "guide") closeMenu();
    else openMenu(name);
  } else if (e.key === "Enter") {
    closeMenu();
  }
}

// Who beats whom: a ring of the five types. Thick arrows are x2, the dashed x1.5.
function typeRing(g) {
  const R = 96;
  const C = 130;
  const at = (i, r = R) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / g.order.length;
    return [C + r * Math.cos(a), C + r * Math.sin(a)];
  };
  const arrow = (i, j, cls) => {
    const [x1, y1] = at(i);
    const [x2, y2] = at(j);
    const len = Math.hypot(x2 - x1, y2 - y1);
    const [ux, uy] = [(x2 - x1) / len, (y2 - y1) / len];
    const color = WanderMap.TYPE_COLORS[g.order[i]];
    return `<line x1="${x1 + ux * 25}" y1="${y1 + uy * 25}" x2="${x2 - ux * 28}" y2="${y2 - uy * 28}" stroke="${color}" class="${cls}" marker-end="url(#guide-arrow-${i})"/>`;
  };
  const n = g.order.length;
  const defs = g.order.map((t, i) => `<marker id="guide-arrow-${i}" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="${WanderMap.TYPE_COLORS[t]}"/></marker>`).join("");
  const lines = g.order.flatMap((_, i) => [arrow(i, (i + 2) % n, "weak"), arrow(i, (i + 1) % n, "strong")]).join("");
  const dots = g.order.map((t, i) => {
    const [x, y] = at(i);
    return `<circle cx="${x}" cy="${y}" r="26" fill="${WanderMap.TYPE_COLORS[t]}"/><text x="${x}" y="${y + 5}" text-anchor="middle">${REGION_NAMES[t]}</text>`;
  }).join("");
  return `<svg class="wander-type-ring" viewBox="0 0 260 260" role="img" aria-label="Which types are strong against which"><defs>${defs}</defs>${lines}${dots}</svg>`;
}

function guideTypes(g) {
  const head = g.order.map((t) => `<th>${chips({ [t]: "" })}</th>`).join("");
  const rows = g.order.map((m) => `<tr><th>${chips({ [m]: "" })}</th>${g.order.map((t) => {
    const x = g.chart[m][t];
    return `<td class="x-${String(x).replace(".", "_")}" title="${STRENGTH_WORD[x]}">${TIMES(x)}</td>`;
  }).join("")}</tr>`).join("");
  return `<div class="wander-guide-types">
      ${typeRing(g)}
      <div>
        <p>Each type is <b>super strong</b> (x2, thick arrow) against the next one round the ring, and <b>strong</b> (x1.5, dashed) against the one after that. It's weak against the two that beat it.</p>
        <table class="wander-combos wander-type-chart"><tr><th>hit / on</th>${head}</tr>${rows}</table>
        <p class="hint">Read across for attacking, and down for defending: a column shows what hits that type hard.</p>
      </div>
    </div>`;
}

function guideMatchups(g) {
  const pick = (side, on) => g.order.map((t) => `<button type="button" class="wander-guide-pick ${on === t ? "on" : ""}" data-guide-${side}="${t}" style="background:${WanderMap.TYPE_COLORS[t]}">${REGION_NAMES[t]}</button>`).join("");
  const [me, foe] = [menu.me, menu.enemy];
  const out = g.chart[me][foe];
  const back = g.chart[foe][me];
  const ranked = (fn) => g.order.filter(fn).sort((a, b) => g.chart[b][foe] - g.chart[a][foe]);
  const bring = ranked((t) => g.chart[t][foe] > 1).map((t) => `${chips({ [t]: TIMES(g.chart[t][foe]) })}`).join(" ");
  const avoid = g.order.filter((t) => g.chart[foe][t] > 1).map((t) => chips({ [t]: "" })).join(" ");
  return `<p><b>Your type</b> <kbd class="keycap">A</kbd><kbd class="keycap">D</kbd> ${pick("me", me)}</p>
    <p><b>Enemy's type</b> <kbd class="keycap">J</kbd><kbd class="keycap">L</kbd> ${pick("enemy", foe)}</p>
    <ul class="wander-guide-result">
      <li>Your hit on it: <b>${TIMES(out)}</b> ${STRENGTH_WORD[out]}.</li>
      <li>Its hit on you: <b>${TIMES(back)}</b> ${STRENGTH_WORD[back]}.</li>
      <li>Bring against it: ${bring}</li>
      <li>It hits these hard: ${avoid}</li>
    </ul>
    <p class="hint">Against a temple's guardian, a strong type's extra is ${Math.round(g.boss_edge * 100)}% as much, so x2 acts like x${1 + g.boss_edge}. A counter does the most as a pet's first type.</p>`;
}

function guideComboChart() {
  const order = ["splash", "ember", "dream", "shock", "leaf"];
  const marks = ["soaked", "glowing", "drowsy", "static", "tangled"];
  const cell = (mark, hit) => state.combo_book.find((c) => c.mark === mark && c.hit === hit);
  const found = state.combo_book.filter((c) => c.name);
  return `<p>A big move leaves a mark; the next hit of the right type sets off a combo. Found ${found.length} of ${state.combo_book.length}.</p>
    <table class="wander-combos">
      <tr><th>mark / hit</th>${order.map((t) => `<th>${chips({ [t]: "" })}</th>`).join("")}</tr>
      ${marks.map((m) => `<tr><th style="color:${WanderMap.TYPE_COLORS[MARK_TYPE[m]]}">${m}</th>${order.map((t) => {
        const c = cell(m, t);
        return `<td class="${c ? (c.name ? "found" : "") : "gap"}">${c ? (c.name ? esc(c.name) : "???") : ""}</td>`;
      }).join("")}</tr>`).join("")}
    </table>`;
}

function guideCombosFound() {
  const found = state.combo_book.filter((c) => c.name);
  return found.length
    ? `<ul class="wander-combo-list">${found.map((c) => `<li><b>${esc(c.name)}</b> (${c.mark} + ${wanderText(`{${c.hit}}`)}): ${wanderText(c.says || "")}</li>`).join("")}</ul>`
    : `<p class="hint">None yet. Set one off in a fight, and it's written down here.</p>`;
}

const guideList = (entries) => `<dl class="wander-guide-terms">${entries.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${wanderText(v)}</dd>`).join("")}</dl>`;

function guideLands(g) {
  return `<p>The land round Camp is ordinary heartland. Past it, each of the five types has its own country, its temple, and a town.</p>
    ${guideList(Object.entries(g.lands).map(([k, v]) => [words(k), v]))}`;
}

function renderGuide(body, keys) {
  const g = guideData;
  menu.page = menu.page || 0;
  if (!g) {
    body.innerHTML = `<p class="hint">Opening the book...</p>`;
    return;
  }
  const tabs = GUIDE_PAGES.map((p, i) => `<button type="button" class="wander-guide-tab ${i === menu.page ? "on" : ""}" data-guide-page="${i}">${esc(p)}</button>`).join("");
  const page = [
    () => guideTypes(g),
    () => guideMatchups(g),
    guideComboChart,
    guideCombosFound,
    () => `<h3>Marks</h3>${guideList(Object.entries(g.marks))}<h3>Effects</h3>${guideList(Object.entries(g.effects))}`,
    () => guideList(Object.entries(g.fight)),
    () => guideLands(g),
  ][menu.page]();
  body.innerHTML = `<nav class="wander-guide-tabs">${tabs}</nav><div class="wander-guide-page">${page}</div>`;
  keys.innerHTML = `<kbd class="keycap">&larr;</kbd><kbd class="keycap">&rarr;</kbd> turn the page &nbsp; <kbd class="keycap">Esc</kbd> close`;
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

const questLine = (q) => `<b>${wanderText(q.title)}</b>: ${q.done ? "done!" : wanderText(q.text)}`;
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
  if (e.key === "Escape") {
    if (menu.picking) {
      menu.picking = null;
      menu.at = 0;
      return render();
    }
    return closeMenu();
  }
  if (menu.name === "guide") return guideKey(e);
  if (menu.name === "shop") {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      menu.at += e.key === "ArrowDown" ? 1 : -1;
      render();
    } else if (e.key === "Enter") {
      const x = menuRows()[menu.at];
      if (x && !x.sold_out) buyItem(x.name);
    }
    return;
  }
  if (menu.name === "bag") {
    const rows = bagRows();
    if (menu.picking) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        menu.at += e.key === "ArrowDown" ? 1 : -1;
        render();
      } else if (e.key === "Enter" && rows[menu.at]) useItem(menu.picking, rows[menu.at].arg);
      return;
    }
    if (e.key === "Enter" && rows[menu.at] && (state.item_uses[rows[menu.at]] || {}).why === null) return useItem(rows[menu.at]);
    if (state.battle && /^[1-9]$/.test(e.key)) {
      const item = rows[Number(e.key) - 1];
      if (item) useItem(item);
      return;
    }
    if (state.battle && e.key === "Enter") return closeMenu();
  }
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    menu.at += e.key === "ArrowDown" ? 1 : -1;
    render();
  } else if (menu.name === "party" && (e.key === "f" || e.key === "F") && state.trip) {
    // pick who fights next: up to two
    if (menu.at === 0) return; // the whole party's picture
    const at = menu.at - 1;
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
  ctx.clearRect(0, 0, canvas.width, canvas.height); // (a canvas that stays, like the creature's, keeps what was drawn before)
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
    text.innerHTML = state.credits.map((l) => wanderText(l) || "&nbsp;").join("<br>");
    keys.innerHTML = `<kbd class="keycap">Enter</kbd> back to the map`;
    return;
  }
  const s = state.screen;
  if (!s) {
    mode = "walk";
    screenBox.hidden = true;
    return;
  }
  title.innerHTML = wanderText(s.title);
  text.innerHTML = wanderText(s.text);
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
    keys.innerHTML = `${s.options.map((o, i) => `<kbd class="keycap">${i + 1}</kbd> ${wanderText(o.label)}`).join("<br>")}<br><kbd class="keycap">Esc</kbd> leave`;
    return;
  }
  keys.innerHTML = s.action
    ? `<kbd class="keycap">Enter</kbd> ${wanderText(s.label)} &nbsp; <kbd class="keycap">Esc</kbd> leave`
    : `<kbd class="keycap">Enter</kbd> leave`;
}

const LEVEL_STATS = [["energy", ENERGY_ICON], ["mana", MANA_ICON], ["power", "Power"], ["speed", "Speed"]];
const CONFETTI = ["#e2a33c", "#c8553d", "#6d9f58", "#4f8fb8", "#a76fb0"];

// Looks like a pet's page in the party book: stats with what grew, its six
// moves, and below them any choice to make. A number previews a choice in
// the six moves; Enter makes it.
function renderLevelup() {
  const box = document.getElementById("levelup");
  const up = mode === "levelup" ? state.levelups[0] : null;
  box.hidden = !up;
  box.parentElement.classList.toggle("leveling", !!up);
  if (!up) {
    levelupShown = null;
    return;
  }
  const entry = `${up.pet}:${up.level}`;
  const step = up.choose ? up.choose.kind : "";
  const id = `${entry}:${step}:${levelPick}`;
  if (levelupShown === id) return;
  if (!levelupShown || !levelupShown.startsWith(`${entry}:`)) {
    document.getElementById("levelup-confetti").innerHTML = Array.from({ length: 36 }, (_, i) =>
      `<i style="left:${(i * 37) % 100}%;background:${CONFETTI[i % CONFETTI.length]};animation-delay:${(i % 7) * 70}ms"></i>`).join("");
  }
  levelupShown = id;
  const options = up.choose ? up.choose.options : [];
  const pick = options[levelPick];
  const moves = pick ? pick.moves : up.moves;
  const types = pick && up.choose.kind === "second" ? { ...up.types, [pick.id]: 1 } : up.types;
  const title = up.max ? `Fully leveled!` : `Level up!`;
  document.getElementById("levelup-detail").innerHTML = `<div class="wander-fighter">
      <div class="wander-fighter-head">
        <canvas id="levelup-pet" width="150" height="120"></canvas>
        <div>
          <span class="wander-level">Level ${up.level}</span>
          <b class="wander-party-name">${esc(up.name)}</b> <small>${words(up.species)}</small>
          ${chips(types)} <b id="levelup-title">${title}</b>
          <dl class="wander-levelup-stats" id="levelup-stats">${LEVEL_STATS.map(([k, name]) => {
            const later = k === "energy" && state.trip ? ` <small>(from tomorrow)</small>` : "";
            return `<dt>${name}</dt><dd>${up.was[k]} &rarr; <b>${up.now[k]}</b> <span class="wander-levelup-gain">+${up.now[k] - up.was[k]}</span>${later}</dd>`;
          }).join("")}</dl>
        </div>
      </div>
      <ul class="wander-moves ${gridSize(moves)}">${moves.map((m, i) => moveCard(m, undefined, pick && m.label !== up.moves[i]?.label)).join("")}</ul>
    </div>`;
  document.getElementById("levelup-choice").innerHTML = options.length
    ? `<h3 class="wander-levelup-ask">${wanderText(up.choose.ask)}</h3>
       ${up.choose.new ? `<ul class="wander-moves wander-levelup-new">${moveCard(up.choose.new)}</ul>` : ""}
       <ul class="wander-levelup-options" style="--across:${options.length === 6 ? 3 : Math.min(4, options.length)}">${options.map((o, i) => levelOption(o, i, levelPick)).join("")}</ul>`
    : "";
  const more = state.levelups.length - 1;
  const left = more ? ` &nbsp; <small>${more} more to celebrate</small>` : "";
  document.getElementById("levelup-keys").innerHTML = (options.length
    ? `${options.map((_, i) => `<kbd class="keycap">${i + 1}</kbd>`).join("")} look at a choice${pick ? ` &nbsp; <kbd class="keycap">Enter</kbd> choose ${wanderText(pick.label)}` : ""}`
    : `<kbd class="keycap">Enter</kbd> hooray!`) + left;
  box.querySelectorAll("[data-option]").forEach((el) => {
    el.onclick = () => {
      levelPick = Number(el.dataset.option);
      render();
    };
  });
  const canvas = document.getElementById("levelup-pet");
  canvas.hidden = !up.genes;
  if (up.genes) paintPet(canvas, up, 4);
}

function levelupKey(e) {
  const up = state.levelups[0];
  if (!up.choose) {
    if (e.key === "Enter") {
      e.preventDefault();
      finishLevelup(null);
    }
    return;
  }
  if (up.choose.options[Number(e.key) - 1]) {
    levelPick = Number(e.key) - 1;
    render();
  } else if (e.key === "Enter" && levelPick !== null) {
    e.preventDefault();
    finishLevelup(up.choose.options[levelPick].id);
  }
}

async function finishLevelup(choice) {
  const data = await send("/api/wander/levelup", { choice });
  if (!data) return;
  levelPick = null;
  apply(data);
  loadPets(); // new levels, new types
}

function noteFor(data) {
  // (a battle's blow-by-blow goes in its own log, and level-ups get a pop-up)
  const texts = (data.events || []).filter((e) => e.text && e.kind !== "hit" && e.kind !== "level").map((e) => e.text);
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
  if (data.battle && mode !== "menu") mode = "battle";
  else if (mode === "battle") mode = "walk";
  if (!data.trip && (!pets || state?.trip)) loadPets(); // back between trips: levels may have changed
  state = data;
  slideTo(data.local.spot);
  typer.release();
  pickTargets();
  if (data.credits) mode = "credits";
  if (data.levelups.length && !data.battle && mode !== "line" && mode !== "credits") {
    if (mode !== "levelup") afterLevelup = mode === "screen" ? "screen" : "walk";
    mode = "levelup";
  } else if (mode === "levelup" && !data.levelups.length) {
    mode = afterLevelup;
  }
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
for (const [id, name] of [["battle-bag", "bag"], ["battle-guide", "guide"]]) {
  document.getElementById(id).addEventListener("click", (e) => {
    e.currentTarget.blur();
    if (state && !busy && !replay) openMenu(name);
  });
}
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
  if (e.key === "Enter" && s && s.action === "shop") return openMenu("shop");
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
  else if (mode === "levelup") levelupKey(e);
  else screenKey(e);
});

load();
