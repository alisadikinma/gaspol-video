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

export const spansWarning =
  "converting the WHOLE track: every voice on it becomes the target voice, not just the " +
  "character you meant. If a second person speaks in this clip, pass --spans with that " +
  "character's turns instead.";

/** Crossfade at every seam between original bed and converted speech. */
export const SEAM_PAD_S = 0.05;

/**
 * "0-3.88,5.2-7" -> [{start_s, end_s}, ...]
 *
 * Refuses anything it cannot honour rather than repairing it: a reversed or overlapping
 * span means the caller has the speaker turns wrong, and quietly sorting them would
 * convert the wrong person while looking like it worked.
 */
export function parseSpans(text) {
  const spans = [];
  for (const raw of String(text).split(",")) {
    const piece = raw.trim();
    if (!piece) continue;
    const m = /^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$/.exec(piece);
    if (!m) {
      throw new Error(
        `invalid span "${piece}" — expected START-END in seconds, e.g. 0-3.88 ` +
        "(negative times are not a position in a clip)",
      );
    }
    const start_s = Number(m[1]);
    const end_s = Number(m[2]);
    if (!(start_s < end_s)) {
      throw new Error(`span "${piece}" is reversed: start must come before end`);
    }
    spans.push({ start_s, end_s });
  }
  if (spans.length === 0) throw new Error("no spans given");
  for (let i = 1; i < spans.length; i += 1) {
    if (spans[i].start_s < spans[i - 1].end_s) {
      throw new Error(
        `spans overlap at ${spans[i].start_s}s — they must be in order and disjoint, ` +
        "because one moment of audio has one speaker",
      );
    }
  }
  return spans;
}

/** Mean level of a region, used to match the converted piece to the bed it replaces. */
export async function measureRms(file, start_s, end_s) {
  try {
    const { stderr } = await execFileAsync("ffmpeg", [
      "-v", "error", "-ss", String(start_s), "-to", String(end_s), "-i", file,
      "-af", "astats=metadata=1", "-f", "null", "-",
    ], { maxBuffer: 8 << 20 });
    const m = /RMS level dB:\s*(-?\d+(?:\.\d+)?)/.exec(stderr ?? "");
    return m ? Number(m[1]) : null;
  } catch {
    return null;
  }
}

/**
 * Rebuild the timeline: original audio everywhere, converted audio inside each span,
 * crossfaded at every seam so the swap does not click.
 *
 * The bed is cut into the gaps BETWEEN spans rather than mixed underneath them — mixing
 * would leave both voices audible at once.
 */
export async function spliceSpans({ bedPath, bedDuration, pieces, outPath, pad = SEAM_PAD_S }) {
  const inputs = ["-i", bedPath];
  for (const piece of pieces) inputs.push("-i", piece.file);

  const parts = [];
  const labels = [];
  let cursor = 0;
  let n = 0;

  const bedSegment = (from, to, fadeIn, fadeOut) => {
    if (to - from <= 0.001) return;
    const label = `b${n}`;
    const filters = [`atrim=${from.toFixed(3)}:${to.toFixed(3)}`, "asetpts=PTS-STARTPTS"];
    if (fadeIn) filters.push(`afade=t=in:d=${pad}`);
    if (fadeOut) filters.push(`afade=t=out:st=${Math.max(to - from - pad, 0).toFixed(3)}:d=${pad}`);
    filters.push(`adelay=${Math.round(from * 1000)}|${Math.round(from * 1000)}`);
    parts.push(`[0:a]${filters.join(",")}[${label}]`);
    labels.push(label);
    n += 1;
  };

  pieces.forEach((piece, i) => {
    bedSegment(cursor, piece.start_s, i > 0, true);
    const head = Math.max(piece.start_s - pad, 0);
    const filters = [
      "asetpts=PTS-STARTPTS",
      ...(piece.gain_db ? [`volume=${piece.gain_db.toFixed(2)}dB`] : []),
      `afade=t=in:d=${pad}`,
      `afade=t=out:st=${Math.max(piece.end_s - head, 0).toFixed(3)}:d=${pad}`,
      `adelay=${Math.round(head * 1000)}|${Math.round(head * 1000)}`,
    ];
    const label = `c${i}`;
    parts.push(`[${i + 1}:a]${filters.join(",")}[${label}]`);
    labels.push(label);
    cursor = piece.end_s;
  });
  bedSegment(cursor, bedDuration, true, false);

  parts.push(
    `${labels.map((l) => `[${l}]`).join("")}amix=inputs=${labels.length}:normalize=0:` +
    `duration=longest,atrim=0:${bedDuration.toFixed(3)},asetpts=PTS-STARTPTS[out]`,
  );

  await mkdir(path.dirname(outPath), { recursive: true });
  await execFileAsync("ffmpeg", [
    "-y", "-v", "error", ...inputs,
    "-filter_complex", parts.join(";"),
    "-map", "[out]", "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-q:a", "2", outPath,
  ], { maxBuffer: 8 << 20 });
  return outPath;
}

