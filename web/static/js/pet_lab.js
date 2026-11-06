// The pet lab (dev only): roll a litter of pets for a species and two
// colors, grow them with a slider, and open one in a close-up that shows
// it in every trial design (pet_render.js PET_VARIANTS) at all five growth
// stages, with knobs to nudge its looks by hand. Rolls come
// from /api/pet-lab/roll (the real roller, nothing saved); the knobs only
// change the copy drawn here.

const $ = (id) => document.getElementById(id);
const LITTER = 24;
const TICK_MS = 400;
const STAGE_GROWTH = [0, 2, 5, 8, 10];
// The species picked first when the lab opens (every species is listed).
const LAB_FIRST = "flower_fairy";

let species = {}; // /api/pet-lab/species
let litter = [];
let selected = null; // a copy of one litter pet, knobs applied
let frame = 0;
let designName = ""; // the name a design is given (it goes along in its JSON)

function canvasPx(canvas) {
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  return (x, y, w, h, c) => {
    ctx.fillStyle = c;
    ctx.fillRect(Math.round(x), Math.round(y), Math.ceil(w), Math.ceil(h));
  };
}

function variants() {
  return PET_VARIANTS[$("opt-species").value] || [];
}

// While shapes are being worked on, every pet can wear one plain color.
function plain(pet) {
  if (!$("opt-plain").checked) return pet;
  return { ...pet, coat: { ...pet.coat, shares: [1, 0, 0] }, hex: [$("opt-plain-color").value, null, null] };
}

// The litter's design: a variant number, or the species' current look.
function withVariant(pet) {
  const v = Number($("opt-variant").value);
  return plain(v ? { ...pet, variant: v } : pet);
}

function growth() {
  return Number($("opt-growth").value);
}

function fillColors() {
  const info = species[$("opt-species").value];
  const options = info.colors
    .map((c) => `<option value="${c.id}" style="background:${c.hex}">${c.name}${c.unlocked ? " ★" : ""}</option>`)
    .join("");
  $("opt-primary").innerHTML = `<option value="">(game picks)</option>` + options;
  $("opt-secondary").innerHTML = `<option value="">(game picks)</option>` + options;
  // the game picks both colors to start, so a litter shows the variety
  $("opt-primary").value = "";
  $("opt-secondary").value = "";
  $("opt-secondary").disabled = true;
  $("opt-variant").innerHTML =
    `<option value="0" selected>Current</option>` +
    variants().map((v, i) => `<option value="${i + 1}">${i + 1}. ${v.name}</option>`).join("");
}

async function roll() {
  const q = new URLSearchParams({
    species: $("opt-species").value,
    primary: $("opt-primary").value,
    secondary: $("opt-secondary").value,
    count: LITTER,
  });
  const res = await fetch(`/api/pet-lab/roll?${q}`);
  const data = await res.json();
  if (!res.ok) return alert(data.detail);
  litter = data.pets;
  showAdoptGrowth();
  renderLitter();
  select(litter[0]);
}

function label(pet) {
  const names = pet.color_names.filter(Boolean);
  const pct = pet.coat.shares.filter(Boolean).map((s) => `${Math.round(s * 100)}%`);
  const breed = pet.shape.breed ? `${pet.shape.breed}${Object.entries(pet.shape.mix || {}).map(([p, d]) => ` + ${d} ${p}`).join("")}<br>` : "";
  return `${breed}${names.map((n, i) => `${n} ${pct[i]}`).join(" / ")}<br>${pet.coat.pattern}${pet.coat.fins ? `, ${pet.coat.fins} fins` : ""}${petShine(pet) ? ` ✨ ${SHINE_NAMES[petShine(pet)]}` : ""}`;
}

function renderLitter() {
  $("litter").innerHTML = litter
    .map(
      (pet, i) => `<button class="litter-pet${selected && selected.seed === pet.seed ? " selected" : ""}" data-i="${i}">
        <canvas width="140" height="110"></canvas><span>${label(pet)}</span></button>`
    )
    .join("");
  drawLitter();
}

// The biggest whole-pixel scale (up to `most`) at which pets of these sizes fit
// in w x h: the big mythical pets step down so nothing gets cut off.
function fitScale(sizes, w, h, most) {
  let scale = most;
  while (scale > 1 && sizes.some((p) => p.w * scale > w || p.h * scale > h)) scale -= 1;
  return scale;
}

