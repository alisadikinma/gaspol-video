> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-23.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. Blocking, like a test gate. **Never batch all updates at the end.** Update ONLY this file — never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. Every path, contract and convention it needs is written here verbatim.

**Ticket:** GV-23
**Ledger:** .gaspol/progress/PROGRESS-GV-23.md
**Spec:** docs/plans/2026-10-17-GV-23-short-form-spec.md

## Goal

Make the gaspol-video short-form path decide its format from the video type, follow the
Thumbnail → Hook → Foreshadow → Body → CTA timeline, let `video-repackage` merge two source links,
and place subtitles, thumbnail titles and the watermark inside a measured safe area, enforced by a
blocking gate. Also fix why `video-repackage` is missing from sessions (marketplace pinned 3.11.1).

## Architecture Context (from CLAUDE.md, verbatim where it matters)

- Worktree: `/Users/alisadikin/Drive-D/claude-plugin/gaspol-video/.claude/worktrees/GV-23-short-form`,
  branch `GV-23-short-form`, base `main` at v3.19.0. Run every command from the worktree root.
- Tests: `bash tests/run.sh` (groups `consistency` = `tests/consistency/*.sh`, `py` =
  `python3 -m unittest` over `tests/py/test_*.py`, `node` = `node --test tests/node/`). There is no
  pytest in this repo on purpose; `detect-stack` printed `unit: pytest`, which is wrong here —
  the runner is `bash tests/run.sh` (decision recorded in the ledger).
- Tool rule: before writing any video/audio script read `docs/tool-routing.md`; new reusable code
  goes in `tools/vidkit/` with a test; register it in `tools/registry.json` (keys `version`,
  `tools`, `routes`, `ffprobe_allow`; tool entry `{"id","purpose","tasks","phase","replaces",
  "distinct_because","internal_reason"}`; route entry `{"task","use","tools"}`), then
  `python3 tools/registry_build.py render`; never edit the table in `docs/tool-routing.md` by hand.
  Gates: `python3 tools/registry_build.py validate --coverage` and `render --check`.
- ffprobe: never call it directly; use `tools/vidkit/ff.py` (`ff.ffmpeg(...)`, `ff.probe(...)`).
- Venv tools: dependency-bearing tools import through `tools/_venv.py`, which re-execs into
  `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/venv` or exits 2 naming `tools/setup.sh`.
  `mediapipe==1.0.1` is already in `requirements.txt` (used by `tools/person_mask.py`).
- Model pinning pattern (`tools/setup.sh` lines 50-72): versioned URL + `MODEL_SHA256`, temp file,
  `shasum -a 256`, refuse on mismatch, `mv` into `$MODEL_DIR`.
- Profile-with-source precedent: `media/loudness-profiles.json` =
  `{"profiles": {"default": {"lufs": -14, "true_peak": -1.0, "source": "..."}}}`.
- `tools/vidkit/karaoke.py` `build_ass(words, total_s, watermark=None, watermark_opacity=0.12,
  font="Helvetica Neue", font_size=86, margin_v=360, accent=ACCENT_TEAL, per_group=2, width=1080,
  height=1920)`; ASS style `Alignment 2` (bottom centre), so baseline Y = 1920 − 360 = 1560 (81 %),
  inside the UI band. `watermark_event(..., font_size=84)` places it at `\an5\pos(540,960)`.
- `tools/vidkit/cover.py` `apply(video, thumb, out, ass=None, hold_s=0.12, ...)` puts the thumbnail
  on the first frames and as mp4 cover art.
- `tools/vidkit/__main__.py` registers subcommands with `sub.add_parser(...)` (`ingest`, `scenes`,
  `karaoke`, `cover`, `mixdown`, `tidy`, …).
- `tools/viral_checklist.py`: `problems_in(text)`, `check(path)`, `rate(stats)`, `main()` with
  subcommands `check` and `rate`.
