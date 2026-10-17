> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-24.md` (created by `gaspol-plan` at plan-write time). After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` block, (b) append a `## Log` line ending with the handoff cursor. This is **blocking**, like a test gate: no next phase until both are written. **Never batch all updates at the end.** Update ONLY this file — never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. It must be executable by an agent with **no other context**. Every file path, contract, config key, and convention it needs is written here verbatim.

**Ticket:** GV-24
**Ledger:** .gaspol/progress/PROGRESS-GV-24.md
**Spec:** docs/plans/2026-10-17-GV-24-surface-insert-spec.md

## Goal

Make two composites stop failing: (1) an app panel inserted onto a phone/monitor screen in a clip,
(2) a logo/text inserted onto clothing so it reads as **embroidery**. Today the panel wobbles,
overhangs, covers fingers and looks pasted; the embroidery floats over folds, looks printed, and
lands on skin or over hands. The fix: learned models for tracking and masks (TAPNext++ point
tracking, SAM 2.1 video masks) plus deterministic numpy/cv2 geometry and rendering, as two new
`vidkit` commands: `screen-insert` and `embroider`. Every failure that makes a composite wrong
refuses with exit 2 and a named reason; nothing degrades silently to the old tools.

## Architecture Context (from CLAUDE.md)

- Repo: `gaspol-video` Claude Code plugin. Work happens in worktree
  `.claude/worktrees/gv-24-surface`, branch `GV-24-surface`. All paths below are relative to it.
- **Tool-first rule:** reusable code goes in `tools/vidkit/` (Python) with a test; each new tool
  is registered in `tools/registry.json` (entry under `"tools"` + a route under `"routes"`), then
  `python3 tools/registry_build.py render` regenerates the table in `docs/tool-routing.md`. Never
  edit that table by hand. Gate: `python3 tools/registry_build.py validate --coverage` and
  `python3 tools/registry_build.py render --check`.
- Registry tool entry shape (copy exactly):
  ```json
  {"id": "tools/vidkit/<name>.py", "purpose": "...", "tasks": ["..."], "phase": "shared",
   "replaces": [], "distinct_because": "", "internal_reason": ""}
  ```
  Route shape: `{"task": "...", "use": "`python3 -m tools.vidkit <cmd> ...`", "tools": ["tools/vidkit/<name>.py"]}`.
  A `|` inside a route cell must be written `\|`.
- Existing tools this plan touches or reuses:
  - `tools/vidkit/bond.py` — screen-PRINT (sablon) onto cloth. **Unchanged.** Embroidery is a new,
    separate module. Its `_deps()` lazy-import pattern (cv2/numpy imported inside functions, a
    `RuntimeError` naming `tools/setup.sh` when missing) is the pattern to copy.
  - `tools/track_screen.py` — brightness flood-fill corner finder. **Unchanged**; may be used by the
    user to get seed corners.
  - `tools/vidkit/sheet.py` — contact sheets; reuse for QA sheets.
  - `tools/vidkit/ff.py` — the only ffprobe owner (`ff.probe`). Never call `ffprobe` directly in
    new code (registry ffprobe ratchet blocks it).
  - `tools/vidkit/__main__.py` — the `python3 -m tools.vidkit` CLI; new subcommands are added here
    the same way `bond` is.
  - `tools/_venv.py` — `venv_python()` returns `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/venv/bin/python`;
    `require(module)` imports or re-execs into that venv, raising `DependencyMissing("missing <m>: run tools/setup.sh")`.
  - `tools/setup.sh` — builds the shared venv and downloads models with a **pinned sha256**
    (pattern: download to a temp file in `$MODEL_DIR`, compare `shasum -a 256`, `mv` on match,
    delete and exit 1 on mismatch). Copy that pattern for every new weight file.
- Test runner: `bash tests/run.sh` (groups `consistency` = `tests/consistency/*.sh`, `py` =
  `python3 -m unittest` over `tests/py`, `node` = `node --test`). **Not pytest**, although
  `detect-stack` prints `unit: pytest` — that is wrong for this repo (same decision as GV-23).
- System `python3` has **no numpy/cv2/torch**. Tests that need them use
  `unittest.skipUnless(...)` so `bash tests/run.sh` stays runnable everywhere — therefore every
  phase that adds such tests ALSO runs them under the venv interpreter and checks the run reports
  **no skips** (a skipped test is not a pass).
- Static check (GV-23 owner decision, reused): `detect-stack` prints `static: UNKNOWN`; no linter
  is configured. Every phase that adds or changes a `.py` file runs
  `python3 -m py_compile <changed .py files>`, which must exit 0.

