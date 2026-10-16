> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-19.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. This is **blocking**, like a test gate: no next phase until both are written. **Never batch all updates at the end.** Update ONLY this file — never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. Every path, contract and convention it needs is written here verbatim.

**Ticket:** GV-19
**Ledger:** .gaspol/progress/PROGRESS-GV-19.md
**Spec:** docs/plans/2026-10-16-GV-19-viral-style-spec.md

## Goal

Give `gaspol-video` the style of a reference Shorts channel (Samuel Christ) and a viral-video framework, without reusing any footage, voice, face or script. Five parts: (A) measure the reference's SFX/music timing instead of guessing; (B) add its overlay vocabulary to `KineticOverlay` (sticker icons, step counter, red vignette, falling-object burst, two-tier caption preset); (C) a retention gate that reports pass/fail per rule on a real cut; (D) a 7-stage viral framework inside `video-script` with a checklist that a generated script must carry filled; (E) docs, routing, tests, version.

## Architecture Context (read from the code at plan time)

- **Tool-first rule:** reusable tools live in `tools/vidkit/` (Python, stdlib + ffmpeg) or top-level `tools/*.py`; each needs a test and a row in `docs/tool-routing.md`. A new top-level `tools/*.py` must be named in `CLAUDE.md`'s Architecture table (`tests/consistency/tools-index.sh` fails otherwise) and the plugin version in `.claude-plugin/plugin.json` is asserted by that same test.
- **Test runner:** `bash tests/run.sh [all|consistency|py|node]`. Python tests are stdlib `unittest` in `tests/py/test_*.py` (helpers in `tests/py/media.py`: `make_clip`, `requires_ffmpeg`; no binary fixtures are committed, clips are synthesized with ffmpeg lavfi). Node tests are `tests/node/*.test.mjs` under bare `node --test`. Consistency checks are `tests/consistency/*.sh`. There is NO pytest and NO numpy: `detect-stack` printing `unit: pytest` is wrong for this repo.
- **Kinetic overlay (GV-17):**
  - `tools/overlay_plan.py` (467 lines): constants `ICONS = ("fire","gavel","chart","cloud","question","arrow","circle")`, `FX_KEYWORD = (1,2,3,4)`, `COLORS = ("white","yellow")`, `LAYERS`, `ANCHORS = ("top","left","right")`, `TEXT_SHARE_MAX = 0.5`, `LEAD_S = 0.10`, `OVERLAP_MAX_S = 0.1`; functions `resolve_anchor(words, phrase, start_index)`, `_validate_cue_fields(cue, label, problems)`, `_plan_scene(out, sc, problems_all)`, `run(output_folder, scene)`. Refuses (collects every problem, then exits non-zero) when text is on screen more than 50% of the speech.
  - `templates/remotion/lib/overlayFx.mjs`: ZERO-IMPORT pure functions of `(frame, startF, fps, ...)`: `clamp01, easeOut, blurIn, glitch(seeded mulberry32), countUp, strokeProgress, leadIn, exitFx, springIn, drift, carouselX, cueVisible, cueStyle`. Tested by `tests/node/overlay-fx.test.mjs`.
  - `templates/remotion/lib/overlay-fx.tsx`: types `CueSpec, PanelSpec, BubbleSpec, OverlayPlan, CuePos`; `export const ICONS: Record<string,string[]>` (stroke-only SVG paths on a 100x100 canvas); components `Icon, CueText, Panel, Bubble, Carousel, SourceBox`; constants `LEAD_PX = 40, KEYWORD_PX = 120, SAFE_PX = 96`.
  - `templates/remotion/Overlay.template.tsx`: `KineticOverlay` composition, `SCENE` constant, `PANELS` registry.
  - **Contract:** `ICONS` keys in `overlay-fx.tsx` and `overlay_plan.py` MUST be identical; `tests/consistency/overlay-template-contract.sh` and `tests/py/test_overlay_plan.py` (around line 253) assert it.
  - Brand tokens come from the project's `shots/src/shots/brand.json` (template: `templates/remotion/brand.json`: `background, ink, inkSoft, accent, highlight, displayFont, bodyFont, scriptFont`), read by `templates/remotion/lib/brand.ts`. Never hardcode a colour (the reference's neon green becomes `highlight`).
  - Reference doc: `reference/post-production/19-keyword-text-overlay.md` (sections 0-7; section 6 = red alarm flash behind the person via ffmpeg `alphamerge`; section 7 = workflow).
  - Evidence convention: `docs/evals/overlay-kinetik-run.md` records a rendered still per effect; `tests/consistency/overlay-evidence.sh` greps that doc for required phrases.
- **Validator:** `skills/video-validate/SKILL.md` has flags `--script --image --video --post --refs --all`; `--post` holds checks P1-P6. Gate pattern to copy: `tools/qa_frames.py --check` (verdict cells, exit 1 on a missing, empty or `FAIL:` cell, `UNSURE:` is not a failure).
- **Script skill:** `skills/video-script/SKILL.md` (Hard Rules at line 58, A/V script format at line ~140: table `| Timecode | Video | Audio | Beat |`, beats named `Pattern Interrupt`, `Hook`, `Foreshadow`, ..., then `## CTA Execution` and `## Production Notes`). Storytelling references: `reference/storytelling_script_gen/F1`..`F11`. Hook Vault = F5, CTA Vault = F6, foreshadow = F7.
- **Vidkit reuse:** `tools/vidkit/ff.py` (`run, ffmpeg, probe, duration, has_audio`), `speech.py` (`words_from_alignment, speech_spans, gaps, snap_to_gaps, energy_db(path,start,end,hop,rate)`), `loudness.py` (`measure`), `sheet.py` (`contact_sheet, montage`), `ingest.py` (`download(url,out_dir,name)`, `detect_cuts(video, threshold)`, `scenes_from_cuts`), CLI registered in `tools/vidkit/__main__.py`. Music headroom: `tools/mix_music.py` `MIN_HEADROOM_DB = 12.0`, `level_dbfs(path)`, `gain_to_sit_under(voice_path, music_path, headroom_db)`. Word timings of a clip: `node tools/vidkit/js/eleven.mjs stt` (billed, needs `ELEVENLABS_API_KEY` in `.env`).
- **Pending sister ticket:** GV-18 lives in worktree `.claude/worktrees/GV-18-master-quality` (branch `GV-18-master-quality`) and plans its own `tools/vidkit/beats.py` and a version bump. This plan names its audio-study module `tools/vidkit/audiostudy.py` so the two cannot collide on a file. At merge time, if both end up with onset detection, unify then (listed in Utang terbuka). Version: Phase E bumps from whatever `.claude-plugin/plugin.json` holds when E runs (now `3.14.0`); do not assume GV-18 shipped first.

