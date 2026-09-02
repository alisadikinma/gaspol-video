---
name: video-gen
description: >
  Phase 5 of AI video promotional production. Starts with per-scene Image Review — AI reads
  actual keyframe images (multimodal), compares with NB2 prompts, brainstorms VEO approach
  with user per scene. Then generates VEO 3.1 video prompts with camera movement, 3-layer
  audio (dialogue/VO + SFX + ambient), lip sync, extensions, and transitions.
  Batch-by-ACT with prompt-reviewer agent validation.
  Triggers on: video gen, video generation, VEO, veo prompt, generate video,
  buat video prompt, video prompts, phase 5, lanjut video.
---

# Video Gen — Phase 5: Image Review & Video Prompts (VEO 3.1)

## Overview

This skill has TWO parts. First, an **Image Review** step (Step 0) where Claude reads the actual keyframe images generated from NB2 prompts using multimodal vision, compares them with the original NB2 prompt text, and brainstorms the VEO approach with the user per scene. Second, **VEO prompt generation** (Steps 5.1-5.4) that produces complete video prompts with camera movement, 3-layer audio (dialogue/VO + SFX + ambient), lip sync directions, extension strategy, and transitions — batch-by-ACT with prompt-reviewer agent validation. Output: `video-prompts.md`.

## Prerequisite

These files must exist in the output folder:
- `strategic-brief.md` (from `/video-brainstorm`)
- `cast-profile.md` (from `/video-brainstorm`)
- `av-script.md` (from `/video-script`)
- `scene-plan.md` (from `/video-script`)
- `image-prompts.md` (from `/video-image`)
- Keyframe images in `{output_folder}/keyframes/` folder (generated from NB2 prompts)

## Reference Files (Read On-Demand)

### Always Read First
| Task | Read |
|------|------|
| ANY generation | `reference/global-promo-config.md` (ALWAYS FIRST) |

### Phase 5: Video Prompts
| Task | Read |
|------|------|
| VEO 3.1 production | `reference/image-video-gen/02-veo-production-guide.md` |
| Seedance 2.0 production | `reference/image-video-gen/07-seedance-production-guide.md` |
| Kling 3.0 production | `reference/image-video-gen/08-kling-production-guide.md` (primary) + `reference/image-video-gen/08b-kling-notebooklm-briefing.md` (NotebookLM-distilled cross-validation) |
| Voice-over consistency (ALL platforms) | `reference/image-video-gen/09-voice-consistency-workflow.md` — MANDATORY for video >1 scene with voice continuity |
| Image-video pipeline | `reference/image-video-gen/project-instruction.md` |
| Cinematography lookup | `reference/image-video-gen/04-cinematography-lookup.md` |

### Image Review (Step 0)
| Task | Read |
|------|------|
| Actual keyframe images | `{output_folder}/keyframes/*.png` (multimodal read) |

### CONTEXT LOADING — Phase 5 (per batch)
READ these files ONLY (platform-conditional — load the guide matching `video_platform` from Step 5.0):
1. `reference/global-promo-config.md` (Sections 6-10, 13, 28: output, resolution, video modes, tone, platform routing)
2. Platform guide (pick ONE based on `video_platform`):
   - VEO 3.1 → `reference/image-video-gen/02-veo-production-guide.md`
   - Seedance 2.0 → `reference/image-video-gen/07-seedance-production-guide.md`
   - Kling 3.0 → `reference/image-video-gen/08-kling-production-guide.md`
   - Mixed → load all three platform guides relevant to scenes in current batch
3. `reference/image-video-gen/03-workflow-pipeline.md`
4. `reference/image-video-gen/04-cinematography-lookup.md`
5. `reference/image-video-gen/09-voice-consistency-workflow.md` (read once per video, NOT per batch — voice strategy is video-level decision)
Plus PER-BATCH context:
- `{output_folder}/cast-profile.md`: ONLY entries for characters in this batch
- `{output_folder}/scene-plan.md`: ONLY entries for this batch's scenes
- `{output_folder}/av-script.md`: ONLY the AV rows for this batch's scenes
- `{output_folder}/image-prompts.md`: ONLY the prompts for this batch's scenes (as NB2→VEO reference)
- `{output_folder}/keyframes/*.png`: Actual keyframe images for Image Review (multimodal read)
Total: 4 reference files + filtered output data. NEVER load storytelling or NB2-specific files.

---

## Hard Rules (NON-NEGOTIABLE)

