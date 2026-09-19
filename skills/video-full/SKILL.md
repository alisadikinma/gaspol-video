---
name: video-full
description: >
  End-to-end AI video promotional production pipeline. Orchestrates the full 6-phase workflow:
  video-brainstorm (Phase 1) → video-script (Phase 2-3.5) → video-image (Phase 4A+4B) →
  video-explainer (Phase 4.5, conditional) → video-gen (Phase 5 with Image Review, delivering one
  kelompok at a time: VO, clips, voice change, Remotion, kelompok cut, approval) →
  video-post --final (Phase 6 tail: edit, SFX, subtitles, music, mix) → video-package (Phase 7). Generates complete 2-3 minute promotional video
  packages for any brand. Supports multi-character cast (max 5), any brand or Ali Sadikin preset.
  Triggers on: video full, full pipeline, end to end, video production, bikin video promosi,
  buat video lengkap, video marketing, iklan video, video agency, generate video complete,
  promotional video, product video, video promo, create promo.
---

# Video Full — End-to-End Promotional Video Pipeline

## Overview

Orchestrator skill that runs the complete production pipeline, Phase 1 through Phase 7, by invoking 7 specialized skills in sequence. Each skill handles its own context loading, reference files, and approval gates. This skill delegates entirely — it carries no generation logic of its own.

**Output:** Complete production package — 8 planning files, the rendered explainer shots, the mixed master, and its packaging — for a 2-3 minute promotional video.

## Reference Files

Read FIRST: `reference/global-promo-config.md` — single source of truth for all configurable values.

Phase-specific references are loaded by each sub-skill automatically. See individual skill files for details.

## Flags

| Flag | Description |
|------|-------------|
| `--full` (default) | Full production plan: cast-profile, ref-manifest, scene breakdown, storyboard notes, NB2 prompts, VEO prompts, audio specs, extension strategy, post-production checklist |
| `--quick` | Copy-paste ready prompts only: NB2 + VEO per scene, no production plan |
| `--preset ali` | Use Ali Sadikin creator preset instead of generic brand profile |

## Workflow

### Step 1: Run `/video-brainstorm` (Phase 1)

Invoke the video-brainstorm skill for:
- Language selection (Bahasa Indonesia / English / Bilingual)
- Cast builder (1-5 characters, Pemeran Utama/Pendamping)
- Product/service discovery
- Institution detection + costume confirmation
- Location & setting context
- Domain Deep Research (6 location-aware WebSearch queries)
- Target market, awareness level, platform selection
- Emotional core discovery
- Storyline input + 7-beat arc mapping
- Tone/mood selection

**Wait for Phase 1 approval gate.**

**Verify output exists:**
- `{output_folder}/strategic-brief.md`
- `{output_folder}/cast-profile.md`

---

### Step 2: Run `/video-script` (Phase 2, 3, 3.5)

Invoke the video-script skill for:
- A/V script generation with 7-beat narrative arc
- Scene breakdown with VEO mode mapping
- Reference image collection (HARD BLOCK gate)
- Cultural location research
- Batch NB2 prompts for missing references

Phase 3 also assigns **Screen Source** (`capture | mock | none`) per scene, next to Render Path —
before any NB2 credit is spent, so an app screen never gets drawn twice.

**Wait for Phase 2, 3, and 3.5 approval gates.**

**Verify output exists:**
- `{output_folder}/av-script.md`
- `{output_folder}/scene-plan.md`
- `{output_folder}/ref-manifest.md`

---

### Step 3: Run `/video-image` (Phase 4A, 4B)

Invoke the video-image skill for:
- Asset Library generation (Phase 4A) — standalone reusable assets with dependency graph
- Scene Keyframe generation (Phase 4B) — start/end frames composed from assets
- Batch-by-ACT with prompt-reviewer agent validation
- After each approved batch, a **render offer** — `Render sekarang?` through
  `mcp__indusia-image-gen__generate_image` (`nano-banana-2`), tracked in `renders.json`

**Wait for Phase 4A and 4B approval gates.**

**Verify output exists:**
- `{output_folder}/nb2-reference-prompts.md`
- `{output_folder}/image-prompts.md`

**Keyframe images come either from a render offer accepted in this step, or from the user
generating them by hand from the NB2 prompts and saving to `{output_folder}/keyframes/`.**

---

### Step 4: Run `/video-explainer` (Phase 4.5) — only if any scene has Render Path `explainer`

Read `{output_folder}/scene-plan.md` and look at the **Render Path** column. Scenes marked
`explainer` are the ones that must be READABLE — metrics, diagrams, tables, UI walkthroughs. No
video platform renders legible text, so those shots are coded in Remotion rather than generated.

**Skip this step entirely when every scene is `platform`.** Say so out loud; a silent skip looks
like a bug to anyone reading the run.

Invoke the video-explainer skill for:
- Remotion workspace scaffold inside the project (first use only)
- Brand tokens written from `strategic-brief.md`
- Reveals timed to the narration in `vo-manifest.json`
- Render, then verify by looking at a still at each cue

**Wait for the Phase 4.5 approval gate.**

**Verify output exists:**
- `{output_folder}/shots/out/` — one rendered file per explainer scene

---

### Step 5: Run `/video-gen` (Phase 5 with Image Review)

