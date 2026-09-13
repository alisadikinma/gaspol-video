import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { parseConfig } from "../../templates/remotion/scripts/gen-registry.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const shotTemplatePath = path.join(here, "..", "..", "templates", "remotion", "Shot.template.tsx");

test("parseConfig reads the compositionConfig block of Shot.template.tsx, trailing comments and all", async () => {
  const src = await readFile(shotTemplatePath, "utf8");
  assert.deepEqual(parseConfig(src), {
    id: "MetricReveal",
    durationInFrames: 150,
    fps: 30,
    width: 1920,
    height: 1080,
    transparent: false,
  });
});

test("no compositionConfig block returns null", () => {
  assert.equal(parseConfig("export const somethingElse = { id: 'X' };"), null);
});

test("compositionConfig without an id returns null", () => {
  assert.equal(
    parseConfig("export const compositionConfig = { width: 1920, height: 1080 };"),
    null,
  );
});

test("durationInSeconds and fps combine into durationInFrames when durationInFrames is absent", () => {
  const cfg = parseConfig(
    "export const compositionConfig = { id: 'X', durationInSeconds: 4, fps: 25 };",
  );
  assert.equal(cfg.durationInFrames, 100);
  assert.equal(cfg.fps, 25);
});

test("transparent: true is read as a boolean", () => {
  const cfg = parseConfig(
    "export const compositionConfig = { id: 'X', transparent: true };",
  );
  assert.equal(cfg.transparent, true);
});
