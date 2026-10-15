import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  easeOut, clamp01, blurIn, glitch, countUp, strokeProgress, leadIn, exitFx,
  springIn, drift, carouselX, cueVisible, cueStyle,
} from "../../templates/remotion/lib/overlayFx.mjs";

const FPS_LIST = [24, 25, 30, 60];

function finite(value) {
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(finite);
  if (value && typeof value === "object") return Object.values(value).every(finite);
  return true;
}

test("blurIn: start, mid, end", () => {
  const start = blurIn(10, 10, 30);
  assert.equal(start.opacity, 0);
  assert.equal(start.blurPx, 12);
  assert.equal(start.scale, 1.06);
  const mid = blurIn(14, 10, 30); // 4 of 9 frames
  assert.ok(mid.opacity > 0 && mid.opacity < 1);
  assert.ok(mid.blurPx > 0 && mid.blurPx < 12);
  assert.ok(mid.scale > 1 && mid.scale < 1.06);
  const end = blurIn(19, 10, 30); // 0.30 s = 9 frames
  assert.deepEqual(end, { opacity: 1, blurPx: 0, scale: 1 });
});

test("easeOut and clamp01", () => {
  assert.equal(easeOut(0), 0);
  assert.equal(easeOut(1), 1);
  assert.equal(easeOut(-3), 0);
  assert.equal(easeOut(7), 1);
  assert.ok(easeOut(0.5) > 0.5);
  assert.equal(clamp01(-1), 0);
  assert.equal(clamp01(2), 1);
  assert.equal(clamp01(0.25), 0.25);
});

test("every function clamps before start, at start, at end and after end, no NaN", () => {
  for (const fps of FPS_LIST) {
    const s = 100;
    const frames = [0, s - 1, s, s + Math.round(0.3 * fps), s + 10 * fps];
    for (const f of frames) {
      const outs = [
        blurIn(f, s, fps), glitch(f, s, fps, 3), countUp(f, s, fps, "1.9%"),
        strokeProgress(f, s, fps), strokeProgress(f, s, fps, 0.4), leadIn(f, s, fps),
        exitFx(f, s, fps), springIn(f, s, fps), drift(f, 5, fps),
        carouselX(f, s, fps, 300, 20, 4),
      ];
      for (const out of outs) assert.ok(finite(out), `fps ${fps} f ${f}`);
    }
    assert.equal(blurIn(0, s, fps).opacity, 0);
    assert.equal(blurIn(s + 10 * fps, s, fps).opacity, 1);
    assert.equal(leadIn(0, s, fps).dy, 8);
    assert.equal(leadIn(s + 10 * fps, s, fps).dy, 0);
    assert.equal(springIn(0, s, fps).scale, 0.9);
    assert.equal(springIn(s + 10 * fps, s, fps).scale, 1);
    assert.equal(strokeProgress(0, s, fps), 0);
    assert.equal(strokeProgress(s + 10 * fps, s, fps), 1);
  }
});

test("glitch: 6 contiguous slices, bounded dx, deterministic", () => {
  const slices = glitch(102, 100, 30, 7);
  assert.equal(slices.length, 6);
  assert.equal(slices[0].y0, 0);
  assert.equal(slices[5].y1, 1);
  for (let i = 1; i < 6; i++) assert.equal(slices[i].y0, slices[i - 1].y1);
  for (const sl of slices) {
    assert.ok(sl.y1 > sl.y0);
    assert.ok(Math.abs(sl.dx) <= 40);
  }
  assert.deepEqual(glitch(102, 100, 30, 7), slices);
  assert.ok(slices.some((sl) => sl.dx !== 0));
});

test("glitch: different seed differs, dx exactly 0 from 0.30 s on, at all fps", () => {
  let differs = false;
  for (let f = 100; f < 108; f++) {
    const a = glitch(f, 100, 30, 1);
    const b = glitch(f, 100, 30, 2);
    if (JSON.stringify(a) !== JSON.stringify(b)) differs = true;
  }
  assert.ok(differs);
  for (const fps of FPS_LIST) {
    const at = 100 + Math.round(0.3 * fps);
    for (const f of [at, at + 1, at + 500]) {
      for (const sl of glitch(f, 100, fps, 9)) assert.ok(Object.is(sl.dx, 0), `fps ${fps} f ${f}`);
    }
  }
});

