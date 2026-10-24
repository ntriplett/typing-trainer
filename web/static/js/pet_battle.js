// Pet Battles (game_pet_battle_v1): a friendly, turn-based battle between
// your pet and a wild critter. No clock: take your time.
//
// Each turn you pick a move by typing its word. The critter shows what it
// will do next, so you can plan: shield before a big hit, snack when low.
// Big moves cost stars (★), and Pounce earns one back. Each slip (wrong key)
// on a move takes 1 off its power, but never below 1.
//
// Tire out the critter to win; if your pet gets tired first, it naps and you
// try that critter again. Score = battles won.
//
// Needs practice_scenes.js (Scene, C), pets.js, avatar.js, and game_kit.js.

const ARENA_W = 240;
const ARENA_H = 96;
const PET_HP = 12;
const MAX_STARS = 3;
const START_STARS = 1;
const MAX_BATTLE_SECONDS = 10 * 60;
const RETRY_FOE_HP = 0.9; // each lost try makes the critter a bit easier
const BORROWED_PET = { name: "Pip", species: "fox", color: "red", stage: "young" };

const MOVES = [
  { id: "pounce", name: "Pounce", group: "short", cost: 0, gain: 1, kind: "hit", power: 2, text: "2 hits, +1 ★" },
  { id: "super", name: "Super pounce", group: "long", cost: 2, gain: 0, kind: "hit", power: 4, text: "4 hits, costs ★★" },
  { id: "shield", name: "Shield", group: "medium", cost: 1, gain: 0, kind: "shield", power: 3, text: "Blocks 3, costs ★" },
  { id: "snack", name: "Snack", group: "medium", cost: 1, gain: 0, kind: "heal", power: 3, text: "Heals 3, costs ★" },
];

// What the critter can do; foe_power (1-3) adds the trickier ones.
const INTENTS = {
  nibble: { says: "Nibble: 1 hit", hit: 1, weight: 3, power: 1 },
  tackle: { says: "Tackle: 2 hits", hit: 2, weight: 3, power: 1 },
  rest: { says: "Rest: heals 2", heal: 2, weight: 1, power: 1 },
  windup: { says: "Winding up a BIG move!", hit: 0, weight: 2, power: 2 },
  guard: { says: "Curling up: your hits are halved", hit: 0, guard: true, weight: 2, power: 3 },
  big: { says: "BIG move: 4 hits!", hit: 4, weight: 0, power: 99 }, // only after a wind-up
};

const CRITTER_NAMES = { bunny: "Bunny", hedgehog: "Hedgehog", goat: "Goat", fox: "Fox", llama: "Llama", cat: "Cat", dog: "Dog", sheep: "Sheep" };

class PetBattle {
  constructor(shell, content, me) {
    this.shell = shell;
    this.game = content.game;
    this.levels = this.game.levels;
    this.avatar = me && me.avatar;
    const own = this.avatar && this.avatar.pets && this.avatar.pets[0];
    this.pet = own ? { ...own, name: own.name || "Your pet" } : BORROWED_PET;
    this.typer = new Typer();
    this.levelIndex = 0;
    this.successes = 0;
    this.playSeconds = 0;
    this.foeEase = 1;
    this.state = "intro"; // intro | turn | busy | won | lost | over
    this.anim = { pet: 0, foe: 0, foeShake: 0, petShake: 0 };

    const game = this;
    this.scene = new (class extends Scene {
      update(dt) {
        game.update(dt);
      }
      draw() {
        game.draw(this);
      }
    })(shell.els.canvas, ARENA_W, ARENA_H);
    shell.els.canvas.classList.add("battle-arena");
    shell.els.below.innerHTML = `<div class="move-cards"></div>`;
    this.cardsEl = shell.els.below.querySelector(".move-cards");
    this.intentEl = document.createElement("div");
    this.intentEl.className = "foe-intent";
    shell.els.layer.appendChild(this.intentEl);

    this.setupBattle();
    this.introScreen();
    window.addEventListener("keydown", (e) => this.handleKey(e));
  }

  get level() {
    return this.levels[this.levelIndex];
  }

  // --- flow -----------------------------------------------------------------

