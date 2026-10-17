// Batch runner: voice-change many scenes with PER-CHARACTER voice_settings and seed from one
// cast file. The request itself is voice_changer.mjs convertSpans (it takes --stability/--style/
// --seed on the CLI); this file only maps each scene to its cast member and converts the listed
// spans, so the clip's SFX between phrases stays original. Without per-character settings the
// account's saved settings apply (a saved stability of 1.0 made a lively character read flat).
// Get the spans from `eleven.mjs stt` word timings.
//
//   node tools/vidkit/js/cast_voice.mjs plan.json [--env .env --env .env.voices] [scene ...]
//
// plan.json:
//   { "cast":   { "c1": { "voice_env": "ELEVENLABS_VOICE_C1", "seed": 2026091301,
//                         "settings": { "stability": 0.22, "similarity_boost": 0.75, "style": 0.8 } } },
//     "scenes": { "S03": { "cast": "c1", "spans": "0.02-2.66,3.08-4.48", "clip": "clips/S03.mp4", "out": "vo/native/S03.mp3" } } }
// A clip with TWO speakers needs two passes (convert speaker A, then run speaker B on that output);
// one scene entry supports one cast member.
import { readFileSync } from "node:fs";
import { loadEnv } from "./env.mjs";
import { convertSpans, parseSpans } from "../../voice_changer.mjs";

export async function run(plan, { env, only = [], convert = convertSpans, fetchImpl } = {}) {
  const results = {};
  for (const [scene, cfg] of Object.entries(plan.scenes)) {
    if (only.length && !only.includes(scene)) continue;
    const member = plan.cast[cfg.cast];
    if (!member) throw new Error(`${scene}: unknown cast "${cfg.cast}"`);
    results[scene] = await convert({
      inputPath: cfg.clip || `clips/${scene}.mp4`,
      outPath: cfg.out || `vo/native/${scene}.mp3`,
      spans: parseSpans(cfg.spans),
      voiceEnv: member.voice_env,
      env,
      voiceSettings: member.settings || null,
      seed: member.seed ?? null,
      fetchImpl,
    });
  }
  return results;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2), envFiles = [], rest = [];
  for (let i = 0; i < args.length; i++) args[i] === "--env" ? envFiles.push(args[++i]) : rest.push(args[i]);
  const [planFile, ...only] = rest;
  if (!planFile) { console.error("usage: cast_voice.mjs plan.json [--env FILE] [scene ...]"); process.exit(1); }
  run(JSON.parse(readFileSync(planFile, "utf8")), { env: loadEnv(...envFiles), only })
    .catch((e) => { console.error(`FAIL: ${e.message}`); process.exit(1); });
}
