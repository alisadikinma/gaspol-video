// Renders the TEXT of every cue of one kinetic overlay, alone on flat mid-grey, one still per cue.
//   node scripts/render-overlay-text.mjs src/shots/overlay-03.json --out <dir>
// Called by tools/layout_gate.py --overlay, which measures the real text box in each still
// (no clip, panels, mask or effects behind it). Writes <dir>/<scene>-<cue id>.png and
// <dir>/overlay-<scene>.frames.json = [{id, frame, inF, outF, png}] on the frame where the cue is
// at full size (measureFrame in lib/overlayFx.mjs).
// @remotion/bundler and @remotion/renderer are imported inside main(), not at module load, so the
// pure helpers (and their node test) work in the plugin's template directory, where those
// packages are never installed.
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'fs';

// lib/ sits at ../src/lib in a scaffolded workspace and at ../lib in the plugin's template tree.
const { measureFrame } = await import('../src/lib/overlayFx.mjs').catch(() => import('../lib/overlayFx.mjs'));

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export function parseArgs(argv) {
  const outIdx = argv.indexOf('--out');
  const plan = argv.find((a, i) => !a.startsWith('--') && i !== outIdx + 1);
  if (!plan || outIdx < 0 || !argv[outIdx + 1]) {
    throw new Error('usage: node scripts/render-overlay-text.mjs <overlay-<scene>.json> --out <dir>');
  }
  return { plan, out: argv[outIdx + 1] };
}

// The overlay json a KineticOverlay scene file imports, or null when the file is not one.
export function wiredPlan(src) {
  if (!/id\s*:\s*['"]KineticOverlay['"]/.test(src)) return null;
  const m = /from\s+['"]\.\/(overlay-[^'"/]+\.json)['"]/.exec(src);
  return m ? m[1] : null;
}

export function framePlan(plan) {
  if (!plan.cues || !plan.cues.length) throw new Error('overlay plan has no cues');
  return plan.cues.map((cue) => ({
    id: String(cue.id),
    frame: measureFrame(cue, plan.fps),
    inF: cue.inF,
    outF: cue.outF,
  }));
}

function slug(text) {
  return String(text).replace(/[^A-Za-z0-9_-]+/g, '_');
}

// One workspace holds ONE KineticOverlay composition (gen-registry skips duplicate ids), wired to
// one overlay json. Measuring another scene's json against it would silently measure the wrong text.
function assertWired(planFile) {
  const dir = path.join(root, 'src', 'shots');
  const wired = [];
  for (const name of readdirSync(dir)) {
    if (!name.endsWith('.tsx')) continue;
    const w = wiredPlan(readFileSync(path.join(dir, name), 'utf8'));
    if (w) wired.push(w);
  }
  const want = path.basename(planFile);
  if (!wired.includes(want)) {
    throw new Error(`the workspace's KineticOverlay is wired to ${wired.join(', ') || 'no overlay json'}, `
      + `not ${want}: set SCENE and the plan import in the scene file together (see Overlay.template.tsx), `
      + 'run npm run gen, then measure again');
  }
}

async function main() {
  const { plan: planFile, out } = parseArgs(process.argv.slice(2));
  const plan = JSON.parse(readFileSync(path.resolve(planFile), 'utf8'));
  const frames = framePlan(plan);
  assertWired(planFile);
  const outDir = path.resolve(out);
  mkdirSync(outDir, { recursive: true });

  const { bundle } = await import('@remotion/bundler');
  const { selectComposition, renderStill } = await import('@remotion/renderer');

  console.log('bundling...');
  // publicDir must be passed explicitly: remotion.config.ts only applies to the CLI.
  const serveUrl = await bundle({ entryPoint: path.join(root, 'src', 'index.ts'), publicDir: path.join(root, 'public') });
  const done = [];
  for (const f of frames) {
    const inputProps = { textOnly: true, cueId: f.id };
    const composition = await selectComposition({ serveUrl, id: 'KineticOverlay', inputProps });
    const png = path.join(outDir, `${plan.scene}-${slug(f.id)}.png`);
    await renderStill({
      serveUrl, composition, output: png, frame: f.frame, imageFormat: 'png', inputProps, overwrite: true,
    });
    done.push({ ...f, png });
    console.log(`  cue ${f.id} -> f${f.frame}`);
  }
  const manifest = path.join(outDir, `overlay-${plan.scene}.frames.json`);
  writeFileSync(manifest, JSON.stringify(done, null, 2));
  console.log('->', manifest);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((err) => {
    console.error(`render-overlay-text: ${err.message}`);
    process.exit(1);
  });
}
