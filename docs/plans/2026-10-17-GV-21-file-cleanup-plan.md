> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-21.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. Blocking, like a test gate. Never batch updates at the end. Update ONLY this file, never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. Every path, contract and convention needed is written here verbatim.

**Ticket:** GV-21
**Ledger:** .gaspol/progress/PROGRESS-GV-21.md
**Spec:** none. Bounded path: the design was approved in chat (section "Design as approved" below).

## Goal

Regenerating a paid asset (image, keyframe, clip) leaves junk behind: the old version is either
overwritten (a paid artefact lost) or left under a stray name or folder. The rules for where
things go exist only as prose in `reference/post-production/10-post-production-pipeline.md` §2,
and no tool enforces or cleans them. This ticket adds (A) an `archive` step in
`tools/renders.py` so the old version is moved into `_arsip/` with a reason BEFORE a re-render,
and (B) `python3 -m tools.vidkit tidy <project>`: a report-first cleaner for what is already
messy.

## Design as approved

- **A. Prevent at the source.** `renders.py <project> archive --file F [--reason R]` moves the
  existing file to `_arsip/<kind>-<stem>-v<N>-<reason><ext>`. Skills call it when `check`
  printed `render` and the file already exists. Nothing is deleted.
- **B. Cleaner.** New `tools/vidkit/tidy.py` + CLI `vidkit tidy`. No flag = report only (dry run).
  `--apply` moves unknown folders into `_arsip/`. `--empty-tmp` is the only deletion and it
  never touches `_arsip/`, `shots/out/` or unmoved MCP renders.
- **Out of scope (one line):** pixel-level automatic QA (face drift between scenes) from the
  chat question 1 is a separate topic; auto-deleting duplicates (we cannot know which copy is
  canonical) is not done, they are only reported.

## Architecture Context (from CLAUDE.md and the code, read before planning)

- `tools/renders.py` is stdlib-only. Ledger `{project}/renders.json` is `{"renders": [entry]}`;
  entry keys: `file` (project-relative path, e.g. `keyframes/scene-03.png`), `phase`
  (`4A|4B|5|6`), `status` (`done|failed|skipped`), `prompt_sha256`, `model`, `rendered_at`,
  optional `cdn_url`. `record()` replaces the entry with the same `file`. `main()` builds an
  argparse sub-command table; handlers are `_cmd_hash/_cmd_check/_cmd_record/_cmd_eligible`
  returning an int exit code. Existing tests: `tests/py/test_renders.py` (unittest).
- `tools/vidkit/` modules are imported in `tools/vidkit/__main__.py`
  (`from . import audiostudy, beats, ...`), each CLI command is `sub.add_parser(...)` in
  `main()` and dispatched in the big `try:` chain; `except (gates.GateError, ff.FFError, ...,
  ValueError, RuntimeError)` prints `FAIL: ...` and returns 1. Tests: `tests/py/test_vidkit.py`
  (unittest, imports `from tools.vidkit import ...`).
- Folder contract (pipeline doc §2, §2.1, §2.2): top-level folders of `{output_folder}`:
  `ref keyframes shots clips vo sfx work output _arsip .tmp`; CLAUDE.md also names `screens/`
  (`gen_app_screen.py`) and `packaging/` (`video-package`), so both are allowed too.
  `.tmp/` and `shots/out/` are the only deletable folders. `_arsip/` is deleted only when the
  user says so. MCP renders (`generate_image`/`generate_video`) write to `.tmp/image/` and
  `.tmp/video/` and are paid, so an unmoved file there must survive `--empty-tmp`.
- `docs/tool-routing.md` has a table `| I want to... | Use |`; new tools need a row there and in
  `docs/vidkit.md`. Rule: reusable code goes in the plugin, with a test, same session.
- Skills that run the render offer: `skills/video-image/SKILL.md` (lines ~295-345, ~486-513),
  `skills/video-gen/SKILL.md` (lines ~446-481), and the folder-contract paragraph in
  `video-image`, `video-gen`, `video-explainer`, `video-post`.
- Tests run with `bash tests/run.sh` (consistency `.sh` checks + `python3 -m unittest discover
  -s tests/py -t . -q` + node). `detect-stack` printed `unit: pytest`, but this repo has no
  pytest on purpose; the real unit command is `python3 -m unittest <module> -q`, and the full
  gate is `bash tests/run.sh`. `static:` and `lint:` printed UNKNOWN: this stdlib-only repo has
  no static checker, so the plan-declared check is `python3 -m py_compile <changed .py>`.