## Tech Stack

- **ML venv (new):** `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/venv-ml`, always separate from the
  shared `venv` (keeps 2–3 GB of torch out of it, and lets the Python version differ: the shared
  venv is Python 3.14; torch may need 3.12). Built by `bash tools/setup.sh --ml`.
  Below, `ML_PY` means `${GASPOL_VIDEO_HOME:-$HOME/.gaspol-video}/venv-ml/bin/python`.
- **TAPNext++** — `google-deepmind/tapnet`, PyTorch checkpoint `tapnextpp_ckpt.pt` (256×256) from
  `https://storage.googleapis.com/dm-tapnet/tapnextpp/tapnextpp_ckpt.pt`. Point tracking with
  per-point visibility. **CoTracker3 is forbidden** (CC-BY-NC 4.0, not usable for client work).
- **SAM 2.1** — `facebookresearch/sam2`, checkpoint `sam2.1_hiera_small.pt` from
  `https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt`, config
  `configs/sam2.1/sam2.1_hiera_s.yaml`. Video API: `build_sam2_video_predictor(cfg, ckpt, device)`,
  `init_state(video_path=<dir of JPEGs named 00000.jpg…>)`,
  `add_new_points_or_box(state, frame_idx, obj_id, points, labels)`,
  `propagate_in_video(state)`. **SAM 3 is forbidden** (hard `triton` = CUDA-only dependency).
- numpy + OpenCV (`cv2.findHomography` RANSAC, `cv2.warpPerspective`, `cv2.remap`) in `venv-ml`.
- ffmpeg for decode/encode (same rawvideo pipe pattern as `bond.py`).

## Contracts (verbatim — every phase codes to these)

```python
# tools/vidkit/ml.py
class MLMissing(RuntimeError): ...        # message: "missing <what>: run tools/setup.sh --ml"
def ml_python() -> Path                   # ${GASPOL_VIDEO_HOME:-~/.gaspol-video}/venv-ml/bin/python
def models_dir() -> Path                  # ${GASPOL_VIDEO_HOME:-~/.gaspol-video}/models
def device() -> str                       # "mps" if torch.backends.mps.is_available() else "cpu";
                                          # env GASPOL_ML_DEVICE=cpu|mps overrides
def weight(name: str) -> Path             # models_dir()/name; MLMissing if absent or sha256 != WEIGHTS[name]
WEIGHTS: dict[str, str]                   # file name -> sha256, filled in Phase B from Phase A's measured hashes

# tools/vidkit/pointtrack.py
def track(frames, queries) -> tuple[tracks, visible]
#   frames : uint8 ndarray [T, H, W, 3] RGB, any H/W (resized internally to the model size,
#            results mapped back to input pixels)
#   queries: float32 ndarray [N, 3] rows (t, x, y) in input pixels, 0 <= t < T
#   tracks : float32 ndarray [T, N, 2] (x, y) in input pixels
#   visible: bool ndarray [T, N]
#   ValueError on T == 0, N == 0, a query outside the frame, or t out of range.

# tools/vidkit/segment.py
def masks(frames, frame_idx, points=None, labels=None, box=None) -> ndarray
#   frames: uint8 [T, H, W, 3] RGB; points: [[x, y], ...]; labels: [1|0, ...] (1 = include);
#   box: [x0, y0, x1, y1]. At least one of points/box. Returns bool [T, H, W].
#   ValueError on no prompt, mismatched points/labels, prompt outside the frame.

# tools/vidkit/screen.py
class OneEuro: __init__(self, fps, min_cutoff=1.0, beta=0.05, d_cutoff=1.0); __call__(self, x: ndarray) -> ndarray
def corners_green(frame_bgr, hue=(40, 85), sat_min=80, val_min=60) -> ndarray[4, 2] | None
#   clockwise from top-left; each side fitted by RANSAC line over its edge points, corners = line
#   intersections, so an occluding finger on one edge does not move the corner. None if no key.
def corners_track(frames, init_corners, ring=24) -> tuple[ndarray[T, 4, 2], ndarray[T] (inlier ratio)]
#   queries a ring of points around + inside init_corners at frame 0, pointtrack.track(), then per
#   frame cv2.findHomography(src, dst, cv2.RANSAC, 3.0) on visible points and maps the corners.
def composite(frame, panel, corners, occluder=None, prev_corners=None, glass=0.08) -> ndarray
#   warpPerspective panel into corners; colour/gamma match to the clip; motion blur along the
#   corner velocity (prev_corners); glass = opacity of the original screen's high-frequency
#   residual kept on top; occluder (bool mask) pixels restored from the original frame EXACTLY.
def insert(clip, panel, out, mode, seed=None, corners=None, occluder_point=None, qa_dir=None) -> dict
#   returns {"frames", "mode", "min_inlier", "max_jump_px", "lost_frames"}.
class Refused(RuntimeError): ...   # CLI maps to exit 2

# tools/vidkit/embroider.py
def thread_maps(rgba, stitch_px=3.0, angle_deg=None) -> tuple[height, normal, albedo]
#   height float32 [h, w] in 0..1 (0 outside alpha, peaks along stroke centre, satin ridges every
#   stitch_px); normal float32 [h, w, 3] unit vectors, z > 0; albedo float32 [h, w, 3] 0..1.
def grid_warp(layer, src_pts, dst_pts, visible, size) -> ndarray
#   thin-plate / piecewise-affine warp of the RGBA layer from src_pts (frame 0) to dst_pts
#   (frame t), using only visible points; returns RGBA [H, W, 4].
def shade(frame_bgr, albedo, normal, height, alpha) -> ndarray
#   light from the clip's local cloth luminance; lambert + small specular on ridges; edge AO.
def embroider(clip, logo, out, at, width, rot=0.0, hand_points=None, qa_dir=None) -> dict
#   returns {"frames", "lost_frames", "shirt_area_ratio"}; Refused on failure.
```

