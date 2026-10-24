// Themed scenes for practice modules (app/activities/practice_modules.py's
// `scene`). Each is a tiny pixel-art animation on a 180x54 canvas, drawn in
// code like the rest of the art (cozy palette), that reacts to typing:
//
//   scene.correct({ ch, progress, wordDone })  // a right key (progress 0..1 of the prompt)
//   scene.miss()                               // a wrong key
//   scene.finish()                             // the prompt is done
//   scene.destroy()                            // stop animating
//
//   const scene = makeScene("fishing", canvas);

const SCENE_W = 180;
const SCENE_H = 54;

const C = {
  ink: "#3b2417",
  cream: "#fbf1dc",
  sky: "#a8d5e2",
  skyLight: "#cfe8ef",
  grass: "#6b8e3a",
  grassDark: "#4a6627",
  soil: "#8b5a2b",
  soilDark: "#5c3a1a",
  wood: "#8b5a2b",
  woodDark: "#5c3a1a",
  water: "#5b9bb5",
  waterDeep: "#3f7a94",
  waterLight: "#8fc3d6",
  gold: "#e8b33e",
  orange: "#d9822b",
  red: "#b8432f",
  white: "#ffffff",
  grey: "#9a958d",
  night: "#1d2340",
  nightLight: "#2f3a63",
};

const lerp = (a, b, t) => a + (b - a) * t;
const clamp01 = (t) => Math.max(0, Math.min(1, t));
// Move `cur` toward `target`, covering `rate` of the gap per second.
const approach = (cur, target, rate, dt) => cur + (target - cur) * (1 - Math.exp(-rate * dt));

function mixColor(a, b, t) {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const ch = (shift) => Math.round(lerp((pa >> shift) & 255, (pb >> shift) & 255, t));
  return `#${((ch(16) << 16) | (ch(8) << 8) | ch(0)).toString(16).padStart(6, "0")}`;
}

class Scene {
  constructor(canvas) {
    canvas.width = SCENE_W;
    canvas.height = SCENE_H;
    this.ctx = canvas.getContext("2d");
    this.t = 0;
    this.progress = 0;
    this.done = false;
    this.parts = [];
    this.alive = true;
    this.setup();
    let last = performance.now();
    const loop = (now) => {
      if (!this.alive) return;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      this.t += dt;
      this.update(dt);
      this.stepParticles(dt);
      this.draw();
      this.drawParticles();
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }

  destroy() {
    this.alive = false;
    cancelAnimationFrame(this.raf);
  }

  // --- events (scenes override, calling super for progress) -------------------
  setup() {}
  update(dt) {}
  draw() {}
  correct(info) {
    this.progress = info.progress;
  }
  miss() {}
  finish() {
    this.done = true;
    this.progress = 1;
  }

  // --- pixel helpers ------------------------------------------------------------
  rect(x, y, w, h, color) {
    this.ctx.fillStyle = color;
    this.ctx.fillRect(Math.round(x), Math.round(y), Math.max(1, Math.round(w)), Math.max(1, Math.round(h)));
  }

  disc(cx, cy, r, color) {
    for (let dy = -r; dy <= r; dy++) {
      const half = Math.round(Math.sqrt(Math.max(0, r * r - dy * dy)));
      this.rect(cx - half, cy + dy, half * 2 + 1, 1, color);
    }
  }

  // Horizontal ellipse, for pots, lily pads, ponds.
  oval(cx, cy, rx, ry, color) {
    for (let dy = -ry; dy <= ry; dy++) {
      const half = Math.round(rx * Math.sqrt(Math.max(0, 1 - (dy * dy) / (ry * ry))));
      this.rect(cx - half, cy + dy, half * 2 + 1, 1, color);
    }
  }

  // Vertical color bands from top to bottom.
  bands(colors, y0 = 0, y1 = SCENE_H) {
    const h = (y1 - y0) / colors.length;
    colors.forEach((c, i) => this.rect(0, y0 + i * h, SCENE_W, h + 1, c));
  }

  line(x0, y0, x1, y1, color) {
    const steps = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0), 1);
    for (let i = 0; i <= steps; i++) this.rect(lerp(x0, x1, i / steps), lerp(y0, y1, i / steps), 1, 1, color);
  }

  burst(x, y, n, colors, { speed = 20, up = 0, gravity = 40, life = 0.7, size = 1 } = {}) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      this.parts.push({
        x, y,
        vx: Math.cos(a) * speed * Math.random(),
        vy: Math.sin(a) * speed * Math.random() - up,
        g: gravity, life, max: life, size,
        c: Array.isArray(colors) ? colors[i % colors.length] : colors,
      });
    }
  }

  stepParticles(dt) {
    for (const p of this.parts) {
      p.vy += p.g * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.life -= dt;
    }
    this.parts = this.parts.filter((p) => p.life > 0);
  }

  drawParticles() {
    for (const p of this.parts) this.rect(p.x, p.y, p.size, p.size, p.c);
  }

  // A tiny "!" or "?" over something, for a moment after a miss.
  mark(x, y, kind = "!") {
    this.rect(x - 2, y - 9, 5, 9, C.cream);
    if (kind === "!") {
      this.rect(x, y - 8, 1, 4, C.red);
      this.rect(x, y - 3, 1, 1, C.red);
    } else {
      this.rect(x - 1, y - 8, 3, 1, C.ink);
      this.rect(x + 1, y - 7, 1, 2, C.ink);
      this.rect(x, y - 5, 1, 1, C.ink);
      this.rect(x, y - 3, 1, 1, C.ink);
    }
  }

  heart(x, y, color = C.red) {
    this.rect(x, y, 2, 2, color);
    this.rect(x + 3, y, 2, 2, color);
    this.rect(x, y + 1, 5, 2, color);
    this.rect(x + 1, y + 3, 3, 1, color);
    this.rect(x + 2, y + 4, 1, 1, color);
  }
}

