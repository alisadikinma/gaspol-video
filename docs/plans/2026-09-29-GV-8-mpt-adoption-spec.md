**Ticket:** GV-8

# GV-8 — Four adoptions from MoneyPrinterTurbo: video-to-music, visual clip QA, pause tags, act dissolves

## Design

### Problem

A review of `harry0703/MoneyPrinterTurbo` at commit `d477832` (2026-09-29) found features that
the repo has grown since v3.0.0 adopted its subtitle and music-bed rules. Four of them close real
gaps in Phase 5 and Phase 6 of gaspol-video:

1. **Music does not follow the picture.** `tools/gen_music.py` generates a generic track per mood
   from `media/music/library/palette.json`, and `mix_music.py` then trims and fades it to length.
   A phrase is cut wherever the video happens to end, and nothing in the music reacts to a cut.
2. **Rendered clips are never looked at by the pipeline.** P6 (`verify_render.py`) checks what the
   master *says*. The Physical Plausibility Gate (v3.4.0, checks K1-K7) checks what the prompt
   *asks for*. Nothing checks what the paid clip actually *shows*, so a duplicated barrier or an
   upside-down phone is found by the client after the render is paid for — the exact failure
   v3.4.0 documented.
3. **Narration pauses cannot be directed.** `gen_vo.mjs` sends one text per layer; the only lever
   on a pause is punctuation, which the model interprets freely.
4. **Every cut is a hard cut.** `edit_render.py` concatenates normalised parts with `-c copy`. An
   act change reads the same as a cut inside a scene.

Batch ruling: four items, one ticket — all four sit in the Phase 5/6 post-production subsystem.
Path: architectural (one new tool, one new API integration, a new plan-file field).

### Decisions taken in brainstorm (2026-09-29)

| Question | Decision |
|---|---|
| Who judges the rendered clip? | Claude reads extracted frames. TwelveLabs Pegasus rejected: new paid key, needs a public URL or upload. |
| Video-to-music vs the mood palette | Opt-in mode. Palette stays the default; video-to-music falls back to the palette on any failure. |
| Transition at act changes | True dissolve using source handles, so total duration and every downstream timing stay unchanged. |
| Send narration audio to video-to-music? | No. The proxy is picture-only, so the music does not react to spoken words. |

### Item 1 — Video-to-music (`gen_music.py video`)

