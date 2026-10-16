// ElevenLabs helpers beyond what gen_vo.mjs / voice_changer.mjs cover: one-off TTS with explicit
// settings + seed, word timings (Scribe STT), and sound-effect generation.
//
//   node tools/vidkit/js/eleven.mjs tts  OUT.mp3 "text" --voice-env ELEVENLABS_VOICE_C1 [--seed N] [--settings '{"stability":0.1}']
//   node tools/vidkit/js/eleven.mjs stt  clip.mp4 [more.mp4 ...] [--out-dir DIR] [--lang ind]
//   node tools/vidkit/js/eleven.mjs sfx  OUT.mp3 "prompt" --seconds 2.5
// Env: ELEVENLABS_API_KEY (+ the voice env) from --env FILE (repeatable) or the process.
//
// Lessons baked in:
//  * Spoken text may not contain an em dash (the voice reads it as a long, odd pause).
//  * Low stability is deterministic PER SEED: the same text + seed reproduces the same clipped
//    tail. Change the seed to get another take instead of re-running.
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import path from "node:path";
import { loadEnv, requireKeys } from "./env.mjs";

const API = "https://api.elevenlabs.io/v1";
export const DEFAULT_SEED = 2026091801;

export function assertSpeakable(text) {
  if (!text || !text.trim()) throw new Error("empty text");
  if (text.includes("—")) throw new Error("em dash in spoken text; use a comma or a full stop");
}

async function failIf(r, what) {
  if (!r.ok) throw new Error(`${what} failed: HTTP ${r.status} ${(await r.text()).slice(0, 300)}`);
}

/** Text to speech. Returns the mp3 bytes. */
export async function tts({ text, voiceId, apiKey, settings = {}, seed = DEFAULT_SEED,
                            model = "eleven_multilingual_v2", format = "mp3_44100_128", fetchImpl = fetch }) {
  assertSpeakable(text);
  const r = await fetchImpl(`${API}/text-to-speech/${voiceId}?output_format=${format}`, {
    method: "POST",
    headers: { "xi-api-key": apiKey, "content-type": "application/json" },
    body: JSON.stringify({ text, model_id: model, voice_settings: settings, seed }),
  });
  await failIf(r, "tts");
  return Buffer.from(await r.arrayBuffer());
}

/** Scribe speech to text with word timings. Returns {text, words:[{start,end,text,type}]}. */
export async function sttWords({ wavBytes, name = "audio.wav", apiKey, lang = "ind", fetchImpl = fetch }) {
  const form = new FormData();
  form.append("model_id", "scribe_v1");
  form.append("language_code", lang);
  form.append("timestamps_granularity", "word");
  form.append("tag_audio_events", "true");
  form.append("file", new Blob([wavBytes]), name);
  const r = await fetchImpl(`${API}/speech-to-text`, { method: "POST", headers: { "xi-api-key": apiKey }, body: form });
  await failIf(r, "stt");
  const j = await r.json();
  return { ...j, words: (j.words || []).filter((w) => w.type !== "spacing") };
}

/** Sound effect from a text prompt. Returns the mp3 bytes. */
export async function sfx({ text, seconds, apiKey, influence = 0.6, fetchImpl = fetch }) {
  const r = await fetchImpl(`${API}/sound-generation`, {
    method: "POST",
    headers: { "xi-api-key": apiKey, "content-type": "application/json" },
    body: JSON.stringify({ text, duration_seconds: seconds, prompt_influence: influence, model_id: "eleven_text_to_sound_v2" }),
  });
  await failIf(r, "sfx");
  return Buffer.from(await r.arrayBuffer());
}

function flags(argv) {
  const pos = [], opt = { env: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const k = a.slice(2), v = argv[++i];
      if (k === "env") opt.env.push(v); else opt[k] = v;
    } else pos.push(a);
  }
  return { pos, opt };
}

async function main() {
  const [cmd, ...rest] = process.argv.slice(2);
  const { pos, opt } = flags(rest);
  const env = loadEnv(...opt.env);
  if (cmd === "tts") {
    const [out, text] = pos;
    if (!out || !text || !opt["voice-env"]) throw new Error('usage: tts OUT.mp3 "text" --voice-env NAME');
    requireKeys(env, "ELEVENLABS_API_KEY", opt["voice-env"]);
    const buf = await tts({ text, voiceId: env[opt["voice-env"]], apiKey: env.ELEVENLABS_API_KEY,
      settings: opt.settings ? JSON.parse(opt.settings) : {}, seed: opt.seed ? Number(opt.seed) : DEFAULT_SEED });
    mkdirSync(path.dirname(out), { recursive: true });
    writeFileSync(out, buf);
    console.log("wrote", out);
  } else if (cmd === "stt") {
    requireKeys(env, "ELEVENLABS_API_KEY");
    const dir = opt["out-dir"] || "stt";
    mkdirSync(dir, { recursive: true });
    for (const clip of pos) {
      const stem = path.basename(clip, path.extname(clip));
      const wav = path.join(dir, `${stem}.wav`);
      execFileSync("ffmpeg", ["-y", "-v", "error", "-i", clip, "-vn", "-ac", "1", "-ar", "16000", wav]);
      const j = await sttWords({ wavBytes: readFileSync(wav), name: `${stem}.wav`, apiKey: env.ELEVENLABS_API_KEY, lang: opt.lang || "ind" });
      writeFileSync(path.join(dir, `${stem}.json`), JSON.stringify(j, null, 2));
      console.log(`\n${stem}: ${j.text}`);
      for (const w of j.words) console.log(`  ${w.start.toFixed(2)}-${w.end.toFixed(2)} ${w.type === "audio_event" ? `[${w.text}]` : w.text}`);
    }
  } else if (cmd === "sfx") {
    const [out, text] = pos;
    if (!out || !text || !opt.seconds) throw new Error('usage: sfx OUT.mp3 "prompt" --seconds N');
    requireKeys(env, "ELEVENLABS_API_KEY");
    const buf = await sfx({ text, seconds: Number(opt.seconds), apiKey: env.ELEVENLABS_API_KEY });
    mkdirSync(path.dirname(out), { recursive: true });
    writeFileSync(out, buf);
    console.log("wrote", out);
  } else {
    throw new Error("commands: tts | stt | sfx");
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((e) => { console.error(`FAIL: ${e.message}`); process.exit(1); });
}
