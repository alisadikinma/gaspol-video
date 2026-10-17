# Short-form layout measurement (GV-23 Phase B)

Date: 2026-10-17. Six Shorts by Samuel Christ, supplied by the owner.

## Clips

| # | Link | Source file | Frames used |
|---|------|-------------|-------------|
| 1 | https://www.youtube.com/shorts/at_O5ErzJlA | 1080x1920, 55.8 s | 10 |
| 2 | https://www.youtube.com/shorts/hgCjFbkUW9s | 1080x1920, 60.4 s | 17 |
| 3 | https://www.youtube.com/shorts/SKwtL_PVhm4 | 1080x1920, 82.2 s | 21 |
| 4 | https://www.youtube.com/shorts/4blpt7DF95M | 1080x1920, 52.4 s | 10 |
| 5 | https://www.youtube.com/shorts/Z5kijakjN0c | 1080x1920, 56.6 s | 8 |
| 6 | https://www.youtube.com/shorts/jmz5z7fdPiw | 360x640, 73.1 s (scaled 3x, see limits) | 12 |

Clips stayed in the scratchpad, none in git.

## Method

1. Download with `python3 -m tools.vidkit ingest`. Link 6 failed in `ingest` with a bot check and HTTP 403 four times, so it was fetched with `yt-dlp --extractor-args "youtube:player_client=mweb"`. That client only offered 360x640.
2. Frames: one every 2 s from t=1 s (`ffmpeg -ss 1 -vf fps=0.5,scale=1080:1920`), plus 7 frames spread over each clip including frame 0 for a visual check.
3. Subtitle lines: a numpy script finds rows in the band y 900-1300, x 100-980 where at least 8 pixels are near white (min channel >= 252; >= 240 for clip 6). Row groups become lines. Baseline = last row with >= 30 % of the peak row count; top = first row with >= 20 % of the peak. "Cap height" = baseline - top + 1.
4. A frame counts only if it has 1-2 lines, each 25-60 px tall, two lines of equal height (within 5 px) and 60-110 px apart. Bright jackets, white paper and charts behind the text made the filter reject many frames, so the numbers come from the accepted frames (78 in total).
5. I opened sheets with the measured boxes and baselines drawn on 24 accepted frames (4 per clip, spread over each clip). Every box sat on the white serif subtitle, none on a logo or bright background.
6. Words per display: tesseract on the white-pixel mask of the accepted subtitle region, tokens with a letter or digit counted.
7. Font size: cap height / 0.71. The 0.71 is `tafsiran:` the cap-height ratio of a bold high-contrast serif that looks like Playfair Display Bold. The font file was not available and the match was not verified. The measured "cap height" also includes ascenders (b, d, k, l), which in this face are about as tall as capitals.
8. Cross-check: line pitch (baseline to baseline) median 71.5 px / 1.333 (Playfair default line height, `tafsiran:`) gives font_pct 0.0279. The cap method gives 0.0286.

## Cover title

Frame 0 of all six clips has a subtitle but no title text. The YouTube thumbnails (`yt-dlp --skip-download --write-thumbnail`, 1280x720) are auto frames of the video with subtitles and no title text either. I also viewed a 24-frame contact sheet of clips 1 and 3 and found no headline overlay anywhere. Result: **no title on frame 0** and no title on the thumbnail, so `title.font_pct` and `title.center_y_pct` have no measurement and stay `tafsiran:`. What was measured here is subtitle only.

## Per clip

| # | Cap height px (median, min-max) | Last-line baseline Y px (median) | Block centre Y px | Line pitch px | Words per display (median) | Widest block px |
|---|---|---|---|---|---|---|
| 1 | 42.0 (41.5-42) | 1208 | 1148 | 80 | 4.5 | 879 |
| 2 | 38.5 (36.5-39) | 1138 | 1084 | 70 | 3 | 822 |
| 3 | 34.0 (32-45) | 1134 | 1118 | 63 | 3 | 750 |
| 4 | 39.5 (39-40) | 1176 | 1136 | 73 | 4 | 864 |
| 5 | 32.5 (31-33) | 1192 | 1145 | 64 | 6 | 820 |
| 6 | 40.5 (34.5-55) | 1203 | 1148 | 79 | 5 | 864 |
| **Median of 6** | **39.0** | **1184** | **1140** | **71.5** | **4.25** | |

Pooled median of words over all 78 frames: 4.0.

Title cap height and title block centre Y: not measured (no title).

## Profile values (units of the profile)

| Value | Raw median | Calculation | Profile value | Clamp |
|---|---|---|---|---|
| `subtitle.font_pct` | cap 39.0 px | 39.0 / 0.71 = 54.9 px; 54.9 / 1920 = 0.0286 | 0.029 | none |
| `subtitle.per_group` | 4.25 words | integer, rounded down (pooled median 4.0) | 4 | none |
| `title.font_pct` | none | no title found | 0.10 unchanged, `tafsiran:` | n/a |
| `title.center_y_pct` | none | no title found | 0.38 unchanged, `tafsiran:` | n/a |

Safe box of `short-organic` is (65, 269, 972, 1517). Measured subtitle block centre 1140 and last baseline 1184 sit inside it. Widest measured block is 879 px, inside the 907 px safe width. No value was clamped.

## Limits

- Six clips from one creator, one channel style. The numbers describe that style, not a rule of the platform.
- Clip 6 is 360x640 scaled up 3x, so its edges are soft and its range (34.5-55) is wide. Dropping clip 6 gives a cap-height median of 38.5 (font_pct 0.0282), so it moves the result by 0.0004.
- Cap height from a row-count profile is approximate (about +/- 3 px). Ascenders can add a pixel or two.
- Font ratio 0.71 and line height 1.333 are assumptions about a font that was not identified from a file.
- Frame filter kept only frames where the text could be isolated, so sampling is biased to plain backgrounds.
- Word counts come from OCR. A hyphenated word such as "berbulan-bulan" can count once or twice.
- Words per display of 4 differs from the old tafsiran of 2. Samuel shows short phrases in two lines, not one or two words at a time.
- Nothing about the title was measured, and the owner's premise that these Shorts carry a cover title was not borne out by these six.