**Refusal rules (exit 2, stderr starts with `refused: `):**

| Condition | Message |
|---|---|
| > 30% of tracked points invisible for ≥ 0.5 s consecutively | `refused: track lost on frames <a>-<b> (<p>% points hidden)` |
| any corner moves > 8% of the screen diagonal between two frames after smoothing | `refused: corner jump <px> px at frame <t>` |
| `track` mode homography inlier ratio < 0.5 on any frame | `refused: homography unstable at frame <t> (inliers <r>)` |
| `green` mode finds no key on > 5% of frames | `refused: green key missing on <n> frames` |
| shirt mask area < 1.5 × design area at frame 0 | `refused: shirt area too small for design (<ratio>)` |
| design centre `at` not inside the shirt mask at frame 0 | `refused: --at is not on the shirt` |
| torch / tapnet / sam2 / a weight missing or wrong hash | `refused: missing <what>: run tools/setup.sh --ml` |

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Panel content | `gen_app_screen.py` PNG or a Remotion mp4 | file path argument | Yes | Use existing |
| Seed corners (track mode) | user `--corners` or `tools/track_screen.py` JSON first key | file/argument | Yes | Use existing |
| Point tracks | TAPNext++ checkpoint | `vidkit.pointtrack.track` | No | Create, real model |
| Masks (screen occluder, shirt, hands) | SAM 2.1 checkpoint | `vidkit.segment.masks` | No | Create, real model |
| Device / weights | `${GASPOL_VIDEO_HOME}/venv-ml`, `/models` | `vidkit.ml` | No | Create |
| Probe/metadata | `ff.probe` | `tools/vidkit/ff.py` | Yes | Use existing |
| QA sheets | `vidkit.sheet` | `tools/vidkit/sheet.py` | Yes | Use existing |
| Registry/routing | `tools/registry.json` | `registry_build.py render` | Yes | Add entries |
| Real failing clips | owner-supplied paths | — | **Pending** | Ask before Phase L; never substitute synthetic clips for the Phase L proof |

## Phases

| Phase | Deliverable | Est. |
|---|---|---|
| A | Probe torch + TAPNext++ + SAM 2.1 on this Mac; `docs/evals/ml-probe.md` | 15 |
| B | `setup.sh --ml`, `requirements-ml.txt`, `vidkit/ml.py` | 15 |
| C | `vidkit/pointtrack.py` | 15 |
| D | `vidkit/segment.py` | 15 |
| E | `screen.corners_green` + `OneEuro` | 15 |
| F | `screen.corners_track` + refusals | 15 |
| G | `screen.composite` + `insert` + CLI `screen-insert` | 15 |
| H | `embroider.thread_maps` | 15 |
| I | `embroider.grid_warp` + `shade` | 15 |
| J | `embroider.embroider` + CLI `embroider` | 15 |
| K | green-screen prompt rule, validator check, registry, docs, CLAUDE.md | 15 |
| L | Proof on owner's real clips, review, release v3.21.0 | 15 |

---

