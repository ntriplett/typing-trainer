// Demo harness for the 3 experimental "teach" modules: pick a module +
// key, step through its micro-lesson (diagram / anchor-check / drill /
// combo), typing each step's prompt where there is one, and see the
// scored result. Stateless on the server side -- nothing here touches
// real progress data.

// --- the hand/keyboard diagram -------------------------------------------------
//
// Built from scratch each time a step needs one, driven purely by
// that step's `highlight_key` / `home_key` -- same finger-assignment
// data as the backend (app/finger_map.py, app/activities/micro_lesson.py)
// duplicated here since this is demo-only UI, not worth a shared-data
// endpoint yet.

const TOP_ROW = ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"];
const HOME_ROW = ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";"];

const KEY_TO_FINGER = {
  q: "left_pinky", a: "left_pinky", z: "left_pinky",
  w: "left_ring", s: "left_ring", x: "left_ring",
  e: "left_middle", d: "left_middle", c: "left_middle",
  r: "left_index", f: "left_index", v: "left_index", t: "left_index", g: "left_index", b: "left_index",
  y: "right_index", h: "right_index", n: "right_index", u: "right_index", j: "right_index", m: "right_index",
  i: "right_middle", k: "right_middle", ",": "right_middle",
  o: "right_ring", l: "right_ring", ".": "right_ring",
  p: "right_pinky", ";": "right_pinky", "/": "right_pinky",
};

const HOME_KEY_FOR_FINGER = {
  left_pinky: "a", left_ring: "s", left_middle: "d", left_index: "f",
  right_index: "j", right_middle: "k", right_ring: "l", right_pinky: ";",
};

const KEY_WIDTH = 52;
const KEY_HEIGHT = 40;
const KEY_GAP = 6;
const TOP_ROW_Y = 20;
const HOME_ROW_Y = TOP_ROW_Y + KEY_HEIGHT + KEY_GAP;
const FINGER_ROW_Y = HOME_ROW_Y + KEY_HEIGHT + 30;
const TOP_ROW_X0 = 20;
const HOME_ROW_X0 = TOP_ROW_X0 + KEY_WIDTH / 2;

function keyPosition(key) {
  const topIndex = TOP_ROW.indexOf(key);
  if (topIndex !== -1) {
    return { x: TOP_ROW_X0 + topIndex * (KEY_WIDTH + KEY_GAP), y: TOP_ROW_Y };
  }
  const homeIndex = HOME_ROW.indexOf(key);
  if (homeIndex !== -1) {
    return { x: HOME_ROW_X0 + homeIndex * (KEY_WIDTH + KEY_GAP), y: HOME_ROW_Y };
  }
  return null;
}

function renderHandDiagram(highlightKey, homeKey) {
  const svg = document.getElementById("hand-diagram");
  const parts = [];

  parts.push(`
    <defs>
      <marker id="arrowhead" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L6,3 L0,6 Z" fill="#4a90d9" />
      </marker>
    </defs>
  `);

  for (const key of [...TOP_ROW, ...HOME_ROW]) {
    const pos = keyPosition(key);
    const isHighlight = key === highlightKey;
    const isHome = key === homeKey && key !== highlightKey;
    const cls = `dkey-rect${isHighlight ? " dkey-highlight" : ""}${isHome ? " dkey-home" : ""}`;
    parts.push(
      `<rect class="${cls}" x="${pos.x}" y="${pos.y}" width="${KEY_WIDTH}" height="${KEY_HEIGHT}" rx="6"></rect>`
    );
    parts.push(
      `<text class="dkey-label" x="${pos.x + KEY_WIDTH / 2}" y="${pos.y + KEY_HEIGHT / 2}">${key.toUpperCase()}</text>`
    );
  }

  const activeFinger = highlightKey ? KEY_TO_FINGER[highlightKey] : null;
  for (const [finger, home] of Object.entries(HOME_KEY_FOR_FINGER)) {
    const pos = keyPosition(home);
    const cx = pos.x + KEY_WIDTH / 2;
    const cy = FINGER_ROW_Y;
    const isActive = finger === activeFinger;
    parts.push(
      `<circle class="dfinger${isActive ? " dfinger-active" : ""}" cx="${cx}" cy="${cy}" r="12"></circle>`
    );
  }

  if (highlightKey && homeKey && homeKey !== highlightKey) {
    const from = keyPosition(homeKey);
    const to = keyPosition(highlightKey);
    const x1 = from.x + KEY_WIDTH / 2;
    const y1 = from.y + KEY_HEIGHT / 2;
    const x2 = to.x + KEY_WIDTH / 2;
    const y2 = to.y + KEY_HEIGHT / 2;
    parts.push(`<line class="dreach-arrow" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"></line>`);
  }

  svg.innerHTML = parts.join("");
}

// --- lesson flow ---------------------------------------------------------------

let moduleId = null;
let focusKey = null;
let microSteps = [];
let stepIndex = 0;
let promptChars = [];
let charSpans = [];
let position = 0;
let keystrokes = [];
const allKeystrokes = []; // across every micro-step, for final scoring
let contentKeys = [];

