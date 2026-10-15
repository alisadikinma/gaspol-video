// Kinetic text overlay composition for gaspol-video (GV-17 Phase F).
//
// Rendered once PER SCENE that carries an overlay. Run `tools/person_mask.py` and
// `tools/overlay_plan.py` first: the second writes shots/src/shots/overlay-<scene>.json from
// work/overlay-plan.json plus the voice-over word times. Copy this file to
// shots/src/shots/Overlay-<scene>.tsx, then edit the TWO lines marked SCENE below together
// (the scene number and the plan import) and render `KineticOverlay`. compositionConfig.id
// and the exported component name stay exactly `KineticOverlay`.
//
// Same non-negotiable rules as Shot.template.tsx and Captions.template.tsx:
//   * frame-based animation ONLY: no React state or lifecycle hooks that persist between
//     frames, no timers, no unseeded randomness. Remotion renders frames out of order and
//     in parallel processes.
//   * interpolate input ranges strictly increasing.
//   * Easing.bezier called directly, never wrapped.
//   * compositionConfig.id in PascalCase, no hyphens, no underscores.
//   * colours and fonts come from brand.json (through ../lib/brand). This plugin ships NO
//     palette.
//
// Effect arithmetic lives in ../lib/overlayFx.mjs (zero imports, unit-tested); the pieces
// that draw it live in ../lib/overlay-fx.tsx. This file only stacks the five layers.

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame } from 'remotion';

import {
  Bubble,
  Carousel,
  CueText,
  Panel,
  SourceBox,
  type CueSpec,
  type OverlayPlan,
  type PanelRegistry,
} from '../lib/overlay-fx';
import { cueVisible } from '../lib/overlayFx.mjs';

// =============================================================================
// SCENE + PLAN — edit both lines together, same scene number
// =============================================================================
import rawPlan from './overlay-03.json';
const SCENE = '03';

// {remotion: Name} panels in the plan are drawn by components registered here, for example
// `const PANELS: PanelRegistry = { SalesChart }`. Empty by default; a plan that names a
// component missing from this object fails the render with a clear error.
const PANELS: PanelRegistry = {};

const plan = rawPlan as unknown as OverlayPlan;
if (String(plan.scene) !== SCENE) {
  throw new Error(`Overlay: SCENE is "${SCENE}" but the plan JSON is for scene "${plan.scene}". Edit both lines together.`);
}

// =============================================================================
// COMPOSITION CONFIG
// =============================================================================
export const compositionConfig = {
  id: 'KineticOverlay',
  width: plan.width,
  height: plan.height,
  fps: plan.fps,
  durationInFrames: plan.durationInFrames,
};

const pad5 = (n: number) => String(n).padStart(5, '0');

const fill: React.CSSProperties = { width: '100%', height: '100%' };

// =============================================================================
// LAYERS — bottom to top
// =============================================================================
export const KineticOverlay: React.FC = () => {
  const frame = useCurrentFrame();
  const visible = (cue: CueSpec) => cueVisible(frame, cue.inF, cue.outF);
  const maskUrl = plan.mask ? staticFile(`${plan.mask}${pad5(frame + 1)}.png`) : null;
  const personMask = maskUrl
    ? ({
        maskImage: `url(${maskUrl})`,
        WebkitMaskImage: `url(${maskUrl})`,
        maskMode: 'luminance',
        WebkitMaskSize: '100% 100%',
        maskSize: '100% 100%',
      } as React.CSSProperties)
    : null;
  const sourceCue = plan.cues.find((cue) => cue.source && visible(cue));

  return (
    <AbsoluteFill>
      {/* L1 clip */}
      <AbsoluteFill>
        <OffthreadVideo src={staticFile(plan.clip)} style={fill} />
      </AbsoluteFill>

      {/* L2 behind */}
      <AbsoluteFill>
        {plan.cues.map((cue, ci) => (
          <React.Fragment key={`behind-${cue.id}`}>
            {cue.panels
              .filter((panel) => panel.layer === 'behind')
              .map((panel, pi) => (
                <Panel key={`p-${pi}`} cue={cue} panel={panel} seed={ci * 31 + pi} registry={PANELS} />
              ))}
            {cue.bubbles.map((bubble, bi) => (
              <Bubble key={`b-${bi}`} cue={cue} bubble={bubble} seed={ci * 31 + 17 + bi} registry={PANELS} />
            ))}
            <Carousel cue={cue} registry={PANELS} />
            {cue.layer === 'behind' ? <CueText cue={cue} /> : null}
          </React.Fragment>
        ))}
      </AbsoluteFill>

      {/* L3 person */}
      {personMask ? (
        <AbsoluteFill style={personMask}>
          <OffthreadVideo src={staticFile(plan.clip)} muted style={fill} />
        </AbsoluteFill>
      ) : null}

      {/* L4 front */}
      <AbsoluteFill>
        {plan.cues.map((cue, ci) => (
          <React.Fragment key={`front-${cue.id}`}>
            {cue.panels
              .filter((panel) => panel.layer === 'front')
              .map((panel, pi) => (
                <Panel key={`p-${pi}`} cue={cue} panel={panel} seed={ci * 31 + 9 + pi} registry={PANELS} />
              ))}
            {cue.layer === 'front' ? <CueText cue={cue} /> : null}
          </React.Fragment>
        ))}
      </AbsoluteFill>

      {/* L5 source */}
      <AbsoluteFill>{sourceCue ? <SourceBox cue={sourceCue} /> : null}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export default KineticOverlay;
