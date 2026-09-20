// Kinetic caption composition for gaspol-video Phase 6 Pass 4.1 (GV-7 Phase C).
//
// Unlike Shot.template.tsx (one file per shot, its own id), this template is rendered
// once PER SCENE that needs captions: edit SCENE and STYLE below to that scene's entry
// from work/caption-plan.json (`tools/gen_captions.py`), render `KineticCaptions`,
// composite it over the master at that scene's offset_s, then edit SCENE again for the
// next scene. compositionConfig.id and the exported component name stay exactly
// `KineticCaptions` — see skills/video-post/SKILL.md Pass 4.1.
//
// Same non-negotiable rules as Shot.template.tsx:
//   * frame-based animation ONLY: no React state or lifecycle hooks that persist
//     between frames, no timers, no unseeded randomness — Remotion renders frames out
//     of order and in parallel processes.
//   * interpolate input ranges strictly increasing.
//   * Easing.bezier called directly, never wrapped.
//   * compositionConfig.id in PascalCase, no hyphens, no underscores.
//   * colours and fonts come from brand.json. This plugin ships NO palette.
//
// Page/word/highlight arithmetic lives in ./lib/captionPages.mjs, which has ZERO
// imports on purpose (this repo has no node_modules and deliberately no npm — see
// that file's header) and is unit-tested directly by tests/node/caption-pages.test.mjs
// with no install needed. The one call that actually needs @remotion/captions —
// createTikTokStyleCaptions() — happens ONLY here, between toCaptionRecords() and
// partitionPages(): this file is a template copied into a project's shots/ workspace,
// where the dependency is installed (scaffold.mjs adds it to package.json), and it is
// never executed by this repo's own test suite.
//
// @remotion/captions' Caption.text carries its own LEADING whitespace, which is why the
// text below renders with `whiteSpace: 'pre'` — without it, a page's concatenated
// words would visually merge into one run.

import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { createTikTokStyleCaptions } from '@remotion/captions';

import brand from './brand.json';
import { toCaptionRecords, partitionPages } from './lib/captionPages.mjs';

// =============================================================================
// COMPOSITION CONFIG
// =============================================================================
export const compositionConfig = {
  id: 'KineticCaptions',
  width: 1920,
  height: 1080,
  fps: 30,
  durationInFrames: 150,      // set to ceil(last word's end_ms / 1000 * fps) for this scene
  // Placed with `composite.py overlay`, which refuses a shot without a real alpha
  // channel. Without this the render is opaque and blacks out the picture it was
  // meant to sit on. See reference/post-production/12-remotion-explainer.md.
  transparent: true,
};

// Legibility floors from global-promo-config.md §29.5 / work/caption-plan.json `style`.
const MIN_BODY_PX = 32;
const SAFE_MARGIN_PCT = 5;

// =============================================================================
// SCENE + STYLE — replace with this render's entry from work/caption-plan.json
// =============================================================================
const SCENE = {
  scene: 12,
  words: [
    { text: 'Truk', start_ms: 0, end_ms: 260 },
    { text: 'antre', start_ms: 260, end_ms: 560 },
    { text: '42', start_ms: 560, end_ms: 780 },
    { text: 'menit', start_ms: 780, end_ms: 1100 },
    { text: 'tiap', start_ms: 1100, end_ms: 1360 },
    { text: 'hari', start_ms: 1360, end_ms: 1700 },
  ],
  highlights: [{ start_word: 2, end_word: 3, score: 9, rule: 'number-unit' }],
};

// `highlight_text_token` is written by tools/gen_captions.py's check_brand_contrast():
// whichever of "ink"/"background" reads at 3:1 or better against `accent` — the
// component reads that decision rather than making one (see Phase C plan doc).
const STYLE = {
  combine_tokens_within_ms: 400,
  max_lines: 3,
  min_body_px: MIN_BODY_PX,
  safe_margin_pct: SAFE_MARGIN_PCT,
  highlight_text_token: 'background',
};

