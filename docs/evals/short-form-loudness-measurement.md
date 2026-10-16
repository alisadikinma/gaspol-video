# Short-form loudness measurement (evidence, not a rule)

Measured 2026-10-16 with `ffmpeg -af ebur128=peak=true` on 12 public vertical Shorts from ONE creator channel, downloaded to a scratch folder (never into this repo). Purpose: a data point for GV-18 Phase N. It does NOT create a loudness profile: one channel is not a platform rule, and `media/loudness-profiles.json` accepts only sourced numbers.

Correction: earlier session notes said '13 Shorts, -7.8 to -13 LUFS'. The correct figures are 12 clips measured (one download failed) and a full range of -24.1 to -7.8 LUFS; the -24.1 clip was left out of the earlier summary.

| # | Format | Duration (s) | Camera cuts | Integrated LUFS | LRA (LU) |
|---|---|---|---|---|---|
| 1 | podcast clip | 37 | 17 | -11.9 | 6.2 |
| 2 | podcast clip | 55 | 28 | -10.3 | 9.5 |
| 3 | vlog/podcast mix | 58 | 8 | -24.1 | 8.3 |
| 4 | podcast clip | 59 | 37 | -10.6 | 2.1 |
| 5 | vlog | 60 | 42 | -13.6 | 3.0 |
| 6 | podcast clip | 48 | 16 | -8.6 | 4.1 |
| 7 | vlog | 33 | 10 | -12.5 | 8.2 |
| 8 | experiment demo | 52 | 11 | -7.8 | 1.5 |
| 9 | single-take talking head + overlays | 53 | 2 | -11.7 | 4.6 |
| 10 | single-take talking head + overlays | 42 | 0 | -12.6 | 4.4 |
| 11 | single-take talking head + overlays | 31 | 0 | -12.3 | 2.9 |
| 12 | single-take talking head + overlays | 51 | 2 | -10.5 | 4.6 |

- All 12: min -24.1, max -7.8, median -11.8, mean -12.2 LUFS.
- Without the one outlier (-24.1): min -13.6, max -7.8, median -11.7, mean -11.1 LUFS (11 clips).
- The outlier is quiet, not louder than the rest; the other 11 sit between -13.6 and -7.8, louder than this plugin's -14 default.
- Camera cuts counted with ffmpeg scene detection threshold 0.25. Two single-take clips show 0 cuts; their motion graphics are overlays on one take.

What this supports: short-form creators master louder than -14 LUFS in this sample. What it does not support: a platform target. The decision to add a `short-vertical` profile needs a sourced number (platform documentation or the owner's own measurement policy).
