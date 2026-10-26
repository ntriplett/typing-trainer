// The arcade: spend arcade tokens (earned by the daily practice goal) on a
// whole game. Playing spends the tokens, then opens /game/<id>?arcade=1,
// which comes back here when the game ends.

const $ = (id) => document.getElementById(id);
let state = null;

function hint(me) {
  const day = me.day;
  if (day.resting_until) return "You earned every token today. Have fun!";
  if (day.goal_reached) return "Practice a little more for a bonus token.";
  return `Practice ${Math.ceil(day.goal_seconds / 60)} minutes to earn ${day.goal_tokens} tokens.`;
}

function render() {
  $("arcade-balance").textContent = state.tokens;
  $("arcade-hint").textContent = hint(state);
  DayTracker.render($("arcade-day"), state.day);
  $("arcade-games").innerHTML = state.games
    .map(
      (g) => `
      <article class="game-card${g.affordable && g.ready ? "" : " locked"}">
        <canvas class="game-art" data-icon="${g.id}" width="160" height="200"></canvas>
        <h2>${escapeHtml(g.title)}</h2>
        <p class="game-blurb">${escapeHtml(g.ready ? g.blurb : "Learn a few more letters to unlock this game!")}</p>
        <button class="${g.affordable && g.ready ? "button-go" : ""} big-button" data-play="${g.id}" ${g.affordable && g.ready ? "" : "disabled"}>
          Play · <span class="token-icon"></span> ${g.price}
        </button>
      </article>`
    )
    .join("");
  draw();
}

let frame = 0;
function draw() {
  document.querySelectorAll(".game-art").forEach((c) => drawHomeIcon(c, c.dataset.icon, frame));
}

async function load() {
  const res = await fetch("/api/arcade");
  state = await res.json();
  render();
}

$("arcade-games").addEventListener("click", async (e) => {
  const button = e.target.closest("[data-play]");
  if (!button) return;
  button.disabled = true;
  const res = await fetch(`/api/arcade/play/${button.dataset.play}`, { method: "POST" });
  if (!res.ok) {
    $("arcade-message").textContent = (await res.json()).detail;
    button.disabled = false;
    return;
  }
  location.href = `/game/${button.dataset.play}?arcade=1`;
});

Header.ready.then((me) => {
  if (!me) return;
  load();
  setInterval(() => {
    frame += 1;
    draw();
  }, 600);
});
