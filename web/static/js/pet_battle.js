// Pet Battles (game_pet_battle_v1): friendly, turn-based battles between a
// pet you pick and a wild critter. No clock: take your time.
//
// Types: Leaf beats Splash, Splash beats Ember, Ember beats Leaf. A move
// against the type it beats does x2 ("Super!"); against the type that beats
// it, half. Critters' hits follow the same rule, so pick your partner well.
//
// Before each battle you see the critter (its type, what it's weak to, its
// trick) and pick a partner by typing its word. Each type plays differently:
//   Leaf   heals, and Tickle makes the critter skip its turn
//   Ember  big damage, and Warm up doubles the next hit
//   Splash shields, and Big wave always lands
// Each turn: type a move's word, or an item's from your bag. Big moves cost
// stars (★); Pounce earns one. Each slip takes 1 off a move's power (min 1).
// The critter shows what it will do next, including its trick.
//
// Win: an arcade tally (paid right away) and you find an item. Lose: your pet
// naps and you try again (pick again; the critter is 10% easier).
//
// Needs practice_scenes.js (Scene, C), pet_render.js, avatar.js, and game_kit.js.

const ARENA_W = 240;
const ARENA_H = 96;
const PET_HP = 14;
const MAX_STARS = 3;
const START_STARS = 1;
const RETRY_FOE_HP = 0.9;

const TYPES = {
  leaf: { name: "Leaf", beats: "splash" },
  splash: { name: "Splash", beats: "ember" },
  ember: { name: "Ember", beats: "leaf" },
};
// A pet's type is its v3 genes' battle element (app/pet_genes.py ELEMENTS).
const typeOf = (pet) => pet.genes.battle.element;
// Pets are v3 pets (pet_render.js), fit into this box in the arena.
const FIGHTER_BOX = { w: 64, h: 56 };

function effectiveness(moveType, targetType) {
  if (!moveType || !targetType) return 1;
  if (TYPES[moveType].beats === targetType) return 2;
  if (TYPES[targetType].beats === moveType) return 0.5;
  return 1;
}

const POUNCE = { id: "pounce", name: "Pounce", group: "short", cost: 0, gain: 1, kind: "hit", power: 2, text: "2 hits, +1 ★" };
const KITS = {
  leaf: [
    POUNCE,
    { id: "vine", name: "Vine whip", group: "medium", cost: 1, kind: "hit", power: 3, type: "leaf", text: "3 Leaf hits, ★" },
    { id: "snack", name: "Leafy snack", group: "medium", cost: 1, kind: "heal", power: 4, text: "Heals 4, ★" },
    { id: "tickle", name: "Tickle", group: "short", cost: 2, kind: "stun", power: 0, text: "It skips its move, ★★" },
  ],
  ember: [
    POUNCE,
    { id: "ember", name: "Ember", group: "medium", cost: 1, kind: "hit", power: 3, type: "ember", text: "3 Ember hits, ★" },
    { id: "blaze", name: "Blaze", group: "long", cost: 2, kind: "hit", power: 6, type: "ember", text: "6 Ember hits, ★★" },
    { id: "warm", name: "Warm up", group: "short", cost: 0, kind: "focus", power: 0, text: "Next hit x2, free" },
  ],
  splash: [
    POUNCE,
    { id: "splash", name: "Splash", group: "medium", cost: 1, kind: "hit", power: 3, type: "splash", text: "3 Splash hits, ★" },
    { id: "bubble", name: "Bubble", group: "medium", cost: 1, kind: "shield", power: 4, text: "Blocks 4, ★" },
    { id: "wave", name: "Big wave", group: "long", cost: 2, kind: "hit", power: 4, type: "splash", sure: true, text: "4 hits, always lands, ★★" },
  ],
};

const ITEMS = {
  berry: { name: "Berry", text: "Heals 5" },
  candy: { name: "Star candy", text: "+2 ★" },
  shell: { name: "Shell charm", text: "Blocks its next move" },
};

