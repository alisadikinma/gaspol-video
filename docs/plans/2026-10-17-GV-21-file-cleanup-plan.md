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
- **Coordination:** branch `GV-20-tool-registry` (worktree `.claude/worktrees/gv-20-tool-registry`)
  adds `tools/registry.json`, `tools/registry_build.py`, `tests/py/test_registry.py` and edits
  `CLAUDE.md`; it does not touch `tools/vidkit/__main__.py` or `tools/renders.py`. If GV-20 has
  merged into `main` before this ticket merges, rebase, then register `vidkit tidy` and
  `renders.py archive` in the registry the way
  `docs/plans/2026-10-17-GV-20-tool-registry-plan.md` specifies, and re-run `bash tests/run.sh`.
  The `CLAUDE.md` line `Last ticket:` is set to `GV-21` in this worktree; a conflict there with
  GV-20 (`GV-20`) resolves to the higher number, `GV-21`.

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
| CLI `tidy` | argv | `tools/vidkit/__main__.py` | Yes | Add parser + dispatch |
| Skill instructions | `skills/*/SKILL.md` | n/a | Yes | Add lines |
| Routing docs | `docs/tool-routing.md`, `docs/vidkit.md`, pipeline doc §2.4 | n/a | Yes | Add rows/section |

No placeholder anywhere: every row reads or writes the real file system or the real ledger.

## Phases

Every phase: commit at the end with the message shown; commit trailer
`Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

### Phase A: `renders.py archive`

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/renders.py`
- Test: `tests/py/test_renders.py`

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
  - destination `_arsip/<kind>-<stem>-v<N>-<slug><ext>`, `N` = smallest integer ≥ 1 such that
    no file in `_arsip/` starts with `<kind>-<stem>-v<N>-`. Create `_arsip/` if missing. Move
    with `os.replace`. Return the destination.
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
8. Commit: `feat(GV-21): renders.py archive moves a superseded render into _arsip`

**Error paths covered (each a test):** file escapes project (`../x.png`, absolute path outside);
file is a directory; file is a symlink; `renders.json` invalid JSON while looking up the phase
(fall back to the extension, do not crash).
**Edge cases covered (each a test):** file missing → `None`; second archive of the same stem →
`v2`; third → `v3`; `v1` removed from `_arsip/` leaves `v2` present → next is `v1`; empty reason
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
- [ ] No placeholder/TODO comments in new code

### Phase B: `tidy` scan (report only, no writes)

**Estimated time:** 20 minutes

**Files:**
- Create: `tools/vidkit/tidy.py`
- Test: `tests/py/test_vidkit.py` (new class `TidyScanTest`)

**Contract (write exactly this):**
- Constants: `CONTRACT_DIRS = {"ref", "keyframes", "shots", "clips", "vo", "sfx", "work", "output", "_arsip", ".tmp", "screens", "packaging"}`; `DUP_DIRS = ("ref", "keyframes", "clips", "vo", "sfx", "output", "_arsip")` (never walk `shots/`, it holds `node_modules`); `MCP_SUBDIRS = (".tmp/image", ".tmp/video")`; `MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".mp3", ".wav"}`.
- `scan(project, tmp_days=7, now=None) -> dict` with keys, all lists of strings
  (paths relative to `project`, sorted):
  - `unknown_dirs`: top-level directories not in `CONTRACT_DIRS` and not starting with `.`
    (other dotted dirs like `.git` are ignored; `.tmp` is in the contract).
  - `duplicates`: list of lists, each a group of ≥ 2 files in `DUP_DIRS` with identical sha256
    (group by size first; skip size 0; symlinks not followed; an unreadable file goes to
    `unreadable`, never raises).
  - `stale_ledger`: `renders.json` entries with status `done` whose `file` does not exist.
  - `old_tmp`: files under `.tmp/` with mtime older than `tmp_days` days (`now` injectable).
  - `unmoved_mcp`: media files (by `MEDIA_EXT`) under `MCP_SUBDIRS`: paid renders still waiting
    to be moved to their home.
  - `unreadable`: files that could not be read.
- `format_report(report) -> str`: one section per non-empty key, a count line each, and a
  final line `clean` when everything is empty. Plain words, no jargon.
- Uses `tools.renders.load` for the ledger; a `RenderLedgerError` becomes a report entry
  `stale_ledger = ["renders.json: <message>"]`, never a crash.
- A `project` that is not a directory raises `ValueError("not a directory: ...")`.

**Steps:**
1. Write failing test for `tidy.scan` reporting an unknown top-level folder `_up/`. Expected error: `ImportError: cannot import name 'tidy' from 'tools.vidkit'`
2. Run test, confirm it fails for the expected reason: `python3 -m unittest tests.py.test_vidkit.TidyScanTest -q`
3. Implement `tidy.py` with `scan` (unknown dirs first)
4. Add one failing test + implementation per remaining key: `duplicates`, `stale_ledger`, `old_tmp`, `unmoved_mcp`, `unreadable`
5. Add `format_report` with its test (empty report → `clean`)
6. Commit: `feat(GV-21): vidkit tidy scan reports unknown folders, duplicates, stale entries, old tmp`