function drawLitter() {
  document.querySelectorAll(".litter-pet canvas").forEach((canvas, i) => {
    const pet = withVariant(litter[i]);
    const px = canvasPx(canvas);
    const size = petSize(pet, growth());
    const scale = fitScale([size], canvas.width - 4, canvas.height - 8, 3);
    const { w } = size;
    drawPet(px, Math.round((canvas.width - w * scale) / 2), canvas.height - 6, pet, growth(), { frame: frame + i, scale });
  });
}

function select(pet) {
  selected = JSON.parse(JSON.stringify(pet));
  $("closeup").hidden = false;
  $("close-seed").textContent = pet.seed;
  fillDesigner();
  $("opt-pattern").value = selected.coat.pattern;
  // a fin pattern of its own (fish)
  $("finpat-knob").hidden = !selected.coat.fins;
  if (selected.coat.fins) $("opt-finpat").value = selected.coat.fins;
  $("opt-splotch").value = selected.coat.splotch;
  $("splotch-value").textContent = Number(selected.coat.splotch).toFixed(2);
  $("opt-length").value = selected.shape.length;
  $("opt-height").value = selected.shape.height;
  // ears show as 0 (smallest) .. 2 (biggest); the gene itself is -1..1
  $("opt-ears").value = selected.shape.ears + 1;
  $("ears-value").textContent = (selected.shape.ears + 1).toFixed(1);
  $("opt-tail").value = selected.shape.tail;
  $("opt-shine").value = petShine(selected) || "";
  // species-only looks show their sliders when this pet has them
  for (const key of ["weight", "snout", "legs", "wool", "horns", "neck", "dome", "crest", "thick", "wings", "fins", "tailh", "size"]) {
    $(`${key}-knob`).hidden = !(key in selected.shape);
    $(`opt-${key}`).value = selected.shape[key] || 0;
  }
  document.querySelectorAll(".litter-pet").forEach((b) => b.classList.toggle("selected", litter[b.dataset.i].seed === pet.seed));
  showStats();
  drawStages();
}

function showStats() {
  const { coat, shape, face, personality, battle } = selected;
  $("close-stats").textContent = [
    `colors: ${selected.color_names.filter(Boolean).join(", ")}  shares: ${coat.shares.join(", ")}`,
    `pattern: ${coat.pattern}  splotch: ${coat.splotch}`,
    `shape: ${JSON.stringify(shape)}`,
    `face: ${JSON.stringify(face)}`,
    `personality: ${JSON.stringify(personality)}`,
    `battle: ${JSON.stringify(battle)}`,
    ...(selected.behavior ? [`behavior: ${JSON.stringify(selected.behavior)}`] : []),
  ].join("\n");
  if (document.activeElement !== $("design-json")) $("design-json").value = JSON.stringify(designJson());
}

// --- the designer: every gene by hand, and the design as JSON ------------------------

const info = () => species[selected.species];
const options = (list, value, label = (x) => x) =>
  list.map((x) => `<option value="${x}"${x === value ? " selected" : ""}>${label(x)}</option>`).join("");

// Every color this species can wear (and, as a third color, treasure metals for some).
function colorChoices(i) {
  const list = [...info().colors, ...(i === 2 ? info().metals : [])];
  return (i ? `<option value="">(none)</option>` : "") + list.map((c) => `<option value="${c.id}" style="background:${c.hex}">${c.name}</option>`).join("");
}

function colorById(id) {
  return [...info().colors, ...info().metals].find((c) => c.id === id);
}

function fillDesigner() {
  const sp = info();
  const { coat, shape, face, personality } = selected;
  $("opt-pattern").innerHTML = patternOptions(sp);
  $("opt-pattern").value = coat.pattern;
  $("breed-knob").hidden = !sp.breeds.length;
  $("opt-breed").innerHTML = options(sp.breeds, shape.breed);
  $("mix-knob").hidden = !sp.mix_parts.length;
  const [part, donor] = Object.entries(shape.mix || {})[0] || ["", ""];
  $("opt-mixpart").innerHTML = `<option value="">(not mixed)</option>` + options(sp.mix_parts, part);
  $("opt-mixdonor").innerHTML = options(sp.breeds, donor);
  $("opt-style").innerHTML = options(sp.styles, coat.style);
  for (const i of [0, 1, 2]) {
    $(`opt-c${i}`).innerHTML = colorChoices(i);
    $(`opt-c${i}`).value = coat.colors[i] || "";
  }
  showShares();
  $("opt-eyes").value = face.eyes;
  $("opt-eyes-pick").innerHTML = `<option value="">(the species' eyes)</option>` + sp.eyes.map((h) => `<option value="${h}" style="background:${h}">${h}</option>`).join("");
  $("opt-odd").checked = Boolean(face.odd_eye);
  $("opt-oddeye").value = face.odd_eye || face.eyes;
  $("opt-favorite").innerHTML = options(sp.veggies, personality.favorite);
  $("opt-name").value = designName;
}