- **GV-20 is merged (main `e33f52a`, v3.18.0); this branch is rebased onto it.** Baseline after
  the rebase: `bash tests/run.sh` RESULT PASS. The `CLAUDE.md` `Last ticket:` conflict was
  resolved to `GV-21`. What GV-20 means for this ticket:
  1. **Version.** `main` is `3.18.0`. This ticket releases **`3.19.0`**.
     `tests/consistency/tools-index.sh` and `tests/consistency/plugin-identity.sh` hardcode the
     version and are bumped with the rest.
  2. **Registry is the source of routing.** `tools/registry.json` is
     `{"version", "tools": [...], "routes": [...], "ffprobe_allow": [...]}`.
     - Tool entry, exact keys: `{"id", "purpose", "tasks", "phase", "replaces",
       "distinct_because", "internal_reason"}`. Example already in the file:
       `{"id": "tools/vidkit/beats.py", "purpose": "...", "tasks": ["beat-detect", "beat-snap",
       "music-grid"], "phase": "shared", "replaces": [], "distinct_because": "",
       "internal_reason": ""}`.
     - Route entry, exact keys: `{"task": "<I want to...>", "use": "<markdown command>",
       "tools": ["<tool id>", ...]}`.
     - The table in `docs/tool-routing.md` between `<!-- registry:routes:begin -->` and
       `<!-- registry:routes:end -->` is generated by `python3 tools/registry_build.py render`.
       Never edit it by hand: `render --check` reports drift and exits 1.
  3. **Gates that bite this ticket** (`tests/consistency/tool-registry-contract.sh`, part of the
     `consistency` group of `bash tests/run.sh`, NOT of the `py` group):
     - Coverage: every `tools/vidkit/*.py` must be in `tools[]`, and must be named in some
       route's `tools` or carry a non-empty `internal_reason`. So the moment `tidy.py` exists,
       the full gate fails until it is registered AND routed. Therefore registration happens in
       the same phase that creates the file (Phase B), not in Phase D.
     - Duplicate: two tools with the same `phase` and the same `tasks` set need
       `distinct_because` or `replaces`. `tidy.py`'s task set must not equal any other tool's.
     - ffprobe ratchet: `tidy.py` must not call `ffprobe` (it does not need to).
  4. **Reminder hook** `hooks/tool-reminder.sh` only fires on files outside `tools/`, `tests/`,
     `templates/`; it does not affect this ticket.

## Tech Stack

Python 3 stdlib only (`argparse`, `hashlib`, `json`, `os`, `pathlib`, `re`, `shutil`, `time`),
`unittest`, bash consistency checks. No new dependency.

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Archive old render | `{project}/<file>` on disk + `renders.json` entry (`phase`) | `tools/renders.py` (`load`, `record`) | Yes | Add `archive_file()` + `archive` sub-command |
| Archive name reason | CLI `--reason` | argparse | Yes | Slugify, default `diganti` |
| Scan folders | real directory listing of `{project}` | `os.scandir` | Yes | New `tidy.scan()` |
| Duplicate detection | real file bytes (sha256, size-grouped) | `hashlib` | Yes | New `tidy.duplicates()` |
| Stale ledger entries | `renders.json` via `renders.load()` | `tools/renders.py` | Yes | Import `tools.renders` from `tidy` |
| Old `.tmp` files | file mtime | `os.stat` | Yes | New `tidy.old_tmp()` |
| Stray subfolders | real listing of `ref keyframes clips vo sfx _arsip output` | `os.scandir` | Yes | `unknown_subdirs` in `scan()` |
| MCP copy already home | sha256 of `.tmp/image` and `.tmp/video` media vs `DUP_DIRS` index | `hashlib` | Yes | `mcp_already_home` in `scan()` |
| Tool + route registration | `tools/registry.json` | `tools/registry_build.py render`, `validate --coverage` | Yes (GV-20, merged) | Extend `tools/renders.py` entry (Phase A), add `tools/vidkit/tidy.py` entry + route (Phase B) |
| CLI `tidy` | argv | `tools/vidkit/__main__.py` | Yes | Add parser + dispatch |
| Skill instructions | `skills/*/SKILL.md` | n/a | Yes | Add lines |
| Routing docs | `docs/tool-routing.md` (generated), `docs/vidkit.md`, pipeline doc §2.4 | n/a | Yes | Regenerate table; add vidkit row and §2.4 by hand |

No placeholder anywhere: every row reads or writes the real file system or the real ledger.

