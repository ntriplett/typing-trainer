// The Dressing Room's close-ups (bedroom.js views): step up to a station
// and everything you own is there to try, with a mirror showing you.
//   closet       shirts and dresses on rails, pants on hangers, shoes on a shelf
//   hats         hats on pegs
//   accessories  things to carry on a pegboard
//   mirror       the vanity: hair styles on wig stands, hair dyes, skin
//                powders, eye colors, boy or girl, and your name plate
// Click something to put it on (click a hat or accessory you're wearing to
// take it off). Wearing uses the store's equip API; looks are
// PUT /api/appearance (app/appearance.py).
//
// Needs sprites.js, wardrobe.js, avatar.js, house_scenes.js; bedroom.js's
// House is used once the page runs.

const DRESS_INK = "#3b2417";
const GLOW = "rgba(246, 212, 101, 0.55)";
const RACK_LEFT = 6;
const RACK_RIGHT = 118; // the mirror stands to the right
const RACK_GAP = 6;

// What the close-ups know: /api/wardrobe and /api/appearance.
const Dress = { wardrobe: null, options: null, page: 0 };

async function loadDress() {
  const [wardrobe, look] = await Promise.all([House.call("/api/wardrobe"), House.call("/api/appearance")]);
  Dress.wardrobe = wardrobe;
  Dress.options = look.options;
  Dress.name = look.learner.name;
}

// --- one item, on its own ----------------------------------------------------------

// An item's sprite as rects in avatar pixels, and the box around them.
const itemCache = new Map();
function itemArt(id) {
  if (!itemCache.has(id)) {
    const rects = [];
    const sprite = spriteFor(id);
    const rec = (x, y, w, h, c) => rects.push([x, y, w, h, c]);
    if (sprite && sprite.draw) sprite.draw(rec, false);
    else if (sprite) drawGrid(rec, sprite, 0);
    const xs = rects.flatMap(([x, , w]) => [x, x + w]);
    const ys = rects.flatMap(([, y, , h]) => [y, y + h]);
    const box = rects.length ? { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) } : { x: 0, y: 0, w: 6, h: 6 };
    itemCache.set(id, { rects, box });
  }
  return itemCache.get(id);
}

// Draws item `id` with its top-left at (x, y).
function paintItem(r, id, x, y) {
  const { rects, box } = itemArt(id);
  for (const [rx, ry, w, h, c] of rects) r(x + rx - box.x, y + ry - box.y, w, h, c);
}

// You, in a standing mirror at the right of a close-up.
function drawStandingMirror(r) {
  r(122, 6, 36, 84, DRESS_INK);
  r(123, 7, 34, 82, "#c8a030");
  r(124, 8, 32, 2, "#f0d470");
  r(125, 11, 30, 74, "#cfe6ee");
  r(125, 66, 30, 19, "#bcd8e2"); // the floor reflected
  r(127, 13, 1, 10, "#ffffff");
  r(129, 13, 1, 4, "#ffffff");
  const glass = { x0: 125, y0: 11, x1: 155, y1: 85 };
  const ox = 116, oy = 39; // the avatar's 48x48 frame: feet land ~y 82
  paintAvatar((x, y, w, h, c) => {
    const x0 = Math.max(ox + x, glass.x0), y0 = Math.max(oy + y, glass.y0);
    const x1 = Math.min(ox + x + w, glass.x1), y1 = Math.min(oy + y + h, glass.y1);
    if (x1 > x0 && y1 > y0) r(x0, y0, x1 - x0, y1 - y0, c);
  }, House.avatar, { background: false, pets: false, frame: House.frame });
  r(126, 89, 4, 1, DRESS_INK);
  r(150, 89, 4, 1, DRESS_INK);
}

// --- racks: rows of things to wear --------------------------------------------------

// rows: [slot, y, kind]; a kind is how things hang: "rail" (on hangers below
// the rail at y), "shelf" (standing on a shelf at y), "pegs" (sitting on a
// peg at y), "hooks" (hanging from a hook at y). A slot can have several
// rows; whatever doesn't fit goes on the next page.
const RACKS = {
  closet: {
    title: "Closet",
    hint: "Click something to put it on. Your mirror shows how it looks.",
    rows: [["shirt", 5, "rail"], ["shirt", 27, "rail"], ["pants", 50, "rail"], ["shoes", 80, "shelf"]],
    back: drawClosetInside,
  },
  hats: {
    title: "Hat Stand",
    hint: "Click a hat to put it on. Click the one you're wearing to take it off.",
    rows: [["hat", 24, "pegs"], ["hat", 50, "pegs"], ["hat", 76, "pegs"]],
    back: drawHatWall,
  },
  accessories: {
    title: "Accessory Corner",
    hint: "Click something to carry it. Click the one you have to put it back.",
    rows: [["accessory", 8, "hooks"], ["accessory", 36, "hooks"], ["accessory", 64, "hooks"]],
    back: drawPegboard,
  },
};

