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
     --voice-env ELEVENLABS_VOICE_C2 --spans 0-3.88 \
     --out {output_folder}/vo/scene-NN-c2.mp3
```

`gen_vo.mjs` stitches consecutive requests so prosody carries across scenes, and writes
`vo-manifest.json` with measured durations and word timings — the input for pass 2 and pass 4.

**`--spans` is MANDATORY whenever the scene has more than one speaker.** Speech-to-speech converts
whatever audio you hand it, so a whole-track conversion rewrites every voice in the clip, including
the ones that were already right. Take the target's turns from `av-script.md` — it already records
who says what — and cross-check against `vo-manifest.json` word timings. Do not rely on speaker
diarization: it merged two AI voices into one label on a real clip. Where the script is ambiguous,
pitch separates them (see `11-voice-cast-and-vo.md` §5).

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

## Pass 3 — SFX

### 3.1 Derive cues from what this plugin already knows

For each scene, in this order:

1. **`strategic-brief.md` > DOMAIN CONTEXT** — the machinery actually in that room, from the six
   location-qualified research queries. `amb-factory-floor` is not "factory sounds"; it is the bed
   this specific place has.
2. **Cultural research** (Phase 3.5) — outdoor scenes carry the traffic and birdlife of that place,
   or they sound like stock footage of nowhere.
3. **The visual beat** — the cut, the reveal, the moment a number lands.

Score the ambience first. It carries most of the realism and it is the part a generic SFX pass
cannot do.

### 3.2 Library first

```bash
python3 tools/gen_sfx.py --library media/sfx/library --dry-run   # what is missing
python3 tools/gen_sfx.py --library media/sfx/library             # generate only the misses
```

Reuse a catalogued clip before generating one. New recipes get GENERIC ids so the next project
reuses them.

### 3.3 Author `work/sfx-plan.json`, then AUDIT

```bash
python3 tools/mix_sfx.py {output_folder} --print
```

**This is a hard gate**, the same kind as the Phase 3.5 reference gate: the user reads the cue sheet
and approves it BEFORE anything is mixed. Not a formality, and not skippable because the sheet looks
obviously fine.

Density 8 to 12 cues per minute; everything past that carries `optional: true`.

### 3.4 Mix and verify with numbers

```bash
python3 tools/mix_sfx.py {output_folder}
```

The tool prints how many dB each cue actually added over the voice-only reference:

| Cue kind | Must add |
|---|---|
| Story-critical | **+4 dB** or more |
| Texture | +1 to +3 dB |

Four ways this measurement lies, all handled by the tool but worth knowing when reading its output:

- a **0.3s** window is used for transients, because 0.6s averages a 50ms click into nothing
- a riser is measured at its final third, where its energy is
- an adjacent loud cue can leak into a wide window and fake a pass
- **a cue sitting fully under continuous speech measures +0 dB at ANY gain.** Accept it as
  felt-not-heard or delete it. Never chase it with gain: it spikes the moment a pause arrives.

A cue the user calls "noisy" is a CHARACTER problem. Swap the sound or use silence; turning it down
just makes quiet noise.

---

## Pass 4 — Subtitles and music

Both are fail-soft. A caption or music failure warns and still ships the video.

### 4.1 Subtitles

```bash
python3 tools/gen_subs.py {output_folder}          # cues + output/master.srt
python3 tools/burn_subs.py {output_folder}         # burn them in
```

Caption text comes from the script, always. A recognizer supplies timing only, and only for dialogue
the platform generated — narration from ElevenLabs already carries word timings in
`vo-manifest.json`, so those captions cost nothing extra.

Review the cue text with the user before burning. Nothing is guessed: a scene with no timing source
is listed as untimed rather than given invented timings.

The `no subtitles` negative stays in every platform prompt and does not conflict — that stops the
model drawing text into the picture. An em dash in a caption is correct; the ban covers spoken text.

### 4.2 Music

```bash
python3 tools/mix_music.py {output_folder}
```

The track is derived from the per-scene music direction already in `av-script.md` plus the video
tone, not asked for again. The bed sits at least 12 dB below the voice by measurement.

Mix SFX before music: cues are short and land on moments, the bed is continuous, and a bed competing
with a cue makes both mushy.

### Pass 4 edge cases

| Situation | Behaviour |
|---|---|
| No `ASSEMBLYAI_API_KEY` | TTS-timed cues still built; scenes needing the recognizer listed as untimed |
| Font cannot draw a character | Refuse and name the characters. A box ships silently otherwise. |
| Caption contrast below 4.5:1 | Refuse. It disappears on the frames that happen to match. |
| Line too long for one screen | Split into consecutive cues, never squeezed or clipped |
| No music direction in the script | Pass does nothing and says so |
| Track fails to load or mix | **Warn and ship the voice-only master.** Exit 0. |

---

## Pass 5 — Final mix

```bash
python3 tools/mix_sfx.py {output_folder}            # duck + limiter
```

- Sidechain duck under the voice, safety limiter after it
- Integrated loudness to **-14 LUFS**, true peak ceiling -1.0 dBTP
- Re-run the A/V duration gate on the mixed file: equality within 0.04s, or the render is rejected
- Print the per-cue dB table one final time and read it

Then produce the playable transcode if the master is 10-bit HEVC, with `-r` before `-i` so no frame
is dropped:

```bash
ffmpeg -r <src_fps> -i master-mixed.mp4 -c:v libx264 -crf 19 -pix_fmt yuv420p -c:a aac master-h264.mp4
```

### Final summary

Report what exists and what did not run:

```
output/master.mp4         assembled, A/V gate passed
output/master-mixed.mp4   {N} SFX cues, music {yes/no}, captions {burned/sidecar/none}
output/master.srt         {M} cues, {K} scenes untimed
Not run: {anything that degraded, and why}
```

A pass that could not run is named here. It is never reported as done.

---

## Degradation

| Missing | Lost | Still works |
|---|---|---|
| `ffmpeg` / `ffprobe` | assembly, compositing, mixing, burn-in | every plan file is still authored and printed |
| `ELEVENLABS_API_KEY` | generated speech, voice conversion, SFX generation | platform-native audio, the edit, and any catalogued SFX |
| `ASSEMBLYAI_API_KEY` | timing for platform-spoken dialogue | captions for ElevenLabs narration, from TTS timestamps |
| A voice env var | that character's voice | the pass stops and names the variable |
| A music track | the bed | the voice-only master still ships, with a warning |

Silent degradation is banned: a pass that could not run says so in the summary, and the skill never
reports a step as done when it was skipped.
