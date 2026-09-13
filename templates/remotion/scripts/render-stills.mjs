// Renders one still frame of a mocked app-screen composition.
//   node scripts/render-stills.mjs <CompId> --props '<json>' --out <png>
// Called once per (screen, state) pair by tools/gen_app_screen.py mock. Every composition
// this renders is a Screen.template.tsx-derived component with durationInFrames: 1 — this
// always asks for frame 0, never a later one, so there is nothing to animate through.
// @remotion/bundler and @remotion/renderer are imported lazily inside main(), not at module
// load, so parseArgs (and its test) work even when this file sits in the plugin's template
// directory, where those packages are never installed — only a scaffolded shots/ workspace
// has them, after `npm install`.
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import { mkdirSync } from 'fs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export function parseArgs(argv) {
  const id = argv[0];
  const propsIdx = argv.indexOf('--props');
  const outIdx = argv.indexOf('--out');
  if (!id || propsIdx < 0 || outIdx < 0 || !argv[propsIdx + 1] || !argv[outIdx + 1]) {
    throw new Error('usage: node scripts/render-stills.mjs <CompId> --props <json> --out <png>');
  }
  let props;
  try {
    props = JSON.parse(argv[propsIdx + 1]);
  } catch {
    throw new Error('props is not valid JSON');
  }
  return { id, props, out: argv[outIdx + 1] };
}

async function main() {
  const { id, props, out } = parseArgs(process.argv.slice(2));
  const outPath = path.resolve(out);
  mkdirSync(path.dirname(outPath), { recursive: true });

  const { bundle } = await import('@remotion/bundler');
  const { selectComposition, renderStill } = await import('@remotion/renderer');

  console.log('bundling...');
  // publicDir must be passed explicitly: remotion.config.ts only applies to the CLI, not
  // the programmatic bundle() API — same rule as render-all.mjs and qa-frames.mjs.
  const serveUrl = await bundle({ entryPoint: path.join(root, 'src', 'index.ts'), publicDir: path.join(root, 'public') });
  const composition = await selectComposition({ serveUrl, id, inputProps: props });
  await renderStill({
    serveUrl,
    composition,
    output: outPath,
    frame: 0,
    imageFormat: 'png',
    inputProps: props,
    overwrite: true,
  });
  console.log('->', outPath);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((err) => {
    console.error(`render-stills: ${err.message}`);
    process.exit(1);
  });
}
