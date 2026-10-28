// One habitat, full size (PLAN.md 11i): its look from habitats.js and the
// pets living there, moving by their personality (pet_motion.js).

const $ = (id) => document.getElementById(id);
const SCENE_PX = 6; // the 160x90 grid on a 960x540 canvas
const PET_SCALE = 2 / 3; // 4 screen pixels per pet pixel
const TICK_MS = 120;

let habitat = null; // /api/trail/{spot}
let world = null;
let background = null;

function painter(ctx) {
  return habitatPainter(ctx, SCENE_PX);
}

function step() {
  PetMotion.step(world);
  const ctx = $("habitat-canvas").getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(background, 0, 0);
  PetMotion.draw(world, painter(ctx), { ctx, unit: SCENE_PX, tags: true });
}

function renderResidents() {
  const pets = habitat.pets;
  $("habitat-count").textContent = `Living here: ${pets.length} of ${habitat.capacity}`;
  const list = $("habitat-pets");
  if (!pets.length) {
    list.innerHTML = `<p>No one lives here yet. Move pets in at the <a href="/pets/care">Pet Care Center</a>!</p>`;
    return;
  }
  list.replaceChildren(
    ...pets.map((p) => {
      const a = document.createElement("a");
      a.className = "habitat-pet";
      a.href = `/pets/care?pet=${p.id}`;
      a.textContent = p.name;
      return a;
    })
  );
}

async function load() {
  const spot = Number(location.pathname.split("/").pop());
  $("habitat-back").href = `/pets/trail?at=${spot}`;
  const r = await fetch(`/api/trail/${spot}`);
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || `/api/trail/${spot} returned ${r.status}`);
  Header.update(data);
  habitat = data.habitat;
  document.title = `Typing Trainer — ${habitat.name}`;
  $("habitat-name").textContent = habitat.name;
  const look = HABITAT_LOOKS[habitat.kind];
  background = habitatBackground(habitat.kind, SCENE_PX);
  const area = { left: 2, right: HABITAT_W - 2, top: look.groundTop, bottom: look.groundBottom, props: look.props };
  world = PetMotion.create(habitat.pets, area, PET_SCALE);
  renderResidents();
  step();
}

load()
  .then(() => setInterval(step, TICK_MS))
  .catch((err) => {
    console.error(err);
    $("habitat-message").textContent = `${err.message} Head back to the Trailhead.`;
  });
