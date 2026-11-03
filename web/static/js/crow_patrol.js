// Crow Patrol (game_crow_patrol_v1): crows fly at your pumpkin patch from
// every side, each carrying a word. Type a crow's word to shoo it.
//
// Crow kinds (each round brings in a new one, see app/activities/game_modules.py):
//   little   fast, short word                     caller   calls a friend when its timer runs out
//   crow     medium speed and word                squirrel drops a squirrel over the patch
//   big      slow, long word, takes 2 pumpkins    golden   ignores pumpkins; 100 points if you catch it
//   king     (a card, rarely) twice the size, comes with two squirrel crows; pays an arcade token
// The first slip on a crow makes it squawk for a friend (one per crow).
//
// Each round starts with a full patch and ends when time runs out or the
// pumpkins are all gone. Then the arcade tally: crows by kind, pumpkins saved
// (100 each, 250 with pie), and a bonus for a perfect patch. Then pick an
// upgrade by typing its word: 3 cards from UPGRADES, so runs differ. A round card
// counters the crow coming next, and is always one of the 3 before that crow.
//
// Pacing comes from the learner's typing speed (content.game.chars_per_second),
// so a slow typer gets slower crows, not a harder game.
//
// Needs practice_scenes.js (Scene, C), avatar.js, and game_kit.js loaded first.

const FIELD_W = 240;
const FIELD_H = 120;
const START_PUMPKINS = 6;
const PUMPKIN_POINTS = 100;
const PIE_POINTS = 250;
const PERFECT_PATCH_POINTS = 200;
const AVG_WORD_LEN = { short: 2.5, medium: 4.5, long: 6.5 };
const MAX_CALLS = 2; // a caller crow calls at most this many friends on its timer

const CROW_KINDS = {
  little: { name: "Little crow", about: "Fast, with a short word.", words: "short", speed: 1.4, size: 0.75, points: 10, color: "#3a3946" },
  crow: { name: "Crow", about: "Medium speed, medium word.", words: "medium", speed: 1, size: 1, points: 20, color: "#2b2a33" },
  big: { name: "Big crow", about: "Slow, with a long word. Takes 2 pumpkins!", words: "long", speed: 0.75, size: 1.45, points: 40, color: "#251f2e", steals: 2 },
  caller: { name: "Caller crow", about: "Shoo it before its timer runs out, or it calls a friend!", words: "medium", speed: 0.8, size: 1, points: 30, color: "#46506e", callEvery: 6 },
  squirrel: { name: "Squirrel crow", about: "Carries a squirrel. Over the patch, it drops it to eat a pumpkin!", words: "medium", speed: 0.85, size: 1.1, points: 30, color: "#2b2a33" },
  golden: { name: "Golden crow", about: "Doesn't want pumpkins. Catch it before it flies off!", words: "long", speed: 1, size: 1, points: 100, color: "#d9a520" },
  king: { name: "King Crow", about: "", words: "long", speed: 0.7, size: 2, points: 0, color: "#e0ad28" },
  runner: { name: "Squirrel", about: "", words: "short", points: 10 },
};

const SKIES = [
  ["#f6d8b0", "#cfe8ef", "#a8d5e2"], // morning
  ["#cfe8ef", "#a8d5e2", "#8fc3d6"], // midday
  ["#f3d9a4", "#cfe8ef", "#a8d5e2"], // afternoon
  ["#e8a06b", "#f3c27a", "#f6d8b0"], // sunset
  ["#1d2340", "#2f3a63", "#4a4f7a"], // moonrise
];

// once: only one of it. family: only one of the family, ever, and they're offered
// side by side. next: a round card, offered just before that round (its index).
const UPGRADES = {
  scarecrow: { name: "Scarecrow", text: "Crows fly slower." },
  fence: { name: "Fence", text: "2 more pumpkins every round." },
  bell: { name: "Bell", text: "Press [Space] once a round to shoo every crow." },
  pie: { name: "Pumpkin pie", text: "Pumpkins you save are worth 250, not 100.", once: true },
  hot: { name: "Hot Streak", text: "Shoo 5 crows in a row with no slips, and the next one is worth triple!", once: true },
  calm: { name: "Calm Crows", text: "Slips don't make crows call a friend.", once: true },
  guard: { name: "Guard Dog", text: "Type the long word over your pet. It runs out and scares off a crow, then comes back.", once: true },
  compost: { name: "Compost", text: "Every 8 crows you shoo, a lost pumpkin grows back.", once: true },
  whistle: { name: "Crow Whistle", text: "More crows come, but each one is worth double.", once: true },
  shiny: { name: "Shiny Beak", text: "Every crow is worth 50% more.", once: true },
  decoy: { name: "Pumpkin Decoy", text: "Crows go for a fake pumpkin first.", once: true },
  sunny: { name: "Sunny Day", text: "Rounds last 10 seconds longer. More crows, more points!", family: "weather" },
  rainy: { name: "Rainy Day", text: "Rounds are 10 seconds shorter. Fewer crows, but fewer points.", family: "weather" },
  slingshot: { name: "Slingshot", text: "Big crows get shorter words.", next: 1 },
  earmuffs: { name: "Earmuffs", text: "Caller crows take twice as long to call.", next: 2 },
  acorns: { name: "Acorn Pile", text: "Dropped squirrels stop for a snack before going for a pumpkin.", next: 3 },
  net: { name: "Golden Net", text: "Golden crows are worth 200, not 100.", next: 4 },
  king: { name: "King Crow", text: "He comes halfway through the last round, with two guards. Shoo him for an arcade token!", next: 4, rare: true },
};
const KING_CHANCE = 0.5;
const WEATHER_SECONDS = 10;
const STREAK = 5;
const STREAK_TIMES = 3;
const COMPOST_EVERY = 8;
const WHISTLE_SPAWN = 0.7;
const SHINY = 1.5;
const GOLDEN_NET_POINTS = 200;
const GUARD_SPEED = 140; // field pixels a second
const GUARD_REACH = 14;
const GUARD_HOME = { x: 66, y: 116 }; // beside you, so its word doesn't cover you