// Critters: a type, a trick, and what they do. Intents with `after` only
// come right after a wind-up.
const CRITTERS = {
  bunny: {
    name: "Bunny", trick: "Hops around so your hit misses.",
    intents: {
      nibble: { says: "Nibble: 1 hit", hit: 1, w: 3 },
      tackle: { says: "Tackle: 2 hits", hit: 2, w: 2 },
      hop: { says: "Hopping! Your next hit will miss.", dodge: true, w: 2 },
      rest: { says: "Rest: heals 2", heal: 2, w: 1 },
    },
  },
  lizard: {
    name: "Lizard", trick: "Puffs up its spiky frill: hitting it pricks you.",
    intents: {
      nibble: { says: "Nibble: 1 hit", hit: 1, w: 2 },
      roll: { says: "Tail whip: 3 hits", hit: 3, w: 2 },
      spiky: { says: "Frill up! Hitting it pricks you 2.", spiky: 2, w: 2 },
    },
  },
  goat: {
    name: "Goat", trick: "Winds up a huge headbutt.",
    intents: {
      tackle: { says: "Tackle: 2 hits", hit: 2, w: 3 },
      windup: { says: "Winding up a HEADBUTT!", next: "headbutt", w: 2 },
      headbutt: { says: "HEADBUTT: 5 hits!", hit: 5, after: true },
      chew: { says: "Chewing grass: heals 3", heal: 3, w: 1 },
    },
  },
  fox: {
    name: "Fox", trick: "Sneaks off with your stars.",
    intents: {
      bite: { says: "Bite: 2 hits", hit: 2, w: 3 },
      trick: { says: "Sneaky! Will steal a ★.", steal: 1, w: 2 },
      windup: { says: "Crouching for a big pounce!", next: "bigpounce", w: 1 },
      bigpounce: { says: "BIG POUNCE: 4 hits!", hit: 4, after: true },
    },
  },
  llama: {
    name: "Llama", trick: "Spits, so your words get longer.",
    intents: {
      stomp: { says: "Stomp: 3 hits", hit: 3, w: 3 },
      spit: { says: "Spit! Your next words will be longer.", spit: true, hit: 1, w: 2 },
      windup: { says: "Rearing up for a MEGA STOMP!", next: "mega", w: 1 },
      mega: { says: "MEGA STOMP: 6 hits!", hit: 6, after: true },
      rest: { says: "Rest: heals 3", heal: 3, w: 1 },
    },
  },
};

const LONGER = { short: "medium", medium: "long", long: "long" };

class PetBattle {
  constructor(shell, content, me) {
    this.shell = shell;
    this.game = content.game;
    this.levels = this.game.levels;
    this.avatar = me && me.avatar;
    this.team = makeTeam((this.avatar && this.avatar.pets) || [], this.game.starters);
    this.typer = new Typer();
    this.levelIndex = 0;
    this.foeEase = 1;
    this.items = { berry: 2, candy: 1, shell: 1 };
    this.state = "pick"; // pick | turn | busy | tally | lost | over
    this.anim = { pet: 0, foe: 0, foeShake: 0, petShake: 0 };
    this.pet = this.team[0];
    this.cards = [];
    this.bag = [];

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
    shell.els.below.innerHTML = `<div class="move-cards"></div><div class="bag"></div>`;
    this.cardsEl = shell.els.below.querySelector(".move-cards");
    this.bagEl = shell.els.below.querySelector(".bag");
    this.intentEl = document.createElement("div");
    this.intentEl.className = "foe-intent";
    shell.els.layer.appendChild(this.intentEl);

    this.setupFoe();
    this.pickScreen();
    window.addEventListener("keydown", (e) => this.handleKey(e));
  }

  get level() {
    return this.levels[this.levelIndex];
  }

  get critter() {
    return CRITTERS[this.level.foe] || CRITTERS.bunny;
  }

  // --- flow -----------------------------------------------------------------

  setupFoe() {
    const lv = this.level;
    this.foe = {
      name: `Wild ${this.critter.name}`,
      species: lv.foe,
      genes: lv.foe_genes,
      growth: lv.foe_growth,
      type: typeOf({ genes: lv.foe_genes }),
      maxHp: Math.max(3, Math.round(lv.foe_hp * this.foeEase)),
    };
    this.foe.hp = this.foe.maxHp;
    this.intent = null;
  }

