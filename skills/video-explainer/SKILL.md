---
name: video-explainer
description: >
  Phase 4.5 of AI video production. Builds the scenes that must be READABLE — metrics,
  diagrams, tables, UI walkthroughs — as coded Remotion shots instead of generated clips,
  because no video platform renders legible text. Runs between Phase 4 (keyframes) and
  Phase 5 (video prompts), over the scenes whose Render Path is explainer. Scaffolds a
  Remotion workspace inside the project on first use, writes brand tokens from the
  strategic brief, times every reveal to the narration, renders, and verifies by looking at
  a still at each cue.
  Triggers on: video explainer, explainer shot, remotion, shot remotion, diagram scene,
  scene angka, bikin shot penjelas, phase 4.5, render shot.
---

# Video Explainer — Phase 4.5: Coded Shots for Scenes That Must Be Read

## Overview

Some scenes exist to make information readable: a metric, a before/after, a labelled diagram, a
price table, a UI flow. No supported video platform can render legible text, so those scenes are
built as **Remotion shots** — real code, rendered to a clip — and composited in Phase 6.

Which scenes those are was already decided in Phase 3. This skill does not re-litigate it; it builds
what `scene-plan.md` marked `explainer`.

## Prerequisite

- `{output_folder}/scene-plan.md` with a `Render Path` column (Phase 3)
- `{output_folder}/strategic-brief.md` with the brand section (Phase 1)
- `{output_folder}/vo/vo-manifest.json` when the audio source is `elevenlabs` or `mixed` (Phase 5
  Step 5.0a runs before this skill in that case, because the narration sets the timing)
- Node 18+ for rendering. Without it, the skill still writes the shots and prints the commands.

## Reference Files (Read On-Demand)

| Task | Read |
|------|------|
| ANY generation | `reference/global-promo-config.md` (ALWAYS FIRST — §29.5 for the floors) |
| Shot authoring | `reference/post-production/12-remotion-explainer.md` |
| Screen walkthrough shots | `reference/post-production/18-screencast.md` (scenes with Screen Source capture/mock only) |
| Which scenes qualify | `reference/script-to-scene-bridge.md` > "Render Path" |
| Compositing later | `reference/post-production/10-post-production-pipeline.md` |

### CONTEXT LOADING — Phase 4.5
READ these files ONLY:
1. `reference/global-promo-config.md` (§29.5 legibility floors, §2 aspect ratio)
2. `reference/post-production/12-remotion-explainer.md`
Plus PER-SHOT context:
- `{output_folder}/scene-plan.md`: ONLY the rows whose Render Path is `explainer`
- `{output_folder}/av-script.md`: ONLY those scenes' narration and on-screen data
- `{output_folder}/strategic-brief.md`: the brand section and the domain figures
- `{output_folder}/vo/vo-manifest.json`: word timings for those scenes, when they exist
NEVER load the storytelling files, the NB2 guide, or any platform guide. None of them apply to a
coded shot.

---

## Hard Rules (NON-NEGOTIABLE)

1. **Build only what Phase 3 marked `explainer`.** Reclassifying a scene here means the keyframes
   for it were already paid for; if the classification is wrong, say so and go back.
2. **No palette ships in this plugin.** Colours and fonts come from `strategic-brief.md` into
   `brand.json`. A hardcoded brand colour in a template is a bug.
3. **Frame-based animation only.** No `useState`, no `useEffect`, no `setTimeout`, no unseeded
   `Math.random()`. See §2 of the reference: these do not crash, they produce a different video
   every render.
4. **Every element appears when it is SAID.** Cue times come from `vo-manifest.json` word timings.
   "Show everything and hold" is a slide, not a shot.
5. **Verify by looking at a still at EVERY cue.** A shot only reasoned about is not done.
6. **Legibility floors are not negotiable** — body ≥ 32px, headline ≥ 64px, contrast ≥ 4.5:1, 5%
   title-safe margin, all at 1080p.
7. **A shot carries no audio.** The narration is already playing underneath.

