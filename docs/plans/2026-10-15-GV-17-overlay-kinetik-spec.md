**Ticket:** GV-17

# Kinetic text overlay with media panels behind the speaker

Source: reference video `reference/snapgram.io_uyws7kjkx870.mp4` (99 s, 9:16, Indonesian
explainer, presenter in an office), watched in full by the session on 2026-10-15. Frame
evidence (1 fps sheets, 10 fps crops at 8.6 s, 50.2 s, 70.8 s) is the basis of every look and
motion rule below.

## Design

### Problem

The approved keyword overlay (v3.10.0, `tools/keyword_cards.py`,
`reference/post-production/19-keyword-text-overlay.md`) draws a gold serif-italic keyword that
flies in from the edge. The user now wants the reference video's style instead: two-tier bold
sans text that animates in on the spoken word, plus floating image/video panels that sit
BEHIND the speaker's head and in front of the room. Text must never be static.

### Decisions (user, 2026-10-15)

| # | Question | Answer |
|---|----------|--------|
| 1 | New style vs gold-serif style | **Replace** the old style |
| 2 | Where panel media comes from | **Mixed, per cue**: user file, project ref (NB2/VEO render), or a Remotion component |
| 3 | Depth (panel behind head) | **Automatic person mask every frame** |
| 4 | Elements in v1 | **All**: two-tier text, floating panels incl. carousel, round photo bubbles + line icons, source box |
| 5 | Engine | **A — one Remotion composition** |
| 6 | Text animation | **Six effects below**, effect 1 is the default; text is never static |
| 7 | Old tool | **Keep `keyword_cards.py`** (marked superseded) until the new style ships in one real video; delete it then, in a later ticket |

### Look (from the reference)

- **Two tiers.** Lead words small regular sans white (~40 px at 1080 w), keyword big heavy sans
  white (~110–150 px), tight leading, centred over the empty space above or beside the speaker.
- **Yellow** (`#F5E625`-ish, exact value goes in `brand.json`) for numbers and hard words
  ("1%", "221", "4x", "LEBIH TEGAS"). Everything else white.
- **Script accent**: an occasional word in a handwriting face ("cerita", "sekarang", "buat mereka").
- Soft dark shadow only. **No box, no pill** behind text (the existing rule survives).
- **Line icon** (fire, gavel, chart, cloud) above a block, white stroke.
- **Panels**: rounded corners (~28 px), image or video, sometimes a map, sometimes a horizontal
  carousel of year cards ("2019", "2023") sliding left. Caption text may sit on the panel.
- **Round photo bubbles** beside the torso with a two-tier label ("Jutaan / warga biasa").
- **Source box** bottom-left: tiny text, dark translucent background, from `av-script.md`.

### Text animation — six effects (mandatory, never static)

| # | Effect | Reference moment | Use |
|---|--------|------------------|-----|
| 1 | **Blur-to-sharp**: opacity 0→1, blur ~12 px→0, scale 1.06→1, ~0.3 s | "ekonomi kita", "baru 1 layer" | default keyword |
| 2 | **Glitch slices**: glyphs cut into horizontal slices offset sideways, snap together ~0.3 s | "LEBIH TEGAS" | hard / warning word |
| 3 | **Count-up**: number ticks from 0 to its value, ~0.6 s, final value held | "221", "1.9%", "1%" | statistics |
| 4 | **Handwrite**: script word drawn stroke by stroke | "cerita", "sekarang" | personal accent |
| 5 | **Stroke draw**: icon, arrow or scribble circle draws itself | fire icon, chart icon, circle on "hukumannya" | decoration |
| 6 | **Exit**: fade + blur out ~0.2 s, next block may overlap ~0.1 s | every block | every cue |

Lead words enter first (fade + 8 px rise); the keyword enters exactly on its spoken word.
Panels and bubbles enter with a spring (scale 0.9→1, opacity) and drift slowly (±6 px) while held.
A cue without `fx` gets effect 1 in and effect 6 out. The renderer has no "static" path.

### Architecture

```
clip (scene-NN.mp4) ──► tools/person_mask.py ──► .tmp/mask-NN/%05d.png  (alpha, cached by clip sha256)
vo/vo-manifest.json ─┐
av-script.md ────────┼─► work/overlay-plan.json (cues; times resolved from words)
ref/, user files ────┘
                         └─► shots/src/shots/Overlay-NN.tsx (from Overlay.template.tsx)
                                layers, bottom → top:
                                1 clip (OffthreadVideo)
                                2 panels + bubbles   (layer "behind")
                                3 person cutout      (clip × mask)
                                4 text + icons       (layer "front", default)
                                5 source box
                         └─► Remotion render → shots/out/overlay-NN.mp4 → qa stills per cue
```