  setupBattle() {
    const lv = this.level;
    const colors = Object.keys(PET_COLORS[lv.foe] || {});
    this.foe = {
      name: `Wild ${CRITTER_NAMES[lv.foe] || "critter"}`,
      species: lv.foe,
      color: colors[Math.floor(Math.random() * colors.length)] || "brown",
      stage: "grown",
      maxHp: Math.max(3, Math.round(lv.foe_hp * this.foeEase)),
    };
    this.foe.hp = this.foe.maxHp;
    this.hp = PET_HP;
    this.stars = START_STARS;
    this.shield = 0;
    this.guard = false;
    this.nextIntent = null;
    this.intent = this.pickIntent();
    this.cards = [];
    this.renderHud();
    this.renderCards();
  }

  introScreen() {
    this.shell.setLabel(`Game · Battle ${this.levelIndex + 1} of ${this.levels.length} · ${this.level.name}`);
    this.state = "intro";
    this.shell.showScreen(
      `<h2>A ${escapeHtml(this.foe.name.toLowerCase())} wants to play!</h2>
       <p>Type a move's word to use it. Watch what it will do next.</p>
       <p>Press ${keycap(" ")} to start.</p>`,
      { " ": () => this.startTurn() }
    );
  }

  startTurn() {
    this.shell.hideScreen();
    this.state = "turn";
    this.typer.release();
    const words = pickWords(this.game.words, MOVES.map((m) => m.group));
    this.cards = MOVES.map((m, i) => ({ move: m, word: words[i], typed: 0, slips: 0 }));
    this.renderCards();
    this.renderHud();
  }

  pickIntent() {
    if (this.nextIntent) {
      const forced = this.nextIntent;
      this.nextIntent = null;
      return forced;
    }
    const power = this.level.foe_power || 1;
    const options = Object.entries(INTENTS).filter(
      ([id, it]) => it.power <= power && it.weight && (id !== "rest" || this.foe.hp < this.foe.maxHp)
    );
    let roll = Math.random() * options.reduce((sum, [, it]) => sum + it.weight, 0);
    for (const [id, it] of options) {
      roll -= it.weight;
      if (roll <= 0) return id;
    }
    return "nibble";
  }

  useMove(card) {
    const m = card.move;
    const power = Math.max(1, m.power - card.slips);
    this.state = "busy";
    this.stars = Math.min(MAX_STARS, this.stars - m.cost + m.gain);
    if (m.kind === "hit") {
      const hits = this.intent === "guard" ? Math.ceil(power / 2) : power;
      this.anim.pet = 0.35;
      this.later(0.2, () => {
        this.foe.hp = Math.max(0, this.foe.hp - hits);
        this.anim.foeShake = 0.4;
        this.floater(`-${hits}`, 178, 50, "hurt");
        this.renderHud();
      });
    } else if (m.kind === "shield") {
      this.shield = power;
      this.floater(`Shield ${power}`, 70, 40, "calm");
    } else {
      const healed = Math.min(PET_HP - this.hp, power);
      this.hp += healed;
      this.scene.burst(70, 60, 8, [C.red, "#e88aa0"], { speed: 15, up: 20, gravity: -5, life: 0.9, size: 2 });
      this.floater(`+${healed}`, 70, 40, "calm");
    }
    if (card.slips) this.floater(`${card.slips} slip${card.slips > 1 ? "s" : ""}`, 70, 62, "note");
    this.renderCards();
    this.renderHud();
    this.later(0.9, () => (this.foe.hp <= 0 ? this.win() : this.foeActs()));
  }

