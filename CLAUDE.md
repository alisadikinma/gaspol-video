# AI Video Promo Engine — Claude Project Instructions

## 🧠 Vault Context Link

Skill library — agnostic terhadap project (IRN / SPARKFLUENCE / etc).

Pre-read kalau perlu konteks lintas-skill:
- `30-Knowledge/video-pipeline-shared.md` — 6-phase, VEO/Seedance/Kling craft
- `30-Knowledge/image-gen-shared.md` — NB2 prompt engineering, anti-AI-look
- `20-Projects/claude-plugin/README.md` — skill ecosystem overview
- `10-Identity/voice-tone.md` — user-facing copy / docs

JANGAN hardcode project-specific values (nama klien, fleet count, dll). Pakai `{{placeholder}}` syntax.

## Project Overview

Claude Code plugin that carries a promotional video from brainstorm to a finished, mixed file: script, image prompts (NB2, in-session render offers via `indusia-image-gen`), video prompts (VEO 3.1 / Seedance 2.0 / Kling 3.0, VEO 3.1 fast render offers via `indusia-video-gen`), app screens and screencasts for software that does not exist yet or is not reachable, Remotion shots for anything that must be readable, then post-production and packaging. 7 production skills + 1 orchestrator + repackage + 2 utility skills + 2 agents + 78 registered tools (`tools/registry.json`; most stdlib, a few need the venv from `tools/setup.sh`, the ML tools need `tools/setup.sh --ml`) + 42 reference documents loaded per phase.

**Core Value:** Anyone — video agencies, freelancers, brand owners — can produce professional 2-3 minute promotional videos by following the generated production plan.

## Commands

| Command | Description |
|---------|-------------|
| `/video-full` | End-to-end pipeline orchestrator (brainstorm → script → images → video) |
| `/video-brainstorm` | Phase 1: brainstorm, cast, product, location, domain research |
| `/video-script` | Phase 2-3.5: script generation, scene breakdown, reference collection |
| `/video-image` | Phase 4: NB2 asset library + scene keyframes |
| `/video-gen` | Phase 5: image review + VEO video prompts |
| `/video-explainer` | Phase 4.5: coded Remotion shots for scenes that must be readable |
| `/video-post` | Phase 6, two modes: per kelompok (VO + kelompok cut) and `--final` (assembly, SFX, subtitles, music, final mix) |
| `/video-package` | Phase 7: locked title, three thumbnail bets, description |
| `/video-validate` | Unified validator: `--script` / `--image` / `--video` / `--refs` / `--all` / `--post` |
| `/video-add-platform` | Scaffold new AI video platform support |

## Architecture