// Lays a rack's items out: [{id, name, slot, x, y, w, h}] per page.
function rackPages(rack) {
  const pages = [[]];
  const queues = {};
  for (const [slot] of rack.rows) queues[slot] = queues[slot] || [...Dress.wardrobe.slots[slot]];
  while (true) {
    let placed = false;
    for (const [slot, y, kind] of rack.rows) {
      let x = RACK_LEFT;
      while (queues[slot].length) {
        const item = queues[slot][0];
        const { box } = itemArt(item.id);
        if (x + box.w > RACK_RIGHT) break;
        queues[slot].shift();
        const top = kind === "rail" ? y + 3 : kind === "hooks" ? y + 3 : y - box.h + (kind === "pegs" ? 2 : 0);
        pages[pages.length - 1].push({ ...item, slot, x, y: top, w: box.w, h: box.h, kind, rowY: y });
        x += box.w + RACK_GAP;
        placed = true;
      }
    }
    if (!Object.values(queues).some((q) => q.length) || !placed) break;
    pages.push([]);
  }
  return pages;
}

function rackView(key) {
  const rack = RACKS[key];
  const worn = (item) => House.avatar[item.slot] === item.id;
  return {
    title: rack.title,
    hint: rack.hint,
    back: "dressing",
    enter: async () => {
      Dress.page = 0;
      await loadDress();
    },
    draw() {
      const r = House.px;
      rack.back(r, rack);
      const pages = rackPages(rack);
      const items = pages[Math.min(Dress.page, pages.length - 1)];
      for (const it of items) {
        if (it.kind === "rail") {
          const cx = it.x + it.w / 2;
          r(cx, it.rowY + 1, 1, 1, "#8a8278");
          r(cx - 3, it.rowY + 2, 7, 1, "#8b5a2b");
        } else if (it.kind === "hooks") {
          r(it.x + it.w / 2, it.rowY, 1, 3, "#5c3a1a");
        }
        if (worn(it)) r(it.x - 1.5, it.y - 1.5, it.w + 3, it.h + 3, GLOW);
        paintItem(r, it.id, it.x, it.y);
      }
      if (pages.length > 1) drawPageArrows(r, Math.min(Dress.page, pages.length - 1), pages.length);
      drawStandingMirror(r);
    },
    spots() {
      const pages = rackPages(rack);
      Dress.page = Math.min(Dress.page, pages.length - 1);
      if (!pages[0].length) House.say("Nothing here yet. Find some in the store!");
      const out = pages[Dress.page].map((it) =>
        House.spot(it.name, { x: it.x - 1, y: it.y - 1, w: it.w + 2, h: it.h + 2 }, () => wear(it, worn(it)), it.id)
      );
      if (pages.length > 1) {
        const { back, next } = PAGE_ARROWS;
        if (Dress.page > 0) out.push(House.spot("Back", { x: back.x - 1, y: back.y - 1, w: back.w + 2, h: back.h + 2 }, () => turnPage(-1), "page-back"));
        if (Dress.page < pages.length - 1) out.push(House.spot("More", { x: next.x - 1, y: next.y - 1, w: next.w + 2, h: next.h + 2 }, () => turnPage(1), "page-next"));
      }
      return out;
    },
  };
}

// Wooden arrow signs along the bottom when there's more than fits, and a
// dot for each page (the gold one is this page).
const PAGE_ARROWS = { back: { x: 2, y: 83, w: 26, h: 7 }, next: { x: 92, y: 83, w: 26, h: 7 } };

