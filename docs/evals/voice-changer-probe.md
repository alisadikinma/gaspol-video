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

## Run 3 — 2026-09-03, a cloned target voice on a second real clip

First run where the target voice is a **clone of a real person** rather than an account preset.
Source: `S03a-empat-pertanyaan.mp4`, an 8s clip from the MoniBatamInovasi pitch — three people in a
meeting room, one speaking, wide framing. Target: an Instant Voice Clone built from an 8.4s sample.

| | |
|---|---|
| Source duration | 8.000s |
| Converted duration | 8.034s |
| **Total drift** | **+0.034s** — identical to run 2, on a different clip |
| Envelope cross-correlation | peaks at **lag 0 ms**, r = 0.891, falling to 0.61 at ±100 ms |
| Shared speech onsets | 8 of 12 within 20 ms; the other four at +0.070, +0.060, −0.080, +0.050 |
| Structural difference | 4 extra onsets (0.65, 2.62, 3.09, 3.25s) where the source had pauses |

### What run 3 adds

**The +0.034s is systematic, not content drift.** Two different clips, different lengths of speech,
different target voices, same 8.000s → 8.034s. 34 ms is about one MP3 frame (1152 samples at 44.1 kHz
= 26 ms) plus encoder delay. The tolerance is measuring container padding, not the model redistributing
time. That is worth knowing before anyone reads a future +0.034s as a warning sign.

**The correlation is much sharper than run 2** — r = 0.891 at lag 0 against run 2's shallower peak —
because this clip has one speaker rather than two. That is consistent with the run 2 finding: the
cleaner the input, the tighter the timing.

**The pause-filling repeats.** Four source pauses came back with sound in them. Same mechanism as run
2: ambience is converted into voice. The rule to feed dialogue rather than a scene bed holds.

**An 8.4s sample is enough for a usable IVC clone.** Below what ElevenLabs recommends, and the clone
was accepted and converted without `requires_verification`. Quality of the likeness is a listening
judgement, not something these numbers cover.

### Still owed, unchanged

This is still a wide shot — the speaker's face is roughly 5% of frame. Rule C-2 routes to
`native+changer` at face >30%, and no run has yet tested that. Three clips in, the timing evidence is
consistent and good, but the case the rule was written for has not been seen.

## Run 4 — 2026-09-03, the multi-speaker failure, and the fix

Run 3's output was played back and rejected: the female supporting character in
`S03a-empat-pertanyaan.mp4` had become the male target voice. This is the run that turned a
suspected weakness into a measured defect and a fix.

| Segment | Source | Whole-track conversion (run 3) | Span conversion (this run) |
|---|---|---|---|
| male, 0.03-3.50s | ZCR 1014 Hz | 1163 Hz — converted | 1015 Hz timbre changed, 90% of samples differ |
| female, 4.25-5.95s | ZCR 1317 Hz | **906 Hz — converted too, wrongly** | **1317 Hz, bit-identical** |

### What went wrong

Speech-to-speech takes an audio file, not a speaker. `voice_changer.mjs` sent the whole
track, so every voice on it was rewritten. Nothing in the tool or the reference said
otherwise, which is why it shipped.

### The fix

`--spans START-END[,START-END]` converts only the named turns and splices them into the
original bed with a 50 ms crossfade, level-matched to what they replace. `parseSpans`
refuses reversed or overlapping ranges rather than sorting them, because a wrong span
converts the wrong person while appearing to work. Whole-track conversion still exists and
now warns on every run.

### Diarization did not solve this, and should not be trusted to

AssemblyAI labelled both speakers `A`, even with `speakers_expected: 2` — the two
AI-generated voices are too close in its embedding space. What separated them cleanly was
pitch: 150 Hz / 136 Hz for the male turns against 214 Hz for the female one. The reliable
source of span boundaries is `av-script.md`, which already records who says what; pitch is
the check when the script is ambiguous.

### One more, smaller finding

An 8.4s sample produces a usable Instant Voice Clone, but ElevenLabs leaves `preview_url`
empty on API-created clones, so the web UI shows "This voice does not have a sample to
play". The clone is fine; only its preview is missing. Generating TTS with it does not
populate the field.

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
