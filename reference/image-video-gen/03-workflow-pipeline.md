---
source: Synthesized from PROD_STEP1-3, NB2 docs, VEO guide + gap analysis
curated: 2026-03-19
version: 2.0
tokens: ~1500
platform: claude-projects
---

# Production Pipeline — NB2 → VEO 3.1 Workflow

## Decision Tree: Which VEO Mode?

```
Need to show a CHARACTER consistently across shots?
├── YES → "Ingredients to Video" (1-3 ref images)
│         ⚠️ Cannot use First+Last Frame in same generation
│         ⚠️ Cannot combine with keyframe control
│
└── NO, need controlled TRANSITION between two states?
    ├── YES → Does scene have FACE >30% of frame?
    │         ├── YES → "Single I2V" (start frame only)
    │         │         ⚠️ Safety filter rejects 2 face images
    │         │         Generate START image (NB2) only
    │         │         VEO animates from single frame
    │         │
    │         └── NO → "First + Last Frame" (Keyframe Control)
    │                   Generate START image (NB2) + END image (NB2)
    │                   VEO interpolates the motion between them
    │                   ✅ Safe for: dashboards, products, environments
    │
    └── NO, need to CONTINUE an existing clip?
        └── "Scene Extension" (Extend)
            Source must be VEO-generated, 720p only
            Uses final 1 second as context anchor
```

**Mutual Exclusivity Rule:** Ingredients ≠ First+Last Frame. Pick ONE per generation.

**Safety Filter Rule:** First+Last Frame with 2 photorealistic face images → VEO rejects as "prominent people." Use single I2V (start frame only) for any face-dominant scene.

## Phase 1: NB2 Image Asset Creation

### Pre-Generation Checklist
- [ ] Aspect ratio matches VEO target (16:9 or 9:16)
- [ ] Resolution ≥ 1280×720 (VEO I2V minimum)
- [ ] Thinking Mode = High (for final assets)
- [ ] CFG 5-7, Denoise 0.35-0.45
- [ ] Critical action within central 60% of frame
- [ ] Material shaders defined (glass/metal/skin/textile)

### For First+Last Frame Mode
- [ ] **NO dominant face (>30% frame)** — safety filter rejects 2 face images (use single I2V instead)
- [ ] Start frame and end frame share SAME aspect ratio
- [ ] SAME lighting temperature (Kelvin) in both frames
- [ ] SAME color palette / grading style
- [ ] Character wardrobe identical between frames
- [ ] Camera lens consistent (same focal length)
- [ ] Camera angle change between start/end is max 15° (drastic angle change = broken VEO interpolation)
- [ ] Shot size change between start/end is max 1 step (CU↔MCU only, CU→WS = rejection — reshoot as multi-scene)

#### Few-Shot: Camera Angle Constraint

**BAD — drastic camera jump (will break VEO interpolation):**
```
START: Camera: 85mm f/1.8, eye-level, close-up of officer's face at desk
END:   Camera: 24mm f/8, overhead bird's-eye, wide shot of entire port facility
```
WHY BAD: CU→WS = 3-step jump. Eye-level→overhead = 90°+ angle change. VEO will produce distorted faces, warped environment, ghosting artifacts.

**GOOD — smooth transition (VEO interpolates cleanly):**
```
START: Camera: 50mm f/2.8, eye-level, MCU of officer sitting at desk with monitor
END:   Camera: 50mm f/2.8, eye-level, MS of officer standing up, desk and monitor visible
```
WHY GOOD: MCU→MS = 1 step. Same lens. Same angle. Subject moves (stands up) but camera stays grounded. VEO smoothly interpolates the motion.

**ALSO GOOD — slight angle shift:**
```
START: Camera: 35mm f/4, eye-level, MS of two men at truck rear
END:   Camera: 35mm f/4, slight low angle (10°), MS of same two men, one holds shells
```
WHY GOOD: Same shot size. Only 10° angle change. Same lens. VEO handles this smoothly.

- [ ] End frame represents plausible physical destination from start

### For Ingredients Mode
- [ ] 1-3 reference images generated in NB2
- [ ] Multiple angles: front, ¾, profile (for face consistency)
- [ ] Neutral diffused lighting on references (clean identity data)
- [ ] Same character description verbatim across all prompts

## Phase 2: VEO Generation

### Image-to-Video Handoff Rules
1. **Describe MOTION only** — VEO sees the image, don't repeat visual details
2. **Specify audio explicitly** — ambient + SFX + dialogue (or "no music")
3. **Include "no subtitles, no audience sounds"** in every prompt
4. **Match camera movement to emotion** (see `04-cinematography-lookup.md`)

### Quality Settings

| Setting | Value |
|---------|-------|
| Quality | "Highest Quality (Experimental Audio)" |
| Resolution | 720p if extending, 1080p if final-only |
| Duration | Match dialogue length (3-6s dialogue sweet spot) |
| Audio | Always enabled for dialogue shots |

## Phase 3: Scene Extension (Same Scene Continuity)

### When to Extend vs New Generation

