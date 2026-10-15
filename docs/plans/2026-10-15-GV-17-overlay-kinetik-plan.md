> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-17.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` block, (b) append a `## Log` line ending with the handoff cursor. Blocking, like a test gate. Never batch updates at the end. Update ONLY this file, never `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. Every path, contract and convention is written here verbatim.

**Ticket:** GV-17
**Ledger:** .gaspol/progress/PROGRESS-GV-17.md
**Spec:** docs/plans/2026-10-15-GV-17-overlay-kinetik-spec.md

## Goal

Replace the gold-serif keyword overlay (v3.10.0) with the reference video's style
(`reference/snapgram.io_uyws7kjkx870.mp4`, main checkout only, untracked): two-tier bold sans
text that is ALWAYS animated (six effects), floating image/video panels and round photo bubbles
that sit BEHIND the speaker's head through an automatic per-frame person mask, line icons, and a
source box. One Remotion composition renders it all. `tools/keyword_cards.py` stays in the repo,
marked superseded, until the new style ships in one real video (user decision 7).

## Architecture Context (from CLAUDE.md and the code)

- Worktree: `/Users/alisadikin/Drive-D/claude-plugin/gaspol-video/.claude/worktrees/GV-17-overlay-kinetik`, branch `GV-17-overlay-kinetik`. Run every command from there.
- Test runner: `bash tests/run.sh` (groups `consistency | py | node`). It is stdlib `unittest` + `node --test` + bash, **no pytest, no npm in the repo, by design** (header of `tests/run.sh`). `detect-stack` printed `unit: pytest`; that is wrong for this repo and is NOT used.
- Python tools import third-party modules only through `tools/_venv.py`: `from tools import _venv; PIL = _venv.require("PIL")`. Missing module → exit 2 naming `tools/setup.sh`. Venv: `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/venv`, Python 3.14.7. `tools/setup.sh` runs `pip install -r requirements.txt` (line 45).
- Test clips: `tests/py/media.py` → `make_clip(path, seconds, fps, size, audio)`, `make_silent_clip(...)`, decorator `requires_ffmpeg`.
- VO words: `vo/vo-manifest.json` → `{"generated_at", "model", "settings", "items": [{id, file, scene, cast, kind, voice_env, fingerprint, chars, duration_s, words:[{text,start_ms,end_ms}]}]}` written by `tools/gen_vo.mjs` (line ~408). Word times are relative to that layer's audio file. Verify the top-level key name (`items` vs another) by reading `tools/gen_captions.py::_read_manifest` callers before coding Phase D.
- Word normalisation to reuse: `tools/gen_captions.py::_align_norm(text)` (strip punctuation, lowercase). Errors there use `CaptionPlanError`; this plan defines its own `OverlayPlanError`.
- Remotion workspace: `templates/remotion/scaffold.mjs <project>` creates `<project>/shots/` and copies EVERY file in `templates/remotion/lib/` into `shots/src/lib/` and every file in `templates/remotion/scripts/` into `shots/scripts/`. Per-scene templates (`Captions.template.tsx`, `TitleCard.template.tsx`) are copied by hand per `skills/video-post/SKILL.md` line ~489; `Overlay.template.tsx` follows the same pattern.
- Remotion rules (header of `templates/remotion/Captions.template.tsx`): frame-based animation only, no React state/lifecycle/timers/unseeded randomness; `interpolate` input ranges strictly increasing; `Easing.bezier` called directly; `compositionConfig.id` PascalCase; colours and fonts only from `brand.json`; pure arithmetic lives in a zero-import `.mjs` in `lib/` unit-tested by `tests/node/*.test.mjs`.
- Brand: `templates/remotion/brand.json` (keys `background, ink, inkSoft, accent, displayFont, bodyFont`), read by `templates/remotion/lib/brand.ts` (`COLORS`, `FONT_DISPLAY`, `FONT_BODY`, `EASINGS`, `SHADOW`, `RADIUS`). `lib/kit.tsx` exports `CLAMP`, `BrandBg`, `useRise`, `ImageRevealShot`.
- QA stills: `shots/scripts/qa-frames.mjs <CompId> --out <dir> name=frame ...`.
- Folder contract (`reference/post-production/10-post-production-pipeline.md` §2.1-2.3): derived files go in `{output_folder}/.tmp/`, plans in `work/`, renders of shots in `shots/out/`. No new top-level folders.
- Files that name the old overlay today: `skills/video-gen/SKILL.md` Rule 25 (line ~106), `skills/video-post/SKILL.md` K.4 (line ~158), `CLAUDE.md` lines 17, 67, 130, 626, `tests/consistency/keyword-text-overlay.sh`.
- Version: `.claude-plugin/plugin.json` `version`; consistency tests may gate on it (`tests/consistency/plugin-identity.sh`) — grep for the old version string before bumping.

