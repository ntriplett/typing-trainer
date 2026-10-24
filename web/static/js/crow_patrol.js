// Crow Patrol (game_crow_patrol_v1): crows fly at your pumpkin patch, each
// carrying a word. Type a crow's word to shoo it. A crow that reaches a
// pumpkin flies off with it. Lose every pumpkin and the patch grows back for
// another try (a little slower). Between levels you pick an upgrade by
// typing its word. Score = crows shooed (plus pie bonuses).
//
// Pacing comes from the learner's typing speed (content.game.chars_per_second),
// so a slow typer gets slower crows, not a harder game.
//
// Needs practice_scenes.js (Scene, C), avatar.js, and game_kit.js loaded first.

const FIELD_W = 240;
const FIELD_H = 120;
const START_PUMPKINS = 5;
const MAX_GAME_SECONDS = 9 * 60; // stop after this even if levels are left
const RETRY_EASE = 0.85; // each lost try slows the crows this much

const SKIES = [
  ["#f6d8b0", "#cfe8ef", "#a8d5e2"], // morning
  ["#cfe8ef", "#a8d5e2", "#8fc3d6"], // midday
  ["#f3d9a4", "#cfe8ef", "#a8d5e2"], // afternoon
  ["#e8a06b", "#f3c27a", "#f6d8b0"], // sunset
  ["#1d2340", "#2f3a63", "#4a4f7a"], // moonrise
];
const AVG_WORD_LEN = { short: 2.5, medium: 4.5, mixed: 3.5 };

const UPGRADES = {
  scarecrow: { name: "Scarecrow", text: "Crows fly slower." },
  fence: { name: "Fence", text: "2 more pumpkins every level." },
  bell: { name: "Bell", text: "Press [Space] once a level to shoo every crow." },
  pie: { name: "Pumpkin pie", text: "Every pumpkin you save counts as a crow shooed." },
};

class CrowPatrol {
  constructor(shell, content, avatar) {
    this.shell = shell;
    this.game = content.game;
    this.avatar = avatar;
    this.levels = this.game.levels;
    this.typer = new Typer();
    this.levelIndex = 0;
    this.successes = 0;
    this.upgrades = { scarecrow: 0, fence: 0, bell: 0, pie: 0 };
    this.ease = 1;
    this.playSeconds = 0;
    this.crows = [];
    this.state = "intro"; // intro | play | between | choose | lost | over
    this.choices = [];
    this.jump = 0;

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
    this.renderHud();
    this.introScreen();
    window.addEventListener("keydown", (e) => this.handleKey(e));
  }

  get level() {
    return this.levels[this.levelIndex];
  }

  // --- flow -----------------------------------------------------------------

  introScreen() {
    this.shell.setLabel(`Game · Level ${this.levelIndex + 1} of ${this.levels.length}`);
    this.shell.showScreen(
      `<h2>${escapeHtml(this.level.name)}</h2>
       <p>Type the word on a crow to shoo it away.</p>
       <p>Press ${keycap(" ")} to start.</p>`,
      { " ": () => this.startLevel() }
    );
  }

  startLevel() {
    this.shell.hideScreen();
    this.state = "play";
    this.timeLeft = this.level.seconds;
    this.spawnIn = 1;
    this.shooedThisLevel = 0;
    this.bellLeft = this.upgrades.bell;
    this.typer.release();
  }

  resetPatch() {
    const count = START_PUMPKINS + 2 * this.upgrades.fence;
    this.pumpkins = Array.from({ length: count }, (_, i) => ({
      x: 92 + (i * 136) / Math.max(1, count - 1) * 0.98,
      y: i % 2 ? 104 : 94,
      taken: false,
    }));
  }

  endLevel() {
    this.state = "between";
    this.typer.release();
    for (const c of this.crows) if (c.state === "fly") this.flee(c, false);
    const saved = this.pumpkins.filter((p) => !p.taken).length;
    const pie = this.upgrades.pie ? saved : 0;
    this.successes += pie;
    this.renderHud();
    const last = this.levelIndex >= this.levels.length - 1 || this.playSeconds >= MAX_GAME_SECONDS;
    const pieLine = pie ? `<p>Pumpkin pie: +${pie}!</p>` : "";
    this.shell.showScreen(
      `<h2>${escapeHtml(this.level.name)} done!</h2>
       <p>You shooed ${this.shooedThisLevel} crows and saved ${saved} pumpkins.</p>${pieLine}
       <p>Press ${keycap(" ")} to ${last ? "finish" : "go on"}.</p>`,
      { " ": () => (last ? this.gameOver() : this.chooseUpgrade()) }
    );
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
    this.renderHud();
    this.introScreen();
    this.state = "intro";
  }

