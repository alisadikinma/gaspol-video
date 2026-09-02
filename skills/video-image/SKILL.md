---
name: video-image
description: >
  Phase 4 of AI video promotional production. Phase 4A generates the Asset Library — standalone
  reusable assets (faces, bodies, costumes, vehicles, objects, products, environments, UI composites)
  with dependency graph and tier system. Phase 4B generates Scene Keyframes — start/end frames
  composed FROM Phase 4A assets. Batch-by-ACT generation with prompt-reviewer agent validation.
  Triggers on: video image, image prompt, NB2, nb2 prompt, generate image, asset library,
  scene keyframe, buat gambar, keyframe, image generation, gambar video.
---

# Video Image — Phase 4: Asset Library & Scene Keyframes (NB2)

## Overview

Phase 4 of the AI video promotional production pipeline. Phase 4A generates the Asset Library — standalone reusable assets (faces, bodies, costumes, vehicles, objects, products, environments, UI composites) with a dependency graph and tier system. Phase 4B generates Scene Keyframes — start/end frames composed FROM Phase 4A assets, using batch-by-ACT generation with prompt-reviewer agent validation. Prerequisite: all output from `/video-brainstorm` (strategic-brief.md, cast-profile.md) and `/video-script` (av-script.md, scene-plan.md, ref-manifest.md). Output: `nb2-reference-prompts.md`, `image-prompts.md`.

## Prerequisite

These files must exist in the output folder:
- `strategic-brief.md` (from `/video-brainstorm`) — Domain Knowledge section must be populated
- `cast-profile.md` (from `/video-brainstorm`)
- `av-script.md` (from `/video-script`)
- `scene-plan.md` (from `/video-script`)
- `ref-manifest.md` (from `/video-script`) — ALL reference images must be validated and uploaded to ref/

## Reference Files (Read On-Demand)

### Always Read First
| Task | Read |
|------|------|
| ANY generation | `reference/global-promo-config.md` (ALWAYS FIRST) |

### Phase 4: Image Prompts
| Task | Read |
|------|------|
| NB2 image specs | `reference/image-video-gen/01-nb2-image-generation.md` |
| Cinematography lookup | `reference/image-video-gen/04-cinematography-lookup.md` |
| Creator profile/preset | `reference/image-video-gen/05-creator-and-holidays.md` |
| Directing, performance, continuity | `reference/image-video-gen/06-directing-and-performance.md` |

### CONTEXT LOADING — Phase 4A
READ these files ONLY:
1. `reference/global-promo-config.md` (Sections 17-23: asset categories, dependency graph, NB2 defaults)
2. `reference/image-video-gen/01-nb2-image-generation.md`
3. `reference/script-to-scene-bridge.md` (Section 7B ONLY: 9-point realism checklist)
Plus: READ `{output_folder}/cast-profile.md`, `{output_folder}/scene-plan.md`, `{output_folder}/strategic-brief.md` (Domain Knowledge section only).
Total: 3 reference files + 3 output files. Do NOT load storytelling, VEO, or cinematography files.

### CONTEXT LOADING — Phase 4B (per batch)
READ these files ONLY:
1. `reference/global-promo-config.md` (Sections 16-20: upload table, asset categories, NB2 defaults, aspect ratio)
2. `reference/image-video-gen/01-nb2-image-generation.md`
3. `reference/script-to-scene-bridge.md` (Sections 3-7 only: templates, transitions, checklists)
4. `reference/image-video-gen/04-cinematography-lookup.md`
Plus PER-BATCH context (NOT full files):
- `{output_folder}/cast-profile.md`: ONLY entries for characters appearing in this batch's scenes
- `{output_folder}/scene-plan.md`: ONLY entries for this batch's scenes
- `{output_folder}/strategic-brief.md`: Domain Knowledge section only
- Previous batch's last scene END frame filename (for dependency chain)
Total: 4 reference files + filtered output data. NEVER load storytelling or VEO files.

---

### Rule 33: Explainer scenes are skipped in Phase 4B (v3.0.0)