class CrowPatrol {
  constructor(shell, content, avatar) {
    this.shell = shell;
    this.game = content.game;
    this.avatar = avatar;
    this.levels = this.game.levels;
    this.typer = new Typer();
    this.levelIndex = 0;
    this.upgrades = Object.fromEntries(Object.keys(UPGRADES).map((id) => [id, 0]));
    this.kingChance = KING_CHANCE;
    this.kingCame = false;
    this.guard = null; // your pet, once you've the card: {word, typed, state, x, y, el}
    this.crows = []; // crows and squirrels: everything with a word
    this.bubbles = [];
    this.state = "intro"; // intro | play | tally | choose | over
    this.choices = [];
    this.jump = 0;
    this.icon = null;

    const game = this;
    this.scene = new (class extends Scene {
      update(dt) {
        game.update(dt, this);
      }
      draw() {
        game.draw(this);
      }
    })(shell.els.canvas, FIELD_W, FIELD_H);
    shell.els.canvas.classList.add("crow-field");

    this.resetPatch();
    this.resetRound();
    this.renderHud();
    this.introScreen();
    window.addEventListener("keydown", (e) => this.handleKey(e));
  }

  get level() {
    return this.levels[this.levelIndex];
  }

  // --- flow -----------------------------------------------------------------

  introScreen() {
    this.state = "intro";
    this.shell.setLabel(`Game · Round ${this.levelIndex + 1} of ${this.levels.length}`);
    const kind = CROW_KINDS[this.level.new];
    const isNew = this.levelIndex > 0;
    this.shell.showScreen(
      `<h2>Round ${this.levelIndex + 1}: ${escapeHtml(this.level.name)}</h2>
       ${this.levelIndex === 0 ? `<p>Type the word on a crow to shoo it. Slips make crows call a friend!</p>` : ""}
       <div class="crow-intro">
         <canvas class="crow-icon"></canvas>
         <div>${isNew ? `<span class="new-tag">NEW!</span> ` : ""}<b>${kind.name}</b> · ${this.pointsFor(this.level.new)} points<br>${escapeHtml(kind.about)}</div>
       </div>
       ${this.kingDue() ? `<p><b>King Crow</b> comes halfway through. Shoo him for an arcade token!</p>` : ""}
       <p>Press ${keycap(" ")} to start.</p>`,
      { " ": () => this.startRound() }
    );
    this.showIcon(this.level.new);
  }

  // A flapping crow on the intro card.
  showIcon(kindId) {
    if (this.icon) this.icon.destroy();
    const game = this;
    const canvas = this.shell.els.screen.querySelector(".crow-icon");
    this.icon = new (class extends Scene {
      draw() {
        this.ctx.clearRect(0, 0, this.w, this.h);
        game.drawCrow(this, { kind: kindId, x: 24, y: 16, dir: -1, phase: this.t * 12, state: "fly", hasSquirrel: kindId === "squirrel" });
      }
    })(canvas, 48, 32);
  }

  startRound() {
    if (this.icon) this.icon.destroy();
    this.shell.hideScreen();
    this.resetPatch();
    this.resetRound();
    this.state = "play";
  }

  get roundSeconds() {
    return this.level.seconds + WEATHER_SECONDS * (this.upgrades.sunny - this.upgrades.rainy);
  }

  // What a shooed crow of this kind is worth, with your upgrades.
  pointsFor(kindId) {
    const base = kindId === "golden" && this.upgrades.net ? GOLDEN_NET_POINTS : CROW_KINDS[kindId].points;
    return Math.round(base * (this.upgrades.whistle ? 2 : 1) * (this.upgrades.shiny ? SHINY : 1));
  }

  resetRound() {
    this.timeLeft = this.roundSeconds;
    this.spawnIn = 1;
    this.streak = 0;
    this.streakHot = false;
    this.streakBonus = 0;
    this.decoy = this.upgrades.decoy ? { x: 84, y: 99, taken: false, fake: true } : null;
    if (this.upgrades.guard) this.readyGuard();
    this.shooed = {}; // kind -> count this round
    this.lostThisRound = 0;
    this.roundPoints = 0;
    this.bellLeft = this.upgrades.bell;
    this.typer.release();
  }

  resetPatch() {
    const count = START_PUMPKINS + 2 * this.upgrades.fence;
    this.pumpkins = Array.from({ length: count }, (_, i) => ({
      x: 92 + (i * 134) / Math.max(1, count - 1),
      y: i % 2 ? 104 : 94,
      taken: false,
    }));
  }

  async endRound() {
    const saved = this.pumpkins.filter((p) => !p.taken).length;
    const wiped = saved === 0;
    this.state = "tally";
    this.typer.release();
    for (const c of this.crows) if (c.state === "fly") this.flee(c, false);
    this.renderHud();
    const rows = Object.keys(CROW_KINDS)
      .filter((k) => this.shooed[k] && this.pointsFor(k))
      .map((k) => ({ label: `${CROW_KINDS[k].name}s shooed`, count: this.shooed[k], each: this.pointsFor(k) }));
    if (this.streakBonus) rows.push({ label: "Hot streak bonus", points: this.streakBonus });
    rows.push({
      label: this.upgrades.pie ? "Pumpkin pies" : "Pumpkins saved",
      count: saved,
      each: this.upgrades.pie ? PIE_POINTS : PUMPKIN_POINTS,
      always: true,
    });
    if (!this.lostThisRound) rows.push({ label: "Perfect patch!", points: PERFECT_PATCH_POINTS });
    await this.shell.roundTally({
      title: wiped ? "The crows got every pumpkin!" : `${this.level.name} done!`,
      rows,
      typer: this.typer,
    });
    this.roundPoints = 0;
    this.renderHud();
    if (this.levelIndex >= this.levels.length - 1) this.gameOver();
    else this.chooseUpgrade();
  }

