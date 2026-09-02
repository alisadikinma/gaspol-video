---
name: video-validate
description: >
  Unified validation for AI Video Promo Engine. Validates script output, NB2 image prompts +
  actual keyframe images (multimodal), VEO video prompts, and/or reference file consistency.
  Supports --script, --image, --video, --refs, --all flags. Interactive picker if no flag provided.
  Triggers on: video validate, validate, check, consistency check, cek referensi, cek konsistensi,
  validate script, validate image, validate video, check refs.
---

# Video Validate — Unified Quality Checker

Unified validation skill for the AI Video Promo Engine. Covers 5 validation targets across the full production pipeline: script output quality, NB2 image prompt rules plus actual keyframe image review (multimodal), VEO video prompt rules, and cross-file reference consistency. Each target can be run independently with a flag, or all at once with `--all`. If no flag is provided, the user is prompted with an interactive picker.

## Usage

| Flag | Target | Input |
|------|--------|-------|
| `--script` | Script output quality | av-script.md + strategic-brief.md |
| `--image` | NB2 prompt rules + actual keyframe image review | image-prompts.md + keyframes/*.png |
| `--video` | VEO prompt rules | video-prompts.md + scene-plan.md |
| `--refs` | Cross-file reference consistency (24 checks) | All reference + skill + agent files |
| `--all` | Everything above | All files |

If no flag provided, use AskUserQuestion:
```
AskUserQuestion:
"Mau validate apa?"

Options:
A) Script output (av-script.md)
B) Image prompts + keyframe images
C) Video prompts (VEO)
D) Reference file consistency
E) All — validate everything
```

---

## Script Validation (`--script`)

**Input:** `{output_folder}/av-script.md` + `{output_folder}/strategic-brief.md`

### Check S1: 7-Beat Arc Completeness
**How:** Search av-script.md for all 8 beat labels: Pattern Interrupt, Hook, Foreshadow, Agitate, Guide+Plan, Peak, CTA, Won Day
**Expected:** All 8 beats present in the Beat column

### Check S2: Forbidden Words
**How:** Search av-script.md for: synergy, leverage, robust, revolutionary, cutting-edge, seamlessly, innovative solution, state-of-the-art
**Expected:** 0 matches

### Check S3: Human Consequence per Feature
**How:** For each row mentioning a product feature in the Video column, check if Audio column has human consequence/benefit
**Expected:** Every feature has a "so what?" follow-up

### Check S4: Hook "So What?" Test
**How:** Read first 3 seconds (first 1-2 rows by timecode) — does the hook create curiosity/tension?
**Expected:** Hook does NOT start with company name, logo, or generic intro

### Check S5: CTA Quality
**How:** Read CTA beat row — is the CTA specific, time-bound, and low-friction?
**Expected:** CTA is actionable (not "visit our website" or "learn more")

### Check S6: No Jargon Without Translation
**How:** Search for technical jargon — should have immediate plain-language follow-up
**Expected:** All jargon has translation/explanation within same row

### Check S7: Narration Language Consistency
**How:** Check strategic-brief.md `Language:` field, then verify av-script.md narration/dialogue matches
**Expected:** All narration in correct language per selection

### Check S8: Tone Consistency
**How:** Check strategic-brief.md `Tone:` field, then verify av-script.md word choice/pacing matches
**Expected:** Script tone matches selected tone throughout

### Check S9: Duration Target
**How:** Check last timecode in av-script.md vs platform target from strategic-brief.md
**Expected:** Total duration within platform's target range

---

## Image Validation (`--image`)

**Input:** `{output_folder}/image-prompts.md` + `{output_folder}/keyframes/*.png` + `{output_folder}/cast-profile.md` + `{output_folder}/scene-plan.md`

### Part A: Prompt Text Checks

### Check I1: Aspect Ratio Triple Enforcement
**How:** For each NB2 prompt, check aspect ratio appears in FIRST line, TECHNICAL section, and LAST line
**Expected:** Triple mention in every prompt

### Check I2: Identity Lock Filename-Only
**How:** Search for `Maintain exact facial identity from reference image: ref/` — should return 0 matches
**Expected:** All identity locks use bare filename (e.g., `cast-c1-face.png`), NO `ref/` prefix

### Check I3: Inline-Only Reference Pattern
**How:** Search for `Using reference image` as standalone header lines
**Expected:** 0 header blocks. All refs inline with elements. No standalone identity lock lines. No duplicate filenames per prompt.

### Check I4: Ref-to-Prompt Body Binding
**How:** For each prompt, verify every file in upload table has matching inline mention in prompt body
**Expected:** Every ref in table → matching injection in body

### Check I5: Output Filename
**How:** Check every prompt has `**Output →** ref/filename.png` line
**Expected:** Present in every prompt

### Check I6: DOMAIN CONTEXT Populated
**How:** Search for `DOMAIN CONTEXT:` in each prompt
**Expected:** Present with specific local details (not generic or placeholder)

### Check I7: NARRATIVE CONTEXT Block
**How:** Search for `NARRATIVE CONTEXT:` in each prompt
**Expected:** Present with Previous/This/Next scene references

### Check I8: Scale Specs for Props
**How:** For each handheld prop/object, check for dimensions (cm/mm), analogy, proportion, negative
**Expected:** All 4 scale elements present for every prop

### Check I9: Costume Verbatim from Cast Profile
**How:** Compare costume text in prompts with cast-profile.md — must be identical
**Expected:** Exact match, no paraphrasing

### Check I10: Sequential Dependency Chain
**How:** For scenes 2+, check upload table includes `scene-{NN-1}-end.png` and prompt body has inline continuity reference
**Expected:** Every scene 2+ references previous scene end frame

### Part B: Actual Image Checks (Multimodal)

### Check I17: Explainer Scenes Have No Keyframe (v3.0.0)

Read `scene-plan.md`. For every scene whose `Render Path` is `explainer`, assert `image-prompts.md`
contains NO prompt for it. An explainer scene is built as a Remotion shot in Phase 4.5; a keyframe
for it is spend with no consumer.

FAIL lists the scene numbers that have both. Mirrors reviewer check C6.

### Check I11: Read Keyframe Images
**How:** READ each .png file in keyframes/ folder (multimodal)
**Expected:** Images are readable and match scene numbering

### Check I12: Aspect Ratio Match
**How:** Compare actual image aspect ratio with prompt's specified ratio
**Expected:** Actual image matches target ratio

### Check I13: Character Face Consistency
**How:** Compare character faces across multiple scenes' keyframe images
**Expected:** Same character looks consistent (similar features, recognizable)

### Check I14: Lighting Consistency
**How:** Compare lighting in connected scenes (sequential timeline)
**Expected:** Time-of-day and lighting direction consistent across connected scenes

### Check I15: Costume Match
**How:** Compare visible costumes in images with cast-profile.md descriptions
**Expected:** Costumes match descriptions

### Check I16: Environment Match
**How:** Compare environment in images with cultural research from strategic-brief.md
**Expected:** Architecture, signage, vegetation match location context

---

## Video Validation (`--video`)

**Input:** `{output_folder}/video-prompts.md` + `{output_folder}/scene-plan.md` + `{output_folder}/image-prompts.md`

### Check V1: VEO Mode Correct
**How:** Compare each scene's VEO mode in video-prompts.md with scene-plan.md
**Expected:** Modes match (Frame/Ingredients/Extend as planned)

### Check V2: Face-Dominant Single I2V
**How:** Identify scenes with face >30% (from scene-plan or image review) — verify they use Single I2V, not First+Last Frame
**Expected:** All face-dominant scenes use Single I2V

### Check V3: Audio 3-Layer Complete
**How:** For each VEO prompt, check all 3 audio layers present (dialogue/VO, SFX, ambient)
**Expected:** All 3 layers specified in every prompt

### Check V4: Dialogue Generic Role
**How:** Search for `says:` in VEO prompts — should be `Host says:`, `Presenter says:`, `Speaker says:`
**Expected:** No real person names before `says:`

### Check V5: B-Roll VO Syntax
**How:** Search B-Roll scenes for voiceover syntax
**Expected:** Uses `Voice-over narrator, [tone]: text` (not bare `Voiceover:`)

### Check V6: B-Roll Has VO + Backup
**How:** Check every B-Roll VEO prompt has VO narration AND `> POST-PROD VO:` backup line
**Expected:** Both present in every B-Roll scene

### Check V7: No Em Dash in Audio
**How:** Search `says:` and `Voice-over narrator` text for `—` (em dash)
**Expected:** 0 em dashes in audio text

### Check V8: No Face Ref Filenames
**How:** Search VEO prompts for `cast-c{N}-face.png` or `ref/cast-c`
**Expected:** 0 matches — VEO uses generic continuity language

### Check V9: Resolution for Extendable
**How:** Check extendable clips have 720p specified
**Expected:** All extendable clips are 720p (not 1080p)

### Check V10: Extension References
**How:** Extension prompts should reference previous clip context
**Expected:** Each extension prompt references source clip

### Check V11: Transition Instructions
**How:** Scene-ending clips should have transition end instruction
**Expected:** Transition instruction present on scene boundaries

### Check V12: NB2→VEO Consistency
**How:** Compare VEO prompt visual description with corresponding NB2 prompt/image
**Expected:** VEO description matches the actual keyframe content

---

## Reference Consistency Validation (`--refs`)

Run 24 automated consistency checks across all operational files. Reports PASS/FAIL per check with exact file:line.

### Scope

**Operational files** (checked):
- `skills/video-brainstorm/SKILL.md`
- `skills/video-script/SKILL.md`
- `skills/video-image/SKILL.md`
- `skills/video-gen/SKILL.md`
- `skills/video-full/SKILL.md`
- `skills/video-validate/SKILL.md`
- `skills/video-add-platform/SKILL.md`
- `agents/video-engine-agent.md`
- `reference/global-promo-config.md`
- `reference/creator-profile-system.md`
- `reference/script-to-scene-bridge.md`
- `reference/storytelling_script_gen/*.md` (all 12 files)
- `reference/image-video-gen/*.md` (all 8 files)
- `CLAUDE.md`

**Excluded:**
- `docs/plans/*.md`
- `.claude-plugin/*.json`
- Output files

### Check R1: VEO Mode Mutual Exclusivity
**Pattern:** Any mention of combining "Ingredients" and "First+Last Frame" in same generation
**Expected:** Always described as mutually exclusive, never combined
**How to verify:** Search all files for "Ingredients" near "First+Last Frame" — must include "mutually exclusive" or "cannot combine" or "pick ONE"

### Check R2: Audio Mandatory Rule
**Pattern:** Any reference to VEO audio being optional
**Expected:** Audio always described as mandatory/required, never optional
**How to verify:** Search for "audio" + "optional" — should only appear in negation ("NOT optional", "NEVER optional")

### Check R3: Dialogue Colon Syntax
**Pattern:** VEO dialogue examples using quotation marks instead of colon syntax
**Expected:** All dialogue examples use `says:` colon syntax, never `says "text"`
**How to verify:** Search for `says "` or `says '` — should return 0 matches (except in "DON'T" examples)

### Check R4: Resolution Extend Rule
**Pattern:** 1080p described as extendable
**Expected:** Only 720p is extendable, 1080p CANNOT extend
**How to verify:** Search for "1080p" + "extend" — must always say "cannot" or "CANNOT"

### Check R5: Reference File Count
**Pattern:** Total reference file count in CLAUDE.md and skill/agent files
**Expected:** 23 reference files (12 storytelling + 8 image-video + 3 global/bridge)
**How to verify:** Count file entries in Reference Files tables in CLAUDE.md, skill files, and agent.md

### Check R6: 7-Beat Arc Completeness
**Pattern:** Beat labels in storytelling references
**Expected:** All 7 beats present: Pattern Interrupt, Hook, Foreshadow, Agitate, Guide+Plan, Peak, CTA, Won Day
**How to verify:** Search `project-instruction.md` and CLAUDE.md for all beat names

### Check R7: Forbidden Words List
**Pattern:** Forbidden words in CLAUDE.md vs project-instruction.md
**Expected:** Same 8 forbidden words in both files
**How to verify:** Extract forbidden words list from both files, compare

### Check R8: Face Minimum Percentage
**Pattern:** Minimum face percentage for lip sync
**Expected:** 30% consistently across all files
**How to verify:** Search for face percentage — should always be "30%" or ">30%"

### Check R9: Cast System Consistency
**Pattern:** References to old single-creator model in operational files
**Expected:** All operational files use cast system terminology (cast-profile, cast-c{N}, Pemeran Utama/Pendamping). No references to `creator-profile.md` (as a generated output), `creator-face.png`, or `creator-brand.png` remain.
**How to verify:** Search all operational files for `creator-face.png`, `creator-brand.png`, `alisadikinface.png` — should return 0 matches. Note: `creator-profile-system.md` as a reference filename is OK (it's the source doc name), but references to generating/saving `creator-profile.md` as output should now be `cast-profile.md`.

### Check R10: Phase 3.5 Hard Block Enforcement
**Pattern:** Pipeline allowing Phase 4 without Phase 3.5 validation
**Expected:** Skill files and agent.md both describe Phase 3.5 as mandatory before Phase 4, using "HARD BLOCK" or "cannot proceed" language. No skip/override option exists.
**How to verify:**
1. Search skill files for "Phase 3.5" — must exist with "HARD BLOCK" nearby
2. Search agent.md for "Phase 3.5" — must exist with "HARD BLOCK" nearby
3. Search skill files Phase 3.5 section for "skip" — should return 0 matches
4. Verify Phase 4 Step 4.1 does NOT have optional ref check with skip option

### Check R11: Reference Naming Convention Consistency
**Pattern:** Reference image filenames across all operational files
**Expected:** All reference image filenames follow the naming conventions from `global-promo-config.md` Section 11:
- Cast: `ref/cast-c{N}-face.png`, `ref/cast-c{N}-body.png`, `ref/cast-c{N}-costume.png`
- Product: `ref/product-{name}.png`
- Environment: `ref/env-{location}.png`
- Brand: `ref/brand-{asset}.png`
- Costume: `ref/costume-{institution}.png`
**How to verify:** Search all operational files for `ref/` image references — all must match one of the 7 naming patterns above. No `ref/creator-*` or `ref/ref-*` patterns should remain.

### Check R12: Language Selection Consistency
**Pattern:** Language handling across pipeline files
**Expected:** Skill files have Step 1.0 Language Selection with 3 options. global-promo-config.md Section 1 has Language Options table with Bahasa Indonesia/English/Bilingual. agent.md mentions language capability. Strategic brief template has `Language:` field. Phase 2 references narration_language.
**How to verify:**
1. Search skill files for "Step 1.0" and "Language Selection" — must exist
2. Search global-promo-config.md for "Language Options" — must have 3-row table
3. Search agent.md for "language" in capabilities — must exist
4. Search skill files Step 1.8 for "Language:" — must be in strategic brief template
5. Search skill files Phase 2 for "narration_language" — must reference it

### Check R13: Tone System Consistency
**Pattern:** Tone handling across pipeline files
**Expected:** Skill files have Step 1.7b Tone Selection with 6 options (humorous, serious, professional, inspirational, casual, edgy). global-promo-config.md Section 13 has Tone Impact Matrix with same 6 tones. script-to-scene-bridge.md has tone-to-cinematography mapping (Section 10) with same 6 tones. agent.md mentions tone capability.
**How to verify:**
1. Search skill files for "Step 1.7b" and "Tone" — must exist with 6 options
2. Search global-promo-config.md for "Tone Impact Matrix" — must have 6 tone columns
3. Search script-to-scene-bridge.md for "Tone-to-Cinematography" — must have Section 10 with 6 tones
4. Verify same 6 tone keywords appear in all 3 files (humorous, serious, professional, inspirational, casual, edgy)

### Check R14: VEO No Real Person Names in `says:`
**Pattern:** Real person names used in VEO `says:` syntax across operational files
**Expected:** All VEO dialogue examples and templates use generic roles (`Host says:`, `Presenter says:`, `Speaker says:`), never real person names. NB2 prompts may still use real names.
**How to verify:**
1. Search VEO prompt templates in `script-to-scene-bridge.md` Section 4 for `says:` — should only have generic roles
2. Search `02-veo-production-guide.md` for `says:` examples — should use generic roles
3. Search all operational files for `alisadikin` or `Ali says:` — should return 0 matches
4. Verify `global-promo-config.md` Section 5 `dialogue_syntax` uses `Host says:` not `[Character] says:`

### Check R15: VEO No Em Dash in Audio Text
**Pattern:** Em dash `—` in VEO dialogue/voiceover text across templates
**Expected:** All VEO prompt templates specify "NO em dash" rule. global-promo-config.md has `em_dash_forbidden: true`.
**How to verify:**
1. Search `global-promo-config.md` for `em_dash_forbidden` — should exist and be `true`
2. Search `script-to-scene-bridge.md` VEO templates for "NO em dash" — should appear in every template
3. Search `02-veo-production-guide.md` for em dash rule — should exist in Audio section

### Check R16: VEO B-Roll Has Voice-over Narrator
**Pattern:** B-Roll VEO templates missing voiceover narration
**Expected:** All B-Roll VEO templates use `Voice-over narrator, [tone]: text` syntax (NOT bare `Voiceover:`). Every B-Roll has `POST-PROD VO:` backup. No silent B-Roll.
**How to verify:**
1. Search `script-to-scene-bridge.md` B-Roll template for `Voice-over narrator` — should exist
2. Search `script-to-scene-bridge.md` for bare `Voiceover:` in templates — should return 0 matches (except in "DON'T" examples)
3. Search `script-to-scene-bridge.md` for `POST-PROD VO` — should appear after every B-Roll template
4. Search `global-promo-config.md` for `voiceover_syntax` — should be `Voice-over narrator, [tone]: text`

### Check R17: VEO Face-Dominant Scenes Use Single I2V
**Pattern:** VEO mode selection allowing First+Last Frame for face-dominant scenes
**Expected:** Decision tree in `03-workflow-pipeline.md` and mode selection in `script-to-scene-bridge.md` route face >30% scenes to single I2V, NOT First+Last Frame. Presenter template specifies Single I2V mode.
**How to verify:**
1. Search `03-workflow-pipeline.md` decision tree for "face" or "single I2V" — should describe safety filter rule
2. Search `script-to-scene-bridge.md` Step 3 for face-dominant routing — should exist
3. Search `script-to-scene-bridge.md` Presenter template for "Single I2V" — should exist
4. Search `02-veo-production-guide.md` for face-dominant safety rule — should exist

### Check R18: VEO No Face Ref Filenames
**Pattern:** Face reference filenames (`ref/cast-c{N}-face.png`) appearing in VEO prompt templates
**Expected:** VEO templates use generic continuity language (`Maintain visual continuity with reference frame character appearance`), NOT explicit filenames. Face ref filenames belong ONLY in NB2 templates.
**How to verify:**
1. Search `script-to-scene-bridge.md` Section 4 VEO templates for `ref/cast-c` — should return 0 matches in VEO templates (OK in NB2 Section 3 templates)
2. Search `02-veo-production-guide.md` I2V template for `ref/cast-c` — should return 0 matches
3. Search `global-promo-config.md` Section 16 for NB2 vs VEO distinction — should exist

### Check R19: Scene Logic Realism Checklist
**Pattern:** Scene Logic Realism 7-point checklist in prompt quality gates
**Expected:** `script-to-scene-bridge.md` has Section 7B with 7-point realism checklist. Skill files and agent.md reference it in hard rules. Quality gate includes scene realism check.
**How to verify:**
1. Search `script-to-scene-bridge.md` for "Scene Logic Realism" — must exist in Section 7B
2. Search `script-to-scene-bridge.md` Section 7B for all 7 check names: environment accuracy, human behavior realism, data consistency, uniform ranks, explicit negatives, reference photos, timeline/shift
3. Search skill files for "Scene Logic Realism" — must exist in hard rules
4. Search agent.md for "Scene Logic Realism" or "7-point" — must exist in hard rules

### Check R20: Character Portrait-First Rule
**Pattern:** Character portrait-first enforcement across files
**Expected:** `global-promo-config.md` Section 18 has "Character Portrait-First Rule" as HARD BLOCK. Skill files and agent.md reference it in hard rules. Phase 4A quality gate checks for it.
**How to verify:**
1. Search `global-promo-config.md` for "Character Portrait-First" — must exist in Section 18
2. Search `global-promo-config.md` for "2+ scenes" near "standalone portrait" — must exist
3. Search skill files for "portrait-first" — must exist in hard rules
4. Search agent.md for "portrait-first" — must exist in hard rules

### Check R21: Narrative Arc Consistency
**Pattern:** Narrative arc consistency rules in prompt templates
**Expected:** `script-to-scene-bridge.md` has Section 7C with narrative arc rules. NB2/VEO templates include `NARRATIVE CONTEXT:` block. Skill files and agent.md reference it.
**How to verify:**
1. Search `script-to-scene-bridge.md` for "Narrative Arc Consistency" — must exist in Section 7C
2. Search `script-to-scene-bridge.md` for "NARRATIVE CONTEXT:" — must appear in NB2 start frame template AND VEO templates
3. Search `script-to-scene-bridge.md` for "visual breadcrumb" — must exist in Section 7C
4. Search skill files for "Narrative arc consistency" — must exist in hard rules
5. Search agent.md for "Narrative arc" — must exist in hard rules

### Check R22: Location-Aware Domain Deep Research
**Pattern:** Location context + domain research steps in pipeline before scripting
**Expected:** Skill files have Step 1.2c "Location & Setting Context" and Step 1.2d "Domain Deep Research" with location-aware WebSearch protocol (6 queries). `global-promo-config.md` has Section 24 with location-specific research config including "Local Differentiators" table. Agent.md references location-aware domain research. NB2/VEO templates include `DOMAIN CONTEXT:` line.
**How to verify:**
1. Search skill files for "Step 1.2c" and "Location" — must exist
2. Search skill files for "Step 1.2d" and "Domain Deep Research" — must exist
3. Search `global-promo-config.md` for "Section 24" and "Location" — must exist with location-specific queries
4. Search `global-promo-config.md` for "Local Differentiators" — must exist in Section 24
5. Search agent.md for "location-aware" or "domain research" — must exist in capabilities and hard rules
6. Search `script-to-scene-bridge.md` for "DOMAIN CONTEXT:" — must appear in NB2/VEO templates
7. Search skill files strategic brief template for "Domain Knowledge" — must exist

### Check R23: NB2 Identity Lock Filename-Only Syntax
**Pattern:** NB2 identity lock lines or reference image mentions in prompt body templates using `ref/` folder prefix
**Expected:** All NB2 prompt body text (identity lock syntax, reference image injection lines, prompt templates/examples) uses bare filenames only — NO `ref/` or `keyframes/` folder prefix. The `ref/` prefix is valid ONLY in: `**Output →** ref/` lines (filesystem paths), upload table paths, directory structure docs, and ref naming convention docs. Inside NB2 prompt body text, `ref/filename.png` fails because NB2 matches by uploaded filename, not path.
**How to verify:**
1. Search `script-to-scene-bridge.md` Section 3 NB2 templates for `Maintain exact facial identity from reference image: ref/` — should return 0 matches (must use bare filename)
2. Search `script-to-scene-bridge.md` Section 3 NB2 templates for `Using reference image ref/` — should return 0 matches
3. Search skill files Phase 4B prompt instructions for `inject \`ref/` — should return 0 matches (continuity injection must use bare filename in prompt body)
4. Search agent.md hard rules for `Maintain exact facial identity from reference image: ref/` — should return 0 matches
5. Verify skill files have hard rule stating "NB2 identity lock: filename only (NO folder prefix like ref/ or keyframes/)"
6. Verify skill files Scene Keyframe Quality Gate has check for filename-only identity lock

### Check R24: Inline-Only Reference Pattern
**Pattern:** NB2 prompt templates or examples using header block pattern for reference images instead of inline-only pattern
**Expected:** All NB2 prompt templates and examples use inline-only reference pattern — filenames appear inline with the element they describe (identity lock inline with character, object ref inline with element, continuity ref inline with continuity statement). No header blocks like `Using reference image xxx.png for [purpose]` at top of prompts. No standalone identity lock lines separated from character description. No duplicate filenames within same prompt. Skill files have hard rule for inline-only pattern.
**How to verify:**
1. Search `script-to-scene-bridge.md` Section 3 NB2 templates for `Using reference image` as standalone header lines — should return 0 matches in templates (only valid in legacy few-shot "BAD" examples)
2. Search `global-promo-config.md` Section 16 for "header block" — should exist in BANNED patterns list
3. Search `global-promo-config.md` Section 16 for "Inline-Only" or "inline-only" — should exist as section title or rule
4. Verify skill files have hard rule stating "Inline-only reference pattern"
5. Verify skill files Scene Keyframe Quality Gate has checks for: no header blocks, no standalone identity lock lines, no duplicate filenames
6. Verify agent.md hard rules include inline-only reference pattern
7. Verify `video-prompt-reviewer.md` has checklist item for inline-only pattern verification

---

## Output Format

```
=== Video Engine Validation Report ===

--- Script Checks (--script) ---
Check S1: 7-Beat Arc Completeness ........... PASS (8/8 beats)
Check S2: Forbidden Words ................... PASS (0 matches)
Check S3: Human Consequence per Feature ...... PASS
Check S4: Hook "So What?" Test .............. PASS
Check S5: CTA Quality ....................... PASS
Check S6: No Jargon Without Translation ...... PASS
Check S7: Narration Language Consistency ...... PASS
Check S8: Tone Consistency .................. PASS
Check S9: Duration Target ................... PASS

--- Image Checks (--image) ---
[Part A: Prompt Text]
Check I1: Aspect Ratio Triple ............... PASS
Check I2: Identity Lock Filename-Only ........ PASS
Check I3: Inline-Only Reference Pattern ...... PASS
Check I4: Ref-to-Prompt Body Binding ......... PASS
Check I5: Output Filename ................... PASS
Check I6: DOMAIN CONTEXT Populated .......... PASS
Check I7: NARRATIVE CONTEXT Block ........... PASS
Check I8: Scale Specs for Props .............. PASS
Check I9: Costume Verbatim from Cast Profile . PASS
Check I10: Sequential Dependency Chain ....... PASS
[Part B: Actual Images (Multimodal)]
Check I11: Read Keyframe Images ............. PASS ({N} images)
Check I12: Aspect Ratio Match ............... PASS
Check I13: Character Face Consistency ........ PASS
Check I14: Lighting Consistency .............. PASS
Check I15: Costume Match .................... PASS
Check I16: Environment Match ................ PASS

--- Video Checks (--video) ---
Check V1: VEO Mode Correct ................. PASS
Check V2: Face-Dominant Single I2V .......... PASS
Check V3: Audio 3-Layer Complete ............ PASS
Check V4: Dialogue Generic Role ............. PASS
Check V5: B-Roll VO Syntax ................. PASS
Check V6: B-Roll Has VO + Backup ........... PASS
Check V7: No Em Dash in Audio .............. PASS
Check V8: No Face Ref Filenames ............ PASS
Check V9: Resolution for Extendable ......... PASS
Check V10: Extension References ............. PASS
Check V11: Transition Instructions .......... PASS
Check V12: NB2→VEO Consistency .............. PASS

--- Reference Checks (--refs) ---
Check R1: VEO Mode Mutual Exclusivity ...... PASS
Check R2: Audio Mandatory Rule .............. PASS
Check R3: Dialogue Colon Syntax ............. PASS
Check R4: Resolution Extend Rule ............ PASS
Check R5: Reference File Count .............. PASS (23/23)
Check R6: 7-Beat Arc Completeness ........... PASS (8/8 beats)
Check R7: Forbidden Words List .............. PASS (8/8 words)
Check R8: Face Minimum Percentage ........... PASS (30%)
Check R9: Cast System Consistency ........... PASS (0 legacy refs)
Check R10: Phase 3.5 Hard Block ............. PASS
Check R11: Ref Naming Convention ............ PASS (7/7 patterns)
Check R12: Language Selection Consistency .... PASS
Check R13: Tone System Consistency .......... PASS
Check R14: VEO No Real Names in says: ....... PASS
Check R15: VEO No Em Dash in Audio .......... PASS
Check R16: VEO B-Roll Has VO Narrator ....... PASS
Check R17: VEO Face-Dominant Single I2V ..... PASS
Check R18: VEO No Face Ref Filenames ........ PASS
Check R19: Scene Logic Realism Checklist .... PASS (7/7 points)
Check R20: Character Portrait-First Rule .... PASS
Check R21: Narrative Arc Consistency ......... PASS
Check R22: Domain Deep Research ............. PASS
Check R23: NB2 Identity Lock Filename-Only .. PASS
Check R24: Inline-Only Reference Pattern .... PASS

Result: {passed}/{total} checks passed
```

If any check FAILS, show:
```
Check {ID}: {Name} ......................... FAIL
  Found in: {file}:{line}
  Expected: {expected}
  Actual: {actual}
  Fix: {suggested fix}
```