`scene-plan.md` gives every scene a `Render Path`. Phase 4B generates keyframes for `live-action`
scenes ONLY. An `explainer` scene is built as a Remotion shot by `/video-explainer` in Phase 4.5, so
generating an NB2 keyframe for it spends credits on an image nothing will ever use.

**Phase 4A is NOT filtered.** An explainer shot still needs its assets — a logo, a product photo, a
UI reference, a face for a portrait inset. Generate those in Phase 4A exactly as before; only the
scene keyframes in 4B are skipped.

The batch summary must name the skipped scenes, so a scene that is `explainer` by mistake is visible
rather than silently missing:

```
Batch {N}: {X} keyframes generated, {Y} scenes skipped (explainer): {list}
```

## Hard Rules (NON-NEGOTIABLE)

1. **Ingredients ≠ First+Last Frame** — mutually exclusive VEO modes, NEVER combine
2. **Dialogue uses colon syntax** — `says:` NEVER quotation marks
3. **NB2 aspect ratio MUST match VEO target** — mismatch = edge hallucination
4. **All AskUserQuestion interactions** — NEVER ask questions as plain text, ALWAYS use AskUserQuestion tool with selectable options
5. **Max 5 cast members** — 1-3 Pemeran Utama + 0-2 Pemeran Pendamping (NB2 identity lock limit)
6. **Cast ref by role** — Utama: face+body+costume(if institutional) MANDATORY. Pendamping: face MANDATORY, body/costume OPTIONAL.
7. **Narration language from Step 1.0** — script dialogue and VEO `says:` text MUST be in user's chosen language. NB2/VEO prompt structure stays English.
8. **Tone consistency** — `video_tone` from Step 1.7b MUST be applied across ALL phases: script word choice (Phase 2), cinematography (Phase 4), atmosphere (Phase 5). Reference global-promo-config.md Section 13 Tone Impact Matrix.
9. **Cultural accuracy** — when location is specified, web search MUST be performed (Step 3.5.2a) and cultural details MUST be injected into environment NB2 prompts and VEO scene prompts. Wrong license plate / wrong ethnicity / wrong architecture = rejection signal.
10. **Asset-first, scene-second** — Phase 4A generates ASSET LIBRARY (atoms: people, vehicles, objects, locations). Phase 4B generates SCENE KEYFRAMES (molecules FROM assets). Scene keyframes NEVER describe visual elements from scratch — always reference an asset file. See `global-promo-config.md` Section 17.
11. **Recurring element detection** — any visual element appearing in 2+ scenes MUST be generated as standalone asset first. Auto-detect from av-script.md scan. See `global-promo-config.md` Section 18.
12. **Auto-scan ref/ folder** — before generating ANY prompt, list ref/ folder, map every visual element to existing refs. Existing user photos = ground truth, NEVER override with text description. See `global-promo-config.md` Section 19.
13. **Aspect ratio triple enforcement** — every NB2 prompt MUST specify target ratio in FIRST line, TECHNICAL section, and LAST line. See `global-promo-config.md` Section 20.
14. **UI text localization** — on-screen text (dashboards, signage, displays) MUST match `narration_language`. Technical abbreviations stay English. See `global-promo-config.md` Section 21.
15. **Product closeup mandatory** — every product/commodity MUST have closeup reference image. User photo preferred over AI. See `global-promo-config.md` Section 22.
16. **Location photo mandatory** — every unique location MUST have reference image (user photo or AI-generated with cultural context). See `global-promo-config.md` Section 22.
17. **Output filename per prompt** — every NB2 prompt MUST include explicit `**Output →** ref/filename.png` line. See `global-promo-config.md` Section 16.
18. **Ref-to-prompt body binding** — every ref in upload table MUST have matching injection line in prompt body. Having ref in table but NOT in prompt = model won't use it. See `global-promo-config.md` Section 16.
19. **Climate-aware costume** — cross-check cast costume vs location climate after cultural research. Flag inappropriate combinations. See `global-promo-config.md` Section 23.
20. **Dynamic tier assignment** — composite assets (UI screens showing truck+face) auto-assigned to tier = max(sub-element tiers) + 1. Never generate composite before its sub-elements. See `global-promo-config.md` Section 18.
21. **Scene Logic Realism (9-point)** — Every prompt passes 9 checks: environment accuracy, human behavior realism, data consistency, uniform ranks, explicit negatives, reference photos, timeline/shift consistency, prop/object scale accuracy, domain context populated. See `script-to-scene-bridge.md` Section 7B.
22. **Character portrait-first** — Any character in 2+ scenes MUST have standalone face portrait generated FIRST in Phase 4A. Text descriptions alone = different faces every time. Applies to cast AND recurring extras. See `global-promo-config.md` Section 18.
23. **Narrative arc consistency** — Connected scenes MUST include `NARRATIVE CONTEXT:` block naming connections, visual breadcrumbs, cause-effect chains, shared environment refs. See `script-to-scene-bridge.md` Section 7C.
24. **(v2.2.0 ENV-GATED) Sequential scene dependency — CONDITIONAL** — Scene N+1 start frame references Scene N end frame (`scene-{NN-1}-end.png`, bare filename, NO ref/ prefix) ONLY IF env(N) == env(N+1). Hard cut between scenes (different location, different lighting Kelvin, different time-of-day) = DROP `scene-{NN-1}-end.png` cross-ref entirely. Character/prop continuity ALONE is NOT sufficient — environment is sole gating criterion. Visual continuity for hard cuts carried by: text SUBJECT spec + standalone identity refs (`cast-c{N}-face.png`) + standalone prop refs + costume verbatim + NARRATIVE CONTEXT block. Validator C4 enforces. See `global-promo-config.md` §27.
25. **Prop/object scale enforcement** — Every handheld prop or object in NB2/VEO prompts MUST include: (a) exact physical dimensions in cm/mm, (b) real-world size analogy, (c) proportion relative to human hand/body, (d) explicit negative for wrong sizes. "Small" alone is NOT sufficient.
26. **Camera angle constraint for Frame mode** — START and END frames within one VEO scene MUST have: max 1-step shot size change (CU↔MCU↔MS↔MWS↔WS) and max 15° camera angle change. Drastic camera jumps break VEO interpolation.
27. **NB2 identity lock: filename only** — `Maintain exact facial identity from reference image:` MUST use bare filename only (e.g., `cast-c1-face.png`). NEVER add folder prefix like `ref/` or `keyframes/` — NB2 matches uploaded images by filename, and `ref/cast-c1-face.png` fails to match the uploaded `cast-c1-face.png`. Same rule applies to all reference image mentions inside NB2 prompt body text.
28. **Inline-only reference pattern** — All NB2 reference image filenames MUST appear INLINE with the element they describe, NOT in a separate header block. Each filename appears EXACTLY ONCE per prompt. Three categories: (1) identity lock inline with character: `[Name] (Maintain exact facial identity from reference image: cast-c1-face.png) in blue uniform...`, (2) object/environment ref inline with element: `...the monitor — EXACTLY matching ui-anpr-screen.png: ANPR interface...`, (3) scene continuity inline: `...continuation from scene-{NN-1}-end.png — maintaining character position...`. BANNED: header blocks like `Using reference image xxx.png for [purpose]`, standalone identity lock lines, duplicate filename mentions.
29. **Multi-POV environment spatial context** — When a scene's upload table has 2+ `env-*` references of the SAME location from DIFFERENT viewpoints (e.g., entry, exit, side, interior, exterior), the prompt MUST include a `SPATIAL CONTEXT` block immediately after the opening line. This block: (a) explicitly states all references show the SAME location from DIFFERENT camera angles, (b) maps each ref to the specific zone/element it depicts, (c) specifies the CAMERA POSITION for this scene relative to the reference angles, (d) clarifies which ref provides PRIMARY layout vs which provide DETAIL for specific zones. Without this block, NB2 may misinterpret multi-POV refs as separate locations or attempt to literally reproduce all angles simultaneously.
30. **NEVER proceed without user approval** — every phase ends with approval gate
31. **(v2.2.0) NB2 Reference Uniqueness Filter HARD GATE (Phase 4A)** — Before generating any Phase 4A standalone asset, apply UNIQUENESS filter test: "Can a competent prompt writer describe this in 20 words and trust NB2 to render correctly?" YES → COMMON tier → SKIP, NB2 renders from text. NO → UNIQUE/AMBIGUOUS tier → GENERATE. COMMON examples to ALWAYS skip: generic phone-in-hand, kopi gelas, concrete pavement, plain office chair, ceiling fan, generic paper stack, plain wall, generic clipboard. UNIQUE examples to ALWAYS generate: faces, company logos, custom UI screens, industry-specific equipment (UHF RFID reader / fuel sensor / chassis ID plate), proprietary product hero shots, location landmarks. Combined filter: (UNIQUE/AMBIGUOUS) AND (recurring 2+ scenes OR critical-identity OR plot-anchor). Validator C2 enforces. See `global-promo-config.md` §26.
32. **(v2.2.0) Max 5 Inline References HARD CAP (Phase 4B)** — Each Phase 4B scene prompt has MAX 5 inline references combined (faces + bodies + costumes + objects + environments + UI). REPLACES old "Max 3 identity locks per scene" rule. All inline with element described. Each filename max 1× per prompt. If >5 refs needed → split scene into 2 sub-scenes OR consolidate via composite asset (Tier 5+ per §18). Validator C3 enforces. See `global-promo-config.md` §26.4.