  // Three cards: King Crow if he's drawn, the round's own card, then the rest at random.
  // Sunny and Rainy come together, so you pick one.
  offerCards() {
    const taken = (id) => this.upgrades[id] > 0;
    const next = this.levelIndex + 1;
    const offer = [];
    if (next === this.levels.length - 1 && this.game.king_ready && Math.random() < this.kingChance) offer.push("king");
    offer.push(...Object.keys(UPGRADES).filter((id) => UPGRADES[id].next === next && !UPGRADES[id].rare));
    const weatherGone = taken("sunny") || taken("rainy");
    const general = Object.keys(UPGRADES).filter((id) => {
      const u = UPGRADES[id];
      return u.next === undefined && !u.family && !(u.once && taken(id));
    });
    const pool = weatherGone ? general : [...general, "weather"];
    for (const id of pool.sort(() => Math.random() - 0.5)) {
      const room = 3 - offer.length;
      if (id === "weather" && room >= 2) offer.push("sunny", "rainy");
      else if (id !== "weather" && room >= 1) offer.push(id);
    }
    return offer;
  }

  cardName(id) {
    if (id !== "guard") return UPGRADES[id].name;
    const species = this.game.helper ? this.game.helper.species.replace(/_/g, " ") : "dog";
    return `Guard ${species[0].toUpperCase()}${species.slice(1)}`;
  }

  chooseUpgrade() {
    const offer = this.offerCards();
    const words = pickWords(this.game.words, offer.map(() => "short"));
    this.choices = offer.map((id, i) => ({ id, word: words[i], typed: 0 }));
    this.state = "choose";
    this.shell.showScreen(
      `<h2>Pick an upgrade</h2>
       <p>Type its word.</p>
       <div class="choice-cards">${this.choices
         .map(
           (c, i) => `<div class="choice-card${c.id === "king" ? " king" : ""}" data-i="${i}">
             <h3>${this.cardName(c.id)}</h3>
             <p>${richText(UPGRADES[c.id].text)}</p>
             <p class="choice-word"></p>
           </div>`
         )
         .join("")}</div>`
    );
    this.renderChoices();
  }

  renderChoices() {
    this.shell.els.screen.querySelectorAll(".choice-card").forEach((card) => {
      const c = this.choices[+card.dataset.i];
      card.classList.toggle("locked", this.typer.target === c);
      card.querySelector(".choice-word").innerHTML = wordHtml(c.word, c.typed);
    });
  }

  takeUpgrade(choice) {
    this.upgrades[choice.id] += 1;
    this.levelIndex += 1;
    this.resetPatch();
    this.resetRound();
    this.renderHud();
    this.introScreen();
  }

  gameOver() {
    this.state = "over";
    this.shell.finish({ line: "Crow Patrol complete!" });
  }

  // --- crows ------------------------------------------------------------------

  // How long a word of this group takes this learner, in seconds (with time to read it).
  wordSeconds(group) {
    const cps = Math.max(0.5, this.game.chars_per_second || 1.5);
    return AVG_WORD_LEN[group] / cps + 1.2;
  }

  flying() {
    return this.crows.filter((c) => c.state === "fly");
  }

  takenLetters() {
    const taken = new Set(this.flying().map((c) => c.word[0]));
    if (this.guard && this.guard.word) taken.add(this.guard.word[0]);
    return taken;
  }

  // Flying straight across the sky, not after pumpkins.
  crossesSky(kindId) {
    return kindId === "golden" || kindId === "king";
  }

  wordGroup(kindId) {
    return kindId === "big" && this.upgrades.slingshot ? "medium" : CROW_KINDS[kindId].words;
  }

  callEvery(kind) {
    return kind.callEvery * (this.upgrades.earmuffs ? 2 : 1);
  }

  pickKind() {
    const entries = Object.entries(this.level.types);
    let roll = Math.random() * entries.reduce((sum, [, w]) => sum + w, 0);
    for (const [kind, w] of entries) {
      roll -= w;
      if (roll <= 0) return kind;
    }
    return "crow";
  }

  // Where a crow comes in: the left, the right, or the top.
  entryPoint() {
    const side = Math.random();
    if (side < 0.35) return { x: -10, y: 8 + Math.random() * 40 };
    if (side < 0.7) return { x: FIELD_W + 10, y: 8 + Math.random() * 40 };
    return { x: 70 + Math.random() * 160, y: -10 };
  }

  spawnCrow(kindId, { friend = false } = {}) {
    const kind = CROW_KINDS[kindId];
    const word = pickWord(this.game.words, this.wordGroup(kindId), this.takenLetters())
      || (kindId === "king" ? pickWord(this.game.words, "medium", new Set()) || pickWord(this.game.words, "short", new Set()) : null);
    if (!word) return null;
    const start = this.entryPoint();
    const slow = Math.pow(0.85, this.upgrades.scarecrow);
    const speed = this.level.speed * kind.speed * slow;
    const crow = {
      kind: kindId, word, typed: 0, slips: 0, friend,
      x: start.x, y: start.y, sx: start.x, sy: start.y, t: 0,
      state: "fly", vx: 0, vy: 0, dir: -1, phase: Math.random() * 6,
      called: friend, calls: 0, callIn: kind.callEvery ? this.callEvery(kind) : 0,
      hasSquirrel: kindId === "squirrel",
    };
    if (this.crossesSky(kindId)) {
      const fromLeft = Math.random() < 0.5;
      crow.sx = crow.x = fromLeft ? -10 : FIELD_W + 10;
      crow.sy = crow.y = (kindId === "king" ? 22 : 12) + Math.random() * 14;
      crow.tx = fromLeft ? FIELD_W + 12 : -12;
      crow.ty = crow.sy + 6;
      crow.dur = (this.wordSeconds("long") * 1.8 + 2) / speed;
    } else {
      crow.pumpkin = this.aimAt();
      if (!crow.pumpkin) return null;
      crow.dur = (this.wordSeconds(kind.words) * 3 + 4) / speed;
    }
    crow.el = this.makeLabel(kindId);
    this.crows.push(crow);
    return crow;
  }

