> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-8.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` block, (b) append a `## Log` line ending with the handoff cursor. This is **blocking**, like a test gate: no next phase until both are written. **Never batch all updates at the end.** Update ONLY this file — never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. It must be executable by an agent with **no other context**. Every file path, contract, config key, and convention it needs is written here verbatim.

**Ticket:** GV-8
**Ledger:** .gaspol/progress/PROGRESS-GV-8.md
**Spec:** docs/plans/2026-09-29-GV-8-mpt-adoption-spec.md

## Goal

Adopt four features from `harry0703/MoneyPrinterTurbo` (commit `d477832`) into gaspol-video's
Phase 5/6 pipeline, releasing 3.6.0:

1. **Pause tags** `[pause: 1.5s]` / `[jeda: 1.5s]` in narration, rendered by `tools/gen_vo.mjs` as
   sample-exact silence, with word timings shifted by the measured chunk lengths.
2. **Act dissolves** — optional `transition_in` on an `edit-plan.json` segment, rendered by
   `tools/edit_render.py` with source handles so total duration never changes.
3. **Visual clip QA** — new `tools/qa_frames.py` writes a 5-frame contact sheet per rendered clip
   and a `work/visual-qa.md` verdict sheet Claude fills; validator check V15 blocks unjudged or
   failed clips.
4. **Video-to-music** — `python3 tools/gen_music.py video <project>` asks ElevenLabs
   `/v1/music/video-to-music` for a bed composed to the edited master; opt-in, falls back to the
   palette.

Work happens in the worktree `.claude/worktrees/gv-8-mpt-adopsi` on branch `GV-8-mpt-adopsi`.
All paths below are relative to that worktree root.

## Architecture Context (from CLAUDE.md and the code, verbatim facts)

- Test runner: `bash tests/run.sh [all|consistency|py|node]`. Python tests are stdlib
  `unittest` in `tests/py/test_*.py`, imported as `from tools import <module>`, run with
  `python3 -m unittest discover -s tests/py -t .`. Node tests are `node --test` in
  `tests/node/*.test.mjs`. Consistency checks are bash in `tests/consistency/*.sh`. There is no
  pytest and no npm — do not add either.
- Media fixtures: `tests/py/media.py` exports `duration_of(path, stream)`, `extract_frame`,
  `make_clip(path, seconds=...)`, `psnr`, and the `requires_ffmpeg` decorator. Reuse them.
- Every tool is stdlib-only (python3 stdlib, node builtins, ffmpeg/ffprobe via subprocess), except
  the four venv tools named in CLAUDE.md. **The new tool `qa_frames.py` stays stdlib-only.**
- A tool that imports from `tools.` MUST start with
  `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` before the import — enforced
  by `tests/consistency/tools-cli.sh`, which runs `python3 tools/<name>.py --help` for every tool.
- `tests/consistency/tools-index.sh` fails when any `tools/*.py` or `tools/*.mjs` is not named in
  `CLAUDE.md`, or when `plugin.json` is not the pinned version (currently `"version": "3.5.0"`).
  `tests/consistency/plugin-identity.sh` pins `want_version="3.5.0"`. Both move to `3.6.0` in
  Phase K.
- Project folder contract (`reference/post-production/10-post-production-pipeline.md` §2): only
  these folders exist under `{output_folder}`: `ref/ keyframes/ shots/ clips/ vo/ sfx/ work/
  output/ _arsip/ .tmp/`. **No new folder.** Derived files go to `.tmp/`. Sheets therefore live
  at `.tmp/qa-scene-NN.jpg` (a filename, not a `.tmp/qa/` subfolder — this corrects the spec).
- `renders.json` (`tools/renders.py`, schema in pipeline §3.8): `{"renders": [{"file", "phase"
  ∈ 4A|4B|5, "scene", "model", "prompt_sha256", "refs", "status" ∈ done|failed|skipped,
  "error", "cdn_url", "rendered_at"}]}`. `record(project, entry)` replaces by `file`, atomic.
  `needs_render(ledger, file, prompt)` is False only for `status == "done"` with the same
  `prompt_sha256(prompt)`.
- `music-plan.json` (pipeline §3.6): `{"out": "output/master-mixed.mp4", "segments": [{"from_s",
  "to_s", "track", "gain_db", "fade_in_s", "fade_out_s", "source": "<provenance string>"}]}`.
  `tools/mix_music.py` reads `project / seg["track"]`.
- `audio-plan.json` layer: `{kind: narration|dialogue, cast, at_s, dur_s, from: tts|clip, text,
  out}`. `tools/gen_vo.mjs` synthesizes layers with `from == "tts"`; `vo-manifest.json` items carry
  `{id, file, scene, cast, kind, voice_env, chars, duration_s, words: [{text, start_ms, end_ms}]}`.
- Script text is read from `layer.text` by `tools/gen_subs.py` (≈line 152,
  `script_text = (layer.get("text") or "").strip()`), `tools/gen_captions.py` (its per-layer loop
  ≈line 360, passes text to `align_to_script`), and `tools/verify_render.py`
  `build_intended()` (≈line 358, `norm(layer.get("text", ""))`). `gen_captions.py` and
  `verify_render.py` already import from `tools.gen_subs`, so the shared stripping helper lives in
  `gen_subs.py`. `tools/check_vo_duration.py` measures audio only and reads no text — **not
  changed** (corrects the spec).
- `edit_render.py`: `load_plan()` validates; `build_commands(plan)` returns one ffmpeg command per
  segment writing `work/render/part-NNN.mp4`, then `render()` concats with
  `-f concat -c copy` and runs `check_av_gate()` (tolerance `AV_TOLERANCE_S = 0.04`). Segment
  encode: `-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -c:a aac -ar 48000 -ac 2`.
  `_motion_filter(motion, duration_s, width, height)` builds a zoom expression
  `({frm}+({delta})*t/{duration_s})`.
- `gen_music.py`: flag-only argparse (`--library --only --length-s --force --dry-run --renorm`),
  `_load_env()` reads `.env`, raises `MusicLibraryError`; HTTP via `urllib.request`; the
  `CERTIFICATE_VERIFY_FAILED` hint text already exists in `generate()` — reuse it.