| Path | Purpose |
|------|---------|
| `.claude-plugin/plugin.json` | Plugin metadata (name, version, author) |
| `hooks/hooks.json` | SessionStart hook definition |
| `hooks/session-start.sh` | Session start script — announces available skills |
| `hooks/tool-reminder.sh` | PreToolUse hook on Write/Edit (GV-20). Calls `registry_build.py hook`; when a `.py`/`.mjs`/`.sh` file outside `tools/`, `tests/`, `templates/` contains `ffmpeg`, `ffprobe` or `remotion`, adds a reminder naming the matching registry tools. Reminds, never blocks. Test: `tests/consistency/tool-reminder-hook.sh` |
| `skills/video-brainstorm/SKILL.md` | Phase 1 — brainstorm, cast, product, location, domain research |
| `skills/video-script/SKILL.md` | Phase 2-3.5 — script, scene breakdown, reference collection |
| `skills/video-image/SKILL.md` | Phase 4 — NB2 asset library + scene keyframes |
| `skills/video-gen/SKILL.md` | Phase 5 — image review + VEO video prompts |
| `skills/video-full/SKILL.md` | Orchestrator — runs all 7 production skills in sequence |
| `skills/video-explainer/SKILL.md` | Phase 4.5 — Remotion explainer shots (scenes with legible text) + screencast shots for app screens |
| `skills/video-post/SKILL.md` | Phase 6 — five passes: VO, edit, SFX, subtitles+music, mix; scoped per kelompok then `--final`; optional stems and P6 verify |
| `skills/video-package/SKILL.md` | Phase 7 — title, thumbnail bets, description; rendering routed to the image plugin; optional logo/scrim post-process |
| `skills/video-validate/SKILL.md` | Unified validator (--script / --image / --video / --refs / --post / --all) |
| `skills/video-add-platform/SKILL.md` | Scaffold new video platform support |
| `tools/_venv.py` | Dependency guard — re-execs into `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/venv` for the tools below that need it, else exits 2 naming `tools/setup.sh` |
| `tools/setup.sh`, `requirements.txt` | Build the shared venv (Pillow, playwright, google-api-python-client, google-auth-oauthlib) |
| `tools/cost_log.py` | Records units of billed renders (`work/cost-log.json`), failed attempts and re-rolls per scene; `add` and `report`. No prices |
| `tools/renders.py` | Render ledger (`{output_folder}/renders.json`) shared by the Phase 4/5 render offers; `archive --file F [--reason R]` moves an existing file into `_arsip/` before a re-render |
| `tools/gen_app_screen.py` | `capture` (Playwright, real URL) and `mock` (Remotion `renderStill`) app screens into `ref/ui-*.png` |
| `tools/asset_home.py` | Where the reusable libraries live: `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/library/{sfx,music,images}` (survives plugin updates); recipes stay in the plugin's `media/<kind>/library/palette.json`. `where` prints the dirs, `adopt` copies earlier plugin versions' clips/tracks in (never moves). SFX plans without `catalog` and music segments `library:<id>` resolve here |
| `tools/asset_library.py` | Cross-project library for generic images in `asset_home.library("images")`: `find` (exact prompt + aspect), `add` (refuses faces, logos, UI, products, costumes, locations), `list --tag`, `use`. The Phase 4A render offer calls it before rendering |
| `tools/gen_music.py` | Two modes. Flag mode generates missing `tracks/*.mp3` (into the home library) from the plugin's mood palette via ElevenLabs Music. `video` subcommand composes one bed to the finished master (`output/music.mp3`) from a picture-only proxy; exit 3 = `FALLBACK palette: <reason>` and the palette segments stay |
| `tools/music_brief.py` | Music that follows the topic: reads `work/music-brief.json` (topic, domain, tone, `sound_world`, beat/energy segments) and writes one prompt per segment to `work/music-palette.json` plus `library:<id>` segments in `work/music-plan.json`. Ids hash prompt and length, so an unchanged segment is never re-billed. Refuses (exit 2) an invalid brief; `--print` shows the table and writes nothing. Then `gen_music.py --recipes <project>/work/music-palette.json --only <ids>`. Test: `tests/py/test_music_brief.py` |
| `tools/verify_render.py` | P6 — second ASR pass diffs the rendered master against `av-script.md` |
| `tools/clean_voice.py`, `tools/models/rnnoise/*.rnnn` | Cleans platform-native dialogue (ElevenLabs Isolator or ffmpeg RNNoise) before the Voice Changer |
| `tools/composite.py` | `cutaway` / `overlay` / `split` (picture-in-picture) / `insert` (pauses the master for a full shot) |
| `tools/make_stems.py` | Full-length voice/SFX/music stems in `output/stems/` for a human editor |
| `tools/composite_logo.py`, `tools/thumb_scrim.py` | Deterministic thumbnail post-process — real logo paste, headline scrim (needs Pillow via `_venv.py`) |
| `tools/yt_stats.py` | Pulls YouTube Data/Analytics stats into `packaging/calibration.json` (needs the venv + an OAuth client) |
| `tools/burn_subs.py`, `tools/edit_render.py`, `tools/gen_sfx.py`, `tools/gen_subs.py`, `tools/mix_music.py`, `tools/mix_sfx.py`, `tools/probe_clips.py` | Existing stdlib-only Phase 6 tools (assembly, SFX, subtitles, music mix, clip QA) |
| `tools/check_vo_duration.py` | Fails when narration does not fit its cut, or a cut runs on in silence |
| `tools/check_overlay_strings.py` | Fails when a rendered Remotion component shows an on-screen string missing from the script's approved list (expands `X 1 of 6` series) |
| `tools/track_screen.py` | Reads the four corners of a screen at frame 0 (flood fill + fitted edge lines) for `vidkit screen-insert --mode track --corners`; exits 2 under 120 px. Placing the panel is screen-insert's job |
| `tools/sfx_snap.py` | Snaps the cue sheet's `at_s` (a stack's parent only) onto the beats of the music bed within `--window` (default 0.12 s); writes `work/sfx-plan.snapped.json`, never the original; `--music-plan` (default `work/music-plan.json`) takes beats from every segment's track, or `--music FILE` for one bed; exit 2 bad input, exit 3 and no file when the music has no beats. Run after the cue sheet is audited and the music tracks are generated, before `mix_sfx.py` |
| `tools/face_box.py` | GV-23 face box per sampled frame (`[x0,y0,x1,y1]` pixel ints, end-exclusive, `null` = no face) from OpenCV YuNet (cv2.FaceDetectorYN, CPU, score >= 0.6); model pinned in `tools/setup.sh`. Exit 2 on missing model or unreadable video. Test: `tests/py/test_face_box.py`, `tests/consistency/face-model-setup.sh` |
| `tools/layout_gate.py` | GV-23 layout gate for 9:16 video, `check <project> [--video] [--ass] [--thumb GLOB] [--overlay SHOTS] [--profile] [--every]`. Measures subtitle and watermark boxes by rendering the ASS alone on black, reads the title box from `<thumb>.box.json`, scales the profile to the video's display size (not 9:16 = exit 2), flags boxes outside the safe area and subtitles or titles that touch or crowd the face box (via `face_box.py`). Exit 0 pass, 1 finding, 2 bad input or nothing measured, 3 INCOMPLETE (`--overlay <dir>`: only the json the workspace is wired to is measured); skipped face samples are listed. Writes `work/layout-report.md` and `.tmp/layout-{tiktok,reels,shorts}.jpg`. `--overlay` renders each kinetic-overlay cue's text alone on grey with Remotion (`templates/remotion/scripts/render-overlay-text.mjs`, `KineticOverlay` `textOnly`), measures it, checks safe area and face (touching only), previews `.tmp/layout-overlay-<scene>-*.jpg`; a render that cannot run exits 2, never an estimate. `overlay_plan.py --profile` refuses explicit cue positions outside the safe area and writes `safe` into the overlay json. Tests: `tests/py/test_layout_gate.py`, `tests/py/test_overlay_plan.py`, `tests/node/{overlay-fx,render_overlay_text}.test.mjs` |
| `media/layout-profiles.json`, `tools/vidkit/layout.py` | GV-23 layout profiles: safe area (left 6 %, top 14 %, right 10 %, bottom 21 %), subtitle, watermark and title numbers, each with a `source` (`data` from the Samuel measurement in `docs/evals/short-form-layout-measurement.md`, or `tafsiran: ...`). `layout.load/safe_box/value/text_box` read it; no number lives in code. Test: `tests/py/test_layout.py` |
| `tools/vidkit/title.py` | `vidkit title <img> "<text>" <out> [--profile] [--y-pct]`: stamps a 9:16 cover title (max 3-5 words by profile, 2 or 3 lines balanced by width, black box, font chain Montserrat, Helvetica Neue, Arial Bold) centred on the safe area centre, using the full safe width, and writes `<out>.box.json` (box, text, font, lines, absolute `source` of the clean image) for `layout_gate.py`, which detects the face on `source` and flags `title overlaps face` (fallback to the stamped image with a note). Font shrinks from `font_pct` 0.065 to `min_font_pct` 0.04 (both `tafsiran`). Refuses with `usable width N px, widest line M px at min font`. Exit 2 on refusal. Test: `tests/py/test_vidkit.py`, `tests/consistency/title-card-contract.sh` |
| `tools/vidkit/karaoke.py` | `vidkit karaoke` now defaults to `--profile short-organic` (56 px, 4 words in 2 lines, MarginV 735, baseline 61.7 %); `--profile none` is the old look. Test: `tests/py/test_vidkit.py` |
| `tools/person_mask.py` | Per-frame person matte (MediaPipe selfie segmenter, venv + model from `tools/setup.sh`) into `.tmp/mask-<scene>/NNNNN.png`, cached by clip sha256; exit 1 when no person in more than 10% of frames, listing the frames |
| `tools/overlay_plan.py` | Resolves `work/overlay-plan.json` cues to frames from VO words (`vo_layer` in `vo-manifest.json`, or `words_file` ASR words), validates fx/colour/layer/icon/media/mask, writes `shots/src/shots/overlay-<scene>.json` and stages media + masks in `shots/public/overlay/<scene>/` for `KineticOverlay` |
| `tools/caption_keywords.py` | Scores key phrases in a narration line (number+unit, brand term, acronym, reversal word) for kinetic-caption highlighting |
| `tools/gen_captions.py` | Builds `work/caption-plan.json` from `vo/vo-manifest.json` words (or AssemblyAI, imported from `gen_subs.py`) plus `caption_keywords.score_spans()`; capped, deterministic, reusable unless `--force` |
| `tools/plan_motion.py` | Fills the `motion` field on static segments of `work/edit-plan.json` — splits a segment over 5.0s into alternating punch-in/punch-out beats, gives a shorter one a single slow punch-in; never overwrites a hand-written `motion` or a `kind: "shot"` segment |
| `tools/qa_frames.py` | Visual clip QA — a 5-frame contact sheet per rendered clip in `.tmp/qa-scene-NN.jpg` (ids may carry a letter suffix, e.g. `01b`) and a `work/visual-qa.md` verdict sheet with each scene's PLAUSIBILITY block, for Claude to judge in-session; `--check` is the V15 gate (reads verdict cells only, exit 1 on a missing, empty or `FAIL:` cell or a clip changed since judged). Tiles through `vidkit.sheet.contact_sheet(times=...)` |
| `tools/thumb_verify.py` | GV-18 thumbnail verify gate. `init <project>` writes `packaging/thumb-verify.md` (one section per `packaging/thumb-*.png`, sha256, five-row verdict table; re-run keeps verdicts of unchanged images); `check <project>` reads only the verdict cells and exits 1 on a missing, empty, malformed or `FAIL:` cell or a changed or removed image, 2 when the sheet is missing; `UNSURE:` is a note. A thumbnail is final only after `check` exits 0. Test: `tests/py/test_thumb_verify.py` |
| `tools/verdict_page.py` | Stills-first gate (GV-18 Phase I). `page` builds one offline `output/verdict.html` from `keyframes/scene-*.png` (JPEG data URIs via ffmpeg, PASS/MAYBE/NO, notes, Download verdict.json); the owner saves it to `work/verdict.json`; `check` exits 0 only when every keyframe is PASS (`--allow-maybe` accepts MAYBE), 1 listing missing/NO/MAYBE scenes, 2 on a missing or malformed file. stdlib + ffmpeg. Test: `tests/py/test_verdict_page.py` |
| `tools/registry.json`, `tools/registry_build.py` | Tool registry (GV-20): every tool and every task-to-tool route in one file. `validate [--coverage]` checks schema, coverage, duplicates and ffprobe ownership; `render [--check]` writes the table in `docs/tool-routing.md`; `suggest`/`hook` feed the write-time reminder hook. Tests: `tests/py/test_registry.py`, `tests/py/test_probe_migration.py`, `tests/consistency/tool-registry-contract.sh` (coverage, duplicate and ffprobe-ratchet gates, generated table in sync) |
| `tools/guide_vo.py` | Guide-voice takes: an expressive stock voice on eleven_v3 (audio tags) reads each line at several stabilities, to be picked with `vidkit prosody`, tightened with `vidkit tighten` and converted to the cast voice with `voice_changer.mjs`. Existing takes are never re-billed unless `--force`; key and voice id never printed. Test: `tests/py/test_guide_vo.py` |
| `tools/retention_gate.py` | Retention report on a finished cut (`report`) and in-session b-roll verdict gate (`check`): static frame, first word, Foreshadow beat, b-roll vs spoken words, BGM headroom. Course defaults tagged `source: course`, overridable; a rule FAIL never exits 1 in report mode. Test: `tests/py/test_retention_gate.py` |
| `tools/viral_checklist.py` | `check` the `## Viral Checklist` block of `av-script.md` (7 stages, exit 1 on a missing/empty/`FAIL:` cell); `rate` a `calibration.json` entry against the course analytics thresholds (`unknown` when a key is absent). Test: `tests/py/test_viral_checklist.py` |
| `tools/gen_vo.mjs`, `tools/voice_changer.mjs` | ElevenLabs TTS and speech-to-speech (spans, not whole tracks) |
| `tools/vidkit/` | Reusable assembly library, `python3 -m tools.vidkit --help`: `audiostudy` (SFX/speech onsets, tempo, energy, word and cut relation of a reference clip), A/V and concat gates, xfade/concat join with timeline maths, freeze-box patch, contact sheets, synth alerts, word-timing and speech-gap cue snapping, two-pass loudnorm, motion-tracked print bond (cv2), `tidy.py` (`vidkit tidy`: report, `--apply`, `--empty-tmp` for a project folder). See `docs/vidkit.md`. Test: `tests/py/test_vidkit.py` |
| `tools/vidkit/ml.py`, `requirements-ml.txt`, `tools/setup.sh --ml` | ML guard (GV-24): `bash tools/setup.sh --ml` builds `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/venv-ml` (torch, TAPNext++, SAM 2.1; Python 3.10+, `PYTHON_ML` overrides) and fetches two weights with pinned URL and sha256. `ml.weight`, `ml.device`, `ml.require`; a missing piece raises `MLMissing` ending `run tools/setup.sh --ml`. Stdlib only, torch imported lazily |
| `tools/vidkit/pointtrack.py` | `track(frames, queries)`: occlusion-aware point tracking with TAPNext++ (Apache-2.0). Needs venv-ml |
| `tools/vidkit/segment.py` | `masks(frames, frame_idx, points, labels, box)`: SAM 2.1 mask of an object through a clip from one click or box. Needs venv-ml |
| `tools/vidkit/screen.py` | `vidkit screen-insert <clip> <panel> <out> --mode green\|track`: app screen into a phone/monitor. Green: exact corners by keyed blob and RANSAC line fits (fingers drop out). Track: TAPNext++ plus homography per frame, `check_track` raises `Refused` (exit 2). One-Euro smoothing. The output is written to a temp file and moved over `out` only when its frame count matches; audio is padded and re-encoded to AAC so short audio never cuts the video. Test: `tests/py/test_screen.py` |
| `tools/vidkit/embroider.py` | `vidkit embroider <clip> <logo> <out> --at x,y --width W`: raised satin thread on clothing (thread height map, per-point cloth warp, shading), refuses a bad track or a click off the shirt. Distinct from `bond` (flat print). Test: `tests/py/test_embroider.py`. Contract: `tests/consistency/surface-insert-contract.sh` |
| `tools/vidkit/js/` | Node helpers: `env.mjs` (.env loading, keys never printed), `eleven.mjs` (`tts` with settings + seed, `stt` word timings, `sfx`), `cast_voice.mjs` (voice change with per-character settings and seed, spans only), `ff.mjs` (`probeDuration`, the only Node file that runs ffprobe). Test: `tests/node/vidkit-js.test.mjs` |
| `templates/remotion/scripts/frames.mjs`, `qa-end.mjs` | Multi-frame and end-state Remotion QA, copied into every scaffolded workspace |
| `templates/remotion/Overlay.template.tsx`, `lib/{overlay-fx.tsx,overlayFx.mjs}` | `KineticOverlay` (GV-17): clip, behind layer, person cut out by mask, front text, source box; six text effects as zero-import maths in `overlayFx.mjs` (unit-tested), drawn by `overlay-fx.tsx` |
| `templates/remotion/lib/{brand.ts,kit.tsx,browser.tsx,screencast.tsx}` | Generic Remotion components ported from `claude-youtube-editor`, brand tokens only from the project's `brand.json` |
| `templates/remotion/scripts/{gen-registry,render-all,qa-frames,render-stills}.mjs` | Registry generation, render, QA-still and mock-screen-still scripts copied into every scaffolded workspace |
| `templates/remotion/` | Remotion shot template, brand token placeholder, workspace scaffolder |
| `media/sfx/library/` | SFX recipes (`palette.json`); clips are generated per install, never committed |
| `media/music/library/` | Music mood palette (`palette.json`, `defaults` block); tracks and `catalog.json` generated per install, never committed |
| `.env.example` | Names of the environment variables the tools read. Never their values |
| `agents/video-engine-agent.md` | Subagent for batch/complex video production (full pipeline incl. render offers, screens, P6 verify) |
| `agents/video-prompt-reviewer.md` | Independent validator — reviews NB2/VEO prompt batches for quality (checks C1-C11) |
| `reference/` | reference docs read on-demand by skill/agent |
| `tests/` | `bash tests/run.sh` — consistency checks, python unittest, node --test |
| `README.md` | Repo README |
| `LICENSE` | MIT license |

