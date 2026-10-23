// Runs one scheduler-built session end to end: fetch the plan, render
// each step's prompt, capture keystrokes with timing, submit for
// scoring, show the result, advance. Deliberately plain -- no visual
// polish yet (PLAN.md Section 11a defers that); this exists to prove
// the scheduler + all 5 activity modules actually work when driven by
// real typing in a real browser.
//
// Prompt rendering (shared by every phase, not just warmup): each
// character is tracked individually as "pending" / "current" /
// "correct" / "incorrect", wrapped into a fixed-width scrolling window.
// The DOM for a step's prompt is built ONCE, and each keystroke only
// touches the 1-2 spans that actually changed -- rebuilding the whole
// prompt's HTML on every keystroke was the earlier design, and it
// visibly bogs down on a long (200-600+ char) prompt: a backlog of
// full-DOM rebuilds + scroll animations piles up on the main thread,
// which is what made finishing the last character feel like a delayed,
// "time-based" wait instead of an instant reaction.

const MAX_CHARS_PER_LINE = 24; // ~5 blocks of 4 chars + inter-block gaps

let sessionId = null;
let steps = [];
let stepIndex = 0;
let promptChars = [];
let lineOfChar = []; // which visual line each char index belongs to
let charSpans = []; // DOM span for each char index, built once per step
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
  lineOfChar = computeLineAssignments(promptChars);
  position = 0;
  keystrokes = [];
  lastKeyTime = performance.now();
  stepFinished = false;

  phaseLabel.textContent = step.phase;
  instructionsEl.textContent = step.content.instructions;
  stepResultEl.hidden = true;
  endNowButton.hidden = false;
  buildPromptDom();
  renderProgress();
}

function renderProgress() {
  // Visible characters only -- spaces are part of the typed stream but
  // not meaningful to count for the learner.
  const total = promptChars.filter((c) => c !== " ").length;
  const done = promptChars.slice(0, position).filter((c) => c !== " ").length;
  progressEl.textContent = `${done} / ${total}`;
}

// A hard wrap every MAX_CHARS_PER_LINE characters, independent of
// where the prompt's own word/block spaces fall. A pure space-boundary
// wrap (the earlier approach) breaks badly for content shaped like
// teach's "ffff....f jjjj....j" -- only 2 chunks total, how ever long
// each one is, so it never wraps at all.
function computeLineAssignments(chars) {
  const lines = [];
  let line = 0;
  let lineLength = 0;
  for (const _ch of chars) {
    if (lineLength >= MAX_CHARS_PER_LINE) {
      line += 1;
      lineLength = 0;
    }
    lines.push(line);
    lineLength += 1;
  }
  return lines;
}

// Builds the prompt's DOM exactly once per step and keeps a flat
// charSpans[] array so later keystrokes can update individual spans
// directly instead of re-rendering everything.
function buildPromptDom() {
  const lineCount = lineOfChar.length ? lineOfChar[lineOfChar.length - 1] + 1 : 0;
  const rows = [];
  for (let l = 0; l < lineCount; l++) rows.push(document.createElement("div"));
  rows.forEach((row) => row.classList.add("prompt-line"));

  charSpans = promptChars.map((ch, i) => {
    const span = document.createElement("span");
    span.className = ch === " " ? "space pending" : "pending";
    span.textContent = ch === " " ? "" : ch;
    rows[lineOfChar[i]].appendChild(span);
    return span;
  });

  promptEl.replaceChildren(...rows);
  setCurrentSpan(0);
}

function setCurrentSpan(index) {
  if (index < charSpans.length) {
    charSpans[index].classList.add("current");
  }
}

function clearCurrentSpan(index) {
  if (index < charSpans.length) {
    charSpans[index].classList.remove("current");
  }
}

function scrollToCurrentLine() {
  const currentLine = lineOfChar[Math.min(position, lineOfChar.length - 1)];
  const lineEl = promptEl.children[currentLine];
  if (lineEl) {
    lineEl.scrollIntoView({ behavior: "smooth", block: "end" });
  }
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

  const previousLine = lineOfChar[position];
  clearCurrentSpan(position);
  charSpans[position].classList.remove("pending");
  charSpans[position].classList.add(correct ? "correct" : "incorrect");

  position += 1;
  setCurrentSpan(position);
  renderProgress();

  if (position >= promptChars.length) {
    finishStep();
    return;
  }

  if (lineOfChar[position] !== previousLine) {
    scrollToCurrentLine();
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