## Phases

Every phase: commit at the end with the message shown; commit trailer
`Co-Authored-By: <the model that wrote the code> <noreply@anthropic.com>` (the executing agent's
own model name, e.g. `Claude Opus 5.5` or `Claude Sonnet 5.5`; do not copy a name blindly).

### Phase A: `renders.py archive`

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/renders.py`, `tools/registry.json`, `docs/tool-routing.md` (regenerated, not hand-edited)
- Test: `tests/py/test_renders.py`

**Registry (write exactly this):** in the existing `tools/renders.py` tool entry, append
`"render-archive"` to `tasks` (giving `["render-ledger", "prompt-hash", "eligibility",
"render-archive"]`). Add one route to `routes`:

```json
{"task": "Re-render a paid asset without losing the old one",
 "use": "`python3 tools/renders.py <project> archive --file F --reason R` (moves the old file into `_arsip/` before the new render)",
 "tools": ["tools/renders.py"]}
```

Then `python3 tools/registry_build.py render`.

**Contract (write exactly this):**
- `ARCHIVE_DIR = "_arsip"`.
- `archive_file(project, file, reason="", phase=None) -> Path | None`:
  - `src = Path(project) / file`. Resolve both; if `src` resolves outside `project` raise
    `ValueError("file escapes project: ...")`. If `src` is a symlink or a directory raise
    `ValueError`. If `src` does not exist return `None`.
  - kind: from `phase` (`4A`→`gambar`, `4B`→`keyframe`, `5`→`klip`, `6`→`audio`); when
    `phase` is None look up the ledger entry for `file`; if still unknown use the extension
    (`.mp4`/`.mov` → `klip`, `.mp3`/`.wav` → `audio`, else `gambar`).
  - reason slug: lowercase, every run of non `[a-z0-9]` → `-`, strip `-`, cut to 40 chars,
    empty → `diganti`.
  - destination `_arsip/<kind>-<stem>-v<N>-<slug><ext>`, `N` = (largest `M` among files in
    `_arsip/` matching `re.escape(f"{kind}-{stem}-v") + r"(\d+)-"` at the start of the name) + 1,
    or 1 when none match. Numbers only go up, so a higher `v` is always the more recent archive,
    even after someone deletes an older one. Create `_arsip/` if missing. If the computed
    destination exists anyway, raise `ValueError` (never overwrite). Move with `os.replace`.
    Return the destination.
- CLI: `renders.py <project> archive --file F [--reason R]` prints
  `archived <file> -> _arsip/<name>` or `nothing to archive: <file>`; exit 0 both. A
  `ValueError` prints `renders: <msg>` to stderr, exit 1.
- The ledger entry is NOT touched by `archive`; the following `record` replaces it.

**Steps:**
1. Write failing test for `archive_file` moving `keyframes/scene-03.png` to `_arsip/keyframe-scene-03-v1-prompt-berubah.png`. Expected error: `AttributeError: module 'tools.renders' has no attribute 'archive_file'`
2. Run test, confirm it fails for the expected reason: `python3 -m unittest tests.py.test_renders -q`
3. Implement `archive_file` and `_slug` in `tools/renders.py`
4. Run the test, confirm it passes
5. Write failing tests for each edge case (one test each; see the list below), confirm each fails, then make them pass
6. Add the `archive` sub-parser and `_cmd_archive` handler, plus a CLI test using `renders.main([...])` and capturing stdout
7. Update the module docstring (add `python3 tools/renders.py <project> archive --file F [--reason R]`)
8. Registry: add the task and route above, run `python3 tools/registry_build.py render`, then `python3 tools/registry_build.py validate --coverage` and `python3 tools/registry_build.py render --check` (both exit 0)
9. Full gate: `bash tests/run.sh` RESULT PASS
10. Commit: `feat(GV-21): renders.py archive moves a superseded render into _arsip`

**Error paths covered (each a test):** file escapes project (`../x.png`, absolute path outside);
file is a directory; file is a symlink; `renders.json` invalid JSON while looking up the phase
(fall back to the extension, do not crash).
**Edge cases covered (each a test):** file missing → `None`; second archive of the same stem →
`v2`; third → `v3`; `v1` removed from `_arsip/` leaves `v2` present → next is `v3` (never
reuses `v1`); `keyframe-scene-03-v10-x.png` present → next is `v11` (numeric, not string, max);
a stem that is a prefix of another (`scene-0` vs `scene-03`) does not share numbering; empty reason
→ `diganti`; reason `"Prompt Berubah!! / wajah"` → `prompt-berubah-wajah`; reason longer than 40
chars is cut; `_arsip/` absent → created; non-ASCII reason → slug without it; `phase` given
overrides ledger lookup; extension fallback for `.mp4`, `.wav`, `.png`.
**Observability:** the CLI always prints one line saying what moved where, so a skill transcript
shows it.
**Concurrency:** not applicable, with the reason: a project folder is driven by one session at a
time, and `os.replace` is atomic for the single move.

**Verification:**
- [ ] static: no checker configured for this stdlib repo; `python3 -m py_compile tools/renders.py` passes
- [ ] unit: `python3 -m unittest tests.py.test_renders -q` passes
- [ ] Moving a real temp file keeps its bytes (test compares sha256 before and after)
- [ ] registry: `validate --coverage` and `render --check` exit 0; the generated table in `docs/tool-routing.md` has the archive row
- [ ] No placeholder/TODO comments in new code

### Phase B: `tidy` scan (report only, no writes)

**Estimated time:** 25 minutes

**Files:**
- Create: `tools/vidkit/tidy.py`
- Modify: `tools/registry.json`, `docs/tool-routing.md` (regenerated)
- Test: `tests/py/test_vidkit.py` (new class `TidyScanTest`)

**Contract (write exactly this):**
- Constants: `CONTRACT_DIRS = {"ref", "keyframes", "shots", "clips", "vo", "sfx", "work", "output", "_arsip", ".tmp", "screens", "packaging"}`; `DUP_DIRS = ("ref", "keyframes", "clips", "vo", "sfx", "output", "_arsip")` (never walk `shots/`, it holds `node_modules`); `MCP_SUBDIRS = (".tmp/image", ".tmp/video")`; `MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".mp3", ".wav"}`.
- `FLAT_DIRS = ("ref", "keyframes", "clips", "vo", "sfx", "_arsip")`: folders that must hold
  files only. `ALLOWED_SUBDIRS = {"output": {"stems"}}`. Every other contract folder (`shots`,
  `work`, `screens`, `packaging`, `.tmp`, and `output` beyond `stems`) is not checked for
  subfolders except `output`. Reason: pipeline doc §2.3 records the real damage as subfolders
  INSIDE contract folders (`keyframes/_up/`, `clips/_ov/`, `clips/_final/`, `keyframes/_gen/`),
  not as new top-level folders, and §2.1 says variants are a filename suffix, never a subfolder.
- `scan(project, tmp_days=7, now=None) -> dict` with keys, all lists of strings
  (paths relative to `project`, sorted):
  - `unknown_dirs`: top-level directories not in `CONTRACT_DIRS` and not starting with `.`
    (other dotted dirs like `.git` are ignored; `.tmp` is in the contract).
  - `unknown_subdirs`: direct sub-directories of each `FLAT_DIRS` folder, plus sub-directories
    of `output/` not in `ALLOWED_SUBDIRS["output"]` (e.g. `keyframes/_up`, `clips/_ov`,
    `output/old`). One level deep is enough: moving the subfolder moves everything below it.
    Symlinked sub-directories are listed (they break the rule too) but never followed.
  - `duplicates`: list of lists, each a group of ≥ 2 files in `DUP_DIRS` with identical sha256
    (group by size first; skip size 0; symlinks not followed; an unreadable file goes to
    `unreadable`, never raises).
  - `stale_ledger`: `renders.json` entries with status `done` whose `file` does not exist.
  - `old_tmp`: files under `.tmp/` with mtime older than `tmp_days` days (`now` injectable).
  - `unmoved_mcp`: media files (by `MEDIA_EXT`) under `MCP_SUBDIRS` whose bytes do NOT match any
    file in `DUP_DIRS`: paid renders still waiting to be moved to their home.
  - `mcp_already_home`: media files under `MCP_SUBDIRS` whose sha256 equals a file in
    `DUP_DIRS` (it was copied, not moved). Each entry is `"<tmp path> = <home path>"`. These are
    safe to delete because the paid bytes live on in their home. Reuses the same size-then-sha256
    index as `duplicates` (one hashing pass, no second read of the home files).
  - `unreadable`: files that could not be read.
- `.tmp` itself being a symlink raises `ValueError(".tmp is a symlink: ...")`, both in `scan` and
  in `empty_tmp`, because emptying it would empty the link's target outside the project.
- `format_report(report) -> str`: one section per non-empty key, a count line each, and a
  final line `clean` when everything is empty. Plain words, no jargon.
- Uses `tools.renders.load` for the ledger; a `RenderLedgerError` becomes a report entry
  `stale_ledger = ["renders.json: <message>"]`, never a crash.
- A `project` that is not a directory raises `ValueError("not a directory: ...")`.

**Registry (write exactly this, in this phase, because the coverage gate fails as soon as
`tidy.py` exists):** add to `tools`:

```json
{"id": "tools/vidkit/tidy.py",
 "purpose": "Report and clean a project folder: stray folders and subfolders, duplicate files, stale ledger entries, old .tmp files, MCP renders not moved home.",
 "tasks": ["folder-tidy", "stray-folders", "tmp-cleanup"],
 "phase": "shared", "replaces": [], "distinct_because": "", "internal_reason": ""}
