import assert from "node:assert/strict";
import test from "node:test";
import { durationFrames, wordFrame, findWordFrame, smooth } from "../../templates/remotion/lib/diagramFx.mjs";

const words = [["Nah,", 0.031, 0.331], ["disinilah", 0.491, 0.851], ["Angkat,", 2.811, 3.191]];

test("durationFrames rounds seconds to frames at 30 fps", () => {
  assert.equal(durationFrames(4.272472), 128);
  assert.equal(durationFrames(6.269388), 188);
  assert.equal(durationFrames(0), 1);
});
test("wordFrame reads a start time and throws on a missing index", () => {
  assert.equal(wordFrame(words, 2), 84);
  assert.throws(() => wordFrame(words, 9));
});
test("findWordFrame ignores case and punctuation", () => {
  assert.equal(findWordFrame(words, "angkat"), 84);
  assert.throws(() => findWordFrame(words, "xyz"));
});
test("smooth clamps and eases", () => {
  assert.equal(smooth(0, 10, 20), 0);
  assert.equal(smooth(30, 10, 20), 1);
  assert.equal(smooth(15, 10, 20), 0.5);
});
