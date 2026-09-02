import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import {
  EM_DASH_MESSAGE,
  buildItems,
  synthesize,
} from "../../tools/gen_vo.mjs";

const PLAN = {
  audio_source: "elevenlabs",
  scenes: [
    {
      scene: 1,
      audio_source: "elevenlabs",
      layers: [
        { kind: "narration", cast: "c1", at_s: 0, dur_s: 4, from: "tts",
          text: "Tiap truk antre 42 menit di gerbang.", out: "vo/scene-01-narr.mp3" },
      ],
    },
    {
      scene: 2,
      audio_source: "elevenlabs",
      layers: [
        { kind: "narration", cast: "c1", at_s: 0, dur_s: 3, from: "tts",
          text: "Sekarang enam menit.", out: "vo/scene-02-narr.mp3" },
        { kind: "dialogue", cast: "c2", at_s: 3, dur_s: 2, from: "clip",
          text: "Sudah lewat, Pak.", out: "vo/scene-02-c2.mp3" },
      ],
    },
  ],
};

const CAST = {
  c1: { voice_env: "ELEVENLABS_VOICE_C1", model: "eleven_multilingual_v2",
        settings: { stability: 0.55, similarity_boost: 0.8, style: 0.3, speed: 0.95 } },
  c2: { voice_env: "ELEVENLABS_VOICE_C2", model: "eleven_multilingual_v2", settings: {} },
};

function fakeFetch(calls, { status = 200 } = {}) {
  let n = 0;
  return async (url, init) => {
    n += 1;
    calls.push({ url, init, body: JSON.parse(init.body) });
    if (status !== 200) {
      return { ok: false, status, text: async () => `error ${status}`, headers: new Map() };
    }
    return {
      ok: true,
      status: 200,
      headers: new Map([["request-id", `req-${n}`]]),
      json: async () => ({
        audio_base64: Buffer.from(`audio-${n}`).toString("base64"),
        alignment: {
          characters: ["a", "b"],
          character_start_times_seconds: [0, 0.2],
          character_end_times_seconds: [0.2, 0.4],
        },
      }),
    };
  };
}

