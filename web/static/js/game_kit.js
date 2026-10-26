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

// The page around a game: the HUD line, the play area, overlay screens, and
// the end-of-round tally (which posts the round and pays its coins).
class GameShell {
  // replay: whether Space plays again for free (the game lab), or the end
  // just goes back (the arcade, where every play costs tokens).
  constructor(root, content, { moduleId, onDone = () => {}, replay = true }) {
    this.content = content;
    this.moduleId = moduleId;
    this.onDone = onDone;
    this.replay = replay;
    root.innerHTML = `
      <p class="stage-label">Game</p>
      <h1 class="stage-title"></h1>
      <p class="stage-text"></p>
      <div class="game-hud"></div>
      <div class="game-area">
        <canvas class="game-canvas"></canvas>
        <div class="game-layer"></div>
      </div>
      <div class="game-below"></div>
      <div class="game-screen" hidden></div>`;
    root.classList.add("game-stage"); // the screen covers all of it, so tall tallies fit
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
    this.total = 0; // points over the whole game
    this.coins = 0;
    this.sent = 0; // keystrokes already posted with a round
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

  // Posts a finished round (paid right away) and counts its points up like
  // an arcade game, row by row. rows: [{label, count, each}] or [{label, points}];
  // rows worth 0 are left out unless they say `always`.
  // Space speeds the count up; after it, Space goes on. Resolves then.
  async roundTally({ title, rows, typer }) {
    const keystrokes = typer.keystrokes.slice(this.sent);
    this.sent = typer.keystrokes.length;
    rows = rows.filter((r) => r.points || r.count || r.always);
    const score = rows.reduce((sum, r) => sum + (r.points ?? r.count * r.each), 0);
    const paid = fetch(`/api/game/${this.moduleId}/round`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keys: this.content.keys, keystrokes, score }),
    }).then((r) => r.json());

    this.fast = false;
    this.showScreen(
      `<h2>${escapeHtml(title)}</h2>
       <div class="tally"></div>
       <p class="tally-total">Round score <b>0</b></p>
       <p class="tally-cheer"></p>
       <p class="teach-coins"></p>
       <p class="tally-go" hidden>Press ${keycap(" ")} to go on.</p>`,
      { " ": () => (this.fast = true) }
    );
    const $ = (sel) => this.els.screen.querySelector(sel);
    const wait = (ms) => new Promise((r) => setTimeout(r, this.fast ? 0 : ms));
    const bump = (el) => {
      el.classList.remove("bump");
      void el.offsetWidth;
      el.classList.add("bump");
    };
    let roundTotal = 0;
    const totalEl = $(".tally-total b");
    for (const row of rows) {
      const points = row.points ?? row.count * row.each;
      const line = document.createElement("div");
      line.className = "tally-row";
      line.innerHTML = `<span class="tally-label">${escapeHtml(row.label)}</span>
        <span class="tally-count"></span><span class="tally-points"></span><span class="tally-wow"></span>`;
      $(".tally").appendChild(line);
      const countEl = line.querySelector(".tally-count");
      const pointsEl = line.querySelector(".tally-points");
      await wait(250);
      if (row.points == null) {
        // count the things one at a time, faster when there are lots
        countEl.textContent = `0 × ${row.each}`;
        const step = Math.max(45, Math.min(160, 900 / Math.max(1, row.count)));
        for (let i = 1; i <= row.count; i++) {
          countEl.textContent = `${i} × ${row.each}`;
          bump(countEl);
          await wait(step);
        }
      }
      // then the row's points tick up into the round total
      const ticks = 12;
      for (let k = 1; k <= ticks; k++) {
        const shown = Math.round((points * k) / ticks);
        pointsEl.textContent = shown.toLocaleString();
        totalEl.textContent = (roundTotal + shown).toLocaleString();
        await wait(30);
      }
      roundTotal += points;
      bump(totalEl);
      if (points >= 300) {
        line.querySelector(".tally-wow").textContent = "WOW!";
        bump(line.querySelector(".tally-wow"));
      }
      await wait(200);
    }
    this.total += roundTotal;

    const best = this.bestRound();
    const cheer = $(".tally-cheer");
    if (roundTotal > best && best > 0) cheer.textContent = "NEW BEST ROUND!";
    else if (roundTotal >= 600) cheer.textContent = "Amazing round!";
    else if (roundTotal >= 300) cheer.textContent = "Great round!";
    else cheer.textContent = roundTotal ? "Nice!" : "Next time!";
    bump(cheer);
    if (roundTotal > best) this.saveBestRound(roundTotal);

    const data = await paid;
    const coins = data.coins_earned.reduce((sum, c) => sum + c.amount, 0);
    this.coins += coins;
    if (coins) $(".teach-coins").textContent = `+${coins} coins!`;
    if (window.Header) Header.celebrate(data.coins_earned, data.coin_balance);
    $(".tally-go").hidden = false;
    await new Promise((resolve) => (this.screenKeys = { " ": resolve }));
    this.hideScreen();
    return roundTotal;
  }

  // The best round score in this browser (just for "NEW BEST ROUND!").
  bestRound() {
    try {
      return Number(localStorage.getItem(`game-best-round:${this.moduleId}`)) || 0;
    } catch {
      return 0;
    }
  }

  saveBestRound(points) {
    try {
      localStorage.setItem(`game-best-round:${this.moduleId}`, String(points));
    } catch {
      // private window etc.: no best, no problem
    }
  }

  // Ends the game: rounds were already paid, so just the summary.
  finish({ line }) {
    this.showScreen(
      `<h2>${escapeHtml(line)}</h2>
       <p class="tally-total">Final score <b>${this.total.toLocaleString()}</b></p>
       ${this.coins ? `<p class="teach-coins">${this.coins} coins earned this game!</p>` : ""}
       ${
         this.replay
           ? `<p>Press ${keycap(" ")} to play again, or ${keycap("Enter")} for another game.</p>`
           : `<p>Press ${keycap("Enter")} to go back to the arcade.</p>`
       }`,
      this.replay ? { " ": () => location.reload(), Enter: () => this.onDone() } : { Enter: () => this.onDone() }
    );
  }
}