## Tech Stack

Python 3.14 stdlib + `mediapipe` (new, venv only, Tasks API `mediapipe.tasks.python.vision.ImageSegmenter`) + ffmpeg; Remotion (already the shot engine, installed per project by `scaffold.mjs`); node built-in test runner.

## Decisions recorded at plan time

- **Static check:** `detect-stack` printed `static: UNKNOWN`, `lint: UNKNOWN`. The repo has no npm and no type checker on purpose. TypeScript is type-checked in Phase G inside the scaffolded workspace with `npx tsc --noEmit` (after `npm install`). Python syntax is checked by `python3 -m py_compile`.
- **Mask model file:** `selfie_segmenter.tflite` lives in `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/models/`, downloaded by `tools/setup.sh` with a pinned sha256, never committed.
- **Mask format:** one 8-bit grayscale PNG per frame, `{output_folder}/.tmp/mask-<scene>/%05d.png` (1-based, matches ffmpeg `image2`), 255 = person. Cache stamp `{output_folder}/.tmp/mask-<scene>/source.json` = `{"clip_sha256", "frames", "fps", "w", "h", "feather_px", "model_sha256"}`.
- **Remotion props:** `tools/overlay_plan.py` writes `shots/src/shots/overlay-<scene>.json` (imported by the template like `brand.json`) and hard-links (fallback copy) media and mask frames into `shots/public/overlay/<scene>/`.

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---------|-------------|----------|---------|--------|
| Cue timing | `vo/vo-manifest.json` words | `overlay_plan.resolve_anchor()` using `gen_captions._align_norm` | Manifest yes, resolver no | Create; refuse on missing anchor |
| Source box text | `work/overlay-plan.json` `source` field, copied from `av-script.md` by Claude when writing the plan | `overlay_plan.py` | No | Create; empty string allowed only when the cue has no source |
| Panel / bubble media | `user:<path>`, `ref:<file>` (`{output_folder}/ref/`), `remotion:<Component>` | `overlay_plan.resolve_src()` | Files yes, resolver no | Create; missing file → refuse, no stand-in |
| Person mask | clip `{output_folder}/clips/scene-NN.mp4` (path from plan) | `tools/person_mask.py` + mediapipe ImageSegmenter | No | Create real integration |
| Mask model | `selfie_segmenter.tflite` (Google mediapipe-models bucket) | `tools/setup.sh` download + sha256 | No | Create |
| Colours, fonts | `shots/src/shots/brand.json` | `lib/brand.ts` `COLORS`, `FONT_*` | Yes | Extend with `highlight`, `scriptFont` |
| Effect maths | — | `templates/remotion/lib/overlayFx.mjs` | No | Create, zero imports |
| Composition | — | `templates/remotion/Overlay.template.tsx` + `lib/overlay-fx.tsx` | No | Create |
| Visual QA | rendered composition | `shots/scripts/qa-frames.mjs` | Yes | Use existing |

## Phases

| Phase | Code deliverable | Design deliverable | Verification |
|-------|------------------|--------------------|--------------|
| A | mediapipe + model in venv | n/a | consistency test + real import |
| B | `person_mask.py` logic (model injected) | n/a | unittest |
| C | `person_mask.py` real model | n/a | real clip run |
| D | `overlay_plan.py` resolver | n/a | unittest |
| E | `lib/overlayFx.mjs` six effects | Spec §"Text animation" table (timings, values) | node test |
| F | `Overlay.template.tsx`, `lib/overlay-fx.tsx`, brand tokens | Spec §"Look" + layer order | consistency test |
| G | real render + evidence | QA stills vs reference frames | tsc + render + look |
| H | docs, rules, version | n/a | full suite |

---

### Phase A: mediapipe and the mask model in the venv

**Estimated time:** 15 minutes

**Files:**
- Modify: `requirements.txt`, `tools/setup.sh`
- Create: `tests/consistency/person-mask-setup.sh`

