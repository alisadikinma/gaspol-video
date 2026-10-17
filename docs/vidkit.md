# vidkit: reusable animation and assembly library

`tools/vidkit/` collects the helper scripts that kept being rewritten per project (Ekaputra, Moni
Batam, indusia-ai-fms catalog-4, REA, Dampak) into one tested package. Core is stdlib + ffmpeg.
Only `bond` needs `cv2` + `numpy` (the `tools/setup.sh` venv has them).

Run from the plugin root: `python3 -m tools.vidkit --help`. Import: `from tools.vidkit import join, gates`.

| Module | What | Replaces (per project) |
|---|---|---|
| `ff` | `probe` (video dict carries `pix_fmt`), `duration`, `has_audio`, `missing()` and `TOOLS` (binaries not on PATH), `FFMissing` (a `FFError` naming the absent binary), `run` (`heartbeat_s=N` prints `still running: <file> <s>s` every N seconds), `ffmpeg` | ad-hoc `ffprobe` helpers in every script |
| `encoder` | `available`, `choose`, `video_args`, `run_with_fallback` (env `GASPOL_VIDEO_ENCODER`, see below) | the hard-coded `-c:v libx264 ...` in each encode |
| `gates` | `gate_av` (video = audio length), `gate_uniform` (same sample rate and channels before concat) | `gerbang.py` |
| `join` | `concat_copy`, `join_xfade`, `clip_starts` (timeline maths for dissolves) | `join.py`, the `rakit_*.py` concat steps |
| `patch` | `freeze_box`: freeze a rectangle of a clip to one frame | `freeze_patch.py` |
| `sheet` | `contact_sheet` (evenly spaced, or exact `times=[...]`), `montage` | `sheet.py`, `mont.py` |
| `synth` | `notification`, `alarm`, `render` (layered ffmpeg tones) | `bunyi-notif.py`, `bunyi-alarm.py` |
| `speech` | `words_from_alignment`, `speech_spans`, `gaps`, `snap_to_gaps`, `energy_db` | `kata.py`, `energi.py`, `geser_cue.py` |
| `loudness` | `normalize`: two-pass loudnorm, audio trimmed to picture | `mix_akhir.py` |
| `bond` | `bond_print`: motion-tracked print on cloth (needs cv2) | `shirt_bond.py` |
| `tidy` | `vidkit tidy <project>`: scan, `--apply` moves unknown folders to `_arsip/`, `--empty-tmp` empties `.tmp/` but keeps every file in `.tmp/image` and `.tmp/video` unless re-verified as a copy of a home file, and keeps `.tmp/vocache-*`; failures are listed and exit 1 | hand-made cleanup `rm`/`mv` in a project |

## Lessons baked in (each cost a real re-render)

- `concat` builds the encoder from the FIRST file: mixed mono/stereo or 44.1/48 kHz corrupts the rest. `gate_uniform` runs first.
- `xfade` overlaps clips, so total length shrinks by the transitions. Take every time point from `clip_starts`. A 0 s transition inside a dissolve chain breaks it; `join_xfade` clamps to one frame.
- Audio is never cross-faded: each clip's audio stays whole and is delayed to its start.
- `loudnorm` shifts timestamps ~0.08 s. Reset with `asetpts` before `atrim`, else real audio is cut and the A/V gate fails.
- A sidechain-ducked mix mutes SFX under narration at any gain. `snap_to_gaps` moves the cue into a speech gap instead.
- ffmpeg `sine` is ~18 dB below full scale. Synth gains are corrected for it; read `synth.measure`.
- `apad` after `amix` truncated to the longest input on some runs. `synth.render` and `join_xfade` add a silent bed of full length instead.

## Not folded in (and why)

- Per-project `rakit_k*.py`, `build_k*.py`, `mix.py`: they hard-code scene ids, timings and file names. The reusable pieces inside them are now the modules above.
- `track_quad.py`, `sudut-lacak.py`, `lacak-layar.py`, `layar.py` (4-corner phone/monitor tracking): overlap `tools/track_screen.py`. Their per-frame matte idea is a candidate for a later merge there.
- Slide tooling: moved to `gaspol-catalog` `tools/deckkit`.
- Remotion `gen-registry`, `render-all`, `render-stills`, `qa-frames`, `captionPages`, `overlayFx`: already identical to `templates/remotion/` (projects copied them). Verified with diff.