```

The task tags are unused by any other tool (checked on main `e33f52a`: only `clean` and
`duplicates` exist, on other tools), so the duplicate gate passes. Add to `routes`:

```json
{"task": "Keep the project folder clean / find stray folders and duplicates",
 "use": "`python3 -m tools.vidkit tidy <project>` (report only; `--apply` moves strays to `_arsip/`, `--empty-tmp` empties `.tmp/`)",
 "tools": ["tools/vidkit/tidy.py"]}
```

The route names the CLI that Phase C adds; both land before release, and the route text is
what the gate and the reminder hook read, not an executed command. Then
`python3 tools/registry_build.py render`.

**Steps:**
1. Write failing test for `tidy.scan` reporting an unknown top-level folder `_up/`. Expected error: `ImportError: cannot import name 'tidy' from 'tools.vidkit'`
2. Run test, confirm it fails for the expected reason: `python3 -m unittest tests.py.test_vidkit.TidyScanTest -q`
3. Implement `tidy.py` with `scan` (unknown dirs first)
4. Add one failing test + implementation per remaining key: `unknown_subdirs`, `duplicates`, `stale_ledger`, `old_tmp`, `unmoved_mcp`, `mcp_already_home`, `unreadable`; plus the `.tmp` symlink `ValueError`
5. Add `format_report` with its test (empty report → `clean`)
6. Registry: add the tool entry and route above, `python3 tools/registry_build.py render`, then `validate --coverage` and `render --check` (both exit 0)
7. Full gate: `bash tests/run.sh` RESULT PASS
8. Commit: `feat(GV-21): vidkit tidy scan reports unknown folders, duplicates, stale entries, old tmp`

**Error paths covered:** project missing or a file → `ValueError`; `.tmp` is a symlink →
`ValueError`; invalid `renders.json` → reported, not raised; unreadable file (chmod 000 in a temp
dir; skip the test when running as root) → in `unreadable`.
**Edge cases covered:** empty project → `clean`; dotted dir `.git` ignored; a dir symlink at top
level is not followed; two identical files, three identical files (one group of 3), two files
same size but different bytes (no group), zero-byte files (ignored); `shots/node_modules`
never walked (test plants a duplicate pair inside it and expects no group); file exactly
`tmp_days` old is not old, one second older is; `.tmp/image/a.png` in `unmoved_mcp` but
`.tmp/a.png` is not; non-media file in `.tmp/image/` not in `unmoved_mcp`; ledger entry with
status `failed` and missing file is not stale; ledger entry whose file exists is not stale;
`keyframes/_up/` and `clips/_ov/` in `unknown_subdirs`; `output/stems/` not listed, `output/old/`
listed; `shots/src/` and `work/x/` not listed; a file (not dir) directly in `keyframes/` not
listed; `.tmp/image/a.png` identical to `keyframes/scene-01.png` → in `mcp_already_home`, NOT in
`unmoved_mcp`; same name but different bytes → in `unmoved_mcp`, not in `mcp_already_home`;
a `.tmp/image` file identical to a home file is not reported as a `duplicates` group (`.tmp` is
not a `DUP_DIRS` member).
**Observability:** `format_report` is the output a person reads; it names every path.
**Concurrency:** not applicable, with the reason: read-only scan.

**Verification:**
- [ ] static: no checker configured for this stdlib repo; `python3 -m py_compile tools/vidkit/tidy.py` passes
- [ ] unit: `python3 -m unittest tests.py.test_vidkit.TidyScanTest -q` passes
- [ ] The scan makes zero writes (a test snapshots the temp tree before and after and compares)
- [ ] registry: `validate --coverage` and `render --check` exit 0; `bash tests/run.sh` PASS
- [ ] No placeholder/TODO comments in new code

### Phase C: `tidy --apply`, `--empty-tmp`, and the CLI

**Estimated time:** 20 minutes

**Files:**
- Modify: `tools/vidkit/tidy.py`, `tools/vidkit/__main__.py`
- Test: `tests/py/test_vidkit.py` (class `TidyApplyTest`, CLI test)

**Contract (write exactly this):**
- `apply_unknown_dirs(project, report) -> list[tuple[str, str]]`: moves each `unknown_dirs`
  entry `X` to `_arsip/folder-X`, and each `unknown_subdirs` entry `P/X` to
  `_arsip/folder-P-X` (e.g. `keyframes/_up` → `_arsip/folder-keyframes-_up`); when the
  destination exists, `-2`, `-3`, … are appended. Never overwrites. Creates `_arsip/` if missing.
  A symlinked entry is moved as the link itself (`os.replace` on the link), the target is
  untouched. Returns `(src, dst)` pairs (relative).
- `empty_tmp(project, include_mcp=False) -> dict` returns
  `{"deleted": [...], "kept_mcp": [...]}`: first calls `scan` to get `mcp_already_home` and
  `unmoved_mcp`. Deletes every file and sub-folder inside `.tmp/` (keeps `.tmp/` itself)
  EXCEPT the `unmoved_mcp` files, which are kept and listed in `kept_mcp` unless
  `include_mcp=True`. `mcp_already_home` files ARE deleted by default (their bytes exist in their
  home). Empty sub-folders left over are removed. A missing `.tmp/` → empty result, no error.
  `.tmp` that is a symlink → `ValueError` before anything is deleted. Never follows symlinks
  inside `.tmp/` (a symlink is unlinked, its target untouched). Never touches anything outside
  `.tmp/`.
- CLI in `__main__.py`: `tidy <project> [--tmp-days N] [--apply] [--empty-tmp] [--include-mcp]`.
  No flag → print `format_report(scan(...))`, exit 0, change nothing. `--apply` → move unknown
  dirs and subdirs, print each `moved A -> B`, or `nothing to move`. `--empty-tmp` → run
  `empty_tmp`, print the deleted count, each deleted already-home copy as
  `deleted <tmp> (copy of <home>)`, and each kept MCP file with the words
  `paid render not moved yet, kept`. `--apply --empty-tmp` together is allowed and runs in that
  order: move first, then empty. `--apply` never touches `.tmp/` (it is a contract folder), and
  `empty_tmp` re-scans after the move, so the already-home check sees the final layout.
  `--include-mcp` without `--empty-tmp` → argparse error (exit 2). `ValueError` from `scan`
  or `empty_tmp` → the existing `FAIL: ...` path, exit 1.
- `_arsip/`, `shots/out/` and every contract folder other than `.tmp/` are never deleted or
  emptied by any flag.

**Steps:**
1. Write failing test for `apply_unknown_dirs` moving `_up/` to `_arsip/folder-_up`. Expected error: `AttributeError: module 'tools.vidkit.tidy' has no attribute 'apply_unknown_dirs'`
2. Run test, confirm it fails for the expected reason
3. Implement `apply_unknown_dirs`; make the test pass
4. Write failing tests for `empty_tmp` (below), implement it, make them pass
5. Write failing CLI tests (dry run changes nothing; `--apply`; `--empty-tmp`; bad flag combination), then add the parser and dispatch in `__main__.py` (import `tidy` in the `from . import ...` line)
6. Run the full gate: `bash tests/run.sh` (py AND consistency, so the registry gate is checked too)
7. Commit: `feat(GV-21): vidkit tidy --apply and --empty-tmp`

**Error paths covered:** `--include-mcp` without `--empty-tmp`; project not a directory; `.tmp`
missing; `.tmp` is a symlink to a folder outside the project (`ValueError`, the target folder's
files all survive, sha256 compared); destination `_arsip/folder-X` already exists (suffix, no
overwrite).
**Edge cases covered:** no unknown dirs → `--apply` prints `nothing to move`; two unknown dirs
with the same name cannot exist, but `_up` and `_arsip/folder-_up` both existing → `-2`;
`keyframes/_up/a.png` → `_arsip/folder-keyframes-_up/a.png` with bytes kept; `keyframes/_up` and
`clips/_up` both present → two distinct destinations; a symlinked subdir is moved as a link, its
target untouched; `.tmp` holding a file, a nested folder and a symlink to a file outside the
project (the target survives); `.tmp/image/a.png` with no home copy kept by default, deleted with
`--include-mcp`; `.tmp/image/a.png` identical to `keyframes/scene-01.png` deleted by default and
`keyframes/scene-01.png` untouched; `.tmp/image/notes.txt` (non-media) deleted; `_arsip/` content
untouched after `--empty-tmp` (sha256 compared); `shots/out/` untouched; `--apply --empty-tmp`
in one run does both in that order; running `--empty-tmp` twice is a no-op the second time.
**Observability:** every move and every kept file is printed; the deleted count is printed.
**Concurrency:** not applicable, with the reason: one session drives a project; stated in the
help text ("do not run while a render is writing to `.tmp/`").

**Verification:**
- [ ] static: no checker configured for this stdlib repo; `python3 -m py_compile tools/vidkit/tidy.py tools/vidkit/__main__.py` passes
- [ ] unit: `bash tests/run.sh` passes (all groups)
- [ ] `python3 -m tools.vidkit tidy --help` lists the four flags
- [ ] Dry run on a real messy temp project prints a report and leaves the tree identical
- [ ] No placeholder/TODO comments in new code

### Phase D: skills, docs, routing, consistency check, release

**Estimated time:** 25 minutes

**Gate before starting:** `git log main --oneline -1`. If `main` moved past `e33f52a` since this
plan, `git rebase main`, then `bash tests/run.sh` must PASS before any edit.

**Files:**
- Modify: `skills/video-image/SKILL.md`, `skills/video-gen/SKILL.md`, `skills/video-post/SKILL.md`, `skills/video-explainer/SKILL.md`, `docs/vidkit.md`, `reference/post-production/10-post-production-pipeline.md`, `CLAUDE.md`, `CHANGELOG.md`, `README.md`, `.claude-plugin/plugin.json`, `tests/consistency/tools-index.sh`, `tests/consistency/plugin-identity.sh` (the files holding `3.18.0`; confirm with `grep -rlF "3.18.0" . --include='*.json' --include='*.md' --include='*.sh' | grep -v docs/plans`, quoting the globs because zsh expands them)
- Not modified by hand: `docs/tool-routing.md` (its table was regenerated in Phases A and B) and `tools/registry.json` (entries already added in Phases A and B)
- Create: `tests/consistency/tidy-contract.sh`

**Text to add (adapt wording to each file's voice, keep it to one short paragraph each):**
- `video-image` and `video-gen`, in the render offer right after a `check` that printed
  `render`: "If `{output_folder}/<file>` already exists, run
  `python3 tools/renders.py {output_folder} archive --file <file> --reason "<why it is re-rendered>"`
  BEFORE the render, so the old paid version is kept in `_arsip/` instead of overwritten.
  Then render, then `record`."
- `video-image`, `video-gen`, `video-post`, `video-explainer`, in the folder-contract paragraph,
  and at the end of each batch: "Run `python3 -m tools.vidkit tidy {output_folder}` (report
  only) and show the user anything it lists."
- Same four folder-contract paragraphs: the heading says "nine folders" and the list omits
  `sfx/`, while pipeline doc §2 has `sfx/` (Phase 6 cues) and `CLAUDE.md` names `screens/` and
  `packaging/`. Make the paragraph match `CONTRACT_DIRS` exactly: list `ref/ keyframes/ shots/
  clips/ vo/ sfx/ work/ output/ _arsip/ .tmp/ screens/ packaging/`, change the heading count to
  match (twelve), and add "subfolders are not allowed inside `ref/ keyframes/ clips/ vo/ sfx/
  _arsip/`; `output/` allows only `stems/`". Check pipeline doc §2/§2.1 says the same; if its
  list differs, fix it in the same commit so the doc, the skills and `tidy.py` agree.
- Routing: nothing to add here; both routes went into `tools/registry.json` in Phases A and B.
  Only re-run `python3 tools/registry_build.py render --check` to confirm no drift.
- `docs/vidkit.md` table: row `tidy` ("scan, move unknown folders to `_arsip/`, empty `.tmp/`
  except unmoved MCP renders").
- Pipeline doc: new `### 2.4 Cleaning up` after §2.3: the three commands, what `--apply` moves
  (unknown top-level folders and subfolders inside flat folders, into `_arsip/folder-...`), what
  `--empty-tmp` can delete (only `.tmp/` content; an MCP render is deleted only when the same
  bytes already sit in its home, otherwise kept unless `--include-mcp`), and that `_arsip/` is
  never touched.
