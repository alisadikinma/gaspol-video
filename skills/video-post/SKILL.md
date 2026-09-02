---
name: video-post
description: >
  Phase 6 of AI video production. Turns generated clips into a finished, mixed file: builds
  the voice-over (ElevenLabs TTS plus speech-to-speech for platform-spoken dialogue),
  assembles with ffmpeg under an A/V duration gate, scores domain-aware SFX, burns captions
  built from the script, lays a music bed under the voice, and mixes. Five passes in a fixed
  order, with a hard user-audit gate before anything is mixed.
  Triggers on: video post, post production, pasca produksi, rakit video, mix audio, sfx,
  subtitle, musik, phase 6, final mix, jadikan video, gabung klip.
---

# Video Post — Phase 6: From Clips to a Finished File

## Overview

Phases 1 to 5 produce a prompt package. This phase produces the video. Five passes, in an order that
is not a preference:

| # | Pass | Produces | Why it cannot move |
|---|---|---|---|
| 1 | Audio | `vo/*.mp3`, `audio-plan.json` | the voice-over has to exist before anything knows how long a beat really is |
| 2 | Edit | `output/master.mp4`, `edit-plan.json` | cue times only mean something once the master timeline exists |
| 3 | SFX | `sfx-plan.json` | needs the assembled master to place cues against |
| 4 | Subtitles + music | `master.srt`, `music-plan.json` | subtitles need the final audio; music is levelled against the finished voice |
| 5 | Final mix | `output/master-mixed.mp4` | loudness and limiting are set once everything is in place |

## Prerequisite

- `{output_folder}/clips/` — the user's generated clips, named `scene-{NN}[-ext{K}].mp4`
- `{output_folder}/av-script.md`, `scene-plan.md`, `cast-profile.md`, `strategic-brief.md`
- `{output_folder}/shots/out/` — rendered explainer shots, when the video has any
- `audio-plan.md` from Phase 5 Step 5.0a — the binding audio-source decision

## Reference Files (Read On-Demand)

| Task | Read |
|------|------|
| ANY pass | `reference/global-promo-config.md` §29 (ALWAYS FIRST) |
| The contract | `reference/post-production/10-post-production-pipeline.md` |
| Pass 1 | `reference/post-production/11-voice-cast-and-vo.md` |
| Pass 2 | `reference/post-production/13-ffmpeg-edit.md` |

### CONTEXT LOADING — per pass, not all at once
Pass 1: global-promo-config §29, `11-voice-cast-and-vo.md`, `cast-profile.md` VOICE blocks,
`av-script.md` narration column.
Pass 2: global-promo-config §29, `13-ffmpeg-edit.md`, `scene-plan.md`, `clip-manifest.json`,
`vo-manifest.json`.
NEVER load the storytelling files or the NB2 guide. Neither applies after the clips exist.

---

## Hard Rules (NON-NEGOTIABLE)

1. **The passes run in order.** Skipping one leaves the next working from numbers it invented.
2. **Every pass is a plan first, a render second.** Author the JSON, show it, then run the tool.
3. **The A/V duration gate blocks.** Video and audio equal within 0.04s or the render is rejected —
   not shipped with a note.
4. **Audio is never optional**, and only SPEECH moves out when the source is ElevenLabs.
5. **A tool never substitutes a voice.** Missing env var means stop and ask.
6. **Degradation is loud.** A missing binary or key costs one capability, says which, and the phase
   continues.

---

## Pass 1 — Audio

Builds every sound a human makes in this video.

### 1.1 Read the decision, do not re-ask it

`audio-plan.md` from Phase 5 already holds the video-level `audio_source` and the per-scene values.
Read it. Asking again here is how the answer drifts between phases.

### 1.2 Build `work/audio-plan.json`

One entry per scene, layers ordered by `at_s`, per the schema in `10-post-production-pipeline.md`:

- `kind: narration`, `from: tts` — spoken by ElevenLabs
- `kind: dialogue`, `from: clip` — spoken by the platform, `changer: true` when that cast member's
  `VOICE:` block says `native+changer`
