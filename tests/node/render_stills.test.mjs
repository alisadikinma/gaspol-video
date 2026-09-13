import assert from "node:assert/strict";
import test from "node:test";

import { parseArgs } from "../../templates/remotion/scripts/render-stills.mjs";

test("parseArgs reads id, props (parsed JSON) and out", () => {
  const result = parseArgs(["X", "--props", '{"state":"a"}', "--out", "o.png"]);
  assert.deepEqual(result, { id: "X", props: { state: "a" }, out: "o.png" });
});

test("invalid JSON props throws a clear error", () => {
  assert.throws(
    () => parseArgs(["X", "--props", "{not json", "--out", "o.png"]),
    /props is not valid JSON/,
  );
});

test("missing --props or --out throws a usage error", () => {
  assert.throws(() => parseArgs(["X"]), /usage/);
});