### Reference Files

#### Storytelling & Script Generation (13 files)

| File | When Used |
|------|-----------|
| `storytelling_script_gen/project-instruction.md` | ALWAYS for script generation — master operating system, 2-phase state machine, 9 commandments (v2.2.0+), 7-beat arc + 6-stage user framework alias |
| `storytelling_script_gen/F1_Audience_Psychology_Matrix.md` | Target market selection — C-Level, VP/Director, Manager, IC, End Consumer psychographics |
| `storytelling_script_gen/F2_Narrative_Arc_and_Video_Typology.md` | Narrative arc selection — 7-beat universal arc, 12 video types, duration mapping |
| `storytelling_script_gen/F3_Cinematic_AV_Production_Rules.md` | Lighting grammar, audio design, camera directions for script |
| `storytelling_script_gen/F4_EV_Persona_Matrix.md` | CONDITIONAL — only when product is EV-related |
| `storytelling_script_gen/F5_Hook_Vault.md` | Hook selection — 100 hooks in 5 categories |
| `storytelling_script_gen/F6_CTA_Vault.md` | CTA frameworks per awareness level |
| `storytelling_script_gen/F7_Foreshadow_and_Peak_Engineering.md` | Psychological techniques for tension and peak moments |
| `storytelling_script_gen/F8_Awareness_Level_Routing.md` | 5 awareness levels — routes to correct narrative strategy |
| `storytelling_script_gen/F9_Platform_Adaptation_Matrix.md` | Platform specs — YouTube, LinkedIn, IG, TikTok, Twitter |
| `storytelling_script_gen/F10_Modular_Asset_and_AB_Testing.md` | Modular asset creation and A/B testing strategy |
| `storytelling_script_gen/F11_Pattern_Interrupt_and_Retention.md` | Pattern interrupt techniques and retention optimization |
| `storytelling_script_gen/F12_Viral_Framework.md` | Short-form only — 7-stage viral framework with pass/fail checklist, title formula, loop ending, analytics thresholds (course advice) |
| `storytelling_script_gen/F13_Short_Form_Timeline.md` | 9:16 only — Thumbnail 0-1 / Hook 0-3 / Foreshadow 3-6 / Body 6-50 / CTA last 2-4 s timeline (notebook `fd70ee32`), checked by `viral_checklist.py timeline`; adds timing to F12, never overrides it |

