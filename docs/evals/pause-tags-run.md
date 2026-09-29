# gen_vo.mjs pause tags and reuse — real run (GV-8 Phase L)

Date: 2026-09-29. Spend approved by Ali. One narration layer in a scratch project, voice
`ELEVENLABS_VOICE_PAK_AON` (named only; the id is never written to the repo or the manifest):

`Solar habis sebelum truk sampai. [pause: 1.5s] Sekarang kita tahu kenapa.`

## Commands

```bash
node tools/gen_vo.mjs <scratch> --dry-run
node tools/gen_vo.mjs <scratch>          # run 1
node tools/gen_vo.mjs <scratch>          # run 2, nothing changed
# edit the tag to [jeda: 0.8 detik]
node tools/gen_vo.mjs <scratch>          # run 3, only the pause changed
```

## Result

| Run | Log | Requests |
|---|---|---|
| dry run | `would generate scene-01-narr (59 chars)` | 0 |
| 1 | `2 chunks (0 cached), 1 pauses (1.50s silence)` | 2 |
| 2 | `reused (unchanged)` | 0 |
| 3 (pause 1.5 → 0.8 s) | `2 chunks (2 cached), 1 pauses (0.80s silence)` | 0 |

Measured with `ffmpeg -af silencedetect=noise=-45dB`:

| Run | Silence start | Silence end | Silence length | `Sekarang` start_ms in manifest | File length |
|---|---|---|---|---|---|
| 1 (1.5 s tag) | 1.9208 s | 3.4505 s | 1.5297 s | 3450 | 4.797 s |
| 3 (0.8 s tag) | 1.9208 s | 2.7505 s | 0.8297 s | 2750 | 4.097 s |

- The measured gap is the requested pause plus ≈0.03 s of natural breath at the chunk edges, and
  the file shrank by exactly 0.700 s when the tag changed by 0.7 s — the silence is sample-exact.
- The first word after the pause (`Sekarang`) starts in the manifest at exactly the measured
  silence end, in both runs, so captions and P6 stay aligned.
- `chars` = 59, the tag-stripped length. `.tmp/` holds two `vocache-*.mp3/.json` pairs; a
  search of the whole scratch project for the voice id value finds nothing.
