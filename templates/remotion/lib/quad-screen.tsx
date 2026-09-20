// Attach an overlay panel to a screen that is NOT facing the camera square-on (v3.4.0).
//
// A monitor or phone seen off-axis is a TRAPEZOID, not a rotated rectangle. Measured on one
// office monitor in a 1920x1080 frame: left edge 524px tall, right edge 375px. A panel placed
// as a box plus a rotation therefore always overhangs one corner — the defect the client
// reported as "the app screen does not match the monitor".
//
// The fix is a homography: map the panel's four corners onto the screen's four corners. CSS can
// express exactly that, as `matrix3d`. Corners come from `tools/track_screen.py`, which fits
// each screen edge to a line and intersects them; never eyeball them, and never use a bounding
// box.
//
// Copy to {project}/shots/src/lib/quad-screen.tsx.
//
//   import track from '../shots/tempelan/track-scene-15.json';
//
//   <QuadScreenTracked track={track} dw={1280} dh={860} from={0.4} until={5.6}>
//     <YourPanel />
//   </QuadScreenTracked>
//
// dw/dh are the panel's own design size in px. Author the panel at that size and let the
// homography do the fitting — do not pre-scale it to the screen.
//
// When NOT to use this at all: a surface under ~120px wide, or one that faces away from the
// camera. A panel composited onto a screen the actor is looking at renders BEHIND the device
// and reads as a sticker. Use a floating card instead. `track_screen.py` exits 2 in the first
// case so the decision is not left to taste.

import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';

const CLAMP = { extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const };

export type Corner = { x: number; y: number };
export type Quad = [Corner, Corner, Corner, Corner];

/** Track file written by tools/track_screen.py. Corners are clockwise from top-left. */
export type ScreenTrack = {
  clip?: string;
  width?: number;
  height?: number;
  keys: { t: number; corners: [number, number][] }[];
};

/** Solve an n x n linear system by Gaussian elimination with partial pivoting. */
function solve(A: number[][], b: number[]): number[] {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let k = 0; k < n; k += 1) {
    let p = k;
    for (let i = k + 1; i < n; i += 1) if (Math.abs(M[i][k]) > Math.abs(M[p][k])) p = i;
    [M[k], M[p]] = [M[p], M[k]];
    for (let i = k + 1; i < n; i += 1) {
      const f = M[i][k] / M[k][k];
      for (let j = k; j <= n; j += 1) M[i][j] -= f * M[k][j];
    }
  }
  const x = new Array(n).fill(0);
  for (let i = n - 1; i >= 0; i -= 1) {
    let s = M[i][n];
    for (let j = i + 1; j < n; j += 1) s -= M[i][j] * x[j];
    x[i] = s / M[i][i];
  }
  return x;
}

/** CSS matrix3d mapping a w x h rectangle onto four destination corners (clockwise from TL). */
export function matrix3dTo(w: number, h: number, dst: Quad): string {
  const src: Corner[] = [{ x: 0, y: 0 }, { x: w, y: 0 }, { x: w, y: h }, { x: 0, y: h }];
  const A: number[][] = [];
  const b: number[] = [];
  for (let i = 0; i < 4; i += 1) {
    const { x, y } = src[i];
    const { x: u, y: v } = dst[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
  }
  const [a1, a2, a3, a4, a5, a6, a7, a8] = solve(A, b);
  // matrix3d takes its arguments column by column.
  return `matrix3d(${a1}, ${a4}, 0, ${a7}, ${a2}, ${a5}, 0, ${a8}, 0, 0, 1, 0, ${a3}, ${a6}, 0, 1)`;
}

const Mapped: React.FC<{
  corners: Quad; dw: number; dh: number; opacity: number; children: React.ReactNode;
}> = ({ corners, dw, dh, opacity, children }) => (
  <div
    style={{
      position: 'absolute', left: 0, top: 0, width: dw, height: dh,
      transform: matrix3dTo(dw, dh, corners), transformOrigin: '0 0',
      overflow: 'hidden', opacity,
    }}
  >
    {children}
  </div>
);

function fade(t: number, from: number, until?: number): number {
  const rise = interpolate(t, [from, from + 0.35], [0, 1], CLAMP);
  const fall = until === undefined ? 1 : interpolate(t, [until, until + 0.35], [1, 0], CLAMP);
  return rise * fall;
}

/** Fixed screen: four corners measured once, for a genuinely locked-off camera. */
export const QuadScreen: React.FC<{
  corners: Quad; dw: number; dh: number; from: number; until?: number; children: React.ReactNode;
}> = ({ corners, dw, dh, from, until, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = fade(frame / fps, from, until);
  if (opacity <= 0) return null;
  return <Mapped corners={corners} dw={dw} dh={dh} opacity={opacity}>{children}</Mapped>;
};

/**
 * Moving screen: corners are interpolated between the samples in a track file.
 *
 * Use this by default. Platform clips drift even when the prompt says locked-off — one measured
 * case moved the screen box from x=80 to x=44 and widened it 256 -> 272px across 8 seconds, and
 * a push-in changes the trapezoid's shape, not just its size.
 */
export const QuadScreenTracked: React.FC<{
  track: ScreenTrack; dw: number; dh: number; from: number; until?: number;
  children: React.ReactNode;
}> = ({ track, dw, dh, from, until, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const opacity = fade(t, from, until);
  if (opacity <= 0) return null;
  if (!track.keys?.length) throw new Error('QuadScreenTracked: track file has no keys');

  let i = 0;
  while (i < track.keys.length - 2 && track.keys[i + 1].t < t) i += 1;
  const a = track.keys[i];
  const b = track.keys[Math.min(i + 1, track.keys.length - 1)];
  const k = b.t === a.t ? 0 : Math.min(1, Math.max(0, (t - a.t) / (b.t - a.t)));
  const corners = a.corners.map((p, j) => ({
    x: p[0] + (b.corners[j][0] - p[0]) * k,
    y: p[1] + (b.corners[j][1] - p[1]) * k,
  })) as Quad;

  return <Mapped corners={corners} dw={dw} dh={dh} opacity={opacity}>{children}</Mapped>;
};