- Validator ids in use: C1-C12, K1-K7, I17, I18, V13, V14, P1-P6. New: **V15** (visual QA) and
  **V16** (pause tag in a platform prompt).

## Tech Stack

python3 stdlib (argparse, json, hashlib, subprocess, urllib, uuid for multipart boundary), node
builtins (`node:fs/promises`, `node:child_process`), ffmpeg/ffprobe. No new dependency.

## Deviations from the spec (decided while planning, 2026-09-29)

| Spec said | Plan does | Why |
|---|---|---|
| `music-plan.json` gains `source: palette\|video` | top-level `"bed_source": "palette" \| "video"` | segments already carry a `source` provenance string; one key with two meanings invites a wrong read |
| gen_music video "falls back to the palette track" | the tool exits **3** and prints `FALLBACK palette: <reason>`; `video-post` then keeps the palette segments | the tool never rewrites a plan it did not write; exit 3 mirrors `verify_render.py`'s SKIPPED convention |
| sheets at `.tmp/qa/scene-NN.jpg` | `.tmp/qa-scene-NN.jpg` | folder contract §2.1 forbids subfolders |
| tags stripped in `check_vo_duration.py` | not touched | it reads no text |
| silence via ffmpeg `anullsrc` | silence written as zero PCM samples in node; ffmpeg only decodes chunks and encodes once | sample-exact by construction, and offsets come from sample counts rather than a probe of an mp3 with encoder padding |
| — | `transition_in` refused when the previous segment has `pad_end_s > 0` | a padded tail is a freeze; there are no source frames to dissolve over |

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Pause-tag stripping | `audio-plan.json` layer `text` | `gen_subs.strip_pause_tags()` | No | Create in `tools/gen_subs.py`, import in 3 tools |
| Pause-tag TTS | ElevenLabs `POST /v1/text-to-speech/{voice}/with-timestamps` | `requestOne()` in `gen_vo.mjs` | Yes | Reuse per chunk |
| Chunk decode/encode | ffmpeg | `execFile("ffmpeg", …)` | Yes (binary) | Use |
| Dissolve | source clips in `clips/` / `shots/out/` | `edit_render.build_commands` | Yes | Extend |
| Rendered clip list | `renders.json` | `renders.load()` | Yes | Use existing |
| PLAUSIBILITY block | `video-prompts.md` `### Scene N` sections | new parser in `qa_frames.py` | No | Create |
| Frame extraction | ffmpeg `-ss … -frames:v 1`, `hstack` | subprocess | Yes | Use |
| Video-to-music | ElevenLabs `POST https://api.elevenlabs.io/v1/music/video-to-music` | new `request_video_music()` | No | Create, real HTTP |
| Music ledger | `renders.json` | `renders.record()` / `needs_render()` | Yes | Reuse, `phase: "6"` entry |
| API key | `.env` `ELEVENLABS_API_KEY` | `gen_music._load_env()` | Yes | Reuse |

`renders.json` gains `phase: "6"` for the music entry. Document it in pipeline §3.8 (Phase J):
`phase ∈ 4A | 4B | 5 | 6`.

## Verification commands (resolved for this repo — use these verbatim)

- static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done`
- unit: `bash tests/run.sh`
- Baseline before Phase A (recorded in the ledger): consistency 20 PASS, python 389 OK
  (19 skipped), node 42 PASS.

---

### Phase A: shared pause-tag helper + tag-free script text in captions, subs and P6

**Estimated time:** 15 minutes

**Contract** (write it in `tools/gen_subs.py`, near the top, after the imports):

```python
# [pause: 1.5s] / [jeda: 1.5s] — a directed silence in narration (GV-8). Case-insensitive,
# optional spaces, seconds with optional decimal and optional "s"/"detik".
PAUSE_TAG_RE = re.compile(
    r"\[\s*(?:pause|jeda)\s*:\s*(\d+(?:\.\d+)?)\s*(?:s|detik)?\s*\]", re.IGNORECASE)

def strip_pause_tags(text):
    """Script text as a viewer or a recognizer meets it: tags removed, the spaces they
    leave collapsed. Captions and P6 compare against this, never against the raw text."""
