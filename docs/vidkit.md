# vidkit: reusable animation and assembly library

`tools/vidkit/` collects the helper scripts that kept being rewritten per project (Ekaputra, Moni
Batam, indusia-ai-fms catalog-4, REA, Dampak) into one tested package. Core is stdlib + ffmpeg.
Only `bond` needs `cv2` + `numpy` (the `tools/setup.sh` venv has them).

Run from the plugin root: `python3 -m tools.vidkit --help`. Import: `from tools.vidkit import join, gates`.

| Module | What | Replaces (per project) |
|---|---|---|
| `ff` | `probe`, `duration`, `run`, `ffmpeg` | ad-hoc `ffprobe` helpers in every script |
| `gates` | `gate_av` (video = audio length), `gate_uniform` (same sample rate and channels before concat) | `gerbang.py` |
| `join` | `concat_copy`, `join_xfade`, `clip_starts` (timeline maths for dissolves) | `join.py`, the `rakit_*.py` concat steps |
| `patch` | `freeze_box`: freeze a rectangle of a clip to one frame | `freeze_patch.py` |
| `sheet` | `contact_sheet`, `montage` | `sheet.py`, `mont.py` |
| `synth` | `notification`, `alarm`, `render` (layered ffmpeg tones) | `bunyi-notif.py`, `bunyi-alarm.py` |
| `speech` | `words_from_alignment`, `speech_spans`, `gaps`, `snap_to_gaps`, `energy_db` | `kata.py`, `energi.py`, `geser_cue.py` |
| `loudness` | `normalize`: two-pass loudnorm, audio trimmed to picture | `mix_akhir.py` |
| `track` | `smooth_track`: median-filter a tracked screen box, pin one angle | `haluskan-lacak.py` |
| `bond` | `bond_print`: motion-tracked print on cloth (needs cv2) | `shirt_bond.py` |

## Lessons baked in (each cost a real re-render)

- `concat` builds the encoder from the FIRST file: mixed mono/stereo or 44.1/48 kHz corrupts the rest. `gate_uniform` runs first.
- `xfade` overlaps clips, so total length shrinks by the transitions. Take every time point from `clip_starts`. A 0 s transition inside a dissolve chain breaks it; `join_xfade` clamps to one frame.
- Audio is never cross-faded: each clip's audio stays whole and is delayed to its start.
- `loudnorm` shifts timestamps ~0.08 s. Reset with `asetpts` before `atrim`, else real audio is cut and the A/V gate fails.
- A sidechain-ducked mix mutes SFX under narration at any gain. `snap_to_gaps` moves the cue into a speech gap instead.
- ffmpeg `sine` is ~18 dB below full scale. Synth gains are corrected for it; read `synth.measure`.
- `apad` after `amix` truncated to the longest input on some runs. `synth.render` and `join_xfade` add a silent bed of full length instead.

## Not folded in (and why)

- Per-project `rakit_k*.py`, `build_k*.py`, `mix.py`: they hard-code scene ids, timings and file names. The reusable pieces inside them are now the modules above.
- `track_quad.py`, `sudut-lacak.py`, `lacak-layar.py`, `layar.py` (4-corner phone/monitor tracking): overlap `tools/track_screen.py`. Their per-frame matte idea is a candidate for a later merge there.
- Slide tooling: moved to `gaspol-catalog` `tools/deckkit`.
- Remotion `gen-registry`, `render-all`, `render-stills`, `qa-frames`, `captionPages`, `overlayFx`: already identical to `templates/remotion/` (projects copied them). Verified with diff.

## Node (`tools/vidkit/js/`)

| Module | What | Replaces |
|---|---|---|
| `env.mjs` | `parseEnv`, `loadEnv`, `requireKeys` (names missing keys, never values) | the `parse()` pasted at the top of every project script, with a hard-coded .env path |
| `eleven.mjs` | `tts` (settings + seed), `sttWords` (Scribe word timings), `sfx`; CLI `tts|stt|sfx` | `tts-satu`, `tes-suara`, `stt`, `sfx/gen` |
| `cast_voice.mjs` | voice change with per-character settings and seed, spans only; plan json | `voice-changer/run.mjs` (which also imported the plugin by a versioned cache path) |

`templates/remotion/scripts/frames.mjs` and `qa-end.mjs` (multi-frame / end-state QA) now ship with every scaffold.

Tests: `tests/py/test_vidkit.py`, `tests/node/vidkit-js.test.mjs` (run with the venv python to include the `bond` test).
