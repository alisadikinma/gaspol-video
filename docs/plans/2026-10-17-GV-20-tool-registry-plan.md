> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-20.md` (created by `gaspol-plan` at plan-write time). After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. This is **blocking**, like a test gate. Never batch updates at the end. Update ONLY this file, never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. Every path, contract and convention needed is written here verbatim.

**Ticket:** GV-20
**Ledger:** .gaspol/progress/PROGRESS-GV-20.md
**Spec:** docs/plans/2026-10-17-GV-20-tool-registry-spec.md

## Goal

Make "which tool for which job" and "no duplicate tools" enforced by machine, not by reading a hand-written table. Deliver: (1) `tools/registry.json`, the single source of truth for every tool and every task-to-tool route; (2) `docs/tool-routing.md` table generated from it; (3) gate tests that fail on an unregistered tool, a duplicate tool, or a new `ffprobe` call outside `vidkit/ff.py`; (4) a PreToolUse hook that, when a new `.py/.mjs/.sh` script containing `ffmpeg|ffprobe|remotion` is written outside `tools/`, reminds the agent which registered tools are closest. The hook reminds, never blocks.

## Architecture Context (from CLAUDE.md, read 2026-10-17)

- Plugin root = repo root (worktree `.claude/worktrees/gv-20-tool-registry`). Run tools from the plugin root: `python3 tools/<name>.py`, `python3 -m tools.vidkit ...`.
- Tool files: `tools/*.py` (35 py), `tools/*.mjs` (2), `tools/vidkit/*.py` (21 modules incl. `__init__.py`, `__main__.py`), `tools/vidkit/js/*.mjs` (3). `tools/_venv.py` and every `__init__.py` are infrastructure, not tools.
- `docs/tool-routing.md` (82 lines): a 60-row markdown table `| I want to... | Use |` then a "When no tool fits" section. It is hand-written today.
- `tests/run.sh` runs three groups: `consistency` (`tests/consistency/*.sh`, each `bash <file>`, exit 0 = pass), `py` (`python3 -m unittest discover -s tests/py -t . -q`), `node` (`node --test`). **There is no pytest in this repo on purpose** (`detect-stack` prints `unit: pytest`, which is wrong here; the real command is `bash tests/run.sh py`).
- `tests/consistency/tools-cli.sh` runs `python3 tools/<f>.py --help` for every `tools/*.py` (except `__init__.py`, `_venv.py`): a new tool file MUST answer `--help` when run as a script, so it must put the repo root on `sys.path` (`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`).
- `tests/consistency/tools-index.sh` requires every `tools/*.py` and `tools/*.mjs` basename to appear in `CLAUDE.md`, and hardcodes `"version": "3.17.0"` in `.claude-plugin/plugin.json`. Bumping the version means editing this test too (Phase I).
- `hooks/hooks.json` today has only `SessionStart` (`${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh`).
- `tools/vidkit/ff.py` exposes `FFError`, `run(cmd, capture_stderr=False, heartbeat_s=None)`, `ffmpeg(*args)`, `probe(path)` (returns `{duration, video:{duration,fps,width,height}|None, audio:{duration,sample_rate,channels}|None}`), `duration(path)`, `has_audio(path)`, `ensure_parent`. Tools under `tools/*.py` do NOT import vidkit today; they use `shutil.which("ffprobe")` plus their own error classes.
- Measured 2026-10-17: ffprobe is referenced in `burn_subs, check_vo_duration, clean_voice, composite, edit_render, gen_music, make_stems, mix_music, mix_sfx, overlay_plan, person_mask, probe_clips, qa_frames, retention_gate, track_screen` (tools/) and `vidkit/color.py`. Four tools are missing from the routing table: `check_overlay_strings.py`, `probe_clips.py`, `vidkit/gates.py`, `vidkit/patch.py`.
- Worktree rules (user standard): spec and plan stay on the branch `GV-20-tool-registry`; never copy them to main. Finish: `git merge --no-ff GV-20-tool-registry` → `git worktree remove` → `git worktree prune`.

## Tech Stack

Python 3 stdlib only (json, re, pathlib, argparse, unittest). Bash for consistency gates and the hook wrapper. No new dependencies. Hook protocol: Claude Code PreToolUse hook receives JSON on stdin (`tool_name`, `tool_input.file_path`, `tool_input.content` for Write or `tool_input.new_string` for Edit) and may print `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"<text>"}}` on stdout with exit 0.

## Registry contract (inline, verbatim)

`tools/registry.json`:

```json
{
  "version": 1,
  "tools": [
    {
      "id": "tools/composite.py",
      "purpose": "Insert, overlay or split a shot into a finished master.",
      "tasks": ["composite", "overlay", "insert", "split"],
      "phase": "6",
      "replaces": [],
      "distinct_because": "",
      "internal_reason": ""
    }
  ],
  "routes": [
    {"task": "Insert/overlay/split a shot into a master", "use": "`composite.py`", "tools": ["tools/composite.py"]}
  ],
  "ffprobe_allow": [
    {"id": "tools/composite.py", "reason": "needs -select_streams per call; migrate under GV-21"}
  ]
}
```

Field rules (enforced by `registry_build.validate`):
- `id`: path relative to plugin root, must exist on disk. Vidkit modules use `tools/vidkit/<stem>.py`; node helpers `tools/vidkit/js/<name>.mjs`.
- `purpose`: non-empty, one sentence, ≤ 140 chars, no newline.
- `tasks`: 1–6 lowercase tokens `[a-z0-9-]+`, unique within the tool.
- `phase`: one of `"1".."7"` or `"shared"`.
- `replaces`: list of tool ids that exist in `tools`.
- `distinct_because`: string; required (non-empty) only to excuse a duplicate pair.
- `internal_reason`: non-empty string means "not reachable from a route row, and here is why" (e.g. imported helper). Otherwise the tool must appear in `tools` of at least one route.
- `routes[].task` / `routes[].use`: non-empty, no `|` character, no newline. `routes[].tools`: existing tool ids (may be empty only for rows that point outside this plugin, such as the `gaspol-catalog deckkit` row).
- `ffprobe_allow[].id` must exist and its file must really contain `ffprobe`; `reason` non-empty. A listed file that no longer contains `ffprobe` is a stale entry and fails.

Excluded from coverage: `__init__.py` files, `tools/_venv.py`, `tools/vidkit/__main__.py` (the CLI entry; its subcommands are routed by their module).

Duplicate rule: two tools with the same `phase` and the same set of `tasks` fail, unless one lists the other in `replaces`, or both have non-empty `distinct_because`.

CLI `python3 tools/registry_build.py`:
- `validate` → exit 0 ok; exit 1 listing every problem (one per line, `path: problem`); exit 2 registry file missing or not JSON.
- `render` → rewrite the block between `<!-- registry:routes:begin -->` and `<!-- registry:routes:end -->` in `docs/tool-routing.md`. Exit 2 if markers are missing.
- `render --check` → exit 1 if the block differs from the registry (drift), 0 otherwise; writes nothing.
- `suggest [--top N] [--text-file PATH]` → read text from the file or stdin, print up to N (default 3) tools as `id — purpose`, best first, score > 0 only. Exit 0 always.

Generated block format: header row `| I want to... | Use |`, separator row `|---|---|`, then one `| <task> | <use> |` row per route in registry order.

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Tool list | files under `tools/`, `tools/vidkit/`, `tools/vidkit/js/` | `pathlib.glob` in `registry_build.discover()` | Yes (files) | Read directly |
| Registry | `tools/registry.json` | `registry_build.load()` | No | Create (Phase A/B, filled C–E) |
| Routing table | `routes` in registry → `docs/tool-routing.md` block | `registry_build.py render` | Table yes, hand-written | Replace with generated block (Phase B) |
| Existing 60 routes | current table in `docs/tool-routing.md` lines 11–70 | one-time parse in Phase B | Yes | Migrate verbatim into `routes` |
| ffprobe call sites | source text of tool files | regex `\bffprobe\b` in the gate | Yes | Ratchet via `ffprobe_allow` |
| Probe helper | `tools/vidkit/ff.py` `probe()`/`duration()` | import `from tools.vidkit import ff` | Yes | Use for migrated callers (Phase G) |
| Hook input | Claude Code PreToolUse stdin JSON | `hooks/tool-reminder.sh` → `registry_build.py suggest` | No | Create (Phase H) |
| Hook registration | `hooks/hooks.json` | PreToolUse entry, matcher `Write|Edit` | SessionStart only | Add entry |
| Version | `.claude-plugin/plugin.json`, `tests/consistency/tools-index.sh`, `README.md`, `CLAUDE.md` | text edit | Yes (3.17.0) | Bump to 3.18.0 (Phase I) |

## Phases

Commands used in every Verification block (resolved for this repo, `detect-stack` prints `static: UNKNOWN`, `lint: UNKNOWN`, `unit: pytest`, but this repo has no pytest and no linter, see Architecture Context):
- unit: `bash tests/run.sh py` and `bash tests/run.sh consistency`
- static: plan-declared `python3 -m py_compile <each new or changed .py file>` (no static checker exists in this repo)

### Phase A: Registry module — load, validate, discover

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/registry_build.py`
- Create: `tools/registry.json` (empty skeleton: `{"version":1,"tools":[],"routes":[],"ffprobe_allow":[]}`)
- Test: `tests/py/test_registry.py`

**Completeness (what this phase owes):**
- Happy path: `load()`, `discover()`, `validate()` per the contract.
- Error paths: registry missing → exit 2; invalid JSON → exit 2 naming the parse error; wrong `version` → problem; unknown field types; `id` not on disk; `replaces` pointing at an unknown id; duplicate `id`.
- Edge cases: empty `tools` list; `tasks` with uppercase/space; duplicate task token inside one tool; `purpose` > 140 chars or with newline; `phase` outside the allowed set; route cell containing `|`.
- Observability: every problem line is `<id or route #>: <problem>`; exit code 1 prints a final count line `registry: N problem(s)`.

**Steps:**
1. Write failing test for `registry_build.validate` rejecting a tool entry whose `id` does not exist on disk. Expected error: `ModuleNotFoundError: No module named 'tools.registry_build'`.
2. Run `bash tests/run.sh py`, confirm it fails for the expected reason.
3. Create `tools/registry_build.py` with `sys.path` idiom, `load(path)`, `discover(root)` (returns sorted ids of `tools/*.py`, `tools/*.mjs`, `tools/vidkit/*.py`, `tools/vidkit/js/*.mjs` minus the excluded set), `validate(reg, root)` returning a list of problem strings, and an argparse CLI that registers only `validate` now (later phases add `render`, `suggest`).
4. Add table-driven tests, one per error path and edge case listed above; run, see them pass.
5. Run `python3 tools/registry_build.py --help` and `python3 tools/registry_build.py validate` (empty registry passes validation of the schema but coverage is checked in Phase C–E, so `validate` has a flag `--coverage` default off until Phase F turns it on in the gate).
6. Commit: `feat(GV-20): registry loader and validator`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/registry_build.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] `python3 tools/registry_build.py --help` exits 0 (tools-cli gate: `bash tests/run.sh consistency` passes)
- [ ] `python3 tools/registry_build.py validate` on a missing registry exits 2 with a message naming the path
- [ ] No placeholder/TODO comments in new code

### Phase B: Routes migration and generated routing table

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/registry_build.py` (add `render`, `render --check`)
- Modify: `tools/registry.json` (fill `routes`)
- Modify: `docs/tool-routing.md` (insert markers, replace table with generated block)
- Test: `tests/py/test_registry.py`

**Completeness:**
- Happy path: 60 routes in `registry.json` reproduce the current table text exactly, so the rendered block is byte-identical to today's table.
- Error paths: markers missing → exit 2; marker order reversed → exit 2; a route with `|` in a cell → validate problem.
- Edge cases: trailing newline preserved; text outside the markers untouched byte for byte; running `render` twice changes nothing (idempotent).
- Observability: `render` prints `routing table: N routes written` or `routing table: unchanged`.

**Steps:**
1. Write failing test for `render --check` reporting drift when a route's `use` text differs from the file. Expected error: `SystemExit: 2` (unknown subcommand `render`).
2. Run the test, confirm it fails for the expected reason.
3. Write a one-time parser (run from the shell, not committed) that reads lines 13–70 of `docs/tool-routing.md` (rows after the header and separator) and writes `{"task","use","tools":[]}` per row into `routes` in `tools/registry.json`. Split on the first ` | ` only, trim the leading `| ` and trailing ` |`. Row 70 (`Deck / slide post-processing`) keeps `tools: []` by design (it points to `gaspol-catalog`).
4. Insert `<!-- registry:routes:begin -->` before the header row and `<!-- registry:routes:end -->` after the last row. Implement `render` and `render --check`. Run `render`, then `git diff docs/tool-routing.md`: only the two marker lines may differ.
5. Add idempotency and byte-identity tests; run, see them pass.
6. Commit: `feat(GV-20): routing table generated from registry`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/registry_build.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] `git diff docs/tool-routing.md` shows only the two marker lines added (table text unchanged)
- [ ] `python3 tools/registry_build.py render --check` exits 0; after hand-editing one table cell it exits 1
- [ ] No placeholder/TODO comments in new code

### Phase C: Register tools/*.py, first half (a–l)

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/registry.json`
- Modify: `tools/registry_build.py` (add `--coverage`: every discovered id has an entry)
- Test: `tests/py/test_registry.py`

Files in this half: `asset_home, asset_library, burn_subs, caption_keywords, check_overlay_strings, check_vo_duration, clean_voice, composite, composite_logo, cost_log, edit_render, gen_app_screen, gen_captions, gen_music, gen_sfx, gen_subs` (all `tools/<name>.py`), plus `tools/gen_vo.mjs`.

**Completeness:**
- Happy path: one entry per file with `purpose` from the file's own docstring (first sentence, shortened), `tasks` 2–4 tags, `phase` per CLAUDE.md pipeline (post-production tools = `"6"`, packaging = `"7"`, screens/explainer = `"4"`, cross-cutting = `"shared"`).
- Error paths: an entry for a file that does not exist fails validate.
- Edge cases: `gen_vo.mjs` is node; `tools/gen_music.py` and `tools/gen_sfx.py` have different tasks (music vs sfx), so no false duplicate.
- Observability: `--coverage` prints each uncovered id on its own line.

**Steps:**
1. Write failing test for `validate --coverage` reporting `tools/composite.py: not in registry`. Expected error: `AssertionError: 'tools/composite.py: not in registry' not found in problems`.
2. Run the test, confirm it fails for the expected reason (registry has no tools yet).
3. For each file listed above, read its module docstring and `--help`, then add the registry entry. Set `routes[].tools` for every route that names that file (match by basename in the route's `use` text); a tool with no route gets `internal_reason` (e.g. `"called only by edit_render.py"`) or, if a user-facing tool has no route, ADD a route row for it (this is how `check_overlay_strings.py` gets onto the table).
4. Run `python3 tools/registry_build.py validate --coverage` and read the remaining uncovered list; it must contain only files from the second half, vidkit, and js.
5. Run `render`; run `bash tests/run.sh py`.
6. Commit: `feat(GV-20): register tools a-l`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/registry_build.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] Coverage list no longer contains any of the 17 files in this half
- [ ] Every purpose is one sentence ≤ 140 chars (validate passes with no `purpose` problem)
- [ ] No placeholder/TODO comments in new code

### Phase D: Register tools/*.py, second half (m–z) and tools/*.mjs

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/registry.json`
- Test: `tests/py/test_registry.py`

Files: `make_stems, mix_music, mix_sfx, music_brief, overlay_plan, person_mask, plan_motion, probe_clips, qa_frames, renders, retention_gate, sfx_snap, thumb_scrim, thumb_verify, track_screen, verdict_page, verify_render, viral_checklist, yt_stats` (all `tools/<name>.py`), plus `tools/voice_changer.mjs`.

**Completeness:**
- Happy path: same entry rules as Phase C.
- Error paths: none new beyond validate.
- Edge cases: `probe_clips.py` vs `vidkit probe`: DECISION made at plan time: `probe_clips.py` stays, with `distinct_because` = "writes work/clip-manifest.json for a project (inventory + audio presence); vidkit probe prints one file's facts". Its tasks must differ from vidkit `ff` (Phase E) so the duplicate rule passes honestly; tasks for it: `["clip-manifest", "inventory", "durations"]`.
- Observability: coverage output shrinks to vidkit + js only.

**Steps:**
1. Write failing test for the full-`tools/*.py` coverage assertion in the repo itself (uses the real registry). Expected error: `AssertionError` listing `tools/make_stems.py: not in registry`.
2. Run the test, confirm it fails for the expected reason.
3. Add the 20 entries following Phase C rules; add routes for any user-facing tool lacking one.
4. Run `validate --coverage`: remaining uncovered must be only `tools/vidkit/*` and `tools/vidkit/js/*`.
5. Run `render`, `bash tests/run.sh py`.
6. Commit: `feat(GV-20): register tools m-z and node tools`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/registry_build.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] Uncovered list contains only vidkit and vidkit/js files
- [ ] `probe_clips.py` entry has non-empty `distinct_because`
- [ ] No placeholder/TODO comments in new code

### Phase E: Register vidkit modules and vidkit/js helpers

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/registry.json`
- Test: `tests/py/test_registry.py`

Files: `tools/vidkit/{audiostudy,beats,bond,color,colormatch,cover,encoder,ff,gates,ingest,join,karaoke,loudness,mixdown,patch,sheet,speech,stages,synth,track,unwhite}.py` and `tools/vidkit/js/{cast_voice,eleven,env}.mjs`. Excluded: `__init__.py`, `__main__.py`.

**Completeness:**
- Happy path: entries as before; `phase: "shared"` for library modules unless tied to one phase. `gates.py` and `patch.py` (previously off the table) get route rows: gates → "Check video length = audio length" row's `tools` (already names `vidkit gate-av`), patch → the "Freeze one region" row (`vidkit freeze`).
- Error paths: none new.
- Edge cases: `env.mjs` is imported by `eleven.mjs`/`cast_voice.mjs` → `internal_reason`. `ff.py` and `color.py` are the only legitimate ffprobe holders in vidkit (Phase G).
- Observability: `validate --coverage` now prints nothing and exits 0.

**Steps:**
1. Write failing test asserting the committed registry covers every discovered tool and every route row's `tools` entries exist. Expected error: `AssertionError` listing `tools/vidkit/audiostudy.py: not in registry`.
2. Run the test, confirm it fails for the expected reason.
3. Add the 24 entries; fix any duplicate-rule failure by sharpening `tasks` (never by deleting a tool).
4. Run `validate --coverage` and `render --check`; both exit 0.
5. Run `bash tests/run.sh py`.
6. Commit: `feat(GV-20): register vidkit modules and helpers`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/registry_build.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] `python3 tools/registry_build.py validate --coverage` exits 0
- [ ] `python3 tools/registry_build.py render --check` exits 0
- [ ] Every previously off-table tool (`check_overlay_strings`, `probe_clips`, `vidkit/gates`, `vidkit/patch`) is reachable from a route or has an `internal_reason`
- [ ] No placeholder/TODO comments in new code

### Phase F: Gate tests — registry coverage, duplicates, ffprobe ratchet

**Estimated time:** 15 minutes

**Files:**
- Create: `tests/consistency/tool-registry-contract.sh`
- Modify: `tools/registry_build.py` (duplicate rule, `ffprobe` scan inside `validate --coverage`)
- Modify: `tools/registry.json` (`ffprobe_allow`)
- Test: `tests/py/test_registry.py`

**Completeness:**
- Happy path: gate runs `validate --coverage` and `render --check`; exit 0 on the current tree.
- Error paths: unregistered file; duplicate pair without excuse; new `ffprobe` call in an unlisted file; stale `ffprobe_allow` entry (file no longer contains `ffprobe`); route pointing at an unknown tool.
- Edge cases: `ffprobe` appearing only inside a comment or docstring still counts (simple, conservative: any `\bffprobe\b` token); `tools/vidkit/ff.py` is exempt by definition; `tests/` is not scanned.
- Observability: each failure names file and rule: `tools/x.py: ffprobe outside vidkit/ff.py and not in ffprobe_allow`.

**Steps:**
1. Write failing test: a temp tree with a new `tools/new_probe.py` containing `ffprobe` must make `validate --coverage` report `tools/new_probe.py: ffprobe outside vidkit/ff.py and not in ffprobe_allow`. Expected error: `AssertionError` (rule not implemented; currently reports only `not in registry`).
2. Run the test, confirm it fails for the expected reason.
3. Implement the ffprobe scan and the duplicate rule in `validate --coverage`.
4. Run it against the real tree: it lists the 16 current callers. Add each to `ffprobe_allow` with a real reason read from the file (e.g. `composite.py`: "needs -select_streams per call"; `vidkit/color.py`: "needs color_space/primaries fields ff.probe does not return"; `probe_clips.py`: "full -show_streams JSON for the manifest, degrades loudly without ffprobe"). Phase G removes the ones it migrates.
5. Create `tests/consistency/tool-registry-contract.sh` (pattern of `tools-index.sh`: `set -uo pipefail`, cd to ROOT, `python3 tools/registry_build.py validate --coverage || fail=1`, `python3 tools/registry_build.py render --check || fail=1`, `exit $fail`).
6. Run `bash tests/run.sh`; commit: `test(GV-20): registry coverage, duplicate and ffprobe gates`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/registry_build.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] unit: `bash tests/run.sh consistency` passes (includes the new gate)
- [ ] Adding a file `tools/zz_tmp.py` makes the gate fail with `not in registry`; deleting it restores pass (then remove the temp file)
- [ ] No placeholder/TODO comments in new code

### Phase G: Migrate the simple ffprobe callers to vidkit.ff

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/check_vo_duration.py`
- Modify: `tools/track_screen.py`
- Modify: `tools/registry.json` (remove their `ffprobe_allow` entries)
- Test: `tests/py/test_registry.py` plus the existing tests of the two tools (`tests/py/test_check_vo_duration.py`, `tests/py/test_track_screen.py` if present; find with `ls tests/py | grep -E "vo_duration|track_screen"`)

Scope decision (made at plan time, deviates from the spec's "all 16"): the spec allows an allowlist with written reasons. These two tools only read a container duration or the first video stream size, which `vidkit.ff.probe` returns, so they migrate. The other 14 call sites use their own error classes, `-select_streams`, full stream JSON, or degrade-without-ffprobe paths; rewriting them is behaviour change beyond a gate ticket. They stay on `ffprobe_allow` with reasons, tracked as open debt for a follow-up ticket.

**Completeness:**
- Happy path: both tools get durations through `from tools.vidkit import ff` (`ff.duration`, `ff.probe(...)["video"]`).
- Error paths: `ff.FFError` (ffprobe missing or failing) must map to each tool's existing exit code and message; ffprobe missing must still exit as it does today.
- Edge cases: a file with no video stream (`probe()["video"]` is `None`); a file with no duration (`ff.duration` raises `FFError`); zero-length file.
- Observability: error messages keep their current text prefix so existing log greps still work.
- Tests: tools must still run as scripts: keep the `sys.path.insert(0, <repo root>)` idiom before `from tools.vidkit import ff` (tools-cli gate).

**Steps:**
1. Write failing test for `check_vo_duration` reading a clip duration through `vidkit.ff` (monkeypatch `ff.duration` to return 5.0 and assert the tool uses it). Expected error: `AttributeError: module 'tools.check_vo_duration' has no attribute 'ff'`.
2. Run the test, confirm it fails for the expected reason.
3. Replace the direct `subprocess` `ffprobe` call in `check_vo_duration.py` with `ff.duration`; translate `ff.FFError` to the tool's current error path.
4. Repeat steps 1–3 for `track_screen.py` (two call sites: first-video-stream size at line ~68, container duration at line ~77).
5. Delete both ids from `ffprobe_allow`; run the registry gate and `bash tests/run.sh`.
6. Commit: `refactor(GV-20): check_vo_duration and track_screen use vidkit.ff`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/check_vo_duration.py tools/track_screen.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] unit: `bash tests/run.sh consistency` passes (tools-cli `--help` still works for both)
- [ ] `grep -n ffprobe tools/check_vo_duration.py tools/track_screen.py` shows no direct call (comments allowed only if the gate still passes, otherwise reword)
- [ ] Same sample inputs give the same exit code and output as before the change (run both tools on one fixture from `tests/fixtures` and compare with `git stash`-free method: run on `main` checkout path `../../..`)
- [ ] No placeholder/TODO comments in new code

### Phase H: Reminder hook

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/registry_build.py` (add `suggest`)
- Create: `hooks/tool-reminder.sh` (executable)
- Modify: `hooks/hooks.json` (add PreToolUse entry)
- Test: `tests/py/test_registry.py` (suggest scoring), `tests/consistency/tool-reminder-hook.sh` (hook end to end)

**Hook contract (verbatim):**
- Registered as `"PreToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/tool-reminder.sh"}]}]`.
- stdin: `{"tool_name":"Write","tool_input":{"file_path":"...","content":"..."}}` (Edit uses `new_string`).
- Fires only if ALL hold: extension in `.py .mjs .sh`; path does NOT contain `/tools/`, `/tests/`, `/templates/` (path relative to the plugin root when it is inside it; any other absolute path counts as outside); text contains `ffmpeg`, `ffprobe` or `remotion` (case-insensitive).
- Output when firing: JSON `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"<text>"}}`, exit 0. `<text>` = "gaspol-video: tools that already do similar work:\n" + up to 3 lines `id — purpose` + "\nUse one, or extend tools/vidkit with a test and a registry row (docs/tool-routing.md). If none fits, say why in your reply." When no tool scores > 0, only the rule sentence.
- Output when not firing: nothing, exit 0.
- Any failure (registry unreadable, bad JSON on stdin, python3 missing): print nothing to stdout, one line to stderr `tool-reminder: <reason>`, exit 0. The hook must never block a write.
- Scoring (`suggest`): tokenise text into lowercase words `[a-z0-9]+`; for each tool score = 2 × (count of its `tasks` tokens present in the text) + 1 × (count of distinct ≥4-letter words of its `purpose` present in the text); `phase`, ids are not scored. Ties broken by registry order.

**Completeness:**
- Happy path: a Write of `/proj/scripts/join.py` containing `ffmpeg -f concat` prints suggestions that include the concat tool.
- Error paths: invalid stdin JSON; missing `tool_input`; registry missing; python3 absent.
- Edge cases: Edit tool (`new_string`); empty content; `.md` file with the word ffmpeg (must not fire); path inside `tools/` (must not fire); content with only the word `Remotion` capitalised; very large content (cap the scan at the first 200 KB).
- Observability: stderr line on every swallowed failure.

**Steps:**
1. Write failing test for `suggest` returning `tools/vidkit/join.py` (or the registered concat tool) first for the text `ffmpeg -f concat -i list.txt out.mp4`. Expected error: `SystemExit: 2` (unknown subcommand `suggest`).
2. Run the test, confirm it fails for the expected reason.
3. Implement `suggest` with the scoring above; run tests.
4. Write failing test `tests/consistency/tool-reminder-hook.sh`: pipes four sample JSON payloads into `hooks/tool-reminder.sh` and asserts (a) firing payload prints `additionalContext` and exits 0, (b) `.md` payload prints nothing, (c) payload path under `tools/` prints nothing, (d) garbage stdin prints nothing, exits 0, stderr non-empty. Expected error: `hooks/tool-reminder.sh: No such file or directory`.
5. Implement `hooks/tool-reminder.sh` (bash wrapper that calls `python3 "$CLAUDE_PLUGIN_ROOT/tools/registry_build.py" hook` or an inline `python3 -` using the importable functions; `chmod +x`), add the `hook` logic to `registry_build.py` if used, add the `hooks.json` entry. Run the new consistency test and `bash tests/run.sh`.
6. Commit: `feat(GV-20): write-time tool reminder hook`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/registry_build.py` passes; `bash -n hooks/tool-reminder.sh` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] unit: `bash tests/run.sh consistency` passes (includes tool-reminder-hook)
- [ ] `python3 -c "import json;json.load(open('hooks/hooks.json'))"` exits 0 and still contains the SessionStart entry
- [ ] Manual: `echo '{"tool_name":"Write","tool_input":{"file_path":"/tmp/x.py","content":"import subprocess; subprocess.run([\"ffmpeg\",\"-f\",\"concat\"])"}}' | CLAUDE_PLUGIN_ROOT=$PWD hooks/tool-reminder.sh` prints JSON with `additionalContext`
- [ ] No placeholder/TODO comments in new code

### Phase I: Docs, version 3.18.0, release gates

**Estimated time:** 15 minutes

**Files:**
- Modify: `CLAUDE.md` (Architecture rows for `tools/registry.json`, `tools/registry_build.py`, `hooks/tool-reminder.sh`; v3.18.0 changelog; version line; tool count 37 → 38 CLI tools; "Tool-first rule" paragraph mentions the registry)
- Modify: `README.md` (version line + changelog, per the plugin release rule)
- Modify: `.claude-plugin/plugin.json` (`"version": "3.18.0"`)
- Modify: `tests/consistency/tools-index.sh` (version needle `3.17.0` → `3.18.0`; also change its message)
- Modify: `docs/tool-routing.md` (intro: "this table is generated; edit `tools/registry.json`, then run `python3 tools/registry_build.py render`")
- Modify: any other test that hardcodes `3.17.0` (find with `grep -rn "3\.17\.0" tests .claude-plugin`)
- Modify: `docs/plans/2026-10-17-GV-20-tool-registry-spec.md` (amend: routes live in the registry; ffprobe migration scoped to 2 callers + 17 allowlisted; decisions made in planning)

**Completeness:**
- Happy path: all docs name the registry; version consistent in plugin.json, tests, README, CLAUDE.md.
- Error paths: a missed hardcoded version makes `bash tests/run.sh` fail; the grep in Verification catches it.
- Edge cases: `tools-index.sh` requires each new `tools/*.py` basename in CLAUDE.md (so `registry_build.py` must appear); marketplace manifest in the sibling `gaspol-one` repo is out of scope for this repo and is listed under open debt.
- Observability: changelog states what was NOT done (17 ffprobe callers remain allowlisted).

**Steps:**
1. Write failing test: update `tests/consistency/tools-index.sh` first to require `3.18.0`. Expected error: `FAIL plugin.json version is not 3.18.0`.
2. Run `bash tests/run.sh consistency`, confirm that exact failure.
3. Bump `plugin.json`, edit CLAUDE.md, README.md, routing-doc intro, spec amendment; grep and fix any other `3.17.0` pin.
4. Run `bash tests/run.sh` (all three groups); run `python3 tools/registry_build.py render --check`.
5. Run `graphify update .` in the worktree.
6. Commit: `docs(GV-20): registry docs, release 3.18.0`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/registry_build.py` passes
- [ ] unit: `bash tests/run.sh` passes (consistency, py, node)
- [ ] `grep -rn "3\.17\.0" tests .claude-plugin README.md CLAUDE.md` shows only historical changelog mentions
- [ ] `python3 tools/registry_build.py validate --coverage` and `render --check` both exit 0
- [ ] No placeholder/TODO comments in new code

## Open debt (named, not hidden)

- 17 ffprobe call sites remain on `ffprobe_allow` (listed with reasons in `tools/registry.json`): `burn_subs`, `clean_voice`, `composite`, `edit_render`, `gen_music`, `gen_vo`, `make_stems`, `mix_music`, `mix_sfx`, `overlay_plan`, `person_mask`, `probe_clips`, `qa_frames`, `registry_build`, `retention_gate`, `vidkit/color`, `voice_changer`. Follow-up ticket should migrate them one tool at a time with behaviour tests.
- Sibling repo `gaspol-one` marketplace.json version must be set to 3.18.0 at release (not in this repo).
- Duplicate detection is exact-match on (phase, task set). Near-duplicates (different tags, same job) are caught only by the hook's reminder and by review.

## Out of scope

Semantic or embedding search; blocking the write; cross-plugin checks (`gaspol-catalog` `deckkit`); rewriting tools beyond the two ffprobe swaps.