const setupScreen = document.getElementById("setup-screen");
const lessonScreen = document.getElementById("lesson-screen");
const completeScreen = document.getElementById("lesson-complete-screen");
const moduleSelect = document.getElementById("module-select");
const moduleDescription = document.getElementById("module-description");
const keySelect = document.getElementById("key-select");
const microStepProgress = document.getElementById("micro-step-progress");
const stepInstructions = document.getElementById("step-instructions");
const lessonProgress = document.getElementById("lesson-progress");
const promptEl = document.getElementById("lesson-prompt");
const microStepResult = document.getElementById("micro-step-result");

async function loadModules() {
  const res = await fetch("/api/teach-demo/modules");
  const modules = await res.json();
  moduleSelect.innerHTML = modules
    .map((m) => `<option value="${m.id}">${m.id.replace(/_demo_v1$/, "").replace(/_/g, " ")}</option>`)
    .join("");
  moduleSelect.dataset.descriptions = JSON.stringify(
    Object.fromEntries(modules.map((m) => [m.id, m.description]))
  );
  updateModuleDescription();
}

function updateModuleDescription() {
  const descriptions = JSON.parse(moduleSelect.dataset.descriptions || "{}");
  moduleDescription.textContent = descriptions[moduleSelect.value] || "";
}

moduleSelect.addEventListener("change", updateModuleDescription);

document.getElementById("start-button").addEventListener("click", startLesson);
document.getElementById("continue-button").addEventListener("click", advanceMicroStep);
document.getElementById("restart-button").addEventListener("click", () => window.location.reload());
document.getElementById("try-another-button").addEventListener("click", () => window.location.reload());
window.addEventListener("keydown", handleKeydown);

async function startLesson() {
  moduleId = moduleSelect.value;
  focusKey = keySelect.value;

  const res = await fetch(
    `/api/teach-demo/${moduleId}/content?focus_key=${focusKey}&allowed_keys=f,j,d,k`
  );
  const content = await res.json();
  microSteps = content.micro_steps;
  contentKeys = content.keys;
  stepIndex = 0;
  allKeystrokes.length = 0;

  setupScreen.hidden = true;
  lessonScreen.hidden = false;
  renderMicroStep();
}

function renderMicroStep() {
  const step = microSteps[stepIndex];
  microStepProgress.textContent = `Step ${stepIndex + 1} of ${microSteps.length} — ${step.kind}`;
  stepInstructions.textContent = step.instructions;
  renderHandDiagram(step.highlight_key, step.home_key);

  promptChars = step.prompt.split("");
  position = 0;
  keystrokes = [];
  microStepResult.hidden = true;

  if (promptChars.length === 0) {
    // pure diagram step -- nothing to type, just a "Continue" to move on
    promptEl.innerHTML = "";
    lessonProgress.textContent = "";
    microStepResult.hidden = false;
    document.getElementById("continue-button").textContent = "Got it →";
  } else {
    document.getElementById("continue-button").textContent = "Continue →";
    buildPromptDom();
    renderLessonProgress();
  }
}

function renderLessonProgress() {
  const total = promptChars.filter((c) => c !== " ").length;
  const done = promptChars.slice(0, position).filter((c) => c !== " ").length;
  lessonProgress.textContent = `${done} / ${total}`;
}

function buildPromptDom() {
  charSpans = promptChars.map((ch) => {
    const span = document.createElement("span");
    span.className = ch === " " ? "space pending" : "pending";
    span.textContent = ch === " " ? "" : ch;
    promptEl.appendChild(span);
    return span;
  });
  promptEl.replaceChildren(...charSpans);
  if (charSpans.length) charSpans[0].classList.add("current");
}

function handleKeydown(e) {
  if (lessonScreen.hidden || promptChars.length === 0 || !microStepResult.hidden) return;
  if (e.key.length !== 1) return;
  e.preventDefault();

  const expected = promptChars[position];
  const typed = e.key;
  const correct = typed === expected;

  const record = { expected_char: expected, typed_char: typed, correct, latency_ms: 150 };
  keystrokes.push(record);
  allKeystrokes.push(record);

  charSpans[position].classList.remove("current", "pending");
  charSpans[position].classList.add(correct ? "correct" : "incorrect");
  position += 1;
  if (position < charSpans.length) charSpans[position].classList.add("current");
  renderLessonProgress();

  if (position >= promptChars.length) {
    microStepResult.hidden = false;
  }
}

function advanceMicroStep() {
  if (stepIndex >= microSteps.length - 1) {
    finishLesson();
    return;
  }
  stepIndex += 1;
  renderMicroStep();
}

async function finishLesson() {
  const res = await fetch(`/api/teach-demo/${moduleId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keys: contentKeys, keystrokes: allKeystrokes }),
  });
  const result = await res.json();

  lessonScreen.hidden = true;
  completeScreen.hidden = false;
  document.getElementById("final-result").textContent =
    `${Math.round(result.accuracy * 100)}% accuracy, ${result.wpm.toFixed(1)} WPM — ${result.reward_signal}`;
}

loadModules();
