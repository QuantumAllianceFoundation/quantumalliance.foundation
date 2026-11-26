// Homepage media slider. Progressive enhancement: without this script the
// track still scrolls by swipe or trackpad, and the buttons stay hidden.

export const AUTOPLAY_MS = 5000;

// Returns the scroll position for one step in `direction` (1 or -1).
// Stepping past either end wraps to the other end.
export function nextScrollLeft(current, step, maxScroll, direction) {
  const edge = 4; // tolerance for subpixel scroll positions
  if (direction > 0 && current >= maxScroll - edge) return 0;
  if (direction < 0 && current <= edge) return maxScroll;
  return Math.min(Math.max(current + direction * step, 0), maxScroll);
}

// Auto-advance runs only when the visitor has not paused it, is not
// pointing at or focused inside the slider, and the tab is visible.
export function shouldAdvance({ paused, hovered, focused, hidden }) {
  return !paused && !hovered && !focused && !hidden;
}

function enhance(slider) {
  const track = slider.querySelector(".media-track");
  const buttons = slider.querySelector(".slider-buttons");
  const toggle = slider.querySelector("button[data-autoplay]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const state = { paused: reduceMotion, hovered: false, focused: false, hidden: document.hidden };

  const step = (direction) => {
    const card = track.firstElementChild;
    const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
    const left = nextScrollLeft(
      track.scrollLeft,
      card.offsetWidth + gap,
      track.scrollWidth - track.clientWidth,
      direction,
    );
    track.scrollTo({ left, behavior: reduceMotion ? "auto" : "smooth" });
  };

  let timer = null;
  const restart = () => {
    clearInterval(timer);
    timer = shouldAdvance(state) ? setInterval(() => step(1), AUTOPLAY_MS) : null;
  };
  const showToggle = () => {
    toggle.textContent = state.paused ? "Play" : "Pause";
    toggle.setAttribute("aria-label", state.paused ? "Play slider" : "Pause slider");
  };

  buttons.hidden = false;
  buttons.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button === toggle) {
      state.paused = !state.paused;
      showToggle();
    } else {
      step(Number(button.dataset.direction));
    }
    restart();
  });

  const watch = (target, on, off, key) => {
    target.addEventListener(on, () => { state[key] = true; restart(); });
    target.addEventListener(off, () => { state[key] = false; restart(); });
  };
  watch(track, "pointerenter", "pointerleave", "hovered");
  watch(track, "focusin", "focusout", "focused");
  document.addEventListener("visibilitychange", () => {
    state.hidden = document.hidden;
    restart();
  });

  showToggle();
  restart();
}

if (typeof document !== "undefined") {
  document.querySelectorAll("[data-media-slider]").forEach(enhance);
}
