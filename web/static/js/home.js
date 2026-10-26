// The home page: you, today's practice trail, and big tiles for everything
// to do. Practice is the biggest; its words change with the day (how far
// to the tokens, or "all done" while practice rests). Tile art is drawn by
// home_icons.js and gently animates.

const TICK_MS = 600;
const $ = (id) => document.getElementById(id);

function minutesLeft(seconds) {
  return Math.max(1, Math.ceil(seconds / 60));
}

function practiceWords(day) {
  if (day.resting_until) {
    return {
      sub: `All done for today! Practice opens ${DayTracker.restingUntil(day)}.`,
      hero: `You earned all your tokens today. Time to play!`,
    };
  }
  if (day.goal_reached) {
    const left = minutesLeft(day.bonus_seconds - day.practiced_seconds);
    return {
      sub: `${left} more minute${left > 1 ? "s" : ""} for a bonus token!`,
      hero: `Goal reached! Keep going for a bonus token, or go have fun.`,
    };
  }
  const left = minutesLeft(day.goal_seconds - day.practiced_seconds);
  return {
    sub: day.practiced_seconds ? `${left} minute${left > 1 ? "s" : ""} to your tokens!` : "Your next lesson is ready!",
    hero: day.practiced_seconds
      ? `Only ${left} minute${left > 1 ? "s" : ""} of practice to earn ${day.goal_tokens} arcade tokens.`
      : `Practice ${minutesLeft(day.goal_seconds)} minutes today to earn ${day.goal_tokens} arcade tokens.`,
  };
}

function render(me) {
  $("home-greeting").textContent = `Welcome back, ${me.learner.name}!`;
  const words = practiceWords(me.day);
  $("home-sub").textContent = words.hero;
  $("practice-sub").textContent = words.sub;
  $("tile-practice").classList.toggle("resting", !!me.day.resting_until);
  DayTracker.render($("home-day"), me.day, { big: true });
  $("arcade-tokens").textContent = `${me.tokens} token${me.tokens === 1 ? "" : "s"}`;
  const pet = (me.avatar.pets || [])[0];
  $("pets-sub").textContent = pet ? `${pet.name} misses you` : "Feed and play";
}

Header.ready.then((me) => {
  if (!me) return;
  let current = me;
  render(me);
  document.addEventListener("avatarchange", (e) => {
    current = e.detail;
    render(current);
  });

  const avatar = $("home-avatar");
  const tiles = [...document.querySelectorAll(".tile-art")];
  let frame = 0;
  const draw = () => {
    drawAvatar(avatar, current.avatar, { frame });
    tiles.forEach((c) => drawHomeIcon(c, c.dataset.icon, frame, current));
  };
  draw();
  setInterval(() => {
    frame += 1;
    draw();
  }, TICK_MS);
});