9. **(v3.4.0) A panel on a screen is attached by homography, never by a box.** An overlay that
   sits on a monitor or phone inside a live-action clip uses `QuadScreenTracked`
   (`templates/remotion/lib/quad-screen.tsx`), fed by corner tracks from
   `python3 tools/track_screen.py <clip> work/track-scene-NN.json --seed x,y --qa .tmp/qa-NN`.
   A screen seen off-axis is a trapezoid, not a rotated rectangle (measured on one monitor: left
   edge 524px, right edge 375px), so box-plus-rotation always overhangs a corner. Corners are read
   from fitted edge lines, never from extreme points and never eyeballed, and the QA frames are
   looked at before the overlay is rendered.

10. **(v3.4.0) Decide tracked-panel vs floating card from a measurement, not from taste.** Frontal
   and ≥300px wide → tracked. Oblique >15° or 120-300px → tracked only if the corners are
   measurable. Under 120px wide, or a screen that faces away from the camera → floating card. A
   guard-post monitor measured 60x45px in a 1920x1080 frame; a panel tracked onto a monitor facing
   the actor rendered behind the device. `track_screen.py` exits 2 below the width floor.

8. **Folder contract — nine folders, no new ones.** Everything this skill writes goes in a folder
that already exists: `ref/` `keyframes/` `clips/` `vo/` `shots/` `output/` `work/` `_arsip/`
`.tmp/`. A new folder needs the user's approval. Derived files (previews, QA stills, upload
copies, composites) go in `.tmp/` and are distinguished by a filename suffix, never by a new
subfolder. Rejected paid artefacts go in `_arsip/` with the reason in the name. MCP renders write
to `{output_folder}/.tmp`, then move to their permanent home. Never `sips --out <folder>/<file>`,
it replaces the folder — use `ffmpeg -vf scale`. Full contract:
`reference/post-production/10-post-production-pipeline.md` §2.

---

## Workflow

### Step 4.5.0: Read the plan

**Scope first (v3.2.0).** If the caller named a kelompok (`/video-explainer K2`, or the hand-off
from `/video-gen` step 5.1b), read `work/kelompok.json` and build ONLY the shots and overlays whose
scenes are in that kelompok. With no kelompok named, build every explainer scene — the old whole-film
behaviour, still correct when the project is not run per kelompok.

Read `scene-plan.md` and list the `explainer` scenes in scope with their durations and what each one
has to make readable. Present the list before building anything:

```
{N} explainer scenes:
  Scene 5  — 5s  — before/after gate waiting time (42 min -> 6 min)
  Scene 11 — 7s  — three-step rollout timeline
Estimated NB2 credits saved by not keyframing these: {N} x 2 frames
```

### Step 4.5.1: Scaffold the workspace (first use only)

```bash
node templates/remotion/scaffold.mjs {output_folder}
```

Then write `{output_folder}/shots/src/shots/brand.json` from the brand section of
`strategic-brief.md`: background, ink, ink-soft, accent, display font, body font. Replace every
placeholder value — they exist only so the scaffold renders before a brand is read.

Tell the user about the one-time `npm install` (about 300MB) rather than running it silently.

### Step 4.5.2: Author one shot per scene

Copy `templates/remotion/Shot.template.tsx`, rename the component and `compositionConfig.id` to
match the scene, and build the content. Pull the cue times from `vo-manifest.json`:

```
local_seconds = cue_seconds_on_master - shot_start_on_master
```

Add a `<Composition>` line in `src/Root.tsx` for each new shot.

One idea per shot. A frame carrying six numbers is not read in five seconds.

### Step 4.5.2b: Screencast shots

For a scene whose `Screen Source` (from `scene-plan.md`) is `capture` or `mock`, build a `Screencast`
shot instead of a plain static frame — see `reference/post-production/18-screencast.md`. Copy the
capture/mock PNGs named in `{output_folder}/screens/manifest.json` into
`{output_folder}/shots/public/screens/`, build the `pages`/`cursor`/`clicks` arrays per that
reference, and pull cue times from `vo-manifest.json` exactly as in Step 4.5.2. A scene whose Screen
Source is `none` never gets a `Screencast` — it either has no screen at all, or the screen is a single
held frame built with `WebBrowserFrame` directly.

### Step 4.5.3: Render and LOOK

```bash
cd {output_folder}/shots
node scripts/gen-registry.mjs
node scripts/render-all.mjs <ShotId>
node scripts/qa-frames.mjs <ShotId> --out <scratch> b1=<f> payoff=<f>
```

