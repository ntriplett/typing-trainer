// For Grown-ups, behind the PIN (asked every visit): the current player's daily goal and
// practice-vs-learn setting, how today is going, and what the lesson brain will pick
// next (with its reasons). Settings save as soon as a slider is let go.

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

      <div class="extra-practice">${extraHtml(p)}</div>

      <div class="brain">
        <h3>Next lesson: ${KIND_NAMES[p.brain.kind] || p.brain.kind}</h3>
        <ul>${p.brain.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
        <p class="next-new">${p.next_new_lesson ? `Next new lesson: <b>${escapeHtml(p.next_new_lesson)}</b>` : "Every lesson is learned!"}</p>
      </div>
    </section>`;
}

// A grown-up's extra 15 minutes (app/daily.py): counts once today's practice is done.
function extraHtml(p) {
  const x = p.day.extra;
  const name = escapeHtml(p.name);
  if (!x) {
    return `<button class="button-go extra-go">⏱️ Allow 15 more minutes (+2 tokens)</button>
      <small>${name} can keep practicing after today's practice is done, until the next practice day starts.</small>`;
  }
  if (!x.active) return `<p>⏱️ <b>15 extra minutes allowed.</b> They start once today's practice is done.</p>`;
  return `<p>⏱️ <b>Extra practice going:</b> ${Math.floor(x.practiced_seconds / 60)} of ${Math.floor(x.seconds / 60)} minutes, then ${x.tokens} more tokens.</p>`;
}

function render(p) {
  $("players").innerHTML = card(p);
  const el = document.querySelector(".player");
  drawAvatar(el.querySelector(".player-avatar"), p.avatar);
  DayTracker.render(el.querySelector(".player-day"), p.day, { big: true });
  wire(el, p);
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
    const res = await fetch("/api/parent/settings", {
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
  const extra = el.querySelector(".extra-go");
  if (extra)
    extra.onclick = async () => {
      extra.disabled = true;
      const res = await fetch("/api/parent/extra", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        el.querySelector(".saved").textContent = data.detail;
        extra.disabled = false;
        return;
      }
      render(data);
      if (window.Header) Header.setDay(data.day);
    };
}

// The installed app's updates (app/desktop.py). Progress is kept: the
// update only replaces the program, and backs up the database first.
function renderUpdate(u) {
  if (!u.installed) return;
  $("update").hidden = false;
  const text = $("update-text");
  if (!u.available) {
    text.textContent = u.latest
      ? `Version ${u.current}. You have the newest version.`
      : `Version ${u.current}. Couldn't reach GitHub to check for a newer one.`;
    return;
  }
  text.textContent = `Version ${u.latest} is ready (you have ${u.current}). Progress is kept, and the app reopens by itself in about a minute.`;
  if (u.notes) {
    $("update-notes").textContent = u.notes;
    $("update-notes").hidden = false;
  }
  const go = $("update-go");
  go.hidden = false;
  go.onclick = async () => {
    go.disabled = true;
    const res = await fetch("/api/update", { method: "POST" });
    if (res.ok) {
      text.textContent = "Updating... this window will close, and the app reopens when it's done.";
    } else {
      text.textContent = (await res.json()).detail;
      go.disabled = false;
    }
  };
}

function askPin(status) {
  const box = $("lock");
  box.hidden = false;
  box.innerHTML = `
    <h1 class="panel-title">For grown-ups</h1>
    <form class="pin-form">
      <label>PIN <input class="pin-input" id="pin" type="password" inputmode="numeric" maxlength="4" autocomplete="off" /></label>
      <button type="submit" class="button-go">Open</button>
    </form>
    <p class="error-text" id="pin-message" role="status"></p>
    <details class="pin-forgot"><summary>Forgot the PIN?</summary>
      <p>Close the app, delete this file, and you'll choose a new PIN next time: <code>${escapeHtml(status.file)}</code></p>
    </details>`;
  $("pin").focus();
  box.querySelector("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await fetch("/api/grownups/unlock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin: $("pin").value }),
    });
    if (!res.ok) {
      $("pin-message").textContent = "That's not the PIN.";
      $("pin").value = "";
      $("pin").focus();
      return;
    }
    openPage();
  });
}

function openPage() {
  $("lock").hidden = true;
  $("grownups").hidden = false;
  fetch("/api/update")
    .then((r) => r.json())
    .then(renderUpdate)
    .catch(() => {});
  fetch("/api/parent")
    .then((r) => r.json())
    .then(render);
  showChangePin();
  showGift();
}

// A pet designed in the pet lab, wrapped up for a player (app/pet_gift.py).
async function showGift() {
  const players = await (await fetch("/api/profiles")).json();
  const me = ((await Header.ready) || {}).learner?.id;
  $("gift-to").innerHTML = players.map((p) => `<option value="${p.id}"${p.id === me ? " selected" : ""}>${escapeHtml(p.name)}</option>`).join("");
  document.querySelector(".gift-form").onsubmit = async (e) => {
    e.preventDefault();
    let design;
    try {
      design = JSON.parse($("gift-design").value);
    } catch {
      $("gift-message").textContent = "That isn't a pet's design: copy the whole thing from the pet lab's JSON box.";
      return;
    }
    const res = await fetch("/api/parent/gift", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ to: Number($("gift-to").value), from_name: $("gift-from").value, design }),
    });
    const data = await res.json();
    if (!res.ok) {
      $("gift-message").textContent = typeof data.detail === "string" ? data.detail : "That pet couldn't be wrapped up.";
      return;
    }
    const who = $("gift-to").selectedOptions[0].textContent;
    $("gift-message").textContent = `🎁 ${data.gift.name} is wrapped up for ${who}, from ${data.gift.from}! It's waiting at the Pet Shop.`;
    $("gift-design").value = "";
  };
}

function showChangePin() {
  const box = $("change-pin");
  box.innerHTML = `<h2 class="panel-title">PIN</h2><p><button id="change-pin-go">Change the PIN</button></p>`;
  $("change-pin-go").onclick = () =>
    choosePinForm(box, {
      title: "Change the PIN",
      intro: "Choose a new 4-number PIN.",
      onDone: () => {
        showChangePin();
        box.insertAdjacentHTML("beforeend", `<p class="saved">Saved!</p>`);
      },
    });
}

// The PIN's asked for on every visit: leaving this page locks it again.
async function start() {
  await fetch("/api/grownups/lock", { method: "POST" });
  const status = await (await fetch("/api/grownups/status")).json();
  if (status.set) return askPin(status);
  const box = $("lock");
  box.hidden = false;
  choosePinForm(box, {
    title: "Choose a PIN",
    intro: "This page is for grown-ups. Choose a 4-number PIN to keep it that way.",
    onDone: openPage,
  });
}

Header.ready.then((me) => {
  if (me) start();
});