| Scenario | Method |
|----------|--------|
| Same scene, continue action | Extend |
| Same character, different location | New gen with Ingredients |
| Transition between two distinct states | First+Last Frame |
| Same scene, change camera angle | New gen (extend won't change angle) |

### Extension Chain Pattern
```
Clip 1 (8s, 720p) → Extend → Clip 2 (+7s) → Extend → Clip 3 (+7s) → ...
```

**Critical:** 
- Generate initial clip at **720p** (1080p cannot extend)
- Ensure final 1 second has clear, non-blurry movement
- Hold pose for final 0.5s for stable handoff
- Monitor for clothing/texture drift across iterations
- Resolution lock: same resolution across ALL segments

### The "Last Frame Secret"
For clips that need stitching but aren't direct extensions:
1. Export final frame of Clip A
2. Feed into NB2 as reference for Clip B's start frame
3. This preserves grading, character position, lighting across the cut

## Phase 4: Post-Production

### Upscaling
- 1080p and 4K upscaling available in Flow, Gemini API, Vertex AI
- This is a **post-generation** step, not at generation time
- Upscale AFTER all extensions are complete

### Quality Audit Checklist
- [ ] No identity drift across clips
- [ ] Lighting consistent across all segments
- [ ] Audio seamless at extension joints
- [ ] No edge hallucination from ratio mismatch
- [ ] SynthID watermark present (ethical compliance)
- [ ] No subtitle artifacts from wrong dialogue syntax

## The Reject Loop — two strikes means the input is wrong (v3.2.1)

A clip that comes back with the same defect twice is not bad luck. The model is reproducing
something it was handed. Re-prompting a third time spends money to receive the same frame.

**The rule: after the SECOND reject with the same defect, stop prompting and go inspect the input.**
In order, the input is:

| # | Suspect | How to check it | Field evidence |
|---|---|---|---|
| 1 | **The keyframe** | Open the PNG at 100% and look at the defect area. Crop it and look again. | `S04` came back with three hands on v1, v3 and v5. The keyframe itself had three hands. Three VEO renders bought nothing; regenerating the still fixed it first try. |
| 2 | **The identity reference** | Compare the ref sheet against the face that came out | `S01` "face not similar at all" survived five renders. The keyframe had been built from a front-only ref. |
| 3 | **The physics being asked for** | See "Motion VEO will not do" in `02-veo-production-guide.md` | Diesel pouring into a jerrycan splashed on the ground on v1, v3 and v5 of a WIDE shot. No prompt wording fixes it — the shot size was wrong. |
| 4 | **The prompt** | Only now | — |

Prompting is suspect #4, not #1. It is the cheapest thing to change, which is exactly why it gets
changed first and why the loop repeats.

### Archive every reject with its reason IN THE FILENAME

```
clips/_tidak-dipakai/scene-04-v5-tangan-ketiga.mp4      # third hand
clips/_tidak-dipakai/scene-03-v3-solar-tumpah.mp4       # diesel spilled
keyframes/_gen/DITOLAK-S04-tangan-lepas-setir.png       # hand off the wheel
```

`ls` on that folder then reads as a defect histogram. `scene-04-v1-tangan-ketiga`,
`-v3-tiga-tangan`, `-v5-tangan-ketiga` is the same word three times — that is the signal to stop
prompting, and it is invisible if the files are named `v1 v2 v3`.

A reject is never deleted while the scene is still open: it is the evidence that a defect is
recurring rather than random. Sweep the folder only after the group is approved.

### Regenerating a keyframe invalidates everything downstream of it

A new keyframe means: re-render the clip, re-run the voice change on the new clip, re-composite its
overlays, rebuild any Remotion static asset that plays that clip
(`12-remotion-explainer.md` §8), re-cut the group. Stopping at "the clip looks right" ships a group
whose overlays still carry the old face.

---

## Common Pitfalls & Fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| Edge hallucination | Aspect ratio mismatch NB2↔VEO | Generate natively in target ratio |
| Plastic texture | Over-denoising | Prompt "visible pores", "natural grain", "micro-scratches" |
| Light jumps between clips | Different lighting in start/end frames | Match Kelvin + light direction in both NB2 images |
| Character morph during extend | Weak context in final second | Hold clear pose, avoid blur at clip end |
| Stutter at extension joint | Abrupt motion at clip end | Maintain consistent camera speed through final second |
| Wrong VEO mode selected | Ingredients + Keyframe confusion | They are mutually exclusive — pick one |
| "Prominent people" safety error | First+Last Frame with face >30% | Use single I2V (start frame only) for face-dominant scenes |
| On-screen char lip-syncs VO | `Voiceover:` with face visible | Use `Voice-over narrator, [tone]: text` |
| Same defect on 2+ renders | The keyframe/ref carries it — the prompt does not | Stop rendering. Open the keyframe at 100%, crop the defect area. See "The Reject Loop" above |
| Face "not similar at all" after several renders | Identity built from a front-only reference | Rebuild the keyframe with a 3-angle ref sheet (front + profile + ¾) named in the prompt text |
| Reference image rejected by the API | File over the 10 MB per-image cap | Downscale to <10 MB before sending; keep the original for the sheet |
| Liquid/particle physics wrong in a wide shot | Physics VEO does not resolve at that scale | Do not animate it wide. Carry it in a macro insert; hold the wide static |
| Clip is right but the group still shows the old version | A composited or Remotion-embedded copy was not rebuilt | Rebuild every derivative: `_ov/`, `_final/`, `shots/public/`, then re-cut |