**Steps:**
1. Write failing test for the setup contract. Expected error: `FAIL requirements.txt lacks mediapipe` (script exits 1). The test checks: `requirements.txt` has a line starting `mediapipe==`; `tools/setup.sh` contains `selfie_segmenter.tflite`, a 64-hex sha256 literal, and `shasum -a 256`; the download target is under `${GASPOL_VIDEO_HOME:-$HOME/.gaspol-video}/models`.
2. Run `bash tests/consistency/person-mask-setup.sh`, confirm it fails for that reason.
3. Pick the mediapipe pin: `mediapipe 1.1.1` was published 2026-10-14 (one day before this plan). Check `pip index versions mediapipe` (venv pip) and pin the newest version at least 14 days old that has a `macosx_11_0_arm64` wheel for py3.14; if none older exists, pin `1.1.1` and record that in `## Keputusan saat jalan`.
4. Download `https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite` once, compute its sha256, write both into `tools/setup.sh` after the pip install: skip when the file exists with the right hash, otherwise `curl -fsSL` to a temp file, verify with `shasum -a 256`, move into place; a hash mismatch exits 1 with `model sha256 mismatch: expected <x> got <y>` and deletes the temp file.
5. Run `bash tools/setup.sh`, then `~/.gaspol-video/venv/bin/python -c "from mediapipe.tasks.python import vision; print(vision.ImageSegmenter)"`.
6. Run the test again, confirm it passes.
7. Commit: `feat(GV-17): mediapipe and selfie segmenter model in the venv`

**Edge/error rungs:** offline download → curl fails, setup exits non-zero naming the URL (no partial file left); wrong hash → refused; re-run → no re-download. Observability: setup prints `model ok <path>` or `model downloaded <path>`.

**Verification:**
- [ ] `bash tests/run.sh consistency` passes
- [ ] venv import of `mediapipe.tasks.python.vision.ImageSegmenter` succeeds
- [ ] second `bash tools/setup.sh` run prints `model ok` and downloads nothing
- [ ] No placeholder/TODO in changed files

---

### Phase B: `tools/person_mask.py` logic with an injected segmenter

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/person_mask.py`, `tests/py/test_person_mask.py`

**Contract:**
```
python3 tools/person_mask.py <output_folder> <scene> <clip.mp4> [--feather 4] [--max-miss 0.10] [--force]
exit 0 -> masks written or cache hit; prints "mask <scene>: <frames> frames, <miss> without person (cached|written)"
exit 1 -> refused: no person in more than max-miss of frames; prints the first 20 frame numbers
exit 2 -> missing venv module / model (via _venv.require), names tools/setup.sh
```
Functions (module level, testable): `clip_sha256(path)`, `read_frames(clip)` (ffmpeg `-f rawvideo -pix_fmt rgb24` pipe, size from ffprobe), `build_masks(frames, segment, feather_px) -> (masks, miss_frames)` where `segment(rgb_array) -> float mask 0..1 or None`, `cache_valid(stamp, clip_sha, model_sha, feather)`, `write_masks(dir, masks)`. A frame is a miss when `segment` returns None or the person area is < 0.5% of the frame. Feather = Gaussian blur of `feather_px` (Pillow `ImageFilter.GaussianBlur`, through `_venv.require("PIL")`).

**Steps:**
1. Write failing test for `build_masks` refusing when more than 10% of frames have no person. Expected error: `ModuleNotFoundError: No module named 'tools.person_mask'`.
2. Run `python3 -m unittest tests.py.test_person_mask -v`, confirm it fails for that reason.
3. Add test cases (all with a fake `segment` callable, clips from `tests/py/media.make_silent_clip`): 0 frames (empty clip) → refused `clip has no frames`; 1 frame with person → ok; exactly 10% misses → ok, 11% → refused with frame list; tiny-area mask counts as miss; cache hit when stamp matches (no `segment` call); cache miss on changed clip bytes, changed feather, changed model hash, missing PNG count; `--force` re-runs; output PNG count == frame count and names `00001.png`…; stamp written last (a crash leaves no valid stamp).
4. Implement `tools/person_mask.py` to pass. Writes into `<output_folder>/.tmp/mask-<scene>/`; refuses an `<output_folder>` that does not exist.
5. Run the tests, confirm all pass.
6. Commit: `feat(GV-17): person_mask.py frame loop, miss threshold, cache`

**Verification:**
- [ ] `bash tests/run.sh py` passes
- [ ] `python3 -m py_compile tools/person_mask.py` passes
- [ ] No placeholder/TODO in new code
- [ ] refusal message lists frame numbers and the miss ratio

---

### Phase C: real model in `person_mask.py`

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/person_mask.py`, `tests/py/test_person_mask.py`

