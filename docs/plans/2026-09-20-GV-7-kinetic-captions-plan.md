> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-7.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. This is **blocking**, like a test gate: no next phase until both are written. **Never batch all updates at the end.** Update ONLY this file — never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. It must be executable by an agent with **no other context**. Every file path, contract, config key, and convention it needs is written here verbatim.

**Ticket:** GV-7
**Ledger:** .gaspol/progress/PROGRESS-GV-7.md
**Spec:** docs/plans/2026-09-20-GV-7-kinetic-captions-spec.md

## Goal

Give gaspol-video three things it does not have: captions that reveal word by word with one
highlighted key phrase per page, title cards at topic boundaries, and automatic zoom on any shot
that would otherwise hold still for more than five seconds. Remotion draws the text; ffmpeg does
the zoom. Word timings already exist in `vo/vo-manifest.json`; nothing here invents data.

## Architecture Context

Read from `CLAUDE.md` of this repo and from the files themselves:

- **Tools are stdlib-only Python 3 in `tools/`.** No pytest, no npm, by design — `tests/run.sh`
  says so in its own header. Tests are `python3 -m unittest` under `tests/py/`, `node --test` under
  `tests/node/`, and bash contract checks under `tests/consistency/`.
- **`tools/gen_subs.py`** builds SRT cues. `_cues_from_words()` (line 113) collapses per-word
  timings into two-line blocks. `derive_keyterms(project, limit=40)` (line 83) already pulls
  ALLCAPS acronyms and capitalised multi-word names from the brief.
  `transcribe_assemblyai(audio_path, api_key, keyterms, ...)` (line 218) returns
  `{"words": [{"text", "start_ms", "end_ms", ...}]}`. **Import these; do not copy them.**
- **`tools/burn_subs.py`** owns `check_contrast(foreground, background)` and
  `MIN_CONTRAST_RATIO = 4.5`. **Import it; do not re-derive WCAG maths.**
- **`tools/composite.py`** has four modes. `overlay <master> <shot> --at <s> [--out-s <s>] -o <out>`
  composites a transparent shot over the picture and keeps master audio. This is the mode the
  caption track and the title card use. `require_alpha(shot)` is enforced by the CLI.
- **`tools/edit_render.py`** assembles the master from `work/edit-plan.json`.
  `build_commands(plan)` (line 153) builds one ffmpeg invocation per segment. Its current video
  filter chain, verbatim:
  ```
  scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}
  ```
  followed by `,tpad=stop_mode={clone}:stop_duration={pad}` when `pad_end_s` is set.
  `VALID_KINDS = ("clip", "shot")`, `AV_TOLERANCE_S = 0.04`, `PlanError` is raised for a plan whose
  numbers do not hold up — validation runs BEFORE ffmpeg is touched.
- **`templates/remotion/scaffold.mjs`** writes the per-project Remotion workspace. Its
  `PACKAGE_JSON.dependencies` currently lists `@remotion/cli`, `@remotion/bundler`,
  `@remotion/renderer`, `remotion`, all `^4.0.0`. It copies every file from
  `templates/remotion/lib/` into `src/lib/` and every file from `templates/remotion/scripts/` into
  `scripts/`.
- **`templates/remotion/Shot.template.tsx`** states the rules a composition must obey: frame-based
  animation only (no `useState`, no `useEffect`, no `setTimeout`, no unseeded `Math.random`),
  strictly increasing `interpolate` input ranges, `Easing.bezier` called directly,
  `compositionConfig.id` in PascalCase, and colours/fonts from `brand.json` — *"This plugin ships
  NO palette: the look belongs to the client, not to the tool."*
- **`brand.json` shape**, as written in production projects today:
  ```json
  {
    "background": "#FAF8F4",
    "ink": "#1A1A1A",
    "inkSoft": "#5A5A5A",
    "accent": "#6366F1",
    "displayFont": "Inter, system-ui, sans-serif",
    "bodyFont": "Inter, system-ui, sans-serif"
  }
  ```
- **`vo/vo-manifest.json` shape:** top-level `items`, each
  `{"id", "file", "duration_s", "cast", "voice_env", "chars", "words"}`. `words` entries are
  `{"text", "start_ms", "end_ms"}`. `tools/gen_vo.mjs` calls the ElevenLabs
  `/with-timestamps` endpoint and derives `words` from the character alignment (line 211), so
  the timings cost nothing extra. **`words` is empty for some items in practice** — measured:
  `catalog-2/vo/vo-manifest.json` has words for 14 of 33 items. Empty is a real case, not a
  theoretical one.
- **Per-scene attributes follow an established pattern** — `Render Path` (v3.0.0) and
  `Screen Source` (v3.1.0) each added a `scene-plan.md` column, an assignment rule in
  `reference/script-to-scene-bridge.md`, a line in `skills/video-script/SKILL.md` Phase 3, and a
  contract check in `tests/consistency/`. Phase D follows exactly this shape.
