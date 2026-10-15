# KineticOverlay — real render (GV-17 Phase G)

Date: 2026-10-15. Machine: macOS arm64, Node 26.0.0, Remotion 4 (node_modules of the Ekaputra
workspace, symlinked read-only), Python 3.14.7 venv with mediapipe 1.0.1.

## Input

- Clip: Ekaputra film `clips/scene-25.mp4` (Ali to camera, chest-up, 1920x1080, 24 fps, 8.0 s),
  copied into a scratch project so the client project was not written to.
- Words: platform-native dialogue, so no `vo-manifest.json` words. `vo/vc-25.mp3` transcribed once
  with AssemblyAI (`tools/gen_subs.transcribe_assemblyai`) into `.tmp/asr-25.json`, 15 words,
  "Kita mulai dari gudang, pak. Minggu pertama kami datang dan petakan masalahnya bersama tim
  bapak." Used through `words_file`. No word time was typed by hand.
- Plan: 5 cues in `work/overlay-plan.json`.

| Cue | Spoken anchor | Shown | Effect | Element |
|-----|---------------|-------|--------|---------|
| c1 | Kita mulai dari gudang | kita mulai dari / **gudang** | fx 1 blur-to-sharp, fx 5 arrow icon | behind panel (image, `ref:env-gudang-lorong.png`), source box |
| c2 | Minggu pertama | minggu / **1** (yellow) | fx 3 count-up, timed on `key_words: "pertama"`; fx 5 chart icon | carousel (3 ref images) |
| c3 | datang | kami / **datang** | fx 2 glitch slices | video panel (`user:clips/scene-24a.mp4`, front) |
| c4 | petakan masalahnya | petakan / *masalahnya* | fx 4 handwrite; fx 5 circle icon | — |
| c5 | tim bapak | bersama / **tim Bapak** (yellow), cue layer `behind` | fx 1 | bubble (`ref:cast-c2-face.png`) |

## Commands

```
python3 tools/person_mask.py <proj> 25 <proj>/clips/scene-25.mp4      # 192 frames, 0 without person, 4.8 s
python3 tools/overlay_plan.py <proj>                                   # overlay 25: 5 cues, 199 files staged
node templates/remotion/scaffold.mjs <proj>; Overlay.template.tsx -> src/shots/Overlay-25.tsx (SCENE 25)
npx tsc --noEmit  (typescript 5.6.3 + @types/react 18.3.12 in an isolated dir; scaffold ships no TS)  -> 0 errors
node scripts/render-all.mjs KineticOverlay                             # out/KineticOverlay.mp4, 6.5 MB
```

## Looked at

QA stills at enter-mid, hold and exit-mid of every cue (15 frames, one contact sheet), then the
fixed frames again after each fix:

- `docs/evals/overlay-kinetik/qa-15-stills.jpg` — rows c1..c5, columns enter-mid / hold / exit-mid
  (frames 20,24,30 / 60,66,73 / 91,98,107 / 130,135,141 / 156,164,173), first render, before
  fixes 3 and 4.
- `docs/evals/overlay-kinetik/qa-defaults-caption.jpg` — frames 24 and 135 of the last render:
  panel caption on c1, c4 drawn with no `layer` in its plan (default front), handwriting font.

- **Never static:** all five cues differ across their three stills. fx 1 sharpens, fx 2 shows
  offset slices on "datang" then snaps together, fx 3 lands on "1", fx 4 reveals "masala" then
  "masalahnya" left to right, fx 5 icons draw, fx 6 blurs every block out.
- **Behind panel:** the warehouse panel sits behind Ali's head; the head edge cuts the panel.
- **Behind text:** "tim Bapak" is partly covered by the head, the depth effect of the reference.
- **Carousel:** cards slide left and pass behind the torso (L2 under the person layer).
- **Video panel:** plays scene 24a inside a rounded card, front layer.
- **Bubble:** round face photo with "Tim / gudang Bapak" label, springs in, fades out.
- **Source box:** bottom-left, legible at 1920 px.

## Failures found by this run and fixed

1. `overlay_plan.py` only wrote `panels`/`bubbles`/`carousel` when the plan had them; the
   composition maps over all three → `TypeError: Cannot read properties of undefined (reading
   'map')` on frame 7. Now always written, even empty (test
   `test_output_cue_always_carries_the_three_media_lists`).
2. A shown number is rarely spoken as digits ("1" for "pertama"), so fx 3 was unusable: the
   keyword had to appear verbatim in the words. New optional `key_words` times the keyword on the
   spoken tokens (two tests).
3. With `pos.x`/`pos.y` set, every block was centred on x, so a long left-anchored keyword
   ("masalahnya") ran off the left edge. Now x is the left edge for `left`, the right edge for
   `right`, the centre for `top`, with a `maxWidth` inside the safe margin.
4. The script font `'Caveat'` is not installed in a fresh workspace, so fx 4 fell back to Times.
   The placeholder chain is now `'Caveat', 'Bradley Hand', 'Noteworthy', cursive`; a project that
   wants Caveat still has to load it.
5. Found by the plan-verifier audit: a cue (or panel) with no `layer`/`pos` validated as the
   default "front" but the output carried no `layer`, and the composition matches it exactly, so
   the cue was silently never drawn. `overlay_plan.py` now writes every default the composition
   reads (`layer`, `fx`, `color`, `script`, `icon`, `source`, `pos`, panel `kind`/`layer`/
   `caption`) and refuses an unknown `pos.anchor`. Re-rendered with c4's `layer` removed: drawn.
6. Spec "caption text may sit on the panel" was not built; added as optional `caption` on a panel
   (lower edge, gradient, body font). Shown on c1 ("Gudang Ekaputra").
7. Plan placement (not the tool): c4 at x=330 put "nya" on the side of the face; moved to x=120.
   The tool cannot measure text width, so placement stays a QA-by-looking step.

## Keywords, not subtitles (follow-up, same day)

Ali: only the important keywords are highlighted; this is not a subtitle. The 5-cue plan above put
text on screen 5.7 s of 7.0 s of speech. `overlay_plan.py` now refuses that:
`refused: scene 25: text is on screen 5.7s of 7.0s of speech (82%, max 50%). These are keywords,
not subtitles: ...`. Re-planned with two keywords only — c1 **gudang** (main claim) and c2 **1**
(number) — accepted and re-rendered: `docs/evals/overlay-kinetik/qa-keywords-only.jpg` (frames 24,
66, 110, 170: text on the two keywords, the second half of the scene has no text).

## Known limits

- Ali is bald: the mask edge on curly hair was not tested. A faint mask bleed onto the table near
  the right forearm is visible in the matte, not noticeable in the render.
- `gen-registry.mjs` logs `30fps 150f` for KineticOverlay because it reads the config with a regex
  and the template's values come from the plan JSON; the render itself uses the real config through
  `selectComposition` (output is 24 fps, 192 frames).
