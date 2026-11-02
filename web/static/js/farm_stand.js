// Farm Stand (game_farm_stand_v1): grow veggies, sell them at your stand.
// The farm itself is saved (app/farm_stand.py): its money, plots, shelf,
// upgrades and the crops it has opened. One play is one day of HOURS hours,
// in real time:
//
//   ready     nothing moves until you plant your first seed; the first
//             customer comes FIRST_CUSTOMER seconds after that.
//   hours     crops grow in seconds; ripe ones move onto the shelf while it
//             has room. Customers (grown animals) keep coming: their orders
//             wait in a stack in the sky, and the bottom one drops down to
//             each animal that walks up. Type a customer's word to sell them
//             their order -- or, short of something, a swap for less money.
//             The line keeps itself full (up to 3), and they wait a long
//             time, so you pick who to serve. Delivery orders hang in the
//             sky at the top left; type one's word and your pet carries it
//             off (they have deadlines). Seed packets stay out below:
//             replant any time.
//   between   each hour's tally (coins); the day picks up where it was.
//   evening   the day's stars, money and reputation (saved only for an arcade
//             play), then the farm shop.
//
// Words come in groups: every seed starts with one letter, every customer
// with another, every delivery with a third (PrefixTyper). The first key
// lights up its group, the next keys pick one.
//
// Your pets along help: the first carries deliveries (a small tip); the
// second (or the only one) is the gardener, hopping around a pet plot that
// it replants with its favorite veggie; and a customer of the same kind
// gets a happy hello (and waits longer).
//
// Needs practice_scenes.js (Scene, C), veggies.js, pet_render.js, avatar.js,
// game_kit.js, and crow_patrol.js (placeInside) loaded first.

const FARM_W = 240;
const FARM_H = 120;
const QUEUE_X = [170, 199, 228]; // where customers stand, nearest the stand first
const CUSTOMER_BOX = { w: 30, h: 28 };
const PET_BOX = { w: 24, h: 20 };
const CUSTOMER_GROUND = 114;
const PET_HOME_X = 150; // the courier waits by the stand
const PET_GROUND = 118;
// The plots fill this area; with more plots, the grid gets more rows and
// smaller cells (your plots first, then the pet's, then the robot's).
const FIELD_AREA = { x: 2, y: 64, w: 93, h: 54 };
const ICON = { w: 24, h: 28 }; // a veggie icon on a ticket (drawn at this size: hidden ones have no layout)
const SMALL_ICON = { w: 18, h: 21 };
const STACK_X = 205; // the orders coming, stacked in the sky
const STACK_BOTTOM = 34;
const STACK_STEP = 9;
const SHOW_NEXT = 4;
const FIRST_CUSTOMER = 10; // seconds after the first seed
const ARRIVE_GAP = 1.5; // seconds between animals when the line has room
const PATIENCE = 4; // the line is always full, so each animal waits a long time
const FRIEND_PATIENCE = 1.25;
const PET_SPEED = 55; // field px a second, on a delivery
const PET_AWAY = 2; // seconds out of sight
const FARM_POINTS = { served: 20, big: 30, fancy: 40, delivery: 60, veggie: 5, tip: 2 };
const FANCY_SIZE = 1.5; // fancy customers want 50% more
const FANCY_PATIENCE = 0.5;
// app/farm_stand.py stars_for: 3 stars (and pet food) for 80% happy, at least 6
const GREAT_SHARE = 0.8;
const GOOD_SHARE = 0.5;
const GREAT_MIN_SERVED = 6;
const AVG_LEN = { short: 2.5, medium: 4.5, long: 6.5 };

const FARM_SKIES = [
  ["#f6d8b0", "#cfe8ef", "#a8d5e2"],
  ["#cfe8ef", "#a8d5e2", "#8fc3d6"],
  ["#cfe8ef", "#a8d5e2", "#8fc3d6"],
  ["#f3d9a4", "#cfe8ef", "#a8d5e2"],
  ["#e8a06b", "#f3c27a", "#f6d8b0"], // evening
];

const SPECIES_NAMES = {
  dog: "Dog", cat: "Cat", bunny: "Bunny", fox: "Fox", sheep: "Sheep", goat: "Goat", llama: "Llama",
  turtle: "Turtle", lizard: "Lizard", snake: "Snake", dragon: "Dragon", unicorn: "Unicorn", phoenix: "Phoenix", flower_fairy: "Flower fairy",
};

class FarmStand {
  constructor(shell, content, me) {
    this.shell = shell;
    this.game = content.game;
    this.rules = this.game.rules;
    this.avatar = me && me.avatar;
    this.farm = this.game.farm;
    this.typer = new PrefixTyper();
    this.hour = 0;
    this.clock = 0; // seconds into the hour
    this.state = "start"; // start | ready | hour | tally | evening | shop
    this.customers = [];
    this.bubbles = [];
    this.shopCards = [];
    this.day = { served: 0, missed: 0, sold: {}, earned: 0, spent: 0 };
    this.stats = this.newStats();
    this.money = this.farm.money;
    this.shelf = {};
    this.letters = this.groupLetters();

    // your pets along: the first carries deliveries; one tends the pet plot
    this.pets = ((this.avatar && this.avatar.pets) || []).map((p) => ({
      ...p, x: PET_HOME_X, tx: null, rest: 0, dir: 1, trip: null, joy: 0, hop: 0,
    }));
    this.courier = this.pets[0] || null;
    this.gardener = this.pets[1] || this.pets[0] || null;
    const plot = (kind) => ({ crop: null, grown: 0, left: 0, kind });
    this.plots = Array.from({ length: this.farm.plots }, () => plot("mine"));
    this.petPlots = this.gardener ? Array.from({ length: this.farm.pet_plots }, () => plot("pet")) : [];
    this.robotPlots = Array.from({ length: this.farm.robot_plots }, () => plot("robot"));
    this.robotCrop = null; // the first seed you plant today
    this.layoutPlots();
    if (this.gardener) this.gardener.x = this.petHome(this.gardener);

    this.packets = this.farm.crops.map((crop) => ({ crop, group: "seeds", word: null, typed: 0 }));
    this.deliveries = this.game.deliveries.map((d) => ({
      ...d, pet: this.game.customers[d.customer], group: "deliveries", word: null, typed: 0, done: false, missed: false,
    }));
    this.line = []; // customers on their way: their orders stack up in the sky
    this.deliveryBox = document.createElement("div");
    this.deliveryBox.className = "farm-deliveries";
    shell.els.layer.appendChild(this.deliveryBox);
    this.cheer = 0;
    this.belowKey = "";
    this.fillLine();

    const game = this;
    this.scene = new (class extends Scene {
      update(dt) {
        game.update(dt, this);
      }
      draw() {
        game.draw(this);
      }
    })(shell.els.canvas, FARM_W, FARM_H);
    shell.els.canvas.classList.add("farm-field");
    this.renderHud();
    this.startScreen();
    window.addEventListener("keydown", (e) => this.handleKey(e));
  }

  crop(id) {
    return this.farm.crops.find((c) => c.id === id);
  }