  // A pumpkin nobody's after yet, if there is one. Crows go for a decoy first (not squirrels).
  aimAt(decoys = true) {
    if (decoys && this.decoy && !this.decoy.taken) return this.decoy;
    const free = this.pumpkins.filter((p) => !p.taken);
    const aimed = new Set(this.flying().map((c) => c.pumpkin));
    const open = free.filter((p) => !aimed.has(p));
    const pool = open.length ? open : free;
    return pool.length ? pool[Math.floor(Math.random() * pool.length)] : null;
  }

  makeLabel(kindId) {
    const el = document.createElement("div");
    el.className = `crow-word kind-${kindId}`;
    el.innerHTML = `<span class="crow-word-text"></span>${kindId === "caller" ? '<span class="call-timer"><span></span></span>' : ""}`;
    this.shell.els.layer.appendChild(el);
    return el;
  }

  // A squawk bubble, then a little crow comes to help.
  callFriend(crow, text) {
    const el = document.createElement("div");
    el.className = "crow-bubble";
    el.textContent = text;
    this.shell.els.layer.appendChild(el);
    this.bubbles.push({ el, crow, life: 1.6 });
    this.spawnCrow("little", { friend: true });
  }

  dropSquirrel(crow) {
    crow.hasSquirrel = false;
    const word = pickWord(this.game.words, "short", this.takenLetters());
    const target = this.aimAt(false);
    if (!word || !target) return;
    this.crows.push({
      kind: "runner", word, typed: 0, slips: 0, called: true,
      x: crow.x, y: crow.y + 6, state: "fly", phase: 0, dir: target.x > crow.x ? 1 : -1,
      fall: true, pumpkin: target, eat: 0, vx: 0, vy: 0,
      snack: this.upgrades.acorns ? this.wordSeconds("short") * 2 : 0,
      el: this.makeLabel("runner"),
    });
  }

  flee(crow, shooed) {
    crow.state = "flee";
    const away = crow.x < FIELD_W / 2 ? -1 : 1;
    if (crow.kind === "runner") {
      crow.vx = 60 * away;
      crow.vy = 0;
    } else {
      crow.vx = 70 * away;
      crow.vy = -55;
    }
    crow.dir = away;
    crow.el.remove();
    if (this.typer.target === crow) this.typer.release();
    if (!shooed) return;
    this.shooed[crow.kind] = (this.shooed[crow.kind] || 0) + 1;
    this.roundPoints += this.pointsFor(crow.kind);
    this.jump = 0.25;
    const shiny = this.crossesSky(crow.kind);
    const colors = shiny ? [C.gold, C.cream] : ["#2b2a33", "#4a4954", C.cream];
    this.scene.burst(crow.x, crow.y, crow.kind === "king" ? 40 : shiny ? 16 : 8, colors, { speed: 30, up: 10, gravity: 30 });
    crow.hasSquirrel = false; // the squirrel hops down and scampers home
    this.growCompost();
    if (crow.kind === "king") this.catchKing(crow);
  }

  // Compost: every few crows shooed, a lost pumpkin grows back.
  growCompost() {
    if (!this.upgrades.compost) return;
    this.compostCount = (this.compostCount || 0) + 1;
    if (this.compostCount % COMPOST_EVERY) return;
    const lost = this.pumpkins.find((p) => p.taken);
    if (!lost) return;
    lost.taken = false;
    this.scene.burst(lost.x, lost.y, 8, [C.grass, C.orange], { speed: 15, up: 12 });
  }

  // Hot Streak: typed crows in a row, no slips. The next one's worth more.
  countStreak(crow) {
    if (!this.upgrades.hot) return;
    if (this.streakHot) {
      const extra = this.pointsFor(crow.kind) * (STREAK_TIMES - 1);
      this.streakBonus += extra;
      this.roundPoints += extra;
      this.streakHot = false;
      this.streak = 0;
      this.say(crow, "TRIPLE!");
      return;
    }
    this.streak += 1;
    if (this.streak >= STREAK) {
      this.streakHot = true;
      this.say(crow, "Hot streak!");
    }
  }

  say(crow, text) {
    const el = document.createElement("div");
    el.className = "crow-bubble";
    el.textContent = text;
    this.shell.els.layer.appendChild(el);
    this.bubbles.push({ el, crow, life: 1.6 });
  }

  // --- King Crow (app/crow_king.py keeps count, so he can't be farmed) ------------

  kingDue() {
    return this.upgrades.king > 0 && !this.kingCame && this.levelIndex === this.levels.length - 1;
  }

  async summonKing() {
    this.kingCame = true;
    const res = await fetch("/api/crow-king/appear", { method: "POST" }).catch(() => null);
    const data = res && res.ok ? await res.json() : null;
    if (!data || !data.ok || this.state !== "play") return;
    this.spawnCrow("king");
    this.spawnCrow("squirrel"); // his guards
    this.spawnCrow("squirrel");
  }