```

It removes every match, collapses runs of whitespace to one space, and strips the ends. It does
NOT validate ranges — `gen_vo.mjs` owns validation (Phase B); a stripped malformed tag like
`[pause: abc]` is left in place because it does not match, and gen_vo refuses it.

**Files:**
- Modify: `tools/gen_subs.py`, `tools/gen_captions.py`, `tools/verify_render.py`
- Test: `tests/py/test_gen_subs.py`, `tests/py/test_gen_captions.py`, `tests/py/test_verify_render.py`
- Create: `tests/fixtures/pause-tags.json` (shared with Phase B's node test)

`tests/fixtures/pause-tags.json` — exact content:

```json
[
  {"in": "Tiap truk antre. [pause: 1.5s] Sekarang enam menit.", "out": "Tiap truk antre. Sekarang enam menit."},
  {"in": "Satu [jeda: 0.8 detik] dua", "out": "Satu dua"},
  {"in": "[PAUSE:2] Mulai", "out": "Mulai"},
  {"in": "Akhir [pause: 0.5s]", "out": "Akhir"},
  {"in": "Tanpa tag sama sekali.", "out": "Tanpa tag sama sekali."},
  {"in": "", "out": ""}
]
```

**Steps:**
1. Write failing test for `gen_subs.strip_pause_tags` over every case in `tests/fixtures/pause-tags.json`. Expected error: `AttributeError: module 'tools.gen_subs' has no attribute 'strip_pause_tags'`.
2. Run `python3 -m unittest tests.py.test_gen_subs`, confirm it fails for that reason.
3. Implement `PAUSE_TAG_RE` + `strip_pause_tags` in `tools/gen_subs.py`.
4. Write failing tests: (a) `gen_subs` builds cues for a layer whose text is `"Tiap truk antre. [pause: 1.5s] Sekarang."` and no cue text contains `[`; (b) `verify_render.build_intended` on the same layer yields no word `pause`/`1.5s`; (c) `gen_captions` output for that layer contains no `[` in any word. Use each test file's existing fixture helpers. Expected: assertions fail showing the tag text.
5. Apply `strip_pause_tags(...)` at the three read sites: `gen_subs.py` (`script_text = strip_pause_tags(layer.get("text") or "")`), `verify_render.build_intended` (`norm(strip_pause_tags(layer.get("text", "")))`), `gen_captions.py` (wherever the layer text is taken for `align_to_script` / page text — import `strip_pause_tags` alongside the existing `from tools.gen_subs import …`).
6. Run `bash tests/run.sh`, all green.
7. Commit: `feat(GV-8): strip pause tags from script text in captions, subtitles and P6`

**Completeness:** error paths — none new (pure function); edge cases covered by the fixture: tag
at start, at end, uppercase, `detik` unit, integer seconds, empty string, no tag. Observability:
not applicable, pure text transform.

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] `grep -n strip_pause_tags tools/gen_subs.py tools/gen_captions.py tools/verify_render.py` shows the definition plus three call sites
- [ ] No placeholder/TODO comments in new code

---

### Phase B: `gen_vo.mjs` renders pause tags as sample-exact silence

**Estimated time:** 15 minutes

**Contract:**

```js
// Same grammar as PAUSE_TAG_RE in tools/gen_subs.py — tests/fixtures/pause-tags.json holds both to it.
export const PAUSE_TAG_RE = /\[\s*(?:pause|jeda)\s*:\s*(\d+(?:\.\d+)?)\s*(?:s|detik)?\s*\]/gi;
export const PAUSE_MIN_S = 0.2;
export const PAUSE_MAX_S = 5.0;

/** Split a layer's text into [{type:"speech", text}, {type:"pause", seconds}] in order.
 *  Empty speech between tags is dropped; two adjacent pauses are summed.
 *  Throws `${id}: pause ${s}s outside ${PAUSE_MIN_S}-${PAUSE_MAX_S}s` when out of range, and
 *  `${id}: malformed pause tag "${raw}"` when text contains `[pause` or `[jeda` that the
 *  regex did not consume. */
export function splitPauses(id, text) { … }

export function stripPauseTags(text) { … } // identical behaviour to gen_subs.strip_pause_tags
```

Synthesis for a layer that has at least one pause segment:

1. Each speech chunk → one `requestOne()` call (unchanged function), chained through
   `previousIds` exactly like whole layers are today, so delivery stays warm across the pause.
2. Each chunk's mp3 bytes → written to `<project>/.tmp/<id>-chunk-<k>.mp3`, decoded with
   `ffmpeg -v error -y -i <mp3> -f s16le -ac 1 -ar 44100 <id>-chunk-<k>.pcm`.
3. Silence = `Buffer.alloc(Math.round(seconds * 44100) * 2)`.
4. Concatenate PCM buffers; encode once:
   `ffmpeg -v error -y -f s16le -ar 44100 -ac 1 -i <all.pcm> -c:a libmp3lame -b:a 128k <out.mp3>`.
5. Word offsets: `chunkStartMs = round(samplesBefore / 44.1)`; each chunk's words (from its own
   `alignment`) get `+chunkStartMs`. Manifest `words` is the concatenation, still ordered.
6. `.tmp/` chunk files are deleted after a successful encode; kept on failure (named in the
   error) for a 3am debugger.

A layer with **no** tag takes today's code path unchanged (one request, bytes written directly,
no ffmpeg). `ffmpeg` missing while a layer has a tag → throw
`${id}: pause tags need ffmpeg on PATH — install it, or remove the tags`. The em-dash check
runs on the tag-stripped text. `chars` in the manifest = length of the tag-stripped text.

**Files:**
- Modify: `tools/gen_vo.mjs`
- Test: `tests/node/gen_vo.test.mjs`

`synthesize()` gains an injectable `execImpl = execFileAsync` parameter (same pattern as the
existing `fetchImpl`/`sleep` injection) so tests can fake ffmpeg decode/encode by writing known
PCM files.

**Steps:**
1. Write failing test for `splitPauses` (order, adjacent pauses summed, empty speech dropped, 0.1s and 5.5s refused, `[pause: abc]` refused as malformed) and for `stripPauseTags` against every case in `tests/fixtures/pause-tags.json`. Expected error: `SyntaxError: The requested module '../../tools/gen_vo.mjs' does not provide an export named 'splitPauses'`.
2. Run `node --test tests/node/gen_vo.test.mjs`, confirm that failure.
3. Implement `PAUSE_TAG_RE`, `PAUSE_MIN_S`, `PAUSE_MAX_S`, `splitPauses`, `stripPauseTags`.
4. Write failing test: a layer `"Satu. [pause: 1s] Dua."` with fake fetch (two responses, each with `alignment` for its chunk) and fake `execImpl` (decode writes PCM of exactly 0.5s = 22050 samples per chunk; encode writes a small mp3). Assert: two fetch calls, the second carries the first's request id in `previous_request_ids`; the first word of chunk 2 has `start_ms` = its own start + 1500 (0.5s chunk + 1.0s pause); the encode call received 22050+44100+22050 samples (check the PCM file size passed to encode = 176400 bytes). Expected: failure because synthesize sends one request with the raw tagged text.
5. Implement the chunked path in `synthesize()`.
6. Write failing tests: untagged layer produces exactly one request whose `text` equals the layer text (regression, byte-identical path); tag + no ffmpeg (`execImpl` rejects with `ENOENT`) → error message above; em dash inside a tagged layer is still refused.
7. Implement the missing guards; run `bash tests/run.sh`, all green.
8. Commit: `feat(GV-8): pause tags in gen_vo render as sample-exact silence`

**Completeness:** error paths — out of range, malformed tag, ffmpeg absent, ffmpeg decode failure
(stderr surfaced, chunk files kept), HTTP errors (existing `requestOne` behaviour). Edge cases —
tag at start (leading silence, first chunk starts at `pause` ms), tag at end (trailing silence),
two adjacent tags (summed), text that is only a tag (no speech chunk → refuse:
`${id}: layer has pauses but no speech`). Observability — log line per layer
`  <id>: N chunks, P pauses (T.TTs silence) -> <out>`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] Node and Python both pass `tests/fixtures/pause-tags.json` (same grammar in both languages)
- [ ] Untagged layer path unchanged (regression test green)
- [ ] No placeholder/TODO comments in new code

---

### Phase C: `edit_render.py` validates `transition_in`

**Estimated time:** 10 minutes

**Contract** — optional segment field:

```jsonc
{ "kind": "clip", "src": "clips/scene-05.mp4", "in_s": 0.0, "out_s": 6.0,
  "transition_in": { "kind": "dissolve", "dur_s": 0.5 } }
```

Constants: `VALID_TRANSITIONS = ("dissolve",)`, `TRANSITION_MIN_S = 0.2`,
`TRANSITION_MAX_S = 1.0`. New `_check_transition(seg, prev, i, project, check_durations)` called
from `load_plan()` for every segment. `None`/absent = fine. Refusals (each a `PlanError` naming
`segment {i}`):

- on segment 1: `transition_in on the first segment — there is nothing to dissolve from`
- not an object / unknown kind / `dur_s` missing, non-numeric, non-finite, or outside 0.2-1.0
- `dur_s` ≥ this segment's planned length, or ≥ the previous segment's planned length
- previous segment has `pad_end_s > 0`: `previous segment ends in a {mode} pad — no source frames to dissolve over`
- `check_durations` and previous source duration < `prev.out_s + dur_s - AV_TOLERANCE_S`:
  `previous source {src} has {x:.2f}s after out_s, dissolve needs {d}s — extend out_s earlier or shorten dur_s`

**Files:**
- Modify: `tools/edit_render.py`
- Test: `tests/py/test_edit_render.py`

**Steps:**
1. Write failing test: a plan whose segment 1 carries `transition_in` must raise `PlanError` mentioning `first segment`. Expected error: `AssertionError: PlanError not raised`.
2. Run `python3 -m unittest tests.py.test_edit_render`, confirm that failure.
3. Implement constants + `_check_transition` + call from `load_plan`.
4. Add failing tests for each remaining refusal (unknown kind, 0.1, 1.5, `"x"`, NaN, previous padded, insufficient handle with a 2.0s `make_clip` source and `out_s: 2.0`, `dur_s` ≥ segment length) plus one accepting case (4.0s source, `out_s: 3.0`, `dur_s: 0.5`). Run, see failures, fix until green.
5. Run `bash tests/run.sh`, all green.
6. Commit: `feat(GV-8): validate transition_in on edit-plan segments`

**Completeness:** every rejection above is one test; the accept case proves the rule is not
over-tight. Observability: messages name the segment and the numbers. Concurrency: not
applicable, single-process CLI.

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] Every refusal path has a test
- [ ] No placeholder/TODO comments in new code

---

### Phase D: `edit_render.py` renders dissolves without moving the timeline

**Estimated time:** 15 minutes

**Contract:**

- Segment `i` is rendered `ext_i` seconds longer, where `ext_i = segments[i+1]["transition_in"]["dur_s"]` when the next segment has one, else 0: `-t (dur + ext)` on input and output, same `-ss in_s`. Its motion expression uses the planned duration and is clamped: `({frm}+({delta})*min(t\,{duration_s})/{duration_s})` (the comma escaped for the filter graph) so the zoom holds at `to` over the handle.
- Consecutive segments joined by transitions form a **group**. A group of one part is used as-is. A group of n>1 parts is merged by one ffmpeg call into `work/render/group-NNN.mp4`:
  - video: chained `xfade=transition=fade:duration={d_k}:offset={O_k}` where `O_k` = sum of the *planned* lengths of the group's segments before part k;
  - audio: chained `acrossfade=d={d_k}:c1=tri:c2=tri`;
  - same encoder flags as a segment (`libx264 veryfast crf 20 yuv420p`, `aac 48000 2ch`), `-r {fps}`.
- Groups are concatenated exactly as parts are today (`-f concat -c copy`). The A/V gate runs as today.
- Master duration = sum of planned segment lengths, with or without transitions.
- `build_commands(plan)` return shape stays `(cmds, parts, work)`; when no segment has `transition_in`, `cmds` and `parts` are **identical** to today (asserted by test). Merge commands are appended to `cmds` after the segment commands, and `parts` becomes the list of group outputs, so `render()` and `--print` need no second code path.

**Files:**
- Modify: `tools/edit_render.py` (`build_commands`, `_motion_filter`, `format_sheet` shows `~0.5s dissolve` on the incoming segment)
- Test: `tests/py/test_edit_render.py`

**Steps:**
1. Write failing test: capture `build_commands` output for a 3-segment plan with no transitions and assert it equals a frozen expected list (build it from the current code before changing anything, then paste the literal). Then a second test: segment 2 carries `transition_in` 0.5s, assert segment 1's command has `-t 2.5` for a planned 2.0s segment. Expected error on the second: `AssertionError: '2.0' != '2.5'`.
2. Run, confirm the regression test passes and the new one fails.
3. Implement handle extension + group merge commands.
4. Write failing `@requires_ffmpeg` render test: three 3.0s `make_clip` sources, plan segments `0.0-2.0`, `0.0-2.0` with `transition_in` 0.5, `0.0-2.0`; assert master `duration_of(out, "v:0")` and `"a:0"` both within 0.04s of 6.0, and the A/V gate passes. Add a frame check with `extract_frame` + `psnr`: at t=2.2s the frame differs from both pure-source frames (it is a blend).
5. Implement until green; add the motion-clamp test (a segment with `motion` and an extension renders; expression contains `min(t`).
6. Run `bash tests/run.sh`, all green.
7. Commit: `feat(GV-8): dissolve at act changes without moving the timeline`

**Completeness:** error paths — ffmpeg failure in a merge surfaces its stderr tail like segment
failures do; edge cases — two consecutive transitions (group of 3), transition into a `kind: shot`
segment, transition on the last segment, a group at the very start; observability — `--print`
sheet marks each dissolve with its offset.

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] Untagged plan produces byte-identical commands (frozen-list test green)
- [ ] Master with dissolves has the same duration as without, within 0.04s
- [ ] No placeholder/TODO comments in new code

---

### Phase E: `tools/qa_frames.py` — contact sheets and the verdict sheet

**Estimated time:** 15 minutes

**Contract:**

```
python3 tools/qa_frames.py <project> [--scenes 5,6] [--clip clips/scene-05.mp4 ...] [--check]
```

- Clip list: every `renders.json` entry with `phase == "5"` and `status == "done"` whose `file`
  exists, plus each `--clip` (scene number parsed from `scene-(\d+)` in its name). `--scenes`
  filters. No clip found → exit 2 `qa_frames: no rendered clips found (renders.json has no done phase-5 entry; pass --clip for hand-rendered clips)`.
- Per clip: probe duration `D`; timestamps `0, D*0.25, D*0.5, D*0.75, max(0, D - 1/fps)` (fps
  from ffprobe `r_frame_rate`, fallback 25). Each frame: `ffmpeg -v error -y -ss {t} -i {clip}
  -frames:v 1 -vf scale=480:-2 .tmp/qa-scene-NN-{k}.jpg`; sheet:
  `ffmpeg -v error -y -i f0 … -i f4 -filter_complex hstack=inputs=5 .tmp/qa-scene-NN.jpg`; the
  five single frames are deleted after the sheet is written.
- PLAUSIBILITY source: `video-prompts.md` in the project; section = from a heading matching
  `^#{2,4} Scene 0*N\b` to the next heading of the same or higher level; block = from the line
  `PLAUSIBILITY:` through the following numbered lines. Missing → the section says
  `PLAUSIBILITY block not found in video-prompts.md — judge against the scene description` and
  still gets all seven rows.
- `work/visual-qa.md` — one section per scene, exact shape:

```markdown
## Scene 05

- clip: clips/scene-05.mp4
- clip_sha256: <hex of the file bytes>
- sheet: .tmp/qa-scene-05.jpg — frames at 0.00s, 2.00s, 4.00s, 6.00s, 7.96s

PLAUSIBILITY:
1. MECHANISM — …
(copied verbatim)

| # | Question | Verdict |
|---|---|---|
| 1 | MECHANISM | |
| 2 | COUNT | |
| 3 | FLOW | |
| 4 | FACING | |
| 5 | PAIR | |
| 6 | PEOPLE | |
| 7 | OVERLAY SURFACE | |
```

- Re-run: sections are merged by scene number. When `clip_sha256` is unchanged the existing
  Verdict cells are kept; when it changed the cells are cleared and the line
  `- note: clip changed since last judged — verdicts cleared` is added. Written atomically
  (tmp file + `os.replace`).
- Verdict grammar: `PASS`, `FAIL: <what is visible>`, `UNSURE: <why the frames cannot tell>`.

**Files:**
- Create: `tools/qa_frames.py` (stdlib, `sys.path.insert` idiom, imports `from tools import renders`)
- Test: `tests/py/test_qa_frames.py`

**Steps:**
1. Write failing test for `qa_frames.frame_times(8.0, 25)` returning `[0.0, 2.0, 4.0, 6.0, 7.96]`. Expected error: `ImportError: cannot import name 'qa_frames' from 'tools'`.
2. Run `python3 -m unittest tests.py.test_qa_frames`, confirm.
3. Create the tool skeleton with `frame_times`, `main()` and `--help`.
4. Add failing tests: `find_plausibility(markdown, 5)` for a found block, a `### Scene 5:` vs `### Scene 05:` heading, and a missing block; `render_section()` exact markdown; `merge_sheet()` keeps verdicts for an unchanged hash and clears them with the note for a changed hash. Implement until green.
5. Add a `@requires_ffmpeg` test: `make_clip` 4.0s, fake `renders.json` entry, run `main([project])`; assert `.tmp/qa-scene-01.jpg` exists and is 2400 px wide (5 × 480), the single frames are gone, and `work/visual-qa.md` has the Scene 01 section. Implement until green.
6. Add a test for the exit-2 "no rendered clips" path. Run `bash tests/run.sh`, all green.
7. Commit: `feat(GV-8): qa_frames writes contact sheets and a visual-qa verdict sheet`

**Completeness:** error paths — no clips (exit 2), clip listed in ledger but missing on disk (skip
with a printed line, not a crash), ffmpeg absent (exit 2 naming ffmpeg), unreadable
`renders.json` (`RenderLedgerError` → exit 2 with its message), clip shorter than 1 frame
(refuse that clip, continue). Edge cases — duration 0/unknown, clip with no scene number in its
name (refuse that `--clip` with a message), duplicate scene from ledger and `--clip` (the
`--clip` wins). Observability — one line per clip: `scene 05  7.96s  sheet .tmp/qa-scene-05.jpg`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] `python3 tools/qa_frames.py --help` works from the repo root (tools-cli consistency check)
- [ ] No new folder under the project — only `.tmp/qa-scene-NN.jpg` and `work/visual-qa.md`
- [ ] No placeholder/TODO comments in new code

---

### Phase F: `qa_frames.py --check` — the V15 gate

**Estimated time:** 10 minutes

**Contract:** `--check` reads `work/visual-qa.md` and the current clip list and exits:

- **1** when any listed clip has no section, any empty Verdict cell, any cell not starting with
  `PASS`, `FAIL:` or `UNSURE:`, any `FAIL:` cell, or a `clip_sha256` that differs from the file
  on disk (judged a different clip). Each problem printed as `V15 FAIL scene NN: <reason>`.
- **0** otherwise. `UNSURE:` cells are printed as `V15 NOTE scene NN q<k>: <reason> — needs a human look`
  but do not fail (the spec: UNSURE is never written as PASS; a human decides).
- **2** for the same "could not run" cases as Phase E.

`--check` never extracts frames and never writes files.

**Files:**
- Modify: `tools/qa_frames.py`
- Test: `tests/py/test_qa_frames.py`

**Steps:**
1. Write failing test: sheet with one empty verdict → `main([project, "--check"])` returns 1 and prints `V15 FAIL`. Expected error: `AssertionError: 0 != 1` (or argparse error for the unknown flag).
2. Run, confirm.
3. Implement `check()`.
4. Add failing tests for: FAIL cell → 1; malformed cell `"ok"` → 1; hash mismatch → 1; all PASS → 0; PASS + one UNSURE → 0 with NOTE printed; missing section for a listed clip → 1. Implement until green.
5. Run `bash tests/run.sh`, all green.
6. Commit: `feat(GV-8): qa_frames --check enforces V15`

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] Each exit code path has a test
- [ ] No placeholder/TODO comments in new code

---

### Phase G: `gen_music.py video` — proxy, limits and the request

**Estimated time:** 15 minutes

**Contract:**

```
python3 tools/gen_music.py video <project> [--master output/master.mp4] [--description-file F]
                                  [--tags cinematic,tense] [--model music_v2] [--force] [--dry-run]
```

Dispatch: in `main(argv)`, `argv = sys.argv[1:] if argv is None else argv`; when `argv[:1] ==
["video"]` hand the rest to `main_video(argv[1:])`, else the existing parser runs unchanged
(existing flags and tests untouched). `--help` of the plain command gains one epilog line naming
the `video` subcommand.

API facts (ElevenLabs docs, fetched 2026-09-29): `POST https://api.elevenlabs.io/v1/music/video-to-music?output_format=mp3_44100_128`,
header `xi-api-key`, `multipart/form-data` with part `videos` (file, `video/mp4`), optional
`description` (1-1000 chars), `tags` (max 10; send one form field `tags` per tag), `model_id`
(`music_v1 | music_v2 | music_v2_5`, default here `music_v2`). Response body = audio bytes.
Limits: 600 s total, 200 MB. 403 when the plan has no Music access; 422 on invalid input.

Constants: `V2M_URL`, `V2M_MAX_S = 600`, `V2M_MAX_BYTES = 200 * 1024 * 1024`,
`V2M_MAX_DESCRIPTION = 1000`, `V2M_MAX_TAGS = 10`, `V2M_MODELS = ("music_v1", "music_v2", "music_v2_5")`.

Functions:

- `make_proxy(master, dest)` →
  `ffmpeg -v error -y -i {master} -an -vf "scale=w=1280:h=1280:force_original_aspect_ratio=decrease:force_divisible_by=2" -c:v libx264 -preset veryfast -crf 28 -pix_fmt yuv420p -movflags +faststart {dest}`; dest = `<project>/.tmp/music-proxy.mp4`.
- `build_video_music_request(proxy_bytes, description, tags, model)` → `(url, headers, body)`,
  pure (no key), multipart built with a `uuid4().hex` boundary. Raises `MusicLibraryError` for
  description > 1000 chars (after the caller's truncation this is a programming error), > 10
  tags, unknown model.
- `default_description(project)` — the music direction lines from `av-script.md` (lines whose
  lowercase starts with `music:` or `musik:`, or table cells under a `Music` column), joined with
  `; `, truncated to 1000 chars on a word boundary. None found → no `description` field.
- Order of checks before any request: master exists → ffprobe duration ≤ 600 → proxy written →
  proxy size ≤ 200 MB → key present. Each failure is a **fallback** (Phase H), not a crash.

**Files:**
- Modify: `tools/gen_music.py`
- Test: `tests/py/test_gen_music.py`

**Steps:**
1. Write failing test for `build_video_music_request(b"VID", "tense low pulse", ["cinematic"], "music_v2")`: URL ends with `/v1/music/video-to-music?output_format=mp3_44100_128`, `Content-Type` starts with `multipart/form-data; boundary=`, body contains a `name="videos"; filename="master.mp4"` part with `b"VID"`, a `description` part, one `tags` part, a `model_id` part, and no `xi-api-key`. Expected error: `AttributeError: module 'tools.gen_music' has no attribute 'build_video_music_request'`.
2. Run `python3 -m unittest tests.py.test_gen_music`, confirm.
3. Implement constants + `build_video_music_request`.
4. Add failing tests: 11 tags refused; unknown model refused; `default_description` on a fixture `av-script.md` (found + truncated at 1000 on a word boundary + none found); `main(["video", "--help"])` exits 0; existing `main(["--dry-run", ...])` behaviour unchanged. Implement until green.
5. Add `@requires_ffmpeg` test for `make_proxy` on a 1920×1080 `make_clip`: output has no audio stream and width 1280. Implement until green.
6. Run `bash tests/run.sh`, all green.
7. Commit: `feat(GV-8): gen_music video builds the video-to-music request and proxy`

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] Palette mode tests unchanged and green
- [ ] Request builder never touches the API key (security: key only added at send time, never logged)
- [ ] No placeholder/TODO comments in new code

---

### Phase H: `gen_music.py video` — send, ledger reuse, fallback

**Estimated time:** 15 minutes

**Contract:**

- Ledger key: `file = "output/music.mp3"`, `phase = "6"`, `model`, `prompt_sha256 =
  renders.prompt_sha256(json.dumps({"master_sha256": <sha256 of master bytes>, "description": d,
  "tags": tags, "model": m}, sort_keys=True))`. `renders.needs_render(ledger, "output/music.mp3",
  <that json string>)` False and the file exists → print `up-to-date: output/music.mp3 (master unchanged)`,
  exit 0, no request. `--force` skips the check.
- Success: bytes ≥ 1000 → write `output/music.mp3` atomically, `renders.record(project, {file,
  phase: "6", scene: None, model, prompt_sha256, refs: [], status: "done", error: None, cdn_url:
  None})`, print `wrote output/music.mp3 (N.NNs) — set music-plan.json "bed_source": "video"`,
  exit 0. Then run the same loudness normalisation the palette path uses on it
  (`_measure_and_normalise`, with the palette `defaults` from `media/music/library/palette.json`).
- Fallback → exit **3**, one line `FALLBACK palette: <reason>`, plus `renders.record(… status:
  "failed", error: <reason>)` when a request was actually sent. Reasons: `master not found`,
  `master is {x:.0f}s, video-to-music accepts up to 600s`, `proxy is {n} MB, limit 200 MB`,
  `ELEVENLABS_API_KEY not set`, `HTTP 403 — this ElevenLabs plan has no Music access`,
  `HTTP 422 — <first 200 chars of body>`, `HTTP <code> — …`, network error (with the existing
  `CERTIFICATE_VERIFY_FAILED` hint), `response too small (N bytes)`, ffmpeg missing.
- `--dry-run`: runs every check up to (not including) the request, prints
  `WOULD request video-to-music: <proxy MB> MB, <duration>s, model <m>, <n> tags`, exit 0.
- The `.tmp/music-proxy.mp4` is deleted after the request (kept on `--dry-run` for inspection).
- Never retries a request whose response was ambiguous (network error after send): billing may
  have happened; the user re-runs deliberately.

**Files:**
- Modify: `tools/gen_music.py`
- Modify: `tools/renders.py` — add `"6"` to `_RENDER_PHASES`, so `python3 tools/renders.py <project> record` accepts the music entry the same way `gen_music.py` writes it
- Test: `tests/py/test_gen_music.py`, `tests/py/test_renders.py`

**Steps:**
0. Write failing test in `tests/py/test_renders.py`: `renders.main([project, "record", "--json", '{"file":"output/music.mp3","phase":"6","status":"done"}'])` returns 0. Expected error: `AssertionError: 1 != 0` (`invalid phase '6'`). Add `"6"` to `_RENDER_PHASES`, see it pass.
1. Write failing test: fake sender raising `HTTPError(403)` → `main_video([project, "--master", …], sender=fake)` returns 3 and prints `FALLBACK palette: HTTP 403`. Expected error: `TypeError: main_video() got an unexpected keyword argument 'sender'` (the sender is the injected seam, default `_request_music`-style `urllib` call).
2. Run, confirm.
3. Implement `run_video_music(project, …, sender, env, log)` and the exit-code mapping.
4. Add failing tests: success writes file + ledger `done` entry; second run with same master is `up-to-date` and the fake sender is not called; changed master bytes → sender called again; `--force` → called; no key → 3 with no sender call and no ledger entry; 700s master (fake probe) → 3 before proxy; tiny response → 3 with a `failed` entry; `--dry-run` → 0, no sender call. Implement until green.
5. Run `bash tests/run.sh`, all green.
6. Commit: `feat(GV-8): gen_music video sends, reuses unchanged results, falls back to the palette`

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] Every fallback reason has a test; no path raises past `main`
- [ ] Security: key read from env/.env only, never printed, never written to renders.json
- [ ] No placeholder/TODO comments in new code

