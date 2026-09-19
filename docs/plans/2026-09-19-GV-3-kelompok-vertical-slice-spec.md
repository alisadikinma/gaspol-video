# GV-3 — Per-kelompok vertical slice (Phase 5 ↔ Phase 6 interleave)

Date: 2026-09-19 · Author: Ali Sadikin · Status: spec

## Problem

The pipeline finishes every clip in Phase 5, and only then starts Phase 6 (voice-over, voice change,
Remotion overlays, edit). On the `catalog-2` film that ordering cost real rework: narration length,
overlay text and lip sync were only checked after all clips existed, so a fix meant re-rendering
clips that had already been approved on picture alone.

A clip is not reviewable on picture alone. It is reviewable when it carries its narration and its
overlay — that is what the audience sees.

## Change

Introduce the **kelompok** (group) as the unit of delivery. A kelompok is the batch Phase 5 already
uses (one ACT, or a sub-batch of at most 5 scenes). Each kelompok is carried to a near-final state
before the next kelompok starts.

Per-kelompok order, once its prompts are approved:

| Step | What | Why here |
|---|---|---|
| K.1 | Voice-over for this kelompok's lines, mastered | VO-first already sets clip duration; it cannot come after the clips |
| K.2 | Render this kelompok's clips | unchanged from Phase 5 step 5.5 |
| K.3 | Voice change on platform-native dialogue in those clips | needs the clip audio to exist |
| K.4 | Remotion: explainer shots and overlays belonging to this kelompok | independent of clips, but needed for the cut |
| K.5 | Assemble `output/kelompok-K{N}.mp4` under the A/V duration gate | the reviewable artefact |
| K.6 | User approves the kelompok | a fix here is contained to ≤5 scenes |

Global tail, once, after every kelompok is approved:

| Pass | Why it stays global |
|---|---|
| Edit (full) | concatenates the approved kelompok segments into `output/master.mp4` |
| SFX | cue levels are judged against the whole film |
| Subtitles + music | music is levelled against the finished voice across the film |
| Final mix | loudness and limiting are set once |
| Check P6 | transcript diff runs against the whole `av-script.md` |

## Not changing

- The five passes keep their internal order. What changes is their **scope**: passes 1 and 2 run per
  kelompok first, then once globally over segments that are already approved.
- Phases 1 to 4.5 are untouched.
- The A/V duration gate still blocks, now at kelompok level as well as at master level.

## New state file

`work/kelompok.json` — the ledger that says which kelompok exists, what it contains and how far it
got. Schema in `reference/post-production/10-post-production-pipeline.md` §3.9.

## Files touched

- `reference/post-production/10-post-production-pipeline.md` — §1 order, §2 folder contract, §3.9 schema
- `skills/video-gen/SKILL.md` — step 5.0b (kelompok ledger), step 5.1b (hand-off)
- `skills/video-post/SKILL.md` — kelompok mode, hard rule 1
- `skills/video-explainer/SKILL.md` — per-kelompok scoping
- `skills/video-full/SKILL.md` — steps 5 and 6
- `.claude-plugin/plugin.json` — 3.1.0 → 3.2.0
