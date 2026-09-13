// App-screen mock template for gaspol-video Phase 4B / Screen Source "mock" (v3.1.0).
//
// Copy this file to {project}/shots/src/shots/screens/<Component>.tsx, rename the component and
// compositionConfig.id to match `screens.json`'s `mock[].component`, and author the real layout
// for a screen that either does not exist yet or cannot be reached with Playwright (use
// `gen_app_screen.py capture` for that case instead).
//
//   * durationInFrames: 1 — this renders a STILL through render-stills.mjs, never a clip.
//   * no useState/useEffect/setTimeout/unseeded Math.random — same determinism rule as shots.
//   * colours and fonts come ONLY from ../../lib/brand.ts, which itself reads
//     shots/src/shots/brand.json, written from the client's strategic-brief.md. This plugin
//     ships no UI palette — a screen that still looks like this template's defaults means
//     brand.json was never written (gen_app_screen.py mock refuses to run until it is).
//   * UI text language follows `ui_text_language` from strategic-brief.md, not this comment
//     block or any of the placeholder strings below.
//   * every value shown MUST come from the `data` prop (screens/data.json), never be invented
//     in the component — that is what keeps the same numbers pinned across every scene that
//     references this screen (Scene Logic Realism check 3).
//   * the component takes exactly `{ state, data }`. `state` selects which visible state to
//     render (screens.json `mock[].states`, e.g. "initial" vs "plate-detected"); `data` is
//     `screens/data.json[name]`, shared by every scene that shows this screen.

import React from 'react';
import { AbsoluteFill } from 'remotion';
import { COLORS, FONT_DISPLAY, FONT_BODY } from '../../lib/brand';

// =============================================================================
// COMPOSITION CONFIG
// =============================================================================
export const compositionConfig = {
  id: 'ExampleDashboardScreen',   // PascalCase, matches the file name AND mock[].component
  width: 1920,
  height: 1080,
  fps: 30,
  durationInFrames: 1,            // a still: render-stills.mjs always asks for frame 0
};

// =============================================================================
// PROPS
// =============================================================================
export type ScreenProps = {
  state: string;
  data: Record<string, unknown>;
};

// =============================================================================
// SCREEN
// =============================================================================
const ExampleDashboardScreen: React.FC<ScreenProps> = ({ state, data }) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.paper,
        padding: 56,
        fontFamily: FONT_BODY,
        color: COLORS.ink,
      }}
    >
      <div style={{ fontFamily: FONT_DISPLAY, fontSize: 44, fontWeight: 700, marginBottom: 8 }}>
        {String((data as { title?: string }).title ?? 'Untitled screen')}
      </div>
      <div style={{ fontSize: 22, color: COLORS.muted, marginBottom: 32 }}>state: {state}</div>

      {/* Replace this block with the real layout — a table, a dashboard, a form. Read every
          value from `data`; never hardcode a number or label here. */}
      <pre
        style={{
          fontFamily: FONT_BODY,
          fontSize: 24,
          color: COLORS.ink,
          background: `${COLORS.muted}22`,
          borderRadius: 12,
          padding: 24,
        }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
    </AbsoluteFill>
  );
};

export default ExampleDashboardScreen;
