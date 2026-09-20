import assert from "node:assert/strict";
import test from "node:test";

import { toCaptionRecords, partitionPages } from "../../templates/remotion/lib/captionPages.mjs";

function sixWordScene() {
  const texts = ["Sistem", "ANPR", "membaca", "plat", "dalam", "detik"];
  const words = [];
  let t = 0;
  for (const text of texts) {
    words.push({ text, start_ms: t, end_ms: t + 300 });
    t += 300;
  }
  return { scene: 1, words, highlights: [] };
}

// --- toCaptionRecords --------------------------------------------------------

test("toCaptionRecords returns one Caption record per word, each carrying its own leading space, in order", () => {
  const scene = sixWordScene();
  const records = toCaptionRecords(scene);
  assert.equal(records.length, scene.words.length);
  assert.deepEqual(records.map((r) => r.text), scene.words.map((w) => ` ${w.text}`));
  assert.deepEqual(records.map((r) => r.startMs), scene.words.map((w) => w.start_ms));
  assert.deepEqual(records.map((r) => r.endMs), scene.words.map((w) => w.end_ms));
});

test("toCaptionRecords: a highlight span with end_word beyond the word list throws, naming the scene", () => {
  const scene = sixWordScene();
  scene.highlights = [{ start_word: 4, end_word: 8, score: 9, rule: "number-unit" }];
  assert.throws(() => toCaptionRecords(scene), /scene 1/);
});

test("toCaptionRecords: end_ms <= start_ms on a word throws rather than producing a zero-length reveal", () => {
  const scene = { scene: 3, words: [{ text: "Diam", start_ms: 100, end_ms: 100 }], highlights: [] };
  assert.throws(() => toCaptionRecords(scene), /scene 3/);
});

test("toCaptionRecords: a one-word scene returns exactly one caption record", () => {
  const scene = { scene: 2, words: [{ text: "Selesai", start_ms: 0, end_ms: 500 }], highlights: [] };
  const records = toCaptionRecords(scene);
  assert.equal(records.length, 1);
  assert.equal(records[0].text, " Selesai");
});

// --- partitionPages ----------------------------------------------------------
// `pages` fixtures below stand in for whatever createTikTokStyleCaptions() would
// return for toCaptionRecords(scene) — only `tokens.length` is read by
// partitionPages (a count, one per original word); text/timing always come back
// from `scene.words`, never from the fixture's own token content.

test("partitionPages: concatenated words across all returned pages equal the input words in order", () => {
  const scene = sixWordScene();
  const pages = [
    { startMs: 0, durationMs: 900, text: " Sistem ANPR membaca", tokens: [{}, {}, {}] },
    { startMs: 900, durationMs: 900, text: " plat dalam detik", tokens: [{}, {}, {}] },
  ];
  const result = partitionPages(pages, scene);
  const flattened = result.flatMap((page) => page.words.map((w) => w.text));
  assert.deepEqual(flattened, scene.words.map((w) => w.text));
});

test("partitionPages: words inside a highlight span carry highlight: true, others false", () => {
  const scene = sixWordScene();
  scene.highlights = [{ start_word: 1, end_word: 2, score: 6, rule: "acronym" }];
  const pages = [{ startMs: 0, durationMs: 1800, text: " all six words", tokens: new Array(6).fill({}) }];
  const result = partitionPages(pages, scene);
  const byText = {};
  for (const page of result) {
    for (const w of page.words) byText[w.text] = w.highlight;
  }
  assert.equal(byText.Sistem, false);
  assert.equal(byText.ANPR, true);
  assert.equal(byText.membaca, true);
  assert.equal(byText.plat, false);
});

test("partitionPages: a one-word scene, one page, returns exactly one page with one word", () => {
  const scene = { scene: 2, words: [{ text: "Selesai", start_ms: 0, end_ms: 500 }], highlights: [] };
  const pages = [{ startMs: 0, durationMs: 500, text: "Selesai", tokens: [{}] }];
  const result = partitionPages(pages, scene);
  assert.equal(result.length, 1);
  assert.equal(result[0].words.length, 1);
  assert.equal(result[0].words[0].text, "Selesai");
});

test("partitionPages: passes page-level startMs/durationMs/text through unchanged", () => {
  const scene = sixWordScene();
  const pages = [{ startMs: 120, durationMs: 480, text: " Sistem ANPR", tokens: [{}, {}] },
    { startMs: 600, durationMs: 1200, text: " membaca plat dalam detik", tokens: [{}, {}, {}, {}] }];
  const result = partitionPages(pages, scene);
  assert.equal(result[0].startMs, 120);
  assert.equal(result[0].durationMs, 480);
  assert.equal(result[0].text, " Sistem ANPR");
});