async function withTmp(fn) {
  const dir = await mkdtemp(path.join(tmpdir(), "gv-vo-"));
  try {
    return await fn(dir);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

test("only tts layers are synthesized; clip layers are left to the voice changer", () => {
  const items = buildItems(PLAN, CAST);
  assert.equal(items.length, 2);
  assert.deepEqual(items.map((i) => i.id), ["scene-01-narr", "scene-02-narr"]);
});

test("consecutive requests carry previous_request_ids so prosody continues", async () => {
  await withTmp(async (dir) => {
    const calls = [];
    await synthesize({
      plan: PLAN, cast: CAST, projectDir: dir,
      env: { ELEVENLABS_API_KEY: "k", ELEVENLABS_VOICE_C1: "v1", ELEVENLABS_VOICE_C2: "v2" },
      fetchImpl: fakeFetch(calls),
    });
    assert.equal(calls.length, 2);
    assert.deepEqual(calls[0].body.previous_request_ids ?? [], []);
    assert.deepEqual(calls[1].body.previous_request_ids, ["req-1"]);
  });
});

test("manifest records duration, the env var NAME, and never a key or an id", async () => {
  await withTmp(async (dir) => {
    await synthesize({
      plan: PLAN, cast: CAST, projectDir: dir,
      env: { ELEVENLABS_API_KEY: "secret-key", ELEVENLABS_VOICE_C1: "voiceid123", ELEVENLABS_VOICE_C2: "v2" },
      fetchImpl: fakeFetch([]),
    });
    const raw = await readFile(path.join(dir, "vo", "vo-manifest.json"), "utf8");
    assert.ok(!raw.includes("secret-key"), "manifest must not contain the API key");
    assert.ok(!raw.includes("voiceid123"), "manifest must not contain the voice id");
    const manifest = JSON.parse(raw);
    assert.equal(manifest.items[0].voice_env, "ELEVENLABS_VOICE_C1");
    assert.ok(manifest.items[0].duration_s >= 0);
    assert.ok(Array.isArray(manifest.items[0].words));
  });
});

test("settings sent are the locked recipe, and the model is never v3", async () => {
  await withTmp(async (dir) => {
    const calls = [];
    await synthesize({
      plan: PLAN, cast: CAST, projectDir: dir,
      env: { ELEVENLABS_API_KEY: "k", ELEVENLABS_VOICE_C1: "v1", ELEVENLABS_VOICE_C2: "v2" },
      fetchImpl: fakeFetch(calls),
    });
    assert.equal(calls[0].body.model_id, "eleven_multilingual_v2");
    assert.equal(calls[0].body.voice_settings.stability, 0.55);
    assert.ok(!JSON.stringify(calls[0].body).includes("v3"));
  });
});

test("an em dash in spoken text is refused before the request is sent", async () => {
  await withTmp(async (dir) => {
    const bad = structuredClone(PLAN);
    bad.scenes[0].layers[0].text = "Antre 42 menit — sekarang enam.";
    const calls = [];
    await assert.rejects(
      () => synthesize({
        plan: bad, cast: CAST, projectDir: dir,
        env: { ELEVENLABS_API_KEY: "k", ELEVENLABS_VOICE_C1: "v1", ELEVENLABS_VOICE_C2: "v2" },
        fetchImpl: fakeFetch(calls),
      }),
      (err) => err.message.includes(EM_DASH_MESSAGE),
    );
    assert.equal(calls.length, 0, "nothing may be sent when the text is rejected");
  });
});

test("a missing voice env stops with the variable name, and picks no substitute", async () => {
  await withTmp(async (dir) => {
    await assert.rejects(
      () => synthesize({
        plan: PLAN, cast: CAST, projectDir: dir,
        env: { ELEVENLABS_API_KEY: "k" },
        fetchImpl: fakeFetch([]),
      }),
      (err) => err.message.includes("ELEVENLABS_VOICE_C1"),
    );
  });
});

test("a missing API key degrades: no throw, no files, a printed command", async () => {
  await withTmp(async (dir) => {
    const result = await synthesize({
      plan: PLAN, cast: CAST, projectDir: dir,
      env: {},
      fetchImpl: fakeFetch([]),
      log: () => {},
    });
    assert.equal(result.degraded, true);
    assert.ok(result.reason.includes("ELEVENLABS_API_KEY"));
    assert.equal(result.items.length, 0);
  });
});

test("empty text is skipped rather than sent", () => {
  const plan = structuredClone(PLAN);
  plan.scenes[0].layers[0].text = "   ";
  const items = buildItems(plan, CAST);
  assert.deepEqual(items.map((i) => i.id), ["scene-02-narr"]);
});

test("HTTP 401 is reported as a credential problem and is not retried", async () => {
  await withTmp(async (dir) => {
    let attempts = 0;
    const failing = async (...args) => {
      attempts += 1;
      return fakeFetch([], { status: 401 })(...args);
    };
    await assert.rejects(
      () => synthesize({
        plan: PLAN, cast: CAST, projectDir: dir,
        env: { ELEVENLABS_API_KEY: "k", ELEVENLABS_VOICE_C1: "v1", ELEVENLABS_VOICE_C2: "v2" },
        fetchImpl: failing, log: () => {},
      }),
      (err) => /401/.test(err.message),
    );
    assert.equal(attempts, 1, "a credential error must not be retried");
  });
});

test("HTTP 429 is retried with backoff before giving up", async () => {
  await withTmp(async (dir) => {
    let attempts = 0;
    const flaky = async (url, init) => {
      attempts += 1;
      if (attempts < 3) return { ok: false, status: 429, text: async () => "rate limited", headers: new Map() };
      return fakeFetch([])(url, init);
    };
    const result = await synthesize({
      plan: PLAN, cast: CAST, projectDir: dir,
      env: { ELEVENLABS_API_KEY: "k", ELEVENLABS_VOICE_C1: "v1", ELEVENLABS_VOICE_C2: "v2" },
      fetchImpl: flaky, log: () => {}, sleep: async () => {},
    });
    assert.ok(attempts >= 3);
    assert.equal(result.items.length, 2);
  });
});
