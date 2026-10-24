// Shared teaching keyboard: a full QWERTY keyboard with gray "ghost" hands
// resting on it in touch-typing position. Used by every teach module
// (teach_player.js), so it knows nothing about lessons. It just shows:
//   - which fingers to use (lit up in orange),
//   - which keys to press (lit up and pulsing),
//   - a finger reaching off home to a key (the hand leans that way too),
//   - key presses (a quick flash, red if it was the wrong key).
//
// Needs keyboard_data.js (KEY_TO_FINGER, HOME_KEY_FOR_FINGER) loaded first.
//
//   const kb = new TeachKeyboard(svgElement);
//   kb.setFocus({ fingers: ["left_index"], keys: ["r"], reach: { left_index: "r" } });
//   kb.focusChar("r");        // same thing, worked out from the character
//   kb.focusChar("R");        // a capital also lights the other hand's Shift
//   kb.flashKey("r", true);   // pressed it (false = wrong key)
//
// Finger names: left_pinky ... right_pinky (as in keyboard_data.js), plus
// left_thumb, right_thumb, and "thumb" for both thumbs.

const TeachKeyboard = (function () {
  const U = 56; // one key width, in SVG units
  const PAD = 24;

  // [id, label, width in keys]. Letter keys use the character as their id;
  // the others get names (shift_l, ...) so lessons can light them up.
  const letters = (chars) => chars.split("").map((c) => [c, c.toUpperCase(), 1]);
  const ROWS = [
    [...letters("`1234567890-="), ["backspace", "Back", 2]],
    [["tab", "Tab", 1.5], ...letters("qwertyuiop[]"), ["\\", "\\", 1.5]],
    [["caps", "Caps", 1.75], ...letters("asdfghjkl;'"), ["enter", "Enter", 2.25]],
    [["shift_l", "Shift", 2.25], ...letters("zxcvbnm,./"), ["shift_r", "Shift", 2.75]],
    [
      ["ctrl_l", "Ctrl", 1.25], ["win_l", "", 1.25], ["alt_l", "Alt", 1.25],
      [" ", "space", 6.25],
      ["alt_r", "Alt", 1.25], ["win_r", "", 1.25], ["menu", "", 1.25], ["ctrl_r", "Ctrl", 1.25],
    ],
  ];
  const WIDTH = PAD * 2 + 15 * U;
  // The palms hang off the bottom edge, like real wrists would.
  const HEIGHT = PAD + 5.9 * U;

  const SIDES = ["left", "right"];
  const FINGERS = ["pinky", "ring", "middle", "index"];
  // Per finger, in keys: knuckle offset toward the middle of the hand,
  // knuckle distance below the home key, and finger thickness.
  const SHAPE = {
    pinky: { dx: 0.3, dy: 1.25, w: 0.4 },
    ring: { dx: 0.12, dy: 1.55, w: 0.46 },
    middle: { dx: 0, dy: 1.7, w: 0.5 },
    index: { dx: -0.12, dy: 1.5, w: 0.5 },
    thumb: { w: 0.55 },
  };
  const TYPEABLE = new Set([...Object.keys(KEY_TO_FINGER), " "]);

  function layoutKeys() {
    const keys = new Map();
    ROWS.forEach((row, r) => {
      let x = PAD;
      for (const [id, label, w] of row) {
        keys.set(id, { id, label, x, y: PAD + r * U, w: w * U, h: U, cx: x + (w * U) / 2, cy: PAD + r * U + U / 2 });
        x += w * U;
      }
    });
    return keys;
  }

  const lerp = (a, b, t) => a + (b - a) * t;
  const easeOut = (t) => 1 - (1 - t) * (1 - t);

  function fingerForChar(ch) {
    if (ch === " ") return "thumb";
    return KEY_TO_FINGER[ch.toLowerCase()] || null;
  }

  // A capital's Shift: always the other hand's, pressed with its pinky.
  function shiftForChar(ch) {
    if (ch === ch.toLowerCase()) return null;
    const finger = fingerForChar(ch);
    if (!finger) return null;
    return finger.startsWith("left")
      ? { key: "shift_r", finger: "right_pinky", side: "right" }
      : { key: "shift_l", finger: "left_pinky", side: "left" };
  }

  function expandFingers(fingers) {
    return new Set(fingers.flatMap((f) => (f === "thumb" ? ["left_thumb", "right_thumb"] : [f])));
  }

  class TeachKeyboard {
    constructor(svg) {
      this.svg = svg;
      this.keys = layoutKeys();
      this.rest = this.restPose();
      this.pose = structuredClone(this.rest); // what's drawn right now
      this.lit = new Set(); // lit fingers
      this.anim = null;
      svg.setAttribute("viewBox", `0 0 ${WIDTH} ${HEIGHT}`);
      this.build();
      this.drawHands();
    }

    // Where every fingertip, knuckle, and palm point sits with both hands on home.
    restPose() {
      const homeY = this.keys.get("f").cy;
      const pose = {};
      for (const side of SIDES) {
        const toMiddle = side === "left" ? 1 : -1;
        const hand = { shift: { x: 0, y: 0 }, tips: {}, knuckles: {} };
        for (const finger of FINGERS) {
          const home = this.keys.get(HOME_KEY_FOR_FINGER[`${side}_${finger}`]);
          const s = SHAPE[finger];
          hand.tips[finger] = { x: home.cx, y: home.cy };
          hand.knuckles[finger] = { x: home.cx + toMiddle * s.dx * U, y: homeY + s.dy * U };
        }
        const indexX = this.keys.get(side === "left" ? "f" : "j").cx;
        const pinkyX = this.keys.get(side === "left" ? "a" : ";").cx;
        hand.thumbBase = { x: indexX + toMiddle * 0.2 * U, y: homeY + 2.9 * U };
        hand.tips.thumb = { x: indexX + toMiddle * 1.05 * U, y: this.keys.get(" ").cy };
        hand.wrist = [
          { x: pinkyX + toMiddle * 0.45 * U, y: homeY + 3.7 * U },
          { x: indexX - toMiddle * 0.1 * U, y: homeY + 3.7 * U },
        ];
        pose[side] = hand;
      }
      return pose;
    }

    build() {
      const keyParts = [];
      const labelParts = [];
      for (const k of this.keys.values()) {
        const mod = TYPEABLE.has(k.id) ? "" : " tk-mod";
        keyParts.push(
          `<g class="tk-key${mod}" data-key="${escapeAttr(k.id)}">` +
            `<rect class="tk-cap-side" x="${k.x + 3}" y="${k.y + 3}" width="${k.w - 6}" height="${k.h - 6}" rx="7"></rect>` +
            `<rect class="tk-cap" x="${k.x + 3}" y="${k.y + 3}" width="${k.w - 6}" height="${k.h - 11}" rx="7"></rect>` +
            (k.id === "f" || k.id === "j"
              ? `<rect class="tk-bump" x="${k.cx - 8}" y="${k.y + k.h - 19}" width="16" height="4" rx="2"></rect>`
              : "") +
            `</g>`
        );
        if (k.label) {
          const small = k.label.length > 1 ? " tk-label-small" : "";
          labelParts.push(
            `<text class="tk-label${mod}${small}" data-key="${escapeAttr(k.id)}" x="${k.cx}" y="${k.y + (k.h - 8) / 2 + 2}">${escapeHtml(k.label)}</text>`
          );
        }
      }
      this.svg.innerHTML =
        `<rect class="tk-case" x="${PAD - 10}" y="${PAD - 10}" width="${15 * U + 20}" height="${5 * U + 20}" rx="14"></rect>` +
        `<g class="tk-keys">${keyParts.join("")}</g>` +
        `<g class="tk-hands"></g>` +
        `<g class="tk-hands-lit"></g>` +
        `<g class="tk-labels">${labelParts.join("")}</g>`;
      this.keyEls = new Map();
      for (const el of this.svg.querySelectorAll(".tk-key")) this.keyEls.set(el.dataset.key, el);
      this.handsEl = this.svg.querySelector(".tk-hands");
      this.litEl = this.svg.querySelector(".tk-hands-lit");
    }

    // --- what to show --------------------------------------------------------

    // fingers: lit fingers; keys: lit keys; reach: {finger: key} moves that
    // finger onto the key (and leans its hand a little that way).
    setFocus({ fingers = [], keys = [], reach = {} } = {}) {
      this.lit = expandFingers(fingers);
      for (const [id, el] of this.keyEls) el.classList.toggle("tk-target", keys.includes(id));
      this.animateTo(this.poseFor(reach));
    }

    // Light up the finger and key for one character, reaching if it isn't
    // that finger's home key. A capital adds the other pinky on its Shift.
    focusChar(ch) {
      const key = ch.toLowerCase();
      const finger = fingerForChar(ch);
      if (!finger) return this.setFocus({ keys: [key] });
      const reach = finger !== "thumb" && HOME_KEY_FOR_FINGER[finger] !== key ? { [finger]: key } : {};
      const fingers = [finger];
      const keys = [key];
      const shift = shiftForChar(ch);
      if (shift) {
        fingers.push(shift.finger);
        keys.push(shift.key);
        reach[shift.finger] = shift.key;
      }
      this.setFocus({ fingers, keys, reach });
    }

    clearFocus() {
      this.setFocus({});
    }

    flashKey(key, ok = true) {
      const el = this.keyEls.get(key.toLowerCase());
      if (!el) return;
      const cls = ok ? "tk-pressed" : "tk-wrong";
      el.classList.remove("tk-pressed", "tk-wrong");
      void el.getBoundingClientRect(); // restart the animation on repeat presses
      el.classList.add(cls);
      clearTimeout(el._flashTimer);
      el._flashTimer = setTimeout(() => el.classList.remove(cls), ok ? 180 : 400);
    }

    // --- posing --------------------------------------------------------------

    poseFor(reach) {
      const pose = structuredClone(this.rest);
      for (const [fingerName, keyId] of Object.entries(reach)) {
        const key = this.keys.get(keyId);
        if (!key) continue;
        const [side, finger] = fingerName.split("_");
        const hand = pose[side];
        const tip = hand.tips[finger];
        // On a wide key (Shift) aim for the end nearest the finger, not the middle.
        const target = {
          x: Math.min(Math.max(tip.x, key.x + 0.5 * U), key.x + key.w - 0.5 * U),
          y: key.cy,
        };
        // The hand leans a third of the way and the finger does the rest --
        // except reaching down, where the knuckles are already close, so
        // the hand drops most of the way and the finger still points up.
        const dy = target.y - tip.y;
        hand.shift = { x: (target.x - tip.x) / 3, y: dy > 0 ? dy * 0.85 : dy / 3 };
        hand.tips[finger] = { x: target.x - hand.shift.x, y: target.y - hand.shift.y };
      }
      return pose;
    }

    animateTo(target) {
      cancelAnimationFrame(this.anim);
      const from = structuredClone(this.pose);
      const start = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - start) / 260);
        this.pose = tweenPose(from, target, easeOut(t));
        this.drawHands();
        if (t < 1) this.anim = requestAnimationFrame(step);
      };
      this.anim = requestAnimationFrame(step);
    }

    drawHands() {
      const ghost = [];
      const lit = [];
      for (const side of SIDES) {
        const hand = this.pose[side];
        const at = (p) => ({ x: p.x + hand.shift.x, y: p.y + hand.shift.y });
        const palm = [
          at(hand.knuckles.pinky),
          ...hand.wrist.map(at),
          at(hand.thumbBase),
          at(hand.knuckles.index),
          at(hand.knuckles.middle),
          at(hand.knuckles.ring),
        ];
        ghost.push({ kind: "palm", points: palm });
        for (const finger of [...FINGERS, "thumb"]) {
          const base = finger === "thumb" ? hand.thumbBase : hand.knuckles[finger];
          const shape = { kind: "finger", from: at(base), to: at(hand.tips[finger]), w: SHAPE[finger].w * U };
          (this.lit.has(`${side}_${finger}`) ? lit : ghost).push({ ...shape, side, finger });
        }
      }
      this.handsEl.innerHTML = drawShapes(ghost, "tk-hand");
      this.litEl.innerHTML = drawShapes(lit, "tk-finger-lit");
    }
  }

  // Each shape is drawn twice, a fat dark pass then a fill pass, so the
  // fingers and palm merge into one outlined hand silhouette.
  function drawShapes(shapes, cls) {
    const outline = [];
    const fill = [];
    for (const s of shapes) {
      if (s.kind === "palm") {
        const pts = s.points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
        outline.push(`<polygon points="${pts}" stroke-width="${0.3 * U + 5}"></polygon>`);
        fill.push(`<polygon points="${pts}" stroke-width="${0.3 * U}"></polygon>`);
      } else {
        const line = `x1="${s.from.x.toFixed(1)}" y1="${s.from.y.toFixed(1)}" x2="${s.to.x.toFixed(1)}" y2="${s.to.y.toFixed(1)}"`;
        const data = `data-finger="${s.side}_${s.finger}"`;
        outline.push(`<line ${line} ${data} stroke-width="${s.w + 5}"></line>`);
        fill.push(`<line ${line} ${data} stroke-width="${s.w}"></line>`);
      }
    }
    return `<g class="${cls} ${cls}-outline">${outline.join("")}</g><g class="${cls} ${cls}-fill">${fill.join("")}</g>`;
  }

  function tweenPose(a, b, t) {
    if (typeof a === "number") return lerp(a, b, t);
    if (Array.isArray(a)) return a.map((v, i) => tweenPose(v, b[i], t));
    const out = {};
    for (const k of Object.keys(a)) out[k] = tweenPose(a[k], b[k], t);
    return out;
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, "&quot;");
  }

  TeachKeyboard.fingerForChar = fingerForChar;
  TeachKeyboard.shiftForChar = shiftForChar;
  return TeachKeyboard;
})();
