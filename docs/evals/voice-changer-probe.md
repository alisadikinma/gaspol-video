# Probe — does speech-to-speech preserve duration?

**Why this exists.** The mixed-source strategy (spec risk #1) rests on one assumption: converting a
platform-spoken line into a locked character voice keeps the timing, so the mouth still matches. If
that is false, the whole per-scene mixing decision is wrong and has to be reopened — the fix is never
to stretch the audio, which produces exactly the artefact the locked voice exists to avoid.

The plan made this a hard stop in Phase H: prove it on the real API before writing the workflow as
settled.

---

## Run 1 — 2026-09-03

| | |
|---|---|
| Endpoint | `POST /v1/speech-to-speech/{voice_id}` |
| Model | `eleven_multilingual_sts_v2` |
| Source voice | Roger (account default) |
| Target voice | Sarah (account default) |
| Line | "Sudah lewat, Pak. Truknya boleh masuk sekarang, gerbang dua." — Indonesian, the shape of an on-screen dialogue line |
| Source duration | **3.297s** |
| Converted duration | **3.297s** |
| **Drift** | **+0.000s** (tolerance 0.050s) |
| Verdict | **PASS** on duration |

Measured with `ffprobe -show_entries format=duration` on both files. Not rounded to flatter the
result: the two durations were identical to the millisecond.

---

## What this proves, and what it does not

**Proved:** the conversion returns audio of the same total length. Total-length drift was the failure
mode that would have made lip-sync impossible on principle, and it did not occur — not "within
tolerance", but exactly zero.

**Still owed:** a visual check on a REAL platform clip with a face speaking. Identical total length
does not by itself guarantee that every phoneme lands where it did before; the model could in
principle redistribute timing inside the clip while keeping the envelope. The measured result makes
that unlikely, and the risk is now low rather than unknown, but low is not verified.

**What that check needs:** one generated clip (VEO / Seedance / Kling) with an on-screen speaker whose
face fills more than 30% of frame, run through `tools/voice_changer.mjs`, then watched.

This is recorded as open debt in the ledger, not quietly assumed. Until it is done, the honest
statement is: duration preservation is measured and holds; visual lip-sync after conversion is
expected to hold and has not been seen.

---

## Re-running

```bash
node tools/voice_changer.mjs <clip.mp4> --voice-env ELEVENLABS_VOICE_C2 --out vo/probe.mp3
```

The tool prints the drift on every run and refuses to write beyond 0.05s, so every future conversion
is its own miniature version of this probe. A drift line in normal output is not noise — it is the
evidence that this assumption still holds.
