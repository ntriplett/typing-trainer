// Wanderpaw's move tiles, the same everywhere they show: battles, the party
// book, level-ups and the move lab. A move comes from the server with its
// label, note and icons (battle.move_icons).

const TYPE_TINT = { ember: "#f6d5cf", splash: "#d4e5f6", leaf: "#dcecd0", dream: "#e6d8f1", shock: "#f9e5c6" };

// A word with what's typed so far shown.
function labelHtml(t) {
  const done = wanderPlain(t.word.slice(0, t.typed));
  const rest = wanderPlain(t.word.slice(t.typed));
  return `<kbd class="wander-word"><span class="done">${done}</span>${rest}</kbd>`;
}

// A move's icons: top right says what it does (>> for haste, circles for how
// hard it hits, a burst for each mark, a shield for protection), bottom right
// what it costs. Hover any for the details.
const SHIELD_ALL = "#55504a"; // dark gray: against every type

// Solid: protects you. A thick outline: your partner. Half and half: both.
function shieldSvg(who, types) {
  const a = types.length ? WanderMap.TYPE_COLORS[types[0]] : SHIELD_ALL;
  const b = types.length ? WanderMap.TYPE_COLORS[types[1] || types[0]] : SHIELD_ALL;
  const left = "M8 1.5 L1.5 3.8 V9 C1.5 13 4.8 15.8 8 17";
  const right = "M8 1.5 L14.5 3.8 V9 C14.5 13 11.2 15.8 8 17";
  const solid = (d, color) => `<path d="${d} Z" fill="${color}" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>`;
  const outline = (d, color) => `<path d="${d}" fill="none" stroke="${color}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>`;
  const parts = who === "you" ? solid(left, a) + solid(right, b) : who === "partner" ? outline(left, a) + outline(right, b) : solid(left, a) + outline(right, b);
  return `<svg class="wander-icon-shield" viewBox="0 0 16 18.5" width="15" height="17" aria-hidden="true">${parts}</svg>`;
}

// A mark: a little soft explosion.
function burstSvg(color) {
  return `<svg class="wander-icon-burst" viewBox="0 0 18 18" width="17" height="17" aria-hidden="true"><path d="M9 1 L10.6 5.4 L14.8 3 L13 7.4 L17 9 L13 10.6 L15 15 L10.6 12.8 L9 17 L7.4 12.8 L3 15 L5 10.6 L1 9 L5 7.4 L3.2 3 L7.4 5.4 Z" fill="${color}" stroke="${color}" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
}

// A mix: a square cut corner to corner, a triangle of each type, like a mix's tile.
function mixSvg(a = "#3a7fc8", b = "#c8382a") {
  return `<svg class="wander-icon-mix" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M1 1 H15 L1 15 Z" fill="${a}"/><path d="M15 1 V15 H1 Z" fill="${b}"/><rect x="1" y="1" width="14" height="14" fill="none" stroke="#3b2417" stroke-width="1.2"/></svg>`;
}

// A hit: the circles a move's card shows.
const hitDots = (color, count = 1) => `<span class="wander-icon-dots">${Array.from({ length: count }, () => `<i class="wander-icon-dot" style="background:${color}"></i>`).join("")}</span>`;

// Fast is the >> on a move's card; going last is the same, turned round.
const hasteIcon = (slow = false) => `<span class="wander-icon-haste">${slow ? "&laquo;" : "&raquo;"}</span>`;

// What an effect does, as a picture: the same in battle and in the guidebook,
// by the words either one uses for it. They share pictures by what they do
// until effects get their own.
const LOSES_TURN = (size) => itemIcon("Lost turn", size);
const HURTS = () => hitDots("#c8382a");
const SOFTER = (size) => itemIcon("Softer", size);
const GUARDED = () => shieldSvg("you", []);
const EFFECT_ICONS = {
  asleep: LOSES_TURN, rooted: LOSES_TURN, sleepy: LOSES_TURN, wired: LOSES_TURN, poppies: LOSES_TURN, lull: LOSES_TURN, "can't move": LOSES_TURN, wisp: LOSES_TURN,
  burning: HURTS, thorns: HURTS, brambles: HURTS, dizzy: HURTS, bubble: HURTS,
  "heavy blow": () => hitDots("#55504a", 2), sweep: () => hitDots("#55504a", 2),
  drenched: SOFTER, scalded: SOFTER,
  sanctuary: GUARDED, hardened: GUARDED, braced: GUARDED, ward: GUARDED,
  mending: () => ENERGY_ICON, "pets mending": () => ENERGY_ICON,
  focused: (size) => itemIcon("Focus", size),
};
const effectIcon = (name, size = 16) => (EFFECT_ICONS[name.toLowerCase()] || LOSES_TURN)(size);

