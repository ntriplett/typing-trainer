// The move lab: every move tile in a grid, at the sizes the game uses them.
// It flags tiles whose words get cut off or run into their icons.

const $ = (id) => document.getElementById(id);
// The room each view has in the game, for the same width of tile.
const WIDTHS = { party: 925, battle: 790, choice: 1140 };
// The longest word each size of move can ask for.
const SAMPLE = { short: "gals", medium: "flasks", long: "butterfly", phrase: "gals dads lags" };
let groups = [];

function tileHtml(t, view, i) {
  if (view === "choice") return levelOption({ ...t.party, title: "Upgrade" }, i, -1);
  if (view === "battle") {
    const m = t.battle;
    return moveCard(m, m.passive ? null : { word: SAMPLE[m.size] || "gal", typed: 0 });
  }
  return moveCard(t.party);
}

function overflows(tile) {
  const name = tile.querySelector("b");
  const icons = tile.querySelector(".wander-move-icons");
  const cost = tile.querySelector(".wander-move-cost");
  const note = tile.querySelector(".wander-move-note");
  const word = tile.querySelector(".wander-word");
  const overlap = (a, b) => {
    if (!a || !b) return false;
    const [x, y] = [a.getBoundingClientRect(), b.getBoundingClientRect()];
    return x.left < y.right && y.left < x.right && x.top < y.bottom && y.top < x.bottom;
  };
  const range = (el) => {
    const r = document.createRange();
    r.selectNodeContents(el);
    return r;
  };
  const why = [];
  if (icons && name && overlap(range(name), icons)) why.push("its name runs into its icons");
  if (note && note.scrollWidth > note.clientWidth + 1) why.push("its note is cut off");
  if (note && note.textContent && cost && overlap(range(note), cost)) why.push("its note runs into its cost");
  if (word && word.getBoundingClientRect().right > tile.getBoundingClientRect().right) why.push("its word doesn't fit");
  if (overlap(icons, cost)) why.push("its cost runs into its icons");
  if (overlap(word, cost)) why.push("its cost runs into its word");
  return why;
}

function render() {
  const view = $("opt-view").value;
  const across = Number($("opt-across").value);
  const onlyTrouble = $("opt-trouble").checked;
  const box = $("lab-groups");
  box.innerHTML = groups
    .map((g) => `<section class="panel move-lab-group ${view === "battle" ? "" : "wander-party"}"><h2 class="panel-title">${g.name} <small>(${g.tiles.length})</small></h2>
      <ul class="wander-moves ${across === 4 ? "wide" : ""}" style="width:${WIDTHS[view]}px;max-width:100%">
        ${g.tiles.map((t, i) => tileHtml(t, view, i)).join("")}
      </ul></section>`)
    .join("");
  box.classList.toggle("in-battle", view === "battle");
  let total = 0;
  let trouble = 0;
  box.querySelectorAll(".wander-moves > li").forEach((tile) => {
    total += 1;
    const why = overflows(tile);
    if (why.length) {
      trouble += 1;
      tile.classList.add("move-lab-trouble");
      tile.title = why.join(", ");
    } else if (onlyTrouble) {
      tile.hidden = true;
    }
  });
  $("lab-count").textContent = `${total} tiles. ${trouble ? `${trouble} don't fit, outlined in red: hover for why.` : "They all fit."}`;
}

["opt-view", "opt-across", "opt-trouble"].forEach((id) => $(id).addEventListener("change", render));

fetch("/api/move-lab")
  .then((r) => r.json())
  .then((data) => {
    groups = data.groups;
    render();
  });
