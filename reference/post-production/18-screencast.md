# Screencast Shots (Phase 4.5)

For scenes whose `Render Path` is `explainer` AND `Screen Source` is `capture` or `mock` — a
walkthrough of an app screen, not just a single static frame of it. Built on
`templates/remotion/lib/screencast.tsx`, which wraps `WebBrowserFrame` from `lib/browser.tsx` with an
animated cursor, click ripples, page transitions, and a ken-burns zoom.

Read `reference/post-production/12-remotion-explainer.md` first — the crash rules, brand rules, and
legibility floors there apply to a screencast shot exactly as they apply to any other explainer shot.
This document covers what is specific to a screen walkthrough.

---

## 1. When a screencast is the right shot

| Situation | Shot |
|---|---|
| The scene shows one screen, no clicking, no state change | `WebBrowserFrame` alone, holding one image or a static `node` |
| The scene shows moving through 2+ states of the app (navigate, filter, a value updating) | `Screencast` — this document |
| The point is genuine proof of a real, live result the user has not seen faked | a real recording, captured with `tools/gen_app_screen.py capture` and played back as a plain clip, not through `Screencast` |

A single held frame with a cursor added for effect is not a screencast — use `WebBrowserFrame`
directly and save the extra machinery for when there are actually multiple pages or states to move
through.

---

## 2. Inputs: where the pages come from

Every page in a `Screencast` is one of:

- **A captured or mocked screenshot**, listed by name in `{output_folder}/screens/manifest.json`
  (written by `tools/gen_app_screen.py capture|mock`, Phases F/G). Copy the file into
  `{output_folder}/shots/public/screens/` (Remotion only serves files under `public/`) and reference
  it as `img: 'screens/<file>'` — the bare `manifest.json` entry's `file` field, not the `ref/` path
  it lives at in the project.
- **A mock TSX component**, passed as `node: <Component data={...} />` instead of `img`. Use this when
  a state needs to animate on its own (a counter rising, a row appearing) rather than switch between
  two static PNGs.

A `Screencast` can mix both kinds of page in the same shot — an `img` page for a real captured screen
followed by a `node` page for an animated detail, for example.

---

## 3. API — read `lib/screencast.tsx` for the exact types

```tsx
import { Screencast, ScreencastPage, CursorKey, sampleCursor, CursorPointer } from '../../lib/screencast';

const PAGES: ScreencastPage[] = [
  { img: 'screens/ui-anpr-dashboard-initial.png', url: 'anpr.client.co.id/gate', tabTitle: 'Gate Monitor', enterAt: 0 },
  { img: 'screens/ui-anpr-dashboard-plate-detected.png', url: 'anpr.client.co.id/gate', tabTitle: 'Gate Monitor',
    enterAt: 90, transition: 'crossfade', transitionFrames: 5,
    zoom: { from: 1.0, to: 1.35, fx: 0.62, fy: 0.30, range: [96, 150] } },
];
const CURSOR: CursorKey[] = [ { frame: 0, x: 0.5, y: 0.5 }, { frame: 60, x: 0.30, y: 0.42 } ];
const CLICKS = [66];

export const compositionConfig = { id: 'GateScreencast', durationInFrames: 180, fps: 30, width: 1920, height: 1080 };
const GateScreencast = () => <Screencast pages={PAGES} cursor={CURSOR} clicks={CLICKS} />;
export default GateScreencast;
```

`ScreencastPage` fields, verbatim from `lib/screencast.tsx`: `img?` (staticFile-relative path) or
`node?` (a live TSX tree, same page machinery applies to both), `url`, `tabTitle`, `favicon?`,
`enterAt` (absolute frame the page becomes active), `transition?` (`'cut' | 'crossfade'`, default
`'cut'`), `transitionFrames?` (default 5), `scroll?: { to, range: [a, b], from? }`,
`zoom?: { from, to, fx, fy, range: [a, b] }`, `drift?` (default 0.02, the constant slow "alive"
push). `Screencast` props: `pages`, `cursor?: CursorKey[]`, `clicks?: number[]`, `box?`, `glow?`,
`appearAt?`, `favicon?`.