**Steps:**
1. Write failing test `test_real_model_on_reference_clip` (skipped unless the venv has mediapipe AND the model file exists) that runs the CLI on a 2 s cut of a real speaker clip and expects exit 0 and ≥ 95% hit frames. Expected error: `AssertionError` (CLI still uses no real segmenter / `segment` not wired).
2. Make the fixture: `ffmpeg -ss 10 -t 2 -i <main checkout>/reference/snapgram.io_uyws7kjkx870.mp4 -an -vf scale=360:-2 tests/fixtures/speaker-2s.mp4` (~200 KB; committed, it is a short derivative used only as a test fixture — if the user objects to committing third-party footage, STOP and ask for a clip of their own).
3. Run the test, confirm it fails for the expected reason.
4. Wire `segment` to `ImageSegmenter.create_from_options(... output_confidence_masks=True, running_mode=VIDEO)`, `segment_for_video(mp.Image(image_format=SRGB, data=rgb), timestamp_ms)`; person mask = confidence mask 0. Model path = `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/models/selfie_segmenter.tflite`; missing → exit 2 naming `tools/setup.sh`.
5. Run the test, confirm it passes. Run the CLI on the full 99 s reference into the scratchpad, open 3 mask PNGs and the matching frames with Read, and confirm by looking that the hair edge is covered (curly hair is the hard case).
6. Commit: `feat(GV-17): person_mask.py uses mediapipe selfie segmenter`

**Edge/error rungs:** two people in frame → both masked (selfie segmenter is class-agnostic; document, do not fix); speaker leaves frame briefly → counted as miss, refused only over threshold. Observability: per-run line with frames, misses, seconds taken.

**Verification:**
- [ ] `bash tests/run.sh py` passes (real-model test runs, not skipped, on this machine)
- [ ] 3 mask stills looked at; hair edge result written to the Log
- [ ] No placeholder/TODO in new code

---

### Phase D: `tools/overlay_plan.py` resolver

**Estimated time:** 15 minutes (split D1 schema+anchors, D2 media+mask staging if it runs long)

**Files:**
- Create: `tools/overlay_plan.py`, `tests/py/test_overlay_plan.py`

**Input `work/overlay-plan.json`:**
```json
{
  "scenes": [{
    "scene": "03", "clip": "clips/scene-03.mp4", "vo_layer": "s03-host", "vo_offset_s": 0.0,
    "fps": 30, "width": 1080, "height": 1920,
    "cues": [{
      "id": "c1", "words": "bukan cerita soal kebakaran",
      "lead": "bukan cerita soal", "keyword": "kebakaran",
      "fx": 1, "color": "white", "script": false, "icon": "fire",
      "pos": {"anchor": "top", "x": 540, "y": 360}, "layer": "front", "hold_s": 0.3,
      "panels": [{"src": "ref:map-borneo.png", "kind": "image", "x": 80, "y": 220, "w": 920, "h": 620, "layer": "behind"}],
      "bubbles": [{"src": "user:photos/warga.jpg", "label_lead": "Jutaan", "label": "warga biasa", "x": 760, "y": 900, "d": 220}],
      "carousel": [{"src": "ref:fire-2019.jpg", "label": "2019"}],
      "source": "Pantau Gambut, 2026"
    }]
  }]
}
```
Allowed values: `fx` ∈ {1,2,3,4} for the keyword (5 = stroke draw applies to `icon`/arrows automatically; 6 = exit applies to every cue automatically — a plan that sets `fx: 5` or `6` on a keyword is refused); `color` ∈ {white, yellow}; `layer` ∈ {front, behind}; `kind` ∈ {image, video}; `icon` ∈ the names exported by `lib/overlay-fx.tsx` (Phase F) — list them in a constant `ICONS` in `overlay_plan.py` and keep both in sync by a consistency test in Phase F; `src` prefix ∈ {user:, ref:, remotion:}. `fx: 3` requires `keyword` to contain a number (`\d`).

**Resolution:** find `words` (normalised with `gen_captions._align_norm`, split on whitespace) as a contiguous run in the layer's `words`; `in_s = first.start_ms/1000 + vo_offset_s - 0.10`, keyword enter = start of the first keyword token inside the run, `out_s = last.end_ms/1000 + vo_offset_s + hold_s`. First occurrence after the previous cue's run wins (cues are in spoken order). Output frames = `round(s * fps)`.