- **`scene-plan.md` has NO title/topic column today.** The spec's Data Integration Map claimed it
  did; that claim is wrong and is corrected in this plan. Phase D creates the column.
- **Two files hardcode the plugin version** and will fail the suite until both are bumped:
  `tests/consistency/tools-index.sh` (`grep -qF '"version": "3.4.0"' .claude-plugin/plugin.json`)
  and `tests/consistency/plugin-identity.sh` (`want_version="3.4.0"`).
- **`tests/consistency/tools-index.sh` also requires** that every `tools/*.py` and `tools/*.mjs`
  basename appears somewhere in `CLAUDE.md`. Two new tools means two new CLAUDE.md entries or the
  suite goes red.

## Tech Stack

- Python 3, stdlib only. No new Python dependency, ever, in `tools/`.
- Node, for the Remotion workspace only. **One new npm dependency:** `@remotion/captions`, added to
  `templates/remotion/scaffold.mjs`'s `PACKAGE_JSON.dependencies` at `^4.0.0` to match the others.
  It supplies `createTikTokStyleCaptions()`, which segments a token list into caption pages; a low
  `combineTokensWithinMilliseconds` yields word-by-word. Its `Caption` shape is
  `{text, startMs, endMs, timestampMs, confidence}` — `text` must carry its own leading whitespace,
  and the rendering container needs `white-space: pre`.
  Docs: <https://www.remotion.dev/docs/captions/create-tiktok-style-captions>
- ffmpeg, for the zoom. **Not `zoompan`** — it rounds pan position to whole pixels, so a slow move
  stutters. Upscale, then `crop` with a `t` expression, then scale back.

## Verification commands (resolved for THIS repo)

`skills/gaspol-execute/scripts/detect-stack .` returns `static: UNKNOWN`, `lint: UNKNOWN`,
`unit: pytest`. **The `unit` answer is wrong for this repo** — there is no pytest here and
`tests/run.sh` says so deliberately. Resolved by the user on 2026-09-20:

| Level | Command |
|---|---|
| static | `python3 -m compileall -q tools` |
| lint | none configured in this repo — no linter config file exists; do not invent one |
| unit | `bash tests/run.sh` |

Every phase's Verification block uses exactly these.

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Word timings (narration) | `vo/vo-manifest.json` → `items[].words` | read JSON | Yes | Use directly |
| Word timings (platform dialogue) | AssemblyAI | `gen_subs.transcribe_assemblyai()` | Yes | **Import from `tools/gen_subs.py`** |
| Caption text | `av-script.md` | `gen_subs` script reader | Yes | Text never comes from the recognizer |
| Brand keyword candidates | `strategic-brief.md` | `gen_subs.derive_keyterms()` | Yes | Import and reuse |
| Contrast check | — | `burn_subs.check_contrast()` | Yes | Import; do not re-derive |
| Colour and type | `shots/src/shots/brand.json` | JSON import in the component | Yes | Use existing keys only |
| Caption page splitting | `@remotion/captions` | `createTikTokStyleCaptions()` | No | Add to `scaffold.mjs` deps |
| Topic title per scene | `scene-plan.md` `Title Card` column | new column | **No** | Create in Phase D — spec was wrong |
| Overlay compositing | `tools/composite.py overlay` | CLI | Yes | Use as-is |
| Shot motion | `work/edit-plan.json` `motion` field | `edit_render.build_commands()` | No | Create in Phase E |
| Automatic motion planning | `work/edit-plan.json` | `tools/plan_motion.py` | No | Create in Phase F |

No placeholders anywhere. Every "No" row is built as a real, working integration in a named phase.

## Phase overview

| Phase | Code Deliverable | Design Deliverable | Verification |
|---|---|---|---|
| A | keyword span scoring, pure functions | n/a (no UI) | unit + static |
| B | `tools/gen_captions.py`, plan IO | n/a (no UI) | unit + static |
| C | `Captions.template.tsx` + page math module | caption layout: 3-line stack, active line full opacity, others dimmed, highlight box grows from zero width — all tokens from `brand.json` | unit + node test + contrast check |
| D | `TitleCard.template.tsx` + `Title Card` column | title card: accent eyebrow over display title, per-line rise+fade, 2.5s hold, side declared in the plan | unit + consistency contract |
| E | `motion` field + ffmpeg filter | n/a (no UI) | unit + static |
| F | `tools/plan_motion.py` | n/a (no UI) | unit + static |
| G | docs sync, version 3.5.0 | n/a | full suite |

Phases A→B→C are sequential. D depends on B and C. E and F are independent of A–D and may run in
parallel with them. G is last.

---

