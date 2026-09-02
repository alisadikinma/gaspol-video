import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, stat, writeFile } from "node:fs/promises";
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

// --- Per-speaker spans -------------------------------------------------------------
// Converting a whole track converts every voice on it. Measured on a real clip: a
// second speaker came back in the target voice, which is a wrong result, not a rough
// one. Spans name the target's turns so the rest of the bed is left alone.

import { SEAM_PAD_S, convertSpans, parseSpans, spansWarning } from "../../tools/voice_changer.mjs";

test("spans parse into ordered, non-overlapping ranges", () => {
  assert.deepEqual(parseSpans("0-3.88,5.2-7"), [
    { start_s: 0, end_s: 3.88 },
    { start_s: 5.2, end_s: 7 },
  ]);
});

test("a reversed or overlapping span is refused, never silently repaired", () => {
  assert.throws(() => parseSpans("3-1"), /start.*before.*end|reversed/i);
  assert.throws(() => parseSpans("0-4,3-6"), /overlap/i);
  assert.throws(() => parseSpans("-1-2"), /negative|invalid/i);
});

test("one request per span, each carrying that span only", async () => {
  await withTmp(async (dir) => {
    const calls = [];
    const extracted = [];
    const result = await convertSpans({
      ...BASE,
      inputPath: path.join(dir, "clip.mp4"),
      outPath: path.join(dir, "out.mp3"),
      spans: [{ start_s: 0, end_s: 3.88 }, { start_s: 5.2, end_s: 7 }],
      fetchImpl: okFetch(calls),
      extract: async (src, out, range) => {
        extracted.push(range ? { ...range } : null);
        await mkdir(path.dirname(out), { recursive: true });
        await writeFile(out, Buffer.from("RIFF....fake wav"));
        return out;
      },
      durationOf: async () => 8.0,
      splice: async ({ outPath }) => {
        await writeFile(outPath, Buffer.from("spliced"));
        return outPath;
      },
    });
    assert.equal(calls.length, 2, "one speech-to-speech request per span");
    // The first extract is the full bed; the rest are the spans, each carrying
    // SEAM_PAD_S of extra audio either side for the crossfade to land on.
    assert.equal(extracted[0], null);
    const round = (v) => Number(v.toFixed(3));
    assert.deepEqual(extracted.slice(1).map((r) => [round(r.start_s), round(r.end_s)]), [
      [0, round(3.88 + SEAM_PAD_S)],
      [round(5.2 - SEAM_PAD_S), round(7 + SEAM_PAD_S)],
    ]);
    assert.equal(result.spans_converted, 2);
  });
});

test("the untouched bed is spliced back, at the offsets the spans named", async () => {
  await withTmp(async (dir) => {
    let seen = null;
    await convertSpans({
      ...BASE,
      inputPath: path.join(dir, "clip.mp4"),
      outPath: path.join(dir, "out.mp3"),
      spans: [{ start_s: 1.0, end_s: 2.5 }],
      fetchImpl: okFetch([]),
      extract: async (src, out) => {
        await mkdir(path.dirname(out), { recursive: true });
        await writeFile(out, Buffer.from("RIFF....fake wav"));
        return out;
      },
      durationOf: async () => 8.0,
      splice: async (args) => {
        seen = args;
        await writeFile(args.outPath, Buffer.from("spliced"));
        return args.outPath;
      },
    });
    assert.ok(seen, "splice must run — otherwise the other speakers are gone");
    assert.ok(seen.bedPath, "the original audio is the bed");
    assert.equal(seen.pieces.length, 1);
    assert.equal(seen.pieces[0].start_s, 1.0);
    assert.equal(seen.pieces[0].end_s, 2.5);
  });
});

test("the drift gate is applied to the spliced result, not to each piece", async () => {
  await withTmp(async (dir) => {
    const durations = [8.0, 8.6]; // the bed, then the spliced result
    let i = 0;
    await assert.rejects(
      convertSpans({
        ...BASE,
        inputPath: path.join(dir, "clip.mp4"),
        outPath: path.join(dir, "out.mp3"),
        spans: [{ start_s: 1.0, end_s: 2.5 }],
        fetchImpl: okFetch([]),
        extract: async (src, out) => {
          await mkdir(path.dirname(out), { recursive: true });
          await writeFile(out, Buffer.from("RIFF....fake wav"));
          return out;
        },
        durationOf: async () => durations[Math.min(i++, durations.length - 1)],
        splice: async ({ outPath }) => {
          await writeFile(outPath, Buffer.from("spliced"));
          return outPath;
        },
      }),
      (err) => err.message.includes(driftMessage) && /8\.600/.test(err.message),
    );
  });
});

test("converting a whole track warns that every voice on it changes", async () => {
  await withTmp(async (dir) => {
    const lines = [];
    await convert({
      ...BASE,
      log: (line) => lines.push(line),
      inputPath: path.join(dir, "clip.mp4"),
      outPath: path.join(dir, "out.mp3"),
      fetchImpl: okFetch([]),
      extract: async () => path.join(dir, "in.wav"),
      durationOf: async () => 4.0,
    });
    assert.ok(
      lines.some((l) => l.includes(spansWarning)),
      "a clip with a second speaker must not convert silently",
    );
  });
});