  foeActs() {
    const id = this.intent;
    const it = INTENTS[id];
    if (it.hit) {
      const extra = id === "big" && (this.level.foe_power || 1) >= 3 ? 1 : 0;
      const hits = it.hit + extra;
      const blocked = Math.min(this.shield, hits);
      const taken = hits - blocked;
      this.anim.foe = 0.35;
      this.later(0.2, () => {
        this.hp = Math.max(0, this.hp - taken);
        if (taken) this.anim.petShake = 0.4;
        this.floater(taken ? `-${taken}` : "Blocked!", 70, 50, taken ? "hurt" : "calm");
        this.renderHud();
      });
    } else if (it.heal) {
      const healed = Math.min(this.foe.maxHp - this.foe.hp, it.heal);
      this.foe.hp += healed;
      this.floater(`+${healed}`, 178, 40, "calm");
    } else if (id === "windup") {
      this.nextIntent = "big";
      this.floater("!", 178, 36, "note");
    }
    this.shield = 0;
    this.renderHud();
    this.later(0.9, () => {
      if (this.hp <= 0) return this.lose();
      this.intent = this.pickIntent();
      this.startTurn();
    });
  }

  win() {
    this.state = "won";
    this.successes += 1;
    this.foeEase = 1;
    this.renderHud();
    const last = this.levelIndex >= this.levels.length - 1 || this.playSeconds >= MAX_BATTLE_SECONDS;
    this.scene.burst(178, 60, 14, [C.gold, C.cream, "#e88aa0"], { speed: 30, up: 25, life: 1.1, size: 2 });
    this.shell.showScreen(
      `<h2>You won!</h2>
       <p>The ${escapeHtml(CRITTER_NAMES[this.foe.species] || "critter").toLowerCase()} is tired out and hops off happy.</p>
       <p>Press ${keycap(" ")} to ${last ? "finish" : "meet the next critter"}.</p>`,
      {
        " ": () => {
          if (last) return this.gameOver();
          this.levelIndex += 1;
          this.setupBattle();
          this.introScreen();
        },
      }
    );
  }

  lose() {
    this.state = "lost";
    this.foeEase *= RETRY_FOE_HP;
    this.shell.showScreen(
      `<h2>${escapeHtml(this.pet.name)} needs a nap!</h2>
       <p>Rest up and try again. Your score stays.</p>
       <p>Press ${keycap(" ")} to try again.</p>`,
      {
        " ": () => {
          if (this.playSeconds >= MAX_BATTLE_SECONDS) return this.gameOver();
          this.setupBattle();
          this.startTurn();
        },
      }
    );
  }

  gameOver() {
    this.state = "over";
    this.shell.finish({
      successes: this.successes,
      line: `You won ${this.successes} battle${this.successes === 1 ? "" : "s"}!`,
      keystrokes: this.typer.keystrokes,
    });
  }

  later(seconds, fn) {
    setTimeout(fn, seconds * 1000);
  }

  floater(text, x, y, kind) {
    const el = document.createElement("div");
    el.className = `float-text ${kind}`;
    el.textContent = text;
    el.style.left = `${(x / ARENA_W) * 100}%`;
    el.style.top = `${(y / ARENA_H) * 100}%`;
    this.shell.els.layer.appendChild(el);
    setTimeout(() => el.remove(), 1200);
  }

  // --- HTML -------------------------------------------------------------------

  renderHud() {
    const bar = (hp, max) => `<span class="hp-bar"><span style="width:${(100 * hp) / max}%"></span></span> ${hp}/${max}`;
    const stars = "★".repeat(this.stars) + "☆".repeat(MAX_STARS - this.stars);
    this.shell.els.hud.innerHTML =
      `<span class="fighter">${escapeHtml(this.pet.name)} ${bar(this.hp, PET_HP)} <span class="stars">${stars}</span></span>` +
      `<span>Wins <b class="game-score">${this.successes}</b></span>` +
      `<span class="fighter">${escapeHtml(this.foe.name)} ${bar(this.foe.hp, this.foe.maxHp)}</span>`;
    this.intentEl.innerHTML = `Next: ${escapeHtml(INTENTS[this.intent].says)}`;
    this.intentEl.hidden = this.state === "won";
  }

  affordable(card) {
    return this.stars >= card.move.cost;
  }

  renderCards() {
    this.cardsEl.innerHTML = this.cards
      .map((c) => {
        const cls = ["move-card"];
        if (!this.affordable(c)) cls.push("cant");
        if (this.typer.target === c) cls.push("locked");
        if (this.state !== "turn") cls.push("waiting");
        const slips = c.slips && this.typer.target === c ? `<span class="move-slips">−${c.slips}</span>` : "";
        return `<div class="${cls.join(" ")}">
          <h3>${escapeHtml(c.move.name)} ${slips}</h3>
          <p>${escapeHtml(c.move.text)}</p>
          <p class="move-word">${wordHtml(c.word, c.typed)}</p>
        </div>`;
      })
      .join("");
  }