// --- 1. Fishing: right keys pull the fish to the hook; a miss scares it off. ------

class FishingScene extends Scene {
  setup() {
    this.hookX = 46;
    this.fish = this.newFish();
    this.caught = 0;
    this.scared = 0;
  }

  newFish() {
    const colors = [C.orange, C.gold, "#c86b8a", "#7aa35a"];
    return { x: 200, target: 168, y: 40, color: colors[Math.floor(Math.random() * colors.length)], lift: 0 };
  }

  correct(info) {
    super.correct(info);
    if (info.ch === " " || this.fish.lift) return;
    this.fish.target -= 12;
  }

  miss() {
    if (this.fish.lift) return;
    this.fish.target = Math.min(176, this.fish.target + 40);
    this.scared = 0.7;
    this.burst(this.fish.x, this.fish.y, 8, [C.waterLight, C.white], { speed: 25, up: 15 });
  }

  finish() {
    super.finish();
    this.burst(20, 10, 16, [C.gold, C.cream], { speed: 30, up: 20 });
  }

  update(dt) {
    const f = this.fish;
    this.scared = Math.max(0, this.scared - dt);
    if (f.lift) {
      f.lift += dt;
      f.x = approach(f.x, 22, 4, dt);
      f.y = approach(f.y, 8, 4, dt);
      if (f.lift > 0.9) {
        this.caught += 1;
        this.fish = this.newFish();
      }
      return;
    }
    f.x = approach(f.x, f.target, this.scared ? 9 : 3, dt);
    f.y = 40 + Math.sin(this.t * 3) * 1.5;
    if (f.x < this.hookX + 7) {
      f.lift = 0.01;
      this.burst(f.x, 18, 10, [C.white, C.waterLight], { speed: 20, up: 25 });
    }
    if (Math.random() < dt * 2) this.parts.push({ x: f.x - 2, y: f.y - 2, vx: 0, vy: -8, g: 0, life: 1.2, max: 1.2, size: 1, c: C.waterLight });
  }

  draw() {
    this.bands([C.skyLight, C.sky], 0, 18);
    this.bands([C.water, C.water, C.waterDeep, C.waterDeep], 18, SCENE_H);
    for (let x = (this.t * 6) % 12; x < SCENE_W; x += 12) this.rect(x, 19, 4, 1, C.waterLight);
    // dock and post
    this.rect(0, 13, 34, 3, C.wood);
    this.rect(0, 16, 34, 1, C.woodDark);
    this.rect(26, 16, 3, 20, C.woodDark);
    // bucket with the catch
    this.rect(16, 7, 10, 6, C.grey);
    this.rect(16, 7, 10, 1, C.ink);
    for (let i = 0; i < Math.min(this.caught, 5); i++) this.rect(17 + i * 2, 5, 1, 2, C.orange);
    // rod and line
    this.line(30, 12, 44, 2, C.woodDark);
    this.line(44, 2, this.hookX, 38, "#e9e2d0");
    this.rect(this.hookX - 1, 17, 3, 2, C.red); // bobber
    this.rect(this.hookX, 38, 1, 3, C.ink);
    this.rect(this.hookX - 2, 40, 3, 1, C.ink);
    // fish (faces left, toward the hook; flips when scared)
    const f = this.fish;
    const dir = this.scared ? 1 : -1;
    this.oval(f.x, f.y, 5, 2, f.color);
    this.rect(f.x - dir * 6, f.y - 2, 2, 5, f.color); // tail
    this.rect(f.x + dir * 3, f.y - 1, 1, 1, C.ink); // eye
    if (this.scared) this.mark(f.x, f.y - 3, "!");
    if (this.done) this.heart(30 + Math.sin(this.t * 4) * 2, 2);
  }
}

// --- 2. Garden rows: words plant seeds, right keys water them. ---------------------

class GardenScene extends Scene {
  setup() {
    this.plots = Array.from({ length: 8 }, () => null);
    this.next = 0;
    this.harvested = 0;
    this.can = { x: 20 };
  }

  plant() {
    const old = this.plots[this.next];
    if (old && old.g >= 1) {
      this.harvested += 1;
      this.burst(this.plotX(this.next), 34, 8, [C.gold, C.cream], { speed: 20, up: 20 });
    }
    const crops = ["#d94f6b", C.gold, "#9b6bd1", C.orange];
    this.plots[this.next] = { g: 0, color: crops[Math.floor(Math.random() * crops.length)] };
    this.newest = this.next;
    this.next = (this.next + 1) % this.plots.length;
  }