1. **NEVER skip a phase** — Image Review (Step 0) MUST complete before VEO generation
2. **NEVER proceed without user approval** — every batch ends with approval gate
3. **Ingredients ≠ First+Last Frame** — mutually exclusive VEO modes, NEVER combine
4. **Audio is NEVER optional** — unspecified = VEO guesses random sounds
5. **Dialogue uses colon syntax** — `says:` NEVER quotation marks
6. **720p for extendable clips** — 1080p clips CANNOT extend
7. **NB2 aspect ratio MUST match VEO target** — mismatch = edge hallucination
8. **B-Roll voiceover = Voice-over narrator** — B-Roll uses `Voice-over narrator, [tone]: text` NOT bare `Voiceover:` (which lip-syncs to visible character). Every B-Roll MUST have VO narration + `> POST-PROD VO:` backup.
9. **Face >30% frame for lip sync** — smaller = sync failure
10. **Tone consistency** — `video_tone` from strategic-brief.md MUST be applied across ALL VEO prompts: atmosphere, cinematography, audio mood. Reference global-promo-config.md Section 13 Tone Impact Matrix.
11. **VEO: No real names in `says:`** — VEO safety filter rejects real person name + photorealistic face. Use `Host says:` / `Presenter says:` / `Speaker says:`. NB2 can still use real names.
12. **VEO: No face ref filenames** — `Maintain exact facial identity from reference image: xxx.png` is NB2-only. VEO prompts use generic: `Maintain visual continuity with reference frame character appearance.`
13. **VEO: Face-dominant = single I2V** — Scene with face >30% frame → single I2V (start frame only). First+Last Frame → only for faceless scenes (dashboards, products, environments). Safety filter rejects 2 face images.
14. **VEO: No em dash in audio text** — NEVER use `—` in `says:` or `Voice-over narrator:` text. VEO audio engine mistranslates em dashes. Replace with `,` or `. `
15. **VEO: Every B-Roll has VO** — No silent B-Roll. Every B-Roll VEO prompt MUST have `Voice-over narrator, [tone]: text` + `> POST-PROD VO:` fallback line outside the prompt block.
16. **Scene Logic Realism (9-point)** — Every prompt passes 9 checks: environment accuracy, human behavior realism, data consistency, uniform ranks, explicit negatives, reference photos, timeline/shift consistency, prop/object scale accuracy, domain context populated. See `script-to-scene-bridge.md` Section 7B.
17. **Narrative arc consistency** — Connected scenes MUST include `NARRATIVE CONTEXT:` block naming connections, visual breadcrumbs, cause-effect chains, shared environment refs. See `script-to-scene-bridge.md` Section 7C.
18. **Sequential scene dependency** — Scene N+1 start frame MUST reference Scene N end frame (`ref/scene-{NN-1}-end.png`) as upstream continuity anchor. Upload table MUST include previous scene output. No exceptions for sequential timeline scenes.
19. **All AskUserQuestion interactions** — NEVER ask questions as plain text, ALWAYS use AskUserQuestion tool with selectable options

---

## Workflow

### Step 5.0a: VOICE CONSISTENCY STRATEGY (NEW v2.4.0 — runs BEFORE platform selection)

For any video with >1 scene OR with character voice continuity, voice consistency must be planned BEFORE platform/mode selection.

```
AskUserQuestion:
"Apakah video ini perlu konsistensi voice-over antar scene?"

Options:
A) Ya, ada voice reference (audio sample / video clip dengan suara target) — engine will route to Path A native lock (Kling Elements 3.0 / Seedance @Audio1) or Path B prep
B) Ya, tapi belum ada voice reference — engine defaults to Path B (post-prod ElevenLabs Voice Changer pass at end)
C) Ya, saya akan record VO sendiri di post-prod (Path C) — engine generates with placeholder audio, drives final edit by VO track
D) Tidak perlu (video pendek single-scene atau tanpa VO continuity) — skip voice strategy
```

If A/B/C: load `reference/image-video-gen/09-voice-consistency-workflow.md`, save selected path + voice description to `{output_folder}/voice-consistency-plan.md` for Phase 5 prompt injection.

**Voice description verbatim rule (universal):** Once locked, the SAME 10-15 word voice description must appear in EVERY VEO/Seedance/Kling prompt in this video. Copy-paste, NEVER paraphrase. See `09-voice-consistency-workflow.md` §"Prompt-Level Discipline".

---

### Step 5.0: PLATFORM SELECTION (v2.3.0 — runs AFTER voice strategy, BEFORE Image Review)

Phase 5 supports three video platforms. Pick at start of session before any image review.

