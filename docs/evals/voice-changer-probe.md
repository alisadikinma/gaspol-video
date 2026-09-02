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

## Run 2 — 2026-09-03, a real platform clip

Source: `S12-penyerahan-v1.mp4`, a VEO-generated 8s clip from the moni-promo project. Two people at a
table, one speaking, room ambience throughout. Converted into a second account voice.

| | |
|---|---|
| Source duration | 8.000s |
| Converted duration | 8.034s |
| **Total drift** | **+0.034s** — inside the 0.05s tolerance, and 68% of it |
| Envelope cross-correlation | peaks at **lag 0 ms** (no global shift), falling to 0.39 at ±100 ms |
| Shared speech onsets | +0.080s, −0.020s, −0.020s, +0.000s |
| **Worst shared-event shift** | **+0.080s** |
| Structural difference | a ~250 ms pause at 2.40-2.65s in the source is **filled with sound** in the conversion |

### What run 2 changes

**Not a pass.** Total duration held and there is no global slip, but one event moved 80 ms — past one
frame — and a quarter-second pause was filled. Both are perceptible against a moving mouth.

**Not a fail either, because this is the wrong clip for the question.** Rule C-2 routes a scene to
`native+changer` only when a face fills more than 30% of frame — a single-speaker close-up. This clip
has a face at roughly 8%, two speakers, and heavy room ambience. It is out of distribution for the
rule it was meant to test.

### The finding that matters more than the verdict

**Speech-to-speech converts EVERYTHING in the audio, not just the dialogue.** Ambience, a second
speaker, room tone — all of it is rendered as the target voice. The filled pause is almost certainly
ambience becoming voice-like.

This was not anticipated in the design, and it changes what the pass has to do:

- The conversion input must be the DIALOGUE, not the whole scene bed. Where a clip carries heavy
  ambience, that ambience is destroyed by the conversion and has to be rebuilt.
- Phase 6 pass 3 already rebuilds domain ambience from `strategic-brief.md`, so the pieces exist. The
  order is what has to change: convert the voice, then lay the ambience back under it, rather than
  assuming the clip's own bed survives.

### Still owed

A run on the case the rule actually targets: a single-speaker close-up, face over 30% of frame, clean
dialogue, watched frame by frame at the conversion points. Until that exists, `native+changer` is
supported by measurement on the wrong clip and should not be presented as verified.

## What run 1 proves, and what it does not

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