  async catchKing(crow) {
    this.say(crow, "+1 token!");
    const res = await fetch("/api/crow-king/caught", { method: "POST" }).catch(() => null);
    const data = res && res.ok ? await res.json() : null;
    if (data && data.paid && window.Header) Header.celebrateTokens([{ amount: 1, reason: "king_crow" }], data.tokens);
  }

  // --- your pet (the Guard card) ---------------------------------------------------

  readyGuard() {
    if (!this.guard) {
      const el = document.createElement("div");
      el.className = "crow-word kind-guard";
      el.innerHTML = '<span class="crow-word-text"></span>';
      this.shell.els.layer.appendChild(el);
      this.guard = { word: "", typed: 0, slips: 0, called: true, el, dir: 1, phase: 0 };
    }
    Object.assign(this.guard, { state: "ready", x: GUARD_HOME.x, y: GUARD_HOME.y, typed: 0, word: "", shown: -1, chasing: null });
    this.newGuardWord();
  }

  newGuardWord() {
    const taken = new Set(this.flying().map((c) => c.word[0]));
    this.guard.word = pickWord(this.game.words, "long", taken) || pickWord(this.game.words, "medium", taken) || "";
    this.guard.typed = 0;
    this.guard.shown = -1;
  }

  // Who it goes for: whoever's closest to taking a pumpkin. Never the ones crossing the sky.
  guardTarget() {
    const after = this.flying().filter((c) => !this.crossesSky(c.kind));
    return after.sort((a, b) => (b.kind === "runner" ? 1 : b.t) - (a.kind === "runner" ? 1 : a.t))[0] || null;
  }

  sendGuard() {
    this.guard.state = "run";
    this.guard.chasing = this.guardTarget();
    if (this.typer.target === this.guard) this.typer.release();
  }

  moveGuard(dt) {
    const g = this.guard;
    g.phase += dt * 12;
    if (g.state === "ready" && !g.word) this.newGuardWord();
    if (g.state === "run") {
      if (!g.chasing || g.chasing.state !== "fly") g.chasing = this.guardTarget();
      if (!g.chasing) g.state = "back";
      else if (this.runGuardTo(g.chasing.x, dt) <= GUARD_REACH) {
        this.flee(g.chasing, true);
        this.say(g, "Woof!");
        g.state = "back";
      }
    } else if (g.state === "back" && this.runGuardTo(GUARD_HOME.x, dt) <= 1) {
      g.state = "ready";
      this.newGuardWord();
    }
  }

  // Steps toward x; how far is left.
  runGuardTo(x, dt) {
    const g = this.guard;
    const dx = x - g.x;
    g.dir = Math.sign(dx) || g.dir;
    g.x += g.dir * Math.min(Math.abs(dx), GUARD_SPEED * dt);
    return Math.abs(x - g.x);
  }

  stealPumpkin(crow) {
    const kind = CROW_KINDS[crow.kind];
    crow.carry = 0;
    for (let i = 0; i < (kind.steals || 1); i++) {
      const p = i === 0 && !crow.pumpkin.taken ? crow.pumpkin : this.pumpkins.find((q) => !q.taken);
      if (!p) break;
      p.taken = true;
      crow.carry += 1;
      this.lostThisRound += 1;
      this.scene.burst(p.x, p.y, 6, [C.orange, C.gold], { speed: 20, up: 10 });
    }
    crow.state = "steal";
    crow.dir = crow.x < FIELD_W / 2 ? -1 : 1;
    crow.vx = 40 * crow.dir;
    crow.vy = -35;
    crow.el.remove();
    if (this.typer.target === crow) this.typer.release();
  }

  // --- each frame -------------------------------------------------------------

  update(dt) {
    this.jump = Math.max(0, this.jump - dt);
    const playing = this.state === "play";
    for (const c of this.crows) {
      c.phase += dt * 12;
      if (c.state !== "fly") {
        c.x += c.vx * dt;
        c.y += c.vy * dt;
        continue;
      }
      if (!playing) continue; // frozen behind a screen
      if (c.kind === "runner") this.moveRunner(c, dt);
      else this.moveCrow(c, dt);
    }
    this.crows = this.crows.filter((c) => c.state === "fly" || (c.state !== "gone" && c.x > -30 && c.x < FIELD_W + 30 && c.y > -30));

    for (const b of this.bubbles) b.life -= dt;
    for (const b of this.bubbles) if (b.life <= 0) b.el.remove();
    this.bubbles = this.bubbles.filter((b) => b.life > 0);

    if (playing) {
      this.timeLeft -= dt;
      this.spawnIn -= dt;
      if (this.spawnIn <= 0 && this.timeLeft > 4) {
        const regular = this.flying().filter((c) => !c.friend && c.kind !== "runner" && c.kind !== "king").length;
        if (regular < this.level.max_crows + this.upgrades.whistle) this.spawnCrow(this.pickKind());
        this.spawnIn = Math.max(this.level.spawn, this.wordSeconds("medium") * 0.9) * (this.upgrades.whistle ? WHISTLE_SPAWN : 1);
      }
      if (this.kingDue() && this.timeLeft <= this.roundSeconds / 2) this.summonKing();
      if (this.guard) this.moveGuard(dt);
      if (this.timeLeft <= 0 || this.pumpkins.every((p) => p.taken)) this.endRound();
      this.renderHud();
    }
    this.placeLabels();
  }

