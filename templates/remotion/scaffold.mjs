/**
 * Create a Remotion workspace inside a video project, on first use.
 *
 *   node templates/remotion/scaffold.mjs <project-dir>
 *
 * The workspace lives in {project}/shots/, not in this plugin: node_modules belongs to the
 * project it renders, and one workspace per client keeps their brand and their output apart.
 *
 * Writes package.json, remotion.config.ts, src/, and copies the shot template plus a
 * brand.json placeholder. Never runs npm install itself — that is the user's call and their
 * bandwidth.
 */

import { mkdir, readFile, writeFile, access } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

const PACKAGE_JSON = {
  name: "gaspol-video-shots",
  private: true,
  version: "1.0.0",
  type: "module",
  scripts: {
    studio: "remotion studio src/index.ts",
    render: "remotion render src/index.ts",
  },
  dependencies: {
    "@remotion/cli": "^4.0.0",
    remotion: "^4.0.0",
    react: "^18.3.1",
    "react-dom": "^18.3.1",
  },
};

const REMOTION_CONFIG = `import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// Explainer shots are composited over clips, so a transparent shot needs ProRes 4444.
// Opaque cutaways render as h264 and stay small.
`;

const INDEX_TS = `import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
`;

const ROOT_TSX = `import React from "react";
import { Composition } from "remotion";
import { MetricReveal, compositionConfig } from "./shots/MetricReveal";

// One <Composition> per shot. Add a line here when you add a shot file.
export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id={compositionConfig.id}
      component={MetricReveal}
      durationInFrames={compositionConfig.durationInFrames}
      fps={compositionConfig.fps}
      width={compositionConfig.width}
      height={compositionConfig.height}
    />
  </>
);
`;

async function exists(p) {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

async function main() {
  const project = process.argv[2];
  if (!project) {
    console.error("usage: node templates/remotion/scaffold.mjs <project-dir>");
    process.exit(2);
  }
  const root = path.join(project, "shots");
  if (await exists(path.join(root, "package.json"))) {
    console.log(`workspace already exists at ${root} — nothing was overwritten`);
    return;
  }

  await mkdir(path.join(root, "src", "shots"), { recursive: true });
  await mkdir(path.join(root, "out"), { recursive: true });

  await writeFile(path.join(root, "package.json"), `${JSON.stringify(PACKAGE_JSON, null, 2)}\n`);
  await writeFile(path.join(root, "remotion.config.ts"), REMOTION_CONFIG);
  await writeFile(path.join(root, "src", "index.ts"), INDEX_TS);
  await writeFile(path.join(root, "src", "Root.tsx"), ROOT_TSX);
  await writeFile(
    path.join(root, "src", "shots", "MetricReveal.tsx"),
    await readFile(path.join(here, "Shot.template.tsx"), "utf8"),
  );
  await writeFile(
    path.join(root, "src", "shots", "brand.json"),
    await readFile(path.join(here, "brand.json"), "utf8"),
  );

  console.log(`scaffolded ${root}`);
  console.log("next:");
  console.log(`  1. write ${path.join(root, "src", "shots", "brand.json")} from strategic-brief.md`);
  console.log(`  2. cd ${root} && npm install    (about 300MB, once per project)`);
  console.log("  3. npm run studio               to see the shot");
  console.log("  4. npx remotion render src/index.ts <ShotId> out/<ShotId>.mp4");
}

main().catch((err) => {
  console.error(`scaffold: ${err.message}`);
  process.exit(1);
});