---

## Workflow

### Phase 4A: ASSET LIBRARY — NB2 (Output: nb2-reference-prompts.md)

### CONTEXT LOADING — Phase 4A
READ these files ONLY:
1. `reference/global-promo-config.md` (Sections 17-23: asset categories, dependency graph, NB2 defaults)
2. `reference/image-video-gen/01-nb2-image-generation.md`
3. `reference/script-to-scene-bridge.md` (Section 7B ONLY: 9-point realism checklist)
Plus: READ `{output_folder}/cast-profile.md`, `{output_folder}/scene-plan.md`, `{output_folder}/strategic-brief.md` (Domain Knowledge section only).
Total: 3 reference files + 3 output files. Do NOT load storytelling, VEO, or cinematography files.

> **CRITICAL: Assets FIRST, scenes SECOND.** This phase generates individual reusable building blocks (atoms). Phase 4B composes scene keyframes (molecules) FROM these assets. See `global-promo-config.md` Section 17.

#### Step 4A.0: Auto-Scan ref/ Folder

**PRE-CHECK — Domain Research Gate:**
CHECK `strategic-brief.md` > Domain Knowledge section.
- IF empty or contains only template placeholders → **HARD BLOCK**: "Domain research not completed. Run Step 1.2d before generating prompts."
- IF populated → extract key domain terms (equipment names, process steps, local brands) for injection into every prompt's DOMAIN CONTEXT line.

