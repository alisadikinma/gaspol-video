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

`brand.json` is written per project from `strategic-brief.md`. **This plugin ships no palette.** The
placeholder values in the template exist only so a scaffolded workspace renders before a brand is
read; replace every one.

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
