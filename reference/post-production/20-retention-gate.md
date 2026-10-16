# 20. Retention gate

`tools/retention_gate.py` measures five retention rules on a finished cut. Every number below is
**course advice** (`source: course`), not platform data. The tool reports; it does not block.

## Why it reports instead of blocking

A gate that fails a cut on a borrowed number becomes a quality ceiling: a deliberate 4 s held
frame would be refused. So `report` always exits 0 on a rule FAIL and the owner decides. Exit 2
means the tool could not run (missing master, no ffmpeg, malformed plan or config). The one real
gate is `check`, which makes the in-session b-roll judgment mandatory.

## Rules and defaults

| Rule | Default | Measured how |
|---|---|---|
| R1 static frame | `static_max_s = 3.0` | `ffmpeg -vf freezedetect=n=0.003:d=<limit>`; every interval of the limit or longer is a FAIL, so a 3.0 s still FAILs (`>=`) |
| R2 hook | `hook_first_word_by_s = 3.0` | earliest word start in `vo/vo-manifest.json` (ms) or `--words-file` |
| R3 foreshadow | `foreshadow_by_s = (3.0, 6.0)` | the `av-script.md` table row whose Beat column is `Foreshadow` (any case, bold ok); start of its Timecode `M:SS` / `M:SS.s`. No such row is a FAIL |
| R4 b-roll matches the word | judged in-session | one section per b-roll segment in `work/retention-qa.md`: range, words spoken over it, contact sheet in `.tmp/`, one Verdict cell |
| R5 BGM under the voice | `bgm_headroom_db = 12.0` (`mix_music.MIN_HEADROOM_DB`) | `output/stems/voice.wav` against `music.wav` (from `tools/make_stems.py --all`), inside each spoken span |

B-roll means every edit-plan segment with `kind: shot`, plus any segment with `role: b-roll`.
Everything else is the main take. Timeline position is the running sum of segment lengths
(`out_s - in_s + pad_end_s`), the same layout `edit_render.py` uses.

## Word timings and film offsets

`vo-manifest.json` times are per item, not per film, and `gen_vo.mjs` writes no offset. The film
offset of an item is the `at_s` of the `work/audio-plan.json` layer whose `out` file has the same
name as the item (the key `gen_subs.py` uses); an `at_s` on the manifest item itself wins. If any
item has no offset, even a single one, R2 is `not measured` and the reason says so: a late-starting
layer must not read as starting at 0 s. Pass `--words-file words.json`
(`[{"word","start","end"}]` in film seconds, any order) instead. R5
uses the same words for its spoken spans, else the stretches where the voice stem is above -50 dBFS.

## Override

Order: defaults, then `work/retention.json`, then command-line flags.

```json
{"static_max_s": 4.0, "foreshadow_by_s": [3.0, 8.0]}
```

Flags: `--static-max-s`, `--hook-first-word-by-s`, `--foreshadow-by-s LO HI`, `--bgm-headroom-db`.
An unknown key in `retention.json` exits 2.

## Statuses

| Status | Meaning |
|---|---|
| `PASS` / `FAIL` | measured against the threshold |
| `not measured` | an input is missing (no word timings, no `av-script.md`, no edit plan, no stems). Never read it as a pass |
| `needs verdict` | R4 Verdict cells are still empty |

## Commands

```
python3 tools/retention_gate.py report <project> [--master FILE] [--words-file FILE]
python3 tools/retention_gate.py check  <project>
```

`report` writes `work/retention-report.md` (rule, status, numbers, threshold, source) and
`work/retention-qa.md`. Fill each Verdict cell with `PASS`, `FAIL: <what is on screen vs what is
said>` or `UNSURE: <why>`. A re-run keeps a verdict while the segment's source clip has the same
sha256 and clears it, with a note, when the clip changed. `check` reads only the Verdict cells and
exits 1 on a missing section, an empty or malformed cell, a `FAIL:` cell, or a verdict judged
against different bytes. `UNSURE:` is a note for a human, not a failure.

## Real run

Finished cut: `REA-final.mp4` (93.13 s), read-only. The scratch project folder held only a copy of
`vo/vo-manifest.json`; the master was passed with `--master`. The REA project has no `av-script.md`,
no `work/edit-plan.json` (it was assembled by project scripts) and no `output/stems/`, and its
there was no `work/audio-plan.json` to place the manifest items, so those inputs were not invented and four rules read `not measured`.

```
python3 tools/retention_gate.py report <scratch> --master .../final/REA-final.mp4   (exit 0)
```

| rule | status | numbers | threshold | source |
|---|---|---|---|---|
| R1 static frame | PASS | no still of 3.0 s or longer | no still >= 3.0 s | source: course |
| R2 hook | not measured | no film offset for vo item '<first item id>' (no at_s in vo-manifest.json and no matching layer in work/audio-plan.json), so word times cannot be placed on the film timeline; pass --words-file | first spoken word by 3.0 s | source: course |
| R3 foreshadow | not measured | no av-script.md | Foreshadow starts 3.0-6.0 s | source: course |
| R4 b-roll vs word | not measured | no work/edit-plan.json | every b-roll segment judged PASS in work/retention-qa.md | source: course |
| R5 bgm headroom | not measured | stem missing: voice.wav, music.wav (run tools/make_stems.py --all) | voice >= 12.0 dB over music in every spoken span | source: course |

Measured: R1 only. Not measured: R2, R3, R4, R5, each for the missing input named in its row.