**PRE-CHECK — Phase 3.5 Asset Dedup:**
SCAN `ref/` folder for assets already generated in Phase 3.5.
- IDENTIFY existing assets by filename pattern.
- SKIP re-generation for assets that already exist and meet quality standards.
- Only generate NEW assets (recurring elements from Step 4A.1 not yet in ref/) or UPGRADE assets (Phase 3.5 used generic prompts, Phase 4A can improve with dependency-aware refs).

Before generating anything:

```
1. LIST all files in {project}/ref/
2. MAP each file to its category (cast, product, env, vehicle, object, brand, ui)
3. IDENTIFY which assets already exist (user photos = ground truth)
4. IDENTIFY which assets need AI generation
5. Present to user: "Ini asset yang sudah ada vs yang perlu di-generate"
```

#### Step 4A.1: Recurring Element Detection

Scan av-script.md for recurring visual elements:

```
FOR each visual element across ALL scenes:
  COUNT appearances
  IF count >= 2 AND no asset exists in ref/:
    → ADD to asset generation queue
    → ASSIGN to appropriate tier

PRESENT detected recurring elements:
"Detected {N} recurring visual elements that need standalone assets:
| # | Element | Appears in Scenes | Asset Needed |
|---|---------|-------------------|-------------|
| 1 | Hino dump truck | 7, 12, 13, 14 | ref/vehicle-truck-hino.png |
| 2 | Driver face | 4, 7, 12, 14 | ref/cast-c2-face.png |
| ... | ... | ... | ... |"
```

