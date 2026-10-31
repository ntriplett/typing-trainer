// Wanderpaw's maps (PLAN.md 11n), like app/wanderpaw/hexes.py and
// local.py. Standalone: the play page and the lab both draw with it.
//
// Small hexes are pointy-top in axial (q, r). Big hexes are clusters of
// them that tile one world grid (local.SPANS), so a big hex sits where its
// small hexes do: turned TILT degrees, drawn as a hexagon with flat sides
// facing its neighbors.
//
//   WanderMap.draw(canvas, map, opts)   // map: {radius, hexes, edges, at}
//   WanderMap.hexAt(canvas, map, opts, x, y) -> [q, r] (canvas pixels)
//
// opts: size (hex corner radius, px), fog (true: only what's in map.hexes
// is known, unvisited ones dimmed; the lab passes false), labels
// ({"q,r": {word, typed}}), names (draw place names), selected ([q, r]),
// bare (no land pictures, just special places), fill ({"q,r": color}),
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
    m: "#d9822b", c: "#c95b8c", n: "#8b5a2b", O: "#fffaf0",
  };
  const GLYPHS = {
    tree: ["..g..", ".gGg.", "gGgGg", ".gGg.", "..t.."],
    pine: ["..g..", ".gGg.", "..g..", ".gGg.", "..t.."],
    tuft: [".....", "G.G.G", ".GGG.", "..G..", "....."],
    wave: [".....", ".B.B.", "B.B.B", ".....", "....."],
    swell: [".....", "..b..", ".b.b.", ".....", "....."],
    mount: ["...w...", "..wwk..", ".ttwtk.", "tttttkk", "ttttkkk"],
    reed: ["G...G", "G.G.G", "GGG.G", ".GGG.", "....."],
    rock: [".....", ".sS..", "sSSs.", "sssss", "....."],
    peak: ["..w..", ".wSs.", ".sSs.", "sSsss", "....."],
    flame: ["..o..", ".omo.", ".oyo.", "omymo", "....."],
    bolt: ["...y.", "..y..", ".yyy.", "..y..", ".y..."],
    shroom: [".ccc.", "cwcwc", "..w..", "..w..", "....."],
    crystal: ["..P..", ".PpP.", ".PpP.", ".ppp.", "....."],
    star: ["..y..", ".yyy.", "..y..", ".....", "....."],
    apple: ["..g..", ".GrG.", "GrGrG", ".GGG.", "..t.."],
    bush: [".....", ".GgG.", "GgGgG", ".ggg.", "....."],
    flower: [".....", ".c.y.", "cGcGy", ".G.G.", "....."],
    house: ["..r..", ".rrr.", "rrrrr", ".wnw.", ".wnw."],
    logfire: ["..o..", ".omo.", ".oyo.", "nnnnn", "....."],
    planks: ["n.n.n", "nnnnn", "n.n.n", "nnnnn", "n.n.n"],
    stones: [".....", ".S...", "...S.", ".S...", "....."],
    cliffs: ["kkk..", ".....", "..kkk", ".....", "kk.kk"],
    sign: ["nnnn.", "nnnnn", "nnnn.", ".n...", ".n..."],
    smoke: [".S...", "..S..", ".S.S.", "..S..", ".S..."],
    // gates
    dark: ["kkkkk", "k...k", "k.y.k", "k...k", "kkkkk"],
    flames: ["o.o.o", "omomo", "mymym", "nnnnn", "....."],
    gap: ["n...n", "n...n", "k...k", "kk.kk", "kkkkk"],
    old_gate: ["sssss", "s.s.s", "sysys", "s.s.s", "sssss"],
    guardian: [".sss.", "skSks", "sSSSs", ".sSs.", "ss.ss"],
    broken_bridge: ["n.n..", "nn..n", ".....", "n..nn", "..n.n"],
    // places
    forage: [".....", ".g...", "grG..", ".Grg.", "..G.."],
    chest: [".....", "nnnnn", "nonon", "nnnnn", "....."],
    shrine: ["..y..", ".sSs.", ".S.S.", ".S.S.", "sssss"],
    lost: ["..y..", ".yoy.", "yooOy", ".yoy.", "..y.."],
    elder: ["..y..", ".rrr.", "rrrrr", ".wnw.", ".wnw."],
    board: ["nnnnn", "nwwwn", "nwwwn", "nnnnn", ".n.n."],
    inn: [".rrr.", "rrrrr", "ryyyr", ".wnw.", ".wnw."],
    shop: ["rwrwr", "rwrwr", ".....", ".wnw.", ".wnw."],
    // nooks on open ground (caves, tunnels and glades are drawn by drawNooks)
    fishing: ["....n", "...nB", "..n.B", ".n..B", "n..bb"],
    dive: ["..B..", ".B.B.", "..B..", ".bBb.", "bbbbb"],
    buried: ["n...n", ".n.n.", "..n..", ".n.n.", "n...n"],
    cache: ["r...r", ".r.r.", "..r..", ".r.r.", "r...r"],
    lookout: ["..n..", ".nnn.", "..n..", ".n.n.", "n...n"],
    spring: [".B.B.", "..B..", ".bbb.", "bBBBb", ".bbb."],
    ruin: ["S.S..", "S.S.S", "SSS.S", "sSSSs", "sssss"],
    nest: [".....", "..w..", ".nwn.", "nnnnn", ".nnn."],
    berries: [".....", ".GpG.", "pGpGp", ".GpG.", "....."],
    log: [".....", ".....", "ntttn", "nkkkn", "ntttn"],
    statue: ["..S..", ".SSS.", "..S..", ".SSS.", "sssss"],
    traveler: ["..o..", ".ooo.", "..n..", ".nnn.", ".n.n."],
    well: [".nnn.", "n...n", "sSSSs", "sbbbs", "sssss"],
    rune: [".sss.", "sPpPs", "spPps", "sPpPs", ".sss."],
    machine: ["sssss", "sy.ys", "s.y.s", "sssss", "s...s"],
    tangle: ["g.G.g", ".GgG.", "GgGgG", ".GgG.", "g.G.g"],
    hole: [".....", ".kkk.", "kkkkk", "kkkkk", "....."],
    ring: ["c...c", ".....", "c...c", ".....", ".c.c."],
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

  // The world grid (local.py): big hex (q, r)'s middle is small hex
  // SPAN_A*q + SPAN_B*r.
  const SPAN_A = [11, -5];
  const SPAN_B = [5, 6];
  const AREA = SPAN_A[0] * SPAN_B[1] - SPAN_A[1] * SPAN_B[0];
  const span = (q, r) => [SPAN_A[0] * q + SPAN_B[0] * r, SPAN_A[1] * q + SPAN_B[1] * r];
  const smallXY = (q, r) => [SQRT3 * (q + r / 2), 1.5 * r]; // size 1
  const [SPAN_X, SPAN_Y] = smallXY(...SPAN_A);
  const BIG_STEP = Math.hypot(SPAN_X, SPAN_Y); // between big middles, in small sizes
  const BIG_CORNER = BIG_STEP / SQRT3; // a big hex's corner radius, in small sizes
  const TILT = Math.atan2(-SPAN_Y, SPAN_X); // where big direction 0 points (ccw)

  // Small maps (big: false): pointy-top, size = corner radius. Big maps
  // (big: true): size = a big hex's corner radius, turned TILT to match the
  // small grid, or not (opts.straight: pointy-top, the way you'd draw a
  // map by itself). focus centers the canvas on a hex, showing `view`
  // hexes around it; camera (fractional q, r) overrides where the middle
  // is, for sliding between hexes.
  function geometry(canvas, map, opts, big = false) {
    const size = opts.size || 34;
    const r = opts.focus ? opts.view : opts.radius ?? map.radius;
    let width;
    let height;
    if (big) {
      const reach = (r * BIG_STEP / BIG_CORNER + 1) * size;
      width = Math.ceil(2 * reach) + 8;
      height = width;
    } else {
      width = Math.ceil(SQRT3 * size * (2 * r + 1)) + 8;
      height = Math.ceil(size * (3 * r + 2)) + 8;
    }
    const g = { size, width, height, big, cx: width / 2, cy: height / 2, turn: big && opts.straight ? TILT : 0 };
    if (opts.legend && map.shape) {
      // A paper map: just the land, with the legend in the right margin.
      const pts = map.shape.map(([q, r]) => center({ ...g, cx: 0, cy: 0 }, q, r));
      const xs = pts.map((p) => p[0]);
      const ys = pts.map((p) => p[1]);
      g.cx = -Math.min(...xs) + size + 12;
      g.cy = -Math.min(...ys) + size + 12;
      g.width = Math.ceil(g.cx + Math.max(...xs) + size + LEGEND_WIDTH);
      g.height = Math.ceil(g.cy + Math.max(...ys) + size + 12);
    }
    if (opts.focus) {
      const [x, y] = center(g, ...(opts.camera || opts.focus));
      g.cx += width / 2 - x;
      g.cy += height / 2 - y;
    }
    return g;
  }

  const distance = (q, r) => (Math.abs(q) + Math.abs(r) + Math.abs(q + r)) / 2;

  function center(g, q, r) {
    if (g.big) {
      const [x, y] = turned(smallXY(...span(q, r)), g.turn);
      const k = g.size / BIG_CORNER;
      return [g.cx + x * k, g.cy + y * k];
    }
    const [x, y] = smallXY(q, r);
    return [g.cx + g.size * x, g.cy + g.size * y];
  }

  // Turn a screen point (y down) clockwise by a.
  const turned = ([x, y], a) => (a ? [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)] : [x, y]);

  // Corner i of a hex, on screen (y down). Small hexes: corner i at 60i - 30
  // degrees clockwise. Big hexes: at TILT + 30 + 60i counter-clockwise.
  function cornerAt(g, x, y, i, s = g.size) {
    if (g.big) {
      const a = TILT - g.turn + (Math.PI / 180) * (30 + 60 * i);
      return [x + s * Math.cos(a), y - s * Math.sin(a)];
    }
    const a = (Math.PI / 180) * (60 * i - 30);
    return [x + s * Math.cos(a), y + s * Math.sin(a)];
  }

  function hexPath(ctx, g, x, y, inset = 0) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const [px, py] = cornerAt(g, x, y, i, g.size - inset);
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath();
  }

  // The side of a hex facing direction d. Small: direction d is at screen
  // angle -60d, between corners -d and 1-d. Big: d faces TILT + 60d, between
  // corners d-1 and d.
  function side(g, x, y, d) {
    if (g.big) return [cornerAt(g, x, y, (d + 5) % 6), cornerAt(g, x, y, d)];
    const i0 = (6 - d) % 6;
    return [cornerAt(g, x, y, i0), cornerAt(g, x, y, (i0 + 1) % 6)];
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

  function decorate(ctx, g, h, x, y, simple) {
    const rand = hashRand(h.q, h.r);
    const px = Math.max(2, Math.round(g.size / 14));
    if (h.special) {
      glyph(ctx, SPECIALS[h.special], x, y - g.size * 0.05, px + 1);
      return;
    }
    const names = BIOME_GLYPHS[h.biome] || ["tuft"];
    if (simple) {
      glyph(ctx, GLYPHS[names[0]], x, y, Math.max(2, Math.round(g.size / 11)));
      return;
    }
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

  // A gate on a big edge: a diamond in its type's color with the levels it
  // takes, planks for a broken shortcut; faded once cleared.
  function drawGate(ctx, g, e) {
    const [x0, y0] = center(g, ...e.a);
    const [x1, y1] = center(g, ...e.b);
    const x = (x0 + x1) / 2;
    const y = (y0 + y1) / 2;
    const s = Math.max(5, g.size * 0.22);
    ctx.save();
    ctx.globalAlpha = e.gate.cleared ? 0.35 : 1;
    if (e.gate.kind === "quest") {
      glyph(ctx, GLYPHS.broken_bridge, x, y, Math.max(2, Math.round(g.size / 9)));
    } else {
      ctx.beginPath();
      ctx.moveTo(x, y - s);
      ctx.lineTo(x + s, y);
      ctx.lineTo(x, y + s);
      ctx.lineTo(x - s, y);
      ctx.closePath();
      ctx.fillStyle = TYPE_COLORS[e.gate.kind];
      ctx.fill();
      ctx.strokeStyle = "#3b2417";
      ctx.lineWidth = 2;
      ctx.stroke();
      if (s >= 7 && e.gate.level) {
        ctx.fillStyle = "#fffaf0";
        ctx.font = `bold ${Math.round(s * 1.05)}px "Atkinson Hyperlegible Mono", monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(e.gate.level), x, y + 1);
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

  // A word box centered on (x, y), kept inside the canvas.
  function drawLabel(ctx, g, x, y, label) {
    ctx.save();
    ctx.font = `bold ${Math.max(14, Math.round(g.size * 0.42))}px "Atkinson Hyperlegible Mono", monospace`;
    const w = ctx.measureText(label.word).width + 12;
    const h = Math.max(20, g.size * 0.6);
    const bx = Math.max(2, Math.min(g.width - w - 2, x - w / 2));
    const by = Math.max(2, Math.min(g.height - h - 2, y - h / 2));
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
    const g = geometry(canvas, map, opts, true);
    canvas.width = g.width;
    canvas.height = g.height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, g.width, g.height);
    const fog = opts.fog !== false;
    const byKey = new Map(map.hexes.map((h) => [key(h.q, h.r), h]));
    // Zoomed in on a hex: skip what's well off the canvas.
    if (opts.focus) {
      const [fq, fr] = opts.focus;
      map = { ...map, hexes: map.hexes.filter((h) => distance(h.q - fq, h.r - fr) <= opts.view + 1) };
    }

    if (opts.paper) drawPaper(ctx, g);
    // Where land is that you haven't found yet: light gray.
    if (opts.shape) {
      (map.shape || []).forEach(([q, r]) => {
        if (byKey.has(key(q, r))) return;
        const [x, y] = center(g, q, r);
        hexPath(ctx, g, x, y);
        ctx.fillStyle = "#e4dfd6";
        ctx.fill();
        ctx.strokeStyle = "rgba(59, 36, 23, 0.18)";
        ctx.lineWidth = 1;
        ctx.stroke();
      });
    }
    // Land, then region borders, then decorations, then walls on top.
    map.hexes.forEach((h) => {
      const [x, y] = center(g, h.q, h.r);
      hexPath(ctx, g, x, y);
      ctx.fillStyle = (opts.fill && opts.fill[key(h.q, h.r)]) || BIOME_COLORS[h.biome] || "#d8c7a0";
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
      if (!opts.bare || h.special) decorate(ctx, g, h, x, y, opts.simple);
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
      if (e.gate) drawGate(ctx, g, e);
    });
    // Glimpsed hexes: hazy until visited.
    if (fog) {
      map.hexes.forEach((h) => {
        if (h.visited) return;
        const [x, y] = center(g, h.q, h.r);
        hexPath(ctx, g, x, y);
        ctx.fillStyle = "rgba(251, 241, 220, 0.4)";
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
    // Highlights: places the journal points at.
    (opts.highlight || []).forEach(([q, r]) => {
      const [x, y] = center(g, q, r);
      hexPath(ctx, g, x, y, 2);
      ctx.strokeStyle = "#e8b33e";
      ctx.lineWidth = Math.max(3, g.size * 0.18);
      ctx.stroke();
    });
    // Marks: places an elder told you about (a star, even in the fog).
    [...(opts.marks || []), ...(map.marks || [])].forEach(([q, r]) => {
      const [x, y] = center(g, q, r);
      glyph(ctx, GLYPHS.lost, x, y - g.size * 0.35, Math.max(2, Math.round(g.size / 8)));
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
    if (opts.legend) drawLegend(ctx, g, map, opts.legend);
    Object.entries(opts.labels || {}).forEach(([k, label]) => {
      const [q, r] = k.split(",").map(Number);
      const [x, y] = center(g, q, r);
      drawLabel(ctx, g, x, y + g.size * 0.48, label);
    });
  }


  // --- small maps ---------------------------------------------------------------

  const TILE_FILL = {
    dark: "#3b3448", flames: "#d9a066", gap: "#5c4430", old_gate: "#b8ae9c", guardian: "#b8ae9c", broken_bridge: "#6fa8d6",
    path: "#dcc08e", sand: "#ecd9a0", plaza: "#d6c6a6", water: "#6fa8d6", bridge: "#6fa8d6", ocean: "#2c5f9a",
    ford: "#9fd0e0", cliff: "#8a6446", building: "#d6c6a6", temple: "#e8dcc0", stone: "#e8dcc0",
    court: "#e8dcc0", colonnade: "#b5a98f",
  };
  const TREE_GLYPH = {
    deepwood: "pine", ridge: "pine", storm_peaks: "pine", ember_peaks: "pine", orchard: "apple",
    mushroom_grove: "shroom", crystal_hollow: "crystal",
  };

  const WALKABLE = new Set(["grass", "flowers", "path", "sand", "plaza", "court", "bridge", "ford", "building", "campfire", "camp", "temple", "stone"]);
  const GATES = new Set(["dark", "flames", "gap", "old_gate", "guardian", "broken_bridge"]);
  const passable = (kind) => WALKABLE.has(kind) || GATES.has(kind);

  // Darken by amount (0..1), then make it a little richer: the small map's
  // colors are the big map's, with more punch.
  function shade(hex, amount = 0) {
    const n = parseInt(hex.slice(1), 16);
    let [r, g, b] = [n >> 16, (n >> 8) & 255, n & 255].map((c) => (c / 255) * (1 - amount));
    const grey = (r + g + b) / 3;
    [r, g, b] = [r, g, b].map((c) => Math.max(0, Math.min(1, grey + (c - grey) * 1.25 - 0.03)));
    return `rgb(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)})`;
  }

  function tileGlyph(kind, biome) {
    switch (kind) {
      case "tree": return GLYPHS[TREE_GLYPH[biome] || "tree"];
      case "bush": return GLYPHS.bush;
      case "rock": return GLYPHS.rock;
      case "cliff": return GLYPHS.mount;
      case "water": return GLYPHS.wave;
      case "ocean": return GLYPHS.swell;
      case "bridge": return GLYPHS.planks;
      case "ford": return GLYPHS.stones;
      case "flowers": return GLYPHS.flower;
      case "building": return null; // drawn by its role
      case "campfire": return GLYPHS.logfire;
      case "camp": return SPECIALS.camp;
      case "temple": return SPECIALS.temple;
      case "stone": return SPECIALS.final;
      case "dark": case "flames": case "gap": case "old_gate": case "guardian": case "broken_bridge":
        return GLYPHS[kind];
      default: return null;
    }
  }

  // Watery biomes are blue on the big map; up close their land is green.
  const LAND_COLORS = { lakeshore: "#a8cf8c", isles: "#b9d68e", brookside: "#a9d4b4" };

  // The great halls: mosaic paving, colonnades, relic pillars (lit once
  // their relic is home), the temples' features, and the magic at their
  // hearts (it moves: drawLocal's opts.time, in ms).
  const HALL_GLYPHS = {
    brazier: ["o.y.o", ".omo.", "..n..", ".nnn.", "sssss"],
    fountain: ["..B..", ".BbB.", "B.b.B", "sssss", ".sss."],
    topiary: [".GgG.", "GgGgG", ".GgG.", "..n..", ".sss."],
    crystal: ["..P..", ".PpP.", ".PpP.", "PpPpP", ".sss."],
    coil: [".yyy.", "..s..", ".sys.", "..s..", ".sss."],
  };
  const FEATURE = { ember: "brazier", splash: "fountain", leaf: "topiary", dream: "crystal", shock: "coil" };
  const HALL_GOLD = "#e8b33e";
  const isHall = (kind) => kind === "court" || kind === "colonnade" || kind.startsWith("pillar_") || kind.startsWith("feature_");
  const accentOf = (t) => (t.accent && t.accent !== "camp" ? TYPE_COLORS[t.accent] : HALL_GOLD);
  let hallTime = 0; // set by drawLocal

  function rgba(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
  }

  // Mosaic paving: an inlaid border and one of four patterns, picked per tile.
  function drawCourt(ctx, g, t, x, y) {
    const s = g.size;
    const accent = accentOf(t);
    ctx.save();
    hexPath(ctx, g, x, y, s * 0.16);
    ctx.strokeStyle = "rgba(139, 110, 70, 0.35)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.strokeStyle = rgba(accent, 0.55);
    ctx.fillStyle = rgba(accent, 0.22);
    ctx.lineWidth = Math.max(1.5, s * 0.06);
    const k = Math.floor(hashRand(t.q * 7, t.r * 13)() * 4);
    ctx.beginPath();
    if (k === 0) {
      // a diamond
      ctx.moveTo(x, y - s * 0.38);
      ctx.lineTo(x + s * 0.3, y);
      ctx.lineTo(x, y + s * 0.38);
      ctx.lineTo(x - s * 0.3, y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    } else if (k === 1) {
      // rings
      ctx.arc(x, y, s * 0.32, 0, 7);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(x, y, s * 0.12, 0, 7);
      ctx.fill();
      ctx.stroke();
    } else if (k === 2) {
      // four petals
      for (let i = 0; i < 4; i++) {
        const a = (Math.PI / 2) * i + Math.PI / 4;
        ctx.beginPath();
        ctx.ellipse(x + Math.cos(a) * s * 0.17, y + Math.sin(a) * s * 0.17, s * 0.15, s * 0.08, a, 0, 7);
        ctx.fill();
        ctx.stroke();
      }
    } else {
      // a six-point star
      for (let i = 0; i < 12; i++) {
        const a = (Math.PI / 6) * i - Math.PI / 2;
        const r = i % 2 ? s * 0.15 : s * 0.36;
        i ? ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r) : ctx.moveTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }
    ctx.restore();
  }

  // A colonnade: three slender columns under a lintel, a banner in the hall's color.
  function drawColonnade(ctx, g, t, x, y) {
    const s = g.size;
    ctx.save();
    // shadow behind the columns
    ctx.fillStyle = "rgba(59, 36, 23, 0.25)";
    ctx.fillRect(x - s * 0.62, y - s * 0.38, s * 1.24, s * 0.8);
    const stone = "#efe6d2";
    const shade_ = "#b5a98f";
    [-0.42, 0, 0.42].forEach((dx) => {
      const cx = x + dx * s;
      ctx.fillStyle = stone;
      ctx.fillRect(cx - s * 0.08, y - s * 0.4, s * 0.16, s * 0.76); // shaft
      ctx.fillStyle = shade_;
      ctx.fillRect(cx + s * 0.03, y - s * 0.4, s * 0.05, s * 0.76); // its shaded side
      ctx.fillStyle = stone;
      ctx.fillRect(cx - s * 0.13, y + s * 0.32, s * 0.26, s * 0.1); // base
      ctx.fillRect(cx - s * 0.13, y - s * 0.46, s * 0.26, s * 0.08); // capital
    });
    // the lintel
    ctx.fillStyle = stone;
    ctx.fillRect(x - s * 0.66, y - s * 0.58, s * 1.32, s * 0.14);
    ctx.strokeStyle = "#8b7a5c";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(x - s * 0.66, y - s * 0.58, s * 1.32, s * 0.14);
    // a little banner
    ctx.fillStyle = accentOf(t);
    ctx.beginPath();
    ctx.moveTo(x - s * 0.1, y - s * 0.44);
    ctx.lineTo(x + s * 0.1, y - s * 0.44);
    ctx.lineTo(x + s * 0.1, y - s * 0.12);
    ctx.lineTo(x, y - s * 0.2);
    ctx.lineTo(x - s * 0.1, y - s * 0.12);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  // Twinkling sparkles round a point: n of them, `spread` out, moving with time.
  function sparkles(ctx, x, y, n, spread, color, seed) {
    const r = hashRand(seed, n);
    for (let i = 0; i < n; i++) {
      const a = r() * Math.PI * 2 + hallTime / (1400 + r() * 1600);
      const d = spread * (0.4 + r() * 0.6);
      const twinkle = 0.5 + 0.5 * Math.sin(hallTime / 220 + r() * 10);
      const size = 1.5 + twinkle * 2.5;
      ctx.fillStyle = rgba(color, 0.4 + 0.6 * twinkle);
      ctx.fillRect(x + Math.cos(a) * d - size / 2, y + Math.sin(a) * d - size / 2, size, size);
      ctx.fillStyle = `rgba(255, 250, 240, ${twinkle})`;
      ctx.fillRect(x + Math.cos(a) * d - 1, y + Math.sin(a) * d - 1, 2, 2);
    }
  }

  // The glow at a temple's or the Heartstone's heart: a pulse, rising
  // motes, and sparkles circling.
  function drawHeart(ctx, g, t, x, y) {
    const s = g.size;
    const color = accentOf(t);
    const pulse = 0.5 + 0.5 * Math.sin(hallTime / 600);
    ctx.save();
    const glow = ctx.createRadialGradient(x, y, 0, x, y, s * (1.3 + pulse * 0.4));
    glow.addColorStop(0, rgba("#fffaf0", 0.55 + pulse * 0.3));
    glow.addColorStop(0.35, rgba(color, 0.45 + pulse * 0.25));
    glow.addColorStop(1, rgba(color, 0));
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, s * (1.3 + pulse * 0.4), 0, 7);
    ctx.fill();
    // motes drifting up
    const r = hashRand(t.q + 3, t.r + 5);
    for (let i = 0; i < 7; i++) {
      const speed = 1800 + r() * 1400;
      const phase = ((hallTime + r() * speed) % speed) / speed;
      const mx = x + (r() - 0.5) * s * 1.1 + Math.sin(hallTime / 500 + i) * s * 0.08;
      const my = y + s * 0.4 - phase * s * 1.4;
      ctx.fillStyle = rgba(i % 2 ? color : "#fffaf0", 1 - phase);
      ctx.fillRect(mx - 1.5, my - 1.5, 3, 3);
    }
    sparkles(ctx, x, y - s * 0.1, 8, s * 0.95, color, t.q * 31 + t.r);
    ctx.restore();
  }

  function drawHall(ctx, g, t, x, y) {
    const px = Math.max(2, Math.round(g.size / 6));
    if (t.kind === "court") {
      drawCourt(ctx, g, t, x, y);
    } else if (t.kind === "colonnade") {
      drawColonnade(ctx, g, t, x, y);
    } else if (t.kind.startsWith("feature_")) {
      drawCourt(ctx, g, t, x, y);
      glyph(ctx, HALL_GLYPHS[FEATURE[t.kind.slice(8)]], x, y, px);
      sparkles(ctx, x, y - g.size * 0.2, 3, g.size * 0.45, accentOf(t), t.q * 17 + t.r);
    } else if (t.kind.startsWith("pillar_")) {
      const color = TYPE_COLORS[t.kind.slice(7)];
      drawCourt(ctx, g, { ...t, accent: t.kind.slice(7) }, x, y);
      const top = y - g.size * 0.5;
      if (t.lit) {
        // its relic is home: a bright, pulsing glow in its color
        const pulse = 0.5 + 0.5 * Math.sin(hallTime / 500 + t.q);
        const glow = ctx.createRadialGradient(x, top, 0, x, top, g.size * (1 + pulse * 0.3));
        glow.addColorStop(0, "#fffaf0");
        glow.addColorStop(0.25, color);
        glow.addColorStop(1, "rgba(255, 255, 255, 0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(x, top, g.size * (1 + pulse * 0.3), 0, 7);
        ctx.fill();
      }
      // the pillar: a fluted column
      const s = g.size;
      ctx.fillStyle = "#efe6d2";
      ctx.fillRect(x - s * 0.13, top + s * 0.15, s * 0.26, s * 0.75);
      ctx.fillStyle = "#b5a98f";
      ctx.fillRect(x + s * 0.04, top + s * 0.15, s * 0.07, s * 0.75);
      ctx.fillStyle = "#efe6d2";
      ctx.fillRect(x - s * 0.22, top + s * 0.85, s * 0.44, s * 0.12);
      ctx.fillRect(x - s * 0.2, top + s * 0.08, s * 0.4, s * 0.1);
      // the orb on top
      ctx.fillStyle = t.lit ? "#fffaf0" : color;
      ctx.strokeStyle = "#3b2417";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, top, s * 0.22, 0, 7);
      ctx.fill();
      ctx.stroke();
      if (t.lit) sparkles(ctx, x, top, 9, s * 0.9, color, t.q * 11 + t.r);
    }
  }

  function drawTile(ctx, g, t, biome, x, y) {
    const base = LAND_COLORS[biome] || BIOME_COLORS[biome] || "#d8c7a0";
    hexPath(ctx, g, x, y);
    const dark = { tree: 0.3, bush: 0.12, rock: 0.12 }[t.kind];
    // Water (and the bridges and fords on it) is land here: the river is
    // painted over it as one channel (connect()).
    const hall = isHall(t.kind);
    const fill = WATERY.has(t.kind) ? base : hall ? TILE_FILL.court : TILE_FILL[t.kind] || base;
    ctx.fillStyle = shade(fill, TILE_FILL[t.kind] && !WATERY.has(t.kind) ? 0 : dark || 0);
    ctx.fill();
    ctx.strokeStyle = "rgba(59, 36, 23, 0.15)";
    ctx.lineWidth = 1;
    ctx.stroke();
    const px = Math.max(2, Math.round(g.size / 8));
    const big = ["camp", "temple", "stone"].includes(t.kind);
    const blocker = ["tree", "bush", "rock", "cliff"].includes(t.kind);
    const rows = t.linked || WATERY.has(t.kind) ? null : tileGlyph(t.kind, biome);
    if (rows) glyph(ctx, rows, x, y, big ? Math.max(2, Math.round(g.size / (t.kind === "camp" ? 10 : 7))) : blocker ? Math.max(2, Math.round(g.size / 5.5)) : px);
    else if (t.kind === "grass" && hashRand(t.q, t.r)() < 0.3) glyph(ctx, GLYPHS.tuft, x, y, px);
    if (hall) drawHall(ctx, g, t, x, y);
    if ((t.kind === "temple" || t.kind === "stone") && t.accent) {
      drawCourt(ctx, g, t, x, y);
      drawHeart(ctx, g, t, x, y);
      if (rows) glyph(ctx, rows, x, y, Math.max(2, Math.round(g.size / 7)));
    }
    const role = t.role && t.role.startsWith("quest:") ? "elder" : t.role; // quest-givers: a house with a star
    if (role && GLYPHS[role]) glyph(ctx, GLYPHS[role], x, y, px + 1);
    if (t.poi) glyph(ctx, GLYPHS[t.poi], x, y, px);
    else if (t.nook && !t.doors && GLYPHS[t.nook]) glyph(ctx, GLYPHS[t.nook], x, y, px);
    if (t.exit !== undefined) glyph(ctx, GLYPHS.sign, x + g.size * 0.35, y - g.size * 0.3, Math.max(2, px - 1));
  }

  // view: {radius, tiles: [{q, r, kind, biome?, big?, faded?, poi?, role?,
  // exit?, nook?, doors?, accent?, lit?}], spot, campfire, biome}. opts.time
  // (ms) moves the magic in the great halls. opts: size, focus (center on this hex,
  // showing view.radius around it, the farthest ring faded into the
  // distance; else the map is centered on (0, 0)), camera (see geometry), fog
  // (show the campfire's smoke before it's seen), labels ({"q,r": {word,
  // typed}}, drawn out past their hex, away from you), selected, edge (the
  // dashed outline of one big hex at (0, 0)).
  //
  // Hexes not seen yet are faint dotted outlines. A solid dark line runs
  // along every side you can't walk across, so blocked ways read at a
  // glance; a faint dash marks where one big hex meets the next.
  function drawLocal(canvas, view, opts = {}) {
    hallTime = opts.time || 0;
    const focus = opts.focus;
    const g = geometry(canvas, view, focus ? { ...opts, view: view.radius } : { ...opts, radius: view.radius });
    canvas.width = g.width;
    canvas.height = g.height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    const fog = opts.fog !== false;
    const byKey = new Map(view.tiles.map((t) => [key(t.q, t.r), t]));
    const [oq, or] = focus || [0, 0];

    // Where hexes could be.
    ctx.save();
    ctx.setLineDash([2, 4]);
    ctx.strokeStyle = "rgba(59, 36, 23, 0.22)";
    ctx.lineWidth = 1;
    const reach = view.radius + (focus ? 1 : 0);
    for (let dq = -reach; dq <= reach; dq++) {
      for (let dr = -reach; dr <= reach; dr++) {
        if (distance(dq, dr) > reach || byKey.has(key(oq + dq, or + dr))) continue;
        const [x, y] = center(g, oq + dq, or + dr);
        hexPath(ctx, g, x, y);
        ctx.stroke();
      }
    }
    ctx.restore();

    // Far hexes fade into the distance; the lab's ring next door is faded.
    const alpha = (t) => (focus && distance(t.q - oq, t.r - or) >= view.radius ? 0.5 : t.faded ? 0.7 : 1);
    // Blockers that touch their own kind get their glyphs from connect().
    const joins = (t) => RANGES[t.kind] && DIRS.some(([dq, dr]) => byKey.get(key(t.q + dq, t.r + dr))?.kind === t.kind);
    view.tiles.forEach((t) => {
      const [x, y] = center(g, t.q, t.r);
      ctx.save();
      ctx.globalAlpha = alpha(t);
      drawTile(ctx, g, joins(t) ? { ...t, linked: true } : t, t.biome || view.biome, x, y);
      ctx.restore();
    });
    connect(ctx, g, view.tiles, byKey, alpha);
    drawNooks(ctx, g, view.tiles, alpha);
    // The campfire's smoke shows from anywhere in its big hex.
    if (fog && view.campfire && !byKey.has(key(...view.campfire))) {
      const [x, y] = center(g, ...view.campfire);
      glyph(ctx, GLYPHS.smoke, x, y - g.size * 0.3, Math.max(2, Math.round(g.size / 7)));
      glyph(ctx, GLYPHS.flame, x, y + g.size * 0.25, Math.max(2, Math.round(g.size / 10)));
    }
    // Where one big hex meets the next.
    ctx.save();
    ctx.strokeStyle = "rgba(59, 36, 23, 0.4)";
    ctx.lineWidth = 2;
    ctx.setLineDash([3, 5]);
    ctx.beginPath();
    view.tiles.forEach((t) => {
      if (!t.big) return;
      const [x, y] = center(g, t.q, t.r);
      DIRS.forEach(([dq, dr], d) => {
        const n = byKey.get(key(t.q + dq, t.r + dr));
        if (!n || !n.big || n.big === t.big || d > 2) return;
        const [p0, p1] = side(g, x, y, d);
        ctx.moveTo(p0[0], p0[1]);
        ctx.lineTo(p1[0], p1[1]);
      });
    });
    ctx.stroke();
    ctx.restore();
    if (opts.edge) {
      ctx.save();
      ctx.strokeStyle = "rgba(59, 36, 23, 0.35)";
      ctx.setLineDash([4, 4]);
      hexPathBig(ctx, g, opts.edge);
      ctx.stroke();
      ctx.restore();
    }
    // Can't-walk lines: from a walkable hex to a blocked one you've seen.
    ctx.save();
    ctx.strokeStyle = "#3b2417";
    ctx.lineWidth = Math.max(3, g.size * 0.11);
    ctx.lineCap = "round";
    ctx.beginPath();
    const banks = []; // beside water: a lighter bank line
    view.tiles.forEach((t) => {
      if (!passable(t.kind)) return;
      const [x, y] = center(g, t.q, t.r);
      DIRS.forEach(([dq, dr], d) => {
        const n = byKey.get(key(t.q + dq, t.r + dr));
        if (!n || passable(n.kind) || (n.doors || []).includes((d + 3) % 6)) return;
        const [p0, p1] = side(g, x, y, d);
        if (n.kind === "water") {
          banks.push([p0, p1]);
          return;
        }
        ctx.moveTo(p0[0], p0[1]);
        ctx.lineTo(p1[0], p1[1]);
      });
    });
    ctx.stroke();
    ctx.strokeStyle = "rgba(38, 74, 104, 0.75)";
    ctx.lineWidth = Math.max(2, g.size * 0.08);
    ctx.beginPath();
    banks.forEach(([p0, p1]) => {
      ctx.moveTo(p0[0], p0[1]);
      ctx.lineTo(p1[0], p1[1]);
    });
    ctx.stroke();
    ctx.restore();
    if (opts.selected) {
      const [x, y] = center(g, ...opts.selected);
      hexPath(ctx, g, x, y, 2);
      ctx.strokeStyle = "#e8b33e";
      ctx.lineWidth = 3;
      ctx.stroke();
    }
    const labels = Object.entries(opts.labels || {});
    // Where each word's step goes: a soft gold ring.
    labels.forEach(([k, label]) => {
      const [x, y] = center(g, ...k.split(",").map(Number));
      hexPath(ctx, g, x, y, 3);
      ctx.strokeStyle = label.typed ? "#e8b33e" : "rgba(232, 179, 62, 0.55)";
      ctx.lineWidth = label.typed ? 3 : 2;
      ctx.stroke();
    });
    let sx = g.cx;
    let sy = g.cy;
    if (view.spot) {
      [sx, sy] = center(g, ...view.spot);
      ctx.fillStyle = "#fffaf0";
      ctx.beginPath();
      ctx.arc(sx, sy, g.size * 0.32, 0, 7);
      ctx.fill();
      ctx.strokeStyle = "#3b2417";
      ctx.lineWidth = 2;
      ctx.stroke();
      glyph(ctx, SPECIALS.paw, sx, sy, Math.max(2, Math.round(g.size / 12)));
    }
    // Words sit out past their hex, so the hexes around you stay in view.
    labels.forEach(([k, label]) => {
      const [x, y] = center(g, ...k.split(",").map(Number));
      drawLabel(ctx, g, sx + (x - sx) * 1.8, sy + (y - sy) * 1.8, label);
    });
  }

  const WATERY = new Set(["water", "bridge", "ford"]);
  // Blockers drawn as ranges: their glyph, and another between neighbors.
  const RANGES = { cliff: "mount", tree: "tree", bush: "bush", rock: "rock" };

  // Rivers and lakes: one channel of water through the water hexes (a pool
  // at each, a band to each watery neighbor, gaps between three filled),
  // with a light current along narrow stretches. Bridges and fords sit on
  // it. Ranges: mountains, woods, rocks and bushes get their glyph on each
  // hex and one more between neighbors, so they read as one range.
  function connect(ctx, g, tiles, byKey, alpha) {
    const at = (t, dq, dr) => byKey.get(key(t.q + dq, t.r + dr));
    const water = tiles.filter((t) => WATERY.has(t.kind));
    const wet = (t) => t && WATERY.has(t.kind);
    const degree = (t) => DIRS.filter(([dq, dr]) => wet(at(t, dq, dr))).length;
    ctx.save();
    ctx.fillStyle = ctx.strokeStyle = shade(TILE_FILL.water);
    ctx.lineCap = "round";
    ctx.lineWidth = g.size;
    water.forEach((t) => {
      ctx.globalAlpha = alpha(t);
      const [x, y] = center(g, t.q, t.r);
      ctx.beginPath();
      ctx.arc(x, y, g.size * 0.8, 0, 7);
      ctx.fill();
      DIRS.forEach(([dq, dr], d) => {
        const n = at(t, dq, dr);
        if (!wet(n)) return;
        const [x1, y1] = center(g, n.q, n.r);
        if (d < 3) {
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x1, y1);
          ctx.stroke();
        }
        // a third watery hex beside both: fill the gap between the three
        const [eq, er] = DIRS[(d + 1) % 6];
        const m = at(t, eq, er);
        if (d > 1 || !wet(m)) return; // each triangle once: (t, E, NE) and (t, NE, NW)
        const [x2, y2] = center(g, m.q, m.r);
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.fill();
      });
    });
    // the current: a thin light thread down narrow water
    ctx.strokeStyle = "#cfeaf2";
    ctx.lineWidth = Math.max(1.5, g.size * 0.07);
    water.forEach((t) => {
      if (degree(t) > 2) return;
      ctx.globalAlpha = alpha(t) * 0.9;
      const [x, y] = center(g, t.q, t.r);
      DIRS.slice(0, 3).forEach(([dq, dr]) => {
        const n = at(t, dq, dr);
        if (!wet(n) || degree(n) > 2) return;
        const [x1, y1] = center(g, n.q, n.r);
        const bend = (hashRand(t.q + n.q, t.r + n.r)() - 0.5) * 0.5;
        const mx = (x + x1) / 2 - (y1 - y) * bend;
        const my = (y + y1) / 2 + (x1 - x) * bend;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.quadraticCurveTo(mx, my, x1, y1);
        ctx.stroke();
      });
    });
    ctx.restore();
    const px = Math.max(2, Math.round(g.size / 8));
    water.forEach((t) => {
      const [x, y] = center(g, t.q, t.r);
      ctx.save();
      ctx.globalAlpha = alpha(t);
      if (t.kind === "bridge") glyph(ctx, GLYPHS.planks, x, y, px);
      else if (t.kind === "ford") {
        // shallows: pale water you can wade, with stepping stones
        ctx.fillStyle = shade(TILE_FILL.ford);
        ctx.beginPath();
        ctx.arc(x, y, g.size * 0.62, 0, 7);
        ctx.fill();
        glyph(ctx, GLYPHS.stones, x, y, px);
      }
      else if (degree(t) > 2 && hashRand(t.q, t.r)() < 0.4) glyph(ctx, GLYPHS.wave, x, y, px);
      ctx.restore();
    });

    // ranges: a glyph between each pair of neighbors, then one on each hex
    const big = Math.max(2, Math.round(g.size / 5.5));
    const small = Math.max(2, Math.round(g.size / 7.5));
    tiles.forEach((t) => {
      const name = RANGES[t.kind];
      if (!name) return;
      const rows = t.kind === "tree" ? tileGlyph("tree", t.biome) : GLYPHS[name];
      const [x, y] = center(g, t.q, t.r);
      DIRS.slice(0, 3).forEach(([dq, dr]) => {
        const n = at(t, dq, dr);
        if (!n || n.kind !== t.kind) return;
        const [x1, y1] = center(g, n.q, n.r);
        ctx.save();
        ctx.globalAlpha = Math.min(alpha(t), alpha(n));
        glyph(ctx, rows, (x + x1) / 2, (y + y1) / 2, small);
        ctx.restore();
      });
    });
    tiles.forEach((t) => {
      const name = RANGES[t.kind];
      if (!name || !DIRS.some(([dq, dr]) => at(t, dq, dr)?.kind === t.kind)) return;
      const [x, y] = center(g, t.q, t.r);
      ctx.save();
      ctx.globalAlpha = alpha(t);
      glyph(ctx, t.kind === "tree" ? tileGlyph("tree", t.biome) : GLYPHS[name], x, y, big);
      ctx.restore();
    });
  }

  // Caves and tunnels: a dark mouth on the side of each door; glades: a
  // sunny clearing in the trees, open toward its door.
  function drawNooks(ctx, g, tiles, alpha) {
    tiles.forEach((t) => {
      if (!t.doors) return;
      const [x, y] = center(g, t.q, t.r);
      ctx.save();
      ctx.globalAlpha = alpha(t);
      if (t.nook === "glade") {
        const [dq, dr] = DIRS[t.doors[0]];
        const [x1, y1] = center(g, t.q + dq, t.r + dr);
        const [mx, my] = [x + (x1 - x) * 0.15, y + (y1 - y) * 0.15];
        ctx.fillStyle = shade("#cfe39a");
        ctx.strokeStyle = "rgba(47, 90, 34, 0.6)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(mx, my, g.size * 0.5, 0, 7);
        ctx.fill();
        ctx.stroke();
        glyph(ctx, GLYPHS.flower, mx, my, Math.max(2, Math.round(g.size / 9)));
      } else {
        // caves dark, grottos misty purple, mines framed in timber
        const look = { grotto: ["#4a2f6e", "#d6b8ee"], mine: ["#2a1a10", "#8b5a2b"] }[t.nook] || ["#2a1a10", "#b89a78"];
        t.doors.forEach((d) => {
          const [dq, dr] = DIRS[d];
          const [x1, y1] = center(g, t.q + dq, t.r + dr);
          const [mx, my] = [x + (x1 - x) * 0.28, y + (y1 - y) * 0.28];
          const w = g.size * 0.6;
          ctx.fillStyle = look[0];
          ctx.strokeStyle = look[1];
          ctx.lineWidth = Math.max(2, g.size * 0.07);
          ctx.beginPath();
          ctx.ellipse(mx, my + w * 0.15, w * 0.62, w * 0.55, 0, Math.PI, 0);
          ctx.lineTo(mx + w * 0.62, my + w * 0.45);
          ctx.lineTo(mx - w * 0.62, my + w * 0.45);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
          if (t.nook === "mine") {
            // a timber lintel and posts
            ctx.fillStyle = "#8b5a2b";
            ctx.fillRect(mx - w * 0.75, my - w * 0.45, w * 1.5, w * 0.18);
            ctx.fillRect(mx - w * 0.72, my - w * 0.4, w * 0.16, w * 0.85);
            ctx.fillRect(mx + w * 0.56, my - w * 0.4, w * 0.16, w * 0.85);
          }
        });
      }
      ctx.restore();
    });
  }

  // Outline of a radius-r hexagon of hexes (corner hexes' outer corners).
  function hexPathBig(ctx, g, r) {
    ctx.beginPath();
    DIRS.forEach(([dq, dr], d) => {
      const [x, y] = center(g, dq * r, dr * r);
      const a = (Math.PI / 180) * (-60 * d);
      const px = x + g.size * Math.cos(a) * 1.0;
      const py = y + g.size * Math.sin(a) * 1.0;
      d ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    });
    ctx.closePath();
  }

  function hexAtLocal(canvas, local, opts, x, y) {
    const g = geometry(canvas, local, { ...opts, radius: local.radius });
    return cubeRound(...toAxial((x - g.cx) / g.size, (y - g.cy) / g.size));
  }

  function hexAt(canvas, map, opts, x, y) {
    const g = geometry(canvas, map, opts, true);
    const k = g.size / BIG_CORNER;
    const [q, r] = toAxial(...turned([(x - g.cx) / k, (y - g.cy) / k], -g.turn));
    // small (q, r) -> big, through the inverse of the spans
    return cubeRound((SPAN_B[1] * q - SPAN_B[0] * r) / AREA, (-SPAN_A[1] * q + SPAN_A[0] * r) / AREA);
  }

  // Where a big hex's middle is on a big map's canvas.
  function pointAt(canvas, map, opts, q, r) {
    return center(geometry(canvas, map, opts, true), q, r);
  }

  const toAxial = (px, py) => [(SQRT3 / 3) * px - py / 3, (2 / 3) * py];

  function cubeRound(q, r) {
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

  // A legend sample in a w x h box at (ox, oy): a special place, you, a
  // quest mark, a wall kind, a trail, or a gate.
  function sampleAt(ctx, kind, ox, oy, w, h) {
    ctx.save();
    ctx.translate(ox, oy);
    const mid = [w / 2, h / 2];
    if (SPECIALS[kind]) {
      glyph(ctx, SPECIALS[kind], ...mid, 3);
    } else if (kind === "you") {
      ctx.fillStyle = "#fffaf0";
      ctx.beginPath();
      ctx.arc(...mid, w * 0.32, 0, 7);
      ctx.fill();
      ctx.strokeStyle = "#3b2417";
      ctx.lineWidth = 2;
      ctx.stroke();
      glyph(ctx, SPECIALS.paw, ...mid, 2);
    } else if (kind === "mark") {
      glyph(ctx, GLYPHS.lost, ...mid, 4);
    } else if (WALLS[kind]) {
      const style = WALLS[kind];
      ctx.strokeStyle = ctx.fillStyle = style.color;
      ctx.lineWidth = 5;
      ctx.lineCap = "round";
      if (kind === "thicket" || kind === "rocks") {
        for (let i = 0; i < 4; i++) {
          const x = 6 + i * ((w - 12) / 3);
          kind === "rocks" ? ctx.fillRect(x - 3, h / 2 - 3, 6, 6) : (ctx.beginPath(), ctx.arc(x, h / 2, 3.5, 0, 7), ctx.fill());
        }
      } else {
        ctx.beginPath();
        ctx.moveTo(4, h / 2);
        ctx.quadraticCurveTo(w / 2, kind === "river" ? h / 2 + 8 : h / 2, w - 4, h / 2);
        ctx.stroke();
      }
    } else if (kind === "trail") {
      ctx.strokeStyle = "rgba(92, 58, 26, 0.55)";
      ctx.lineWidth = 3;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(4, h / 2);
      ctx.lineTo(w - 4, h / 2);
      ctx.stroke();
    } else if (kind === "gate" || kind === "shortcut") {
      if (kind === "shortcut") glyph(ctx, GLYPHS.broken_bridge, ...mid, 4);
      else {
        const s = 10;
        ctx.beginPath();
        ctx.moveTo(w / 2, h / 2 - s);
        ctx.lineTo(w / 2 + s, h / 2);
        ctx.lineTo(w / 2, h / 2 + s);
        ctx.lineTo(w / 2 - s, h / 2);
        ctx.closePath();
        ctx.fillStyle = TYPE_COLORS.ember;
        ctx.fill();
        ctx.strokeStyle = "#3b2417";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // Old paper under the map: warm parchment, flecks and fibers, darker
  // toward the edges.
  function drawPaper(ctx, g) {
    const { width: w, height: h } = g;
    ctx.save();
    ctx.fillStyle = "#efe0bf";
    ctx.fillRect(0, 0, w, h);
    const rand = hashRand(17, 29);
    for (let i = 0; i < (w * h) / 180; i++) {
      ctx.fillStyle = rand() < 0.5 ? "rgba(139, 90, 43, 0.10)" : "rgba(255, 250, 235, 0.35)";
      ctx.fillRect(Math.floor(rand() * w), Math.floor(rand() * h), 2, 2);
    }
    ctx.strokeStyle = "rgba(139, 90, 43, 0.07)";
    ctx.lineWidth = 1;
    for (let i = 0; i < (w * h) / 6000; i++) {
      const x = rand() * w;
      const y = rand() * h;
      const a = rand() * Math.PI;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + Math.cos(a) * 18, y + Math.sin(a) * 18);
      ctx.stroke();
    }
    const edge = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.35, w / 2, h / 2, Math.max(w, h) * 0.75);
    edge.addColorStop(0, "rgba(120, 72, 30, 0)");
    edge.addColorStop(1, "rgba(120, 72, 30, 0.22)");
    ctx.fillStyle = edge;
    ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }

  // The legend, like on a paper map: to the right of the farthest-right
  // land, down in the bottom corner. items: [[kind, label], ...].
  const LEGEND_WIDTH = 210;
  function drawLegend(ctx, g, map, items) {
    const points = (map.shape || map.hexes.map((h) => [h.q, h.r])).map(([q, r]) => center(g, q, r));
    const row = 27;
    const left = Math.max(...points.map((p) => p[0])) + g.size * 0.95 + 14;
    const bottom = Math.max(...points.map((p) => p[1])) + g.size;
    const top = Math.max(8, bottom - (items.length * row + 40));
    ctx.save();
    ctx.fillStyle = "rgba(250, 240, 214, 0.95)";
    ctx.strokeStyle = "#3b2417";
    ctx.lineWidth = 3;
    ctx.fillRect(left, top, LEGEND_WIDTH - 24, items.length * row + 40);
    ctx.strokeRect(left, top, LEGEND_WIDTH - 24, items.length * row + 40);
    ctx.fillStyle = "#3b2417";
    ctx.font = `bold 16px "Atkinson Hyperlegible Mono", monospace`;
    ctx.textBaseline = "middle";
    ctx.fillText("Legend", left + 12, top + 18);
    ctx.font = `13px "Atkinson Hyperlegible Mono", monospace`;
    items.forEach(([kind, label], i) => {
      const y = top + 36 + i * row;
      sampleAt(ctx, kind, left + 8, y, 40, row - 4);
      ctx.fillStyle = "#3b2417";
      ctx.fillText(label, left + 54, y + (row - 4) / 2);
    });
    ctx.restore();
  }

  return { draw, drawLocal, hexAt, hexAtLocal, pointAt, TYPE_COLORS, BIOME_COLORS, DIRS, key, span };
})();