  moveCrow(c, dt) {
    const kind = CROW_KINDS[c.kind];
    c.t += dt / c.dur;
    const k = Math.min(1, c.t);
    const across = this.crossesSky(c.kind);
    const tx = across ? c.tx : c.pumpkin.x + 2;
    const ty = across ? c.ty : c.pumpkin.y - 6 * kind.size;
    c.x = lerp(c.sx, tx, k);
    c.y = lerp(c.sy, ty, k) + Math.sin(c.phase / 3) * 2 * (1 - k);
    c.dir = tx >= c.sx ? 1 : -1;

    if (kind.callEvery && c.calls < MAX_CALLS) {
      c.callIn -= dt;
      if (c.callIn <= 0) {
        c.calls += 1;
        c.callIn = this.callEvery(kind);
        this.callFriend(c, "CAW CAW!");
      }
    }
    if (c.hasSquirrel && c.t >= 0.7) this.dropSquirrel(c);

    if (c.t < 1) return;
    if (across) {
      c.state = "gone"; // got away
      c.el.remove();
      if (this.typer.target === c) this.typer.release();
    } else if (c.pumpkin.fake && !c.pumpkin.taken) {
      // it's fake! off to a real one, and that's the time you've bought
      c.pumpkin.taken = true;
      this.scene.burst(c.x, c.y, 8, [C.cream, "#c8c2a8"], { speed: 25, up: 12 });
      const next = this.aimAt();
      if (!next) return this.flee(c, false);
      c.pumpkin = next;
      c.sx = c.x;
      c.sy = c.y;
      c.t = 0;
      c.dur *= 0.5;
    } else if (!c.pumpkin.taken) {
      this.stealPumpkin(c);
    } else {
      // someone beat it there: pick another
      const next = this.aimAt();
      if (!next) return this.flee(c, false);
      c.pumpkin = next;
      c.sx = c.x;
      c.sy = c.y;
      c.t = 0.6;
    }
  }

  // A dropped squirrel falls, scampers to a pumpkin, and eats it.
  moveRunner(c, dt) {
    if (c.fall) {
      c.y += 60 * dt;
      if (c.y >= c.pumpkin.y + 2) {
        c.y = c.pumpkin.y + 2;
        c.fall = false;
      }
      return;
    }
    if (c.snack > 0) {
      c.snack -= dt; // an acorn first
      return;
    }
    if (c.pumpkin.taken) {
      const next = this.aimAt(false);
      if (!next) return this.flee(c, false);
      c.pumpkin = next;
      c.eat = 0;
    }
    const goal = c.pumpkin.x + (c.x < c.pumpkin.x ? -7 : 7);
    const dx = goal - c.x;
    if (Math.abs(dx) > 1) {
      c.dir = Math.sign(dx);
      // about two words' time to cross the patch
      c.x += c.dir * Math.min(Math.abs(dx), (70 / (this.wordSeconds("short") * 2)) * dt);
      c.y = lerp(c.y, c.pumpkin.y + 2, 0.1);
      return;
    }
    c.dir = Math.sign(c.pumpkin.x - c.x) || 1;
    c.eat += dt;
    if (c.eat >= 1.5) {
      c.pumpkin.taken = true;
      this.lostThisRound += 1;
      this.scene.burst(c.pumpkin.x, c.pumpkin.y, 6, [C.orange, C.gold], { speed: 20, up: 10 });
      c.state = "steal";
      c.vx = c.x < FIELD_W / 2 ? -50 : 50;
      c.vy = 0;
      c.el.remove();
      if (this.typer.target === c) this.typer.release();
    }
  }

  placeLabels() {
    const W = this.shell.els.layer.clientWidth;
    const H = this.shell.els.layer.clientHeight;
    for (const c of this.crows) {
      if (c.state !== "fly") continue;
      if (c.shown !== c.typed) {
        c.el.querySelector(".crow-word-text").innerHTML = wordHtml(c.word, c.typed);
        c.shown = c.typed;
      }
      c.el.classList.toggle("locked", this.typer.target === c);
      const above = c.kind === "runner" ? 6 : 7 * CROW_KINDS[c.kind].size + 2;
      placeInside(c.el, (c.x / FIELD_W) * W, ((c.y - above) / FIELD_H) * H, W, H);
      if (c.kind === "caller") {
        const left = c.calls >= MAX_CALLS ? 0 : c.callIn / this.callEvery(CROW_KINDS.caller);
        c.el.querySelector(".call-timer span").style.width = `${left * 100}%`;
      }
    }
    if (this.guard) {
      const g = this.guard;
      const shown = this.state === "play" && g.state === "ready" && g.word;
      g.el.style.display = shown ? "" : "none";
      if (shown) {
        if (g.shown !== g.typed) {
          g.el.querySelector(".crow-word-text").innerHTML = wordHtml(g.word, g.typed);
          g.shown = g.typed;
        }
        g.el.classList.toggle("locked", this.typer.target === g);
        placeInside(g.el, (g.x / FIELD_W) * W, ((g.y - 14) / FIELD_H) * H, W, H);
      }
    }
    for (const b of this.bubbles) {
      placeInside(b.el, (b.crow.x / FIELD_W) * W, ((b.crow.y - 22) / FIELD_H) * H, W, H);
    }
  }

  renderHud() {
    const left = this.pumpkins.filter((p) => !p.taken).length;
    const secs = Math.max(0, Math.ceil(this.timeLeft));
    const score = this.shell.total + this.roundPoints;
    const bell = this.upgrades.bell ? ` · Bell ${keycap(" ")} ×${this.bellLeft}` : "";
    const streak = this.upgrades.hot ? ` · ${this.streakHot ? "Next crow ×3!" : `Streak ${this.streak}/${STREAK}`}` : "";
    this.shell.els.hud.innerHTML =
      `<span>Pumpkins ${left}</span><span>Score <b class="game-score">${score.toLocaleString()}</b>${bell}${streak}</span>` +
      `<span>${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}</span>`;
  }

  // --- drawing ----------------------------------------------------------------