API facts (fetched 2026-09-29 from
<https://elevenlabs.io/docs/api-reference/music/video-to-music>): `POST /v1/music/video-to-music`,
multipart `videos` (max 10 files, 200 MB combined, 600 s total), optional `description`
(1-1000 chars), optional `tags` (max 10), `model_id` in `music_v1 | music_v2 | music_v2_5`
(default `music_v1`), response is one audio file matching the video length (default mp3). 403 when
the plan does not include Music. 192 kbps mp3 needs Creator tier or above.

- New subcommand `python3 tools/gen_music.py video <project>`; existing palette behaviour and flags
  unchanged.
- `work/music-plan.json` gains `source: "palette" | "video"`, default `"palette"`. Absent field =
  today's behaviour.
- Steps: ffmpeg writes a picture-only proxy of `output/master.mp4` to `.tmp/` (long side 1280 px,
  `-an`); refuse before any request when the master exceeds 600 s or the proxy exceeds 200 MB.
  `description` is built from the script's music direction in `av-script.md`, truncated to 1000
  chars; `tags` from the tone (`video_tone`), max 10. `model_id` defaults to `music_v2`.
- Output: `output/music.mp3`. `mix_music.py` consumes it exactly as it consumes a palette track —
  the measured -12 dB headroom rule and ducking in `17-music-bed.md` apply unchanged.
- No double billing: the request is recorded in `renders.json` keyed by the sha256 of the proxy's
  source master plus the description and tags. An unchanged key reuses the file; `--force`
  re-requests.
- Failure (403, 422, network, over limit): print the reason, fall back to the palette track, keep
  the fail-soft rule — a finished video without a generated bed is still a deliverable.
- Stdlib only (urllib multipart), same as the rest of `gen_music.py`.

### Item 2 — Visual clip QA (`tools/qa_frames.py`)

- New stdlib tool: `python3 tools/qa_frames.py <project> [--scenes 5,6,7]`. For every clip in
  `renders.json` with a finished status (or the given scenes), extract five frames with ffmpeg at
  0 %, 25 %, 50 %, 75 % and the last frame, tile them into one contact sheet
  `.tmp/qa-scene-NN.jpg`; the five timestamps are written on the `sheet:` line of `work/visual-qa.md`, not drawn on the image (ffmpeg `drawtext` needs a freetype build, and a sheet that fails to render on some machines is worse than an unlabelled one). Amended 2026-09-30 after the plan-verifier audit.
- It writes or updates `work/visual-qa.md`: one section per scene carrying the scene's
  `PLAUSIBILITY:` block copied verbatim from `video-prompts.md`, the contact sheet path, and an
  empty verdict row per question (MECHANISM, COUNT, FLOW, FACING, PAIR, PEOPLE, OVERLAY SURFACE).
  Existing verdicts are preserved on re-run; a scene whose clip changed (hash differs) has its
  verdicts cleared.
- `video-gen` (and `video-engine-agent`) gain a step after every render batch: run the tool, read
  each contact sheet, fill each verdict with `PASS`, `FAIL: <what is visible>` or
  `UNSURE: <why frames cannot tell>`. Any FAIL is offered as a re-render before the next batch is
  rendered. UNSURE is never written as PASS.
- Validator check **V15**: a rendered clip with no verdicts, or with an unresolved FAIL, fails
  `video-validate --video`.
- Known limit, written into the reference: motion between sampled frames is not seen.

### Item 3 — Pause tags in narration (`gen_vo.mjs`)

- Syntax inside narration/dialogue text: `[pause: 1.5s]` or `[jeda: 1.5s]`; allowed range
  0.2-5.0 s; out of range or malformed → error naming the layer id.
- `gen_vo.mjs` splits a layer at its tags. Each speech chunk is one TTS request, still chained
  through `previous_request_ids`, so delivery stays warm across the pause. Silence is generated
  with ffmpeg `anullsrc` at the chunk sample rate for the exact duration; chunks and silences are
  concatenated into the layer's single mp3.
- Word timings in `vo-manifest.json` are offset by each chunk's *measured* duration (ffprobe), not
  by the requested pause, so captions and P6 stay aligned. A layer with no tag produces exactly
  today's request and manifest.
- ffmpeg becomes required only for layers that carry a tag; absent ffmpeg with a tag → error, not
  a silent tag-less render.
- Tags are stripped wherever script text is compared or displayed: `gen_captions.py`, `gen_subs.py`,
  `verify_render.py`, `check_vo_duration.py`. One shared stripping rule per language (Python
  helper + the JS parser), tested against the same fixture strings.
- Validator: a pause tag inside a VEO/Seedance/Kling prompt is a FAIL — the platform would speak
  it.

### Item 5 — Dissolve at act changes (`edit_render.py`)

- Optional segment field `"transition_in": {"kind": "dissolve", "dur_s": 0.5}`; `dur_s` 0.2-1.0;
  not allowed on segment 1. Unknown kind or out-of-range value → `PlanError` naming the segment.
- `video-post` writes the field only on the first segment of a new act, taken from the beat labels
  in `scene-plan.md`. Everywhere else stays a hard cut.
- Timing: the previous segment is rendered `dur_s` longer, using source frames after its `out_s`.
  The two parts are joined with `xfade` (video) and `acrossfade` (audio) at offset = the previous
  segment's planned length. The incoming segment therefore starts at exactly the second it starts
  today; total duration is unchanged, so VO, captions, SFX and music timing do not move.
- If the source has fewer than `dur_s` seconds after `out_s`, `load_plan` raises `PlanError`
  naming the segment. No freeze-frame fallback.
- The A/V duration gate still runs on the master. A plan with no `transition_in` produces
  byte-identical ffmpeg commands to today (asserted by test).

### Data Integration Map

| Component | Data source | Existing? | Notes |
|---|---|---|---|
| Video-to-music | `output/master.mp4`, `av-script.md` music direction, tone | Yes | ElevenLabs key already in `.env`; needs a paid Music plan |
| Music ledger | `renders.json` via `tools/renders.py` | Yes | New entry kind for music |
| Visual QA | `renders.json`, `clips/`, `video-prompts.md` PLAUSIBILITY blocks | Yes | New `work/visual-qa.md` |
| Pause tags | `work/audio-plan.json` layer text | Yes | Manifest schema unchanged |
| Dissolve | `work/edit-plan.json`, `scene-plan.md` beat labels | Yes | New optional field |

### Tests

- `gen_vo`: tag parser (both spellings, range, malformed), chunking, manifest offset from measured
  durations (fake fetch + fake probe), untagged layer unchanged.
- Tag stripping: shared fixtures run by the Python and Node tests.
- `edit_render`: `transition_in` validation, insufficient handle refused, command build for a
  dissolve, untagged plan byte-identical.
- `gen_music video`: multipart body shape, 403 → palette fallback, ledger reuse, 600 s refusal.
- `qa_frames`: frame timestamps, `visual-qa.md` skeleton, verdict preservation, clearing on hash
  change.
- Consistency: V15 and the pause-tag prompt check documented in the validator skill and the
  reviewer agent; version gates at 3.6.0.

### Docs and version

- References: `17-music-bed.md` (video source), `11-voice-cast-and-vo.md` (pause tags),
  `13-ffmpeg-edit.md` (dissolve), `10-physical-plausibility-gate.md` (post-render frame check),
  `10-post-production-pipeline.md` (music-plan and edit-plan schema).
- `CLAUDE.md` architecture table (+`qa_frames.py`, tool count 20), debugging rows, v3.6.0
  changelog; `NOTICE` gains the adapted items under MoneyPrinterTurbo.
- `plugin.json` 3.5.0 → 3.6.0.

### Out of scope

TwelveLabs; Sonilo; the other video-model adapters (OFox, Volcengine, MuAPI, MiniMax) and the
no-retry-on-ambiguous-billing rule (worth its own ticket); slide/zoom transitions; transitions
anywhere except act changes; per-platform social metadata; hardware encoders; batch variants.