---

### Phase I: wire the skills, the validator and the agents

**Estimated time:** 15 minutes

**Files:**
- Modify: `skills/video-gen/SKILL.md`, `skills/video-post/SKILL.md`, `skills/video-script/SKILL.md`, `skills/video-validate/SKILL.md`, `agents/video-prompt-reviewer.md`, `agents/video-engine-agent.md`
- Create: `tests/consistency/gv8-contract.sh`

Exact content to add:

- **video-gen** — new numbered Hard Rule (next number after the current last) and a step right
  after each render batch: *"Run `python3 tools/qa_frames.py {output_folder} --scenes <batch>`.
  Read every `.tmp/qa-scene-NN.jpg` with the Read tool. Fill each row of `work/visual-qa.md` with
  `PASS`, `FAIL: <what is visible>` or `UNSURE: <why frames cannot tell>` against that scene's
  PLAUSIBILITY answers. Never write PASS for something the frames do not show. Any FAIL → offer
  a re-render of that scene before rendering the next batch."* Also for hand-rendered clips:
  `--clip clips/scene-NN.mp4`.
- **video-post** — pass 2: *"On the first segment of each new act (beat label changes in
  `scene-plan.md`) write `"transition_in": {"kind": "dissolve", "dur_s": 0.5}`; nowhere else.
  If `edit_render.py` refuses for lack of handle frames, shorten `dur_s` (min 0.2) or leave the
  hard cut — never pad."* Pass 4: *"`music-plan.json` `bed_source` defaults to `palette`. When the
  user asked for a composed bed, run `python3 tools/gen_music.py video {output_folder}` after the
  master exists. Exit 0 → one segment `0.0 → master duration`, `track: output/music.mp3`,
  `bed_source: video`. Exit 3 → keep the palette segments and report the printed FALLBACK line."*
  Pass 1: pause tags are honoured by `gen_vo.mjs`.