### Phase A: keyword span scoring

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/caption_keywords.py`
- Test: `tests/py/test_caption_keywords.py`

**What this phase owes (completeness ladder):**
1. *Happy path* — score candidate spans in a word list, return the winners.
2. *Error paths* — malformed word records (missing `text`); a word list that is not a list.
3. *Edge cases* — empty list; one word; no candidate at all; tied scores; a span running to the
   last word; duplicate identical spans; a page that is entirely stopwords.
4. *Tests* — one failing test first, then a covering case for every item above.
5. *Observability* — every returned span carries the `rule` that matched and its `score`, so a
   wrong pick is explainable from the plan file alone without re-running anything.

**The contract, verbatim:**

```python
def score_spans(words):
    """words: list of {"text": str, ...}. Returns list of
    {"start_word": int, "end_word": int, "score": int, "rule": str},
    sorted by (-score, start_word). Spans never overlap: the higher score wins,
    ties go to the earlier span."""
```

Rules and their scores. A span is the **maximal** run of words matching its rule.

| Rule | Matches | Score |
|---|---|---|
| `number-unit` | a digit run or a spelled number (`satu`..`sepuluh`, `puluh`, `ratus`, `ribu`, `juta`, `miliar`) together with an adjacent unit, currency or time word (`Rp`, `%`, `tahun`, `bulan`, `hari`, `jam`, `detik`, `menit`, `kali`, `persen`), including an interior `sampai`/`hingga`/`-` | 9 |
| `brand-term` | a term returned by `gen_subs.derive_keyterms(project)`, passed in by the caller as `keyterms` | 7 |
| `acronym` | a token of two or more characters, all uppercase letters or digits, with at least one letter | 6 |
| `reversal` | one of the closed list `tapi`, `tetapi`, `justru`, `bukan`, `hanya`, `malah`, `padahal` | 4 |

Comparison is case-insensitive and ignores trailing punctuation. `"di 1 sampai 4 tahun setelahnya"`
yields one `number-unit` span covering `1 sampai 4 tahun`, not three spans.

**Steps:**
1. Write failing test `test_number_unit_span_covers_whole_range` asserting
   `score_spans([{"text": w} for w in "di 1 sampai 4 tahun setelahnya".split()])` returns exactly
   one span `{"start_word": 1, "end_word": 4, "score": 9, "rule": "number-unit"}`.
   Expected error: `ModuleNotFoundError: No module named 'tools.caption_keywords'`
2. Run `bash tests/run.sh py`, confirm it fails for that reason.
3. Implement `tools/caption_keywords.py` with the rule table above.
4. Run `bash tests/run.sh py`, confirm pass.
5. Add test: empty list returns `[]`; single word with no rule match returns `[]`.
6. Add test: two spans with equal score — the earlier `start_word` sorts first.
7. Add test: overlapping `acronym` inside a `number-unit` span — only the higher-scoring span is
   returned, no overlap in the output.
8. Add test: a word record missing `"text"` raises `CaptionKeywordError` naming the index.
9. Add test: span ending on the final word is returned with `end_word == len(words) - 1`.
10. Run `bash tests/run.sh py`, confirm all pass.
11. Commit: `feat(GV-7): keyword span scoring for kinetic captions`

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] lint: none configured in this repo — no linter check applies to this phase
- [ ] unit: `bash tests/run.sh` passes
- [ ] `score_spans` returns non-overlapping spans sorted by `(-score, start_word)`
- [ ] Every returned span carries both `rule` and `score`
- [ ] No placeholder/TODO comments in new code

---

### Phase B: caption plan builder

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/gen_captions.py`
- Test: `tests/py/test_gen_captions.py`

**What this phase owes:**
1. *Happy path* — read `vo/vo-manifest.json` + the script, apply Phase A scoring, write
   `work/caption-plan.json`.
2. *Error paths* — manifest missing; manifest not valid JSON; no `ASSEMBLYAI_API_KEY` when a scene
   needs the recognizer; AssemblyAI returns no words.
3. *Edge cases* — `items[].words` empty (measured: 19 of 33 items in `catalog-2`); a scene with no
   timing source at all; a scene whose every candidate scores below the cap; re-running when the
   plan file already exists; `--force` overriding that; two scenes sharing one vo item.
4. *Tests* — failing test first; a covering case for each of the above.
5. *Observability* — `untimed` lists every scene that got no timing and why; each scene records its
   `timing_source` (`elevenlabs` / `assemblyai` / `none`).

**Plan file schema, verbatim — `work/caption-plan.json`:**

```json
{
  "version": 1,
  "generated_at": "2026-09-20T12:00:00Z",
  "style": {
    "combine_tokens_within_ms": 400,
    "max_lines": 3,
    "min_body_px": 32,
    "safe_margin_pct": 5
  },
  "scenes": [
    {
      "scene": 12,
      "vo_item_id": "scene-12-narr",
      "offset_s": 41.2,
      "timing_source": "elevenlabs",
      "words": [{"text": "harga", "start_ms": 0, "end_ms": 320}],
      "highlights": [{"start_word": 4, "end_word": 7, "score": 9, "rule": "number-unit"}]
    }
  ],
  "untimed": [{"scene": 7, "reason": "no words in manifest and no ASSEMBLYAI_API_KEY"}]
}
```

**Caps, applied per scene after Phase A returns its sorted spans:**
- Pages are computed as `ceil(len(words) / 6)` for cap purposes only — the real page split happens
  in the Remotion component. Allowed highlights = `max(1, pages // 4)`.