  newStats() {
    return { served: 0, big: 0, fancy: 0, deliveries: 0, veggies: 0, tips: 0 };
  }

  allPlots() {
    return [...this.plots, ...this.petPlots, ...this.robotPlots];
  }

  // A grid sized to fit every plot: 6 a row while it fits, 8 after; cells
  // shrink so up to 4 rows fit FIELD_AREA.
  layoutPlots() {
    const all = this.allPlots();
    const n = all.length;
    const rows = Math.min(4, Math.ceil(n / (n <= 18 ? 6 : 8)));
    const cols = Math.ceil(n / rows);
    this.cell = { w: Math.min(15, Math.floor(FIELD_AREA.w / cols)), h: Math.min(23, Math.floor(FIELD_AREA.h / rows)) };
    all.forEach((p, i) => {
      p.x = FIELD_AREA.x + (i % cols) * this.cell.w;
      p.y = FIELD_AREA.y + Math.floor(i / cols) * this.cell.h;
    });
  }

  // --- flow -----------------------------------------------------------------

  startScreen() {
    this.state = "start";
    this.shell.setLabel("Game · Farm Stand");
    const f = this.farm;
    const next = f.next_crop ? `<p>At ${f.next_crop.rep} reputation: <b>${escapeHtml(f.next_crop.name)}</b> seeds!</p>` : "";
    const helper = this.courier ? `<p>${escapeHtml(this.courier.name)} is here to help!</p>` : "";
    this.shell.showScreen(
      `<h2>Day ${f.day + 1} on your farm</h2>
       <p>Money <b>$${this.money}</b> · Reputation <b>${f.reputation}</b> · ${f.plots} plots</p>
       ${f.day === 0 ? "<p>Plant seeds, sell veggies to the animals, and send the delivery orders. Happy customers make your farm famous!</p>" : ""}
       ${helper}${next}
       <p class="farm-goal">★★★ Keep 8 of 10 customers happy for a free veggie for your pets!</p>
       <p>Press ${keycap(" ")} to go to the farm, or ${keycap("Enter")} for the farm shop.</p>`,
      { " ": () => this.ready(), Enter: () => this.openShop(() => this.startScreen()) }
    );
  }

  // The stand opens with the first seed you plant.
  ready() {
    this.shell.hideScreen();
    this.state = "ready";
    this.shell.setLabel("Game · Morning");
    this.ensureWords();
    this.renderBelow(true);
    this.renderHud();
  }

  startHour() {
    this.hour += 1;
    this.clock = 0;
    this.state = "hour";
    this.stats = this.newStats();
    this.shell.setLabel(`Game · Hour ${this.hour} of ${this.game.hours}`);
    if (this.hour === 1) this.arriveIn = FIRST_CUSTOMER;
    for (const c of this.customers) c.el.hidden = false;
    this.renderBelow(true);
    this.renderHud();
  }

  hourSeconds() {
    return this.game.levels[this.hour - 1].seconds;
  }

  async endHour() {
    this.state = "tally";
    this.typer.release(this.worded());
    const last = this.hour >= this.game.hours;
    for (const d of this.deliveries) {
      if (!d.done && !d.missed && d.due <= this.hour) {
        d.missed = true;
        this.day.missed += 1;
      }
    }
    if (last) for (const c of this.waiting()) this.leave(c, null); // closing time: no one's counted
    for (const c of this.customers) c.el.hidden = true;
    const s = this.stats;
    await this.shell.roundTally({
      title: last ? "Closing time!" : `Hour ${this.hour} done!`,
      rows: [
        { label: "Happy customers", count: s.served, each: FARM_POINTS.served, always: true },
        { label: "Deliveries", count: s.deliveries, each: FARM_POINTS.delivery },
        { label: "Big baskets", count: s.big, each: FARM_POINTS.big },
        { label: "Fancy customers", count: s.fancy, each: FARM_POINTS.fancy },
        { label: "Veggies sold", count: s.veggies, each: FARM_POINTS.veggie },
        { label: "Tips", points: s.tips * FARM_POINTS.tip },
      ],
      typer: this.typer,
    });
    if (last) this.evening();
    else this.startHour();
  }