## Node (`tools/vidkit/js/`)

| Module | What | Replaces |
|---|---|---|
| `env.mjs` | `parseEnv`, `loadEnv`, `requireKeys` (names missing keys, never values) | the `parse()` pasted at the top of every project script, with a hard-coded .env path |
| `eleven.mjs` | `tts` (settings + seed), `sttWords` (Scribe word timings), `sfx`; CLI `tts|stt|sfx` | `tts-satu`, `tes-suara`, `stt`, `sfx/gen` |
| `ff.mjs` | `probeDuration` (seconds, or `null` when the binary is missing or the file unreadable); the only Node file that calls the probe binary | the `probeDuration` copies in `gen_vo.mjs` and `voice_changer.mjs` |
| `cast_voice.mjs` | voice change with per-character settings and seed, spans only; plan json | `voice-changer/run.mjs` (which also imported the plugin by a versioned cache path) |

`templates/remotion/scripts/frames.mjs` and `qa-end.mjs` (multi-frame / end-state QA) now ship with every scaffold.

Tests: `tests/py/test_vidkit.py`, `tests/node/vidkit-js.test.mjs` (run with the venv python to include the `bond` test).

## Ingest (`tools/vidkit/ingest.py`)

| Function | What |
|---|---|
| `download(url, dir, name, cookies_from_browser, section)` | yt-dlp, best mp4 with audio; `cookies_from_browser="chrome"` reads that browser's login (Instagram refuses anonymous downloads, YouTube may 403); `section="START-END"` fetches only that range |
| `scenes_from_cuts(cuts, duration, min_len)` | cut times to scene spans; flash cuts under `min_len` are dropped |
| `split_scenes(video, dir, threshold, min_len)` | scene clips, first/mid/last stills, `scenes.json` |

Used by `skills/video-repackage`. CLI: `vidkit ingest`, `vidkit scenes`.

## Audio study (`tools/vidkit/audiostudy.py`)

| Function | What |
|---|---|
| `decode_mono(path)` | 16 kHz mono samples; `ValueError` when there is no audio stream or no file |
| `onsets(samples, rate)` | transient times; silence and steady tones give `[]` |
| `tempo(onset_times)` | BPM folded into 60-180, or `None` under 4 onsets |
| `energy_profile(path, seg_s)` | dBFS per segment, a tail under 0.5 s dropped |
| `relate(onsets, words, cuts)` | each onset labelled `on-word`, `on-cut`, `both` or `free` |

Onsets cannot tell a sound effect from a consonant: read results with word timings, never as music tempo on its own (`docs/evals/viral-audio-study.md`). CLI: `vidkit audiostudy`.

## Prosody (`tools/vidkit/prosody.py`)

How a voice is delivered, so a new take can copy the delivery of a reference voice without copying the voice. Pure Python (no numpy).

| Function | What |
|---|---|
| `load_words(path)` | gen_subs `{"words":[{text,start_ms,end_ms}]}`, raw AssemblyAI `{"words":[{text,start,end}]}` (ms), `[[word,start,end]]` or `[{word,start,end}]` to `[(word, start_s, end_s)]` |
| `sentences(words)` | split on `. ? !`; per sentence `wps` and `pause_after` |
| `read_wav(path)` | mono 16-bit PCM only (`ffmpeg -ac 1 -c:a pcm_s16le`); stereo raises |
| `pitch_hz(samples, sr, t0, t1)` | autocorrelation at the word's middle; `None` when unvoiced |
| `report(wav, words, stress_z)` | `overall` (wps, mean pause, median pitch, p10-p90 pitch range in semitones), `sentences`, `emphasis` (loudness + pitch z-score ≥ `stress_z`), `words` |
| `gate(rep, min_range_st, min_wps, max_pause_s)` | problems against targets; `[]` passes |

Use: measure the reference (pace, pauses, stressed words), write per-line delivery direction, then gate every take before speech-to-speech: a voice changer keeps the input's pitch and pace, so a flat take stays flat. A music bed under the reference inflates stress on function words; pick the stressed words by hand from `emphasis`. Measure the reference first and derive the gate thresholds from it; there is no universal "engaging" number. CLI: `vidkit prosody <wav> <words> [--out] [--min-range-st] [--min-wps] [--max-pause]`, exit 1 on a gate failure.