- At most one highlight per page: two spans whose word indices fall in the same page bucket — the
  lower-scoring one is dropped.

**Determinism:** running the tool twice on unchanged inputs must produce byte-identical
`scenes` and `untimed` (`generated_at` is the only field allowed to differ). By default the tool
**reuses an existing plan** and exits 0 without rewriting; `--force` regenerates.

**Steps:**
1. Write failing test `test_builds_plan_from_manifest_words` with the `VO_MANIFEST` fixture style
   already used in `tests/py/test_gen_subs.py`, asserting the written plan has one scene with
   `timing_source == "elevenlabs"` and a `number-unit` highlight.
   Expected error: `ModuleNotFoundError: No module named 'tools.gen_captions'`
2. Run `bash tests/run.sh py`, confirm it fails for that reason.
3. Implement `tools/gen_captions.py`: read the manifest, import
   `from tools.gen_subs import derive_keyterms, transcribe_assemblyai` and
   `from tools.caption_keywords import score_spans`, apply the caps, write the plan.
4. Run `bash tests/run.sh py`, confirm pass.
5. Add test: item with `"words": []` and no `ASSEMBLYAI_API_KEY` lands in `untimed` with that reason
   and is absent from `scenes`. Timings are never invented.
6. Add test: item with `"words": []` and a patched `transcribe_assemblyai` returning words produces
   `timing_source == "assemblyai"`.
7. Add test: running twice without `--force` leaves the file byte-identical apart from
   `generated_at`, and the second run exits 0.
8. Add test: `--force` regenerates and the two runs' `scenes` are byte-identical.
9. Add test: a 3-page scene with four scoring spans keeps exactly one highlight
   (`max(1, 3 // 4) == 1`).
10. Add test: missing `vo/vo-manifest.json` exits non-zero with a message naming the file.
11. Add test: a manifest that is not valid JSON raises with the filename in the message.
12. Run `bash tests/run.sh py`, confirm all pass.
13. Commit: `feat(GV-7): caption plan builder with reusable, deterministic output`

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] lint: none configured in this repo — no linter check applies to this phase
- [ ] unit: `bash tests/run.sh` passes
- [ ] Plan is built from `vo/vo-manifest.json` and `gen_subs` imports — no duplicated AssemblyAI code
- [ ] Two consecutive runs produce byte-identical `scenes`
- [ ] A scene with no timing source appears in `untimed`, never with guessed timings
- [ ] No placeholder/TODO comments in new code

---

### Phase C: kinetic caption composition

**Estimated time:** 15 minutes

**Files:**
- Create: `templates/remotion/lib/captionPages.mjs`
- Create: `templates/remotion/Captions.template.tsx`
- Modify: `templates/remotion/scaffold.mjs` (add `"@remotion/captions": "^4.0.0"` to
  `PACKAGE_JSON.dependencies`)
- Test: `tests/node/caption-pages.test.mjs`
- Test: `tests/py/test_caption_contrast.py`

**Design deliverable (from the approved spec, not re-derived here):** a stack of up to three lines.
The line being spoken renders at full opacity and the larger size; the others render smaller and
dimmed. Each word appears at its own `start_ms`. A highlighted span gets a box in `accent` that
grows from zero width behind it. Font sizes never fall below `min_body_px` (32); nothing is drawn
inside `safe_margin_pct` (5) of any edge. Every colour and both typefaces come from `brand.json` —
`background`, `ink`, `inkSoft`, `accent`, `displayFont`, `bodyFont`. No colour is written into the
component.

**Why the page math is its own `.mjs` module:** a Remotion component cannot be unit-tested without
rendering. The page/word/highlight arithmetic moves into `captionPages.mjs`, which `node --test`
imports directly; the component stays a thin renderer of what that module returns. Same reasoning
as `tools/` being stdlib-only — the testable part must not need the heavy runtime.

**What this phase owes:**
1. *Happy path* — plan JSON in, pages with per-word timings and highlight flags out, rendered by a
   composition that obeys the `Shot.template.tsx` rules.
2. *Error paths* — `brand.json` missing a key the component needs; a highlight span whose indices
   fall outside the word list.
3. *Edge cases* — a page with one word; a highlight covering the whole page; a word with
   `end_ms <= start_ms`; more than three lines' worth of words on a page; empty `scenes`.
4. *Tests* — failing node test first; plus a Python contrast test that runs
   `burn_subs.check_contrast(brand["ink"], brand["background"])` and
   `check_contrast(brand["ink"], brand["accent"])` so an unreadable highlight is refused before a
   render is paid for.
5. *Observability* — `captionPages.mjs` throws with the scene number and word index in the message,
   never a bare `undefined`.

