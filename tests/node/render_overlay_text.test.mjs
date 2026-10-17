import assert from "node:assert/strict";
import test from "node:test";

import {
  parseArgs, wiredPlan, framePlan,
} from "../../templates/remotion/scripts/render-overlay-text.mjs";
import { measureFrame } from "../../templates/remotion/lib/overlayFx.mjs";

test("parseArgs reads the overlay json and --out", () => {
  assert.deepEqual(parseArgs(["a/overlay-03.json", "--out", "o"]), { plan: "a/overlay-03.json", out: "o" });
});

test("parseArgs without both arguments is a usage error", () => {
  assert.throws(() => parseArgs([]), /usage/);
  assert.throws(() => parseArgs(["x.json"]), /usage/);
  assert.throws(() => parseArgs(["--out", "o"]), /usage/);
});

test("wiredPlan names the json a KineticOverlay scene file imports", () => {
  const src = "import rawPlan from './overlay-03.json';\nexport const compositionConfig = {\n  id: 'KineticOverlay',\n};";
  assert.equal(wiredPlan(src), "overlay-03.json");
});

test("wiredPlan is null for a file that is not the overlay composition", () => {
  assert.equal(wiredPlan("import rawPlan from './overlay-03.json';\nexport const compositionConfig = { id: 'Other' };"), null);
  assert.equal(wiredPlan("export const compositionConfig = { id: 'KineticOverlay' };"), null);
});

test("framePlan gives one measure frame per cue, with its id and window", () => {
  const plan = {
    fps: 30,
    cues: [{ id: "a", inF: 30, keyF: 45, outF: 150 }, { id: 2, inF: 160, keyF: 170, outF: 260 }],
  };
  const frames = framePlan(plan);
  assert.deepEqual(frames.map((f) => f.id), ["a", "2"]);
  assert.equal(frames[0].frame, measureFrame(plan.cues[0], 30));
  assert.deepEqual([frames[1].inF, frames[1].outF], [160, 260]);
});

test("framePlan refuses a plan with no cues", () => {
  assert.throws(() => framePlan({ fps: 30, cues: [] }), /no cues/);
});