- `skills/video-brainstorm/SKILL.md`: Step 1.0b Video Type at line 79 (`promo | issue`), Step 1.5
  Platform Selection at line 422, brief template at line 556+ with `## Platform: {platform}
  ({aspect_ratio}, {duration})` and `## Honesty Limits (only when video_type: issue)`.
  `video_type` is read only by `skills/video-script/SKILL.md` and `video-brainstorm`.
- `skills/video-script/SKILL.md` rule 27 and context item 12 gate F12 on "Shorts/Reels/TikTok".
- `skills/video-repackage/SKILL.md` flow: 1 Ingest, 2 Read the source, 3 Storyline map,
  4 Assets, 5 Production, 6 Packaging, 6b Tools, 7 Hand-off.
- Owner decisions (2026-10-17): one ticket; four types; 9:16 max 60 s; merge max 2 links; safe area
  profile `short-organic` (bottom 21 %) default, `short-ads` (bottom 35 %) shipped; thumbnail title
  stamped by code, never rendered by the image model; measure 6 Samuel Christ Shorts; layout gate
  BLOCKS.
- Language: skill/reference/plan text in English (repo convention). Owner-facing questions inside
  skills are Indonesian, as today.

## Tech Stack

Python 3 stdlib + ffmpeg for everything except the face box (MediaPipe face detector in the venv).
Bash consistency checks. No new pip dependency.

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Video type + format | owner answer in Step 1.0b | `strategic-brief.md` fields | Partly | Extend to 4 types + `aspect`, `max_duration_s`, `platforms` |
| F13 timeline | NotebookLM `fd70ee32` answers of 2026-10-17 (quoted in Phase I) | reference file | No | Create `reference/storytelling_script_gen/F13_Short_Form_Timeline.md` |
| Timeline check | `av-script.md` `Tahap`/`Detik` columns | `viral_checklist.py timeline` | No | Create subcommand |
| Merge two links | yt-dlp via `vidkit ingest`, `vidkit scenes`, AssemblyAI via `tools/gen_subs.py` | existing CLIs | Yes | Use; add the merge flow to the skill |
| Layout profiles | Meta official page + third-party templates + Samuel measurement | `media/layout-profiles.json`, `tools/vidkit/layout.py` | No | Create |
| Samuel numbers | 6 real Samuel Christ Shorts | `vidkit ingest` + ffmpeg frames | No | Measure in Phase B |
| Subtitle defaults | profile | `vidkit karaoke` | Yes | Read defaults from profile |
| Thumbnail title | profile + owner title text | `vidkit title` (ffmpeg drawtext) | No | Create |
| Face box | MediaPipe face detector `blaze_face_short_range` | `tools/layout_gate.py` via `_venv.py` | No | Create + pin model in `setup.sh` |
| Layout gate | rendered ASS/title/watermark boxes, face boxes | `tools/layout_gate.py` | No | Create, blocking |
| Skill registration | `gaspol-one/.claude-plugin/marketplace.json` (`"version": "3.11.1"` today) | `claude plugin update` | Yes | Bump at release |

If any source above cannot be reached (Samuel links, model URL, a real 9:16 master): STOP and ask.

## Phase table

| Phase | Deliverable | Est. |
|---|---|---|
| A | layout profiles + loader | 15 |
| B | Samuel measurement → profile `data` values | 15 |
| C | karaoke + watermark defaults from profile | 10 |
| D | `vidkit title` | 15 |
| E | face model pin + face box | 15 |
| F | `layout_gate.py` text boxes + safe area | 15 |
| G | `layout_gate.py` face checks + previews + CLI | 15 |
| H | wiring: registry, validate `--layout`, post `--final`, package | 15 |
| I | F13 reference + `viral_checklist.py timeline` | 15 |
| J | video-brainstorm 4 types + video-script | 15 |
| K | video-repackage Foreshadow + merge 2 links | 15 |
| L | video-package three texts + doc 21 9:16 path | 10 |
| M | release + marketplace + real-data run | 15 |