  // Meet the critter, then pick a partner by typing a word.
  pickScreen() {
    this.state = "pick";
    this.typer.release();
    this.cards = [];
    this.bag = [];
    this.renderCards();
    this.shell.setLabel(`Game · Battle ${this.levelIndex + 1} of ${this.levels.length} · ${this.level.name}`);
    const weak = Object.keys(TYPES).find((t) => TYPES[t].beats === this.foe.type);
    const words = pickWords(this.game.words, this.team.map(() => "short"));
    this.choices = this.team.map((pet, i) => ({ pet, word: words[i], typed: 0 }));
    this.shell.showScreen(
      `<h2>A wild ${escapeHtml(this.critter.name.toLowerCase())} wants to play!</h2>
       <p>${typeTag(this.foe.type)} Weak to ${typeTag(weak)} · ${escapeHtml(this.critter.trick)}</p>
       <p>Pick your partner: type its word.</p>
       <div class="choice-cards">${this.choices
         .map(
           (c, i) => `<div class="choice-card" data-i="${i}">
             <h3>${escapeHtml(c.pet.name)} ${typeTag(c.pet.type)}</h3>
             <p>${KITS[c.pet.type].slice(1).map((m) => escapeHtml(m.name)).join(" · ")}</p>
             <p class="choice-word"></p>
           </div>`
         )
         .join("")}</div>`
    );
    this.renderChoices();
    this.renderHud();
  }

  renderChoices() {
    this.shell.els.screen.querySelectorAll(".choice-card").forEach((card) => {
      const c = this.choices[+card.dataset.i];
      card.classList.toggle("locked", this.typer.target === c);
      card.querySelector(".choice-word").innerHTML = wordHtml(c.word, c.typed);
    });
  }

  startBattle(pet) {
    this.pet = pet;
    this.hp = PET_HP;
    this.stars = START_STARS;
    this.shield = 0;
    this.focus = false;
    this.charm = false;
    this.stunned = false;
    this.spat = false;
    this.nextIntent = null;
    this.stats = { clean: 0, supers: 0 };
    this.intent = this.pickIntent();
    this.shell.hideScreen();
    this.startTurn();
  }

  startTurn() {
    this.state = "turn";
    this.typer.release();
    const kit = KITS[this.pet.type];
    const group = (g) => (this.spat ? LONGER[g] : g);
    const itemIds = Object.keys(ITEMS).filter((id) => this.items[id] > 0);
    const words = pickWords(this.game.words, [...kit.map((m) => group(m.group)), ...itemIds.map(() => "short")]);
    this.cards = kit.map((m, i) => ({ move: m, word: words[i], typed: 0, slips: 0 }));
    this.bag = itemIds.map((id, i) => ({ item: id, word: words[kit.length + i], typed: 0, slips: 0 }));
    this.spat = false;
    this.renderCards();
    this.renderHud();
  }

  pickIntent() {
    if (this.nextIntent) {
      const forced = this.nextIntent;
      this.nextIntent = null;
      return forced;
    }
    const options = Object.entries(this.critter.intents).filter(
      ([, it]) => !it.after && (!it.heal || this.foe.hp < this.foe.maxHp)
    );
    let roll = Math.random() * options.reduce((sum, [, it]) => sum + it.w, 0);
    for (const [id, it] of options) {
      roll -= it.w;
      if (roll <= 0) return id;
    }
    return options[0][0];
  }

  useMove(card) {
    const m = card.move;
    const it = this.critter.intents[this.intent];
    const power = Math.max(1, m.power - card.slips);
    if (!card.slips) this.stats.clean += 1;
    this.state = "busy";
    this.stars = Math.min(MAX_STARS, this.stars - m.cost + (m.gain || 0));
    if (m.kind === "hit") {
      this.anim.pet = 0.35;
      this.later(0.2, () => {
        if (it.dodge && !m.sure) {
          this.floater("Missed!", 178, 46, "note");
          return;
        }
        const eff = effectiveness(m.type, this.foe.type);
        const hits = Math.max(1, Math.round(power * eff * (this.focus ? 2 : 1)));
        this.focus = false;
        this.foe.hp = Math.max(0, this.foe.hp - hits);
        this.anim.foeShake = 0.4;
        this.floater(`-${hits}`, 178, 50, "hurt");
        if (eff > 1) {
          this.stats.supers += 1;
          this.floater("Super!", 178, 30, "super");
        } else if (eff < 1) {
          this.floater("Not very good...", 178, 30, "note");
        }
        if (it.spiky) {
          this.hp = Math.max(0, this.hp - it.spiky);
          this.anim.petShake = 0.4;
          this.floater(`Ouch! -${it.spiky}`, 70, 40, "hurt");
        }
        this.renderHud();
      });
    } else if (m.kind === "shield") {
      this.shield = power;
      this.floater(`Shield ${power}`, 70, 40, "calm");
    } else if (m.kind === "heal") {
      this.heal(power);
    } else if (m.kind === "stun") {
      this.stunned = true;
      this.floater("Hee hee!", 178, 40, "calm");
    } else if (m.kind === "focus") {
      this.focus = true;
      this.floater("Warmed up! x2", 70, 40, "calm");
    }
    if (card.slips) this.floater(`${card.slips} slip${card.slips > 1 ? "s" : ""}`, 70, 62, "note");
    this.afterYourTurn();
  }

