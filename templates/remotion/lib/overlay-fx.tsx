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
  anchorGeometry,
  burstParticles,
  carouselX,
  cueStyle,
  cueVisible,
  drift,
  exitFx,
  leadIn,
  settledCue,
  springIn,
  stepState,
  vignetteAlpha,
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
  // Short text drawn on the panel's lower edge (e.g. "Foto: ANTARA"); empty = none.
  caption?: string;
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
  // GV-19. Optional so a plan written before them still type-checks.
  vignette?: boolean;
  burst?: { icon: string; count: number } | null;
};

export type StepsSpec = { total: number; marks: { n: number; f: number }[] };

// Two-tier caption preset written by tools/overlay_plan.py. source is always "course": the sizes
// are course advice, not platform data.
export type PresetSpec = { name: string; source: string; lead_px: number; key_px: number };

// Safe area in pixels written by tools/overlay_plan.py from a layout profile (GV-23).
export type SafeBox = { x0: number; y0: number; x1: number; y1: number; profile?: string };

export type OverlayPlan = {
  scene: string;
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  clip: string;
  mask: string | null;
  cues: CueSpec[];
  steps?: StepsSpec;
  preset?: PresetSpec;
  safe?: SafeBox;
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
  warning: [
    'M50 10 L92 86 L8 86 Z',
    'M50 38 L50 62',
    'M50 74 L50 75',
  ],
  money: [
    'M8 26 L92 26 L92 74 L8 74 Z',
    'M50 36 C57 36 62 42 62 50 C62 58 57 64 50 64 C43 64 38 58 38 50 C38 42 43 36 50 36 Z',
    'M18 50 L24 50',
    'M76 50 L82 50',
  ],
  check: [
    'M50 8 C74 8 92 26 92 50 C92 74 74 92 50 92 C26 92 8 74 8 50 C8 26 26 8 50 8 Z',
    'M28 52 L44 68 L72 34',
  ],
  cross: [
    'M50 8 C74 8 92 26 92 50 C92 74 74 92 50 92 C26 92 8 74 8 50 C8 26 26 8 50 8 Z',
    'M34 34 L66 66',
    'M66 34 L34 66',
  ],
  clock: [
    'M50 8 C74 8 92 26 92 50 C92 74 74 92 50 92 C26 92 8 74 8 50 C8 26 26 8 50 8 Z',
    'M50 24 L50 50 L68 62',
  ],
  lock: [
    'M22 44 L78 44 L78 90 L22 90 Z',
    'M32 44 L32 30 C32 18 40 10 50 10 C60 10 68 18 68 30 L68 44',
    'M50 62 L50 74',
  ],
};

type IconProps = { name: string; progress: number; size: number; opacity: number; stroke?: string };

