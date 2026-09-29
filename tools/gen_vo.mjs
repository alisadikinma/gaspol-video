/**
 * Generate narration audio from work/audio-plan.json with ElevenLabs.
 *
 *   node tools/gen_vo.mjs <project-dir> [--plan PATH] [--dry-run] [--force]
 *
 * Two things make this more than a text-to-speech wrapper:
 *
 *   1. Consecutive requests are stitched with previous_request_ids, so delivery carries
 *      across scene boundaries. Without it every scene is spoken cold and the video
 *      sounds like separate recordings of the same person.
 *   2. The response's word timings are written into vo-manifest.json, which is what sets
 *      each clip's duration in Phase 5 and what the subtitle pass reads in Phase 6. The
 *      measurement is the point; the mp3 is almost a side effect.
 *
 * A layer whose text, voice, model and settings are unchanged is reused from the previous
 * vo-manifest.json, and each speech chunk of a pause-tagged layer is cached in .tmp/ by
 * fingerprint, so nothing already generated is requested (and billed) twice. --force skips both.
 * The fingerprint carries a hash of the voice id; the id itself is never written anywhere.
 *
 * No dependencies: global fetch, node:fs, and ffprobe when it happens to be installed.
 * A missing key degrades loudly and returns; it never throws and never picks a voice.
 */

import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const API_BASE = "https://api.elevenlabs.io/v1/text-to-speech";
const DEFAULT_MODEL = "eleven_multilingual_v2"; // never v3 — no PVC fine-tune, identity drifts
const DEFAULT_SETTINGS = { stability: 0.55, similarity_boost: 0.8, style: 0.3, speed: 0.95 };
const PROSODY_CONTEXT = 3;   // how many prior request ids to carry
const MAX_RETRIES = 4;
const PCM_RATE = 44100;      // pause chunks are stitched as mono s16le at this rate

export const EM_DASH_MESSAGE =
  "em dash in spoken text — the audio engine mistranslates it. Use ',' or '. ' instead";

// Same grammar as PAUSE_TAG_RE in tools/gen_subs.py — tests/fixtures/pause-tags.json holds both to it.
export const PAUSE_TAG_RE = /\[\s*(?:pause|jeda)\s*:\s*(\d+(?:\.\d+)?)\s*(?:s|detik)?\s*\]/gi;
export const PAUSE_MIN_S = 0.2;
export const PAUSE_MAX_S = 5.0;

/** Script text as a viewer meets it: tags removed, the spaces they leave collapsed. */
export function stripPauseTags(text) {
  return text.replace(PAUSE_TAG_RE, " ").replace(/\s+/g, " ").trim();
}

/**
 * Split a layer's text into [{type:"speech", text}, {type:"pause", seconds}] in order.
 * Empty speech between tags is dropped; two adjacent pauses are summed.
 */
export function splitPauses(id, text) {
  const segments = [];
  const push = (segment) => {
    const last = segments[segments.length - 1];
    if (segment.type === "pause" && last?.type === "pause") {
      last.seconds = Number((last.seconds + segment.seconds).toFixed(3));
    } else {
      segments.push(segment);
    }
  };
  const speech = (chunk) => {
    const trimmed = chunk.replace(/\s+/g, " ").trim();
    if (!trimmed) return;
    // A tag the grammar did not consume is a typo, not speech: say it out loud in the mp3 and
    // nobody notices until the client does.
    const stray = trimmed.match(/\[\s*(?:pause|jeda)[^\]]*\]?/i);
    if (stray) throw new Error(`${id}: malformed pause tag "${stray[0]}"`);
    push({ type: "speech", text: trimmed });
  };

  let cursor = 0;
  for (const match of text.matchAll(PAUSE_TAG_RE)) {
    speech(text.slice(cursor, match.index));
    const seconds = Number.parseFloat(match[1]);
    if (seconds < PAUSE_MIN_S || seconds > PAUSE_MAX_S) {
      throw new Error(`${id}: pause ${seconds}s outside ${PAUSE_MIN_S}-${PAUSE_MAX_S}s`);
    }
    push({ type: "pause", seconds });
    cursor = match.index + match[0].length;
  }
  speech(text.slice(cursor));
  return segments;
}

