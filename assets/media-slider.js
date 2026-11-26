// Homepage media slider. Progressive enhancement: without this script the
// track still scrolls by swipe or trackpad, and the buttons stay hidden.

// Returns the scroll position for one step in `direction` (1 or -1).
// Stepping past either end wraps to the other end.
export function nextScrollLeft(current, step, maxScroll, direction) {
  const edge = 4; // tolerance for subpixel scroll positions
  if (direction > 0 && current >= maxScroll - edge) return 0;
  if (direction < 0 && current <= edge) return maxScroll;
  return Math.min(Math.max(current + direction * step, 0), maxScroll);
}

function enhance(slider) {
  const track = slider.querySelector(".media-track");
  const buttons = slider.querySelector(".slider-buttons");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  buttons.hidden = false;
  buttons.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-direction]");
    if (!button) return;
    const card = track.firstElementChild;
    const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
    const left = nextScrollLeft(
      track.scrollLeft,
      card.offsetWidth + gap,
      track.scrollWidth - track.clientWidth,
      Number(button.dataset.direction),
    );
    track.scrollTo({ left, behavior: reduceMotion ? "auto" : "smooth" });
  });
}

if (typeof document !== "undefined") {
  document.querySelectorAll("[data-media-slider]").forEach(enhance);
}
