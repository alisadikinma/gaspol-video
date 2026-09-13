// Shared building blocks for shots. NOT a shot itself (no compositionConfig,
// and it lives outside src/shots so gen-registry never scans it). Keeps every
// explainer shot on one consistent look. Frame-based only; monotonic
// interpolate + clamp.
import React from 'react';
import {
  AbsoluteFill, interpolate, Img, useCurrentFrame,
} from 'remotion';
import {
  COLORS, EASINGS, FONT_BODY, FONT_DISPLAY, FONT_MONO, RADIUS, SHADOW,
} from './brand';

export const CLAMP = { extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const };

// ---- brand backdrop: paper + soft color glow + faint dotted grid -------------
export const BrandBg: React.FC<{ glow?: string }> = ({ glow = COLORS.accent }) => (
  <>
    <AbsoluteFill style={{ backgroundColor: COLORS.paper }} />
    <AbsoluteFill style={{ background: `radial-gradient(1300px 700px at 50% -12%, ${glow}22, transparent 60%)` }} />
    <AbsoluteFill style={{ backgroundImage: `radial-gradient(${COLORS.line} 1.5px, transparent 1.5px)`, backgroundSize: '46px 46px', opacity: 0.45 }} />
  </>
);

// rise-in (fade + translateY), driven by the current frame
export const useRise = () => {
  const frame = useCurrentFrame();
  return (start: number, dist = 24, dur = 14) => ({
    opacity: interpolate(frame, [start, start + dur], [0, 1], { ...CLAMP, easing: EASINGS.easeOut }),
    transform: `translateY(${interpolate(frame, [start, start + dur], [dist, 0], { ...CLAMP, easing: EASINGS.easeOut })}px)`,
  });
};

// Inline 24x24 checkmark — no icon package dependency.
const CheckIcon: React.FC<{ size?: number; color?: string; strokeWidth?: number }> = ({
  size = 24, color = 'currentColor', strokeWidth = 2,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

// =============================================================================
// Full-screen image reveal (the real generated asset in a framed card)
// =============================================================================
export const ImageRevealShot: React.FC<{
  src: string; tag: string; title: string; subtitle?: string;
  color: string; boxW?: number; boxH?: number;
}> = ({ src, tag, title, subtitle, color, boxW = 760, boxH = 760 }) => {
  const frame = useCurrentFrame();
  const rise = useRise();
  const imgScale = interpolate(frame, [8, 30], [0.92, 1], { ...CLAMP, easing: EASINGS.easeOut });
  const imgOp = interpolate(frame, [8, 26], [0, 1], { ...CLAMP, easing: EASINGS.easeOut });
  return (
    <AbsoluteFill style={{ fontFamily: FONT_BODY }}>
      <BrandBg glow={color} />
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', gap: 30 }}>
        {/* eyebrow tag */}
        <div style={{ ...rise(2, 14), display: 'flex', alignItems: 'center', gap: 12, background: `${color}16`, border: `1px solid ${color}44`, borderRadius: RADIUS.pill, padding: '10px 22px' }}>
          <div style={{ width: 24, height: 24, borderRadius: '50%', background: color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CheckIcon size={15} color={COLORS.onAccent} strokeWidth={3.4} />
          </div>
          <span style={{ fontFamily: FONT_MONO, fontSize: 22, letterSpacing: 1.5, color, fontWeight: 500 }}>{tag}</span>
        </div>
        {/* image card */}
        <div style={{ width: boxW, height: boxH, borderRadius: RADIUS.card, overflow: 'hidden', border: `1px solid ${COLORS.line}`, boxShadow: SHADOW.card, background: COLORS.cream, opacity: imgOp, transform: `scale(${imgScale})` }}>
          <Img src={src} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
        {/* caption */}
        <div style={{ ...rise(20, 16), textAlign: 'center' }}>
          <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: 42, color: COLORS.ink }}>{title}</div>
          {subtitle && <div style={{ fontSize: 30, color: COLORS.muted, marginTop: 6 }}>{subtitle}</div>}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
