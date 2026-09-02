import assert from "node:assert/strict";
import { mkdtemp, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { MAX_DRIFT_S, convert, driftMessage } from "../../tools/voice_changer.mjs";

function okFetch(calls) {
  return async (url, init) => {
    calls.push({ url, init });
    return {
      ok: true,
      status: 200,
      headers: new Map(),
      arrayBuffer: async () => Buffer.from("converted-audio").buffer,
    };
  };
}

async function withTmp(fn) {
  const dir = await mkdtemp(path.join(tmpdir(), "gv-vc-"));
  // The extracted wav has to exist: convert() reads it to build the upload, and a stub
  // that hands back a path to nothing would be testing a tool that never touches disk.
  await writeFile(path.join(dir, "in.wav"), Buffer.from("RIFF....fake wav"));
  try {
    return await fn(dir);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

const BASE = {
  env: { ELEVENLABS_API_KEY: "k", ELEVENLABS_VOICE_C2: "voice-c2" },
  voiceEnv: "ELEVENLABS_VOICE_C2",
  log: () => {},
};

test("duration is preserved within tolerance, and the output is written", async () => {
  await withTmp(async (dir) => {
    const calls = [];
    const out = path.join(dir, "vo", "scene-02-c2.mp3");
    const result = await convert({
      ...BASE,
      inputPath: path.join(dir, "in.wav"),
      outPath: out,
      fetchImpl: okFetch(calls),
      extract: async () => path.join(dir, "in.wav"),
      durationOf: async (p) => (p.endsWith(".mp3") ? 3.22 : 3.20),
    });
    assert.equal(result.ok, true);
    assert.ok(Math.abs(result.drift_s) <= MAX_DRIFT_S);
    assert.equal(calls.length, 1);
    assert.ok((await stat(out)).size > 0);
  });
});

test("drift beyond tolerance refuses to write and reports the number", async () => {
  await withTmp(async (dir) => {
    const out = path.join(dir, "vo", "scene-02-c2.mp3");
    await assert.rejects(
      () => convert({
        ...BASE,
        inputPath: path.join(dir, "in.wav"),
        outPath: out,
        fetchImpl: okFetch([]),
        extract: async () => path.join(dir, "in.wav"),
        durationOf: async (p) => (p.endsWith(".mp3") ? 3.55 : 3.20),
      }),
      (err) => err.message.includes("0.35") && err.message.includes(driftMessage),
    );
    await assert.rejects(() => stat(out), /ENOENT/);
  });
});

test("an unmeasurable duration is refused, not assumed fine", async () => {
  await withTmp(async (dir) => {
    await assert.rejects(
      () => convert({
        ...BASE,
        inputPath: path.join(dir, "in.wav"),
        outPath: path.join(dir, "vo", "x.mp3"),
        fetchImpl: okFetch([]),
        extract: async () => path.join(dir, "in.wav"),
        durationOf: async () => null,
      }),
      (err) => /cannot measure/i.test(err.message),
    );
  });
});

test("a missing API key degrades instead of throwing", async () => {
  await withTmp(async (dir) => {
    const result = await convert({
      ...BASE,
      env: {},
      inputPath: path.join(dir, "in.wav"),
      outPath: path.join(dir, "vo", "x.mp3"),
      fetchImpl: okFetch([]),
      extract: async () => path.join(dir, "in.wav"),
      durationOf: async () => 1,
    });
    assert.equal(result.degraded, true);
    assert.ok(result.reason.includes("ELEVENLABS_API_KEY"));
  });
});

test("a missing voice env names the variable and substitutes nothing", async () => {
  await withTmp(async (dir) => {
    await assert.rejects(
      () => convert({
        ...BASE,
        env: { ELEVENLABS_API_KEY: "k" },
        inputPath: path.join(dir, "in.wav"),
        outPath: path.join(dir, "vo", "x.mp3"),
        fetchImpl: okFetch([]),
        extract: async () => path.join(dir, "in.wav"),
        durationOf: async () => 1,
      }),
      (err) => err.message.includes("ELEVENLABS_VOICE_C2"),
    );
  });
});

test("HTTP 401 surfaces as a credential error", async () => {
  await withTmp(async (dir) => {
    const failing = async () => ({
      ok: false, status: 401, headers: new Map(), text: async () => "unauthorized",
    });
    await assert.rejects(
      () => convert({
        ...BASE,
        inputPath: path.join(dir, "in.wav"),
        outPath: path.join(dir, "vo", "x.mp3"),
        fetchImpl: failing,
        extract: async () => path.join(dir, "in.wav"),
        durationOf: async () => 1,
      }),
      (err) => /401/.test(err.message),
    );
  });
});

test("the request carries no text: speech-to-speech converts audio, it does not re-read a script",
  async () => {
    await withTmp(async (dir) => {
      const calls = [];
      await convert({
        ...BASE,
        inputPath: path.join(dir, "in.wav"),
        outPath: path.join(dir, "vo", "x.mp3"),
        fetchImpl: okFetch(calls),
        extract: async () => path.join(dir, "in.wav"),
        durationOf: async () => 2.0,
      });
      const body = calls[0].init.body;
      assert.ok(!(typeof body === "string" && body.includes("text")),
        "a speech-to-speech request must not carry script text");
      assert.ok(calls[0].url.includes("speech-to-speech"));
    });
  });
