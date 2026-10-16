// End-state QA: bundle once, render the last frame (every cue visible) of each listed shot.
//   node scripts/qa-end.mjs S05Rumus S12SatuLayar   (no ids = every shot in src/shots.manifest.json)
// Output: out/qa/<ShotId>-end.png
import { bundle } from '@remotion/bundler';
import { selectComposition, renderStill } from '@remotion/renderer';
import { readFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ids = process.argv.slice(2);
const manifest = JSON.parse(readFileSync(path.join(root, 'src', 'shots.manifest.json'), 'utf8'));
const outDir = path.join(root, 'out', 'qa');
mkdirSync(outDir, { recursive: true });
const serveUrl = await bundle({ entryPoint: path.join(root, 'src', 'index.ts'), publicDir: path.join(root, 'public') });
for (const s of manifest) {
  if (ids.length && !ids.includes(s.id)) continue;
  const composition = await selectComposition({ serveUrl, id: s.id });
  await renderStill({ serveUrl, composition, output: path.join(outDir, `${s.id}-end.png`), frame: composition.durationInFrames - 2, imageFormat: 'png' });
  console.log('qa', s.id);
}
