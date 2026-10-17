# Thumbnail style elements (menu for the render hand-off)

Phase 7 decides WHAT each thumbnail bets on (`15-packaging.md`). This file is the menu of
prompt pieces that turns a bet into a request for `ai-image-carousel-prompt-gen`, the plugin that
renders images. Nothing here renders anything. Pick only the pieces the bet needs; every extra
piece costs text, and text is where renders break.

Idea adapted from `claude-youtube-editor` (see NOTICE): a menu of slot-based prompt pieces plus a
table of known failures. One data point from that source, quoted with its origin: a flat,
low-contrast frame lost to a bold, high-contrast, clearly ranked frame by about 4.4x on views.
That is one channel's before/after, not a rule. Treat it as a reason to test, never as a promise.

## 1. Honesty guardrail (applies to every piece below)

The frame may promise only what the video delivers. Before a prompt is written, name the scene in
`av-script.md` that keeps the promise (Step 7.5). A hook word, badge or sticker that the video does
not back up is cut, however well it would render. A mocked screen (`simulated: true`) may appear as
an illustration but never as a shipped feature.

## 2. Base axes (always on)

- High contrast: deep darks or clean brights, never a flat middle.
- One accent colour doing the work against its ground.
- Clear hierarchy: at most three reading steps (text, then object, then face).
- One dominant element. If two things fight for first look, remove one.
- Every letter spelled out and sharp, or no text at all.

Close every prompt with this block:

```
STYLE: high contrast, one <accent> colour against a <ground> ground, crisp edges, clear
hierarchy, nothing decorative. Every text element is spelled exactly as written and sharp.
```

When a real person is shown, open the prompt with an identity line first:

```
REFERENCE: <reference-file> is the identity reference. Keep this person's face, hair and skin
tone exactly; do not restyle the face. Expression: <expression>.
```

## 3. Environment pieces (pick one)

```
SETTING: a dim, softly blurred <place> with deep shadows. The only strong light is a <accent>
glow coming from <hero object>, and a thin <accent> rim light separates the subject from the
background. Sharp focus on <subject>.
```

```
SETTING: a plain, believable photo of <real place>, daylight from a window, natural colour,
shallow depth of field. Keep what is visible behind the subject: <landmark in the room>.
The photo itself looks untouched; the overlay words are the only addition.
```

```
SETTING: a saturated studio backdrop in <colour>, a strong <accent> key light, a warm rim light,
background blur, bright and punchy. Subject <subject> sits inside the same colour grade.
```

## 4. Text pieces (default budget: one element)

Hook word (the default):

```
TEXT: a single overlay, "<WORD>" (letters <W-O-R-D>), huge, heavy condensed capitals in
<accent>, hard shadow, placed <corner>. It is the largest thing in the frame. Nothing else
written, no figures, badges or marks anywhere.
```

Two-tier headline (small setup, big promise):

```
TEXT: two stacked lines in <corner>. Line one, small, white: "<SETUP>" (letters <spelling>).
The second line sits right under it, far bigger, in <accent>: "<PROMISE>" (letters <spelling>).
Leave the rest of the frame free of writing.
```

Sticker (two short words at most):

```
EXTRA: a small tilted <sticker colour> sticker reading "<WORD>" (letters <spelling>) in heavy
black capitals, with one hand-drawn arrow pointing at <hero object>.
```

Badge or tag:

```
EXTRA: a <colour> brush-stroke tag in the <corner> reading "<TAG>" (letters <spelling>) in bold
capitals. Leave the rest of the frame free of writing.
```

## 5. Object pieces (optional)

```
HERO: a <accent> glow with fine particles spreads from <hero object> onto <surface>.
```

```
HARDWARE: <device> in a neutral dark casing, with no brand marks or lettering anywhere on it.
```

For a real brand mark or a real app screen, pass the actual file as an extra reference and say what
it is (for example: the second file is the <brand> mark; draw it sharp and unwarped). Use the plugin's own
pixel-exact tools in Step 7.8 (`composite_logo.py`) when the logo must be exact.

## 6. Failure table (symptom, then fix)

| Symptom | Fix |
|---|---|
| Garbled or misspelled text | Spell the word letter by letter in the prompt; cut to one short word; remove every other text element; re-roll |
| Text is right but unreadable at phone size | Make it larger, more contrasty, fewer words; shrink the browse-size preview to check |
| Extra text, numbers or logos appear | Add "nothing else written, no figures or marks, anywhere in the frame" at the end of the text section |
| Sticker or badge text breaks | Two short words at most; otherwise move the words into the hook line |
| Face is a stranger | Put the identity line first, pass the reference file, drop other face refs that average into someone else |
| Extra or malformed hands | Give a hand a job or hide it; state "that hand has five fingers; no other hands" |
| Fake-looking logo or UI on a device | Pass the real file as a reference, or leave the screen blank and add the mark in post |
| Frame feels busy | Remove one piece. Go back to one hook element and one hero |
| Colour cast on skin | Name warm natural skin tones; keep the screen glow faint |

## 7. How it plugs into the packaging flow

1. Step 7.4 gives three bets on three levers (outcome, tension, subject). Each bet picks one
   environment, one text piece, and at most one extra from this menu.
2. Step 7.5 confirms each promise against `av-script.md`.
3. Step 7.7 hands the assembled prompts to `ai-image-carousel-prompt-gen`.
4. After each render, `python3 tools/thumb_verify.py init <project>` and judge every image by
   looking at it. `thumb_verify.py check <project>` must exit 0 before any thumbnail is offered as
   final. A FAIL cell means one re-roll with the matching fix from section 6; after two re-rolls,
   ask the owner.

## 8. 9:16 path (GV-23)

Sections 1 to 7 are the 16:9 path and stay as they are. A 9:16 short cover works differently:
the image is rendered with no text and the tool stamps the title.

1. **Render the cover without text.** Expressive face (shock or awe) or one high-value object.
   Put no title words in the prompt. End the prompt with the negative
   `no text, no letters, no captions`. Section 4 text pieces are not used on this path.
2. **Write the title.** 3-5 words, ALL CAPS. Formula: extreme number + public figure or brand +
   curiosity word, for example `SISKA KOHL BELI NASI GORENG SEHARGA 400 JUTA!` or
   `RAFATHAR HASILKAN 2 MILYAR PER ENDORSE?!`. The honesty guardrail of section 1 applies: the
   promise must be in the video, and numbers must come from the brief.
3. **Stamp it.** `python3 -m tools.vidkit title <img> "<TEXT>" <out>`. Size and position come from
   `media/layout-profiles.json`. Say plainly: these title numbers are tafsiran. The 6 measured
   Samuel Shorts carry no cover title, so no data backs them (see
   `docs/evals/short-form-layout-measurement.md`). The title goes never over the face.
4. **Gate it.** `python3 tools/layout_gate.py check <project> --thumb <png>` must exit 0
   (title inside the safe area, off the face).
5. **Verify it.** Then `thumb_verify.py init` and `check`, as in section 7.
