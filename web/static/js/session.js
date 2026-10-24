// Runs one scheduler-built session end to end: collect the pre-session
// config, fetch the skeleton + first step, render each step's prompt
// (fetching its content lazily, right before it's needed), capture
// keystrokes with timing, submit for scoring, show the result, advance.
// Each scored step also pays coins (PLAN.md 11c), shown here and in the
// shared header (header.js).

const IDLE_PAUSE_MS = 5000; // no keystroke in this long -> the session timer pauses
const WRONG_STREAK_LOCKOUT = 5; // this many consecutive misses -> must get the next one right

let sessionId = null;
let skeleton = []; // [{phase, activity_id, focus_keys, duration_s}], no content
let contentCache = {}; // stepIndex -> ActivityContent
let stepIndex = 0;
let keystrokes = [];
let lastKeyTime = 0;
let stepFinished = false; // guards against double-submitting the same step
let consecutiveWrong = 0;
let locked = false;
const stepResults = [];
let sessionCoins = 0; // total coins earned this session, for the summary

// Overall session timer: counts up only while actively typing (paused
// when idle for IDLE_PAUSE_MS), compared against the skeleton's total
// planned time budget.
let totalBudgetMs = 0;
let activeElapsedMs = 0;
let timerIntervalId = null;
const TIMER_TICK_MS = 200;

const startScreen = document.getElementById("start-screen");
const sessionScreen = document.getElementById("session-screen");
const completeScreen = document.getElementById("complete-screen");
const phaseLabel = document.getElementById("phase-label");
const instructionsEl = document.getElementById("instructions");
const progressEl = document.getElementById("progress");
const lockMessageEl = document.getElementById("lock-message");
// One line at a time, wrapped between words (prompt_view.js).
const view = new PromptView(document.getElementById("prompt"));
const stepResultEl = document.getElementById("step-result");
const resultSummaryEl = document.getElementById("result-summary");
const resultCoinsEl = document.getElementById("result-coins");
const endNowButton = document.getElementById("end-now-button");
const planPreviewEl = document.getElementById("plan-preview");
const timeRemainingEl = document.getElementById("time-remaining");
const stepProgressEl = document.getElementById("step-progress");

document.getElementById("start-button").addEventListener("click", startSession);
document.getElementById("next-button").addEventListener("click", advanceStep);
endNowButton.addEventListener("click", endStepNow);
document.getElementById("home-button").addEventListener("click", goHome);
document.getElementById("complete-home-button").addEventListener("click", goHome);
document.getElementById("complete-new-session-button").addEventListener("click", () => {
  window.location.reload();
});
window.addEventListener("keydown", handleKeydown);

// --- pre-session config sliders ----------------------------------------------

const durationSlider = document.getElementById("duration-slider");
const learnPracticeSlider = document.getElementById("learn-practice-slider");
const focusSlider = document.getElementById("focus-slider");

durationSlider.addEventListener("input", () => {
  document.getElementById("duration-value").textContent = durationSlider.value;
});
learnPracticeSlider.addEventListener("input", () => {
  document.getElementById("learn-practice-value").textContent = learnPracticeLabel(
    Number(learnPracticeSlider.value)
  );
});
focusSlider.addEventListener("input", () => {
  document.getElementById("focus-value").textContent = focusLabel(Number(focusSlider.value));
});

function learnPracticeLabel(v) {
  if (v <= 20) return "Mostly practice";
  if (v >= 80) return "Push new letters hard";
  return "Balanced";
}

function focusLabel(v) {
  if (v <= 20) return "General practice";
  if (v >= 80) return "Focus on problem letters";
  return "A bit of both";
}

function goHome() {
  window.location.href = "/";
}

// --- session lifecycle ---------------------------------------------------------