```
AskUserQuestion:
"Pilih video platform untuk video ini:"

Options:
A) VEO 3.1 (Google) — broadcast cinematic, prompt-faithful, lip-sync EN/ID, 8s/clip + extend ke 148s
B) Seedance 2.0 (ByteDance) — native 2K, @ reference system (12 assets), unlimited extension, audio reference input
C) Kling 3.0 (Kuaishou) — native 4K, multi-shot storyboard (6 shots/15s), mixed-language scene, photoreal human motion (Bahasa Indonesia: ✅ Voice-over narrator native, ❌ on-screen lip-sync 5 langs only)
D) Mixed (pilih per-scene) — set `platform` column per scene in scene-plan.md
```

**Platform selection rules:**
- Save `video_platform` to `{output_folder}/scene-plan.md` (header line or per-scene column for Mixed mode)
- If Bahasa Indonesia dialogue is mandatory: Kling 3.0 OK for **B-Roll + off-screen Voice-over narrator** (native ID support). Only switch to VEO/Seedance for **on-screen lip-sync ID dialogue** scenes (face >30% frame speaking ID)
- If user picks Mixed → engine suggests per-scene platform via heuristic table in `reference/image-video-gen/08-kling-production-guide.md` "Phase 5 Decision Matrix"
- Platform-specific mode selection (VEO Ingredients vs First+Last Frame; Seedance Omni vs First/Last; Kling I2V vs Multi-Shot vs Motion Control) happens per-scene during Image Review (Step 0)
- Subsequent VEO-named steps in this skill (Step 5.1-5.4) apply to all three platforms — substitute mode/audio/safety rules from the matching platform guide

**Cross-platform invariants (all three platforms):**
- NB2 aspect ratio MUST match video model target — mismatch = edge hallucination
- Audio is NEVER optional — specify all 3 layers (dialogue/VO, ambient, music)
- Dialogue uses colon syntax (`says:` NEVER quotation marks)
- NO real person names in `says:` — use `Host says:` / `Presenter says:`
- NO em dash `—` in audio text — use `,` or `. `
- B-Roll narration = `Voice-over narrator, [tone]: text` + `> POST-PROD VO:` backup
- Face >30% frame for lip-sync (all platforms)
- Cannot render legible text in scene — use post-prod overlay
- **Voice-over consistency** — for any video >1 scene, follow `09-voice-consistency-workflow.md` (pick Path A/B/C, lock voice description verbatim across all prompts, single emotion per scene)

**Platform-specific divergences (load matching guide for full rules):**
| Aspect | VEO 3.1 | Seedance 2.0 | Kling 3.0 |
|--------|---------|--------------|-----------|
| Resolution | 720p (extend) / 1080p (final) | Native 2K | Native 4K |
| Clip duration | 8s + extension ~148s | 4-15s + unlimited extend | **3-15s per-second granular** (no native extend) |
| Modes | Ingredients / First+Last / Extend / I2V | T2V / I2V / First-Last / Omni / Video Ext | T2V / I2V / First-Last / Multi-Shot / Motion Control |
| Audio langs | 10+ (lip-sync + VO) | 10+ (lip-sync + VO) | Lip-sync 5 (EN/ZH/JA/KO/ES) / VO inc. Bahasa Indonesia native |
| Unique feature | Reliable text-faithful | @ reference system + audio ref | Multi-shot 6-in-1 + mixed-language scene |

---

### Step 0: IMAGE REVIEW — Per-Scene Validation & Brainstorm

Before generating ANY VEO prompt, review the actual keyframe images with the user.

**CONTEXT LOADING — Step 0:**
- `{output_folder}/image-prompts.md` (NB2 prompt text for comparison)
- `{output_folder}/scene-plan.md` (scene intent, VEO mode, duration)
- `{output_folder}/av-script.md` (narration/dialogue for each scene)
- `{output_folder}/keyframes/*.png` (actual keyframe images — multimodal read)

#### Per-Scene Review Loop

