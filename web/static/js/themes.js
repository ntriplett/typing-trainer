// Page themes (PLAN.md 11c-2): the equipped place re-themes the whole page
// -- its scenery behind everything (scenery.js), the top bar, and drifting
// particles -- and a night unlock switches the UI to dark mode (theme.css
// :root[data-night]).
//
// applyTheme(avatar) is called by header.js whenever the avatar changes.
// Every page has its scenery. Particles float in front of everything, so only pages
// with <body data-particles> get them (not where you type).

// page: background color, grain: its speckle color, bar: top bar color,
// particles: [kind, colors] -- see PARTICLE_KINDS.
const PLACE_THEMES = {
  bg_meadow: { page: "#f3e2bf", grain: "#e8d3a8", bar: "#5c3a1a", particles: ["fluff", ["#ffffff", "#f4ead2"]] },
  bg_flower_forest: { page: "#f1e6c6", grain: "#e3d4ad", bar: "#4f6b3a", particles: ["petal", ["#f6aacb", "#ffffff", "#f6d465"]] },
  bg_autumn_forest: { page: "#ead0a2", grain: "#d8b886", bar: "#4a2a14", particles: ["leaf", ["#b8432f", "#c4502a", "#d9822b", "#e8b33e"]] },
  bg_pine_forest: { page: "#e6e2c8", grain: "#d4d0b0", bar: "#2f4a2d", particles: ["needle", ["#5c7a3a", "#7a5636"]] },
  bg_cherry_grove: { page: "#f6e2dc", grain: "#ecd0c8", bar: "#6b3a4a", particles: ["petal", ["#f2a6c0", "#fbd0de"]] },
  bg_jungle: { page: "#e2e6c4", grain: "#d0d6ac", bar: "#2f5a2a", particles: ["leaf", ["#4f9a3a", "#86c46a"]] },
  bg_beach: { page: "#f6e6c0", grain: "#ead6a6", bar: "#4f6f80", particles: ["sand", ["#e0c890", "#fbf1dc"]] },
  bg_river: { page: "#e8ecd6", grain: "#d6dcc0", bar: "#3f6a7a", particles: ["drop", ["#a8dcf0"]] },
  bg_waterfall: { page: "#e4ece6", grain: "#d0dcd6", bar: "#4a5a5a", particles: ["drop", ["#e8f6fc", "#a8dcf0"]] },
  bg_under_sea: { page: "#d6e8ec", grain: "#c0dae0", bar: "#24506a", particles: ["bubble", ["#e8f6fc", "#a8dcf0"]] },
  bg_swamp: { page: "#e0e2c8", grain: "#cdd0b0", bar: "#3a4a2a", particles: ["spore", ["#c8d8a0", "#a8b880"]] },
  bg_desert: { page: "#f6e0b0", grain: "#ebcc90", bar: "#8a5a2a", particles: ["sand", ["#e0aa58", "#c8913f"]] },
  bg_badlands: { page: "#f2d4b4", grain: "#e4bc94", bar: "#7a3a1a", particles: ["sand", ["#c4673a", "#e8a66a"]] },
  bg_tundra: { page: "#eef2f4", grain: "#dce4ea", bar: "#3f5a6a", particles: ["snow", ["#ffffff", "#e2eef8"]] },
  bg_mushroom_island: { page: "#ece0ea", grain: "#dccbda", bar: "#5a3a5a", particles: ["spore", ["#f6d465", "#ff8a9a"]] },
  bg_space: { page: "#dcdcec", grain: "#c8c8dc", bar: "#1c1e3a", particles: ["star", ["#f6e27a", "#9ae6f0"]] },
  bg_moon: { page: "#e4e4e8", grain: "#d0d0d6", bar: "#2a2c40", particles: ["star", ["#ffffff", "#f6e27a"]] },
  bg_mars: { page: "#f2d6c4", grain: "#e4bca4", bar: "#6a2a1a", particles: ["sand", ["#c4602e", "#8e3f22"]] },
};

// At night every place shares the dark palette; particles follow the
// place group (forests get fireflies, everything else stars).
const NIGHT_THEME = { page: "#1b1f30", grain: "#242a42", bar: "#14121e" };
const NIGHT_PARTICLES = {
  forests: ["firefly", ["#f6e27a", "#c8f07a"]],
  water: ["star", ["#fff6d8", "#9ae6f0"]],
  wild: ["star", ["#fff6d8", "#f6e27a"]],
  space: ["star", ["#ffffff", "#9ae6f0", "#f6aacb"]],
};
const PLACE_GROUP = {
  forests: ["bg_meadow", "bg_flower_forest", "bg_autumn_forest", "bg_pine_forest", "bg_cherry_grove", "bg_jungle"],
  water: ["bg_beach", "bg_river", "bg_waterfall", "bg_under_sea", "bg_swamp"],
  wild: ["bg_desert", "bg_badlands", "bg_tundra", "bg_mushroom_island"],
  space: ["bg_space", "bg_moon", "bg_mars"],
};