## Tech Stack

Python 3 stdlib + ffmpeg/ffprobe/yt-dlp (all already required); `unittest`; Node builtins; TypeScript/TSX in the Remotion template (checked with `npx tsc --noEmit` inside a scaffolded workspace); bash consistency checks; markdown references. No new third-party dependency.

## Verification commands (resolved at plan time)

`detect-stack` returned `static: UNKNOWN`, `lint: UNKNOWN`, `unit: pytest` (wrong for this repo). Same resolution the owner already chose for GV-18 in this repo (decision to be re-confirmed in the post-plan modal):
- **static:** `python3 -m compileall -q tools`
- **unit (per phase):** `python3 -m unittest discover -s tests/py -t . -p 'test_<file>.py' -q` and `node --test tests/node/<file>.test.mjs`
- **full suite (end of each phase):** `bash tests/run.sh`
- **Baseline at `bbbcf10`:** `bash tests/run.sh` → RESULT PASS (node 87/0 fail).

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Reference clips (13 Shorts) | the channel's public Shorts; URLs from NotebookLM notebook `SAMUEL-STYLE 2026-10` (`fd70ee32-cc7f-4bfd-8462-46531c1ccd5d`) via `notebooklm source list` | `python3 -m tools.vidkit ingest <url> <scratch>` (yt-dlp) | Clips were deleted from scratch; tool exists | Re-download into a scratch dir OUTSIDE the repo; never commit |
| Word timings of reference clips | the clips' audio | `node tools/vidkit/js/eleven.mjs stt` (billed) | Yes | Ask the owner before billing; no guessed timings |
| SFX onsets, music tempo/energy, cut times | the clips | new `tools/vidkit/audiostudy.py` over `ff.run` PCM decode + `ingest.detect_cuts` + `speech.energy_db` | No | Create (real measurement, stdlib) |
| Sticker icons / step counter / vignette / burst | `work/overlay-plan.json` read by `tools/overlay_plan.py` | extend `overlay_plan.py` + `overlayFx.mjs` + `overlay-fx.tsx` | Partly | Extend; keep `ICONS` identical in py and tsx |
| Alarm colour, caption preset | project `brand.json` | `lib/brand.ts` | Yes (`highlight`); `alarm` missing | Add optional `alarm` token with a neutral default; preset tagged `source: course` |
| Static-frame detection | rendered master | `ffmpeg -vf freezedetect` | No | Create inside `tools/retention_gate.py` |
| Hook / foreshadow timing | `av-script.md` Beat column + `vo/vo-manifest.json` words | new `tools/retention_gate.py` | No | Create |
| B-roll vs spoken word | `work/edit-plan.json` segments + VO words | `retention_gate.py` writes `work/retention-qa.md` verdict cells, `--check` reads them | No | Create (judged in-session, same pattern as `qa_frames.py`) |
| BGM vs voice | master voice and music levels | reuse `mix_music.level_dbfs` / `MIN_HEADROOM_DB` | Yes | Reuse |
| Viral checklist | `av-script.md` `## Viral Checklist` block | new `tools/viral_checklist.py check` | No | Create |
| Analytics thresholds | `packaging/calibration.json` written by `tools/yt_stats.py` | `viral_checklist.rate()` | Schema must be read first | Read `yt_stats.py`, map real keys; if a key is absent, report `unknown`, never invent |

## Pre-flight Conflict Matrix (written at plan time; gaspol-parallel re-scans before dispatch)

| Pair | Shared file / interface | Finding |
|---|---|---|
| B and C | none (B: overlay files + doc 19; C: `retention_gate.py`, doc 20, `video-validate`, `global-promo-config.md`) | Safe in parallel |
| B and D | none | Safe |
| C and D | `reference/global-promo-config.md` would be shared if D edited it | Ruling: D does NOT touch it; thresholds live in `F12_Viral_Framework.md`. Only C appends §31 |
| C, D and CLAUDE.md | `tools-index.sh` demands a CLAUDE.md row per new `tools/*.py` | Ruling: Phase E alone edits `CLAUDE.md`. Until E, `bash tests/run.sh` is expected to fail ONLY `tools-index.sh`, naming `retention_gate.py` / `viral_checklist.py`; phases C and D verify with their own test files plus `bash tests/run.sh py node` |
| A and B/C/D | A's findings decide icon list, SFX/music rules, defaults | Ruling: A ends with a user-review gate; B/C/D step 0 re-reads the findings and STOPs if a finding contradicts that phase's text |
| B self-check | `ICONS` in py vs tsx | Same step edits both; both contract tests listed in verification |

## Out of scope

GV-18 items. Auto-posting. Pulling analytics (`yt_stats.py` needs an OAuth client that does not exist; D only reads the file it writes). Copying any footage, voice, face, script or music of the reference. Computer-vision "is this b-roll relevant" (judged in-session by a person/Claude, not by a model call).

---

### Phase A: Audio & timing study (spec phase 1)

**Estimated time:** 15 minutes of editing plus download/measure runtime. This phase is large; split into A1 (tool, TDD) and A2 (run on real clips, write evidence) in the ledger.

**Files:**
- Create: `tools/vidkit/audiostudy.py`
- Modify: `tools/vidkit/__main__.py` (register `audiostudy`)
- Test: `tests/py/test_audiostudy.py`
- Create: `docs/evals/viral-audio-study.md` (evidence; the findings table)
- Create: `tests/consistency/viral-study-evidence.sh`

