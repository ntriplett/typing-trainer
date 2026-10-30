// Wanderpaw's big map (PLAN.md 11n): pointy-top hexes in axial (q, r), like
// app/wanderpaw/hexes.py. Standalone: the play page and the lab both draw
// with it.
//
//   WanderMap.draw(canvas, map, opts)   // map: {radius, hexes, edges, at}
//   WanderMap.hexAt(canvas, map, opts, x, y) -> [q, r] (canvas pixels)
//
// opts: size (hex corner radius, px), fog (true: only what's in map.hexes
// is known, unvisited ones dimmed; the lab passes false), labels
// ({"q,r": {word, typed}}), names (draw place names), selected ([q, r]),
// trail (draw known open paths between visited hexes).

const WanderMap = (() => {
  const SQRT3 = Math.sqrt(3);
  const DIRS = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];

  const TYPE_COLORS = {
    camp: "#8b5a2b", ember: "#c8432f", splash: "#3a7fc8", leaf: "#4f8f2a", dream: "#8a4fb8", shock: "#e89a2a",
  };
  const BIOME_COLORS = {
    fields: "#cdd884", orchard: "#aec870",
    meadow: "#a5c862", woods: "#77a447", fern_hollow: "#64935a", deepwood: "#4a7a3c",
    brookside: "#a6d6c8", marsh: "#86b39c", lakeshore: "#80bcdc", isles: "#64a6d2",
    heath: "#dfab72", red_rocks: "#cc8556", hot_springs: "#e6aa92", ember_peaks: "#b06446",
    windy_hills: "#ecd889", mesa: "#dfbc68", ridge: "#cdaa56", storm_peaks: "#b09256",
    glade: "#c1b1dd", mushroom_grove: "#b097cf", mist_vale: "#a6a6c8", crystal_hollow: "#8a79ba",
  };
  const WALLS = {
    river: { color: "#3a7fc8", width: 0.16 },
    cliff: { color: "#6b4226", width: 0.16 },
    thicket: { color: "#2f5a22", width: 0.18 },
    rocks: { color: "#7a7268", width: 0.15 },
  };

  // Tiny pixel pictures: one char per pixel, "." clear.
  const PAL = {
    k: "#3b2417", g: "#3f6e34", G: "#5f9a3c", t: "#7a5230", b: "#3a7fc8", B: "#a8d5e2", w: "#fbf1dc",
    r: "#b8432f", o: "#e8b33e", y: "#f6d465", s: "#8a8478", S: "#c9c1b0", p: "#8a4fb8", P: "#d6b8ee",
    m: "#d9822b", c: "#c95b8c", n: "#8b5a2b",
  };
  const GLYPHS = {
    tree: ["..g..", ".gGg.", "gGgGg", ".gGg.", "..t.."],
    pine: ["..g..", ".gGg.", "..g..", ".gGg.", "..t.."],
    tuft: [".....", "G.G.G", ".GGG.", "..G..", "....."],
    wave: [".....", ".B.B.", "B.B.B", ".....", "....."],
    reed: ["G...G", "G.G.G", "GGG.G", ".GGG.", "....."],
    rock: [".....", ".sS..", "sSSs.", "sssss", "....."],
    peak: ["..w..", ".wSs.", ".sSs.", "sSsss", "....."],
    flame: ["..o..", ".omo.", ".oyo.", "omymo", "....."],
    bolt: ["...y.", "..y..", ".yyy.", "..y..", ".y..."],
    shroom: [".ccc.", "cwcwc", "..w..", "..w..", "....."],
    crystal: ["..P..", ".PpP.", ".PpP.", ".ppp.", "....."],
    star: ["..y..", ".yyy.", "..y..", ".....", "....."],
    apple: ["..g..", ".GrG.", "GrGrG", ".GGG.", "..t.."],
  };
  const BIOME_GLYPHS = {
    fields: ["tuft"], orchard: ["apple", "tuft"],
    meadow: ["tuft", "tuft", "tree"], woods: ["tree", "tree", "pine"], fern_hollow: ["tree", "reed"], deepwood: ["pine", "pine", "tree"],
    brookside: ["wave", "reed"], marsh: ["reed", "reed", "wave"], lakeshore: ["wave", "wave", "reed"], isles: ["wave", "wave", "tree"],
    heath: ["tuft", "rock"], red_rocks: ["rock", "rock"], hot_springs: ["wave", "flame"], ember_peaks: ["peak", "flame"],
    windy_hills: ["tuft", "rock"], mesa: ["rock"], ridge: ["peak", "rock"], storm_peaks: ["peak", "bolt"],
    glade: ["tuft", "star"], mushroom_grove: ["shroom", "shroom", "tree"], mist_vale: ["star", "tuft"], crystal_hollow: ["crystal", "rock"],
  };
  const SPECIALS = {
    camp: [
      "....o....", "...omo...", "....y....", ".........", "...nnn...", "..nwnwn..", ".nwwnwwn.", "nnnnnnnnn", ".........",
    ],
    town: [
      ".........", "..r...r..", ".rrr.rrr.", "rrrrrrrrr", ".wnw.wnw.", ".wnw.wnw.", ".www.www.", ".........", ".........",
    ],
    temple: [
      "....k....", "...kSk...", "..kSSSk..", ".kkkkkkk.", ".S.S.S.S.", ".S.S.S.S.", ".S.S.S.S.", "kkkkkkkkk", ".........",
    ],
    final: [
      "....y....", "...yPy...", "...sSs...", "...sSs...", "...sSs...", "...sSs...", "..sSSSs..", ".sssssss.", ".........",
    ],
    paw: [".k.k.", "k.k.k", ".....", ".kkk.", ".kkk."],
  };

  const key = (q, r) => `${q},${r}`;

  function geometry(canvas, map, opts) {
    const size = opts.size || 34;
    const r = map.radius;
    const width = Math.ceil(SQRT3 * size * (2 * r + 1)) + 8;
    const height = Math.ceil(size * (3 * r + 2)) + 8;
    return { size, width, height, cx: width / 2, cy: height / 2 };
  }

  function center(g, q, r) {
    return [g.cx + g.size * SQRT3 * (q + r / 2), g.cy + g.size * 1.5 * r];
  }

  function corner(g, x, y, i) {
    const a = (Math.PI / 180) * (60 * i - 30);
    return [x + g.size * Math.cos(a), y + g.size * Math.sin(a)];
  }

  function hexPath(ctx, g, x, y, inset = 0) {
    const s = g.size - inset;
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 180) * (60 * i - 30);
      const px = x + s * Math.cos(a);
      const py = y + s * Math.sin(a);
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath();
  }

  // Side of the hex facing direction d (at screen angle -60d): corners at
  // -60d -+ 30, which are corners -d and 1-d (corner i sits at 60i - 30).
  function side(g, x, y, d) {
    const i0 = (6 - d) % 6;
    return [corner(g, x, y, i0), corner(g, x, y, (i0 + 1) % 6)];
  }

  function glyph(ctx, rows, x, y, px) {
    const w = rows[0].length;
    const h = rows.length;
    const ox = Math.round(x - (w * px) / 2);
    const oy = Math.round(y - (h * px) / 2);
    rows.forEach((row, j) => {
      [...row].forEach((ch, i) => {
        if (ch === ".") return;
        ctx.fillStyle = PAL[ch];
        ctx.fillRect(ox + i * px, oy + j * px, px, px);
      });
    });
  }

  // A steady little random per hex, so decorations don't jump about.
  function hashRand(q, r) {
    let s = (q * 73856093) ^ (r * 19349663) ^ 0x5bd1e995;
    return () => {
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      return s / 0x7fffffff;
    };
  }

  function decorate(ctx, g, h, x, y) {
    const rand = hashRand(h.q, h.r);
    const px = Math.max(2, Math.round(g.size / 14));
    if (h.special) {
      glyph(ctx, SPECIALS[h.special], x, y - g.size * 0.05, px + 1);
      return;
    }
    const names = BIOME_GLYPHS[h.biome] || ["tuft"];
    const spots = [[-0.42, -0.3], [0.38, -0.32], [-0.05, 0.05], [-0.4, 0.35], [0.4, 0.3]];
    spots.forEach(([dx, dy]) => {
      if (rand() < 0.25) return;
      const name = names[Math.floor(rand() * names.length)];
      glyph(ctx, GLYPHS[name], x + dx * g.size + (rand() - 0.5) * 4, y + dy * g.size + (rand() - 0.5) * 4, px);
    });
  }

  function drawWall(ctx, g, a, b, kind) {
    const [x, y] = center(g, a[0], a[1]);
    const d = DIRS.findIndex(([dq, dr]) => dq === b[0] - a[0] && dr === b[1] - a[1]);
    const [p0, p1] = side(g, x, y, d);
    const style = WALLS[kind] || WALLS.rocks;
    ctx.save();
    ctx.lineCap = "round";
    ctx.strokeStyle = style.color;
    ctx.lineWidth = Math.max(3, g.size * style.width);
    if (kind === "thicket" || kind === "rocks") {
      const n = 4;
      ctx.fillStyle = style.color;
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        const cx = p0[0] + (p1[0] - p0[0]) * t;
        const cy = p0[1] + (p1[1] - p0[1]) * t;
        const s = ctx.lineWidth;
        kind === "rocks" ? ctx.fillRect(cx - s / 2, cy - s / 2, s, s) : (ctx.beginPath(), ctx.arc(cx, cy, s * 0.62, 0, 7), ctx.fill());
      }
    } else {
      ctx.beginPath();
      ctx.moveTo(p0[0], p0[1]);
      if (kind === "river") {
        const mx = (p0[0] + p1[0]) / 2;
        const my = (p0[1] + p1[1]) / 2;
        const nx = -(p1[1] - p0[1]) * 0.18;
        const ny = (p1[0] - p0[0]) * 0.18;
        ctx.quadraticCurveTo(mx + nx, my + ny, p1[0], p1[1]);
      } else {
        ctx.lineTo(p1[0], p1[1]);
      }
      ctx.stroke();
      if (kind === "river") {
        ctx.strokeStyle = "#a8d5e2";
        ctx.lineWidth = Math.max(1, g.size * 0.05);
        ctx.stroke();
      }
      if (kind === "cliff") {
        ctx.strokeStyle = "#3b2417";
        ctx.lineWidth = Math.max(1, g.size * 0.05);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  function drawTrail(ctx, g, a, b) {
    const [x0, y0] = center(g, a[0], a[1]);
    const [x1, y1] = center(g, b[0], b[1]);
    ctx.save();
    ctx.strokeStyle = "rgba(92, 58, 26, 0.55)";
    ctx.lineWidth = Math.max(2, g.size * 0.07);
    ctx.setLineDash([g.size * 0.12, g.size * 0.12]);
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
    ctx.restore();
  }

  function drawLabel(ctx, g, x, y, label) {
    ctx.save();
    ctx.font = `bold ${Math.max(14, Math.round(g.size * 0.42))}px "Atkinson Hyperlegible Mono", monospace`;
    const w = ctx.measureText(label.word).width + 12;
    const h = Math.max(20, g.size * 0.6);
    const bx = x - w / 2;
    const by = y + g.size * 0.18;
    ctx.fillStyle = "#fffaf0";
    ctx.strokeStyle = "#3b2417";
    ctx.lineWidth = 2;
    ctx.fillRect(bx, by, w, h);
    ctx.strokeRect(bx, by, w, h);
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    const typed = label.typed || 0;
    let tx = bx + 6;
    [...label.word].forEach((ch, i) => {
      ctx.fillStyle = i < typed ? "#4f7a2a" : i === typed && typed > 0 ? "#b8432f" : "#3b2417";
      ctx.fillText(ch, tx, by + h / 2 + 1);
      tx += ctx.measureText(ch).width;
    });
    ctx.restore();
  }

  function draw(canvas, map, opts = {}) {
    const g = geometry(canvas, map, opts);
    canvas.width = g.width;
    canvas.height = g.height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, g.width, g.height);
    const fog = opts.fog !== false;
    const byKey = new Map(map.hexes.map((h) => [key(h.q, h.r), h]));

    // Land, then region borders, then decorations, then walls on top.
    map.hexes.forEach((h) => {
      const [x, y] = center(g, h.q, h.r);
      hexPath(ctx, g, x, y);
      ctx.fillStyle = BIOME_COLORS[h.biome] || "#d8c7a0";
      ctx.fill();
    });
    map.hexes.forEach((h) => {
      const [x, y] = center(g, h.q, h.r);
      DIRS.forEach(([dq, dr], d) => {
        const n = byKey.get(key(h.q + dq, h.r + dr));
        if (n && n.region === h.region) return;
        const [p0, p1] = side(g, x, y, d);
        // Region borders: a thin dotted line in the region's color, so they
        // never look like walls. The edge of the world is a solid outline.
        ctx.strokeStyle = n ? TYPE_COLORS[h.region] : "#3b2417";
        ctx.lineWidth = n ? 2 : 3;
        ctx.setLineDash(n ? [2, 4] : []);
        ctx.beginPath();
        ctx.moveTo(p0[0], p0[1]);
        ctx.lineTo(p1[0], p1[1]);
        ctx.stroke();
        ctx.setLineDash([]);
      });
      decorate(ctx, g, h, x, y);
    });
    if (opts.trail) {
      map.edges.forEach((e) => {
        if (e.kind !== "open") return;
        const a = byKey.get(key(...e.a));
        const b = byKey.get(key(...e.b));
        if (a && b && (!fog || (a.visited && b.visited))) drawTrail(ctx, g, e.a, e.b);
      });
    }
    map.edges.forEach((e) => {
      if (e.kind !== "open") drawWall(ctx, g, e.a, e.b, e.kind);
    });
    // Glimpsed hexes: hazy until visited.
    if (fog) {
      map.hexes.forEach((h) => {
        if (h.visited) return;
        const [x, y] = center(g, h.q, h.r);
        hexPath(ctx, g, x, y);
        ctx.fillStyle = "rgba(251, 241, 220, 0.55)";
        ctx.fill();
      });
    }
    if (opts.names) {
      ctx.save();
      ctx.font = `${Math.max(10, Math.round(g.size * 0.3))}px "Atkinson Hyperlegible Mono", monospace`;
      ctx.textAlign = "center";
      ctx.fillStyle = "#3b2417";
      map.hexes.forEach((h) => {
        if (!h.name) return;
        const [x, y] = center(g, h.q, h.r);
        ctx.fillText(h.special ? h.name.replace(/^The /, "") : h.name.split(" ")[0], x, y + g.size * 0.72);
      });
      ctx.restore();
    }
    if (opts.selected) {
      const [x, y] = center(g, ...opts.selected);
      hexPath(ctx, g, x, y, 3);
      ctx.strokeStyle = "#e8b33e";
      ctx.lineWidth = 4;
      ctx.stroke();
    }
    (opts.marks || []).forEach(([q, r]) => {
      const [x, y] = center(g, q, r);
      ctx.fillStyle = "rgba(232, 179, 62, 0.85)";
      ctx.fillRect(x - 3, y + g.size * 0.45, 6, 6);
    });
    if (map.at) {
      const [x, y] = center(g, ...map.at);
      ctx.fillStyle = "#fffaf0";
      ctx.beginPath();
      ctx.arc(x, y, g.size * 0.36, 0, 7);
      ctx.fill();
      ctx.strokeStyle = "#3b2417";
      ctx.lineWidth = 2;
      ctx.stroke();
      glyph(ctx, SPECIALS.paw, x, y, Math.max(3, Math.round(g.size / 10)));
    }
    Object.entries(opts.labels || {}).forEach(([k, label]) => {
      const [q, r] = k.split(",").map(Number);
      const [x, y] = center(g, q, r);
      drawLabel(ctx, g, x, y, label);
    });
  }

  function hexAt(canvas, map, opts, x, y) {
    const g = geometry(canvas, map, opts);
    const px = (x - g.cx) / g.size;
    const py = (y - g.cy) / g.size;
    const q = (SQRT3 / 3) * px - py / 3;
    const r = (2 / 3) * py;
    // round in cube coordinates
    let rq = Math.round(q);
    let rr = Math.round(r);
    const rs = Math.round(-q - r);
    const dq = Math.abs(rq - q);
    const dr = Math.abs(rr - r);
    const ds = Math.abs(rs + q + r);
    if (dq > dr && dq > ds) rq = -rr - rs;
    else if (dr > ds) rr = -rq - rs;
    return [rq, rr];
  }

  return { draw, hexAt, TYPE_COLORS, BIOME_COLORS, DIRS, key };
})();
