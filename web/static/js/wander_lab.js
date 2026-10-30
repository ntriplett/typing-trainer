// The Wanderpaw lab (PLAN.md 11n): admin view of whole worlds. No fog, no
// walls in the way: click any place to see it; in your own world, put
// yourself anywhere or start the world over.

const canvas = document.getElementById("wander-map");
const info = document.getElementById("info");
const stats = document.getElementById("stats");
const opt = (id) => document.getElementById(id);
let world = null;
let selected = null;

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
  selected = null;
  renderInfo();
  renderStats();
  render();
}

// Walking steps from Camp along open edges.
function stepsFrom(start) {
  const exits = new Map();
  world.edges.forEach((e) => {
    if (e.kind !== "open") return;
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
  if (!opt("opt-fog").checked) {
    return { radius: world.radius, at, hexes: world.hexes.map((h) => ({ ...h, visited: true })), edges: world.edges };
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
  const edges = world.edges.filter((e) => visited.has(WanderMap.key(...e.a)) || visited.has(WanderMap.key(...e.b)));
  return { radius: world.radius, at, hexes, edges };
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
      const x = canvas.width / 2 + size * Math.sqrt(3) * (h.q + h.r / 2);
      const y = canvas.height / 2 + size * 1.5 * h.r - size * 0.45;
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
    if (confirm(`Start your Wanderpaw world over with seed ${world.seed}? Everything you've explored is forgotten.`)) {
      act("/api/wander-lab/reset", { seed: world.seed });
    }
  };
}

async function act(url, body) {
  const keep = selected;
  try {
    world = await fetchJson(url, body);
  } catch (err) {
    alert(err.message);
    return;
  }
  opt("opt-fog").disabled = false;
  selected = keep;
  renderInfo();
  renderStats();
  render();
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
    <p>Edges: ${Object.entries(walls).map(([k, v]) => `${k} ${v}`).join(", ")}</p>
    ${isMine() ? `<p>Visited ${world.me.visited.length} places.</p>` : ""}
  `;
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
});

opt("mine-button").onclick = () => show();
opt("seed-button").onclick = () => show(Number(opt("opt-seed").value) || 0);
opt("random-button").onclick = () => show(Math.floor(Math.random() * 2 ** 31));
["opt-fog", "opt-names", "opt-paths", "opt-steps", "opt-size"].forEach((id) => opt(id).addEventListener("input", render));

show();