  plotX(i) {
    return 12 + i * 18;
  }

  correct(info) {
    super.correct(info);
    if (info.wordDone || this.newest === undefined) this.plant();
    if (info.ch === " ") return;
    for (const p of this.plots) if (p) p.g = Math.min(1, p.g + 0.05);
    const x = this.plotX(this.newest);
    for (let i = 0; i < 3; i++) this.parts.push({ x: x - 2 + i * 2, y: 14, vx: 0, vy: 30, g: 60, life: 0.35, max: 0.35, size: 1, c: C.waterLight });
  }

  miss() {
    if (this.newest === undefined) return;
    const p = this.plots[this.newest];
    p.g = Math.max(0, p.g - 0.1);
    this.burst(this.plotX(this.newest), 38, 10, [C.soil, C.soilDark], { speed: 18, up: 10 });
  }

  update(dt) {
    if (this.newest !== undefined) this.can.x = approach(this.can.x, this.plotX(this.newest) + 4, 5, dt);
  }

  draw() {
    this.bands([C.skyLight, C.sky], 0, 38);
    const sunX = 10 + this.progress * 160;
    this.disc(sunX, 10 - Math.sin(this.progress * Math.PI) * 4, 4, C.gold);
    this.rect(0, 36, SCENE_W, 3, C.grass);
    this.bands([C.soil, C.soilDark], 39, SCENE_H);
    this.plots.forEach((p, i) => {
      const x = this.plotX(i);
      this.oval(x, 41, 5, 1, C.soilDark);
      if (!p) return;
      if (p.g < 0.2) {
        this.rect(x - 1, 39, 3, 1, C.soilDark);
        return;
      }
      const h = 2 + p.g * 14;
      this.rect(x, 39 - h, 1, h, C.grassDark);
      if (p.g > 0.3) {
        this.rect(x - 3, 39 - h * 0.5, 3, 2, C.grass);
        this.rect(x + 1, 39 - h * 0.6, 3, 2, C.grass);
      }
      if (p.g >= 0.8) {
        const bloom = p.g >= 1 ? 2 : 1;
        this.disc(x, 39 - h - 1, bloom, p.color);
        this.rect(x, 39 - h - 1, 1, 1, C.gold);
      }
    });
    // watering can
    const cx = this.can.x;
    this.rect(cx, 6, 7, 5, C.grey);
    this.rect(cx - 4, 7, 4, 1, C.grey);
    this.rect(cx + 2, 4, 3, 2, C.ink);
    // basket of harvest
    this.rect(160, 26, 16, 8, C.wood);
    for (let i = 0; i < Math.min(this.harvested, 7); i++) this.disc(162 + i * 2, 25, 1, i % 2 ? C.red : C.orange);
    if (this.done) this.heart(84, 4);
  }
}

// --- 3. Puppy walk: keep typing to walk home; a miss makes the puppy sniff. ------

class PetWalkScene extends Scene {
  setup() {
    this.dist = 0;
    this.target = 0;
    this.sniff = 0;
  }

  correct(info) {
    super.correct(info);
    if (info.ch !== " ") this.target += 5;
  }

  miss() {
    this.sniff = 0.9;
  }

  finish() {
    super.finish();
    this.burst(100, 30, 10, [C.red, "#e88aa0"], { speed: 15, up: 20, gravity: -5, life: 1.2, size: 2 });
  }

  update(dt) {
    this.sniff = Math.max(0, this.sniff - dt);
    if (!this.sniff) this.dist = approach(this.dist, this.target, 4, dt);
  }

  repeat(spacing, parallax, fn) {
    // count slots with integers: deriving k from the fractional x made it
    // jump by one now and then, so every-other-slot trees flickered
    const scroll = this.dist * parallax;
    const first = Math.floor(scroll / spacing) - 1;
    for (let k = first; (k - first) * spacing < SCENE_W + spacing * 2; k++) fn(k * spacing - scroll, k);
  }

