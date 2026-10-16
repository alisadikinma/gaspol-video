# GV-19 Phase A — audio and timing study of the reference Shorts

Measured with `python3 -m tools.vidkit audiostudy` (commit 35d7462) on **12 clips**: sources 1-13 of
NotebookLM notebook `SAMUEL-STYLE 2026-10`, except source 10 (HTTP 403 on every attempt). The clips sit in a
scratch folder outside the repo and are not committed. This may not be the same 13 clips the spec measured
earlier; the spec does not list which ones.

**Word timings: not measured.** The owner declined the billed speech-to-text run, so `relate()` ran with no
words. Nothing below says whether a sound lands on a spoken word.

## Per clip (data)

| clip | sec | LUFS | cuts | onsets/min | energy range dBFS (2 s windows) |
|---|---|---|---|---|---|
| s01 | 59.7 | -9.8 | 23 | 136 | -11.9 to -6.3 |
| s02 | 44.4 | -14.5 | 24 | 119 | -17.1 to -6.6 |
| s03 | 58.6 | -15.4 | 29 | 127 | -24.8 to -11.8 |
| s04 | 45.0 | -18.1 | 18 | 141 | -22.7 to -14.7 |
| s05 | 58.3 | -12.2 | 19 | 99 | -23.4 to -8.3 |
| s06 | 60.1 | -19.2 | 14 | 174 | -26.5 to -13.9 |
| s07 | 59.9 | -14.0 | 19 | 177 | -15.7 to -10.1 |
| s08 | 60.0 | -10.6 | 37 | 126 | -11.3 to -8.5 |
| s09 | 37.6 | -11.9 | 14 | 121 | -16.3 to -8.7 |
| s11 | 44.5 | -10.3 | 16 | 132 | -13.3 to -8.0 |
| s12 | 58.8 | -13.2 | 27 | 117 | -15.4 to -9.1 |
| s13 | 60.1 | -13.7 | 29 | 157 | -16.5 to -11.5 |

Tempo output (`tempo_bpm`) per clip: 94, 115, 136 and 167 BPM appear, with no pattern. See finding 4.

## Findings

| # | claim | number | data or interpretation | clips |
|---|---|---|---|---|
| 1 | Integrated loudness is spread widely, not a single level | -9.8 to -19.2 LUFS, mean -13.6 | data | all 12 |
| 2 | The earlier spec figure (-7.8 to -13, mean about -11) is not reproduced by this sample | 5 of 12 clips are at or above -12.2 LUFS; 7 are quieter | data | all 12 |
| 3 | Cut rate is moderate to high | 14 to 37 cuts per 37-60 s clip, about 0.3 to 0.6 cuts per second | data | all 12 |
| 4 | Onset counts follow speech, not SFX | 99 to 177 onsets per minute, about 2 per second, the pace of syllables | interpretation (a count cannot separate a sound effect from a consonant) | all 12 |
| 5 | The tempo values are not a music tempo | Four recurring values (94, 115, 136, 167) look like speech rhythm folded into 60-180 BPM | interpretation; treat as `none detected` for music | all 12 |
| 6 | Music genre and SFX type | not measured | not measured | none |
| 7 | SFX onset vs spoken word offset | not measured | not measured (no word timings) | none |
| 8 | SFX onset vs cut offset | not measured (onsets cannot be told apart from speech) | not measured | none |
| 9 | Energy swings of 5 to 15 dB inside a clip | per-clip ranges in the table | data (cause unknown: speech dynamics, music or SFX) | all 12 |

## What this changes in phases B, C, D

- **B (overlay):** nothing here sets the icon list; keep the six planned icons. Do not copy any loudness figure into
  the overlay work.
- **C (retention gate):** a cut every 1.6 to 4.3 s is the measured range, so the course default of 3.0 s for a static
  frame is plausible. It stays tagged `source: course`. Keep BGM headroom at the existing 12 dB.
- **D (framework):** nothing here supports a claim about SFX or music. The framework must not state one as measured.
- **Loudness target:** this sample does not support moving the plugin target from -14 LUFS. Leave it.
- **Follow-up that needs a decision:** a real SFX/music finding needs word timings (billed STT) or a stem separation.
  Neither was approved. Recorded under "Utang terbuka" in the ledger.