// Its own patterns starred first, then ones any animal can wear, then other
// animals' (on this body they draw as patches).
function patternOptions(sp) {
  const own = new Set(sp.patterns);
  const any = sp.any_patterns.filter((p) => !own.has(p));
  const rest = sp.all_patterns.filter((p) => !own.has(p) && !any.includes(p));
  const name = selected.species.replace("_", " ");
  return `<optgroup label="★ ${name} patterns">${sp.patterns.map((p) => `<option value="${p}">★ ${p}</option>`).join("")}</optgroup>
    <optgroup label="Any animal">${options(any)}</optgroup>
    <optgroup label="Other animals' (draw as patches on a ${name})">${options(rest)}</optgroup>`;
}

function showShares() {
  $("opt-s1").value = selected.coat.shares[1];
  $("opt-s2").value = selected.coat.shares[2];
  $("s1-value").textContent = `${Math.round(selected.coat.shares[1] * 100)}%`;
  $("s2-value").textContent = `${Math.round(selected.coat.shares[2] * 100)}%`;
}

function setColor(i, id) {
  const c = id ? colorById(id) : null;
  selected.coat.colors[i] = c ? c.id : null;
  selected.hex[i] = c ? c.hex : null;
  selected.color_names[i] = c ? c.name : null;
  if (!c) setShares(i === 1 ? 0 : selected.coat.shares[1], i === 2 || i === 1 ? 0 : selected.coat.shares[2]);
}

// The second and third colors' shares; the main color has the rest.
function setShares(s1, s2) {
  s1 = selected.coat.colors[1] ? s1 : 0;
  s2 = selected.coat.colors[2] ? Math.min(s2, 1 - s1 - 0.1) : 0;
  const r = (x) => Math.round(x * 1000) / 1000;
  selected.coat.shares = [r(1 - s1 - s2), r(s1), r(s2)];
  showShares();
}

// What the JSON box shows: the genes as the game stores them, and a name.
function designJson() {
  const { hex, color_names, shine, variant, ...genes } = selected;
  return { name: designName || undefined, genes };
}

// A design's genes ready to draw: colors' hex and names from the species' palette.
function drawable(genes) {
  const sp = species[genes.species];
  const find = (id) => [...sp.colors, ...sp.metals].find((c) => c.id === id);
  const colors = genes.coat.colors.map((id) => (id ? find(id) : null));
  if (colors.some((c, i) => genes.coat.colors[i] && !c)) throw new Error("a color that species can't wear");
  return { ...genes, hex: colors.map((c) => (c ? c.hex : null)), color_names: colors.map((c) => (c ? c.name : null)), shine: petShine(genes) };
}

function loadJson() {
  try {
    const data = JSON.parse($("design-json").value);
    const genes = data.genes || data;
    if (!species[genes.species]) throw new Error("no species");
    designName = data.name || "";
    if ($("opt-species").value !== genes.species) {
      $("opt-species").value = genes.species;
      fillColors();
      buildRows();
    }
    select(drawable(genes));
    $("json-message").textContent = "Loaded!";
  } catch (err) {
    $("json-message").textContent = `That isn't a design (${err.message}).`;
  }
}

$("json-copy").onclick = async () => {
  $("design-json").value = JSON.stringify(designJson());
  try {
    await navigator.clipboard.writeText($("design-json").value);
    $("json-message").textContent = "Copied!";
  } catch {
    $("design-json").select();
    $("json-message").textContent = "Selected: press Ctrl+C to copy.";
  }
};
$("json-load").onclick = loadJson;

// One row per design, each with all five stages side by side, walking.
// Species built from parts (fish) show a row per part, every option drawn on
// the selected pet, instead of a row per design across the growth stages.
function parts() {
  return $("opt-species").value === "fish" ? FISH_PARTS : null;
}

