// Text the player reads in Wanderpaw: server strings and ours mark type names
// as tokens, "{ember}" (world.tw on the server), and this draws each one all
// caps in its type's color. Everything else in the string is escaped, so
// wanderText's result is safe for innerHTML.

const WANDER_TYPE_TOKEN = /\{(splash|ember|dream|leaf|shock)\}/g;
// Icons for what a pet spends and earns: {energy}, {mana} and {xp} in text
// (terms.py) draw these in place of the word.
const MANA_ICON = `<svg class="wander-stat-icon" viewBox="0 0 12 14" width="12" height="14" aria-hidden="true"><path d="M6 0 C6 0 12 7 12 9.5 A6 4.5 0 0 1 0 9.5 C0 7 6 0 6 0 Z" fill="#3a7fc8"/></svg>`;
const ENERGY_ICON = `<svg class="wander-stat-icon" viewBox="0 0 12 14" width="12" height="14" aria-hidden="true"><path d="M7.5 0 L1 8 H5 L4 14 L11 5.5 H6.8 Z" fill="#6fae3e"/></svg>`;
const XP_ICON = `<svg class="wander-stat-icon" viewBox="0 0 14 14" width="14" height="14" aria-hidden="true"><path d="M7 0 L8.8 5.2 L14 7 L8.8 8.8 L7 14 L5.2 8.8 L0 7 L5.2 5.2 Z" fill="#e2a33c"/></svg>`;
// Text colors: shock's orange is too light to read as words on our paper.
const WANDER_TYPE_TEXT = { shock: "#a86a10" };

// The same text with no formatting, for tooltips.
function wanderPlain(text) {
  return String(text ?? "").replace(WANDER_TYPE_TOKEN, (_, kind) => kind.toUpperCase()).replace(/\{(energy|mana|xp)\}/g, "$1").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

function wanderText(text) {
  const safe = String(text ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
  return safe
    .replace(WANDER_TYPE_TOKEN, (_, kind) =>
      `<span class="type-word" style="color:${WANDER_TYPE_TEXT[kind] || WanderMap.TYPE_COLORS[kind]}">${kind.toUpperCase()}</span>`)
    .replace(/\{(energy|mana|xp)\}([.,!?]?)/g, (_, stat, mark) =>
      `<span class="wander-stat-word">${{ energy: ENERGY_ICON, mana: MANA_ICON, xp: XP_ICON }[stat]}${mark}</span>`);
}
