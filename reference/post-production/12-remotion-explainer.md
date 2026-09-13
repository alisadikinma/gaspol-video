# Remotion Explainer Shots (Phase 4.5)

For scenes whose `Render Path` is `explainer`. These are built as code, not generated, because no
video platform renders legible text — VEO, Seedance and Kling all warp it.

Assignment rule in `reference/script-to-scene-bridge.md` > "Render Path". Values in
`global-promo-config.md` §29.5. Template in `templates/remotion/`.

---

## 1. Workspace lives in the project, not in this plugin

```
node templates/remotion/scaffold.mjs {output_folder}
```

Creates `{output_folder}/shots/` with `package.json`, `remotion.config.ts`, `src/`, the shot
template, and a `brand.json` placeholder. It does **not** run `npm install` — that is about 300MB and
the user's decision.

One workspace per project, deliberately. `node_modules` belongs to the project it renders, and
keeping clients' brands and outputs apart matters more than saving the disk.

---

## 2. The rules that stop a render crashing

Adopted from `vidtsx-2d-generator` (see NOTICE). Every one of these is a real crash or a real
nondeterminism, not a style preference:

| Rule | Why |
|---|---|
| Frame-based animation only, via `useCurrentFrame()` | Remotion renders frames out of order across parallel processes. Anything remembering state between frames produces a different video each run. |
| No `useState`, `useEffect`, `setTimeout`, unseeded `Math.random()` | Same reason. These do not error; they produce a video that quietly differs. |
| `interpolate` input ranges strictly increasing | A non-monotonic range throws mid-render, often minutes in. |
| `Easing.bezier(...)` called directly, not wrapped | The wrapper form silently does nothing. |
| `compositionConfig.id` PascalCase, no hyphens or underscores | The id is used as a module identifier. |

---

## 3. Brand comes from the project

`brand.json` is written per project from `strategic-brief.md`. **This plugin ships no brand
palette; only neutral browser-chrome defaults and a white on-accent mark, overridable** (see
`18-screencast.md`). The placeholder values in the template exist only so a scaffolded workspace
renders before a brand is read; replace every one.

What is fixed are the legibility floors, and they are not style choices:

| Floor | Value |
|---|---|
| Body text | ≥ 32px at 1080p |
| Headline | ≥ 64px at 1080p |
| Contrast against its own background | ≥ 4.5:1 |
| Title-safe margin | 5% |

A number that cannot be read at arm's length on a phone has failed at the one job this shot exists to
do.

---

## 4. Timing comes from the narration

Each element appears when it is SAID. Read the word timings from `vo/vo-manifest.json`, convert to
this shot's local frames, and use them as cue times:

```
local_frame = (cue_seconds - shot_start_on_master) * fps
```

Never show a thing before it is spoken, and never hold everything on screen from frame one. "Show it
all and wait" is the difference between a coded shot and a slide.

Where the audio source is `platform-native` there is no word timing, so the shot's duration comes
from `scene-plan.md` and the cues are spaced evenly across it.

---

## 5. Verify by looking

A shot that has only been reasoned about is not finished. Render it, then pull a still at **each cue**
and look:

```bash
cd {output_folder}/shots
npx remotion render src/index.ts MetricReveal out/MetricReveal.mp4
ffmpeg -ss 2.4 -i out/MetricReveal.mp4 -frames:v 1 /tmp/cue-statOne.jpg
```

One still at 60% proves nothing about a reveal that lands at 2.4s. Check every cue, and check the
composited frame too — the shot over the real master, not the shot alone.

---

## 6. Cutaway or overlay

| Placement | When | Tool |
|---|---|---|
| **cutaway** | the shot IS the scene, the picture cuts to it | `composite.py cutaway` |
| **overlay** | a number or label sits over a live-action scene that keeps playing | `composite.py overlay` |

Master audio continues underneath in both. A shot never carries its own audio: the narration is
already playing, and a second track would double it.

An overlay needs a real alpha channel — render with `transparent: true` to ProRes 4444. An opaque
`.mov` used as an overlay blacks out the picture it was meant to decorate, so it is rejected rather
than composited.

---

## 7. Degradation

No Node: the `.tsx` files are still written, and the skill prints the exact scaffold, install and
render commands to run elsewhere. The shots do not exist, the skill says so, and the scenes that
needed them are listed rather than silently dropped from the edit.

---

## Style presets

`brand.json` fixes the project's own palette (`background`, `ink`, `inkSoft`, `accent`, fonts) — see
§3. What varies shot to shot within that fixed palette is the *treatment*: how much whitespace, how
hard the edges are, whether there is a glow. When the user names a style, apply its characteristics
using the project's `brand.json` tokens (via `lib/brand.ts`'s `COLORS`), never a hardcoded hex value.
If no style is named, use **minimalist**.

---

### Minimalist (default)

Use `COLORS.paper` as the background, `COLORS.ink` for primary text, `COLORS.muted` for secondary
text, `COLORS.accent` sparingly.

**Characteristics:** maximum whitespace, subtle animations, thin fonts, no decorative elements. Let
the content breathe — restraint is the point.

---

### Memphis

Use `COLORS.accent` and `COLORS.signal` for the geometric shapes, `COLORS.paper` for the background,
`COLORS.ink` for outlines.

**Characteristics:** geometric shapes (triangles, circles, squiggles), bold outlines in `COLORS.ink`,
scattered elements, confetti particles. Playful and busy — lean into the chaos, but stay inside the
project's own palette rather than importing a stock Memphis rainbow.

---

### Neo-brutalism

Use `COLORS.ink` for harsh borders, `COLORS.accent` for solid color blocks, `COLORS.paper` for the
background.

**Characteristics:** harsh borders (3-4px) in `COLORS.ink`, solid color blocks in `COLORS.accent`,
offset box shadows (`4px 4px 0px` in `COLORS.ink`), raw aesthetic. No gradients, no softness —
everything is hard-edged.

---

### Glassmorphism

Use `COLORS.paper` for frosted panels over a gradient built from `COLORS.accent` and `COLORS.signal`,
`COLORS.ink` (or its lightest tint) for text on the gradient.

**Characteristics:** frosted glass panels (`backdrop-filter: blur(...)`), transparency, subtle 1px
borders, a gradient background. Layer translucent cards over the gradient rather than a flat fill.

> `background` here is a gradient string built from the project's own accent tokens. Apply it via
> `background` (not `backgroundColor`) on the `AbsoluteFill`.

---

### Neon / signal glow

Use `COLORS.ink` as a near-black background, `COLORS.signal` and `COLORS.accent` for glowing
elements.

**Characteristics:** dark backgrounds, glowing effects (`box-shadow` / `text-shadow` in
`COLORS.signal`), scanlines, tech-inspired elements. The glow is what sells it — apply colored shadows
generously, but only in colors that already exist in `brand.json`.

---

### Corporate

Use `COLORS.paper` as the background, `COLORS.accent` for structure, `COLORS.ink`/`COLORS.muted` for
text.

**Characteristics:** professional, clean, structured layouts, subtle gradients built from the existing
tokens. Conservative motion — nothing flashy.