Name a frame for every cue — every reveal, every screencast arrival/click/navigation, and the payoff
— then Read each still with vision. Check: does the number or click arrive when it is said, is the
smallest text still readable, does anything sit outside the safe margin, does the contrast hold, does
the cursor land on the element it names.

If the Node renderer packages are not installed, fall back to plain ffmpeg:

```bash
cd {output_folder}/shots
npx remotion render src/index.ts <ShotId> out/<ShotId>.mp4
ffmpeg -ss <cue> -i out/<ShotId>.mp4 -frames:v 1 /tmp/<ShotId>-<cue>.jpg
```

**Skipping this step is the failure mode of this whole phase.** A shot that renders is not a shot
that reads.

### Step 4.5.4: Approval gate

Present each shot's stills and the cue list. AskUserQuestion:

- A) Approve — continue to the next shot
- B) Revise this shot — say what
- C) This scene should be live-action after all — return it to Phase 3

### Step 4.5.5: Hand off

Record each rendered shot in `scene-plan.md` next to its scene (`shot: <ShotId>`), so Phase 6's edit
plan can place it. Overlay shots additionally record their placement span.

---

When this run was scoped to a kelompok, set that kelompok's `remotion` field to `done` in
`work/kelompok.json` and return to `/video-gen` step 5.1b — the kelompok cut (K.5) is next, not the
next kelompok's shots.

## Kinetic captions and title cards (GV-7)

Two more compositions live beside `Shot.template.tsx` in `templates/remotion/`, in the same
workspace this skill scaffolds: `Captions.template.tsx` (`compositionConfig.id: 'KineticCaptions'`)
and `TitleCard.template.tsx` (`compositionConfig.id: 'TitleCard'`). They render and QA the same
way as any shot here — `node scripts/gen-registry.mjs` then `node scripts/render-all.mjs
KineticCaptions` (or `TitleCard`) from `{output_folder}/shots/` — and follow the same non-negotiable
rules: frame-based animation only, strictly increasing `interpolate` ranges, `Easing.bezier` called
directly, colours and fonts from `brand.json` only.

They are not built here, though. `KineticCaptions` draws a word-by-word caption page with one
highlighted key phrase, timed from `work/caption-plan.json`; `TitleCard` draws an eyebrow-plus-title
card at a topic boundary, timed from `scene-plan.md`'s `Title Card` column. Both numbers come from
Phase 6, not Phase 4.5 — `/video-post` Pass 4.1 owns building `work/caption-plan.json`
(`python3 tools/gen_captions.py {output_folder}`), authoring each scene's copy of these two
templates, rendering them, and compositing them over the master with `tools/composite.py overlay`.
See `skills/video-post/SKILL.md` Pass 4.1 for that workflow.

## Quality Gates

- [ ] Every `explainer` scene has a rendered shot; no `live-action` scene has one
- [ ] `brand.json` contains no placeholder value from the template
- [ ] No `useState` / `useEffect` / `setTimeout` / unseeded `Math.random()` in any shot
- [ ] Every `interpolate` input range is strictly increasing
- [ ] A still was inspected at EVERY cue, not just one
- [ ] Body text ≥ 32px, headline ≥ 64px, contrast ≥ 4.5:1, everything inside the 5% margin
- [ ] Cue times trace to `vo-manifest.json` where narration exists
- [ ] No shot carries its own audio track
- [ ] Shot ids recorded in `scene-plan.md`
- [ ] **(v3.4.0)** Screen-attached panels use `QuadScreenTracked` with a `track_screen.py` track, and the QA frames were inspected
- [ ] **(v3.4.0)** Every surface under 120px wide, or facing away from camera, became a floating card instead of a tracked panel
- [ ] **(v3.4.0)** On-screen strings pass `python3 tools/check_overlay_strings.py shots/src --from-markdown av-script.md --heading "Blok 4"`

## Degradation

No Node: write the `.tsx` files anyway, print the scaffold, install and render commands, and list the
scenes that have no rendered shot yet. They are reported to Phase 6 as missing, never dropped
silently from the edit.

## Output

- `{output_folder}/shots/src/shots/*.tsx` — the shots
- `{output_folder}/shots/out/*.mp4` (or `.mov` with alpha for overlays) — the renders
- `scene-plan.md` updated with each scene's shot id
