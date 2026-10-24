// The typing stage for warmups and practice (session page and practice lab),
// in the teach pages' look: a big title, short text with keycaps, the
// module's themed scene (practice_scenes.js), the one-line prompt
// (prompt_view.js), and a "Keyboard hint" button that spends coins to show
// the keyboard with hands (teach_keyboard.js) for the rest of the lesson.
//
// Practice rules: a wrong key still moves on (marked red), but
// LOCKOUT_STREAK wrong keys in a row lock the prompt until the right one.
//
//   const stage = new PracticeStage(element, { onFinish, onKey });
//   stage.load(content, { label: "Warmup", hintRef: "session:3:2" });
//   stage.finish();   // end early ("End this step now")
//   stage.view        // the PromptView (tests read view.typeable)
//
// onFinish({ keystrokes, skipped }) runs once, when the prompt is done or
// finish() is called. Needs prompt_view.js, rich_text.js, keyboard_data.js,
// teach_keyboard.js, and practice_scenes.js loaded first.

const LOCKOUT_STREAK = 5;
const HINT_PRICE = 10; // matches app/config.py KEYBOARD_HINT_PRICE

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
        <button type="button" class="stage-hint-buy">Keyboard hint · ${HINT_PRICE} coins</button>
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
      buy: $(".stage-hint-buy"),
      keyboard: $(".stage-keyboard"),
    };
    this.view = new PromptView($(".stage-lines"));
    this.kb = null; // made the first time a hint is bought
    this.scene = null;
    this.active = false;
    this.els.buy.addEventListener("click", () => this.buyHint());
    window.addEventListener("keydown", (e) => this.handleKey(e));
  }

  load(content, { label = "", hintRef = "" } = {}) {
    this.content = content;
    this.hintRef = hintRef;
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
    this.els.buy.hidden = false;
    this.els.buy.disabled = false;

    if (this.scene) this.scene.destroy();
    this.scene = content.scene ? makeScene(content.scene, this.els.scene) : null;
    this.els.scene.hidden = !this.scene;

    this.view.load(content.prompt);
    this.renderProgress();
    this.active = true;
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

    this.keystrokes.push({ expected_char: expected, typed_char: typed, correct, latency_ms: latency });
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
    } else if (this.kb) {
      this.kb.focusChar(this.view.expected);
    }
  }

  finish() {
    if (!this.active) return;
    this.active = false;
    if (this.view.done) this.scene?.finish();
    this.kb?.clearFocus();
    this.els.buy.hidden = true;
    this.onFinish({ keystrokes: this.keystrokes, skipped: this.view.skipped });
  }

  async buyHint() {
    this.els.buy.blur(); // so Space types instead of pressing the button again
    if (!this.active) return;
    this.els.buy.disabled = true;
    const res = await fetch("/api/hint/keyboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref: this.hintRef }),
    });
    if (!res.ok) {
      this.els.buy.disabled = false;
      this.setHint(`You need ${HINT_PRICE} coins for a keyboard hint.`, "oops");
      return;
    }
    const data = await res.json();
    if (window.Header) Header.setCoins(data.coin_balance);
    this.els.buy.hidden = true;
    this.els.keyboard.removeAttribute("hidden");
    this.kb = this.kb || new TeachKeyboard(this.els.keyboard);
    if (this.active) this.kb.focusChar(this.view.expected);
  }
}