function drawPageArrows(r, page, count) {
  // a signpost: a plank with a pointed end, a dark triangle painted on it
  const arrow = ({ x, y, w, h }, dir, on) => {
    const ink = on ? DRESS_INK : "rgba(59, 36, 23, 0.3)";
    const wood = on ? "#e8b33e" : "rgba(232, 179, 62, 0.25)";
    const tip = (h + 1) / 2; // the point is as long as half the height
    const len = w - tip;
    const x0 = dir > 0 ? x : x + tip;
    const col = (i) => (dir > 0 ? x0 + len + i : x0 - 1 - i);
    r(x0, y, len, h, ink);
    for (let i = 0; i < tip; i++) r(col(i), y + i, 1, h - 2 * i, ink);
    r(x0 + (dir > 0 ? 1 : 0), y + 1, len - 1, h - 2, wood);
    for (let i = 0; i < tip - 1; i++) r(col(i), y + 1 + i, 1, h - 2 - 2 * i, wood);
    if (!on) return;
    r(x0 + 1, y + 1, len - 2, 1, "#f6d465");
    const start = x0 + len / 2 - dir;
    for (let i = 0; i < 2; i++) r(start + dir * i, y + 2 + i, 1, h - 4 - 2 * i, DRESS_INK); // a little painted triangle
  };
  arrow(PAGE_ARROWS.back, -1, page > 0);
  arrow(PAGE_ARROWS.next, 1, page < count - 1);
  const left = 60 - count * 2.5;
  for (let i = 0; i < count; i++) {
    r(left + i * 5, 85, 3, 3, DRESS_INK);
    r(left + i * 5 + 0.5, 85.5, 2, 2, i === page ? "#f6d465" : "#8a8278");
  }
}

function turnPage(step) {
  Dress.page += step;
  House.refresh();
}

async function wear(item, wearing) {
  try {
    if (wearing && (item.slot === "hat" || item.slot === "accessory")) await House.call(`/api/store/unequip/${item.slot}`, "POST");
    else if (wearing) return House.say(`You're wearing the ${item.name}!`);
    else await House.call(`/api/store/equip/${item.id}`, "POST");
    House.say("");
  } catch (err) {
    House.say(err.message);
  }
  House.refresh();
}

// --- the racks' backgrounds ----------------------------------------------------------

function closetWall(r) {
  r(0, 0, 160, 90, "#efe0f2"); // the Dressing Room behind the mirror
  for (let x = 3; x < 160; x += 10) r(x, 0, 4, 90, "#e6d2ec");
}

function drawClosetInside(r) {
  closetWall(r);
  r(0, 0, 121, 90, "#4a2e18"); // inside the closet: dark boards
  for (let x = 8; x < 121; x += 12) r(x, 0, 1, 90, "#3e2614");
  r(0, 0, 121, 3, "#3a2210");
  r(119, 0, 3, 90, DRESS_INK);
  for (const [, y, kind] of RACKS.closet.rows) {
    if (kind === "rail") {
      r(2, y, 116, 1, "#d8d0c0");
      r(2, y + 1, 116, 0.5, "#8a8278");
      r(2, y - 1, 2, 3, "#8b5a2b");
      r(116, y - 1, 2, 3, "#8b5a2b");
    } else {
      r(0, y, 120, 3, "#8b5a2b");
      r(0, y, 120, 1, "#b07a43");
      r(0, y + 3, 120, 7, "#3a2210");
    }
  }
}

function drawHatWall(r) {
  closetWall(r);
  r(0, 0, 121, 90, "#f4e4d0");
  for (let x = 4; x < 121; x += 8) r(x, 0, 3, 90, "#ecd8c0");
  r(119, 0, 3, 90, "#8b5a2b");
  for (const [, y] of RACKS.hats.rows) {
    r(2, y + 2, 116, 4, DRESS_INK); // a peg board under each row
    r(3, y + 3, 114, 2, "#a0703a");
    for (let x = 12; x < 116; x += 22) r(x, y + 2, 2, 1, "#5c3a1a");
  }
}

function drawPegboard(r) {
  closetWall(r);
  r(0, 0, 121, 90, "#8b5a2b");
  r(2, 2, 116, 86, "#e8d3a8");
  for (let y = 5; y < 88; y += 4) for (let x = 5; x < 118; x += 4) r(x, y, 1, 1, "#c8b088");
  r(119, 0, 3, 90, DRESS_INK);
}

// --- the mirror: your looks ------------------------------------------------------------

const LOOK_NAMES = {
  short: "Short hair", medium: "Medium hair", long: "Long hair", boy: "Boy", girl: "Girl",
};
const title = (id) => id.charAt(0).toUpperCase() + id.slice(1);

