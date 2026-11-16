// The typing stage for warmups and practice (session page and practice lab),
// in the teach pages' look: a big title, short text with keycaps, the
// module's themed scene (practice_scenes.js), the one-line prompt
// (prompt_view.js), and the fading keyboard hint (teach_keyboard.js).
//
// The hint (app/hint_model.py has the rules and the why): every key has a
// support level from 0 to 5 that the server picks. 5 is the keyboard with
// its letters and the finger and key lit at once; lower levels light them
// later and later, then hide the letters, then the key, then the finger,
// then the whole keyboard. On top of that:
//   - the rescue, for this lesson only: when the last few keys go badly,
//     every key gets more help (all the way up if need be), and it eases
//     back off as things go well again;
//   - solo lines: now and then a line with no hints at all;
//   - More help / Less help buttons (the server decides how much).
//
// Practice rules: a wrong key still moves on (marked red), but
// LOCKOUT_STREAK wrong keys in a row lock the prompt until the right one.
//
//   const stage = new PracticeStage(element, { onFinish, onKey });
//   stage.load(content, { label: "Warmup", hints });  // hints: the lesson's plan, or null for none
//   stage.finish();   // end early ("End this step now")
//   stage.view        // the PromptView (tests read view.typeable)
//
// onFinish({ keystrokes, skipped }) runs once, when the prompt is done or
// finish() is called. Needs prompt_view.js, rich_text.js, keyboard_data.js,
// teach_keyboard.js, and practice_scenes.js loaded first.

const LOCKOUT_STREAK = 5;

// The same rules as app/hint_model.py display() and rescue_step(), which
// are the reference (tests check the two agree).
const HintRules = {
  MAX: 5,
  LETTERS_BELOW: 4,
  KEYBOARD_BELOW: 1,

  clamp(s) {
    return Math.max(0, Math.min(HintRules.MAX, s));
  },

  // support -> { letter, fingerMs, keyMs } (null ms: never)
  display(support) {
    const s = HintRules.clamp(support);
    if (s >= 4) {
      const t = s - 4;
      const finger = Math.round(1500 * (1 - t));
      return { letter: true, fingerMs: finger, keyMs: finger + Math.round(400 * (1 - t)) };
    }
    if (s >= 3) {
      const finger = Math.round(3000 - 1500 * (s - 3));
      return { letter: false, fingerMs: finger, keyMs: finger + 1000 };
    }
    if (s >= 2) return { letter: false, fingerMs: Math.round(5000 - 2000 * (s - 2)), keyMs: null };
    return { letter: false, fingerMs: null, keyMs: null };
  },

  // The rescue offset after a press; recent is this lesson's right/wrong so far.
  rescueStep(offset, recent, p) {
    const window = recent.slice(-p.window);
    if (window.length < p.min_presses) return offset;
    const accuracy = window.filter(Boolean).length / window.length;
    if (accuracy < p.below) offset += p.up;
    else if (accuracy >= p.ease && window[window.length - 1]) offset -= p.down;
    return Math.max(0, Math.min(p.max, offset));
  },
};

const HELP_SAYS = {
  more: "A little more help is on the way.",
  less: "Less help. You've got this!",
};

class PracticeStage {
  constructor(root, { onFinish = () => {}, onKey = () => {} } = {}) {
    this.onFinish = onFinish;
    this.onKey = onKey;
    root.classList.add("stage");
    root.innerHTML = `
      <p class="stage-label"></p>
      <h1 class="stage-title"></h1>
      <p class="stage-text"></p>
      <canvas class="stage-scene" hidden></canvas>
      <div class="stage-prompt"><div class="stage-lines"></div></div>
      <p class="stage-hint" aria-live="polite"></p>
      <div class="stage-tools">
        <span class="stage-progress"></span>
        <span class="stage-help" hidden>
          <button type="button" class="stage-help-less">Less help</button>
          <button type="button" class="stage-help-more">More help</button>
        </span>
      </div>
      <svg class="stage-keyboard" hidden role="img" aria-label="Keyboard with hands showing which finger to use"></svg>`;
    const $ = (sel) => root.querySelector(sel);
    this.els = {
      label: $(".stage-label"),
      title: $(".stage-title"),
      text: $(".stage-text"),
      scene: $(".stage-scene"),
      hint: $(".stage-hint"),
      progress: $(".stage-progress"),
      help: $(".stage-help"),
      less: $(".stage-help-less"),
      more: $(".stage-help-more"),
      keyboard: $(".stage-keyboard"),
    };
    this.view = new PromptView($(".stage-lines"));
    this.kb = null; // made the first time a lesson has hints
    this.scene = null;
    this.active = false;
    this.els.less.addEventListener("click", () => this.askForHelp("less"));
    this.els.more.addEventListener("click", () => this.askForHelp("more"));
    window.addEventListener("keydown", (e) => this.handleKey(e));
  }