- **video-script** — narration may carry `[pause: Ns]` / `[jeda: Ns]`, 0.2-5.0 s, only in the
  narration/dialogue text of `av-script.md`, never in a prompt.
- **video-validate** — `### Check V15: Visual QA verdicts (v3.6.0)` (runs
  `python3 tools/qa_frames.py {output_folder} --check`; exit 1 = FAIL, 2 = ERROR, 0 with NOTE
  lines = PASS with human-look items listed) and `### Check V16: No pause tag in a platform prompt (v3.6.0)`
  (grep `video-prompts.md` prompt bodies for `\[\s*(pause|jeda)\s*:`; any hit = FAIL, the platform
  would speak it). Add both to the `--video` list and to `--all`.
- **video-prompt-reviewer** — V16 as a check it runs on every Phase 5 batch.
- **video-engine-agent** — the post-render QA step and the two post-production options, one line each.

`tests/consistency/gv8-contract.sh` fails unless: `skills/video-gen/SKILL.md` names
`qa_frames.py`; `skills/video-validate/SKILL.md` contains `Check V15` and `Check V16`;
`skills/video-post/SKILL.md` contains `transition_in` and `bed_source`;
`skills/video-script/SKILL.md` contains `[pause:`; `agents/video-prompt-reviewer.md` contains `V16`.

