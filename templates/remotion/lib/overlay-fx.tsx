// Building blocks of the kinetic overlay (GV-17 Phase F): text, icons, panels, bubbles,
// carousel and source box. Every number that moves comes from ./overlayFx.mjs (pure maths,
// unit-tested); this file only turns those numbers into CSS and SVG.
//
// Same non-negotiable rules as the shot templates:
//   * frame-based animation ONLY: no React state or lifecycle hooks, no timers, no unseeded
//     randomness. Remotion renders frames out of order and in parallel processes.
//   * interpolate input ranges strictly increasing (this file does not need interpolate).
//   * colours and fonts come from ./brand.ts, which reads the project's brand.json. The only
//     colour literals allowed here are rgba() shadows and scrims, never a hex code.
//
// Layout units are pixels of the composition (1920x1080 by default); the plan JSON written by
// tools/overlay_plan.py carries the real width and height.

import React from 'react';
import { Img, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import { COLORS, FONT_BODY, FONT_DISPLAY, FONT_SCRIPT } from './brand';
import {
  carouselX,
  cueStyle,
  cueVisible,
  drift,
  exitFx,
  leadIn,
  springIn,
} from './overlayFx.mjs';

// =============================================================================
// TYPES — the shape tools/overlay_plan.py writes to shots/src/shots/overlay-<scene>.json
// =============================================================================
export type MediaSrc = string | { remotion: string };

export type PanelSpec = {
  src: MediaSrc;
  kind: 'image' | 'video';
  x: number;
  y: number;
  w: number;
  h: number;
  layer: 'front' | 'behind';
};

export type BubbleSpec = {
  src: MediaSrc;
  label_lead: string;
  label: string;
  x: number;
  y: number;
  d: number;
};

export type CarouselCard = { src: MediaSrc; label: string };

export type CuePos = { anchor: string; x: number | null; y: number | null };

export type CueSpec = {
  id: string | number;
  lead: string;
  keyword: string;
  fx: number;
  color: 'white' | 'yellow';
  script: boolean;
  icon: string | null;
  pos: CuePos;
  layer: 'front' | 'behind';
  inF: number;
  keyF: number;
  outF: number;
  panels: PanelSpec[];
  bubbles: BubbleSpec[];
  carousel: CarouselCard[];
  source: string;
};

export type OverlayPlan = {
  scene: string;
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  clip: string;
  mask: string | null;
  cues: CueSpec[];
};

// A {remotion: Name} panel is drawn by a component the user registers in the scene file.
export type PanelRegistry = Record<string, React.ComponentType>;

// =============================================================================
// ICONS — stroke-only paths on a 100x100 canvas, drawn with fx 5 (strokeProgress)
// =============================================================================
export const ICONS: Record<string, string[]> = {
  fire: [
    'M50 8 C58 26 78 38 78 62 C78 80 66 92 50 92 C34 92 22 80 22 62 C22 48 30 40 36 32 C38 42 44 46 46 46 C48 32 46 20 50 8 Z',
    'M50 92 C42 92 36 85 36 77 C36 68 44 64 50 54 C56 64 64 68 64 77 C64 85 58 92 50 92 Z',
  ],
  gavel: [
    'M18 36 L44 10 L64 30 L38 56 Z',
    'M50 44 L84 78',
    'M72 66 L88 82 L80 90 L64 74',
    'M14 92 L56 92',
  ],
  chart: [
    'M10 10 L10 90 L92 90',
    'M24 70 L42 50 L58 62 L86 24',
    'M70 24 L86 24 L86 40',
  ],
  cloud: [
    'M28 78 C14 78 8 66 12 56 C16 46 28 44 34 48 C36 32 52 24 66 32 C76 38 78 46 78 50 C90 50 94 62 90 70 C88 76 82 78 76 78 Z',
  ],
  question: [
    'M32 34 C32 18 44 10 54 10 C68 10 76 20 76 32 C76 46 62 50 54 58 C50 62 50 68 50 72',
    'M50 90 L50 91',
  ],
  arrow: [
    'M8 52 C30 40 56 40 84 52',
    'M66 34 L86 52 L64 68',
  ],
  circle: [
    'M50 8 C76 8 94 26 92 52 C90 78 70 94 46 92 C22 90 6 70 10 44 C13 24 30 10 56 12',
  ],
};

type IconProps = { name: string; progress: number; size: number; opacity: number };

export const Icon: React.FC<IconProps> = ({ name, progress, size, opacity }) => {
  const paths = ICONS[name];
  if (!paths) {
    throw new Error(`Overlay icon "${name}" is not one of: ${Object.keys(ICONS).join(', ')}`);
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      style={{ opacity, overflow: 'visible', filter: 'drop-shadow(0 4px 18px rgba(0,0,0,0.45))' }}
    >
      {paths.map((d) => (
        <path
          key={d}
          d={d}
          fill="none"
          stroke={COLORS.ink}
          strokeWidth={4}
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - progress}
        />
      ))}
    </svg>
  );
};

