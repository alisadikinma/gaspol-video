import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { execFileSync, spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import path from "node:path";
import { parseEnv, loadEnv, requireKeys } from "../../tools/vidkit/js/env.mjs";
import { tts, sfx, sttWords, assertSpeakable } from "../../tools/vidkit/js/eleven.mjs";
import { planFetch, run } from "../../tools/vidkit/js/cast_voice.mjs";
import { probeDuration } from "../../tools/vidkit/js/ff.mjs";

const okBytes = (b = "AUDIO") => async () => ({ ok: true, arrayBuffer: async () => Buffer.from(b), json: async () => ({}) });

test("parseEnv strips quotes, skips comments, tolerates a missing file", () => {
  const f = path.join(mkdtempSync(path.join(tmpdir(), "vk-")), ".env");
  writeFileSync(f, '# c\nA_KEY="abc"\nB=two words\nnot a line\n');
  assert.deepEqual(parseEnv(f), { A_KEY: "abc", B: "two words" });
  assert.deepEqual(parseEnv(f + ".nope"), {});
});

test("loadEnv: later files win; requireKeys names the missing, never values", () => {
  const d = mkdtempSync(path.join(tmpdir(), "vk-"));
  writeFileSync(path.join(d, "a"), "X=1\nY=a\n");
  writeFileSync(path.join(d, "b"), "Y=b\n");
  const env = loadEnv(path.join(d, "a"), path.join(d, "b"));
  assert.equal(env.X, "1");
  assert.equal(env.Y, "b");
  assert.throws(() => requireKeys({ X: "secret" }, "X", "MISSING_ONE"), /MISSING_ONE/);
  assert.throws(() => requireKeys({ X: "secret" }, "X", "M"), (e) => !e.message.includes("secret"));
});

test("assertSpeakable rejects em dash and empty", () => {
  assert.throws(() => assertSpeakable("a — b"), /em dash/);
  assert.throws(() => assertSpeakable("  "), /empty/);
  assertSpeakable("ok, fine.");
});

test("tts sends settings + seed and returns bytes", async () => {
  let sent;
  const buf = await tts({ text: "Halo.", voiceId: "V1", apiKey: "k", settings: { stability: 0.1 }, seed: 7,
    fetchImpl: async (url, opts) => { sent = { url, opts }; return okBytes("MP3")(); } });
  assert.equal(buf.toString(), "MP3");
  assert.match(sent.url, /text-to-speech\/V1/);
  const body = JSON.parse(sent.opts.body);
  assert.equal(body.seed, 7);
  assert.equal(body.voice_settings.stability, 0.1);
  assert.equal(sent.opts.headers["xi-api-key"], "k");
});

test("tts surfaces HTTP errors without the key", async () => {
  await assert.rejects(
    tts({ text: "x", voiceId: "V", apiKey: "SECRETKEY", fetchImpl: async () => ({ ok: false, status: 401, text: async () => "no" }) }),
    (e) => /401/.test(e.message) && !e.message.includes("SECRETKEY"));
});

test("sfx and stt hit the right endpoints; stt drops spacing tokens", async () => {
  const urls = [];
  await sfx({ text: "boom", seconds: 1, apiKey: "k", fetchImpl: async (u) => { urls.push(u); return okBytes()(); } });
  const j = await sttWords({ wavBytes: Buffer.from("x"), apiKey: "k", fetchImpl: async (u) => {
    urls.push(u);
    return { ok: true, json: async () => ({ text: "hi", words: [{ type: "word", text: "hi", start: 0, end: 1 }, { type: "spacing", text: " " }] }) };
  } });
  assert.match(urls[0], /sound-generation/);
  assert.match(urls[1], /speech-to-text/);
  assert.equal(j.words.length, 1);
});

test("planFetch appends voice_settings and seed to the multipart body", async () => {
  const body = new FormData();
  let seen;
  await planFetch({ settings: { stability: 0.2 }, seed: 5 }, async (u, o) => { seen = o.body; return {}; })("u", { body });
  assert.equal(seen.get("seed"), "5");
  assert.equal(JSON.parse(seen.get("voice_settings")).stability, 0.2);
});

test("run converts only the wanted scenes with each cast member's voice env", async () => {
  const calls = [];
  const plan = { cast: { a: { voice_env: "VA" }, b: { voice_env: "VB" } },
    scenes: { S1: { cast: "a", spans: "0.1-1.0" }, S2: { cast: "b", spans: "0.1-1.0" } } };
  await run(plan, { env: {}, only: ["S2"], convert: async (o) => { calls.push(o); return { ok: true }; } });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].voiceEnv, "VB");
  assert.equal(calls[0].inputPath, "clips/S2.mp4");
  await assert.rejects(run({ cast: {}, scenes: { S9: { cast: "zz", spans: "0-1" } } }, { env: {}, convert: async () => ({}) }), /unknown cast/);
});

const hasFfmpeg = spawnSync("ffmpeg", ["-version"]).status === 0 && spawnSync("ffprobe", ["-version"]).status === 0;

test("probeDuration measures a real clip", { skip: !hasFfmpeg }, async () => {
  const f = path.join(mkdtempSync(path.join(tmpdir(), "vk-")), "a.wav");
  execFileSync("ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "anullsrc", "-t", "1", f]);
  const d = await probeDuration(f);
  assert.ok(Math.abs(d - 1) < 0.1, `got ${d}`);
});

test("probeDuration gives null for a non-media file", async () => {
  const f = path.join(mkdtempSync(path.join(tmpdir(), "vk-")), "note.txt");
  writeFileSync(f, "not media");
  assert.equal(await probeDuration(f), null);
});

test("probeDuration gives null when the binary is not on PATH", async () => {
  const saved = process.env.PATH;
  process.env.PATH = mkdtempSync(path.join(tmpdir(), "vk-"));
  try {
    assert.equal(await probeDuration("whatever.wav"), null);
  } finally {
    process.env.PATH = saved;
  }
});
