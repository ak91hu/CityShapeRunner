import assert from "node:assert/strict";
import test from "node:test";
import { shuffled } from "../src/inspiration.js";

test("shuffling keeps every idea once, preserves the source and supports empty decks", () => {
  const source = Object.freeze(["heart", "star", "fish", "tree"]);
  const deck = shuffled(source, () => 0);
  assert.deepEqual([...deck].sort(), [...source].sort());
  assert.notDeepEqual(deck, source);
  assert.deepEqual(source, ["heart", "star", "fish", "tree"]);
  assert.deepEqual(shuffled([]), []);
  assert.deepEqual(shuffled(["heart"]), ["heart"]);
});
