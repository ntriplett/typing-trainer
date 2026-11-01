// Text the player reads in Wanderpaw: server strings and ours mark type names
// as tokens, "{ember}" (world.tw on the server), and this draws each one all
// caps in its type's color. Everything else in the string is escaped, so
// wanderText's result is safe for innerHTML.

const WANDER_TYPE_TOKEN = /\{(splash|ember|dream|leaf|shock)\}/g;
// Text colors: shock's orange is too light to read as words on our paper.
const WANDER_TYPE_TEXT = { shock: "#a86a10" };

function wanderText(text) {
  const safe = String(text ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
  return safe.replace(WANDER_TYPE_TOKEN, (_, kind) =>
    `<span class="type-word" style="color:${WANDER_TYPE_TEXT[kind] || WanderMap.TYPE_COLORS[kind]}">${kind.toUpperCase()}</span>`);
}