### Phase A: ML probe on this Mac

**Estimated time:** 15 minutes

**Files:**
- Create: `docs/evals/ml-probe.md`
- Test: `tests/consistency/ml-probe-evidence.sh`

**Steps:**
1. Write failing test for the probe evidence: `tests/consistency/ml-probe-evidence.sh` greps `docs/evals/ml-probe.md` for the lines `python:`, `torch:`, `mps_available:`, `tapnextpp_sha256:`, `sam2_sha256:`, `tapnext_fps:`, `sam2_fps:`, `licence_tapnet:`, `licence_sam2:` each followed by a non-empty value. Expected error: `ml-probe.md missing` (exit 1).
2. Run `bash tests/consistency/ml-probe-evidence.sh`, confirm it fails for that reason.
3. Create a scratch venv in the session scratchpad (NOT in the repo): try `python3.14 -m venv`, `pip install torch torchvision`; if no wheel, retry with `python3.12` (install via `brew install python@3.12` only after asking the owner). Record which Python worked.
4. Install `git+https://github.com/google-deepmind/tapnet.git` (torch extra) and `git+https://github.com/facebookresearch/sam2.git`; download both checkpoints (URLs in Tech Stack); record `shasum -a 256` of each.
5. Read each repo's LICENSE and the weight licence statement; record verbatim. If either weight is not commercial-use, **STOP and ask the owner**.
6. Run TAPNext++ on a 48-frame 512×512 synthetic clip (textured plane with a known translation) with 64 query points, on `mps` then `cpu`; record frames/s and max position error. If MPS errors, record the error line and use `cpu`.
7. Run SAM 2.1 small on the same clip with one point prompt; record frames/s and mask IoU against the known plane.
8. Write `docs/evals/ml-probe.md` with all fields from step 1 plus the exact working import lines and call signatures for both models (Phase C/D code from them).
9. Run the test, confirm it passes. Commit: `docs(GV-24): ML probe on Apple M5 Pro`.

**Edge cases:** no torch wheel for any local Python → STOP; MPS unavailable → cpu recorded, not a failure; checkpoint download fails or hash changes between two downloads → STOP.
**Observability:** the eval doc is the record.

**Verification:**
- [ ] static: UNKNOWN in detect-stack — no `.py` added in this phase (n/a, reason: docs only)
- [ ] `bash tests/consistency/ml-probe-evidence.sh` passes
- [ ] `bash tests/run.sh` passes
- [ ] Both licences recorded verbatim and commercial use allowed (else STOP)
- [ ] Measured numbers come from a real run on this machine, not estimates

### Phase B: ML venv, weights, `vidkit/ml.py`

**Estimated time:** 15 minutes

**Files:**
- Create: `requirements-ml.txt` (exact versions from `docs/evals/ml-probe.md`)
- Modify: `tools/setup.sh` (new `--ml` flag)
- Create: `tools/vidkit/ml.py`
- Test: `tests/py/test_ml.py`, extend `tests/py/test_setup_sh.py`

**Steps:**
1. Write failing test for `ml.weight("x.pt")` raising `MLMissing` whose message contains `run tools/setup.sh --ml` when the file is absent, and when present with the wrong sha256 (temp `GASPOL_VIDEO_HOME`). Expected error: `ModuleNotFoundError: No module named 'tools.vidkit.ml'`.
2. Run `python3 -m unittest tests.py.test_ml`, confirm it fails for that reason.
3. Implement `ml.py` per Contracts. `ml.py` itself imports only stdlib at module level (`device()` imports torch lazily and raises `MLMissing("missing torch: ...")`). `WEIGHTS` holds the two hashes from the probe.
4. Add tests: `device()` honours `GASPOL_ML_DEVICE=cpu`; `ml_python()` path under a temp home; correct hash passes.
5. Extend `tools/setup.sh`: with `--ml`, build `venv-ml` with the Python the probe recorded (`PYTHON_ML` env overrides), `pip install -r requirements-ml.txt`, download both checkpoints with the pinned-sha256 pattern already used for the selfie model. Without `--ml`, behaviour is byte-identical to today. Add a `test_setup_sh.py` case asserting `--ml` is parsed and the two URLs + hashes are present in the script.
6. Run `bash tools/setup.sh --ml` for real; confirm `ML_PY -c "import torch, tapnet, sam2"` exits 0.
7. Run tests, py_compile, commit: `feat(GV-24): ml venv and weight guard`.

