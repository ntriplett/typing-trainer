// Paints a place from the facts in app/wanderpaw/scene.py. No stored pictures:
// a kit of parts on the habitats' 160x90 grid, laid out by rules, with the
// scene's seed picking exactly where, so a small hex looks the same each time.
//
//   const s = WanderScene.build(spec, px, { night });
//   s.background  a canvas of everything that doesn't move
//   s.area        where pets can go, for PetMotion.create (water, blocks, props)
//   s.avatar      {x, y}: where you stand (feet)
//   WanderScene.animate(s, ctx, tick)   the fire and the smoke
//   WanderScene.shade(s, ctx)           night's dark, over the pets too
//
// Needs habitats.js (the grid and its painter).

const WanderScene = (() => {
  const W = HABITAT_W;
  const H = HABITAT_H;
  const HORIZON = 34; // where the far land meets the near land
  const GROUND_TOP = 44; // the near land starts
  const FEET_TOP = 56; // pets stay in front of the middle distance
  const FEET_BOTTOM = 88;
  const MID_RINGS = 2; // scene.py's: nearer than this, it's drawn as itself
  const NEAR_IS_MID = new Set(["cave", "shrine", "house"]);
  const HALL_NEAR = 4; // a hall's other tiles, this close, are the hall you're in
  const FAR_WATER = 0.06; // of the horizon: less and it doesn't show
  const FAR_SPILL = 14; // far hills run this far past their land, sloping to the ground
  const NEAR_SPILL = 8;
  const ROCKY_AT = 7; // land this much raised by cliffs is bare rock
  const SHORE_FADE = 22; // the land flattens toward the water over this far
  const WATER = "#4a8ab0";
  const WATER_LIGHT = "#8cc4dc";
  const TENT_WHITE = "#fbf8ee";
  const TENT_SHADE = "#ddd6c4";
  const TENT_EDGE = "#6e5a48";
  const STONE = ["#9a948a", "#b8b2a6", "#7a7468"];

  // The land's colors: what tells you where you are at a glance.
  const REGIONS = {
    camp: { sky: "#a8d5e2", skyLow: "#d2ecef", far: "#9cc46a", near: "#8fb85a", ground: "#7fa346", light: "#94c25c", dark: "#6d9440", roof: "#b5533c", cloth: "#d8a24a" },
    leaf: { sky: "#b0dcc8", skyLow: "#def0d8", far: "#6f9e6a", near: "#5a8f52", ground: "#5f8f3e", light: "#78a94f", dark: "#4b7732", roof: "#8a5a34", cloth: "#6aa84a" },
    splash: { sky: "#92cfec", skyLow: "#d2eef6", far: "#94bc8e", near: "#79ac82", ground: "#78b08c", light: "#94caa6", dark: "#5c9476", roof: "#3f7fa8", cloth: "#4aa0c8" },
    ember: { sky: "#ee9a68", skyLow: "#f9d9a0", far: "#b8604a", near: "#a04e3c", ground: "#b86e48", light: "#cf8d5e", dark: "#96553a", roof: "#7e2f24", cloth: "#d8582e" },
    shock: { sky: "#c4c4a0", skyLow: "#f4e8a4", far: "#c8a84e", near: "#b4923c", ground: "#c4a858", light: "#dac272", dark: "#a08a40", roof: "#5a6a8a", cloth: "#e8c02e" },
    dream: { sky: "#8a78c4", skyLow: "#d6b8e6", far: "#8a6cb0", near: "#76589c", ground: "#7e6aa8", light: "#9c86c2", dark: "#64528c", roof: "#4a3a7e", cloth: "#b47ae0" },
  };

  // The land inside the region: its trees, its rocks, its weather, what's underfoot.
  // decor: [part, how many]
  const BIOMES = {
    fields: { tree: "round", decor: [["tuft", 14], ["flower", 6], ["wheat", 5]], weather: "clouds" },
    orchard: { tree: "apple", decor: [["tuft", 10], ["apple", 7], ["flower", 3]], weather: "clouds" },
    meadow: { tree: "round", decor: [["flower", 18], ["tuft", 10]], weather: "clouds" },
    woods: { tree: "round", decor: [["tuft", 8], ["fern", 6], ["mushroom", 2]], weather: "clouds", backTrees: 0.5 },
    fern_hollow: { tree: "pine", decor: [["fern", 16], ["mushroom", 3]], weather: "haze", backTrees: 0.7, ground: "#4f7e38" },
    deepwood: { tree: "darkpine", decor: [["fern", 10], ["mushroom", 5], ["pebble", 3]], weather: "haze", backTrees: 1, ground: "#3f6a30", light: "#578640", dark: "#325626", skyTint: "#7fae98" },
    brookside: { tree: "round", decor: [["reed", 7], ["pebble", 9], ["flower", 5]], weather: "clouds" },
    marsh: { tree: "dead", decor: [["reed", 16], ["tuft", 6]], weather: "haze", ground: "#6a9a7a", dark: "#4e7c64" },
    lakeshore: { tree: "round", sandy: true, decor: [["pebble", 8], ["reed", 6], ["sandpatch", 4]], weather: "clouds" },
    isles: { tree: "palm", sandy: true, decor: [["sandpatch", 9], ["shell", 5], ["pebble", 3]], weather: "clouds", ground: "#d8c888", light: "#e8dca0", dark: "#c0ae70" },
    heath: { tree: "shrub", decor: [["rock", 8], ["pebble", 12], ["shrub", 7]], weather: "clouds" },
    red_rocks: { tree: "dead", decor: [["redrock", 9], ["pebble", 12]], weather: "clear", rock: ["#a04a34", "#c46a4a", "#7e3626"] },
    hot_springs: { tree: "dead", decor: [["vent", 4], ["pebble", 10], ["redrock", 3]], weather: "haze", water: ["#5ec2c0", "#b8ecdc"] },
    ember_peaks: { tree: "dead", decor: [["crack", 5], ["ashrock", 7], ["pebble", 8]], weather: "smoky", ground: "#6e4438", light: "#8a5a48", dark: "#54322a", rock: ["#4e4040", "#6e5a58", "#382e2e"] },
    windy_hills: { tree: "shrub", decor: [["windgrass", 16], ["rock", 3]], weather: "clouds" },
    mesa: { tree: "shrub", decor: [["pebble", 12], ["rock", 3], ["windgrass", 6]], weather: "clear", rock: ["#b08a4a", "#cca868", "#8a6c38"] },
    ridge: { tree: "dead", decor: [["rock", 8], ["pebble", 12]], weather: "clouds", rock: ["#8a8a8e", "#aaaab0", "#68686e"] },
    storm_peaks: { tree: "dead", decor: [["rock", 8], ["pebble", 8], ["spark", 4]], weather: "storm", ground: "#8c8452", dark: "#6e683e", light: "#a29a64", rock: ["#6a6a76", "#8a8a96", "#4e4e5a"] },
    glade: { tree: "round", treeLeaf: "#7a7ac4", decor: [["flower", 12], ["sparkle", 6], ["tuft", 8]], weather: "clouds" },
    mushroom_grove: { tree: "mushroomtree", decor: [["mushroom", 12], ["sparkle", 4]], weather: "haze", backTrees: 0.5 },
    mist_vale: { tree: "dead", decor: [["rock", 5], ["tuft", 8], ["sparkle", 3]], weather: "mist" },
    crystal_hollow: { tree: "crystal", decor: [["crystal", 9], ["pebble", 6], ["sparkle", 6]], weather: "haze", rock: ["#6a5a8e", "#8a7ab0", "#4e4270"] },
  };
  const NO_BIOME = {};

  function rng(seed) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const between = (rand, a, b) => a + rand() * (b - a);
  const chance = (rand, p) => rand() < p;
  const xAt = (at) => W / 2 + at * (W / 2 - 4);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const disc = (r, cx, cy, rx, ry, c) => drawHabitatDisc(r, Math.round(cx), Math.round(cy), rx, ry, c);

  // A land's colors: its region's, with its biome's changes.
  function colors(region, biome) {
    const look = BIOMES[biome] || NO_BIOME;
    return { ...REGIONS[region] || REGIONS.camp, ...look, rock: look.rock || STONE, water: look.water || [WATER, WATER_LIGHT] };
  }

  // --- the rules: where everything goes, before anything's drawn ---------------------

  // All the water in the picture is one body, coming in from one side (where most of
  // it really is): out to the horizon, with the far land flattening down behind it,
  // and if you're beside it, on down past the bottom of the picture, so you're
  // on its shore. reach(y): how far in from that side it comes at height y.
  function shoreOf(spec, rand, crossing) {
    const near = spec.water && !crossing ? spec.water : null;
    const share = spec.far.reduce((sum, s) => sum + s.water + s.ocean, 0) / spec.far.length;
    const marks = spec.landmarks.filter((m) => m.kind === "sea" || m.kind === "lake" || m.kind === "pond");
    if (!near && share < FAR_WATER && !marks.length) return null;
    const leaning = near ? near.at : spec.far.reduce((sum, s) => sum + (s.water + s.ocean) * s.at, 0);
    const side = leaning < 0 || (leaning === 0 && spec.seed % 2) ? -1 : 1;
    const sea = (near && near.kind === "sea") || marks.some((m) => m.kind === "sea");
    const crowded = spec.setting !== "wild" ? 0.6 : 1; // leave room for the camp or town
    const wide = crowded * (near ? [58, 76, 96][near.size - 1] : clamp(30 + share * 200, 34, 76));
    const bottom = near && near.size > 1 ? H + 1 : near ? 84 : GROUND_TOP + 7;
    const stays = near ? [0, 0.5, 0.8][near.size - 1] : 0; // how much is left at the bottom
    const phase = between(rand, 0, 6);
    const reach = (y) => {
      if (y < HORIZON || y > bottom) return 0;
      const t = (y - HORIZON) / (bottom - HORIZON);
      const run = stays ? 1 - t * t * (1 - stays) : Math.sqrt(1 - t * t);
      return Math.max(0, wide * run + (3 * Math.sin(y / 5 + phase) + 1.5 * Math.sin(y / 2.3 + phase)) * Math.min(1, run * 2) * Math.min(1, t * 6));
    };
    return { side, sea, near: Boolean(near), wide, bottom, reach };
  }

  // How much x is taken up by the shore's water at the horizon: 1 inside, 0 well clear.
  function underWater(plan, x) {
    const s = plan.shore;
    if (!s) return 0;
    const off = s.side < 0 ? x : W - x;
    return clamp(1 - (off - s.wide) / SHORE_FADE, 0, 1);
  }

  function layout(spec) {
    const rand = rng(spec.seed);
    const out = { blocks: [], water: [], props: [], fire: null, avatar: null, lights: [] };
    const crossing = spec.ground === "bridge" || spec.ground === "ford";
    out.shore = shoreOf(spec, rand, crossing);
    const fill = colors(spec.region, spec.biome).water[0];
    if (crossing) {
      // a river right across the picture, with you on the way over it
      const cy = 70;
      const ry = 9;
      out.band = { y: cy - ry, h: 2 * ry, kind: spec.ground };
      for (let y = cy - ry; y < cy + ry; y += 2) out.water.push({ x: 0, y, w: W, h: 2, color: fill });
    } else if (spec.water) {
      // the part of the shore's water you could swim in
      for (let y = GROUND_TOP + 4; y < H; y += 2) {
        const w = Math.round(out.shore.reach(y));
        if (w > 3) out.water.push({ x: out.shore.side < 0 ? 0 : W - w, y, w, h: 2, color: fill });
      }
    }
    // Keep x on dry land at height y, `room` clear of the water, and on the picture.
    out.land = (x, y, room = 0) => {
      const s = out.shore;
      if (!s) return x;
      const need = s.reach(y) + room;
      const off = s.side < 0 ? x : W - x;
      return off >= need ? x : s.side < 0 ? Math.min(need, W - 4) : Math.max(W - need, 4);
    };
    // What you came to see stands in the middle, unless that's the water.
    out.center = out.land(80, 66, 18);
    if (spec.setting === "shrine" || spec.setting === "house") out.blocks.push({ x: out.center - 14, y: 60, w: 28, h: 8 });
    const camp = spec.setting === "camp";
    if (camp) {
      const fy = out.band ? 82 : 74;
      const fx = Math.round(out.land(80 + between(rand, -12, 12), fy, 14));
      out.fire = { x: fx, y: fy };
      out.blocks.push({ x: fx - 6, y: fy - 3, w: 12, h: 5 });
      const side = out.shore ? -out.shore.side : chance(rand, 0.5) ? -1 : 1; // the tent on the dry side
      out.tent = { x: clamp(fx + side * 36, 22, W - 22), y: fy - 8, side };
      out.blocks.push({ x: out.tent.x - 16, y: out.tent.y - 4, w: 32, h: 6 });
      if (spec.special === "camp") {
        out.tent2 = { x: clamp(fx - side * 40, 22, W - 22), y: fy - 12 };
        out.blocks.push({ x: out.tent2.x - 14, y: out.tent2.y - 4, w: 28, h: 6 });
      }
      out.seat = { x: out.land(fx - side * 18, fy + 4, 10), y: fy + 4 };
      out.blocks.push({ x: out.seat.x - 8, y: out.seat.y - 2, w: 16, h: 3 });
      out.avatar = { x: out.seat.x + (out.seat.x < fx ? 2 : -2), y: fy + 3 };
      out.props.push({ id: "fire", x: fx + side * 8, y: fy + 4, action: "bask" });
    }
    if (!out.avatar) {
      const left = chance(rand, 0.5);
      const y = Math.round(between(rand, 72, 80));
      out.avatar = { x: Math.round(out.land(left ? between(rand, 34, 58) : between(rand, 102, 126), y, 10)), y };
      if (crossing) out.avatar = { x: 80, y: 72 };
    }
    out.blocks.push({ x: out.avatar.x - 5, y: out.avatar.y - 2, w: 10, h: 3 });
    return out;
  }

  function area(spec, plan) {
    return {
      left: 2, right: W - 2, top: FEET_TOP, bottom: FEET_BOTTOM, sky: true, props: plan.props,
      terrain: { water: plan.water, blocks: plan.blocks },
    };
  }

  // --- the kit of parts: small things, drawn with their feet at (x, y) ----------------

  function tree(r, kind, x, y, s, c) {
    const leaf = c.treeLeaf || "#4a8a4a";
    switch (kind) {
      case "pine":
      case "darkpine": {
        const dark = kind === "darkpine";
        r(x - s, y - 4 * s, 2 * s, 4 * s, "#5a3a22");
        for (let i = 0; i < 3; i++) {
          const w = (5 - i) * 2 * s;
          r(x - w / 2, y - (4 + 3 * i) * s - 3 * s, w, 4 * s, dark ? "#23503c" : "#2f6a48");
          r(x - w / 2 + s, y - (4 + 3 * i) * s - 3 * s, w / 2 - s, 1.2 * s, dark ? "#2f6450" : "#3f8058");
        }
        break;
      }
      case "apple":
        r(x - s, y - 7 * s, 2 * s, 7 * s, "#6e4a2a");
        disc(r, x, y - 11 * s, 7 * s, 6 * s, "#4a8a4a");
        disc(r, x - s, y - 12 * s, 4 * s, 3 * s, "#5fa45a");
        for (const [dx, dy] of [[-4, -12], [3, -13], [-1, -9], [4, -9], [-3, -8]]) r(x + dx * s, y + dy * s, 1.3 * s, 1.3 * s, "#d8473a");
        break;
      case "dead":
        r(x - s / 2, y - 12 * s, s, 12 * s, "#5e4636");
        r(x - 4 * s, y - 9 * s, 4 * s, s, "#5e4636");
        r(x, y - 7 * s, 4 * s, s, "#5e4636");
        r(x - 4 * s, y - 11 * s, s, 2 * s, "#5e4636");
        r(x + 3 * s, y - 10 * s, s, 3 * s, "#5e4636");
        break;
      case "shrub":
        disc(r, x, y - 3 * s, 5 * s, 3 * s, c.dark);
        disc(r, x - s, y - 4 * s, 3 * s, 2 * s, c.light);
        r(x - 2 * s, y - 5 * s, s, s, "#c478b0");
        r(x + 2 * s, y - 4 * s, s, s, "#c478b0");
        break;
      case "palm":
        r(x - s / 2, y - 12 * s, 1.5 * s, 12 * s, "#8a6a3a");
        for (const [dx, dy, w] of [[-7, -13, 7], [1, -13, 7], [-5, -15, 10], [-8, -11, 3], [6, -11, 3]]) r(x + dx * s, y + dy * s, w * s, 1.5 * s, "#4a9a5a");
        break;
      case "mushroomtree":
        r(x - 1.5 * s, y - 9 * s, 3 * s, 9 * s, "#e8dcc4");
        disc(r, x, y - 11 * s, 7 * s, 4 * s, "#c44e7e");
        r(x - 7 * s, y - 10 * s, 14 * s, s, "#8e3058");
        for (const [dx, dy] of [[-4, -13], [2, -14], [4, -11], [-1, -11]]) r(x + dx * s, y + dy * s, 1.5 * s, 1.5 * s, "#f8e8f0");
        break;
      case "crystal":
        crystal(r, x, y, 2.2 * s);
        break;
      default:
        r(x - s, y - 6 * s, 2 * s, 6 * s, "#6e4a2a");
        disc(r, x, y - 10 * s, 6 * s, 5 * s, c.treeLeaf ? "#5a5aa4" : "#3f7a40");
        disc(r, x - s, y - 11 * s, 4 * s, 3 * s, leaf);
    }
  }

  function rock(r, x, y, s, c) {
    disc(r, x, y - 2 * s, 5 * s, 3 * s, c.rock[2]);
    disc(r, x, y - 3 * s, 4 * s, 2.5 * s, c.rock[0]);
    r(x - 2 * s, y - 5 * s, 3 * s, s, c.rock[1]);
  }

  function crag(r, x, y, s, c) {
    const w = 11 * s;
    for (let i = 0; i < 5; i++) {
      const h = (9 + ((i * 7) % 5) * 1.6) * s;
      r(x - w + (i * 2 * w) / 5, y - h, (2 * w) / 5 + 1, h, i % 2 ? c.rock[2] : c.rock[0]);
      r(x - w + (i * 2 * w) / 5, y - h, (2 * w) / 5 + 1, s, c.rock[1]);
    }
  }

  function crystal(r, x, y, s) {
    r(x - s, y - 5 * s, 2 * s, 5 * s, "#9a6ad8");
    r(x - s, y - 6 * s, 1.2 * s, s, "#d8b8f8");
    r(x - s / 3, y - 5 * s, s / 2, 4 * s, "#c8a0f0");
    r(x + s, y - 3 * s, 1.4 * s, 3 * s, "#7e50c0");
    r(x - 2.4 * s, y - 2.5 * s, 1.4 * s, 2.5 * s, "#b488e8");
  }

  function house(r, x, y, s, c, plan, door = true) {
    const w = 8 * s;
    r(x - w, y - 8 * s, 2 * w, 8 * s, "#e6d4b0");
    r(x - w, y - 8 * s, 2 * w, s, "#c8b48e");
    for (let i = 0; i < 5; i++) r(x - w - s + i * s, y - 8 * s - i * s, 2 * w + 2 * s - 2 * i * s, s + 0.5, c.roof);
    r(x - w - s, y - 8 * s, 2 * w + 2 * s, 0.6 * s, "#00000033");
    if (door) r(x - 1.5 * s, y - 5 * s, 3 * s, 5 * s, "#6e4a2a");
    const wy = y - 6 * s;
    r(x - w + 2 * s, wy, 2.5 * s, 2.5 * s, "#8ac4dc");
    r(x + w - 4.5 * s, wy, 2.5 * s, 2.5 * s, "#8ac4dc");
    if (plan) plan.lights.push({ x: x - w + 2 * s, y: wy, w: 2.5 * s, h: 2.5 * s }, { x: x + w - 4.5 * s, y: wy, w: 2.5 * s, h: 2.5 * s });
  }

  function roofs(r, x, y, n, s, c, rand, plan) {
    const count = clamp(n, 2, 7);
    const spread = count * 6.5 * s;
    const order = Array.from({ length: count }, (_, i) => i);
    order.forEach((i) => {
      const dx = (i - (count - 1) / 2) * (2 * spread) / count + between(rand, -1, 1);
      const back = i % 2 === 0 ? 2 * s : 0;
      house(r, x + dx, y - back, s * between(rand, 0.8, 1.05), c, plan, false);
    });
  }

  function temple(r, x, y, s, region) {
    const accent = (window.WanderMap && WanderMap.TYPE_COLORS && WanderMap.TYPE_COLORS[region]) || REGIONS[region]?.cloth || "#e8b33e";
    const w = 13 * s;
    r(x - w - s, y - s, 2 * w + 2 * s, s, "#a8a294");
    for (let i = 0; i < 5; i++) {
      r(x - w + (i * 2 * w) / 4 - s / 2, y - 9 * s, 1.6 * s, 8 * s, "#d8d2c2");
      r(x - w + (i * 2 * w) / 4 + s / 2, y - 9 * s, 0.5 * s, 8 * s, "#a8a294");
    }
    r(x - w - s, y - 10.5 * s, 2 * w + 2 * s, 1.5 * s, "#c8c2b2");
    for (let i = 0; i < 5; i++) r(x - w - s + i * 2.6 * s, y - 11.5 * s - i * s, 2 * w + 2 * s - i * 5.2 * s, s, i === 2 ? accent : "#e0dac8");
    r(x - 1.5 * s, y - 8 * s, 3 * s, 7 * s, accent);
  }

  function heartstone(r, x, y, s) {
    disc(r, x, y - 5 * s, 9 * s, 7 * s, "rgba(248,224,138,0.35)");
    r(x - 3 * s, y - 11 * s, 6 * s, 11 * s, "#d8c8a8");
    r(x - 2 * s, y - 13 * s, 4 * s, 2 * s, "#e8dcc4");
    r(x - s, y - 10 * s, 2 * s, 7 * s, "#f4d35e");
    r(x - 5 * s, y - s, 10 * s, s, "#a8a294");
  }

  function shrine(r, x, y, s, c, plan) {
    r(x - 5 * s, y - s, 10 * s, s, STONE[2]);
    r(x - 4 * s, y - 2 * s, 8 * s, s, STONE[0]);
    r(x - 2.5 * s, y - 8 * s, 5 * s, 6 * s, STONE[1]);
    r(x - 3.5 * s, y - 9 * s, 7 * s, s, STONE[0]);
    r(x - 2.5 * s, y - 10 * s, 5 * s, s, c.roof);
    r(x - s, y - 7 * s, 2 * s, 3 * s, "#f4d35e");
    if (plan) plan.lights.push({ x: x - s, y: y - 7 * s, w: 2 * s, h: 3 * s });
  }

  function caveMouth(r, x, y, s, c) {
    for (const [dx, w, h, tone] of [[-13, 7, 7, 2], [-8, 7, 11, 0], [-2, 6, 14, 0], [3, 7, 11, 2], [8, 6, 6, 0]]) {
      r(x + dx * s, y - h * s, w * s, h * s, c.rock[tone]);
      r(x + dx * s, y - h * s, w * s, 1.2 * s, c.rock[1]);
    }
    disc(r, x, y - 3 * s, 3.5 * s, 4 * s, "#241c1c");
    r(x - 3.5 * s, y - s, 7 * s, s, "#241c1c");
    r(x - 14 * s, y - 0.6 * s, 28 * s, 0.8 * s, c.rock[2]);
  }

  function well(r, x, y, s) {
    r(x - 3 * s, y - 3 * s, 6 * s, 3 * s, STONE[0]);
    r(x - 3 * s, y - 3 * s, 6 * s, s, STONE[1]);
    r(x - 3 * s, y - 8 * s, s, 5 * s, "#6e4a2a");
    r(x + 2 * s, y - 8 * s, s, 5 * s, "#6e4a2a");
    r(x - 4 * s, y - 9 * s, 8 * s, s, "#8a4a34");
  }

  function statue(r, x, y, s) {
    r(x - 3 * s, y - 2 * s, 6 * s, 2 * s, STONE[0]);
    r(x - 1.5 * s, y - 8 * s, 3 * s, 6 * s, STONE[1]);
    r(x - s, y - 10 * s, 2 * s, 2 * s, STONE[1]);
  }

  function ruin(r, x, y, s) {
    r(x - 6 * s, y - 7 * s, 2 * s, 7 * s, STONE[0]);
    r(x + 3 * s, y - 4 * s, 2 * s, 4 * s, STONE[0]);
    r(x - 6 * s, y - 7 * s, 5 * s, s, STONE[1]);
    r(x - 2 * s, y - s, 3 * s, s, STONE[2]);
  }

  function flower(r, x, y, c) {
    r(x, y - 2, 1, 2, "#4f7a34");
    r(x - 1, y - 3, 3, 1, c);
    r(x, y - 4, 1, 3, c);
    r(x, y - 3, 1, 1, "#f4d35e");
  }

  const PETALS = ["#e86a8a", "#fbf1dc", "#9a7ae0", "#f4a24a", "#f4d35e"];
  // The little things underfoot, with their feet at (x, y).
  const DECOR = {
    tuft: (r, x, y, c) => { r(x, y - 2, 1, 2, c.dark); r(x + 2, y - 3, 1, 3, c.dark); r(x + 1, y - 1, 1, 1, c.light); },
    windgrass: (r, x, y, c) => { r(x, y - 2, 1, 2, c.dark); r(x + 1, y - 3, 2, 1, c.dark); r(x + 3, y - 2, 1, 2, c.light); r(x + 4, y - 3, 2, 1, c.light); },
    flower: (r, x, y, c, rand) => flower(r, x, y, PETALS[Math.floor(rand() * PETALS.length)]),
    wheat: (r, x, y) => { r(x, y - 5, 1, 5, "#c8a848"); r(x - 1, y - 6, 3, 2, "#e0c060"); },
    apple: (r, x, y) => { r(x, y - 1, 2, 2, "#d8473a"); r(x + 1, y - 2, 1, 1, "#4f7a34"); },
    fern: (r, x, y) => { r(x, y - 5, 1, 5, "#3f7a40"); for (let i = 0; i < 3; i++) { r(x - 3 + i, y - 4 + i, 3 - i, 1, "#4f9a4a"); r(x + 1, y - 4 + i, 3 - i, 1, "#4f9a4a"); } },
    mushroom: (r, x, y) => { r(x, y - 2, 1, 2, "#e8dcc4"); r(x - 1, y - 3, 3, 1, "#c44e7e"); r(x, y - 4, 1, 1, "#c44e7e"); },
    reed: (r, x, y) => { r(x, y - 7, 1, 7, "#5a8a4a"); r(x, y - 9, 1, 3, "#7a5a34"); r(x + 2, y - 5, 1, 5, "#6a9a58"); },
    pebble: (r, x, y, c) => { r(x, y - 1, 2, 1, c.rock[0]); r(x, y - 2, 1, 1, c.rock[1]); },
    rock: (r, x, y, c) => rock(r, x, y, 1, c),
    redrock: (r, x, y, c) => rock(r, x, y, 1.3, c),
    ashrock: (r, x, y, c) => rock(r, x, y, 1.2, c),
    shrub: (r, x, y, c) => tree(r, "shrub", x, y, 1, c),
    shell: (r, x, y) => { r(x, y - 1, 2, 1, "#f8e8e0"); r(x + 1, y - 2, 1, 1, "#e8b8a8"); },
    sandpatch: (r, x, y) => { r(x - 5, y - 1, 10, 2, "#e0c890"); r(x - 3, y - 2, 6, 1, "#e0c890"); },
    vent: (r, x, y, c) => { disc(r, x, y, 4, 2, c.rock[2]); r(x - 1, y - 1, 2, 1, "#5ec2c0"); r(x - 1, y - 4, 1, 2, "rgba(255,255,255,0.6)"); r(x + 1, y - 7, 1, 2, "rgba(255,255,255,0.4)"); },
    crack: (r, x, y) => { r(x - 3, y, 3, 1, "#f4823a"); r(x, y - 1, 3, 1, "#f4a24a"); r(x + 3, y - 2, 2, 1, "#f4823a"); },
    crystal: (r, x, y) => crystal(r, x, y, 1),
    sparkle: (r, x, y) => { r(x, y - 8, 1, 1, "#fff6c8"); r(x + 1, y - 10, 1, 1, "#e8d8ff"); },
    spark: (r, x, y) => { r(x, y - 3, 1, 1, "#f4e04a"); r(x + 1, y - 2, 1, 1, "#fff6c8"); },
  };

  // --- the layers ---------------------------------------------------------------------

  function sky(r, c, spec, rand, night) {
    const top = c.skyTint || c.sky;
    for (let y = 0; y < GROUND_TOP; y++) r(0, y, W, 1, y < 8 ? top : y < 22 ? mix(top, c.skyLow, (y - 8) / 14) : c.skyLow);
    const weather = (BIOMES[spec.biome] || NO_BIOME).weather || "clouds";
    if (!night && weather !== "storm" && weather !== "smoky" && weather !== "mist") {
      const sx = Math.round(between(rand, 20, 140));
      disc(r, sx, 9, 5, 5, "#fbeeb0");
      disc(r, sx, 9, 4, 4, "#fff6d0");
    }
    const clouds = { clear: 1, clouds: 3, haze: 2, storm: 5, smoky: 4, mist: 2 }[weather];
    const cloud = weather === "storm" ? "#5a5a6e" : weather === "smoky" ? "#6e5a58" : weather === "haze" ? "rgba(255,255,255,0.55)" : "#ffffff";
    for (let i = 0; i < clouds; i++) {
      const x = between(rand, -6, W - 10);
      const y = between(rand, 2, weather === "storm" ? 10 : 16);
      r(x, y + 2, 18, 3, cloud);
      r(x + 3, y, 10, 2, cloud);
      if (weather === "storm") r(x + 2, y + 5, 14, 1, "#4a4a5e");
    }
    if (weather === "storm") {
      const x = Math.round(between(rand, 30, 130));
      for (const [dx, dy, h] of [[0, 8, 4], [-2, 12, 4], [0, 16, 4]]) r(x + dx, dy, 1, h, "#fff6a0");
    }
  }

  function mix(a, b, t) {
    const n = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    const [x, y] = [n(a), n(b)];
    return `rgb(${x.map((v, i) => Math.round(v + (y[i] - v) * t)).join()})`;
  }

  // The horizon's slices, by x: whatever's nearest.
  function sliceAt(spec, x) {
    const at = clamp((x - W / 2) / (W / 2 - 4), -1, 1);
    return spec.far.reduce((best, s) => (Math.abs(s.at - at) < Math.abs(best.at - at) ? s : best));
  }
  // One thing about the horizon, smoothed across its slices.
  function smooth(spec, x, key) {
    let sum = 0;
    let weight = 0;
    const at = (x - W / 2) / (W / 2 - 4);
    for (const s of spec.far) {
      const w = Math.max(0, 0.34 - Math.abs(s.at - at));
      sum += w * s[key];
      weight += w;
    }
    return weight ? sum / weight : 0;
  }

  // The horizon as lands, left to right: runs of x that are one land's. Each is
  // drawn as its own hill, spilling a little past its ends and sloping away, so
  // lands overlap with a clean edge. Widest first: the small ones stand in front.
  function landRuns(spec) {
    const runs = [];
    for (let x = 0; x < W; x++) {
      const s = sliceAt(spec, x);
      const biome = s.biome || spec.biome;
      const last = runs[runs.length - 1];
      if (last && last.biome === biome) last.x1 = x;
      else runs.push({ biome, x0: x, x1: x });
    }
    return runs.sort((a, b) => b.x1 - b.x0 - (a.x1 - a.x0));
  }

  // How far down a hill has sloped: 0 along its run, 1 at the ground past its ends
  // (not at the picture's edges: it just carries on out of sight).
  function slopeAt(run, x, spill) {
    const past = Math.max(run.x0 - x, x - run.x1, -spill) + spill;
    return run.x0 === 0 && x < run.x1 / 2 ? 0 : run.x1 === W - 1 && x > run.x0 + (W - run.x0) / 2 ? 0 : past / (2 * spill);
  }

  function farLand(r, spec, seedPhase, plan) {
    const lowBy = plan.shore && plan.shore.sea ? HORIZON + 1 : HORIZON - 2; // past a lake there's a low far shore
    for (const run of landRuns(spec)) {
      const land = colors(regionOf(run.biome), run.biome);
      for (let x = Math.max(0, run.x0 - FAR_SPILL); x <= Math.min(W - 1, run.x1 + FAR_SPILL); x++) {
        const wet = underWater(plan, x);
        const cliff = smooth(spec, x, "cliff") * (1 - wet);
        const rolling = 3 * Math.sin(x / 17 + seedPhase) + 1.5 * Math.sin(x / 7 + seedPhase * 2);
        const jag = cliff * 18 * Math.abs(((x + seedPhase * 11) % 26) / 13 - 1) + cliff * 9;
        const top = GROUND_TOP - (GROUND_TOP - (HORIZON - 5 + rolling - jag)) * (1 - slopeAt(run, x, FAR_SPILL));
        const h = Math.round(top + (lowBy - top) * wet);
        if (h >= GROUND_TOP) continue;
        const rocky = jag > ROCKY_AT;
        const color = rocky ? land.rock[0] : land.far;
        r(x, h, 1, GROUND_TOP - h, color);
        r(x, h, 1, 1, mix(color, "#000000", 0.14)); // a clear edge against the sky
        const peak = HORIZON - 5 - h;
        if (rocky && peak > 12) r(x, h, 1, Math.min(4, peak - 10), "#f4f2ea"); // snow up high
      }
    }
  }

  // The biomes in each region (the far land can be someone else's).
  const REGION_OF = {
    fields: "camp", orchard: "camp", meadow: "leaf", woods: "leaf", fern_hollow: "leaf", deepwood: "leaf",
    brookside: "splash", marsh: "splash", lakeshore: "splash", isles: "splash", heath: "ember", red_rocks: "ember", hot_springs: "ember",
    ember_peaks: "ember", windy_hills: "shock", mesa: "shock", ridge: "shock", storm_peaks: "shock", glade: "dream",
    mushroom_grove: "dream", mist_vale: "dream", crystal_hollow: "dream",
  };
  const regionOf = (biome) => REGION_OF[biome] || "camp";

  // The nearer hills, with the woods on them. plan.nearTop: where they start, per x:
  // what stands on the land stands on this.
  function nearLand(r, spec, rand, seedPhase, plan) {
    plan.nearTop = new Array(W).fill(GROUND_TOP + 2);
    plan.nearColor = new Array(W).fill(colors(spec.region, spec.biome).near);
    for (const run of landRuns(spec)) {
      const color = colors(regionOf(run.biome), run.biome).near;
      for (let x = Math.max(0, run.x0 - NEAR_SPILL); x <= Math.min(W - 1, run.x1 + NEAR_SPILL); x++) {
        const wet = underWater(plan, x);
        const top = GROUND_TOP + 2 - (GROUND_TOP + 2 - (HORIZON + 3 + 2 * Math.sin(x / 11 + seedPhase) + Math.sin(x / 4 + seedPhase))) * (1 - slopeAt(run, x, NEAR_SPILL));
        const h = Math.round(top + (GROUND_TOP + 2 - top) * wet);
        if (h >= GROUND_TOP + 2) continue;
        r(x, h, 1, GROUND_TOP + 2 - h, color);
        plan.nearTop[x] = Math.min(plan.nearTop[x], h);
        plan.nearColor[x] = color;
      }
    }
    const backTrees = (BIOMES[spec.biome] || NO_BIOME).backTrees || 0;
    // treelines: bumps of the slice's own trees
    for (let x = 0; x < W; x += 3) {
      if (underWater(plan, x) > 0.2) continue;
      const trees = smooth(spec, x, "tree");
      if (rand() < Math.max(trees * 2.2, backTrees)) {
        const s = sliceAt(spec, x);
        const land = colors(s.biome ? regionOf(s.biome) : spec.region, s.biome);
        tree(r, (BIOMES[s.biome] || NO_BIOME).tree || "round", x, plan.nearTop[x] + 1, 0.6, land);
      }
    }
  }

  // Deep woods crowd in: a wall of trees along the back of the near land.
  function backWoods(r, spec, c, rand, plan) {
    const look = BIOMES[spec.biome] || NO_BIOME;
    if (!look.backTrees) return;
    for (let x = -4; x < W + 4; x += 8) {
      if (rand() < look.backTrees && !underWater(plan, x)) tree(r, look.tree, x + between(rand, -2, 2), GROUND_TOP + between(rand, 1, 3), between(rand, 0.8, 1.15), c);
    }
  }

  // Half a landmark's width at scale 1.
  const MARK_HALF = { town: 28, house: 10, temple: 15, heartstone: 8, cave: 15, shrine: 6, smoke: 2 };

  // Where a landmark stands: its whole width on land, its base low enough to have
  // ground under all of it, and a lip of the land in front so it sits in, not on.
  function standing(spec, plan, at, half) {
    let x = clamp(xAt(at * 0.92), half + 1, W - half - 1);
    const s = plan.shore;
    if (s) {
      const off = s.side < 0 ? x : W - x;
      const need = s.wide + SHORE_FADE + half;
      if (off < need) x = clamp(s.side < 0 ? need : W - need, half + 1, W - half - 1);
    }
    let base = 0;
    for (let i = Math.floor(x - half); i <= x + half; i++) base = Math.max(base, plan.nearTop[clamp(i, 0, W - 1)]);
    return { x, y: Math.min(base + 1, GROUND_TOP + 1) };
  }

  function nestle(r, spec, plan, x, y, half) {
    for (let i = Math.floor(x - half - 2); i <= x + half + 2; i++) {
      if (i < 0 || i >= W) continue;
      r(i, y - 1 + Math.round(Math.sin(i / 2.7)), 1, GROUND_TOP + 2 - y + 1, plan.nearColor[i]);
    }
  }

  function landmarks(r, spec, plan, rand) {
    const smokes = [];
    const here = colors(spec.region, spec.biome);
    for (const m of [...spec.landmarks].reverse()) {
      if (m.dist <= MID_RINGS && NEAR_IS_MID.has(m.kind)) continue; // already there, in the middle distance
      if (!(m.kind in MARK_HALF)) continue;
      if (m.kind === spec.setting && m.dist <= HALL_NEAR) continue; // you're inside it: it's the big one in front
      const s = m.dist <= 4 ? 1 : m.dist <= 8 ? 0.75 : 0.55;
      const half = MARK_HALF[m.kind] * s;
      const { x, y } = standing(spec, plan, m.at, half);
      switch (m.kind) {
        case "town": roofs(r, x, y, m.n, s, here, rand, plan); break;
        case "house": house(r, x, y, s, here, plan); break;
        case "temple": temple(r, x, y, s * 1.1, m.region); break;
        case "heartstone": heartstone(r, x, y, s * 1.3); break;
        case "cave": caveMouth(r, x, y, s * 1.1, here); break;
        case "shrine": shrine(r, x, y, s, here, plan); break;
        default: smokes.push({ x, y: y - 2, s }); break;
      }
      if (m.kind !== "smoke") nestle(r, spec, plan, x, y, half);
    }
    plan.smokes = smokes;
    // a river only when there's no lake or sea to be the water
    const stream = spec.landmarks.find((m) => m.kind === "river");
    if (stream && !plan.shore) river(r, standing(spec, plan, stream.at, 6).x, spec, plan, rand);
  }

  // A river winding down out of the far land, wider as it comes.
  function river(r, x, spec, plan, rand) {
    const c = colors(spec.region, spec.biome);
    const wiggle = between(rand, 0, 6);
    const top = plan.nearTop[clamp(Math.round(x), 0, W - 1)] + 1;
    for (let y = top; y < GROUND_TOP + 10; y++) {
      const t = (y - top) / 18;
      const cx = x + 5 * Math.sin(y / 3.5 + wiggle) * t;
      const half = 0.8 + t * 5;
      r(cx - half, y, 2 * half, 1, c.water[0]);
      if (y % 3 === 0) r(cx - half / 2, y, half / 2, 1, c.water[1]);
    }
  }

  // Flat stones, growing as they come toward you, so it lies down like a floor.
  function paving(r, base, rand, accent) {
    let y = GROUND_TOP + 1;
    let row = 0;
    for (let h = 2; y < H; h = Math.min(h + 1, 8), row++) {
      const w = Math.round(h * 2.8);
      let col = 0;
      for (let x = row % 2 ? -w / 2 : -w; x < W; x += w, col++) {
        r(x, y, w - 1, h - 1, rand() < 0.5 ? base[1] : base[2]);
        if (accent && (col + row) % 3 === 0 && h > 3) r(x + w / 2 - 1, y + h / 2 - 1, 2, 1, accent);
      }
      y += h;
    }
  }

  function ground(r, spec, c, rand) {
    const base = spec.ground === "sand" ? ["#e0c890", "#ecd8a8", "#c8ae70"]
      : spec.ground === "plaza" ? ["#b4a48c", "#c8b8a0", "#9a8a74"]
      : spec.ground === "court" || spec.ground === "temple" || spec.ground === "stone" ? ["#c8c2b4", "#dad4c6", "#aca698"]
      : [c.ground, c.light, c.dark];
    r(0, GROUND_TOP, W, H - GROUND_TOP, base[0]);
    r(0, GROUND_TOP, W, 1, base[1]);
    if (spec.ground === "plaza") {
      paving(r, base, rand, null);
    } else if (spec.ground === "court" || spec.ground === "temple" || spec.ground === "stone") {
      paving(r, base, rand, REGIONS[spec.region]?.cloth || "#e8b33e");
    } else {
      for (let i = 0; i < 150; i++) r(between(rand, 0, W), between(rand, GROUND_TOP + 2, H), 1, 1, rand() < 0.6 ? base[2] : base[1]);
    }
  }

  // Trails from the path hexes around you, down to your feet.
  function trails(r, spec, c, plan) {
    const onPath = spec.ground === "path" || spec.ground === "bridge";
    const paths = spec.mid.filter((t) => t.kind === "path" || t.kind === "bridge").sort((a, b) => a.ring - b.ring || Math.abs(a.at) - Math.abs(b.at));
    const dirt = "#c8a878";
    const edge = "#a8895c";
    const drawn = paths.slice(0, onPath ? 2 : 1);
    if (onPath && !drawn.length) drawn.push({ at: 0.1 });
    for (const p of drawn) {
      const top = xAt(p.at * 0.8);
      const foot = 80 + p.at * 20;
      for (let y = GROUND_TOP + 1; y < H; y++) {
        const t = (y - GROUND_TOP) / (H - GROUND_TOP);
        const x = plan.land(top + (foot - top) * t * t + 2 * Math.sin(y / 5), y, 3 + t * 8);
        const half = 2 + t * 8;
        r(x - half, y, 2 * half, 1, dirt);
        r(x - half, y, 1, 1, edge);
        r(x + half - 1, y, 1, 1, edge);
      }
    }
  }

  // The shore's water, off the side of the picture, then any river you're crossing.
  function water(r, spec, plan, c, rand, sky) {
    const s = plan.shore;
    if (s) {
      const bank = s.sea || (BIOMES[spec.biome] || NO_BIOME).sandy ? "#e0c890" : c.dark;
      const from = (w) => (s.side < 0 ? 0 : W - w);
      for (let y = HORIZON; y <= s.bottom; y++) {
        const w = s.reach(y);
        if (w <= 0) continue;
        if (y > GROUND_TOP) r(s.side < 0 ? w : W - w - 2, y, 2, 1, bank);
        const far = clamp((GROUND_TOP + 6 - y) / 12, 0, 1); // paler toward the horizon
        r(from(w), y, w, 1, mix(c.water[0], sky, far * 0.4));
      }
      r(from(s.wide), HORIZON, s.wide, 1, c.water[1]); // where it meets the far side
      for (let i = 0; i < 26; i++) {
        const y = Math.round(between(rand, HORIZON + 2, Math.min(s.bottom, H - 1)));
        const len = 2 + (y - HORIZON) / 10;
        const w = s.reach(y);
        if (w > len + 3) r(s.side < 0 ? between(rand, 0, w - len - 2) : W - w + 2 + between(rand, 0, w - len - 2), y, len, 1, c.water[1]);
      }
    }
    const band = plan.band;
    if (band) {
      r(0, band.y - 1, W, 1, c.dark);
      r(0, band.y, W, band.h, c.water[0]);
      r(0, band.y + band.h, W, 2, c.dark);
      for (let i = 0; i < 18; i++) r((i * 37) % W, band.y + 1 + (i * 5) % (band.h - 2), 5, 1, c.water[1]);
      if (band.kind === "bridge") {
        for (let y = band.y - 3; y < band.y + band.h + 3; y += 2) r(70, y, 20, 1.6, y % 4 ? "#a87a44" : "#8b5a2b");
        r(69, band.y - 3, 1, band.h + 6, "#6e4a2a");
        r(90, band.y - 3, 1, band.h + 6, "#6e4a2a");
      } else {
        for (const [dx, dy] of [[-22, 3], [-10, 11], [2, 5], [14, 13], [26, 7]]) disc(r, 80 + dx, band.y + dy, 4, 2, STONE[0]);
      }
    }
  }

  // One hex of the middle distance. Ring 2 is further back; ring 1 nearer. Whatever's
  // behind you gets pulled in at the sides, big, framing the picture.
  function midItem(r, t, spec, plan, rand) {
    const land = colors(t.biome ? regionOf(t.biome) : spec.region, t.biome);
    const behind = Math.abs(t.at) > 0.68;
    const frame = t.ring === 1 && behind && !FLAT.has(t.kind);
    let x = frame ? (t.at < 0 ? between(rand, 2, 14) : between(rand, W - 14, W - 2)) : xAt(t.at) + between(rand, -3, 3);
    const y = frame ? between(rand, 70, 86) : t.ring === 2 ? between(rand, 46, 50) : between(rand, 52, 56);
    if (plan.shore && plan.land(x, y, 6) !== x) {
      if (frame) return; // the water's there instead
      x = plan.land(x, y, 6);
    }
    const s = frame ? 1.5 : t.ring === 2 ? 0.7 : 1;
    const thing = t.poi === "shrine" ? "shrine" : t.nook && NOOK_PARTS[t.nook] ? t.nook : t.kind;
    if (frame) plan.blocks.push({ x: x - 8, y: y - 2, w: 16, h: 3 });
    const part = PARTS[thing];
    if (part) part(r, x, y, s, land, plan, rand, t);
  }
  const FLAT = new Set(["sand", "plaza", "court", "flowers"]);
  const NOOK_PARTS = { cave: 1, grotto: 1, mine: 1, tunnel: 1, well: 1, statue: 1, ruin: 1, log: 1 };
  const PARTS = {
    tree: (r, x, y, s, c, plan, rand, t) => tree(r, (BIOMES[t.biome] || NO_BIOME).tree || "round", x, y, s, c),
    bush: (r, x, y, s, c) => { disc(r, x, y - 3 * s, 5 * s, 3 * s, c.dark); disc(r, x - s, y - 4 * s, 3 * s, 2 * s, c.light); },
    rock: (r, x, y, s, c) => rock(r, x, y, s, c),
    cliff: (r, x, y, s, c) => crag(r, x, y, s, c),
    building: (r, x, y, s, c, plan) => house(r, x, y, s * 1.2, c, plan),
    colonnade: (r, x, y, s) => { r(x - s, y - 12 * s, 2.5 * s, 12 * s, "#d8d2c2"); r(x - 2 * s, y - 13 * s, 4.5 * s, s, "#c8c2b2"); },
    sand: (r, x, y, s) => disc(r, x, y, 8 * s, 2 * s, "#e0c890"),
    plaza: (r, x, y, s, c, plan, rand) => { for (let i = 0; i < 9; i++) r(x + between(rand, -9, 7) * s, y + between(rand, -2, 2) * s, 3 * s, 1 * s, i % 2 ? "#b4a48c" : "#9a8a74"); },
    court: (r, x, y, s, c, plan, rand) => { for (let i = 0; i < 9; i++) r(x + between(rand, -9, 7) * s, y + between(rand, -2, 2) * s, 3 * s, 1 * s, i % 2 ? "#c8c2b4" : "#aca698"); },
    flowers: (r, x, y, s, c, plan, rand) => { for (let i = 0; i < 5; i++) flower(r, x + between(rand, -7, 7), y + between(rand, -2, 2), PETALS[i % PETALS.length]); },
    shrine: (r, x, y, s, c, plan) => shrine(r, x, y, s, c, plan),
    cave: (r, x, y, s, c) => caveMouth(r, x, y, s, c),
    grotto: (r, x, y, s, c) => caveMouth(r, x, y, s, c),
    mine: (r, x, y, s, c) => { caveMouth(r, x, y, s, c); r(x - 4 * s, y - 6 * s, 8 * s, s, "#6e4a2a"); r(x - 4 * s, y - 6 * s, s, 6 * s, "#6e4a2a"); r(x + 3 * s, y - 6 * s, s, 6 * s, "#6e4a2a"); },
    tunnel: (r, x, y, s, c) => caveMouth(r, x, y, s, c),
    well: (r, x, y, s) => well(r, x, y, s),
    statue: (r, x, y, s) => statue(r, x, y, s),
    ruin: (r, x, y, s) => ruin(r, x, y, s),
    log: (r, x, y, s) => { r(x - 7 * s, y - 3 * s, 14 * s, 3 * s, "#7a5232"); r(x + 6 * s, y - 3 * s, 2 * s, 3 * s, "#d8b070"); },
  };

  // White canvas, so it stands out from any land: the shaded side and hem in the land's color.
  function tent(r, x, y, s, trim, plan) {
    r(x - 13.5 * s, y, 27 * s, s, "rgba(40, 30, 20, 0.3)"); // its shadow
    for (let i = 0; i < 12; i++) {
      const half = (i + 1) * s;
      const top = y - (12 - i) * s;
      r(x - half, top, half, s + 0.5, TENT_WHITE);
      r(x, top, half, s + 0.5, TENT_SHADE);
      r(x - half - 0.5, top, s * 0.6, s + 0.5, TENT_EDGE); // its outline
      r(x + half - 0.1, top, s * 0.6, s + 0.5, TENT_EDGE);
    }
    r(x - 12 * s, y - 1.6 * s, 24 * s, 1.6 * s, trim); // the hem
    for (let i = 0; i < 12; i++) r(x - (i * 0.3 + 0.5) * s, y - (12 - i) * s, (i * 0.6 + 1) * s, s + 0.5, "#3a2a22"); // the door
    r(x - 0.5 * s, y - 15 * s, s, 3 * s, "#6e4a2a");
    r(x, y - 15 * s, 4 * s, 1.5 * s, trim); // its flag
    if (plan) plan.lights.push({ x: x - 1.5 * s, y: y - 5 * s, w: 3 * s, h: 4 * s });
  }

  function campPieces(r, spec, plan, c, rand) {
    const f = plan.fire;
    if (plan.tent2) tent(r, plan.tent2.x, plan.tent2.y, 1.3, c.roof);
    tent(r, plan.tent.x, plan.tent.y, 1.5, c.cloth, plan);
    // a ring of stones, and the logs (the flames are animate()'s)
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      r(f.x + Math.cos(a) * 7 - 1, f.y + Math.sin(a) * 3, 2, 2, i % 2 ? STONE[0] : STONE[2]);
    }
    r(f.x - 5, f.y - 1, 10, 2, "#6e4a2a");
    r(f.x - 3, f.y - 2, 6, 2, "#8b5a2b");
    // somewhere to sit
    r(plan.seat.x - 8, plan.seat.y - 3, 16, 3, "#7a5232");
    r(plan.seat.x + 7, plan.seat.y - 3, 2, 3, "#d8b070");
    r(plan.seat.x - 8, plan.seat.y - 3, 16, 1, "#94673e");
    // a pack by the tent
    r(plan.tent.x + plan.tent.side * 16, plan.tent.y - 4, 5, 5, "#8a5a34");
    r(plan.tent.x + plan.tent.side * 16, plan.tent.y - 5, 5, 1, "#a87a44");
    // kindling
    r(f.x + 12, f.y + 6, 7, 1, "#7a5232");
    r(f.x + 13, f.y + 5, 6, 1, "#94673e");
  }

  function townPieces(r, spec, plan, c, rand) {
    const near = spec.mid.filter((t) => t.kind === "building").length;
    if (near < 2) {
      for (const x of [34, 126]) house(r, plan.land(x + between(rand, -6, 6), 54, 16), 54, 1.3, c, plan);
    }
    // a lamp post, some bunting, barrels
    const lx = Math.round(plan.land(between(rand, 18, 40), 76, 4));
    r(lx, 58, 1, 18, "#3a3a44");
    r(lx - 1, 56, 3, 3, "#f4d35e");
    plan.lights.push({ x: lx - 1, y: 56, w: 3, h: 3 });
    plan.blocks.push({ x: lx - 2, y: 75, w: 5, h: 2 });
    const bx = Math.round(clamp(plan.land(between(rand, 110, 146), 79, 3), 2, W - 14));
    r(bx, 72, 6, 7, "#8a5a34");
    r(bx, 74, 6, 1, "#5e3a20");
    r(bx + 7, 74, 5, 5, "#a87a44");
    plan.blocks.push({ x: bx - 1, y: 77, w: 14, h: 3 });
    for (let x = 4; x < W; x += 6) if (plan.land(x, 46, 2) === x) r(x, 46 + Math.sin(x / 19) * 2, 3, 2, PETALS[(x / 6) % PETALS.length | 0]);
  }

  function hallPieces(r, spec, plan, c) {
    if (spec.setting === "heartstone") {
      heartstone(r, 80, 62, 2);
      for (const x of [20, 50, 110, 140]) { r(x - 2, 44, 5, 18, "#d8d2c2"); r(x + 1, 44, 2, 18, "#a8a294"); r(x - 3, 42, 7, 2, "#c8c2b2"); }
    } else {
      temple(r, 80, 58, 1.7, spec.region);
      for (const x of [10, 150]) { r(x - 2, 52, 5, 22, "#d8d2c2"); r(x + 1, 52, 2, 22, "#a8a294"); r(x - 3, 50, 7, 2, "#c8c2b2"); plan.blocks.push({ x: x - 3, y: 72, w: 7, h: 3 }); }
    }
  }

  // The little things underfoot, keeping clear of everything else.
  function decorate(r, spec, plan, c, rand) {
    const look = BIOMES[spec.biome] || NO_BIOME;
    const wet = (x, y) => (plan.shore && plan.land(x, y, 3) !== x) || (plan.band && y > plan.band.y - 2 && y < plan.band.y + plan.band.h + 4);
    const clear = (x, y) => !plan.blocks.some((b) => x > b.x - 2 && x < b.x + b.w + 2 && y > b.y - 2 && y < b.y + b.h + 2) && !wet(x, y);
    const paved = ["plaza", "court", "temple", "stone"].includes(spec.ground);
    const scatter = (part, n) => {
      const placed = [];
      for (let i = 0; i < n; i++) {
        const x = Math.round(between(rand, 2, W - 2));
        const y = Math.round(between(rand, GROUND_TOP + 4, H - 1));
        if (clear(x, y)) placed.push([x, y]);
      }
      placed.sort((a, b) => a[1] - b[1]).forEach(([x, y]) => part(r, x, y, c, rand));
    };
    if (paved) return;
    for (const [part, n] of look.decor || [["tuft", 10]]) {
      const extra = spec.ground === "flowers" && part === "flower" ? 16 : 0;
      scatter(DECOR[part], n + extra);
    }
    if (spec.ground === "flowers" && !(look.decor || []).some(([p]) => p === "flower")) scatter(DECOR.flower, 16);
  }

  function weather(r, spec) {
    const sky = (BIOMES[spec.biome] || NO_BIOME).weather;
    if (sky === "mist") {
      for (const [y, h, a] of [[30, 6, 0.45], [40, 5, 0.5], [50, 4, 0.35], [66, 3, 0.25]]) r(0, y, W, h, `rgba(240,232,250,${a})`);
    } else if (sky === "haze") {
      r(0, 28, W, 10, "rgba(255,255,255,0.14)");
    }
  }

  // --- putting it together ---------------------------------------------------------------

  function build(spec, px, opts = {}) {
    const scene_night = Boolean(opts.night);
    const plan = layout(spec);
    const canvas = document.createElement("canvas");
    canvas.width = W * px;
    canvas.height = H * px;
    const r = habitatPainter(canvas.getContext("2d"), px);
    const rand = rng(spec.seed ^ 0x5bd1e995);
    const c = colors(spec.region, spec.biome);
    const phase = between(rand, 0, 6);
    sky(r, c, spec, rand, scene_night);
    farLand(r, spec, phase, plan);
    nearLand(r, spec, rand, phase, plan);
    landmarks(r, spec, plan, rand);
    ground(r, spec, c, rand);
    backWoods(r, spec, c, rand, plan);
    water(r, spec, plan, c, rand, c.skyLow);
    trails(r, spec, c, plan);
    // the middle distance, back to front
    const mid = spec.mid.filter((t) => PARTS[t.poi === "shrine" ? "shrine" : t.nook && NOOK_PARTS[t.nook] ? t.nook : t.kind]);
    mid.sort((a, b) => b.ring - a.ring).forEach((t) => midItem(r, t, spec, plan, rand));
    if (spec.setting === "town") townPieces(r, spec, plan, c, rand);
    if (spec.setting === "temple" || spec.setting === "heartstone") hallPieces(r, spec, plan, c);
    if (spec.setting === "shrine") shrine(r, plan.center, 66, 2, c, plan);
    if (spec.setting === "house") house(r, plan.center, 62, 2, c, plan);
    if (plan.fire) campPieces(r, spec, plan, c, rand);
    decorate(r, spec, plan, c, rand);
    weather(r, spec);
    const scene = { spec, px, background: canvas, plan, area: area(spec, plan), avatar: plan.avatar, night: Boolean(opts.night) };
    if (opts.night) scene.nightLayer = nightLayer(scene, phase);
    return scene;
  }

  // Night: one dark layer that goes over the pets too, with stars up top, and
  // holes where the fire and windows shine through.
  function nightLayer(scene, phase) {
    const { px, plan } = scene;
    const canvas = document.createElement("canvas");
    canvas.width = W * px;
    canvas.height = H * px;
    const ctx = canvas.getContext("2d");
    const r = habitatPainter(ctx, px);
    r(0, 0, W, H, "rgba(16, 20, 62, 0.62)");
    for (let y = 0; y < 30; y += 2) r(0, y, W, 2, `rgba(10, 12, 44, ${(0.62 * (1 - y / 30)).toFixed(2)})`); // darker higher up
    const rand = rng(scene.spec.seed ^ 0x2f);
    for (let i = 0; i < 48; i++) r(between(rand, 0, W), between(rand, 0, 24), 1, 1, i % 5 ? "rgba(240,240,220,0.9)" : "#ffffff");
    const mx = Math.round(between(rand, 24, 136));
    // a crescent moon: the big circle's left edge up to the small circle's
    for (let dy = -5; dy <= 5; dy++) {
      const outer = Math.sqrt(25 - dy * dy);
      const bite = 16 - (dy + 1) * (dy + 1);
      const right = bite > 0 ? mx + 2 - Math.sqrt(bite) : mx + outer;
      if (right > mx - outer) r(mx - outer, 10 + dy, right - mx + outer, 1, "#f4f0d8");
    }
    const cut = (x, y, w, h, alpha = 1) => {
      ctx.globalCompositeOperation = "destination-out";
      r(x, y, w, h, `rgba(0,0,0,${alpha})`);
      ctx.globalCompositeOperation = "source-over";
    };
    for (const l of plan.lights) {
      cut(l.x, l.y, l.w, l.h);
      r(l.x, l.y, l.w, l.h, "rgba(248,208,110,0.6)");
    }
    if (plan.fire) {
      // the fire's light, in steps, like everything else here
      ctx.globalCompositeOperation = "destination-out";
      for (const [rx, ry, a] of [[46, 26, 0.16], [32, 18, 0.2], [18, 10, 0.35]]) drawHabitatDisc(r, plan.fire.x, plan.fire.y - 2, rx, ry, `rgba(0,0,0,${a})`);
      ctx.globalCompositeOperation = "source-over";
      drawHabitatDisc(r, plan.fire.x, plan.fire.y - 2, 30, 16, "rgba(244,150,70,0.07)");
    }
    return canvas;
  }

  function animate(scene, ctx, tick) {
    const r = habitatPainter(ctx, scene.px);
    const { plan } = scene;
    for (const s of plan.smokes || []) wisps(r, s.x, s.y, s.s, tick);
    const f = plan.fire;
    if (f) {
      wisps(r, f.x, f.y - 12, 1.2, tick);
      const lick = tick % 3;
      r(f.x - 3, f.y - 5, 6, 4, "#e8622e");
      r(f.x - 2 - (lick === 1 ? 1 : 0), f.y - 8, 4, 4, "#f4823a");
      r(f.x - 1 + (lick === 2 ? 1 : 0), f.y - 10 - lick % 2, 2, 3, "#f4c84a");
      r(f.x - 1, f.y - 5, 2, 3, "#fbeeb0");
    }
  }

  function wisps(r, x, y, s, tick) {
    for (let i = 0; i < 5; i++) {
      const up = ((tick / 2 + i * 5) % 24);
      const a = 0.5 * (1 - up / 24);
      r(x + Math.sin((up + i) / 4) * 2 * s, y - up * s, 1.6 * s, 1.6 * s, `rgba(240,236,228,${a.toFixed(2)})`);
    }
  }

  // Tumble, the last Wanderpaw: a wizard in silver robes and a tall hat, feet at (x, y),
  // with an orb for each of the five lands bobbing over his hat, in their ring.
  function tumble(r, x, y, tick, orbs) {
    const silver = "#c9ced8";
    const light = "#e8ebf0";
    const shade = "#9299a8";
    const dark = "#6b7282";
    const hat = "#8f96a6";
    r(x - 11, y - 1, 22, 2, "rgba(40, 30, 20, 0.28)"); // his shadow
    // the robe, wider toward the hem, lit from the left
    for (let i = 0; i < 20; i++) {
      const half = 4 + Math.round((i / 19) * 6);
      const top = y - 20 + i;
      r(x - half, top, 2 * half, 1, silver);
      r(x - half, top, 2, 1, light);
      r(x + half - 3, top, 3, 1, shade);
      r(x - half - 1, top, 1, 1, dark);
      r(x + half, top, 1, 1, dark);
    }
    r(x - 10, y - 2, 20, 2, shade); // the hem, with the toes of his boots
    r(x - 6, y, 4, 1, "#4a3a30");
    r(x + 2, y, 4, 1, "#4a3a30");
    r(x - 6, y - 11, 12, 2, dark); // his belt
    r(x - 1, y - 11, 2, 2, "#e8b33e");
    // his sleeves, and a hand out to the side with a staff
    r(x - 9, y - 17, 3, 7, shade);
    r(x - 10, y - 11, 3, 2, "#e8c8a0");
    r(x + 6, y - 17, 4, 5, silver);
    r(x + 9, y - 14, 3, 2, "#e8c8a0");
    r(x + 11, y - 26, 2, 27, "#6e4a2a");
    r(x + 11, y - 26, 1, 27, "#8b5a2b");
    // his face and big white beard
    r(x - 4, y - 25, 8, 5, "#e8c8a0");
    r(x - 3, y - 24, 2, 2, "#3b2417");
    r(x + 1, y - 24, 2, 2, "#3b2417");
    r(x - 3, y - 24, 1, 1, "#ffffff");
    r(x + 1, y - 24, 1, 1, "#ffffff");
    for (let i = 0; i < 8; i++) {
      const half = 5 - Math.floor(i / 2);
      r(x - half, y - 21 + i, 2 * half, 1, i % 3 === 2 ? "#dcd8cc" : "#f6f3ea");
    }
    // his tall hat, bending a little at the tip, and its band
    r(x - 9, y - 27, 18, 2, dark);
    r(x - 8, y - 28, 16, 1, hat);
    for (let i = 0; i < 12; i++) {
      const half = Math.max(1, 5 - Math.floor(i / 2.6));
      const lean = i > 8 ? i - 8 : 0;
      r(x - half + lean, y - 29 - i, 2 * half, 1, hat);
      r(x - half + lean, y - 29 - i, 1, 1, silver);
    }
    r(x - 5, y - 31, 10, 2, "#6a5ab8");
    r(x - 1, y - 31, 2, 2, "#f4d35e");
    // the five orbs, in an arc over his hat
    orbs.forEach((color, i) => {
      const off = i - (orbs.length - 1) / 2;
      const ox = x + off * 8;
      const oy = y - 47 + off * off * 2 + Math.round(Math.sin(tick / 5 + i * 1.3));
      drawHabitatDisc(r, ox, oy, 4, 4, `${color}44`); // its glow
      drawHabitatDisc(r, ox, oy, 2, 2, color);
      r(ox - 1, oy - 1, 1, 1, "#ffffff");
    });
  }

  function shade(scene, ctx) {
    if (scene.nightLayer) ctx.drawImage(scene.nightLayer, 0, 0);
  }

  return { build, animate, shade, tumble, BIOMES, REGIONS };
})();
