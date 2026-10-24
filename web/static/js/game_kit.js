// Shared pieces for the games (app/activities/game_modules.py): typing words
// to pick targets, choosing words so the first letters on screen differ, the
// start/between/end screens, and posting the score.
//
// The first key you press locks onto the word that starts with it (like
// ZType); then each right key moves along it. A wrong key doesn't move on;
// it counts as a slip on that word. Escape or Backspace lets go of the word,
// so you can pick a different one.
//
//   const typer = new Typer();
//   const r = typer.press("f", targets);   // targets: [{word, typed}, ...]
//   r.kind: "lock" | "hit" | "done" | "slip" | "stray"   (stray: matched nothing)
//
// A game is a function registered in GAMES: GAMES.crow_patrol(shell, content).
// Needs rich_text.js and practice_scenes.js (mixColor) loaded first.

const GAMES = {};

class Typer {
  constructor() {
    this.target = null;
    this.keystrokes = [];
    this.lastAt = performance.now();
  }

  press(ch, targets) {
    const now = performance.now();
    const latency = Math.max(1, Math.min(5000, Math.round(now - this.lastAt)));
    this.lastAt = now;
    if (this.target && !targets.includes(this.target)) this.release();

    if (!this.target) {
      const t = targets.find((x) => x.word[0] === ch);
      if (!t) return { kind: "stray" };
      this.target = t;
      t.typed = 0;
      t.slips = 0;
    }
    const t = this.target;
    const expected = t.word[t.typed];
    const correct = ch === expected;
    this.keystrokes.push({ expected_char: expected, typed_char: ch, correct, latency_ms: latency });
    if (!correct) {
      t.slips += 1;
      return { kind: "slip", target: t };
    }
    t.typed += 1;
    if (t.typed === t.word.length) {
      this.target = null;
      return { kind: "done", target: t };
    }
    return { kind: t.typed === 1 ? "lock" : "hit", target: t };
  }

  release() {
    if (this.target) this.target.typed = 0;
    this.target = null;
  }
}

// The word as HTML: typed part, then the next letter, then the rest.
function wordHtml(word, typed = 0) {
  const done = escapeHtml(word.slice(0, typed));
  const next = escapeHtml(word.slice(typed, typed + 1));
  const rest = escapeHtml(word.slice(typed + 1));
  return `<span class="w-typed">${done}</span><span class="w-next">${next}</span>${rest}`;
}

// A word from `groups[group]` ("mixed": short or medium) whose first letter
// isn't in `taken`, or null if there's none.
function pickWord(groups, group, taken) {
  const name = group === "mixed" ? (Math.random() < 0.5 ? "short" : "medium") : group;
  const words = groups[name] || [];
  const free = words.filter((w) => !taken.has(w[0]));
  return free.length ? free[Math.floor(Math.random() * free.length)] : null;
}

// n words with different first letters, one per group in `groups_wanted`.
function pickWords(groups, wanted) {
  const taken = new Set();
  return wanted.map((g) => {
    const w = pickWord(groups, g, taken) || pickWord(groups, "short", taken) || "";
    if (w) taken.add(w[0]);
    return w;
  });
}

// `colors` blended into `steps` bands, so the sky fades instead of striping.
function smoothSky(colors, steps) {
  return Array.from({ length: steps }, (_, i) => {
    const t = (i / (steps - 1)) * (colors.length - 1);
    const k = Math.min(colors.length - 2, Math.floor(t));
    return mixColor(colors[k], colors[k + 1], t - k);
  });
}

// The page around a game: the HUD line, the play area, and overlay screens.
class GameShell {
  constructor(root, content, { moduleId, onDone = () => {} }) {
    this.content = content;
    this.moduleId = moduleId;
    this.onDone = onDone;
    root.innerHTML = `
      <p class="stage-label">Game</p>
      <h1 class="stage-title"></h1>
      <p class="stage-text"></p>
      <div class="game-hud"></div>
      <div class="game-area">
        <canvas class="game-canvas"></canvas>
        <div class="game-layer"></div>
        <div class="game-screen" hidden></div>
      </div>
      <div class="game-below"></div>`;
    const $ = (sel) => root.querySelector(sel);
    this.els = {
      label: $(".stage-label"),
      title: $(".stage-title"),
      text: $(".stage-text"),
      hud: $(".game-hud"),
      area: $(".game-area"),
      canvas: $(".game-canvas"),
      layer: $(".game-layer"),
      screen: $(".game-screen"),
      below: $(".game-below"),
    };
    this.els.title.textContent = content.title;
    this.els.text.innerHTML = richText(content.instructions);
    this.screenKeys = null;
  }

  setLabel(text) {
    this.els.label.textContent = text;
  }

  // An overlay card; `keys` maps a key (" ", "Enter") to what it does.
  showScreen(html, keys = {}) {
    this.els.screen.innerHTML = `<div class="game-card">${html}</div>`;
    this.els.screen.hidden = false;
    this.screenKeys = keys;
  }

  hideScreen() {
    this.els.screen.hidden = true;
    this.screenKeys = null;
  }

  // For games: true when a screen took the key.
  screenKey(e) {
    if (!this.screenKeys) return false;
    const action = this.screenKeys[e.key];
    if (action) {
      e.preventDefault();
      action();
    }
    return true;
  }

  // Ends the game: posts the score and shows the summary.
  async finish({ successes, line, keystrokes }) {
    const res = await fetch(`/api/game/${this.moduleId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keys: this.content.keys, keystrokes, successes }),
    });
    const data = await res.json();
    const coins = data.coins_earned.reduce((sum, c) => sum + c.amount, 0);
    if (window.Header) Header.celebrate(data.coins_earned, data.coin_balance);
    const accuracy = keystrokes.length ? `${Math.round(data.result.accuracy * 100)}% of keys right.` : "";
    this.showScreen(
      `<h2>${escapeHtml(line)}</h2>
       ${coins ? `<p class="teach-coins">+${coins} coins!</p>` : ""}
       <p>${accuracy}</p>
       <p>Press ${keycap(" ")} to play again, or ${keycap("Enter")} for another game.</p>`,
      { " ": () => location.reload(), Enter: () => this.onDone() }
    );
  }
}
