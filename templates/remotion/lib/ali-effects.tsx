// Presenter-video effects distilled from the REA film. Props only: no scene ids, no project paths.
// NOT a shot (no compositionConfig, lives outside src/shots). Frame-based; every start frame is a prop.
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';

const out = Easing.bezier(0.16, 1, 0.3, 1);
const io = Easing.bezier(0.65, 0, 0.35, 1);
const seg = (f: number, a: number, b: number, e: (t: number) => number = out) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: e });
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const FONT = "'Helvetica Neue', Arial, sans-serif";

// ---- Follow popup: avatar + handle + FOLLOW button, a cursor clicks it, it turns to "Mengikuti" ----
export const FollowModal: React.FC<{
  handle: string;
  avatar: string;            // staticFile path, e.g. 'ref/avatar.png'
  popAt: number;             // frame the card drops in
  clickAt: number;           // frame of the click
  top?: number;              // card top (1080x1920 frame). Centre of screen = ~845
  doneLabel?: string;
}> = ({ handle, avatar, popAt, clickAt, top = 845, doneLabel = 'Mengikuti' }) => {
  const f = useCurrentFrame();
  const pop = seg(f, popAt, popAt + 14);
  const done = f >= clickAt + 3;
  const press = seg(f, clickAt - 2, clickAt + 3);
  const cur = seg(f, popAt + 10, clickAt - 2, io);
  const bx = 800, by = top + 108;                        // centre of the FOLLOW button
  const cx = lerp(930, bx + 20, cur), cy = lerp(top + 405, by + 22, cur);
  const ring = seg(f, clickAt, clickAt + 14);
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: 90, top, width: 900, height: 230, borderRadius: 40, background: 'rgba(255,255,255,0.96)', boxShadow: '0 30px 80px rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', gap: 30, padding: '0 36px', fontFamily: FONT, opacity: pop, transform: `translateY(${(1 - pop) * -50}px) scale(${lerp(0.9, 1, pop)})` }}>
        <div style={{ width: 150, height: 150, borderRadius: 75, padding: 6, background: 'linear-gradient(45deg,#f9ce34,#ee2a7b,#6228d7)', flex: 'none' }}>
          <Img src={staticFile(avatar)} style={{ width: 138, height: 138, borderRadius: 69, border: '5px solid #fff', objectFit: 'cover' }} />
        </div>
        <div style={{ flex: 1, minWidth: 0, fontSize: 44, fontWeight: 800, color: '#111' }}>{handle}</div>
        <div style={{ width: 230, height: 84, borderRadius: 18, background: done ? '#e6e8ea' : '#0095f6', color: done ? '#111' : '#fff', fontSize: 38, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${1 - 0.06 * Math.sin(press * Math.PI)})` }}>
          {done ? doneLabel : 'FOLLOW'}
        </div>
      </div>
      {f >= popAt + 10 && (
        <>
          <div style={{ position: 'absolute', left: bx - 35, top: by - 18, width: 80, height: 80, borderRadius: 40, border: '5px solid #0095f6', opacity: ring > 0 ? 1 - ring : 0, transform: `scale(${0.4 + 1.2 * ring})` }} />
          <svg width="70" height="70" viewBox="0 0 24 24" style={{ position: 'absolute', left: cx, top: cy, filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.5))', transform: `scale(${1 - 0.12 * Math.sin(press * Math.PI)})` }}><path d="M5 3 L5 19 L9.5 15 L12.5 21 L15 20 L12 14 L18 14 Z" fill="#111" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round" /></svg>
        </>
      )}
    </AbsoluteFill>
  );
};

// ---- "Ssst!" coming out of the mouth: three sound arcs and a word that grows and drifts away ----
export const ShushEffect: React.FC<{
  mouthX: number; mouthY: number; startAt: number; endAt: number;
  toX?: number; toY?: number; accent?: string; label?: string;
}> = ({ mouthX, mouthY, startAt, endAt, toX = mouthX - 285, toY = mouthY + 125, accent = '#4fd1d0', label = 'Ssst!' }) => {
  const f = useCurrentFrame();
  if (f < startAt) return null;
  const span = endAt - startAt;
  const t = seg(f, startAt, startAt + span * 0.8);
  const fade = 1 - seg(f, startAt + span * 0.7, endAt);
  const x = lerp(mouthX - 40, toX, t), y = lerp(mouthY - 10, toY, t);
  const sc = lerp(0.3, 1.15, seg(f, startAt, startAt + span * 0.4));
  return (
    <AbsoluteFill>
      <svg width="1080" height="1920" style={{ position: 'absolute', left: 0, top: 0, opacity: fade }}>
        {[0, 1, 2].map((i) => {
          const p = seg(f, startAt + i * 4, startAt + 16 + i * 4);
          const r = 40 + 55 * i + 60 * p;
          return <path key={i} d={`M ${mouthX - 30 - r * 0.6} ${mouthY - r * 0.8} A ${r} ${r} 0 0 0 ${mouthX - 30 - r * 0.6} ${mouthY + r * 0.8}`} fill="none" stroke="#ffffff" strokeWidth={7 - i * 1.5} strokeLinecap="round" opacity={p > 0 ? 0.85 * (1 - p) : 0} style={{ filter: `drop-shadow(0 0 10px ${accent})` }} />;
        })}
      </svg>
      <div style={{ position: 'absolute', left: x - 260, top: y - 90, width: 520, textAlign: 'center', fontFamily: FONT, fontSize: 150, fontWeight: 900, color: '#fff', letterSpacing: 4, opacity: fade, transform: `rotate(${lerp(-4, 8, t)}deg) scale(${sc})`, textShadow: `0 0 28px ${accent}, 0 6px 0 rgba(0,0,0,0.5)`, WebkitTextStroke: '3px #04282a' }}>{label}</div>
    </AbsoluteFill>
  );
};

// ---- "WOW!" surprise: white flash, ray burst, ring, shaking word. Put it OVER the clip. ----
export const WowBurst: React.FC<{
  centerX: number; centerY: number; startAt: number;
  textTop?: number; accent?: string; label?: string; holdFrames?: number;
}> = ({ centerX, centerY, startAt, textTop = 520, accent = '#4fd1d0', label = 'WOW!', holdFrames = 60 }) => {
  const f = useCurrentFrame();
  const a = startAt;
  const flash = f >= a && f < a + 8 ? 1 - (f - a) / 8 : 0;
  const burst = seg(f, a, a + 22);
  const pop = seg(f, a + 4, a + 16);
  const out_ = 1 - seg(f, a + holdFrames, a + holdFrames + 18);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: `rgba(220,250,255,${0.55 * flash})` }} />
      {f >= a && (
        <>
          <svg width="1080" height="1920" style={{ position: 'absolute', left: 0, top: 0, opacity: out_ }}>
            {Array.from({ length: 16 }, (_, i) => {
              const ang = (i / 16) * Math.PI * 2, r0 = 90 + 40 * burst, r1 = r0 + 160 + (i % 2) * 90;
              return <line key={i} x1={centerX + Math.cos(ang) * r0} y1={centerY + Math.sin(ang) * r0} x2={centerX + Math.cos(ang) * (r0 + (r1 - r0) * burst)} y2={centerY + Math.sin(ang) * (r0 + (r1 - r0) * burst)} stroke={i % 2 ? '#ffffff' : accent} strokeWidth={i % 2 ? 6 : 10} strokeLinecap="round" opacity={1 - burst * 0.4} style={{ filter: `drop-shadow(0 0 12px ${accent})` }} />;
            })}
            <circle cx={centerX} cy={centerY} r={30 + 420 * burst} fill="none" stroke="#e8ffff" strokeWidth={8 * (1 - burst)} opacity={1 - burst} />
          </svg>
          <div style={{ position: 'absolute', left: 90, top: textTop, width: 900, textAlign: 'center', fontFamily: FONT, fontSize: 230, fontWeight: 900, color: '#fff', opacity: out_ * pop, transform: `scale(${lerp(0.2, 1, pop) + 0.06 * Math.sin(f / 3)}) rotate(${lerp(-12, -6, pop)}deg)`, textShadow: `0 0 50px ${accent}, 0 10px 0 rgba(0,0,0,0.55)`, WebkitTextStroke: '4px #04282a' }}>{label}</div>
        </>
      )}
    </AbsoluteFill>
  );
};

// ---- Thumbnail: photo, bottom scrim, a blurred "mystery" blob, headline + pill. Keep text above y 1540. ----
export const ThumbCover: React.FC<{
  photo: string;                         // staticFile path
  line1: string; line2: string; pill?: string;
  accent?: string;
  blur?: { x: number; y: number; size: number; amount?: number; html: React.ReactNode } | null;
  titleTop?: number;
}> = ({ photo, line1, line2, pill, accent = '#4fd1d0', blur = null, titleTop = 1165 }) => (
  <AbsoluteFill style={{ backgroundColor: '#05090a' }}>
    <Img src={staticFile(photo)} style={{ width: 1080, height: 1920, objectFit: 'cover' }} />
    <AbsoluteFill style={{ background: 'linear-gradient(180deg, rgba(0,0,0,0) 52%, rgba(3,9,10,0.82) 72%, rgba(3,9,10,0.92) 100%)' }} />
    {blur && (
      <>
        <div style={{ position: 'absolute', left: blur.x, top: blur.y, width: blur.size, height: blur.size, filter: `blur(${blur.amount ?? 15}px)` }}>{blur.html}</div>
        <div style={{ position: 'absolute', left: blur.x, top: blur.y, width: blur.size, height: blur.size, borderRadius: blur.size / 2, boxShadow: `0 0 60px 20px ${accent}40` }} />
      </>
    )}
    <div style={{ position: 'absolute', left: 60, top: titleTop, width: 960, fontFamily: FONT, fontWeight: 900, textTransform: 'uppercase', lineHeight: 0.98, textShadow: '0 8px 30px rgba(0,0,0,0.6)' }}>
      <div style={{ fontSize: 130, color: '#fff', letterSpacing: -2 }}>{line1}</div>
      <div style={{ fontSize: 88, color: accent, letterSpacing: -1 }}>{line2}</div>
      {pill && <div style={{ marginTop: 22, display: 'inline-block', background: '#fff', color: '#06100f', fontSize: 64, fontWeight: 800, textTransform: 'none', padding: '10px 28px', borderRadius: 16 }}>{pill}</div>}
    </div>
  </AbsoluteFill>
);