**Steps:**
1. Write failing test `tests/consistency/gv8-contract.sh` as specified. Expected error: `FAIL skills/video-gen/SKILL.md does not name qa_frames.py` (and the other FAIL lines), exit 1.
2. Run `bash tests/run.sh consistency`, confirm it fails.
3. Edit the six files with the content above.
4. Run `bash tests/run.sh`, all green.
5. Commit: `docs(GV-8): wire visual QA, dissolves, pause tags and video-to-music into the skills`

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes (21 consistency checks)
- [ ] Skill text references real tool flags that exist (`--scenes`, `--clip`, `--check`, `video`)
- [ ] No placeholder/TODO comments in new text

---

### Phase J: reference documents

**Estimated time:** 15 minutes

**Files:**
- Modify: `reference/post-production/10-post-production-pipeline.md` (§3.3 edit-plan `transition_in`; §3.6 `bed_source` + the exit-3 fallback; §3.7 manifest words include pause offsets; §3.8 `phase ∈ 4A | 4B | 5 | 6` and the music entry; §2 derived files `.tmp/qa-scene-NN.jpg`, `.tmp/music-proxy.mp4`; `work/visual-qa.md` listed under `work/`)
- Modify: `reference/post-production/11-voice-cast-and-vo.md` (pause tags: grammar, range, why sample-exact, chunk stitching)
- Modify: `reference/post-production/13-ffmpeg-edit.md` (dissolve: act changes only, handle rule, duration invariant, refusal messages)
- Modify: `reference/post-production/17-music-bed.md` (video source: when to use, limits, paid plan, fallback, picture-only proxy and why)
- Modify: `reference/image-video-gen/10-physical-plausibility-gate.md` (post-render frame check: sheet, verdict grammar, V15, the known limit — motion between frames is not seen)
- Test: extend `tests/consistency/gv8-contract.sh`