  lostPatch() {
    this.state = "lost";
    this.typer.release();
    for (const c of this.crows) if (c.state === "fly") this.flee(c, false);
    this.ease *= RETRY_EASE;
    this.shell.showScreen(
      `<h2>The crows got every pumpkin!</h2>
       <p>The patch grows back. Your score stays.</p>
       <p>Press ${keycap(" ")} to try ${escapeHtml(this.level.name)} again.</p>`,
      {
        " ": () => {
          this.resetPatch();
          this.startLevel();
        },
      }
    );
  }

  gameOver() {
    this.state = "over";
    this.shell.finish({
      successes: this.successes,
      line: `You shooed ${this.successes} crows!`,
      keystrokes: this.typer.keystrokes,
    });
  }

  // --- crows ------------------------------------------------------------------

  // How long a word takes this learner, in seconds (with time to read it).
  wordSeconds() {
    const cps = Math.max(0.5, this.game.chars_per_second || 1.5);
    return (AVG_WORD_LEN[this.level.words] || 3.5) / cps + 1.2;
  }

  spawnCrow() {
    const flying = this.crows.filter((c) => c.state === "fly");
    const word = pickWord(this.game.words, this.level.words, new Set(flying.map((c) => c.word[0])));
    const free = this.pumpkins.filter((p) => !p.taken);
    if (!word || !free.length) return;
    const aimed = new Set(flying.map((c) => c.pumpkin));
    const open = free.filter((p) => !aimed.has(p));
    const pumpkin = (open.length ? open : free)[Math.floor(Math.random() * (open.length || free.length))];
    const slow = Math.pow(0.85, this.upgrades.scarecrow) * this.ease;
    const el = document.createElement("div");
    el.className = "crow-word";
    this.shell.els.layer.appendChild(el);
    this.crows.push({
      word, typed: 0, slips: 0, el, shown: -1,
      sx: FIELD_W + 8, sy: 12 + Math.random() * 36,
      x: FIELD_W + 8, y: 30,
      pumpkin, t: 0,
      dur: (this.wordSeconds() * 3 + 4) / (this.level.speed * slow),
      state: "fly", vx: 0, vy: 0, dir: -1, phase: Math.random() * 6,
    });
  }

  flee(crow, shooed) {
    crow.state = "flee";
    crow.vx = 70;
    crow.vy = -55;
    crow.dir = 1;
    crow.el.remove();
    if (this.typer.target === crow) this.typer.release();
    if (shooed) {
      this.successes += 1;
      this.shooedThisLevel += 1;
      this.jump = 0.25;
      this.scene.burst(crow.x, crow.y, 8, ["#2b2a33", "#4a4954", C.cream], { speed: 30, up: 10, gravity: 30 });
    }
  }

  // --- each frame -------------------------------------------------------------

  update(dt, scene) {
    this.jump = Math.max(0, this.jump - dt);
    for (const c of this.crows) {
      c.phase += dt * 12;
      if (c.state === "fly") {
        if (this.state !== "play") continue; // frozen behind a screen
        c.t += dt / c.dur;
        const k = Math.min(1, c.t);
        c.x = lerp(c.sx, c.pumpkin.x + 2, k);
        c.y = lerp(c.sy, c.pumpkin.y - 6, k) + Math.sin(c.phase / 3) * 2 * (1 - k);
        if (c.t >= 1 && !c.pumpkin.taken) {
          c.pumpkin.taken = true;
          c.state = "steal";
          c.vx = 40;
          c.vy = -35;
          c.dir = 1;
          c.el.remove();
          if (this.typer.target === c) this.typer.release();
          scene.burst(c.x, c.y + 4, 6, [C.orange, C.gold], { speed: 20, up: 10 });
          if (this.pumpkins.every((p) => p.taken)) this.lostPatch();
        } else if (c.t >= 1) {
          c.pumpkin = this.pumpkins.find((p) => !p.taken) || c.pumpkin; // someone beat it there
          c.sx = c.x;
          c.sy = c.y;
          c.t = 0.6;
        }
      } else {
        c.x += c.vx * dt;
        c.y += c.vy * dt;
      }
    }
    this.crows = this.crows.filter((c) => c.state === "fly" || (c.x < FIELD_W + 20 && c.y > -20));

    if (this.state === "play") {
      this.playSeconds += dt;
      this.timeLeft -= dt;
      this.spawnIn -= dt;
      const flying = this.crows.filter((c) => c.state === "fly").length;
      if (this.spawnIn <= 0 && this.timeLeft > 4) {
        if (flying < this.level.max_crows) this.spawnCrow();
        this.spawnIn = Math.max(this.level.spawn, this.wordSeconds() * 0.9) / this.ease;
      }
      if (this.timeLeft <= 0) this.endLevel();
      this.renderHud();
    }
    this.placeLabels();
  }