**Error paths covered:** project missing or a file → `ValueError`; invalid `renders.json` →
reported, not raised; unreadable file (chmod 000 in a temp dir; skip the test when running as
root) → in `unreadable`.
**Edge cases covered:** empty project → `clean`; dotted dir `.git` ignored; a dir symlink at top
level is not followed; two identical files, three identical files (one group of 3), two files
same size but different bytes (no group), zero-byte files (ignored); `shots/node_modules`
never walked (test plants a duplicate pair inside it and expects no group); file exactly
`tmp_days` old is not old, one second older is; `.tmp/image/a.png` in `unmoved_mcp` but
`.tmp/a.png` is not; non-media file in `.tmp/image/` not in `unmoved_mcp`; ledger entry with
status `failed` and missing file is not stale; ledger entry whose file exists is not stale.
**Observability:** `format_report` is the output a person reads; it names every path.
**Concurrency:** not applicable, with the reason: read-only scan.

**Verification:**
- [ ] static: no checker configured for this stdlib repo; `python3 -m py_compile tools/vidkit/tidy.py` passes
- [ ] unit: `python3 -m unittest tests.py.test_vidkit.TidyScanTest -q` passes
- [ ] The scan makes zero writes (a test snapshots the temp tree before and after and compares)
- [ ] No placeholder/TODO comments in new code

### Phase C: `tidy --apply`, `--empty-tmp`, and the CLI

**Estimated time:** 20 minutes

**Files:**
- Modify: `tools/vidkit/tidy.py`, `tools/vidkit/__main__.py`
- Test: `tests/py/test_vidkit.py` (class `TidyApplyTest`, CLI test)

**Contract (write exactly this):**
- `apply_unknown_dirs(project, report) -> list[tuple[str, str]]`: moves each `unknown_dirs`
  entry `X` to `_arsip/folder-X`; when that exists, `_arsip/folder-X-2`, `-3`, … Creates
  `_arsip/` if missing. Returns `(src, dst)` pairs (relative).
- `empty_tmp(project, include_mcp=False) -> dict` returns `{"deleted": [...], "kept_mcp": [...]}`:
  deletes every file and sub-folder inside `.tmp/` (keeps `.tmp/` itself) EXCEPT media files
  under `MCP_SUBDIRS`, which are kept and listed in `kept_mcp` unless `include_mcp=True`.
  Empty sub-folders left over are removed. A missing `.tmp/` → empty result, no error. Never
  follows symlinks (a symlink is unlinked, its target untouched). Never touches anything outside
  `.tmp/`.
- CLI in `__main__.py`: `tidy <project> [--tmp-days N] [--apply] [--empty-tmp] [--include-mcp]`.
  No flag → print `format_report(scan(...))`, exit 0, change nothing. `--apply` → move unknown
  dirs, print each `moved A -> B`. `--empty-tmp` → run `empty_tmp`, print the deleted count and
  each kept MCP file with the words `paid render not moved yet, kept`. `--include-mcp` without
  `--empty-tmp` → argparse error (exit 2). `ValueError` from `scan` → the existing
  `FAIL: ...` path, exit 1.
- `_arsip/`, `shots/out/` and every contract folder other than `.tmp/` are never deleted or
  emptied by any flag.

**Steps:**
1. Write failing test for `apply_unknown_dirs` moving `_up/` to `_arsip/folder-_up`. Expected error: `AttributeError: module 'tools.vidkit.tidy' has no attribute 'apply_unknown_dirs'`
2. Run test, confirm it fails for the expected reason
3. Implement `apply_unknown_dirs`; make the test pass
4. Write failing tests for `empty_tmp` (below), implement it, make them pass
5. Write failing CLI tests (dry run changes nothing; `--apply`; `--empty-tmp`; bad flag combination), then add the parser and dispatch in `__main__.py` (import `tidy` in the `from . import ...` line)
6. Run the whole py suite: `bash tests/run.sh py`
7. Commit: `feat(GV-21): vidkit tidy --apply and --empty-tmp`

**Error paths covered:** `--include-mcp` without `--empty-tmp`; project not a directory; `.tmp`
missing; destination `_arsip/folder-X` already exists (suffix, no overwrite).
**Edge cases covered:** no unknown dirs → `--apply` prints `nothing to move`; two unknown dirs
with the same name cannot exist, but `_up` and `_arsip/folder-_up` both existing → `-2`;
`.tmp` holding a file, a nested folder and a symlink to a file outside the project (the target
survives); `.tmp/image/a.png` kept by default, deleted with `--include-mcp`;
`.tmp/image/notes.txt` (non-media) deleted; `_arsip/` content untouched after `--empty-tmp`
(sha256 compared); `shots/out/` untouched; running `--empty-tmp` twice is a no-op the second time.
**Observability:** every move and every kept file is printed; the deleted count is printed.
**Concurrency:** not applicable, with the reason: one session drives a project; stated in the
help text ("do not run while a render is writing to `.tmp/`").

