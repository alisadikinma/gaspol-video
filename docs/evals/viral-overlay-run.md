# Viral overlay vocabulary: real render (GV-19 Phase B)

Date: 2026-10-16. Machine: macOS arm64, Node 26, Remotion 4 (the `node_modules` of a client
project's workspace, linked entry by entry read-only into a scratch workspace; nothing was written
into the client project), typescript 5.6.3 and @types/react 18.3.12 in an isolated directory.

## Input

- Clip: `tests/fixtures/speaker-2s.mp4` (360x202, 24 fps, 2 s), looped four times with
  `ffmpeg -stream_loop 3 -c copy` to 8 s so five cues fit under the 50% text-share limit. The
  composition is declared 1920x1080 and stretches the clip. No client media.
- Words: **hand-written word timings** in `work/words.json` (12 words, 0.4 s to 7.6 s), used
  through `words_file`. The fixture has no usable speech, so these are synthetic. They prove the
  planning and the drawing, not recognizer accuracy.
- Scene 01: `preset: "viral"`, `steps` with 3 marks, three cues (`check` icon; `money` icon plus
  `burst`; `warning` icon plus `vignette`, fx 2). Scene 02: no preset, three cues with the
  remaining icons `cross`, `clock`, `lock`, the last with an explicit centre anchor.
- Front layer only; no person mask (not needed for these elements).
- `overlay_plan.py` ran clean on both scenes. Text on screen was 3.3 s of 7.2 s of speech (46%).

## Commands

```
python3 tools/overlay_plan.py <proj>      # overlay 01: 3 cues; overlay 02: 3 cues
node templates/remotion/scaffold.mjs <proj>; Overlay.template.tsx -> src/shots/Overlay-0N.tsx
node scripts/qa-frames.mjs KineticOverlay --out ../qa01 name=frame ...   # 15 + 4 stills
npx tsc --noEmit  (typescript 5.6.3, isolated dir, tsconfig strict, jsx react)   -> exit 0, no output
```

The scaffold ships no TypeScript, so `tsc` is the isolated 5.6.3 binary with a `tsconfig.json`
written into the scratch workspace (strict, `allowJs`, `paths` to the isolated `@types/react`).
`--listFiles` confirmed it read `src/lib/overlay-fx.tsx`, `src/lib/brand.ts` and the scene file.

## Looked at

Every still below was opened and read. Scene 01 frames (24 fps): steps 12 / 60 / 108; c1 24 / 38 /
46; c2 72 / 85 / 90, burst 96 / 108 / 120; c3 130 / 142 / 146 / 150; end 170. Scene 02: 38 / 85 /
130 / 142. Stills show only the repo fixture and are not committed.

### sticker icon

`check`, `money`, `warning` (scene 01) and `cross`, `clock`, `lock` (scene 02) all draw as clean
outline icons above the lead word, in `ink`, and are readable at 110 px. The warning triangle's
exclamation and the lock's keyhole are legible. The enter-mid frame of c3 shows the icon half
drawn, so the stroke animation runs.

### step counter

A row of three circles at the top. Frame 12 (just after "pertama"): circle 1 lit in `highlight`,
2 and 3 dim. Frame 60: 1 white filled, 2 lit. Frame 108+: 1 and 2 filled, 3 lit. The lit circle
fills in over a quarter second (frame 108 shows 3 partly filled). The bar stays up to the end of
the clip (frame 170 shows 1 2 3 with 3 lit); there is no exit, by design: it is a progress bar.

### red vignette

Scene 01, c3. Frame 130 and 142: the frame edges glow red, the middle (face and chest) stays
clear. Frame 146 shows it at a different strength than 142, so it blinks. Frame 150, the last frame before the cue ends (`outF` 151): still tinted, inside its 0.2 s
fade-out. Frame 170, after the cue: no red at all. The red is the `alarm` token (template default).

### falling burst

Scene 01, c2, from the keyword "uang". Frame 85: first notes enter at the top edge. Frame 96:
about a dozen banknote icons in `highlight`, spread across the width at different heights and
angles, in the upper half. Frame 120: they are at the bottom edge, most leaving. Different frames show different positions.
Determinism of the positions is covered by the unit test, not by a repeat render.

### two-tier preset

Scene 01 cues carry no `fx`, `color` or `pos`. They render as the preset says: small white lead
word (40 px), large yellow keyword (120 px, the `highlight` token), centred across. Scene 02, no
preset, renders the same text in white at the default top anchor, so the preset is what changed
the colour and the position. The generated `overlay-01.json` carries `preset.source: "course"`.

### center anchor

First render: the anchor sat at the vertical middle, 50% down, and in this talking-head frame
that is the face. The warning icon in c3 covered the speaker's nose and "kunci" sat on the chin.
Fixed: the block is centred across and 64% down (`CueText` in `overlay-fx.tsx`), so icon, lead
word and keyword all sit on the chest. Re-rendered c1 and c3 at enter-mid, hold and exit-mid and
the face is clear in each. Scene 02 cue d3, with an explicit `pos.anchor: center`, draws in the
same place.

## Failures found by this run and fixed

1. Centre anchor on the face (above). Fixed in `overlay-fx.tsx`; doc 19 section 8 now says
   "centred across and 64% down".
2. Not a defect of this work, seen again: the existing default `top` anchor also lands on the
   head of this fixture (scene 02, d1 and d2). It is placed for a speaker lower in frame. Left as
   it is; the plan says to fix placement per project, not the style.

## `npx tsc --noEmit`

```
$ tsc --noEmit -p tsconfig.json     # typescript 5.6.3
(no output)
tsc exit=0
```

## Not covered

- No person mask: nothing here draws behind the speaker.
- The red vignette was judged on stills, so the 3 Hz blink is read from two frames of different
  strength, not from the playing video. No video was rendered.
- Word timings are hand-written, see Input.
