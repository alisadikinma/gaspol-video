# Tool routing: reach for the tool, do not rewrite it

Before writing any script for video, animation, audio or assembly, find the task below. If a
tool exists, use it. If none does, build the new tool INSIDE this plugin (see the last section),
never as a one-off in a project folder.

Run Python tools from the plugin root (`python3 tools/<name>.py`, `python3 -m tools.vidkit ...`).
Tools that need Pillow/cv2/Playwright/MediaPipe use the venv from `tools/setup.sh`
(`~/.gaspol-video/venv/bin/python`). Node tools: `node tools/<name>.mjs`.

<!-- registry:routes:begin -->
| I want to... | Use |
|---|---|
| Download someone's video from a link | `python3 -m tools.vidkit ingest <url> <dir>` |
| Cut a video into scenes (clip + first/mid/last stills + scenes.json) | `python3 -m tools.vidkit scenes <video> <dir>` |
| Probe a clip (duration, fps, size, sample rate, channels) | `python3 -m tools.vidkit probe` / `vidkit.ff.probe` |
| Check video length = audio length | `vidkit gate-av`; narration fits its cut: `check_vo_duration.py` |
| Check clips are safe to concat (same sample rate and channels) | `vidkit gate-uniform` |
| Join clips with hard cuts | `vidkit concat` |
| Join clips with dissolves (audio kept whole) | `vidkit xfade`; clip start times: `vidkit.join.clip_starts` |
| Edit from a plan (cuts, motion, shots, transitions) | `edit_render.py`, `plan_motion.py` |
| Insert/overlay/split a shot into a master | `composite.py` |
| Narration (TTS) from a script | `gen_vo.mjs` |
| One quick line with explicit voice settings and seed | `node tools/vidkit/js/eleven.mjs tts` |
| Replace the voice in a clip's dialogue | `voice_changer.mjs` |
| ...with per-character settings/seed, only the spoken spans | `node tools/vidkit/js/cast_voice.mjs plan.json` |
| Clean platform dialogue before voice change | `clean_voice.py` |
| Word timings of a clip | `node tools/vidkit/js/eleven.mjs stt`; from an alignment json: `vidkit words` |
| Music that follows the topic, tone and beat arc | `music_brief.py <project>` writes `work/music-palette.json` + plan segments, then `gen_music.py --recipes <project>/work/music-palette.json --only <ids>` |
| Sound effects: generate | `gen_sfx.py` (palette), `eleven.mjs sfx` (one-off prompt) |
| Sound effects: mix into the cut | `mix_sfx.py`; move cues out from under narration: `vidkit.speech.snap_to_gaps` |
| Clips of one kelompok differ in colour / grade | `python3 -m tools.vidkit colormatch CLIPS...` (report; add `--apply OUTDIR` only after the owner looked at `vidkit sheet`; `vidkit.colormatch.plan/apply`) |
| Beat times of a music file | `python3 -m tools.vidkit beats FILE` (`vidkit.beats.detect`) |
| Land SFX cues on the music beat | `python3 tools/sfx_snap.py <project> --music-plan work/music-plan.json` (or `--music FILE`; exit 2 bad input, 3 no beats; writes `work/sfx-plan.snapped.json`; `snap` = `vidkit.beats.snap`) |
| Skip an expensive step when its inputs did not change | `vidkit.stages.fingerprint(files, params, version)` + `StageCache(path).is_fresh/record`. `tools/edit_render.py` already uses it: a re-run skips unchanged segments (`--no-cache` forces a full render) |
| Phone notification / alarm sound without paid files | `vidkit synth notification|alarm` |
| Music: generate / mix | `gen_music.py`, `mix_music.py` |
| Final loudness (-14 LUFS) with A/V kept aligned | `vidkit normalize` |
| Final loudness to a named, sourced target (`--profile NAME`; unknown or unsourced profile exits 2) | `vidkit normalize --profile`, `loudness.profile()` |
| Pick the loudness target of a final mix by name | mixdown plan key `loudness_profile` (explicit `lufs` wins) |
| Karaoke subtitles from a word list + centre watermark (any opacity) | `python3 -m tools.vidkit karaoke words.json out.ass --total N --watermark @handle` |
| Thumbnail on the first frames + as mp4 cover (subtitles stay off it) | `python3 -m tools.vidkit cover video thumb out [--ass f.ass]` |
| Logo on a white box -> mark that blends onto a prop | `python3 -m tools.vidkit unwhite logo.png out.png`, then CSS `mix-blend-mode: multiply` |
| Final mix in one command (voice + SFX cues + ducked music, -14 LUFS, subs, thumbnail) | `python3 -m tools.vidkit mixdown plan.json` |
| Tag a final encode as BT.709 (flags + `setparams` filter) | `vidkit.color.ENCODE_FLAGS`, `vidkit.color.TAG_FILTER` (already wired into `edit_render.py` and `mixdown`) |
| Read a file's colour space / primaries / transfer / range | `vidkit.color.probe_color(path)` |
| Does a source need a BT.601 to BT.709 conversion? | `vidkit.color.convert_filter(probe, warnings, source)` (`''` = leave alone) |
| Follow popup with clicking cursor, "Ssst!", "WOW!", thumbnail cover (Remotion) | `templates/remotion/lib/ali-effects.tsx`: `FollowModal`, `ShushEffect`, `WowBurst`, `ThumbCover` |
| Subtitles / captions / keyword highlight | `gen_subs.py`, `burn_subs.py`, `gen_captions.py`, `caption_keywords.py` |
| Kinetic text overlay behind the speaker | `overlay_plan.py`, `person_mask.py`, Remotion `KineticOverlay` |
| Viral overlay extras (sticker icons, step counter, red vignette, falling burst, `viral` caption preset) | `overlay_plan.py` fields `steps`, `vignette`, `burst`, `preset` + `KineticOverlay` (doc 19 section 8) |
| Measure onsets, tempo, energy and word/cut timing of a reference clip | `python3 -m tools.vidkit audiostudy <clip> [--words w.json] [--out r.json]` |
| Retention check on a finished cut (static frame, hook, foreshadow, b-roll, BGM) | `python3 tools/retention_gate.py report` / `check` |
| Fill/check the viral checklist of a short-form script; rate analytics against course thresholds | `python3 tools/viral_checklist.py check` / `rate` |
| Put an app screen into a phone/monitor in a clip | `track_screen.py` (+ `vidkit smooth-track` for jitter), Remotion `quad-screen.tsx` |
| App screen for software that does not exist | `gen_app_screen.py` |
| Print a logo/sablon onto a person's clothing | `vidkit bond` |
| Freeze one region of a clip (a bar that must not move) | `vidkit freeze` |
| Look at a clip without watching it | `qa_frames.py` (gate), `vidkit sheet`, `vidkit montage` |
| Check rendered thumbnails by looking before they are final | `thumb_verify.py init`, then `thumb_verify.py check` (gate); prompt pieces in `reference/post-production/21-thumbnail-style-elements.md` |
| Let the owner approve keyframes before clips are rendered | `verdict_page.py page`, then `verdict_page.py check` (gate) |
| Remotion shot: scaffold / render / stills | `templates/remotion/scaffold.mjs`, `scripts/render-all.mjs`, `render-stills.mjs` |
| Remotion shot: several frames or the end state for QA | `scripts/frames.mjs`, `scripts/qa-end.mjs` |
| Compare the rendered master with the script | `verify_render.py` |
| Stems for a human editor | `make_stems.py` |
| Thumbnail logo / headline scrim | `composite_logo.py`, `thumb_scrim.py` |
| Choose the video encoder for edit renders, or see a long encode is alive | env `GASPOL_VIDEO_ENCODER` = `libx264` (default) / `auto` / `h264_videotoolbox` (`vidkit.encoder`); `ff.run(cmd, heartbeat_s=30)` |
| Render ledger, reusable asset library | `renders.py`, `asset_library.py`, `asset_home.py` |
| Units of billed renders, failed attempts, re-rolls per scene (no prices) | `cost_log.py` |
| YouTube stats | `yt_stats.py` |
| Deck / slide post-processing (PDF, watermark, numbering) | NOT here: `gaspol-catalog` `tools/deckkit` |
| Check a Remotion overlay shows only approved on-screen text | `python3 tools/check_overlay_strings.py <shots-dir> --from-markdown av-script.md --heading "<block>"` |
<!-- registry:routes:end -->

## When no tool fits (inject back)

1. Search first: `ls tools tools/vidkit`, this table, `docs/vidkit.md`.
2. Close but not quite: extend the existing tool or module (parameter, option), add a test.
3. Truly new and reusable: add a module to `tools/vidkit/` (Python) or `tools/vidkit/js/` (Node),
   register it in `tools/vidkit/__main__.py` if it has a CLI, add a test in `tests/py/test_vidkit.py`
   or `tests/node/vidkit-js.test.mjs`, add its row HERE and in `docs/vidkit.md`.
4. Do it in the same session you needed it. A script left in a project folder is a script the next
   project rewrites.
5. Hard-coded scene ids, timings, file names, client names or absolute paths do NOT go in the
   library. Parameterise them, keep the project part as a small plan json in the project.
