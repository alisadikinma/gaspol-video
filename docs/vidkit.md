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
| `sheet` | `contact_sheet`, `montage` | `sheet.py`, `mont.py` |
| `synth` | `notification`, `alarm`, `render` (layered ffmpeg tones) | `bunyi-notif.py`, `bunyi-alarm.py` |
| `speech` | `words_from_alignment`, `speech_spans`, `gaps`, `snap_to_gaps`, `energy_db` | `kata.py`, `energi.py`, `geser_cue.py` |
| `loudness` | `normalize`: two-pass loudnorm, audio trimmed to picture | `mix_akhir.py` |
| `track` | `smooth_track`: median-filter a tracked screen box, pin one angle | `haluskan-lacak.py` |
| `bond` | `bond_print`: motion-tracked print on cloth (needs cv2) | `shirt_bond.py` |

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
| `cast_voice.mjs` | voice change with per-character settings and seed, spans only; plan json | `voice-changer/run.mjs` (which also imported the plugin by a versioned cache path) |

`templates/remotion/scripts/frames.mjs` and `qa-end.mjs` (multi-frame / end-state QA) now ship with every scaffold.

Tests: `tests/py/test_vidkit.py`, `tests/node/vidkit-js.test.mjs` (run with the venv python to include the `bond` test).

## Ingest (`tools/vidkit/ingest.py`)

| Function | What |
|---|---|
| `download(url, dir)` | yt-dlp, best mp4 with audio |
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

## Finishing (`karaoke`, `cover`, `unwhite`, `mixdown`)

| Module | What |
|---|---|
| `karaoke.build_ass(words, total, watermark, opacity)` | 2-word karaoke ASS (`\kf`), groups close at sentence end, `C Sharp` becomes `C#`, optional centre watermark |
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