#### Image & Video Production (9 files)

| File | When Used |
|------|-----------|
| `image-video-gen/00-index.md` | ALWAYS for image/video — production stack overview, critical constraints |
| `image-video-gen/01-nb2-image-generation.md` | NB2 image prompts — parameters, resolution, identity lock, material shaders, text rendering |
| `image-video-gen/02-veo-production-guide.md` | VEO 3.1 video prompts — specs, camera movement, I2V motion, lip sync, extensions, audio |
| `image-video-gen/03-workflow-pipeline.md` | NB2 → VEO pipeline — decision tree, handoff rules, extension chain, "Last Frame Secret" |
| `image-video-gen/04-cinematography-lookup.md` | Emotion → complete setup mapping (lighting, lens, film stock, atmosphere, camera motion) |
| `image-video-gen/05-creator-and-holidays.md` | Ali Sadikin as cast slot, cast-c{N} naming, holiday palettes, cultural context |
| `image-video-gen/06-directing-and-performance.md` | Film directing grammar — 180° rule, gaze direction, blocking, vocal performance, continuity supervision |
| `image-video-gen/07-seedance-production-guide.md` | Seedance 2.0 video prompts — native 2K, @ reference system, dual-branch audio, modes, materials |
| `image-video-gen/08-kling-production-guide.md` | Kling 3.0 video prompts — native 4K, 5-part formula, multi-shot storyboard (6/15s), motion control, omni audio (5 langs incl mixed-language scene). **Primary** Kling reference (curated by Claude from 10-source WebSearch + UI ground truth) |
| `image-video-gen/08b-kling-notebooklm-briefing.md` | Kling 3.0 NotebookLM-distilled Briefing Doc — independent cross-validation of 08-kling guide, contains efficiency data (rerolls/credit savings), Elements 3.0 system, 5-layer prompt formula breakdown. **Supplementary** RAG layer #2 (auto-generated from notebook `kling-prod`, regenerate via `nlm report create kling-prod`) |
| `image-video-gen/09-voice-consistency-workflow.md` | **Cross-platform** voice-over consistency — applies to VEO 3.1 + Seedance 2.0 + Kling 3.0. 3 solution paths (Path A native voice lock per platform, Path B universal ElevenLabs post-prod, Path C single VO + sync), prompt-level discipline rules, hybrid workflow per video type, plugin integration spec for Phase 5 Step 5.0. **MANDATORY** for any video with >1 scene or character voice continuity. |
| `image-video-gen/10-physical-plausibility-gate.md` | Phase 4B and 5 — nine defect classes and the seven-line `PLAUSIBILITY:` block (MECHANISM, COUNT, FLOW, FACING, PAIR, PEOPLE, OVERLAY SURFACE), checks K1-K7 |
| `image-video-gen/project-instruction.md` | Image/video project instructions — critical rules, example workflows |

