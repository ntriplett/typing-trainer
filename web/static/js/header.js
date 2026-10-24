// Shared top bar on every page (PLAN.md Section 11c): brand, coin
// counter, and the player's avatar, which opens the profile menu (my
// profile, wardrobe, switch player -- PLAN.md 11d). With no player picked
// in this browser, it sends you to the welcome screen.
//
// Also applies the current place's page theme (themes.js) and shows a
// day/night switch when that place's night is unlocked.
//
// Needs sprites.js, backgrounds.js, avatar.js, and themes.js loaded first.
// Exposes window.Header so pages can update coins/avatar without
// refetching.

(function () {
  const bar = document.createElement("header");
  bar.className = "topbar";
  bar.innerHTML = `
    <a class="brand" href="/">Typing Trainer</a>
    <div class="topbar-right">
      <span class="coin-pill" title="Your coins">
        <span class="coin-icon" aria-hidden="true"></span>
        <span id="coin-count">…</span>
      </span>
      <button class="night-toggle" hidden></button>
      <div class="profile-menu-wrap">
        <button class="topbar-avatar" aria-haspopup="true" aria-expanded="false" title="Profile menu"></button>
        <nav class="profile-menu" hidden>
          <p class="profile-menu-name"></p>
          <a href="/profile">My profile</a>
          <a href="/wardrobe">Wardrobe</a>
          <a href="/designer">Change my look</a>
          <button class="switch-player">Switch player</button>
        </nav>
      </div>
    </div>`;
  document.body.prepend(bar);

  const coinCount = bar.querySelector("#coin-count");
  const coinPill = bar.querySelector(".coin-pill");
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
  bar.querySelector(".switch-player").addEventListener("click", async () => {
    await fetch("/api/profiles/logout", { method: "POST" });
    window.location.href = "/welcome";
  });

  const toast = document.createElement("div");
  toast.className = "coin-toast";
  document.body.appendChild(toast);

  const REASON_LABELS = {
    lesson: "Lesson",
    key_mastered: "New key mastered!",
    session_complete: "Session complete!",
    teach: "Lesson",
    teach_first: "First lesson bonus!",
  };

  function setCoins(n) {
    coinCount.textContent = n.toLocaleString();
    coinPill.classList.remove("bump");
    void coinPill.offsetWidth; // restart the animation
    coinPill.classList.add("bump");
  }

  const nightToggle = bar.querySelector(".night-toggle");
  let current = null; // latest /api/me-shaped response

  function setAvatar(equipped) {
    drawAvatar(avatarCanvas, equipped);
    applyTheme(equipped);
  }

  // Any response shaped like /api/me (store actions, designer, ...).
  function update(me) {
    current = me;
    bar.querySelector(".profile-menu-name").textContent = me.learner.name;
    setCoins(me.coins);
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

  // `earned` is the step-completion response's coins_earned list.
  function celebrate(earned, newBalance) {
    earned.forEach((c, i) => {
      const item = document.createElement("div");
      item.className = "coin-toast-item";
      item.style.animationDelay = `${i * 0.35}s`;
      item.innerHTML = `<span class="coin-icon"></span>+${c.amount} ${REASON_LABELS[c.reason] || ""}`;
      toast.appendChild(item);
      setTimeout(() => item.remove(), 2400 + i * 350);
    });
    setCoins(newBalance);
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
      return me;
    })
    .catch((err) => {
      console.error(err);
      coinCount.textContent = "?";
      return null;
    });

  window.Header = { ready, setCoins, setAvatar, update, celebrate };
})();
