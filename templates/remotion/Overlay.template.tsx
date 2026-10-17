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
// GV-23: `plan.safe` (written by overlay_plan.py from a layout profile) keeps every text block
// inside the safe area. `textOnly` (an input prop, with `cueId` to pick one cue) renders ONLY the cue text on a flat mid-grey:
// no clip, panels, mask, vignette, burst or step bar. tools/layout_gate.py --overlay renders it
// through scripts/render-overlay-text.mjs and measures the real text box.
//
// Effect arithmetic lives in ../lib/overlayFx.mjs (zero imports, unit-tested); the pieces
// that draw it live in ../lib/overlay-fx.tsx. This file only stacks the five layers. GV-19 adds the step bar, red vignette and falling
// burst inside L4 front, so the layer order is unchanged.

import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame } from 'remotion';

import {
  Bubble,
  Burst,
  Carousel,
  CueText,
  Panel,
  SourceBox,
  StepBar,
  Vignette,
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
// Flat mid-grey (gray level 128) the gate measures against: a dark outline differs from it and
// counts in the box. rgb() on purpose: hex colours come from brand.ts only.
const MEASURE_GREY = 'rgb(128, 128, 128)';

export const KineticOverlay: React.FC<{ textOnly?: boolean; cueId?: string }> = ({ textOnly = false, cueId }) => {
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

  if (textOnly) {
    return (
      <AbsoluteFill style={{ backgroundColor: MEASURE_GREY }}>
        {plan.cues
          .filter((cue) => cueId === undefined || String(cue.id) === String(cueId))
          .map((cue) => (
          <CueText key={`text-${cue.id}`} cue={cue} preset={plan.preset} safe={plan.safe} />
          ))}
      </AbsoluteFill>
    );
  }

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
            {cue.layer === 'behind' ? <CueText cue={cue} preset={plan.preset} safe={plan.safe} /> : null}
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
            <Vignette cue={cue} />
            {cue.panels
              .filter((panel) => panel.layer === 'front')
              .map((panel, pi) => (
                <Panel key={`p-${pi}`} cue={cue} panel={panel} seed={ci * 31 + 9 + pi} registry={PANELS} />
              ))}
            {cue.layer === 'front' ? <CueText cue={cue} preset={plan.preset} safe={plan.safe} /> : null}
            <Burst cue={cue} seed={ci * 131 + 5} />
          </React.Fragment>
        ))}
        {plan.steps ? <StepBar steps={plan.steps} /> : null}
      </AbsoluteFill>

      {/* L5 source */}
      <AbsoluteFill>{sourceCue ? <SourceBox cue={sourceCue} /> : null}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export default KineticOverlay;