---

### Phase A: Layout profiles and loader

**Estimated time:** 15 minutes

**Files:**
- Create: `media/layout-profiles.json`
- Create: `tools/vidkit/layout.py`
- Test: `tests/py/test_layout.py`

**Steps:**
1. Write failing test for `layout.load("short-organic")` returning a safe box `(x0, y0, x1, y1)` = `(65, 269, 972, 1517)` on 1080×1920 (left 6 %, top 14 %, right 10 %, bottom 21 %; rounding: `round(pct*size)`, x1 = width − right, y1 = height − bottom). Expected error: `ModuleNotFoundError: No module named 'tools.vidkit.layout'`.
2. Run `python3 -m unittest tests.py.test_layout`, confirm it fails for that reason.
3. Write `media/layout-profiles.json`:
   ```json
   {"profiles": {
     "short-organic": {"width": 1080, "height": 1920,
       "safe": {"top": {"pct": 0.14, "source": "official: Meta, facebook.com/business/help/980593475366490"},
                "bottom": {"pct": 0.21, "source": "tafsiran: YouTube Shorts / TikTok overlay templates (third-party), organic posts"},
                "left": {"pct": 0.06, "source": "official: Meta"},
                "right": {"pct": 0.10, "source": "tafsiran: YouTube Shorts template right 192px (third-party)"}},
       "subtitle": {"font_pct": {"value": 0.045, "source": "tafsiran: notebook fd70ee32 4-6%"},
                    "per_group": {"value": 2, "source": "tafsiran: notebook fd70ee32 1-3 words"},
                    "chin_gap_pct": {"value": 0.10, "source": "tafsiran: notebook fd70ee32"}},
       "title": {"font_pct": {"value": 0.10, "source": "tafsiran: notebook fd70ee32 8-12%"},
                 "center_y_pct": {"value": 0.38, "source": "tafsiran: notebook fd70ee32 30-45%"},
                 "max_words": {"value": 5, "source": "data: notebook fd70ee32, Samuel titles 3-5 words"},
                 "min_font_pct": {"value": 0.07, "source": "tafsiran"}},
       "timeline_tolerance_s": {"value": 1.0, "source": "tafsiran"}},
     "short-ads": {"inherits": "short-organic",
       "safe": {"bottom": {"pct": 0.35, "source": "official: Meta ads Reels/Stories 35%"}}}}}
   ```
4. Implement `tools/vidkit/layout.py`: `load(name, path=None)` (resolves `inherits`, deep-merges), `safe_box(profile)`, `value(profile, dotted_key)`, `validate(doc)` returning a list of problems (every leaf number object must carry a non-empty `source` starting with `official:`, `data:` or `tafsiran:`; unknown profile → `KeyError` listing valid names).
5. Add tests: unknown name lists valid names; `short-ads` bottom = 1920 − 672 = 1248; a leaf without `source` is reported; `inherits` of a missing profile is reported; malformed JSON raises `ValueError` naming the file.
6. Run tests, confirm all pass.
7. Commit: `feat(GV-23): layout profiles with a source on every number`.