  placeLabels() {
    for (const c of this.crows) {
      if (c.state !== "fly") continue;
      if (c.shown !== c.typed) {
        c.el.innerHTML = wordHtml(c.word, c.typed);
        c.shown = c.typed;
      }
      c.el.classList.toggle("locked", this.typer.target === c);
      // keep the word on screen while the crow flies in from the edge
      c.el.style.left = `${Math.min(92, Math.max(6, (c.x / FIELD_W) * 100))}%`;
      c.el.style.top = `${((c.y - 7) / FIELD_H) * 100}%`;
    }
  }

  renderHud() {
    const left = this.pumpkins.filter((p) => !p.taken).length;
    const secs = Math.max(0, Math.ceil(this.timeLeft ?? this.level.seconds));
    const bell = this.upgrades.bell ? ` · Bell ${keycap(" ")} ×${this.state === "play" ? this.bellLeft : this.upgrades.bell}` : "";
    this.shell.els.hud.innerHTML =
      `<span>Pumpkins ${left}</span><span>Shooed <b class="game-score">${this.successes}</b>${bell}</span>` +
      `<span>${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}</span>`;
  }

  // --- drawing ----------------------------------------------------------------

  draw(s) {
    const sky = SKIES[Math.min(this.levelIndex, SKIES.length - 1)];
    const night = this.levelIndex >= SKIES.length - 1;
    s.bands(smoothSky(sky, 12), 0, 74);
    if (night) {
      s.disc(200, 18, 7, C.cream);
      s.disc(203, 16, 6, sky[0]);
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
      const ring = this.state === "play" && this.bellLeft ? 0 : 1;
      s.disc(54, 88, 3, ring ? C.grey : C.gold);
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
    for (const c of this.crows) this.drawCrow(s, c);
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

  drawCrow(s, c) {
    const ink = "#2b2a33";
    const x = c.x;
    const y = c.y;
    const d = c.dir; // -1 flying left (in), 1 flying away
    const up = Math.floor(c.phase) % 2;
    s.oval(x, y, 5, 3, ink);
    s.disc(x + d * 5, y - 2, 2, ink);
    s.rect(x + d * 7 + (d < 0 ? -1 : 0), y - 2, 2, 1, C.gold); // beak
    s.rect(x + d * 5, y - 3, 1, 1, C.white); // eye
    s.rect(x - d * 6 + (d > 0 ? -2 : 0), y - 1, 3, 2, ink); // tail
    if (up) s.rect(x - 2, y - 7, 4, 5, "#4a4954");
    else s.rect(x - 2, y + 2, 4, 4, "#4a4954");
    if (c.state === "steal") this.drawPumpkin(s, { x: x, y: y + 6 });
  }

  // --- keys -------------------------------------------------------------------

  targets() {
    if (this.state === "choose") return this.choices;
    if (this.state === "play") return this.crows.filter((c) => c.state === "fly");
    return [];
  }

  handleKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (this.state === "over") {
      this.shell.screenKey(e);
      return;
    }
    if (this.state !== "choose" && this.state !== "play") {
      this.shell.screenKey(e);
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
      r.target.el.classList.remove("slip");
      void r.target.el.offsetWidth; // restart the shake
      r.target.el.classList.add("slip");
    }
  }

  ringBell() {
    this.bellLeft -= 1;
    this.scene.burst(54, 88, 12, [C.gold, C.cream], { speed: 40, up: 10, gravity: 0, life: 0.6 });
    for (const c of this.crows) if (c.state === "fly") this.flee(c, true);
    this.renderHud();
  }
}

GAMES.crow_patrol = (shell, content, me) => new CrowPatrol(shell, content, me && me.avatar);
