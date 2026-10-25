// Crow Patrol (game_crow_patrol_v1): crows fly at your pumpkin patch from
// every side, each carrying a word. Type a crow's word to shoo it.
//
// Crow kinds (each round brings in a new one, see app/activities/game_modules.py):
//   little   fast, short word                     caller   calls a friend when its timer runs out
//   crow     medium speed and word                squirrel drops a squirrel over the patch
//   big      slow, long word, takes 2 pumpkins    golden   ignores pumpkins; 100 points if you catch it
// The first slip on a crow makes it squawk for a friend (one per crow).
//
// Each round starts with a full patch and ends when time runs out or the
// pumpkins are all gone. Then the arcade tally: crows by kind, pumpkins saved
// (100 each, 250 with pie), and a bonus for a perfect patch. Then pick an
// upgrade by typing its word.
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
  golden: { name: "Golden crow", about: "Doesn't want pumpkins. Catch it before it flies off: 100 points!", words: "long", speed: 1, size: 1, points: 100, color: "#d9a520" },
  runner: { name: "Squirrel", about: "", words: "short", points: 10 },
};

const SKIES = [
  ["#f6d8b0", "#cfe8ef", "#a8d5e2"], // morning
  ["#cfe8ef", "#a8d5e2", "#8fc3d6"], // midday
  ["#f3d9a4", "#cfe8ef", "#a8d5e2"], // afternoon
  ["#e8a06b", "#f3c27a", "#f6d8b0"], // sunset
  ["#1d2340", "#2f3a63", "#4a4f7a"], // moonrise
];

const UPGRADES = {
  scarecrow: { name: "Scarecrow", text: "Crows fly slower." },
  fence: { name: "Fence", text: "2 more pumpkins every round." },
  bell: { name: "Bell", text: "Press [Space] once a round to shoo every crow." },
  pie: { name: "Pumpkin pie", text: "Pumpkins you save are worth 250, not 100." },
};