  draw(s) {
    const sky = SKIES[Math.min(this.levelIndex, SKIES.length - 1)];
    const night = this.levelIndex >= SKIES.length - 1;
    const rain = this.upgrades.rainy > 0;
    s.bands(smoothSky(rain && !night ? ["#9aa6b0", "#b4bec6", "#c4ccd2"] : sky, 12), 0, 74);
    if (rain) {
      for (const [x, w] of [[40, 34], [120, 44], [195, 30]]) s.oval(x, 12, w, 7, night ? "#3a3f5a" : "#7e8a96");
    } else if (night) {
      s.disc(200, 18, 7, C.cream);
      s.disc(203, 16, 6, mixColor(sky[0], sky[1], 0.15));
      for (let i = 0; i < 12; i++) s.rect((i * 53) % 230 + 5, (i * 17) % 50 + 4, 1, 1, C.cream);
    } else {
      const sunX = 30 + this.levelIndex * 45;
      const sunY = 20 + Math.abs(this.levelIndex - 1.5) * 8;
      if (this.upgrades.sunny) for (let i = 0; i < 8; i++) s.rect(sunX + Math.cos(i * 0.785) * 11, sunY + Math.sin(i * 0.785) * 11, 2, 2, C.gold);
      s.disc(sunX, sunY, 7, C.gold);
    }
    s.oval(60, 76, 70, 10, night ? "#3a4a3a" : "#8fb36b");
    s.oval(190, 77, 80, 9, night ? "#34442f" : "#7ea35c");
    s.rect(0, 74, FIELD_W, 46, night ? "#4a6627" : C.grass);
    // back fence
    for (let x = 4; x < FIELD_W; x += 12) s.rect(x, 70, 2, 10, C.woodDark);
    s.rect(0, 73, FIELD_W, 1, C.wood);
    s.rect(0, 77, FIELD_W, 1, C.wood);
    // the patch
    s.rect(80, 86, 156, 26, C.soil);
    for (let y = 89; y < 112; y += 5) s.rect(82, y, 152, 1, C.soilDark);
    for (const p of this.pumpkins) this.drawPumpkin(s, p);
    if (this.decoy && !this.decoy.taken) {
      s.oval(this.decoy.x, this.decoy.y, 6, 4, "#d8d2b8"); // straw, painted to look like a pumpkin
      s.rect(this.decoy.x - 2, this.decoy.y - 3, 1, 7, "#b4ac8c");
      s.rect(this.decoy.x + 2, this.decoy.y - 3, 1, 7, "#b4ac8c");
    }
    if (this.upgrades.compost) {
      s.oval(14, 113, 7, 4, C.soilDark);
      s.oval(14, 111, 5, 3, C.soil);
      s.rect(12, 108, 2, 2, C.grass);
    }
    if (this.upgrades.fence) {
      for (let x = 78; x < 238; x += 8) s.rect(x, 108, 2, 8, C.cream);
      s.rect(78, 111, 160, 1, C.cream);
    }
    if (this.upgrades.scarecrow) this.drawScarecrow(s, 66, 80);
    if (this.upgrades.bell) {
      s.rect(56, 82, 2, 30, C.woodDark);
      s.rect(52, 82, 10, 2, C.woodDark);
      s.disc(54, 88, 3, this.bellLeft ? C.gold : C.grey);
    }
    // the avatar, by the patch
    const ox = 8;
    const oy = 70 - (this.jump > 0 ? 3 : 0);
    if (this.avatar) {
      // your guard runs about on its own, so it isn't also drawn at your feet
      const worn = this.guard ? { ...this.avatar, pets: (this.avatar.pets || []).filter((p) => p.id !== this.game.helper.id) } : this.avatar;
      paintAvatar((x, y, w, h, c) => s.rect(ox + x, oy + y, w, h, c), worn, {
        background: false,
        frame: Math.floor(s.t * 2) % 2,
      });
    }
    if (this.guard) this.drawGuard(s);
    for (const c of this.crows) {
      if (c.kind === "runner") {
        if (c.snack > 0 && !c.fall) s.rect(c.x + c.dir * 5, c.y - 2, 2, 2, "#8a5a2c"); // the acorn
        this.drawSquirrel(s, c.x, c.y, c.dir, c.phase, c.eat > 0 || c.snack > 0);
      } else this.drawCrow(s, c);
    }
    if (rain) {
      for (let i = 0; i < 40; i++) {
        const x = (i * 37 + s.t * 40) % FIELD_W;
        const y = (i * 23 + s.t * 150) % FIELD_H;
        s.rect(x, y, 1, 3, "rgba(190, 215, 235, 0.65)");
      }
    }
  }

  drawGuard(s) {
    const g = this.guard;
    const pet = this.game.helper;
    const genes = petOnLand(pet.genes);
    const scale = ALONG_PET_SCALE;
    const hop = g.state === "ready" ? 0 : Math.floor(g.phase / 2) % 2;
    drawPet((x, y, w, h, c) => s.rect(x, y, w, h, c), g.x - (petSize(genes, pet.growth).w * scale) / 2, g.y - hop, genes, pet.growth, {
      faceLeft: g.dir < 0, scale, frame: Math.floor(g.phase / 3) % 2,
    });
  }

  drawPumpkin(s, p) {
    if (p.taken) {
      s.rect(p.x - 1, p.y + 2, 3, 1, C.soilDark); // an empty spot
      return;
    }
    s.oval(p.x, p.y, 6, 4, C.orange);
    s.rect(p.x - 2, p.y - 3, 1, 7, "#b8651f");
    s.rect(p.x + 2, p.y - 3, 1, 7, "#b8651f");
    s.rect(p.x, p.y - 6, 1, 3, C.grassDark);
    s.rect(p.x + 1, p.y - 6, 2, 1, C.grass);
  }

