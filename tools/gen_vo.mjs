/**
 * Generate narration audio from work/audio-plan.json with ElevenLabs.
 *
 *   node tools/gen_vo.mjs <project-dir> [--plan PATH] [--dry-run]
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
 * No dependencies: global fetch, node:fs, and ffprobe when it happens to be installed.
 * A missing key degrades loudly and returns; it never throws and never picks a voice.
 */

import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const API_BASE = "https://api.elevenlabs.io/v1/text-to-speech";
const DEFAULT_MODEL = "eleven_multilingual_v2"; // never v3 — no PVC fine-tune, identity drifts
const DEFAULT_SETTINGS = { stability: 0.55, similarity_boost: 0.8, style: 0.3, speed: 0.95 };
const PROSODY_CONTEXT = 3;   // how many prior request ids to carry
const MAX_RETRIES = 4;

export const EM_DASH_MESSAGE =
  "em dash in spoken text — the audio engine mistranslates it. Use ',' or '. ' instead";

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

function assertNoEmDash(items) {
  for (const item of items) {
    if (item.text.includes("—")) {
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

export async function synthesize({
  plan, cast, projectDir,
  env = process.env,
  fetchImpl = globalThis.fetch,
  log = console.log,
  sleep = defaultSleep,
  dryRun = false,
}) {
  const items = buildItems(plan, cast);
  assertNoEmDash(items);

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

  for (const item of items) {
    if (dryRun) {
      log(`  would synthesize ${item.id} (${item.text.length} chars) with ${item.voice_env}`);
      continue;
    }
    const { payload, requestId } = await requestOne({
      item, voiceId: env[item.voice_env], apiKey, fetchImpl, previousIds, sleep, log,
    });
    if (requestId) previousIds.push(requestId);

    const outPath = path.join(projectDir, item.out);
    await mkdir(path.dirname(outPath), { recursive: true });
    await writeFile(outPath, Buffer.from(payload.audio_base64, "base64"));

    manifestItems.push({
      id: item.id,
      file: item.out,
      scene: item.scene,
      cast: item.cast,
      kind: item.kind,
      voice_env: item.voice_env,      // the NAME, never the id
      chars: item.text.length,
      duration_s: await probeDuration(outPath),
      words: wordsFromAlignment(payload.alignment),
    });
    log(`  ${item.id}: ${item.text.length} chars -> ${item.out}`);
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

/** cast-profile.md is markdown; pull the VOICE: blocks out of it. */
export function parseCastProfile(markdown) {
  const cast = {};
  const slotRe = /cast-(c\d+)/i;
  const blocks = markdown.split(/^##\s+/m);
  for (const block of blocks) {
    const slot = block.match(slotRe)?.[1]?.toLowerCase();
    const voice = block.match(/VOICE:\s*\n([\s\S]*?)(?:\n\s*\n|$)/);
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
    console.error("usage: node tools/gen_vo.mjs <project-dir> [--plan PATH] [--dry-run]");
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
  } catch {
    console.error("warning: cast-profile.md not readable — falling back to default voice settings");
  }

  const result = await synthesize({
    plan, cast, projectDir,
    env: { ...envFile, ...process.env },
    dryRun: args.includes("--dry-run"),
  });
  return result.degraded ? 0 : 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv).then((code) => process.exit(code)).catch((err) => {
    console.error(`gen_vo: ${err.message}`);
    process.exit(1);
  });
}
