# Music Bed (Phase 6 pass 4)

`av-script.md` has carried a per-scene music direction since Phase 2 — the Audio column reads
`Narration + SFX + Music` — and `script-to-scene-bridge.md` already maps each tone to a music style.
Until v3.0.0 nothing read either. This pass does.

Schema (`music-plan.json`) in `10-post-production-pipeline.md`. Values in `global-promo-config.md`
§29.3. Tool: `tools/mix_music.py`.

---

## 1. The track is derived, not asked for

```
av-script.md per-scene music direction
   +  video tone (global-promo-config.md §13)
        -> mood id in media/music/library/palette.json
              -> a track in media/music/library/tracks/
```

| Tone | Mood |
|---|---|
| Serious | `tense-low-pulse` |
| Inspirational, Humorous | `warm-uplift` |
| Professional | `neutral-corporate` |
| Casual | `sparse-ambient` |
| Edgy | `driving-build` |

Asking the user again for something the script already says is how a pipeline loses the thread
between what was written and what was made.

**Audio files are never committed.** `palette.json` holds the mood recipes; the tracks are yours,
licensed by you, in `tracks/`.

---

## 2. Under the voice, measured

The bed sits at least **12 dB** below the voice, and that is measured rather than trusted to a fixed
gain: `gain_to_sit_under()` compares the two levels and returns the correction, and it never returns a
boost. A default of -22 dB is the starting point, not the guarantee.

Music and SFX both duck under the same voice, so they also have to be reconciled with each other. Mix
SFX first: cues are short and land on moments, while the bed is continuous. A bed that competes with
a cue makes both mushy, and the cue is the one carrying meaning.

---

## 3. Segments, fades, and a track that is too short

- Segments never overlap. Two beds at once fight each other and the voice, so an overlap is rejected
  rather than mixed.
- Segments that touch end-to-start are fine and normal: that is a bed change on a beat.
- A segment running past the master is trimmed to the master.
- A track shorter than its segment either **loops** with a crossfade, or the **segment shortens** when
  looping would repeat more than four times. The tool prints which it chose — a four-times loop of an
  eight-second track is audible as a loop, and being told is better than wondering.

Default fades: 1.2s in, 2.0s out. A bed that starts abruptly reads as a mistake.

---

## 4. Fail-soft, deliberately

A music track that will not load, fade or mix leaves a **finished voice-only video** plus a warning
naming what failed, and an exit code of 0.

This is the opposite of the A/V duration gate, and the asymmetry is intentional:

| Failure | Behaviour | Why |
|---|---|---|
| A/V durations disagree | **reject the render** | invisible until someone watches the whole thing; ships broken |
| Music bed fails | **warn and ship** | obvious on the first play, and the video is still usable without it |

Blocking the deliverable on a background track would trade a working video for a missing one.
