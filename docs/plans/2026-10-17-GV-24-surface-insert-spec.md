**Ticket:** GV-24

# GV-24 — Screen insert and embroidery that stick to the surface

## Design

### Problem

Two composites are the most-rejected artefacts after the clip is rendered:

1. **App on a phone/monitor screen.** Observed failures (all four reported by the owner):
   panel wobbles or floats when camera or hand moves; corners overhang or miss the glass;
   a finger passing in front of the screen is covered by the panel; the panel looks pasted
   (too sharp, too bright, no glass, no motion blur).
2. **Logo/text as embroidery on clothing.** Observed failures: it does not follow the cloth
   (floats over folds); it looks like a flat print/sticker, not raised thread; it lands on
   skin/arm/hair or is drawn over a hand.

Root causes in the current tools:

| Failure | Cause in code |
|---|---|
| Wobble, lag | `tools/track_screen.py` samples every 0.5 s and smooths with an EMA; between samples the panel trails the camera |
| Wrong corners | Corners come from a brightness flood fill; a dark or busy screen, or a finger, breaks the fill |
| Finger covered | No hand/occluder mask anywhere in the screen path |
| Looks pasted | No motion blur, colour match or glass residual |
| Embroidery floats | `tools/vidkit/bond.py` tracks the whole chest as ONE affine (ECC) |
| Looks printed | `bond.py` blends by multiply: flat ink, no thread relief |
| Wrong place / over hand | Fabric mask is "low saturation and bright" — not clothing segmentation |

### Decision (owner-approved 2026-10-17)

Use learned models for tracking and masks, deterministic numpy/cv2 for geometry and look.

| Need | Model | Why this one |
|---|---|---|
| Point tracking (screen corners, cloth grid) | **TAPNext++** (`google-deepmind/tapnet`, PyTorch weights) | Per-frame tracking with occlusion flag and re-detection; reported Apache 2.0 weights. **CoTracker3 rejected: CC-BY-NC 4.0, not usable for client work** |
| Video masks (screen, shirt, hands) | **SAM 2.1** (Meta, Apache 2.0) | Runs on Apple Silicon (MPS/CPU). **SAM 3 rejected: hard `triton` (CUDA-only) dependency** |

Licences are re-checked against the actual weight files in Phase A, not taken from search
snippets.

Clip sources: both. New clips render the screen as solid green (cheap, exact, fingers drop
out by keying); existing / repackaged clips are tracked as they are.

### Components (all in `tools/vidkit/`, per the tool-first rule)

| Component | Responsibility |
|---|---|
| `ml.py` | Install/load models; device pick MPS → CPU; weights in `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/models/` with pinned sha256; if torch has no wheel for the shared venv's Python (3.14), a separate `venv-ml` (Python 3.12) is used. `tools/setup.sh --ml` builds it |
| `pointtrack.py` | TAPNext++ wrapper: query points at frame k → per-frame positions + visibility |
| `segment.py` | SAM 2.1 video predictor wrapper: click or box at frame k → per-frame mask |
| `screen.py` + `vidkit screen-insert` | Corners by `--mode green` (chroma key + per-side line fit) or `--mode track` (TAPNext++ points around the screen → RANSAC homography per frame); One-Euro smoothing (no lag, replaces EMA); composite: `warpPerspective`, occluder (hand) mask restored on top, motion blur from corner velocity, colour/gamma match to the clip, low-opacity glass residual from the original screen. Writes mp4 directly |
| `embroider.py` + `vidkit embroider` | Logo RGBA → satin-stitch height map → normal map; cloth grid tracked by TAPNext++ → mesh warp of the design per frame; apply only on SAM 2.1 shirt mask minus hand mask; shading from the clip's cloth luminance, edge shadow/AO |
| `video-gen` rule + validator check | A screen that will receive an app is prompted as flat solid green |

Unchanged: `vidkit bond` stays the tool for screen-print (sablon); `track_screen.py` stays
and may seed initial corners.

### Data flow

```
screen:    panel.png|mp4 (gen_app_screen / Remotion) + clip.mp4
           → vidkit screen-insert --mode green|track --seed x,y
           → out.mp4 + .tmp/qa-screen-<scene>.jpg
embroider: logo.png + clip.mp4
           → vidkit embroider --at x,y --width W   (the click also seeds SAM 2.1 on the shirt)
           → out.mp4 + .tmp/qa-embroider-<scene>.jpg
```

### Error handling (refuse, never degrade silently)

Exit 2 with a named reason when:
- more than 30% of tracked points are invisible for too long (clip too chaotic to composite);
- a corner jumps more than the plausibility limit between frames;
- the shirt mask is too small for the requested design size;
- torch or a model weight is missing → message names `tools/setup.sh --ml`.

No hidden fallback to the old tools.

### Verification

- Geometry unit tests on synthetic clips with known ground truth (moving quad: corner error
  < 2 px; warped cloth texture: design follows the known warp).
- Real model tests run the real models on the Mac — no mocked inference.
- Owner's failing clips (paths supplied before Phase J): before/after contact sheets judged
  by eye; the composite is final only after that look.

### Phases (one ticket)

| Phase | Content |
|---|---|
| A | Probe: install torch + TAPNext++ + SAM 2.1 on this Mac (Python 3.14 vs 3.12, MPS on macOS 26), measure speed, confirm weight licences. **Stop and report on failure** |
| B | `ml.py` + `setup.sh --ml` |
| C | `pointtrack.py` |
| D | `segment.py` |
| E | Screen geometry: green key, homography, One-Euro |
| F | Screen composite: occlusion, blur, colour, glass |
| G | Thread texture: height map, normal map |
| H | Embroidery: mesh warp, shirt mask, shading |
| I | Green-screen rule in `video-gen`, validator check, `registry.json`, `tool-routing.md` |
| J | Proof on owner's real clips, review, release |

### Open items

- Owner's real failing clips: paths pending (needed by Phase J).
- Cost: ~2–3 GB download; processing in minutes per clip, not seconds.

### Data Integration Map

| Component | Data source | Existing? | Notes |
|---|---|---|---|
| Panel content | `gen_app_screen.py` / Remotion render | Yes | Unchanged |
| Initial corners | `track_screen.py` or `--seed` | Yes | Optional seed only |
| Point tracks | TAPNext++ weights | No | Phase A/B |
| Masks | SAM 2.1 weights | No | Phase A/B |
| QA sheets | `vidkit sheet` | Yes | Reused |
| Registry/routing | `tools/registry.json` → `docs/tool-routing.md` | Yes | New entries, rendered |