**Steps:**
1. Write failing test: extend `gv8-contract.sh` to require `transition_in` in `13-ffmpeg-edit.md`, `bed_source` in `17-music-bed.md` and in `10-post-production-pipeline.md`, `[pause:` in `11-voice-cast-and-vo.md`, `qa_frames.py` in `10-physical-plausibility-gate.md`. Expected error: FAIL lines naming each file, exit 1.
2. Run `bash tests/run.sh consistency`, confirm.
3. Write the reference sections.
4. Run `bash tests/run.sh`, all green (including `renders-schema-once.sh`, which requires the renders.json schema to be documented in exactly one place — only edit §3.8, never restate it).
5. Commit: `docs(GV-8): reference docs for pause tags, dissolves, video-to-music and frame QA`

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] `renders-schema-once.sh` still passes
- [ ] No placeholder/TODO comments in new text

---

### Phase K: version 3.6.0, CLAUDE.md, NOTICE

**Estimated time:** 10 minutes

**Files:**
- Modify: `.claude-plugin/plugin.json` (`"version": "3.6.0"`), `tests/consistency/tools-index.sh` and `tests/consistency/plugin-identity.sh` (pin `3.6.0`)
- Modify: `CLAUDE.md` — Project Overview tool count `20 CLI tools (18 Python + 2 Node)`; Architecture table row for `tools/qa_frames.py`; `tools/gen_music.py` row mentions the `video` subcommand; debugging rows (V15 FAIL, `FALLBACK palette: HTTP 403`, dissolve refused for handle, pause tag out of range, pause tag spoken by a platform = V16); `**Version:** 3.6.0`, `**Last Updated:** 2026-09-29` (or the execution date); a `### v3.6.0 Changelog` section above v3.4.0
- Modify: `NOTICE` — under MoneyPrinterTurbo "Adapted": pause-tag syntax and PCM silence (`app/services/voice.py _tts_with_pauses`), picture-only proxy and video-to-music request shape (`app/services/elevenlabs_music.py`), post-render clip QA idea (`app/services/twelvelabs.py analyze_clip`, adapted to frame sheets judged in-session), transitions (`app/services/utils/video_effects.py`, adapted to ffmpeg `xfade` with source handles)
- Modify: `README.md` if it lists tools or the version (check with `grep -n "3.5.0\|gen_music" README.md`)

