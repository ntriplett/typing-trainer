// The practice page: one brain-picked lesson at a time (app/brain.py).
// Asks /api/lesson/next, runs warmups and practice on the shared practice
// stage (practice_stage.js), and hands learn lessons to the teach page
// (/teach/<module>?lesson=<id>), which comes back here when it's done.
// After each lesson: how it went, coins, tokens and seeds, and Enter for the next
// one -- or Esc/Home, since the day is free-form. When today's practice is
// all done (the bonus is in), it shows when practice opens again.

const IDLE_MS = 5000; // a gap longer than this between keys doesn't count as practice time

const $ = (id) => document.getElementById(id);
let lesson = null; // the brain's plan for this lesson (/api/lesson/next's "lesson")
let content = null;
let contentLoaded = false; // tests wait on this
let activeMs = 0;
let lastKeyAt = 0;
let finished = false;
let resting = false;

const stage = new PracticeStage($("stage"), {
  onKey: () => {
    const now = performance.now();
    activeMs += Math.min(IDLE_MS, now - lastKeyAt);
    lastKeyAt = now;
  },
  onFinish: (typed) => finishLesson(typed),
});
const view = stage.view; // tests read view.typeable / view.typed

const KIND_LABELS = { warmup: "Warmup", practice: "Practice" };

function showRest(day) {
  resting = true;
  $("loading").hidden = true;
  $("lesson-screen").hidden = true;
  $("rest-screen").hidden = false;
  $("rest-until").textContent = DayTracker.restingUntil(day);
  DayTracker.render($("rest-day"), day, { big: true });
}

async function nextLesson() {
  $("loading").hidden = false;
  $("lesson-screen").hidden = true;
  contentLoaded = false;
  const res = await fetch("/api/lesson/next", { method: "POST" });
  if (res.status === 409) {
    const day = await (await fetch("/api/day")).json();
    return showRest(day);
  }
  const data = await res.json();
  lesson = data.lesson;
  content = data.content;
  if (lesson.kind === "learn") {
    const keys = lesson.teach_keys ? `keys=${encodeURIComponent(lesson.teach_keys)}&` : "";
    location.href = `/teach/${lesson.activity_id}?${keys}lesson=${lesson.lesson_id}`;
    return;
  }
  startLesson();
}

function startLesson() {
  finished = false;
  activeMs = 0;
  lastKeyAt = performance.now();
  $("loading").hidden = true;
  $("lesson-screen").hidden = false;
  $("lesson-result").hidden = true;
  $("end-now-button").hidden = false;
  stage.load(content, {
    label: lesson.comfort ? "An easy one" : KIND_LABELS[lesson.kind] || "Practice",
    hintRef: `lesson:${lesson.lesson_id}`,
  });
  contentLoaded = true;
}

function headlineFor(result) {
  if (result.reward_signal === "nailed_it") return "🎉 Great job!";
  if (result.reward_signal === "solid") return "✅ Nice work!";
  return "💪 Good effort! The next one will be easier.";
}

function rewardsHtml(data) {
  const coins = data.coins_earned.reduce((sum, c) => sum + c.amount, 0);
  const tokens = data.tokens_earned.reduce((sum, t) => sum + t.amount, 0);
  const parts = [];
  if (coins) parts.push(`<span class="coin-icon"></span>+${coins.toLocaleString()} coins`);
  if (tokens) parts.push(`<span class="token-icon big"></span>+${tokens} arcade token${tokens > 1 ? "s" : ""}!`);
  if (data.seeds_earned && data.seeds_earned.length) parts.push(`<span class="seed-icon big"></span>+1 seed!`);
  return parts.join(" ");
}

function dayLine(day) {
  if (day.resting_until) return "That's all your practice for today. Every token earned!";
  if (day.goal_reached) {
    const left = Math.max(1, Math.ceil((day.bonus_seconds - day.practiced_seconds) / 60));
    return `Goal reached! ${left} more minute${left > 1 ? "s" : ""} for a bonus token.`;
  }
  if (!day.seed_reached) {
    const left = Math.max(1, Math.ceil((day.seed_seconds - day.practiced_seconds) / 60));
    return `${left} more minute${left > 1 ? "s" : ""} to a seed and watering your garden.`;
  }
  const left = Math.max(1, Math.ceil((day.goal_seconds - day.practiced_seconds) / 60));
  return `${left} more minute${left > 1 ? "s" : ""} to your tokens.`;
}

async function finishLesson({ keystrokes, skipped }) {
  if (finished) return;
  finished = true;
  $("end-now-button").hidden = true;
  const res = await fetch(`/api/lesson/${lesson.lesson_id}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keystrokes, skipped_chars: skipped, active_ms: Math.round(activeMs) }),
  });
  if (!res.ok) return nextLesson(); // the server forgot it (restarted): just get a new one
  const data = await res.json();
  const r = data.result;
  $("result-headline").textContent = headlineFor(r);
  $("result-summary").textContent = `${Math.round(r.accuracy * 100)}% accuracy, ${r.wpm.toFixed(1)} WPM. ${dayLine(data.day)}`;
  $("result-rewards").innerHTML = rewardsHtml(data);
  resting = !!data.day.resting_until;
  $("next-button").hidden = resting;
  $("arcade-button").hidden = !resting;
  $("result-keys").innerHTML = resting
    ? `Press ${keycap("Enter")} for the arcade, or ${keycap("Esc")} to go home.`
    : `Press ${keycap("Enter")} for the next lesson, or ${keycap("Esc")} to go home.`;
  $("lesson-result").hidden = false;

  if (window.Header) {
    Header.celebrate(data.coins_earned, data.coin_balance);
    Header.setDay(data.day);
    Header.celebrateTokens(data.tokens_earned, data.token_balance);
    Header.celebrateSeeds(data);
  }
}

$("next-button").addEventListener("click", nextLesson);
$("end-now-button").addEventListener("click", () => stage.finish());

window.addEventListener("keydown", (e) => {
  const resultShown = !$("lesson-result").hidden && !$("lesson-screen").hidden;
  if (e.key === "Escape" && (resultShown || resting)) {
    location.href = "/";
  } else if (e.key === "Enter" && resultShown) {
    e.preventDefault();
    if (resting) location.href = "/arcade";
    else nextLesson();
  }
});

nextLesson();