- `CLAUDE.md`: Architecture table gets a `tools/vidkit/tidy.py` mention in the `tools/vidkit/`
  row and the `renders.py` row mentions `archive`; Version + Last Updated; a `v3.19.0` changelog
  entry; the GV-20 changelog counts "62 tool entries, 61 routes" stay as history, the new entry
  states the new totals (63 tool entries, 63 routes; confirm by counting `tools` and `routes` in
  `tools/registry.json`); tool counts elsewhere only if the repo counts them in text you edited.
- `CHANGELOG.md` and `README.md` (version line + changelog): matching `3.19.0` entry.
- Version: `.claude-plugin/plugin.json`, `tests/consistency/tools-index.sh`,
  `tests/consistency/plugin-identity.sh`, `README.md`, `CLAUDE.md` all to `3.19.0`. If the
  marketplace file in the parent `gaspol-one` repo lists this plugin's version, report it to the
  user as a follow-up; it is outside this repo.

**Consistency check `tests/consistency/tidy-contract.sh`:** model it on the nearest existing
script in `tests/consistency/` (read one first, keep its output style). It must `exit 1` with a
message naming the file when any of these is missing: `archive --file` in `video-image` and
`video-gen` SKILL.md; `vidkit tidy` in those two plus `video-post` and `video-explainer`; `sfx/`
in the folder-contract paragraph of all four skills; `vidkit tidy` and `archive --file` in the
generated table of `docs/tool-routing.md`; `"tools/vidkit/tidy.py"` and `"render-archive"` in
`tools/registry.json`; `### 2.4` in the pipeline doc.