  drawScarecrow(s, x, y) {
    s.rect(x, y, 2, 32, C.woodDark);
    s.rect(x - 8, y + 8, 18, 2, C.woodDark);
    s.rect(x - 4, y + 7, 10, 10, "#b8432f");
    s.disc(x + 1, y + 3, 4, "#e8c57a");
    s.rect(x - 4, y - 2, 11, 2, C.wood);
    s.rect(x - 2, y - 5, 7, 3, C.wood);
  }

  // Facing `dir` (1 right, -1 left); `eating` bobs its head down.
  drawSquirrel(s, x, y, dir, phase, eating) {
    const fur = "#a0602c";
    const hop = eating ? 0 : Math.floor(phase / 2) % 2;
    const head = eating ? 2 : 0;
    s.oval(x, y - 2 - hop, 3, 2, fur);
    s.disc(x + dir * 3, y - 4 - hop + head, 2, fur);
    s.rect(x + dir * 4, y - 5 - hop + head, 1, 1, C.ink);
    s.oval(x - dir * 4, y - 6 - hop, 2, 4, "#c47a3c"); // tail
  }

  // Works on any Scene (the field, or the intro card's icon).
  drawCrow(s, c) {
    const kind = CROW_KINDS[c.kind];
    const z = kind.size;
    const ink = kind.color;
    const wing = c.kind === "golden" || c.kind === "king" ? "#f0c640" : mixColor(ink, "#ffffff", 0.15);
    const { x, y, dir: d } = c;
    const up = Math.floor(c.phase) % 2;
    if (c.hasSquirrel) this.drawSquirrel(s, x, y + 7 * z, d, 0, false);
    s.oval(x, y, Math.round(5 * z), Math.max(2, Math.round(3 * z)), ink);
    s.disc(x + d * 5 * z, y - 2 * z, Math.max(1, Math.round(2 * z)), ink);
    s.rect(x + d * (5 * z + 2) + (d < 0 ? -1 : 0), y - 2 * z, Math.round(2 * z), 1, C.gold); // beak
    s.rect(x + d * 5 * z, y - 3 * z, 1, 1, C.white); // eye
    s.rect(x - d * 6 * z + (d > 0 ? -2 : 0), y - 1, Math.round(3 * z), 2, ink); // tail
    if (up) s.rect(x - 2 * z, y - 7 * z, 4 * z, 5 * z, wing);
    else s.rect(x - 2 * z, y + 2, 4 * z, 4 * z, wing);
    if (c.kind === "caller") s.rect(x + d * 3 * z - 1, y + 1, 3, 2, C.red); // scarf
    if (c.kind === "king") {
      // his crown
      const cx = x + d * 5 * z - 4;
      const cy = y - 2 * z - 7;
      s.rect(cx, cy + 2, 9, 3, "#ffe27a");
      for (const dx of [0, 4, 8]) s.rect(cx + dx, cy, 1, 2, "#ffe27a");
      s.rect(cx + 4, cy + 3, 1, 1, C.red);
    }
    if (c.state === "steal") for (let i = 0; i < (c.carry || 1); i++) this.drawPumpkin(s, { x: x + i * 6 - 3, y: y + 7 * z });
  }

  // --- keys -------------------------------------------------------------------

  targets() {
    if (this.state === "choose") return this.choices;
    if (this.state === "play") {
      const ready = this.guard && this.guard.state === "ready" && this.guard.word;
      return ready ? [...this.flying(), this.guard] : this.flying();
    }
    return [];
  }

  handleKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (this.state !== "choose" && this.state !== "play") {
      this.shell.screenKey(e);
      if (e.key === " ") e.preventDefault();
      return;
    }
    if (e.key === "Escape" || e.key === "Backspace") {
      e.preventDefault();
      this.typer.release();
      if (this.state === "choose") this.renderChoices();
      for (const c of this.crows) c.shown = -1;
      if (this.guard) this.guard.shown = -1;
      return;
    }
    if (e.key.length !== 1) return;
    e.preventDefault();
    if (e.repeat) return;
    if (e.key === " ") {
      if (this.state === "play" && this.bellLeft > 0) this.ringBell();
      return;
    }
    const r = this.typer.press(e.key, this.targets());
    if (this.state === "choose") {
      if (r.kind === "done") this.takeUpgrade(r.target);
      else this.renderChoices();
      return;
    }
    if (r.kind === "done") {
      if (r.target === this.guard) {
        this.sendGuard();
      } else {
        this.flee(r.target, true);
        this.countStreak(r.target);
      }
      this.renderHud();
    } else if (r.kind === "slip") {
      const c = r.target;
      this.streak = 0;
      this.streakHot = false;
      c.el.classList.remove("slip");
      void c.el.offsetWidth; // restart the shake
      c.el.classList.add("slip");
      if (!c.called && !this.upgrades.calm) {
        c.called = true;
        this.callFriend(c, "CAW! Help!");
      }
    }
  }

  ringBell() {
    this.bellLeft -= 1;
    this.scene.burst(54, 88, 12, [C.gold, C.cream], { speed: 40, up: 10, gravity: 0, life: 0.6 });
    for (const c of this.flying()) if (c.kind !== "king") this.flee(c, true); // him, you have to type
    this.renderHud();
  }
}

// Puts a label (centered on x, bottom at y) where the crow is, but always
// whole inside the W x H field: a long word from the edge isn't cut off.
function placeInside(el, x, y, W, H) {
  const pad = 4;
  const w = el.offsetWidth;
  const h = el.offsetHeight;
  el.style.left = `${Math.min(W - w / 2 - pad, Math.max(w / 2 + pad, x))}px`;
  el.style.top = `${Math.min(H - pad, Math.max(h + pad, y))}px`;
}

GAMES.crow_patrol = (shell, content, me) => new CrowPatrol(shell, content, me && me.avatar);
