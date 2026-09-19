---
source: NB2 Technical Standards, Composition, Prompting, Video Workflow (Docs 01-04)
curated: 2026-03-19
version: 2.0
tokens: ~1800
platform: claude-projects
---

# Nano Banana 2 (Gemini 3.1 Flash Image) — Image Generation Reference

## Model Identity

| Model | Designation | Speed | Max Resolution | Use Case |
|-------|------------|-------|----------------|----------|
| Nano Banana 2 | Gemini 3.1 Flash Image | Flash | Native 4K (4096×4096) | Production keyframes, start/end frames |
| Nano Banana Pro | Gemini 3 Pro Image | Production | Native 4K | Maximum fidelity, complex layering |

NB2 = primary image model for this pipeline. NB Pro = fallback for extreme precision only.

## Thinking Mode

Activate reasoning layer for spatial logic, occlusion, refraction before pixel diffusion.

| Level | Use | Time |
|-------|-----|------|
| Minimal | Rapid iteration, aesthetic exploration | 1-3s |
| High | Complex spatial logic, physics, final 4K output | ~60-65s |

Triggers: "calculate light transmission through glass", "subject behind third column from left"
Result: ~35-point quality increase on 100-pt scale. Eliminates spatial hallucinations.

## Core Parameters

| Parameter | Range | Violation Effect |
|-----------|-------|-----------------|
| **CFG Scale** | 5.0–7.0 | >8 = hyper-processed, crushed colors, noise |
| **Denoise/Variation** | 0.35–0.45 | >0.50 = structural hallucination, identity loss |
| **JPEG Quality** | 90–92 | >92 = no perceptual benefit, bloated file |
| **Color Space** | sRGB (web), Adobe RGB (print) | Unmanaged Adobe RGB = dull on web browsers |

## Resolution & Cost

| Tier | Pixels | Tokens | Cost (Standard/Batch) | Use |
|------|--------|--------|-----------------------|-----|
| 1K | 1024² | 560 | $0.067 / $0.034 | Drafts, social thumbnails |
| 2K | 2048² | 1,120 | $0.134 / $0.067 | Web heroes, presentations |
| 4K | 4096² | 2,000 | $0.240 / $0.120 | Print, commercial, video keyframes |

Third-party (LaoZhang AI): ~$0.05 flat any resolution, OpenAI-compatible API.
API = watermark-free. Gemini App = SynthID watermark included.

## Aspect Ratios (14 Native)

| Ratio | Purpose | Video Motion |
|-------|---------|-------------|
| 16:9 | Widescreen standard | Horizontal pans, tracking |
| 9:16 | Mobile-first (TikTok, Reels) | Vertical crane, tall subjects |
| 21:9 | CinemaScope storytelling | Expansive landscapes, negative space |
| 4:1 / 8:1 | Ultra-wide panoramic | Hero headers, matte paintings |
| 1:1 | Square format | Feed posts |

**Auto Mode:** NB2 selects ratio from prompt reasoning.
**Cropping cost:** 16:9 → 9:16 = **68% pixel loss**. Generate natively instead.
**60% Rule:** Keep critical action in central 60% for cross-platform safety.

## Identity Lock System

Track up to **5 characters + 14 objects** per workflow.

**Workflow:**
1. Generate high-res "Hero Shot" (neutral lighting)
2. Create reference sheet: front, profile, ¾ view
3. Upload: 4 person refs + 10 object refs to API/AI Studio
4. Inject via `@identity` tag: "Place @character1 in rainy Shibuya street"
5. Quality audit via multi-turn: "Keep facial features identical to Image 1"

**CRITICAL — Reference Image Injection Rule:**
All reference images MUST be explicitly embedded in the prompt text, not just uploaded as files. The prompt must tell the model to look at and match the reference:

```
maintain exact facial identity from reference image: cast-c1-face.png
```

Without this injection, the model generates from text description only — causing identity drift. This is especially critical for faces where even slight deviation is immediately noticeable.

Every NB2 prompt MUST also include a **Required Reference Images** table listing all ref files needed for that prompt, so the user never misses uploading a file. See `global-promo-config.md` Section 16 for table format.

### Uniqueness Filter (v2.2.0+ — MANDATORY pre-Phase-4A)

**Before generating any standalone asset reference in Phase 4A, apply the UNIQUENESS filter:**

| Tier | Action |
|---|---|
| **UNIQUE** (faces, company logos, custom UI screens, industry-specific equipment like UHF RFID readers / fuel sensors / chassis ID plates, proprietary product designs, location landmarks) | **GENERATE reference** |
| **COMMON** (generic phone in hand, kopi gelas, concrete pavement, plain office chair, generic paper stack, ceiling fan, plain wall, generic clipboard) | **SKIP reference** — NB2 renders reliably from text alone |
| **AMBIGUOUS** | Default GENERATE (safer; user can drop in Phase 4B review) |