test("countUp formats", () => {
  assert.equal(countUp(0, 0, 30, "1.9%"), "0.0%");
  assert.equal(countUp(1000, 0, 30, "1.9%"), "1.9%");
  assert.equal(countUp(18, 0, 30, "1.9%"), "1.9%"); // 0.60 s = 18 frames
  const midPct = countUp(9, 0, 30, "1.9%");
  assert.match(midPct, /^\d\.\d%$/);
  assert.notEqual(midPct, "0.0%");
  assert.notEqual(midPct, "1.9%");
  assert.equal(countUp(0, 0, 30, "221"), "0");
  assert.equal(countUp(30, 0, 30, "221"), "221");
  assert.match(countUp(9, 0, 30, "221"), /^\d{1,3}$/);
  assert.equal(countUp(0, 0, 30, "4x"), "0x");
  assert.equal(countUp(30, 0, 30, "4x"), "4x");
  assert.equal(countUp(0, 0, 30, "1%"), "0%");
  assert.equal(countUp(30, 0, 30, "1%"), "1%");
  assert.equal(countUp(0, 0, 30, "Rp 2,5 T"), "Rp 0,0 T");
  assert.equal(countUp(30, 0, 30, "Rp 2,5 T"), "Rp 2,5 T");
  assert.match(countUp(9, 0, 30, "Rp 2,5 T"), /^Rp \d,\d T$/);
  assert.equal(countUp(-5, 0, 30, "4x"), "0x");
});

test("countUp is monotonic non-decreasing", () => {
  let prev = -1;
  for (let f = 0; f <= 20; f++) {
    const n = Number(countUp(f, 0, 30, "221"));
    assert.ok(n >= prev);
    prev = n;
  }
});

test("countUp throws on text without a digit", () => {
  assert.throws(() => countUp(5, 0, 30, "abc"));
  assert.throws(() => countUp(5, 0, 30, ""));
});

test("strokeProgress is monotonic and honours durS", () => {
  for (const fps of FPS_LIST) {
    let prev = -1;
    for (let f = 90; f < 90 + 2 * fps; f++) {
      const p = strokeProgress(f, 100, fps);
      assert.ok(p >= prev && p >= 0 && p <= 1);
      prev = p;
    }
  }
  assert.equal(strokeProgress(115, 100, 30), 1); // 0.5 s = 15 frames
  assert.ok(strokeProgress(112, 100, 30) < 1);
  assert.equal(strokeProgress(112, 100, 30, 0.4), 1); // 0.4 s = 12 frames
});

test("leadIn, exitFx, springIn, drift values", () => {
  const mid = leadIn(103, 100, 30);
  assert.ok(mid.opacity > 0 && mid.opacity < 1 && mid.dy > 0 && mid.dy < 8);
  assert.deepEqual(leadIn(108, 100, 30), { opacity: 1, dy: 0 });

  assert.deepEqual(exitFx(0, 200, 30), { opacity: 1, blurPx: 0 });
  assert.deepEqual(exitFx(200, 200, 30), { opacity: 0, blurPx: 8 });
  assert.deepEqual(exitFx(900, 200, 30), { opacity: 0, blurPx: 8 });
  const ex = exitFx(197, 200, 30);
  assert.ok(ex.opacity > 0 && ex.opacity < 1 && ex.blurPx > 0 && ex.blurPx < 8);
  assert.deepEqual(exitFx(194, 200, 30), { opacity: 1, blurPx: 0 }); // window is 6 frames

  for (let f = 100; f < 160; f++) {
    const sp = springIn(f, 100, 30);
    assert.ok(sp.scale >= 0.9 && sp.scale <= 1.03);
    assert.ok(sp.opacity >= 0 && sp.opacity <= 1);
  }

  const seen = new Set();
  for (let f = 0; f < 600; f++) {
    const d = drift(f, 4, 30);
    assert.ok(Math.abs(d.dx) <= 6 && Math.abs(d.dy) <= 6);
    seen.add(d.dx.toFixed(3));
  }
  assert.ok(seen.size > 20);
  assert.deepEqual(drift(37, 4, 30), drift(37, 4, 30));
  assert.ok(Math.abs(drift(0, 4, 30).dx - drift(120, 4, 30).dx) < 1e-9); // ~4 s period
});

test("carouselX slides one card per 0.8 s and stops at the last card", () => {
  assert.ok(Object.is(carouselX(0, 100, 30, 300, 20, 4), 0));
  assert.ok(Object.is(carouselX(100, 100, 30, 300, 20, 4), 0));
  assert.equal(carouselX(124, 100, 30, 300, 20, 4), -320); // 0.8 s = 24 frames
  assert.equal(carouselX(148, 100, 30, 300, 20, 4), -640);
  const stop = carouselX(100 + 24 * 3, 100, 30, 300, 20, 4);
  assert.equal(stop, -960);
  assert.equal(carouselX(5000, 100, 30, 300, 20, 4), -960);
  assert.ok(Object.is(carouselX(5000, 100, 30, 300, 20, 1), 0));
  assert.ok(carouselX(112, 100, 30, 300, 20, 4) < 0);
});

