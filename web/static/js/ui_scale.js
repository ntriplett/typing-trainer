// How big the whole app draws, for big high-resolution screens. Picked on
// the grown-ups page and kept in this browser (so it belongs to the
// computer and its screen, not a player). Loaded in every page's <head>,
// so the page never shows at the wrong size first.
//
// It's CSS zoom on <html>. Element boxes and mouse positions zoom
// together, so clicks need no change; code that compares a box
// (getBoundingClientRect) with an element's own size (clientWidth, style
// px) divides by UIScale.zoom(el). Full-window sizes use var(--ui-zoom).

const UIScale = {
  SIZES: [1, 1.25, 1.5, 1.75, 2],
  KEY: "ui-scale",

  get() {
    let v = 1;
    try {
      v = Number(localStorage.getItem(this.KEY)) || 1;
    } catch (e) {
      /* storage blocked: normal size */
    }
    return this.SIZES.includes(v) ? v : 1;
  },

  set(v) {
    try {
      localStorage.setItem(this.KEY, String(v));
    } catch (e) {
      /* it still applies to this page */
    }
    this.apply(v);
  },

  apply(v = this.get()) {
    const root = document.documentElement;
    root.style.zoom = v === 1 ? "" : String(v);
    root.style.setProperty("--ui-zoom", String(v));
  },

  // The zoom an element is drawn at (1 when the browser can't say).
  zoom(el = document.documentElement) {
    return el.currentCSSZoom || 1;
  },
};

UIScale.apply();
// another window (the grown-ups page) changed it
window.addEventListener("storage", (e) => {
  if (e.key === UIScale.KEY) UIScale.apply();
});