**Verification:**
- [ ] static: UNKNOWN in detect-stack — none configured in this repo; `python3 -m py_compile tools/vidkit/layout.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `layout.validate()` on the shipped file returns `[]`
- [ ] No placeholder/TODO comments in new code
- [ ] Error paths covered: unknown profile, missing source, bad inherits, malformed JSON

### Phase B: Measure 6 Samuel Christ Shorts

**Estimated time:** 15 minutes (plus download time)

**Files:**
- Create: `docs/evals/short-form-layout-measurement.md`
- Modify: `media/layout-profiles.json`
- Test: `tests/py/test_layout.py`

**Steps:**
1. Write failing test asserting `subtitle.font_pct`, `subtitle.per_group`, `title.font_pct` and `title.center_y_pct` of `short-organic` have a `source` starting with `data:` and naming `docs/evals/short-form-layout-measurement.md`. Expected error: `AssertionError` (source starts with `tafsiran:`).
2. Run it, confirm the failure.
3. Ask the owner (AskUserQuestion) for 6 Samuel Christ Shorts links, or confirm the channel URL to list them with `yt-dlp --flat-playlist`. Never guess the channel handle.
4. `python3 -m tools.vidkit ingest "<url>" <scratchpad>/samuel/<n>` for each; clips stay in the scratchpad, never in the repo. A failed download: report the link, ask for a replacement; do not measure fewer than 6 without owner approval.
5. Per clip: extract 5 frames where a subtitle is visible and the cover frame (`ffmpeg -ss <t> -frames:v 1`). Measure in pixels on the 1080×1920-scaled frame: subtitle cap height, subtitle baseline Y, words shown at once, title cap height and title block centre Y on the cover. Use a crop + threshold with ffmpeg (`crop`, `lutyuv`) and read the box from the bright-pixel extent; record the method.
6. Write the eval doc: table per clip, median per measure, method, date, links. Values outside the safe box are listed with the clamped value used.
7. Update the four profile values with medians (clamped to the safe box), `source: "data: docs/evals/short-form-layout-measurement.md, median of 6"`.
8. Run tests, confirm all pass. Commit: `docs(GV-23): Samuel layout measurement, profile values from data`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Eval doc lists 6 real links and per-clip numbers (no invented number)
- [ ] No clip file added to git (`git status --short` shows no `.mp4`)
- [ ] No placeholder/TODO comments

### Phase C: Karaoke and watermark defaults from the profile

**Estimated time:** 10 minutes

**Files:**
- Modify: `tools/vidkit/karaoke.py`, `tools/vidkit/__main__.py`
- Test: `tests/py/test_vidkit.py`

**Steps:**
1. Write failing test: `build_ass(words, 5.0, profile="short-organic")` puts the subtitle style `MarginV` so the baseline sits at or above `safe_box.y1` and font size = `round(font_pct*1920)`; `per_group` from the profile. Expected error: `TypeError: build_ass() got an unexpected keyword argument 'profile'`.
2. Run it, confirm the failure.
3. Add `profile=None` to `build_ass` and the `karaoke` CLI (`--profile`, default `short-organic`). Explicit `font_size`/`margin_v`/`per_group` arguments still win. Without a profile and with no explicit values, behaviour stays as today (existing tests unchanged).
4. Watermark: keep centre position; assert its box stays inside the safe area at the profile's font size (test).
5. Error paths: unknown profile → CLI exit 2 with valid names; non-1080×1920 width/height scales the pct values.
6. Run tests, confirm all pass. Commit: `feat(GV-23): karaoke subtitles sit inside the safe area`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Old default call (no profile) produces byte-identical ASS to before (test)
- [ ] No placeholder/TODO comments

### Phase D: `vidkit title` — stamp the thumbnail title

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/title.py`
- Modify: `tools/vidkit/__main__.py`
- Test: `tests/py/test_vidkit.py`