  useItem(card) {
    this.items[card.item] -= 1;
    this.state = "busy";
    if (card.item === "berry") {
      this.heal(5);
    } else if (card.item === "candy") {
      this.stars = Math.min(MAX_STARS, this.stars + 2);
      this.floater("+2 ★", 70, 40, "calm");
    } else {
      this.charm = true;
      this.floater("Shell charm!", 70, 40, "calm");
    }
    this.afterYourTurn();
  }

  heal(amount) {
    const healed = Math.min(PET_HP - this.hp, amount);
    this.hp += healed;
    this.scene.burst(70, 60, 8, [C.red, "#e88aa0"], { speed: 15, up: 20, gravity: -5, life: 0.9, size: 2 });
    this.floater(`+${healed}`, 70, 40, "calm");
  }

  afterYourTurn() {
    this.renderCards();
    this.renderHud();
    this.later(0.9, () => {
      if (this.foe.hp <= 0) return this.win();
      if (this.hp <= 0) return this.lose();
      this.foeActs();
    });
  }

  foeActs() {
    const it = this.critter.intents[this.intent];
    if (this.stunned) {
      this.stunned = false;
      this.floater("Too giggly to move!", 178, 40, "note");
    } else if (this.charm && (it.hit || it.steal)) {
      this.charm = false;
      this.floater("Shell charm blocked it!", 70, 40, "calm");
    } else {
      if (it.hit) {
        const hits = Math.max(1, Math.round(it.hit * effectiveness(this.foe.type, this.pet.type)));
        const taken = hits - Math.min(this.shield, hits);
        this.anim.foe = 0.35;
        this.later(0.2, () => {
          this.hp = Math.max(0, this.hp - taken);
          if (taken) this.anim.petShake = 0.4;
          this.floater(taken ? `-${taken}` : "Blocked!", 70, 50, taken ? "hurt" : "calm");
          this.renderHud();
        });
      }
      if (it.heal) {
        const healed = Math.min(this.foe.maxHp - this.foe.hp, it.heal);
        this.foe.hp += healed;
        this.floater(`+${healed}`, 178, 40, "calm");
      }
      if (it.steal && this.stars) {
        this.stars -= 1;
        this.floater("Stole a ★!", 70, 30, "hurt");
      }
      if (it.spit) this.spat = true;
      if (it.next) {
        this.nextIntent = it.next;
        this.floater("!", 178, 36, "note");
      }
    }
    this.shield = 0;
    this.renderHud();
    this.later(0.9, () => {
      if (this.hp <= 0) return this.lose();
      this.intent = this.pickIntent();
      this.startTurn();
    });
  }

  async win() {
    this.state = "tally";
    this.foeEase = 1;
    this.scene.burst(178, 60, 14, [C.gold, C.cream, "#e88aa0"], { speed: 30, up: 25, life: 1.1, size: 2 });
    const found = Object.keys(ITEMS)[Math.floor(Math.random() * 3)];
    this.items[found] += 1;
    this.renderCards();
    this.renderHud();
    await this.shell.roundTally({
      title: `You won! Found a ${ITEMS[found].name.toLowerCase()}!`,
      rows: [
        { label: "Battle won", points: 200 },
        { label: "HP left", count: this.hp, each: 10 },
        { label: "Clean moves", count: this.stats.clean, each: 20 },
        { label: "Super hits", count: this.stats.supers, each: 30 },
      ],
      typer: this.typer,
    });
    if (this.levelIndex >= this.levels.length - 1) return this.gameOver();
    this.levelIndex += 1;
    this.setupFoe();
    this.pickScreen();
  }