**Steps:**
1. Write failing test: create `tests/consistency/tidy-contract.sh` as above. Expected error: the script exits 1 naming `skills/video-image/SKILL.md` as missing `archive --file`
2. Run it, confirm it fails for that reason: `bash tests/consistency/tidy-contract.sh`
3. Edit the two render-offer skills (`video-image`, `video-gen`), including the folder-contract paragraph
4. Edit `video-post` and `video-explainer`, including the folder-contract paragraph
5. Edit `docs/vidkit.md` and the pipeline doc §2.4 (and §2/§2.1 if its folder list differs)
6. Run the consistency check, confirm it passes; also `bash tests/consistency/tool-registry-contract.sh`
7. Edit `CLAUDE.md`, `CHANGELOG.md`, `README.md`, version files to `3.19.0` (the existing version-gate consistency checks fail until all agree; run `bash tests/run.sh consistency`)
8. Run the full gate: `bash tests/run.sh` and record the counts
9. Commit: `feat(GV-21): skills, docs and release v3.19.0 for tidy and archive`

**Error paths covered:** the consistency script fails loudly per missing item (not just the
first); the version gates catch a half-done bump.
**Edge cases covered:** the `video-explainer` skill has no render offer, so it gets only the
`tidy` line; `video-post` likewise.
**Observability:** not applicable, with the reason: docs and a check script; the script prints
which file lacks which text.
**Concurrency:** a newer `main` is handled by the gate at the top of this phase.