// =============================================================================
// SHARED
// =============================================================================
const TEXT_SHADOW = '0 4px 18px rgba(0,0,0,0.45)';
const LEAD_PX = 40;
const KEYWORD_PX = 120;
const SAFE_PX = 96;

const MEDIA_VIDEO = /\.(mp4|mov|webm|m4v)$/i;

type MediaProps = {
  src: MediaSrc;
  kind?: 'image' | 'video';
  registry: PanelRegistry;
};

// One media slot: a public file (image or video) or a registered Remotion component.
const Media: React.FC<MediaProps> = ({ src, kind, registry }) => {
  if (typeof src !== 'string') {
    const Comp = registry[src.remotion];
    if (!Comp) {
      throw new Error(
        `Overlay panel "${src.remotion}" is not in PANELS. Register it in the scene file: ` +
          `const PANELS = { ${src.remotion}: YourComponent }.`,
      );
    }
    return <Comp />;
  }
  const asVideo = kind ? kind === 'video' : MEDIA_VIDEO.test(src);
  const fill: React.CSSProperties = { width: '100%', height: '100%', objectFit: 'cover' };
  return asVideo ? (
    <OffthreadVideo src={staticFile(src)} muted style={fill} />
  ) : (
    <Img src={staticFile(src)} style={fill} />
  );
};

// Opacity and blur of an element that belongs to a cue: springs in at the cue's start and
// leaves with the same exit as the text.
const useOwnedMotion = (cue: CueSpec, seed: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = springIn(frame, cue.inF, fps);
  const exit = exitFx(frame, cue.outF, fps);
  const sway = drift(frame, seed, fps);
  return {
    opacity: enter.opacity * exit.opacity,
    blurPx: exit.blurPx,
    transform: `translate(${sway.dx}px, ${sway.dy}px) scale(${enter.scale})`,
  };
};

// =============================================================================
// CueText — lead words, keyword, optional line icon. No box behind the text.
// =============================================================================
const anchorBox = (pos: CuePos, width: number): React.CSSProperties => {
  if (pos.x !== null && pos.y !== null && pos.x !== undefined && pos.y !== undefined) {
    // x is the text block's LEFT edge for anchor "left", its RIGHT edge for "right", and its
    // centre only for "top". Centring a left-anchored block pushed a long keyword off the
    // frame in the first real render (scene 25, "masalahnya").
    if (pos.anchor === 'left') {
      return { left: pos.x, top: pos.y, maxWidth: width - pos.x - SAFE_PX,
        transform: 'translateY(-50%)', alignItems: 'flex-start', textAlign: 'left' };
    }
    if (pos.anchor === 'right') {
      return { right: width - pos.x, top: pos.y, maxWidth: pos.x - SAFE_PX,
        transform: 'translateY(-50%)', alignItems: 'flex-end', textAlign: 'right' };
    }
    return {
      left: pos.x,
      top: pos.y,
      maxWidth: 2 * Math.min(pos.x, width - pos.x) - 2 * SAFE_PX,
      transform: 'translate(-50%, -50%)',
      alignItems: 'center',
      textAlign: 'center',
    };
  }
  if (pos.anchor === 'left') {
    return { left: SAFE_PX, top: '50%', transform: 'translateY(-50%)', alignItems: 'flex-start', textAlign: 'left' };
  }
  if (pos.anchor === 'right') {
    return { right: SAFE_PX, top: '50%', transform: 'translateY(-50%)', alignItems: 'flex-end', textAlign: 'right' };
  }
  // top (default): centred over the empty space above the speaker
  return { left: width / 2, top: SAFE_PX, transform: 'translateX(-50%)', alignItems: 'center', textAlign: 'center' };
};

