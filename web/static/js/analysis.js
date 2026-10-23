// The analysis page: 4 tabs (keyboard heatmap, fingers, letter pairs,
// trend), each rendered with plain HTML/CSS/SVG -- no charting
// library (PLAN.md Section 11a still defers real visual polish; this
// just needs to show the data clearly).

const KEYBOARD_ROWS = [
  ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";"],
  ["z", "x", "c", "v", "b", "n", "m", ",", ".", "/"],
];

const FINGER_LABELS = {
  left_pinky: "Left pinky",
  left_ring: "Left ring",
  left_middle: "Left middle",
  left_index: "Left index",
  right_index: "Right index",
  right_middle: "Right middle",
  right_ring: "Right ring",
  right_pinky: "Right pinky",
};
const FINGER_ORDER = Object.keys(FINGER_LABELS);

document.querySelectorAll(".tab-button").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

function showTab(name) {
  document.querySelectorAll(".tab-button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = p.id !== `tab-${name}`));
}

async function loadAll() {
  const [keys, fingers, bigrams, trend] = await Promise.all([
    fetch("/api/analytics/keys").then((r) => r.json()),
    fetch("/api/analytics/fingers").then((r) => r.json()),
    fetch("/api/analytics/bigrams").then((r) => r.json()),
    fetch("/api/analytics/trend").then((r) => r.json()),
  ]);
  renderKeyboard(keys);
  renderFingers(fingers);
  renderBigrams(bigrams);
  renderTrend(trend);
}

function accuracyColor(accuracy) {
  if (accuracy === null || accuracy === undefined) return null;
  const hue = Math.max(0, Math.min(1, accuracy)) * 120; // 0=red, 120=green
  return `hsl(${hue}, 65%, 45%)`;
}

function renderKeyboard(keys) {
  const byKey = {};
  keys.forEach((k) => (byKey[k.key] = k));

  const container = document.getElementById("keyboard");
  container.innerHTML = KEYBOARD_ROWS.map((row, i) => {
    const keyDivs = row
      .map((k) => {
        const entry = byKey[k];
        const color = entry ? accuracyColor(entry.accuracy) : null;
        const cls = color ? "" : "not-started";
        const style = color ? `style="background:${color}"` : "";
        const title = entry
          ? `${k}: ${entry.sample_count} attempts` +
            (entry.accuracy !== null ? `, ${Math.round(entry.accuracy * 100)}% accuracy` : ", not started")
          : k;
        return `<div class="kb-key ${cls}" ${style} title="${title}">${k}</div>`;
      })
      .join("");
    const indent = i * 0.8;
    return `<div class="kb-row" style="margin-left:${indent}rem">${keyDivs}</div>`;
  }).join("");
}

function renderFingers(fingers) {
  const container = document.getElementById("finger-bars");
  container.innerHTML = FINGER_ORDER.map((finger) => {
    const stat = fingers[finger];
    const accuracy = stat && stat.accuracy !== null ? stat.accuracy : 0;
    const label = stat && stat.accuracy !== null ? `${Math.round(accuracy * 100)}%` : "—";
    const widthPct = Math.round(accuracy * 100);
    return `
      <div class="finger-row">
        <div class="finger-label">${FINGER_LABELS[finger]}</div>
        <div class="finger-bar-track"><div class="finger-bar-fill" style="width:${widthPct}%"></div></div>
        <div class="finger-value">${label}</div>
      </div>`;
  }).join("");
}

function renderBigrams(bigrams) {
  const tbody = document.querySelector("#bigram-table tbody");
  if (bigrams.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4">Not enough practice yet to tell.</td></tr>`;
    return;
  }
  tbody.innerHTML = bigrams
    .map((b) => {
      const speed = b.ema_time_ms !== null ? Math.round(b.ema_time_ms) : "—";
      const accuracy = b.accuracy_rolling !== null ? `${Math.round(b.accuracy_rolling * 100)}%` : "—";
      return `<tr><td>${b.key1}${b.key2}</td><td>${accuracy}</td><td>${speed}</td><td>${b.sample_count}</td></tr>`;
    })
    .join("");
}

function renderTrend(trend) {
  const svg = document.getElementById("trend-chart");
  if (trend.length === 0) {
    svg.innerHTML = `<text x="300" y="100" text-anchor="middle" fill="#999">No sessions yet.</text>`;
    return;
  }

  const width = 600;
  const height = 200;
  const maxWpm = Math.max(...trend.map((t) => t.avg_wpm), 1) * 1.2;
  const step = trend.length > 1 ? width / (trend.length - 1) : 0;

  const wpmPoints = trend
    .map((t, i) => `${i * step},${height - (t.avg_wpm / maxWpm) * height}`)
    .join(" ");
  const accuracyPoints = trend
    .map((t, i) => `${i * step},${height - t.avg_accuracy * height}`)
    .join(" ");

  svg.innerHTML = `
    <polyline points="${wpmPoints}" fill="none" stroke="#4a90d9" stroke-width="2" />
    <polyline points="${accuracyPoints}" fill="none" stroke="#e08e45" stroke-width="2" />
  `;
}

loadAll();