/** Layers this tool is responsible for: narration and dialogue generated as speech. */
export function buildItems(plan, cast) {
  const items = [];
  for (const scene of plan.scenes ?? []) {
    for (const layer of scene.layers ?? []) {
      if (layer.from !== "tts") continue;
      if (!["narration", "dialogue"].includes(layer.kind)) continue;
      const text = (layer.text ?? "").trim();
      if (!text) continue;
      const profile = cast?.[layer.cast] ?? {};
      items.push({
        id: path.basename(layer.out ?? `scene-${String(scene.scene).padStart(2, "0")}-${layer.kind}`,
                          ".mp3"),
        scene: scene.scene,
        cast: layer.cast,
        kind: layer.kind,
        text,
        out: layer.out ?? `vo/scene-${String(scene.scene).padStart(2, "0")}-narr.mp3`,
        voice_env: profile.voice_env,
        model: profile.model ?? DEFAULT_MODEL,
        settings: { ...DEFAULT_SETTINGS, ...(profile.settings ?? {}) },
      });
    }
  }
  return items;
}

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

/** Identity of what a request would produce. The voice id enters only as a hash. */
function fingerprint(item, voiceId, text = item.text) {
  return sha256(JSON.stringify({
    text, voice_env: item.voice_env, voice_id_sha: sha256(voiceId ?? ""),
    model: item.model, settings: item.settings,
  }));
}

async function readPreviousItems(voDir) {
  try {
    const previous = JSON.parse(await readFile(path.join(voDir, "vo-manifest.json"), "utf8"));
    return new Map((previous.items ?? []).map((entry) => [entry.id, entry]));
  } catch {
    return new Map(); // no manifest yet, or an unreadable one: generate everything
  }
}

async function exists(file) {
  try { await stat(file); return true; } catch { return false; }
}

function assertNoEmDash(items) {
  for (const item of items) {
    if (stripPauseTags(item.text).includes("—")) {
      throw new Error(`${item.id}: ${EM_DASH_MESSAGE}`);
    }
  }
}

function wordsFromAlignment(alignment) {
  if (!alignment?.characters?.length) return [];
  const chars = alignment.characters;
  const starts = alignment.character_start_times_seconds ?? [];
  const ends = alignment.character_end_times_seconds ?? [];
  const words = [];
  let current = null;
  for (let i = 0; i < chars.length; i += 1) {
    const ch = chars[i];
    if (/\s/.test(ch)) {
      if (current) { words.push(current); current = null; }
      continue;
    }
    if (!current) {
      current = { text: "", start_ms: Math.round((starts[i] ?? 0) * 1000), end_ms: 0 };
    }
    current.text += ch;
    current.end_ms = Math.round((ends[i] ?? starts[i] ?? 0) * 1000);
  }
  if (current) words.push(current);
  return words;
}

async function probeDuration(file) {
  try {
    const { stdout } = await execFileAsync("ffprobe", [
      "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file,
    ]);
    const value = Number.parseFloat(stdout.trim());
    return Number.isFinite(value) ? Number(value.toFixed(3)) : null;
  } catch {
    return null; // ffprobe absent: the manifest simply carries no measured duration
  }
}

