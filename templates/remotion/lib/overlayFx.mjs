// Effect arithmetic for the kinetic overlay (GV-17 Phase E).
//
// ZERO IMPORTS, same rule as captionPages.mjs: this repo has no node_modules and no npm
// on purpose, and every node test runs under bare `node --test`. A tested module that
// imports a package makes the suite unrunnable on a clean checkout. Everything here is
// a pure function of (frame, start frame, fps, ...): no Date, no Math.random, no state.
// Overlay.template.tsx and overlay-fx.tsx (copied into a project's shots/ workspace)
// turn these numbers into CSS and SVG; Remotion renders frames in separate processes,
// so frame N must come out identical every time. That is why the glitch uses a seeded
// mulberry32 and why drift() is a plain sine.
//
// Every function clamps outside its window and never returns NaN. Windows are measured
// in whole frames (round(seconds * fps), at least 1) so a 24 or 25 fps project reaches
// the end value on a real frame.

export function clamp01(x) {
  if (!(x > 0)) return 0; // also catches NaN
  return x > 1 ? 1 : x;
}

export function easeOut(t) {
  const u = 1 - clamp01(t);
  return 1 - u * u * u;
}

function winFrames(durS, fps) {
  return Math.max(1, Math.round(durS * fps));
}

// Progress 0..1 of frame f through [start, start + durS).
function progressOf(f, startF, fps, durS) {
  return clamp01((f - startF) / winFrames(durS, fps));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// fx 1: blur to sharp, 0.30 s.
export function blurIn(f, startF, fps) {
  const e = easeOut(progressOf(f, startF, fps, 0.3));
  return { opacity: e, blurPx: lerp(12, 0, e), scale: lerp(1.06, 1, e) };
}

// fx 2: six horizontal slices shifted sideways, amplitude 40 px decaying to exactly 0
// at 0.30 s. y0/y1 are fractions of the text height.
export function glitch(f, startF, fps, seed) {
  const t = progressOf(f, startF, fps, 0.3);
  const rand = mulberry32((seed >>> 0) + Math.max(0, Math.round(f)));
  const amp = 40 * (1 - t);
  const slices = [];
  for (let i = 0; i < 6; i++) {
    const dx = t >= 1 ? 0 : Math.round((rand() * 2 - 1) * amp) || 0;
    slices.push({ y0: i / 6, y1: i === 5 ? 1 : (i + 1) / 6, dx });
  }
  return slices;
}

// fx 3: count up to the number inside `text`, 0.60 s ease-out. Prefix, suffix, decimal
// count and decimal separator (dot or comma) are kept. Final frame returns `text` itself.
const NUMBER_RE = /\d[\d.,]*\d|\d/;

function parseNumber(text) {
  const match = NUMBER_RE.exec(text);
  if (!match) throw new Error(`countUp: no digit in "${text}"`);
  const raw = match[0];
  const seps = raw.match(/[.,]/g) || [];
  const lastIdx = Math.max(raw.lastIndexOf("."), raw.lastIndexOf(","));
  const after = lastIdx >= 0 ? raw.length - lastIdx - 1 : 0;
  let decimals = 0;
  let sep = ".";
  let group = "";
  if (seps.length === 1 && after !== 3) {
    decimals = after;
    sep = raw[lastIdx];
  } else if (seps.length >= 1 && after === 3) {
    group = raw[lastIdx]; // thousands grouping, e.g. 1,000 or 1.234.567
  } else if (seps.length > 1) {
    decimals = after;
    sep = raw[lastIdx];
  }
  const digits = raw.split(group || "\u0000").join("");
  const value = Number(decimals ? digits.replace(sep, ".") : digits);
  return {
    prefix: text.slice(0, match.index),
    suffix: text.slice(match.index + raw.length),
    value, decimals, sep, group,
  };
}

function withGrouping(intPart, group) {
  if (!group) return intPart;
  return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, group);
}

export function countUp(f, startF, fps, text) {
  const parsed = parseNumber(text);
  const t = progressOf(f, startF, fps, 0.6);
  if (t >= 1) return text;
  const current = parsed.value * easeOut(t);
  const fixed = current.toFixed(parsed.decimals);
  const [intPart, decPart] = fixed.split(".");
  const body = withGrouping(intPart, parsed.group) + (decPart !== undefined ? parsed.sep + decPart : "");
  return parsed.prefix + body + parsed.suffix;
}

// fx 4 (handwrite) and fx 5 (stroke draw, 0.4 s): 0..1 for SVG strokeDashoffset.
export function strokeProgress(f, startF, fps, durS = 0.5) {
  return easeOut(progressOf(f, startF, fps, durS));
}

// Lead words slide up 8 px while fading in, 0.25 s.
export function leadIn(f, startF, fps) {
  const e = easeOut(progressOf(f, startF, fps, 0.25));
  return { opacity: e, dy: lerp(8, 0, e) };
}

// fx 6: the 0.20 s window ENDING at endF.
export function exitFx(f, endF, fps) {
  const t = progressOf(f, endF - winFrames(0.2, fps), fps, 0.2);
  return { opacity: 1 - t, blurPx: 8 * t };
}

// Panels and bubbles: critically damped spring, never above 1, so scale stays <= 1.
export function springIn(f, startF, fps) {
  const t = Math.max(0, (f - startF) / fps);
  const w = 14;
  const x = 1 - (1 + w * t) * Math.exp(-w * t);
  return { opacity: clamp01(t / 0.15), scale: lerp(0.9, 1, clamp01(x)) };
}