**Component rules that are non-negotiable** (copied from `templates/remotion/Shot.template.tsx`):
frame-based animation only — no `useState`, no `useEffect`, no `setTimeout`, no unseeded
`Math.random`; `interpolate` input ranges strictly increasing; `Easing.bezier` called directly, not
wrapped; `compositionConfig.id` in PascalCase (`KineticCaptions`). The container needs
`white-space: pre`, and every `text` handed to `createTikTokStyleCaptions()` carries its own leading
space — omitting it merges the whole page into one run.

**Steps:**
1. Write failing test `tests/node/caption-pages.test.mjs`: `buildPages(scene, style)` for a
   six-word scene with `combine_tokens_within_ms: 400` returns pages whose concatenated words equal
   the input words in order. Expected error:
   `Cannot find module '../../templates/remotion/lib/captionPages.mjs'`
2. Run `bash tests/run.sh node`, confirm it fails for that reason.
3. Implement `captionPages.mjs`: map plan words to `@remotion/captions` `Caption` records (leading
   whitespace on `text`), call `createTikTokStyleCaptions`, attach a `highlight` flag to each word
   whose index falls inside a span.
4. Run `bash tests/run.sh node`, confirm pass.
5. Add test: a highlight span with `end_word` beyond the word list throws, and the message contains
   the scene number.
6. Add test: a one-word scene returns exactly one page with one word.
7. Add test: `end_ms <= start_ms` on a word throws rather than producing a zero-length reveal.
8. Add `"@remotion/captions": "^4.0.0"` to `PACKAGE_JSON.dependencies` in
   `templates/remotion/scaffold.mjs`.
9. Write `templates/remotion/Captions.template.tsx` to the design deliverable above, importing
   `brand.json` and `./lib/captionPages.mjs`.
10. Write failing test `tests/py/test_caption_contrast.py` asserting a brand whose `ink` and
    `accent` are too close raises `StyleError` via `burn_subs.check_contrast`. Expected error:
    `ModuleNotFoundError: No module named 'tools.caption_contrast'` — or, if implemented as a
    function inside `gen_captions.py`, `AttributeError: module 'tools.gen_captions' has no
    attribute 'check_brand_contrast'`.
11. Run `bash tests/run.sh`, confirm it fails for that reason, then implement
    `check_brand_contrast(brand)` in `tools/gen_captions.py` and confirm pass.
12. Commit: `feat(GV-7): kinetic caption composition and page math`

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] lint: none configured in this repo — no linter check applies to this phase
- [ ] unit: `bash tests/run.sh` passes
- [ ] `grep -n '@remotion/captions' templates/remotion/scaffold.mjs` returns the dependency line
- [ ] `Captions.template.tsx` contains no hex colour and no font-family string — every token reads
      from `brand.json`
- [ ] `grep -nE 'useState|useEffect|setTimeout|Math\.random' templates/remotion/Captions.template.tsx`
      returns nothing
- [ ] `compositionConfig.id` is `KineticCaptions`, PascalCase, no hyphen or underscore
- [ ] Brand contrast below 4.5:1 is refused before rendering
- [ ] No placeholder/TODO comments in new code

---

### Phase D: title card and its scene-plan column

**Estimated time:** 15 minutes

**Files:**
- Create: `templates/remotion/TitleCard.template.tsx`
- Create: `tests/consistency/title-card-contract.sh`
- Modify: `reference/script-to-scene-bridge.md` (assignment rule)
- Modify: `skills/video-script/SKILL.md` (Phase 3 assigns the column)
- Modify: `tools/gen_captions.py` (suppress caption pages under a title card)
- Test: `tests/py/test_gen_captions.py` (extend)

**The new column.** `scene-plan.md` gains `Title Card`, placed right after `Screen Source`, exactly
as `Render Path` (v3.0.0) and `Screen Source` (v3.1.0) were added before it. Values:

| Value | Meaning |
|---|---|
| `—` | no card on this scene (the default; most scenes) |
| `left: <eyebrow> / <title>` | card on the left third |
| `right: <eyebrow> / <title>` | card on the right third |

The side is declared, never guessed, so the card never covers a speaking face. Assignment rule, to
be written into `reference/script-to-scene-bridge.md`: a scene gets a card when it opens an ACT or
changes topic — at most one per ACT. A card on consecutive scenes is a defect, not a style.

**The overlap rule.** A title card holds for 2.5s from its scene's start. Caption pages that would
begin inside that window are pushed to its end; a page already running when the card begins is left
alone. Two large text blocks at once give the eye no reading order. Enforced in `gen_captions.py`,
which is the only place that knows both timelines.

**What this phase owes:**
1. *Happy path* — a scene with `left: Grafik Depresiasi / Mobil Listrik` produces a card and its
   captions start after 2.5s.
2. *Error paths* — a malformed cell (no `/`, unknown side) raises naming the scene.
3. *Edge cases* — card on the very first scene at t=0; a scene shorter than 2.5s; two consecutive
   scenes both carrying a card; a card with an empty eyebrow; a scene with a card but no captions.
4. *Tests* — failing test first; a covering case for each; plus the consistency contract.
5. *Observability* — the suppression is recorded per scene in the plan as
   `"captions_held_until_s": 2.5`, so a gap in the captions is explainable from the file.