**Steps:**
1. Write failing test: `title.stamp(img, "RUMAH 70 MILIAR", out, profile="short-organic")` writes `out` and returns the drawn box; box inside the safe area; text upper-cased. Expected error: `ModuleNotFoundError: No module named 'tools.vidkit.title'`.
2. Run it, confirm the failure.
3. Implement with ffmpeg `drawtext` (bold font from `fc-match -f '%{file}' 'Montserrat:bold'`, falling back to `Helvetica Neue Bold` via `fc-match`; the resolved font path is printed), `box=1:boxcolor=black@0.85:boxborderw=<pad>`, centre X, centre Y = `center_y_pct`, up to 2 lines (split at the word boundary nearest the middle). Box returned by re-rendering the text alone on black and reading the bright-pixel extent (shared helper with Phase F: put `text_box(png)` in `tools/vidkit/layout.py`).
4. Refusals (exit 2 in CLI, `ValueError` in API): more than `max_words`; empty text; a line wider than the safe area at `min_font_pct` (shrink from `font_pct` down to `min_font_pct` first, never below); input image not 9:16.
5. CLI: `python3 -m tools.vidkit title <img> "<text>" <out> [--profile P] [--y-pct F]`; prints the box as JSON and writes `<out>.box.json` for the gate.
6. Run tests, confirm all pass. Commit: `feat(GV-23): vidkit title stamps the cover title inside the safe area`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Rendered test PNG opened and looked at; the title reads correctly
- [ ] Each refusal has a test
- [ ] No placeholder/TODO comments

### Phase E: Face detector model and face box

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/setup.sh`
- Create: `tools/face_box.py`
- Test: `tests/py/test_face_box.py`, `tests/consistency/person-mask-setup.sh` (extend, or a new `face-model-setup.sh`)

**Steps:**
1. Write failing consistency test: `tools/setup.sh` fetches `face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite` from `https://storage.googleapis.com/mediapipe-models/` with a 64-hex `FACE_MODEL_SHA256`. Expected error: grep exit 1.
2. Run it, confirm the failure.
3. Download the model once into the scratchpad, compute `shasum -a 256`, and pin that value; add the fetch block to `setup.sh` copying the selfie-model pattern (temp file, hash check, refuse on mismatch). Run `bash tools/setup.sh` and confirm `model ok`.
4. Write failing unit test for `face_box.boxes(video, every_n)` pure parts: frame index selection and the "no face" record (`{"frame": i, "box": null}`), with the detector injected as a fake. Expected error: `ModuleNotFoundError`.
5. Implement `tools/face_box.py` through `tools/_venv.py` (lazy mediapipe import inside the function, so pure helpers stay stdlib-testable). Frames read with ffmpeg to raw RGB; returns `[{"frame", "t", "box": [x0,y0,x1,y1] | null}]`. Errors: model missing → exit 2 naming `tools/setup.sh`; unreadable video → exit 2.
6. Real check: run on one real clip with a face (any project clip under `~/Drive-D` with a person; find with `find`), look at one frame with the box drawn.
7. Run tests, confirm all pass. Commit: `feat(GV-23): face box from MediaPipe face detector, pinned model`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] `bash tools/setup.sh` prints `model ok` for both models
- [ ] One real frame with the drawn face box looked at
- [ ] No placeholder/TODO comments

### Phase F: `layout_gate.py` — text boxes and safe area

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/layout_gate.py`
- Test: `tests/py/test_layout_gate.py`

**Steps:**
1. Write failing test: `layout_gate.text_boxes_from_ass(ass, times)` returns a box per sampled time, measured by rendering the ASS alone on a black 1080×1920 `color` source with ffmpeg and reading the non-black extent. Expected error: `ModuleNotFoundError: No module named 'tools.layout_gate'`.
2. Run it, confirm the failure.
3. Implement `text_boxes_from_ass`, `watermark_box` (same method), `title_box` (reads `<thumb>.box.json` from Phase D; missing → re-measure the thumbnail is impossible without the clean image, so missing box.json = exit 2 naming `vidkit title`).
4. Implement `check_safe(boxes, profile)` → list of `{"what","t","box","overflow_px","edge"}`.
5. Tests: box fully inside → `[]`; 1 px past bottom → one finding naming `bottom`; empty ASS → no boxes, reported as `no subtitles found` note (not a pass silently: the CLI prints it); ASS with text at several times samples each event's midpoint.
6. Run tests, confirm all pass. Commit: `feat(GV-23): layout gate measures text boxes and the safe area`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Measured box of a known ASS matches the expected position within 4 px (test)
- [ ] No placeholder/TODO comments

### Phase G: `layout_gate.py` — face checks, previews, CLI

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/layout_gate.py`
- Test: `tests/py/test_layout_gate.py`

