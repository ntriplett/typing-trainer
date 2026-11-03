// The Wanderpaw lab (PLAN.md 11n): admin view of whole worlds. No fog, no
// walls in the way: click any place to open its small map; in your own
// world, put yourself on any small hex, refill energy, or start the world
// over. The land gallery shows one small map of every biome.

const canvas = document.getElementById("wander-map");
const info = document.getElementById("info");
const stats = document.getElementById("stats");
const opt = (id) => document.getElementById(id);
let world = null;
let selected = null;
let local = null; // the selected place's whole small map
let tile = null; // the selected small hex
const localCanvas = document.getElementById("local-map");
const localInfo = document.getElementById("local-info");

const words = (name) => (name || "").replace(/_/g, " ");
const isMine = () => Boolean(world && world.me);

async function fetchJson(url, body) {
  const res = await fetch(url, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

async function show(seed) {
  world = await fetchJson(seed === undefined ? "/api/wander-lab/world" : `/api/wander-lab/world?seed=${seed}`);
  opt("opt-seed").value = world.seed;
  opt("opt-fog").disabled = !isMine();
  if (!isMine()) opt("opt-fog").checked = false;
  selected = isMine() ? world.me.at : null;
  renderInfo();
  renderStats();
  render();
  loadLocal();
  loadNeeds();
}

// --- gate levels: what it takes to reach each place --------------------------------------

const needsCanvas = document.getElementById("needs-map");
let needs = null;
let shortcutsOpen = false;
let needsPicked = null;
const NEED_FILL = { 0: "#e6efcf", 2: "#eef0b8", 3: "#f2dc94", 8: "#eea867" };
const TYPE_ORDER = ["splash", "ember", "dream", "leaf", "shock"];

async function loadNeeds() {
  needs = (await fetchJson(`/api/wander-lab/needs?seed=${world.seed}&shortcuts=${shortcutsOpen}`)).needs;
  renderNeeds();
}

function needsOpts() {
  const fill = {};
  world.hexes.forEach((h) => {
    const k = WanderMap.key(h.q, h.r);
    const best = needs[k] && needs[k][0];
    fill[k] = best ? NEED_FILL[Math.max(0, ...Object.values(best))] : "#8f8a80";
  });
  return { size: Number(opt("opt-size").value), bare: true, trail: false, fog: false, fill, selected: needsPicked };
}

function renderNeeds() {
  opt("needs-button").textContent = shortcutsOpen ? "Shortcuts: open (fixed)" : "Shortcuts: broken";
  const map = { radius: world.radius, hexes: world.hexes.map((h) => ({ ...h, visited: true })), edges: world.edges, marks: [] };
  const opts = needsOpts();
  WanderMap.draw(needsCanvas, map, opts);
  const ctx = needsCanvas.getContext("2d");
  const s = opts.size;
  ctx.font = `bold ${Math.max(11, Math.round(s * 0.3))}px "Atkinson Hyperlegible Mono", monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  world.hexes.forEach((h) => {
    const k = WanderMap.key(h.q, h.r);
    const [x, y] = WanderMap.pointAt(needsCanvas, map, opts, h.q, h.r);
    const all = needs[k];
    if (!all) {
      ctx.fillStyle = "#fffaf0";
      ctx.fillText("no way", x, y + s * 0.35);
      return;
    }
    const chips = TYPE_ORDER.filter((t) => all[0][t]).map((t) => [t, all[0][t]]);
    const w = s * 0.42;
    const y1 = h.special ? y + s * 0.42 : y;
    chips.forEach(([t, n], i) => {
      const cx = x + (i - (chips.length - 1) / 2) * (w + 3);
      ctx.fillStyle = WanderMap.TYPE_COLORS[t];
      ctx.fillRect(cx - w / 2, y1 - w / 2, w, w);
      ctx.strokeStyle = "#3b2417";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(cx - w / 2, y1 - w / 2, w, w);
      ctx.fillStyle = "#fffaf0";
      ctx.fillText(String(n), cx, y1 + 1);
    });
    if (all.length > 1) {
      ctx.fillStyle = "#3b2417";
      ctx.fillText(`+${all.length - 1} way${all.length > 2 ? "s" : ""}`, x, y1 + w * 0.9);
    }
  });
  const h = needsPicked && world.hexes.find((x) => x.q === needsPicked[0] && x.r === needsPicked[1]);
  const all = h && needs[WanderMap.key(h.q, h.r)];
  const say = (n) => (Object.keys(n).length ? TYPE_ORDER.filter((t) => n[t]).map((t) => `${t} ${n[t]}`).join(" + ") : "nothing (free)");
  document.getElementById("needs-detail").innerHTML = h
    ? `<p><b>${h.name}</b> (${h.region})</p>${all ? `<ul>${all.map((n) => `<li>${say(n)}</li>`).join("")}</ul>` : "<p>No way in with shortcuts broken.</p>"}`
    : `<p class="hint">Click a place.</p>`;
}

opt("needs-button").onclick = () => {
  shortcutsOpen = !shortcutsOpen;
  loadNeeds();
};

needsCanvas.addEventListener("click", (e) => {
  if (!needs) return;
  const rect = needsCanvas.getBoundingClientRect();
  const x = ((e.clientX - rect.left) * needsCanvas.width) / rect.width;
  const y = ((e.clientY - rect.top) * needsCanvas.height) / rect.height;
  const map = { radius: world.radius, hexes: world.hexes, edges: world.edges };
  const hex = WanderMap.hexAt(needsCanvas, map, needsOpts(), x, y);
  needsPicked = world.hexes.some((h) => h.q === hex[0] && h.r === hex[1]) ? hex : null;
  renderNeeds();
});

// Walking steps from Camp along open edges (field-skill gates count as open).
function stepsFrom(start) {
  const exits = new Map();
  const cleared = new Set(isMine() ? world.me.cleared : []);
  world.edges.forEach((e) => {
    if (e.kind !== "open") return;
    // Shortcuts count once repaired (in your world), not before.
    if (e.gate && e.gate.kind === "quest" && !cleared.has(`${e.a.join(",")}|${e.b.join(",")}`)) return;
    const a = WanderMap.key(...e.a);
    const b = WanderMap.key(...e.b);
    (exits.get(a) || exits.set(a, []).get(a)).push(b);
    (exits.get(b) || exits.set(b, []).get(b)).push(a);
  });
  const dist = new Map([[start, 0]]);
  const todo = [start];
  while (todo.length) {
    const h = todo.shift();
    (exits.get(h) || []).forEach((n) => {
      if (!dist.has(n)) {
        dist.set(n, dist.get(h) + 1);
        todo.push(n);
      }
    });
  }
  return dist;
}

// The map as the player sees it (their save's fog), or all of it.
function mapView() {
  const at = isMine() ? world.me.at : null;
  const cleared = new Set(isMine() ? world.me.cleared : []);
  const edgeView = (e) => (e.gate ? { ...e, gate: { ...e.gate, cleared: cleared.has(`${e.a.join(",")}|${e.b.join(",")}`) } } : e);
  const marks = opt("opt-story").checked ? [...world.plan.givers.map((g) => g.lost.big), ...Object.values(world.plan.keys).map((k) => k.big)] : [];
  if (!opt("opt-fog").checked) {
    return { radius: world.radius, at, marks, hexes: world.hexes.map((h) => ({ ...h, visited: true })), edges: world.edges.map(edgeView) };
  }
  const visited = new Set(world.me.visited.map((v) => WanderMap.key(...v)));
  const seen = new Set(visited);
  world.me.visited.forEach(([q, r]) => WanderMap.DIRS.forEach(([dq, dr]) => seen.add(WanderMap.key(q + dq, r + dr))));
  const hexes = world.hexes
    .filter((h) => seen.has(WanderMap.key(h.q, h.r)))
    .map((h) => {
      const known = visited.has(WanderMap.key(h.q, h.r));
      return { ...h, visited: known, name: known ? h.name : null };
    });
  const edges = world.edges.filter((e) => visited.has(WanderMap.key(...e.a)) || visited.has(WanderMap.key(...e.b))).map(edgeView);
  return { radius: world.radius, at, hexes, edges, marks: [] };
}

function drawOpts() {
  return {
    size: Number(opt("opt-size").value),
    fog: opt("opt-fog").checked,
    names: opt("opt-names").checked,
    trail: opt("opt-paths").checked,
    selected,
  };
}

function render() {
  const map = mapView();
  const opts = drawOpts();
  WanderMap.draw(canvas, map, opts);
  if (opt("opt-steps").checked) {
    const dist = stepsFrom("0,0");
    const ctx = canvas.getContext("2d");
    const size = opts.size;
    ctx.font = `bold ${Math.max(12, Math.round(size * 0.36))}px "Atkinson Hyperlegible Mono", monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    map.hexes.forEach((h) => {
      const [x, y0] = WanderMap.pointAt(canvas, map, opts, h.q, h.r);
      const y = y0 - size * 0.45;
      ctx.fillStyle = "#fffaf0";
      ctx.fillRect(x - size * 0.22, y - size * 0.2, size * 0.44, size * 0.4);
      ctx.fillStyle = "#3b2417";
      ctx.fillText(String(dist.get(WanderMap.key(h.q, h.r)) ?? "-"), x, y + 1);
    });
  }
}

function renderInfo() {
  if (!selected) {
    info.innerHTML = `<h2 class="panel-title">Place</h2><p class="hint">Click a place on the map.</p>`;
    return;
  }
  const h = world.hexes.find((x) => x.q === selected[0] && x.r === selected[1]);
  const k = WanderMap.key(h.q, h.r);
  const steps = stepsFrom("0,0").get(k);
  const sides = world.edges
    .filter((e) => WanderMap.key(...e.a) === k || WanderMap.key(...e.b) === k)
    .map((e) => e.kind);
  const open = sides.filter((s) => s === "open").length;
  const walls = sides.filter((s) => s !== "open");
  const visited = isMine() && world.me.visited.some(([q, r]) => q === h.q && r === h.r);
  info.innerHTML = `
    <h2 class="panel-title">${h.name}</h2>
    <dl>
      <dt>Region</dt><dd><span class="type-chip" style="background:${WanderMap.TYPE_COLORS[h.region]}">${h.region}</span></dd>
      <dt>Land</dt><dd>${words(h.biome)}</dd>
      <dt>Special</dt><dd>${h.special || "-"}</dd>
      <dt>Ring</dt><dd>${h.ring}</dd>
      <dt>Steps</dt><dd>${steps ?? "-"} from Camp</dd>
      <dt>Ways out</dt><dd>${open}${walls.length ? `, walls: ${walls.join(", ")}` : ""}</dd>
      <dt>Hex</dt><dd>${h.q}, ${h.r}</dd>
      ${isMine() ? `<dt>Visited</dt><dd>${visited ? "yes" : "no"}</dd>` : ""}
    </dl>
    ${isMine() ? `<button class="button-go" id="teleport-button">Put me here</button>` : ""}
    <button class="button-go" id="reset-button">Start my world over${isMine() ? "" : " with this seed"}</button>
  `;
  const tp = document.getElementById("teleport-button");
  if (tp) tp.onclick = () => act("/api/wander-lab/teleport", { q: h.q, r: h.r });
  document.getElementById("reset-button").onclick = () => {
    if (confirm(`Start your Wanderpaw world over with seed ${world.seed}? Everything you've explored is forgotten, and your pets go back to level 1.`)) {
      act("/api/wander-lab/reset", { seed: world.seed });
    }
  };
}

async function act(url, body) {
  const keep = selected;
  const keepTile = tile;
  try {
    world = await fetchJson(url, body);
  } catch (err) {
    alert(err.message);
    return;
  }
  opt("opt-fog").disabled = false;
  selected = keep;
  tile = keepTile;
  renderInfo();
  renderStats();
  render();
  renderLocal();
}

function renderStats() {
  const dist = stepsFrom("0,0");
  const temples = world.hexes.filter((h) => h.special === "temple");
  const walls = {};
  world.edges.forEach((e) => {
    walls[e.kind] = (walls[e.kind] || 0) + 1;
  });
  stats.innerHTML = `
    <h2 class="panel-title">World ${world.seed}</h2>
    <p>${world.hexes.length} places, ${world.hexes.filter((h) => h.special === "town").length} towns.</p>
    <p>Temples (steps from Camp):<br>${temples
      .map((t) => `<span class="type-chip" style="background:${WanderMap.TYPE_COLORS[t.region]}">${t.region} ${dist.get(WanderMap.key(t.q, t.r))}</span>`)
      .join(" ")}</p>
    ${isMine() ? `<p>Try a boss (puts you at its door with the key; then open Wanderpaw and press Enter):<br>${temples
      .map((t) => `<button class="boss-button" data-region="${t.region}">${t.region}</button> <button class="letter-button" data-region="${t.region}">Letter</button>`)
      .join(" ")}</p>` : ""}
    <p>Edges: ${Object.entries(walls).map(([k, v]) => `${k} ${v}`).join(", ")}</p>
    <p>Gates: ${gateSummary()}</p>
    <p>Quests (star: where each lost thing hides; check):<br>${world.plan.givers
      .map((g) => {
        const name = (h) => world.hexes.find((x) => x.q === h[0] && x.r === h[1]).name;
        const check = g.lost.check ? ` (${g.lost.check[0]} ${g.lost.check[1]})` : "";
        const state = isMine() ? world.me.quests[g.id] || "-" : "";
        return `<span class="type-chip" style="background:${WanderMap.TYPE_COLORS[g.region]}">${g.region}</span> about ${g.shortcut}'s bridge: ${g.lost.kind} in ${name(g.lost.big)}${check} ${state}`;
      })
      .join("<br>")}</p>
    <p>Temple keys:<br>${Object.entries(world.plan.keys)
      .map(([r, k]) => `<span class="type-chip" style="background:${WanderMap.TYPE_COLORS[r]}">${r}</span> ${k.kind} in ${world.hexes.find((x) => x.q === k.big[0] && x.r === k.big[1]).name}`)
      .join("<br>")}</p>
    ${isMine() ? `<p>Visited ${world.me.visited.length} places. Temples open: ${world.me.temples.join(", ") || "none"}. Gates cleared: ${world.me.cleared.length}.</p>` : ""}
  `;
  stats.querySelectorAll(".letter-button").forEach((b) => (b.onclick = () => act("/api/wander-lab/keeper-beaten", { region: b.dataset.region })));
  stats.querySelectorAll(".boss-button").forEach((b) => (b.onclick = () => act("/api/wander-lab/boss", { region: b.dataset.region })));
  renderParty();
}

function gateSummary() {
  const counts = {};
  world.edges.forEach((e) => {
    if (!e.gate) return;
    const k = e.gate.kind === "quest" ? "shortcut" : `${e.gate.kind} ${e.gate.level}`;
    counts[k] = (counts[k] || 0) + 1;
  });
  return Object.entries(counts).sort().map(([k, v]) => `${k} ${v}`).join(", ");
}

// Your pets: level, type levels, and buttons to give XP.
async function renderParty() {
  const box = document.getElementById("party-box");
  box.hidden = !isMine();
  if (!isMine()) return;
  const res = await fetch("/api/wander/pets");
  if (res.ok) showPets(await res.json());
}

function showPets(data) {
  const types = (t) => Object.entries(t).map(([k, n]) => `${k} ${n}`).join(", ");
  document.getElementById("lab-pets").innerHTML = data.pets.length
    ? data.pets
        .map((p) => `<li><b>${p.name}</b> (${p.species}) lv ${p.level}, ${types(p.types)}, ${p.xp} xp
          <button class="button-go" data-xp="${p.id}" data-n="${Math.max(0, p.next - p.xp)}">+1 level</button>
          <button class="button-go" data-xp="${p.id}" data-n="${Math.max(0, p.plus4 - p.xp)}">+4 levels</button></li>`)
        .join("")
    : `<li class="hint">No pets that can adventure yet (fish stay home).</li>`;
  document.querySelectorAll("#lab-pets [data-xp]").forEach((b) => {
    b.onclick = async () => {
      const res = await fetch("/api/wander-lab/xp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pet_id: Number(b.dataset.xp), xp: Number(b.dataset.n) }),
      });
      if (res.ok) showPets(await res.json());
    };
  });
}

canvas.addEventListener("click", (e) => {
  if (!world) return;
  const rect = canvas.getBoundingClientRect();
  const x = ((e.clientX - rect.left) * canvas.width) / rect.width;
  const y = ((e.clientY - rect.top) * canvas.height) / rect.height;
  const [q, r] = WanderMap.hexAt(canvas, mapView(), drawOpts(), x, y);
  if (!world.hexes.some((h) => h.q === q && h.r === r)) return;
  selected = [q, r];
  renderInfo();
  render();
  loadLocal();
});

// --- the selected place's small map ---------------------------------------------

async function loadLocal() {
  if (!selected) {
    document.getElementById("local-section").hidden = true;
    return;
  }
  local = await fetchJson(`/api/wander-lab/local?seed=${world.seed}&q=${selected[0]}&r=${selected[1]}`);
  tile = null;
  document.getElementById("local-section").hidden = false;
  renderLocal();
}

function here() {
  return isMine() && local && world.me.at[0] === local.big[0] && world.me.at[1] === local.big[1];
}

// The small map as the player sees it (their fog), or all of it.
function localView() {
  const spot = here() ? world.me.spot : null;
  const place = world.hexes.find((h) => h.q === local.big[0] && h.r === local.big[1]);
  // Its own hexes, and (faded) the ring around it from the big hexes next door.
  const big = WanderMap.key(...local.big);
  const own = local.tiles.map((t) => ({ ...t, big }));
  const around = local.beyond.map((b) => ({ ...b, big: WanderMap.key(...b.big), faded: true }));
  const base = { radius: local.radius + 1, biome: local.biome, campfire: local.campfire, spot, place };
  if (!opt("opt-fog").checked) return { ...base, tiles: [...own, ...around] };
  const seenIn = (b, h) => (world.me.seen[b] || []).some((s) => s[0] === h[0] && s[1] === h[1]);
  return {
    ...base,
    tiles: [...own.filter((t) => seenIn(big, [t.q, t.r])), ...around.filter((b) => seenIn(b.big, b.at))],
  };
}

function renderLocal() {
  if (!local) return;
  const view = localView();
  WanderMap.drawLocal(localCanvas, view, { size: 34, fog: opt("opt-fog").checked, selected: tile, edge: local.radius });
  const counts = {};
  local.tiles.forEach((t) => {
    counts[t.kind] = (counts[t.kind] || 0) + 1;
  });
  const picked = tile && local.tiles.find((t) => t.q === tile[0] && t.r === tile[1]);
  const walkable = picked && !["tree", "bush", "rock", "cliff", "water", "ocean"].includes(picked.kind);
  localInfo.innerHTML = `
    <h2 class="panel-title">${view.place.name}: small map</h2>
    <dl>
      <dt>Land</dt><dd>${words(local.biome)}</dd>
      <dt>Feel</dt><dd>${words(local.style)}</dd>
      <dt>Walkable</dt><dd>${Math.round(local.walkable * 100)}%</dd>
      <dt>Exits</dt><dd>${local.tiles.filter((t) => t.exit !== undefined).length}</dd>
      <dt>Tiles</dt><dd>${Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join(", ")}</dd>
    </dl>
    <p>Places: ${local.tiles.filter((t) => t.poi || t.role).map((t) => t.poi || t.role).join(", ") || "none"}</p>
    <p>Nooks: ${local.tiles.filter((t) => t.nook).map((t) => t.nook).join(", ") || "none"}</p>
    ${picked ? `<p>Small hex ${picked.q}, ${picked.r}: <b>${words(picked.kind)}</b>${picked.exit !== undefined ? " (exit)" : ""}${picked.poi ? `, ${picked.poi}` : ""}${picked.role ? `, ${picked.role}` : ""}${picked.nook ? `, ${picked.nook}` : ""}</p>` : `<p class="hint">Click a small hex.</p>`}
    ${picked && (walkable || picked.nook) && isMine() ? `<button class="button-go" id="spot-button">Put me here</button>` : ""}
  `;
  const btn = document.getElementById("spot-button");
  if (btn) btn.onclick = () => act("/api/wander-lab/teleport", { q: local.big[0], r: local.big[1], spot: [picked.q, picked.r] });
}

localCanvas.addEventListener("click", (e) => {
  if (!local) return;
  const rect = localCanvas.getBoundingClientRect();
  const x = ((e.clientX - rect.left) * localCanvas.width) / rect.width;
  const y = ((e.clientY - rect.top) * localCanvas.height) / rect.height;
  const [q, r] = WanderMap.hexAtLocal(localCanvas, localView(), { size: 34 }, x, y);
  if (!local.tiles.some((t) => t.q === q && t.r === r)) return;
  tile = [q, r];
  renderLocal();
});

// --- the land gallery --------------------------------------------------------------

async function showGallery() {
  const maps = await fetchJson(`/api/wander-lab/gallery?seed=${world.seed}`);
  const box = document.getElementById("gallery");
  box.innerHTML = "";
  maps.forEach((m) => {
    const fig = document.createElement("figure");
    const c = document.createElement("canvas");
    WanderMap.drawLocal(c, { ...m, spot: null }, { size: 14, fog: false, edge: m.radius });
    fig.append(c);
    const cap = document.createElement("figcaption");
    cap.textContent = `${words(m.biome)} (${words(m.style)}, ${Math.round(m.walkable * 100)}%)`;
    fig.append(cap);
    fig.onclick = async () => {
      if (m.seed !== world.seed) await show(m.seed);
      selected = m.big;
      renderInfo();
      render();
      await loadLocal();
      document.getElementById("local-section").scrollIntoView({ behavior: "smooth" });
    };
    box.append(fig);
  });
  document.getElementById("gallery-section").hidden = false;
}

opt("mine-button").onclick = () => show();
opt("seed-button").onclick = () => show(Number(opt("opt-seed").value) || 0);
opt("random-button").onclick = () => show(Math.floor(Math.random() * 2 ** 31));
opt("refill-button").onclick = () => act("/api/wander-lab/refill", {});
opt("gallery-button").onclick = showGallery;
["opt-fog", "opt-names", "opt-paths", "opt-steps", "opt-size", "opt-story"].forEach((id) =>
  opt(id).addEventListener("input", () => {
    render();
    renderLocal();
    if (needs) renderNeeds();
  }));

show();

// Straight to the Heartstone with all five relics, in your own world, to place them and watch.
document.getElementById("ending-button").addEventListener("click", async () => {
  if (!confirm("This puts you at the Heartstone with all five relics, in your own save, and can't be undone: creatures and gates get harder for all five. Go ahead?")) return;
  const res = await fetch("/api/wander-lab/to-the-end", { method: "POST" });
  if (res.ok) location.href = "/wanderpaw";
});
