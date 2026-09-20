// Title card composition for gaspol-video Phase 6 Pass 4.1 (GV-7 Phase D).
//
// Rendered once PER SCENE whose scene-plan.md `Title Card` column is not `—`. Edit CARD
// below to that scene's side/eyebrow/title (parsed by tools/gen_captions.py from the cell
// `left: <eyebrow> / <title>` or `right: <eyebrow> / <title>`), render `TitleCard`, then
// composite it over the master at that scene's start with
//   python3 tools/composite.py overlay {master} {shot}.mov --at {scene_start_s} --out-s 2.5 -o {out}
// — see skills/video-post/SKILL.md Pass 4.1. compositionConfig.id and the exported component
// name stay exactly `TitleCard`.
//
// Same non-negotiable rules as Shot.template.tsx and Captions.template.tsx:
//   * frame-based animation ONLY: no React state or lifecycle hooks that persist between
//     frames, no timers, no unseeded randomness — Remotion renders frames out of order and
//     in parallel processes.
//   * interpolate input ranges strictly increasing.
//   * Easing.bezier called directly, never wrapped.
//   * compositionConfig.id in PascalCase, no hyphens, no underscores.
//   * colours and fonts come from brand.json. This plugin ships NO palette: the look
//     belongs to the client, not to the tool.
//
// HOLD_S matches tools/gen_captions.py's TITLE_CARD_HOLD_S / captions_held_until_s for this
// scene (2.5s, or the scene's own length when shorter) — the same window gen_captions.py
// already pushes caption words out of, so the card and the kinetic captions never compete
// for the same reading order.

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
  id: 'TitleCard',
  width: 1920,
  height: 1080,
  fps: 30,
  durationInFrames: 75,        // set to ceil(HOLD_S * fps) for this scene
  // Placed with `composite.py overlay`, which refuses a shot without a real alpha
  // channel. Without this the render is opaque and blacks out the picture it was
  // meant to sit on. See reference/post-production/12-remotion-explainer.md.
  transparent: true,
};

// =============================================================================
// CARD — replace with this render's entry from scene-plan.md's Title Card column
// =============================================================================
const CARD = {
  side: 'left',                 // 'left' | 'right' — declared in scene-plan.md, never guessed here
  eyebrow: 'Grafik Depresiasi',
  title: 'Mobil Listrik',
};

// Matches tools/gen_captions.py's captions_held_until_s for this scene: 2.5, or the scene's
// own length when shorter. The card animates in, holds, then animates out inside this span.
const HOLD_S = 2.5;
const IN_S = 0.5;
const OUT_S = 0.4;
const LINE_STAGGER_S = 0.15;

const MIN_BODY_PX = 32;
const SAFE_MARGIN_PCT = 5;

// =============================================================================
// HELPERS
// =============================================================================
const useLineReveal = (delaySeconds: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inStart = delaySeconds * fps;
  const inEnd = inStart + IN_S * fps;
  const outStart = (HOLD_S - OUT_S) * fps;
  const outEnd = HOLD_S * fps;
  // Strictly increasing input range across in -> hold -> out.
  return interpolate(
    frame,
    [inStart, inEnd, outStart, outEnd],
    [0, 1, 1, 0],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    },
  );
};

// =============================================================================
// TITLE CARD
// =============================================================================
export const TitleCard: React.FC = () => {
  const eyebrow = useLineReveal(0);
  const title = useLineReveal(LINE_STAGGER_S);

  const isRight = CARD.side === 'right';
  const alignItems = isRight ? 'flex-end' : 'flex-start';
  const textAlign: 'left' | 'right' = isRight ? 'right' : 'left';

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          padding: `${SAFE_MARGIN_PCT}%`,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems,
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems,
            gap: 14,
            width: '33%',
            marginLeft: isRight ? '67%' : 0,
          }}
        >
          <div
            style={{
              fontFamily: brand.bodyFont,
              fontSize: Math.max(MIN_BODY_PX, 34),
              letterSpacing: '0.16em',
              textTransform: 'uppercase',
              fontWeight: 700,
              color: brand.accent,
              textAlign,
              opacity: eyebrow,
              transform: `translateY(${(1 - eyebrow) * 16}px)`,
            }}
          >
            {CARD.eyebrow}
          </div>
          <div
            style={{
              fontFamily: brand.displayFont,
              fontSize: Math.max(MIN_BODY_PX, 72),
              fontWeight: 700,
              lineHeight: 1.08,
              color: brand.ink,
              textAlign,
              opacity: title,
              transform: `translateY(${(1 - title) * 16}px)`,
            }}
          >
            {CARD.title}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export default TitleCard;