**Steps:**
1. Write failing test: `check_face(sub_boxes, face_boxes, profile)` flags an intersecting subtitle and a subtitle whose top is less than `chin_gap_pct*1920` below the face box bottom; frames with `box: null` go to `skipped`. Expected error: `AttributeError: module 'tools.layout_gate' has no attribute 'check_face'`.
2. Run it, confirm the failure.
3. Implement `check_face`; thumbnail: title box must not intersect the face box of the cover image.
4. Previews: `.tmp/layout-{tiktok,reels,shorts}.jpg` = one frame with semi-transparent bands for that platform's UI (TikTok bottom 320 px / right 120 px, Reels bottom 35 %/top 14 %, Shorts bottom 400 px / right 192 px; numbers from the spec's research, written as constants with a comment naming the source) and the safe box outline.
5. CLI: `python3 tools/layout_gate.py check <project> [--video output/final.mp4] [--ass <file>] [--thumb packaging/thumb-*.png] [--profile short-organic] [--every 15]`. Exit 0 pass, 1 any finding, 2 bad input (missing file, unknown profile, missing venv/model). Report to stdout and `work/layout-report.md`. Skipped face frames listed, never counted as pass silently.
6. Run tests, confirm all pass. Commit: `feat(GV-23): layout gate face checks, platform previews, CLI`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Exit codes 0/1/2 each covered by a test
- [ ] One preview JPG looked at
- [ ] No placeholder/TODO comments

