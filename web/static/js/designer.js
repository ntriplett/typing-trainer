// Character designer: pick boy/girl, skin, hair length, and hair color.
// Every click saves straight away (PUT /api/appearance) -- no separate
// save step for a kid to forget. Allowed values come from the server
// (app/appearance.py); colors come from sprites.js.

const LABELS = {
  boy: "Boy",
  girl: "Girl",
  short: "Short",
  medium: "Medium",
  long: "Long",
};

const preview = document.getElementById("designer-avatar");

// New players come here straight from the welcome screen (?setup=1); the
// next step is the placement questions, not the profile page.
if (new URLSearchParams(window.location.search).has("setup")) {
  const done = document.getElementById("designer-done");
  done.textContent = "Next →";
  done.href = "/placement";
  done.classList.add("button-go");
}
const statusEl = document.getElementById("designer-status");
const nameInput = document.getElementById("name-input");

let me = null; // latest /api/appearance response
let options = null;

async function load() {
  const r = await fetch("/api/appearance");
  if (!r.ok) throw new Error(`/api/appearance returned ${r.status}`);
  const data = await r.json();
  me = data;
  options = data.options;
  nameInput.value = data.learner.name;
  render();
}

function look() {
  return me.avatar.appearance;
}

function render() {
  drawAvatar(preview, me.avatar);
  renderTextChoices("gender");
  renderHairStyles();
  renderSwatches("skin", options.skin.map((id) => ({ id, unlocked: true })), (id) => SKIN_TONES[id][0]);
  renderSwatches("hair_color", options.hair_color, (id) => HAIR_COLORS[id][0]);
  renderSwatches("eye_color", options.eye_color.map((id) => ({ id, unlocked: true })), (id) => EYE_COLORS[id]);
}

function renderTextChoices(field) {
  const row = document.getElementById(`choices-${field}`);
  row.replaceChildren(
    ...options[field].map((id) => {
      const btn = document.createElement("button");
      btn.className = "choice" + (look()[field] === id ? " selected" : "");
      btn.textContent = LABELS[id] || id;
      btn.onclick = () => choose(field, id);
      return btn;
    })
  );
}

// Hair lengths are easier to pick by picture than by word.
function renderHairStyles() {
  const row = document.getElementById("choices-hair_style");
  row.replaceChildren(
    ...options.hair_style.map((id) => {
      const btn = document.createElement("button");
      btn.className = "choice" + (look().hair_style === id ? " selected" : "");
      const canvas = makeAvatarCanvas(96);
      drawAvatar(canvas, { ...me.avatar, hat: null, appearance: { ...look(), hair_style: id } });
      const label = document.createElement("div");
      label.textContent = LABELS[id];
      btn.append(canvas, label);
      btn.onclick = () => choose("hair_style", id);
      return btn;
    })
  );
}

function renderSwatches(field, choices, colorOf) {
  const row = document.getElementById(`choices-${field}`);
  row.replaceChildren(
    ...choices.map(({ id, unlocked }) => {
      const btn = document.createElement("button");
      btn.className =
        "swatch-choice" + (look()[field] === id ? " selected" : "") + (unlocked ? "" : " locked");
      btn.style.background = colorOf(id);
      btn.title = unlocked ? id : `${id} — buy this hair dye in the store`;
      btn.setAttribute("aria-label", btn.title);
      btn.onclick = unlocked ? () => choose(field, id) : () => (window.location.href = "/store");
      return btn;
    })
  );
}

async function choose(field, value) {
  const body = { ...look(), [field]: value };
  const r = await fetch("/api/appearance", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) {
    statusEl.textContent = data.detail || "That didn't work.";
    return;
  }
  me.avatar = data.avatar;
  Header.update(data);
  statusEl.textContent = "Saved!";
  render();
}

document.getElementById("name-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await fetch("/api/me/name", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: nameInput.value }),
  });
  const data = await r.json();
  statusEl.textContent = r.ok ? `Hi, ${data.learner.name}!` : data.detail || "That name didn't work.";
});

load().catch((err) => {
  console.error(err);
  statusEl.textContent = `Couldn't load the designer (${err.message}).`;
});
