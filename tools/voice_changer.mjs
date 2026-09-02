/**
 * Convert dialogue a video platform generated into a locked character voice.
 *
 *   node tools/voice_changer.mjs <clip> --voice-env ELEVENLABS_VOICE_C2 --out vo/scene-02-c2.mp3
 *
 * Why this exists: no video platform can lip-sync to an audio file you hand it, so a scene
 * where a face is speaking has to be voiced by the platform. That voice is whatever the
 * model felt like producing, and it changes between clips. Speech-to-speech replaces the
 * timbre while keeping the performance, which is what keeps the mouth matching.
 *
 * The whole approach rests on one property: speech-to-speech preserves duration. That is
 * VERIFIED here, never assumed. Drift beyond 0.05s means the output is not written and the
 * number is reported, because a stretched voice is exactly the artefact this system exists
 * to avoid.
 *
 * No dependencies: global fetch, node:fs, ffmpeg/ffprobe for extraction and measurement.
 */

import { execFile } from "node:child_process";
import { mkdir, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const API_BASE = "https://api.elevenlabs.io/v1/speech-to-speech";
const DEFAULT_MODEL = "eleven_multilingual_sts_v2";

/** See global-promo-config.md §29.4 voice_changer_max_drift_s. */
export const MAX_DRIFT_S = 0.05;

export const driftMessage =
  "speech-to-speech changed the duration, so lip-sync would no longer match";

export async function extractAudio(clipPath, outPath) {
  await mkdir(path.dirname(outPath), { recursive: true });
  await execFileAsync("ffmpeg", [
    "-y", "-v", "error", "-i", clipPath,
    "-vn", "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", outPath,
  ]);
  return outPath;
}

export async function probeDuration(file) {
  try {
    const { stdout } = await execFileAsync("ffprobe", [
      "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file,
    ]);
    const value = Number.parseFloat(stdout.trim());
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

export async function convert({
  inputPath,
  outPath,
  voiceEnv,
  env = process.env,
  model = DEFAULT_MODEL,
  fetchImpl = globalThis.fetch,
  extract = extractAudio,
  durationOf = probeDuration,
  log = console.log,
}) {
  const apiKey = env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    const reason =
      "ELEVENLABS_API_KEY not set — dialogue was left in the platform's own voice. " +
      "The video still assembles; the character's voice will differ between scenes. " +
      "Set the key in this plugin's .env and re-run this pass.";
    log(reason);
    return { degraded: true, reason };
  }
  if (!voiceEnv) {
    throw new Error("no voice_env given — the VOICE: block in cast-profile.md must name one");
  }
  const voiceId = env[voiceEnv];
  if (!voiceId) {
    throw new Error(
      `voice env ${voiceEnv} not set. Add it to .env; this tool never substitutes another voice.`,
    );
  }

  const workDir = path.join(path.dirname(outPath), ".work");
  const extracted = await extract(inputPath, path.join(workDir, `${path.basename(outPath, ".mp3")}.wav`));

  const sourceDuration = await durationOf(extracted);
  if (sourceDuration === null) {
    throw new Error(
      `cannot measure the source duration of ${path.basename(extracted)} — ` +
      "refusing to convert, because duration preservation is the property this step depends on",
    );
  }

  const form = new FormData();
  form.append("model_id", model);
  // Deliberately no text field: this converts the performance that is already there.
  // Handing it a script would re-read the line and destroy the timing that lip-sync needs.
  const { readFile } = await import("node:fs/promises");
  form.append("audio", new Blob([await readFile(extracted)]), path.basename(extracted));

  const response = await fetchImpl(`${API_BASE}/${voiceId}`, {
    method: "POST",
    headers: { "xi-api-key": apiKey },
    body: form,
  });

  if (!response.ok) {
    const detail = (await response.text?.()) ?? "";
    throw new Error(`ElevenLabs speech-to-speech returned ${response.status}. ${detail}`.trim());
  }

  const audio = Buffer.from(await response.arrayBuffer());
  const staging = path.join(workDir, `${path.basename(outPath, ".mp3")}.candidate.mp3`);
  await mkdir(workDir, { recursive: true });
  await writeFile(staging, audio);

  const outDuration = await durationOf(staging);
  if (outDuration === null) {
    throw new Error(
      "cannot measure the converted duration — refusing to write an unverified conversion",
    );
  }

  const drift = Number((outDuration - sourceDuration).toFixed(3));
  if (Math.abs(drift) > MAX_DRIFT_S) {
    await unlink(staging).catch(() => {});
    throw new Error(
      `${driftMessage}: ${sourceDuration.toFixed(3)}s -> ${outDuration.toFixed(3)}s ` +
      `(drift ${drift.toFixed(3)}s, tolerance ${MAX_DRIFT_S}s). Nothing was written. ` +
      "Do not stretch the audio to fit; reopen the mixed-source decision instead.",
    );
  }

  await mkdir(path.dirname(outPath), { recursive: true });
  await writeFile(outPath, audio);
  await unlink(staging).catch(() => {});
  log(`  ${path.basename(outPath)}: ${sourceDuration.toFixed(3)}s -> ${outDuration.toFixed(3)}s ` +
      `(drift ${drift >= 0 ? "+" : ""}${drift.toFixed(3)}s)`);

  return { ok: true, drift_s: drift, source_s: sourceDuration, out_s: outDuration, out: outPath };
}

async function main(argv) {
  const args = argv.slice(2);
  const clip = args.find((a) => !a.startsWith("--"));
  const flag = (name, fallback = null) => {
    const i = args.indexOf(`--${name}`);
    return i >= 0 ? args[i + 1] : fallback;
  };
  if (!clip) {
    console.error(
      "usage: node tools/voice_changer.mjs <clip> --voice-env ELEVENLABS_VOICE_C2 --out vo/scene-02-c2.mp3",
    );
    return 2;
  }

  let envFile = {};
  try {
    const { readFile } = await import("node:fs/promises");
    const text = await readFile(path.join(process.cwd(), ".env"), "utf8");
    for (const line of text.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const [k, ...v] = trimmed.split("=");
      const value = v.join("=").trim().replace(/^["']|["']$/g, "");
      if (value) envFile[k.trim()] = value;
    }
  } catch { /* no .env is fine */ }

  const result = await convert({
    inputPath: clip,
    outPath: flag("out", "vo/converted.mp3"),
    voiceEnv: flag("voice-env"),
    model: flag("model", DEFAULT_MODEL),
    env: { ...envFile, ...process.env },
  });
  return result.degraded ? 0 : 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv).then((code) => process.exit(code)).catch((err) => {
    console.error(`voice_changer: ${err.message}`);
    process.exit(1);
  });
}