**Output:** `<output_folder>/shots/src/shots/overlay-<scene>.json` (cues with frames, resolved `public` paths) and media + mask frames staged in `<output_folder>/shots/public/overlay/<scene>/` (`os.link`, fallback `shutil.copy2`).

**CLI:** `python3 tools/overlay_plan.py <output_folder> [--scene 03]`; exit 0 ok, exit 1 refused (all problems listed at once, each naming scene + cue id), exit 2 missing input file.

**Steps:**
1. Write failing test for resolving one anchor phrase to frames. Expected error: `ModuleNotFoundError: No module named 'tools.overlay_plan'`.
2. Run `python3 -m unittest tests.py.test_overlay_plan -v`, confirm it fails for that reason.
3. Add cases: anchor found mid-layer; anchor repeated (picks the one after the previous cue); anchor missing → refused; punctuation/case differences still match; keyword not inside `words` → refused; `vo_offset_s` shifts times; overlapping cues allowed only ≤ 0.1 s (spec §6) else refused; `in_s < 0` clamps to 0; `out_s` past clip duration → refused; unknown `fx`/`color`/`layer`/`icon`/prefix → refused; `fx: 3` without a digit → refused; `user:`/`ref:` file missing → refused (no stand-in); `remotion:` name not a PascalCase identifier → refused; `layer: behind` (cue or panel) without a valid mask stamp for that scene → refused `run tools/person_mask.py first`; empty `cues` → refused; manifest layer id missing → refused; re-run idempotent (same output bytes); staged file count == referenced files + mask frames.
4. Implement to pass.
5. Run tests, confirm all pass.
6. Commit: `feat(GV-17): overlay_plan.py resolves cues from vo words`

**Verification:**
- [ ] `bash tests/run.sh py` passes
- [ ] `python3 -m py_compile tools/overlay_plan.py` passes
- [ ] refusal output lists every problem in one run
- [ ] No placeholder/TODO in new code

---

### Phase E: `templates/remotion/lib/overlayFx.mjs` — the six effects as pure maths

**Estimated time:** 15 minutes

**Files:**
- Create: `templates/remotion/lib/overlayFx.mjs`, `tests/node/overlay-fx.test.mjs`

**Values (from the reference, frame-measured at 10 fps):**
| fx | Function | Values |
|----|----------|--------|
| 1 blur-to-sharp | `blurIn(f, start, fps)` → `{opacity, blurPx, scale}` | 0.30 s; opacity 0→1, blur 12→0, scale 1.06→1, ease-out |
| 2 glitch slices | `glitch(f, start, fps, seed)` → `[{y0, y1, dx}]` 6 slices | 0.30 s; |dx| ≤ 40 px decaying to 0; seeded (mulberry32) so frame N is identical across processes |
| 3 count-up | `countUp(f, start, fps, text)` → string | 0.60 s ease-out; keeps prefix/suffix and decimals: "1.9%" → "0.0%"…"1.9%", "221" → "0"…"221", "4x" → "0x"…"4x" |
| 4 handwrite | `strokeProgress(f, start, fps, dur=0.5)` → 0..1 | used as SVG `strokeDashoffset` |
| 5 stroke draw | same function, dur 0.4 s, starts 0.1 s before the keyword (decided 2026-10-15, was "before the lead words") | icons, arrows, scribble circles |
| 6 exit | `exitFx(f, end, fps)` → `{opacity, blurPx}` | 0.20 s; opacity 1→0, blur 0→8 |
| lead words | `leadIn(f, start, fps)` → `{opacity, dy}` | 0.25 s; dy 8→0 |
| panels/bubbles | `springIn(f, start, fps)` → `{opacity, scale}`; `drift(f, seed)` → `{dx, dy}` | scale 0.9→1 spring; drift ±6 px, period ~4 s |
| carousel | `carouselX(f, start, fps, cardW, gap, n)` | slides left 1 card per 0.8 s |
| envelope | `cueVisible(f, inF, outF)` and `cueStyle(cue, f, fps)` | `cueStyle` ALWAYS composes an enter fx and `exitFx`; there is no branch that returns a constant style for the cue's whole life |