**Module contract (`tools/vidkit/audiostudy.py`, stdlib only):**
- `decode_mono(path, rate=16000)` → `array('h')` of samples via `ff.run` (`ffmpeg -i path -ac 1 -ar 16000 -f s16le -`). Raises `ff.FFError` on a file with no audio stream (check `ff.has_audio` first and raise `ValueError("no audio stream: <path>")`).
- `onsets(samples, rate, hop_ms=10, min_gap_ms=80, k=3.0)` → list of onset times in seconds: high-pass by first difference, short-time energy, an onset is a frame whose energy exceeds `k` times the median of the previous 0.5 s AND is a local maximum; peaks closer than `min_gap_ms` collapse to the first. Empty or shorter-than-one-hop input → `[]`.
- `tempo(onset_times)` → BPM `float` from the histogram of inter-onset intervals folded into 60-180 BPM; fewer than 4 onsets → `None` (never a made-up number).
- `energy_profile(path, seg_s=2.0)` → list of `{start, end, dbfs}` using `speech.energy_db`; last short segment kept if ≥ 0.5 s.
- `relate(onset_times, word_times, cut_times, tol_s=0.06)` → per onset `{t, nearest_word_start, d_word, nearest_cut, d_cut, label}` with `label` one of `on-word` (|d_word| ≤ tol), `on-cut` (|d_cut| ≤ tol), `both`, `free`. Empty words or cuts lists are legal (their distance is `None`).
- `study(clip, words=None)` → dict `{clip, duration, loudness_lufs, cuts, onsets, tempo_bpm, energy, relations}`; `loudness_lufs` via `loudness.measure`.
- CLI: `python3 -m tools.vidkit audiostudy <clip> [--words words.json] [--out report.json]`; `words.json` is `[[word,start_s,end_s],...]` (same shape `vidkit karaoke` reads).

**Steps:**
1. Write failing test for `onsets` in `tests/py/test_audiostudy.py`: synthesize a 4 s 16 kHz signal with 5 clicks at 0.5, 1.2, 2.0, 2.8, 3.5 s (build the samples in Python and write a wav with the `wave` module, or use `make_clip`); assert the detected times match within 30 ms and count == 5. Expected error: `ImportError: cannot import name 'audiostudy' from 'tools.vidkit'`.
2. Run the test, confirm it fails for that reason.
3. Implement `decode_mono` and `onsets`. Run, confirm pass.
4. Write failing tests, one at a time, each followed by minimal code: (a) `tempo` of a click train at 120 BPM (0.5 s apart, 12 clicks) → `119 ≤ bpm ≤ 121`; (b) `tempo([0.1, 0.9])` → `None`; (c) `onsets` of pure silence → `[]`; of a 5 ms buffer → `[]`; (d) `onsets` of a continuous sine (no transients) → `[]`; (e) two clicks 30 ms apart collapse to one; (f) `relate` labels: click at a word start → `on-word`, at a cut → `on-cut`, at both → `both`, neither → `free`, empty `words` → `d_word is None`; (g) `decode_mono` on a clip with `audio=False` (from `make_clip`) raises `ValueError`; (h) `energy_profile` of a 5 s clip with `seg_s=2.0` returns 3 segments, the last 1.0 s long; of a 4.2 s clip drops nothing, of 4.3 s... keeps a 0.3 s tail only if ≥ 0.5 s (so it is dropped); (i) `study()` on a `make_clip` clip returns every key and is JSON-serializable.
5. Register `audiostudy` in `tools/vidkit/__main__.py`; test the CLI end to end on a `make_clip` clip: exit 0, JSON written, a missing file → non-zero exit and a one-line error, no traceback.
6. Commit: `feat(GV-19): vidkit audiostudy — onsets, tempo, energy, word/cut relation`.
7. **A2 — get the clips.** Run `notebooklm source list -n fd70ee32 --no-truncate` and obtain the 13 Short URLs (use whatever flag shows the URL; if the CLI shows only titles, fall back to the channel page via `yt-dlp --flat-playlist -J <channel>/shorts`). Create a scratch dir OUTSIDE the repo: `/private/tmp/claude-501/-Users-alisadikin-Drive-D-claude-plugin-gaspol-video/viral-ref/` (verify `git status` shows nothing from it). Download with `python3 -m tools.vidkit ingest <url> <dir> --name s01` … `s13`. If fewer than 13 download, record which failed and why; continue with what exists (state the real N in the evidence doc).
8. **STOP and ask the owner** (AskUserQuestion, plain Indonesian) whether to run billed ElevenLabs STT on the clips to get word timings (rough cost = total seconds of audio). No answer = no billing. If declined, the word-related columns in the findings read `not measured` and `relate()` runs with `words=None`.
9. Run `audiostudy` on every clip (with words where available). Write per-clip JSON to the scratch dir, never the repo.
10. Write `docs/evals/viral-audio-study.md`: a table per clip (duration, LUFS, cuts, SFX-onset count, onsets per minute, tempo BPM or `none detected`, energy range) plus a **Findings** table with columns `claim | number | data or interpretation | clips supporting it`. Every sentence about SFX type or music genre is `interpretation` unless a measurement backs it. State plainly that onset detection cannot separate SFX from speech consonants; flag which onsets fall inside speech (when words exist) as `inside-speech`. Include the section **"What this changes in phases B, C, D"** (icon list additions, any default that should differ from the course numbers, SFX-vs-word offset to use).
11. Write `tests/consistency/viral-study-evidence.sh` that fails unless the doc exists and contains the phrases `data`, `interpretation`, `Findings`, `What this changes in phases B, C, D`, and `not measured` or a words column. Run it, confirm green.
12. Commit: `docs(GV-19): audio and timing study of the reference clips`.
13. **Review gate:** present the Findings table to the owner (AskUserQuestion: proceed to B/C/D as planned / adjust phases first). Record the decision in the ledger under `## Keputusan saat jalan`.

