# ffmpeg Assembly (Phase 6 pass 2)

Turns generated clips and rendered explainer shots into one master. Schema and folder contract are in
`10-post-production-pipeline.md`; this file is the judgement around them.

Tool: `tools/edit_render.py`. Inventory first with `tools/probe_clips.py`.

---

## 1. Order of work

```
probe_clips.py            what do we actually have, and how long is it
   └── edit-plan.json     author it, then PRINT it for the user
         └── edit_render.py --print     the sheet plus the exact ffmpeg commands
               └── edit_render.py       render, then the A/V gate
```

The plan is validated **before** ffmpeg runs. A plan error found after a long encode is a plan error
found too late, so every check that can be made on numbers alone is made first: unknown segment kind,
missing source, inverted range, a trim longer than the clip.

---

## 2. Deciding each segment's length

The clip you have and the beat you need rarely match. In order of preference:

1. **Trim.** The clip is longer than the beat. Cut it. Prefer trimming the tail — a generated clip's
   last moments are where motion tends to drift.
2. **Re-time the beat.** The narration is what sets the beat, and if the VO is 6.4s the beat is 6.4s.
   This is why VO-first exists: with `vo-manifest.json` the right clip length was requested in the
   first place.
3. **Pad.** Only when the clip is genuinely shorter than the audio that must play over it.
   `pad_mode: freeze` holds the last frame; `black` appends black. A pad above **1.0s** is warned
   about because a long freeze reads as a stall rather than a beat.
4. **Regenerate.** When the gap is large, padding is a bandage. Regenerate the clip at the right
   length — for Kling that is an exact second between 3 and 15, so there is no reason to be off.

Never speed-ramp a clip to fit. It changes the motion the model produced and pulls the audio with it.

---

## 3. Inserting explainer shots

An `explainer` scene has no clip; it has a rendered Remotion shot in `shots/out/`. In the plan it is a
segment with `"kind": "shot"` and it behaves exactly like a clip: same scale and pad treatment, same
place in the concat order.

An **overlay** shot is different — it composites on top of a clip rather than replacing it, and that
is `tools/composite.py`, not this tool. A scene recorded as `live-action + overlay:<shot-id>` is
composited first, and the composited file is what the edit plan points at.

---

## 4. Normalising before concat

Every segment is scaled, padded to the target frame, and re-encoded to the same codec, frame rate,
sample rate and channel layout before concat. That looks wasteful and is not: `-c copy` concat only
works when every input already agrees, and generated clips do not — different platforms hand back
different frame rates and audio layouts, and a mismatched concat produces silent audio drops or a
stream that stops halfway.

---

## 5. The A/V duration gate

After every render:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 master.mp4
ffprobe -v error -select_streams a:0 -show_entries stream=duration -of csv=p=0 master.mp4
```

Equal within **0.04s**, one frame at 25fps. Failure means the render is **rejected**, not shipped with
a note.

Two details worth knowing:

- A small positive difference is normal. AAC encodes in frames of 1024 samples, so audio usually ends
  a few milliseconds after the video. That is what the tolerance is for.
- **Do not replace equality with a budget that grows along the timeline.** Drift accumulates, so a
  tolerance that scales with duration hides exactly the fault the gate exists to catch.

---

## 6. Making the master playable

A 10-bit HEVC master will not play in many players, and on 59.94fps footage the frames are stamped
about 0.1% fast. Both are fixed by re-stamping to true constant frame rate, with `-r` BEFORE `-i` so
no frame is dropped:

```bash
ffmpeg -r <src_fps> -i master.mp4 -c:v libx264 -crf 19 -pix_fmt yuv420p -c:a aac master-h264.mp4
```

This is the file the user reviews and the file later passes read.

---

## 7. Degradation

No ffmpeg means no render, and that is all it means. `--print` still produces the segment sheet, the
tool still prints every command it would have run, and the skill continues and says which capability
was lost. It never fails the phase and never pretends the master exists.