  draw() {
    this.bands([C.skyLight, C.sky], 0, 30);
    this.repeat(60, 0.2, (x) => this.oval(x + 30, 30, 32, 8, "#8fb36b"));
    this.rect(0, 30, SCENE_W, 24, C.grass);
    this.rect(0, 44, SCENE_W, 5, "#c9a66b"); // path
    this.repeat(48, 0.5, (x, k) => {
      if (k % 2) return;
      this.rect(x + 10, 22, 3, 12, C.woodDark);
      this.disc(x + 11, 18, 6, C.grassDark);
      this.disc(x + 9, 16, 4, C.grass);
    });
    this.repeat(14, 1, (x) => {
      this.rect(x, 37, 2, 7, C.cream);
      this.rect(x - 4, 39, 14, 1, C.cream);
    });
    this.repeat(23, 1, (x, k) => this.rect(x + 5, 49 + (k % 3), 2, 2, k % 2 ? "#e88aa0" : C.gold));
    // home appears near the end
    const houseX = 140 + (1 - this.progress) * 400;
    if (houseX < SCENE_W) {
      this.rect(houseX, 26, 26, 18, C.cream);
      for (let i = 0; i < 9; i++) this.rect(houseX - 2 + i, 26 - i, 30 - i * 2, 1, C.red);
      this.rect(houseX + 10, 34, 6, 10, C.wood);
    }
    // the puppy (from wardrobe colors: brown with a darker ear)
    const moving = Math.abs(this.target - this.dist) > 0.5 && !this.sniff;
    const step = moving ? Math.floor(this.t * 10) % 2 : 0;
    const px = 66;
    const py = 38 + (moving ? step : 0) * -1;
    this.rect(px, py, 12, 5, "#b07a43"); // body
    this.rect(px + 1, py + 5, 2, 3 - step, "#8b5a2b");
    this.rect(px + 9, py + 5, 2, 2 + step, "#8b5a2b");
    const headY = this.sniff ? py + 3 : py - 4;
    this.rect(px + 10, headY, 6, 5, "#b07a43");
    this.rect(px + 10, headY, 2, 4, C.woodDark); // ear
    this.rect(px + 14, headY + 1, 1, 1, C.ink); // eye
    this.rect(px + 16, headY + 3, 1, 1, C.ink); // nose
    const wag = Math.sin(this.t * 14) > 0 ? -1 : 0;
    this.rect(px - 2, py - 1 + wag, 2, 2, "#b07a43"); // tail
    if (this.sniff) this.mark(px + 14, headY - 1, "?");
  }
}

// --- 4. Moon rocket: right keys fire the engine; fly to the moon. ----------------

class RocketScene extends Scene {
  setup() {
    this.thrust = 0;
    this.wobble = 0;
    this.scroll = 0;
    this.pos = { x: 90, y: 30 };
    this.stars = Array.from({ length: 40 }, () => ({ x: Math.random() * SCENE_W, y: Math.random() * SCENE_H }));
  }

  correct(info) {
    super.correct(info);
    if (info.ch !== " ") this.thrust = 1;
  }

  miss() {
    this.wobble = 0.6;
    this.burst(90, 44, 8, [C.grey, "#c8c3ba"], { speed: 12, gravity: -10, life: 0.9, size: 2 });
  }

  update(dt) {
    this.thrust = Math.max(0, this.thrust - dt * 2.5);
    this.wobble = Math.max(0, this.wobble - dt);
    this.scroll += (6 + this.thrust * 40) * dt;
    // at the end it flies over to the moon
    this.pos.x = approach(this.pos.x, this.done ? 128 : 90, 2, dt);
    this.pos.y = approach(this.pos.y, this.done ? 20 : 30, 2, dt);
    if (this.thrust > 0.3) this.parts.push({ x: this.pos.x - 1 + Math.random() * 3, y: this.pos.y + 16, vx: 0, vy: 30, g: 0, life: 0.25, max: 0.25, size: 1, c: Math.random() < 0.5 ? C.orange : C.gold });
  }

  draw() {
    const p = this.progress;
    const top = mixColor(C.sky, "#05060f", clamp01(p * 1.5));
    const bottom = mixColor(C.skyLight, C.night, clamp01(p * 1.5));
    this.bands([top, mixColor(top, bottom, 0.5), bottom]);
    for (const s of this.stars) {
      if (p < 0.15) break;
      const y = (s.y + this.scroll) % SCENE_H;
      this.rect(s.x, y, 1, 1, Math.random() < 0.02 ? C.gold : C.cream);
    }
    // earth falls away, moon comes closer
    const groundY = 48 + p * 120;
    if (groundY < SCENE_H) {
      this.rect(0, groundY, SCENE_W, SCENE_H, C.grass);
      this.rect(84, groundY - 2, 12, 2, C.grey); // launch pad
    }
    const moonR = Math.round(3 + p * 14);
    const moonY = this.done ? 14 : -8 + p * 20;
    this.disc(140, moonY, moonR, "#e9e2d0");
    this.disc(140 - moonR / 3, moonY - moonR / 4, Math.max(1, Math.round(moonR / 4)), "#cfc6b0");
    // the rocket
    const x = this.pos.x + (this.wobble ? Math.sin(this.t * 40) * 2 : 0);
    const y = this.pos.y;
    this.rect(x - 2, y - 6, 5, 2, C.red); // nose
    this.rect(x - 3, y - 4, 7, 12, C.cream);
    this.rect(x - 1, y - 1, 3, 3, C.water); // window
    this.rect(x - 5, y + 4, 2, 4, C.red);
    this.rect(x + 4, y + 4, 2, 4, C.red);
    if (this.thrust > 0.05) {
      const h = 2 + Math.round(this.thrust * 5 + Math.random() * 2);
      this.rect(x - 2, y + 8, 5, h, C.orange);
      this.rect(x - 1, y + 8, 3, h - 1, C.gold);
    }
  }
}

// --- 5. Potion lab: words drop ingredients in; a miss puffs smoke. ----------------

class PotionScene extends Scene {
  setup() {
    this.liquid = "#6fae6a";
    this.drops = [];
    this.shake = 0;
  }