const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function requestOne({ item, voiceId, apiKey, fetchImpl, previousIds, sleep, log }) {
  const body = {
    text: item.text,
    model_id: item.model,
    voice_settings: item.settings,
    previous_request_ids: previousIds.slice(-PROSODY_CONTEXT),
  };

  let attempt = 0;
  for (;;) {
    attempt += 1;
    const response = await fetchImpl(
      `${API_BASE}/${voiceId}/with-timestamps`,
      {
        method: "POST",
        headers: { "xi-api-key": apiKey, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );

    if (response.ok) {
      const payload = await response.json();
      const requestId = response.headers?.get?.("request-id") ?? null;
      return { payload, requestId };
    }

    const status = response.status;
    // A credential or request error will not fix itself; only rate limiting is worth retrying.
    if (status !== 429 && status < 500) {
      const detail = await response.text?.() ?? "";
      throw new Error(`${item.id}: ElevenLabs returned ${status}. ${detail}`.trim());
    }
    if (attempt >= MAX_RETRIES) {
      throw new Error(`${item.id}: ElevenLabs returned ${status} after ${attempt} attempts`);
    }
    const wait = 500 * 2 ** (attempt - 1);
    log(`  ${item.id}: HTTP ${status}, retrying in ${wait}ms`);
    await sleep(wait);
  }
}

/**
 * A layer with pause tags: one request per speech chunk (chained through previousIds so delivery
 * stays warm across the pause), decoded to PCM, joined with zero samples, encoded once. Silence is
 * a sample count, so every offset is exact; nothing is probed off an mp3 with encoder padding.
 *
 * Each chunk is cached flat in <project>/.tmp as vocache-<fingerprint16>.mp3 + .json (the
 * response's alignment and request id). A chunk found there costs no request and does not feed
 * previousIds, whose old ids may have expired. The cache is disposable: deleting it only costs
 * re-requests. The mp3 is written before the json, so a json always has its audio beside it.
 */
async function synthesizeWithPauses({
  item, segments, voiceId, apiKey, fetchImpl, previousIds, sleep, log, execImpl, projectDir, outPath, force,
}) {
  const tmpDir = path.join(projectDir, ".tmp");
  await mkdir(tmpDir, { recursive: true });
  const kept = [];
  const buffers = [];
  const words = [];
  let samples = 0;
  let chunks = 0;
  let cached = 0;
  let pauses = 0;
  let silenceSeconds = 0;

  try {
    for (const segment of segments) {
      if (segment.type === "pause") {
        const count = Math.round(segment.seconds * PCM_RATE);
        buffers.push(Buffer.alloc(count * 2));
        samples += count;
        pauses += 1;
        silenceSeconds += segment.seconds;
        continue;
      }
      chunks += 1;
      const key = fingerprint(item, voiceId, segment.text).slice(0, 16);
      const mp3 = path.join(tmpDir, `vocache-${key}.mp3`);
      const meta = path.join(tmpDir, `vocache-${key}.json`);
      const pcm = path.join(tmpDir, `vocache-${key}.pcm`);

      let alignment;
      const hit = !force && await exists(mp3) && await readJson(meta).catch(() => null);
      if (hit) {
        alignment = hit.alignment;
        cached += 1;
      } else {
        const { payload, requestId } = await requestOne({
          item: { ...item, text: segment.text }, voiceId, apiKey, fetchImpl, previousIds, sleep, log,
        });
        if (requestId) previousIds.push(requestId);
        alignment = payload.alignment;
        await writeFile(mp3, Buffer.from(payload.audio_base64, "base64"));
        await writeFile(meta, `${JSON.stringify({ alignment, request_id: requestId })}\n`);
      }

      kept.push(pcm);
      await runFfmpeg(execImpl, item.id, ["-v", "error", "-y", "-i", mp3,
        "-f", "s16le", "-ac", "1", "-ar", String(PCM_RATE), pcm]);
      const data = await readFile(pcm);

      const startMs = Math.round(samples / (PCM_RATE / 1000));
      for (const word of wordsFromAlignment(alignment)) {
        words.push({ ...word, start_ms: word.start_ms + startMs, end_ms: word.end_ms + startMs });
      }
      buffers.push(data);
      samples += data.length / 2;
    }

    const all = path.join(tmpDir, `${item.id}-all.pcm`);
    kept.push(all);
    await writeFile(all, Buffer.concat(buffers));
    await runFfmpeg(execImpl, item.id, ["-v", "error", "-y", "-f", "s16le", "-ar", String(PCM_RATE),
      "-ac", "1", "-i", all, "-c:a", "libmp3lame", "-b:a", "128k", outPath]);
  } catch (err) {
    if (kept.length) err.message += ` (chunk files kept in ${tmpDir})`;
    throw err;
  }
  await Promise.all(kept.map((file) => rm(file, { force: true })));
  log(`  ${item.id}: ${chunks} chunks (${cached} cached), ${pauses} pauses ` +
    `(${silenceSeconds.toFixed(2)}s silence) -> ${item.out}`);
  return { words };
}

async function runFfmpeg(execImpl, id, args) {
  try {
    await execImpl("ffmpeg", args);
  } catch (err) {
    if (err.code === "ENOENT") {
      throw new Error(`${id}: pause tags need ffmpeg on PATH — install it, or remove the tags`);
    }
    const detail = (err.stderr ?? err.message ?? "").toString().trim();
    throw new Error(`${id}: ffmpeg failed on a pause chunk. ${detail}`.trim());
  }
}

export async function synthesize({
  plan, cast, projectDir,
  env = process.env,
  fetchImpl = globalThis.fetch,
  log = console.log,
  sleep = defaultSleep,
  dryRun = false,
  force = false,
  execImpl = execFileAsync,
}) {
  const items = buildItems(plan, cast);
  assertNoEmDash(items);
  // Validate every tag up front: a typo must stop the run before the first paid request.
  for (const item of items) {
    item.segments = splitPauses(item.id, item.text);
    // Untagged text is measured as written; only a tagged layer is measured without its tags.
    item.plain = item.segments.some((s) => s.type === "pause") ? stripPauseTags(item.text) : item.text;
    if (item.segments.some((s) => s.type === "pause") && !item.segments.some((s) => s.type === "speech")) {
      throw new Error(`${item.id}: layer has pauses but no speech`);
    }
  }

  const apiKey = env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    const reason =
      "ELEVENLABS_API_KEY not set — no narration was generated. Set it in this plugin's .env " +
      "(see .env.example), or generate the mp3s elsewhere and drop them in vo/. " +
      "Clip durations fall back to the word-count estimate for this run.";
    log(reason);
    return { degraded: true, reason, items: [] };
  }

  for (const item of items) {
    if (!item.voice_env) {
      throw new Error(`${item.id}: cast ${item.cast} has no VOICE: block in cast-profile.md`);
    }
    if (!env[item.voice_env]) {
      throw new Error(
        `${item.id}: voice env ${item.voice_env} not set. ` +
        "Add it to .env; this tool never substitutes another voice.",
      );
    }
  }

  const voDir = path.join(projectDir, "vo");
  await mkdir(voDir, { recursive: true });

  const previousIds = [];
  const manifestItems = [];
  const previous = force ? new Map() : await readPreviousItems(voDir);

  for (const item of items) {
    const fp = fingerprint(item, env[item.voice_env]);
    const old = previous.get(item.id);
    const reusable = old?.fingerprint === fp && old.file === item.out &&
      await exists(path.join(projectDir, item.out));
    if (dryRun) {
      log(reusable
        ? `  would reuse ${item.id} (unchanged)`
        : `  would generate ${item.id} (${item.plain.length} chars) with ${item.voice_env}`);
      continue;
    }
    if (reusable) {
      log(`  ${item.id}: reused (unchanged)`);
      manifestItems.push(old);
      continue;
    }
    const outPath = path.join(projectDir, item.out);
    await mkdir(path.dirname(outPath), { recursive: true });

    let words;
    if (item.segments.some((segment) => segment.type === "pause")) {
      ({ words } = await synthesizeWithPauses({
        item, segments: item.segments, voiceId: env[item.voice_env], apiKey, fetchImpl,
        previousIds, sleep, log, execImpl, projectDir, outPath, force,
      }));
    } else {
      const { payload, requestId } = await requestOne({
        item, voiceId: env[item.voice_env], apiKey, fetchImpl, previousIds, sleep, log,
      });
      if (requestId) previousIds.push(requestId);
      await writeFile(outPath, Buffer.from(payload.audio_base64, "base64"));
      words = wordsFromAlignment(payload.alignment);
      log(`  ${item.id}: ${item.plain.length} chars -> ${item.out}`);
    }

    manifestItems.push({
      id: item.id,
      file: item.out,
      scene: item.scene,
      cast: item.cast,
      kind: item.kind,
      voice_env: item.voice_env,      // the NAME, never the id
      fingerprint: fp,
      chars: item.plain.length,
      duration_s: await probeDuration(outPath),
      words,
    });
  }

  const manifest = {
    generated_at: new Date().toISOString(),
    model: items[0]?.model ?? DEFAULT_MODEL,
    settings: items[0]?.settings ?? DEFAULT_SETTINGS,
    items: manifestItems,
  };
  if (!dryRun) {
    await writeFile(path.join(voDir, "vo-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  }

  return { degraded: false, items: manifestItems, manifest };
}

async function readJson(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

/**
 * cast-profile.md is markdown; pull the VOICE blocks out of it.
 *
 * Two things here are deliberate, both from production failures:
 *
 *  - The trailing colon on the `VOICE` heading is OPTIONAL. A profile written
 *    `### VOICE` used to parse to {} — every character silently lost, and the
 *    first sign of it was `cast c1 has no VOICE: block` at synthesis time.
 *  - The slot is read from the BLOCK HEADING, not from anywhere in the block.
 *    `## Character 5: Kawan sopir` whose body happened to mention
 *    `cast-c3-costume.png` used to bind character 5's voice to slot c3, which
 *    is not an error at all — it is the wrong voice, delivered confidently.
 */
export function parseCastProfile(markdown) {
  const cast = {};
  const slotRe = /cast-(c\d+)/i;
  const blocks = markdown.split(/^##\s+/m);
  for (const block of blocks) {
    const heading = block.split("\n", 1)[0];
    const slot = (heading.match(slotRe) ?? block.match(slotRe))?.[1]?.toLowerCase();
    const voice = block.match(/(?:^|\n)#{0,6}[ \t]*VOICE:?[ \t]*\n([\s\S]*?)(?:\n\s*\n|$)/);
    if (!slot || !voice) continue;
    const entry = { settings: {} };
    for (const line of voice[1].split("\n")) {
      const [key, ...rest] = line.trim().split(":");
      const value = rest.join(":").split("#")[0].trim();
      if (!value) continue;
      if (key === "settings") {
        for (const pair of value.split(",")) {
          const [k, v] = pair.split("=").map((s) => s.trim());
          if (k) entry.settings[k] = Number.parseFloat(v);
        }
      } else {
        entry[key] = value;
      }
    }
    cast[slot] = entry;
  }
  return cast;
}

async function main(argv) {
  const args = argv.slice(2);
  const projectDir = args.find((a) => !a.startsWith("--"));
  if (!projectDir) {
    console.error("usage: node tools/gen_vo.mjs <project-dir> [--plan PATH] [--dry-run] [--force]");
    return 2;
  }
  const planFlag = args.indexOf("--plan");
  const planPath = planFlag >= 0 ? args[planFlag + 1] : path.join(projectDir, "work", "audio-plan.json");

  let envFile = {};
  try {
    const text = await readFile(path.join(process.cwd(), ".env"), "utf8");
    for (const line of text.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const [k, ...v] = trimmed.split("=");
      const value = v.join("=").trim().replace(/^["']|["']$/g, "");
      if (value) envFile[k.trim()] = value;
    }
  } catch { /* no .env is fine; the environment may already carry the vars */ }

  const plan = await readJson(planPath);
  let cast = {};
  try {
    cast = parseCastProfile(await readFile(path.join(projectDir, "cast-profile.md"), "utf8"));
    if (Object.keys(cast).length === 0) {
      // Readable but zero entries is the dangerous case: it looks like success.
      console.error(
        "warning: cast-profile.md parsed to 0 voices. Each character needs a `## ...(cast-cN)...` " +
        "heading and a `VOICE` block under it. No voice is substituted; synthesis will stop.",
      );
    }
  } catch {
    console.error("warning: cast-profile.md not readable — falling back to default voice settings");
  }

  const result = await synthesize({
    plan, cast, projectDir,
    env: { ...envFile, ...process.env },
    dryRun: args.includes("--dry-run"),
    force: args.includes("--force"),
  });
  return result.degraded ? 0 : 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv).then((code) => process.exit(code)).catch((err) => {
    console.error(`gen_vo: ${err.message}`);
    process.exit(1);
  });
}
