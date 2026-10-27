// The garden (app/garden.py): plant seeds in 10 spots, pick the veggies
// that practice ripens, and collect the basket that withered plants leave.
// Keyboard first: arrows move between spots, Enter plants or picks, B
// collects the basket, Esc goes home. Clicking works too.

const $ = (id) => document.getElementById(id);
const COLUMNS = 5;
const TICK_MS = 600;

let garden = null; // /api/garden's "garden"
let cursor = 0;
let frame = 0;

function plural(kind, n) {
  const name = garden.names[kind];
  return n === 1 ? name.name : name.plural;
}

function spotLabel(spot) {
  if (!spot) return garden.seeds ? "Plant a seed" : "Empty";
  if (spot.ready) return `${spot.ready} ripe! Pick`;
  if (spot.babies) return `${spot.name}: ${spot.babies} growing`;
  return spot.name;
}

function hint() {
  const day = window.lastDay;
  if (garden.ready) return `You have ${garden.ready} veggie${garden.ready > 1 ? "s" : ""} to pick!`;
  if (garden.seeds && garden.growing < garden.spots.length) return "Pick an empty spot and press Enter to plant a seed.";
  if (day && !day.seed_reached) {
    return `Practice ${Math.ceil(day.seed_seconds / 60)} minutes to water your garden and earn a seed.`;
  }
  if (garden.growing) return "Your garden is watered. Come back after your next practice!";
  return "Practice to earn a seed, then plant it here.";
}

function veggieList(counts, emptyText) {
  const kinds = Object.keys(counts);
  if (!kinds.length) return `<p class="veggie-empty">${emptyText}</p>`;
  return kinds
    .map(
      (k) => `<span class="veggie-chip" title="${plural(k, counts[k])}">
        <canvas class="veggie-icon" data-kind="${k}" width="32" height="40"></canvas>
        <span>${counts[k]}</span></span>`
    )
    .join("");
}

function render() {
  $("garden-seeds").textContent = garden.seeds;
  $("garden-hint").textContent = hint();
  $("garden-bed").innerHTML = garden.spots
    .map(
      (spot, i) => `
      <button class="garden-spot${spot && spot.ready ? " ripe" : ""}${i === cursor ? " selected" : ""}" data-slot="${i}"
        aria-label="Spot ${i + 1}: ${spotLabel(spot)}">
        <canvas class="spot-art" width="120" height="120"></canvas>
        <span class="spot-label">${spotLabel(spot)}</span>
      </button>`
    )
    .join("");
  $("basket-list").innerHTML = veggieList(garden.basket, "Empty. Veggies from wilted plants land here.");
  $("basket-button").hidden = !garden.basket_total;
  $("garden-basket").classList.toggle("full", !!garden.basket_total);
  $("pantry-list").innerHTML = veggieList(garden.veggies, "None yet. Pick some!");
  document.querySelectorAll(".veggie-icon").forEach((c) => drawVeggieIcon(c, c.dataset.kind));
  draw();
}

function draw() {
  document.querySelectorAll(".spot-art").forEach((canvas, i) => {
    drawPlant(veggieCanvas(canvas, PLANT_W, PLANT_H), 0, 0, garden.spots[i], frame + i);
  });
}

function say(text) {
  $("garden-message").textContent = text;
}

async function act(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  if (!res.ok) {
    say(data.detail);
    return null;
  }
  garden = data.garden;
  Header.update(data);
  if (path.endsWith("plant") || path.endsWith("pick")) Header.setSeeds(data.seeds);
  render();
  return data.done;
}

async function useSpot(i) {
  cursor = i;
  const spot = garden.spots[i];
  if (!spot) {
    const done = await act("/api/garden/plant", { slot: i });
    if (done) say(`You planted a seed! What will it grow? Practice to find out.`);
  } else if (spot.ready) {
    const done = await act("/api/garden/pick", { slot: i });
    if (done) say(`You picked ${done.count} ${plural(done.kind, done.count).toLowerCase()}!`);
  } else {
    say(`Those ${spot.name.toLowerCase()} babies need water. Practice to water them!`);
    render();
  }
}

async function collectBasket() {
  const done = await act("/api/garden/basket");
  if (done) {
    const n = Object.values(done).reduce((a, b) => a + b, 0);
    say(`You collected ${n} veggie${n > 1 ? "s" : ""} from the basket!`);
  }
}

$("garden-bed").addEventListener("click", (e) => {
  const spot = e.target.closest("[data-slot]");
  if (spot) useSpot(Number(spot.dataset.slot));
});
$("basket-button").addEventListener("click", collectBasket);

window.addEventListener("keydown", (e) => {
  if (!garden) return;
  const moves = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -COLUMNS, ArrowDown: COLUMNS };
  if (e.key in moves) {
    e.preventDefault();
    const next = cursor + moves[e.key];
    if (next >= 0 && next < garden.spots.length) {
      cursor = next;
      render();
    }
  } else if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    useSpot(cursor);
  } else if (e.key === "b" || e.key === "B") {
    if (garden.basket_total) collectBasket();
  } else if (e.key === "Escape") {
    location.href = "/";
  }
});

document.addEventListener("daychange", (e) => {
  window.lastDay = e.detail;
});

Header.ready.then(async (me) => {
  if (!me) return;
  window.lastDay = me.day;
  const res = await fetch("/api/garden");
  garden = (await res.json()).garden;
  // start on the first spot with something to do
  const todo = garden.spots.findIndex((s) => (s && s.ready) || (!s && garden.seeds));
  cursor = Math.max(0, todo);
  render();
  setInterval(() => {
    frame += 1;
    draw();
  }, TICK_MS);
});