## Tighten (`tools/vidkit/tighten.py`)

| Function | What |
|---|---|
| `plan_cuts(words, max_gap, keep)` | gaps longer than `max_gap` between ASR words become cuts that leave `keep` seconds (half each side) |
| `apply(audio, words, out, max_gap, keep)` | writes `out` with those cuts; `{cuts, removed_s, duration}` |

Run it on a guide-voice take before speech-to-speech (which keeps durations), never on a clip with lip-sync. Pair with `tools/guide_vo.py` (stock-voice takes on eleven_v3 with audio tags) and `vidkit prosody` (gate). CLI: `vidkit tighten <audio> <words> <out> [--max-gap] [--keep]`.

## Place voice (`tools/vidkit/placevoice.py`)

| Function | What |
|---|---|
| `ambience_gaps(words, duration, min_gap, pad)` | spans with no ASR word |
| `quiet_runs(env, max_db, min_len)` | spans where the dB envelope stays under `max_db` |
| `intersect(a, b, min_len)` | overlap of two span lists |
| `separate(clip, work_dir, model)` | Demucs two-stem split of the clip's audio; returns the background (`no_vocals.wav`) stem |
| `place(clip, voice, words, out, space, bed_db, min_gap, quiet_below_db, bed)` | clip video + voice with body EQ, light compression and a faint reflection, level-matched AFTER that chain to the original speech, over the bed. `bed`: `gaps` (default: loop of word-free, quiet gaps), `stems` (experimental: Demucs background, whole clip) |

Speech-to-speech output is studio-dry; on location it reads as a dub. Video models also laugh and breathe without an ASR word, so in `gaps` mode a gap is used only when it is `quiet_below_db` (12) under the median speech level. CLI: `vidkit placevoice <clip> <voice> <words> <out> [--space] [--bed gaps|stems] [--bed-db]`.

Rules (field case: a 4 s VEO line, three versions):
- Never mux a converted on-camera voice raw: it sounds pasted on.
- Match the level AFTER the space chain. Matching before it, with an echo `out_gain` of 0.6, lost ~5 dB and the voice sounded deflated. `test_speech_level_matches_original_after_the_chain` keeps ±1 dB.
- Keep the default `--bed gaps`. `--bed stems` (Demucs background under the whole clip) was tried on the same 4 s line and the owner judged it WORSE than the 0.38 s looped gap. Use stems only as an experiment, keep the gaps render beside it, and let the owner pick by ear. Install for that: `uv tool install --python 3.11 demucs --with soundfile`.

## Reframe (`tools/vidkit/reframe.py`)

| Function | What |
|---|---|
| `parse_keys("T:CX,...")` | keys; CX = subject centre as a fraction of the frame width |
| `center_at(keys, t)` / `x_expr(keys, w, win_w)` | linear pan between keys, held at the ends; ffmpeg crop `x` expression, clamped in frame |
| `apply(src, out, keys, zoom, size)` | 9:16 window panning across wide footage, scaled to `size`, audio dropped |
| `fit(src, out, size, blur)` | whole wide frame centred over a blurred copy, for a subject wider than any 9:16 window |

Official 16:9 product footage into a 9:16 short: a centre crop loses a moving car. Read CX off a gridded contact sheet (10% lines), give 2-4 keys per clip, then look at frames of the result before using it. A side-on close-up wider than ~32% of the frame gets `--fit`. CLI: `vidkit reframe <src> <out> --keys 0:0.6,2:0.45 [--zoom 1.0]` or `--fit`.

## Grain (`tools/vidkit/grain.py`)

| Function | What |
|---|---|
| `vf(strength)` | ffmpeg filter `noise=alls=S:allf=t` (moving grain), strength 1-40 |
| `apply(src, out, strength, crf)` | `src` with grain, audio copied; refuses `out == src` |