**Edge cases:** empty file, wrong hash, missing dir, `GASPOL_ML_DEVICE` invalid value → `ValueError`.
**Observability:** `MLMissing` message names exactly what is missing and the command.

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/ml.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `"$ML_PY" -c "import torch, tapnet, sam2"` exits 0
- [ ] `bash tools/setup.sh` without `--ml` still succeeds unchanged
- [ ] No placeholder/TODO comments in new code

### Phase C: `vidkit/pointtrack.py`

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/pointtrack.py`
- Test: `tests/py/test_pointtrack.py`

**Steps:**
1. Write failing test for synthetic 32-frame 320×240 RGB clip of a textured plane translating +3 px/frame in x; 16 queries at t=0; `track()` returns tracks within 1.5 px of truth on ≥ 90% of (t, n) and `visible` all True. Expected error: `ModuleNotFoundError: No module named 'tools.vidkit.pointtrack'`. Test class decorated `skipUnless(ML available)`.
2. Run `"$ML_PY" -m unittest tests.py.test_pointtrack`, confirm it fails for that reason.
3. Implement per Contracts using the exact calls recorded in `docs/evals/ml-probe.md`; resize to the model size, map back to input pixels; weights via `ml.weight`, device via `ml.device()`.
4. Add tests: occlusion — a grey box covers half the points for frames 10–14 → those points `visible=False` there and back within 2 px by frame 18; input validation (`T==0`, `N==0`, query outside frame, `t>=T`) raises `ValueError` (these run without ML).
5. Run under `ML_PY` (no skips) and `bash tests/run.sh`; py_compile; commit: `feat(GV-24): TAPNext++ point tracking`.

**Edge cases:** T=1, N=1, non-multiple-of-8 sizes, query at the exact border.
**Observability:** debug log of device and fps to stderr when `GASPOL_ML_DEBUG=1`.

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/pointtrack.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `"$ML_PY" -m unittest tests.py.test_pointtrack -v` passes with 0 skipped
- [ ] Uses the real TAPNext++ checkpoint, no mocked inference
- [ ] No placeholder/TODO comments in new code

### Phase D: `vidkit/segment.py`

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/segment.py`
- Test: `tests/py/test_segment.py`

**Steps:**
1. Write failing test for 24-frame clip, a red disc moving across a noisy background; one point prompt on the disc at frame 0 → mask IoU ≥ 0.9 vs the known disc on every frame. Expected error: `ModuleNotFoundError: No module named 'tools.vidkit.segment'`.
2. Run under `ML_PY`, confirm it fails for that reason.
3. Implement per Contracts: write frames as `00000.jpg…` into a `tempfile.TemporaryDirectory`, `init_state`, add prompt, `propagate_in_video`, threshold logits > 0, return bool `[T,H,W]`. Prompt at `frame_idx > 0` must still cover frames before it (run propagation in reverse as SAM 2 supports).
4. Add tests: box prompt; negative point (label 0) excludes a second disc; `ValueError` cases (no prompt, length mismatch, outside frame) run without ML.
5. Run under `ML_PY` (no skips) and `bash tests/run.sh`; py_compile; commit: `feat(GV-24): SAM 2.1 video masks`.

**Edge cases:** object leaves frame (mask empty, no crash), prompt on last frame, T=1.
**Observability:** `GASPOL_ML_DEBUG=1` prints device, fps, mask area per frame summary.

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/segment.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `"$ML_PY" -m unittest tests.py.test_segment -v` passes with 0 skipped
- [ ] Uses the real SAM 2.1 checkpoint
- [ ] No placeholder/TODO comments in new code

### Phase E: screen corners (green) + One-Euro smoothing

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/screen.py`
- Test: `tests/py/test_screen.py`

**Steps:**
1. Write failing test for 640×360 frame, grey background, pure green (`#00FF00`) quad with corners `[[200,80],[450,95],[440,280],[190,260]]`, plus a skin-coloured "finger" rectangle crossing the bottom edge → `corners_green` returns each corner within 2 px. Expected error: `ModuleNotFoundError: No module named 'tools.vidkit.screen'`.
2. Run under the shared venv python, confirm it fails for that reason.
3. Implement `corners_green` per Contracts (HSV key → largest component → contour edge points split into four sides by the min-area-rect orientation → RANSAC line per side → intersections, clockwise from top-left).
4. Add tests: no green → `None`; green with JPEG noise and a 1 px anti-aliased edge → within 2 px; finger covering one corner region → still within 3 px.
5. Write failing test for `OneEuro`: static point + ±2 px noise → output std reduced ≥ 3×; constant velocity 10 px/frame → error < 2 px after 5 frames. Implement; run.
6. Run under the shared venv (no skips) and `bash tests/run.sh`; py_compile; commit: `feat(GV-24): green-key screen corners and one-euro filter`.