#### Post-Production (Phase 6)

| File | When Used |
|------|-----------|
| `post-production/10-post-production-pipeline.md` | ALWAYS for Phase 6 — pass order, `{output_folder}` contract, every plan schema, A/V duration gate, degradation policy |
| `post-production/15-packaging.md` | Phase 7 — Views = Reach x CTR, three bets on three levers, honesty guardrail, calibration honesty, hand-off to the image plugin |
| `post-production/12-remotion-explainer.md` | Phase 4.5 — scaffolding the workspace, the rules that stop a render crashing, brand from the project, timing from the narration, verify-by-looking, cutaway vs overlay |
| `post-production/18-screencast.md` | Phase 4.5 — screencast shots for scenes whose Screen Source is capture/mock: page/cursor/click API, navigation-vs-filter motion rules, cue timing from vo-manifest.json, qa-frames verification, mock-screen honesty |
| `post-production/19-keyword-text-overlay.md` | Kinetic text overlay (v3.11.0): two-tier keyword, six effects (never static), media panels/carousel/bubbles behind the speaker via person mask, timing from voice words (`key_words` for numbers), placement off the face, red alarm flash behind the person only |
| `post-production/21-thumbnail-style-elements.md` | Phase 7 — slot-based thumbnail prompt pieces (environment, hook text, sticker, badge), base axes, failure table for garbled text and wrong faces, honesty guardrail, hand-off to the image plugin and `thumb_verify.py` gate |
| `post-production/20-retention-gate.md` | Retention gate (v3.16.0) — five rules with course defaults, why it reports and does not block, `not measured` meaning, a real run |
| `post-production/17-music-bed.md` | Phase 6 pass 4 — deriving the track from the script's music direction and tone, sitting 12 dB under the voice by measurement, segment fades and short-track handling, why the music pass fails soft while the A/V gate blocks |
| `post-production/16-subtitles-and-captions.md` | Phase 6 pass 4 — caption text from the script (recognizer times only), derived keyterms, wrap-or-split rule, font and contrast guards, why this does not conflict with the `no subtitles` prompt negative |
| `post-production/14-sfx-design.md` | Phase 6 pass 3 — deriving cues from DOMAIN CONTEXT and cultural research, library-first sourcing, gain calibration incl. the transient correction, the four ways an audibility measurement lies, density ceiling, hard audit gate |
| `post-production/13-ffmpeg-edit.md` | Phase 6 pass 2 — trim vs pad vs regenerate, inserting explainer shots, why every segment is normalised before concat, the A/V duration gate, playable transcode |
| `post-production/11-voice-cast-and-vo.md` | Voice per cast member — `VOICE:` block, `tts` vs `native+changer`, VO-first duration budgeting, prosody stitching, Voice Changer 0.05s drift rule, prompt-level discipline |

