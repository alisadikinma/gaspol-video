**Ticket:** GV-22

# GV-22: Pipe escape in routes, and the remaining ffprobe callers move to vidkit.ff

Follow-up to GV-20 (v3.18.0, merged at `e33f52a`). GV-20 moved 2 of 19 ffprobe callers and put
the other 17 on `ffprobe_allow`. This ticket decides each of the 17 and moves the ones that can move.

## Design

### Part 1: `|` in a route

`docs/tool-routing.md` is a GitHub table. A bare `|` inside a cell splits the cell, even inside a
code span. GitHub accepts `\|` and renders it as `|`.

- `tools/registry.json`: the route `Phone notification / alarm sound without paid files` gets
  `use: "`vidkit synth notification\|alarm`"` (JSON string `\\|`).
- `tools/registry_build.py` validate (line 177 today): stop removing code spans before the check.
  New rule for `task` and `use`: every `|` must be preceded by `\`. A bare `|` anywhere is an error
  naming the route. A newline stays an error.
- `python3 tools/registry_build.py render`, then `render --check` exits 0.

### Part 2: ffprobe callers

Decision per file (approved 2026-10-17):

| File | Fields it reads | Decision |
|---|---|---|
| `tools/burn_subs.py` | video height | move |
| `tools/clean_voice.py` | format duration, has audio stream | move |
| `tools/composite.py` | stream duration, width/height/fps, has stream, `pix_fmt` | move (after `pix_fmt` is added to `ff.probe`) |
| `tools/edit_render.py` | format duration, per-stream duration | move |
| `tools/gen_music.py` | format duration | move |
| `tools/make_stems.py` | format duration | move |
| `tools/mix_music.py` | format duration | move |
| `tools/mix_sfx.py` | format duration | move |
| `tools/overlay_plan.py` | format duration | move |
| `tools/qa_frames.py` | stream duration, fps, format duration | move |
| `tools/gen_vo.mjs` | format duration (Node) | move to new `tools/vidkit/js/ff.mjs` |
| `tools/voice_changer.mjs` | format duration (Node) | move to new `tools/vidkit/js/ff.mjs` |
| `tools/person_mask.py` | `nb_read_packets` (`-count_packets`) | stay |
| `tools/probe_clips.py` | full `-show_streams` JSON for the manifest | stay |
| `tools/vidkit/color.py` | four colour fields | stay (inside vidkit, already uses `ff.run`) |
| `tools/registry_build.py` | none, only names ffprobe | stay |
| `tools/retention_gate.py` | none, only `shutil.which` | stay |

Result: `ffprobe_allow` goes from 17 entries to 5.

#### Changes to `tools/vidkit/ff.py`

- `probe()` adds `pix_fmt` to the video dict (one more `show_entries` field).
- `run()` turns a missing binary (`FileNotFoundError`) into `FFError("<binary> not found on PATH")`,
  so callers handle one error type.

#### New `tools/vidkit/js/ff.mjs`

`probeDuration(path)`: runs `ffprobe` `format=duration`, returns seconds, or `null` when ffprobe is
missing or the output is not a number. Same contract both Node tools have today. The registry gets
an entry for it, and the ffprobe ratchet treats it as the second allowed owner beside
`tools/vidkit/ff.py`.

#### Behaviour stays per tool

Each tool keeps what it does today when ffprobe is missing or the file is unreadable:

| Tool | Today when ffprobe is missing / file unreadable |
|---|---|
| clean_voice | raises `CleanError("ffprobe not found on PATH")`; unreadable duration returns `None` |
| composite | raises `CompositeError` (missing binary, unreadable file) |
| make_stems | raises `StemError` |
| mix_music, mix_sfx | returns `None` |
| qa_frames | exits 2 before probing |
| gen_vo.mjs, voice_changer.mjs | returns `null` |
| others | read during planning from the code, recorded in the plan |

The local wrapper in each tool stays (same name, same return), and only its body calls
`ff.probe` / `ff.duration` and maps `ff.FFError` to the tool's own result. Callers do not change.
Module-level `FFPROBE = shutil.which("ffprobe")` goes where nothing else reads it; tests that set
`module.FFPROBE = None` are rewritten to simulate the missing binary through `ff`.

## Out of scope

- Changing what any tool does beyond swapping the probe.
- Moving `person_mask.py`, `probe_clips.py`, `color.py` (fields `ff.probe` does not return).
- Making the ratchet scan smarter so `registry_build.py` and `retention_gate.py` drop off the list.

## Data Integration Map

| Component | Data source | Existing? | Notes |
|---|---|---|---|
| Route text | `tools/registry.json` routes | yes | one `use` value changes |
| Pipe rule | `registry_build.validate` | yes | rule narrowed |
| Probe | `tools/vidkit/ff.py` `probe`, `duration`, `has_audio` | yes | add `pix_fmt`, missing-binary error |
| Node probe | `tools/vidkit/js/ff.mjs` | no | new, one function |
| Allowlist | `tools/registry.json` `ffprobe_allow` | yes | 17 to 5 |
| Ratchet gate | `tests/consistency/tool-registry-contract.sh`, `tests/py/test_registry.py` | yes | second owner `ff.mjs` |

## Testing

- `test_registry.py`: bare `|` in `use` (inside and outside backticks) is refused; `\|` passes.
- `render --check` exits 0 after the route change.
- `test_vidkit.py`: `probe()` returns `pix_fmt`; `run()` with a missing binary raises `FFError`.
- Per moved tool: a test that the wrapper returns the same value on a real fixture clip
  (`tests/py/media.py`) and the same result when ffprobe is missing. Written before the swap.
- `tests/node/vidkit-js.test.mjs`: `probeDuration` on a fixture and with ffprobe absent from PATH.
- Ratchet: removing a moved tool's allowlist entry does not fail the gate; adding a raw ffprobe
  call to a moved tool does.
- `bash tests/run.sh` green at the end.

## Risks

- A tool's missing-binary behaviour differs subtly from the table above. Mitigated: the plan reads
  each wrapper and the test pins today's behaviour first.
- `ff.probe` reads more fields than a single-field probe; slower only by a negligible amount.
- `CLAUDE.md` ticket counter conflicts with `GV-21-tidy` on merge (both edit the same line). Take
  the higher number.