  load(content, { label = "", hints = null } = {}) {
    this.content = content;
    this.hints = hints && Object.keys(hints.keys || {}).length ? hints : null;
    this.rescue = 0;
    this.recent = []; // right/wrong, for the rescue
    this.soloLine = null; // the solo line being typed: { index, right, total }
    this.keystrokes = [];
    this.wrongStreak = 0;
    this.locked = false;
    this.lastKeyAt = performance.now();
    this.els.label.textContent = label;
    this.els.label.hidden = !label;
    this.els.title.innerHTML = richText(content.title || label || "Practice");
    this.els.text.innerHTML = richText(content.instructions || "");
    this.setHint("");
    // an <svg> has no .hidden property, so set the attribute itself
    this.els.keyboard.setAttribute("hidden", "");
    this.els.help.hidden = !(this.hints && this.hints.mode === "auto");
    this.els.less.disabled = this.els.more.disabled = false;
    if (this.hints && !this.kb) this.kb = new TeachKeyboard(this.els.keyboard);

    if (this.scene) this.scene.destroy();
    this.scene = content.scene ? makeScene(content.scene, this.els.scene) : null;
    this.els.scene.hidden = !this.scene;

    this.view.load(content.prompt);
    this.renderProgress();
    this.active = true;
    this.refreshHint();
  }

  setHint(html, kind = "") {
    this.els.hint.innerHTML = html;
    this.els.hint.className = `stage-hint ${kind}`;
  }

  renderProgress() {
    const text = this.view.typeable;
    const total = text.replace(/ /g, "").length;
    const done = text.slice(0, this.view.typed).replace(/ /g, "").length;
    this.els.progress.textContent = `${done} / ${total}`;
  }

  // --- the hint --------------------------------------------------------------

  // A key's support right now: the server's, plus the rescue.
  supportFor(ch) {
    const base = this.hints.keys[ch.toLowerCase()];
    return base === undefined ? null : HintRules.clamp(base + this.rescue);
  }

  otherKeys() {
    return Object.keys(KEY_TO_FINGER).filter((k) => !(k in this.hints.keys));
  }

  onSoloLine() {
    return !!this.hints && this.hints.solo_lines.includes(this.view.lineIndex);
  }

  // Show the keyboard the way the current key's support says, and start its lights.
  refreshHint() {
    if (!this.hints || !this.kb) return;
    const expected = this.view.expected;
    const levels = Object.keys(this.hints.keys).map((k) => [k, this.supportFor(k)]);
    const show = this.active && expected !== undefined && !this.onSoloLine() && levels.some(([, s]) => s >= HintRules.KEYBOARD_BELOW);
    this.els.keyboard.toggleAttribute("hidden", !show);
    if (!show) {
      this.kb.clearFocus();
      return;
    }
    // Keys not in this lesson keep their letters only while some lesson key
    // still shows its own; after that they'd just point the way to it.
    const lettered = levels.filter(([, s]) => s >= HintRules.LETTERS_BELOW).map(([k]) => k);
    this.kb.setLabels(lettered.length ? new Set([...this.otherKeys(), ...lettered]) : new Set());
    const support = this.supportFor(expected);
    this.kb.focusStaged(expected, HintRules.display(support === null ? HintRules.MAX : support));
  }

