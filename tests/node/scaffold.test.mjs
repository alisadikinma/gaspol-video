import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const here = path.dirname(fileURLToPath(import.meta.url));
const scaffoldPath = path.join(here, "..", "..", "templates", "remotion", "scaffold.mjs");

async function withTmp(fn) {
  const dir = await mkdtemp(path.join(tmpdir(), "gv-scaffold-"));
  try {
    return await fn(dir);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

test("scaffold copies the lib and script files a registry-based workspace needs", async () => {
  await withTmp(async (project) => {
    execFileSync("node", [scaffoldPath, project]);

    const shotsRoot = path.join(project, "shots");
    for (const rel of [
      "src/lib/brand.ts",
      "src/lib/kit.tsx",
      "src/lib/browser.tsx",
      "src/lib/screencast.tsx",
      "scripts/gen-registry.mjs",
      "scripts/render-all.mjs",
      "scripts/qa-frames.mjs",
      "scripts/render-stills.mjs",
      "src/registry.gen.tsx",
    ]) {
      const p = path.join(shotsRoot, rel);
      const st = await stat(p);
      assert.ok(st.isFile(), `expected file to exist: ${rel}`);
    }
    await stat(path.join(shotsRoot, "public"));

    const pkg = JSON.parse(await readFile(path.join(shotsRoot, "package.json"), "utf8"));
    assert.ok(pkg.dependencies["@remotion/renderer"], "package.json must depend on @remotion/renderer");
    assert.ok(pkg.dependencies["@remotion/bundler"], "package.json must depend on @remotion/bundler");

    const registryStat1 = await stat(path.join(shotsRoot, "src", "registry.gen.tsx"));

    const out = execFileSync("node", [scaffoldPath, project], { encoding: "utf8" });
    assert.match(out, /already exists/);

    const registryStat2 = await stat(path.join(shotsRoot, "src", "registry.gen.tsx"));
    assert.equal(registryStat1.mtimeMs, registryStat2.mtimeMs, "second run must not touch existing files");
  });
});