#### Global Config & Bridge (3 files)

| File | When Used |
|------|-----------|
| `global-promo-config.md` | ALWAYS (read FIRST) — single source of truth for all configurable values (Section 29 = post-production defaults) |
| `creator-profile-system.md` | Phase 1 (Cast Builder) — multi-character cast profiles, institution detection, generic + Ali Sadikin preset |
| `script-to-scene-bridge.md` | Phase 3 (Scene Breakdown) — script → scene list → VEO mode → image/video prompts |

## Key Concepts

Full rules live in the skills and `reference/`; this section is the part an agent must never break.
Source of truth for every value: `reference/global-promo-config.md` (section numbers below).

### Pipeline and gates

| Phase | Output | Gate |
|---|---|---|
| 1 Brainstorm | `strategic-brief.md`, `cast-profile.md` | user approval; location confirmed before the 6 domain-research searches (§24) |
| 2 Script | `av-script.md` | user approval; BODY 1 dramatizes every brainstormed pain (§25, check C1) |
| 3 Scene breakdown | `scene-plan.md` (Render Path `platform`/`explainer`, Screen Source `capture`/`mock`/`none`) | user approval |
| 3.5 References | `ref-manifest.md` | **hard block**: 100% of refs in `{project}/ref/`, no skip, no "lanjut dulu" |
| 4A Asset library | `nb2-reference-prompts.md` | uniqueness filter, COMMON items skipped (§26, C2) |
| 4B Keyframes | `image-prompts.md`, one start frame per clip | batches of max 5 scenes, `video-prompt-reviewer` per batch |
| 4.5 Explainer | Remotion shots | clips of the kelompok exist first |
| 5 Video prompts | `video-prompts.md` | image review per scene, reviewer per batch |
| 6 Post | VO, edit, SFX, captions, music, mix | SFX cue sheet audited by the user before any mix; A/V duration gate |
| 7 Package | title, three thumbnail bets, description | `thumb_verify.py check` exits 0 |