  correct(info) {
    super.correct(info);
    if (info.ch !== " ") this.parts.push({ x: 82 + Math.random() * 16, y: 32, vx: 0, vy: -12, g: 0, life: 0.8, max: 0.8, size: 1, c: mixColor(this.liquid, C.white, 0.5) });
    if (info.wordDone) {
      const colors = ["#9b6bd1", C.gold, "#d94f6b", C.water, "#e88aa0", "#7aa35a"];
      this.drops.push({ x: 80 + Math.random() * 20, y: -4, c: colors[Math.floor(Math.random() * colors.length)] });
    }
  }

  miss() {
    this.shake = 0.4;
    this.burst(90, 26, 14, [C.grey, "#c8c3ba", "#7d7871"], { speed: 14, gravity: -15, life: 1.0, size: 2 });
  }

  finish() {
    super.finish();
    this.burst(150, 30, 20, [C.gold, C.cream, this.liquid], { speed: 30, up: 10, gravity: 5, life: 1.2 });
  }

  update(dt) {
    this.shake = Math.max(0, this.shake - dt);
    for (const d of this.drops) d.y += 50 * dt;
    for (const d of this.drops.filter((d) => d.y >= 31)) {
      this.liquid = mixColor(this.liquid, d.c, 0.45);
      this.burst(d.x, 31, 8, [d.c, C.white], { speed: 18, up: 15 });
    }
    this.drops = this.drops.filter((d) => d.y < 31);
  }

  draw() {
    this.bands(["#d8c7a0", "#cdb98e"], 0, 46);
    this.rect(0, 46, SCENE_W, 8, C.woodDark);
    // shelves with bottles
    for (const sx of [10, 128]) {
      this.rect(sx, 16, 40, 2, C.wood);
      ["#9b6bd1", C.gold, "#d94f6b", C.water].forEach((c, i) => {
        this.rect(sx + 3 + i * 9, 9, 5, 7, c);
        this.rect(sx + 4 + i * 9, 7, 3, 2, C.cream);
      });
    }
    const jx = this.shake ? Math.sin(this.t * 50) : 0;
    // fire under the pot
    for (let i = 0; i < 5; i++) this.rect(80 + i * 4 + jx, 45 - ((this.t * 8 + i) % 3), 2, 3, i % 2 ? C.orange : C.gold);
    this.oval(90 + jx, 38, 15, 8, "#3d3a40"); // pot
    this.oval(90 + jx, 30, 15, 3, "#55515a"); // rim
    this.oval(90 + jx, 30, 12, 2, this.liquid);
    for (const d of this.drops) {
      this.rect(d.x, d.y, 3, 3, d.c);
      this.rect(d.x + 1, d.y - 1, 1, 1, C.cream);
    }
    if (this.done) {
      this.rect(146, 26, 8, 10, this.liquid);
      this.rect(148, 22, 4, 4, C.cream);
      this.rect(147, 21, 6, 1, C.wood);
    }
  }
}

// --- 6. Mountain hike: every right key is a step up the trail. ---------------------

class HikeScene extends Scene {
  setup() {
    this.shown = 0;
    this.trail = [[28, 50], [70, 44], [44, 36], [86, 28], [66, 20], [104, 13], [112, 8]];
    this.clouds = [{ x: 20, y: 8 }, { x: 120, y: 14 }];
  }

  miss() {
    this.shown = Math.max(0, this.shown - 0.02);
    const [x, y] = this.at(this.shown);
    this.burst(x, y + 2, 6, [C.grey, C.soil], { speed: 12, gravity: 50 });
  }

  finish() {
    super.finish();
    this.burst(112, 6, 18, [C.red, C.gold, C.water, C.cream], { speed: 30, up: 25, life: 1.2 });
  }

  at(t) {
    const pts = this.trail;
    const segs = pts.length - 1;
    const f = clamp01(t) * segs;
    const i = Math.min(segs - 1, Math.floor(f));
    const k = f - i;
    return [lerp(pts[i][0], pts[i + 1][0], k), lerp(pts[i][1], pts[i + 1][1], k)];
  }

  update(dt) {
    this.shown = approach(this.shown, this.progress, 3, dt);
    for (const c of this.clouds) c.x = ((c.x + dt * 4 + 30) % (SCENE_W + 60)) - 30;
  }

  draw() {
    this.bands([C.skyLight, C.sky]);
    for (const c of this.clouds) {
      this.oval(c.x, c.y, 9, 2, C.white);
      this.oval(c.x + 5, c.y - 2, 5, 2, C.white);
    }
    // the mountain, with a snowy cap
    for (let y = 6; y < SCENE_H; y++) {
      const half = (y - 6) * 1.6;
      this.rect(112 - half, y, half * 2, 1, y < 13 ? C.cream : y % 7 === 0 ? "#7d8a6a" : "#8a9a72");
    }
    this.rect(0, 50, SCENE_W, 4, C.grass);
    for (const tx of [8, 18, 150, 166]) {
      for (let i = 0; i < 6; i++) this.rect(tx - i, 40 + i * 2, i * 2 + 1, 2, C.grassDark);
      this.rect(tx, 52, 1, 2, C.woodDark);
    }
    // trail
    for (let i = 0; i < this.trail.length - 1; i++) {
      const [x0, y0] = this.trail[i];
      const [x1, y1] = this.trail[i + 1];
      const steps = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0));
      for (let s = 0; s <= steps; s += 3) this.rect(lerp(x0, x1, s / steps), lerp(y0, y1, s / steps), 2, 1, "#e0c896");
    }
    // flag at the top
    this.rect(112, 0, 1, 8, C.woodDark);
    const wave = Math.floor(this.t * (this.done ? 10 : 4)) % 2;
    this.rect(113, 1 + wave, 6, 3, C.red);
    // the hiker
    const [hx, hy] = this.at(this.shown);
    const bob = Math.floor(this.t * 8) % 2;
    this.rect(hx - 1, hy - 6 - bob, 3, 3, "#e9b48a"); // head
    this.rect(hx - 1, hy - 3, 3, 3, C.water); // shirt
    this.rect(hx - 3, hy - 3, 2, 3, C.orange); // backpack
    this.rect(hx - 1, hy, 1, 2, C.ink);
    this.rect(hx + 1, hy, 1, 2, C.ink);
  }
}