- Two speech layers in one scene MUST NOT overlap. A platform lip-syncs one speaker at a time, and a
  narration line starting before the dialogue ends renders as garble.

### 1.3 Generate

```bash
node tools/gen_vo.mjs {output_folder}
node tools/voice_changer.mjs {output_folder}/clips/scene-NN.mp4 \
     --voice-env ELEVENLABS_VOICE_C2 --out {output_folder}/vo/scene-NN-c2.mp3
```

`gen_vo.mjs` stitches consecutive requests so prosody carries across scenes, and writes
`vo-manifest.json` with measured durations and word timings — the input for pass 2 and pass 4.

`voice_changer.mjs` prints the duration drift on every conversion and refuses beyond 0.05s. **That
line is evidence, not noise.** A refusal means the mixed-source decision needs reopening, never an
audio stretch to force the fit.

### 1.4 Present the layer sheet

Scene, layer, cast, source, measured duration. Get approval before pass 2 builds a timeline on top
of it.

### Pass 1 edge cases

| Situation | Behaviour |
|---|---|
| No speaking cast at all | Pass does nothing and says so. A silent B-Roll video is legitimate. |
| A speaking cast with no `VOICE:` block | **Stop and ask.** Never pick a voice. |
| Overlapping speech layers | Rejected at plan time, before any audio is generated. |
| Em dash in spoken text | Rejected before the request is sent. |
| No `ELEVENLABS_API_KEY` | Degrade: no generated speech, durations fall back to the word-count estimate, affected scenes marked in `audio-plan.md`. |

---

## Pass 2 — Edit

Assembles the master.

### 2.1 Inventory first

```bash
python3 tools/probe_clips.py {output_folder}
```

Reads every clip's real duration, fps, resolution and whether it has sound, into
`work/clip-manifest.json`. Everything downstream used to assume these numbers; now it reads them.
Read the `problems` list out loud — an A/V mismatch inside a source clip becomes an A/V mismatch in
the master.

### 2.2 Build `work/edit-plan.json`

Segment order comes from `scene-plan.md`. Each scene contributes:

- `Render Path: live-action` → `kind: clip`, its file from `clip-manifest.json`
- `Render Path: explainer` → `kind: shot`, its render from `shots/out/`
- `live-action + overlay:<shot-id>` → composite first with `tools/composite.py overlay`, then point
  the segment at the composited file

Segment length: trim first, re-time the beat second, pad only when the clip is genuinely shorter
than the audio over it, regenerate when the gap is large. A pad above 1.0s is warned about because a
long freeze reads as a stall. **Never speed-ramp to fit** — it changes the motion the model produced
and drags the audio with it.

### 2.3 Print, audit, render

```bash
python3 tools/edit_render.py {output_folder} --print   # the segment sheet + every ffmpeg command
python3 tools/edit_render.py {output_folder}           # render, then the A/V gate
```

The gate is equality within 0.04s. A failure rejects the render.

### Pass 2 edge cases

| Situation | Behaviour |
|---|---|
| A scene has no clip | **Stop and list them.** A silently shortened video is worse than a blocked one. |
| Clip shorter than its beat | Pad, with a warning above 1.0s. |
| Clip longer than its beat | Trim, tail first. |
| `explainer` scene with no rendered shot | Stop. Phase 4.5 is incomplete. |
| Clip with no audio stream | Allowed, flagged. The narration may be carrying that scene. |
| No ffmpeg | Degrade: the plan and every command are printed, nothing renders, the skill says so. |

---

## Degradation

| Missing | Lost | Still works |
|---|---|---|
| `ffmpeg` / `ffprobe` | assembly, compositing | every plan file is still authored and printed |
| `ELEVENLABS_API_KEY` | generated speech, voice conversion | platform-native audio and the whole edit |
| A voice env var | that character's voice | the pass stops and names the variable |

Silent degradation is banned: a pass that could not run says so in the summary, and the skill never
reports a step as done when it was skipped.