Invoke the video-gen skill for:
- Image Review (Step 0) — per-scene collaborative review of actual keyframe images
- Kelompok ledger (Step 5.0b) — `work/kelompok.json`, the batches this film is delivered in
- VEO 3.1 video prompt generation with camera movement, 3-layer audio, lip sync
- Batch-by-ACT with prompt-reviewer agent validation
- After each approved batch, a **render offer** — `Render sekarang?` through
  `mcp__indusia-video-gen__generate_video` (`veo-3.1-fast`), for VEO scenes only; Seedance, Kling,
  Scene Extension, and unsupported durations/aspects stay copy-paste
- **Then step 5.1b hands that kelompok straight to post (v3.2.0):** its VO, its voice change, its
  Remotion shots and overlays, and a `output/kelompok-K{N}.mp4` cut the user approves before the
  next batch starts. Phase 5 and the first two Phase 6 passes interleave; they are no longer two
  separate stages.

**Wait for Image Review, and for the approval gate of every kelompok.**

**Verify output exists:**
- `{output_folder}/video-prompts.md`
- `{output_folder}/work/kelompok.json` with every entry `approved`
- `{output_folder}/output/kelompok-K*.mp4` — one cut per kelompok

---

### Step 6: Run `/video-post --final` (Phase 6 tail) — after every kelompok is approved

Passes 1 and 2 already ran per kelompok inside Step 5. This step is the global tail, and it refuses
to start while any entry in `work/kelompok.json` is not `approved` — it says which one and stops.

Invoke the video-post skill for the remaining passes, in order:
1. ~~Voice-over~~ — already done per kelompok; every line was spoken, measured and approved there
2. Edit — concatenate the approved `output/kelompok-K*.mp4` cuts into `output/master.mp4` under the
   A/V duration gate. An approved segment is never re-rendered here.
3. SFX — domain-aware cue sheet, user-audited before anything is mixed
4. Subtitles and music — captions built from the script, music bed under the voice
5. Final mix

After the final mix, **Check P6** (`tools/verify_render.py`) transcribes the master a second time
and diffs it against `av-script.md` — FAIL on any missing/inserted word, WARN on the rest, SKIPPED
(never PASS) without `ASSEMBLYAI_API_KEY`.

**Wait for the SFX cue-sheet audit gate and the Phase 6 approval gate.**

**Verify output exists:**
- `{output_folder}/output/master-mixed.mp4`
- `{output_folder}/output/master.srt`

---

### Step 7: Run `/video-package` (Phase 7)

Invoke the video-package skill for one locked title, three thumbnail bets built on different levers,
and one value-forward description. This step decides WHAT to bet on. The thumbnail image itself is
rendered by the image plugin through a soft reference, never here.

**Verify output exists:**
- `{output_folder}/packaging.md`

---

### Step 8: Production Summary

Present final production package:

```
## Production Package Complete

**Output folder:** {output_folder}/

| File | Content | Skill |
|------|---------|-------|
| strategic-brief.md | Strategic planning, domain knowledge, cultural context | /video-brainstorm |
| cast-profile.md | Character profiles, costume details, identity lock refs | /video-brainstorm |
| av-script.md | A/V script with 7-beat arc, narration, audio direction | /video-script |
| scene-plan.md | Scene breakdown, VEO modes, durations, extension strategy | /video-script |
| ref-manifest.md | Reference image manifest (validated 100%) | /video-script |
| nb2-reference-prompts.md | Asset library NB2 prompts (tiered) | /video-image |
| image-prompts.md | Scene keyframe NB2 prompts (start + end frames) | /video-image |
| video-prompts.md | VEO 3.1 video prompts with audio specs | /video-gen |
| shots/out/ | Rendered Remotion explainer shots (only when a scene is Render Path `explainer`) | /video-explainer |
| output/kelompok-K*.mp4 | One approved cut per kelompok: picture + narasi + tempelan | /video-gen + /video-post |
| output/master-mixed.mp4 | Finished, mixed video: VO, SFX, captions, music | /video-post --final |
| output/master.srt | Caption file, text taken from the script | /video-post |
| packaging.md | Locked title, three thumbnail bets, description | /video-package |

**Total scenes:** {N}
**Total VEO clips:** {M} (generations + extensions)
**Estimated total duration:** {X}s
```

## Hard Rules

All hard rules from individual skills apply. Key cross-cutting rules:

1. **NEVER skip a phase** — all phases must execute in order
2. **NEVER proceed without user approval** — every phase ends with approval gate
3. **Phase 3.5 is HARD BLOCK** — cannot proceed to Phase 4 without ALL refs validated
4. **Asset-first, scene-second** — Phase 4A atoms before Phase 4B molecules
5. **Image Review before VEO** — Phase 5 Step 0 reviews actual images before generating video prompts
5b. **A kelompok is approved on its cut, not on its clips** — picture with narration and overlays,
    reviewed before the next kelompok starts
6. **Audio is NEVER optional** — all 3 layers specified in every VEO prompt
7. **Product is NEVER the hero** — customer is hero, product is bridge
8. **Phase 6 needs real clips** — it runs on rendered video, not on prompts. Stop and wait rather
   than assembling a master out of files that do not exist yet
9. **A scene is never spoken twice** — a scene whose `audio_source` is `elevenlabs` carries no
   speech line in its platform prompt. Two voices saying the same line is the failure this rule
   exists to prevent

See individual skill files for complete hard rules per phase.