  // What the server needs to know about the hint for this keystroke.
  hintFields(expected) {
    if (!this.hints) return {};
    const solo = this.onSoloLine();
    const support = this.supportFor(expected);
    if (support === null) return {};
    return { hint_support: Math.round(support * 1000) / 1000, solo };
  }

  // Cheer a solo line when it's done, and announce the next one.
  trackSolo(correct) {
    const index = this.view.lineIndex;
    if (this.soloLine && this.soloLine.index === index) {
      this.soloLine.total += 1;
      this.soloLine.right += correct;
    }
    return () => {
      const now = this.view.lineIndex;
      if (this.soloLine && this.soloLine.index !== now) {
        const { right, total } = this.soloLine;
        this.soloLine = null;
        if (total && right / total >= 0.9) this.setHint("🌟 Solo line, all by yourself! Super!", "yay");
        else this.setHint("Solo line done. The hints are back!");
      }
      if (!this.soloLine && this.onSoloLine() && !this.view.done) {
        this.soloLine = { index: now, right: 0, total: 0 };
        this.setHint("🌟 Solo line! No hints this time. You can do it!", "yay");
      }
    };
  }

  async askForHelp(direction) {
    this.els[direction].blur(); // so Space types instead of pressing the button again
    if (!this.active || !this.hints) return;
    this.els.less.disabled = this.els.more.disabled = true;
    const res = await fetch("/api/hint/nudge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction, keys: this.content.prompt }),
    });
    this.els.less.disabled = this.els.more.disabled = false;
    if (!res.ok) return;
    const data = await res.json();
    Object.assign(this.hints.keys, data.keys);
    this.setHint(HELP_SAYS[direction]);
    this.refreshHint();
  }

  // --- typing ------------------------------------------------------------------

  handleKey(e) {
    if (!this.active || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key.length !== 1) return; // Shift, Tab, arrows, ...
    e.preventDefault(); // Space would scroll the page
    if (e.repeat) return;

    const expected = this.view.expected;
    const typed = e.key;
    const correct = typed === expected;
    const now = performance.now();
    const latency = Math.max(1, Math.round(now - this.lastKeyAt));
    this.lastKeyAt = now;
    this.onKey();

    const wasLocked = this.locked;
    if (this.locked) {
      // Locked: nothing counts until the right key.
      if (!correct) return;
      this.locked = false;
      this.view.setLocked(false);
      this.setHint("");
    } else if (!correct) {
      this.wrongStreak += 1;
      this.scene?.miss();
      if (this.wrongStreak >= LOCKOUT_STREAK) {
        this.locked = true;
        this.view.setLocked(true);
        this.setHint(`🔒 Get this one right to keep going! Press ${keycap(expected)}.`, "oops");
        return;
      }
    }
    if (correct) this.wrongStreak = 0;

    const hint = this.hintFields(expected);
    // The lockout names the key, so the press that ends it was shown the answer.
    if (wasLocked && "hint_support" in hint) hint.hint_support = HintRules.MAX;
    this.keystrokes.push({ expected_char: expected, typed_char: typed, correct, latency_ms: latency, ...hint });
    const afterSolo = this.hints ? this.trackSolo(correct) : () => {};
    if (this.hints && this.hints.rescue) {
      this.recent.push(correct);
      this.rescue = HintRules.rescueStep(this.rescue, this.recent, this.hints.rescue);
    }
    const finished = this.view.mark(correct);
    // a word ends at a space, a line wrap, or the end of the prompt
    const wordDone = correct && typed !== " " && (finished || this.view.expected === " " || this.view.col === 0);
    if (correct) {
      const progress = this.view.typed / Math.max(1, this.view.typeable.length);
      this.scene?.correct({ ch: typed, progress, wordDone });
    }
    this.renderProgress();
    if (finished) {
      this.finish();
    } else {
      afterSolo();
      this.refreshHint();
    }
  }

  finish() {
    if (!this.active) return;
    this.active = false;
    if (this.view.done) this.scene?.finish();
    this.kb?.clearFocus();
    this.els.help.hidden = true;
    this.onFinish({ keystrokes: this.keystrokes, skipped: this.view.skipped });
  }
}