class CrowPatrol {
  constructor(shell, content, avatar) {
    this.shell = shell;
    this.game = content.game;
    this.avatar = avatar;
    this.levels = this.game.levels;
    this.typer = new Typer();
    this.levelIndex = 0;
    this.upgrades = { scarecrow: 0, fence: 0, bell: 0, pie: 0 };
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
         <div>${isNew ? `<span class="new-tag">NEW!</span> ` : ""}<b>${kind.name}</b> · ${kind.points} points<br>${escapeHtml(kind.about)}</div>
       </div>
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

  resetRound() {
    this.timeLeft = this.level.seconds;
    this.spawnIn = 1;
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
      .filter((k) => this.shooed[k])
      .map((k) => ({ label: `${CROW_KINDS[k].name}s shooed`, count: this.shooed[k], each: CROW_KINDS[k].points }));
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

  chooseUpgrade() {
    const names = Object.keys(UPGRADES).filter((n) => n !== "pie" || !this.upgrades.pie);
    const offer = names.sort(() => Math.random() - 0.5).slice(0, 3);
    const words = pickWords(this.game.words, offer.map(() => "short"));
    this.choices = offer.map((id, i) => ({ id, word: words[i], typed: 0 }));
    this.state = "choose";
    this.shell.showScreen(
      `<h2>Pick an upgrade</h2>
       <p>Type its word.</p>
       <div class="choice-cards">${this.choices
         .map(
           (c, i) => `<div class="choice-card" data-i="${i}">
             <h3>${UPGRADES[c.id].name}</h3>
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
    return new Set(this.flying().map((c) => c.word[0]));
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
    const word = pickWord(this.game.words, kind.words, this.takenLetters());
    if (!word) return null;
    const start = this.entryPoint();
    const slow = Math.pow(0.85, this.upgrades.scarecrow);
    const speed = this.level.speed * kind.speed * slow;
    const crow = {
      kind: kindId, word, typed: 0, slips: 0, friend,
      x: start.x, y: start.y, sx: start.x, sy: start.y, t: 0,
      state: "fly", vx: 0, vy: 0, dir: -1, phase: Math.random() * 6,
      called: friend, calls: 0, callIn: kind.callEvery || 0,
      hasSquirrel: kindId === "squirrel",
    };
    if (kindId === "golden") {
      // straight across the sky, not after pumpkins
      const fromLeft = Math.random() < 0.5;
      crow.sx = crow.x = fromLeft ? -10 : FIELD_W + 10;
      crow.sy = crow.y = 12 + Math.random() * 14;
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

  // A pumpkin nobody's after yet, if there is one.
  aimAt() {
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
    const target = this.aimAt();
    if (!word || !target) return;
    this.crows.push({
      kind: "runner", word, typed: 0, slips: 0, called: true,
      x: crow.x, y: crow.y + 6, state: "fly", phase: 0, dir: target.x > crow.x ? 1 : -1,
      fall: true, pumpkin: target, eat: 0, vx: 0, vy: 0,
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
    this.roundPoints += CROW_KINDS[crow.kind].points;
    this.jump = 0.25;
    const colors = crow.kind === "golden" ? [C.gold, C.cream] : ["#2b2a33", "#4a4954", C.cream];
    this.scene.burst(crow.x, crow.y, crow.kind === "golden" ? 16 : 8, colors, { speed: 30, up: 10, gravity: 30 });
    crow.hasSquirrel = false; // the squirrel hops down and scampers home
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
        const regular = this.flying().filter((c) => !c.friend && c.kind !== "runner").length;
        if (regular < this.level.max_crows) this.spawnCrow(this.pickKind());
        this.spawnIn = Math.max(this.level.spawn, this.wordSeconds("medium") * 0.9);
      }
      if (this.timeLeft <= 0 || this.pumpkins.every((p) => p.taken)) this.endRound();
      this.renderHud();
    }
    this.placeLabels();
  }

  moveCrow(c, dt) {
    const kind = CROW_KINDS[c.kind];
    c.t += dt / c.dur;
    const k = Math.min(1, c.t);
    const tx = c.kind === "golden" ? c.tx : c.pumpkin.x + 2;
    const ty = c.kind === "golden" ? c.ty : c.pumpkin.y - 6 * kind.size;
    c.x = lerp(c.sx, tx, k);
    c.y = lerp(c.sy, ty, k) + Math.sin(c.phase / 3) * 2 * (1 - k);
    c.dir = tx >= c.sx ? 1 : -1;

    if (kind.callEvery && c.calls < MAX_CALLS) {
      c.callIn -= dt;
      if (c.callIn <= 0) {
        c.calls += 1;
        c.callIn = kind.callEvery;
        this.callFriend(c, "CAW CAW!");
      }
    }
    if (c.hasSquirrel && c.t >= 0.7) this.dropSquirrel(c);

    if (c.t < 1) return;
    if (c.kind === "golden") {
      c.state = "gone"; // got away
      c.el.remove();
      if (this.typer.target === c) this.typer.release();
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
    if (c.pumpkin.taken) {
      const next = this.aimAt();
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
    for (const c of this.crows) {
      if (c.state !== "fly") continue;
      if (c.shown !== c.typed) {
        c.el.querySelector(".crow-word-text").innerHTML = wordHtml(c.word, c.typed);
        c.shown = c.typed;
      }
      c.el.classList.toggle("locked", this.typer.target === c);
      // keep the word on screen while the crow flies in from an edge
      c.el.style.left = `${Math.min(92, Math.max(6, (c.x / FIELD_W) * 100))}%`;
      const above = c.kind === "runner" ? 6 : 7 * CROW_KINDS[c.kind].size + 2;
      c.el.style.top = `${Math.max(9, ((c.y - above) / FIELD_H) * 100)}%`;
      if (c.kind === "caller") {
        const left = c.calls >= MAX_CALLS ? 0 : c.callIn / CROW_KINDS.caller.callEvery;
        c.el.querySelector(".call-timer span").style.width = `${left * 100}%`;
      }
    }
    for (const b of this.bubbles) {
      b.el.style.left = `${Math.min(88, Math.max(10, (b.crow.x / FIELD_W) * 100))}%`;
      b.el.style.top = `${Math.max(0, ((b.crow.y - 22) / FIELD_H) * 100)}%`;
    }
  }

  renderHud() {
    const left = this.pumpkins.filter((p) => !p.taken).length;
    const secs = Math.max(0, Math.ceil(this.timeLeft));
    const score = this.shell.total + this.roundPoints;
    const bell = this.upgrades.bell ? ` · Bell ${keycap(" ")} ×${this.bellLeft}` : "";
    this.shell.els.hud.innerHTML =
      `<span>Pumpkins ${left}</span><span>Score <b class="game-score">${score.toLocaleString()}</b>${bell}</span>` +
      `<span>${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}</span>`;
  }

  // --- drawing ----------------------------------------------------------------

  draw(s) {
    const sky = SKIES[Math.min(this.levelIndex, SKIES.length - 1)];
    const night = this.levelIndex >= SKIES.length - 1;
    s.bands(smoothSky(sky, 12), 0, 74);
    if (night) {
      s.disc(200, 18, 7, C.cream);
      s.disc(203, 16, 6, mixColor(sky[0], sky[1], 0.15));
      for (let i = 0; i < 12; i++) s.rect((i * 53) % 230 + 5, (i * 17) % 50 + 4, 1, 1, C.cream);
    } else {
      s.disc(30 + this.levelIndex * 45, 20 + Math.abs(this.levelIndex - 1.5) * 8, 7, C.gold);
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
      paintAvatar((x, y, w, h, c) => s.rect(ox + x, oy + y, w, h, c), this.avatar, {
        background: false,
        frame: Math.floor(s.t * 2) % 2,
      });
    }
    for (const c of this.crows) {
      if (c.kind === "runner") this.drawSquirrel(s, c.x, c.y, c.dir, c.phase, c.eat > 0);
      else this.drawCrow(s, c);
    }
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
    const wing = c.kind === "golden" ? "#f0c640" : mixColor(ink, "#ffffff", 0.15);
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
    if (c.state === "steal") for (let i = 0; i < (c.carry || 1); i++) this.drawPumpkin(s, { x: x + i * 6 - 3, y: y + 7 * z });
  }

  // --- keys -------------------------------------------------------------------

  targets() {
    if (this.state === "choose") return this.choices;
    if (this.state === "play") return this.flying();
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
      this.flee(r.target, true);
      this.renderHud();
    } else if (r.kind === "slip") {
      const c = r.target;
      c.el.classList.remove("slip");
      void c.el.offsetWidth; // restart the shake
      c.el.classList.add("slip");
      if (!c.called) {
        c.called = true;
        this.callFriend(c, "CAW! Help!");
      }
    }
  }

  ringBell() {
    this.bellLeft -= 1;
    this.scene.burst(54, 88, 12, [C.gold, C.cream], { speed: 40, up: 10, gravity: 0, life: 0.6 });
    for (const c of this.flying()) this.flee(c, true);
    this.renderHud();
  }
}

GAMES.crow_patrol = (shell, content, me) => new CrowPatrol(shell, content, me && me.avatar);