Generated skin and backgrounds have no sensor noise, so faces read as plastic next to real footage. Give every clip of a film the same strength (6-8 subtle on a phone, 14 only to demonstrate) so generated shots and official footage look like one camera. Write to a new file; the approved clip stays. CLI: `vidkit grain <src> <out> [--strength 7]`.

## Finishing (`karaoke`, `cover`, `unwhite`, `mixdown`)

| Module | What |
|---|---|
| `karaoke.build_ass(words, total, watermark, opacity, profile=)` | karaoke ASS (`\kf`), groups close at sentence end, `C Sharp` becomes `C#`, optional centre watermark. Default profile `short-organic`: 56 px, 4 words in 2 lines, last baseline about 61.7% from the top; `--profile none` = old 2-word look |
| `cover.apply(video, thumb, out, ass, hold_s)` | burns subtitles, THEN lays the thumbnail on the first `hold_s` seconds (so no subtitle on it), attaches it as cover art |
| `unwhite.unwhite(src, out)` | keys the white box out of a logo (ffmpeg only, no numpy) |
| `mixdown.run(plan)` | voice + SFX cues + sidechain-ducked music, two-step loudness (gain to target, then limiter), subs, thumbnail |

`mixdown` plan keys: `video out total ass thumb hold cues[{at,sfx,gain}] music{file,start,gain,fade_in,fade_out} lufs loudness_profile limit`. Cue `at` is absolute seconds; `sfx` is a path or a library clip name. Use absolute paths in the plan. Checked against the REA film: same loudness and peak as the project's own mix script (-14.8 LUFS before gain, peak -1.3 dBFS).

### Loudness profiles

`media/loudness-profiles.json` holds named targets (`lufs`, `true_peak`, `source`). `loudness.profile(name)` returns the two numbers. Rules:

- Every profile needs a non-empty `source` (URL or document title). An unsourced number is refused with `ProfileError`.
- `lufs` must be in [-24, -6], `true_peak` in [-9, 0]. Duplicate names and malformed JSON are refused. A missing file falls back to the built-in -14 / -1.0 with a warning.
- Only `default` ships (-14 LUFS, -1.0 dBTP). Add another only with a real source.
- `vidkit normalize SRC OUT --profile NAME` prints the profile and targets used; unknown or invalid profile exits 2. An explicit `--lufs` wins over the profile's loudness. Mixdown: plan key `loudness_profile`; absent means today's -14; an explicit `lufs` key wins. Mixdown applies only the profile's `lufs`: its `true_peak` is ignored, because mixdown keeps its own limiter (`limit`, default 0.78). Only `vidkit normalize` uses the profile's `true_peak`.
- Tests can point at another file with the `GASPOL_LOUDNESS_PROFILES` env var.

Remotion: `templates/remotion/lib/ali-effects.tsx` (copied into every scaffold). Props only, each start frame is a prop.

## Colour (`color`)

Final encodes are tagged BT.709, so players do not guess the matrix. `edit_render.py` (segment and dissolve-merge encodes) and `mixdown` (final mux) add `color.ENCODE_FLAGS` and end the video filter with `color.TAG_FILTER` (`setparams=...`). The `setparams` filter is what writes the tag; the encoder flags alone leave an untagged input untagged. Stream-copy steps are not touched.

| Function | Use |
|---|---|
| `probe_color(path)` | `color_space`, `color_primaries`, `color_transfer`, `color_range`; `unknown` when missing; `ff.FFError` "no video stream" when there is none |
| `convert_filter(probe, warnings=None, source="")` | `""` for bt709 or untagged (assumed bt709); `colorspace=all=bt709:iall=bt601-6-525` / `-625` for smpte170m / bt470bg; `""` plus a line in `warnings` for HDR (`smpte2084`, `arib-std-b67`) or an unknown matrix. It never converts on a guess |

