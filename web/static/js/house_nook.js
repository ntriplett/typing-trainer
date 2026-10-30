// The Window Nook's close-ups (bedroom.js views): a postcard board per
// place group, and the day & night switch. Click a postcard of a place you
// own to go there (the store's equip API); the switch turns night on and off
// where you've unlocked it (PUT /api/me/night).
//
// Needs house_scenes.js (the art) and house_dressing.js (HOUSE_VIEWS);
// bedroom.js's House is used once the page runs.

const PLACE_GROUP_NAMES = { forests: "Forests", water: "Water", wild: "Wild Places", space: "Space" };
const CARD = { w: 36, h: 28, gap: 10, top: 12 };

// The group your current place is in.
function currentGroup() {
  return Object.keys(House.places || {}).find((g) => House.places[g].some((p) => p.current));
}

function nookSpots() {
  const s = NOOK_SPOTS;
  return [
    House.spot("Bedroom", s.bedroom, () => House.go("bedroom"), "bedroom"),
    ...Object.keys(NOOK_BOARDS).map((g) => House.spot(`${PLACE_GROUP_NAMES[g]} postcards`, s[g], () => House.go(`board-${g}`), g)),
    House.spot("The window", s.window, lookOutside, "window"),
    House.spot("Day & night", s.daynight, flipNight, "daynight"),
  ];
}

function lookOutside() {
  const here = Object.values(House.places || {}).flat().find((p) => p.current);
  House.say(here ? `You're at ${here.name}. ${House.avatar.night ? "What a starry night!" : "What a nice day!"}` : "");
}

async function flipNight() {
  const group = currentGroup();
  if (!group || !House.night[group]) {
    return House.say(`Night for ${group ? PLACE_GROUP_NAMES[group] : "this place"} is in the store (the Night tab).`);
  }
  try {
    await House.call("/api/me/night", "PUT", { on: !House.avatar.night });
    House.say(House.avatar.night ? "Goodnight! The stars are out." : "Good morning! The sun is up.");
  } catch (err) {
    House.say(err.message);
  }
  House.refresh();
}

// Where each postcard of a group goes on its big board: three across.
function cards(group) {
  const list = (House.places && House.places[group]) || [];
  const left = (160 - (3 * CARD.w + 2 * CARD.gap)) / 2;
  return list.map((p, i) => ({ ...p, x: left + (i % 3) * (CARD.w + CARD.gap), y: CARD.top + Math.floor(i / 3) * (CARD.h + CARD.gap) }));
}

function drawBigBoard(r, group) {
  r(0, 0, 160, 90, "#dfe8cc");
  r(2, 2, 156, 86, "#6b4423");
  r(4, 4, 152, 82, "#d8a868");
  for (let i = 0; i < 60; i++) r(6 + ((i * 37) % 148), 6 + ((i * 23) % 78), 1, 1, "#c08a50");
  const night = House.night && House.night[group];
  if (night) {
    r(143, 74, 10, 10, "#2a2c50"); // a moon sticker: night is unlocked here
    r(146, 76, 4, 6, "#f4ecc8");
    r(148, 76, 2, 3, "#2a2c50");
  }
  cards(group).forEach((c, i) => {
    r(c.x + 1, c.y + 1, CARD.w, CARD.h, "rgba(0, 0, 0, 0.25)");
    r(c.x, c.y, CARD.w, CARD.h, c.current ? "#f6d465" : "#fbf1dc");
    const pic = { x: c.x + 2, y: c.y + 2, w: CARD.w - 4, h: CARD.h - 4 };
    if (c.owned) housePlaceView(r, pic, null, 2 / 3, c.id);
    else {
      r(pic.x, pic.y, pic.w, pic.h, "#e8dcc0");
      for (const [x, y] of [[13, 6], [15, 6], [17, 7], [17, 9], [15, 11], [15, 12], [15, 15]]) r(pic.x + x, pic.y + y, 2, 2, "#c8b896");
    }
    r(c.x + CARD.w / 2 - 1, c.y - 2, 3, 3, ["#c8423a", "#4a7ec8", "#e8b33e"][i % 3]); // a pin
    if (c.current) {
      r(c.x + CARD.w - 7, c.y - 3, 6, 6, "#e8b33e"); // a gold star: you're here
      r(c.x + CARD.w - 5, c.y - 4, 2, 8, "#e8b33e");
      r(c.x + CARD.w - 8, c.y - 1, 8, 2, "#e8b33e");
    }
  });
}

function boardView(group) {
  return {
    title: `${PLACE_GROUP_NAMES[group]} Postcards`,
    hint: "Click a postcard to go there. The gold star is where you are now.",
    back: "nook",
    enter: () => House.loadPlaces(),
    draw: () => drawBigBoard(House.px, group),
    spots: () =>
      cards(group).map((c) =>
        House.spot(c.owned ? c.name : `${c.name}: find it in the store`, { x: c.x, y: c.y, w: CARD.w, h: CARD.h }, () => travel(c), c.id)
      ),
  };
}

async function travel(card) {
  if (!card.owned) return House.say(`${card.name} is in the store (the Places tab). Then come back and visit!`);
  if (card.current) return House.say(`You're already at ${card.name}!`);
  try {
    await House.call(`/api/store/equip/${card.id}`, "POST");
    await House.loadPlaces();
    House.say(`Welcome to ${card.name}!`);
  } catch (err) {
    House.say(err.message);
  }
  House.refresh();
}

Object.assign(HOUSE_VIEWS, Object.fromEntries(Object.keys(NOOK_BOARDS).map((g) => [`board-${g}`, boardView(g)])));