function buildRows() {
  if (parts()) {
    $("variant-rows").innerHTML = Object.entries(parts())
      .map(([part, options]) => `<div class="variant-row"><h3>${part}: ${Object.keys(options).join(", ")}</h3>
      <canvas class="stages-art" data-part="${part}" width="960" height="230"></canvas></div>`)
      .join("");
    return;
  }
  const designs = [[0, "Current"], ...variants().map((v, i) => [i + 1, `${i + 1}. ${v.name}`])];
  $("variant-rows").innerHTML = designs
    .map(([v, name]) => `<div class="variant-row"><h3>${name}</h3>
      <canvas class="stages-art" data-variant="${v}" width="960" height="190"></canvas></div>`)
    .join("");
}

// The selected pet on its own, big, under the sliders: as the knobs set it,
// at the growth slider's stage. The scale is fixed per species (fitted to its
// biggest size), so the size knobs visibly grow and shrink it.
function drawSolo() {
  const canvas = $("solo");
  const pet = plain(selected);
  const px = canvasPx(canvas);
  const roomy = { ...pet, shape: { ...pet.shape, size: 1, length: 3, height: 3, fins: 1, tail: 1, tailh: 1 } };
  const scale = fitScale([petSize(roomy, 10)], canvas.width - 20, canvas.height - 20, 10);
  const { w } = petSize(pet, growth());
  drawPet(px, Math.round((canvas.width - w * scale) / 2), canvas.height - 10, pet, growth(), { frame, scale });
}

// One row per part: the selected pet wearing each option of that part.
function drawParts() {
  document.querySelectorAll("#variant-rows canvas").forEach((canvas) => {
    const part = canvas.dataset.part;
    const keys = Object.keys(parts()[part]);
    const pets = keys.map((k) => plain({ ...selected, variant: 0, shape: { ...selected.shape, [part]: k } }));
    const px = canvasPx(canvas);
    const slot = canvas.width / keys.length;
    const scale = fitScale(pets.map((p) => petSize(p, 10)), slot - 4, canvas.height - 10, 4);
    pets.forEach((pet, i) => {
      const { w } = petSize(pet, 10);
      drawPet(px, Math.round(i * slot + (slot - w * scale) / 2), canvas.height - 6, pet, 10, { frame, scale });
    });
  });
}

function drawStages() {
  if (!selected) return;
  drawSolo();
  if (parts()) return drawParts();
  document.querySelectorAll("#variant-rows canvas").forEach((canvas) => {
    const v = Number(canvas.dataset.variant);
    const pet = plain(v ? { ...selected, variant: v } : selected);
    const px = canvasPx(canvas);
    const slot = canvas.width / STAGE_GROWTH.length;
    // one scale for the whole row, so the stages still compare
    const scale = fitScale(STAGE_GROWTH.map((g) => petSize(pet, g)), slot - 4, canvas.height - 18, 4);
    STAGE_GROWTH.forEach((g, i) => {
      const { w } = petSize(pet, g);
      drawPet(px, Math.round(i * slot + (slot - w * scale) / 2), canvas.height - 14, pet, g, { frame, scale });
    });
  });
}

function knob(id, apply) {
  $(id).addEventListener("input", () => {
    if (!selected) return;
    apply($(id));
    showStats();
    drawStages();
  });
}