**Steps:**
1. Write failing test `test_title_card_holds_captions` asserting a scene with a `Title Card` cell
   has `captions_held_until_s == 2.5` and its first caption page starts at or after that.
   Expected error: `KeyError: 'captions_held_until_s'`
2. Run `bash tests/run.sh py`, confirm it fails for that reason.
3. Implement scene-plan `Title Card` parsing and the hold in `tools/gen_captions.py`.
4. Run `bash tests/run.sh py`, confirm pass.
5. Add test: a cell with no `/` raises, and the message names the scene number.
6. Add test: an unknown side (`center: a / b`) raises naming the allowed values.
7. Add test: a scene shorter than 2.5s holds captions for the scene's own length, not 2.5s.
8. Add test: a scene with `—` gets no `captions_held_until_s` key at all.
9. Write `templates/remotion/TitleCard.template.tsx`: accent-coloured eyebrow in `bodyFont` above a
   large title in `displayFont`, each line rising and fading in, 2.5s hold, then out. Same
   non-negotiable component rules as Phase C. `compositionConfig.id` is `TitleCard`.
10. Write `tests/consistency/title-card-contract.sh` on the shape of
    `tests/consistency/render-path-contract.sh`: assert `Title Card` is defined in
    `reference/script-to-scene-bridge.md`, assigned in `skills/video-script/SKILL.md`, that the
    pre-existing `Render Path` and `Screen Source` columns are still present and untouched, and
    that `skills/video-post/SKILL.md` states the caption-hold rule.
11. Write the column into `reference/script-to-scene-bridge.md` and
    `skills/video-script/SKILL.md` Phase 3.
12. Run `bash tests/run.sh`, confirm all three groups pass.
13. Commit: `feat(GV-7): title card composition and scene-plan Title Card column`

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] lint: none configured in this repo — no linter check applies to this phase
- [ ] unit: `bash tests/run.sh` passes
- [ ] `bash tests/consistency/title-card-contract.sh` exits 0
- [ ] `bash tests/consistency/render-path-contract.sh` still exits 0 — the older columns survived
- [ ] `TitleCard.template.tsx` contains no hex colour and no font-family string
- [ ] A scene carrying a card records `captions_held_until_s` in the plan
- [ ] No placeholder/TODO comments in new code

---

### Phase E: `motion` field and the ffmpeg filter

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/edit_render.py`
- Test: `tests/py/test_edit_render.py` (extend — the file already exists)

**The field, verbatim.** Each segment in `work/edit-plan.json` may carry:

```json
{"kind": "punch-in", "from": 1.0, "to": 1.08}
```

| Constraint | Rule |
|---|---|
| `kind` | one of `punch-in`, `punch-out`, `none` |
| `from`, `to` | finite floats, `1.0 <= v <= 1.12` |
| `punch-in` | requires `to > from` |
| `punch-out` | requires `to < from` |
| `none` | `from` and `to` ignored; renders exactly as today |
| absent | renders exactly as today — the field is additive, old plans keep working |

**Why 1.12 is the ceiling:** beyond it, 1080p platform-generated clips go visibly soft, which costs
more than a still frame does. A plan asking for more raises `PlanError` naming the segment, in the
same validate-before-ffmpeg pass that already exists.

**The filter.** Inserted into the chain in `build_commands()` **after `pad=` and before `fps=`**,
where `F` is `from`, `T` is `to`, `D` is the segment duration, `W`/`H` the output size:

```
scale=iw*2:ih*2,crop=w='iw/2/(F+(T-F)*t/D)':h='ih/2/(F+(T-F)*t/D)':x='(iw-ow)/2':y='(ih-oh)/2',scale=W:H
```

The 2x upscale is what buys sub-pixel motion; it costs one 4K intermediate per segment at 1080p
output, which is the price of not using `zoompan`. A segment with no motion keeps today's chain
character for character.

**What this phase owes:**
1. *Happy path* — a `punch-in` segment renders with the crop expression above.
2. *Error paths* — unknown `kind`; non-finite `from`/`to`; `to` above 1.12; `punch-in` with
   `to <= from`; `punch-out` with `to >= from`. Each raises `PlanError` naming the segment index.
3. *Edge cases* — `from == to` on `kind: none`; a segment carrying `motion` and `pad_end_s` together
   (motion applies to the trimmed body, `tpad` still appends after); a zero-length segment; the
   field present but `null`.
4. *Tests* — failing test first; a covering case for each; plus a regression test that a plan with
   no `motion` produces a filter string identical to today's.
5. *Observability* — `--print` already exists on this tool and now shows the motion filter inline,
   so what ffmpeg will run is readable before it runs.

**Steps:**
1. Write failing test `test_punch_in_adds_crop_expression` asserting `build_commands()` for a
   segment with `{"kind": "punch-in", "from": 1.0, "to": 1.08}` yields a `-vf` value containing
   `crop=w='iw/2/(1.0+(0.08)*t/`. Expected error:
   `AssertionError: 'crop=' not found in 'scale=1920:1080:force_original_aspect_ratio=decrease,...'`