#### Step 4A.2: Build Dependency Graph

Auto-assign tiers per `global-promo-config.md` Section 18 algorithm:

```
Tier 0: User-provided assets (brand logos, user photos already in ref/)
Tier 1: Faces, standalone products, product closeups, environments, vehicles, objects
Tier 2: Bodies (inject face ref)
Tier 3: Costumes (inject face + body ref)
Tier N: Composites (inject all sub-elements — e.g., UI screens showing truck+face)
```

Present dependency graph to user for approval.

#### Step 4A.3: Generate Asset Prompts (Tier by Tier)

Follow templates from `script-to-scene-bridge.md` Section 11.

**For each tier (in order):**
1. Generate all prompts for current tier (parallel within tier)
2. Include aspect ratio triple enforcement (first line, TECHNICAL, last line)
3. Include `**Output →** ref/{filename}.png` per prompt
4. Include Required Reference Images table directly BELOW each image heading, BEFORE prompt body (bare filenames, NO ref/ prefix)
5. Include ref-to-prompt body binding (every ref in table → matching injection line in prompt)
6. Apply UI text localization if prompt contains on-screen text
7. **Wait for user to generate/upload all current tier assets**
8. Validate all current tier assets exist before advancing to next tier

#### Step 4A.4: Climate-Aware Costume Check

After cultural research and before generating costume prompts:

```
Cross-check cast costume vs location climate.
FLAG inappropriate combinations (e.g., wool suit in 33°C tropical climate).
See global-promo-config.md Section 23.
```

#### Step 4A.5: Asset Library Approval

```
AskUserQuestion:
"Asset library ({N} assets across {M} tiers) sudah lengkap. Review?"

Options:
A) Approve — lanjut ke scene keyframes (Phase 4B)
B) Regenerate specific assets
C) Add more assets
```

**Save output:** `{output_folder}/nb2-reference-prompts.md`

---

### Phase 4B: SCENE KEYFRAMES — NB2 (Output: image-prompts.md)

### CONTEXT LOADING — Phase 4B (per batch)
READ these files ONLY:
1. `reference/global-promo-config.md` (Sections 16-20: upload table, asset categories, NB2 defaults, aspect ratio)
2. `reference/image-video-gen/01-nb2-image-generation.md`
3. `reference/script-to-scene-bridge.md` (Sections 3-7 only: templates, transitions, checklists)
4. `reference/image-video-gen/04-cinematography-lookup.md`
Plus PER-BATCH context (NOT full files):
- `{output_folder}/cast-profile.md`: ONLY entries for characters appearing in this batch's scenes
- `{output_folder}/scene-plan.md`: ONLY entries for this batch's scenes
- `{output_folder}/strategic-brief.md`: Domain Knowledge section only
- Previous batch's last scene END frame filename (for dependency chain)
Total: 4 reference files + filtered output data. NEVER load storytelling or VEO files.

> **CRITICAL: Scene keyframes are MOLECULES composed FROM Phase 4A ATOMS.**
> NEVER describe a visual element from text alone if an asset exists in ref/.
> Every character, vehicle, object, product, environment MUST reference its asset file.

#### Step 4B.1: Load All Assets

Load all assets from ref/ (Phase 4A output + user photos + user-provided files).
Build scene-to-asset mapping from scene-plan.md.

#### Step 4B.2: Batch-by-ACT Generation

**BATCH EXECUTION — max 5 scenes per batch.**

Group scenes by ACT from scene-plan.md. Each ACT = 1 batch. If an ACT has >5 scenes, split into sub-batches of max 5.