FOR each scene in current batch:

  #### Step 0.1: Visual Analysis

  1. READ start keyframe image: `keyframes/scene-{NN}-start.png` (multimodal — Claude sees the actual image)
  2. IF Frame mode: also READ end keyframe: `keyframes/scene-{NN}-end.png`
  3. Load corresponding NB2 prompt text from `image-prompts.md` for this scene
  4. Load scene entry from `scene-plan.md` (VEO mode, duration, intent)
  5. Load narration/dialogue from `av-script.md` for this scene's timecode

  #### Step 0.2: AI Observation Report

  Present to user:

  ```
  ## Scene {NN} — Image Review

  **Apa yang saya lihat di keyframe image:**
  {AI describes what it actually SEES in the image — characters, their appearance,
   environment details, lighting quality, props visible, expressions, composition,
   color palette, camera angle}

  **Perbandingan dengan NB2 prompt:**
  {AI notes differences — things user edited, elements that generated differently
   from the original prompt, missing elements, added elements}

  **Scene intent (dari script):**
  Beat: {beat label}
  Narration: "{narration text from av-script}"
  Purpose: {what this scene needs to convey — emotion, information, transition}

  **Suggestion untuk VEO prompt:**
  - Camera movement: {suggestion based on what image shows}
  - Focus emphasis: {what to draw attention to in motion}
  - Transition approach: {how to connect to next scene}
  - Audio approach: {dialogue/VO direction, SFX, ambient matching the image}
  - Duration: {from scene-plan} | Mode: {VEO mode from scene-plan}
  ```

  #### Step 0.3: User Brainstorm

  ```
  AskUserQuestion:
  "Scene {NN} — ada catatan atau arahan khusus untuk video prompt-nya?"

  Options:
  A) Setuju dengan suggestion di atas — lanjut generate VEO prompt
  B) Ada arahan tambahan — saya akan jelaskan
  C) Image ini perlu di-generate ulang dulu — skip scene ini untuk sekarang
  ```

  - If A → save AI suggestion as VEO direction for this scene
  - If B → user provides notes → AI incorporates into VEO direction
  - If C → mark scene as SKIPPED, continue to next scene, address later

  #### Step 0.4: Save Scene Context

  Save per-scene context for VEO generation:
  - `actual_description`: What AI sees in the actual image (NOT the original NB2 prompt)
  - `user_notes`: User's additional direction (if any)
  - `veo_approach`: Agreed-upon VEO approach (camera, emphasis, transition, audio)
  - `skipped`: true/false

END FOR

After reviewing all scenes in the batch:
- List any SKIPPED scenes
- Proceed to Step 5.1 for non-skipped scenes
- VEO prompts will use `actual_description` + `user_notes`, NOT original NB2 text

---

### Phase 5: VIDEO PROMPTS — VEO 3.1 (Output: video-prompts.md)

#### Step 5.1: Batch-by-ACT VEO Generation

**BATCH EXECUTION — max 5 scenes per batch.**

Same ACT grouping as Phase 4B.

```
FOR each batch (ACT or sub-batch):

  1. CONTEXT RELOAD (fresh per batch):
     → Re-read Phase 5 CONTEXT LOADING files
     → Load ONLY this batch's scene entries + cast entries + AV script rows
     → Load this batch's NB2 keyframes from image-prompts.md (as NB2→VEO reference)
     → Load Image Review context for this batch's scenes (Step 0 output)

  2. GENERATE VEO prompts for this batch's scenes:
     FOR each scene in this batch:

       NOTE: For each scene, use `actual_description` from Image Review (not original NB2
       text) as the visual reference for VEO prompt. Incorporate `user_notes` if provided.

       **Presenter scenes (lip sync):**
       - Use presenter template from `script-to-scene-bridge.md` Section 4
       - VEO mode: Single I2V (start frame only) — NOT First+Last Frame (safety filter)
       - Dialogue: `Host says: {text}` — NEVER real person names (safety filter)
       - NO em dash `—` in dialogue — replace with `,` or `. `
       - NO face ref filenames in VEO prompt — use generic continuity language
       - Face >30% frame
       - All 3 audio layers specified

       **B-Roll scenes (voiceover):**
       - Use B-Roll template from `script-to-scene-bridge.md` Section 4
       - Voiceover: `Voice-over narrator, {tone}: {text}` — NOT bare `Voiceover:` (lip-syncs to visible char)
       - NO em dash `—` in voiceover text
       - EVERY B-Roll MUST have voiceover narration (no silent B-Roll)
       - Add `> POST-PROD VO:` backup line outside prompt block for every B-Roll
       - SFX + music + ambient all specified

       **Extension scenes:**
       - Use extension template
       - Reference previous clip context
       - 720p locked, same camera speed

       **Transitions:**
       - Add transition end instruction per `script-to-scene-bridge.md` Section 5
       - Apply "Last Frame Secret" for cross-scene continuity

     END FOR

  3. VALIDATE — spawn video-prompt-reviewer agent:
     → Agent tool: subagent_type="gaspol-video:video-prompt-reviewer"
     → Pass: this batch's VEO prompts + scene-plan.md + image-prompts.md (this batch only)
     → Agent returns: PASS / FAIL with per-prompt feedback

  4. IF FAIL → re-generate failing prompts only (max 2 retries)

  5. APPROVE — AskUserQuestion:
     "Batch {N} ({ACT name}, Scenes {X}-{Y}) VEO prompts ready for review."
     A) Approve batch — proceed to next batch
     B) Revise specific scenes — list scene numbers
     C) Regenerate entire batch — start fresh

  6. APPEND to {output_folder}/video-prompts.md

END FOR
```

