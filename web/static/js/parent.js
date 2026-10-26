// The parent page: every player's daily goal and practice-vs-learn
// setting, how today is going, and what the lesson brain will pick next
// (with its reasons). Settings save as soon as a slider is let go.

const $ = (id) => document.getElementById(id);
const KIND_NAMES = { warmup: "a warmup", learn: "a new-letter lesson", practice: "practice" };

function learnLabel(v) {
  if (v <= 0.15) return "Mostly practice";
  if (v >= 0.85) return "Push new letters";
  return "Balanced";
}

function card(p) {
  const s = p.settings;
  const goal = s.goal_minutes;
  return `
    <section class="panel player" data-id="${p.id}">
      <div class="player-head">
        <canvas width="96" height="96" class="player-avatar"></canvas>
        <div>
          <h2>${escapeHtml(p.name)}</h2>
          <p class="player-stats">
            <span class="token-icon"></span> ${p.tokens} tokens ·
            about ${p.predicted_wpm} words a minute
          </p>
        </div>
      </div>
      <div class="player-day"></div>

      <div class="setting">
        <label>Daily goal: <output class="goal-out">${goal}</output> minutes
          <small>(bonus token at <span class="bonus-out">${Math.round(goal * 1.5)}</span>)</small></label>
        <input type="range" class="goal" min="2" max="30" step="1" value="${goal}" />
      </div>
      <div class="setting">
        <label>Practice ↔ Learn: <output class="learn-out">${learnLabel(s.learn_vs_practice)}</output>
          <small>(new letters once every key is above <span class="bar-out">${Math.round(p.solid_bar * 100)}</span>%)</small></label>
        <input type="range" class="learn" min="0" max="100" step="5" value="${Math.round(s.learn_vs_practice * 100)}" />
      </div>
      <p class="saved" aria-live="polite"></p>

      <div class="brain">
        <h3>Next lesson: ${KIND_NAMES[p.brain.kind] || p.brain.kind}</h3>
        <ul>${p.brain.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
        <p class="next-new">${p.next_new_lesson ? `Next new lesson: <b>${escapeHtml(p.next_new_lesson)}</b>` : "Every lesson is learned!"}</p>
      </div>
    </section>`;
}

function render(players) {
  $("players").innerHTML = players.map(card).join("");
  players.forEach((p) => {
    const el = document.querySelector(`.player[data-id="${p.id}"]`);
    drawAvatar(el.querySelector(".player-avatar"), p.avatar);
    DayTracker.render(el.querySelector(".player-day"), p.day, { big: true });
    wire(el, p);
  });
}

function wire(el, p) {
  const goal = el.querySelector(".goal");
  const learn = el.querySelector(".learn");
  const bar = (v) => Math.round((0.98 + (0.8 - 0.98) * v) * 100);
  goal.addEventListener("input", () => {
    el.querySelector(".goal-out").textContent = goal.value;
    el.querySelector(".bonus-out").textContent = Math.round(goal.value * 1.5);
  });
  learn.addEventListener("input", () => {
    el.querySelector(".learn-out").textContent = learnLabel(learn.value / 100);
    el.querySelector(".bar-out").textContent = bar(learn.value / 100);
  });
  const save = async () => {
    const res = await fetch(`/api/parent/${p.id}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal_minutes: Number(goal.value), learn_vs_practice: learn.value / 100 }),
    });
    const updated = await res.json();
    el.outerHTML = card(updated);
    const fresh = document.querySelector(`.player[data-id="${p.id}"]`);
    drawAvatar(fresh.querySelector(".player-avatar"), updated.avatar);
    DayTracker.render(fresh.querySelector(".player-day"), updated.day, { big: true });
    fresh.querySelector(".saved").textContent = "Saved!";
    wire(fresh, updated);
  };
  goal.addEventListener("change", save);
  learn.addEventListener("change", save);
}

fetch("/api/parent")
  .then((r) => r.json())
  .then(render);