**Verification:**
- [ ] static: no checker configured for this stdlib repo; `python3 -m py_compile tools/vidkit/tidy.py tools/vidkit/__main__.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] `python3 -m tools.vidkit tidy --help` lists the four flags
- [ ] Dry run on a real messy temp project prints a report and leaves the tree identical
- [ ] No placeholder/TODO comments in new code

### Phase D: skills, docs, routing, consistency check, release

**Estimated time:** 20 minutes

**Files:**
- Modify: `skills/video-image/SKILL.md`, `skills/video-gen/SKILL.md`, `skills/video-post/SKILL.md`, `skills/video-explainer/SKILL.md`, `docs/tool-routing.md`, `docs/vidkit.md`, `reference/post-production/10-post-production-pipeline.md`, `CLAUDE.md`, `CHANGELOG.md`, plugin version files (find them with `grep -rn "3.17.0" --include=*.json --include=*.md .` and follow how GV-18 bumped them)
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
- `docs/tool-routing.md` two rows: "Keep the project folder clean / find stray folders and
  duplicates" → `python3 -m tools.vidkit tidy <project>`; "Re-render a paid asset without
  losing the old one" → `python3 tools/renders.py <project> archive --file F --reason R`.
- `docs/vidkit.md` table: row `tidy` ("scan, move unknown folders to `_arsip/`, empty `.tmp/`
  except unmoved MCP renders").
- Pipeline doc: new `### 2.4 Cleaning up` after §2.3: the three commands, what each can delete
  (only `.tmp/` content, MCP renders kept unless `--include-mcp`), and that `_arsip/` is never
  touched.
- `CLAUDE.md`: Architecture table gets a `tools/vidkit/tidy.py` mention in the `tools/vidkit/`
  row and the `renders.py` row mentions `archive`; Version + Last Updated; a `v3.18.0` changelog
  entry; tool counts only if the repo counts them in text you edited.
- `CHANGELOG.md`: matching entry.

**Consistency check `tests/consistency/tidy-contract.sh`:** model it on the nearest existing
script in `tests/consistency/` (read one first, keep its output style). It must `exit 1` with a
message naming the file when any of these is missing: `archive --file` in `video-image` and
`video-gen` SKILL.md; `vidkit tidy` in those two plus `video-post` and `video-explainer`; a
`tidy` row and an `archive` row in `docs/tool-routing.md`; `### 2.4` in the pipeline doc.

**Steps:**
1. Write failing test: create `tests/consistency/tidy-contract.sh` as above. Expected error: the script exits 1 naming `skills/video-image/SKILL.md` as missing `archive --file`
2. Run it, confirm it fails for that reason: `bash tests/consistency/tidy-contract.sh`
3. Edit the two render-offer skills (`video-image`, `video-gen`)
4. Edit `video-post` and `video-explainer`
5. Edit `docs/tool-routing.md`, `docs/vidkit.md`, the pipeline doc §2.4
6. Run the consistency check, confirm it passes
7. Edit `CLAUDE.md`, `CHANGELOG.md`, version files (the existing version-gate consistency checks fail until all agree; run `bash tests/run.sh consistency`)
8. Run the full gate: `bash tests/run.sh` and record the counts
9. Commit: `feat(GV-21): skills, routing docs and release v3.18.0 for tidy and archive`

**Error paths covered:** the consistency script fails loudly per missing item (not just the
first); the version gates catch a half-done bump.
**Edge cases covered:** the `video-explainer` skill has no render offer, so it gets only the
`tidy` line; `video-post` likewise.
**Observability:** not applicable, with the reason: docs and a check script; the script prints
which file lacks which text.
**Concurrency:** if GV-20 merged first, see "Coordination" above.

**Verification:**
- [ ] static: no checker configured for this stdlib repo; `bash -n tests/consistency/tidy-contract.sh` passes
- [ ] unit: `bash tests/run.sh` passes (all groups)
- [ ] `grep -rn "archive --file" skills/video-image/SKILL.md skills/video-gen/SKILL.md` finds both
- [ ] Real end-to-end by hand in a temp project: make `keyframes/scene-01.png`, run
      `renders.py <tmp> archive --file keyframes/scene-01.png --reason "wajah beda"`, see it in
      `_arsip/`; create `_up/x.png`, run `vidkit tidy <tmp>` (report), then `--apply` (moved)
- [ ] No placeholder/TODO comments in new code or docs

## Out of scope

Pixel-based image/video QA; auto-removal of duplicates; deleting `_arsip/`; changing where MCP
renders land (stays `.tmp/`).

## Red-flag self-check

Data Integration Map present; every phase has TDD step 1 in the required form, a Verification
block and its owed error/edge/observability/concurrency answers; CLAUDE.md read; the
self-contained header is present.
