# qa_frames.py — real run (GV-8 Phase L)

Date: 2026-09-29. Project: a scratch copy of a real client project (`catalog-4`: 19 VEO clips,
24 fps, `video-prompts.md` headed `### S01 — …`). Four clips copied: `scene-01`, `scene-01b`,
`scene-01c`, `scene-02`. The original project was never written to.

## Commands

```bash
python3 tools/qa_frames.py <scratch> --clip clips/scene-01.mp4 --clip clips/scene-01b.mp4 \
    --clip clips/scene-01c.mp4 --clip clips/scene-02.mp4
python3 tools/qa_frames.py <scratch> --clip clips/scene-01b.mp4 --scenes 1b --check
python3 tools/qa_frames.py <scratch> --clip clips/scene-01.mp4 --clip clips/scene-01b.mp4 --check
```

## Result

Two defects that the unit tests did not catch were found on real material and fixed before this
result was recorded:

| Defect | Symptom on the real project | Fix |
|---|---|---|
| Scene ids were integers, headings `### Scene N` only | `01`, `01b`, `01c` folded into one scene; no PLAUSIBILITY block ever found under `### S01b` | `cfb3dc3` — string ids with a letter suffix, `S01b` and `Scene 1` headings both match |
| Last sample `round(D - 1/fps, 2)` | every 8.0 s / 24 fps clip failed: the last frame starts at 7.9583 s, the tool asked for 7.96 s, ffmpeg wrote nothing (`Nothing was written into output file`) | `38384ba` — half a frame inside the last frame, rounded down |

After the fixes:

- Extraction: exit 0; four sheets `.tmp/qa-scene-01.jpg`, `-01b`, `-01c`, `-02` (2400 × 270 px),
  single frames removed, `work/visual-qa.md` with four `## Scene …` sections. Whole run ≈ 2.7 s.
- All four sections say `PLAUSIBILITY block not found` — correct: this project predates the
  v3.4.0 plausibility gate and its prompts carry no block.
- Judged scene 01b by reading the sheet against its prompt: MECHANISM, COUNT, FLOW, PAIR, PEOPLE,
  OVERLAY SURFACE = PASS (one man, one phone, one tea glass, static camera, same porch as S01, no
  second person, no overlay in this scene). FACING = `UNSURE: phone back faces camera in frames
  3-5, so the blank-screen requirement cannot be seen`.
- `--check --scenes 1b`: exit 0 with `V15 NOTE scene 01b q4: … — needs a human look`.
- `--check` over 01 (unjudged) and 01b: exit 1, `V15 FAIL scene 01 q1: MECHANISM has no verdict` …

Open point: the seven PLAUSIBILITY questions have no row for a performance beat (the prompt's
"at second 5 his jaw tightens"). Frames cannot judge it and no row asks for it; it stays a human
look, noted here rather than forced into an unrelated row.