export const Icon: React.FC<IconProps> = ({ name, progress, size, opacity, stroke = COLORS.ink }) => {
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
          stroke={stroke}
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
// Geometry lives in overlayFx.mjs (anchorGeometry, unit-tested). With a safe box (GV-23) the
// block is kept inside it; without one the geometry is the one the overlay always had.
const anchorBox = (pos: CuePos, width: number, height: number, safe?: SafeBox | null): React.CSSProperties =>
  anchorGeometry(pos, { width, height }, safe ?? undefined, SAFE_PX) as React.CSSProperties;

// `settled` (the layout gate's text-only render) draws the cue at full size at any frame: every
// enter effect finished, no exit, whatever frame the still is taken at.
export const CueText: React.FC<{ cue: CueSpec; preset?: PresetSpec; safe?: SafeBox | null; settled?: boolean }> = ({
  cue: planCue, preset, safe, settled = false,
}) => {
  const currentFrame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const fixed = settled ? settledCue(planCue, fps) : null;
  const cue: CueSpec = fixed ? { ...planCue, ...fixed.cue } : planCue;
  const frame = fixed ? fixed.frame : currentFrame;
  if (!cueVisible(frame, cue.inF, cue.outF)) return null;

  const style = cueStyle(cue, frame, fps);
  const exit = exitFx(frame, cue.outF, fps);
  const kw = style.keyword;
  const color = cue.color === 'yellow' ? COLORS.highlight : COLORS.ink;
  const keywordFont = cue.script ? FONT_SCRIPT : FONT_DISPLAY;
  const leadPx = preset ? preset.lead_px : LEAD_PX;
  const keyPx = preset ? preset.key_px : KEYWORD_PX;

  const keywordBase: React.CSSProperties = {
    fontFamily: keywordFont,
    fontWeight: cue.script ? 700 : 800,
    fontSize: cue.script ? keyPx * 1.15 : keyPx,
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
        ...anchorBox(cue.pos, width, height, safe),
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
            fontSize: leadPx,
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
      {panel.caption ? (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            padding: '28px 20px 14px',
            background: 'linear-gradient(transparent, rgba(0,0,0,0.6))',
            color: COLORS.ink,
            fontFamily: FONT_BODY,
            fontSize: 26,
            fontWeight: 600,
            textShadow: TEXT_SHADOW,
          }}
        >
          {panel.caption}
        </div>
      ) : null}
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

// =============================================================================
// StepBar — numbered circles along the top, the current step lit (GV-19)
// =============================================================================
const STEP_D = 56;

export const StepBar: React.FC<{ steps: StepsSpec }> = ({ steps }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const state = stepState(frame, steps.marks, steps.total, fps);
  if (state.active === 0) return null;
  const circles = Array.from({ length: steps.total }, (_, i) => i + 1);
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        top: 36,
        display: 'flex',
        justifyContent: 'center',
        gap: 14,
      }}
    >
      {circles.map((n) => {
        const past = n < state.active;
        const lit = n === state.active;
        return (
          <div
            key={n}
            style={{
              position: 'relative',
              width: STEP_D,
              height: STEP_D,
              borderRadius: '50%',
              boxSizing: 'border-box',
              border: `4px solid ${past || lit ? COLORS.ink : COLORS.muted}`,
              background: past ? COLORS.ink : 'transparent',
              opacity: past || lit ? 1 : 0.5,
              boxShadow: '0 4px 18px rgba(0,0,0,0.45)',
              overflow: 'hidden',
            }}
          >
            {lit ? (
              <div style={{ position: 'absolute', inset: 0, background: COLORS.highlight, opacity: state.litProgress }} />
            ) : null}
            <div
              style={{
                position: 'relative',
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: FONT_DISPLAY,
                fontWeight: 800,
                fontSize: 30,
                color: past || (lit && state.litProgress > 0.5) ? COLORS.paper : COLORS.muted,
              }}
            >
              {n}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// =============================================================================
// Vignette — blinking red edge glow, centre (the face) left clear (GV-19)
// =============================================================================
const VIGNETTE_MAX = 0.55;

export const Vignette: React.FC<{ cue: CueSpec }> = ({ cue }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!cue.vignette) return null;
  const alpha = vignetteAlpha(frame, cue.inF, cue.outF, fps) * VIGNETTE_MAX;
  if (alpha <= 0) return null;
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: `radial-gradient(ellipse at center, transparent 55%, ${COLORS.alarm} 100%)`,
        opacity: alpha,
      }}
    />
  );
};

// =============================================================================
// Burst — icons falling over the frame from the keyword on (GV-19)
// =============================================================================
const BURST_PX = 96;

export const Burst: React.FC<{ cue: CueSpec; seed: number }> = ({ cue, seed }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  if (!cue.burst) return null;
  const parts = burstParticles(frame, cue.keyF, fps, seed, cue.burst.count);
  return (
    <>
      {parts.map((p, i) =>
        p.opacity > 0 ? (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: p.x * width - BURST_PX / 2,
              top: p.y * height - BURST_PX / 2,
              transform: `rotate(${p.rot}deg)`,
            }}
          >
            <Icon name={cue.burst!.icon} progress={1} size={BURST_PX} opacity={p.opacity} stroke={COLORS.highlight} />
          </div>
        ) : null,
      )}
    </>
  );
};
