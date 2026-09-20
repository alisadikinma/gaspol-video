**Ticket:** GV-7

# GV-7 — Kinetic captions, title cards, and shot motion

## Design

### Problem

gaspol-video ships captions as static SRT blocks burned with ffmpeg's `subtitles` filter. A
viewer sees one unchanged frame composition for the whole length of a clip — often eight or ten
seconds. Retention drops.

Three things are missing, all in the post-production visual layer:

1. **Word-by-word captions with a highlighted key phrase.** The word timings needed for this
   already exist: `vo/vo-manifest.json` carries `start_ms`/`end_ms` per word for every line
   ElevenLabs spoke, and `_cues_from_words()` in `tools/gen_subs.py` throws that resolution away
   by collapsing words into two-line blocks. SRT cannot express per-word reveal or a background
   box, so the format is the ceiling, not the data.
2. **Title cards** at act and topic boundaries — an accent-coloured eyebrow line above a large
   display title, entering line by line.
3. **Motion when nothing else changes.** Nothing in the plugin currently asks how long a shot
   holds still. `tools/composite.py` has a `--zoom`, but it is a static crop factor on a PIP
   window, not animated, and it never touches the master.

Reference: two frames from a THE OVERPOST video supplied by the user (stacked three-line caption
with a red box on `1 sampai 4 tahun`; a gold/cream two-line title card set to the left of frame).

### Decisions taken during brainstorm

| Decision | Choice | Reason |
|---|---|---|
| Scope | All three items, one ticket, three phases | Same subsystem; two share the Remotion overlay path and the word-timing source |
| Where the look comes from | Structure ships with the plugin, colour and type always from `brand.json` | `templates/remotion/Shot.template.tsx` states the plugin ships no palette; a hardcoded red would make every client's video identical |
| Keyword selection | Fully automatic | User's explicit choice over script-authored markers |
| Determinism of that selection | Scored by fixed rules, written once to `work/caption-plan.json`, reused on re-render | Automatic selection that re-rolls per render produces a different video from the same inputs |
| Shots held longer than 5s | Pass 2 inserts motion automatically and reports what it did | User's choice over a blocking gate; the plan file keeps it visible and editable |
| Renderer split | Remotion draws text, ffmpeg does zoom | User's instruction, and correct: zoom transforms the source image, so it belongs in the chain that assembles the master, not in an alpha overlay |
| Caption renderer | Remotion, not ASS/libass | The Remotion overlay path is already in daily production use (Ov22/Ov24 in catalog-4 K5). ASS would add a second rendering mechanism with a worse result — no rounded highlight box, no scale animation on a tracked active line, no title card |

### Phase 1 — Kinetic captions

**New:** `tools/gen_captions.py`, `templates/remotion/Captions.template.tsx`.

`gen_captions.py` reads word timings from `vo/vo-manifest.json`, and for platform-spoken dialogue
reuses the AssemblyAI path already in `tools/gen_subs.py` — that transcription code is imported,
not copied. As in `gen_subs.py`, **caption text always comes from the script**; a recognizer
supplies timing only.

Keyword scoring, fixed rules, highest score per caption page wins:

- numbers with a unit or currency (`1 sampai 4 tahun`, `Rp 325 juta`, `30%`)
- product and brand names drawn from `strategic-brief.md` (`derive_keyterms()` is reused)
- ALLCAPS acronyms
- reversal words from a closed list: `tapi`, `justru`, `bukan`, `hanya`, `malah`, `padahal`

Two hard caps: at most one highlighted phrase per caption page, and at most 25% of a scene's pages
may carry one. Highlighting everything highlights nothing.

Output is `work/caption-plan.json`: per scene, the word list with timings, the highlight spans, and
the `combineTokensWithinMilliseconds` value. The file is written once and reused on re-render, so
the same project always yields the same video. A wrong pick is fixable by editing the file.

The Remotion component calls `createTikTokStyleCaptions()` from `@remotion/captions` for page
splitting rather than reimplementing it. Its `Caption` shape (`{text, startMs, endMs}`) maps
directly onto the manifest's word records. **`@remotion/captions` must be added to the scaffold's
`package.json`** — `templates/remotion/scaffold.mjs` currently pins `remotion ^4.0.0` with no
captions package.