async function startSession() {
  const quick = document.getElementById("quick-test-checkbox").checked;
  const config = {
    duration_minutes: Number(durationSlider.value),
    learn_vs_practice: Number(learnPracticeSlider.value) / 100,
    focus_vs_general: Number(focusSlider.value) / 100,
  };

  const res = await fetch(`/api/session/start${quick ? "?quick=1" : ""}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  const data = await res.json();

  sessionId = data.session_id;
  skeleton = data.steps;
  contentCache = { 0: data.first_step_content };
  stepIndex = 0;
  totalBudgetMs = skeleton.reduce((sum, s) => sum + s.duration_s, 0) * 1000;
  activeElapsedMs = 0;

  startScreen.hidden = true;
  sessionScreen.hidden = false;
  startSessionTimer();
  await renderStep();
}

function startSessionTimer() {
  stopSessionTimer();
  renderTimeRemaining(); // show the full budget immediately, don't wait for the first tick
  timerIntervalId = setInterval(() => {
    const idle = performance.now() - lastKeyTime > IDLE_PAUSE_MS;
    timeRemainingEl.classList.toggle("paused", idle);
    if (!idle) {
      activeElapsedMs += TIMER_TICK_MS;
    }
    renderTimeRemaining();
  }, TIMER_TICK_MS);
}

function stopSessionTimer() {
  if (timerIntervalId !== null) {
    clearInterval(timerIntervalId);
    timerIntervalId = null;
  }
}

function renderTimeRemaining() {
  const remainingMs = Math.max(0, totalBudgetMs - activeElapsedMs);
  if (remainingMs === 0) {
    timeRemainingEl.textContent = "Time's up — finish this lesson!";
    return;
  }
  const totalSeconds = Math.round(remainingMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  timeRemainingEl.textContent = `${minutes}:${String(seconds).padStart(2, "0")} left`;
}

async function fetchStepContent(index) {
  if (contentCache[index]) return contentCache[index];
  const res = await fetch(`/api/session/${sessionId}/steps/${index}/content`);
  const data = await res.json();
  contentCache[index] = data.content;
  return data.content;
}

async function renderStep() {
  const content = await fetchStepContent(stepIndex);
  keystrokes = [];
  lastKeyTime = performance.now();
  stepFinished = false;
  consecutiveWrong = 0;
  locked = false;
  lockMessageEl.hidden = true;

  phaseLabel.textContent = skeleton[stepIndex].phase;
  instructionsEl.textContent = content.instructions;
  stepResultEl.hidden = true;
  endNowButton.hidden = false;
  view.load(content.prompt);
  renderProgress();
  renderPlanPreview();
}

function renderProgress() {
  // Visible characters only -- spaces are part of the typed stream but
  // not meaningful to count for the learner.
  const text = view.typeable;
  const total = text.replace(/ /g, "").length;
  const done = text.slice(0, view.typed).replace(/ /g, "").length;
  progressEl.textContent = `${done} / ${total}`;
}

function renderPlanPreview() {
  planPreviewEl.innerHTML = skeleton
    .map((step, i) => {
      const status = i < stepIndex || (i === stepIndex && !stepResultEl.hidden)
        ? "done"
        : i === stepIndex
          ? "current"
          : "";
      return `<span class="plan-phase ${status}">${step.phase}</span>`;
    })
    .join("");
  stepProgressEl.textContent = `Step ${stepIndex + 1} of ${skeleton.length}`;
}

function handleKeydown(e) {
  if (sessionScreen.hidden || !stepResultEl.hidden) {
    return; // not mid-step (not started yet, or waiting on "Next")
  }
  if (e.key.length !== 1) {
    return; // ignore Shift/Enter/Tab/etc.
  }
  e.preventDefault();

  const expected = view.expected;
  const typed = e.key;
  const correct = typed === expected;

  // Latency is measured against the PREVIOUS keystroke's timestamp,
  // so capture "now" before overwriting lastKeyTime with it (also the
  // same timestamp the idle-pause timer uses to detect activity).
  const now = performance.now();
  const latencyMs = Math.round(now - lastKeyTime) || 1;
  lastKeyTime = now;

  if (locked) {
    // Prevent-smashing lockout: ignore anything that isn't the correct
    // character for the current position -- no keystroke recorded,
    // no advancing, until the learner actually gets it right.
    if (!correct) return;
    locked = false;
    view.setLocked(false);
    lockMessageEl.hidden = true;
    consecutiveWrong = 0;
  } else if (!correct) {
    consecutiveWrong += 1;
    if (consecutiveWrong >= WRONG_STREAK_LOCKOUT) {
      locked = true;
      lockMessageEl.hidden = false;
      view.setLocked(true);
      return; // this miss itself still doesn't advance; next miss is ignored until correct
    }
  } else {
    consecutiveWrong = 0;
  }

  keystrokes.push({ expected_char: expected, typed_char: typed, correct, latency_ms: latencyMs });

  const finished = view.mark(correct);
  renderProgress();
  if (finished) finishStep();
}

async function finishStep() {
  if (stepFinished) return; // handles a keystroke racing with "End now"
  stepFinished = true;
  endNowButton.hidden = true;
  lockMessageEl.hidden = true;

  // Out of time: this lesson is the last one, even if more were planned.
  const timeUp = activeElapsedMs >= totalBudgetMs;
  const res = await fetch(`/api/session/${sessionId}/steps/${stepIndex}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // Spaces dropped at line wraps aren't typed; they don't count against finishing.
    body: JSON.stringify({ keystrokes, end_session: timeUp, skipped_chars: view.skipped }),
  });
  const data = await res.json();
  if (data.session_complete) {
    skeleton = skeleton.slice(0, stepIndex + 1); // drop the unplayed steps
  }
  stepResults.push({ phase: skeleton[stepIndex].phase, ...data.result });

  document.getElementById("result-headline").textContent = headlineFor(data.result.reward_signal);
  resultSummaryEl.textContent =
    `${Math.round(data.result.accuracy * 100)}% accuracy, ${data.result.wpm.toFixed(1)} WPM. ` +
    (data.session_complete
      ? (timeUp ? "Time's up — great session! " : "") + "Click below to see your session summary."
      : "Click below to move on to the next lesson.");
  showCoins(data.coins_earned || [], data.coin_balance);
  stepResultEl.hidden = false;
  renderPlanPreview();

  document.getElementById("next-button").textContent = data.session_complete
    ? "See summary →"
    : "Next lesson →";

  if (data.session_complete) {
    stopSessionTimer();
  }
}