**Decision test:** "Can a competent prompt writer describe this in 20 words and trust NB2 to render correctly?" YES → COMMON, skip. NO → UNIQUE, generate.

See `global-promo-config.md` §26 for full rule + validator C2 (Phase 4A uniqueness audit) + IRN before/after examples.

### Max 5 Inline References Per Phase 4B Prompt (v2.2.0+ — HARD CAP)

**Replaces** old "Max 3 identity locks per scene" rule (which applied to faces only).

**New rule:** Each Phase 4B scene prompt has MAX 5 inline references **combined** (faces + bodies + costumes + objects + environments + UI). All inline with element described (no header blocks). Each filename max 1× per prompt.

**If >5 refs needed:** Split scene OR consolidate via composite asset (Tier 5+ per §18 dependency graph).

See `global-promo-config.md` §26.4 + validator C3 (Phase 4B ref count audit).

### Face refs: three angles, or the face drifts (v3.2.1)

A front-only reference produces a face that is *plausible* from the front and wrong from every other
angle — and the clip will move the head. The identity ref is a **sheet**, not a photo:

```
ref/cast-c2-face-3sudut.png     front + profile + three-quarter, same lighting, neutral expression
ref/cast-c2-face.png            the hero front shot
```

Name BOTH in the prompt text. Field case: a keyframe built from the front shot alone produced
"the face is not similar at all" and survived five video renders before the still was rebuilt with
the 3-angle sheet.

**10 MB hard cap per reference image.** The image API rejects anything larger. A 4K render is
routinely 17 MB, so keep a downscaled copy for sending and the original for the sheet:

```bash
mkdir -p ref/_small
sips -Z 2048 ref/cast-c2-face-3sudut.png --out ref/_small/cast-c2-face-3sudut.png
```

### Inspect the keyframe before spending a video render (v3.2.1)

A video model reproduces what the still gives it. A defect in the keyframe is not a risk in the clip
— it is a certainty, and it costs a video render each time to rediscover.

Before any still is promoted to `keyframes/`, crop and look at:

| Check | Why it is on the list |
|---|---|
| **Count the hands.** One per arm, attached to a body. | A keyframe with three hands produced three rejected clips before anyone opened the PNG. |
| **Every hand is doing the thing the script says.** A hand on the wheel stays on the wheel; a hand holding a phone is not also on the wheel. | Fixing "third hand" by regenerating without the constraint produced the opposite defect: both hands off the wheel of a moving truck. |
| **The face against the ref sheet**, side by side at 100%. | See above. |
| **Props are in the state the action needs.** An open jerrycan is open; a screen the script wants blank is blank. | A closed jerrycan cannot be filled, whatever the prompt says. |
| **Nothing the script did not ask for.** | A patrolling guard nobody wanted survived two renders. |

Write the constraint into the image prompt as a positive, not a negative: "left hand gripping the
steering wheel at 9 o'clock, right hand holding the phone to the ear — exactly two hands" beats
"no third hand".

## Text Rendering (94.2% Accuracy)

- Exact wording in **quotes**: `"SALE"`
- Font directive: `"bold sans-serif"`, `"modern geometric"`
- Anchor placement: `"centered 40px above the subject"`
- Don't use tag soup → use full-sentence technical instructions

## Prompt Formula

```
Subject/Material + Lighting Architecture + Camera/Lens + Campaign Context
```

**Example:**
"A heavy crystal perfume bottle [Material] on black marble, side-lit by 5500K softbox creating long shadows [Lighting], shot on Hasselblad X2D 85mm f/2.8 [Camera], for luxury fragrance editorial [Context]."

## Material Shaders

| Material | Trigger | Physics |
|----------|---------|---------|
| Glass | "Crystal" + 1.5 refraction index | Light bending, transmission |
| Metal | "Anisotropic reflections" | Directional scatter, normal mapping |
| Skin | "Subsurface scattering, visible pores" | Non-plastic, dewy finish |
| Textiles | "Fabric drape by weight" | Weave-level light interaction |
| Plastic | "Specular highlights" | Hard mirror reflections |

## Multi-Turn Refinement (Not Prompt Roulette)

1. **Brief/Ratio Lock** — set native aspect ratio
2. **Low-Thinking 1K Draft** — composition check
3. **Semantic Masking** — "Make text neon", "Increase shadow depth"
4. **Promote to High-Thinking 4K** — final production asset
5. **Localization** — re-prompt same ad into 10+ languages, pixel-perfect