```
FILTER scenes: keep only rows whose Render Path is `live-action`
  (an `explainer` scene is built as a Remotion shot in Phase 4.5 and gets NO keyframe here —
   skip it, and list what was skipped in the batch summary)

FOR each batch (ACT or sub-batch):

  1. CONTEXT RELOAD (fresh per batch):
     → Re-read Phase 4B CONTEXT LOADING files
     → Load ONLY this batch's cast entries + scene entries
     → Load previous batch's LAST scene END frame filename as dependency anchor

  2. GENERATE prompts for this batch's scenes:
     FOR each scene in this batch:

       **If Frame mode:**
       - Generate START frame prompt (per `script-to-scene-bridge.md` Section 3)
       - Generate END frame prompt (maintain consistency checklist)
       - **Every visual element MUST reference its asset file** — no text-only descriptions

       **If Ingredients mode:**
       - Generate 1-3 character reference prompts
       - Front, three-quarter, profile angles

       **Apply:**
       - Cinematography lookup (emotion → lighting/lens/film stock)
       - Apply creator reference phrase **per character** from `cast-profile.md` (verbatim)
       - For multi-character scenes, use Cast Interaction Templates from `creator-profile-system.md` Section 8
       - NB2 technical parameters (CFG 5-7, denoise 0.35-0.45)
       - **Aspect ratio triple enforcement** (first line, TECHNICAL, last line)
       - Central 60% rule
       - **`Output →` filename** per prompt (ref/scene-{NN}-start.png, ref/scene-{NN}-end.png)
       - **Ref-to-prompt body binding (inline-only)** — every ref in upload table MUST have matching INLINE mention in prompt body, placed directly with the element it describes. BANNED: header blocks like `Using reference image xxx.png for [purpose]`. Each filename MAX 1x per prompt.
       - **UI text localization** — on-screen text in narration language
       - **Scale/dimension specification** — every visible prop and object MUST have real-world dimensions in the prompt (cm/mm + visual analogy + proportion to hand + negative for wrong size)
       - **Wardrobe verbatim consistency** — pull EXACT costume text from cast-profile.md or Character Costume Tracking Table (Section 7D of script-to-scene-bridge.md). NEVER paraphrase. If character appears in 3+ scenes, the costume text string MUST be identical across all prompts.
       - **Previous scene continuity injection (inline)** — for scenes 2+ in timeline, inject `scene-{NN-1}-end.png` inline with continuity statement (e.g., `continuation from scene-{NN-1}-end.png — maintaining character position...`), filename only (NO `ref/` prefix), and include in upload table

     END FOR

  3. VALIDATE — spawn prompt-reviewer agent:
     → Agent tool: subagent_type="gaspol-video:video-prompt-reviewer"
     → Pass: this batch's generated prompts + cast-profile.md + scene-plan.md
     → Agent returns: PASS / FAIL with per-prompt feedback

  4. IF validator returns FAIL:
     → Read validator feedback (specific prompts + specific issues)
     → Re-generate ONLY the failing prompts (not entire batch)
     → Re-validate (max 2 retry cycles per batch)

  5. APPROVE — AskUserQuestion:
     "Batch {N} ({ACT name}, Scenes {X}-{Y}) ready for review."
     A) Approve batch — proceed to next batch
     B) Revise specific scenes — list scene numbers
     C) Regenerate entire batch — start fresh

  6. APPEND approved batch to {output_folder}/image-prompts.md

END FOR
```

Write the Generation Checklist and Dependency Chain table AFTER all batches complete.

#### Step 4B.3: Final Review

After ALL batches are generated and approved:
1. Read the complete `{output_folder}/image-prompts.md`
2. Verify cross-batch dependency chain integrity (Scene N→N+1 references correct across batch boundaries)
3. Present summary:
   - Total batches: {N}
   - Total scenes: {M}
   - Validator pass rate: {X}% first-pass, {Y}% after retry
4. AskUserQuestion: final approval or revision

**Save output:** `{output_folder}/image-prompts.md`

---

## Quality Gates