// --- 7. Leaf catcher: right keys catch falling leaves; a gust blows one away. ------

class LeavesScene extends Scene {
  setup() {
    this.leaves = [];
    this.caught = 0;
    this.basketX = 90;
    this.gust = 0;
    this.spawnClock = 0;
  }

  spawn() {
    const colors = [C.orange, C.red, C.gold, "#c96a2b"];
    this.leaves.push({ x: 10 + Math.random() * 160, y: -3, sway: Math.random() * 6, c: colors[Math.floor(Math.random() * 4)], state: "fall" });
  }

  correct(info) {
    super.correct(info);
    if (info.ch === " ") return;
    let leaf = this.leaves.filter((l) => l.state === "fall").sort((a, b) => b.y - a.y)[0];
    if (!leaf) {
      this.spawn();
      leaf = this.leaves[this.leaves.length - 1];
    }
    leaf.state = "catch";
  }

  miss() {
    this.gust = 0.8;
    const leaf = this.leaves.find((l) => l.state === "fall");
    if (leaf) leaf.state = "blown";
  }

  finish() {
    super.finish();
    this.burst(this.basketX, 40, 16, [C.gold, C.cream], { speed: 25, up: 20 });
  }

  update(dt) {
    this.gust = Math.max(0, this.gust - dt);
    this.spawnClock += dt;
    if (this.spawnClock > 0.6) {
      this.spawnClock = 0;
      this.spawn();
    }
    const target = this.leaves.find((l) => l.state === "catch");
    this.basketX = approach(this.basketX, target ? target.x : this.basketX, 4, dt);
    for (const l of this.leaves) {
      if (l.state === "fall") {
        l.y += 10 * dt;
        l.x += Math.sin(this.t * 2 + l.sway) * 6 * dt + (this.gust ? 25 * dt : 0);
      } else if (l.state === "catch") {
        l.x = approach(l.x, this.basketX, 6, dt);
        l.y = approach(l.y, 40, 6, dt);
        if (Math.abs(l.y - 40) < 1.5) {
          l.state = "in";
          this.caught += 1;
        }
      } else if (l.state === "blown") {
        l.x += 80 * dt;
        l.y -= 10 * dt;
      }
    }
    this.leaves = this.leaves.filter((l) => l.state !== "in" && l.y < 52 && l.x < SCENE_W + 5);
  }

  draw() {
    this.bands([C.skyLight, C.sky], 0, 44);
    this.rect(0, 44, SCENE_W, 10, C.grass);
    // the tree
    this.rect(8, 10, 5, 34, C.woodDark);
    for (const [x, y, r, c] of [[10, 8, 10, C.orange], [24, 6, 8, C.red], [2, 14, 7, C.gold], [18, 14, 7, "#c96a2b"]]) this.disc(x, y, r, c);
    if (this.gust) for (let i = 0; i < 4; i++) this.rect(((this.t * 120 + i * 40) % 200) - 10, 10 + i * 8, 10, 1, C.white);
    for (const l of this.leaves) {
      this.rect(l.x, l.y, 3, 2, l.c);
      this.rect(l.x + 1, l.y + 2, 1, 1, C.woodDark);
    }
    // basket with the pile growing
    const bx = this.basketX;
    const pile = Math.min(6, Math.floor(this.caught / 4));
    for (let i = 0; i < pile; i++) this.rect(bx - 6 + (i % 3) * 4, 39 - Math.floor(i / 3) * 2, 4, 2, [C.orange, C.red, C.gold][i % 3]);
    this.rect(bx - 8, 41, 17, 7, C.wood);
    this.rect(bx - 8, 41, 17, 1, C.woodDark);
    for (let x = bx - 7; x < bx + 8; x += 3) this.rect(x, 42, 1, 6, C.woodDark);
  }
}

// --- 8. Star map: each word lights a star; finish to see the constellation. -------

