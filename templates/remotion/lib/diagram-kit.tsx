// Line-art diagram pieces for technical explainer shots (dark background, arrows, labels).
// NOT a shot. Props only; frame-based. Colours come from brand.json through ./brand.
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { COLORS, FONT_BODY, FONT_DISPLAY } from './brand';
import { smooth } from './diagramFx.mjs';

export { durationFrames, wordFrame, findWordFrame, smooth } from './diagramFx.mjs';

/** Flat dark backdrop with a faint grid. */
export const DiagramBg: React.FC = () => (
  <>
    <AbsoluteFill style={{ backgroundColor: COLORS.paper }} />
    <AbsoluteFill style={{ backgroundImage: `linear-gradient(${COLORS.line} 1px, transparent 1px), linear-gradient(90deg, ${COLORS.line} 1px, transparent 1px)`, backgroundSize: '90px 90px', opacity: 0.18 }} />
  </>
);

/** Straight arrow from (x1,y1) to (x2,y2) that draws itself between frames [a,b]. Lives in a 1080x1920 SVG layer. */
export const Arrow: React.FC<{
  x1: number; y1: number; x2: number; y2: number; a: number; b: number;
  color?: string; width?: number; head?: number; dashed?: boolean; fadeOutAt?: number;
}> = ({ x1, y1, x2, y2, a, b, color = COLORS.ink, width = 10, head = 36, dashed = false, fadeOutAt }) => {
  const f = useCurrentFrame();
  const t = smooth(f, a, b);
  if (t <= 0) return null;
  const ex = x1 + (x2 - x1) * t, ey = y1 + (y2 - y1) * t;
  const ang = Math.atan2(y2 - y1, x2 - x1);
  const hx = (k: number) => ex - Math.cos(ang + k) * head, hy = (k: number) => ey - Math.sin(ang + k) * head;
  const op = fadeOutAt === undefined ? 1 : 1 - smooth(f, fadeOutAt, fadeOutAt + 8);
  return (
    <svg width={1080} height={1920} style={{ position: 'absolute', left: 0, top: 0, opacity: op }}>
      <line x1={x1} y1={y1} x2={ex - Math.cos(ang) * head * 0.6} y2={ey - Math.sin(ang) * head * 0.6} stroke={color} strokeWidth={width} strokeLinecap="round" strokeDasharray={dashed ? '22 16' : undefined} />
      <polygon points={`${ex},${ey} ${hx(0.42)},${hy(0.42)} ${hx(-0.42)},${hy(-0.42)}`} fill={color} />
    </svg>
  );
};

/** Text chip that pops in at frame `at`. (x,y) = top-left, width fixed so text stays inside the frame. */
export const Tag: React.FC<{
  text: string; x: number; y: number; at: number; w?: number; size?: number;
  color?: string; bg?: string; align?: 'left' | 'center'; display?: boolean; fadeOutAt?: number;
}> = ({ text, x, y, at, w = 520, size = 52, color = COLORS.ink, bg, align = 'left', display = true, fadeOutAt }) => {
  const f = useCurrentFrame();
  const p = smooth(f, at, at + 8);
  const out = fadeOutAt === undefined ? 1 : 1 - smooth(f, fadeOutAt, fadeOutAt + 8);
  if (p <= 0) return null;
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, textAlign: align, fontFamily: display ? FONT_DISPLAY : FONT_BODY, fontWeight: 800, fontSize: size, lineHeight: 1.05, color, letterSpacing: 1, background: bg, padding: bg ? '10px 22px' : 0, borderRadius: 14, opacity: p * out, transform: `translateY(${interpolate(p, [0, 1], [14, 0])}px)`, boxSizing: 'border-box' }}>{text}</div>
  );
};