const { pages: TIKTOK_PAGES } = createTikTokStyleCaptions({
  captions: toCaptionRecords(SCENE),
  combineTokensWithinMilliseconds: STYLE.combine_tokens_within_ms,
});
const CAPTION_PAGES = partitionPages(TIKTOK_PAGES, SCENE);
const HIGHLIGHT_TEXT_COLOR = brand[STYLE.highlight_text_token] || brand.ink;

// =============================================================================
// HELPERS
// =============================================================================
const useReveal = (atMs: number, holdMs: number = 220) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = (atMs / 1000) * fps;
  // Strictly increasing input range, clamped so nothing drifts past its end state.
  return interpolate(frame, [start, start + (holdMs / 1000) * fps], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
};

const activePageIndex = (frameMs: number) => {
  for (let i = 0; i < CAPTION_PAGES.length; i += 1) {
    const page = CAPTION_PAGES[i];
    const end = page.startMs + (Number.isFinite(page.durationMs) ? page.durationMs : Infinity);
    if (frameMs >= page.startMs && frameMs < end) return i;
  }
  // Before the first page, or after the last one has fully played: hold on the
  // nearest page rather than drawing nothing.
  if (CAPTION_PAGES.length === 0) return -1;
  return frameMs < CAPTION_PAGES[0].startMs ? 0 : CAPTION_PAGES.length - 1;
};

// =============================================================================
// WORD + HIGHLIGHT
// =============================================================================
const Word: React.FC<{ text: string; startMs: number; highlight: boolean }> = ({
  text,
  startMs,
  highlight,
}) => {
  const reveal = useReveal(startMs, 180);
  const boxGrow = useReveal(startMs, 260);
  return (
    <span
      style={{
        position: 'relative',
        display: 'inline-block',
        opacity: reveal,
        transform: `translateY(${(1 - reveal) * 14}px)`,
        marginRight: '0.32em',
      }}
    >
      {highlight && (
        <span
          style={{
            position: 'absolute',
            inset: '-2% -6%',
            backgroundColor: brand.accent,
            transform: `scaleX(${boxGrow})`,
            transformOrigin: 'left center',
            zIndex: 0,
            borderRadius: 6,
          }}
        />
      )}
      <span style={{ position: 'relative', zIndex: 1, color: highlight ? HIGHLIGHT_TEXT_COLOR : undefined }}>
        {text}
      </span>
    </span>
  );
};

// =============================================================================
// CAPTIONS
// =============================================================================
export const KineticCaptions: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const frameMs = (frame / fps) * 1000;

  const index = activePageIndex(frameMs);
  const activePage = index >= 0 ? CAPTION_PAGES[index] : null;
  const contextLines = index > 0
    ? CAPTION_PAGES.slice(Math.max(0, index - (STYLE.max_lines - 1)), index).map((p) => p.text)
    : [];

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          padding: `${SAFE_MARGIN_PCT}%`,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'flex-end',
          alignItems: 'flex-start',
          gap: 10,
        }}
      >
        {activePage
          && contextLines.map((lineText, i) => (
            <div
              // eslint-disable-next-line react/no-array-index-key
              key={`context-${index}-${i}`}
              style={{
                fontFamily: brand.bodyFont,
                fontSize: Math.max(MIN_BODY_PX, 40),
                color: brand.inkSoft,
                opacity: 0.55,
                whiteSpace: 'pre',
              }}
            >
              {lineText}
            </div>
          ))}

        {activePage && (
          <div
            style={{
              fontFamily: brand.displayFont,
              fontWeight: 700,
              fontSize: Math.max(MIN_BODY_PX, 56),
              color: brand.ink,
              whiteSpace: 'pre',
              lineHeight: 1.15,
            }}
          >
            {activePage.words.map((word, i) => (
              <Word
                // eslint-disable-next-line react/no-array-index-key
                key={`${index}-${i}-${word.text}`}
                text={word.text}
                startMs={word.startMs}
                highlight={word.highlight}
              />
            ))}
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export default KineticCaptions;