export const CueText: React.FC<{ cue: CueSpec }> = ({ cue }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  if (!cueVisible(frame, cue.inF, cue.outF)) return null;

  const style = cueStyle(cue, frame, fps);
  const exit = exitFx(frame, cue.outF, fps);
  const kw = style.keyword;
  const color = cue.color === 'yellow' ? COLORS.highlight : COLORS.ink;
  const keywordFont = cue.script ? FONT_SCRIPT : FONT_DISPLAY;

  const keywordBase: React.CSSProperties = {
    fontFamily: keywordFont,
    fontWeight: cue.script ? 700 : 800,
    fontSize: cue.script ? KEYWORD_PX * 1.15 : KEYWORD_PX,
    lineHeight: 1.0,
    color,
    textShadow: TEXT_SHADOW,
    whiteSpace: 'pre',
  };

  let keywordNode: React.ReactNode;
  if (cue.fx === 2 && kw.slices.length > 0) {
    // Glitch: stacked copies of the word, each clipped to one horizontal slice and shifted.
    keywordNode = (
      <div style={{ display: 'grid' }}>
        {kw.slices.map((s: { y0: number; y1: number; dx: number }, i: number) => (
          <div
            key={i}
            style={{
              ...keywordBase,
              gridArea: '1 / 1',
              transform: `translateX(${s.dx}px)`,
              clipPath: `inset(${s.y0 * 100}% 0 ${(1 - s.y1) * 100}% 0)`,
            }}
          >
            {kw.text}
          </div>
        ))}
      </div>
    );
  } else if (cue.fx === 4) {
    // Handwrite: revealed left to right as the stroke progress runs 0..1.
    keywordNode = (
      <div style={{ ...keywordBase, clipPath: `inset(-20% ${(1 - kw.progress) * 100}% -20% -5%)` }}>
        {kw.text}
      </div>
    );
  } else {
    keywordNode = <div style={keywordBase}>{kw.text}</div>;
  }

  return (
    <div
      style={{
        position: 'absolute',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        maxWidth: width * 0.5,
        ...anchorBox(cue.pos, width),
      }}
    >
      {cue.icon ? (
        <Icon name={cue.icon} progress={style.icon.progress} size={110} opacity={exit.opacity} />
      ) : null}
      {cue.lead ? (
        <div
          style={{
            fontFamily: FONT_BODY,
            fontWeight: 400,
            fontSize: LEAD_PX,
            lineHeight: 1.15,
            color: COLORS.ink,
            textShadow: TEXT_SHADOW,
            opacity: style.lead.opacity,
            transform: `translateY(${style.lead.dy}px)`,
          }}
        >
          {cue.lead}
        </div>
      ) : null}
      <div
        style={{
          opacity: kw.opacity,
          filter: `blur(${kw.blurPx}px)`,
          transform: `scale(${kw.scale})`,
        }}
      >
        {keywordNode}
      </div>
    </div>
  );
};

// =============================================================================
// Panel — rounded image or video floating at x,y,w,h
// =============================================================================
export const Panel: React.FC<{
  cue: CueSpec;
  panel: PanelSpec;
  seed: number;
  registry: PanelRegistry;
}> = ({ cue, panel, seed, registry }) => {
  const frame = useCurrentFrame();
  const motion = useOwnedMotion(cue, seed);
  if (!cueVisible(frame, cue.inF, cue.outF)) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: panel.x,
        top: panel.y,
        width: panel.w,
        height: panel.h,
        borderRadius: 28,
        overflow: 'hidden',
        boxShadow: '0 24px 60px rgba(0,0,0,0.35)',
        opacity: motion.opacity,
        filter: `blur(${motion.blurPx}px)`,
        transform: motion.transform,
      }}
    >
      <Media src={panel.src} kind={panel.kind} registry={registry} />
    </div>
  );
};