**Steps:**
1. Write failing test: bump the pins in `tools-index.sh` and `plugin-identity.sh` to `3.6.0` and add `qa_frames` + `video-to-music` to `tools-index.sh`'s NOTICE needle list. Expected error: `FAIL plugin.json version is not 3.6.0`, `FAIL NOTICE does not mention qa_frames`.
2. Run `bash tests/run.sh consistency`, confirm.
3. Edit plugin.json, CLAUDE.md, NOTICE, README.
4. Run `bash tests/run.sh`, all green.
5. Commit: `docs(GV-8): release 3.6.0 — CLAUDE.md, NOTICE and version gates`

**Verification:**
- [ ] static: `python3 -m py_compile tools/*.py && for f in tools/*.mjs; do node --check "$f" || exit 1; done` passes
- [ ] unit: `bash tests/run.sh` passes
- [ ] `grep -c qa_frames.py CLAUDE.md` ≥ 1 and `grep '"version"' .claude-plugin/plugin.json` shows 3.6.0
- [ ] No placeholder/TODO comments in new text

---

### Phase L: real-run evidence (billable — ask before each run)

**Estimated time:** 15 minutes

Earlier releases recorded real runs in `docs/evals/`. Unit tests fake the network; this phase
proves the real endpoints.

**Files:**
- Create: `docs/evals/gen-music-video-run.md`, `docs/evals/pause-tags-run.md`, `docs/evals/qa-frames-run.md`

**Steps:**
1. Write failing test: `tests/consistency/gv8-contract.sh` requires the three eval files to exist and each to contain a `## Result` heading. Expected error: `FAIL docs/evals/gen-music-video-run.md missing`.
2. Run, confirm.
3. **Ask the user (AskUserQuestion) which real project folder to use and approve the ElevenLabs spend** for (a) one `gen_music.py video` run and (b) one `gen_vo.mjs` run of a single tagged layer. No approval → record `## Result` as `NOT RUN — no approval (<date>)` and list it under the ledger's `## Utang terbuka`. Never fake a result.
4. `qa_frames.py` needs no spend: run it on an existing rendered project, judge one sheet, run `--check`, record output.
5. Record commands, exit codes, measured numbers (bed duration vs master, pause length measured with ffprobe/silencedetect vs requested), and anything surprising.
6. Run `bash tests/run.sh`, all green. Commit: `docs(GV-8): real-run evidence for video-to-music, pause tags and frame QA`

**Verification:**
- [ ] unit: `bash tests/run.sh` passes
- [ ] Each eval file has a `## Result` that is either measured output or an explicit `NOT RUN` with reason
- [ ] Security: no API key, voice id or signed URL in any eval file (`tests/consistency/no-secrets.sh` passes)

---

## Out of scope

TwelveLabs; Sonilo; OFox/Volcengine/MuAPI/MiniMax render adapters; no-retry-on-ambiguous-billing
for the indusia render offers (own ticket); slide/zoom transitions; transitions outside act
changes; per-platform social metadata; hardware encoders; batch variants.
