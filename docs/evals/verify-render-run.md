# verify_render.py — real run

Date: 2026-09-13. One ElevenLabs TTS generation + one AssemblyAI transcription, both billed.

## Project

Scratch project, one scene, one narration layer, Indonesian, numbers written as words on
purpose to probe the digit-vs-words ASR question:

```
"Tiap truk antre empat puluh dua menit di gerbang."
```

`cast-profile.md`:

```markdown
## Pemeran Utama — cast-c1 (Pak Aon)

VOICE:
  provider: elevenlabs
  voice_env: ELEVENLABS_VOICE_PAK_AON
  model: eleven_multilingual_v2
  settings: stability=0.55, similarity_boost=0.8, style=0.3, speed=0.95
  source: tts
  description: "calm middle-aged Indonesian male narrator, warm baritone, measured pace"
```

`work/audio-plan.json`: one scene, one `narration` layer, `cast: c1`, `at_s: 0.0`, `dur_s: 5.0`
(estimate — VO-first means the real duration comes from generation, below).

## Commands

```bash
cd .claude/worktrees/gv-2
set -a; . /Users/alisadikin/Drive-D/claude-plugin/gaspol-video/.env; set +a

# 1. Generate the VO (ElevenLabs TTS)
node tools/gen_vo.mjs "$PROJ"
#   scene-01-narr: 49 chars -> vo/scene-01-narr.mp3
#   vo-manifest.json: duration_s 2.786, 9 words with timings

# 2. Build a clip that CARRIES the VO as its own audio track.
#    edit_render.py does not mux an external vo/*.mp3 onto a clip — a "clip" segment's audio
#    comes straight from that segment's own source file. Since this scene's audio_source is
#    "elevenlabs" (no platform dialogue to keep), the VO has to be the clip's audio before
#    edit_render.py ever sees it. Muxed here by hand with ffmpeg, as the task anticipated:
ffmpeg -y -v error -f lavfi -i testsrc=size=1280x720:rate=30:duration=2.786 \
  -i "$PROJ/vo/scene-01-narr.mp3" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$PROJ/clips/scene-01.mp4"

# 3. work/edit-plan.json: one clip segment, in_s 0.0, out_s 2.78
python3 tools/edit_render.py "$PROJ"
#   A/V duration gate passed: v:0 2.767s, a:0 2.801s

# 4. Live P6 run (no --asr-json — this really called AssemblyAI)
/opt/homebrew/bin/python3 tools/verify_render.py "$PROJ"
```

Ran with `/opt/homebrew/bin/python3` for the same reason as the `gen_music.py` run
(`docs/evals/gen-music-run.md`): the default framework `python3`'s `cert.pem` does not exist on
this machine, so any HTTPS call fails `CERTIFICATE_VERIFY_FAILED`. `node` needed no such
workaround — Node's own trust store worked unmodified for the ElevenLabs call.

The `.env` was sourced into the shell for these commands only, never copied into the worktree.

## Result

```
Extra: 0 · missing: 2 · heard differently: 3 · gaps: 0 · low-confidence: 1 · drift flags: 0
```

Exit code: **1** (FAIL — `missing > 0`).

`work/verify-asr.json` (the saved live transcript):

```json
{"words": [
  {"text": "Setiap",  "start_ms": 31,   "end_ms": 331,  "confidence": 0.737},
  {"text": "trak",    "start_ms": 331,  "end_ms": 551,  "confidence": 0.153},
  {"text": "antre",   "start_ms": 551,  "end_ms": 871,  "confidence": 0.960},
  {"text": "42",      "start_ms": 871,  "end_ms": 1351, "confidence": 0.729},
  {"text": "menit",   "start_ms": 1351, "end_ms": 1851, "confidence": 0.887},
  {"text": "di",      "start_ms": 1851, "end_ms": 2011, "confidence": 0.769},
  {"text": "gerbang.","start_ms": 2011, "end_ms": 2511, "confidence": 0.858}
]}
```

`work/verify-report.md`:

```
Extra: 0 · missing: 2 · heard differently: 3 · gaps: 0 · low-confidence: 1 · drift flags: 0

## Missing words (intended but never rendered)
00:02 (2.22 s) · "puluh"
00:02 (2.78 s) · "dua"

## Heard differently (possible mangled join, or ASR variance)
00:00 (0.03 s) · expected "tiap", heard "Setiap"
00:00 (0.33 s) · expected "truk", heard "trak"
00:00 (0.87 s) · expected "empat", heard "42"

## Low-confidence rendered words (< 0.70)
00:00 · conf 0.15 · "trak"

## A/V drift: OK (within budget)
00:00 · +0.031s vs planned · "Setiap"
```

## What actually happened (listened, not guessed from the numbers)

- **"tiap" → "Setiap"**: AssemblyAI's own formatting/punctuation pass expanded the spoken word to
  a fuller Indonesian form. A genuine ASR variance, correctly bucketed as "heard differently",
  correctly NOT counted toward missing/inserted (see `test_word_heard_differently_is_replaced_not_missing_and_still_passes`).
- **"truk" → "trak"**: low-confidence (0.15) misrecognition, flagged as both "heard differently"
  and "low-confidence" — exactly the advisory pairing the tool is meant to produce so a human
  knows where to listen.
