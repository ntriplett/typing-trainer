// Shared top bar on every page (PLAN.md Section 11c): brand, the day
// tracker (how close today's practice is to its tokens), coin and token
// counters, and the player's avatar, which opens the profile menu (my
// profile, wardrobe, switch player -- PLAN.md 11d). With no player picked
// in this browser, it sends you to the welcome screen.
//
// Also applies the current place's page theme (themes.js) and shows a
// day/night switch when that place's night is unlocked.
//
// Rooms that unlock as letters are learned (app/unlocks.py): a page with
// <body data-unlock="pets"> shows a "mystery room" card instead of itself
// while that room is locked.
//
// Needs sprites.js, backgrounds.js, avatar.js, and themes.js loaded first.
// Exposes window.Header so pages can update coins/avatar without
// refetching.

// The day tracker: a trail that fills with today's practice, with a seed
// at half the goal (1/3 of the way), a token chest at the goal (2/3) and
// one at the 1.5x bonus (the end).
// DayTracker.render(el, day) works for any element; the home page uses a
// big one ({ big: true }).
const DayTracker = {
  minutes(seconds) {
    return Math.floor(seconds / 60);
  },

  restingUntil(day) {
    const when = new Date(day.resting_until);
    const time = when.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const tomorrow = when.toDateString() !== new Date().toDateString();
    return `${tomorrow ? "tomorrow " : ""}${time}`;
  },

  label(day) {
    if (day.resting_until) return `All done! Back ${this.restingUntil(day)}`;
    const goal = this.minutes(day.goal_seconds);
    if (day.goal_reached) return `Bonus: ${this.minutes(day.practiced_seconds)} / ${this.minutes(day.bonus_seconds)} min`;
    return `${this.minutes(day.practiced_seconds)} / ${goal} min`;
  },

  title(day) {
    if (day.resting_until) return `You earned all ${day.goal_tokens + day.bonus_tokens} tokens today. Practice opens again ${this.restingUntil(day)}.`;
    if (day.goal_reached) return `Goal reached! Keep going to ${this.minutes(day.bonus_seconds)} minutes for a bonus token.`;
    if (day.seed_reached) return `Garden watered! Practice ${this.minutes(day.goal_seconds)} minutes to earn ${day.goal_tokens} arcade tokens.`;
    return `Practice ${this.minutes(day.seed_seconds)} minutes to earn a seed and water your garden, ${this.minutes(day.goal_seconds)} for ${day.goal_tokens} arcade tokens.`;
  },

  // A grown-up's extra practice, once the regular day is full: its own
  // trail over the usual one, with the tokens it pays at the end.
  renderExtra(el, day, big) {
    const x = day.extra;
    const share = Math.min(1, x.practiced_seconds / x.seconds);
    el.classList.add("day-tracker", "extra");
    el.classList.toggle("big", big);
    el.classList.remove("goal", "resting");
    el.title = `Extra practice! ${this.minutes(x.seconds)} more minutes earns ${x.tokens} more tokens.`;
    el.innerHTML = `
      <span class="day-track" role="progressbar" aria-valuemin="0" aria-valuemax="${x.seconds}" aria-valuenow="${x.practiced_seconds}">
        <span class="day-fill" style="width:${(share * 100).toFixed(1)}%"></span>
        <span class="day-chest stack" style="left:100%" aria-label="${x.tokens} tokens">${'<span class="token-icon"></span>'.repeat(x.tokens)}</span>
      </span>
      <span class="day-label">Extra: ${this.minutes(x.practiced_seconds)} / ${this.minutes(x.seconds)} min</span>
      ${big ? `<span class="day-legend"><span></span><span></span><span>Extra practice: +${x.tokens} tokens</span></span>` : ""}`;
  },

  render(el, day, { big = false } = {}) {
    if (day.extra && day.extra.active) return this.renderExtra(el, day, big);
    el.classList.remove("extra");
    const share = Math.min(1, day.practiced_seconds / day.bonus_seconds);
    el.classList.add("day-tracker");
    el.classList.toggle("big", big);
    el.classList.toggle("goal", day.goal_reached);
    el.classList.toggle("resting", !!day.resting_until);
    el.title = this.title(day);
    // one token icon per token: the goal chest holds a little stack of 2
    const chest = (left, open, n) =>
      `<span class="day-chest${open ? " open" : ""}${n > 1 ? " stack" : ""}" style="left:${left}%" aria-label="${n} token${n > 1 ? "s" : ""}${open ? " earned" : ""}">${'<span class="token-icon"></span>'.repeat(n)}</span>`;
    el.innerHTML = `
      <span class="day-track" role="progressbar" aria-valuemin="0" aria-valuemax="${day.bonus_seconds}" aria-valuenow="${day.practiced_seconds}">
        <span class="day-fill" style="width:${(share * 100).toFixed(1)}%"></span>
        <span class="day-chest seed-chest${day.seed_reached ? " open" : ""}" style="left:33.333%" aria-label="a seed${day.seed_reached ? " earned" : ""}"><span class="seed-icon"></span></span>
        ${chest(66.667, day.goal_reached, day.goal_tokens)}
        ${chest(100, day.bonus_reached, day.bonus_tokens)}
      </span>
      <span class="day-label">${this.label(day)}</span>
      ${big ? `<span class="day-legend"><span>Seed</span><span>Goal: +${day.goal_tokens} tokens</span><span>Extra: +${day.bonus_tokens}</span></span>` : ""}`;
  },
};