`--full` (default) writes the production plan; `--quick` writes copy-paste prompts only.

### Prompt rules that break renders when ignored

- **Audio is never optional**: dialogue/VO + SFX + ambient in every video prompt; always add `no subtitles, no audience sounds, no text overlays`.
- Presenter: `Host says: text` (generic role, never a real name: safety filter). Lip sync needs face >30% of frame.
- B-roll: `Voice-over narrator, [tone]: text` plus a `> POST-PROD VO:` backup line. Never bare `Voiceover:`.
- **No em dash `—` in spoken text**; use `,` or `. `. No `[pause: Ns]` tag in a platform prompt (V16).
- `security camera` makes Veo draw REC text: write `fixed overhead view`.
- VEO prompts never name face ref files; NB2 prompts name them **bare** (`cast-c1-face.png`, never `ref/...`), **inline** with the element, **once** per prompt, **max 5** refs per 4B prompt (§26.4). The Required Reference Images table sits directly below each prompt heading.
- Identity lock syntax: `Maintain exact facial identity from reference image: cast-c1-face.png`.
- `scene-N-end.png` cross-reference only when both scenes share the environment (§27, C4).
- NB2 aspect ratio must equal the video target (triple enforcement: first line, TECHNICAL, last line).
- Every 4B and 5 prompt carries the seven-line `PLAUSIBILITY:` block and a `NARRATIVE CONTEXT:` block; every prompt carries a `DOMAIN CONTEXT:` line.

### VEO mode choice

Default: **one keyframe per clip, Single I2V**. Ingredients (1-3 refs, consistent character) and
First+Last Frame are **mutually exclusive**. First+Last only for faceless scenes and only when the
user asks for it on a named clip (two photoreal faces = "prominent people" rejection). Extend needs a
VEO-made 720p source; 1080p clips cannot be extended. Kling: per-second 3-15 s, Indonesian VO yes,
Indonesian on-screen lip sync no. Platform guides: `reference/image-video-gen/02`, `07`, `08`.

### Story rules

Customer is the hero, product is the bridge, brand is the guide. Nine commandments and 22 rejection
signals in `reference/storytelling_script_gen/project-instruction.md`; forbidden words include
synergy, leverage, robust, revolutionary, cutting-edge, seamlessly. Short-form (9:16) adds F12 viral
checklist and F13 timeline (`viral_checklist.py`).

### Cast and realism