`edit_render.py` probes every source clip and puts `convert_filter` in front of the scale chain, so an explicitly bt601 clip (smpte170m / bt470bg) is converted before it is tagged bt709, and its colours are preserved. Untagged and bt709 sources get no extra filter, so their commands are unchanged. HDR or an unknown matrix is tagged bt709 without conversion and prints one stderr warning per file (`... left unconverted; tagged bt709 anyway`). A source that cannot be probed is not converted. The dissolve merge and `mixdown` only read already-rendered bt709 files, so they need tagging only.
Full-range sources (`color_range=pc` or a `yuvj*` pix_fmt) get `scale=in_range=full:out_range=tv` first, so the tv tag is true (measured: full-range black/white Y 0/255 became 16/235). `color.source_filters(path, warn=None)` returns the ordered list `[range, matrix]`; `edit_render`, `colormatch.apply` and `mixdown` all use it. A matrix of `unknown` is read from the primaries or transfer (smpte170m / bt470bg means bt601); a file with no colour tags at all is assumed bt709 with one warning. A probe that fails on an existing file prints one stderr warning naming the error (a file that does not exist yet stays silent). `probe_color` also returns `pix_fmt` and uses the resolved `ffprobe`.

## Colour match (`colormatch`)

Pulls clips of one kelompok toward one colour. Report first; rewriting is a separate step the owner approves.

| Function | What |
|---|---|
| `colormatch.mean_rgb(path, samples=5)` | mean (r, g, b) 0-255 over `samples` evenly spaced frames, each scaled to 1x1 `rgb24` by ffmpeg. `ColorMatchError` names an undecodable file |
| `colormatch.plan(paths, reference=None, max_gain=0.15)` | per clip `{file, mean, gain, delta, suspect?}`. Reference is the `reference` clip or the per-channel median. `gain = ref/clip`, clamped to `1 +/- max_gain`; `delta` = largest `abs(gain - 1)`. A near-black clip (mean under 8) is `suspect: near-black` with gain (1,1,1). One clip: gain (1,1,1) |
| `colormatch.apply(path, out, gain)` | `colorchannelmixer` plus the BT.709 tags from `color.py`, audio stream-copied. Refuses `out` equal to `path` |

CLI: `vidkit colormatch CLIPS... [--reference F] [--max-gain 0.15] [--min-delta 0.03] [--apply OUTDIR]` prints a table (file, mean, gain, delta, note) and one spread line (largest per-channel max-min, before and, with `--apply`, after). Without `--apply` nothing is written. With `--apply`, only clips with `delta >= --min-delta` are rewritten into OUTDIR; the others are copied untouched. Sources are never modified, and an OUTDIR that would overwrite a source is refused. The 0.15 clamp limits how much one clip may move: a clip further off than that stays visibly off, and the spread line shows it.
`--force` lets `--apply` overwrite files already in OUTDIR; without it an existing target is refused before anything is written. A target equal to a source or to `--reference` is refused even with `--force`. The table has a `frames` column (`5/5`: sampled frames that decoded); fewer than half decoding raises `ColorMatchError` naming the file. `apply` runs `color.source_filters` on its input first, so a bt601 or full-range input is converted, not relabelled.

## Beats (`beats`)

| Function | What |
|---|---|
| `beats.detect(path, hop_s, min_gap_s, threshold)` | ffmpeg decodes to mono 16 kHz PCM; short-time energy, positive differences, local maxima above `threshold` x the median onset (and a small absolute floor); beats closer than `min_gap_s` collapse to the stronger. `[]` for silence. `BeatError` when ffmpeg is missing or the file cannot be decoded |
| `beats.snap(times, beats, window_s)` | each time goes to the nearest beat within `window_s`, else stays |

CLI: `vidkit beats FILE` prints the times as JSON. `tools/sfx_snap.py` applies `snap` to a cue sheet and writes a new file. Onset energy suits percussive music; a pad-only bed may return `[]`, and then `sfx_snap.py` exits 3 (2 is bad input) and leaves the plan alone. `sfx_snap.py --music-plan` collects the beats of every music-plan segment (`library:<id>` or project path), cut to the segment, repeated for a looped short track, shifted by `from_s`.

## Stage cache (`stages`)

| Function | What |
|---|---|
| `stages.fingerprint(files=(), params=None, version="1")` | sha256 over each file's content sha256 (1 MiB chunks, in order, names ignored), the canonical json of `params` and `version`. Optional `sha_memo` dict hashes a file used by many stages once (key: path, mtime_ns, size). `StageError` names a missing file |
| `stages.StageCache(path).is_fresh(stage, fp, outputs)` | true only when the recorded fingerprint equals `fp` AND every output file exists |
| `stages.StageCache(path).record(stage, fp, outputs)` | writes atomically (temp file + `os.replace`). A corrupt or absent cache file reads as empty. An unwritable place prints one stderr warning and turns caching off for the run, never a crash |

