# GV-24 surface insert — real-clip proof

Date: 2026-10-17. Machine: Apple M5 Pro, macOS 26, MPS. Tools: `vidkit embroider` at `54ba69f`.

## Shirt (embroidery)

Project: REA (Reverse Engineer Anything), scene 01. 720×1280, 24 fps, 4.0 s, presenter in a cream
hoodie, hands moving in front of the chest. The first attempt at this logo was a flat paste
(`clips/_v2-baju-tempel/scene-01-print.mp4`): it ran off the hoodie edge and floated over the folds,
so the scene was re-rendered in VEO 3.1 with the print baked in (`clips/scene-01-print.mp4`).

shirt_source: REA-Reverse_Engineer_Anything/clips/_v2-baju-tempel/scene-01.mp4 + work/print-sablon.png (1600×392 RGBA)
shirt_command: python3 -m tools.vidkit embroider <source> print-sablon.png emb-l0.mp4 --at 232,840 --width 140 --hand 220,1040 --hand 420,1020 --hand 315,880 --hand 387,880
shirt_result: {"frames": 96, "lost_frames": 1, "shirt_area_ratio": 344.319}, 85.8 s wall time
shirt_qa: docs/evals/surface-insert-rea-zoom.png (frame 30, 4× crop: top = run 2, bottom = run 3 accepted)
shirt_verdict: owner, 2026-10-17 — "sudah oke.. lanjut" (accepted after three runs, see below)

### The three runs

| Run | Settings | Owner verdict | What was wrong |
|---|---|---|---|
| 1 | `--at 230,830 --width 200 --hand ×2`, before Phase L0 | not good | looks like a print; the text crossed the hoodie drawstring |
| 2 | VEO placement `--at 232,840 --width 140`, drawstrings added as `--hand` points | (not asked) | drawstring fixed; text thin and faded grey, teal line almost gone |
| 3 | same as run 2, after Phase L0 (min stroke, 3× relief, colour kept, raised shadow, edge fuzz) | accepted | — |

What run 3 shows on a 4× crop of frame 30: the teal underline reads as twisted satin thread and keeps
its colour; the black text stays black; a soft contact shadow sits below-right of the design; the
design stays on the hoodie and between the drawstrings on every frame and bends with the folds.

What it does not show, stated plainly:
- The text strokes are under 2 px wide at 140 px design width. Raised relief cannot be resolved at
  that size, so it reads as thread texture, not as clearly raised embroidery. Real embroidery has the
  same limit (minimum lettering around 5 mm); a bigger or bolder design is the fix, not more tuning.
- The three social icons became blobs at this size; `@alisadikinma` and `.com` are softer than the
  flat run.
- The hands never pass in front of the design in this clip, so hand occlusion is proven only on the
  synthetic test (0 changed pixels under the hand), not on this footage.
- A drawstring is not excluded automatically: SAM masks it as part of the hoodie. It has to be passed
  as a `--hand` point.

## Screen (app insert)

screen_skipped: owner, 2026-10-17 — no failing real screen clip available; chose to release with the shirt proof only. Screen insert is proven on synthetic clips only (green: corner error ≤ 1.48 px; track: ≤ 1.37 px; composite correlation 0.98). Recorded as open debt.