(function () {
  const bar = document.createElement("header");
  bar.className = "topbar";
  bar.innerHTML = `
    <a class="brand" href="/">Typing Trainer</a>
    <div class="topbar-right">
      <a class="day-tracker" href="/session" hidden></a>
      <span class="coin-pill seed-pill" title="Seeds: earn one by practicing, plant them in your garden">
        <span class="seed-icon" aria-hidden="true"></span>
        <span id="seed-count">…</span>
      </span>
      <span class="coin-pill token-pill" title="Arcade tokens: earn them by practicing, spend them in the arcade">
        <span class="token-icon" aria-hidden="true"></span>
        <span id="token-count">…</span>
      </span>
      <span class="coin-pill" title="Your coins">
        <span class="coin-icon" aria-hidden="true"></span>
        <span id="coin-count">…</span>
      </span>
      <div class="scale-menu-wrap">
        <button class="scale-toggle" aria-haspopup="true" aria-expanded="false" title="Make everything bigger or smaller">🔍</button>
        <div class="scale-menu" role="radiogroup" aria-label="How big everything is" hidden></div>
      </div>
      <button class="night-toggle" hidden></button>
      <div class="profile-menu-wrap">
        <button class="topbar-avatar" aria-haspopup="true" aria-expanded="false" title="Profile menu"></button>
        <nav class="profile-menu" hidden>
          <p class="profile-menu-name"></p>
          <a href="/profile">My profile</a>
          <button class="switch-player">Switch user</button>
          <a href="/parent">For grown-ups</a>
        </nav>
      </div>
    </div>`;
  document.body.prepend(bar);

  const coinCount = bar.querySelector("#coin-count");
  const coinPill = bar.querySelector(".coin-pill:not(.token-pill):not(.seed-pill)");
  const seedCount = bar.querySelector("#seed-count");
  const seedPill = bar.querySelector(".seed-pill");
  const tokenCount = bar.querySelector("#token-count");
  const tokenPill = bar.querySelector(".token-pill");
  const tracker = bar.querySelector(".day-tracker");
  const avatarCanvas = makeAvatarCanvas(48);
  const avatarButton = bar.querySelector(".topbar-avatar");
  avatarButton.appendChild(avatarCanvas);

  const menu = bar.querySelector(".profile-menu");
  avatarButton.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
    avatarButton.setAttribute("aria-expanded", String(!menu.hidden));
  });
  document.addEventListener("click", (e) => {
    if (!menu.contains(e.target)) menu.hidden = true;
  });
  // How big everything draws on this computer (ui_scale.js). Its buttons
  // never take the keyboard's focus, so typing carries on mid-lesson or game.
  const scaleWrap = bar.querySelector(".scale-menu-wrap");
  const scaleToggle = bar.querySelector(".scale-toggle");
  const scaleMenu = bar.querySelector(".scale-menu");
  const scale = typeof UIScale === "undefined" ? null : UIScale; // a top-level const, not on window
  function showScales() {
    const now = scale ? scale.get() : 1;
    scaleMenu.innerHTML = (scale ? scale.SIZES : [1]).map(
      (v) => `<button class="scale-pick${v === now ? " current" : ""}" role="radio" aria-checked="${v === now}" data-scale="${v}">${Math.round(v * 100)}%</button>`
    ).join("");
  }
  scaleWrap.addEventListener("mousedown", (e) => e.preventDefault()); // keep focus where it was
  scaleToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    showScales();
    scaleMenu.hidden = !scaleMenu.hidden;
    scaleToggle.setAttribute("aria-expanded", String(!scaleMenu.hidden));
  });
  scaleMenu.addEventListener("click", (e) => {
    e.stopPropagation();
    const pick = e.target.closest(".scale-pick");
    if (!pick || !scale) return;
    scale.set(Number(pick.dataset.scale));
    showScales();
  });
  document.addEventListener("click", (e) => {
    if (!scaleWrap.contains(e.target)) {
      scaleMenu.hidden = true;
      scaleToggle.setAttribute("aria-expanded", "false");
    }
  });
  window.addEventListener("storage", (e) => {
    if (e.key === "ui-scale" && !scaleMenu.hidden) showScales();
  });

  bar.querySelector(".switch-player").addEventListener("click", async () => {
    await fetch("/api/profiles/logout", { method: "POST" });
    window.location.href = "/welcome";
  });

  const toast = document.createElement("div");
  toast.className = "coin-toast";
  document.body.appendChild(toast);

  const REASON_LABELS = {
    lesson: "Lesson",
    key_solid: "Key solid!",
    key_halfway: "15 WPM on a key!",
    key_mastered: "Key mastered! 30 WPM!",
    session_complete: "Session complete!",
    teach: "Lesson",
    teach_first: "First lesson bonus!",
    game: "Game",
    daily_goal: "Daily goal!",
    king_crow: "King Crow!",
    daily_bonus: "Bonus token!",
    daily_extra: "Extra practice tokens!",
    daily_seed: "A seed!",
  };

  function setCoins(n) {
    coinCount.textContent = n.toLocaleString();
    coinPill.classList.remove("bump");
    void coinPill.offsetWidth; // restart the animation
    coinPill.classList.add("bump");
  }

  function setTokens(n) {
    tokenCount.textContent = n.toLocaleString();
    tokenPill.classList.remove("bump");
    void tokenPill.offsetWidth;
    tokenPill.classList.add("bump");
  }

  function setSeeds(n) {
    seedCount.textContent = n.toLocaleString();
    seedPill.classList.remove("bump");
    void seedPill.offsetWidth;
    seedPill.classList.add("bump");
  }

  let day = null;
  function setDay(d) {
    day = d;
    tracker.hidden = false;
    DayTracker.render(tracker, d);
    document.dispatchEvent(new CustomEvent("daychange", { detail: d }));
  }

  const nightToggle = bar.querySelector(".night-toggle");
  let current = null; // latest /api/me-shaped response

  function setAvatar(equipped) {
    drawAvatar(avatarCanvas, equipped);
    applyTheme(equipped);
  }

  // Any response shaped like /api/me (store actions, the Home, ...).
  function update(me) {
    current = me;
    bar.querySelector(".profile-menu-name").textContent = me.learner.name;
    setCoins(me.coins);
    tokenCount.textContent = me.tokens.toLocaleString();
    seedCount.textContent = me.seeds.toLocaleString();
    if (me.day) setDay(me.day);
    setAvatar(me.avatar);
    nightToggle.hidden = !me.night.available;
    nightToggle.textContent = me.night.on ? "☀️" : "🌙";
    nightToggle.title = me.night.on ? "Switch to day" : "Switch to night";
    document.dispatchEvent(new CustomEvent("avatarchange", { detail: me }));
  }

  nightToggle.addEventListener("click", async () => {
    const r = await fetch("/api/me/night", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ on: !current.night.on }),
    });
    if (r.ok) update(await r.json());
  });

  function toastItem(html, i, extraClass = "") {
    const item = document.createElement("div");
    item.className = `coin-toast-item ${extraClass}`;
    item.style.animationDelay = `${i * 0.35}s`;
    item.innerHTML = html;
    toast.appendChild(item);
    setTimeout(() => item.remove(), 2400 + i * 350);
  }

  // `earned` is a completion response's coins_earned list.
  function celebrate(earned, newBalance) {
    earned.forEach((c, i) =>
      toastItem(`<span class="coin-icon"></span>+${c.amount} ${REASON_LABELS[c.reason] || ""}`, i)
    );
    setCoins(newBalance);
  }

  // `earned` is a completion response's tokens_earned list.
  function celebrateTokens(earned, newBalance) {
    earned.forEach((t, i) =>
      toastItem(
        `<span class="token-icon"></span>+${t.amount} token${t.amount > 1 ? "s" : ""}! ${REASON_LABELS[t.reason] || ""}`,
        i + 1,
        "token-toast"
      )
    );
    if (earned.length) {
      setTokens(newBalance);
      tracker.querySelectorAll(".day-chest.open").forEach((c) => c.classList.add("pop"));
    }
  }

  // `data` is a completion response: its seeds_earned list, and `watered`
  // (the garden got its water: which plants ripened a veggie).
  function celebrateSeeds(data) {
    const earned = data.seeds_earned || [];
    earned.forEach((t, i) =>
      toastItem(`<span class="seed-icon"></span>+${t.amount} seed! Plant it in your garden`, i + 1, "seed-toast")
    );
    if (earned.length) {
      setSeeds(data.seed_balance);
      tracker.querySelectorAll(".seed-chest.open").forEach((c) => c.classList.add("pop"));
    }
    if (data.watered) showWatering(data.watered.ripened);
  }

  // A little pop-up: the watering can pours over three plants, and the
  // babies on them turn ripe. Draws the plants that really ripened (or
  // empty soil if nothing is planted yet).
  const WATER_FRAMES = 22;
  function showWatering(ripened) {
    if (!window.drawPlant) return;
    const pop = document.createElement("div");
    pop.className = "watering";
    const n = ripened.length;
    pop.innerHTML = `
      <canvas class="watering-art" width="264" height="144"></canvas>
      <p>${n ? `Your garden got watered! ${n} veggie${n > 1 ? "s" : ""} ripened.` : "Your garden got watered! Plant a seed to grow veggies."}</p>`;
    document.body.appendChild(pop);
    const canvas = pop.querySelector("canvas");
    const plants = [0, 1, 2].map((i) => ripened[i] || null);
    let frame = 0;
    const draw = () => {
      const px = veggieCanvas(canvas, 66, 36);
      const ripe = frame > WATER_FRAMES / 2 ? 1 : 0;
      plants.forEach((p, i) =>
        drawPlant(px, i * 23, 16, p && { kind: p.kind, picked: 0, ready: ripe }, frame)
      );
      const t = Math.min(1, frame / (WATER_FRAMES - 4));
      const canX = Math.round(50 - t * 48);
      drawWateringCan(px, canX, 0, 2);
      for (let k = 0; k < 4; k++) {
        const dy = (frame * 2 + k * 4) % 14;
        px(canX + (k % 2), 6 + dy, 1, 2, "#6fb8e8");
      }
    };
    draw();
    const timer = setInterval(() => {
      frame += 1;
      if (frame > WATER_FRAMES) {
        clearInterval(timer);
        pop.classList.add("done");
        setTimeout(() => pop.remove(), 1200);
        return;
      }
      draw();
    }, 150);
  }

  // Resolves with /api/me so pages that also need it don't fetch twice.
  const ready = fetch("/api/me")
    .then((r) => {
      if (r.status === 401) {
        window.location.href = "/welcome"; // nobody picked in this browser yet
        return new Promise(() => {}); // never resolves; we're leaving
      }
      if (!r.ok) throw new Error(`/api/me returned ${r.status}`);
      return r.json();
    })
    .then((me) => {
      update(me);
      const room = document.body.dataset.unlock;
      if (room && me.unlocks && !me.unlocks[room]) {
        showMystery(me.unlocks, room);
        return new Promise(() => {}); // the page itself never starts
      }
      return me;
    })
    .catch((err) => {
      console.error(err);
      coinCount.textContent = "?";
      return null;
    });

  // The locked-room card: a "?" block, what opens it, and the keys still to learn.
  function showMystery(unlocks, room) {
    const main = document.querySelector("main");
    const missing = [...unlocks.missing[room]].map((k) => keycap(k)).join(" ");
    main.innerHTML = `
      <section class="panel mystery">
        <canvas class="mystery-art" width="160" height="160"></canvas>
        <h1>A mystery room!</h1>
        <p class="mystery-text">${unlocks.hints[room]}</p>
        <p class="mystery-keys">Still to learn: ${missing}</p>
        <p><a class="button button-go big-button" href="/session">Practice</a> <a class="button big-button" href="/">Home</a></p>
      </section>`;
    const art = main.querySelector(".mystery-art");
    if (window.drawHomeIcon) {
      let frame = 0;
      drawHomeIcon(art, "mystery", frame);
      setInterval(() => drawHomeIcon(art, "mystery", ++frame), 600);
    }
  }

  window.Header = {
    ready, setCoins, setTokens, setSeeds, setDay, setAvatar, update, celebrate, celebrateTokens, celebrateSeeds,
  };
})();