// Where each choice sits at the vanity.
function mirrorChoices() {
  const o = Dress.options;
  const look = House.avatar.appearance;
  const out = [];
  o.hair_style.forEach((id, i) => out.push({ field: "hair_style", id, name: LOOK_NAMES[id], x: 5 + i * 16, y: 11, w: 14, h: 14 }));
  o.gender.forEach((id, i) => out.push({ field: "gender", id, name: LOOK_NAMES[id], x: 11 + i * 18, y: 35, w: 14, h: 14 }));
  o.hair_color.forEach(({ id, unlocked }, i) => out.push({ field: "hair_color", id, unlocked, name: `${title(id)} hair`, x: 9 + i * 4, y: 51, w: 3, h: 7 }));
  o.skin.forEach((id, i) => out.push({ field: "skin", id, name: `${title(id)} skin`, x: 110 + i * 8, y: 54, w: 6, h: 4 }));
  o.eye_color.forEach((id, i) => out.push({ field: "eye_color", id, name: `${title(id)} eyes`, x: 112 + i * 9, y: 25, w: 7, h: 5 }));
  return out.map((c) => ({ ...c, chosen: look[c.field] === c.id, unlocked: c.unlocked ?? true }));
}

// The avatar's head and shoulders with a different look, small.
function paintHead(r, appearance, x, y) {
  const crop = { x: 10, y: 2, w: 28, h: 28 };
  const s = 0.5;
  paintAvatar((ax, ay, w, h, c) => {
    const x0 = Math.max(ax, crop.x), y0 = Math.max(ay, crop.y);
    const x1 = Math.min(ax + w, crop.x + crop.w), y1 = Math.min(ay + h, crop.y + crop.h);
    if (x1 > x0 && y1 > y0) r(x + (x0 - crop.x) * s, y + (y0 - crop.y) * s, (x1 - x0) * s, (y1 - y0) * s, c);
  }, { ...House.avatar, hat: null, accessory: null, appearance }, { background: false, pets: false });
}

function drawVanity(r) {
  const avatar = House.avatar;
  const look = avatar.appearance;
  closetWall(r);
  r(0, 54, 160, 2, "#8b5a2b");
  r(0, 56, 160, 34, "#c89a60");
  for (let y = 61; y < 90; y += 6) r(0, y, 160, 1, "#b0844c");

  // the big oval mirror, you in it
  r(58, 1, 44, 55, "#8a6418");
  r(55, 4, 50, 49, "#8a6418");
  r(59, 2, 42, 53, "#c8a030");
  r(56, 5, 48, 47, "#c8a030");
  r(60, 4, 40, 49, "#cfe6ee");
  r(58, 7, 44, 43, "#cfe6ee");
  r(62, 7, 1, 10, "#ffffff");
  r(64, 7, 1, 4, "#ffffff");
  const glass = { x0: 58, y0: 4, x1: 102, y1: 53 };
  paintAvatar((x, y, w, h, c) => {
    const x0 = Math.max(56 + x, glass.x0), y0 = Math.max(6 + y, glass.y0);
    const x1 = Math.min(56 + x + w, glass.x1), y1 = Math.min(6 + y + h, glass.y1);
    if (x1 > x0 && y1 > y0) r(x0, y0, x1 - x0, y1 - y0, c);
  }, avatar, { background: false, pets: false, frame: House.frame });

  // shelves: wig stands (hair styles), portraits (boy or girl), eye colors
  for (const [x0, x1, y] of [[2, 52, 26], [2, 52, 50], [108, 156, 31]]) {
    r(x0, y, x1 - x0, 2, "#8b5a2b");
    r(x0, y, x1 - x0, 1, "#b07a43");
    r(x0 + 2, y + 2, 1, 2, DRESS_INK);
    r(x1 - 3, y + 2, 1, 2, DRESS_INK);
  }
  for (const c of mirrorChoices()) {
    if (c.chosen) r(c.x - 1.5, c.y - 1.5, c.w + 3, c.h + 3, GLOW);
    if (c.field === "hair_style") {
      r(c.x + 5, c.y + 13, 4, 1, "#5c3a1a"); // the stand
      paintHead(r, { ...look, hair_style: c.id }, c.x, c.y);
    } else if (c.field === "gender") {
      r(c.x - 1, c.y - 1, c.w + 2, c.h + 2, "#c8a030");
      r(c.x, c.y, c.w, c.h, "#f4ead2");
      paintHead(r, { ...look, gender: c.id }, c.x, c.y);
    } else if (c.field === "hair_color") {
      const [main, dark] = HAIR_COLORS[c.id];
      r(c.x, c.y + 2, c.w, c.h - 2, c.unlocked ? main : "#d8d0c8");
      r(c.x + 2, c.y + 2, 1, c.h - 2, c.unlocked ? dark : "#b8b0a8");
      r(c.x + 1, c.y, 1, 2, DRESS_INK); // its cap
      if (!c.unlocked) r(c.x + 1, c.y + 4, 1, 1, DRESS_INK);
    } else if (c.field === "skin") {
      r(c.x, c.y + 1, c.w, c.h - 1, DRESS_INK); // a powder compact
      r(c.x + 1, c.y + 1, c.w - 2, c.h - 2, SKIN_TONES[c.id][0]);
      r(c.x, c.y - 2, c.w, 3, "#e8b33e"); // its open lid
      r(c.x + 1, c.y - 1, c.w - 2, 1, "#cfe6ee");
    } else if (c.field === "eye_color") {
      r(c.x, c.y + 1, c.w, c.h - 2, "#ffffff");
      r(c.x + 1, c.y, c.w - 2, c.h, "#ffffff");
      r(c.x + 2, c.y + 1, 3, 3, EYE_COLORS[c.id]);
      r(c.x + 3, c.y + 2, 1, 1, DRESS_INK);
      r(c.x, c.y, 1, 1, DRESS_INK);
    }
  }

  // the vanity table, its name plate, and a stool
  r(6, 58, 148, 4, DRESS_INK);
  r(7, 58, 146, 3, "#a0703a");
  r(7, 58, 146, 1, "#c48a50");
  r(10, 62, 140, 12, DRESS_INK);
  r(11, 62, 138, 11, "#8b5a2b");
  r(30, 66, 3, 1, "#e8b33e");
  r(127, 66, 3, 1, "#e8b33e");
  r(60, 63, 40, 9, "#5c3a1a");
  r(61, 64, 38, 7, "#e8d3a8");
  r(12, 74, 2, 14, DRESS_INK);
  r(146, 74, 2, 14, DRESS_INK);
  r(70, 78, 20, 3, DRESS_INK);
  r(71, 78, 18, 2, "#e87aa8");
  r(72, 81, 1, 7, DRESS_INK);
  r(87, 81, 1, 7, DRESS_INK);
}

