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

**Tracks can be generated (v3.1.0).** A mood with no track yet is not a dead end — but generating one
spends ElevenLabs credits, so this is never a bare `gen_music.py` call:

```bash
python3 tools/gen_music.py --only sparse-ambient --length-s 20 --dry-run   # 1. show the plan first
# 2. confirm with the user — this bills ElevenLabs Music for the mood shown above
python3 tools/gen_music.py --only sparse-ambient --length-s 20             # 3. generate, master's length
```

Always `--dry-run` first, then ask the user to confirm before the real call — the dry run names
exactly which mood and length is about to be billed, and a mood generated for the wrong length is a
mood generated (and billed) twice. Always pass `--only <mood>` with the ONE mood the current scene's
tone derives to (the Tone -> Mood table above) — never a bare `python3 tools/gen_music.py` that
would generate every missing mood in the palette in one uncounted batch.

```bash
python3 tools/gen_music.py --force --only sparse-ambient   # regenerate one mood, re-bills ElevenLabs
python3 tools/gen_music.py --renorm                        # re-balance existing tracks, no API call
```

Library-first, same shape as `tools/gen_sfx.py`: a mood whose `tracks/<id>.mp3` already exists is
skipped and never re-billed unless `--force`. Each track is loudness-normalised toward
`palette.json`'s `defaults.target_lufs`, clamped so the peak never crosses `defaults.ceiling_dbfs` —
the resulting `catalog.json` (`{output_folder}` independent, lives in the library) records
`loudness_lufs` and `peak_dbfs` per track so `mix_music.py`'s own `gain_to_sit_under()` measurement
starts from a known level. `catalog.json` is gitignored, same as the tracks — it is regenerated
data, not a reviewable artefact.

Missing `ELEVENLABS_API_KEY` degrades loudly: the tool exits 1 naming which moods it could not make
and says to supply a licensed track by hand instead. A missing `palette.json` (wrong working
directory, or `--library` pointed somewhere without one) is the same kind of loud failure, not a
silent "nothing to generate" — the tool exits 1 naming the path it looked for. A network or TLS
failure while calling ElevenLabs is reported by name too, including a certificate hint if the
failure is Python not trusting the system's CA store.

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

---

## 5. A bed composed to the picture (`bed_source: video`, GV-8)

The palette route picks a mood and plays a track under it. The video route asks ElevenLabs
video-to-music to compose a bed for the edited master, so the changes in the music land on the cuts.

```bash
python3 tools/gen_music.py video {output_folder} --dry-run     # size and limits, no spend
python3 tools/gen_music.py video {output_folder}               # confirm first, this bills
```

Flags: `--master` (default `output/master.mp4`), `--description-file`, `--tags a,b` (up to 10),
`--model` (`music_v1`, `music_v2` default, `music_v2_5`), `--force`, `--dry-run`. With no
`--description-file` the description is the script's music direction (`music:` lines and the Music
column of `av-script.md`), cut to 1000 characters.

**When to use it:** the user asked for a bed that follows the film, and the master exists (run it
after pass 2, before the mix). **When not to:** a master over 600 s, or no paid plan. Video-to-music
needs an ElevenLabs plan with Music access; a free key gets HTTP 403.

**Why the proxy is picture-only.** The tool sends a small copy of the master with the audio removed
(`.tmp/music-proxy.mp4`, at most 1280 px, well under the 200 MB limit), deleted after a real run.
The music should follow the cuts, not react to the words: with narration in the upload the model
tends to score the speech, and the bed then fights the voice it must sit under.

Outcomes, by exit code:

| Exit | Meaning | What `/video-post` does |
|---|---|---|
| 0 | `output/music.mp3` written and normalised, or the master and inputs are unchanged since the last paid run (nothing re-billed) | one segment `0.0` to the master duration, `track: output/music.mp3`, `bed_source: video` |
| 1 | bad input (unreadable description file, description over 1000 characters, unknown model, more than 10 tags) | fix and rerun |
| 3 | no bed was made; the last line is `FALLBACK palette: <reason>` (master over 600 s, proxy over 200 MB, no key, HTTP 403 no Music access, HTTP 422, network error) | keep the palette segments, `bed_source: palette`, report the reason |

The request is sent once. After an ambiguous failure billing may already have happened, so the tool
never retries by itself; the user reruns on purpose. A sent request is recorded in `renders.json`
with phase `6` (schema in `10-post-production-pipeline.md` §3.8). The same fail-soft rule as section
4 applies: a missing bed never blocks the video, and the mix still measures the bed 12 dB under the
voice like any other track.