  // --- each frame -------------------------------------------------------------

  update(dt) {
    for (const k of Object.keys(this.anim)) this.anim[k] = Math.max(0, this.anim[k] - dt);
    if (this.state === "turn" || this.state === "busy") this.playSeconds += dt;
  }

  draw(s) {
    s.bands(smoothSky(["#cfe8ef", "#a8d5e2"], 8), 0, 52);
    s.oval(50, 54, 80, 10, "#8fb36b");
    s.oval(200, 52, 70, 9, "#7ea35c");
    s.rect(0, 54, ARENA_W, 42, C.grass);
    for (let i = 0; i < 14; i++) s.rect((i * 37) % 236, 60 + ((i * 11) % 30), 2, 1, C.grassDark);
    // the two spots
    s.oval(72, 84, 30, 6, "#5c7f30");
    s.oval(180, 74, 28, 5, "#5c7f30");
    if (this.avatar) {
      paintAvatar((x, y, w, h, c) => s.rect(-2 + x, 44 + y, w, h, c), this.avatar, {
        background: false,
        pets: false,
        frame: Math.floor(s.t * 2) % 2,
      });
    }
    // your pet, lunging right on its move
    const lunge = (t) => (t > 0 ? Math.sin((t / 0.35) * Math.PI) * 14 : 0);
    const shake = (t) => (t > 0 ? Math.round(Math.sin(t * 60) * 2) : 0);
    this.drawPet(s, this.pet, 72 + lunge(this.anim.pet) + shake(this.anim.petShake), 86, false);
    if (this.shield && this.state !== "won") {
      for (let y = 50; y < 88; y += 2) s.rect(102 + Math.round(Math.abs(y - 69) / 4), y, 2, 1, "#8fc3d6");
    }
    // the critter, lunging left
    const flicker = this.anim.foeShake > 0 && Math.floor(this.anim.foeShake * 20) % 2;
    if (this.state !== "won" && !flicker) {
      this.drawPet(s, this.foe, 180 - lunge(this.anim.foe) + shake(this.anim.foeShake), 76, true);
    }
    if (this.intent === "guard" && this.state === "turn") {
      s.rect(176, 28, 8, 6, C.grey);
      s.rect(177, 34, 6, 2, C.grey);
    }
    if (this.intent === "big" && this.state === "turn") s.mark(180, 36, "!");
  }

  // pet: {species, color, stage}; (cx, bottom) is where its feet go.
  drawPet(s, pet, cx, bottom, faceLeft) {
    const sprite = petSprite({ ...pet, slot: 2 }, { x: 0, y: 0, faceLeft });
    const scale = pet.stage === "baby" ? 4 : 3;
    const w = sprite.rows[0].length * scale;
    const ox = Math.round(cx - w / 2);
    const oy = bottom - sprite.rows.length * scale;
    drawGrid((x, y, ww, hh, c) => s.rect(ox + x * scale, oy + y * scale, ww * scale, hh * scale, c), sprite, 0);
  }

  // --- keys -------------------------------------------------------------------

  targets() {
    return this.state === "turn" ? this.cards.filter((c) => this.affordable(c)) : [];
  }

  handleKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (this.state !== "turn") {
      this.shell.screenKey(e);
      if (e.key === " ") e.preventDefault();
      return;
    }
    if (e.key === "Escape" || e.key === "Backspace") {
      e.preventDefault();
      this.typer.release();
      this.renderCards();
      return;
    }
    if (e.key.length !== 1) return;
    e.preventDefault();
    if (e.repeat || e.key === " ") return;
    const r = this.typer.press(e.key, this.targets());
    if (r.kind === "done") this.useMove(r.target);
    else this.renderCards();
  }
}

GAMES.pet_battle = (shell, content, me) => new PetBattle(shell, content, me);