1-5 characters (`creator-profile-system.md`). Anyone in 2+ scenes gets a face portrait in Phase 4A
first (§18). Pemeran Utama: face + body + costume refs (+ side face ref); Pendamping: face ref.
Institution keywords require a real uniform ref; brand logos are always user-provided. The 9-point
Scene Logic Realism check is in `script-to-scene-bridge.md` §7B; narrative continuity in §7C.

### Smart Context Loading

Each phase loads ONLY the reference files it needs.

| Phase | Files Loaded | Max |
|-------|-------------|-----|
| Phase 1 | global-promo-config, creator-profile-system, F1, F8 | 4 |
| Phase 2 | global-promo-config, project-instruction, F2-F11 (excl F4 unless EV) | 10-11 |
| Phase 3 | global-promo-config, script-to-scene-bridge, 03-workflow | 3 |
| Phase 3.5 | global-promo-config, creator-profile-system | 2 |
| Phase 4A | global-promo-config, 01-nb2, script-to-scene-bridge (7B only) | 3 |
| Phase 4B | global-promo-config, 01-nb2, script-to-scene-bridge, 04-cinematography | 4 per batch |
| Phase 4.5 (explainer) | global-promo-config §29.5, 12-remotion-explainer, 18-screencast (screen scenes only) | 3 per shot |
| Phase 5 (VEO / Seedance / Kling) | global-promo-config, 02-veo or 07-seedance or 08-kling, 03-workflow, 04-cinematography, 09-voice-consistency | 5 per batch |
| Phase 5 (Mixed) | global-promo-config, 02 + 07 + 08, 03-workflow, 04-cinematography, 09-voice-consistency | 7 per batch |
| Phase 6 pass 1 (audio) | global-promo-config §29, 11-voice-cast-and-vo | 2 |
| Phase 6 pass 2 (edit) | global-promo-config §29, 13-ffmpeg-edit | 2 |
| Phase 6 pass 3 (SFX) | global-promo-config §29, 14-sfx-design | 2 |
| Phase 6 pass 4 (subs+music) | global-promo-config §29-30, 16-subtitles-and-captions, 17-music-bed | 3 |
| Phase 6 pass 5 (final mix) | global-promo-config §29, 10-post-production-pipeline | 2 |
| Phase 7 (packaging) | global-promo-config §29, 15-packaging | 2 |

The `video-prompt-reviewer` agent runs with fresh context (batch prompts + `cast-profile.md` +
`scene-plan.md` only), returns PASS/FAIL per prompt, max 2 regenerations.

## Technical Defaults

All configurable values live in `reference/global-promo-config.md` — single source of truth. Includes: resolution, aspect ratio, film stock, NB2 CFG/denoise, VEO duration, cast limits, ref naming conventions, institution keywords, tone impact matrix, and cultural search settings.

## Conventions for Contributors

### Changing Any Setting (Global, Cast, Tone, etc.)
1. Edit `reference/global-promo-config.md` — single source of truth (cast = Section 7)
2. No need to edit other files — they all reference global-promo-config.md

### Adding a New Reference File
1. Create `.md` file in `reference/`
2. Add entry to the Reference Files table in skill SKILL.md
3. Add entry to the Reference Files table in `agents/video-engine-agent.md`
4. Update this CLAUDE.md file
5. Run `/video-validate --refs` to verify cross-file consistency

### Adding a New Video Platform
1. Run `/video-add-platform` skill
2. It scaffolds platform guide, updates cross-references

### File Naming
- Reference files: lowercase, kebab-case (e.g., `global-promo-config.md`)
- No spaces in filenames
- Storytelling refs: `F{N}_{Name}.md` format (existing convention)
- Image-video refs: `{NN}-{name}.md` format (existing convention)

## Debugging

Symptom or error message? `grep -n '<text>' docs/debugging.md` (one row per known failure, with cause and fix).

---

**Version:** 3.21.1
**Last Updated:** 2026-10-17

Release history: [CHANGELOG.md](CHANGELOG.md).

## gaspol Ticket Counter

Prefix: GV
Last ticket: GV-25

## Tool-first rule (library)

Before writing any script for video, audio, animation or assembly, read `docs/tool-routing.md` and use the listed tool. If nothing fits, extend `tools/vidkit/` (Python) or `tools/vidkit/js/` (Node) in this plugin, with a test, in the same session. Register it by adding its entry (tool + route) to `tools/registry.json`, then run `python3 tools/registry_build.py render`; do not edit the table in `docs/tool-routing.md` by hand. Never leave a reusable script in a project folder.

**New-tool gate (GV-25).** `python3 tools/registry_build.py validate --coverage` (run by `bash tests/run.sh`) refuses a tool that overlaps another tool of the same phase on ≥50% of tasks without `distinct_because`/`replaces`, that no test names (file name, import line, `vidkit.<stem>`), or that no skill, agent, reference, hook, template or other tool uses (a `vidkit <cmd>` mention counts; `docs/` does not). Fix the cause; `internal_reason` only for a real imported helper.