**Edge cases:** quad touching the frame border, two green blobs (largest wins), tiny quad (< 40 px wide → `None`).
**Observability:** n/a beyond return values — pure function (reason: no I/O).

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/screen.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `"$HOME/.gaspol-video/venv/bin/python" -m unittest tests.py.test_screen -v` passes with 0 skipped
- [ ] No placeholder/TODO comments in new code

### Phase F: screen corners (track) + refusals

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/vidkit/screen.py`
- Test: `tests/py/test_screen.py`

**Steps:**
1. Write failing test for 40-frame synthetic clip, a textured screen + textured bezel warped by a known homography sequence (slow pan + 3° roll) → `corners_track` within 3 px of truth on every frame. Expected error: `AttributeError: module 'tools.vidkit.screen' has no attribute 'corners_track'`.
2. Run under `ML_PY`, confirm it fails for that reason.
3. Implement per Contracts (ring of points on and around the quad, `pointtrack.track`, per-frame RANSAC homography, One-Euro on the 8 corner coordinates).
4. Implement `Refused` and the refusal checks (track lost, corner jump, inlier ratio) as a separate pure function `check_track(corners, inliers, visible, fps, diag)` and test each refusal with hand-built arrays (no ML needed).
5. Run under `ML_PY` (no skips) and `bash tests/run.sh`; py_compile; commit: `feat(GV-24): planar screen tracking with refusals`.

**Edge cases:** hand covering 40% of the screen for 0.3 s (must pass), for 0.6 s with > 30% hidden (must refuse); screen partly leaving the frame.
**Observability:** `insert` returns `min_inlier`, `max_jump_px`, `lost_frames`; refusals name the frames.

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/screen.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `"$ML_PY" -m unittest tests.py.test_screen -v` passes with 0 skipped
- [ ] Every refusal row in the Contracts table has a test
- [ ] No placeholder/TODO comments in new code

### Phase G: screen composite, `insert`, CLI `screen-insert`

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/vidkit/screen.py`, `tools/vidkit/__main__.py`
- Test: `tests/py/test_screen.py`, `tests/py/test_vidkit.py` (CLI parse)