**Verification:**
- [ ] static: no checker configured for this stdlib repo; `bash -n tests/consistency/tidy-contract.sh` passes
- [ ] unit: `bash tests/run.sh` passes (all groups)
- [ ] `grep -rn "archive --file" skills/video-image/SKILL.md skills/video-gen/SKILL.md` finds both
- [ ] Real end-to-end by hand in a temp project: make `keyframes/scene-01.png`, run
      `renders.py <tmp> archive --file keyframes/scene-01.png --reason "wajah beda"`, see it in
      `_arsip/`; create `_up/x.png` and `keyframes/_ov/y.png`, run `vidkit tidy <tmp>` (report
      lists both), then `--apply` (both moved); copy `keyframes/scene-01.png` to
      `.tmp/image/scene-01.png`, run `--empty-tmp`, see the copy deleted and the home file kept
- [ ] `python3 tools/registry_build.py validate --coverage` and `render --check` exit 0; registry holds 63 tools and 63 routes
- [ ] No placeholder/TODO comments in new code or docs

## Out of scope

Pixel-based image/video QA; auto-removal of duplicates; deleting `_arsip/`; changing where MCP
renders land (stays `.tmp/`).

## Red-flag self-check

Data Integration Map present; every phase has TDD step 1 in the required form, a Verification
block and its owed error/edge/observability/concurrency answers; CLAUDE.md read; the
self-contained header is present.