### Phase H: Wiring and registry

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/registry.json`, `docs/tool-routing.md` (generated), `skills/video-validate/SKILL.md`, `skills/video-post/SKILL.md`, `skills/video-package/SKILL.md`, `skills/video-repackage/SKILL.md` (6b tools list)
- Test: `tests/consistency/layout-gate-contract.sh`

**Steps:**
1. Write failing consistency check: registry has `tools/layout_gate.py`, `tools/face_box.py`, `tools/vidkit/layout.py`, `tools/vidkit/title.py`; `video-validate` has a `--layout` section; `video-post` `--final` and `video-package` call `layout_gate.py check` before final; `media/layout-profiles.json` validates. Expected error: check exit 1.
2. Run it, confirm the failure.
3. Add registry entries + routes ("Check text and watermark sit in the 9:16 safe area", "Stamp the thumbnail title", "Face box of a clip"); `python3 tools/registry_build.py render`.
4. Edit the four skills (one short paragraph each, blocking language: "not final until `layout_gate.py check` exits 0").
5. Run `python3 tools/registry_build.py validate --coverage`, `render --check`, `bash tests/run.sh`. Commit: `feat(GV-23): wire the layout gate into validate, post and package`.

**Verification:**
- [ ] `python3 tools/registry_build.py validate --coverage` exit 0
- [ ] `python3 tools/registry_build.py render --check` exit 0
- [ ] `bash tests/run.sh` passes
- [ ] No placeholder/TODO comments

### Phase I: F13 timeline reference and timeline check

**Estimated time:** 15 minutes

**Files:**
- Create: `reference/storytelling_script_gen/F13_Short_Form_Timeline.md`
- Modify: `tools/viral_checklist.py`
- Test: `tests/py/test_viral_checklist.py`

**Steps:**
1. Write failing test: `viral_checklist.timeline_problems(text)` on an `av-script.md` table with columns `Tahap` and `Detik` returns `[]` for Hook 0-3, Foreshadow 3-6, Body 6-50, CTA 50-54 and a problem for a missing Foreshadow, out-of-order stages, Hook ending after 3 s + tolerance. Expected error: `AttributeError: ... no attribute 'timeline_problems'`.
2. Run it, confirm the failure.
3. Write F13 with the table and rules from the spec §2, each labelled `[DATA]`/`[TAFSIRAN]`, citing notebook `fd70ee32` queried 2026-10-17, plus: Thumbnail frame 0-1; Hook 0-3 (bold statement + bold text + motion, no greeting, promise kept); Foreshadow 3-6 (micro clue 0.5-1 s / reaction snippet / mystery prop; conflict not answer; no fake foreshadow); Body 6-50 (points or escalation, chat tone, no dead air); CTA last 2-4 s ("follow @alisadikinma biar …", never bare "jangan lupa subscribe"); watermark 0-100 %; loop ending "Dan itulah …"; cut every 1-3 s; b-roll matches the spoken word; BGM under voice. State that F13 adds timing to F12 and never overrides the 9 Commandments, F5, F6.
4. Implement `timeline_problems` and subcommand `timeline <av-script.md>` (exit 0/1, 2 when the table has no `Tahap`/`Detik` columns). Tolerance from `media/layout-profiles.json` `timeline_tolerance_s`. Stage names accepted: `Thumbnail`, `Hook`, `Foreshadow`, `Body`, `CTA` (case-insensitive). `Detik` format `a-b` with decimals allowed; malformed → problem naming the row.
5. Run tests, confirm all pass. Commit: `feat(GV-23): F13 short-form timeline and timeline check`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Every F13 rule carries `[DATA]` or `[TAFSIRAN]`
- [ ] No placeholder/TODO comments

### Phase J: video-brainstorm four types, video-script

**Estimated time:** 15 minutes

**Files:**
- Modify: `skills/video-brainstorm/SKILL.md`, `skills/video-script/SKILL.md`, `reference/global-promo-config.md` (short note on `video_type` values)
- Test: `tests/consistency/video-type-routing.sh`

**Steps:**
1. Write failing consistency check: Step 1.0b lists `presentasi`, `promo`, `isu`, `edukasi`; `edukasi` routes to `/video-repackage`; Step 1.5 no longer asks a platform question and shows the derived format; brief template has `video_type`, `aspect`, `max_duration_s`, `platforms`; `issue` alias documented; video-script loads F13 and requires `Tahap`/`Detik` for 9:16 and runs `viral_checklist.py timeline`. Expected error: check exit 1.
2. Run it, confirm the failure.
3. Edit Step 1.0b (AskUserQuestion in Indonesian, 4 options with the table from the spec §1), Step 1.5 → "Format Confirmation" (show derived values, owner confirms or edits), brief template fields, Honesty Limits heading `video_type: isu (or legacy issue)`, Hard Rule 16 text for the four types.
4. video-script: rule 27 and context item 12 trigger on `aspect: 9:16` (not only on platform names); add rule 28 (F13 timeline + `timeline` check before the approval gate); A/V table gains `Tahap`, `Detik` for 9:16.
5. Run tests, confirm all pass. Commit: `feat(GV-23): video type decides format; 9:16 scripts follow F13`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] No placeholder/TODO comments

### Phase K: video-repackage Foreshadow and two-link merge

**Estimated time:** 15 minutes

**Files:**
- Modify: `skills/video-repackage/SKILL.md`
- Test: `tests/consistency/repackage-merge.sh`

**Steps:**
1. Write failing consistency check: repackage flow names Foreshadow (3-6 s) between hook and body; has a merge mode with `ref/sumber-1/`, `ref/sumber-2/`, a point table with same/unique/conflicting/strongest hook, a hard stop for owner approval before the storyline, 60 s budget with cut proposal or two-part series, max two links, both links in `strategic-brief.md`; loads F13. Expected error: check exit 1.
2. Run it, confirm the failure.
3. Edit the skill: step 1 Ingest (one or two links; a failed download stops and names the link), step 2 transcribe each via `tools/gen_subs.py`, new step 2b Merge (table + approval), step 3 storyline in F13 order, rule list adds Foreshadow and the 60 s cap, triggers add "gabung dua video", "dua link".
4. Run tests, confirm all pass. Commit: `feat(GV-23): repackage adds foreshadow and merges two links`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] No placeholder/TODO comments

### Phase L: video-package three texts and doc 21 9:16 path

**Estimated time:** 10 minutes

**Files:**
- Modify: `skills/video-package/SKILL.md`, `reference/post-production/21-thumbnail-style-elements.md`
- Test: `tests/consistency/thumbnail-style.sh` (extend existing contract, or new `short-form-texts.sh`)

**Steps:**
1. Write failing check: package defines thumbnail title (3-5 words), video title (5-9 words + tags, ALL CAPS), hook on-screen text (4-7 words) as separate outputs; doc 21 has a 9:16 path: image rendered without text, title via `vidkit title`, formula number + public figure + curiosity word, honesty guardrail, never over the face; `layout_gate.py check` before final. Expected error: check exit 1.
2. Run it, confirm the failure.
3. Edit both files. 16:9 path in doc 21 unchanged.
4. Run tests, confirm all pass. Commit: `feat(GV-23): three distinct short-form texts; 9:16 thumbnails stamp the title`.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] No placeholder/TODO comments

### Phase M: Release, marketplace, real-data run

**Estimated time:** 15 minutes

**Files:**
- Modify: `.claude-plugin/plugin.json`, `CLAUDE.md` (architecture rows, reference rows for F13, changelog), `README.md`, `tests/consistency/*` version gates that pin the version
- Modify (separate repo): `/Users/alisadikin/Drive-D/claude-plugin/gaspol-one/.claude-plugin/marketplace.json`, `/Users/alisadikin/Drive-D/claude-plugin/gaspol-one/README.md`
- Create: `docs/evals/layout-gate-run.md`
- Test: `tests/consistency/marketplace-version.sh`

**Steps:**
1. Write failing check: `plugin.json` version equals the gaspol-video entry version in `../gaspol-one/.claude-plugin/marketplace.json` when that file exists (skip with a printed note when absent). Expected error: check exit 1 (`3.20.0` vs `3.11.1`).
2. Run it, confirm the failure.
3. Bump to `3.20.0` (next minor after `3.19.0`; if main moved, take the next free minor and record it). Update CLAUDE.md (tool count, architecture rows for `layout_gate.py`, `face_box.py`, `vidkit layout/title`, `media/layout-profiles.json`, F13 in the storytelling reference table, v3.20.0 changelog incl. "Not done": >2 links, 4:5 LinkedIn, OCR, per-platform renders), README version + changelog.
4. In gaspol-one: set the gaspol-video entry version to the same value, update its README version table. Commit there separately (`chore: gaspol-video 3.20.0`).
5. Real-data run: find a real finished 9:16 master (`find /Users/alisadikin/Drive-D -name '*.mp4' -path '*output*'` then `ff.probe` for 1080×1920); none → STOP and ask. Run `layout_gate.py check` on it with its ASS and thumbnail; record command, exit code, findings and one preview in `docs/evals/layout-gate-run.md`. A FAIL on an old master is a finding, not a test failure; record it honestly.
6. `bash tests/run.sh`; registry gates. Commit: `release(GV-23): v3.20.0`.
7. After merge (gaspol-finish): `claude plugin update gaspol-video@gaspol-one`, then in a new session confirm `gaspol-video:video-repackage` is listed; record the result in the ledger.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] `python3 tools/registry_build.py validate --coverage` and `render --check` exit 0
- [ ] Versions match: plugin.json, CLAUDE.md, README, gaspol-one marketplace + README
- [ ] `docs/evals/layout-gate-run.md` has a real run with its exit code
- [ ] No placeholder/TODO comments

## Out of scope

More than two merge links; a 4:5 LinkedIn variant; OCR of burned-in text; separate renders per
platform; changing the 16:9 thumbnail path.
