// Shared top bar on every page (PLAN.md Section 11c): brand, coin
// counter, and the player's avatar (links to the profile hub). Profiles
// (PLAN.md 11d) will add the switch-player menu here.
//
// Needs sprites.js and avatar.js loaded first. Exposes window.Header so
// pages can update coins without refetching.

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
      <a class="topbar-avatar" href="/profile" title="My profile"></a>
    </div>`;
  document.body.prepend(bar);

  const coinCount = bar.querySelector("#coin-count");
  const coinPill = bar.querySelector(".coin-pill");
  const avatarCanvas = makeAvatarCanvas(48);
  bar.querySelector(".topbar-avatar").appendChild(avatarCanvas);

  const toast = document.createElement("div");
  toast.className = "coin-toast";
  document.body.appendChild(toast);

  const REASON_LABELS = {
    lesson: "Lesson",
    key_mastered: "New key mastered!",
    session_complete: "Session complete!",
  };

  function setCoins(n) {
    coinCount.textContent = n.toLocaleString();
    coinPill.classList.remove("bump");
    void coinPill.offsetWidth; // restart the animation
    coinPill.classList.add("bump");
  }

  function setAvatar(equipped) {
    drawAvatar(avatarCanvas, equipped);
  }

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
      if (!r.ok) throw new Error(`/api/me returned ${r.status}`);
      return r.json();
    })
    .then((me) => {
      setCoins(me.coins);
      setAvatar(me.avatar);
      return me;
    })
    .catch((err) => {
      console.error(err);
      coinCount.textContent = "?";
      return null;
    });

  window.Header = { ready, setCoins, setAvatar, celebrate };
})();