export async function extractAudio(clipPath, outPath, range = null) {
  await mkdir(path.dirname(outPath), { recursive: true });
  const cut = range
    ? ["-ss", String(range.start_s), "-to", String(range.end_s)]
    : [];
  await execFileAsync("ffmpeg", [
    "-y", "-v", "error", ...cut, "-i", clipPath,
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

  log(`  ${spansWarning}`);

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

/**
 * Convert only the named spans, leaving every other voice on the track alone.
 *
 * This is the correct default whenever a clip has more than one speaker. Measured on a
 * real three-hander: converting the whole track turned the second speaker into the target
 * voice too, which is not a rough result, it is the wrong one.
 *
 * The drift gate applies to the SPLICED file, because that is what gets muxed against the
 * picture. A per-piece check would pass while the assembled timeline had shifted.
 */
export async function convertSpans({
  inputPath,
  outPath,
  spans,
  voiceEnv,
  env = process.env,
  model = DEFAULT_MODEL,
  fetchImpl = globalThis.fetch,
  extract = extractAudio,
  durationOf = probeDuration,
  splice = spliceSpans,
  rmsOf = measureRms,
  log = console.log,
}) {
  if (!Array.isArray(spans) || spans.length === 0) {
    throw new Error("convertSpans needs at least one span; use convert() for a whole track");
  }
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

  const stem = path.basename(outPath, ".mp3");
  const workDir = path.join(path.dirname(outPath), ".work");
  const bed = await extract(inputPath, path.join(workDir, `${stem}.bed.wav`));

  const bedDuration = await durationOf(bed);
  if (bedDuration === null) {
    throw new Error(
      `cannot measure the source duration of ${path.basename(bed)} — ` +
      "refusing to convert, because duration preservation is the property this step depends on",
    );
  }
  for (const span of spans) {
    if (span.end_s > bedDuration + 0.001) {
      throw new Error(
        `span ${span.start_s}-${span.end_s}s runs past the clip (${bedDuration.toFixed(3)}s)`,
      );
    }
  }

  const { readFile } = await import("node:fs/promises");
  const pieces = [];

  for (const [i, span] of spans.entries()) {
    // A little audio either side of the turn gives the crossfade something to land on.
    const range = {
      start_s: Math.max(span.start_s - SEAM_PAD_S, 0),
      end_s: Math.min(span.end_s + SEAM_PAD_S, bedDuration),
    };
    const src = await extract(inputPath, path.join(workDir, `${stem}.span${i}.wav`), range);

    const form = new FormData();
    form.append("model_id", model);
    form.append("audio", new Blob([await readFile(src)]), path.basename(src));

    const response = await fetchImpl(`${API_BASE}/${voiceId}`, {
      method: "POST",
      headers: { "xi-api-key": apiKey },
      body: form,
    });
    if (!response.ok) {
      const detail = (await response.text?.()) ?? "";
      throw new Error(`ElevenLabs speech-to-speech returned ${response.status}. ${detail}`.trim());
    }

    const file = path.join(workDir, `${stem}.span${i}.mp3`);
    await mkdir(workDir, { recursive: true });
    await writeFile(file, Buffer.from(await response.arrayBuffer()));

    // Match the level of what it replaces, or the swap reads as a jump in the mix.
    const before = await rmsOf(bed, span.start_s, span.end_s);
    const after = await rmsOf(file, SEAM_PAD_S, SEAM_PAD_S + (span.end_s - span.start_s));
    const gain_db = before !== null && after !== null ? Number((before - after).toFixed(2)) : 0;

    pieces.push({ file, start_s: span.start_s, end_s: span.end_s, gain_db });
    log(`  span ${span.start_s.toFixed(2)}-${span.end_s.toFixed(2)}s converted` +
        (gain_db ? ` (level matched ${gain_db >= 0 ? "+" : ""}${gain_db} dB)` : ""));
  }

  const staging = path.join(workDir, `${stem}.candidate.mp3`);
  await splice({ bedPath: bed, bedDuration, pieces, outPath: staging });

  const outDuration = await durationOf(staging);
  if (outDuration === null) {
    throw new Error(
      "cannot measure the converted duration — refusing to write an unverified conversion",
    );
  }
  const drift = Number((outDuration - bedDuration).toFixed(3));
  if (Math.abs(drift) > MAX_DRIFT_S) {
    await unlink(staging).catch(() => {});
    throw new Error(
      `${driftMessage}: ${bedDuration.toFixed(3)}s -> ${outDuration.toFixed(3)}s ` +
      `(drift ${drift.toFixed(3)}s, tolerance ${MAX_DRIFT_S}s). Nothing was written. ` +
      "Do not stretch the audio to fit; reopen the mixed-source decision instead.",
    );
  }

  await mkdir(path.dirname(outPath), { recursive: true });
  await writeFile(outPath, await readFile(staging));
  await unlink(staging).catch(() => {});
  log(`  ${path.basename(outPath)}: ${bedDuration.toFixed(3)}s -> ${outDuration.toFixed(3)}s ` +
      `(drift ${drift >= 0 ? "+" : ""}${drift.toFixed(3)}s, ${pieces.length} span(s) converted, ` +
      "every other voice left as it was)");

  return {
    ok: true,
    drift_s: drift,
    source_s: bedDuration,
    out_s: outDuration,
    out: outPath,
    spans_converted: pieces.length,
  };
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
      "usage: node tools/voice_changer.mjs <clip> --voice-env ELEVENLABS_VOICE_C2 --out vo/scene-02-c2.mp3\n" +
      "       [--spans 0-3.88,5.2-7]  convert only these turns; required when the clip has a second speaker",
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

  const spansArg = flag("spans");
  const common = {
    inputPath: clip,
    outPath: flag("out", "vo/converted.mp3"),
    voiceEnv: flag("voice-env"),
    model: flag("model", DEFAULT_MODEL),
    env: { ...envFile, ...process.env },
  };
  const result = spansArg
    ? await convertSpans({ ...common, spans: parseSpans(spansArg) })
    : await convert(common);
  return result.degraded ? 0 : 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv).then((code) => process.exit(code)).catch((err) => {
    console.error(`voice_changer: ${err.message}`);
    process.exit(1);
  });
}