function showCoins(earned, balance) {
  const total = earned.reduce((sum, c) => sum + c.amount, 0);
  sessionCoins += total;
  resultCoinsEl.hidden = total === 0;
  resultCoinsEl.innerHTML = `<span class="coin-icon"></span>+${total} coins`;
  if (earned.length && window.Header) Header.celebrate(earned, balance);
}

// This is the end-of-lesson signal: once a step's keystrokes are
// scored, a clear "you're done, here's how it went" state replaces the
// typing view until the learner chooses to continue.
function headlineFor(rewardSignal) {
  if (rewardSignal === "nailed_it") return "🎉 Great job!";
  if (rewardSignal === "solid") return "✅ Nice work!";
  return "💪 Good effort — keep practicing!";
}

async function advanceStep() {
  if (stepIndex >= skeleton.length - 1) {
    showSummary();
    return;
  }
  stepIndex += 1;
  await renderStep();
}

// "End this step now" scores whatever was actually typed so far rather
// than discarding it -- a deliberate "I'm done with this one" control,
// not a way to skip being scored.
function endStepNow() {
  finishStep();
}

function showSummary() {
  stopSessionTimer();
  sessionScreen.hidden = true;
  completeScreen.hidden = false;
  document.getElementById("session-coins").innerHTML =
    `<span class="coin-icon"></span>You earned ${sessionCoins.toLocaleString()} coins!`;
  const list = document.getElementById("summary-list");
  list.innerHTML = stepResults
    .map(
      (r) =>
        `<li>${r.phase}: ${Math.round(r.accuracy * 100)}% accuracy, ${r.wpm.toFixed(1)} WPM — ${r.reward_signal}</li>`
    )
    .join("");
}