**Error paths covered:** no audio stream (step 4g), missing file (step 5), yt-dlp failure or removed video (step 7, recorded not hidden), billing declined (step 8), too few onsets for tempo (4b). **Edge cases covered:** silence, tiny buffer, no transients, onsets closer than the gap, empty words/cuts, last short segment. **Observability:** the CLI prints one line per clip (`clip dur LUFS onsets bpm`) and `--out` keeps the full JSON.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_audiostudy.py' -q` passes
- [ ] `bash tests/run.sh` passes (new tool lives under `tools/vidkit/`, so `tools-index.sh` does not apply)
- [ ] Findings table in `docs/evals/viral-audio-study.md` has a number and a data/interpretation tag on every row; N of clips stated is the N actually measured
- [ ] `git status` shows no downloaded media inside the repo
- [ ] No placeholder/TODO comments in new code
- [ ] Owner decision after the review gate recorded in the ledger

---

### Phase B: Overlay vocabulary in KineticOverlay (spec phase 2)

**Estimated time:** split in the ledger into B1 icons, B2 step counter, B3 vignette, B4 burst, B5 preset, B6 evidence. Each ≤ 15 minutes.

**Step 0 (all of B):** read `docs/evals/viral-audio-study.md` "What this changes". If it contradicts this phase, STOP and ask. Then read, in full, the functions this phase extends: `templates/remotion/lib/overlayFx.mjs` (`cueStyle`, `cueVisible`), `templates/remotion/lib/overlay-fx.tsx` (`CueText` lines ~246-340, `Icon`), `templates/remotion/Overlay.template.tsx`, `tools/overlay_plan.py` (`_validate_cue_fields`, `_plan_scene`), `templates/remotion/lib/brand.ts`.

**Files:**
- Modify: `templates/remotion/lib/overlayFx.mjs`, `templates/remotion/lib/overlay-fx.tsx`, `templates/remotion/Overlay.template.tsx`, `templates/remotion/lib/brand.ts`, `templates/remotion/brand.json`, `tools/overlay_plan.py`, `reference/post-production/19-keyword-text-overlay.md`
- Test: `tests/node/overlay-fx.test.mjs`, `tests/py/test_overlay_plan.py`, `tests/consistency/overlay-template-contract.sh`
- Create: `docs/evals/viral-overlay-run.md`, `tests/consistency/viral-overlay-evidence.sh`

