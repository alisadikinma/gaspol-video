> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-18.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. This is **blocking**, like a test gate: no next phase until both are written. **Never batch all updates at the end.** Update ONLY this file — never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. Every path, contract and convention it needs is written here verbatim.

**Ticket:** GV-18
**Ledger:** .gaspol/progress/PROGRESS-GV-18.md
**Spec:** docs/plans/2026-10-16-GV-18-master-quality-spec.md
**Artifact:** https://claude.ai/artifact/K74HGERZ5EMavYKLDAfGP4

## Goal

Raise the finished master of `gaspol-video`: (1) music that follows the video's topic and arc, and SFX with punch (layered impacts, cues snapped to music beats); (2) true colour (BT.709 tags, cross-clip colour match); (3) credit control (stills-first verdict gate, cost log, pre-flight estimate); (4) better thumbnails (style-element menu, render-verify check); (5) cheaper, safer re-renders (per-stage cache, encoder probe with fallback, heartbeat, sourced loudness profiles). The owner's stated pain is phase group 1: music does not match the topic and SFX lack punch.

## Architecture Context (from CLAUDE.md and code read at plan time)

- **Tool-first rule:** new reusable tools live in `tools/vidkit/` (Python, stdlib + ffmpeg) with a test and a row in `docs/tool-routing.md`, in the same change. Never a script in a project folder. New top-level `tools/*.py` must be named in CLAUDE.md's Architecture table (`tests/consistency/tools-index.sh` fails otherwise).
- **Test runner:** `bash tests/run.sh [all|consistency|py|node]`. Python tests are stdlib `unittest` in `tests/py/test_*.py`, run as `python3 -m unittest discover -s tests/py -t . -q` (single file: add `-p 'test_<name>.py'`). Consistency checks are `tests/consistency/*.sh`. No pytest in this repo (`detect-stack` printing `unit: pytest` is wrong; the repo's own runner is authoritative).
- **Music today:** `tools/gen_music.py` (`load_palette`, `plan_work`, `build_request(mood, defaults, length_s)`, `generate(library, env, only, force, dry_run, length_s, log, recipes)`; CLI flags `--library --recipes --only --length-s --force --dry-run --renorm`). Moods come from `media/music/library/palette.json` (`moods` is a LIST of `{id, tones, prompt, duration_s}`; `defaults` = model `music_v2`, `force_instrumental`, `target_lufs -20`, `ceiling_dbfs -1.5`). Tracks land in `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/library/music/` (`tools/asset_home.py`). `tools/mix_music.py` reads `work/music-plan.json` `{"out":..., "segments":[{"from_s","to_s","track":"library:<id>","gain_db"?}]}`; segments must not overlap; `MIN_HEADROOM_DB = 12`; `TONE_TO_MOOD` maps the six tones.
- **SFX today:** `tools/gen_sfx.py` (same recipe pattern, `recipes` list of `{id, prompt, duration_s, category, tags}`, clips normalised to -20 LUFS / -1.5 dBFS). `tools/mix_sfx.py` reads `work/sfx-plan.json` `{"catalog"?, "events":[{"sfx_id","at_s","gain_db"?,"optional"?}]}`; `load_plan(plan_path, project, master_duration_s, include_optional)` raises `PlanError`; `DENSITY_PER_MIN = 12`; audibility gate `STORY_CRITICAL_DB = 4.0`. Hard rule in `reference/post-production/14-sfx-design.md`: the user audits the cue sheet before anything is mixed.
- **Encode sites:** `tools/edit_render.py` (two `libx264 -crf 20 -pix_fmt yuv420p` sites in `build_commands` / `_merge_command`; `render(plan_path, project, out, allow_degraded, keep_parts)` runs per-segment commands then a concat copy, then `check_av_gate`), `tools/vidkit/mixdown.py` (final mux, `-crf 17`), `tools/vidkit/cover.py`, `tools/vidkit/join.py`.
- **Loudness:** `tools/vidkit/loudness.py` (`measure`, `normalize`, default `LUFS` constant -14).
- **Ledger of renders:** `tools/renders.py` (`renders.json`, phases `4A 4B 5 6`).
- **Pattern to copy for "check" gates:** `tools/qa_frames.py --check` (verdict cells; exit 1 on missing, empty or `FAIL:`).
- **Library home:** generated audio never enters the repo; recipes (palette json) do.
- **Marketplace:** `../gaspol-one/.claude-plugin/marketplace.json` entry `gaspol-video` (currently lists version 3.11.1; must be brought to the new version in Phase O).

## Tech Stack

Python 3 stdlib + ffmpeg/ffprobe (already required); `unittest`; bash consistency checks; markdown references. No new third-party dependency. Node only if an existing `.mjs` test must change (none planned).

## Verification commands (resolved at plan time)

`detect-stack` returned `static: UNKNOWN`, `unit: pytest` (wrong for this repo). The owner chose:
- **static:** `python3 -m compileall -q tools`
- **unit (per phase):** `python3 -m unittest discover -s tests/py -t . -p 'test_<file>.py' -q`
- **full suite (end of each phase):** `bash tests/run.sh`

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Per-topic music prompts | `work/music-brief.json` (authored by the skill from `strategic-brief.md` + `av-script.md`) | new `tools/music_brief.py` | No | Create (real file reader, no placeholder brief) |
| Music generation | ElevenLabs Music | `gen_music.generate(..., recipes=<project palette>)` | Yes | Reuse via `--recipes work/music-palette.json`; bills, confirm first |
| Music placement | `work/music-plan.json` | `mix_music.apply` | Yes | Reuse; brief tool writes `library:<id>` segments |
| Layered SFX | `work/sfx-plan.json` `stack` field | `mix_sfx.load_plan` | Partly | Extend `load_plan` to expand `stack` |
| New SFX clips | ElevenLabs sound-generation | `gen_sfx.generate` | Yes | Add recipes to `media/sfx/library/palette.json`; bills, confirm first |
| Beat times | the music file (mp3/wav) | new `tools/vidkit/beats.py` (ffmpeg PCM decode + onset peaks) | No | Create |
| BT.709 tag | ffprobe colour fields + ffmpeg flags | new `tools/vidkit/color.py` | No | Create; wire into edit_render + mixdown |
| Colour match | per-clip mean RGB (ffmpeg downscale to 1x1) | new `tools/vidkit/colormatch.py` | No | Create |
| Verdict gate | `keyframes/*.png` + `work/verdict.json` | new `tools/verdict_page.py` | No | Create |
| Cost log | `work/cost-log.json` + `media/pricing.json` (owner-maintained prices) | new `tools/cost_log.py` | No | Create; REFUSE when a price is missing, never guess |
| Thumbnail menu | own wording; source read from `/Users/alisadikin/Drive-D/claude-plugin/claude-youtube-editor/.claude/skills/thumbnail/references/style-elements.md` | new reference doc + `tools/thumb_verify.py` | No | Create |
| Stage cache | `.tmp/stages.json` in the project | new `tools/vidkit/stages.py` | No | Create; wire into `edit_render.render` |
| Encoder probe | `ffmpeg -encoders` | new `tools/vidkit/encoder.py` | No | Create; opt-in via env |
| Loudness profiles | `media/loudness-profiles.json` with a required `source` per entry | `vidkit.loudness` | No | Create; entries without `source` are refused |

## Out of scope

GV-19 (sticker icons, step counter, retention gate, script framework), avatar and cheap-model video paths, ControlNet, multi-provider TTS, stock matching, zoompan Ken-Burns (integer-pixel stutter; `plan_motion.py` covers motion).

---

## Phases

Phase labels: Phase 0 pre-flight, then A–O. Every phase's step 1 is the failing test. Each phase ends with a commit. A rung that does not apply says so with the reason.

### Phase 0: Pre-flight (no code)

**Estimated time:** 10 minutes

**Files:** none created by code. Branch/worktree only.

**Steps:**
1. Write failing test for the pre-flight precondition: run `git status --short` and confirm it is NOT clean (v3.14.0 work is uncommitted). Expected error: n/a (precondition check, not code), record the dirty list in the ledger Pre-flight table.
2. Commit the v3.14.0 work on `feat/vidkit-library` as its own commit(s) (vidkit mixdown/karaoke/cover/ingest/unwhite, `templates/remotion/lib/ali-effects.tsx`, `skills/video-repackage/`, docs, tests, plugin.json/CLAUDE.md/global-promo-config edits). Owner chose "commit v3.14.0 first". Do NOT stage the GV-18/GV-19 spec and plan files in that commit.
3. Run `bash tests/run.sh`; if red, STOP and record the failing check in the ledger Pre-flight table (a red baseline must not be blamed on GV-18). Ask the owner before continuing.
4. Commit the two spec files and this plan on `feat/vidkit-library` (spec/plan stay on a branch, never copied to main).
5. Create the worktree: `git worktree add .claude/worktrees/GV-18-master-quality -b GV-18-master-quality`. `.claude/worktrees/` is already in `.gitignore`. Do all remaining phases inside it. Note: a worktree does NOT isolate `~/.gaspol-video` (shared library); do not delete library files.
6. Copy the ledger into the worktree only if the worktree needs it; the ledger path `.gaspol/progress/PROGRESS-GV-18.md` is gitignored and lives in the main tree.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `bash tests/run.sh` passes (baseline recorded with counts in the ledger)
- [ ] `git worktree list` shows `.claude/worktrees/GV-18-master-quality`
- [ ] No placeholder/TODO comments introduced

### Phase A: Music brief builder (topic + domain + tone + arc → per-segment prompts)

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/music_brief.py`
- Test: `tests/py/test_music_brief.py`

**Contract (write exactly this):**
- Input `work/music-brief.json`:
  `{"topic": str, "domain": str, "tone": "Serious|Inspirational|Humorous|Professional|Casual|Edgy", "sound_world": str, "segments": [{"from_s": float, "to_s": float, "beat": "hook|build|body|peak|resolve|cta", "energy": 1-5}]}`. `sound_world` is the free-text instrument/texture world (e.g. "container port, cranes, industrial pulse"); the skill writes it from `strategic-brief.md` Domain Knowledge.
- `build_prompt(brief, segment) -> str`: pure. Joins, in order: tone style words (table below), beat shape words (table below), the brief's `sound_world`, energy phrase, and the fixed tail `instrumental, no vocals, leaves room for a speaking voice`. Hard cap 400 characters; if longer, drop energy phrase first, then trim `sound_world`. Never raises on length.
- Tone table: Serious → "restrained low pulse, documentary tension"; Inspirational → "warm rising strings and piano, hopeful"; Humorous → "playful light pizzicato, bouncy"; Professional → "clean modern underscore, steady light pulse"; Casual → "relaxed soft groove, airy"; Edgy → "tight driving synth, modern, punchy".
- Beat table: hook → "immediate, attention-grabbing, strong first second"; build → "gradually rising tension"; body → "steady supportive bed"; peak → "swelling to the loudest moment, then clean stop"; resolve → "releasing, settling, warm"; cta → "confident resolving lift".
- Energy phrase: 1 → "very low energy", 2 → "low energy", 3 → "medium energy", 4 → "high energy", 5 → "maximum energy".
- `mood_id(prompt, length_s) -> "brief-" + first 10 hex of sha256(prompt|round(length_s))`. Same input, same id (so an unchanged brief never re-bills).
- Length per segment is `to_s - from_s` clamped to `[10, 120]` seconds; a longer segment is covered by `mix_music.fit_track` looping (existing behaviour), a shorter one is padded up to 10 so the API gets a valid request. Verify these bounds against the `build_request`/ElevenLabs Music docs before shipping (open item); if the API limits differ, change the clamp constants and note it in the ledger Keputusan.
- CLI: `python3 tools/music_brief.py <project> [--brief work/music-brief.json] [--print]` writes `work/music-palette.json` (`{"_comment":..., "defaults": <copied from media/music/library/palette.json defaults>, "moods":[{"id","tones":[tone],"prompt","duration_s"}]}`) and `work/music-plan.json` segments (`track: "library:<id>"`, `gain_db` default left to `mix_music`), preserving an existing `out` key if the plan exists. `--print` prints the segment table (time, beat, id, prompt) and writes nothing. Refuses (exit 2, message names the field) a brief with a missing/empty `topic`, `domain`, `sound_world`, unknown `tone`/`beat`, `energy` outside 1–5, overlapping segments, or `to_s <= from_s`.

**Steps:**
1. Write failing test for `build_prompt`: two briefs identical except `topic`/`sound_world` ("container port" vs "hospital ward") yield different prompts, both ≤400 chars, both containing the tail `no vocals`. Expected error: `ModuleNotFoundError: No module named 'tools.music_brief'`.
2. Run the test, confirm it fails for that reason.
3. Implement `build_prompt`, tables, `mood_id`.
4. Write failing tests (one each): same input → same `mood_id`; different `beat` → different id; overlong `sound_world` (600 chars) → prompt ≤400; empty `topic` → `BriefError`; overlapping segments → `BriefError`; unknown tone → `BriefError`; energy 6 → `BriefError`. Expected error for each: `AttributeError`/`NameError` until implemented.
5. Implement validation and `BriefError`; make tests pass.
6. Write failing CLI test: run `main([project])` on a temp project with a valid brief; assert `work/music-palette.json` has one mood per segment, ids match `mood_id`, and `work/music-plan.json` segments reference `library:<id>`; assert `--print` writes no files. Expected error: `AttributeError: module has no attribute 'main'`.
7. Implement `main`; tests pass.
8. Add CLAUDE.md Architecture-table row for `tools/music_brief.py`; add the `docs/tool-routing.md` row ("music that follows the topic → `music_brief.py`, then `gen_music.py --recipes work/music-palette.json --only <ids>`").
9. Commit: "feat(GV-18): music brief builder, topic + arc aware prompts".

**Error paths covered:** missing file, bad JSON, each invalid field, overlap, non-numeric times. **Edge cases covered:** one segment, exactly 10 s, 120 s, 600 s, prompt at cap boundary, unicode in `sound_world`, duplicate segments (overlap error). **Observability:** `--print` table and every `BriefError` names the segment index and field. **Not applicable:** concurrency (single-process CLI).

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_music_brief.py' -q` passes, then `bash tests/run.sh` passes
- [ ] Two briefs differing only in topic/sound_world produce different prompts and ids (shown in test output)
- [ ] `tests/consistency/tools-index.sh` passes (tool named in CLAUDE.md)
- [ ] No placeholder/TODO comments in new code

### Phase B: Wire the brief into generation and the post skill

**Estimated time:** 15 minutes

**Files:**
- Modify: `reference/post-production/17-music-bed.md`, `skills/video-post/SKILL.md`, `tools/gen_music.py` (only if the test shows `--recipes` cannot take a project palette), `CLAUDE.md`
- Test: `tests/py/test_gen_music.py` (add cases), `tests/consistency/music-brief-contract.sh` (create)

**Steps:**
1. Write failing test in `tests/py/test_gen_music.py`: `plan_work(palette, library, only=["brief-abc"])` with a palette loaded from a project-local file containing mood `brief-abc` returns that mood, and `generate(..., dry_run=True, recipes=<project palette path>)` lists it without any network call. Expected error: `KeyError`/assertion failure only if current code rejects non-palette ids; if the test already passes, record "reuse confirmed, no gen_music change" in the ledger and skip the implementation step.
2. Run it; record the outcome.
3. Only if step 2 failed: make the smallest `gen_music.py` change so a `--recipes` palette outside the plugin works (reading `moods` list unchanged). Tests pass.
4. Write failing consistency test `tests/consistency/music-brief-contract.sh`: asserts `17-music-bed.md` and `skills/video-post/SKILL.md` both mention `music_brief.py` and `work/music-brief.json`, and that `17-music-bed.md` states the tone→mood table is now only the FALLBACK when no brief exists. Expected error: the script prints `FAIL` for a missing mention.
5. Edit `17-music-bed.md`: add "the brief route" section (topic + domain + tone + arc, per-segment, id is content-hashed so unchanged brief never re-bills; billed run needs the confirmation already required in this doc; always pass `--only <ids>` of the current brief). Keep the 5-mood table as fallback.
6. Edit `skills/video-post/SKILL.md` music pass: before generating, write `work/music-brief.json` from `strategic-brief.md` (topic, domain, tone, Domain Knowledge → `sound_world`) and `av-script.md` (scene timings and beat labels → segments with `beat`/`energy`), then `music_brief.py`, confirm the billed ids with the user, `gen_music.py --recipes work/music-palette.json --only <ids>`, then `mix_music.py`.
7. Make the consistency test pass; run `bash tests/run.sh`.
8. Commit: "feat(GV-18): music brief route in post skill and bed doc".

**Error paths:** brief absent → skill falls back to the tone table (documented, tested by the consistency grep). **Edge cases:** project palette id already in library (library-first skips, no re-bill; covered by existing `plan_work` behaviour). **Not applicable:** observability beyond existing `gen_music` logs.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_gen_music.py' -q` passes, then `bash tests/run.sh` passes
- [ ] `bash tests/consistency/music-brief-contract.sh` exits 0
- [ ] A dry run `python3 tools/gen_music.py --recipes <project>/work/music-palette.json --only <id> --dry-run` prints the mood and makes no request
- [ ] No placeholder/TODO comments in new code

### Phase C: Layered SFX (`stack`) in the cue sheet

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/mix_sfx.py`
- Test: `tests/py/test_mix_sfx.py` (add cases)

**Contract:** an event may carry `"stack": [{"sfx_id", "offset_s", "gain_db"}]` instead of `sfx_id`. `load_plan` expands it into one event per layer at `at_s + offset_s` (offset may be negative down to -0.5 so a riser can lead; resulting time must be ≥ 0), each inheriting `optional` and the parent's `note`; a layer's `gain_db` defaults to the parent's. An event may not have both `sfx_id` and `stack`. A stack counts as ONE cue for the density ceiling (`DENSITY_PER_MIN`) and one line in `format_sheet` (prints `stack(3): sub-boom+hit-heavy+tail-air`). An unknown `sfx_id` inside a stack raises `PlanError` naming the event and layer.

**Steps:**
1. Write failing test: a plan with one event `{"at_s": 5.0, "stack": [{"sfx_id":"a","offset_s":-0.2},{"sfx_id":"b","offset_s":0},{"sfx_id":"c","offset_s":0.1}]}` loads into 3 mix events at 4.8, 5.0, 5.1. Expected error: `PlanError: event 1: sfx_id None is not in the catalog` (current behaviour).
2. Run, confirm it fails for that reason.
3. Implement expansion in `load_plan`; keep the density count by parent events.
4. Write failing tests: both `sfx_id` and `stack` → `PlanError`; empty stack → `PlanError`; `offset_s` giving negative time → `PlanError`; unknown layer id → `PlanError` naming layer; `optional` inheritance; `--no-optional` drops the whole stack; sheet shows one `stack(N)` line. Expected error: assertion failures until implemented.
5. Implement; all tests pass; existing `test_mix_sfx.py` cases untouched and green.
6. Run `bash tests/run.sh`. Commit: "feat(GV-18): layered SFX stacks in the cue sheet".

**Error paths:** each `PlanError` above. **Edge cases:** single-layer stack, stack at `at_s = 0` with negative offset (error), duplicate layers (allowed), stack at the master's end (existing `at_s` > duration check applies to the parent AND each layer's final time). **Observability:** sheet line plus layer times printed under `--print`.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_mix_sfx.py' -q` passes, then `bash tests/run.sh` passes
- [ ] `python3 tools/mix_sfx.py <fixture> --print` shows a `stack(3)` line
- [ ] No placeholder/TODO comments in new code

### Phase D: New SFX recipes with punch

**Estimated time:** 10 minutes

**Files:**
- Modify: `media/sfx/library/palette.json`
- Test: `tests/py/test_gen_sfx.py` (add cases)

**Recipes to add (ids, categories, prompts; keep prompts generic, no client names):**
`sub-boom` (emphasis, 1.2 s, "deep sub bass boom, single, tight, clean decay"), `hit-heavy` (emphasis, 0.5 s, "heavy cinematic impact hit, short, dry"), `tail-air` (emphasis, 1.6 s, "airy reverb tail after an impact, fading"), `whoosh-fast` (motion, 0.5 s, "fast sharp whoosh, tight, no reverb tail"), `riser-long` (tension, 3.0 s, "rising tension riser, clean build, abrupt end"), `glitch-hit` (emphasis, 0.4 s, "digital glitch stutter hit, short"), `stinger-up` (emphasis, 1.0 s, "short bright positive stinger, uplifting"), `stinger-warn` (tension, 1.0 s, "short dark warning stinger, ominous").

**Steps:**
1. Write failing test: the plugin palette contains the eight new ids, ids are unique, every recipe has `id`, `prompt`, `duration_s`, `category` in {motion, tension, emphasis, ambience, ...existing categories}, and `0.2 <= duration_s <= 5`. Expected error: `AssertionError: missing recipe sub-boom`.
2. Run, confirm failure.
3. Add the eight recipes to `palette.json` (valid JSON, existing recipes untouched).
4. Tests pass. Run `bash tests/run.sh`.
5. DO NOT run a billed `gen_sfx.py` here. Billing happens in Phase F with the owner's confirmation.
6. Commit: "feat(GV-18): eight punchier SFX recipes".

**Error paths:** invalid JSON caught by the test's `json.load`. **Edge cases:** duplicate id, duration bounds. **Not applicable:** observability, concurrency (data file only).

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_gen_sfx.py' -q` passes, then `bash tests/run.sh` passes
- [ ] `python3 tools/gen_sfx.py --dry-run --only sub-boom,hit-heavy` lists the recipes and makes no request
- [ ] No placeholder/TODO comments in new code

### Phase E: Beat detection and cue snapping

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/beats.py`, `tools/sfx_snap.py`
- Modify: `tools/vidkit/__main__.py` (add `beats` subcommand), `tools/vidkit/__init__.py` (import `beats`)
- Test: `tests/py/test_vidkit.py` (add cases), `tests/py/test_sfx_snap.py` (create)

**Contract:**
- `beats.detect(path, hop_s=0.01, min_gap_s=0.25, threshold=1.5) -> list[float]`: decode to mono 16-bit PCM at 16 kHz via ffmpeg to stdout, compute short-time energy per `hop_s` window, onset = positive energy difference, keep local maxima above `threshold × median positive onset` separated by ≥ `min_gap_s`; return times in seconds. Pure stdlib (`array`). Returns `[]` for silence; never raises on a decodable file; raises `BeatError` if ffmpeg is missing or cannot decode.
- `beats.snap(times, beats, window_s=0.12) -> list[float]`: each time moves to the nearest beat if within `window_s`, else unchanged.
- `tools/sfx_snap.py <project> --music <file> [--plan work/sfx-plan.json] [--window 0.12] [--out work/sfx-plan.snapped.json]`: reads the plan, snaps `at_s` of non-stack events and of each stack's parent `at_s`, writes the NEW file (never mutates the original), prints a table of moved cues (id, from, to, delta) and the count unchanged. Exits 2 when the music has no detectable beats (message says so; no file written).
- CLI `python3 -m tools.vidkit beats <file>` prints the beat times as JSON.

**Steps:**
1. Write failing test: synthesise a 6 s mono wav with a short click at 0.5, 1.5, 2.5, 3.5, 4.5 s over low noise (use the stdlib `wave`/`struct` pattern from `tests/py/test_mix_music.py`); `beats.detect` returns 5 times each within ±0.03 s of the clicks. Expected error: `ImportError: cannot import name 'beats' from 'tools.vidkit'`.
2. Run, confirm failure.
3. Implement `detect` and `snap`.
4. Write failing tests: silence → `[]`; `snap` moves 1.54 → 1.5 with window 0.12 but leaves 1.9 alone; a missing file → `BeatError`; clicks closer than `min_gap_s` collapse to one.
5. Implement; pass.
6. Write failing `test_sfx_snap.py`: plan with cues at 1.55 and 3.0 plus the click track from step 1 → output file has 1.5 and 3.0, original unchanged byte-for-byte, table lists one moved cue; silent music → exit 2 and no output file; stack parent snapped.
7. Implement `sfx_snap.py`; pass. Register `beats` in `__main__.py` and `__init__.py`.
8. Add CLAUDE.md rows (`tools/sfx_snap.py`; vidkit line mentions `beats`), `docs/tool-routing.md` rows, `docs/vidkit.md` section.
9. Run `bash tests/run.sh`. Commit: "feat(GV-18): beat detection and SFX cue snapping".

**Error paths:** ffmpeg missing, undecodable file, silent music, empty plan. **Edge cases:** one beat only, cue before first beat, cue after last, window 0 (no moves), stereo/44.1 kHz input (decode normalises). **Observability:** moved-cue table; count of beats found printed.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -q` passes (vidkit + sfx_snap), then `bash tests/run.sh` passes
- [ ] `python3 -m tools.vidkit beats <real music mp3 from the library>` prints plausible times (record the count and first five in the ledger)
- [ ] `tests/consistency/tools-index.sh` passes
- [ ] No placeholder/TODO comments in new code

### Phase F: Docs, skill steps, and the owner's listening gate for music + SFX

**Estimated time:** 15 minutes

**Files:**
- Modify: `reference/post-production/14-sfx-design.md`, `skills/video-post/SKILL.md`, `docs/evals/` (new evidence file)
- Create: `tests/consistency/sfx-stack-contract.sh`, `docs/evals/music-sfx-listening-run.md`

**Steps:**
1. Write failing consistency test `tests/consistency/sfx-stack-contract.sh`: `14-sfx-design.md` documents `stack`, the eight new recipe ids, `sfx_snap.py`, and states that a stack counts as one cue for density; `skills/video-post/SKILL.md` SFX pass names `sfx_snap.py` as the step after the cue sheet is audited and before mixing. Expected error: script prints `FAIL ... not documented`.
2. Edit `14-sfx-design.md`: add the "punch" section (layered impact recipe: `riser-long` leading −0.3 s, `sub-boom` at 0, `hit-heavy` at 0, `tail-air` +0.1 s; gain guidance unchanged: layers share the parent's gain so the audibility gate still decides; do not raise gain to fake punch), the beat-snap step, and that the audit gate still applies to the cue sheet.
3. Edit `skills/video-post/SKILL.md` SFX pass accordingly (order: cue sheet → owner audit → `sfx_snap.py` against the final music file → `mix_sfx.py`).
4. Make the consistency test pass.
5. **Owner listening gate (billed, requires confirmation):** ask the owner to confirm the cost, then (a) `gen_sfx.py --only sub-boom,hit-heavy,tail-air,riser-long,whoosh-fast,glitch-hit,stinger-up,stinger-warn`; (b) pick two real finished projects with different topics, write a `music-brief.json` for each, generate ONE short segment per project, and mix one SFX stack. Record in `docs/evals/music-sfx-listening-run.md`: project descriptors (no client names), brief fields, ids, durations, the commands, measured loudness (`vidkit probe`/`loudness.measure`), and the owner's verdict per item (PASS / NOT YET with reason). If the owner says NOT YET, STOP and adjust prompt tables in `tools/music_brief.py` (new failing test first), regenerate only the changed ids.
6. Commit: "docs(GV-18): punch + beat-snap docs and listening evidence".

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] `bash tests/consistency/sfx-stack-contract.sh` exits 0
- [ ] `docs/evals/music-sfx-listening-run.md` exists with the owner's verdict recorded (not assumed)
- [ ] Billed generations were confirmed by the owner beforehand (note the confirmation in the ledger Keputusan)
- [ ] No placeholder/TODO comments in new code

### Phase G: BT.709 colour tagging at the final encode

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/color.py`
- Modify: `tools/edit_render.py` (both `libx264` encode sites), `tools/vidkit/mixdown.py` (final mux), `tools/vidkit/__init__.py`
- Test: `tests/py/test_vidkit.py` (add), `tests/py/test_edit_render.py` (add)

**Contract:**
- `color.probe_color(path) -> dict` with `color_space`, `color_primaries`, `color_transfer`, `color_range` from ffprobe (`unknown` when missing).
- `color.convert_filter(probe) -> str`: returns `""` when the source is already bt709 OR untagged (assume bt709 for HD, matching players); returns `colorspace=all=bt709:iall=<mapped>` when the source is explicitly bt601 (`smpte170m`/`bt470bg`) or another known matrix; never converts silently on an unknown value (returns `""` and the caller logs a warning).
- `color.ENCODE_FLAGS = ["-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv"]`; use `-vf` `setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv` so the tag is written to the stream.
- Applied at: `edit_render` per-segment encodes and group merges, `mixdown` final mux. Not applied to intermediate stream-copy steps.

**Steps:**
1. Write failing test: encode a 1 s synthetic `testsrc` clip through the new helper with `ENCODE_FLAGS` and assert `probe_color` reports `bt709` for space, primaries and transfer. Expected error: `ImportError: cannot import name 'color' from 'tools.vidkit'`.
2. Run, confirm failure.
3. Implement `color.py`; test passes.
4. Write failing tests: explicit bt601 source → `convert_filter` returns a `colorspace=` filter; untagged → `""`; unknown value → `""` plus a recorded warning; probe on a file with no video stream → raises a clear error (not a KeyError).
5. Implement; pass.
6. Write failing test in `test_edit_render.py`: `build_commands(plan)` output commands contain the colour flags (and the setparams filter) for each libx264 encode. Expected error: assertion that `-colorspace` is in the command.
7. Wire into `edit_render.py`; write failing test that `mixdown`'s mux command contains the flags; wire into `mixdown.py`; tests pass.
8. Render a tiny real plan end to end (fixture in `tests/fixtures/` if one exists; else the synthetic clip) and `ffprobe` the result: bt709 present, `check_av_gate` still passes.
9. Add rows to `docs/tool-routing.md`, `docs/vidkit.md`. Run `bash tests/run.sh`. Commit: "feat(GV-18): BT.709 tags on final encodes".

**Error paths:** no video stream; ffprobe missing; unknown matrix. **Edge cases:** untagged, bt709 already, bt601, HDR transfer (`smpte2084` → leave unconverted, warn: out of scope), odd dimensions. **Observability:** warning lines name the file and the unknown value.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -q` passes, then `bash tests/run.sh` passes
- [ ] `ffprobe` of a freshly rendered output shows `color_space=bt709`, `color_primaries=bt709`, `color_transfer=bt709`
- [ ] A/V gate still passes on the rendered output
- [ ] No placeholder/TODO comments in new code

### Phase H: Cross-clip colour match

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/colormatch.py`
- Modify: `tools/vidkit/__main__.py`, `tools/vidkit/__init__.py`, `skills/video-post/SKILL.md`
- Test: `tests/py/test_vidkit.py` (add)

**Contract:**
- `colormatch.mean_rgb(path, samples=5) -> (r, g, b)` floats 0–255: for `samples` evenly spaced timestamps extract one frame each scaled to 1×1 `rgb24` via ffmpeg to stdout, average.
- `colormatch.plan(paths, reference=None, max_gain=0.15) -> list[{"file", "mean", "gain": (gr,gg,gb), "delta"}]`: reference is the `reference` path or, when None, the per-channel MEDIAN of all clips. `gain = ref/clip` per channel clamped to `[1-max_gain, 1+max_gain]`. `delta` = max channel gain deviation from 1.0.
- `colormatch.apply(path, out, gain)`: ffmpeg `colorchannelmixer=rr=<gr>:gg=<gg>:bb=<gb>`, with BT.709 flags from `color.ENCODE_FLAGS` if Phase G is merged; stream-copy audio.
- CLI `python3 -m tools.vidkit colormatch <clips...> [--reference F] [--max-gain 0.15] [--apply OUTDIR] [--min-delta 0.03]`: prints a table and a one-line spread summary; without `--apply` it is report-only; with `--apply` it only rewrites clips whose `delta ≥ --min-delta` (others copied untouched) into OUTDIR; never overwrites sources.

**Steps:**
1. Write failing test: three synthetic 1 s `color=c=` clips (neutral grey, slightly warm, slightly cool); `mean_rgb` of each is within ±2 of the generated colour. Expected error: `ImportError: cannot import name 'colormatch'`.
2. Run, confirm failure.
3. Implement `mean_rgb`.
4. Write failing tests: `plan` with three clips gives gains moving warm and cool toward the median; gains clamp at ±0.15 for an extreme red clip; with a given `reference` that clip's gain is (1,1,1); one clip alone → gain (1,1,1), no error; zero-length/undecodable clip → clear `ColorMatchError` naming the file.
5. Implement `plan` and `apply`; write failing test that after `apply` the max channel spread between the three clips shrinks by at least 50%; pass.
6. Write failing CLI test: report-only run writes nothing; `--apply` writes only clips over `--min-delta`; sources unchanged (sha256 equal). Implement; pass.
7. Edit `skills/video-post/SKILL.md`: run `vidkit colormatch` report on the kelompok's clips before assembly; apply only after the owner looks at the contact sheet of adjacent clips; record the decision in the ledger.
8. Docs rows; `bash tests/run.sh`. Commit: "feat(GV-18): cross-clip colour match".

**Error paths:** undecodable clip, missing reference, ffmpeg missing. **Edge cases:** single clip, identical clips (no-op), black clip (mean ~0 → gain clamp, flagged `suspect: near-black` in the table, not corrected), mixed resolutions. **Observability:** the table and spread summary. **Not applicable:** concurrency.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -q` passes, then `bash tests/run.sh` passes
- [ ] Spread reduction ≥50% on the synthetic trio (printed by the test)
- [ ] Run once on two real adjacent clips from a finished project; record before/after spread in the ledger and have the owner confirm by eye (contact sheet via `vidkit sheet`)
- [ ] No placeholder/TODO comments in new code

### Phase I: Stills-first verdict gate and page

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/verdict_page.py`
- Modify: `skills/video-gen/SKILL.md`, `CLAUDE.md`
- Test: `tests/py/test_verdict_page.py`

**Contract:**
- `tools/verdict_page.py page <project> [--keyframes keyframes] [--out output/verdict.html] [--max-mb 16]`: builds ONE self-contained HTML: one card per `keyframes/scene-*.png` (sorted; letter suffixes ok), image inlined as downscaled JPEG data URI (long side ≤ 900 px; if total >`--max-mb`, downscale further in steps and say so), scene id, PASS / MAYBE / NO buttons (keyboard 1/2/3), a note field, and a "Download verdict.json" button. No network, no external assets. Dark/light safe. Escapes all text.
- `verdict.json` shape: `{"scenes": {"<id>": {"verdict": "PASS|MAYBE|NO", "note": str}}}`.
- `tools/verdict_page.py check <project> [--allow-maybe]`: reads `work/verdict.json`; exit 0 only when every keyframe has `PASS` (or `MAYBE` with `--allow-maybe`); exit 1 listing each missing / `NO` / `MAYBE` scene; exit 2 when the file is missing or malformed.
- Image downscale uses Pillow only if available, else ffmpeg `scale` (ffmpeg is the guaranteed dependency; do NOT require the venv). Never `sips --out` onto a folder path.

**Steps:**
1. Write failing test: build a temp project with three tiny PNG keyframes (generate with ffmpeg `color` source) and run `page`; output file exists, contains three scene ids, contains `data:image/jpeg;base64,`, contains no `http://` or `https://` substring, and its size ≤ 16 MB. Expected error: `ModuleNotFoundError: No module named 'tools.verdict_page'`.
2. Run, confirm failure.
3. Implement `page`.
4. Write failing tests for `check`: all PASS → 0; one NO → 1 naming it; missing scene → 1; MAYBE → 1 unless `--allow-maybe`; absent file → 2; malformed JSON → 2; verdict value outside the three → 2.
5. Implement `check`; pass. Add a test that scene ids and notes with `<script>` are escaped in the page.
6. Edit `skills/video-gen/SKILL.md`: before the render offer for clips, run `verdict_page.py page`, owner reviews in browser and saves `verdict.json` into `work/`, then `verdict_page.py check` must exit 0 before any clip render is offered; skipping requires an explicit owner statement recorded in the ledger.
7. CLAUDE.md row; routing row; `bash tests/run.sh`. Commit: "feat(GV-18): stills-first verdict gate".

**Error paths:** no keyframes, unreadable image, oversize, malformed verdict. **Edge cases:** one scene, 60 scenes (size cap), letter-suffixed ids (`02a`), non-ASCII notes. **Observability:** the page prints its final size and downscale level to stdout. **Not applicable:** concurrency.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_verdict_page.py' -q` passes, then `bash tests/run.sh` passes
- [ ] Open the generated page in a real browser (Playwright MCP or the owner's browser): buttons set verdicts, download works, produced `verdict.json` passes `check` (record in ledger)
- [ ] No placeholder/TODO comments in new code

### Phase J: Cost log and pre-flight estimate

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/cost_log.py`, `media/pricing.json` (schema + empty price slots only)
- Modify: `skills/video-full/SKILL.md`, `skills/video-gen/SKILL.md`, `skills/video-image/SKILL.md`, `CLAUDE.md`
- Test: `tests/py/test_cost_log.py`

**Contract:**
- `media/pricing.json`: `{"_comment": "owner fills real prices; the tool refuses to guess", "currency": "", "items": {"nb2-image": {"unit": "image", "price": null, "source": ""}, "veo-3.1-fast-clip": {"unit": "second", "price": null, "source": ""}, "eleven-tts": {"unit": "1k-chars", "price": null, "source": ""}, "eleven-music": {"unit": "second", "price": null, "source": ""}, "eleven-sfx": {"unit": "clip", "price": null, "source": ""}}}`. An item with `price: null` or empty `source` is UNPRICED.
- `work/cost-log.json`: `{"budget": number|null, "entries": [{"ts", "kind", "scene"?, "units", "status": "ok|failed", "note"?}]}`. Entries store units, NOT money; money is computed at report time from the current pricing file, so a corrected price fixes history.
- CLI: `cost_log.py <project> add --kind K --units N [--scene S] [--status ok|failed] [--note T]`, `report` (totals per kind, failed-attempt share, total vs budget; lists UNPRICED kinds and prints their units instead of money), `estimate --plan <json>` where plan is `{"nb2-image": 18, "veo-3.1-fast-clip": 140, ...}` units → refuses (exit 2, names every unpriced item) rather than estimating with a missing price; `--budget N` sets the budget; `check` exits 1 when the priced total exceeds the budget.
- Integration points in skills: after each billed render offer, record units (`add`); before `/video-full` starts billed work, run `estimate` and show it to the owner.

**Steps:**
1. Write failing test: `add` twice then `report` on a temp project with priced items prints correct totals (units × price) and the failed share. Expected error: `ModuleNotFoundError: No module named 'tools.cost_log'`.
2. Run, confirm failure.
3. Implement entries + report.
4. Write failing tests: unpriced kind → report prints units and an `UNPRICED` line, no invented money; `estimate` with an unpriced item → exit 2 naming it; `check` over budget → exit 1; no budget set → `check` exits 0 and says "no budget"; negative or non-numeric units → rejected (exit 2); malformed `cost-log.json` → exit 2 (never overwritten); concurrent `add` safety → write via temp file + `os.replace`.
5. Implement; pass.
6. Edit the three skills to call `add` after billed renders and `estimate` before the pipeline's billed phases.
7. Docs rows, CLAUDE.md row; `bash tests/run.sh`. Commit: "feat(GV-18): cost log and pre-flight estimate".
8. STOP and ask the owner to fill `media/pricing.json` with real prices and sources (do not invent them); until filled the estimate refuses by design. Record in the ledger Utang terbuka if the owner defers.

**Error paths:** each refusal above. **Edge cases:** zero units, fractional units, huge counts, same scene logged many times (re-rolls), budget equal to total. **Observability:** report is the observability.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_cost_log.py' -q` passes, then `bash tests/run.sh` passes
- [ ] `cost_log.py estimate` with the shipped (empty) pricing exits 2 and names all unpriced items
- [ ] No price number appears anywhere in the repo that the owner did not supply (grep `media/pricing.json` for non-null prices at the end of the phase)
- [ ] No placeholder/TODO comments in new code

### Phase K: Thumbnail style-element menu and render-verify check

**Estimated time:** 15 minutes

**Files:**
- Create: `reference/post-production/20-thumbnail-style-elements.md`, `tools/thumb_verify.py`, `tests/consistency/thumbnail-style-contract.sh`
- Modify: `skills/video-package/SKILL.md`, `NOTICE`, `CLAUDE.md`
- Test: `tests/py/test_thumb_verify.py`

**Contract:**
- The reference doc is written in this plugin's own words after reading the source file named in the Data Integration Map: copy-paste prompt blocks with `<slots>` (environment, hook text, sticker, badge), base axes (high contrast, clear hierarchy, one dominant element), and a failure table for garbled text (symptom → fix). It must keep the plugin's honesty guardrail (frame promise inside what the video delivers). Cite no result numbers as fact unless they are quoted with their source and marked "one channel's before/after, not a rule".
- `tools/thumb_verify.py init <project>` writes `packaging/thumb-verify.md` with one section per `packaging/thumb-*.png` and a fixed verdict table (rows: `text spelled correctly`, `text legible at phone size`, `face recognisable (if cast shown)`, `one dominant element`, `matches the video's promise`). `check <project>` reads ONLY the verdict cells: exit 1 on a missing, empty, malformed or `FAIL:` cell, or when the image's sha256 changed after it was judged (pattern: `tools/qa_frames.py --check`); `UNSURE:` is a note, not a failure.

**Steps:**
1. Write failing consistency test `tests/consistency/thumbnail-style-contract.sh`: the doc exists, has at least four `<slot>` blocks, has a failure table, mentions the honesty guardrail; `video-package/SKILL.md` links the doc and requires `thumb_verify.py check` to exit 0 before a thumbnail is offered as final; `NOTICE` has an entry for the style-element source. Expected error: `FAIL doc missing`.
2. Read the source file; write the doc in own words; edit the skill and NOTICE (adapted: structure of a slot-based prompt menu and the failure table idea; nothing vendored).
3. Make the consistency test pass.
4. Write failing test for `thumb_verify.py`: `init` on a temp project with two PNGs writes two sections; `check` exits 1 on empty cells; 0 when all cells hold `PASS` text; 1 with any `FAIL:`; 1 after the PNG bytes change; 2 when `thumb-verify.md` is missing. Expected error: `ModuleNotFoundError: No module named 'tools.thumb_verify'`.
5. Implement; pass.
6. `bash tests/run.sh`. Commit: "feat(GV-18): thumbnail style menu and verify check".

**Error paths:** missing sections, edited cells, changed images. **Edge cases:** zero thumbnails (init prints nothing to do, exit 0), letters in names, re-run of `init` preserving existing verdicts for unchanged images. **Observability:** `check` lists each failing cell by thumbnail and row.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -p 'test_thumb_verify.py' -q` passes, then `bash tests/run.sh` passes
- [ ] `bash tests/consistency/thumbnail-style-contract.sh` exits 0
- [ ] The reference doc contains no passage copied from the source (spot-check three sentences against the source file; record the check in the ledger)
- [ ] No placeholder/TODO comments in new code

### Phase L: Per-stage fingerprint cache in the edit render

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/stages.py`
- Modify: `tools/edit_render.py` (`render`, `build_commands`), `tools/vidkit/__init__.py`
- Test: `tests/py/test_vidkit.py` (add), `tests/py/test_edit_render.py` (add)

**Contract:**
- `stages.fingerprint(files=(), params=None, version="1") -> str`: sha256 over, in order, each file's content sha256 (streamed in 1 MiB chunks; a missing file raises `StageError` naming it), canonical `json.dumps(params, sort_keys=True, separators=(",",":"))`, and `version`. Same inputs → same string; any change → different.
- `stages.StageCache(path)`: `is_fresh(stage, fp, outputs) -> bool` (true only when recorded fp equals AND every output file exists), `record(stage, fp, outputs)` writing atomically (temp + `os.replace`), tolerant of a corrupt or absent cache file (treated as empty, never crashes, corrupt file replaced on next record).
- In `edit_render.render`: each segment part is skipped when `is_fresh("seg-<i>", fp, [part])`, where `fp` covers the source file content, the segment's plan fields (`in_s,out_s,pad_*,motion,transition_in`), the encode flags (including Phase G colour flags) and `RENDERER_VERSION = "1"` (bump when the encode recipe changes). Parts must be kept between runs for this to work: add a `--cache` flag (default on) storing parts under `<project>/.tmp/edit-parts/`; `--no-cache` forces a full render; `--keep` behaviour unchanged. The concat and the A/V gate ALWAYS run. Print `skipped N of M segments (cached)`.

**Steps:**
1. Write failing test: `fingerprint` is stable for equal inputs, differs when a file's bytes change, when a param changes, and when version changes; missing file → `StageError`. Expected error: `ImportError: cannot import name 'stages'`.
2. Run, confirm failure.
3. Implement `fingerprint` and `StageCache`.
4. Write failing tests: cache file corrupt → treated empty; `is_fresh` false when the output file was deleted; atomic write leaves no partial file when interrupted (simulate by mocking `os.replace` to raise and asserting the old cache survives).
5. Implement; pass.
6. Write failing test in `test_edit_render.py`: render a two-segment plan twice with real ffmpeg on synthetic clips; second run prints `skipped 2 of 2`, produces a byte-identical master, and takes the A/V gate path; change ONE segment's `out_s` → only that segment re-encodes (assert via the printed command count); `--no-cache` re-encodes all. Expected error: `AssertionError` (no skip logic yet).
7. Wire into `edit_render.py`; pass. Confirm `test_edit_render.py` existing cases unchanged and green.
8. Docs rows (`tool-routing.md`, `vidkit.md`). `bash tests/run.sh`. Commit: "feat(GV-18): per-stage fingerprint cache for edit render".

**Error paths:** missing source, corrupt cache, cache dir unwritable (fall back to full render with a warning). **Edge cases:** zero segments, identical segments (distinct stage names), source replaced with the same bytes (still fresh), cache from an older `RENDERER_VERSION` (stale). **Observability:** skipped/total line plus per-segment `cached`/`rendered` in `--print`.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -q` passes, then `bash tests/run.sh` passes
- [ ] Changing only one segment re-encodes only that one (test output shows the count)
- [ ] Master after a cached run is byte-identical to a full render of the same plan (test asserts sha256 equality)
- [ ] No placeholder/TODO comments in new code

### Phase M: Encoder probe with fallback, and a heartbeat for silent stages

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/encoder.py`
- Modify: `tools/vidkit/ff.py` (heartbeat), `tools/edit_render.py` (encoder selection for final-path encodes)
- Test: `tests/py/test_vidkit.py` (add), `tests/py/test_edit_render.py` (add)

**Contract:**
- Env `GASPOL_VIDEO_ENCODER` = `libx264` (default) | `auto` | `h264_videotoolbox`. `libx264` default keeps today's quality-stable behaviour; hardware encoders are opt-in because their quality per bitrate differs.
- `encoder.available(ffmpeg_encoders_text) -> set[str]` parses `ffmpeg -hide_banner -encoders` output.
- `encoder.choose(env_value, available) -> str`: `auto` picks `h264_videotoolbox` when available else `libx264`; an unavailable explicit choice falls back to `libx264` with a returned warning string; unknown value → `EncoderError`.
- `encoder.video_args(name, crf=20) -> list[str]`: `libx264` → `-c:v libx264 -preset veryfast -crf <crf> -pix_fmt yuv420p`; `h264_videotoolbox` → `-c:v h264_videotoolbox -b:v <bitrate by resolution: read from a constant table (1080p: 12M, 720p: 6M)> -pix_fmt yuv420p`.
- Fallback on failure: `encoder.run_with_fallback(cmd_builder, chosen, run)` retries once with `libx264` when a hardware encode exits non-zero, logging `encoder X failed, retried with libx264`.
- `ff.run(cmd, capture_stderr=False, heartbeat_s=None)`: when `heartbeat_s` is set, run via `Popen` and print `still running: <label> <elapsed>s` every `heartbeat_s` seconds until exit; default behaviour unchanged. Edit render passes `heartbeat_s=30` for per-segment and merge encodes.

**Steps:**
1. Write failing test: `encoder.choose("auto", {"libx264","h264_videotoolbox"})` → `h264_videotoolbox`; `choose("auto", {"libx264"})` → `libx264`; explicit unavailable → `libx264` with warning; `"bogus"` → `EncoderError`. Expected error: `ImportError: cannot import name 'encoder'`.
2. Run, confirm failure.
3. Implement `available`, `choose`, `video_args`.
4. Write failing test for `run_with_fallback`: stub runner fails on the first (hardware) call and succeeds on libx264; assert exactly two calls and the log line; when libx264 also fails → raises the original error with both stderr tails.
5. Implement; pass.
6. Write failing test for heartbeat: run `sleep`-like child (`python3 -c "import time; time.sleep(1.2)"`) with `heartbeat_s=0.5` and capture stdout; at least two heartbeat lines; exit code propagated; child failure propagates stderr tail. Expected error: `TypeError: run() got an unexpected keyword argument 'heartbeat_s'`.
7. Implement in `ff.py`; pass. Wire `encoder` into `edit_render.py` encode sites (default path must produce the same command as before — assert with an existing-command snapshot test); pass.
8. On this Mac run a real render with `GASPOL_VIDEO_ENCODER=auto`; record in the ledger whether videotoolbox was used, wall time vs libx264 for the same plan, and the A/V gate result. If quality or time shows no benefit, leave the default untouched and record that (no further work).
9. Docs rows. `bash tests/run.sh`. Commit: "feat(GV-18): encoder probe with fallback and ffmpeg heartbeat".

**Error paths:** ffmpeg missing, hardware encoder present but failing, unknown env value. **Edge cases:** no ffmpeg `-encoders` output, heartbeat longer than the process (no lines), process killed. **Observability:** heartbeat and fallback log lines.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -q` passes, then `bash tests/run.sh` passes
- [ ] Default (`GASPOL_VIDEO_ENCODER` unset) produces the same ffmpeg command as before this phase (snapshot test)
- [ ] Real timing comparison recorded in the ledger
- [ ] No placeholder/TODO comments in new code

### Phase N: Sourced loudness profiles

**Estimated time:** 10 minutes

**Files:**
- Create: `media/loudness-profiles.json`
- Modify: `tools/vidkit/loudness.py`, `tools/vidkit/__main__.py` (`normalize --profile`), `tools/vidkit/mixdown.py` (profile key in plan)
- Test: `tests/py/test_vidkit.py` (add)

**Contract:**
- `media/loudness-profiles.json`: `{"profiles": {"default": {"lufs": -14, "true_peak": -1.0, "source": "plugin default since v3.12.0, YouTube normalisation reference"}}}`. Any other profile (e.g. `short-vertical`) may be added ONLY with a non-empty `source` URL or document title; `loudness.profile(name)` raises `ProfileError` for a profile without `source`, an unknown name, or a `lufs` outside `[-24, -6]`.
- `vidkit normalize --profile NAME` and mixdown plan key `"loudness_profile"` select it; absent → `default` (today's -14 behaviour, no change).
- The Samuel Christ measurement (12 Shorts, -24.1 to -7.8 LUFS, median -11.8; 11 of 12 between -13.6 and -7.8) is recorded as EVIDENCE in `docs/evals/short-form-loudness-measurement.md` (descriptors only, no client assets), clearly labelled "one channel, not a platform rule". It does NOT create a profile by itself.

**Steps:**
1. Write failing test: `loudness.profile("default")` returns `-14.0` and `-1.0`; `profile("nope")` raises `ProfileError`; a temp profile file with a profile lacking `source` raises `ProfileError`; `lufs` of -3 raises. Expected error: `AttributeError: module 'tools.vidkit.loudness' has no attribute 'profile'`.
2. Run, confirm failure.
3. Implement `profile`, load path from an env/arg override for tests, ship the JSON with only `default`.
4. Write failing test: `normalize --profile default` output equals the previous default result (loudness within ±0.5 LU of -14 on a synthetic tone); unknown profile exits 2. Implement; pass.
5. Write the evidence file from the ledger's recorded measurements; no profile added.
6. Ask the owner whether to add a `short-vertical` profile and which sourced number to use; if they supply a source, add it with a test, else record in Utang terbuka. Do NOT adopt the expert's unsourced "-11 to -13 LUFS" claim.
7. Docs rows. `bash tests/run.sh`. Commit: "feat(GV-18): sourced loudness profiles".

**Error paths:** each `ProfileError`. **Edge cases:** profile file missing (use built-in default with a warning), duplicate profile names (JSON last-wins is forbidden: loader rejects duplicates). **Observability:** `normalize` prints the profile name and targets used.

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `python3 -m unittest discover -s tests/py -t . -q` passes, then `bash tests/run.sh` passes
- [ ] Default output loudness unchanged (test asserts ±0.5 LU of -14)
- [ ] `grep -n "lufs" media/loudness-profiles.json` shows only entries with a `source`
- [ ] No placeholder/TODO comments in new code

### Phase O: Wrap, version, evidence, review

**Estimated time:** 15 minutes

**Files:**
- Modify: `CLAUDE.md` (Architecture rows for every new tool, tool counts, changelog `v3.15.0`, Last updated, version), `README.md` (version line + changelog), `NOTICE` (MoneyPrinterTurbo: BT.709 tagging, encoder probe with fallback, per-stage fingerprint idea, heartbeat; claude-youtube-editor: stills-first verdict page idea, thumbnail style-element/failure-table idea, cost log idea; note beat detection and colour match as original), `.claude-plugin/plugin.json` (version `3.15.0`), `docs/tool-routing.md`, `docs/vidkit.md`, `tests/consistency/plugin-identity.sh` and `tests/consistency/tools-index.sh` (version gates track the release), `../gaspol-one/.claude-plugin/marketplace.json` (gaspol-video version `3.15.0`, and the README version table in `../gaspol-one/README.md`)
- Test: whole suite

**Steps:**
1. Write failing test: run `bash tests/run.sh`; the version gates in `tests/consistency/plugin-identity.sh` / `tools-index.sh` are updated to demand `3.15.0` FIRST. Expected error: `FAIL plugin.json version 3.14.0 != 3.15.0`.
2. Bump versions and docs; make the gates pass.
3. Confirm every new tool under `tools/` is named in CLAUDE.md (`tools-index.sh`) and every new routing row exists in `docs/tool-routing.md`.
4. Update the marketplace entry and `../gaspol-one/README.md` version table in the marketplace repo (separate repo: commit there separately, do NOT push without the owner's go-ahead).
5. Run the full suite twice (second run proves no stale cache effects): `bash tests/run.sh`.
6. Run `graphify update .` (AST-only) as CLAUDE.md requires after code changes.
7. Dispatch the review agents ONCE for the whole branch (token rule): `typescript-reviewer` is not needed (no TS changed); use `silent-failure-hunter` (opus/high) on the new Python tools, and `security-reviewer` (opus/high) on `verdict_page.py` (HTML generation, escaping) and any subprocess calls. Fix findings with a failing test first.
8. Run `gaspol-dev:plan-verifier` for the spec-and-plan audit; zero MISSING items required.
9. Commit: "chore(GV-18): v3.15.0 docs, notice, version gates". Hand over to `gaspol-finish` (merge `--no-ff`, `git worktree remove`, `git worktree prune`; spec and plan arrive in main through the merge, never copied beforehand).

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] unit: `bash tests/run.sh` passes (all three groups)
- [ ] `grep -rn "3.14.0" .claude-plugin/plugin.json CLAUDE.md README.md` shows no stale current-version line
- [ ] Marketplace entry and README table versions match `plugin.json`
- [ ] `silent-failure-hunter` and `security-reviewer` findings resolved or recorded as Utang terbuka with reasons
- [ ] plan-verifier verdict recorded in the ledger with zero MISSING
- [ ] No placeholder/TODO comments in new code

---

## Open items carried from the spec (resolve inside the named phase, not by guessing)

1. ElevenLabs Music length bounds and prompt length cap → Phase A (verify against the API docs; adjust constants and note it in Keputusan).
2. Per-platform loudness numbers → Phase N (only with a source; the expert's unsourced figure is not adopted).
3. Real prices for the cost log → Phase J (owner supplies).
4. Whether videotoolbox helps on the owner's machine → Phase M step 8 (measure, then decide).