**Steps:**
1. Write failing test for `blurIn` at start / mid / end frames. Expected error: `ERR_MODULE_NOT_FOUND` for `overlayFx.mjs`.
2. Run `node --test tests/node/overlay-fx.test.mjs`, confirm it fails for that reason.
3. Add cases: every function at f < start, f = start, f = end, f > end (clamped, no NaN); `glitch` deterministic for the same seed and different for another seed, dx = 0 after 0.30 s; `countUp` for "1.9%", "221", "4x", "1%", "Rp 2,5 T" (comma decimal kept), a string without a digit throws; `strokeProgress` monotonic; `cueStyle` for every fx returns different values at enter-mid vs hold vs exit-mid (the "never static" guarantee); fps 24/25/30/60; zero-length cue (inF == outF) throws.
4. Implement with zero imports (same rule as `lib/captionPages.mjs`).
5. Run `bash tests/run.sh node`, confirm all pass.
6. Commit: `feat(GV-17): overlayFx.mjs effect maths`

**Verification:**
- [ ] `bash tests/run.sh node` passes
- [ ] `overlayFx.mjs` has no `import` line
- [ ] No placeholder/TODO in new code

---

### Phase F: `Overlay.template.tsx`, `lib/overlay-fx.tsx`, brand tokens

**Estimated time:** 15 minutes

**Files:**
- Create: `templates/remotion/Overlay.template.tsx`, `templates/remotion/lib/overlay-fx.tsx`, `tests/consistency/overlay-template-contract.sh`
- Modify: `templates/remotion/brand.json` (add `"highlight": "#F5E625"`, `"scriptFont": "'Caveat', cursive"` — placeholders like the rest, replaced per project), `templates/remotion/lib/brand.ts` (expose `COLORS.highlight`, `FONT_SCRIPT`), `tests/node/scaffold.test.mjs` (expect `src/lib/overlay-fx.tsx`, `src/lib/overlayFx.mjs`)

**Template contract:** `compositionConfig.id = "KineticOverlay"`; imports `./overlay-<scene>.json` (the executor edits one constant `SCENE` per render, like `Captions.template.tsx`); layer order in JSX, bottom → top, each with a comment marker exactly `{/* L1 clip */}`, `{/* L2 behind */}`, `{/* L3 person */}`, `{/* L4 front */}`, `{/* L5 source */}`:
L1 `<OffthreadVideo src={staticFile(clip)}>`; L2 panels/bubbles/carousel and cues with `layer: behind`; L3 the same clip again with CSS `mask-image: url(staticFile(mask/%05d.png for this frame))` (mask frame = `useCurrentFrame()+1`, zero-padded 5); L4 text, icons, `layer: front` panels; L5 source box (bottom-left, 22 px body font, `rgba(0,0,0,0.55)` background, radius 8). Text: lead in `FONT_BODY` ~40 px `COLORS.ink`; keyword `FONT_DISPLAY` weight 800 ~120 px, `COLORS.highlight` when `color: yellow`, `FONT_SCRIPT` when `script: true`; shadow `0 4px 18px rgba(0,0,0,0.45)`; NO background box behind text. `overlay-fx.tsx` exports `ICONS` (fire, gavel, chart, cloud, question, arrow, circle) as stroke-only SVG paths drawn with fx 5, plus `<CueText>`, `<Panel>`, `<Bubble>`, `<Carousel>`, `<SourceBox>` — every one takes its style from `overlayFx.mjs`.

**Steps:**
1. Write failing test `tests/consistency/overlay-template-contract.sh`. Expected error: `FAIL templates/remotion/Overlay.template.tsx missing`. Checks: file exists; the five layer markers appear in order L1<L2<L3<L4<L5 (line numbers); no `useState|useEffect|setTimeout|Math.random`; `KineticOverlay` id; no hex colour literal outside `brand.json` (grep `#[0-9a-fA-F]{6}` in the two `.tsx` files → fail); `ICONS` names in `overlay-fx.tsx` equal `ICONS` in `tools/overlay_plan.py`; `brand.json` has `highlight` and `scriptFont`.
2. Run it, confirm it fails for that reason.
3. Implement the three template files and the brand changes.
4. Run `bash tests/run.sh`, confirm all pass (scaffold node test now expects the two new lib files).
5. Commit: `feat(GV-17): KineticOverlay template with person layer`

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] No placeholder/TODO in new code
- [ ] static: TypeScript checked in Phase G (repo has no tsc)

---

### Phase G: real render and evidence

