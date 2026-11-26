import { test } from "node:test";
import assert from "node:assert/strict";
import { nextScrollLeft, shouldAdvance } from "../assets/media-slider.js";

test("steps forward and back by one card", () => {
  assert.equal(nextScrollLeft(0, 300, 1200, 1), 300);
  assert.equal(nextScrollLeft(600, 300, 1200, -1), 300);
});
test("clamps a partial last step to the end", () => {
  assert.equal(nextScrollLeft(1000, 300, 1200, 1), 1200);
  assert.equal(nextScrollLeft(200, 300, 1200, -1), 0);
});
test("wraps around at either end", () => {
  assert.equal(nextScrollLeft(1199, 300, 1200, 1), 0);
  assert.equal(nextScrollLeft(2, 300, 1200, -1), 1200);
});
test("auto-advance runs only when nothing holds it", () => {
  const idle = { paused: false, hovered: false, focused: false, hidden: false };
  assert.equal(shouldAdvance(idle), true);
  for (const key of Object.keys(idle)) {
    assert.equal(shouldAdvance({ ...idle, [key]: true }), false, key);
  }
});