// =============================================================================
// Bubble — round photo with a two-tier label under it
// =============================================================================
export const Bubble: React.FC<{
  cue: CueSpec;
  bubble: BubbleSpec;
  seed: number;
  registry: PanelRegistry;
}> = ({ cue, bubble, seed, registry }) => {
  const frame = useCurrentFrame();
  const motion = useOwnedMotion(cue, seed);
  if (!cueVisible(frame, cue.inF, cue.outF)) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: bubble.x,
        top: bubble.y,
        width: bubble.d,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 10,
        opacity: motion.opacity,
        filter: `blur(${motion.blurPx}px)`,
        transform: motion.transform,
      }}
    >
      <div
        style={{
          width: bubble.d,
          height: bubble.d,
          borderRadius: '50%',
          overflow: 'hidden',
          boxShadow: '0 16px 40px rgba(0,0,0,0.35)',
        }}
      >
        <Media src={bubble.src} registry={registry} />
      </div>
      <div style={{ textAlign: 'center', textShadow: TEXT_SHADOW }}>
        <div style={{ fontFamily: FONT_BODY, fontWeight: 400, fontSize: 30, color: COLORS.ink, lineHeight: 1.1 }}>
          {bubble.label_lead}
        </div>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 800, fontSize: 48, color: COLORS.ink, lineHeight: 1.05 }}>
          {bubble.label}
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// Carousel — row of rounded cards with labels, sliding left one card per 0.8 s
// =============================================================================
const CARD_W = 420;
const CARD_H = 300;
const CARD_GAP = 28;

export const Carousel: React.FC<{ cue: CueSpec; registry: PanelRegistry }> = ({ cue, registry }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const motion = useOwnedMotion(cue, 7);
  if (cue.carousel.length === 0 || !cueVisible(frame, cue.inF, cue.outF)) return null;

  const viewport = Math.min(width - SAFE_PX * 2, CARD_W * 2 + CARD_GAP);
  const x = carouselX(frame, cue.inF + Math.round(0.5 * fps), fps, CARD_W, CARD_GAP, cue.carousel.length);
  return (
    <div
      style={{
        position: 'absolute',
        left: SAFE_PX,
        top: height * 0.5,
        width: viewport,
        overflow: 'hidden',
        opacity: motion.opacity,
        filter: `blur(${motion.blurPx}px)`,
        transform: motion.transform,
      }}
    >
      <div style={{ display: 'flex', gap: CARD_GAP, transform: `translateX(${x}px)` }}>
        {cue.carousel.map((card, i) => (
          <div key={i} style={{ flex: `0 0 ${CARD_W}px`, textShadow: TEXT_SHADOW }}>
            <div style={{ width: CARD_W, height: CARD_H, borderRadius: 28, overflow: 'hidden' }}>
              <Media src={card.src} registry={registry} />
            </div>
            <div
              style={{
                marginTop: 12,
                fontFamily: FONT_DISPLAY,
                fontWeight: 800,
                fontSize: 48,
                color: COLORS.ink,
                lineHeight: 1.05,
              }}
            >
              {card.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// =============================================================================
// SourceBox — small text, dark translucent background, bottom-left
// =============================================================================
export const SourceBox: React.FC<{ cue: CueSpec }> = ({ cue }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  if (!cue.source || !cueVisible(frame, cue.inF, cue.outF)) return null;
  const enter = leadIn(frame, cue.inF, fps);
  const exit = exitFx(frame, cue.outF, fps);
  return (
    <div
      style={{
        position: 'absolute',
        left: 48,
        bottom: 48,
        maxWidth: width * 0.6,
        padding: '8px 16px',
        borderRadius: 8,
        background: 'rgba(0,0,0,0.55)',
        fontFamily: FONT_BODY,
        fontSize: 22,
        lineHeight: 1.25,
        color: COLORS.ink,
        opacity: enter.opacity * exit.opacity,
        filter: `blur(${exit.blurPx}px)`,
        transform: `translateY(${enter.dy}px)`,
      }}
    >
      {cue.source}
    </div>
  );
};