// Each kind: a pixel shape (rects on an 8x8 grid, "c" = the particle's
// color) and a motion class from theme.css. count = how many on screen.
const PARTICLE_KINDS = {
  leaf: { motion: "fall", count: 7, size: 21, rects: [[3, 0, 3, 1], [2, 1, 5, 3], [3, 4, 3, 1], [4, 1, 1, 6, "#5c3a1a"]] },
  petal: { motion: "fall", count: 9, size: 12, rects: [[1, 2, 5, 3], [2, 1, 3, 5]] },
  fluff: { motion: "fall", count: 6, size: 12, rects: [[3, 1, 2, 6], [1, 3, 6, 2]] },
  needle: { motion: "fall", count: 8, size: 15, rects: [[3, 0, 1, 7]] },
  snow: { motion: "fall", count: 14, size: 9, rects: [[2, 2, 4, 4]] },
  drop: { motion: "fall", count: 10, size: 12, rects: [[3, 1, 2, 5]] },
  sand: { motion: "blow", count: 12, size: 6, rects: [[2, 2, 4, 4]] },
  bubble: { motion: "rise", count: 9, size: 15, rects: [[2, 0, 4, 1], [2, 7, 4, 1], [0, 2, 1, 4], [7, 2, 1, 4], [1, 1, 1, 1], [6, 1, 1, 1], [1, 6, 1, 1], [6, 6, 1, 1], [2, 2, 1, 1, "#ffffff"]] },
  spore: { motion: "rise", count: 8, size: 9, rects: [[2, 2, 4, 4]] },
  star: { motion: "twinkle", count: 14, size: 12, rects: [[3, 0, 2, 8], [0, 3, 8, 2]] },
  firefly: { motion: "wander", count: 10, size: 9, rects: [[2, 2, 4, 4], [3, 3, 2, 2, "#ffffff"]] },
};

function pixelSvg(rects, color, background) {
  const body = rects
    .map(([x, y, w, h, c]) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${c || color}"/>`)
    .join("");
  const bg = background ? `<rect width="8" height="8" fill="${background}"/>` : "";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8" shape-rendering="crispEdges">${bg}${body}</svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
}

function groupOf(placeId) {
  return Object.keys(PLACE_GROUP).find((g) => PLACE_GROUP[g].includes(placeId)) || "forests";
}

function applyTheme(avatar) {
  const place = avatar.background || "bg_meadow";
  const night = Boolean(avatar.night);
  const theme = night ? NIGHT_THEME : PLACE_THEMES[place] || PLACE_THEMES.bg_meadow;
  const root = document.documentElement;

  root.toggleAttribute("data-night", night);
  root.style.setProperty("--page-bg", theme.page);
  root.style.setProperty("--topbar", theme.bar);
  // the sand grain tile, recolored: speckles on the place's page color
  const grain = [[1, 2, 1, 1, theme.grain], [5, 1, 1, 1, theme.grain], [6, 5, 1, 1, theme.grain], [2, 6, 1, 1, theme.grain]];
  root.style.backgroundImage = pixelSvg(grain, theme.grain, theme.page);

  if (window.renderScenery) renderScenery(place, night);

  const particles = night ? NIGHT_PARTICLES[groupOf(place)] : (PLACE_THEMES[place] || PLACE_THEMES.bg_meadow).particles;
  renderParticles(particles);
}

function renderParticles([kind, colors]) {
  if (!document.body.hasAttribute("data-particles")) return;
  let layer = document.querySelector(".particles");
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "particles";
    layer.setAttribute("aria-hidden", "true");
    document.body.prepend(layer);
  }
  const spec = PARTICLE_KINDS[kind];
  const spans = [];
  for (let i = 0; i < spec.count; i++) {
    const span = document.createElement("span");
    span.className = spec.motion;
    const color = colors[i % colors.length];
    span.style.backgroundImage = pixelSvg(spec.rects, color);
    span.style.width = span.style.height = `${spec.size}px`;
    // spread evenly with a little jitter so it never looks like a grid
    const spread = ((i + 0.5) / spec.count) * 100 + (Math.random() * 8 - 4);
    if (spec.motion === "blow") span.style.top = `${spread}%`;
    else span.style.left = `${spread}%`;
    if (spec.motion === "twinkle" || spec.motion === "wander") span.style.top = `${10 + Math.random() * 80}%`;
    const duration = { fall: 16, rise: 14, blow: 9, twinkle: 3, wander: 6 }[spec.motion];
    span.style.animationDuration = `${duration * (0.75 + Math.random() * 0.5)}s`;
    span.style.animationDelay = `${-Math.random() * duration}s`;
    spans.push(span);
  }
  layer.replaceChildren(...spans);
}