function moveIcons(m) {
  const icons = m.icons;
  if (!icons) return "";
  const parts = [];
  if (icons.haste) parts.push(`<span class="wander-icon wander-icon-haste" data-icon="haste" title="${wanderPlain(icons.haste)}">&raquo;</span>`);
  if (icons.hit) {
    const [a, b] = [WanderMap.TYPE_COLORS[icons.hit.types[0]], WanderMap.TYPE_COLORS[icons.hit.types[1] || icons.hit.types[0]]];
    const dots = Array.from({ length: icons.hit.count }, () => `<i class="wander-icon-dot" style="background:linear-gradient(90deg, ${a} 50%, ${b} 50%)"></i>`).join("");
    parts.push(`<span class="wander-icon" data-icon="hit" title="${wanderPlain(icons.hit.tip)}">${dots}</span>`);
  }
  (icons.marks || []).forEach((mark) => {
    parts.push(`<span class="wander-icon" data-icon="mark" title="${wanderPlain(mark.tip)}">${burstSvg(WanderMap.TYPE_COLORS[mark.type])}</span>`);
  });
  if (icons.shield) {
    const s = icons.shield;
    const one = shieldSvg(s.who, s.types);
    parts.push(`<span class="wander-icon wander-icon-shields" data-icon="shield" data-who="${s.who}" title="${wanderPlain(s.tip)}">${one}${s.double ? one : ""}</span>`);
  }
  return parts.length ? `<span class="wander-move-icons">${parts.join("")}</span>` : "";
}

function moveCosts(m) {
  const cost = m.icons && m.icons.cost;
  if (!cost || !(cost.mana || cost.energy)) return "";
  const one = (n, icon, name) => (n ? `<span class="wander-icon" data-icon="${name}" title="${name === "mana" ? "Mana" : "Energy"} cost.">${n}${icon}</span>` : "");
  return `<span class="wander-move-cost">${one(cost.mana, MANA_ICON, "mana")}${one(cost.energy, ENERGY_ICON, "energy")}</span>`;
}

// What the creature will try next, above it: circles for an attack, and who at.
function intentHtml(i) {
  const color = i.type ? WanderMap.TYPE_COLORS[i.type] : "";
  const dots = Array.from({ length: i.count || 0 }, () => `<i class="wander-icon-dot" style="background:${color}"></i>`).join("");
  return `${dots}<small>${wanderText(i.name)}</small>`;
}

// Three across for six moves; four once a pet has more slots.
const gridSize = (moves) => (moves.length > 6 ? "wide" : "");

// A tile's border and background: its type's, half and half for a mix.
function tileStyle(m) {
  const color = m.type ? WanderMap.TYPE_COLORS[m.type] : "#8b7a5c";
  const tint = m.type ? TYPE_TINT[m.type] : "#efe6d2";
  return m.type2
    ? `background:linear-gradient(135deg, ${tint} 50%, ${TYPE_TINT[m.type2]} 50%);border-image:linear-gradient(135deg, ${color} 50%, ${WanderMap.TYPE_COLORS[m.type2]} 50%) 1`
    : `border-color:${color};background:${tint}`;
}

function moveCard(m, word, fresh = false) {
  const color = m.type ? WanderMap.TYPE_COLORS[m.type] : "#8b7a5c";
  const always = `<span class="wander-move-always">Always on</span>`;
  const slot = word === undefined ? (m.passive ? always : "") : `<span class="wander-move-word">${m.passive ? always : word ? labelHtml(word) : "&nbsp;"}</span>`;
  const paid = moveCosts(m) ? "paid" : "";
  return `<li class="wander-move ${m.can === false ? "off" : ""} ${fresh ? "fresh" : ""} ${paid}" data-move="${m.id}" style="${tileStyle(m)}">
    <div class="wander-move-head"><b class="wander-move-name" style="color:${color}">${wanderText(m.label)}</b>${moveIcons(m)}</div>
    ${slot}
    <span class="wander-move-note">${m.spent ? `<s>${wanderText(m.note)}</s> <b class="wander-used-up">Used up</b>` : wanderText(m.note)}</span>
    ${moveCosts(m)}</li>`;
}

function levelOption(o, i, picked) {
  const color = o.type ? WanderMap.TYPE_COLORS[o.type] : "#8b7a5c";
  const on = i === picked ? "on" : "";
  const paid = moveCosts(o) ? "paid" : "";
  return `<li class="wander-levelup-option ${on} ${paid}" data-option="${i}" style="${tileStyle(o)}">
    <small><kbd class="keycap">${i + 1}</kbd> ${wanderText(o.title)}</small>
    <div class="wander-move-head"><b style="color:${color}">${wanderText(o.label)}</b>${moveIcons(o)}</div>
    ${o.passive ? `<span class="wander-move-always">Always on</span>` : ""}
    <span class="wander-move-note">${wanderText(o.note)}</span>
    ${moveCosts(o)}
    ${o.replaces ? `<small>Replaces ${wanderText(o.replaces)}.${o.also ? ` ${wanderText(o.also)}` : ""}</small>` : ""}
  </li>`;
}
