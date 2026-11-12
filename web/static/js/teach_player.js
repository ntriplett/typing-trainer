// Runs any keyboard-driven teach module (app/activities/teach_steps.py) at
// /teach/<module id>. Everything moves on from a key press, so hands stay
// on home the whole lesson:
//   - "show" steps wait for their advance_key (e.g. Space with a thumb),
//   - "type" steps finish when the prompt is typed (a wrong key doesn't
//     move on; you retry it), then move on by themselves.
// At the end: Space to go again, Enter to pick another lesson (/teach-lab).
// The query string (?keys=dk for the key-pair module) is passed through.
//
// Brain mode (?lesson=<id>, from the practice page): the content is that
// lesson's, finishing reports to /api/lesson/<id>/complete (it counts
// toward the day's goal), and Enter goes on to the next lesson.
//
// Needs keyboard_data.js, teach_keyboard.js, prompt_view.js, and rich_text.js loaded first.

const FINGER_NAMES = {
  left_pinky: "left pinky", left_ring: "left ring finger", left_middle: "left middle finger",
  left_index: "left pointer finger", right_index: "right pointer finger",
  right_middle: "right middle finger", right_ring: "right ring finger", right_pinky: "right pinky",
  thumb: "thumb",
};
const NEXT_STEP_DELAY_MS = 700;
// Reading a page counts as practice time, up to this long between keys.
const IDLE_MS = 20000;
const lessonId = new URLSearchParams(location.search).get("lesson");
let activeMs = 0;
let lastAnyKeyAt = performance.now();

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

// New letters, and anything they opened: each line pops in after the last.
// The letters' key bonuses come later, from practice (app/lessons.py).
function showFanfare(data) {
  const learned = data.learned || [];
  const lines = [];
  if (learned.length) {
    const caps = learned.map((k) => keycap(k)).join(" and ");
    const them = learned.length > 1 ? "them" : "it";
    const each = learned.length > 1 ? "each one" : "it";
    lines.push(`<p class="fanfare-big">🎉 You learned ${caps}!</p>`);
    lines.push(`<p>Practice ${them}, and once ${them === "them" ? "they're" : "it's"} solid ${each} pays a ` +
      `<span class="coin-icon"></span>${(data.key_bonus || 0).toLocaleString()} coin bonus!</p>`);
  }
  for (const d of data.shop_opened || []) lines.push(`<p class="fanfare-shop">🐾 ${escapeHtml(d.name)} just opened at the Pet Shop!</p>`);
  for (const r of data.reward_pets || []) {
    const a = /^[aeiou]/i.test(r.name) ? "an" : "a";
    lines.push(`<p class="fanfare-shop">🎁 You earned ${a} ${escapeHtml(r.name.toLowerCase())}! It's waiting at the Pet Shop.</p>`);
  }
  if (data.pet_coupon) lines.push(`<p class="fanfare-shop">🎟️ You got a free pet coupon for Household Pets!</p>`);
  if (!lines.length) return;
  const box = el("teach-fanfare");
  box.innerHTML = lines.join("");
  [...box.children].forEach((line, i) => (line.style.animationDelay = `${0.25 + i * 0.45}s`));
  box.hidden = false;
}

async function finish() {
  finished = true;
  busy = true;
  stepIndex = steps.length;
  renderProgress();
  kb.setFocus({ fingers: ["thumb"], keys: [" "] });
  el("teach-lesson").hidden = true;
  el("teach-done").hidden = false;

  const res = lessonId
    ? await fetch(`/api/lesson/${lessonId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keystrokes, active_ms: Math.round(activeMs) }),
      })
    : await fetch(`/api/teach/${moduleId}/complete${location.search}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keys: content.keys, keystrokes }),
      });
  if (!res.ok && lessonId) {
    location.href = "/session"; // the server forgot this lesson: get a fresh one
    return;
  }
  const data = await res.json();
  el("teach-result").textContent = `${Math.round(data.result.accuracy * 100)}% of keys right the first time.`;
  const coins = data.coins_earned.reduce((sum, c) => sum + c.amount, 0);
  el("teach-coins").textContent = coins ? `+${coins.toLocaleString()} coins!` : "";
  if (window.Header) Header.celebrate(data.coins_earned, data.coin_balance);
  if (lessonId) {
    el("teach-next").innerHTML = `Press ${keycap("Enter")} for your next lesson, or ${keycap("Esc")} to go home.`;
    const opened = {}; // room -> how to say it (app/unlocks.py NEEDS)
    if (data.unlocked && data.unlocked.length) {
      el("teach-unlock").textContent = `🎉 You unlocked ${data.unlocked.map((r) => opened[r]).join(" and ")}!`;
      el("teach-unlock").hidden = false;
    }
    showFanfare(data);
    if (window.Header) {
      Header.setDay(data.day);
      Header.celebrateTokens(data.tokens_earned, data.token_balance);
      Header.celebrateSeeds(data);
    }
  }
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
    if (lessonId) {
      if (e.key === "Enter") location.href = "/session";
      else if (e.key === "Escape") location.href = "/";
    } else if (e.key === " ") {
      e.preventDefault();
      location.reload();
    } else if (e.key === "Enter") {
      location.href = "/teach-lab";
    }
    return;
  }
  const now = performance.now();
  activeMs += Math.min(IDLE_MS, now - lastAnyKeyAt);
  lastAnyKeyAt = now;
  if (e.key.length !== 1) return; // Shift, Tab, arrows, ...
  e.preventDefault(); // Space would scroll the page
  if (busy || e.repeat) return;
  const step = steps[stepIndex];
  if (step.kind === "show") handleShowKey(step, e.key);
  else handleTypeKey(e.key);
});

async function start() {
  const res = await fetch(lessonId ? `/api/lesson/${lessonId}` : `/api/teach/${moduleId}/content${location.search}`);
  if (!res.ok) {
    if (lessonId) location.href = "/session";
    else el("teach-title").textContent = "Couldn't load this lesson.";
    return;
  }
  content = lessonId ? (await res.json()).content : await res.json();
  steps = content.micro_steps;
  renderStep();
}

start();