**Coordinates are fractions, not pixels**, so they survive any resize:
- `cursor` `x`/`y` and click ripple position → **viewport** fraction (0..1 of the page area under the
  URL bar).
- `zoom` `fx`/`fy` → **image** fraction (transform-origin of the ken-burns push).

`sampleCursor(frame, keys)` eases the cursor between keyframes and is what the pointer and the click
ripple position both call — use it directly if a shot needs to know where the cursor is at a given
frame for something else on screen. `CursorPointer` is the SVG pointer itself, exported in case a shot
needs to draw it somewhere `Screencast` does not (a picture-in-picture inset, for example).

---

## 4. Timing: cue times come from the narration, not from guessing

Exactly as in `12-remotion-explainer.md` §4: read word timings from `vo/vo-manifest.json` and convert
to this shot's local frames:

```
local_frame = (cue_seconds - shot_start_on_master) * fps
```

Never show a page before it is spoken. A click that names an item should land the click a few frames
before the word finishes, so the *result* appears on the word — not while it is still being said.
Where the audio source is `platform-native` (no word timings), fall back to `12-remotion-explainer.md`
§4's rule: space the cues evenly across the scene's duration from `scene-plan.md`.

---

## 5. Motion rules — the choices that read as fake if you get them backwards

| Move | Rule | Why |
|---|---|---|
| Page **navigation** (the URL path changes) | hard cut (`transition: 'cut'`, the default) | A real navigation is instant, not a fade |
| An **in-page filter** or state change (same path, value changed) | short crossfade, `transitionFrames: 5` | Selling "this is the same page, something on it changed" |
| **Scroll** | only with a tall capture (the full page below the fold) | A single-viewport screenshot cannot really scroll; faking it with `scroll` on a viewport-sized image just slides a static edge into view |
| Constant **drift** | leave the default `0.02`, or set explicitly per page | A perfectly still image reads as a slideshow, not a recording |
| **Ken-burns zoom** | push onto the payoff element exactly as it is spoken | Sells that the walkthrough is *about* that number or row, not incidental to it |

Mixing up navigation and filter — a hard cut on a filter, or a crossfade on a real navigation — is the
single biggest tell that a screencast is fake. Get this one right before anything else.

---

## 6. Mock animation inside a `node` page

A `node` page is a live TSX tree, so it can animate data the way any other explainer shot does — a
counter rising, a row fading in, a badge changing color — using frame-based `interpolate` only. The
same crash rules from `12-remotion-explainer.md` §2 apply: no `useState`, no `useEffect`, no
`setTimeout`, no unseeded `Math.random()`. The `Screencast` wrapper still drives drift, zoom, scroll
and transitions around the `node` exactly as it would around an `img`.

---

## 7. QA: render, then look at named frames

```bash
cd {output_folder}/shots
node scripts/qa-frames.mjs <ShotId> --out <scratch> arrive1=<f> click1=<f> nav1=<f> payoff=<f>
```

Name a frame for every cursor arrival, every click, every navigation/crossfade, and the ken-burns
payoff. Read every still with vision: does the pointer land on the element it is supposed to name,
does the URL bar show the right path for a navigation vs. the right query for a filter, does the zoom
frame the number or row the narration is naming at that instant. A screencast that renders without
error but was never looked at frame-by-frame has not been verified — the same rule as
`12-remotion-explainer.md` §5, applied to a shot with more moving parts.

---

## 8. Honesty

A screencast built from `mock` screens (per `screens/manifest.json`'s `simulated: true`) illustrates a
flow. It is never presented, in the title, thumbnail, or description, as a recording of a shipped
product — see `skills/video-package/SKILL.md` Step 7.5. A screencast built from `capture` screens
(`simulated: false`) is a real screen, animated; it may be described as a walkthrough of the actual
product.
