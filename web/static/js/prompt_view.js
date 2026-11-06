// Shared typing prompt (session page and teach pages): one line at a time,
// the current line plus the next one faded below it, wrapped only between
// words to fit the box. The space where a line wraps is neither shown nor
// typed, so a line never ends on a space. A space is just a gap: boxed in
// yellow when it's the key to press, light red if it was mistyped.
//
//   const view = new PromptView(element);
//   view.load("asdf jkl; asdf");
//   view.expected        // the character to type now
//   view.mark(correct)   // record the current character and move on; true when the prompt is done
//   view.flagMiss()      // a wrong try that stays put (teach pages): shake + mark
//   view.setLocked(bool) // session's wrong-streak lockout look
//   view.typed           // characters marked so far
//   view.typeable        // exactly what a perfect typist types (tests use it)
//   view.skipped         // wrap spaces dropped (not typed)
//
// The fit is measured again when the typing font finishes loading or the
// box changes size, and whatever isn't typed yet is wrapped again, so a
// line never runs out of the box (the first measure can happen in the
// fallback font, which is narrower).

class PromptView {
  constructor(container) {
    this.container = container;
    container.classList.add("prompt-view");
    this.currentEl = document.createElement("div");
    this.nextEl = document.createElement("div");
    this.currentEl.className = "prompt-line prompt-current";
    this.nextEl.className = "prompt-line prompt-next";
    container.replaceChildren(this.currentEl, this.nextEl);
    this.lines = [];
    if (window.ResizeObserver) new ResizeObserver(() => this.refit()).observe(container);
    if (document.fonts) document.fonts.addEventListener("loadingdone", () => this.refit());
  }

  load(prompt) {
    this.chars = [...prompt];
    this.marks = []; // char index -> "correct" / "incorrect", kept through a refit
    this.missed = new Set();
    this.maxChars = this.fitChars();
    this.lines = PromptView.wrap(this.chars, this.maxChars);
    this.lineIndex = 0;
    this.col = 0;
    this.typed = 0;
    this.locked = false;
    this.render();
    if (document.fonts) {
      document.fonts.load(getComputedStyle(this.currentEl).font).then(() => this.refit(), () => {});
      document.fonts.ready.then(() => this.refit());
    }
  }

  // Wrap the rest again if the box now fits a different number of
  // characters; typed characters keep their marks and the place moves with them.
  refit() {
    if (this.done || !this.lines.length || !this.currentEl.clientWidth) return;
    const fit = this.fitChars();
    if (fit === this.maxChars) return;
    this.maxChars = fit;
    const line = this.lines[this.lineIndex];
    const at = line[this.col];
    const start = line[0];
    const rest = PromptView.wrap(this.chars.slice(start), fit).map((l) => l.map((i) => i + start));
    let li = rest.findIndex((l) => l[l.length - 1] >= at);
    if (li < 0) li = rest.length - 1;
    const col = rest[li].findIndex((i) => i >= at);
    this.lines = this.lines.slice(0, this.lineIndex).concat(rest);
    this.lineIndex += li;
    this.col = col < 0 ? 0 : col;
    this.render();
  }

  get done() {
    return this.lineIndex >= this.lines.length;
  }

  get expected() {
    return this.done ? undefined : this.chars[this.lines[this.lineIndex][this.col]];
  }

  get typeable() {
    return this.lines.map((line) => line.map((i) => this.chars[i]).join("")).join("");
  }

  get skipped() {
    return this.chars.length - this.lines.reduce((n, line) => n + line.length, 0);
  }

  mark(correct) {
    const span = this.spans[this.col];
    span.classList.remove("current", "locked", "pending", "shake");
    span.classList.add(correct ? "correct" : "incorrect");
    this.marks[this.lines[this.lineIndex][this.col]] = correct ? "correct" : "incorrect";
    this.typed += 1;
    this.col += 1;
    if (this.col >= this.lines[this.lineIndex].length) {
      this.lineIndex += 1;
      this.col = 0;
      if (this.done) return true;
      this.render();
      return false;
    }
    this.highlightCurrent();
    return false;
  }

  flagMiss() {
    const span = this.spans[this.col];
    span.classList.remove("shake");
    void span.offsetWidth; // restart the shake on repeated misses
    span.classList.add("shake", "missed");
    this.missed.add(this.lines[this.lineIndex][this.col]);
  }

  setLocked(locked) {
    this.locked = locked;
    this.highlightCurrent();
  }

  // --- drawing ----------------------------------------------------------------

  render() {
    this.spans = this.fill(this.currentEl, this.lines[this.lineIndex] || []);
    this.fill(this.nextEl, this.lines[this.lineIndex + 1] || []);
    this.highlightCurrent();
  }

  fill(lineEl, indices) {
    const spans = indices.map((i) => {
      const span = document.createElement("span");
      const ch = this.chars[i];
      span.className = (ch === " " ? "space " : "") + (this.marks[i] || "pending");
      if (this.missed.has(i)) span.classList.add("missed");
      span.textContent = ch;
      return span;
    });
    lineEl.replaceChildren(...spans);
    return spans;
  }

  highlightCurrent() {
    if (this.done) return;
    this.spans.forEach((s, i) => {
      s.classList.toggle("current", i === this.col && !this.locked);
      s.classList.toggle("locked", i === this.col && this.locked);
    });
  }

  // How many characters fit on one line of this box, measured in its font.
  fitChars() {
    const probe = document.createElement("span");
    probe.textContent = "MMMMMMMMMM";
    probe.style.cssText = "position: absolute; visibility: hidden";
    this.currentEl.appendChild(probe);
    const charWidth = probe.getBoundingClientRect().width / 10 / (probe.currentCSSZoom || 1); // in the box's own px
    const width = this.currentEl.clientWidth;
    probe.remove();
    return charWidth && width ? Math.max(8, Math.floor(width / charWidth) - 1) : 24;
  }

  // Lines of character indices. Breaks only between words (a word longer
  // than a whole line is split), and the spaces at a break -- or at the
  // very end -- are dropped from every line.
  static wrap(chars, maxChars) {
    const lines = [];
    let line = [];
    let spaces = []; // spaces seen since the last word
    let i = 0;
    while (i < chars.length) {
      if (chars[i] === " ") {
        spaces.push(i++);
        continue;
      }
      const word = [];
      while (i < chars.length && chars[i] !== " ") word.push(i++);
      if (line.length && line.length + spaces.length + word.length <= maxChars) {
        line.push(...spaces, ...word);
      } else {
        if (line.length) lines.push(line);
        line = [];
        for (let start = 0; start < word.length; start += maxChars) {
          if (line.length) lines.push(line);
          line = word.slice(start, start + maxChars);
        }
      }
      spaces = [];
    }
    if (line.length) lines.push(line);
    return lines;
  }
}