**Steps:**
1. Write failing test for `composite` with an occluder mask → every occluder pixel equals the original frame exactly; pixels inside the quad and outside the occluder differ from the original and correlate ≥ 0.9 with the warped panel. Expected error: `AttributeError: ... no attribute 'composite'`.
2. Run, confirm it fails for that reason.
3. Implement `composite` per Contracts: warp, 1.5 px feathered edge, colour/gamma match (match panel mean luminance to the screen region's 90th percentile luminance), motion blur kernel length = corner displacement from `prev_corners` (0 when None), glass residual = original minus its Gaussian blur (σ 6) × `glass`.
4. Add tests: motion blur reduces horizontal gradient energy when corners move 20 px/frame vs 0; `glass=0` leaves no residual; panel PNG with alpha respected.
5. Implement `insert(clip, panel, out, mode, ...)`: decode via ffmpeg rawvideo, `mode="green"` (occluder = non-green pixels inside the quad) or `mode="track"` (`corners` required; occluder from `segment.masks` with `occluder_point` when given), panel may be PNG or mp4 (looped/held to clip length), write mp4 with the clip's audio copied, QA contact sheet via `vidkit.sheet` when `qa_dir`. Raise `Refused` per the table.
6. Add CLI subcommand `screen-insert <clip> <panel> <out> --mode green|track [--corners x,y,x,y,x,y,x,y] [--occluder x,y] [--qa DIR]`; `Refused` → exit 2 with `refused: ...`; `MLMissing` → exit 2. Test the argument parsing and the exit code mapping.
7. End-to-end test under `ML_PY` on a 2 s synthetic green clip: output exists, duration equal within 1 frame (`ff.probe`), audio stream present.
8. Run all; py_compile; commit: `feat(GV-24): vidkit screen-insert`.

**Edge cases:** panel aspect differs from the quad (fill, no stretch beyond 2%: letterbox with black), clip without audio, panel mp4 longer than clip.
**Observability:** CLI prints the returned dict as one JSON line on success.

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/screen.py tools/vidkit/__main__.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `"$ML_PY" -m unittest tests.py.test_screen -v` passes with 0 skipped
- [ ] Occluder pixels restored exactly (test)
- [ ] No direct `ffprobe` call (registry ratchet)
- [ ] No placeholder/TODO comments in new code

### Phase H: thread texture maps

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/vidkit/embroider.py`
- Test: `tests/py/test_embroider.py`

**Steps:**
1. Write failing test for `thread_maps` on a 200×80 RGBA bar → `height` is 0 where alpha is 0, maximum lies within 2 px of the bar's centre line, `normal[..., 2] > 0` everywhere, and the FFT of a height row inside the bar peaks at period `stitch_px` ± 0.5. Expected error: `ModuleNotFoundError: No module named 'tools.vidkit.embroider'`.
2. Run under the shared venv, confirm it fails for that reason.
3. Implement per Contracts: distance transform of alpha → dome profile; satin ridges = `0.5 + 0.5·cos(2π·u/stitch_px)` along the stitch direction (`angle_deg`, default perpendicular to the local stroke via the distance-transform gradient); normal from Sobel of height; albedo = logo RGB with slight per-ridge brightness variation (± 6%).
4. Add tests: fully transparent input → `ValueError("logo has no opaque pixels")`; non-RGBA → `ValueError`; thin 2 px stroke still has height > 0.
5. Run (no skips) and `bash tests/run.sh`; py_compile; commit: `feat(GV-24): satin thread texture maps`.

**Edge cases:** 1×1 logo, huge logo (> 2000 px wide — downscale first, documented), anti-aliased alpha.
**Observability:** n/a — pure function (reason: no I/O).

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/embroider.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `"$HOME/.gaspol-video/venv/bin/python" -m unittest tests.py.test_embroider -v` passes with 0 skipped
- [ ] No placeholder/TODO comments in new code

### Phase I: cloth grid warp + shading

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/vidkit/embroider.py`
- Test: `tests/py/test_embroider.py`

**Steps:**
1. Write failing test for `grid_warp` with a 7×7 grid displaced by a known smooth field (`dx = 6·sin(y/40)`, `dy = 4·cos(x/50)`) → mean absolute difference to the ground-truth `cv2.remap` result ≤ 1.5 px-equivalent (compare alpha centroids per cell). Expected error: `AttributeError: ... no attribute 'grid_warp'`.
2. Run, confirm it fails for that reason.
3. Implement `grid_warp` (piecewise-affine over a Delaunay triangulation of visible points; points with `visible=False` dropped; fewer than 4 visible → `Refused("track lost ...")`).
4. Write failing test for `shade`: on a frame whose cloth luminance ramps dark→bright, the shaded thread luminance correlates ≥ 0.8 with the cloth luminance; ridge pixels brighter than valley pixels. Implement; run.
5. Run (no skips) and `bash tests/run.sh`; py_compile; commit: `feat(GV-24): cloth mesh warp and thread shading`.

**Edge cases:** all points visible but collinear → `Refused`; dst outside frame (clipped).
**Observability:** n/a — pure functions (reason: no I/O).

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/embroider.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `"$HOME/.gaspol-video/venv/bin/python" -m unittest tests.py.test_embroider -v` passes with 0 skipped
- [ ] No placeholder/TODO comments in new code

### Phase J: `embroider()` + CLI `embroider`

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/vidkit/embroider.py`, `tools/vidkit/__main__.py`
- Test: `tests/py/test_embroider.py`, `tests/py/test_vidkit.py`

**Steps:**
1. Write failing test for synthetic 24-frame clip of a textured "shirt" region that deforms by a known field, plus a "hand" disc crossing it → output pixels outside the shirt mask equal the input exactly; pixels under the hand equal the input exactly; inside the shirt the design is present. Expected error: `AttributeError: ... no attribute 'embroider'`.
2. Run under `ML_PY`, confirm it fails for that reason.
3. Implement `embroider()`: shirt mask = `segment.masks(point=at)`; hand mask = `segment.masks(points=hand_points)` when given, else none; tracking grid = 7×7 points over the design footprint, restricted to shirt-mask pixels, via `pointtrack.track`; per frame `grid_warp` → `shade` → alpha × (shirt ∧ ¬hand); refusals per table; QA sheet when `qa_dir`; audio copied.
4. Add CLI `embroider <clip> <logo.png> <out> --at x,y --width W [--rot DEG] [--hand x,y ...] [--qa DIR]`; exit codes as `screen-insert`. Test parsing and exit mapping.
5. Run under `ML_PY` (no skips) and `bash tests/run.sh`; py_compile; commit: `feat(GV-24): vidkit embroider`.

**Edge cases:** `--at` off the shirt → refuse; design wider than the shirt → refuse; clip without audio.
**Observability:** success prints the returned dict as one JSON line.

**Verification:**
- [ ] static: `python3 -m py_compile tools/vidkit/embroider.py tools/vidkit/__main__.py` passes
- [ ] `bash tests/run.sh` passes
- [ ] `"$ML_PY" -m unittest tests.py.test_embroider -v` passes with 0 skipped
- [ ] Pixels outside shirt and under hand unchanged (test)
- [ ] No placeholder/TODO comments in new code

### Phase K: prompt rule, validator, registry, docs

**Estimated time:** 15 minutes

**Files:**
- Modify: `skills/video-gen/SKILL.md` (new numbered Hard Rule: a screen that will receive an app insert is prompted as `flat solid chroma green screen (#00FF00), no reflections, no content`, and the scene's `Screen Source` row notes `insert: green`)
- Modify: `skills/video-validate/SKILL.md`, `agents/video-prompt-reviewer.md` (next free V-number check: a scene marked `insert: green` whose VEO/Seedance/Kling prompt lacks the green-screen phrase FAILS)
- Modify: `tools/registry.json` (entries for `ml.py`, `pointtrack.py`, `segment.py`, `screen.py`, `embroider.py`; routes "Put an app screen into a phone/monitor in a clip" → `vidkit screen-insert`, "Embroider a logo/text onto clothing" → `vidkit embroider`; update the old screen route to name `screen-insert` first)
- Modify: `docs/vidkit.md`, `CLAUDE.md` (architecture rows, debugging rows for each refusal message, v3.21.0 changelog), `.env.example` unchanged
- Test: `tests/consistency/surface-insert-contract.sh`

**Steps:**
1. Write failing test for the docs contract `tests/consistency/surface-insert-contract.sh`: asserts the video-gen rule phrase, the validator check id in both validator files, both routes in `docs/tool-routing.md`, and each refusal message in CLAUDE.md debugging. Expected error: exit 1 `missing green-screen rule`.
2. Run, confirm it fails for that reason.
3. Make the edits; run `python3 tools/registry_build.py render`.
4. Run `python3 tools/registry_build.py validate --coverage`, `render --check`, `bash tests/run.sh`; commit: `docs(GV-24): green-screen rule, validator check, routes`.

**Edge cases:** n/a — docs (reason: no runtime input).
**Observability:** n/a — docs.

**Verification:**
- [ ] static: no `.py` changed (n/a)
- [ ] `bash tests/run.sh` passes
- [ ] `python3 tools/registry_build.py validate --coverage` and `render --check` pass
- [ ] `docs/tool-routing.md` table was generated, not hand-edited

### Phase L: proof on real clips, review, release

**Estimated time:** 15 minutes

**Files:**
- Create: `docs/evals/surface-insert-run.md`
- Modify: `.claude-plugin/plugin.json` (version 3.21.0), README version line
- Test: `tests/consistency/surface-insert-evidence.sh`

**Steps:**
1. Write failing test for the real-clip evidence `tests/consistency/surface-insert-evidence.sh`: the eval doc lists ≥ 1 real screen clip and ≥ 1 real shirt clip, each with source path, command, returned JSON, QA sheet path and an owner verdict line. Expected error: exit 1 `surface-insert-run.md missing`.
2. Run, confirm it fails.
3. **Ask the owner for the real failing clip paths** (pending since brainstorm). Never substitute synthetic clips here.
4. Run `screen-insert` and `embroider` on them; produce before/after contact sheets; look at them; record honest results including any refusal.
5. Run the final reviewers once for the branch (`silent-failure-hunter`, `security-reviewer` — downloads and subprocess calls), fix findings.
6. Bump version to 3.21.0; run full gates; commit: `feat(GV-24): surface insert proof and release v3.21.0`.

**Edge cases:** a real clip refuses → recorded as a result, not hidden; owner rejects the look → back to the responsible phase.
**Observability:** the eval doc.

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] All `ML_PY` test modules pass with 0 skipped
- [ ] `python3 tools/registry_build.py validate --coverage` and `render --check` pass
- [ ] Owner verdict recorded for each real clip
- [ ] No placeholder/TODO comments in new code

## Out of scope

- CoTracker3, SAM 3, any CUDA path.
- Replacing `vidkit bond` (screen-print stays), changing `track_screen.py` or `quad-screen.tsx`.
- Rendering new paid VEO clips (owner supplies real clips).