Used by `tools/edit_render.py`: parts live in `<project>/.tmp/edit-parts/` with `stages.json`. The fingerprint covers the source bytes, the segment's plan fields, the final ffmpeg command (colour flags included) and `RENDERER_VERSION`. `--no-cache` forces a full render. `--print` ends with a `cached`/`rendered` line per stage.
A part is encoded to `part-NNN.tmp.mp4` and renamed into place only when ffmpeg succeeded, and the stage's cache entry is dropped (`StageCache.drop`) BEFORE the encode. A killed encode or a failed `record()` therefore re-encodes next run; it never reuses a truncated or foreign part. The cache file is written through `tempfile.mkstemp` (no predictable temp name to symlink). The concat list escapes `'` in paths as `'\''`.

## Encoder choice (`encoder`)

`GASPOL_VIDEO_ENCODER` selects the video encoder of `tools/edit_render.py` encodes. Default (unset) is `libx264`: the encoder arguments are the same libx264 recipe as before; the colour tag (`setparams` plus the bt709 flags) is added to every encode. `auto` uses `h264_videotoolbox` when `ffmpeg -hide_banner -encoders` lists it, else libx264. An explicit `h264_videotoolbox` that is not available falls back to libx264 with a warning. Any other value is an error.

Hardware is opt-in because its quality per bitrate differs from CRF 20. It takes a bitrate by short side (1080: 12M, 720: 6M, other: 8M). A failed hardware encode is retried once with libx264 and logs `encoder X failed, retried with libx264`. The cache fingerprint covers the final command, so a changed encoder re-encodes the parts. `edit_render` also prints `still running: <part> <s>s` every 30 seconds during an encode.

Measured 2026-10-16 on this Mac (3 synthetic 1080x1920 clips of 6s, `--no-cache`): libx264 1.2s, 16.9 MB; `auto` (h264_videotoolbox used) 2.9s, 27.5 MB. Both passed the A/V gate. No benefit on that clip, so the default stays libx264.

## Machine-learning tools (`ml`, `pointtrack`, `segment`)

Point tracking and segmentation need torch, so they run in their own venv, `venv-ml`, kept apart from the shared `venv` (a torch upgrade never breaks Pillow, Playwright or mediapipe tools). Build it once with `bash tools/setup.sh --ml` (needs Python 3.10+; set `PYTHON_ML=/path/to/python3.10+` if the default is older). The script also fetches two weights into `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/models/`, each from a pinned URL and checked against a pinned sha256 (a mismatch deletes the download and stops): `tapnextpp_ckpt.pt` (TAPNext++, Apache-2.0) and `sam2.1_hiera_small.pt` (SAM 2.1, Apache-2.0). Rejected: CoTracker3 (CC-BY-NC, no commercial use) and SAM 3 (CUDA only).

`ml.py` imports only the standard library. `ml.weight(name)` returns a weight path and re-checks its sha256; `ml.device()` picks the torch device; `ml.require()` checks torch. A missing venv, weight or torch raises `ml.MLMissing` with a message ending `run tools/setup.sh --ml`.

`pointtrack.track(frames, queries)`: `frames` is uint8 `[T, H, W, 3]` RGB, `queries` is float `[N, 3]` of `(t, x, y)` pixels. Returns `tracks [T, N, 2]` and `visible [T, N]` bool. TAPNext++ follows a point through occlusion.

`segment.masks(frames, frame_idx, points=[[x, y]], labels=[1], box=None)`: SAM 2.1 masks an object through the clip from a click or a box on one frame. Returns bool `[T, H, W]`; a frame where the object is gone is all False.

## Screen insert (`screen`, `vidkit screen-insert`)

`python3 -m tools.vidkit screen-insert <clip> <panel> <out> --mode green|track [--corners x,y,x,y,x,y,x,y] [--occluder x,y] [--qa DIR]`

`tools/track_screen.py` only reads `--corners`; `templates/remotion/lib/quad-screen.tsx` is legacy.

`panel` is a PNG (held) or an mp4 (looped or cut to the clip). The output keeps the clip's size and frame count; the clip's audio is re-encoded to AAC and padded with silence to the video length, so audio shorter than the video never shortens it. The file is written to a hidden temp file and moved over `<out>` only when its duration matches the frames written, so a failure leaves a previous `<out>` alone. A phone clip with a display-rotation tag is decoded upright (`ff.probe` returns the displayed `width`/`height` and a `rotation` key). A 16-bit PNG panel is scaled to 8 bits; a video panel with an alpha channel keeps it.

- `--mode green`: for a screen prompted as `flat solid chroma green screen` (video-gen Rule 26). Per frame it keys the green, takes the largest blob, fits one line per side (RANSAC) and intersects them. A finger over an edge only adds outliers, so the corner does not move. Corners are smoothed with a One-Euro filter. Refuses `green key missing on <n> frames` (over 5% of the clip) and `green key missing on frames A-B` (0.5 s running), a `corner jump` after smoothing, and `screen mostly not green on frames A-B` (over 60% of the screen not green for 0.5 s). The JSON result has `occluder_share_max`.
- `--mode track`: for a clip with no key colour. `--corners` gives the four corners at frame 0, clockwise from top-left. TAPNext++ tracks points on and around the quad and a homography is fitted per frame. `--occluder x,y` marks a point on whatever covers the screen at frame 0 (a hand), and SAM 2.1 masks it out; an empty mask is refused (`occluder mask is empty at frame 0`), and so is one over 60% of the screen (`occluder covers P% of the screen (click landed on the screen?)`). Needs `venv-ml`.
- Refusals print `refused: <message>` and exit 2: `track lost on frames A-B (P% points hidden)` (more than 30% of points hidden for 0.5 s or longer), `corner jump N px at frame F` (a corner moved over 8% of the screen diagonal in one frame), `homography unstable at frame F (inliers X)` (inlier ratio under 0.5), `green key missing on N frames`, `green key missing on frames A-B`, `screen mostly not green on frames A-B`, `occluder mask is empty at frame 0`, `occluder covers P% of the screen (click landed on the screen?)`, `missing <what>: run tools/setup.sh --ml`. A clip whose frame rate cannot be read raises `cannot read fps of <clip>`; a decoded size that differs from the probed one raises `frame size mismatch`.
- `--qa DIR` writes `qa-screen.jpg`, a contact sheet. Look at it before accepting the result.

## Embroider (`embroider`, `vidkit embroider`)

`python3 -m tools.vidkit embroider <clip> <logo.png> <out> --at x,y --width W [--rot DEG] [--hand x,y ...] [--qa DIR]`

`logo` is a PNG with alpha. `--at` is the design centre on the shirt at frame 0, `--width` its width in px, `--hand` a point on a hand over the shirt at frame 0 (repeatable). The JSON result has `frames`, `lost_frames` and `shirt_area_ratio`.

How it works:
1. SAM 2.1 masks the shirt from `--at`; hands are masked and excluded.
2. TAPNext++ tracks points on the shirt through the clip, and a per-point warp (not one global warp) moves the design with the folds.
3. The logo becomes a thread surface: a rounded ridge along each stroke, fine ridges from the stitches, its own normal and shading. This is why it is not `bond`, which multiplies flat ink into the cloth.
4. The thread is shaded against the cloth lighting, composited under the hand mask and written with the clip's audio.

Refusals (`refused: ...`, exit 2): `--at is not on the shirt`, `shirt area too small for design (R)`, `hand mask is empty at frame 0`, `hand mask covers P% of the design (click landed on the shirt?)`, `track lost on frames A-B (P% points hidden)`, `track lost on frames A-B (mesh warp failed)`, `track lost: only N grid points on the shirt` (fewer than 9), `shirt lost on frames A-B` (the shirt under the design fell under half its frame-0 share for 0.5 s; a hand over the design does not count), `missing <what>: run tools/setup.sh --ml`. Every "for 0.5 s" rule uses `screen.bad_runs`. A 16-bit logo PNG is scaled to 8 bits.

Known gap: a click on the background is not refused if SAM returns a large mask there. Always open the QA sheet (`qa-embroider.jpg`) and check the design sits on the shirt.
