// Runs one scheduler-built session end to end: fetch the plan, render
// each step's prompt, capture keystrokes with timing, submit for
// scoring, show the result, advance. Deliberately plain -- no visual
// polish yet (PLAN.md Section 11a defers that); this exists to prove
// the scheduler + all 5 activity modules actually work when driven by
// real typing in a real browser.

let sessionId = null;
let steps = [];
let stepIndex = 0;
let promptChars = [];
let position = 0;
let keystrokes = [];
let lastKeyTime = 0;
const stepResults = [];

const startScreen = document.getElementById("start-screen");
const sessionScreen = document.getElementById("session-screen");
const completeScreen = document.getElementById("complete-screen");
const phaseLabel = document.getElementById("phase-label");
const instructionsEl = document.getElementById("instructions");
const promptEl = document.getElementById("prompt");
const stepResultEl = document.getElementById("step-result");
const resultSummaryEl = document.getElementById("result-summary");

document.getElementById("start-button").addEventListener("click", startSession);
document.getElementById("next-button").addEventListener("click", advanceStep);
window.addEventListener("keydown", handleKeydown);

async function startSession() {
  const res = await fetch("/api/session/start", { method: "POST" });
  const data = await res.json();
  sessionId = data.session_id;
  steps = data.steps;
  stepIndex = 0;

  startScreen.hidden = true;
  sessionScreen.hidden = false;
  renderStep();
}

function renderStep() {
  const step = steps[stepIndex];
  promptChars = step.content.prompt.split("");
  position = 0;
  keystrokes = [];
  lastKeyTime = performance.now();

  phaseLabel.textContent = step.phase;
  instructionsEl.textContent = step.content.instructions;
  stepResultEl.hidden = true;
  renderPrompt();
}

function renderPrompt() {
  const html = promptChars
    .map((ch, i) => {
      const cls = i < position ? "correct" : i === position ? "pending" : "pending";
      const display = ch === " " ? "&nbsp;" : ch;
      return `<span class="${cls}">${display}</span>`;
    })
    .join("");
  promptEl.innerHTML = html;
}

function handleKeydown(e) {
  if (sessionScreen.hidden || !stepResultEl.hidden) {
    return; // not mid-step (not started yet, or waiting on "Next")
  }
  if (e.key.length !== 1) {
    return; // ignore Shift/Enter/Tab/etc.
  }
  e.preventDefault();

  const expected = promptChars[position];
  const typed = e.key;
  const now = performance.now();
  const latencyMs = Math.round(now - lastKeyTime);
  lastKeyTime = now;

  keystrokes.push({
    expected_char: expected,
    typed_char: typed,
    correct: typed === expected,
    latency_ms: latencyMs,
  });

  position += 1;
  renderPrompt();

  if (position >= promptChars.length) {
    finishStep();
  }
}

async function finishStep() {
  const res = await fetch(`/api/session/${sessionId}/steps/${stepIndex}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keystrokes }),
  });
  const data = await res.json();
  stepResults.push({ phase: steps[stepIndex].phase, ...data.result });

  resultSummaryEl.textContent =
    `${steps[stepIndex].phase}: ${Math.round(data.result.accuracy * 100)}% accuracy, ` +
    `${data.result.wpm.toFixed(1)} WPM — ${data.result.reward_signal}`;
  stepResultEl.hidden = false;

  if (data.session_complete) {
    document.getElementById("next-button").textContent = "See summary";
  }
}

function advanceStep() {
  if (stepIndex >= steps.length - 1) {
    showSummary();
    return;
  }
  stepIndex += 1;
  renderStep();
}

function showSummary() {
  sessionScreen.hidden = true;
  completeScreen.hidden = false;
  const list = document.getElementById("summary-list");
  list.innerHTML = stepResults
    .map(
      (r) =>
        `<li>${r.phase}: ${Math.round(r.accuracy * 100)}% accuracy, ${r.wpm.toFixed(1)} WPM — ${r.reward_signal}</li>`
    )
    .join("");
}