class StarsScene extends Scene {
  setup() {
    // A fox: ears, face, and a curly tail.
    this.pts = [[40, 40], [56, 22], [62, 10], [70, 20], [82, 20], [90, 10], [96, 22], [108, 34], [92, 44], [76, 48], [120, 40], [138, 30], [150, 18], [146, 8]];
    this.edges = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 8], [8, 9], [9, 0], [7, 10], [10, 11], [11, 12], [12, 13]];
    this.lit = 0;
    this.cloud = -60;
    this.sky = Array.from({ length: 50 }, () => [Math.random() * SCENE_W, Math.random() * SCENE_H, Math.random() * 6]);
  }

  // Stars light up in order as the prompt goes; the next one glows brighter
  // as you get closer to it.
  correct(info) {
    super.correct(info);
    const want = Math.min(this.pts.length, Math.floor(info.progress * this.pts.length));
    while (this.lit < want) {
      const [x, y] = this.pts[this.lit];
      this.lit += 1;
      this.burst(x, y, 8, [C.gold, C.cream], { speed: 15, gravity: 0, life: 0.6 });
    }
  }

  miss() {
    this.cloud = -50;
  }

  finish() {
    super.finish();
    this.lit = this.pts.length;
  }

  update(dt) {
    if (this.cloud < SCENE_W + 60) this.cloud += 70 * dt;
  }

  draw() {
    this.bands([C.night, "#232b4d", C.nightLight]);
    for (const [x, y, ph] of this.sky) if (Math.sin(this.t * 2 + ph) > -0.3) this.rect(x, y, 1, 1, "#8a90b8");
    this.disc(14, 10, 4, "#e9e2d0");
    this.disc(16, 9, 4, C.night);
    const glow = this.done ? C.gold : "#e9d58a";
    for (const [a, b] of this.edges) {
      if (a < this.lit && b < this.lit) this.line(...this.pts[a], ...this.pts[b], this.done ? C.gold : "#6d74a8");
    }
    this.pts.forEach(([x, y], i) => {
      if (i < this.lit) {
        const tw = Math.sin(this.t * 5 + i) > 0.6 ? 1 : 0;
        this.rect(x - 1 - tw, y, 3 + tw * 2, 1, glow);
        this.rect(x, y - 1 - tw, 1, 3 + tw * 2, glow);
      } else {
        this.rect(x, y, 1, 1, "#4b527d");
      }
    });
    const charge = this.progress * this.pts.length - this.lit;
    if (this.lit < this.pts.length && charge > 0.3) {
      const [x, y] = this.pts[this.lit];
      this.disc(x, y, Math.round(charge * 2), "#b8b070");
    }
    if (this.cloud < SCENE_W + 40) {
      this.oval(this.cloud, 22, 22, 5, "#3b4366");
      this.oval(this.cloud + 12, 18, 12, 4, "#3b4366");
    }
    if (this.done) {
      const s = (this.t * 60) % 260;
      this.line(170 - s, s * 0.2, 176 - s, s * 0.2 - 2, C.cream);
    }
  }
}

// --- 9. Campfire: right keys add sparks, mistakes let it shrink; toast a marshmallow.

class CampfireScene extends Scene {
  setup() {
    this.heat = 0.4;
    this.flies = Array.from({ length: 6 }, () => ({ x: Math.random() * SCENE_W, y: 10 + Math.random() * 25, p: Math.random() * 6 }));
  }

  correct(info) {
    super.correct(info);
    if (info.ch === " ") return;
    this.heat = Math.min(1, this.heat + 0.06);
    this.burst(90, 36, 2, [C.gold, C.orange], { speed: 8, up: 30, gravity: -5, life: 0.8 });
  }

  miss() {
    this.heat = Math.max(0.15, this.heat - 0.15);
    this.burst(90, 30, 10, [C.grey, "#6d6a66"], { speed: 10, gravity: -15, life: 1.1, size: 2 });
  }

  finish() {
    super.finish();
    this.heat = 1;
    this.burst(110, 24, 10, [C.red, "#e88aa0"], { speed: 12, up: 15, gravity: -5, life: 1.3, size: 2 });
  }

  update(dt) {
    this.heat = Math.max(0.2, this.heat - dt * 0.05);
    for (const f of this.flies) {
      f.x += Math.sin(this.t + f.p) * 6 * dt;
      f.y += Math.cos(this.t * 1.3 + f.p) * 4 * dt;
    }
  }

  draw() {
    this.bands([C.night, "#252b4a", "#2f3654"], 0, 40);
    this.rect(0, 40, SCENE_W, 14, "#2c3b22");
    for (const tx of [12, 30, 150, 168]) for (let i = 0; i < 8; i++) this.rect(tx - i, 12 + i * 3, i * 2 + 1, 3, "#1a2418");
    for (const f of this.flies) if (Math.sin(this.t * 3 + f.p) > 0) this.rect(f.x, f.y, 1, 1, "#e9f28a");
    // warm glow around the fire
    this.ctx.globalAlpha = 0.08 + this.heat * 0.1;
    this.disc(90, 40, Math.round(10 + this.heat * 10), C.gold);
    this.disc(90, 40, Math.round(6 + this.heat * 6), C.gold);
    this.ctx.globalAlpha = 1;
    // logs
    this.line(78, 47, 102, 42, C.woodDark);
    this.line(78, 42, 102, 47, C.wood);
    this.rect(78, 44, 24, 2, C.woodDark);
    // flames
    const h = 5 + this.heat * 16;
    for (let i = 0; i < 6; i++) {
      const fh = h * (0.6 + 0.4 * Math.abs(Math.sin(this.t * 9 + i * 1.7)));
      const x = 82 + i * 3;
      this.rect(x, 43 - fh, 3, fh, C.red);
      this.rect(x, 43 - fh * 0.75, 3, fh * 0.75, C.orange);
      this.rect(x + 1, 43 - fh * 0.45, 1, fh * 0.45, C.gold);
    }
    // marshmallow on a stick, toasting with progress
    const toast = this.progress;
    const color = toast < 0.6 ? mixColor("#fff8ee", C.gold, toast / 0.6) : mixColor(C.gold, "#a0612b", (toast - 0.6) / 0.4 * 0.6);
    this.line(150, 34, 104, 26, C.wood);
    this.rect(100, 23, 5, 5, color);
    if (this.done) this.mark(102, 22, "!");
  }
}

