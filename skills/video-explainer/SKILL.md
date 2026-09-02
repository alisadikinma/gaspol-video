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

---

## Workflow

### Step 4.5.0: Read the plan

Read `scene-plan.md` and list the `explainer` scenes with their durations and what each one has to
make readable. Present the list before building anything:

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

### Step 4.5.3: Render and LOOK

```bash
cd {output_folder}/shots
npx remotion render src/index.ts <ShotId> out/<ShotId>.mp4
ffmpeg -ss <cue> -i out/<ShotId>.mp4 -frames:v 1 /tmp/<ShotId>-<cue>.jpg
```

Read every still with vision. Check: does the number arrive when it is said, is the smallest text
still readable, does anything sit outside the safe margin, does the contrast hold.

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

## Degradation

No Node: write the `.tsx` files anyway, print the scaffold, install and render commands, and list the
scenes that have no rendered shot yet. They are reported to Phase 6 as missing, never dropped
silently from the edit.

## Output

- `{output_folder}/shots/src/shots/*.tsx` — the shots
- `{output_folder}/shots/out/*.mp4` (or `.mov` with alpha for overlays) — the renders
- `scene-plan.md` updated with each scene's shot id