test("cueVisible is inclusive", () => {
  assert.equal(cueVisible(9, 10, 20), false);
  assert.equal(cueVisible(10, 10, 20), true);
  assert.equal(cueVisible(20, 10, 20), true);
  assert.equal(cueVisible(21, 10, 20), false);
});

function cue(fx, extra = {}) {
  return {
    id: `cue-${fx}`, lead: "turun", keyword: fx === 3 ? "1.9%" : "Rp 2,5 T",
    fx, color: "yellow", script: fx === 4, icon: "fire", layer: "front",
    inF: 30, keyF: 45, outF: 150, ...extra,
  };
}

test("cueStyle is never static for fx 1..4 at any fps", () => {
  for (const fps of FPS_LIST) {
    for (const fx of [1, 2, 3, 4]) {
      const c = cue(fx, {
        inF: Math.round(1 * fps), keyF: Math.round(1.5 * fps), outF: Math.round(5 * fps),
      });
      const enterMid = cueStyle(c, c.keyF + Math.round(0.12 * fps), fps);
      const hold = cueStyle(c, Math.round(3 * fps), fps);
      const exitMid = cueStyle(c, c.outF - Math.round(0.1 * fps), fps);
      const a = JSON.stringify(enterMid);
      const b = JSON.stringify(hold);
      const d = JSON.stringify(exitMid);
      assert.notEqual(a, b, `fx ${fx} fps ${fps} enter vs hold`);
      assert.notEqual(b, d, `fx ${fx} fps ${fps} hold vs exit`);
      assert.notEqual(a, d, `fx ${fx} fps ${fps} enter vs exit`);
      for (const s of [enterMid, hold, exitMid]) assert.ok(finite(s));
    }
  }
});

test("cueStyle: hold is fully shown, end is gone, lead enters at inF", () => {
  const c = cue(1);
  const hold = cueStyle(c, 100, 30);
  assert.equal(hold.lead.opacity, 1);
  assert.equal(hold.keyword.opacity, 1);
  assert.equal(hold.keyword.blurPx, 0);
  assert.equal(hold.keyword.text, "Rp 2,5 T");
  assert.equal(hold.icon.progress, 1);
  const gone = cueStyle(c, c.outF, 30);
  assert.equal(gone.lead.opacity, 0);
  assert.equal(gone.keyword.opacity, 0);
  assert.equal(gone.keyword.blurPx, 8);
  const early = cueStyle(c, c.inF, 30);
  assert.equal(early.lead.opacity, 0);
  assert.equal(early.keyword.opacity, 0); // keyword waits for keyF
  const leadOnly = cueStyle(c, c.inF + 4, 30);
  assert.ok(leadOnly.lead.opacity > 0);
  assert.equal(leadOnly.keyword.opacity, 0);
});

test("cueStyle: fx specifics", () => {
  const g = cueStyle(cue(2), 47, 30);
  assert.equal(g.keyword.slices.length, 6);
  assert.ok(g.keyword.slices.some((s) => s.dx !== 0));
  assert.deepEqual(cueStyle(cue(2), 47, 30), g);
  assert.equal(cueStyle(cue(2), 100, 30).keyword.slices.every((s) => s.dx === 0), true);
  // seed comes from cue id
  const other = cueStyle(cue(2, { id: "different-id" }), 47, 30);
  assert.notDeepEqual(other.keyword.slices, g.keyword.slices);

  assert.equal(cueStyle(cue(3), 45, 30).keyword.text, "0.0%");
  assert.equal(cueStyle(cue(3), 100, 30).keyword.text, "1.9%");
  assert.notEqual(cueStyle(cue(3), 52, 30).keyword.text, "1.9%");

  // icon starts 0.1 s before keyF, never before inF
  assert.equal(cueStyle(cue(1), 42, 30).icon.progress, 0);
  assert.ok(cueStyle(cue(1), 48, 30).icon.progress > 0);
  const tight = cue(1, { inF: 45, keyF: 45 });
  assert.equal(cueStyle(tight, 44, 30).icon.progress, 0);
  assert.ok(cueStyle(tight, 50, 30).icon.progress > 0);
});

test("cueStyle throws on zero or negative length", () => {
  assert.throws(() => cueStyle(cue(1, { inF: 50, outF: 50 }), 50, 30));
  assert.throws(() => cueStyle(cue(1, { inF: 60, outF: 50 }), 50, 30));
});

test("overlayFx.mjs has no import line", () => {
  const src = readFileSync(new URL("../../templates/remotion/lib/overlayFx.mjs", import.meta.url), "utf8");
  assert.equal(/^\s*import[\s{(]/m.test(src), false);
});