// --- 10. Lily pad hop: each word is a hop; a miss is a wobble and a splash. -------

class FrogScene extends Scene {
  setup() {
    this.pad = 0;
    this.hop = null; // {from, t}
    this.cam = 0;
    this.wobble = 0;
    this.fly = { x: 0, y: 0 };
  }

  padX(i) {
    return 24 + i * 30;
  }

  correct(info) {
    super.correct(info);
    if (info.wordDone && !this.hop) this.hop = { from: this.pad, t: 0 };
  }

  miss() {
    this.wobble = 0.5;
    this.burst(this.padX(this.pad) - this.cam, 42, 10, [C.white, C.waterLight], { speed: 20, up: 20 });
  }

  finish() {
    super.finish();
    this.burst(this.fly.x, this.fly.y, 10, [C.gold, C.cream], { speed: 15, gravity: 0 });
  }

  update(dt) {
    this.wobble = Math.max(0, this.wobble - dt);
    if (this.hop) {
      this.hop.t += dt / 0.35;
      if (this.hop.t >= 1) {
        this.pad = this.hop.from + 1;
        this.hop = null;
        this.burst(this.padX(this.pad) - this.cam, 42, 5, [C.waterLight], { speed: 12, up: 10 });
      }
    }
    this.cam = approach(this.cam, this.padX(this.pad) - 50, 3, dt);
    this.fly = { x: 120 + Math.sin(this.t * 3) * 20, y: 14 + Math.cos(this.t * 5) * 6 };
  }

  draw() {
    this.bands([C.waterLight, C.water, C.water, C.waterDeep]);
    for (let i = 0; i < 6; i++) this.rect(((i * 37 - this.cam * 0.5) % 200 + 200) % 200 - 10, 8 + i * 7, 6, 1, C.skyLight);
    // reeds
    for (let i = 0; i < 8; i++) {
      const x = ((i * 53 - this.cam) % 220 + 220) % 220 - 20;
      this.rect(x, 2, 1, 14, C.grassDark);
      this.rect(x - 1, 2, 3, 4, C.wood);
    }
    const first = Math.floor(this.cam / 30) - 1;
    for (let i = Math.max(0, first); i < first + 9; i++) {
      const x = this.padX(i) - this.cam;
      const bob = Math.sin(this.t * 2 + i) * 0.6;
      this.oval(x, 44 + bob, 9, 3, C.grass);
      this.rect(x + 2, 42 + bob, 4, 2, C.water); // notch
      if (i % 3 === 1) this.disc(x - 4, 42 + bob, 1, "#e88aa0");
    }
    // the frog
    let fx = this.padX(this.pad) - this.cam;
    let fy = 40;
    if (this.hop) {
      fx = lerp(this.padX(this.hop.from), this.padX(this.hop.from + 1), this.hop.t) - this.cam;
      fy = 40 - Math.sin(this.hop.t * Math.PI) * 14;
    }
    fx += this.wobble ? Math.sin(this.t * 40) * 1.5 : 0;
    this.oval(fx, fy, 5, 3, "#5f9e3a");
    this.rect(fx - 4, fy - 4, 3, 3, "#5f9e3a");
    this.rect(fx + 2, fy - 4, 3, 3, "#5f9e3a");
    this.rect(fx - 3, fy - 3, 1, 1, C.ink);
    this.rect(fx + 3, fy - 3, 1, 1, C.ink);
    this.rect(fx - 6, fy + 2, 3, 1, "#4a7f2c");
    this.rect(fx + 4, fy + 2, 3, 1, "#4a7f2c");
    if (this.wobble) this.mark(fx, fy - 5, "!");
    // a fly to catch at the end
    if (!this.done || this.t % 1 < 0.5) {
      this.rect(this.fly.x, this.fly.y, 2, 1, C.ink);
      this.rect(this.fly.x, this.fly.y - 1, 1, 1, C.cream);
    }
    if (this.done) this.line(fx + 1, fy - 1, this.fly.x, this.fly.y, "#d94f6b");
  }
}

const SCENES = {
  fishing: FishingScene,
  garden: GardenScene,
  pet_walk: PetWalkScene,
  rocket: RocketScene,
  potion: PotionScene,
  hike: HikeScene,
  leaves: LeavesScene,
  stars: StarsScene,
  campfire: CampfireScene,
  frog: FrogScene,
};

function makeScene(name, canvas) {
  const SceneClass = SCENES[name];
  return SceneClass ? new SceneClass(canvas) : null;
}