  async evening() {
    this.state = "evening";
    this.shell.els.below.innerHTML = "";
    for (const c of this.line) c.el.remove();
    this.deliveryBox.remove();
    this.shell.setLabel("Game · Evening");
    this.day.earned = Math.round(this.day.earned);
    const res = await fetch("/api/farm/day", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(this.day),
    });
    const out = await res.json();
    if (!res.ok) {
      this.shell.showScreen(`<h2>Hmm!</h2><p>${escapeHtml(out.detail || "The day couldn't be saved.")}</p>`, {
        Enter: () => this.shell.finish({ line: "Farm Stand" }),
      });
      return;
    }
    this.farm = out.farm;
    this.money = out.farm.money;
    const stars = "★".repeat(out.stars) + "☆".repeat(3 - out.stars);
    const veggieName = out.veggie && (this.farm.crops.find((c) => c.id === out.veggie) || {}).name;
    const newCrops = out.new_crops.map((id) => this.farm.crops.find((c) => c.id === id).name);
    this.shell.showScreen(
      `<h2>${["Better luck tomorrow!", "Good day!", "Great day!", "Amazing day!"][out.stars]}</h2>
       <p class="stars farm-stars">${stars}</p>
       <p>${this.day.served} happy · ${this.day.missed} missed · Profit <b>$${out.profit}</b>${out.best ? " · NEW BEST DAY!" : ""}</p>
       ${out.counted ? `<p>Farm money <b>$${this.farm.money}</b> · Reputation <b>${this.farm.reputation}</b></p>` : "<p>(A practice day: the farm wasn't changed.)</p>"}
       ${newCrops.length ? `<p><span class="new-tag">NEW!</span> ${newCrops.map(escapeHtml).join(", ")} seeds!</p>` : ""}
       ${veggieName ? `<div class="farm-gift"><canvas class="veggie-icon" data-kind="${out.veggie}" width="64" height="76"></canvas>
         <p><b>PET FOOD!</b> Great job! A ${escapeHtml(veggieName)} for your pets is waiting at the Pet Care Center.</p></div>`
         : out.counted && out.stars < 3 ? "<p>Get 3 stars for a free veggie for your pets!</p>" : ""}
       <p>Press ${keycap(" ")} for the farm shop.</p>`,
      { " ": () => this.openShop(() => this.shell.finish({ line: `Day ${this.farm.day} done!` })) }
    );
    this.shell.els.screen.querySelectorAll(".veggie-icon").forEach((c) => drawVeggieIcon(c, c.dataset.kind));
  }

  // --- the farm shop ------------------------------------------------------------

  openShop(then) {
    this.state = "shop";
    this.afterShop = then;
    this.shopTyper = new Typer();
    const shop = this.farm.shop.filter((u) => u.cost != null);
    // what you can buy, then what opens soonest
    shop.sort((a, b) => b.can_buy - a.can_buy || (a.needs_rep || 0) - (b.needs_rep || 0) || a.cost - b.cost);
    const shown = shop.slice(0, 6);
    const words = pickWords(this.game.words, shown.map(() => "short"));
    this.shopCards = shown.map((u, i) => ({ u, word: words[i], typed: 0 }));
    this.renderShop();
  }

  renderShop(message = "") {
    const cards = this.shopCards
      .map((s, i) => {
        const u = s.u;
        const lv = u.max_level > 1 ? ` ${u.level + 1}/${u.max_level}` : "";
        const why = u.needs_rep ? `Needs ${u.needs_rep} reputation` : u.can_buy ? "" : `$${u.cost - this.farm.money} more to go`;
        return `<div class="choice-card${u.can_buy ? "" : " cant"}${this.shopTyper.target === s ? " locked" : ""}" data-i="${i}">
          <h3>${escapeHtml(u.name)}${lv}</h3>
          <p>${escapeHtml(u.blurb)}</p>
          <p>$${u.cost}</p>
          ${u.can_buy ? `<p class="choice-word">${wordHtml(s.word, s.typed)}</p>` : `<p class="shop-why">${escapeHtml(why)}</p>`}
        </div>`;
      })
      .join("");
    this.shell.showScreen(
      `<h2>Farm Shop</h2>
       <p>Money <b>$${this.farm.money}</b> · Type a word to buy. ${message ? `<b>${escapeHtml(message)}</b>` : ""}</p>
       <div class="choice-cards farm-shop">${cards || "<p>You have everything!</p>"}</div>
       <p>Press ${keycap("Enter")} when you're done.</p>`
    );
    this.shell.screenKeys = null; // typing words here; Enter is handled in handleKey
  }

  async buy(card) {
    const res = await fetch(`/api/farm/buy/${card.u.id}`, { method: "POST" });
    const out = await res.json();
    if (!res.ok) return this.renderShop(out.detail);
    this.farm = out;
    this.money = out.money;
    const name = card.u.name;
    this.openShop(this.afterShop);
    this.renderShop(`${name}!`);
  }

  // --- words ------------------------------------------------------------------

  wordSeconds(group) {
    const cps = Math.max(0.5, this.game.chars_per_second || 1.5);
    return AVG_LEN[group] / cps + 1.2;
  }

  // A starting letter for each group of words: the letters with the most
  // different words, customers (the most words at once) first.
  groupLetters() {
    const all = [...new Set(Object.values(this.game.words).flat())];
    const count = {};
    for (const w of all) count[w[0]] = (count[w[0]] || 0) + 1;
    const best = Object.keys(count).sort((a, b) => count[b] - count[a]);
    return { customers: best[0], seeds: best[1] || best[0], deliveries: best[2] || best[1] || best[0] };
  }

  // Everything that has (or needs) a word right now.
  worded() {
    return [...this.packets, ...this.openDeliveries(), ...this.waiting()];
  }

  // A word in the thing's group: starting with the group's letter, not the
  // start of another word in the group (or the other way round), and if it
  // can be, with a second letter none of the others has.
  pickGroupWord(t, others) {
    const letter = this.letters[t.group];
    const size = t.size || "short";
    const fits = (w) => w[0] === letter && !others.some((o) => o.startsWith(w) || w.startsWith(o));
    let pool = [...new Set(this.game.words[size] || [])].filter(fits);
    if (!pool.length) pool = [...new Set(Object.values(this.game.words).flat())].filter(fits);
    const seconds = new Set(others.map((o) => o[1]));
    const fresh = pool.filter((w) => !seconds.has(w[1]));
    const from = fresh.length ? fresh : pool;
    return from.length ? from[Math.floor(Math.random() * from.length)] : null;
  }

  ensureWords() {
    const all = this.worded();
    for (const t of all) {
      if (t.word) continue;
      const others = all.filter((o) => o !== t && o.word && o.group === t.group).map((o) => o.word);
      t.word = this.pickGroupWord(t, others);
      t.typed = 0;
      t.shown = null;
    }
  }

  reword(t) {
    t.word = null;
    t.typed = 0;
    this.ensureWords();
  }

  // --- planting -----------------------------------------------------------------

  emptyPlots() {
    return this.plots.filter((p) => !p.crop);
  }

  // Seeds can go on credit during the day (money below $0), so you can
  // never get stuck with nothing to sell; a day never saves below $0.
  canPlant() {
    return this.emptyPlots().length > 0;
  }

  plant(packet) {
    const plot = this.emptyPlots()[0];
    const c = packet.crop;
    if (!plot) return;
    Object.assign(plot, { crop: c.id, grown: 0, left: 0 });
    this.money -= c.seed_cost;
    this.day.spent += c.seed_cost;
    this.robotCrop ||= c.id;
    this.scene.burst(plot.x + this.cell.w / 2, plot.y + this.cell.h - 4, 8, [C.soil, C.grass, C.cream], { speed: 20, up: 15 });
    this.reword(packet);
    if (this.state === "ready") this.startHour();
  }

  // The pet's plots replant themselves: its favorite veggie if it can, for free.
  petReplant() {
    for (const p of this.petPlots) {
      if (p.crop) continue;
      const fav = this.gardener.genes.personality && this.gardener.genes.personality.favorite;
      const ids = this.farm.crops.map((c) => c.id);
      p.crop = ids.includes(fav) ? fav : ids[Math.floor(Math.random() * ids.length)];
      p.grown = 0;
      p.planting = true; // the gardener hops over to plant it
      if (!this.gardener.trip) this.gardener.tx = p.x + this.cell.w / 2;
    }
  }

  // Robot plots keep planting your first seed of the day (and pay for it, on credit too).
  robotReplant() {
    const crop = this.robotCrop && this.crop(this.robotCrop);
    if (!crop) return;
    for (const p of this.robotPlots) {
      if (p.crop) continue;
      Object.assign(p, { crop: crop.id, grown: 0, left: 0 });
      this.money -= crop.seed_cost;
      this.day.spent += crop.seed_cost;
      this.scene.burst(p.x + this.cell.w / 2, p.y + this.cell.h - 4, 6, ["#9aa4ad", C.soil], { speed: 15, up: 10 });
    }
  }

  // Plots grow; ripe ones fill the shelf while it has room.
  grow(dt) {
    this.petReplant();
    this.robotReplant();
    for (const p of this.allPlots()) {
      if (!p.crop || p.left) continue;
      p.grown += dt;
      if (p.grown >= this.crop(p.crop).grow) {
        p.left = this.crop(p.crop).yields;
        this.scene.burst(p.x + this.cell.w / 2, p.y + this.cell.h / 2, 5, [C.gold, C.cream], { speed: 15, up: 10 });
        if (p.kind === "pet" && !this.gardener.trip) this.gardener.joy = 1.2;
      }
    }
    this.harvest();
  }

  harvest() {
    let room = this.farm.shelf - this.shelfCount();
    for (const p of this.allPlots()) {
      while (p.left > 0 && room > 0) {
        p.left -= 1;
        room -= 1;
        this.shelf[p.crop] = (this.shelf[p.crop] || 0) + 1;
      }
      if (p.crop && p.grown >= this.crop(p.crop).grow && !p.left) Object.assign(p, { crop: null, grown: 0 });
    }
  }

  shelfCount() {
    return Object.values(this.shelf).reduce((a, b) => a + b, 0);
  }

  takeFromShelf(order) {
    let count = 0;
    for (const [k, n] of Object.entries(order)) {
      this.shelf[k] -= n;
      if (!this.shelf[k]) delete this.shelf[k];
      this.day.sold[k] = (this.day.sold[k] || 0) + n;
      count += n;
    }
    this.stats.veggies += count;
    this.harvest();
    return count;
  }

  hasOrder(order) {
    return Object.entries(order).every(([k, n]) => (this.shelf[k] || 0) >= n);
  }

  // --- customers ----------------------------------------------------------------

  waiting() {
    return this.customers.filter((c) => c.state === "wait" || c.state === "walk");
  }

  // The line: first come is at the front; when someone leaves, everyone
  // behind steps up.
  freeSlot() {
    const n = this.waiting().length;
    return n < QUEUE_X.length ? n : -1;
  }

  closeGaps() {
    this.waiting().forEach((c, i) => (c.slot = i));
  }

  // Customers want the open crops, their favorite more often.
  newCustomer() {
    const pet = this.game.customers[Math.floor(Math.random() * this.game.customers.length)];
    const rep = this.farm.reputation;
    const big = Math.random() < this.farm.big_share;
    const fancy = Math.random() < this.farm.fancy_share;
    let size = big ? 3 + Math.floor(Math.random() * 2) : 1 + Math.floor(Math.random() * (rep >= 15 ? 3 : 2));
    if (fancy) size = Math.ceil(size * FANCY_SIZE);
    const kinds = this.farm.crops.map((c) => c.id);
    const weights = kinds.map((k) => (k === pet.favorite ? 2.5 : 1));
    const total = weights.reduce((a, b) => a + b, 0);
    const order = {};
    for (let i = 0; i < size; i++) {
      let roll = Math.random() * total;
      const k = kinds.find((_, j) => (roll -= weights[j]) <= 0) || kinds[0];
      order[k] = (order[k] || 0) + 1;
    }
    const el = document.createElement("div");
    el.className = `farm-next${big ? " big" : ""}${fancy ? " fancy" : ""}`;
    el.innerHTML = this.orderIcons(order, false, SMALL_ICON);
    this.shell.els.layer.appendChild(el);
    el.querySelectorAll(".veggie-icon").forEach((v) => drawVeggieIcon(v, v.dataset.kind));
    return { pet, big, fancy, order, el, group: "customers", size: big || fancy ? "long" : Math.random() < 0.5 ? "short" : "medium" };
  }

  fillLine() {
    while (this.line.length < SHOW_NEXT) this.line.push(this.newCustomer());
  }

  orderIcons(order, showShort = true, size = ICON) {
    return Object.entries(order)
      .map(([k, n]) => `<span class="${showShort && (this.shelf[k] || 0) < n ? "short" : ""}">${n > 1 ? `${n}×` : ""}<canvas class="veggie-icon" data-kind="${k}" width="${size.w}" height="${size.h}"></canvas></span>`)
      .join("");
  }

  // The bottom order in the sky drops down to the animal walking up.
  arrive() {
    const slot = this.freeSlot();
    if (slot < 0) return false;
    const next = this.line.shift();
    const drop = next.el;
    drop.classList.add("dropping");
    this.placeAt(drop, QUEUE_X[slot], CUSTOMER_GROUND - CUSTOMER_BOX.h - 4);
    setTimeout(() => drop.remove(), 450);
    this.fillLine();
    let patience = (this.wordSeconds(next.size) * 2 + 14) * PATIENCE * this.farm.patience * (next.big ? 1.4 : 1);
    if (next.fancy) patience *= FANCY_PATIENCE;
    const friend = this.pets.find((p) => p.species === next.pet.species);
    if (friend) patience *= FRIEND_PATIENCE;
    const el = document.createElement("div");
    el.className = `crow-word farm-ticket${next.big ? " big" : ""}${next.fancy ? " fancy" : ""}`;
    el.hidden = true; // shows once the order has dropped
    setTimeout(() => (el.hidden = this.state !== "hour"), 400);
    this.shell.els.layer.appendChild(el);
    const c = { ...next, el, word: null, typed: 0, slot, patience, max: patience, x: FARM_W + 20, state: "walk", hop: 0 };
    this.customers.push(c);
    if (friend) this.greet(friend, c);
    this.ensureWords();
    this.belowKey = "";
    return true;
  }

  // A pet sees a friend of its own kind in line.
  greet(pet, c) {
    pet.joy = 1.5;
    setTimeout(() => {
      this.say(c, `${pet.name}'s friend!`);
      this.scene.burst(pet.x, PET_GROUND - 18, 8, ["#e87aa8", "#f6a6c8"], { speed: 15, up: 20, gravity: 10, life: 1 });
    }, 900);
  }

  // How a customer's order would go right now: the whole order, a swap
  // (what's missing traded for what's on the shelf), or nothing.
  plan(c) {
    if (this.hasOrder(c.order)) return { kind: "full", give: c.order };
    const spare = { ...this.shelf };
    const give = {};
    let missing = 0;
    for (const [k, n] of Object.entries(c.order)) {
      const have = Math.min(n, spare[k] || 0);
      if (have) give[k] = have;
      spare[k] = (spare[k] || 0) - have;
      missing += n - have;
    }
    // swap in their favorite first, then whatever there's most of
    const kinds = Object.keys(spare)
      .filter((k) => spare[k] > 0)
      .sort((a, b) => (b === c.pet.favorite) - (a === c.pet.favorite) || spare[b] - spare[a]);
    for (const k of kinds) {
      while (missing > 0 && spare[k] > 0) {
        give[k] = (give[k] || 0) + 1;
        spare[k] -= 1;
        missing -= 1;
      }
    }
    return missing > 0 ? { kind: "none", give: null } : { kind: "swap", give };
  }

  serve(c) {
    const plan = this.plan(c);
    if (plan.kind === "none") {
      const need = Object.entries(c.order)
        .filter(([k, n]) => (this.shelf[k] || 0) < n)
        .map(([k]) => this.crop(k).name);
      this.say(c, `Need ${need.join(" + ")}!`);
      c.shown = null;
      return;
    }
    // what they pay: swapped-in veggies at a share (full price if it's their favorite)
    let value = 0;
    for (const [k, n] of Object.entries(plan.give)) {
      const asked = Math.min(n, c.order[k] || 0);
      const share = k === c.pet.favorite ? 1 : this.rules.swap_share;
      value += (asked + (n - asked) * share) * this.crop(k).price;
    }
    this.takeFromShelf(plan.give);
    if (c.fancy) value *= this.farm.fancy_pay;
    const tip = plan.kind === "full" ? Math.round(value * this.farm.max_tip * Math.max(0, c.patience / c.max)) : 0;
    value = Math.round(value);
    this.money += value + tip;
    this.day.earned += value + tip;
    this.day.served += 1;
    this.stats.served += 1;
    this.stats.big += c.big ? 1 : 0;
    this.stats.fancy += c.fancy ? 1 : 0;
    this.stats.tips += tip;
    this.cheer = 0.3;
    this.say(c, plan.kind === "swap" ? `Swap is OK! +$${value}` : tip ? `Thanks! +$${tip} tip` : "Thanks!");
    this.scene.burst(c.x, CUSTOMER_GROUND - 24, 10, ["#e87aa8", C.gold, C.cream], { speed: 25, up: 20, gravity: 20 });
    this.leave(c, true);
  }

  // happy: true (served), false (gave up), null (closing time)
  leave(c, happy) {
    c.state = happy === false ? "sad" : "happy";
    c.el.remove();
    this.closeGaps();
    if (happy === false) {
      this.day.missed += 1;
      this.say(c, "Hmph.");
    }
    this.belowKey = "";
  }

  say(c, text) {
    const el = document.createElement("div");
    el.className = "crow-bubble";
    el.textContent = text;
    this.shell.els.layer.appendChild(el);
    this.bubbles.push({ el, c, life: 1.6 });
  }

  // --- delivery orders ----------------------------------------------------------------

  openDeliveries() {
    return this.deliveries.filter((d) => !d.done && !d.missed && !this.petOut());
  }

  // Where a pet waits: the gardener by its plot, a courier by the stand.
  petHome(p) {
    return p === this.gardener ? this.petRange()[0] + 4 : PET_HOME_X;
  }

  // Where the gardener hops about: along its plots (or the field's edge).
  petRange() {
    const plots = this.petPlots.length ? this.petPlots : this.plots.slice(-1);
    const xs = plots.map((p) => p.x);
    return [Math.max(8, Math.min(...xs) - 2), Math.min(98, Math.max(...xs) + this.cell.w + 2)];
  }

  petOut() {
    return Boolean(this.courier && this.courier.trip);
  }

  deliver(d) {
    if (!this.hasOrder(d.order)) {
      const need = Object.entries(d.order)
        .filter(([k, n]) => (this.shelf[k] || 0) < n)
        .map(([k, n]) => `${n - (this.shelf[k] || 0)} ${this.crop(k).name}`);
      this.flash = { text: `That delivery needs ${need.join(" + ")} more`, life: 2 };
      return;
    }
    this.takeFromShelf(d.order);
    d.done = true;
    d.word = null;
    const tip = this.courier ? Math.round(d.pay * this.rules.pet_tip) : 0;
    this.money += d.pay + tip;
    this.day.earned += d.pay + tip;
    this.day.served += 1;
    this.stats.deliveries += 1;
    this.stats.tips += tip;
    this.cheer = 0.4;
    if (this.courier) {
      this.courier.trip = { phase: "out", away: 0, order: d.order };
      this.flash = { text: `${this.courier.name} is off with the delivery! +$${d.pay}${tip ? ` and a $${tip} tip` : ""}`, life: 3 };
    } else {
      this.flash = { text: `Delivered! +$${d.pay}`, life: 2 };
    }
    const x = this.courier ? this.courier.x : PET_HOME_X;
    this.scene.burst(x, PET_GROUND - 12, 14, [C.gold, C.cream, "#e87aa8"], { speed: 30, up: 20, gravity: 20 });
  }

  // The courier walks off left, is gone a moment, comes back. The gardener
  // hops about its plot, and over to it when it plants.
  movePets(dt) {
    for (const p of this.pets) {
      p.hop += dt * 8;
      p.joy = Math.max(0, p.joy - dt);
    }
    const c = this.courier;
    if (c && c.trip) {
      const t = c.trip;
      if (t.phase === "out") {
        c.dir = -1;
        c.x -= PET_SPEED * dt;
        if (c.x < -20) t.phase = "away";
      } else if (t.phase === "away") {
        t.away += dt;
        if (t.away >= PET_AWAY) t.phase = "back";
      } else {
        c.dir = 1;
        const home = this.petHome(c);
        c.x = Math.min(home, c.x + PET_SPEED * dt);
        if (c.x === home) {
          c.trip = null;
          c.joy = 0.6;
          this.ensureWords();
        }
      }
    }
    const g = this.gardener;
    if (!g || g.trip) return;
    if (g.tx == null) {
      g.rest -= dt;
      if (g.rest <= 0) {
        const [lo, hi] = this.petRange();
        g.tx = lo + Math.random() * (hi - lo);
      }
      return;
    }
    const dx = g.tx - g.x;
    g.dir = Math.sign(dx) || g.dir;
    g.x += Math.sign(dx) * Math.min(Math.abs(dx), 22 * dt);
    if (Math.abs(g.tx - g.x) < 0.5) {
      g.tx = null;
      g.rest = 0.6 + Math.random() * 1.4;
      // plant the plot it came to, then hop on to the next one waiting
      const here = this.petPlots.find((p) => p.planting && Math.abs(p.x + this.cell.w / 2 - g.x) < 1);
      if (here) {
        here.planting = false;
        this.scene.burst(here.x + this.cell.w / 2, here.y + this.cell.h - 4, 8, [C.soil, C.grass, C.cream], { speed: 20, up: 15 });
        g.joy = 0.5;
      }
      const next = this.petPlots.find((p) => p.planting);
      if (next) g.tx = next.x + this.cell.w / 2;
    }
  }

  // The delivery orders, in the sky at the top left.
  renderDeliveries() {
    const show = ["ready", "hour"].includes(this.state);
    this.deliveryBox.hidden = !show;
    if (!show) return;
    const key = [this.petOut(), JSON.stringify(this.shelf), ...this.deliveries.map((d) => `${d.word}:${d.typed}:${d.done}${d.missed}:${this.typer.matches(d)}`)].join("|");
    if (key === this.deliveryKey) return;
    this.deliveryKey = key;
    const word = (t) => (t.word ? wordHtml(t.word, t.typed) : "…");
    this.deliveryBox.innerHTML =
      `<p class="farm-deliveries-title">Delivery orders</p>` +
      this.deliveries
        .map((d) => {
          const over = d.done || d.missed;
          const status = d.done ? "Delivered!" : d.missed ? "Missed" : `by hour ${d.due}`;
          const away = !over && this.petOut() ? `<p class="delivery-away">${escapeHtml(this.courier.name)} is out…</p>` : "";
          return `<div class="farm-delivery${over ? " over" : ""}${this.typer.matches(d) ? " locked" : ""}">
            <p>${escapeHtml(SPECIES_NAMES[d.pet.species] || d.pet.species)} · $${d.pay} · ${status}</p>
            <div class="delivery-line"><span class="ticket-order">${this.orderIcons(d.order, true, SMALL_ICON)}</span>
              ${over ? "" : away || `<span class="crow-word-text">${word(d)}</span>`}</div>
          </div>`;
        })
        .join("");
    this.deliveryBox.querySelectorAll(".veggie-icon").forEach((c) => drawVeggieIcon(c, c.dataset.kind));
  }

  // --- below the field: seeds and delivery orders, lined up -----------------------------

  renderBelow(force = false) {
    const key = [
      this.state, this.money, this.emptyPlots().length, this.typer.prefix,
      ...this.packets.map((t) => `${t.word}:${t.typed}`), this.flash && this.flash.text,
    ].join("|");
    if (!force && key === this.belowKey) return;
    this.belowKey = key;
    const open = this.emptyPlots().length;
    const word = (t) => (t.word ? wordHtml(t.word, t.typed) : "…");
    const packets = this.packets
      .map((p) => {
        const c = p.crop;
        return `<div class="farm-card seed-packet${this.canPlant(p) ? "" : " cant"}${this.typer.matches(p) ? " locked" : ""}">
          <h3><canvas class="veggie-icon" data-kind="${c.id}"></canvas> ${escapeHtml(c.name)}</h3>
          <p>$${c.seed_cost} seed · ${c.grow}s · ${c.yields}×$${c.price}</p>
          <p class="choice-word">${word(p)}</p>
        </div>`;
      })
      .join("");
    const tip =
      this.state === "ready"
        ? `Plant a seed to open the stand! · ${open} empty plot${open === 1 ? "" : "s"}`
        : this.flash
          ? escapeHtml(this.flash.text)
          : `Serve customers, send deliveries, replant · ${open} empty plot${open === 1 ? "" : "s"}`;
    this.shell.els.below.innerHTML = `
      <p class="farm-below-title">${tip}</p>
      <div class="farm-row">${packets}${this.comingSeeds()}</div>`;
    this.shell.els.below.querySelectorAll(".veggie-icon").forEach((c) => drawVeggieIcon(c, c.dataset.kind));
  }

  // The next veggie to open, so you know more are coming.
  comingSeeds() {
    const next = this.farm.next_crop;
    if (!next) return "";
    return `<div class="farm-card seed-packet coming-seed">
      <h3><canvas class="veggie-icon" data-kind="${next.id}" width="${SMALL_ICON.w}" height="${SMALL_ICON.h}"></canvas> ${escapeHtml(next.name)}</h3>
      <p>New seeds coming!</p>
      <p>Opens at ${next.rep} reputation</p>
    </div>`;
  }

  // --- each frame -------------------------------------------------------------

  update(dt) {
    this.cheer = Math.max(0, this.cheer - dt);
    const playing = this.state === "hour";
    for (const c of this.customers) {
      c.hop += dt * 8;
      if (c.state === "walk" || c.state === "wait") {
        if (!playing) continue;
        c.x = Math.max(QUEUE_X[c.slot], c.x - 50 * dt); // walking up, or stepping up the line
        c.moving = c.x > QUEUE_X[c.slot];
        if (!c.moving) c.state = "wait";
        if (c.state === "wait") {
          c.patience -= dt;
          if (c.patience <= 0) this.leave(c, false);
        }
      } else {
        c.x += (c.state === "sad" ? 30 : 50) * dt;
      }
    }
    this.customers = this.customers.filter((c) => c.state === "wait" || c.state === "walk" || c.x < FARM_W + 30);

    for (const b of this.bubbles) b.life -= dt;
    for (const b of this.bubbles) if (b.life <= 0) b.el.remove();
    this.bubbles = this.bubbles.filter((b) => b.life > 0);
    if (this.flash && (this.flash.life -= dt) <= 0) this.flash = null;

    if (playing) {
      this.clock += dt;
      this.grow(dt);
      this.movePets(dt);
      this.arriveIn -= dt;
      const left = this.hourSeconds() - this.clock;
      if (this.arriveIn <= 0 && left > 6 && this.arrive()) this.arriveIn = ARRIVE_GAP;
      this.ensureWords();
      if (left <= 0) this.endHour();
      this.renderHud();
    } else if (this.state === "ready") {
      this.movePets(dt);
    }
    if (playing || this.state === "ready") this.renderBelow();
    this.renderDeliveries();
    this.placeTickets();
  }

  // Puts a layer element centered on field x with its bottom at field y.
  placeAt(el, x, y) {
    const W = this.shell.els.layer.clientWidth;
    const H = this.shell.els.layer.clientHeight;
    placeInside(el, (x / FARM_W) * W, (y / FARM_H) * H, W, H);
  }

  placeTickets() {
    const showLine = ["ready", "hour"].includes(this.state);
    this.line.forEach((c, i) => {
      c.el.hidden = !showLine;
      this.placeAt(c.el, STACK_X, STACK_BOTTOM - i * STACK_STEP);
    });
    for (const c of this.waiting()) {
      const plan = this.plan(c).kind;
      const key = `${c.word}:${c.typed}:${this.typer.matches(c)}:${plan}:${JSON.stringify(this.shelf)}`;
      if (c.shown !== key) {
        c.el.innerHTML = `<span class="ticket-order">${this.orderIcons(c.order)}${plan === "swap" ? '<span class="swap-tag">swap</span>' : ""}</span>` +
          `<span class="crow-word-text">${c.word ? wordHtml(c.word, c.typed) : "…"}</span><span class="call-timer"><span></span></span>`;
        c.el.querySelectorAll(".veggie-icon").forEach((v) => drawVeggieIcon(v, v.dataset.kind));
        c.el.classList.toggle("locked", this.typer.matches(c));
        c.el.classList.toggle("can-serve", plan === "full");
        c.shown = key;
      }
      c.el.querySelector(".call-timer span").style.width = `${Math.max(0, c.patience / c.max) * 100}%`;
      const lift = c.slot === 1 ? 14 : 0; // the middle ticket sits higher, so neighbors don't overlap
      this.placeAt(c.el, c.x, CUSTOMER_GROUND - CUSTOMER_BOX.h - 2 - lift);
    }
    // bubbles go above the animal's ticket
    for (const b of this.bubbles) this.placeAt(b.el, b.c.x, CUSTOMER_GROUND - CUSTOMER_BOX.h - 26 - (b.c.slot === 1 ? 14 : 0));
  }

  // The day's stars so far (the same rule as the server's).
  starsNow() {
    const { served, missed } = this.day;
    if (!served) return 0;
    const share = served / (served + missed);
    if (share >= GREAT_SHARE && served >= GREAT_MIN_SERVED) return 3;
    return share >= GOOD_SHARE ? 2 : 1;
  }

  renderHud() {
    const secs = Math.max(0, Math.ceil(this.state === "hour" ? this.hourSeconds() - this.clock : 0));
    const when =
      this.state === "hour" ? `Hour ${this.hour} · ${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`
        : this.state === "ready" ? "Plant to open!"
          : `Hour ${this.hour}`;
    this.shell.els.hud.innerHTML =
      `<span>$${Math.round(this.money)}</span><span>Shelf ${this.shelfCount()}/${this.farm.shelf}</span>` +
      `<span class="stars" title="3 stars: a free veggie for your pets">${"★".repeat(this.starsNow())}${"☆".repeat(3 - this.starsNow())}</span>` +
      `<span>Score <b class="game-score">${this.shell.total.toLocaleString()}</b></span><span>${when}</span>`;
  }

  // --- drawing ----------------------------------------------------------------

  owns(id) {
    return Boolean(this.farm.upgrades[id]);
  }

  draw(s) {
    const evening = this.state === "evening" || (this.state === "shop" && this.hour >= this.game.hours);
    const sky = FARM_SKIES[evening ? 4 : Math.min(this.hour, 3)];
    s.bands(smoothSky(sky, 12), 0, 64);
    s.disc(120 + this.hour * 15, 14 + Math.abs(this.hour - 2) * 4, 7, C.gold);
    s.oval(50, 64, 70, 9, "#8fb36b");
    s.oval(200, 65, 70, 8, "#7ea35c");
    this.drawBackDecor(s);
    s.rect(0, 62, FARM_W, 58, C.grass);
    s.rect(0, 62, FARM_W, 1, C.grassDark);
    // the path customers walk on
    s.rect(150, 104, 90, 16, "#c9a66b");
    s.rect(150, 104, 90, 1, "#a8854a");
    for (const p of this.allPlots()) this.drawPlot(s, p);
    this.drawStand(s);
    for (const c of this.customers) {
      const inLine = c.state === "walk" || c.state === "wait";
      this.drawAnimal(s, c.pet, c.x, CUSTOMER_GROUND, inLine, CUSTOMER_BOX, !inLine || c.moving ? c.hop : 0);
    }
    this.drawPets(s);
    this.drawFrontDecor(s);
  }

  // One plot in its grid cell: soil, then a sprout, then its veggies when
  // ripe. Pet plots have a little fence and a heart, robot plots a robot;
  // with the sprout alarm, an empty plot of yours blinks.
  drawPlot(s, p) {
    const { x, y } = p;
    const { w, h } = this.cell;
    const top = y + Math.round(h * 0.3);
    if (this.farm.alarm && p.kind === "mine" && !p.crop && this.state === "hour" && Math.floor(s.t * 3) % 2) {
      s.rect(x, top - 1, w, h - (top - y), C.gold);
    }
    s.rect(x + 1, top, w - 2, h - (top - y) - 1, C.soil);
    s.rect(x + 1, y + h - 2, w - 2, 1, C.soilDark);
    if (p.kind === "pet") {
      s.rect(x, top - 1, w, 1, C.cream);
      for (let fx = x; fx < x + w; fx += 4) s.rect(fx, top - 3, 1, 4, C.cream);
      s.rect(x + w - 4, top - 5, 1, 1, "#e87aa8");
      s.rect(x + w - 2, top - 5, 1, 1, "#e87aa8");
      s.rect(x + w - 4, top - 4, 3, 1, "#e87aa8");
      s.rect(x + w - 3, top - 3, 1, 1, "#e87aa8");
    } else if (p.kind === "robot") {
      // a little robot head: antenna, grey face, a blinking eye
      s.rect(x + 1, top - 1, w - 2, 1, "#9aa4ad");
      s.rect(x + w - 5, top - 6, 4, 4, "#9aa4ad");
      s.rect(x + w - 3, top - 8, 1, 2, "#5c6670");
      s.rect(x + w - 4, top - 5, 1, 1, Math.floor(s.t * 2) % 2 ? "#d8283a" : "#5c6670");
    }
    if (!p.crop) return;
    const crop = this.crop(p.crop);
    const cx = x + Math.floor(w / 2);
    if (p.left > 0) {
      s.rect(cx - 3, top + 1, 7, 2, C.grassDark);
      drawVeggie((xx, yy, ww, hh, c) => s.rect(cx - 2 + xx, top + 2 + yy, ww, hh, c), 0, 0, crop.id, 1);
      if (p.left > 1) s.rect(x + w - 3, top + 1, 1, 1, C.cream);
      return;
    }
    // growing: a sprout that gets taller as it grows
    const room = Math.max(3, h - (top - y) - 3);
    const tall = 2 + Math.round(Math.min(1, p.grown / crop.grow) * (room - 2));
    s.rect(cx, y + h - 2 - tall, 1, tall, C.grassDark);
    s.rect(cx - 2, y + h - 2 - tall, 2, 1, C.grass);
    s.rect(cx + 1, y + h - 1 - tall, 2, 1, C.grass);
  }

  // Your pets: the courier by the stand (off on deliveries with a basket),
  // the gardener hopping about its plot. Happy or busy ones hop.
  drawPets(s) {
    for (const p of this.pets) {
      if (p.trip && p.trip.phase === "away") continue;
      const moving = p.tx != null || (p.trip && p.trip.phase !== "away");
      const hop = p.joy > 0 || moving ? p.hop : 0;
      this.drawAnimal(s, p, p.x, PET_GROUND, p.dir < 0, PET_BOX, hop);
      if (p.trip && p.trip.phase === "out") {
        // the basket
        const x = p.x;
        s.rect(x - 4, PET_GROUND - PET_BOX.h - 4, 9, 4, C.wood);
        s.rect(x - 3, PET_GROUND - PET_BOX.h - 7, 1, 3, C.woodDark);
        s.rect(x + 3, PET_GROUND - PET_BOX.h - 7, 1, 3, C.woodDark);
        s.rect(x - 3, PET_GROUND - PET_BOX.h - 7, 7, 1, C.woodDark);
      }
      if (p.joy > 0 && Math.floor(p.hop) % 2) s.rect(p.x, PET_GROUND - PET_BOX.h - 6, 2, 2, "#e87aa8");
    }
  }

  drawStand(s) {
    const x = 98;
    // roof posts and roof
    s.rect(x + 1, 52, 2, 52, C.woodDark);
    s.rect(x + 45, 52, 2, 52, C.woodDark);
    const stripe = this.owns("awning");
    for (let i = 0; i < 8; i++) s.rect(x - 2 + i * 6.5, 46, 7, 7, i % 2 ? C.cream : stripe ? "#3f7a94" : C.red);
    for (let i = 0; i < 8; i++) s.disc(x + 1 + i * 6.5, 53, 3, i % 2 ? C.cream : stripe ? "#3f7a94" : C.red);
    // the keeper
    if (this.avatar) {
      const bob = this.cheer > 0 ? 3 : 0;
      paintAvatar((ax, ay, w, h, c) => s.rect(x + ax, 46 + ay - bob, w, h, c), this.avatar, {
        background: false,
        pets: false,
        frame: Math.floor(s.t * 2) % 2,
      });
    }
    // counter
    s.rect(x - 2, 84, 52, 4, C.wood);
    s.rect(x, 88, 48, 18, C.woodDark);
    for (let yy = 91; yy < 106; yy += 5) s.rect(x, yy, 48, 1, C.wood);
    // the shelf: a pile of each veggie along the counter
    let sx = x;
    for (const [kind, n] of Object.entries(this.shelf)) {
      if (sx > x + 40) break;
      for (let k = 0; k < Math.min(n, 3); k++) {
        drawVeggie((xx, yy, w, h, c) => s.rect(sx + k * 3 + xx, 77 - (k % 2) * 2 + yy, w, h, c), 0, 0, kind, 1);
      }
      sx += 6 + Math.min(n, 3) * 3;
    }
    // a little price board
    s.rect(x + 14, 92, 20, 10, C.cream);
    s.rect(x + 16, 95, 16, 1, C.soilDark);
    s.rect(x + 16, 98, 10, 1, C.soilDark);
    if (this.owns("flowers")) {
      for (let i = 0; i < 6; i++) s.disc(x + 3 + i * 8, 106, 2, ["#e87aa8", C.gold, "#9a6ad6"][i % 3]);
      s.rect(x, 107, 48, 3, C.wood);
    }
    if (this.owns("lanterns")) {
      for (const lx of [x + 6, x + 42]) {
        s.rect(lx, 55, 1, 3, C.ink);
        s.rect(lx - 1, 58, 3, 4, C.gold);
      }
    }
    if (this.owns("bunting")) {
      for (let i = 0; i < 7; i++) {
        const fx = x + 3 + i * 6.5;
        s.rect(fx, 57, 3, 2, ["#d8283a", C.gold, "#3f7a94", "#6b8e3a"][i % 4]);
        s.rect(fx + 1, 59, 1, 1, ["#d8283a", C.gold, "#3f7a94", "#6b8e3a"][i % 4]);
      }
    }
    if (this.owns("ribbon")) {
      s.disc(x + 24, 40, 3, "#3f6ab8");
      s.rect(x + 22, 43, 2, 4, "#3f6ab8");
      s.rect(x + 25, 43, 2, 4, "#3f6ab8");
      s.rect(x + 24, 40, 1, 1, C.gold);
    }
  }

  drawBackDecor(s) {
    if (this.owns("barn")) {
      s.rect(118, 34, 30, 28, C.red);
      for (let i = 0; i < 9; i++) s.rect(118 + i * 1.7, 34 - i, 30 - i * 3.4, 1, "#8a2f22");
      s.rect(129, 46, 8, 16, C.cream);
      s.rect(130, 47, 6, 15, "#8a2f22");
    }
    if (this.owns("windmill")) {
      s.rect(158, 30, 4, 32, C.cream);
      const a = s.t * 1.5;
      for (let k = 0; k < 4; k++) {
        const ang = a + (k * Math.PI) / 2;
        s.line(160, 30, 160 + Math.cos(ang) * 11, 30 + Math.sin(ang) * 11, C.woodDark);
      }
    }
    if (this.owns("apple_tree")) {
      s.rect(91, 40, 3, 22, C.woodDark);
      s.disc(92, 36, 9, "#4a7f2a");
      for (const [ax, ay] of [[88, 33], [95, 38], [91, 40], [97, 32]]) s.rect(ax, ay, 2, 2, "#d8283a");
    }
  }

  drawFrontDecor(s) {
    if (this.owns("scarecrow")) {
      const x = 92;
      s.rect(x, 80, 2, 30, C.woodDark);
      s.rect(x - 6, 88, 14, 2, C.woodDark);
      s.rect(x - 3, 87, 8, 9, "#b8432f");
      s.disc(x + 1, 83, 3, "#e8c57a");
      s.rect(x - 3, 79, 9, 2, C.wood);
    }
    if (this.owns("bench")) {
      s.rect(152, 98, 14, 2, C.wood);
      s.rect(153, 100, 1, 4, C.woodDark);
      s.rect(164, 100, 1, 4, C.woodDark);
    }
    if (this.owns("beehive")) {
      s.oval(10, 66, 4, 3, C.gold);
      s.rect(7, 66, 7, 1, "#b5862a");
      if (Math.floor(s.t * 4) % 2) s.rect(16, 62, 1, 1, C.ink);
    }
    if (this.owns("pond")) {
      s.oval(60, 114, 14, 4, C.water);
      s.oval(60, 113, 10, 2, C.waterLight);
      s.rect(56 + Math.round(Math.sin(s.t) * 4), 111, 3, 2, C.cream);
    }
  }


  // An animal drawn once small enough to fit `box`, its feet at (x, ground).
  drawAnimal(s, pet, x, ground, faceLeft, box, hop = 0) {
    const key = `${faceLeft ? "left" : "right"}:${box.w}`;
    pet.art ||= {};
    if (!pet.art[key]) {
      const { w, h } = petSize(pet.genes, pet.growth);
      const art = document.createElement("canvas");
      art.width = w;
      art.height = h + 2;
      const ctx = art.getContext("2d");
      drawPet((px, py, ww, hh, col) => {
        ctx.fillStyle = col;
        ctx.fillRect(px, py, ww, hh);
      }, 0, h, pet.genes, pet.growth, { faceLeft });
      pet.art[key] = { canvas: art, scale: Math.min(1, box.w / w, box.h / h) };
    }
    const { canvas, scale } = pet.art[key];
    const w = Math.round(canvas.width * scale);
    const h = Math.round(canvas.height * scale);
    const up = hop ? Math.abs(Math.round(Math.sin(hop) * 2)) : 0;
    s.ctx.imageSmoothingEnabled = false;
    s.ctx.drawImage(canvas, Math.round(x - w / 2), Math.round(ground - h - up), w, h);
  }

  // --- keys -------------------------------------------------------------------

  targets() {
    if (this.state === "ready") return this.packets.filter((p) => p.word && this.canPlant(p));
    if (this.state === "hour") return this.worded().filter((t) => t.word && (!this.packets.includes(t) || this.canPlant(t)));
    return [];
  }

  handleKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (this.state === "shop") return this.shopKey(e);
    if (!["ready", "hour"].includes(this.state)) {
      this.shell.screenKey(e);
      if (e.key === " ") e.preventDefault();
      return;
    }
    if (e.key === "Escape" || e.key === "Backspace") {
      e.preventDefault();
      this.typer.release(this.worded());
      this.refresh();
      return;
    }
    if (e.key.length !== 1) return;
    e.preventDefault();
    if (e.repeat || e.key === " ") return;
    const r = this.typer.press(e.key, this.targets());
    if (r.kind === "done") {
      const t = r.target;
      if (this.packets.includes(t)) this.plant(t);
      else if (this.deliveries.includes(t)) this.deliver(t);
      else this.serve(t);
    } else if (r.kind === "slip") {
      for (const c of r.targets.filter((t) => t.el)) {
        c.patience = Math.max(0.5, c.patience - 1);
        c.el.classList.remove("slip");
        void c.el.offsetWidth;
        c.el.classList.add("slip");
      }
    }
    this.refresh();
  }

  shopKey(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      this.shell.hideScreen();
      this.afterShop();
      return;
    }
    if (e.key === "Escape" || e.key === "Backspace") {
      e.preventDefault();
      this.shopTyper.release();
      return this.renderShop();
    }
    if (e.key.length !== 1) return;
    e.preventDefault();
    if (e.repeat) return;
    const r = this.shopTyper.press(e.key, this.shopCards.filter((c) => c.u.can_buy));
    if (r.kind === "done") this.buy(r.target);
    else this.renderShop();
  }

  refresh() {
    for (const c of this.customers) c.shown = null;
    this.renderBelow(true);
    this.renderHud();
  }
}

GAMES.farm_stand = (shell, content, me) => new FarmStand(shell, content, me);