**New**

- `tools/person_mask.py` — needs the venv (`mediapipe` added to `requirements.txt`, re-exec via
  `_venv.py`). Writes one grayscale PNG per frame. Cached: an unchanged clip (sha256) is not
  re-segmented. Refuses (exit 1, names the frames) when no person is found in more than 10% of
  frames — it never guesses a mask. Feather 3–6 px.
- `work/overlay-plan.json` — schema: `cues[]` with `lead`, `keyword`, `fx` (1–5), `color`
  (`white|yellow`), `icon`, `script` (bool), `pos` (`top|left|right` + optional x/y), `layer`
  (`front|behind`), `words` (the spoken phrase to anchor to), and `panels[]` / `bubbles[]` with
  `src` = `user:<path>` | `ref:<file>` | `remotion:<Component>`, plus `source` text. Times are
  NOT written by hand: they resolve from `vo-manifest.json` word timestamps, the same way
  `tools/gen_captions.py` does. An anchor phrase not found in the words → the plan is refused.
- `templates/remotion/Overlay.template.tsx` and `templates/remotion/lib/overlay-fx.tsx` — the
  five layers and the six effects; brand colours and fonts only from `brand.json`.

**Changed**

- `reference/post-production/19-keyword-text-overlay.md` — rewritten for this style (look,
  six effects, layers, placement off the face/mouth, mask rules). The red alarm flash section
  stays and now uses the automatic mask.
- `video-gen` Rule 25, `tests/consistency/keyword-text-overlay.sh`, `CLAUDE.md` (tool table,
  reference table, changelog, tool count), plugin version bump.
- `tools/keyword_cards.py` — kept, header marks it superseded by GV-17; not deleted (decision 7).

**Reused, unchanged**: `vo/vo-manifest.json`, `tools/gen_captions.py` word lookup,
`templates/remotion/lib/{brand.ts,kit.tsx}`, `templates/remotion/scripts/qa-frames.mjs`,
`templates/remotion/scaffold.mjs`.

### Data Integration Map

| Component | Data source | Existing? | Notes |
|-----------|-------------|-----------|-------|
| Cue timing | `vo/vo-manifest.json` words | Yes | anchor phrase lookup, refuse on miss |
| Source box text | `av-script.md` | Yes | never invented |
| Panel media | `ref/`, user path, Remotion component | Partly | missing file → refuse, no placeholder |
| Person mask | `tools/person_mask.py` (MediaPipe) | New | cached by clip sha256 |
| Colours, fonts | `shots/src/shots/brand.json` | Yes | yellow + script font added as tokens |
| Visual QA | `qa-frames.mjs` still per cue | Yes | text must not cover face/mouth |

### Error handling

- No person in >10% of frames → `person_mask.py` exits 1 with frame list.
- Anchor phrase not in `vo-manifest.json` → plan refused, names the cue.
- Panel `src` file missing → refused, names the cue; no stand-in image.
- Missing venv module → exit 2 naming `tools/setup.sh` (existing `_venv.py` contract).
- Cue with `layer: behind` but no mask for that scene → refused (would silently render in front).

### Testing

- Python unittest for `person_mask.py` caching + refusal (synthetic clip with and without a person
  shape is not enough for MediaPipe — use a short real clip fixture, or mock the model at the
  segmentation call and test the threshold/caching logic around it).
- Unittest for plan resolution: anchor found, anchor missing, panel missing, behind-without-mask.
- Consistency test: doc 19 describes six effects and no gold-serif rule; Rule 25 points at the
  new tool; `keyword_cards.py` header says superseded.
- Real-run evidence (required before merge): one real speaker clip rendered with at least one cue
  of each effect, one `behind` panel, one bubble, one source box; QA stills attached in the plan
  ledger.

### Out of scope

- Deleting `keyword_cards.py` (later ticket, after one real video).
- Auto-choosing which words become cues (the plan is written by Claude per scene, as today).
- Map animation as a built-in component (a map is a `remotion:<Component>` the project writes,
  or a user/ref video).
