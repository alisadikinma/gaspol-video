> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-25.md` (in the MAIN checkout, `/Users/alisadikin/Drive-D/claude-plugin/gaspol-video/.gaspol/progress/PROGRESS-GV-25.md`, gitignored; created by `gaspol-plan` at plan-write time). After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. This is **blocking**, like a test gate: no next phase until both are written. **Never batch all updates at the end** — a crash mid-run must leave a truthful state, not a stale one. Update ONLY this file — never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. It must be executable by an agent with **no other context**. Every file path, contract, config key, and convention it needs is written here **verbatim**.

**Ticket:** GV-25
**Ledger:** .gaspol/progress/PROGRESS-GV-25.md
**Spec:** docs/plans/2026-10-17-GV-25-tool-dedup-spec.md

## Goal

Remove four overlaps in the gaspol-video tool set found after v3.21.0 (GV-24): (1) skills still route
a panel on a phone/monitor through the old Remotion `QuadScreenTracked` + `track_screen.py` pipeline,
whose failures caused GV-24, instead of `vidkit screen-insert`; (2) `tools/vidkit/track.py`
(`vidkit smooth-track`) only smooths the old box tracks and no skill calls it; (3) the
`cast_voice.mjs` header is stale and the `seed` form field only exists there; (4) `qa_frames.py`
re-implements frame tiling that `vidkit.sheet` owns. Release as patch **3.21.1**. One pipeline per
job means the next agent cannot pick the broken one.

## Architecture Context

Work happens in the worktree `/Users/alisadikin/Drive-D/claude-plugin/gaspol-video/.claude/worktrees/gv-25-tool-dedup`
on branch `GV-25-tool-dedup` (base `e0da0a4`). Run every command from that directory.

Conventions from `CLAUDE.md` (repo root) that apply:
- **Tool registry (GV-20).** `tools/registry.json` holds every tool (`tools[]`: `id`, `purpose`,
  `tasks`, `phase`, `replaces`, `distinct_because`, `internal_reason`) and every route (`routes[]`:
  `task`, `use`, `tools`). `docs/tool-routing.md` table is GENERATED: run
  `python3 tools/registry_build.py render`, never edit the table by hand. Gates:
  `python3 tools/registry_build.py validate --coverage` (every `tools/*.py`, `tools/*.mjs`,
  `tools/vidkit/*.py`, `tools/vidkit/js/*.mjs` must be registered) and
  `python3 tools/registry_build.py render --check`. A route cell may contain `|` only as `\|`.
- `tests/py/test_registry.py:458` asserts `len(reg["routes"]) == 78`. This plan keeps 78 routes
  (the screen route stays; only its `use` text and `tools` list change).
- **ffprobe ownership.** Only `tools/vidkit/ff.py` and `tools/vidkit/js/ff.mjs` call ffprobe
  (ratchet in `tests/consistency/tool-registry-contract.sh`). `ff.ffmpeg(*args)` runs
  `ffmpeg -y -v error ...` and raises `ff.FFError` (a `RuntimeError` subclass) on failure;
  `ff.FFMissing(FFError)` when the binary is absent.
- **Test runner:** `bash tests/run.sh` (groups `consistency`, `py`, `node`; `bash tests/run.sh py`
  runs one). Python tests are stdlib `unittest`; Node tests are `node --test`. Every
  `tests/consistency/*.sh` is picked up automatically.
- **Release (from CLAUDE.md + memory):** version lives in `.claude-plugin/plugin.json`,
  pinned in `tests/consistency/plugin-identity.sh` (`want_version="3.21.0"` line 15) and
  `tests/consistency/tools-index.sh` (lines 39-40), headline `README.md:6` (`<b>v3.21.0</b>`) plus
  a `## v3.21.0 Changelog` section (README:251), and the `**Version:**` / `**Last Updated:**` lines
  plus `### v3.21.0 Changelog` in `CLAUDE.md`. `tests/consistency/marketplace-version.sh` compares
  plugin.json with the gaspol-video entry in `../gaspol-one/.claude-plugin/marketplace.json` and
  its README table. The marketplace version must come from `plugin.json` on the pushed remote
  `origin/main`, never from a local checkout.
- **Worktree finish (global standard):** `git merge --no-ff GV-25-tool-dedup` in main →
  `git worktree remove .claude/worktrees/gv-25-tool-dedup` → `git worktree prune`. The spec/plan
  stay on the branch and reach main through the merge; never copy them to main by hand.
- No `security-reviewer` agent (plugin repo, owner rule).

Facts measured while writing this plan (verify, do not re-derive):
- `tools/vidkit/track.py` (37 lines, `smooth_track(points, window=9, shrink=1.0, fixed_angle=True)`).
  Callers: `tools/vidkit/__main__.py` line 9 (`track` in the `from . import ...` list), lines 224-227
  (`smooth-track` subparser), lines 397-401 (dispatch); `tests/py/test_vidkit.py` line 17 (import
  list ends `..., tidy, track`) and three tests lines 306-320
  (`test_smooth_track_removes_angle_jitter_and_spike`, `test_smooth_track_shrink_keeps_centre`,
  `test_smooth_track_rejects_even_window`); `tools/registry.json` tool entry lines 867-879 and the
  screen route lines 1395-1403; `docs/vidkit.md` line 20 table row. No skill, agent, reference or
  template calls it.
- Screen route today (`tools/registry.json` ~1396): task `Put an app screen into a phone/monitor in a clip`,
  tools `["tools/vidkit/screen.py", "tools/track_screen.py", "tools/vidkit/track.py"]`.
- `vidkit screen-insert` CLI (`tools/vidkit/__main__.py:238-245`):
  `screen-insert <clip> <panel> <out> --mode green|track [--corners x,y,x,y,x,y,x,y] [--occluder x,y] [--qa DIR]`;
  `panel` = "PNG (held) or mp4 (looped / cut to the clip)"; `--corners` = "clockwise from top-left at frame 0".
  `tools/track_screen.py` writes `{"keys": [{"t": 0.0, "corners": [[x,y],[x,y],[x,y],[x,y]]}, ...]}`,
  corners clockwise from top-left in delivery pixels (its docstring line 40) — the same order.
- Skills still routing to the old pipeline: `skills/video-explainer/SKILL.md` Hard Rules 9-10
  (lines 79-92) and checklist line 246; **also `skills/video-image/SKILL.md` Rule 36 (line 134)**,
  which the spec did not list but which routes to the same `QuadScreenTracked` + `track_screen.py`
  pair. Spec #1 requires "not used by any skill", so Rule 36 is in scope. `README.md:239` describes
  the old pair as the screen-overlay feature. No agent, reference doc or hook mentions it.
- `tools/voice_changer.mjs`: `parseVoiceSettings({stability, style})` lines 63-78; `convert()` form
  built lines 242-248; `convertSpans({... voiceSettings = null ...})` lines 302-316, per-span form
  lines 369-372; CLI `main()` lines 434-476 (usage text lines 441-446, `common` object lines 464-471).
- `tools/vidkit/js/cast_voice.mjs` (53 lines): `planFetch(member, fetchImpl)` appends
  `voice_settings` and `seed` to the multipart body by wrapping fetch; `run()` passes
  `fetchImpl: planFetch(member, fetchImpl)` to `convertSpans`. Tested in
  `tests/node/vidkit-js.test.mjs` line 9 (import `{ planFetch, run }`) and lines 68-73.
- `tools/qa_frames.py` `make_sheet(clip, project, scene, times)` lines 197-215: one
  `ffmpeg -ss t -i clip -frames:v 1 -vf scale=480:-2` per time, then `hstack`, no padding;
  `_run()` lines 191-194 raises `RuntimeError`; caller line 337-342 catches `RuntimeError`.
  `FFMPEG = shutil.which("ffmpeg")` line 34. `tests/py/test_qa_frames.py:200-218` asserts the
  5-frame sheet is 2400 px wide (5 × 480) and the single frames are removed.
- `tools/vidkit/sheet.py` `contact_sheet(clip, out, frames=5, cols=None, width=360)` samples by
  `fps=frames/d` with `tile=...:padding=4`. Other callers: `screen.py:750`, `embroider.py:739`,
  `__main__.py:376`, `retention_gate.py:306` — none pass `times`, so their output must not change.

## Tech Stack

Python 3 stdlib + ffmpeg (no new dependency), Node built-ins (`node --test`), bash consistency
checks. detect-stack printed `static: UNKNOWN`, `lint: UNKNOWN`, `unit: pytest`; the spec fixes the
real gates instead: static = `python3 -m py_compile <changed .py>` and `node --check <changed .mjs>`,
unit = `bash tests/run.sh` (stdlib unittest + node --test, no pytest in this repo).

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---------|-------------|----------|---------|--------|
| Screen panel into a clip | `vidkit screen-insert` | `tools/vidkit/screen.py` `insert()` via `python3 -m tools.vidkit screen-insert` | Yes | Route skills to it |
| Corners for `--mode track` | `tools/track_screen.py` json `keys[0].corners` | CLI | Yes | Keep, re-document as corner reader only |
| Panel content | Remotion screen/screencast shot render | `templates/remotion` workspace, `shots/out/*.mp4` or still PNG | Yes | Use existing render; no new component |
| `QuadScreenTracked` | `templates/remotion/lib/quad-screen.tsx` | — | Yes | Mark LEGACY, no skill uses it |
| Smoothing of screen corners | One-Euro inside `screen.py` | internal | Yes | Replaces `vidkit/track.py` |
| `vidkit smooth-track` | `tools/vidkit/track.py` | CLI subcommand | Yes | Delete |
| Seed on speech-to-speech | ElevenLabs STS multipart field `seed` | `tools/voice_changer.mjs` `convert` / `convertSpans` | No (only via `cast_voice.planFetch`) | Add `seed` param + `--seed N` |
| Per-cast batch | `tools/vidkit/js/cast_voice.mjs` `run()` | `convertSpans` | Yes | Pass `voiceSettings` + `seed` as params; drop `planFetch` |
| Exact-time contact sheet | ffmpeg via `ff.ffmpeg` | `tools/vidkit/sheet.py` `contact_sheet(times=...)` | No | Add `times` |
| QA sheet V15 | `tools/qa_frames.py` `make_sheet` | `sheet.contact_sheet` | Yes (own ffmpeg code) | Call `vidkit.sheet` |

## Out of scope

- `prosody` vs `guide_vo` (#5) and `keyword_cards.py` (#6): spec says no change.
- Deleting `quad-screen.tsx` or `track_screen.py`: spec keeps both (legacy / corner reader).
- History lines in older CLAUDE.md/README changelogs (v3.4.0 etc.) that mention `QuadScreenTracked`: history, not routing; left as is.
- Any change to `screen.py` itself.

---

### Phase A: retire `vidkit smooth-track` (spec #2)

**Estimated time:** 15 minutes

**Completeness:** happy path = module, CLI, tests, registry, docs gone, suite green. Error path: a
real caller exists → STOP (step 2). Edge: `--coverage` gate fails if the file is deleted but the
entry stays, or the reverse → both in the same commit. Observability: argparse prints
`invalid choice: 'smooth-track'` to anyone with an old command. Tests: step 1.

**Files:**
- Delete: `tools/vidkit/track.py`
- Modify: `tools/vidkit/__main__.py`, `tests/py/test_vidkit.py`, `tools/registry.json`, `docs/vidkit.md`, `docs/tool-routing.md` (generated)
- Test: `tests/py/test_vidkit.py`

**Steps:**
1. Write failing test for the retired subcommand. In `tests/py/test_vidkit.py` add `test_smooth_track_is_retired`: `subprocess.run([sys.executable, "-m", "tools.vidkit", "smooth-track", "x.json"], cwd=<repo root>, capture_output=True, text=True)`; assert `returncode == 2` and `"invalid choice"` in stderr; also assert `not (Path(<repo root>) / "tools/vidkit/track.py").exists()`. Expected error: `AssertionError: 0 != 2` (or the `FileNotFoundError` from reading a missing `x.json`, exit 1) — the subcommand still exists.
2. Run `python3 -m unittest tests.py.test_vidkit -k smooth_track_is_retired`; confirm it fails for that reason. Then run `rtk proxy grep -rn -E "smooth_track|smooth-track|vidkit\.track|from \.track|import.*\btrack\b" --include='*.py' --include='*.mjs' --include='*.md' --include='*.json' --include='*.sh' --include='*.tsx' . | grep -v docs/plans | grep -v graphify-out`. Allowed hits: the ones listed in Architecture Context plus `pointtrack` imports. Any other caller → STOP and ask.
3. Delete `tools/vidkit/track.py`. In `tools/vidkit/__main__.py` remove `track` from the line-9 import list, the `smooth-track` subparser (lines 224-227) and its `elif a.cmd == "smooth-track":` branch (lines 397-401).
4. In `tests/py/test_vidkit.py` remove `track` from the line-17 import and delete the three `test_smooth_track_*` tests (lines 306-320).
5. In `tools/registry.json` delete the `tools/vidkit/track.py` tool entry; in the screen route set `"tools": ["tools/vidkit/screen.py", "tools/track_screen.py"]` and `"use"` to: ``"`python3 -m tools.vidkit screen-insert <clip> <panel> <out> --mode green\\|track` (green: exact corners from a green screen, `--mode track --corners ...` for a clip without green); `track_screen.py` only reads the four `--corners` numbers for `--mode track`. Remotion `quad-screen.tsx` is legacy, no skill uses it"``. Run `python3 tools/registry_build.py render`.
6. In `docs/vidkit.md` delete the `| \`track\` | \`smooth_track\` ...` row (line 20).
7. Run `bash tests/run.sh`; confirm all pass. Commit: `refactor(GV-25): retire vidkit smooth-track (One-Euro in screen.py replaced it)`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/__main__.py tests/py/test_vidkit.py` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] `python3 tools/registry_build.py validate --coverage` and `python3 tools/registry_build.py render --check` exit 0
- [ ] `python3 -m tools.vidkit smooth-track x.json` exits 2 with `invalid choice`
- [ ] grep from step 2 returns no hit outside `docs/plans/` and history changelogs
- [ ] No placeholder/TODO comments in new code

---

### Phase B: `voice_changer.mjs --seed`, `cast_voice.mjs` as batch runner only (spec #3)

**Estimated time:** 15 minutes

**Completeness:** happy path = `seed` sent as form field on `convert` and on every span request of
`convertSpans`. Error paths: a bad seed (`-1`, `1.5`, `abc`, `4294967296`, empty) throws
`seed must be an integer 0-4294967295, got <raw>` — refused, never clamped (same policy as
`parseVoiceSettings`). Edge: no `--seed` → no `seed` field (API default kept); seed `0` is valid and
must be sent (not dropped as falsy). Observability: the error names the flag and the raw value.
Not applicable: network retries (unchanged code path).

**Files:**
- Modify: `tools/voice_changer.mjs`, `tools/vidkit/js/cast_voice.mjs`
- Test: `tests/node/voice_changer.test.mjs`, `tests/node/vidkit-js.test.mjs`

**Steps:**
1. Write failing test for the seed field. In `tests/node/voice_changer.test.mjs` import `parseSeed` and add: (a) `convert({... seed: 7, fetchImpl: okFetch(calls)})` → `calls[0].init.body.get("seed") === "7"`; (b) `seed: 0` → `"0"`; (c) no seed → `calls[0].init.body.get("seed") === null`; (d) `convertSpans` with two spans and `seed: 7` → both requests carry `"7"`; (e) `parseSeed` returns `null` for `undefined`/`null`, `42` for `"42"`, and throws `/seed must be an integer 0-4294967295/` for `"-1"`, `"1.5"`, `"abc"`, `""`, `"4294967296"`. Reuse the existing `okFetch`, `extract`, `durationOf` stubs used by the `voice settings are sent as JSON when given` test (line 295). Expected error: `SyntaxError: The requested module '../../tools/voice_changer.mjs' does not provide an export named 'parseSeed'`.
2. Run `node --test tests/node/voice_changer.test.mjs`; confirm it fails for that reason.
3. In `tools/voice_changer.mjs`: add exported `parseSeed(raw)` next to `parseVoiceSettings` (null for undefined/null; `/^\d+$/` and `<= 4294967295` else throw `seed must be an integer 0-4294967295, got ${raw}`); add `seed = null` to `convert`'s and `convertSpans`'s parameter objects; after each `voice_settings` append add `if (seed !== null) form.append("seed", String(seed));`; in `main()` add `seed: parseSeed(flag("seed")),` to `common` and the usage line `       [--seed 2026091301]  same seed -> same delivery on a re-run (default: none)`.
4. Run `node --test tests/node/voice_changer.test.mjs`; confirm pass.
5. Write failing test for cast_voice. In `tests/node/vidkit-js.test.mjs` replace the `planFetch` test (lines 68-73) with `run passes per-cast settings and seed to convertSpans`: call `run({cast:{c1:{voice_env:"V",seed:5,settings:{stability:0.2}}},scenes:{S1:{cast:"c1",spans:"0-1"}}}, {env:{}, convert: async (o) => (seen = o)})` and assert `seen.seed === 5`, `seen.voiceSettings` deep-equals `{stability:0.2}`, `seen.fetchImpl === undefined`; change the import to `{ run }`. Run it; expected failure: `AssertionError ... undefined !== 5`.
6. In `tools/vidkit/js/cast_voice.mjs` delete `planFetch`; in `run()` pass `voiceSettings: member.settings || null, seed: member.seed ?? null, fetchImpl` (plain, may be undefined → `convertSpans` default). Rewrite the header's first paragraph to: `Batch runner: voice-change many scenes with PER-CHARACTER voice_settings and seed from one cast file. The request itself is voice_changer.mjs convertSpans (it takes --stability/--style/--seed on the CLI); this file only maps each scene to its cast member and converts the listed spans, so the clip's SFX between phrases stays original. Get the spans from eleven.mjs stt word timings.` Keep the usage and plan.json block unchanged.
7. Run `bash tests/run.sh node`; confirm pass. Commit: `feat(GV-25): voice_changer --seed; cast_voice passes settings and seed as params`.

**Verification:**
- [ ] static: `node --check tools/voice_changer.mjs && node --check tools/vidkit/js/cast_voice.mjs` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] `node tools/voice_changer.mjs` (no args) usage text lists `--seed`
- [ ] `rtk proxy grep -n "planFetch\|sends no" tools/ tests/ -r` returns nothing
- [ ] No placeholder/TODO comments in new code

---

### Phase C: exact-time contact sheet; `qa_frames` uses it (spec #4)

**Estimated time:** 15 minutes

**Completeness:** happy path = `contact_sheet(clip, out, width=480, times=[...])` returns one
JPEG with one tile per time, in order, no padding, cols defaulting to `len(times)`. Error paths:
`times=[]` → `ValueError("times is empty")`; a negative time → `ValueError`; an ffmpeg failure
raises `ff.FFError` (a `RuntimeError`, so `qa_frames` line 339 still catches it and marks the scene
failed). Edge: one time (n=1, no `xstack`); `cols < len(times)` (two rows, short last row filled
black); last-frame time. `times=None` keeps today's fps path byte-for-byte (other four callers
unchanged). Observability: `qa_frames` keeps printing `scene NN  failed: <ffmpeg stderr>`.

**Files:**
- Modify: `tools/vidkit/sheet.py`, `tools/qa_frames.py`
- Test: `tests/py/test_vidkit.py`, `tests/py/test_qa_frames.py` (new test only; existing tests unchanged)

**Steps:**
1. Write failing test for exact timestamps. In `tests/py/test_vidkit.py` add `test_contact_sheet_exact_times`: build a 2 s clip with `ffmpeg -f lavfi -i color=c=red:s=64x64:d=1 -f lavfi -i color=c=blue:s=64x64:d=1 -filter_complex concat=n=2:v=1 -r 25`, call `sheet.contact_sheet(clip, out, width=64, times=[0.5, 1.5])`, read the sheet as raw RGB (`ffmpeg -i out -f rawvideo -pix_fmt rgb24 -`), assert width 128 and that the centre pixel of the left tile is red-dominant and of the right tile blue-dominant. Add `test_contact_sheet_times_edges`: `times=[]` raises `ValueError`; `times=[-1]` raises `ValueError`; one time gives width 64; three times with `cols=2` gives width 128 and height 128. Expected error: `TypeError: contact_sheet() got an unexpected keyword argument 'times'`.
2. Run `python3 -m unittest tests.py.test_vidkit -k contact_sheet`; confirm it fails for that reason.
3. In `tools/vidkit/sheet.py` add `times=None` to `contact_sheet`. When given: validate (non-empty, all `>= 0`), `cols = cols or len(times)`, build inputs `-ss t -i clip` per time, filter `[k:v]scale={width}:-2,trim=end_frame=1,setpts=PTS-STARTPTS[s{k}]` per input, then `hstack`/`xstack` like `montage` (`n == 1` → map `[s0]` directly; `cols < n` → `xstack` with `fill=black`), `-frames:v 1 -q:v 3`, through `ff.ffmpeg`. Docstring: "``times`` (seconds) picks exact frames, e.g. the last frame; without it, ``frames`` evenly spaced frames." Leave the `times=None` branch untouched.
4. Run `python3 -m unittest tests.py.test_vidkit`; confirm pass.
5. Write failing test for the delegation. In `tests/py/test_qa_frames.py` add `test_make_sheet_delegates_to_vidkit_sheet`: `mock.patch.object(qa_frames.sheet, "contact_sheet")` and assert it was called once with `(str(clip), str(project/".tmp/qa-scene-01.jpg"))`, `width=480`, `times=[0.0, 1.0]`, and that `make_sheet` returns `project/".tmp/qa-scene-01.jpg"`. Expected error: `AttributeError: module 'tools.qa_frames' has no attribute 'sheet'`.
6. In `tools/qa_frames.py`: `from tools.vidkit import ff, sheet`; `make_sheet` becomes: ensure `.tmp`, `out = tmp / ("qa-scene-%s.jpg" % scene)`, `sheet.contact_sheet(str(clip), str(out), width=480, times=list(times))`, `return out`. Remove `_run` and `FFMPEG` only if `rtk proxy grep -n "_run(\|FFMPEG" tools/qa_frames.py` shows no other use (5 hits today; check each). Update the `make_sheet` docstring: "Tile one frame per timestamp into .tmp/qa-scene-NN.jpg (vidkit.sheet.contact_sheet)."
7. Run `bash tests/run.sh`; confirm all pass, including the unchanged `test_writes_sheet_and_verdict_section_and_removes_single_frames` (2400 px). Commit: `refactor(GV-25): qa_frames tiles through vidkit.sheet (exact times)`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/sheet.py tools/qa_frames.py` passes
- [ ] unit: `bash tests/run.sh` passes; `git diff e0da0a4 -- tests/py/test_qa_frames.py` shows only additions
- [ ] `python3 tools/registry_build.py validate --coverage` exits 0 (ffprobe ratchet unchanged)
- [ ] `qa_frames.py` on a real project clip still writes `.tmp/qa-scene-NN.jpg` and `qa_frames.py --check` reads the same verdict sheet (run on any project folder under `~/Drive-D` that has `clips/` + `renders.json`; record which in the ledger, or `[~]` with reason if none exists)
- [ ] No placeholder/TODO comments in new code

---

### Phase D: one route for screen panels (spec #1)

**Estimated time:** 15 minutes

**Completeness:** happy path = both skills route a screen panel to Remotion render → `vidkit
screen-insert`. Error paths written into the skill text: `screen-insert` refusals (exit 2,
`refused: ...`) mean re-render or trim per the CLAUDE.md Debugging rows, never fall back to
`QuadScreenTracked`; a screen under 120 px wide or facing away stays a floating card (rule kept).
Edge: a clip without green → `--mode track` with `--corners` from `track_screen.py` json
`keys[0].corners` flattened `x,y,x,y,x,y,x,y`, clockwise from top-left. Observability:
`--qa .tmp/qa-NN` writes `qa-screen.jpg`, which the skill says to look at. Test: a consistency
check so no skill can drift back.

**Files:**
- Create: `tests/consistency/screen-route-contract.sh`
- Modify: `skills/video-explainer/SKILL.md`, `skills/video-image/SKILL.md`, `templates/remotion/lib/quad-screen.tsx`, `tools/track_screen.py`, `README.md`

**Steps:**
1. Write failing test for the single route. Create `tests/consistency/screen-route-contract.sh` (bash 3.2 safe, `set -uo pipefail`, `cd` to repo root like the other checks) that prints `FAIL <file>: <reason>` and exits 1 when: any `skills/*/SKILL.md` or `agents/*.md` contains `QuadScreenTracked` or `smooth-track`; `skills/video-explainer/SKILL.md` or `skills/video-image/SKILL.md` lacks `screen-insert`; the first 5 lines of `templates/remotion/lib/quad-screen.tsx` lack `LEGACY`; the module docstring of `tools/track_screen.py` (first 15 lines) lacks `--corners`. Prints `PASS screen-route-contract` otherwise. Expected error: `FAIL skills/video-explainer/SKILL.md: routes to QuadScreenTracked`.
2. Run `bash tests/consistency/screen-route-contract.sh`; confirm it fails for that reason.
3. Rewrite `skills/video-explainer/SKILL.md` Hard Rule 9 as: **(v3.21.1) A panel on a screen is rendered here, then placed by `vidkit screen-insert`.** Render the panel content as a normal screen/screencast shot (`shots/out/<shot>.mp4`, or a still PNG for a held screen). Place it: `python3 -m tools.vidkit screen-insert clips/scene-NN.mp4 shots/out/<shot>.mp4 clips/scene-NN-screen.mp4 --mode green --qa .tmp/qa-NN` when the clip's screen was prompted `flat solid chroma green screen` (video-gen Rule 26, check V17); otherwise `--mode track --corners x,y,x,y,x,y,x,y` with the corners of frame 0, clockwise from top-left, read from `python3 tools/track_screen.py <clip> work/track-scene-NN.json --seed x,y --qa .tmp/qa-NN` (`keys[0].corners`). Look at `.tmp/qa-NN/qa-screen.jpg`. A `refused: ...` exit 2 means trim or re-render (CLAUDE.md Debugging rows), never fall back to `QuadScreenTracked` (legacy, kept only for old projects). Keep the trapezoid sentence (524 px vs 375 px) as the reason. In Rule 10 replace "tracked" wording with "screen-insert" and keep the measurements and the 120 px floor. Replace checklist line 246 with `- [ ] **(v3.21.1)** Screen-attached panels are placed with \`vidkit screen-insert\` (green or track), and \`qa-screen.jpg\` was inspected`.
4. Rewrite `skills/video-image/SKILL.md` Rule 36's last two sentences: the panel is attached with `python3 -m tools.vidkit screen-insert` (`--mode green` when the screen is prompted as chroma green per video-gen Rule 26; `--mode track --corners` from `tools/track_screen.py` otherwise); keep the measurement rules (frontal ≥300 px, oblique, under 120 px → floating card) and "never from a bounding box". Remove the `QuadScreenTracked` sentence.
5. Prepend to `templates/remotion/lib/quad-screen.tsx`: `// LEGACY (v3.21.1, GV-25): no skill uses this. Screen panels are placed with\n// \`python3 -m tools.vidkit screen-insert\` (tools/vidkit/screen.py). Kept for projects scaffolded before v3.21.0.\n//`. In `tools/track_screen.py` add after the first docstring line: `Since v3.21.1 its only job is reading the four corners for \`vidkit screen-insert --mode track --corners x,y,x,y,x,y,x,y\` (keys[0].corners, clockwise from top-left). Placing the panel is screen-insert's job.` Change nothing else in either file.
6. In `README.md:239` change the Screen-Attached Overlays row to `` `vidkit screen-insert` (`--mode green` / `--mode track`); `tools/track_screen.py` reads `--corners` ``.
7. Run `bash tests/run.sh`; confirm all pass. Commit: `docs(GV-25): screen panels route to vidkit screen-insert only`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/track_screen.py` passes; `bash -n tests/consistency/screen-route-contract.sh` passes
- [ ] unit: `bash tests/run.sh` passes (includes `screen-route-contract.sh`)
- [ ] `rtk proxy grep -rn "QuadScreenTracked" skills/ agents/ reference/ hooks/` returns nothing
- [ ] `python3 -m tools.vidkit screen-insert --help` still matches the flags written in both skills (`--mode`, `--corners`, `--occluder`, `--qa`)
- [ ] No placeholder/TODO comments in new code

---

### Phase E: Penutup — docs, 3.21.1, merge, marketplace

**Estimated time:** 15 minutes

**Completeness:** happy path = docs and version agree everywhere, suite green, merged, pushed,
marketplace matches `origin/main`. Error paths: merge conflict in `tools/registry.json` or
`tools/vidkit/__main__.py` (main moved) → resolve keeping both sides, re-run `render` and the
suite; `marketplace-version.sh` FAIL before the marketplace bump is expected and is the step-10
signal, not a bug. Edge: main has uncommitted work (happened in GV-24) → STOP and ask, never stash
someone else's work. Not applicable: deploy (plugin, no server).

**Files:**
- Modify: `tests/consistency/plugin-identity.sh`, `tests/consistency/tools-index.sh`, `.claude-plugin/plugin.json`, `CLAUDE.md`, `README.md`, `docs/vidkit.md`
- Modify (other repo): `../gaspol-one/.claude-plugin/marketplace.json`, `../gaspol-one/README.md`

**Steps:**
1. Write failing test for the version pin. Set `want_version="3.21.1"` in `tests/consistency/plugin-identity.sh` and `3.21.1` in both places in `tests/consistency/tools-index.sh` (lines 39-40). Expected error: `FAIL plugin.json version is not 3.21.1`.
2. Run `bash tests/run.sh consistency`; confirm it fails for that reason.
3. `.claude-plugin/plugin.json` `"version": "3.21.1"`; `README.md` headline `<b>v3.21.1</b>` and a `## v3.21.1 Changelog` section above `## v3.21.0 Changelog`; `CLAUDE.md` `**Version:** 3.21.1`, `**Last Updated:** 2026-10-17`, and a `### v3.21.1 Changelog` above v3.21.0 with four bullets: screen panels → `vidkit screen-insert` only (video-explainer Rules 9-10, video-image Rule 36, `quad-screen.tsx` legacy, `track_screen.py` = corner reader, check `tests/consistency/screen-route-contract.sh`); `vidkit smooth-track` / `tools/vidkit/track.py` removed; `voice_changer.mjs --seed N`, `cast_voice.mjs` is the per-cast batch runner; `vidkit.sheet.contact_sheet(times=...)`, `qa_frames.py` uses it, V15 unchanged. Plus a registry-count line (tool entries one fewer than before; 78 routes).
4. `CLAUDE.md` architecture table: in the `tools/vidkit/` rows remove "track smoothing" from the listed features; in the `tools/qa_frames.py` row add "(tiles through `vidkit.sheet.contact_sheet`)". `docs/vidkit.md`: in the `sheet` row mention `times=`; add one line under Screen insert: "`tools/track_screen.py` only reads `--corners`; `quad-screen.tsx` is legacy."
5. Run gates: `bash tests/run.sh`, `python3 tools/registry_build.py validate --coverage`, `python3 tools/registry_build.py render --check`, `python3 -m py_compile` on every changed `.py`. Only `marketplace-version.sh` may fail (3.21.0 vs 3.21.1). Commit: `chore(GV-25): release v3.21.1`.
6. In main checkout: `git status --short` must be empty (else STOP and ask). `git merge --no-ff GV-25-tool-dedup`; on conflict resolve, `python3 tools/registry_build.py render`, re-run `bash tests/run.sh`. `git push origin main`.
7. Confirm remote: `git show origin/main:.claude-plugin/plugin.json | grep version` prints `3.21.1`.
8. In `../gaspol-one`: set the gaspol-video entry to `3.21.1` in `.claude-plugin/marketplace.json` and the README version table row; commit `chore: gaspol-video 3.21.1`, push.
9. Back in gaspol-video main: `bash tests/run.sh` — all pass, including `marketplace-version.sh`.
10. `git worktree remove .claude/worktrees/gv-25-tool-dedup`, `git worktree prune`, `git branch -d GV-25-tool-dedup`.

**Verification:**
- [ ] static: `python3 -m py_compile` on every changed `.py` passes
- [ ] unit: `bash tests/run.sh` passes on main after merge, including `marketplace-version.sh`
- [ ] `python3 tools/registry_build.py validate --coverage` and `render --check` exit 0 on main
- [ ] `git show origin/main:.claude-plugin/plugin.json` shows `3.21.1`; gaspol-one `marketplace.json` gaspol-video = `3.21.1`
- [ ] `git worktree list` no longer shows `gv-25-tool-dedup`
- [ ] No placeholder/TODO comments in new code