### Asset Library Quality Gate (Phase 4A)
- [ ] Auto-scan ref/ folder completed before generating any prompt
- [ ] Recurring elements (2+ scenes) detected and queued as standalone assets
- [ ] Dependency graph built with correct tier assignments
- [ ] Composites (UI screens, etc.) assigned tier = max(sub-element tiers) + 1
- [ ] Each tier fully validated before advancing to next tier
- [ ] Product closeup reference exists for every product/commodity
- [ ] Location reference exists for every unique location
- [ ] User photos used as ground truth (not overridden by AI generation)
- [ ] Climate-aware costume check completed
- [ ] Brand logos are user-provided (not AI-generated)
- [ ] Domain Knowledge section in strategic-brief.md populated with real research (not template placeholders)
- [ ] Phase 3.5 assets audited — no duplicate generation

### Scene Keyframe Quality Gate (Phase 4B)
- [ ] NB2 aspect ratio triple enforcement (first line, TECHNICAL, last line)
- [ ] CFG 5-7, Denoise 0.35-0.45
- [ ] Start/End frames share same lighting Kelvin
- [ ] Cast reference phrase verbatim per character from cast-profile.md
- [ ] Central 60% rule applied
- [ ] Thinking mode specified (minimal for draft, high for final)
- [ ] EVERY visual element references its asset file (no text-only descriptions for recurring elements)
- [ ] Output filename specified per prompt (`ref/scene-{NN}-start.png`)
- [ ] Every ref in upload table has matching INLINE mention in prompt body — placed directly with the element it describes, NOT in a header block
- [ ] No `Using reference image xxx.png for [purpose]` header blocks — all refs must be inline with elements
- [ ] No standalone identity lock lines — must be inline with character description (e.g., `[Name] (Maintain exact facial identity...) — description...`)
- [ ] No duplicate filenames within same prompt — each filename MAX 1x
- [ ] UI text localized per narration_language (except technical abbreviations)
- [ ] DOMAIN CONTEXT line in every prompt contains specific local equipment/process details (not generic)
- [ ] Every prop/object has explicit scale specification (dimensions + analogy + negative)
- [ ] Previous scene end frame referenced in upload table and inline in prompt body (for scenes 2+)
- [ ] Camera angle between start/end max 15° change, shot size max 1 step
- [ ] Aspect ratio specified in ALL prompts (NB2: triple enforcement; VEO: first + last line)
- [ ] NB2 identity lock uses filename only — NO `ref/` or other folder prefix in `Maintain exact facial identity from reference image:` lines or any reference image mention inside prompt body text

### Cross-Cutting Quality Gate (All Phases 4-5)
- [ ] **Scene Logic Realism 9-point** — each prompt passes: environment accuracy, behavior realism, data consistency, uniform ranks, explicit negatives, ref photos, timeline/shift, prop/object scale accuracy, domain context populated
- [ ] **Character portrait-first** — every character in 2+ scenes has standalone face ref in Phase 4A
- [ ] **Narrative arc consistency** — every prompt has `NARRATIVE CONTEXT:` block with connections, breadcrumbs, cause-effect
- [ ] **Visual breadcrumbs** — at least 1 shared visual element between adjacent scenes
- [ ] **Data pinning** — dashboard names/numbers consistent across all scenes showing same data
- [ ] **Timeline consistency** — time-of-day/lighting matches across connected scenes
- [ ] **Wardrobe tracking** — Character Costume Tracking Table built, each character's costume text verbatim identical across all scenes (unless script-directed change with justification)
- [ ] **Sequential dependency chain** — every scene N+1 references scene N end frame output in upload table and inline in prompt body (continuity statement, not header block)
- [ ] **Inline-only reference pattern** — no header blocks, no standalone identity lock lines, no duplicate filenames per prompt (Rule 28)

---

**Save output:** `{output_folder}/nb2-reference-prompts.md`, `{output_folder}/image-prompts.md`

## Next Step

Run `/video-gen` to continue to Phase 5 (Video Prompts — VEO 3.1). The video-gen skill includes an Image Review step that reads your actual keyframe images before generating VEO prompts.
