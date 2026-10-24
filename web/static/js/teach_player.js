// Runs any keyboard-driven teach module (app/activities/teach_steps.py) at
// /teach/<module id>. Everything moves on from a key press, so hands stay
// on home the whole lesson:
//   - "show" steps wait for their advance_key (e.g. Space with a thumb),
//   - "type" steps finish when the prompt is typed (a wrong key doesn't
//     move on; you retry it), then move on by themselves.
// At the end: Space to go again, Enter to pick another lesson (/teach-lab).
// The query string (?keys=dk for the key-pair module) is passed through.
//
// Needs keyboard_data.js, teach_keyboard.js, and prompt_view.js loaded first.

const FINGER_NAMES = {
  left_pinky: "left pinky", left_ring: "left ring finger", left_middle: "left middle finger",
  left_index: "left pointer finger", right_index: "right pointer finger",
  right_middle: "right middle finger", right_ring: "right ring finger", right_pinky: "right pinky",
  thumb: "thumb",
};
const NEXT_STEP_DELAY_MS = 700;

const moduleId = decodeURIComponent(location.pathname.split("/").pop());
const kb = new TeachKeyboard(document.getElementById("teach-keyboard"));
const el = (id) => document.getElementById(id);
const view = new PromptView(el("teach-lines"));

let content = null;
let steps = [];
let stepIndex = 0;
let busy = true; // between steps, or still loading: ignore keys
let finished = false;
let lastKeyAt = 0;
const keystrokes = []; // type steps only; show-step presses aren't scored

// "[F]" in step text -> a keycap.
function keycap(key) {
  const label = key === " " ? "Space" : key.length === 1 ? key.toUpperCase() : key;
  return `<kbd class="keycap">${escapeHtml(label)}</kbd>`;
}

function richText(text) {
  return escapeHtml(text).replace(/\[([^\]]+)\]/g, (_, k) => keycap(k === "Space" ? " " : k));
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function setHint(html, kind = "") {
  const hint = el("teach-hint");
  hint.innerHTML = html;
  hint.className = kind;
}

function renderProgress() {
  el("teach-progress").innerHTML = steps
    .map((_, i) => `<span class="dot${i < stepIndex ? " done" : ""}${i === stepIndex ? " now" : ""}"></span>`)
    .join("");
}

function renderStep() {
  const step = steps[stepIndex];
  renderProgress();
  el("teach-title").innerHTML = richText(step.title);
  el("teach-text").innerHTML = richText(step.text);
  setHint("");

  el("teach-press").hidden = step.kind !== "show";
  el("teach-lines").hidden = step.kind !== "type";
  if (step.kind === "show") {
    el("teach-press").innerHTML = `<span class="press-label">Press</span> ${keycap(step.advance_key)}`;
    kb.setFocus({ fingers: step.fingers, keys: step.keys, reach: step.reach });
  } else {
    view.load(step.prompt);
    kb.focusChar(view.expected);
  }
  lastKeyAt = performance.now();
  busy = false;
}

function fingerHint(ch) {
  const finger = TeachKeyboard.fingerForChar(ch);
  return finger ? ` with your ${FINGER_NAMES[finger]}` : "";
}

function shiftHint(expected) {
  const { side } = TeachKeyboard.shiftForChar(expected);
  return `Hold ${side} [Shift] with your ${side} pinky, then press [${expected}].`;
}

function wrongKeyHint(typed, expected) {
  if (typed.toLowerCase() === expected.toLowerCase()) {
    // right letter, wrong size
    if (expected !== expected.toLowerCase()) return richText(`Almost! ${shiftHint(expected)}`);
    return richText("That one's small, no [Shift]. (Is Caps Lock on?)");
  }
  return `Oops, that was ${keycap(typed)}. Press ${keycap(expected)}${fingerHint(expected)}.`;
}

// Which Shift is held down right now ("left"/"right"), from Shift's own key
// events. null when none, or when we never saw it go down.
let shiftHeld = null;

// Whether `typed` is the `expected` key, and if not, what to say. A capital
// typed with the same hand's Shift counts as a miss: that's the habit to build.
function judge(typed, expected) {
  if (typed !== expected) return { correct: false, hint: wrongKeyHint(typed, expected) };
  const need = TeachKeyboard.shiftForChar(expected);
  if (need && shiftHeld && shiftHeld !== need.side) {
    return { correct: false, hint: richText(`Use the other Shift! ${shiftHint(expected)}`) };
  }
  return { correct: true, hint: "" };
}

function nextStep(delayMs = NEXT_STEP_DELAY_MS) {
  busy = true;
  setTimeout(() => {
    if (stepIndex >= steps.length - 1) return finish();
    stepIndex += 1;
    renderStep();
  }, delayMs);
}

function handleShowKey(step, typed) {
  const { correct, hint } = judge(typed, step.advance_key);
  kb.flashKey(typed, correct);
  if (correct) {
    nextStep(200); // just long enough to see the key flash
  } else {
    setHint(hint, "oops");
  }
}

function handleTypeKey(typed) {
  const expected = view.expected;
  const now = performance.now();
  const { correct, hint } = judge(typed, expected);
  keystrokes.push({
    expected_char: expected,
    typed_char: typed,
    correct,
    latency_ms: Math.min(5000, Math.round(now - lastKeyAt)),
  });
  lastKeyAt = now;
  kb.flashKey(typed, correct);

  if (!correct) {
    view.flagMiss();
    setHint(hint, "oops");
    return;
  }
  setHint("");
  if (!view.mark(true)) {
    kb.focusChar(view.expected);
  } else {
    kb.clearFocus();
    setHint("Nice!", "yay");
    nextStep();
  }
}

async function finish() {
  finished = true;
  busy = true;
  stepIndex = steps.length;
  renderProgress();
  kb.setFocus({ fingers: ["thumb"], keys: [" "] });
  el("teach-lesson").hidden = true;
  el("teach-done").hidden = false;

  const res = await fetch(`/api/teach/${moduleId}/complete${location.search}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keys: content.keys, keystrokes }),
  });
  const data = await res.json();
  el("teach-result").textContent = `${Math.round(data.result.accuracy * 100)}% of keys right the first time.`;
  const coins = data.coins_earned.reduce((sum, c) => sum + c.amount, 0);
  el("teach-coins").textContent = coins ? `+${coins.toLocaleString()} coins!` : "";
  if (window.Header) Header.celebrate(data.coins_earned, data.coin_balance);
  busy = false;
}

window.addEventListener("keyup", (e) => {
  if (e.key === "Shift") shiftHeld = null;
});

window.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return; // leave browser shortcuts alone
  if (e.key === "Shift") {
    shiftHeld = e.code === "ShiftRight" ? "right" : "left";
    if (!finished) kb.flashKey(`shift_${shiftHeld[0]}`, true);
    return;
  }
  if (finished) {
    if (busy) return;
    if (e.key === " ") {
      e.preventDefault();
      location.reload();
    } else if (e.key === "Enter") {
      location.href = "/teach-lab";
    }
    return;
  }
  if (e.key.length !== 1) return; // Shift, Tab, arrows, ...
  e.preventDefault(); // Space would scroll the page
  if (busy || e.repeat) return;
  const step = steps[stepIndex];
  if (step.kind === "show") handleShowKey(step, e.key);
  else handleTypeKey(e.key);
});

async function start() {
  const res = await fetch(`/api/teach/${moduleId}/content${location.search}`);
  if (!res.ok) {
    el("teach-title").textContent = "Couldn't load this lesson.";
    return;
  }
  content = await res.json();
  steps = content.micro_steps;
  renderStep();
}

start();