  lose() {
    this.state = "lost";
    this.foeEase *= RETRY_FOE_HP;
    this.shell.showScreen(
      `<h2>${escapeHtml(this.pet.name)} needs a nap!</h2>
       <p>Try again. Maybe a different partner?</p>
       <p>Press ${keycap(" ")} to try again.</p>`,
      {
        " ": () => {
          this.setupFoe();
          this.pickScreen();
        },
      }
    );
  }

  gameOver() {
    this.state = "over";
    this.shell.finish({ line: "You played with every critter!" });
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
    const inBattle = this.state !== "pick" && this.hp != null;
    const stars = "★".repeat(this.stars || 0) + "☆".repeat(MAX_STARS - (this.stars || 0));
    const chips = [this.focus && "x2", this.charm && "Charm", this.shield && `Shield ${this.shield}`].filter(Boolean);
    const you = inBattle
      ? `${escapeHtml(this.pet.name)} ${typeTag(this.pet.type)} ${bar(this.hp, PET_HP)} <span class="stars">${stars}</span>` +
        chips.map((c) => ` <span class="chip">${c}</span>`).join("")
      : "Your team";
    this.shell.els.hud.innerHTML =
      `<span class="fighter">${you}</span>` +
      `<span>Score <b class="game-score">${this.shell.total.toLocaleString()}</b></span>` +
      `<span class="fighter">${escapeHtml(this.foe.name)} ${typeTag(this.foe.type)} ${bar(this.foe.hp, this.foe.maxHp)}</span>`;
    const it = this.intent && this.critter.intents[this.intent];
    this.intentEl.innerHTML = it ? `Next: ${escapeHtml(it.says)}` : "";
    this.intentEl.hidden = !it || this.state === "pick" || this.state === "tally";
  }

  affordable(card) {
    return Boolean(card.word) && (!card.move || this.stars >= card.move.cost);
  }

  renderCards() {
    const card = (c, title, text, cls) => {
      const classes = [cls];
      if (!this.affordable(c)) classes.push("cant");
      if (this.typer.target === c) classes.push("locked");
      if (this.state !== "turn") classes.push("waiting");
      const slips = c.slips && this.typer.target === c ? `<span class="move-slips">−${c.slips}</span>` : "";
      return `<div class="${classes.join(" ")}">
        <h3>${title} ${slips}</h3>
        <p>${escapeHtml(text)}</p>
        <p class="move-word">${c.word ? wordHtml(c.word, c.typed) : "…"}</p>
      </div>`;
    };
    this.cardsEl.innerHTML = this.cards
      .map((c) => card(c, `${escapeHtml(c.move.name)}${c.move.type ? " " + typeTag(c.move.type) : ""}`, c.move.text, "move-card"))
      .join("");
    this.bagEl.innerHTML = this.bag.length
      ? `<h3 class="bag-title">Bag</h3><div class="bag-cards">` +
        this.bag
          .map((c) => card(c, `${escapeHtml(ITEMS[c.item].name)} ×${this.items[c.item]}`, ITEMS[c.item].text, "move-card item-card"))
          .join("") +
        `</div>`
      : "";
  }

  // --- each frame -------------------------------------------------------------

