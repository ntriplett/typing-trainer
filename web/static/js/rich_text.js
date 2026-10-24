// Shared by teach and practice pages: lesson text can mark keys as [F] or
// [Space], and those are drawn as keycaps.

function keycap(key) {
  const label = key === " " ? "Space" : key.length === 1 ? key.toUpperCase() : key;
  return `<kbd class="keycap">${escapeHtml(label)}</kbd>`;
}

function richText(text) {
  return escapeHtml(text).replace(/\[([^\]]+)\]/g, (_, k) => keycap(k === "Space" ? " " : k));
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