// New players come here from the welcome screen (?setup=1); next is the
// placement questions.
const SETUP = new URLSearchParams(location.search).has("setup");

const mirrorView = {
  title: "Vanity Mirror",
  hint: "Try a new hair style or color, skin, eyes, and more. Click your name plate to change your name.",
  back: "dressing",
  nav: () => (SETUP ? [["Next", "/placement"]] : []),
  enter: loadDress,
  draw: () => drawVanity(House.px),
  spots() {
    const out = mirrorChoices().map((c) =>
      House.spot(c.unlocked ? c.name : `${c.name}: a hair dye from the store`, { x: c.x - 1, y: c.y - 2, w: c.w + 2, h: c.h + 3 }, () => chooseLook(c), `${c.field}-${c.id}`)
    );
    out.push(namePlate());
    return out;
  },
};

async function chooseLook(choice) {
  if (!choice.unlocked) return House.say(`${choice.name} is a hair dye. Find it in the store!`);
  try {
    await House.call("/api/appearance", "PUT", { ...House.avatar.appearance, [choice.field]: choice.id });
    House.say("");
  } catch (err) {
    House.say(err.message);
  }
  House.refresh();
}

// Your name, carved on the plate under the mirror: click it to change it.
function namePlate() {
  const input = document.createElement("input");
  input.className = "name-plate";
  input.id = "name-plate";
  input.maxLength = 20;
  input.value = Dress.name;
  input.setAttribute("aria-label", "Your name");
  Object.assign(input.style, { left: `${(61 / 160) * 100}%`, top: `${(64 / 90) * 100}%`, width: `${(38 / 160) * 100}%`, height: `${(7 / 90) * 100}%` });
  const save = async () => {
    const name = input.value.trim();
    if (!name || name === Dress.name) return void (input.value = Dress.name);
    try {
      const data = await House.call("/api/me/name", "PUT", { name });
      Dress.name = data.learner.name;
      House.say(`Hi, ${Dress.name}!`);
    } catch (err) {
      House.say(err.message);
      input.value = Dress.name;
    }
  };
  input.addEventListener("change", save);
  input.addEventListener("keydown", (e) => e.key === "Enter" && input.blur());
  return input;
}

const HOUSE_VIEWS = {
  closet: rackView("closet"),
  hats: rackView("hats"),
  accessories: rackView("accessories"),
  mirror: mirrorView,
};
