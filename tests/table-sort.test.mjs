import { test } from "node:test";
import assert from "node:assert/strict";
import { compareValues, sortOrder } from "../assets/table-sort.js";

test("numbers compare numerically", () => {
  assert.deepEqual(sortOrder(["10", "9", "100"], "number", "asc"), [1, 0, 2]);
});
test("text compares case-insensitively", () => {
  assert.deepEqual(sortOrder(["beta", "Alpha"], "text", "asc"), [1, 0]);
});
test("empty values sort last in both directions", () => {
  assert.deepEqual(sortOrder(["", "2", "1"], "number", "asc"), [2, 1, 0]);
  assert.deepEqual(sortOrder(["", "2", "1"], "number", "desc"), [1, 2, 0]);
});
test("ties keep original order", () => {
  assert.deepEqual(sortOrder(["a", "a", "a"], "text", "desc"), [0, 1, 2]);
});
test("compareValues returns a signed number", () => {
  assert.ok(compareValues("2", "10", "number") < 0);
  assert.ok(compareValues("b", "A", "text") > 0);
});