2. Run `bash tests/run.sh py`, confirm it fails for that reason.
3. Implement motion validation in the existing validate pass and the filter in `build_commands()`.
4. Run `bash tests/run.sh py`, confirm pass.
5. Add regression test: a plan with no `motion` key produces the exact filter string the tool
   produces today — assert the literal
   `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=25`.
6. Add test: `{"kind": "zoom-out"}` raises `PlanError` naming the segment index and listing the
   three valid kinds.
7. Add test: `{"kind": "punch-in", "from": 1.0, "to": 1.30}` raises `PlanError` mentioning 1.12.
8. Add test: `{"kind": "punch-in", "from": 1.08, "to": 1.0}` raises `PlanError` — direction and kind
   disagree.
9. Add test: `{"kind": "punch-out", "from": 1.08, "to": 1.0}` passes and its expression descends.
10. Add test: `motion` present alongside `pad_end_s` — the chain contains both the crop expression
    and `tpad`, in that order.
11. Add test: `"motion": null` is treated as absent, not as malformed.
12. Run `bash tests/run.sh`, confirm pass.
13. Commit: `feat(GV-7): animated zoom via motion field in edit-plan`

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] lint: none configured in this repo — no linter check applies to this phase
- [ ] unit: `bash tests/run.sh` passes
- [ ] A plan with no `motion` field renders the byte-identical filter chain it renders today
- [ ] `zoompan` appears nowhere in `tools/edit_render.py`
- [ ] Every invalid `motion` raises `PlanError` before ffmpeg is invoked
- [ ] No placeholder/TODO comments in new code

---

