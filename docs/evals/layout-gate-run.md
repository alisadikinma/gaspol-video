# Layout gate, real-data run (GV-23)

Date: 2026-10-17. A finished 9:16 master, not a fixture. Media stays in the scratchpad; only this record is committed.

## Input

- Master: `/Users/alisadikin/Drive-D/project-video/Alisha-school-video/output/alisha-5-superstar-master.mp4`, 1080x1920, 63.03 s. It had no ASS and no cover.
- Audio: `ffmpeg -vn -ac 1 -ar 16000` to a wav, then `transcribe_assemblyai` from `tools/gen_subs.py` (key from the main repo `.env`, not printed).

## Honest limit: almost no speech

AssemblyAI returned 1 word in 63 s: `Yay!` at 38.917-39.560 s. The master is a child studying with music and sound, not narration. So the subtitle check ran on one cue, not on a full caption track. The ASS has that one word plus the centre watermark `ALISADIKIN`.

## Commands

```
python3 -m tools.vidkit karaoke words.json master.ass --total 63.033 --profile short-organic --watermark ALISADIKIN   # exit 0
python3 -m tools.vidkit title frame.png "Alisha Si Bintang" cover.png                                                  # exit 0
python3 tools/layout_gate.py check <scratch project> --video <master> --ass master.ass --thumb cover.png
```

`frame.png` is the master at 47.067 s (largest face box in a `face_box.py --every 2` pass: 409 of 945 samples had a face).

## Result

- **Exit code: 1** (a finding, not a tool error). Report: `Result: FAIL (1 face sample(s) skipped)`.
- Safe box `[65, 269, 972, 1517]`, profile `short-organic`.
- **Findings (1):** subtitle at 39.30 s, "too close under the face (108 px, needs 192)", box `[484, 1134, 594, 1193]`. This is a true finding: the face detector found the girl's face above the caption and the profile's face gap is 192 px.
- **Skipped face samples: 1** (frame 0 at 0.00 s: no face detected on thumbnail `cover.png`). The girl is in profile, turned away, and the gate lists the skip instead of passing it silently.
- Watermark and cover title: inside the safe area, no finding.
- Previews written: `.tmp/layout-{tiktok,reels,shorts}.jpg`.

## Preview (tiktok), what I saw

The red bands are the platform UI zones and sit outside the green safe box. The one subtitle, `Yay!` (teal and white, black outline), sits low in the safe box on the open book with a yellow box around it. The watermark box is a faint yellow rectangle over the book above it. The TikTok control bar at the bottom ("Kewajiban 2 / Belajar", a part of the video's own picture, not from the gate) falls in the red zone. The preview matches the report: subtitle inside the safe area, close under the child's head.

## Findings about the tools

1. **Title width is asymmetric.** The title is centred on the screen but the safe box is 65 px left, 108 px right. The widest centred line is therefore 2 x (972 - 540) = 864 px, not 907. `vidkit title` refuses with `title is N px wide, centred on the screen it is wider than the safe area` for these (min_font_pct 0.07): "Alisha Superstar Sekolah" (1080), "Alisha Superstar Cilik" (1080), "Alisha Jadi Superstar" (905), "Alisha Si Superstar" (885), "Alisha Jadi Bintang" (905). Only "Alisha Si Bintang" fit. A 3-5 word Indonesian title often has a word like SUPERSTAR or SEKOLAH that is too wide at 7 % font. The refusal is correct (it never stamps a title the gate would fail), but the message does not say that the safe area is asymmetric.
2. The cover title numbers stay interpretation (no Samuel cover title was found); this run checked the title against the safe area only.
3. A single-word track proves the pipeline end to end but is a weak test of subtitle wrapping (4 words in 2 lines is not exercised). A talking-head Short would be a better second run.

## After the fix (same day): titles use the full safe width, up to 3 lines

Fix: the title is centred on the safe-area centre x (518.5 px, not 540), may use 3 lines (words split to balance line width), `font_pct` 0.065, `min_font_pct` 0.04 (both `tafsiran`, source in `media/layout-profiles.json`). The refusal now reads `title does not fit the safe area: usable width 907 px, widest line N px at min font (0.04 of the height); shorten the longest word`.

Before and after, 1080x1920, same frame:

| title | before | after (box, lines) |
|---|---|---|
| Alisha Superstar Sekolah | refused (1080 px) | ok, [106, 498, 930, 960], 3 lines |
| Alisha Superstar Cilik | refused (1080 px) | ok, [106, 498, 930, 959], 3 lines |
| Alisha Jadi Superstar | refused (905 px) | ok, [97, 575, 940, 883], 2 lines |
| Alisha Si Superstar | refused (885 px) | ok, [106, 575, 930, 883], 2 lines |
| Alisha Jadi Bintang | refused (905 px) | ok, [97, 575, 940, 883], 2 lines |

A single 20-letter word still refuses: `usable width 907 px, widest line 1062 px at min font`.

Gate re-run with "Alisha Superstar Sekolah" as the cover, same video and ASS: **exit 1**, same single finding (subtitle at 39.30 s, 108 px under the face, needs 192), 1 skipped sample (`no face detected on thumbnail cover2.png`). The title adds no finding.

Cover look: three stacked lines ALISHA / SUPERSTAR / SEKOLAH, white bold caps on black boxes, each line centred on the safe area, the widest (SUPERSTAR) nearly edge to edge of the safe box. The block sits at about 26-50 % of the height and covers the child's lower face and the snack she holds. That is the profile's `center_y_pct` 0.38 (tafsiran) on this frame; the gate did not catch it at that point because it ran face detection on the stamped cover, where the title itself hides the face (fixed below). A risk to keep: a 3-line title is tall.

## After the second fix: the face is detected on the clean image

Defect: the gate looked for the face on the stamped cover, so a title that hides the face made the face vanish and the title passed. Fix: `vidkit title` writes the absolute path of the clean input as `source` in `<out>.box.json`; the gate detects the face on `source` and flags `title overlaps face`. If `source` is missing or unreadable the gate falls back to the stamped image and notes `face checked on stamped image; source missing`.

Same video, ASS and frame (face on the clean frame: [447, 206, 913, 708]), title "Alisha Superstar Sekolah":

| cover | gate | cover part |
|---|---|---|
| before the fix (old stamp, no `source`, box [106, 498, 930, 960]) | exit 1 | face not found, 1 skipped sample, note `face checked on stamped image; source missing`, no title finding |
| default `--y-pct` (0.38), new stamp | exit 1 | `title overlaps face`, box [106, 498, 930, 960] |
| `--y-pct 0.50`, box [106, 729, 930, 1191] | exit 1 (only the subtitle finding) | **no title finding**, no skipped sample, no note |

`--y-pct 0.52` also clears. The remaining exit 1 is the subtitle at 39.30 s, 108 px under the face, unchanged. `center_y_pct` in the profile is not changed: the finding is the right outcome and the user picks `--y-pct` or another frame.

Cover at `--y-pct 0.50`, seen with Read: ALISHA / SUPERSTAR / SEKOLAH in three white-on-black lines across the lower half of the picture. The child's eyes and face stay free; the block covers her hands, the snack and the shirt.