Rendering, per the reference frames: a stack of up to three lines; the line being spoken is large
and at full opacity, the others smaller and dimmed; each word appears at its own `start_ms`; a
highlighted phrase gets an accent-coloured box that grows from zero width behind it.

Legibility floors are the existing ones (`MIN_BODY_PX` 32, `SAFE_MARGIN_PCT` 5, from
`global-promo-config.md` §29.5). Contrast is checked with `check_contrast()` from
`tools/burn_subs.py`, imported rather than rewritten.

**`gen_subs.py` and the SRT output stay.** YouTube needs a sidecar caption file, and if Node
rendering fails the video still ships with plain burned captions. This phase adds a track; it
removes nothing.

### Phase 2 — Title cards

**New:** `templates/remotion/TitleCard.template.tsx`.

An accent eyebrow line above a large display title, each line entering with a short rise and fade,
holding ~2.5s, then leaving. Colour and both typefaces come from `brand.json`.

Triggered by a scene carrying a topic title in `scene-plan.md` — typically an act opening or a
topic change. The side of frame (left or right) is written into the plan so the card never covers
a speaking face.

**Title card and kinetic captions never render at the same time.** On overlap the title card wins
and captions are held until it leaves. Two large text blocks at once give the eye no reading order.

### Phase 3 — Shot motion

**Changed:** `tools/edit_render.py`, the Pass 2 planning step in `skills/video-post/SKILL.md`.

Each segment in `work/edit-plan.json` gains an optional `motion` field:

```json
{"kind": "punch-in", "from": 1.0, "to": 1.08}
```

`kind` is one of `punch-in`, `punch-out`, `none`.

Pass 2 fills it automatically: a segment longer than 5s is divided into 3–5s beats with alternating
direction; a segment of 5s or less gets one slow move in a single direction. The user is shown a
short list (`S12 8.4s -> in 0-4.2, out 4.2-8.4`) before rendering and may edit the plan.

Implementation attaches to the `vf` chain already built in `build_commands()`
(`tools/edit_render.py:153`). **Not `zoompan`** — it rounds pan position to whole pixels, so a slow
move visibly stutters. Use an upscale followed by `crop` with time expressions, which moves at
sub-pixel precision.

Maximum zoom factor is **1.12**. Beyond that, 1080p platform-generated clips go visibly soft, which
costs more than a still frame does.

A segment with no `motion` field renders exactly as it does today — this field is additive and old
plans keep working.

### Data integration map

| Component | Data source | Existing? | Notes |
|---|---|---|---|
| Word timings (narration) | `vo/vo-manifest.json` | Yes | Free, from ElevenLabs |
| Word timings (platform dialogue) | AssemblyAI | Yes | Via `gen_subs.py`'s transcribe path, imported |
| Caption text | `av-script.md` | Yes | Text never comes from the recognizer |
| Colour and type | `shots/src/brand.json` | Yes | Written from `strategic-brief.md` |
| Keyword candidates | `strategic-brief.md` + scoring rules | Partial | `derive_keyterms()` reused; number and reversal rules are new |
| Topic titles | `scene-plan.md` `Title Card` column | **No** | Corrected 2026-09-20 while planning: no title column exists today. Phase D of the plan creates it, following the `Render Path` / `Screen Source` pattern |
| Overlay compositing | `tools/composite.py` | Yes | Same path as Ov22/Ov24 in catalog-4 K5 |
| Shot motion | `tools/edit_render.py` | No | New `motion` field |

No placeholder data anywhere. Every input already exists in the pipeline.

### Degradation

| Situation | Behaviour |
|---|---|
| Node or Remotion unavailable | Kinetic track skipped; SRT burn-in still ships the video. Warn, exit 0 |
| Scene has no timing source | Listed as untimed, as today. Timings are never invented |
| `brand.json` missing a needed token | Refuse and name the token. No fallback palette — the plugin ships none |
| Caption contrast below 4.5:1 | Refuse, via the existing `check_contrast()` |
| Old `edit-plan.json` with no `motion` field | Renders as today |

### Out of scope

- Motion other than zoom (cutaways, B-roll inserts, PIP alternation) — needs material that usually
  is not there, and falls back to zoom anyway
- Changing how `scene-plan.md` decides scene length; this ticket only adds motion within a shot
- Replacing or removing `gen_subs.py` / SRT output