**Design (decided here so the executor does not invent):**
- **B1 Sticker icons.** Add stroke-only icons to BOTH `ICONS` (tsx, 100x100 canvas paths) and `ICONS` tuple (py): `warning` (triangle with exclamation), `money` (banknote), `check`, `cross`, `clock`, `lock`. Add more only if the Phase A table names them. Order in both = identical (the contract test compares the lists).
- **B2 Step counter.** New optional scene field `steps: {"total": N, "marks": [{"n": 1, "words": "pertama"}, ...]}` (N from 2 to 9). `overlay_plan.py` resolves each mark's `words` with `resolve_anchor` into a frame and writes `steps: {total, marks:[{n, f}]}` into the generated json. Pure function `stepState(f, marks, total)` in `overlayFx.mjs` → `{active, litProgress}`: `active` = highest `n` whose frame ≤ f (0 before the first), `litProgress` eases 0→1 over 0.25 s after the mark. Drawn in `overlay-fx.tsx` as a top bar of numbered circles ①..N, active lit with `highlight`, past ones `ink`, future dimmed `inkSoft`. Step marks do NOT count toward `TEXT_SHARE_MAX` (they are numerals, not words); say so in doc 19.
- **B3 Red vignette.** New optional cue field `vignette: true`. `overlay_plan.py` accepts only a boolean. `vignetteAlpha(f, inF, outF, fps)` → 0..1: fade in 0.15 s, blink at 3 Hz between 0.55 and 1.0 of max, fade out 0.2 s, exactly 0 outside `[inF, outF]`. Drawn as a front-layer `radial-gradient(transparent 55%, alarm)` that leaves the centre (face) clear; max alpha 0.55. Colour token `alarm` (new, optional in `brand.json`, default `#D7263D`); `brand.ts` falls back to the default if the project file lacks it. Doc 19 §6 keeps the person-only ffmpeg flash for full-frame backgrounds; the vignette is the cheap edge-only variant.
- **B4 Falling-object burst.** New optional cue field `burst: {"icon": "money", "count": 14}`; `icon` must be in `ICONS`; `count` integer 1-30. `burstParticles(f, startF, fps, seed, count)` → array of `{x, y, rot, opacity}` (x spread across width as a 0-1 fraction from a seeded `mulberry32`, y falls from -0.1 to 1.1 over 1.6 s with per-particle delay up to 0.5 s, constant rotation speed). Pure, deterministic: same arguments → same array, no `Math.random`.
- **B5 Two-tier caption preset.** `overlay_plan.py` gains `PRESETS = {"viral": {...}}` and an optional scene field `preset`. The `viral` preset sets, for cues that did not state them: `color: "yellow"` (rendered with the `highlight` token, so the neon green is the brand's, not hardcoded), `fx: 1`, `pos.anchor: "center"`, and writes `preset: {"name": "viral", "source": "course"}` plus size hints `lead_px 40, key_px 120` into the generated json. Add `"center"` to `ANCHORS` and handle it in `CueText`. The preset is **course advice (Montserrat 15-18, centre, 1-3 s cut interval)**, tagged `source: course` in the code constant, the generated json and doc 19; an explicit cue field always overrides it. Unknown preset name → refusal naming the allowed set.

**Steps:**
1. Write failing node tests in `tests/node/overlay-fx.test.mjs`: `stepState` (before first mark → `active 0`; at mark → `active n`, `litProgress` 0; 0.25 s later → 1; marks out of order are sorted by `n`), `vignetteAlpha` (0 outside window, 0 exactly at `inF`, > 0 inside, 0 at and after `outF`, never NaN, never above 1), `burstParticles` (length == count; deterministic across two calls; changes with seed; all `y` ≥ -0.1 at start and ≥ 1.1 at end; count 0 → `[]`). Expected error: `SyntaxError: The requested module ... does not provide an export named 'stepState'` (and the same for the others).
2. Run, confirm it fails for that reason.
3. Implement `stepState`, `vignetteAlpha`, `burstParticles` in `overlayFx.mjs`, zero imports, clamped, NaN-free. Run, confirm pass.
4. Write failing Python tests in `tests/py/test_overlay_plan.py` for the new plan fields: valid `steps` resolved to frames; `steps.total` 1 or 10 → refusal; a mark whose `words` are not spoken after the previous mark → refusal naming scene and mark; duplicate `n` → refusal; `vignette: "yes"` → refusal; `burst` with unknown icon, `count` 0 or 31 or a float → refusal; unknown `preset` → refusal; `viral` preset fills defaults and an explicit `fx: 3` overrides; the preset block carries `source: course` in the generated json; all problems of a plan are listed at once (existing behaviour kept); a scene that stays under the 50% share with steps but would exceed it with step words counted still passes. Expected error: `AssertionError` / missing key `steps`.
5. Implement in `overlay_plan.py`. Add the six icon names to `ICONS` in py AND `overlay-fx.tsx` in the same commit. Run `tests/py/test_overlay_plan.py` and `bash tests/consistency/overlay-template-contract.sh`; both green.
6. Implement the TSX drawing: step bar, vignette layer, burst particles using `Icon`, `center` anchor, preset size hints. Add `alarm` to `brand.json` (`_comment` kept) and `brand.ts` fallback. Update `Overlay.template.tsx` only if it needs to pass the new `steps` through; keep `SCENE` import pattern unchanged.
7. Extend `tests/consistency/overlay-template-contract.sh` to assert: new `ICONS` equal in py and tsx (already), `alarm` exists in `templates/remotion/brand.json`, the string `source: course` appears in `reference/post-production/19-keyword-text-overlay.md` and in `tools/overlay_plan.py`. Run, green.
8. Update `reference/post-production/19-keyword-text-overlay.md`: new section "8. Viral vocabulary" covering icons, step counter, vignette, burst, preset; list which numbers are course advice; keep §0 "keywords, not subtitles" intact and say the 50% limit still binds.
9. Commit: `feat(GV-19): viral overlay vocabulary — icons, step counter, vignette, burst, preset`.
10. **Render proof.** Scaffold a Remotion workspace in the scratch dir with `templates/remotion/scaffold.mjs` (use `speaker-2s.mp4` from `tests/fixtures/` as the clip; no real client media), write a `work/overlay-plan.json` using every new element, run `overlay_plan.py`, render a still at enter-mid, hold and exit-mid of each new element with `scripts/qa-frames.mjs`, and run `npx tsc --noEmit` in the workspace. LOOK at each still. Write `docs/evals/viral-overlay-run.md` with one heading per element (`sticker icon`, `step counter`, `red vignette`, `falling burst`, `two-tier preset`, `center anchor`), what was seen, what was fixed, and the literal `npx tsc --noEmit` result. If `npm`/`npx` or the Remotion install is unavailable on this machine, STOP and ask — do not write evidence for a render that did not happen.
11. Write `tests/consistency/viral-overlay-evidence.sh` (pattern: `tests/consistency/overlay-evidence.sh`) requiring those six phrases plus `npx tsc --noEmit` in the doc. Run, green.
12. Commit: `docs(GV-19): rendered evidence for the viral overlay vocabulary`.

**Error paths covered:** every invalid field is a listed refusal (step 4); words not spoken; unknown preset; render tooling missing (step 10). **Edge cases covered:** step count bounds, duplicate and out-of-order marks, vignette outside window, zero/one/max burst count, determinism of seeds, explicit cue field vs preset default, 50% share unaffected by numerals. **Observability:** refusals name scene + cue/mark like the existing ones; the generated json records `preset.source` so a later reader sees it was course advice.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_overlay_plan.py' -q` passes
- [ ] unit: `node --test tests/node/overlay-fx.test.mjs` passes
- [ ] `bash tests/consistency/overlay-template-contract.sh` and `bash tests/consistency/viral-overlay-evidence.sh` pass
- [ ] `bash tests/run.sh py node` passes (full `bash tests/run.sh` may fail only `tools-index.sh` if C/D already added tools; B adds none)
- [ ] `npx tsc --noEmit` in the scaffolded workspace is clean, and the result is quoted in `docs/evals/viral-overlay-run.md`
- [ ] A rendered still exists and was looked at for every new element
- [ ] `overlay_plan.py` still refuses text on screen > 50% of speech (existing test still green, not weakened)
- [ ] No hardcoded colour in new TSX (grep new lines for `#[0-9a-fA-F]{3,6}` outside the `alarm` fallback in `brand.ts`)
- [ ] No placeholder/TODO comments in new code

---

### Phase C: Retention gate (spec phase 3)

**Estimated time:** split in the ledger into C1 freeze, C2 hook/foreshadow, C3 b-roll sheet, C4 bgm, C5 CLI+docs. Each ≤ 15 minutes.

**Step 0:** re-read `docs/evals/viral-audio-study.md`; STOP and ask if a finding contradicts the defaults below. Read `tools/qa_frames.py` (`--check` and verdict-cell parsing) and `tools/mix_music.py` (`level_dbfs`, `gain_to_sit_under`, `MIN_HEADROOM_DB`) before writing code; reuse them, do not copy.

**Files:**
- Create: `tools/retention_gate.py`, `reference/post-production/20-retention-gate.md`
- Modify: `skills/video-validate/SKILL.md`, `reference/global-promo-config.md` (append §31 only)
- Test: `tests/py/test_retention_gate.py`

**Rules and defaults (all are COURSE ADVICE, overridable, reported not enforced):** module constant `DEFAULTS = {"static_max_s": 3.0, "hook_first_word_by_s": 3.0, "foreshadow_by_s": (3.0, 6.0), "bgm_headroom_db": 12.0, "source": "course"}`; every override via `--static-max-s` etc. or a `work/retention.json` file. The tool always exits 0 on a rule FAIL when run as a report (`retention_gate.py report`), because the gate must not become a quality ceiling; the owner decides. Exit codes: 0 = report written, 2 = the tool could not run (missing master, no ffmpeg, malformed plan). `check` (reads `work/retention-qa.md` verdict cells only) exits 1 on a missing/empty/`FAIL:` cell, mirroring `qa_frames.py --check`; this is what makes the in-session b-roll judgment a real gate.
- **R1 static frame:** run `ffmpeg -i master -vf freezedetect=n=0.003:d=<static_max_s> -an -f null -` and parse `freeze_start`/`freeze_end`/`freeze_duration` from stderr; every interval ≥ the limit is a FAIL listing start, end, length.
- **R2 hook:** first spoken word starts by `hook_first_word_by_s`. Word source: `vo/vo-manifest.json` items' `words` (ms) with offsets, else `--words-file`. No word source → `not measured`, never PASS.
- **R3 foreshadow:** the `av-script.md` table row whose Beat column is `Foreshadow` (case-insensitive) starts within `foreshadow_by_s`; parse the Timecode `M:SS` / `M:SS.s` start. No such row → FAIL `no Foreshadow beat`; unparsable timecode → `not measured` with the cell text quoted.
- **R4 b-roll matches the spoken word:** for every `edit-plan.json` segment of kind b-roll (any segment that is not the main speaker take; read `tools/edit_render.py` for the real field names before coding), write into `work/retention-qa.md` one section with: segment id, time range, the spoken words overlapping that range, a contact-sheet path from `vidkit.sheet.contact_sheet` into `.tmp/`, and a Verdict cell (`PASS` / `FAIL: reason` / `UNSURE: note`). Cells survive a re-run when the segment's clip bytes are unchanged (hash), cleared when changed — copy that behaviour from `qa_frames.py`.
- **R5 BGM not covering voice:** reuse `mix_music` level functions on voice and music stems (`tools/make_stems.py` output `output/stems/voice.wav`, `music.wav` if present, else `not measured`); FAIL if voice-minus-music headroom < `bgm_headroom_db` in any spoken span (`speech.speech_spans`).
- **Output:** `work/retention-report.md` with one row per rule: `rule | status (PASS / FAIL / not measured / needs verdict) | numbers | threshold | source: course`.

**Steps:**
1. Write failing test for R1 in `tests/py/test_retention_gate.py`: a `make_clip` master with a 4 s still segment (build with ffmpeg concat of a moving bar clip and a `-loop 1` still) → the report lists one freeze interval ≥ 3.0 s; a 2.5 s still → PASS; `--static-max-s 2` turns the 2.5 s case into a FAIL. Expected error: `ModuleNotFoundError: No module named 'tools.retention_gate'`.
2. Run, confirm it fails for that reason.
3. Implement R1 (`parse_freezes(stderr)` pure function tested with canned stderr text including: no freezes, two freezes, a freeze that runs to end of file with no `freeze_end`). Run, green.
4. Failing tests then code, one rule at a time: R2 (first word at 2.9 s PASS, 3.1 s FAIL, no manifest → `not measured`, manifest with empty words → `not measured`); R3 (`| 0:04-0:06 | ... | Foreshadow |` PASS, `0:07` FAIL, no Foreshadow row FAIL, `0:03.5-0:06` PASS, garbage timecode → `not measured`, beat label with different case/spacing); R4 (sections written, cells preserved on re-run with unchanged clip, cleared on changed clip, `check` exits 1 with an empty cell and 0 when all `PASS`/`UNSURE:`); R5 (voice 20 dB over music PASS, 8 dB FAIL, missing stems `not measured`).
5. Implement `report` and `check` subcommands, `--help`, argument errors (missing `output_folder` → exit 2 with one line). Test: a full `report` run on a synthesized project folder produces `work/retention-report.md` with all five rows and the exit code 0 even when rules FAIL; a missing master → exit 2.
6. Write `reference/post-production/20-retention-gate.md`: each rule, its default, "source: course, not platform data", how to override, why it reports instead of blocking, what `not measured` means.
7. In `skills/video-validate/SKILL.md`: add `--retention` to the Usage table (`Input: master + av-script.md + vo-manifest.json + edit-plan.json`) and a section `## Retention Validation (--retention)` with checks R1-R5 pointing at the tool; add the flag to the AskUserQuestion list and to `--all`. Do not renumber existing checks.
8. Append `## 31. Retention gate defaults (course advice)` to `reference/global-promo-config.md` with the `DEFAULTS` table, tagged `source: course`. Do not edit any other section.
9. Run it for real on a finished cut: `/Users/alisadikin/Drive-D/project-video/REA-Reverse_Engineer_Anything/` (has `final/REA-final.mp4`). Read-only: pass `--out` into the scratch dir if the tool would write inside the project; otherwise copy the needed inputs to a scratch project folder. Paste the real report table into `reference/post-production/20-retention-gate.md` under "Real run". If the REA folder lacks `av-script.md` or word timings, say which rules were `not measured`. Do not fake inputs.
10. Commit: `feat(GV-19): retention gate — static frame, hook, foreshadow, b-roll sheet, bgm headroom`.

**Error paths covered:** missing master/ffmpeg/plan (exit 2), no word source, no stems, unparsable timecode, absent Foreshadow row, stale verdicts. **Edge cases covered:** freeze to end of file, two freezes, thresholds exactly at the limit (≥ vs >: a 3.0 s freeze is a FAIL, state it in the test name), empty segment lists, re-run idempotence. **Observability:** report rows carry the measured numbers; `check` prints which section/cell is wrong.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_retention_gate.py' -q` passes
- [ ] `bash tests/run.sh py node` passes; `bash tests/run.sh` fails ONLY `tools-index.sh` naming `retention_gate.py` (fixed in Phase E)
- [ ] `video-validate --retention` section exists and is in Usage and `--all`
- [ ] A real report from a finished cut is pasted in `20-retention-gate.md`, with `not measured` rows named honestly
- [ ] Every default is tagged `source: course` and overridable (a test overrides one)
- [ ] The gate never exits 1 on a rule FAIL in `report` mode (test)
- [ ] No placeholder/TODO comments in new code

---

### Phase D: Viral framework in video-script (spec phase 4)

**Estimated time:** split in the ledger into D1 reference doc, D2 checklist tool (TDD), D3 skill wiring, D4 real script proof. Each ≤ 15 minutes.

**Step 0:** re-read `docs/evals/viral-audio-study.md`. Query the course notebook for the framework wording — `notebooklm ask -n 114215f6 "<question>"` — for: the 7 stages, the title formula, the loop ending, the analytics thresholds. Treat answers as source material; quote the notebook as the source in the doc. Keep `[DATA]` (stated by the course/transcripts) separate from `[TAFSIRAN]` (interpretation), as the spec's evidence does. Read `skills/video-script/SKILL.md` Hard Rules (line ~58) and the A/V script format (line ~140), and `tools/yt_stats.py` for the keys it writes to `packaging/calibration.json`.

**Files:**
- Create: `reference/storytelling_script_gen/F12_Viral_Framework.md`, `tools/viral_checklist.py`
- Modify: `skills/video-script/SKILL.md`, `skills/video-validate/SKILL.md` (S-check only), `agents/video-engine-agent.md` (reference table row)
- Test: `tests/py/test_viral_checklist.py`, `tests/consistency/viral-framework-contract.sh`

**Content contract for F12:** the 7 stages in order — (1) topic research, (2) hook, (3) script, (4) edit, (5) caption, (6) posting, (7) analytics — each with a pass/fail checklist line set (3-5 items, each testable by reading the script or the files); a **title formula** (emotion + public figure + large amount; flagged `[DATA]` from the 24 transcripts; a title that names a real person must not assert an unverified claim about them — add this guard in the doc and in the checklist); a **loop ending** rule (last line returns to the hook's open question; "Dan itulah..." as an example, not a mandatory phrase); **analytics thresholds** from the spec: watched-full ≥ 20%, average watch ≥ 50%, replicate winners > 100k views, each tagged `source: course`. Includes the plain-language statement that this is imitation of structure, never of content.

**`tools/viral_checklist.py` contract:**
- `STAGES = ("topic research","hook","script","edit","caption","posting","analytics")`; `ITEMS = {stage: [item ids]}` loaded from constants that match F12 (test asserts every item id in the constant appears in F12).
- `check(path)` parses the `## Viral Checklist` block of an `av-script.md`: a markdown table `| Stage | Item | Verdict |` where Verdict is `PASS`, `FAIL: reason`, `N/A: reason` or `PENDING: reason` (posting and analytics are legitimately `PENDING` at script time, because they happen after publishing). Exit 1 on: block missing, a stage missing, an item missing, an empty Verdict cell, `N/A` or `PENDING` without a reason, a `FAIL:` cell; `PENDING` on stages 1-5 is also exit 1 (they must be decided before the script is approved).
- `rate(stats)` → `{"watched_full": "pass"|"fail"|"unknown", "avg_watch": ..., "replicate": "yes"|"no"|"unknown"}` from a dict with the real keys found in `yt_stats.py` output; a missing key gives `unknown`, never a guess; thresholds module constants tagged course.
- CLI: `python3 tools/viral_checklist.py check <av-script.md>`; `python3 tools/viral_checklist.py rate <calibration.json>`.

**Steps:**
1. Write failing test in `tests/py/test_viral_checklist.py`: a fully filled checklist block → exit 0. Expected error: `ModuleNotFoundError: No module named 'tools.viral_checklist'`.
2. Run, confirm it fails for that reason.
3. Implement the parser and `check`. Failing tests then code, one each: block missing; one stage missing; one item missing; empty Verdict; `N/A` without reason; `FAIL:` cell; `PENDING` on stage 6 with a reason → OK; `PENDING` on stage 2 → fail; extra whitespace and different cell padding; Verdict in lowercase (`pass`) accepted; a table placed before `## Production Notes` and one after both found; two checklist blocks → refusal ("one block only").
4. Failing tests then code for `rate`: all three green (watched-full 0.21, avg 0.5, views 100001 → replicate yes); boundary (exactly 0.20 → pass, exactly 0.50 → pass, exactly 100000 → no); missing keys → `unknown`; string numbers like `"21%"` → parsed or `unknown`, tested; negative or > 1 fractions → `unknown` with a note.
5. Read `tools/yt_stats.py`; map its real output keys in `rate`; add a test using a dict shaped exactly like what `yt_stats.py` writes (copy a real example from its test file `tests/py/test_yt_stats.py`).
6. Write `reference/storytelling_script_gen/F12_Viral_Framework.md` per the content contract. Register it in the reference tables of `skills/video-script/SKILL.md` (Phase 2 reference list, "When Used: viral/short-form target") and `agents/video-engine-agent.md`.
7. Wire `skills/video-script/SKILL.md`: in the A/V script template add a `## Viral Checklist` block after `## Production Notes` (table skeleton with every stage/item and `PENDING` placeholders to be filled by the generator, not left); add a Hard Rule: "For short-form (platform Shorts/Reels/TikTok) the generated script MUST carry the filled Viral Checklist; run `python3 tools/viral_checklist.py check` before the approval gate"; add the Quality Gate line in "Script Quality Gate (Phase 2)". Add check `S10: Viral Checklist filled (short-form only)` to `skills/video-validate/SKILL.md` `--script`. The 9 Commandments and the existing Hook/CTA vault rules stay unchanged; F12 adds, never overrides.
8. Write `tests/consistency/viral-framework-contract.sh`: F12 exists with the seven stage headings, `source: course` appears next to each threshold, `video-script/SKILL.md` and `video-engine-agent.md` mention `F12_Viral_Framework.md` and `viral_checklist.py`, `video-validate` mentions `S10`. Run, green.
9. **Real proof (spec: "a generated script carries the filled checklist"):** pick a real finished project under `/Users/alisadikin/Drive-D/project-video/` that has an `av-script.md`, copy it to the scratch dir, fill the checklist honestly against it (FAIL where it fails), and run `check`. Paste the table and the exit code into `F12_Viral_Framework.md` under "Worked example". Do not edit the original project.
10. Commit: `feat(GV-19): viral framework F12, checklist tool and video-script wiring`.

**Error paths covered:** missing/duplicate block, missing stage or item, empty or reasonless cells, FAIL cells, malformed stats. **Edge cases covered:** threshold boundaries (≥), percent strings, out-of-range fractions, lowercase verdicts, padding, block placement. **Observability:** `check` prints each offending stage/item on its own line; `rate` returns `unknown` with the missing key named.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_viral_checklist.py' -q` passes
- [ ] `bash tests/consistency/viral-framework-contract.sh` passes
- [ ] `bash tests/run.sh py node` passes; `bash tests/run.sh` fails ONLY `tools-index.sh` naming `viral_checklist.py` (fixed in Phase E)
- [ ] F12 separates `[DATA]` from `[TAFSIRAN]`, names the notebook as source, and every threshold is tagged `source: course`
- [ ] The worked example in F12 is a real script's checklist with the real exit code
- [ ] Title-formula guard about unverified claims on a real person is in F12 and in the checklist items
- [ ] No placeholder/TODO comments in new code

---

### Phase E: Wrap (spec phase 5)

**Estimated time:** 15 minutes.

**Step 0:** confirm A-D are ticked `[x]` in the ledger. Run `git log --oneline -10` and `git -C ../gaspol-one log -1` to learn whether GV-18 shipped a version; read `.claude-plugin/plugin.json` for the current version `V`. New version = next minor above `V` (now `3.14.0` → `3.15.0`; if GV-18 already bumped to `3.15.0`, use `3.16.0`).

**Files:**
- Modify: `CLAUDE.md` (Architecture table rows for `tools/retention_gate.py`, `tools/viral_checklist.py`, `tools/vidkit/audiostudy.py`; Reference Files rows for `20-retention-gate.md` and `F12_Viral_Framework.md`; tool counts in Project Overview; changelog `### v<new> Changelog`; Version/Last Updated lines), `docs/tool-routing.md` (rows), `docs/vidkit.md` (audiostudy), `NOTICE`, `README.md` (version line + changelog), `.claude-plugin/plugin.json` and root `plugin.json` if it carries a version, `../gaspol-one/.claude-plugin/marketplace.json` and the version table in `../gaspol-one/README.md`
- Test: `tests/consistency/tools-index.sh` (version literal), any other consistency test that hardcodes `3.14.0` (find with `grep -rn '3\.14\.0' tests`)

**Steps:**
1. Write failing check: update the version literal in `tests/consistency/tools-index.sh` (and every other test that hardcodes the old version) to the new version. Expected error: `FAIL plugin.json version is not <new>`. Run `bash tests/consistency/tools-index.sh`, confirm it fails for that reason AND for the two missing CLAUDE.md rows.
2. Add the CLAUDE.md Architecture rows, Reference Files rows, tool counts (count from `tools/`, do not trust the old number) and the changelog entry. Run `tools-index.sh`; remaining failure must be only the version.
3. Bump `.claude-plugin/plugin.json` (and root `plugin.json` if it has a version). Run `tools-index.sh`, green.
4. Add rows to `docs/tool-routing.md`: "Measure SFX onsets / music tempo / cuts of a reference clip" → `python3 -m tools.vidkit audiostudy`; "Retention check on a finished cut" → `python3 tools/retention_gate.py report|check`; "Viral checklist / analytics verdict" → `python3 tools/viral_checklist.py check|rate`; "Viral overlay (icons, step counter, vignette, burst, preset)" → `overlay_plan.py` + `KineticOverlay`. Add `audiostudy` to `docs/vidkit.md`.
5. `NOTICE`: add an attribution-of-ideas entry — style and structure observed from a public Shorts channel (Samuel Christ) and framework from the owner's course notebook; state that no footage, voice, face, script, music or SFX is copied or redistributed.
6. README: version line + changelog entry; `../gaspol-one` marketplace entry version and README table must equal the plugin version (rule from the owner's global notes: cross-check `marketplace.json` before calling the release done).
7. Update the `## gaspol Ticket Counter` only if it is behind (it already says `Last ticket: GV-19`; leave it).
8. Run `graphify update .` (AST only, no API cost) if `graphify-out/` exists (it is gitignored).
9. Run `bash tests/run.sh` — full suite must be RESULT PASS.
10. Commit: `docs(GV-19): sync CLAUDE.md, routing, NOTICE and version for <new>`. Do NOT push or tag; the owner decides (finish offer via `gaspol-finish`).

**Error paths covered:** version drift between plugin.json / marketplace / README / test literal (step 6, 1). **Edge cases covered:** GV-18 merged first or not (step 0); tool counts recomputed. **Observability:** the changelog entry names each tool and doc added.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] `bash tests/run.sh` → RESULT PASS (all groups)
- [ ] `grep -rn '3\.14\.0' tests .claude-plugin plugin.json README.md CLAUDE.md` shows only changelog history lines, no live version assertion
- [ ] marketplace.json version == plugin.json version == README version line
- [ ] Every new tool/doc has a row in `CLAUDE.md` and `docs/tool-routing.md`
- [ ] No downloaded reference media, no `.env` values, no absolute scratch paths committed (`git diff --stat` reviewed; `tests/consistency/no-secrets.sh` green)
- [ ] No placeholder/TODO comments in new code

---

## Execution notes

- **Order:** A → (B ‖ C ‖ D) → E. B, C and D share no file (see matrix). Concurrent dispatch needs worktree isolation (`gaspol-worktree`). Parallel agents must each run only their own test file, never `tests/run.sh` consistency, until E (see matrix ruling).
- **Billing:** only Phase A step 8 can bill (ElevenLabs STT) and it is gated on an explicit owner answer. No other step calls a paid service.
- **Utang terbuka (known at plan time):** unify onset detection with GV-18's `beats.py` if both ship; `yt_stats.py` real run still pending an OAuth client, so `viral_checklist rate` is exercised on a synthetic dict shaped like its output until then.