knob("opt-pattern", (el) => (selected.coat.pattern = el.value));
knob("opt-breed", (el) => (selected.shape.breed = el.value));
const setMix = () => {
  const part = $("opt-mixpart").value;
  selected.shape.mix = part ? { [part]: $("opt-mixdonor").value } : {};
};
knob("opt-mixpart", setMix);
knob("opt-mixdonor", setMix);
knob("opt-style", (el) => (selected.coat.style = el.value));
for (const i of [0, 1, 2]) {
  knob(`opt-c${i}`, (el) => {
    if (i === 0 && !el.value) return;
    setColor(i, el.value);
  });
}
knob("opt-s1", (el) => setShares(Number(el.value), selected.coat.shares[2]));
knob("opt-s2", (el) => setShares(selected.coat.shares[1], Number(el.value)));
knob("opt-eyes", (el) => (selected.face.eyes = el.value));
knob("opt-eyes-pick", (el) => {
  if (!el.value) return;
  selected.face.eyes = el.value;
  $("opt-eyes").value = el.value;
});
const setOdd = () => {
  if ($("opt-odd").checked) selected.face.odd_eye = $("opt-oddeye").value;
  else delete selected.face.odd_eye;
};
knob("opt-odd", setOdd);
knob("opt-oddeye", setOdd);
knob("opt-favorite", (el) => (selected.personality.favorite = el.value));
knob("opt-name", (el) => (designName = el.value.trim()));
knob("opt-finpat", (el) => (selected.coat.fins = el.value));
knob("opt-splotch", (el) => {
  selected.coat.splotch = Number(el.value);
  $("splotch-value").textContent = selected.coat.splotch.toFixed(2);
});
knob("opt-length", (el) => (selected.shape.length = Number(el.value)));
knob("opt-height", (el) => (selected.shape.height = Number(el.value)));
knob("opt-ears", (el) => {
  selected.shape.ears = Number(el.value) - 1;
  $("ears-value").textContent = Number(el.value).toFixed(1);
});
knob("opt-tail", (el) => (selected.shape.tail = Number(el.value)));
knob("opt-shine", (el) => {
  selected.shine = el.value || null;
  selected.face = { ...selected.face, shine: selected.shine, sparkle: false };
});
knob("opt-weight", (el) => (selected.shape.weight = Number(el.value)));
knob("opt-snout", (el) => (selected.shape.snout = Number(el.value)));
knob("opt-legs", (el) => (selected.shape.legs = Number(el.value)));
knob("opt-wool", (el) => (selected.shape.wool = Number(el.value)));
knob("opt-horns", (el) => (selected.shape.horns = Number(el.value)));
knob("opt-neck", (el) => (selected.shape.neck = Number(el.value)));
knob("opt-dome", (el) => (selected.shape.dome = Number(el.value)));
knob("opt-crest", (el) => (selected.shape.crest = Number(el.value)));
knob("opt-thick", (el) => (selected.shape.thick = Number(el.value)));
knob("opt-wings", (el) => (selected.shape.wings = Number(el.value)));
knob("opt-fins", (el) => (selected.shape.fins = Number(el.value)));
knob("opt-tailh", (el) => (selected.shape.tailh = Number(el.value)));
knob("opt-size", (el) => (selected.shape.size = Number(el.value)));

$("opt-species").addEventListener("change", () => {
  fillColors();
  buildRows();
  roll();
});
$("opt-variant").addEventListener("change", drawLitter);
for (const id of ["opt-plain", "opt-plain-color"]) {
  $(id).addEventListener("input", () => {
    drawLitter();
    drawStages();
  });
}
$("opt-primary").addEventListener("change", () => {
  // the second color can only be picked along with the first
  const game = !$("opt-primary").value;
  if (game) $("opt-secondary").value = "";
  $("opt-secondary").disabled = game;
  roll();
});
$("opt-secondary").addEventListener("change", roll);
$("roll-button").addEventListener("click", roll);
$("opt-growth").addEventListener("input", () => {
  $("growth-value").textContent = growth();
  showAdoptGrowth();
  drawLitter();
});
$("litter").addEventListener("click", (e) => {
  const b = e.target.closest(".litter-pet");
  if (b) select(litter[b.dataset.i]);
});

// Companions are always grown, whatever the slider says.
function showAdoptGrowth() {
  $("adopt-growth").textContent = species[$("opt-species").value].always_grown ? 10 : growth();
}

// The close-up pet, knobs and design as drawn, joins your pets for free.
async function adopt() {
  const design = Number($("opt-variant").value);
  const pet = design ? { ...selected, variant: design } : selected;
  const res = await fetch("/api/pet-lab/adopt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ genes: pet, growth: growth(), name: designName }),
  });
  const data = await res.json();
  $("adopt-message").innerHTML = res.ok ? `Adopted! <a href="/pets/care?pet=${data.id}">See ${data.name} in the Pet Care Center</a>` : data.detail;
}

$("adopt-button").onclick = adopt;

(async () => {
  species = await (await fetch("/api/pet-lab/species")).json();
  $("opt-species").innerHTML = Object.keys(species)
    .map((s) => `<option${s === LAB_FIRST ? " selected" : ""}>${s}</option>`)
    .join("");
  fillColors();
  buildRows();
  await roll();
  setInterval(() => {
    frame += 1;
    drawLitter();
    drawStages();
  }, TICK_MS);
})();
