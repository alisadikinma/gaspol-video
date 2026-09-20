// Page/word/highlight arithmetic for kinetic captions (GV-7 Phase C).
//
// ZERO IMPORTS (decided 2026-09-20, after a first attempt imported @remotion/captions
// here). This repo has no node_modules and deliberately no npm — tests/run.sh says
// "no pytest and no npm here on purpose" — and all node tests run under bare
// `node --test`. A tested module that imports a package makes the suite unrunnable on
// a clean checkout. The actual word-grouping algorithm (createTikTokStyleCaptions)
// therefore lives ONLY in Captions.template.tsx, which is copied into a project's
// shots/ workspace where the dependency is installed and is never executed by this
// repo's own suite. This module supplies the input to that call (toCaptionRecords)
// and consumes its output (partitionPages) — both pure, both testable with no install.
//
// @remotion/captions requires every Caption.text to carry its OWN LEADING whitespace;
// it trims that away only for the first token of a page. toCaptionRecords() adds
// exactly one leading space per word so words never merge into one run once
// Captions.template.tsx concatenates tokens back together (its container renders with
// white-space: pre for exactly this reason).

function assertWordsTimed(scene) {
  const words = scene.words;
  if (!Array.isArray(words)) {
    throw new Error(`scene ${scene.scene}: "words" must be an array`);
  }
  words.forEach((word, index) => {
    if (!(word.end_ms > word.start_ms)) {
      throw new Error(
        `scene ${scene.scene}: word ${index} ("${word.text}") has end_ms (${word.end_ms}) `
          + `<= start_ms (${word.start_ms}) — refusing to produce a zero-length reveal`,
      );
    }
  });
  return words;
}

function assertHighlightsInRange(scene, words) {
  const highlights = scene.highlights || [];
  highlights.forEach((span, index) => {
    if (
      span.start_word < 0
      || span.end_word < span.start_word
      || span.end_word > words.length - 1
    ) {
      throw new Error(
        `scene ${scene.scene}: highlight ${index} spans word ${span.start_word}-${span.end_word}, `
          + `out of range for ${words.length} word(s)`,
      );
    }
  });
  return highlights;
}

/**
 * toCaptionRecords(scene)
 *
 * scene: one entry of work/caption-plan.json's `scenes` array —
 *   {scene, words: [{text, start_ms, end_ms}], highlights: [{start_word, end_word, ...}]}
 *
 * Validates every word's timing and every highlight span's bounds (throwing with the
 * scene number and word/span index on either failure — never a bare `undefined`), then
 * returns one @remotion/captions `Caption` record per word, in order:
 *   {text, startMs, endMs, timestampMs, confidence}
 * `text` carries its own leading space (see module header). Captions.template.tsx
 * passes this array straight to createTikTokStyleCaptions() as `captions`.
 */
export function toCaptionRecords(scene) {
  const words = assertWordsTimed(scene);
  assertHighlightsInRange(scene, words);

  return words.map((word) => ({
    text: ` ${word.text}`,
    startMs: word.start_ms,
    endMs: word.end_ms,
    timestampMs: null,
    confidence: null,
  }));
}

/**
 * partitionPages(pages, scene)
 *
 * pages: the `pages` array createTikTokStyleCaptions() returned for
 *   toCaptionRecords(scene) — only each page's `tokens.length` is used (a count, one
 *   per original word); `startMs`, `durationMs` and `text` are passed through as-is.
 * scene: the same scene object passed to toCaptionRecords() — text and timing for
 *   every returned word come from `scene.words`, never from the library's own tokens,
 *   the same "text always comes from the script" rule Phase B2 enforces elsewhere.
 *
 * Returns pages in the same order, each reshaped to
 *   {startMs, durationMs, text, words: [{text, startMs, endMs, highlight}]}
 * Concatenating every page's `words` reproduces `scene.words` exactly, in order —
 * every word belongs to exactly one page.
 */
export function partitionPages(pages, scene) {
  const words = scene.words;
  const highlights = scene.highlights || [];
  const highlighted = new Set();
  for (const span of highlights) {
    for (let i = span.start_word; i <= span.end_word; i += 1) {
      highlighted.add(i);
    }
  }

  let cursor = 0;
  return pages.map((page) => {
    const pageWords = page.tokens.map(() => {
      const index = cursor;
      cursor += 1;
      const word = words[index];
      return {
        text: word.text,
        startMs: word.start_ms,
        endMs: word.end_ms,
        highlight: highlighted.has(index),
      };
    });
    return {
      startMs: page.startMs,
      durationMs: page.durationMs,
      text: page.text,
      words: pageWords,
    };
  });
}
