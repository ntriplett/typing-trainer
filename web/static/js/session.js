// Runs one scheduler-built session end to end: fetch the plan, render
// each step's prompt, capture keystrokes with timing, submit for
// scoring, show the result, advance. Deliberately plain -- no visual
// polish yet (PLAN.md Section 11a defers that); this exists to prove
// the scheduler + all 5 activity modules actually work when driven by
// real typing in a real browser.
//
// Prompt rendering (shared by every phase, not just warmup): each
// character is tracked individually as "pending" / "current" /
// "correct" / "incorrect", and grouped into visual lines of 5 blocks
// (the prompt's existing space-separated 4-char chunks) so the text
// wraps into a fixed 4-line window and auto-scrolls as typing advances,
// instead of running on as one long unbroken block.

const BLOCKS_PER_LINE = 5;

let sessionId = null;
let steps = [];
let stepIndex = 0;
let promptChars = [];
let charStates = []; // "pending" | "correct" | "incorrect", parallel to promptChars
let lineOfChar = []; // which visual line each char index belongs to
let position = 0;
let keystrokes = [];
let lastKeyTime = 0;
let stepFinished = false; // guards against double-submitting the same step
const stepResults = [];

const startScreen = document.getElementById("start-screen");
const sessionScreen = document.getElementById("session-screen");
const completeScreen = document.getElementById("complete-screen");
const phaseLabel = document.getElementById("phase-label");
const instructionsEl = document.getElementById("instructions");
const progressEl = document.getElementById("progress");
const promptEl = document.getElementById("prompt");
const stepResultEl = document.getElementById("step-result");
const resultSummaryEl = document.getElementById("result-summary");
const endNowButton = document.getElementById("end-now-button");

document.getElementById("start-button").addEventListener("click", startSession);
document.getElementById("next-button").addEventListener("click", advanceStep);
endNowButton.addEventListener("click", endStepNow);
document.getElementById("home-button").addEventListener("click", goHome);
document.getElementById("complete-home-button").addEventListener("click", goHome);
document.getElementById("complete-new-session-button").addEventListener("click", () => {
  window.location.reload();
});
window.addEventListener("keydown", handleKeydown);

function goHome() {
  window.location.href = "/";
}

async function startSession() {
  const quick = document.getElementById("quick-test-checkbox").checked;
  const res = await fetch(`/api/session/start${quick ? "?quick=1" : ""}`, { method: "POST" });
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
  charStates = promptChars.map(() => "pending");
  lineOfChar = computeLineAssignments(promptChars);
  position = 0;
  keystrokes = [];
  lastKeyTime = performance.now();
  stepFinished = false;

  phaseLabel.textContent = step.phase;
  instructionsEl.textContent = step.content.instructions;
  stepResultEl.hidden = true;
  endNowButton.hidden = false;
  renderPrompt();
  renderProgress();
}

function renderProgress() {
  // Visible characters only -- spaces are part of the typed stream but
  // not meaningful to count for the learner.
  const total = promptChars.filter((c) => c !== " ").length;
  const done = promptChars.slice(0, position).filter((c) => c !== " ").length;
  progressEl.textContent = `${done} / ${total}`;
}

// Groups characters into visual lines of BLOCKS_PER_LINE space-separated
// chunks. A chunk boundary is a literal space character in the prompt
// (the server already groups output into ~4-char chunks); every 5th
// chunk starts a new line. The space itself stays part of whichever
// line precedes it, same as any other character in the typed stream.
function computeLineAssignments(chars) {
  const lines = [];
  let line = 0;
  let blocksInLine = 0;
  for (const ch of chars) {
    lines.push(line);
    if (ch === " ") {
      blocksInLine += 1;
      if (blocksInLine >= BLOCKS_PER_LINE) {
        blocksInLine = 0;
        line += 1;
      }
    }
  }
  return lines;
}

function renderPrompt() {
  const lineCount = lineOfChar.length ? lineOfChar[lineOfChar.length - 1] + 1 : 0;
  const rows = [];
  for (let l = 0; l < lineCount; l++) rows.push([]);

  promptChars.forEach((ch, i) => {
    const state = i === position ? "current" : charStates[i];
    const cls = ch === " " ? `space ${state}` : state;
    const content = ch === " " ? "" : escapeHtml(ch);
    rows[lineOfChar[i]].push(`<span class="${cls}" data-index="${i}">${content}</span>`);
  });

  promptEl.innerHTML = rows
    .map((spans) => `<div class="prompt-line">${spans.join("")}</div>`)
    .join("");

  const currentLine = lineOfChar[Math.min(position, lineOfChar.length - 1)];
  const lineEl = promptEl.children[currentLine];
  if (lineEl) {
    lineEl.scrollIntoView({ behavior: "smooth", block: "end" });
  }
}

function escapeHtml(ch) {
  return ch === "<" ? "&lt;" : ch === "&" ? "&amp;" : ch;
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
  const correct = typed === expected;

  keystrokes.push({
    expected_char: expected,
    typed_char: typed,
    correct,
    latency_ms: latencyMs,
  });
  charStates[position] = correct ? "correct" : "incorrect";

  position += 1;
  renderPrompt();
  renderProgress();

  if (position >= promptChars.length) {
    finishStep();
  }
}

async function finishStep() {
  if (stepFinished) return; // handles a keystroke racing with "End now"
  stepFinished = true;
  endNowButton.hidden = true;

  const res = await fetch(`/api/session/${sessionId}/steps/${stepIndex}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keystrokes }),
  });
  const data = await res.json();
  stepResults.push({ phase: steps[stepIndex].phase, ...data.result });

  document.getElementById("result-headline").textContent = headlineFor(data.result.reward_signal);
  resultSummaryEl.textContent =
    `${Math.round(data.result.accuracy * 100)}% accuracy, ${data.result.wpm.toFixed(1)} WPM. ` +
    (data.session_complete
      ? "Click below to see your session summary."
      : "Click below to move on to the next lesson.");
  stepResultEl.hidden = false;

  document.getElementById("next-button").textContent = data.session_complete
    ? "See summary →"
    : "Next lesson →";
}

// This is the end-of-lesson signal: once a step's keystrokes are
// scored, a clear "you're done, here's how it went" state replaces the
// typing view until the learner chooses to continue.
function headlineFor(rewardSignal) {
  if (rewardSignal === "nailed_it") return "🎉 Great job!";
  if (rewardSignal === "solid") return "✅ Nice work!";
  return "💪 Good effort — keep practicing!";
}

function advanceStep() {
  if (stepIndex >= steps.length - 1) {
    showSummary();
    return;
  }
  stepIndex += 1;
  renderStep();
}

// "End this step now" scores whatever was actually typed so far rather
// than discarding it -- a deliberate "I'm done with this one" control,
// not a way to skip being scored.
function endStepNow() {
  finishStep();
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
