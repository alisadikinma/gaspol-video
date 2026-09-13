// QA-frame renderer: bundle once, render specific frames of one composition.
//   node scripts/qa-frames.mjs MetricReveal --out ../scratch b1=40 b3-tail=90
// Frames land as <out>/<name>.jpeg at scale 0.5 — for READING during QA, not delivery.
import { bundle } from '@remotion/bundler';
import { selectComposition, renderStill } from '@remotion/renderer';
import path from 'path';
import { fileURLToPath } from 'url';
import { mkdirSync } from 'fs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const compId = args[0];
const outIdx = args.indexOf('--out');
const outDir = path.resolve(outIdx >= 0 ? args[outIdx + 1] : 'out/qa');
const pairs = args.slice(1).filter((a, i) => !a.startsWith('--') && (outIdx < 0 || i + 1 !== outIdx + 1));
if (!compId || !pairs.length) {
  console.error('usage: node scripts/qa-frames.mjs <CompId> [--out dir] name=frame [name=frame ...]');
  process.exit(1);
}
mkdirSync(outDir, { recursive: true });

console.log('bundling...');
const serveUrl = await bundle({ entryPoint: path.join(root, 'src', 'index.ts'), publicDir: path.join(root, 'public') });
const composition = await selectComposition({ serveUrl, id: compId });
for (const p of pairs) {
  const [name, f] = p.split('=');
  const frame = Number(f);
  if (!Number.isFinite(frame)) { console.error(`skip ${p}`); continue; }
  await renderStill({
    serveUrl, composition, output: path.join(outDir, `${name}.jpeg`),
    frame, scale: 0.5, overwrite: true, imageFormat: 'jpeg',
  });
  console.log(`  ${name} -> f${frame}`);
}
console.log('done ->', outDir);
