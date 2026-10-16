# Tool routing: reach for the tool, do not rewrite it

Before writing any script for video, animation, audio or assembly, find the task below. If a
tool exists, use it. If none does, build the new tool INSIDE this plugin (see the last section),
never as a one-off in a project folder.

Run Python tools from the plugin root (`python3 tools/<name>.py`, `python3 -m tools.vidkit ...`).
Tools that need Pillow/cv2/Playwright/MediaPipe use the venv from `tools/setup.sh`
(`~/.gaspol-video/venv/bin/python`). Node tools: `node tools/<name>.mjs`.

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
| Sound effects: generate | `gen_sfx.py` (palette), `eleven.mjs sfx` (one-off prompt) |
| Sound effects: mix into the cut | `mix_sfx.py`; move cues out from under narration: `vidkit.speech.snap_to_gaps` |
| Phone notification / alarm sound without paid files | `vidkit synth notification|alarm` |
| Music: generate / mix | `gen_music.py`, `mix_music.py` |
| Final loudness (-14 LUFS) with A/V kept aligned | `vidkit normalize` |
| Karaoke subtitles from a word list + centre watermark (any opacity) | `python3 -m tools.vidkit karaoke words.json out.ass --total N --watermark @handle` |
| Thumbnail on the first frames + as mp4 cover (subtitles stay off it) | `python3 -m tools.vidkit cover video thumb out [--ass f.ass]` |
| Logo on a white box -> mark that blends onto a prop | `python3 -m tools.vidkit unwhite logo.png out.png`, then CSS `mix-blend-mode: multiply` |
| Final mix in one command (voice + SFX cues + ducked music, -14 LUFS, subs, thumbnail) | `python3 -m tools.vidkit mixdown plan.json` |
| Follow popup with clicking cursor, "Ssst!", "WOW!", thumbnail cover (Remotion) | `templates/remotion/lib/ali-effects.tsx`: `FollowModal`, `ShushEffect`, `WowBurst`, `ThumbCover` |
| Subtitles / captions / keyword highlight | `gen_subs.py`, `burn_subs.py`, `gen_captions.py`, `caption_keywords.py` |
| Kinetic text overlay behind the speaker | `overlay_plan.py`, `person_mask.py`, Remotion `KineticOverlay` |
| Put an app screen into a phone/monitor in a clip | `track_screen.py` (+ `vidkit smooth-track` for jitter), Remotion `quad-screen.tsx` |
| App screen for software that does not exist | `gen_app_screen.py` |
| Print a logo/sablon onto a person's clothing | `vidkit bond` |
| Freeze one region of a clip (a bar that must not move) | `vidkit freeze` |
| Look at a clip without watching it | `qa_frames.py` (gate), `vidkit sheet`, `vidkit montage` |
| Remotion shot: scaffold / render / stills | `templates/remotion/scaffold.mjs`, `scripts/render-all.mjs`, `render-stills.mjs` |
| Remotion shot: several frames or the end state for QA | `scripts/frames.mjs`, `scripts/qa-end.mjs` |
| Compare the rendered master with the script | `verify_render.py` |
| Stems for a human editor | `make_stems.py` |
| Thumbnail logo / headline scrim | `composite_logo.py`, `thumb_scrim.py` |
| Render ledger, reusable asset library | `renders.py`, `asset_library.py`, `asset_home.py` |
| YouTube stats | `yt_stats.py` |
| Deck / slide post-processing (PDF, watermark, numbering) | NOT here: `gaspol-catalog` `tools/deckkit` |

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