#### Step 5.2: Output Mode

Check `global-promo-config.md` `output_mode`:

**--full mode:** Complete production plan per `script-to-scene-bridge.md` Section 8
**--quick mode:** Copy-paste ready prompts only (NB2 + VEO per scene)

#### Step 5.3: Final Review

After ALL batches are generated and approved:
1. Read the complete `{output_folder}/video-prompts.md`
2. Verify cross-batch continuity (transition instructions link correctly across batch boundaries)
3. Verify NB2→VEO consistency (each VEO prompt references correct NB2 keyframe)
4. Present summary:
   - Total batches: {N}
   - Total scenes: {M}
   - Total VEO clips: {P} (generations + extensions)
   - Total estimated duration: {X}s
   - Validator pass rate: {Y}% first-pass, {Z}% after retry
5. AskUserQuestion: final approval or revision

**Save output:** `{output_folder}/video-prompts.md`

#### Step 5.4: Production Summary

Present final production package summary:
- Output files saved to: `{output_folder}/`
- Files: strategic-brief.md, cast-profile.md, av-script.md, scene-plan.md, ref-manifest.md, nb2-reference-prompts.md, image-prompts.md, video-prompts.md

---

## Quality Gates

### Image Review Quality Gate (Step 0)
- [ ] Every scene's keyframe image has been READ (multimodal)
- [ ] AI Observation Report presented for every scene
- [ ] User has responded (approved/added notes/skipped) for every scene
- [ ] Skipped scenes are tracked and listed
- [ ] Scene context saved with actual_description (not NB2 text)

### Video Prompt Quality Gate (Phase 5)
- [ ] VEO mode correct per scene (no Ingredients + Frame mix)
- [ ] Face-dominant scenes use single I2V (NOT First+Last Frame)
- [ ] All 3 audio layers specified per scene
- [ ] Dialogue uses generic role: `Host says:` — no real person names
- [ ] Voiceover uses `Voice-over narrator, [tone]: text` — no bare `Voiceover:`
- [ ] Every B-Roll scene has voiceover narration + `> POST-PROD VO:` backup
- [ ] No em dash `—` in any `says:` or `Voice-over narrator:` text
- [ ] No face ref filenames (`ref/cast-c{N}-face.png`) in VEO prompts
- [ ] Face >30% for lip sync scenes
- [ ] 720p for extendable clips
- [ ] Extension prompts reference previous clip
- [ ] Transition instructions on scene-ending clips
- [ ] Negative prompt block included
- [ ] Total duration within target range

### Cross-Cutting Quality Gate (Phase 5)
- [ ] **Scene Logic Realism 9-point** — each prompt passes: environment accuracy, behavior realism, data consistency, uniform ranks, explicit negatives, ref photos, timeline/shift, prop/object scale accuracy, domain context populated
- [ ] **Narrative arc consistency** — every prompt has `NARRATIVE CONTEXT:` block with connections, breadcrumbs, cause-effect
- [ ] **Visual breadcrumbs** — at least 1 shared visual element between adjacent scenes
- [ ] **Data pinning** — dashboard names/numbers consistent across all scenes showing same data
- [ ] **Timeline consistency** — time-of-day/lighting matches across connected scenes
- [ ] **Wardrobe tracking** — Character Costume Tracking Table built, each character's costume text verbatim identical across all scenes (unless script-directed change with justification)
- [ ] **Sequential dependency chain** — every scene N+1 references scene N end frame output in upload table and inline in prompt body (continuity statement, not header block)

---

## Output

**Save output:** `{output_folder}/video-prompts.md`

---

## Production Summary

After ALL batches are generated and approved, present final production package:
- Output files: strategic-brief.md, cast-profile.md, av-script.md, scene-plan.md, ref-manifest.md, nb2-reference-prompts.md, image-prompts.md, video-prompts.md
- Total scenes, VEO clips, extensions, estimated duration
- Validator pass rate
