> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-22.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. Never batch all updates at the end. Update ONLY this file.
> **Self-contained:** this plan is the COMPLETE spec. Every path, contract and convention it needs is written here verbatim.

**Ticket:** GV-22
**Ledger:** .gaspol/progress/PROGRESS-GV-22.md
**Spec:** docs/plans/2026-10-17-GV-22-ffprobe-migration-spec.md

## Goal

Two leftovers of GV-20 (v3.18.0, merged at `e33f52a`). (1) The route `vidkit synth notification|alarm`
breaks the GitHub table in `docs/tool-routing.md` because of the bare `|`; write it `\|` and narrow
the validator so only `\|` is accepted. (2) 12 of the 17 files on `ffprobe_allow` in
`tools/registry.json` stop calling `ffprobe` themselves and go through `tools/vidkit/ff.py` (Python)
or a new `tools/vidkit/js/ff.mjs` (Node). `ffprobe_allow` shrinks from 17 to 5. Every tool keeps
exactly the behaviour it has today, including when ffprobe is missing or a file is unreadable.

## Architecture Context

- Work in the worktree `.claude/worktrees/gv-22-ffprobe`, branch `GV-22-ffprobe`. Never in the main checkout.
- `tools/registry.json`: keys `version`, `tools[]`, `routes[]` (`task`, `use`, `tools`), `ffprobe_allow[]` (`id`, `reason`).
- `tools/registry_build.py`:
  - line 40 `FF_EXEMPT = "tools/vidkit/ff.py"`; line 41 `FFPROBE_RE = re.compile(r"\bffprobe\b")`;
    line 53 `SCAN_GLOBS = ("tools/**/*.py", "tools/**/*.mjs")`.
  - line 177 (route check): `elif ("|" in (re.sub(r"`[^`\n]*`", "", v) if key == "use" else v)) or "\n" in v:` → problem `"{label}: {key} has a pipe or newline"`.
  - `_check_ffprobe_allow` (line 191): an allowlisted file with no `ffprobe` word is reported `"{aid}: stale ffprobe_allow entry (no ffprobe in file)"`. So removing the last `ffprobe` word from a file FORCES removing its allowlist entry in the same commit.
  - `_scan_ffprobe` (line 214): any file under `SCAN_GLOBS` containing the WORD `ffprobe` (comments, docstrings and error strings count) that is not `FF_EXEMPT` and not allowlisted → `"{rel}: ffprobe outside vidkit/ff.py and not in ffprobe_allow"`.
  - `render` writes the table between `<!-- registry:routes:begin -->` / `<!-- registry:routes:end -->` in `docs/tool-routing.md`; `render --check` exits 1 on drift.
- **Consequence for every moved file: the word `ffprobe` must disappear completely** — module constants, docstrings, comments and error strings. Error text that today says `ffprobe not found on PATH` comes from `ff` instead (same text, see Phase B).
- `tools/vidkit/ff.py` today: `FFError(RuntimeError)`; `run(cmd, capture_stderr=False, heartbeat_s=None)` (uses `subprocess.run`, or `subprocess.Popen` in `_run_with_heartbeat`); `probe(path)` returns `{"duration", "video": {"duration","fps","width","height"} | None, "audio": {"duration","sample_rate","channels"} | None}`; `duration(path)` raises `FFError("no duration for …")` when absent; `has_audio(path)`.
- Precedent: `tools/check_vo_duration.py` and `tools/track_screen.py` were moved in GV-20; tests in `tests/py/test_probe_migration.py` (pattern: `mock.patch.object(<module>.ff, "probe", side_effect=ff.FFError("boom"))`).
- Tool modules import ff with: `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` then `from tools.vidkit import ff  # noqa: E402` (see `tools/check_vo_duration.py`). Reuse exactly; skip if the module already has the sys.path line.
- Tests: `bash tests/run.sh py|node|consistency` (stdlib `unittest`, `node --test`, bash). There is NO pytest and NO npm; `detect-stack` printed `unit: pytest`, which is wrong for this repo — use `tests/run.sh` (GV-20 precedent). `detect-stack` printed `static: UNKNOWN`; this plan uses `python3 -m py_compile` and `node --check` as in GV-20.
- Fixture clips: `tests/py/media.py` (skip decorator when ffmpeg/ffprobe absent; helpers build tiny real clips with ffmpeg).
- Version references to bump in the last phase: `.claude-plugin/plugin.json`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `tests/consistency/plugin-identity.sh`, `tests/consistency/tools-index.sh`.
- `CLAUDE.md` ticket counter on this branch already says `Last ticket: GV-22` (GV-21 belongs to branch `GV-21-tidy`, not merged). On merge, keep the higher number.

## Tech Stack

python3 stdlib, Node builtins (`node:child_process`, `node:util`), ffmpeg/ffprobe. No new dependency.

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Route text | `tools/registry.json` routes | `registry_build.render` | Yes | change one `use` value |
| Pipe rule | `registry_build.validate` route check | line 177 | Yes | narrow to `\|` only |
| Python probe | `tools/vidkit/ff.py` | `probe`, `duration`, `has_audio`, `run` | Yes | add `pix_fmt`, `FFMissing`, `TOOLS`, `missing()` |
| Node probe | `tools/vidkit/js/ff.mjs` | `probeDuration(file)` | No | create, real `execFile("ffprobe")` |
| Allowlist | `tools/registry.json` `ffprobe_allow` | `_check_ffprobe_allow` | Yes | 17 → 5 entries |
| Ratchet owners | `registry_build.FF_EXEMPT` | `_scan_ffprobe` | Yes | becomes `FF_OWNERS` tuple incl. `ff.mjs` |
| Fixture media | `tests/py/media.py` | real ffmpeg clips | Yes | reuse |

## Behaviour contract per moved tool (pin it, then swap)

Every moved wrapper keeps its name, signature and return. "missing" = the ffprobe binary is not on
PATH (`ff.FFMissing`). "unreadable" = ffprobe ran but failed or gave no number (`ff.FFError`, or a
`None` field in `ff.probe`).

| Tool / function | Today: value | missing | unreadable |
|---|---|---|---|
| `burn_subs.video_height_of(path)` | `int` height of v:0 | `1080` | `1080` (also no video stream) |
| `clean_voice.duration_of(path)` | `float` format duration | raise `CleanError("ffprobe not found on PATH")` | `None` (incl. `N/A`) |
| `clean_voice.has_audio_stream(path)` | `bool` | raise `CleanError("ffprobe not found on PATH")` | `False` |
| `composite._probe` callers: `duration_of(path, stream="v:0")` | `float` stream duration of v:0 or a:0 | raise `CompositeError("ffprobe not found on PATH")` | file fails → `CompositeError(f"{name}: unreadable")`; stream absent or duration N/A → `None` |
| `composite.require_alpha(path)` | `True` or `CompositeError("… has no alpha channel (pix_fmt …)")` | `CompositeError` | `CompositeError(f"{name}: unreadable")` |
| `composite._video_info(path)` | `(width, height, fps)`, fps default from `"30/1"` | `CompositeError` | no stream → `CompositeError(f"{name}: unreadable")` |
| `composite._has_stream(path, "v"\|"a")` | `bool` | raise `CompositeError("ffprobe not found on PATH")` | `False` |
| `edit_render._probe_duration(path)` | `float` format duration | `None` | `None` |
| `edit_render._probe_duration_stream(path, "v:0"\|"a:0")` | `float` stream duration | `None` | `None` (incl. N/A, stream absent) |
| `gen_music.probe_duration(path)` | `round(float, 3)` | `None` | `None` |
| `make_stems._duration_of(path)` | `float` | raise `StemError("ffprobe not found on PATH")` | raise `StemError(f"{name}: unreadable duration")` |
| `mix_music.duration_of(path)` | `float` | `None` | `None` |
| `mix_sfx.master_duration(path)` | `float` | `None` | `None` |
| `overlay_plan._clip_duration(clip)` | `float` | today `TypeError` crash (`FFPROBE` is `None` in argv); new: `None` (caller at line 303 already handles `None`; executor confirms by reading it) | `None` |
| `qa_frames.probe(clip)` | `(duration, fps)`; duration = v:0 stream duration, else format duration; fps default `DEFAULT_FPS` (25.0) | n/a: `main` exits 2 first | `(None, 25.0)` |
| `qa_frames` main (line 324) | — | prints `qa_frames: ffmpeg and ffprobe are required and were not found on PATH` to stderr, exit 2 | — |
| `gen_vo.mjs` `probeDuration(file)` | `Number(value.toFixed(3))` | `null` | `null` |
| `voice_changer.mjs` exported `probeDuration(file)` | raw `Number` | `null` | `null` |

The `ff.FFMissing` message is exactly `"<binary> not found on PATH"` (e.g. `ffprobe not found on PATH`), so `CleanError(str(exc))`, `CompositeError(str(exc))`, `StemError(str(exc))` reproduce today's text without the word appearing in the tool file.

---

### Phase A: Pipe rule and the synth route

**Estimated time:** 10 minutes

**Files:**
- Modify: `tools/registry_build.py` (line 177), `tools/registry.json` (route `Phone notification / alarm sound without paid files`), `docs/tool-routing.md` (regenerated)
- Test: `tests/py/test_registry.py` (existing tests at lines 148, 425, 428, 431)

**Steps:**
1. Write failing test for a bare `|` inside a code span of `use` being refused (`` "`a|b`" `` → problem `has a pipe or newline`) and `` "`a\|b`" `` passing, also for `task`. Expected error: `AssertionError` (today the code-span `|` passes, test at line 428 `test_pipe_inside_code_span_of_use_is_allowed` asserts the old rule).
2. Run `bash tests/run.sh py`, confirm it fails for that reason.
3. Replace `test_pipe_inside_code_span_of_use_is_allowed` with `test_escaped_pipe_is_allowed` (`\|` passes in `use` and `task`) and `test_bare_pipe_inside_code_span_rejected`.
4. In `registry_build.py` line 177, change the check to: a `|` not preceded by `\` → problem. Use `re.search(r"(?<!\\)\|", v)`. Same rule for `task` and `use`. Keep the newline check and the problem text `"{label}: {key} has a pipe or newline"`.
5. Edge cases in tests: `\\|` at cell start, two escaped pipes, an escaped pipe next to a bare one (rejected), empty string still `is empty`.
6. `tools/registry.json`: set that route's `use` to the JSON string `"`vidkit synth notification\\|alarm`"` (renders as `` `vidkit synth notification\|alarm` ``).
7. Run `python3 tools/registry_build.py validate --coverage`, then `python3 tools/registry_build.py render`; `git diff docs/tool-routing.md` shows only that one row changed.
8. Run `bash tests/run.sh py` and `bash tests/run.sh consistency`, all pass.
9. Commit: `fix(GV-22): route cells accept only escaped pipes`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/registry_build.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] `bash tests/run.sh consistency` passes
- [ ] `python3 tools/registry_build.py render --check` exits 0
- [ ] `grep -n 'notification' docs/tool-routing.md` shows `notification\|alarm`
- [ ] No placeholder/TODO comments in new code

### Phase B: vidkit.ff — pix_fmt, missing binary, tool check

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/vidkit/ff.py`, `docs/vidkit.md` (the `ff` row, line 11)
- Test: `tests/py/test_vidkit.py` (near `test_probe`, line 209)

**Steps:**
1. Write failing test for `ff.probe(clip)["video"]["pix_fmt"] == "yuv420p"` on a real fixture clip (built with `-pix_fmt yuv420p`). Expected error: `KeyError: 'pix_fmt'`.
2. Run `bash tests/run.sh py`, confirm it fails for that reason.
3. Add `pix_fmt` to the `show_entries` stream list and to the video dict in `probe()`.
4. Write failing test: with `mock.patch.dict(os.environ, {"PATH": <empty tmp dir>})`, `ff.probe(clip)` raises `ff.FFMissing` with message `ffprobe not found on PATH`, and `isinstance(exc, ff.FFError)` is true. Expected error: `AttributeError: module 'tools.vidkit.ff' has no attribute 'FFMissing'`.
5. Add `class FFMissing(FFError)` ("the binary is not on PATH"). In `run()` and `_run_with_heartbeat()`, catch `FileNotFoundError` from `subprocess.run` / `subprocess.Popen` and raise `FFMissing(f"{argv[0]} not found on PATH")` (`from None`).
6. Write failing test for `ff.TOOLS == ("ffmpeg", "ffprobe")` and `ff.missing()` returning `[]` normally and `["ffmpeg", "ffprobe"]` with the empty PATH. Expected error: `AttributeError`.
7. Add `TOOLS = ("ffmpeg", "ffprobe")` and `def missing(): return [t for t in TOOLS if shutil.which(t) is None]`.
8. Edge cases in tests: heartbeat path with missing binary also raises `FFMissing`; a non-zero exit still raises plain `FFError` (not `FFMissing`); an audio-only file gives `video` `None` (no `pix_fmt` lookup crash).
9. Update `docs/vidkit.md` `ff` row: add `pix_fmt`, `FFMissing`, `missing()`.
10. Run `bash tests/run.sh py`, all pass. Commit: `feat(GV-22): ff.probe returns pix_fmt, missing binary raises FFMissing`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/ff.py` passes
- [ ] unit: `bash tests/run.sh py` passes
- [ ] Existing callers of `ff.FFError` (e.g. `tools/retention_gate.py` line 508) still catch `FFMissing` because it subclasses `FFError`
- [ ] Observability: the `FFMissing` message names the missing binary
- [ ] No placeholder/TODO comments in new code

### Phase C: Node helper ff.mjs and second ratchet owner

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/js/ff.mjs`
- Modify: `tools/gen_vo.mjs` (lines ~20 and 171-182), `tools/voice_changer.mjs` (lines ~16 and 178-189), `tools/registry_build.py` (`FF_EXEMPT`, `_scan_ffprobe` message), `tools/registry.json` (new tool entry; remove 2 allowlist entries), `docs/tool-routing.md` (regenerated if the table changes), `docs/vidkit.md` (js section)
- Test: `tests/node/vidkit-js.test.mjs`, `tests/py/test_registry.py` (line 541 `test_unlisted_ffprobe_reported_exactly`)

**Steps:**
1. Write failing test in `tests/node/vidkit-js.test.mjs` for `probeDuration` from `../../tools/vidkit/js/ff.mjs` on a real clip made with `ffmpeg -f lavfi -i anullsrc -t 1` in a tmp dir (≈1.0 s), and returning `null` for a non-media file and when `process.env.PATH` is set to an empty tmp dir (restore after). Expected error: `ERR_MODULE_NOT_FOUND`. Skip the clip case with `{ skip: !hasFfmpeg }` when ffmpeg is absent.
2. Run `bash tests/run.sh node`, confirm it fails for that reason.
3. Create `tools/vidkit/js/ff.mjs`: `export async function probeDuration(file)` using `promisify(execFile)("ffprobe", ["-v","error","-show_entries","format=duration","-of","csv=p=0", file])`; parse with `Number.parseFloat`; return the number when finite, else `null`; `catch` → `null`. One header comment: the only Node file allowed to call ffprobe.
4. `gen_vo.mjs`: delete its local `probeDuration`, import from `./vidkit/js/ff.mjs`, keep rounding at the call site via a local `const measured = await probeDuration(f); … measured === null ? null : Number(measured.toFixed(3))` (same output as today). Rewrite the header line 20 so the word `ffprobe` is gone (e.g. "duration measured through vidkit/js/ff.mjs when available").
5. `voice_changer.mjs`: delete its local function and `export { probeDuration } from "./vidkit/js/ff.mjs";` so the existing export stays. Rewrite header line 16 without the word.
6. Confirm both files contain no `ffprobe` word: `grep -n '\bffprobe\b' tools/gen_vo.mjs tools/voice_changer.mjs` prints nothing.
7. Write failing test in `test_registry.py`: a fake root with `tools/vidkit/js/ff.mjs` containing `ffprobe` and no allowlist reports no problem. Expected error: `AssertionError` (reported as outside today).
8. `registry_build.py`: replace `FF_EXEMPT` with `FF_OWNERS = ("tools/vidkit/ff.py", "tools/vidkit/js/ff.mjs")`, use `rel in FF_OWNERS`, and change the message to `"{rel}: ffprobe outside vidkit/ff.py or vidkit/js/ff.mjs and not in ffprobe_allow"`. Update the exact-message test at line 541.
9. `tools/registry.json`: add a tool entry for `tools/vidkit/js/ff.mjs` the same way `tools/vidkit/js/env.mjs` is registered (internal helper with a reason, see test line 517), remove the `ffprobe_allow` entries for `tools/gen_vo.mjs` and `tools/voice_changer.mjs`.
10. Run `python3 tools/registry_build.py validate --coverage` and `render`, then `bash tests/run.sh` (all groups). Commit: `refactor(GV-22): Node tools probe through vidkit/js/ff.mjs`.

**Verification:**
- [ ] static: `node --check tools/vidkit/js/ff.mjs tools/gen_vo.mjs tools/voice_changer.mjs` passes
- [ ] unit: `bash tests/run.sh node` and `bash tests/run.sh py` pass
- [ ] `bash tests/run.sh consistency` passes (`render --check`, coverage, ratchet)
- [ ] `ffprobe_allow` has 15 entries
- [ ] Existing `gen_vo` / `voice_changer` node tests unchanged and green
- [ ] No placeholder/TODO comments in new code

### Phase D: Duration-only Python tools (5 files)

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/gen_music.py`, `tools/make_stems.py`, `tools/mix_music.py`, `tools/mix_sfx.py`, `tools/overlay_plan.py`, `tools/registry.json` (remove 5 allowlist entries)
- Test: `tests/py/test_probe_migration.py`

**Steps:**
1. Write failing tests in `test_probe_migration.py`, one class per tool, using the contract table above: value on a real 1 s fixture clip (`tests/py/media.py`), "missing" via `mock.patch.dict(os.environ, {"PATH": <empty tmp dir>})`, "unreadable" via a text file renamed `.mp4`. Expected error for the missing case on the old code: `AssertionError` (old code resolved `FFPROBE` at import and still runs it), and for `overlay_plan` a `TypeError`.
2. Run `bash tests/run.sh py`, confirm the missing-case tests fail and the value tests pass (they pin today's value).
3. In each file: import `ff` (Architecture Context idiom), rewrite the wrapper body to `ff.probe(path)["duration"]`, map per the contract (`except ff.FFMissing` first where the tool raises, then `except ff.FFError` → `None` or the tool error), keep `gen_music`'s `round(…, 3)`. Delete `FFPROBE = shutil.which("ffprobe")` and any `if FFPROBE is None` guard. Drop `import shutil` / `subprocess` only if nothing else uses them.
4. Remove every remaining `ffprobe` word: `overlay_plan.py` line 28 docstring, `make_stems.py` line 16 docstring, and error strings (now from `ff`). `grep -n '\bffprobe\b'` on the five files prints nothing.
5. `overlay_plan`: read the caller at line ~303 and confirm `None` is handled (a refusal naming the clip, not a crash); if it is not, STOP and ask before changing the caller.
6. Remove the 5 entries from `ffprobe_allow`. Run `python3 tools/registry_build.py validate --coverage`.
7. Run `bash tests/run.sh` (all groups), all pass. Commit: `refactor(GV-22): duration probes go through vidkit.ff`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/gen_music.py tools/make_stems.py tools/mix_music.py tools/mix_sfx.py tools/overlay_plan.py` passes
- [ ] unit: `bash tests/run.sh py` passes (existing tests for these tools untouched and green)
- [ ] `bash tests/run.sh consistency` passes
- [ ] `ffprobe_allow` has 10 entries
- [ ] Every row of the contract table for these 5 tools has a test
- [ ] No placeholder/TODO comments in new code

### Phase E: Stream-field tools (burn_subs, clean_voice, edit_render, qa_frames)

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/burn_subs.py`, `tools/clean_voice.py`, `tools/edit_render.py`, `tools/qa_frames.py`, `tools/registry.json` (remove 4 allowlist entries)
- Test: `tests/py/test_probe_migration.py`; `tests/py/test_qa_frames.py` (line 216 uses `media.FFPROBE` itself — test code, leave it)

**Steps:**
1. Write failing tests per the contract table for `burn_subs.video_height_of`, `clean_voice.duration_of`, `clean_voice.has_audio_stream`, `edit_render._probe_duration`, `edit_render._probe_duration_stream` (v:0 and a:0, plus an audio-only file for v:0 → `None`), `qa_frames.probe` (value, and `(None, 25.0)` unreadable), and `qa_frames` main printing the exact message and exit 2 with empty PATH. Expected error: `AssertionError` on the missing-binary cases.
2. Run `bash tests/run.sh py`, confirm those fail and the value cases pass.
3. Swap bodies: height ← `probe["video"]["height"]`; duration ← `probe["duration"]`; has audio ← `probe["audio"] is not None`; stream duration ← `probe["video" if stream.startswith("v") else "audio"]["duration"]` (stream dict `None` → `None`); `qa_frames.probe` ← `(video duration or format duration, video fps or DEFAULT_FPS)`. `qa_frames` main: `if ff.missing(): print(f"qa_frames: {' and '.join(ff.TOOLS)} are required and were not found on PATH", file=sys.stderr); return 2` (same text as today). Keep `FFMPEG` where the file still runs ffmpeg.
4. Remove every `ffprobe` word (docstring `qa_frames.py` line 16, `clean_voice` error strings now via `CleanError(str(exc))`). `grep -n '\bffprobe\b'` on the four files prints nothing.
5. Remove the 4 entries from `ffprobe_allow`; `python3 tools/registry_build.py validate --coverage`.
6. Run `bash tests/run.sh` (all groups). Commit: `refactor(GV-22): stream probes go through vidkit.ff`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/burn_subs.py tools/clean_voice.py tools/edit_render.py tools/qa_frames.py` passes
- [ ] unit: `bash tests/run.sh py` passes (existing `test_edit_render.py`, `test_qa_frames.py`, clean_voice and burn_subs tests green)
- [ ] `bash tests/run.sh consistency` passes
- [ ] `ffprobe_allow` has 6 entries
- [ ] No placeholder/TODO comments in new code

### Phase F: composite.py

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/composite.py` (`_probe` line 43, `duration_of` 56, `_has_stream` 64, `require_alpha` 76, `_video_info` 140), `tools/registry.json` (remove 1 allowlist entry)
- Test: `tests/py/test_probe_migration.py`

**Steps:**
1. Write failing tests per the contract table for `duration_of` (v:0, a:0, stream absent → `None`), `require_alpha` (a `yuva420p` or `rgba` fixture passes, a `yuv420p` one raises the alpha message), `_video_info`, `_has_stream("v"/"a")`, the missing-binary `CompositeError("ffprobe not found on PATH")` and the unreadable `CompositeError(f"{name}: unreadable")`. Expected error: `AssertionError` on the missing-binary cases.
2. Run `bash tests/run.sh py`, confirm those fail and the value cases pass.
3. Replace `_probe(path, entries, stream)` with `_info(path)`: `ff.probe(path)`, `ff.FFMissing` → `CompositeError(str(exc))`, other `ff.FFError` → `CompositeError(f"{Path(path).name}: unreadable")`. Rewrite the four callers on the returned dict; `require_alpha` reads `info["video"]["pix_fmt"]` and keeps its alpha test unchanged. `_has_stream`: unreadable → `False` (today's behaviour), missing → `CompositeError`.
4. Remove every `ffprobe` word (line 65 docstring). `grep -n '\bffprobe\b' tools/composite.py` prints nothing.
5. Remove its `ffprobe_allow` entry; `python3 tools/registry_build.py validate --coverage`.
6. Run `bash tests/run.sh` (all groups). Commit: `refactor(GV-22): composite probes through vidkit.ff`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/composite.py` passes
- [ ] unit: `bash tests/run.sh py` passes (existing composite tests green: cutaway / overlay / split / insert)
- [ ] `bash tests/run.sh consistency` passes
- [ ] `ffprobe_allow` has exactly 5 entries: `person_mask.py`, `probe_clips.py`, `vidkit/color.py`, `registry_build.py`, `retention_gate.py`
- [ ] No placeholder/TODO comments in new code

### Phase G: Release 3.18.1 and closing checks

**Estimated time:** 15 minutes

**Files:**
- Modify: `.claude-plugin/plugin.json`, `CLAUDE.md` (version line, `### v3.18.1 Changelog`, the v3.18.0 "Not done" ffprobe line stays as history), `README.md`, `CHANGELOG.md`, `tests/consistency/plugin-identity.sh`, `tests/consistency/tools-index.sh`, `docs/plans/2026-10-17-GV-22-ffprobe-migration-spec.md` (Amendments section only if something changed during execution)
- Test: `tests/py/test_registry.py`

**Steps:**
1. Write failing test in `test_registry.py` asserting the committed `ffprobe_allow` ids equal the 5 listed in Phase F. Expected error: none if Phase F is done — this test is the regression lock; if it passes immediately, record "RED not applicable: lock test for state reached in Phase F" in the ledger.
2. Bump `3.18.0` → `3.18.1` in all six version files; add a short changelog: pipe escape rule, 12 callers moved, `ff.probe` `pix_fmt`, `FFMissing`, `ff.missing()`, `vidkit/js/ff.mjs`, allowlist 17 → 5 with the 5 reasons unchanged.
3. Run `bash tests/run.sh` (all groups), all pass.
4. Run one `silent-failure-hunter` agent (opus, effort high) over the whole branch diff (`git diff main...GV-22-ffprobe`), focused on the error mapping in the 12 wrappers. Fix confirmed findings with a test each.
5. `graphify update .`
6. Commit: `docs(GV-22): release 3.18.1`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py tools/vidkit/*.py` passes
- [ ] unit: `bash tests/run.sh` passes (consistency, py, node)
- [ ] `python3 tools/registry_build.py validate --coverage` and `render --check` exit 0
- [ ] `git grep -nw ffprobe -- tools/` lists only `vidkit/ff.py`, `vidkit/js/ff.mjs` and the 5 allowlisted files
- [ ] Version 3.18.1 in all six files
- [ ] No placeholder/TODO comments in new code

## Completeness notes

- Error paths covered per tool by the contract table (missing binary, unreadable file, absent stream, `N/A`).
- Edge cases: audio-only file, video-only file, non-media file, empty PATH, escaped/bare pipes.
- Observability: `FFMissing` names the binary; tool errors keep today's text.
- Concurrency: not applicable — each probe is one synchronous subprocess call, no shared state.

## Out of scope

- `person_mask.py`, `probe_clips.py`, `vidkit/color.py`, `registry_build.py`, `retention_gate.py` stay allowlisted.
- Smarter ratchet scan (ignoring comments/strings).
- Any behaviour change beyond the probe swap, except `overlay_plan._clip_duration` returning `None` instead of crashing when ffprobe is missing.
- The `gaspol-one` marketplace version (set at release, outside this repo).