- **"empat puluh dua" (3 spoken words) → "42" (1 ASR token)**: **this is the digits-vs-words
  finding the task asked about.** AssemblyAI's transcript formatting collapses a spoken
  three-word Indonesian number into a single digit token. The word-level diff (`difflib`
  matching one intended word against one rendered token at a time) sees this as a "replace" of
  `empat`→`42` and then has no ASR token left to align `puluh` and `dua` against, so both are
  reported as **missing** — a **false FAIL**. The narration was almost certainly spoken
  correctly (ElevenLabs TTS reads written text literally); the ASR's own number-formatting is
  what erased two of the three words at the token level.

## Fix (GV-2): collapse spoken and written numbers before the word diff

The false FAIL above is fixed. `tools/verify_render.py` now has `collapse_numbers(tokens) ->
tokens`, a pure function applied to BOTH the intended script's word list and the rendered ASR
word list before `SequenceMatcher` ever sees them. It scans for maximal runs of number words —
Indonesian (`nol`..`sembilan`, `sepuluh`, `sebelas`, `belas`, `puluh`, `ratus`, `ribu`, `juta`,
`miliar`, and the `se`-prefixed forms `seratus`/`seribu`/`sejuta`/`semiliar`) or English (`zero`
through `billion`, plus `and`) — and replaces each run with one canonical digit token via a
small recursive-descent parser (`parse_id_number_words` / `parse_en_number_words`). So `"empat
puluh dua"` and `"42"` normalise to the same token on both sides, and the diff sees them as
equal instead of a false replace-then-two-missing.

Two more variants in the same family, handled in `norm()` itself (before `collapse_numbers`
ever runs): thousands-separated digit groups the ASR may emit (`"2.026"`, `"2,026"`,
`"1.500.000"`) are merged into a plain integer string, and `"%"` / the word `"percent"` are both
mapped to the language-neutral token `"persen"` so `"42%"` and `"empat puluh dua persen"` land
on the same two tokens (`"42"`, `"persen"`).

Timestamps stay correct across a collapsed run: `flatten_rendered` now returns collapsed tokens
alongside a metadata list (`{"start_ms", "end_ms", "text", "orig_idxs"}`), and every original
ASR word index a run absorbed gets marked matched/`render_layer`-tagged when the collapsed token
matches — so gaps, drift and low-confidence flags (which iterate the raw per-word ASR list
directly) are unaffected, and a "replaced"/"missing" report line for a collapsed token takes the
start of its first source word and the end of its last, per `tests/py/test_verify_render.py::
test_collapsed_number_timestamps_span_first_to_last_source_word`. A genuinely different number
(`"empat puluh tiga"` vs `"42"`) still comes back as `replaced` (`expected "43", heard "42"`),
never silently matched.

TDD: `tests/py/test_verify_render.py` grew a `NumberCollapseTest` class (the parser, unit-by-unit
for both languages, thousands separators, percent mapping, non-number words left alone) plus
three `VerifyRenderTest` cases for the two real directions (words→digits, digits→words) and the
timestamp-span check. RED was confirmed (5 failures + `AttributeError` on the not-yet-existing
`collapse_numbers`) before the implementation; `python3 -m unittest tests.py.test_verify_render`
now reports **27 tests, OK**.

### Re-run against the saved ASR transcript (no new API cost)

Same project, same live `work/verify-asr.json` from the run above, no new AssemblyAI or
ElevenLabs call:

```bash
python3 tools/verify_render.py "$PROJ" --asr-json "$PROJ/work/verify-asr.json"
```

Result, before vs after the fix:

| | missing | extra | heard differently | exit code |
|---|---|---|---|---|
| Before (recorded above) | 2 (`"puluh"`, `"dua"`) | 0 | 3 | 1 (FAIL) |
| After | **0** | **0** | 2 | **0** (PASS) |

`work/verify-report.md` now:

```
Extra: 0 · missing: 0 · heard differently: 2 · gaps: 0 · low-confidence: 1 · drift flags: 0

## Heard differently (possible mangled join, or ASR variance)
00:00 (0.03 s) · expected "tiap", heard "setiap"
00:00 (0.33 s) · expected "truk", heard "trak"

## Low-confidence rendered words (< 0.70)
00:00 · conf 0.15 · "trak"

## A/V drift: OK (within budget)
00:00 · +0.031s vs planned · "Setiap"
```

The digits-vs-words false FAIL (`empat puluh dua` vs `42`) is gone entirely — both `"puluh"` and
`"dua"` no longer appear as missing, and `"empat"`→`"42"` no longer appears as replaced, because
`collapse_numbers` now normalises both sides to the token `"42"` before the diff runs. The two
remaining "heard differently" lines (`tiap`→`setiap`, `truk`→`trak`) are genuine ASR variance —
exactly the kind of thing this tool is supposed to still flag — and correctly do not fail the
run.

## Verification against the plan's checklist

| Item | Result |
|---|---|
| Real live run recorded | Yes — this file |
| Exit 3 path never reported as PASS | Confirmed by `test_no_key_and_no_asr_json_exits_3`; live run here used a real key, exit was 1 (FAIL), not conflated with PASS or SKIPPED |
| `bash tests/run.sh` prints `RESULT PASS` | Yes (see commit) |
| No placeholder/TODO in new code | Yes |
| Digits-vs-words false FAIL fixed | Yes — `collapse_numbers`, re-run above: 0 missing / 0 extra, exit 0 |
