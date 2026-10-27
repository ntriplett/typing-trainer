// The home page: you, today's practice trail, and big tiles for everything
// to do. Practice is the biggest; its words change with the day (how far
// to the tokens, or "all done" while practice rests). Tile art is drawn by
// home_icons.js and gently animates.

const TICK_MS = 600;
const $ = (id) => document.getElementById(id);

// The hero's greeting, picked by where the day is at ({name} is filled in).
const GREETINGS = {
  hello: [
    "Welcome back, {name}!", "Hi, {name}! Ready to type?", "Good to see you, {name}!",
    "Hey {name}, your keyboard missed you!", "Hello, {name}! Fingers on home?", "{name} is here! Let's go!",
    "Howdy, {name}!", "A brand new day, {name}!", "Ready for an adventure, {name}?",
    "Let's wake up those fingers, {name}!", "Hi {name}! The tokens are waiting.", "Welcome home, {name}!",
  ],
  morning: ["Good morning, {name}!"],
  afternoon: ["Good afternoon, {name}!"],
  evening: ["Good evening, {name}!"],
  mid: [
    "Nice going, {name}!", "You're on a roll, {name}!", "Keep it up, {name}!", "Look at those fingers fly!",
    "Great work so far, {name}!", "Steady and strong, {name}!", "Every key counts, {name}!",
    "You're doing great!", "Back for more? Awesome!", "Keep those keys clicking!",
  ],
  almost: [
    "So close, {name}!", "Almost there, {name}!", "Just a little more, {name}!", "The tokens are in sight!",
    "One more push, {name}!", "Nearly there! You've got this!",
  ],
  goal: [
    "You did it, {name}!", "Goal reached! Woohoo!", "Tokens earned, {name}!", "High five, {name}!",
    "Amazing work today, {name}!", "Daily goal: done!", "Want a bonus token, {name}?",
  ],
  celebrate: [
    "All done! Time to play, {name}!", "Superstar typing, {name}!", "The arcade is calling!",
    "Every token earned! Wow!", "You earned your fun, {name}!", "Champion typist, {name}!",
    "Go spend those tokens!",
  ],
  winddown: [
    "What a day, {name}!", "Nice and cozy now, {name}.", "Time to relax, {name}.",
    "Your pets say thanks, {name}!", "Rest those fingers, {name}.", "Great job today. See you soon!",
    "Sweet dreams of keyboards, {name}.",
  ],
};

function greetingMood(me) {
  const day = me.day;
  if ((day.resting_until || day.goal_reached) && me.tokens === 0) return "winddown";
  if (day.resting_until) return "celebrate";
  if (day.goal_reached) return "goal";
  if (day.practiced_seconds === 0) return "hello";
  return day.goal_seconds - day.practiced_seconds <= 120 ? "almost" : "mid";
}

const greetingRoll = Math.random(); // one pick per visit, so it doesn't flicker on updates

function greeting(me) {
  const mood = greetingMood(me);
  let pool = GREETINGS[mood];
  if (mood === "hello") {
    const hour = new Date().getHours();
    pool = pool.concat(GREETINGS[hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening"]);
  }
  return pool[Math.floor(greetingRoll * pool.length)].replace("{name}", me.learner.name);
}

// Locked rooms show a "?" block until enough letters are learned (app/unlocks.py).
function renderLocks(me) {
  const u = me.unlocks;
  const lock = (room, name, openName, openSub, art) => {
    const tile = document.querySelector(`.tile-${room}`);
    tile.classList.toggle("locked", !u[room]);
    tile.querySelector(".tile-art").dataset.icon = u[room] ? art : "mystery";
    $(`${room}-name`).textContent = u[room] ? openName : "Mystery";
    if (!u[room]) $(`${room}-sub`).textContent = `Learn the ${room === "pets" ? "home" : "top"} row!`;
    else if (openSub) $(`${room}-sub`).textContent = openSub;
  };
  const pet = (me.avatar.pets || [])[0];
  lock("pets", "Pet Room", "Pet Room", u.free_pet ? "A free pet is waiting!" : pet ? `${pet.name} misses you` : "Feed and play", "pets");
  lock("bedroom", "Bedroom", "Bedroom", "Decorate it", "bedroom");
}

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
  $("home-greeting").textContent = greeting(me);
  const words = practiceWords(me.day);
  $("home-sub").textContent = words.hero;
  $("practice-sub").textContent = words.sub;
  $("tile-practice").classList.toggle("resting", !!me.day.resting_until);
  DayTracker.render($("home-day"), me.day, { big: true });
  $("arcade-tokens").textContent = `${me.tokens} token${me.tokens === 1 ? "" : "s"}`;
  renderLocks(me);
  $("garden-sub").textContent = gardenWords(me);
}

function gardenWords(me) {
  const g = me.garden;
  if (g.ready) return `${g.ready} veggie${g.ready > 1 ? "s" : ""} to pick!`;
  if (g.basket_total) return "Veggies in your basket!";
  if (g.seeds && g.growing < 10) return "Plant your seed!";
  if (g.growing) return "Growing nicely";
  return "Practice for a seed";
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
