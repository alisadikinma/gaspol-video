// Motion QA: bundle ONCE, render several frames of one shot.
//   node scripts/frames.mjs <ShotId> 0,30,60,90   -> out/frames/<ShotId>-<frame>.png
import { bundle } from '@remotion/bundler';
import { selectComposition, renderStill } from '@remotion/renderer';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [id, list] = process.argv.slice(2);
if (!id || !list) {
  console.error('usage: node scripts/frames.mjs <ShotId> <frame,frame,...>');
  process.exit(1);
}
const frames = list.split(',').map(Number);
if (frames.some((f) => !Number.isInteger(f) || f < 0)) {
  console.error(`bad frame list: ${list}`);
  process.exit(1);
}
const serveUrl = await bundle({ entryPoint: path.join(root, 'src', 'index.ts'), publicDir: path.join(root, 'public') });
const composition = await selectComposition({ serveUrl, id });
mkdirSync(path.join(root, 'out', 'frames'), { recursive: true });
for (const frame of frames) {
  await renderStill({ composition, serveUrl, frame, output: path.join(root, 'out', 'frames', `${id}-${frame}.png`) });
}
console.log('ok', id, frames.length, 'frames');