### Phase F: automatic motion planning

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/plan_motion.py`
- Test: `tests/py/test_plan_motion.py`

**Why a tool and not a skill instruction:** Pass 2 authors `work/edit-plan.json` by hand today. A
rule written only in prose produces a different answer every run. This tool reads the plan, fills
every empty `motion`, prints a report, and writes the plan back — so the same cut always gets the
same movement.

**The rule:**
- A segment longer than 5.0s is divided into beats of 3.0–5.0s. The beat count is
  `ceil(duration / 5.0)`; beats are equal length. Directions alternate, starting with `punch-in`.
  **Beats are emitted as separate segments** in the plan, each carrying its own `motion`, so
  `edit_render.py` needs no per-beat concept.
- A segment of 5.0s or less gets one `punch-in` from 1.0 to 1.04.
- `from`/`to` for a beat: `punch-in` 1.0 → 1.08, `punch-out` 1.08 → 1.0.
- A segment that already carries a `motion` field is left exactly as it is. Manual beats a planner.
- Report line format, one per changed segment:
  `S12 8.4s -> in 0.0-4.2, out 4.2-8.4`

**What this phase owes:**
1. *Happy path* — an 8.4s segment becomes two beats with alternating direction.
2. *Error paths* — plan file missing; plan not valid JSON; a segment with `out_s <= in_s`.
3. *Edge cases* — a segment of exactly 5.0s (one slow move, not split); 5.01s (two beats);
   a 30s segment (six beats); a segment already carrying `motion` (untouched); a segment of
   `kind: "shot"` — a Remotion shot is already animated, so it is skipped and said to be skipped;
   an empty segment list.
4. *Tests* — failing test first; a covering case for each.
5. *Observability* — the report names every segment it changed and every segment it skipped, with
   the reason. A silent planner is an unauditable one.

**Steps:**
1. Write failing test `test_long_segment_splits_into_alternating_beats` asserting an 8.4s segment
   becomes two segments, first `punch-in`, second `punch-out`, each 4.2s.
   Expected error: `ModuleNotFoundError: No module named 'tools.plan_motion'`
2. Run `bash tests/run.sh py`, confirm it fails for that reason.
3. Implement `tools/plan_motion.py`.
4. Run `bash tests/run.sh py`, confirm pass.
5. Add test: a 5.0s segment stays one segment with `punch-in` 1.0 → 1.04.
6. Add test: a 5.01s segment becomes two beats.
7. Add test: a 30.0s segment becomes six beats, directions alternating from `punch-in`.
8. Add test: a segment already carrying `motion` is returned unchanged and is named in the skipped
   list.
9. Add test: a `kind: "shot"` segment is skipped with the reason `already animated`.
10. Add test: an empty segment list writes an unchanged plan and exits 0.
11. Add test: `out_s <= in_s` raises naming the segment index.
12. Add test: running twice is a no-op — the second run reports zero changes.
13. Run `bash tests/run.sh`, confirm pass.
14. Commit: `feat(GV-7): automatic motion planning for static shots`

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] lint: none configured in this repo — no linter check applies to this phase
- [ ] unit: `bash tests/run.sh` passes
- [ ] Running the tool twice on the same plan reports zero changes on the second run
- [ ] A segment carrying a hand-written `motion` is never overwritten
- [ ] The report names every skipped segment and why
- [ ] No placeholder/TODO comments in new code

---

### Phase G: wire into the skill, sync docs, bump to 3.5.0

**Estimated time:** 15 minutes

**Files:**
- Modify: `skills/video-post/SKILL.md` (Pass 2 calls `plan_motion.py`; Pass 4.1 calls
  `gen_captions.py` and composites the caption track)
- Modify: `skills/video-explainer/SKILL.md` (the two new compositions exist and how they are
  rendered)
- Modify: `CLAUDE.md` (Architecture table gains `gen_captions.py`, `caption_keywords.py`,
  `plan_motion.py` — required by `tests/consistency/tools-index.sh`)
- Modify: `README.md` (v3.5.0 line, feature bullets, changelog section)
- Modify: `.claude-plugin/plugin.json` (`"version": "3.5.0"`)
- Modify: `tests/consistency/tools-index.sh` (`'"version": "3.5.0"'`)
- Modify: `tests/consistency/plugin-identity.sh` (`want_version="3.5.0"`)

**The wiring, stated so the executor does not have to infer it.**

Pass 2, after the edit plan is authored and before it is rendered:
```bash
python3 tools/plan_motion.py {output_folder}
```

Pass 4.1, alongside the existing SRT path which stays:
```bash
python3 tools/gen_captions.py {output_folder}
python3 tools/gen_subs.py {output_folder}          # unchanged — YouTube still needs the sidecar
```
Then render `KineticCaptions` and any `TitleCard` through the Remotion workspace and composite each
over the master:
```bash
python3 tools/composite.py overlay {master} {shot}.mov --at {at_s} --out-s {out_s} -o {out}
```

**Degradation, to be written into the SKILL's Pass 4 edge-case table:**

| Situation | Behaviour |
|---|---|
| Node or Remotion unavailable | Kinetic track skipped; SRT burn-in still ships the video. Warn, exit 0 |
| Scene has no timing source | Listed in `untimed`, as today. Timings are never invented |
| `brand.json` missing a needed token | Refuse and name the token. No fallback palette |
| Brand contrast below 4.5:1 | Refuse, via the existing `check_contrast()` |
| Old `edit-plan.json` with no `motion` | Renders as today |

**What this phase owes:**
1. *Happy path* — both new passes are documented with runnable commands.
2. *Error paths* — the degradation table above is written, not implied.
3. *Edge cases* — n/a for a docs phase; the behaviour edge cases live in A–F and are tested there.
4. *Tests* — the consistency suite is the test: `tools-index.sh` fails until CLAUDE.md names the
   new tools and both version needles move.
5. *Observability* — the changelog says what changed and why, for whoever reads this in six months.

**Steps:**
1. Write failing test for the 3.5.0 docs-sync gate: change the version needle in
   `tests/consistency/tools-index.sh` to `'"version": "3.5.0"'` and `want_version` in
   `tests/consistency/plugin-identity.sh` to `3.5.0`. The gate now demands a version the repo
   does not carry and names three tools `CLAUDE.md` does not list.
   Expected error: `FAIL plugin.json version is not 3.5.0`
2. Run `bash tests/run.sh consistency`, confirm it fails for that reason and names
   `tools/gen_captions.py`, `tools/caption_keywords.py` and `tools/plan_motion.py` as unlisted.
3. Bump `.claude-plugin/plugin.json` to `3.5.0`.
4. Add the three tools to the `CLAUDE.md` Architecture table.
5. Run `bash tests/run.sh consistency`, confirm pass.
7. Write the Pass 2 and Pass 4.1 wiring into `skills/video-post/SKILL.md`, including the
   degradation table.
8. Write the two new compositions into `skills/video-explainer/SKILL.md`.
9. Update `README.md`: the `**v3.5.0**` line at line 3, the feature bullets, and a
   `## v3.5.0 Changelog` section.
10. Run `bash tests/run.sh`, confirm all three groups pass.
11. Commit: `docs(GV-7): wire kinetic captions and shot motion into the pipeline, 3.5.0`

**Verification:**
- [ ] static: `python3 -m compileall -q tools` passes
- [ ] lint: none configured in this repo — no linter check applies to this phase
- [ ] unit: `bash tests/run.sh` passes — all three groups
- [ ] `grep -c '3\.4\.0' .claude-plugin/plugin.json tests/consistency/*.sh` returns 0 for each
- [ ] `bash tests/consistency/tools-index.sh` exits 0
- [ ] Pass 2 and Pass 4.1 in `skills/video-post/SKILL.md` carry runnable commands, not descriptions
- [ ] No placeholder/TODO comments in new code

---

## Out of scope

- Motion other than zoom (cutaways, B-roll inserts, PIP alternation).
- Changing how `scene-plan.md` decides scene length; this ticket adds motion *within* a shot.
- Replacing or removing `gen_subs.py` / the SRT output.
- Adding a Python linter to this repo — a deliberate character change, not a GV-7 detail.