**Estimated time:** 15 minutes active (npm install and render run in the background)

**Files:**
- Create: `docs/evals/overlay-kinetik-run.md`

**Steps:**
1. Write failing test: `tests/consistency/overlay-evidence.sh` requires `docs/evals/overlay-kinetik-run.md` to exist and to name at least one still per fx 1–5, one `behind` panel, one bubble, one carousel, one source box. Expected error: `FAIL docs/evals/overlay-kinetik-run.md missing`.
2. Run it, confirm it fails.
3. Ask the user (AskUserQuestion) which real project and scene to use: a real speaker clip with a real `vo/vo-manifest.json`. If none fits, ask permission to use the reference clip with a manifest built from AssemblyAI words (`tools/gen_subs.py transcribe_assemblyai`). Never hand-type word times.
4. Scaffold (`node templates/remotion/scaffold.mjs <project>`), copy the new lib/template files if the workspace already existed, `npm install`, run `tools/person_mask.py`, write `work/overlay-plan.json` with ≥ 6 cues covering fx 1–4, a yellow number, a script word, an icon, a behind panel (image), a video panel, a bubble, a carousel, a source box; run `tools/overlay_plan.py`.
5. `cd <project>/shots && npx tsc --noEmit`; fix type errors in the template (and back-port to `templates/remotion/`).
6. Render `KineticOverlay`; take QA stills with `scripts/qa-frames.mjs` at enter-mid, hold and exit-mid of every cue. Open them with Read. Check against the reference frames: text animates (stills differ across the three points), panel is cut by the head (person in front), text never covers face or mouth, source box legible.
7. Write `docs/evals/overlay-kinetik-run.md` (project, commands, timings, still paths, what failed and was fixed). Run the evidence test, confirm it passes.
8. Commit: `test(GV-17): real KineticOverlay render evidence`

**Verification:**
- [ ] `npx tsc --noEmit` in the scaffolded workspace passes
- [ ] render exit 0; QA stills looked at, findings written in the eval doc
- [ ] `bash tests/run.sh` passes
- [ ] No placeholder data: word times came from a real manifest or ASR

---

### Phase H: docs, rules, version

**Estimated time:** 15 minutes

**Files:**
- Modify: `reference/post-production/19-keyword-text-overlay.md` (rewrite: look, six effects with values, five layers, mask rules, placement off face/mouth, plan schema, the red flash section kept and pointed at the automatic mask), `skills/video-gen/SKILL.md` Rule 25 (new text: `(v3.11.0) Kinetic text overlay`, `tools/person_mask.py` → `tools/overlay_plan.py` → `KineticOverlay`), `skills/video-post/SKILL.md` K.4 (same pointer), `tools/keyword_cards.py` (docstring first line: `SUPERSEDED by GV-17 (KineticOverlay); kept until the new style ships in one real video.`), `tests/consistency/keyword-text-overlay.sh` (assert the new Rule 25 string, doc 19 names all six effects and `KineticOverlay`, doc 19 has no `gold serif`, keyword_cards header says SUPERSEDED), `CLAUDE.md` (tool table rows for `person_mask.py`, `overlay_plan.py`, `Overlay.template.tsx`; row 67 marks keyword_cards superseded; row 130 new doc summary; line 17 tool count 29 → 31 and venv tool list; v3.11.0 changelog; Debugging rows for `person_mask` exit 1 and `overlay_plan` refusal), `.claude-plugin/plugin.json` version `3.11.0` plus every test that gates on the version string.

**Steps:**
1. Write failing test: update `tests/consistency/keyword-text-overlay.sh` first. Expected error: `FAIL video-gen Rule 25 missing` (new string not there yet).
2. Run it, confirm it fails.
3. Edit the docs and version.
4. Run `bash tests/run.sh`, confirm all pass.
5. `graphify update .`
6. Commit: `docs(GV-17): v3.11.0 kinetic overlay replaces gold-serif style`

**Verification:**
- [ ] `bash tests/run.sh` passes (all three groups)
- [ ] `rtk proxy grep -rn "gold serif" skills reference` returns only historical changelog lines
- [ ] No placeholder/TODO in changed files

---

## Out of scope

- Deleting `tools/keyword_cards.py` (later ticket, after one real video ships with the new style).
- Auto-choosing which spoken words become cues.
- A built-in animated map component (a project writes its own `remotion:<Component>` or uses a video panel).
- Two-person scenes needing per-person masks.
