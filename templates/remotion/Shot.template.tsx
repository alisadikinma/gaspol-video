// Explainer shot template for gaspol-video Phase 4.5.
//
// Copy this file, rename the component and the compositionConfig id to match, and replace
// the content. The structure is not decoration: every rule it follows is one that stops a
// render crashing or a caption becoming unreadable.
//
//   * frame-based animation ONLY. No useState, no useEffect, no setTimeout, no unseeded
//     Math.random. Remotion renders frames out of order and in parallel processes; anything
//     that remembers between frames produces a different video every time.
//   * interpolate input ranges strictly increasing.
//   * Easing.bezier called directly, never wrapped.
//   * compositionConfig.id in PascalCase. No hyphens, no underscores.
//   * colours and fonts come from brand.json, written from the project's strategic-brief.md.
//     This plugin ships NO palette: the look belongs to the client, not to the tool.

import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

import brand from './brand.json';

// =============================================================================
// COMPOSITION CONFIG
// =============================================================================
export const compositionConfig = {
  id: 'MetricReveal',          // PascalCase, matches the file name
  width: 1920,
  height: 1080,
  fps: 30,
  durationInFrames: 150,       // set from the narration length in vo-manifest.json
};

// =============================================================================
// CUE TIMES
// =============================================================================
// Seconds from the shot's own start, taken from vo-manifest.json word timings so each
// element appears exactly when it is said. Never show a thing before it is spoken.
const CUES = {
  eyebrow: 0.2,
  headline: 0.8,
  statOne: 2.4,
  statTwo: 3.1,
  statThree: 4.2,
};

// Legibility floors from global-promo-config.md §29.5. These are not style choices.
const MIN_BODY_PX = 32;
const MIN_HEADLINE_PX = 64;
const SAFE_MARGIN_PCT = 5;

// =============================================================================
// HELPERS
// =============================================================================
const useReveal = (atSeconds: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = atSeconds * fps;
  // Strictly increasing input range, and clamped so nothing drifts past its end state.
  return interpolate(frame, [start, start + 0.35 * fps], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
};

const Stat: React.FC<{ value: string; unit: string; label: string; at: number }> = ({
  value,
  unit,
  label,
  at,
}) => {
  const t = useReveal(at);
  return (
    <div style={{ flex: 1, opacity: t, transform: `translateY(${(1 - t) * 16}px)` }}>
      <div style={{ borderTop: `2px solid ${brand.accent}`, paddingTop: 18 }}>
        <span
          style={{
            fontFamily: brand.displayFont,
            fontSize: 120,
            fontWeight: 700,
            color: brand.ink,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {value}
        </span>
        <span style={{ fontFamily: brand.bodyFont, fontSize: 44, color: brand.inkSoft }}>
          {' '}
          {unit}
        </span>
        <div
          style={{
            fontFamily: brand.bodyFont,
            fontSize: Math.max(MIN_BODY_PX, 34),
            color: brand.inkSoft,
            marginTop: 10,
          }}
        >
          {label}
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// SHOT
// =============================================================================
export const MetricReveal: React.FC = () => {
  const eyebrow = useReveal(CUES.eyebrow);
  const headline = useReveal(CUES.headline);

  return (
    <AbsoluteFill style={{ backgroundColor: brand.background }}>
      <AbsoluteFill
        style={{
          padding: `${SAFE_MARGIN_PCT}%`,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          gap: 28,
        }}
      >
        <div
          style={{
            fontFamily: brand.bodyFont,
            fontSize: Math.max(MIN_BODY_PX, 32),
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            fontWeight: 700,
            color: brand.accent,
            opacity: eyebrow,
          }}
        >
          Sebelum sistem dipasang
        </div>

        <div
          style={{
            fontFamily: brand.displayFont,
            fontSize: Math.max(MIN_HEADLINE_PX, 96),
            lineHeight: 1.06,
            fontWeight: 700,
            color: brand.ink,
            maxWidth: '72%',
            opacity: headline,
            transform: `translateY(${(1 - headline) * 20}px)`,
          }}
        >
          Tiap truk antre 42 menit di gerbang
        </div>

        <div style={{ display: 'flex', gap: '4%', marginTop: 12 }}>
          <Stat value="42" unit="menit" label="rata-rata antre" at={CUES.statOne} />
          <Stat value="7" unit="jam/hari" label="waktu hilang" at={CUES.statTwo} />
          <Stat value="0" unit="data" label="tidak tercatat" at={CUES.statThree} />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export default MetricReveal;
