# Kinetic Text Overlay (animated keywords and media panels around a speaker)

Use it when a speaker or narrator says the phrase the viewer must keep, and when a picture or
clip should appear beside them while they say it. It is the film's kinetic-typography beat, not
a caption. Not a subtitle (`16-subtitles-and-captions.md`) and not a full-screen Remotion card
(`12-remotion-explainer.md`).

Pipeline: `tools/person_mask.py` (person matte per frame) → `work/overlay-plan.json` →
`tools/overlay_plan.py` (cues timed from the voice) → Remotion composition `KineticOverlay`
(`templates/remotion/Overlay.template.tsx` + `lib/overlay-fx.tsx` + `lib/overlayFx.mjs`).
Source: a 9:16 Indonesian explainer the user supplied as the target style, 2026-10-15 (GV-17).
Real run: `docs/evals/overlay-kinetik-run.md`.

v3.10.0's gold-serif fly-in cards (`tools/keyword_cards.py`) are SUPERSEDED by this pattern. The
tool stays until the new style has shipped in one real video; do not use it for new work.

## 1. Look

- **Two tiers.** Lead words small regular sans in the ink colour (~40 px at 1080 wide), the
  keyword big heavy sans (weight 800, ~120 px), tight leading.
- **Highlight colour** (`brand.json` `highlight`) for numbers and hard words ("1%", "221", "4x",
  "LEBIH TEGAS"). Everything else in `ink`.
- **Script accent:** now and then one word in a handwriting face (`brand.json` `scriptFont`; the
  placeholder chain is `'Caveat', 'Bradley Hand', 'Noteworthy', cursive` — load the brand's real
  face in the project when it has one).
- **No box, no pill, no background** behind text. A soft dark shadow only.
- **Line icon** above a block (fire, gavel, chart, cloud, question, arrow, circle), stroke only.
- **Panels:** rounded image or video cards; a **carousel** of rounded cards sliding left; **round
  photo bubbles** with a two-tier label beside the torso.
- **Source box** bottom-left: tiny body text on a dark translucent background, copied from
  `av-script.md`. Never invented.

## 2. Motion — text is never static

Every cue has an enter effect and the exit effect. A cue without `fx` gets effect 1. The
renderer has no static path (`cueStyle` in `lib/overlayFx.mjs` always composes enter + exit, and a
test proves enter-mid, hold and exit-mid differ for every effect).

| fx | Effect | Values | Use |
|----|--------|--------|-----|
| 1 | **Blur-to-sharp** | 0.30 s; opacity 0→1, blur 12→0 px, scale 1.06→1 | default keyword |
| 2 | **Glitch slices** | 0.30 s; 6 horizontal slices offset ≤ 40 px, snap to 0, seeded per cue | hard or warning word |
| 3 | **Count-up** | 0.60 s; number ticks to its value, prefix/suffix/decimal kept ("1.9%", "Rp 2,5 T") | statistics |
| 4 | **Handwrite** | 0.50 s; script word revealed left to right | personal accent |
| 5 | **Stroke draw** | 0.40 s; icon, arrow or circle draws itself, starts 0.1 s before the keyword | decoration (automatic with `icon`) |
| 6 | **Exit** | 0.20 s; fade + blur 0→8 px, ending at the cue's out | every cue (automatic) |

Lead words enter first (0.25 s fade + 8 px rise); the keyword enters on its spoken word. Panels and
bubbles spring in (scale 0.9→1) and drift ±6 px while held; the carousel slides one card per 0.8 s.

## 3. Layers and depth

Bottom to top: **L1** the clip, **L2** `behind` panels, bubbles, carousel and `behind` cues,
**L3** the person cut out of the same clip with the per-frame mask, **L4** front text, icons and
`front` panels, **L5** the source box. A `behind` element is cut by the speaker's head and body —
the depth effect of the reference. Anything `behind` needs a valid mask for that scene; the plan is
refused without one.

`tools/person_mask.py <output_folder> <scene> <clip>` writes `.tmp/mask-<scene>/NNNNN.png`
(MediaPipe selfie segmenter, cached by clip sha256). Exit 1 when more than 10% of frames have no
person, listing them. The segmenter is class-agnostic: two people in frame are both masked.

## 4. Timing

Times come from the voice, never by eye. Each scene names one word source: `vo_layer` (an item id
in `vo/vo-manifest.json`) or `words_file` (ASR words, e.g. AssemblyAI, for platform-native
dialogue). A cue's `words` is the spoken phrase found as a contiguous run after the previous cue;
in = run start − 0.10 s, keyword = start of the keyword inside the run, out = run end + `hold_s`
(default 0.3 s). Consecutive cues may overlap by at most 0.1 s.

A keyword shown differently from how it is said ("1" for "pertama", "221" for "dua ratus dua puluh
satu") sets **`key_words`** to the spoken tokens; the keyword is timed on them.

## 5. Placement

- Never on the face or mouth. Look at a frame first.
- `pos.anchor` `left` / `right` / `top`. With `x`/`y` set, x is the block's LEFT edge for `left`,
  its RIGHT edge for `right`, its centre for `top`; a `maxWidth` keeps it inside a 96 px safe
  margin. The tool cannot measure text width, so a long keyword can still reach the face: check
  the exit-mid still (scene 25 run, "masalahnya" moved from x=330 to x=120).
- A `behind` cue may sit over the head on purpose; the head then covers part of it.
- Keep off other burned text (subtitles at the bottom, a Remotion card).

## 6. Red alarm flash behind a person (optional)

For a "danger" beat ("ini bukan yang pertama"): flash the **background only**, never the person.
Use the same matte from `tools/person_mask.py` (white = person, so invert it: the flash may only
touch black), feather 3–6 px. Blink 0.3 s period, alpha 0.45, start exactly on the word, not
before it. Pair with a short alarm SFX (`14-sfx-design.md`) at the same moment, low enough to keep
the voice clear. A full-frame `drawbox` is wrong: it tints the face and shirt. Do not let
`maskedmerge` do it: in yuv420 the chroma leaks and tints the person; use `alphamerge`.
Over a red flash keep the keyword in `ink` or `highlight`, never red.

## 7. Workflow (per kelompok, after the clips and voice exist)

1. Pick the phrases with the user, or from the script lines marked keyword. Three to five words
   per block, one keyword per block.
2. `python3 tools/person_mask.py <output_folder> <scene> clips/scene-<NN>.mp4` for every scene
   with a `behind` element.
3. Write `work/overlay-plan.json` (schema in `tools/overlay_plan.py`'s docstring), with media as
   `ref:<file>`, `user:<path>` or `remotion:<Component>`.
4. `python3 tools/overlay_plan.py <output_folder>` — fix every refusal it lists; never edit the
   generated `overlay-<scene>.json` by hand.
5. Copy `Overlay.template.tsx` to `shots/src/shots/Overlay-<scene>.tsx`, set `SCENE` and the plan
   import together, render `KineticOverlay`.
6. Look at enter-mid, hold and exit-mid of every cue (`scripts/qa-frames.mjs`). Fix placement,
   not the style.
