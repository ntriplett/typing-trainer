// The analysis page: 4 tabs (keyboard heatmap, fingers, letter pairs,
// trend), each rendered with plain HTML/CSS/SVG -- no charting
// library (PLAN.md Section 11a still defers real visual polish; this
// just needs to show the data clearly).
//
// KEYBOARD_ROWS/FINGER_LABELS/FINGER_ORDER come from keyboard_data.js,
// loaded before this script.

document.querySelectorAll(".tab-button").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

function showTab(name) {
  document.querySelectorAll(".tab-button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = p.id !== `tab-${name}`));
}

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} returned ${r.status}`);
  return r.json();
}

async function loadAll() {
  const [keys, fingers, bigrams, trend] = await Promise.all([
    fetchJson("/api/analytics/keys"),
    fetchJson("/api/analytics/fingers"),
    fetchJson("/api/analytics/bigrams"),
    fetchJson("/api/analytics/trend"),
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
        const cls = (color ? "" : "not-started") + (k === " " ? " kb-space" : "");
        const style = color ? `style="background:${color}"` : "";
        const name = k === " " ? "space" : k;
        const title = entry
          ? `${name}: ${entry.sample_count} attempts` +
            (entry.accuracy !== null ? `, ${Math.round(entry.accuracy * 100)}% accuracy` : ", not started")
          : k;
        return `<div class="kb-key ${cls}" ${style} title="${title}">${name}</div>`;
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
    svg.innerHTML = `<text x="300" y="100" text-anchor="middle" fill="#6b4a2e">No sessions yet.</text>`;
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
    <polyline points="${wpmPoints}" fill="none" stroke="#6b8e3a" stroke-width="2" />
    <polyline points="${accuracyPoints}" fill="none" stroke="#d9822b" stroke-width="2" />
  `;
}

// A failed fetch used to leave every panel silently blank (PLAN.md 11b);
// say so instead, so a server error is visible rather than a white page.
loadAll().catch((err) => {
  console.error(err);
  document.getElementById("keyboard").innerHTML =
    `<p class="hint">Couldn't load progress data (${err.message}). Try reloading.</p>`;
});