// Slow float, +-6 px, period 4 s. The seed only shifts the phase.
export function drift(f, seed, fps) {
  const phase = ((seed >>> 0) % 628) / 100;
  const a = (2 * Math.PI * f) / (4 * fps);
  return { dx: 6 * Math.sin(a + phase), dy: 6 * Math.cos(a + phase * 1.7) };
}

// Carousel: one card (cardW + gap) to the left per 0.8 s, stops on the last card.
export function carouselX(f, startF, fps, cardW, gap, n) {
  const cards = Math.max(0, Math.min((f - startF) / (0.8 * fps), n - 1));
  return -(cards * (cardW + gap)) + 0;
}

export function cueVisible(f, inF, outF) {
  return f >= inF && f <= outF;
}

// One cue at one frame. Always composes an enter effect for cue.fx AND the exit effect at
// outF; nothing here returns a style that is constant for the cue's whole life.
export function cueStyle(cue, f, fps) {
  if (!(cue.outF > cue.inF)) {
    throw new Error(`cue ${cue.id}: outF (${cue.outF}) must be greater than inF (${cue.inF})`);
  }
  const exit = exitFx(f, cue.outF, fps);
  const lead = leadIn(f, cue.inF, fps);
  const started = f >= cue.keyF;

  let keyword;
  if (cue.fx === 2) {
    const enter = progressOf(f, cue.keyF, fps, 0.1);
    keyword = {
      opacity: enter, blurPx: 0, scale: 1, progress: 1,
      slices: glitch(f, cue.keyF, fps, hashString(String(cue.id))), text: cue.keyword,
    };
  } else if (cue.fx === 3) {
    const b = blurIn(f, cue.keyF, fps);
    keyword = {
      opacity: b.opacity, blurPx: b.blurPx, scale: b.scale, progress: 1, slices: [],
      text: countUp(f, cue.keyF, fps, cue.keyword),
    };
  } else if (cue.fx === 4) {
    const p = strokeProgress(f, cue.keyF, fps);
    keyword = {
      opacity: clamp01(p * 3), blurPx: 0, scale: 1, progress: p, slices: [], text: cue.keyword,
    };
  } else {
    const b = blurIn(f, cue.keyF, fps);
    keyword = {
      opacity: b.opacity, blurPx: b.blurPx, scale: b.scale, progress: 1, slices: [], text: cue.keyword,
    };
  }
  if (!started) keyword.opacity = 0;

  const iconStart = Math.max(cue.inF, cue.keyF - Math.round(0.1 * fps));
  return {
    lead: { opacity: lead.opacity * exit.opacity, dy: lead.dy },
    keyword: {
      ...keyword,
      opacity: keyword.opacity * exit.opacity,
      blurPx: Math.max(keyword.blurPx, exit.blurPx),
    },
    icon: { progress: strokeProgress(f, iconStart, fps, 0.4) },
  };
}

// Step counter (GV-19). marks = [{n, f}] in any order. active = highest n whose frame is
// <= f (0 before the first). litProgress eases 0..1 over 0.25 s from that mark's frame.
// The plan gives (f, marks, total); fps is a 4th argument, default 30, because the window
// is measured in seconds. total is only needed by the drawing, so it is not read here.
export function stepState(f, marks, total, fps = 30) {
  let hit = null;
  for (const m of marks || []) {
    if (f >= m.f && (hit === null || m.n > hit.n)) hit = m;
  }
  if (!hit) return { active: 0, litProgress: 0 };
  return { active: hit.n, litProgress: easeOut(progressOf(f, hit.f, fps, 0.25)) };
}

// Red edge vignette strength 0..1 of its maximum (the drawing multiplies by 0.55). Fades in
// 0.15 s, blinks at 3 Hz between 0.55 and 1.0, fades out over the 0.20 s ending at outF, and
// is exactly 0 at inF and from outF on.
export function vignetteAlpha(f, inF, outF, fps) {
  if (!Number.isFinite(f) || !(f > inF) || !(f < outF)) return 0;
  const fadeIn = progressOf(f, inF, fps, 0.15);
  const fadeOut = 1 - progressOf(f, outF - winFrames(0.2, fps), fps, 0.2);
  const blink = 0.775 + 0.225 * Math.sin((2 * Math.PI * 3 * (f - inF)) / fps);
  return clamp01(fadeIn * fadeOut * blink);
}

// Falling-object burst: `count` particles with x (0..1 across the width) from a seeded
// mulberry32, y falling -0.1 -> 1.1 (fractions of the height) over 1.6 s after a per-particle
// delay of up to 0.5 s, constant rotation speed. Same arguments, same array.
export function burstParticles(f, startF, fps, seed, count) {
  const n = Number.isFinite(count) ? Math.min(Math.max(Math.floor(count), 0), 30) : 0;
  const rand = mulberry32(seed);
  const out = [];
  for (let i = 0; i < n; i++) {
    const x = rand();
    const delay = rand() * 0.5;
    const rot0 = rand() * 360;
    const spin = (rand() * 2 - 1) * 360;
    const elapsed = Math.max(0, (f - startF) / fps - delay);
    const t = clamp01(elapsed / 1.6);
    out.push({
      x,
      y: lerp(-0.1, 1.1, t),
      rot: rot0 + spin * elapsed,
      opacity: elapsed <= 0 || t >= 1 ? 0 : clamp01(elapsed / 0.1),
    });
  }
  return out;
}