  update(dt) {
    for (const k of Object.keys(this.anim)) this.anim[k] = Math.max(0, this.anim[k] - dt);
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
    const inBattle = this.state !== "pick" && this.state !== "lost";
    const lunge = (t) => (t > 0 ? Math.sin((t / 0.35) * Math.PI) * 14 : 0);
    const shake = (t) => (t > 0 ? Math.round(Math.sin(t * 60) * 2) : 0);
    if (inBattle) {
      this.drawFighter(s, this.pet, 72 + lunge(this.anim.pet) + shake(this.anim.petShake), 86, false);
      if (this.focus && Math.random() < 0.3) s.burst(72, 70, 1, [C.orange, C.gold], { speed: 10, up: 15, gravity: -10, life: 0.5 });
      if (this.shield || this.charm) {
        const color = this.charm ? C.gold : "#8fc3d6";
        for (let y = 50; y < 88; y += 2) s.rect(102 + Math.round(Math.abs(y - 69) / 4), y, 2, 1, color);
      }
    }
    const it = (this.intent && this.critter.intents[this.intent]) || {};
    const flicker = this.anim.foeShake > 0 && Math.floor(this.anim.foeShake * 20) % 2;
    const hopping = it.dodge && this.state === "turn" ? -Math.abs(Math.round(Math.sin(s.t * 8) * 6)) : 0;
    if (this.state !== "tally" && !flicker) {
      this.drawFighter(s, this.foe, 180 - lunge(this.anim.foe) + shake(this.anim.foeShake), 76 + hopping, true);
    }
    if (this.state === "turn") {
      if (it.spiky) for (let i = 0; i < 7; i++) s.rect(160 + i * 6, 44 + (i % 2) * 2, 2, 4, C.cream);
      if (it.after) s.mark(180, 36, "!");
      if (this.stunned) s.mark(180, 36, "?");
    }
  }

  // pet: {genes, growth}; (cx, bottom) is where its feet go. Drawn once at a
  // pixel per pet pixel, then scaled down to fit FIGHTER_BOX.
  drawFighter(s, pet, cx, bottom, faceLeft) {
    const key = faceLeft ? "left" : "right";
    pet.art ||= {};
    if (!pet.art[key]) {
      const { w, h } = petSize(pet.genes, pet.growth);
      const art = document.createElement("canvas");
      art.width = w;
      art.height = h + 2;
      const ctx = art.getContext("2d");
      drawPet((x, y, ww, hh, c) => {
        ctx.fillStyle = c;
        ctx.fillRect(x, y, ww, hh);
      }, 0, h, pet.genes, pet.growth, { faceLeft });
      pet.art[key] = { canvas: art, scale: Math.min(1, FIGHTER_BOX.w / w, FIGHTER_BOX.h / h) };
    }
    const { canvas, scale } = pet.art[key];
    const w = Math.round(canvas.width * scale);
    const h = Math.round(canvas.height * scale);
    s.ctx.imageSmoothingEnabled = false;
    s.ctx.drawImage(canvas, Math.round(cx - w / 2), Math.round(bottom - h + 2 * scale), w, h);
  }

  // --- keys -------------------------------------------------------------------

  targets() {
    if (this.state === "pick") return this.choices;
    if (this.state === "turn") return [...this.cards, ...this.bag].filter((c) => this.affordable(c));
    return [];
  }

  handleKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (this.state !== "turn" && this.state !== "pick") {
      this.shell.screenKey(e);
      if (e.key === " ") e.preventDefault();
      return;
    }
    if (e.key === "Escape" || e.key === "Backspace") {
      e.preventDefault();
      this.typer.release();
      if (this.state === "pick") this.renderChoices();
      else this.renderCards();
      return;
    }
    if (e.key.length !== 1) return;
    e.preventDefault();
    if (e.repeat || e.key === " ") return;
    const r = this.typer.press(e.key, this.targets());
    if (this.state === "pick") {
      if (r.kind === "done") this.startBattle(r.target.pet);
      else this.renderChoices();
      return;
    }
    if (r.kind === "done") {
      if (r.target.item) this.useItem(r.target);
      else this.useMove(r.target);
    } else {
      this.renderCards();
    }
  }
}

function typeTag(type) {
  return `<span class="type-tag type-${type}">${TYPES[type].name}</span>`;
}

// Up to 3 partners: the pets that come along, then starters (app/pet_care.py
// BATTLE_STARTERS) for the types still missing, so there's always one of
// each type when you have none.
function makeTeam(owned, starters) {
  const team = owned.slice(0, 2).map((p) => ({ name: p.name, species: p.species, genes: p.genes, growth: p.growth, type: typeOf(p) }));
  for (const s of starters) {
    if (team.length >= 3) break;
    if (!team.some((p) => p.type === typeOf(s))) team.push({ ...s, type: typeOf(s) });
  }
  return team;
}

GAMES.pet_battle = (shell, content, me) => new PetBattle(shell, content, me);
