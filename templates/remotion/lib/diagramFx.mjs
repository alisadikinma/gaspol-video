// Pure timing helpers for diagram shots. Zero imports so node --test can run them.
// A cue is a word start time (seconds) from vo/scene-NN-narr-words.json: [[text, start, end], ...].

/** Frames a shot must last to match a voice file: round(seconds * fps), at least 1. */
export function durationFrames(seconds, fps = 30) {
  return Math.max(1, Math.round(seconds * fps));
}

/** Frame where word number `index` (0-based) starts. Throws on a missing word. */
export function wordFrame(words, index, fps = 30) {
  const w = words[index];
  if (!w) throw new Error(`wordFrame: no word at index ${index} (have ${words.length})`);
  return Math.round(w[1] * fps);
}

/** Frame where the first word whose text starts with `prefix` (case-insensitive, punctuation ignored) starts. */
export function findWordFrame(words, prefix, fps = 30) {
  const norm = (s) => String(s).toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
  const p = norm(prefix);
  const i = words.findIndex((w) => norm(w[0]).startsWith(p));
  if (i < 0) throw new Error(`findWordFrame: "${prefix}" not found`);
  return wordFrame(words, i, fps);
}

/** Linear position of a point along a polyline-free segment: 0 before a, 1 after b, eased by t^2*(3-2t). */
export function smooth(frame, a, b) {
  if (b <= a) return frame >= a ? 1 : 0;
  const t = Math.min(1, Math.max(0, (frame - a) / (b - a)));
  return t * t * (3 - 2 * t);
}
