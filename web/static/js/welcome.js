// Who's playing? Pick your player (each shown as their avatar), or make a
// new one: name -> your look (the Home's vanity mirror) -> a quick placement -> home.
// Picking sets this browser's player cookie (PLAN.md 11d).

const playersEl = document.getElementById("players");
const newPanel = document.getElementById("new-player");
const nameInput = document.getElementById("new-name");
const messageEl = document.getElementById("welcome-message");

applyTheme({ background: "bg_meadow" }); // nobody's place yet: the default look

async function load() {
  const r = await fetch("/api/profiles");
  const players = await r.json();
  playersEl.replaceChildren(...players.map(playerCard), newCard());
  if (!players.length) showNew();
}

function playerCard(p) {
  const btn = document.createElement("button");
  btn.className = "player-card";
  btn.dataset.learnerId = p.id;
  const c = makeAvatarCanvas(144);
  drawAvatar(c, p.avatar);
  const name = document.createElement("span");
  name.textContent = p.name;
  btn.append(c, name);
  btn.onclick = async () => {
    await fetch(`/api/profiles/${p.id}/select`, { method: "POST" });
    window.location.href = "/";
  };
  return btn;
}

function newCard() {
  const btn = document.createElement("button");
  btn.className = "player-card new";
  btn.innerHTML = `<span class="plus">+</span><span>New player</span>`;
  btn.onclick = showNew;
  return btn;
}

function showNew() {
  newPanel.hidden = false;
  nameInput.focus();
}

document.getElementById("new-player-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  messageEl.textContent = "";
  const r = await fetch("/api/profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: nameInput.value }),
  });
  const data = await r.json();
  if (!r.ok) {
    messageEl.textContent = data.detail || "That name didn't work.";
    return;
  }
  window.location.href = "/bedroom?room=mirror&setup=1"; // next: make your character
});

load();
