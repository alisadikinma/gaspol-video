# AI Video Promo Engine — Claude Project Instructions

## 🧠 Vault Context Link

Skill library — agnostic terhadap project (IRN / SPARKFLUENCE / etc).

Pre-read kalau perlu konteks lintas-skill:
- `30-Knowledge/video-pipeline-shared.md` — 6-phase, VEO/Seedance/Kling craft
- `30-Knowledge/image-gen-shared.md` — NB2 prompt engineering, anti-AI-look
- `20-Projects/claude-plugin/README.md` — skill ecosystem overview
- `10-Identity/voice-tone.md` — user-facing copy / docs

JANGAN hardcode project-specific values (nama klien, fleet count, dll). Pakai `{{placeholder}}` syntax.

## Project Overview

Claude Code plugin that carries a promotional video from brainstorm to a finished, mixed file: script, image prompts (NB2), video prompts (VEO 3.1 / Seedance 2.0 / Kling 3.0), Remotion shots for anything that must be readable, then post-production and packaging. 7 production skills + 1 orchestrator + 2 utility skills + 2 agents + 10 CLI tools + 33 reference documents as RAG knowledge base.

**Core Value:** Anyone — video agencies, freelancers, brand owners — can produce professional 2-3 minute promotional videos by following the generated production plan.

## Commands

| Command | Description |
|---------|-------------|
| `/video-full` | End-to-end pipeline orchestrator (brainstorm → script → images → video) |
| `/video-brainstorm` | Phase 1: brainstorm, cast, product, location, domain research |
| `/video-script` | Phase 2-3.5: script generation, scene breakdown, reference collection |
| `/video-image` | Phase 4: NB2 asset library + scene keyframes |
| `/video-gen` | Phase 5: image review + VEO video prompts |
| `/video-explainer` | Phase 4.5: coded Remotion shots for scenes that must be readable |
| `/video-post` | Phase 6: voice-over, assembly, SFX, subtitles, music, final mix |
| `/video-package` | Phase 7: locked title, three thumbnail bets, description |
| `/video-validate` | Unified validator: `--script` / `--image` / `--video` / `--refs` / `--all` |
| `/video-explainer` | Phase 4.5: Remotion shots for scenes that must be readable |
| `/video-post` | Phase 6: voice-over, edit, SFX, subtitles, music, final mix |
| `/video-package` | Phase 7: title, thumbnail bets, description |
| `/video-add-platform` | Scaffold new AI video platform support |

## Architecture

| Path | Purpose |
|------|---------|
| `.claude-plugin/plugin.json` | Plugin metadata (name, version, author) |
| `hooks/hooks.json` | SessionStart hook definition |
| `hooks/session-start.sh` | Session start script — announces available skills |
| `skills/video-brainstorm/SKILL.md` | Phase 1 — brainstorm, cast, product, location, domain research |
| `skills/video-script/SKILL.md` | Phase 2-3.5 — script, scene breakdown, reference collection |
| `skills/video-image/SKILL.md` | Phase 4 — NB2 asset library + scene keyframes |
| `skills/video-gen/SKILL.md` | Phase 5 — image review + VEO video prompts |
| `skills/video-full/SKILL.md` | Orchestrator — runs all 4 production skills in sequence |
| `skills/video-explainer/SKILL.md` | Phase 4.5 — Remotion shots for explainer scenes |
| `skills/video-post/SKILL.md` | Phase 6 — five post-production passes, clips to a finished file |
| `skills/video-package/SKILL.md` | Phase 7 — title, thumbnail bets, description; rendering routed to the image plugin |
| `skills/video-validate/SKILL.md` | Unified validator (--script / --image / --video / --refs / --all) |
| `skills/video-explainer/SKILL.md` | Phase 4.5 — Remotion explainer shots (scenes with legible text) |
| `skills/video-post/SKILL.md` | Phase 6 — five passes: VO, edit, SFX, subtitles+music, mix |
| `skills/video-package/SKILL.md` | Phase 7 — title, thumbnail bets, description |
| `skills/video-add-platform/SKILL.md` | Scaffold new video platform support |
| `tools/` | 10 zero-dependency CLI tools for phases 4.5-7 (python3 stdlib + node builtins + ffmpeg) |
| `templates/remotion/` | Remotion shot template, brand token placeholder, workspace scaffolder |
| `media/sfx/library/` | SFX recipes (`palette.json`); clips are generated per install, never committed |
| `media/music/library/` | Music mood palette mapped to the six tones; tracks never committed |
| `.env.example` | Names of the environment variables the tools read. Never their values |
| `agents/video-engine-agent.md` | Subagent for batch/complex video production (6-phase pipeline) |
| `agents/video-prompt-reviewer.md` | Independent validator — reviews NB2/VEO prompt batches for quality |
| `reference/` | reference docs read on-demand by skill/agent |
| `tools/` | Executable helpers for Phase 6 (stdlib Python + ESM Node, no installs) |
| `tests/` | `bash tests/run.sh` — consistency checks, python unittest, node --test |
| `README.md` | Repo README |
| `LICENSE` | MIT license |

### Reference Files

#### Storytelling & Script Generation (12 files)

| File | When Used |
|------|-----------|
| `storytelling_script_gen/project-instruction.md` | ALWAYS for script generation — master operating system, 2-phase state machine, 9 commandments (v2.2.0+), 7-beat arc + 6-stage user framework alias |
| `storytelling_script_gen/F1_Audience_Psychology_Matrix.md` | Target market selection — C-Level, VP/Director, Manager, IC, End Consumer psychographics |
| `storytelling_script_gen/F2_Narrative_Arc_and_Video_Typology.md` | Narrative arc selection — 7-beat universal arc, 12 video types, duration mapping |
| `storytelling_script_gen/F3_Cinematic_AV_Production_Rules.md` | Lighting grammar, audio design, camera directions for script |
| `storytelling_script_gen/F4_EV_Persona_Matrix.md` | CONDITIONAL — only when product is EV-related |
| `storytelling_script_gen/F5_Hook_Vault.md` | Hook selection — 100 hooks in 5 categories |
| `storytelling_script_gen/F6_CTA_Vault.md` | CTA frameworks per awareness level |
| `storytelling_script_gen/F7_Foreshadow_and_Peak_Engineering.md` | Psychological techniques for tension and peak moments |
| `storytelling_script_gen/F8_Awareness_Level_Routing.md` | 5 awareness levels — routes to correct narrative strategy |
| `storytelling_script_gen/F9_Platform_Adaptation_Matrix.md` | Platform specs — YouTube, LinkedIn, IG, TikTok, Twitter |
| `storytelling_script_gen/F10_Modular_Asset_and_AB_Testing.md` | Modular asset creation and A/B testing strategy |
| `storytelling_script_gen/F11_Pattern_Interrupt_and_Retention.md` | Pattern interrupt techniques and retention optimization |

#### Image & Video Production (9 files)

| File | When Used |
|------|-----------|
| `image-video-gen/00-index.md` | ALWAYS for image/video — production stack overview, critical constraints |
| `image-video-gen/01-nb2-image-generation.md` | NB2 image prompts — parameters, resolution, identity lock, material shaders, text rendering |
| `image-video-gen/02-veo-production-guide.md` | VEO 3.1 video prompts — specs, camera movement, I2V motion, lip sync, extensions, audio |
| `image-video-gen/03-workflow-pipeline.md` | NB2 → VEO pipeline — decision tree, handoff rules, extension chain, "Last Frame Secret" |
| `image-video-gen/04-cinematography-lookup.md` | Emotion → complete setup mapping (lighting, lens, film stock, atmosphere, camera motion) |
| `image-video-gen/05-creator-and-holidays.md` | Ali Sadikin as cast slot, cast-c{N} naming, holiday palettes, cultural context |
| `image-video-gen/06-directing-and-performance.md` | Film directing grammar — 180° rule, gaze direction, blocking, vocal performance, continuity supervision |
| `image-video-gen/07-seedance-production-guide.md` | Seedance 2.0 video prompts — native 2K, @ reference system, dual-branch audio, modes, materials |
| `image-video-gen/08-kling-production-guide.md` | Kling 3.0 video prompts — native 4K, 5-part formula, multi-shot storyboard (6/15s), motion control, omni audio (5 langs incl mixed-language scene). **Primary** Kling reference (curated by Claude from 10-source WebSearch + UI ground truth) |
| `image-video-gen/08b-kling-notebooklm-briefing.md` | Kling 3.0 NotebookLM-distilled Briefing Doc — independent cross-validation of 08-kling guide, contains efficiency data (rerolls/credit savings), Elements 3.0 system, 5-layer prompt formula breakdown. **Supplementary** RAG layer #2 (auto-generated from notebook `kling-prod`, regenerate via `nlm report create kling-prod`) |
| `image-video-gen/09-voice-consistency-workflow.md` | **Cross-platform** voice-over consistency — applies to VEO 3.1 + Seedance 2.0 + Kling 3.0. 3 solution paths (Path A native voice lock per platform, Path B universal ElevenLabs post-prod, Path C single VO + sync), prompt-level discipline rules, hybrid workflow per video type, plugin integration spec for Phase 5 Step 5.0. **MANDATORY** for any video with >1 scene or character voice continuity. |
| `image-video-gen/project-instruction.md` | Image/video project instructions — critical rules, example workflows |

#### Post-Production (Phase 6)

| File | When Used |
|------|-----------|
| `post-production/10-post-production-pipeline.md` | ALWAYS for Phase 6 — pass order, `{output_folder}` contract, every plan schema, A/V duration gate, degradation policy |
| `post-production/15-packaging.md` | Phase 7 — Views = Reach x CTR, three bets on three levers, honesty guardrail, calibration honesty, hand-off to the image plugin |
| `post-production/12-remotion-explainer.md` | Phase 4.5 — scaffolding the workspace, the rules that stop a render crashing, brand from the project, timing from the narration, verify-by-looking, cutaway vs overlay |
| `post-production/17-music-bed.md` | Phase 6 pass 4 — deriving the track from the script's music direction and tone, sitting 12 dB under the voice by measurement, segment fades and short-track handling, why the music pass fails soft while the A/V gate blocks |
| `post-production/16-subtitles-and-captions.md` | Phase 6 pass 4 — caption text from the script (recognizer times only), derived keyterms, wrap-or-split rule, font and contrast guards, why this does not conflict with the `no subtitles` prompt negative |
| `post-production/14-sfx-design.md` | Phase 6 pass 3 — deriving cues from DOMAIN CONTEXT and cultural research, library-first sourcing, gain calibration incl. the transient correction, the four ways an audibility measurement lies, density ceiling, hard audit gate |
| `post-production/13-ffmpeg-edit.md` | Phase 6 pass 2 — trim vs pad vs regenerate, inserting explainer shots, why every segment is normalised before concat, the A/V duration gate, playable transcode |
| `post-production/11-voice-cast-and-vo.md` | Voice per cast member — `VOICE:` block, `tts` vs `native+changer`, VO-first duration budgeting, prosody stitching, Voice Changer 0.05s drift rule, prompt-level discipline |

#### Global Config & Bridge (3 files)

| File | When Used |
|------|-----------|
| `global-promo-config.md` | ALWAYS (read FIRST) — single source of truth for all configurable values (Section 29 = post-production defaults) |
| `creator-profile-system.md` | Phase 1 (Cast Builder) — multi-character cast profiles, institution detection, generic + Ali Sadikin preset |
| `script-to-scene-bridge.md` | Phase 3 (Scene Breakdown) — script → scene list → VEO mode → image/video prompts |

## Key Concepts

### Production Pipeline (6-Phase Full Pipeline)

The plugin operates as a single end-to-end pipeline with mandatory approval gates between phases:

```
Phase 1: BRAINSTORM          → Output: strategic-brief.md + cast-profile.md
  ├─ Language selection (Bahasa Indonesia / English / Bilingual)
  ├─ Cast builder (1-5 characters, Utama/Pendamping roles)
  ├─ Institution detection + costume confirmation
  ├─ Product discovery + tech doc upload
  ├─ **Location & setting context (city, country, setting type)**
  ├─ **Domain Deep Research (6 location-aware WebSearch queries)**
  ├─ Target market, awareness level, platform selection
  ├─ Emotional core discovery
  ├─ Storyline input (user freeform / brainstorm / reference) + 7-beat arc mapping
  ├─ Tone/mood selection (Humorous / Serious / Professional / Inspirational / Casual / Edgy)
  └─ [USER APPROVAL GATE]

Phase 2: SCRIPT               → Output: av-script.md
  ├─ Generate 2-3 min video script
  ├─ A/V table with beat labels + timing
  ├─ Narration/dialogue per scene
  ├─ Audio direction (SFX, music, ambient)
  └─ [USER APPROVAL GATE]

Phase 3: SCENE BREAKDOWN       → Output: scene-plan.md
  ├─ Script → Scene list (auto-calculated)
  ├─ VEO mode per scene (Frame / Ingredients / Extend)
  ├─ Duration allocation
  ├─ Extension strategy
  └─ [USER APPROVAL GATE]

Phase 3.5: REFERENCE COLLECTION  → Output: ref-manifest.md
  ├─ Auto-derive from scene-plan.md + cast-profile.md
  ├─ Present manifest checklist (5 categories)
  ├─ Cultural location web search (5 facts per location via WebSearch)
  ├─ Batch NB2 prompt generation for missing refs (6 categories)
  ├─ User generates/uploads to {project}/ref/
  ├─ Validate ALL refs exist
  └─ [HARD BLOCK — 100% required before Phase 4]

Phase 4A: ASSET LIBRARY (NB2)   → Output: nb2-reference-prompts.md
  ├─ Auto-scan ref/ folder (user photos = ground truth)
  ├─ Recurring element detection (2+ scenes → standalone asset) — **v2.2.0+: combined with UNIQUENESS filter (skip COMMON-tier generic items) per global-promo-config.md §26**
  ├─ Dynamic tier assignment with dependency graph
  ├─ Tier-by-tier generation with validation gates
  ├─ Extended categories: cast, vehicles, objects, products, product closeups, environments, UI composites
  ├─ Product closeup + location photo enforcement
  ├─ Climate-aware costume check
  └─ [USER APPROVAL GATE]

Phase 4B: SCENE KEYFRAMES (NB2)  → Output: image-prompts.md
  ├─ **BATCH BY ACT (max 5 scenes/batch)**
  ├─ Per-batch: generate → validate (prompt-reviewer agent) → approve
  ├─ Start frame + End frame per scene (Frame mode)
  ├─ Ingredient images (Ingredients mode)
  ├─ EVERY visual element references Phase 4A asset (no text-only descriptions)
  ├─ Aspect ratio triple enforcement
  ├─ Output filename per prompt
  ├─ Ref-to-prompt body binding
  ├─ UI text localization
  └─ [USER APPROVAL GATE]

Phase 5: VIDEO PROMPTS (VEO)   → Output: video-prompts.md
  ├─ **BATCH BY ACT (max 5 scenes/batch)**
  ├─ Per-batch: generate → validate (prompt-reviewer agent) → approve
  ├─ Per-scene VEO 3.1 prompts
  ├─ Extension prompts (same-scene continuity)
  ├─ Audio specs (dialogue + SFX + ambient)
  ├─ Transition end instructions
  ├─ Post-production checklist
  └─ [FINAL OUTPUT]
```

### Output Modes

- **`--full`** (default): Full production plan with cast-profile.md, ref-manifest.md, scene breakdown, storyboard notes, NB2 prompts, VEO prompts, audio specs, extension strategy, post-production checklist
- **`--quick`**: Copy-paste ready prompts only (NB2 + VEO per scene, no production plan)

### Production Stack

- **Image Model**: Nano Banana 2 (NB2) — Gemini 3.1 Flash Image
- **Video Model (Primary)**: VEO 3.1 — 720p/1080p, 8s clips, 148s extension chain
- **Video Model (Alt)**: Seedance 2.0 — native 2K, 15s clips, @ reference system, dual-branch AV
- **Video Model (Alt)**: Kling 3.0 — 720p/1080p UI (4K via API), **per-second duration 3-15s** (pick exact second), multi-shot storyboard (6 shots within chosen duration), motion control, omni audio (lip-sync 5 langs EN/ZH/JA/KO/ES, mixed-language scene unique). **Bahasa Indonesia: ✅ Voice-over narrator native, ❌ on-screen lip-sync** — perfect for B-Roll ID, use VEO for face-front ID dialogue.
- **Pipeline (VEO)**: NB2 image → VEO First+Last Frame / Ingredients → VEO Extend
- **Pipeline (Seedance)**: NB2 image → Seedance @Image refs + Omni mode → Seedance @Video extend
- **Pipeline (Kling)**: NB2 image → Kling I2V / First+Last / Multi-Shot Storyboard / Motion Control (no native extension; restart with new NB2 anchor for long-form)

### Critical Audio Rules

- Audio is NEVER optional — unspecified = VEO guesses random sounds
- Presenter scenes: `Host says: text` (generic role, colon syntax) — NEVER real person names (safety filter). Lip sync ON, face >30% frame
- B-Roll scenes: `Voice-over narrator, [tone]: text` — NEVER bare `Voiceover:` (lip-syncs to visible character). Every B-Roll MUST have VO narration + `> POST-PROD VO:` backup
- NEVER use em dash `—` in dialogue/voiceover text — VEO audio engine mistranslates. Use `,` or `. `
- Always add: `no subtitles, no audience sounds, no text overlays`
- VEO prompts: NO face ref filenames (`cast-c{N}-face.png`) — use generic continuity language. Face refs are NB2-only.
- NB2 prompt body text: use filename only (e.g., `cast-c1-face.png`), NEVER add `ref/` folder prefix — NB2 matches by uploaded filename, not path. All filenames MUST be inline with the element they describe (no header blocks, no standalone lines, each filename MAX 1x per prompt).
- See `image-video-gen/02-veo-production-guide.md` for full audio specs, safety filter rules, and duration rules

### VEO 3.1 Mode Selection (Mutual Exclusivity + Safety Filter)

```
Need consistent CHARACTER across shots?
├── YES → "Ingredients to Video" (1-3 ref images)
│         Cannot combine with First+Last Frame
│
└── NO, need controlled TRANSITION between two states?
    ├── YES → Does scene have FACE >30% of frame?
    │         ├── YES → "Single I2V" (start frame only)
    │         │         Safety filter rejects 2 face images
    │         │
    │         └── NO → "First + Last Frame" (Keyframe Control)
    │                   Generate START (NB2) + END (NB2)
    │                   Only for faceless scenes (dashboards, products, environments)
    │
    └── NO, need to CONTINUE an existing clip?
        └── "Scene Extension" (Extend)
            Source must be VEO-generated, 720p only
            Uses final 1 second as context anchor
```

**CRITICAL: Ingredients ≠ First+Last Frame. They are MUTUALLY EXCLUSIVE. Pick ONE per generation.**
**SAFETY: First+Last Frame with 2 photorealistic face images → rejected as "prominent people." Use single I2V for face-dominant scenes.**

### Key Technical Rules

- **Resolution Rule:** Generate initial clip at **720p** if ANY extensions planned. 1080p = 8s only, CANNOT extend.
- **NB2 aspect ratio MUST match VEO target** — mismatch = edge hallucination.
- **NB2 Prompt Formula:** `Subject/Material + Lighting Architecture + Camera/Lens + Campaign Context`
- Scene count auto-calculated from script beats. Scene → VEO mode mapping in `script-to-scene-bridge.md`.
- VEO specs (resolution, duration, extensions, prompt limits) in `image-video-gen/02-veo-production-guide.md`.
- NB2 parameters (CFG, denoise, thinking mode, identity lock) in `image-video-gen/01-nb2-image-generation.md`.
- **NB2 Identity Lock Syntax:** `Maintain exact facial identity from reference image: filename.png` — use bare filename only (NO `ref/` or `keyframes/` prefix). NB2 matches uploaded files by filename; `ref/cast-c1-face.png` fails to match the uploaded `cast-c1-face.png`. **v2.2.0+: Max 5 inline references per Phase 4B prompt (combined faces + bodies + costumes + objects + envs + UI), replaces old "Max 3 identity locks per scene" (which applied to faces only). See global-promo-config.md §26.4.**
- **Inline-Only Reference Pattern:** All NB2 reference image filenames MUST appear inline with the element they describe, NOT in header blocks. Each filename MAX 1x per prompt. Three categories: (1) identity lock inline with character: `[Name] (Maintain exact facial identity from reference image: cast-c1-face.png) in uniform...`, (2) object/env ref inline: `...the monitor — EXACTLY matching ui-anpr-screen.png: interface...`, (3) scene continuity inline: `...continuation from scene-{NN-1}-end.png — maintaining position...`. BANNED: header blocks (`Using reference image xxx.png for [purpose]`), standalone identity lock lines, duplicate filenames.
- **Required Reference Images Table Placement:** Table MUST appear directly BELOW each image/prompt heading, BEFORE the prompt body text — NOT above the heading, NOT after the prompt body. Use bare filenames only (NO `ref/` prefix). Add note: "Upload all files to `{project}/ref/` folder."
- **No Em Dash in VEO Audio Text:** NEVER use `—` (em dash) in `says:` or `Voice-over narrator:` text — VEO audio engine mistranslates it. Replace with `,` or `. ` in all dialogue/voiceover template placeholders.
- Cinematography defaults per content type in `image-video-gen/04-cinematography-lookup.md`.

### Smart Context Loading

Each phase loads ONLY the reference files it needs — NOT all 23. This prevents context window overflow.

| Phase | Files Loaded | Max |
|-------|-------------|-----|
| Phase 1 | global-promo-config, creator-profile-system, F1, F8 | 4 |
| Phase 2 | global-promo-config, project-instruction, F2-F11 (excl F4 unless EV) | 10-11 |
| Phase 3 | global-promo-config, script-to-scene-bridge, 03-workflow | 3 |
| Phase 3.5 | global-promo-config, creator-profile-system | 2 |
| Phase 4A | global-promo-config, 01-nb2, script-to-scene-bridge (7B only) | 3 |
| Phase 4B | global-promo-config, 01-nb2, script-to-scene-bridge, 04-cinematography | 4 per batch |
| Phase 4.5 (explainer) | global-promo-config §29.5, 12-remotion-explainer | 2 per shot |
| Phase 5 (VEO) | global-promo-config, 02-veo, 03-workflow, 04-cinematography, 09-voice-consistency | 5 per batch |
| Phase 5 (Seedance) | global-promo-config, 07-seedance, 03-workflow, 04-cinematography, 09-voice-consistency | 5 per batch |
| Phase 5 (Kling) | global-promo-config, 08-kling, 03-workflow, 04-cinematography, 09-voice-consistency | 5 per batch |
| Phase 5 (Mixed) | global-promo-config, 02-veo + 07-seedance + 08-kling, 03-workflow, 04-cinematography, 09-voice-consistency | 7 per batch (one-time platform-guide load + voice workflow, then filter per scene) |
| Phase 6 pass 1 (audio) | global-promo-config §29, 11-voice-cast-and-vo | 2 |
| Phase 6 pass 2 (edit) | global-promo-config §29, 13-ffmpeg-edit | 2 |
| Phase 6 pass 3 (SFX) | global-promo-config §29, 14-sfx-design | 2 |
| Phase 6 pass 4 (subs+music) | global-promo-config §29-30, 16-subtitles-and-captions, 17-music-bed | 3 |
| Phase 6 pass 5 (final mix) | global-promo-config §29, 10-post-production-pipeline | 2 |
| Phase 7 (packaging) | global-promo-config §29, 15-packaging | 2 |

Phase 4B and 5 also load per-batch filtered data from output files (cast entries + scene entries for current batch only).

Phases 4.5, 6 and 7 stay small on purpose: each pass reads its own reference plus the plan file the
previous pass wrote, never the storytelling set. A post-production pass has no use for the hook vault.

### Prompt Reviewer Agent (Independent Validator)

After each batch in Phase 4B/5, a separate `prompt-reviewer` agent validates the output:
- **Fresh context** — no generation instructions, no storytelling files
- **Reads only:** batch prompts + cast-profile.md + scene-plan.md (ground truth)
- **Checks:** dependency chain, costume consistency, prop scale, camera angle, aspect ratio, 9-point realism, upload table completeness
- **Returns:** PASS/FAIL with per-prompt line-level feedback
- **On FAIL:** generator re-generates only failing prompts (max 2 retries)

This eliminates self-check bias — the validator has never seen the generation rules, so it cannot "explain away" violations.

### Location & Domain Deep Research (MANDATORY — Steps 1.2c + 1.2d)

AI is blind about specific product domains, AND domains are **location-specific**. RS Indonesia ≠ RS USA ≠ RS Japan. Factory di Cikarang ≠ Factory di Shenzhen. Same domain, completely different visuals — architecture, equipment brands, uniforms, signage, safety standards.

**Step 1.2c: Location Context** — Confirm location/setting BEFORE domain research:
- City/region, country, setting type (factory/hospital/port/office), indoor/outdoor

**Step 1.2d: Domain Deep Research** — 6 location-qualified WebSearch queries:

| # | Query | Purpose |
|---|-------|---------|
| 1 | `{domain} in {country} production process workflow` | Local process flow |
| 2 | `{domain} {country} equipment machines brands commonly used` | Local equipment brands |
| 3 | `{domain} {country} worker roles uniforms PPE requirements` | Local workforce, dress norms |
| 4 | `{domain} {location} facility layout photos` | Local architecture, interior |
| 5 | `{product_name} product interface dashboard features` | Product appearance |
| 6 | `{domain} {country} regulations standards signage` | Local safety signage, certifications |

Output saved to `strategic-brief.md` > Domain Knowledge section with **Local Differentiators** table (generic AI default vs actual local reality). Every NB2/VEO prompt includes `DOMAIN CONTEXT:` line with location-specific details.

**HARD RULES:**
- Location MUST be confirmed before domain research begins
- Domain research MUST complete before Phase 2 (Script)
- Domain research + cultural research (Step 3.5.2a) are COMPLEMENTARY

See `global-promo-config.md` Section 24.

### Scene Logic Realism (9-Point)

Every NB2/VEO prompt must pass 9 realism checks to prevent "stock photo generic" output:

1. **Environment Accuracy** — location matches cultural research, architecture/vegetation/signage match real location
2. **Human Behavior Realism** — workers work, supervisors supervise, no "standing and smiling at camera" in action scenes
3. **Data/Display Consistency** — dashboard numbers, ANPR readings, metrics consistent across all scenes
4. **Uniform & Rank Accuracy** — institutional uniforms match rank/role (supervisor ≠ operator uniform, correct epaulettes/stripes)
5. **Explicit Negatives** — prompt states what should NOT appear ("no outdoor elements" for indoor, "no sunlight" for night)
6. **Reference Photo Enforcement** — every element with ref/ image uses it, user photos = ground truth
7. **Timeline & Shift Consistency** — time-of-day/lighting matches across connected scenes, PPE matches shift

Full checklist and per-prompt algorithm in `script-to-scene-bridge.md` Section 7B.

### Character Portrait-First Rule

**Any character in 2+ scenes MUST have standalone face portrait generated FIRST in Phase 4A.** Text descriptions alone = different faces every time. Applies to cast members AND recurring named extras.

- Cast Pemeran Utama: face → body → costume → scene (mandatory chain)
- Cast Pemeran Pendamping: face → scene (minimum)
- Recurring extras (2+ scenes): face portrait in Phase 4A FIRST
- Scene keyframes MUST reference the portrait inline — NB2 injects `cast-c{N}-face.png` inline with character description (e.g., `[Name] (Maintain exact facial identity from reference image: cast-c{N}-face.png) — description...`), filename only (NO `ref/` prefix), VEO uses generic continuity

See `global-promo-config.md` Section 18.

### Narrative Arc Consistency

Connected scenes MUST explicitly reference each other. Every NB2/VEO prompt includes a `NARRATIVE CONTEXT:` block:

```
NARRATIVE CONTEXT:
  Previous: Scene {N-1} — {what happened}.
  This scene: {what happens now and WHY}.
  Next: Scene {N+1} — {what this scene sets up}.
  Visual breadcrumb: {shared element connecting adjacent scenes}.
  Emotional arc: {start emotion} → {end emotion}.
```

Key rules: name the connection, add visual breadcrumbs (shared props/screens/landmarks), state cause-effect chains, share environment references, maintain character state continuity, pin data labels in UI scenes. See `script-to-scene-bridge.md` Section 7C.

### Cast System (Multi-Character)

Supports 1-5 characters per video.

- **Pemeran Utama** (main, 1-3): FULL identity lock — face + body + costume ref MANDATORY
- **Pemeran Pendamping** (supporting, 0-2): PARTIAL identity lock — face ref MANDATORY, body/costume OPTIONAL
- **Ali Sadikin preset**: Pre-configured profile that fills 1 Pemeran Utama cast slot
- **Institution-aware costume**: Auto-detects institutional brand (KAI, Pelindo, BRI, etc.) and requires uniform reference images
- **Reference images**: `{project-folder}/ref/` — naming: `cast-c{N}-face.png`, `cast-c{N}-body.png`, `cast-c{N}-costume.png`
- See `creator-profile-system.md` for full cast builder details and institution keyword list

### Language Selection

Pipeline starts with language choice (Phase 1 Step 1.0):

| Option | Narration/Dialogue | NB2/VEO Prompts | Strategic Brief |
|--------|-------------------|-----------------|-----------------|
| Bahasa Indonesia | Indonesian | English (fixed) | Indonesian |
| English | English | English (fixed) | English |
| Bilingual | Indonesian + English tech terms | English (fixed) | Indonesian |

**Key rule:** NB2/VEO prompt structure ALWAYS stays English (technical requirement for AI models). Only narration text and `says:` dialogue follow user's language choice.

### Tone/Mood System

Selected in Phase 1 Step 1.7b. 6 tones (Humorous / Serious / Professional / Inspirational / Casual / Edgy) that affect script style, lighting, camera, music, and expression across ALL subsequent phases. Full impact matrix in `global-promo-config.md` Section 13.

### User Storyline Input

Phase 1 Step 1.7 offers 3 modes: **freeform** (user pastes storyline, AI maps to 7-beat arc), **brainstorm** (AI guides through pain points/USP/CTA), or **reference video** (user describes a video, AI extracts and adapts structure).

### Phase 3.5: Reference Image Validation Gate

Mandatory gate between Scene Breakdown (Phase 3) and Image Prompts (Phase 4).

**HARD BLOCK:** Cannot proceed to Phase 4 without ALL reference images validated.

**5 Reference Categories (all hard block):**

| # | Category | Naming Pattern | Required When |
|---|----------|---------------|---------------|
| 1 | Character (cast) | `ref/cast-c{N}-face.png`, `-body.png`, `-costume.png` | Any scene with character |
| 2 | Product | `ref/product-{name}.png` | Any scene showing product |
| 3 | Environment | `ref/env-{location}.png` | Any B-Roll or location-specific scene |
| 4 | Brand Assets | `ref/brand-{asset}.png` | Any scene with visible logo/UI/brand |
| 5 | Costume/Uniform | `ref/costume-{institution}.png` | When institution detected |

**Auto-derive logic:** Engine scans scene-plan.md + cast-profile.md → builds ref-manifest.md → user uploads → engine validates 100% → proceed.

**No skip. No override. No "lanjut dulu."**

### Cultural Location Research

Phase 3.5 web searches 5 facts per location (license plates, ethnicity, landmarks, architecture, climate). Without this, AI generates generic visuals — wrong plate numbers, wrong ethnicity, wrong architecture. Results inject into NB2 environment prompts and VEO atmosphere. See `global-promo-config.md` Section 14.

**Brand logos MUST be user-provided** — AI cannot generate reliable logos. Ref image NB2 templates in `script-to-scene-bridge.md` Section 11.

### Storytelling Core Rules

**Product is NEVER the hero. Product is the BRIDGE. Customer is the hero. Brand is the guide.**

9 Commandments (cannot be overridden):
1. NEVER open with company name or logo
2. NEVER use jargon without immediate translation
3. Every feature MUST have a human consequence
4. Forbidden words: synergy, leverage, robust, revolutionary, cutting-edge, seamlessly, innovative solution, state-of-the-art
5. B-roll MUST advance the story (never decorative)
6. Every scene MUST pass the "So What?" test
7. CTA must be specific, time-bound, and low-friction
8. The first 3 seconds determine everything
9. **(v2.2.0+) BODY 1 must dramatize ALL identified problems** — count(pains dramatized as dedicated scenes in BODY 1) >= count(pains identified in Phase 1 brainstorm). Pairing OK if shared root cause (max 2/scene). Anchor pain NOT pairable. Overlay "1 of N" while N>1 = auto-fail. See `global-promo-config.md` §25.

22 rejection signals auto-checked — see `storytelling_script_gen/project-instruction.md`. Target market adaptation in `F1_Audience_Psychology_Matrix.md`. 7-beat arc and awareness routing in `F2` and `F8`. 6-stage user framework alias (HOOK → Foreshadow → BODY 1 → BODY 2 → Peak → Ending+CTA) in `F2` §B0 + `global-promo-config.md` §25.

### v2.2.0 Hard Rules (NEW — must read for any new project)

| Rule | Reference | Validator Check |
|---|---|---|
| BODY 1 Completeness — all identified pains dramatized | `global-promo-config.md` §25 | C1 (Phase 2) |
| NB2 Reference Uniqueness Filter — skip COMMON, generate UNIQUE | `global-promo-config.md` §26 | C2 (Phase 4A) |
| Max 5 inline refs per Phase 4B prompt | `global-promo-config.md` §26.4 | C3 (Phase 4B) |
| Cross-scene `scene-N-end.png` ref env-gated only | `global-promo-config.md` §27 | C4 (Phase 4B) |

## Technical Defaults

All configurable values live in `reference/global-promo-config.md` — single source of truth. Includes: resolution, aspect ratio, film stock, NB2 CFG/denoise, VEO duration, cast limits, ref naming conventions, institution keywords, tone impact matrix, and cultural search settings.

## Conventions for Contributors

### Changing Any Setting (Global, Cast, Tone, etc.)
1. Edit `reference/global-promo-config.md` — single source of truth (cast = Section 7)
2. No need to edit other files — they all reference global-promo-config.md

### Adding a New Reference File
1. Create `.md` file in `reference/`
2. Add entry to the Reference Files table in skill SKILL.md
3. Add entry to the Reference Files table in `agents/video-engine-agent.md`
4. Update this CLAUDE.md file
5. Run `/video-validate --refs` to verify cross-file consistency

### Adding a New Video Platform
1. Run `/video-add-platform` skill
2. It scaffolds platform guide, updates cross-references

### File Naming
- Reference files: lowercase, kebab-case (e.g., `global-promo-config.md`)
- No spaces in filenames
- Storytelling refs: `F{N}_{Name}.md` format (existing convention)
- Image-video refs: `{NN}-{name}.md` format (existing convention)

## Debugging

| Issue | Check |
|-------|-------|
| Edge hallucination in video | NB2 aspect ratio doesn't match VEO target — generate natively in target ratio |
| Wrong VEO mode selected | Ingredients ≠ First+Last Frame — they are MUTUALLY EXCLUSIVE |
| No audio in video | Audio is NEVER optional — specify all 3 layers (dialogue/VO, SFX, ambient) |
| Lip sync fails | Wrong dialogue syntax — use colon syntax `says:` not quotation marks |
| Frozen mouth in video | Camera too far — MCU/CU, face >30% frame, add "visible mouth openings" |
| Identity drift across clips | Weak context in final second — hold clear pose, use same description verbatim |
| Light jumps between clips | Different lighting in start/end frames — match Kelvin + direction in both NB2 images |
| Can't extend clip | Clip was generated at 1080p — use 720p for extendable clips |
| Stutter at extension joint | Abrupt motion at clip end — maintain consistent camera speed through final second |
| Script too corporate | Check 9 Commandments (v2.2.0+) — forbidden words, missing human consequences, BODY 1 incomplete |
| Weak hook | Must pass "So What?" test in first 3 seconds — check F5 Hook Vault |
| CTA too generic | Must be specific, time-bound, low-friction — check F6 CTA Vault |
| Wrong target market tone | Check F1 Audience Psychology Matrix for correct psychographic profile |
| Missing emotional beats | Check 7-Beat Arc compliance — all beats mandatory |
| Plastic texture in image | Over-denoising — prompt "visible pores", "natural grain", "micro-scratches" |
| B-Roll voiceover rendered as lip sync | Bare `Voiceover:` assigns speech to visible character — use `Voice-over narrator, [tone]: text` (VEO treats narrator as off-screen) |
| "Prominent people" safety error | Real person name in VEO `says:` + photorealistic face — use `Host says:` / `Presenter says:`, NEVER real names. NB2 can still use real names. |
| "Prominent people" on First+Last Frame | Two photorealistic face images uploaded to VEO — use single I2V (start frame only) for face-dominant scenes (face >30% frame) |
| Em dash audio artifact | `—` in says:/narrator: text — VEO audio engine mistranslates em dashes. Replace with `,` or `. ` |
| B-Roll scene has no narration | Silent B-Roll breaks continuous VO flow — every B-Roll MUST have `Voice-over narrator, [tone]: text` + `> POST-PROD VO:` backup |
| Face ref filename in VEO prompt | `cast-c{N}-face.png` in VEO prompt is useless and may trigger safety filter — face ref injection is NB2-only. VEO uses `Maintain visual continuity with reference frame character appearance.` |
| Identity conflict between cast members | Different characters look too similar — use distinct clothing + accessories + positioning per character |
| Wrong character appears in scene | NB2 prompt missing specific `cast-c{N}-face.png` identity lock — each prompt must reference exact cast slot (filename only, NO `ref/` prefix) |
| Costume doesn't match institution | Wrong/generic uniform generated — use `ref/costume-{institution}.png` as upload reference, describe badge/emblem details |
| Missing ref blocks Phase 4 | ref-manifest.md validation failed — upload ALL required refs to `{project}/ref/` per manifest |
| Multi-char dialogue overlap | VEO renders garbled speech — lip sync is 1 speaker at a time, use sequential delivery with reaction pauses |
| Cast member inconsistent across scenes | Weak reference phrase — use EXACT verbatim phrase from cast-profile.md in EVERY NB2 prompt |
| Wrong language in dialogue | narration_language not applied in Phase 2 — check strategic-brief.md Language field, ensure script uses it |
| Tone inconsistent across scenes | video_tone not applied uniformly — reference global-promo-config.md Section 13 Tone Impact Matrix |
| Wrong license plate in video | No cultural research performed — run Step 3.5.2a web search, check plat kendaraan fact |
| Wrong ethnicity for local extras | Cultural context missing — check strategic-brief.md Cultural Context, inject into NB2 |
| AI-generated logo looks wrong | Logo generation unreliable — brand logo MUST be user-provided, not AI-generated |
| Storyline missing beats | User input incomplete — Step 1.7 maps to 7-beat arc, AI suggests missing beats |
| Cross-file drift | Run `/video-validate --refs` — checks all reference files for consistency |
| Same element looks different across scenes | Recurring element not generated as standalone asset — auto-detect from av-script.md, generate in Phase 4A first |
| Gate/facility hallucinated wrong | No user photo used — auto-scan ref/ folder, existing photos = ground truth, NEVER override with text description |
| Product texture completely wrong | No product closeup reference — user photo mandatory (AI generates wrong species/shape for commodities like cangkang) |
| Wrong aspect ratio in NB2 output | Missing triple enforcement — add aspect ratio to FIRST line, TECHNICAL section, and LAST line of every prompt |
| UI text in wrong language | ui_text_language not applied — on-screen text must match narration_language, except technical abbreviations |
| Composite asset has wrong sub-elements | Wrong tier assignment — composite tier = max(sub-element tiers) + 1. Generate sub-elements FIRST |
| Ref in upload table but model ignores it | Missing ref-to-prompt body binding — every ref in table needs matching injection line in prompt body text |
| User doesn't know where to save output | Missing Output filename — every NB2 prompt needs explicit `**Output →** ref/filename.png` line |
| Costume inappropriate for climate | No climate-aware check — cross-check costume vs location climate after cultural research (Step 3.5.2a) |
| Scene keyframe describes element from scratch | Asset-first violation — if element has ref in Phase 4A, scene keyframe MUST reference it, not describe from text |
| Identity conflict between cast members | Different characters look too similar — use distinct clothing + accessories + positioning per character |
| Wrong character appears in scene | NB2 prompt missing specific `cast-c{N}-face.png` identity lock — each prompt must reference exact cast slot (filename only, NO `ref/` prefix) |
| Costume doesn't match institution | Wrong/generic uniform generated — use `ref/costume-{institution}.png` as upload reference, describe badge/emblem details |
| Missing ref blocks Phase 4 | ref-manifest.md validation failed — upload ALL required refs to `{project}/ref/` per manifest |
| Multi-char dialogue overlap | VEO renders garbled speech — lip sync is 1 speaker at a time, use sequential delivery with reaction pauses |
| Cast member inconsistent across scenes | Weak reference phrase — use EXACT verbatim phrase from cast-profile.md in EVERY NB2 prompt |
| Wrong language in dialogue | narration_language not applied in Phase 2 — check strategic-brief.md Language field, ensure script uses it |
| Generic stock-photo environment | Scene Logic Realism check 1 failed — prompt must reference cultural research + ref/env-{location}.png, not generic "modern office" |
| Workers posing instead of working | Scene Logic Realism check 2 failed — direct plausible actions: "supervisor reviewing clipboard," not "supervisor smiling at camera" |
| Dashboard numbers inconsistent | Scene Logic Realism check 3 failed — pin specific numbers and names across all scenes showing same data |
| Supervisor in operator uniform | Scene Logic Realism check 4 failed — uniform details must match institutional rank hierarchy (stripes, helmet color, vest) |
| AI adds wrong elements to scene | Scene Logic Realism check 5 failed — add explicit negatives: "no outdoor elements," "no sunlight" for indoor/night |
| Dawn scene followed by midday lighting | Scene Logic Realism check 7 failed — timeline consistency: connected scenes must share same time-of-day lighting |
| Character face changes between scenes | Character portrait-first rule violated — generate standalone face ref in Phase 4A Tier 1 BEFORE any scene keyframe |
| Scenes feel disconnected / no flow | Narrative arc consistency missing — add NARRATIVE CONTEXT block: connections, visual breadcrumbs, cause-effect chains |
| Same dashboard shows different names | Data not pinned across scenes — use exact same text/numbers in every prompt showing the same data display |
| Wrong machine/equipment in scene | No domain research — Step 1.2c Domain Deep Research must complete before script. WebSearch 5 queries about domain process/equipment/roles |
| Operator doing wrong action | Domain knowledge missing — check strategic-brief.md Domain Knowledge > Operator Roles table for plausible actions per role |
| Generic "factory" instead of specific domain | Missing DOMAIN CONTEXT line in prompt — inject specific equipment/process details from Domain Knowledge section |
| Product UI/interface looks nothing like real thing | No product research — WebSearch "{product_name} product interface screenshots features" in Step 1.2c |
| NB2 identity lock fails / face not matched | Prompt body text uses `ref/cast-c1-face.png` instead of bare `cast-c1-face.png` — NB2 matches by uploaded filename, `ref/` prefix causes lookup failure. Remove ALL folder prefixes from identity lock lines and reference image mentions in prompt body |
| Ref image uploaded but model ignores identity | Reference filename in header block at top of prompt, not inline with character — model reads past header blocks. Move filename inline: `[Name] (Maintain exact facial identity from reference image: cast-c1-face.png) — description...` |
| Same ref file mentioned multiple times | Duplicate filename dilutes reference signal. Each filename MAX 1x per prompt — place inline with the primary element it describes |
| ref/ prefix in Required Reference Images table | Upload table filenames use `ref/filename.png` — user copies wrong filename to NB2. Table MUST use bare filenames only (e.g., `cast-c1-face.png`), add "Upload all to `{project}/ref/` folder" note |
| Reference table appears above image heading | Table placement wrong — table MUST appear directly BELOW each image/prompt heading, BEFORE the prompt body. Not above heading, not after prompt body |
| VEO voiceover mispronounces words | Em dash `—` in `says:` or `Voice-over narrator:` text — VEO audio engine mistranslates em dashes. Replace with `,` or `. ` in all dialogue/voiceover text including template placeholders |
| **(v2.2.0) BODY 1 dramatizes only 1 pain while brainstorm identified many** | C1 validator auto-fail — Phase 2 script REJECTED. Phase 2 output MUST include Pain Coverage Table. count(pains dramatized in BODY 1 scenes) >= count(pains brainstormed). Pairing allowed (max 2/scene, shared root cause). Overlay "1 dari N" while N>1 = auto-fail trigger. See `global-promo-config.md` §25. |
| **(v2.2.0) Phase 4A generates assets for generic items (kopi gelas, plain phone, pavement)** | C2 validator FLAG — apply UNIQUENESS filter BEFORE generating any Phase 4A asset. COMMON tier (generic everyday items that NB2 can render from text alone) = SKIP reference. UNIQUE tier (faces, logos, industry-specific equipment, custom UI) = GENERATE. Decision test: "Can a competent prompt writer describe this in 20 words and trust NB2?" YES → COMMON, skip. NO → UNIQUE, generate. See `global-promo-config.md` §26. |
| **(v2.2.0) Phase 4B scene prompt has 8+ reference filenames** | C3 validator FAIL — Max 5 inline refs per Phase 4B prompt (combined faces + objects + env + UI). Replaces old "Max 3 identity locks". If >5 needed → split scene into 2 sub-scenes OR consolidate via composite asset (Tier 5+ per §18). See `global-promo-config.md` §26.4. |
| **(v2.2.0) `scene-N-end.png` cross-ref between hard-cut scenes (different env)** | C4 validator FAIL — Cross-scene ref env-gated ONLY. Allowed only if env(N) == env(N+1). Hard cut (location differs) = DROP cross-ref entirely. Visual continuity carried by text SUBJECT spec + standalone identity refs (cast-c{N}-face.png) + costume verbatim + NARRATIVE CONTEXT block. Reason: NB2 treats scene-NN-end.png as compositional template — using cross-env confuses model into mixing wrong-location elements. See `global-promo-config.md` §27. |
| **(v2.3.1) Kling Bahasa Indonesia on-screen lip-sync garbled** | Lip-sync only supports 5 langs (EN/ZH/JA/KO/ES). For ID dialogue with face >30%: switch to VEO 3.1 OR reframe scene as mouth-neutral (back-of-head, partial obscure) + `Voice-over narrator, [tone]: [ID text]`. **NOTE**: Bahasa Indonesia **Voice-over narrator IS supported natively** in Kling — only on-screen lip-sync is restricted. Most B-Roll ID scenes work natively. |
| **(v2.3.1) Bahasa Indonesia VO not rendering in Kling** | User wrote `Host says: [Indonesian text]` for what should be B-Roll narration | Wrong syntax. B-Roll needs `Voice-over narrator, [tone]: [ID text]` (Kling treats narrator as off-screen — natively supports ID). `Host says:` triggers on-screen lip-sync path which is 5-lang restricted. |
| **(v2.3.0) Kling multi-shot scenes flicker / shots blend** | Shot boundaries weak. Strengthen with numbered markers (`Shot 1: ... Shot 2: ...`) + transition cues (`match cut to`, `whip pan to`). Use ONLY when shots share env/character. Don't multi-shot complex narrative beats. |
| **(v2.3.0) Kling text in scene warps to gibberish** | Same constraint as VEO/Seedance — Kling cannot render legible text. Strip logos/text from prompt, add as post-prod overlay. Brand visual = colors + shapes only, not text. |
| **(v2.3.0) Kling prompt 200+ words = half ignored** | Kling optimal is 80-120 words. Longer prompts get half ignored, half hallucinated. Apply 5-part formula strictly: Camera + Scene + Action + Vibe/Lighting + Time/Audio. |
| **(v2.3.0) Kling generic camera term produces static** | Vague terms (`dynamic shot`, `cinematic angle`) → static or random direction. Use specific phrases from Kling Camera Movement Library: `slow dolly-in`, `360° orbit`, `whip pan right`, `crane up`. Camera term position determines weight (start = camera dominates, end = camera follows subject). |
| **(v2.3.0) Kling negative prompt overweighted (stiff/lifeless output)** | Generic 20-term negative dump → Kling overweights and outputs stiff motion. Use focused 3-5 terms per relevant category (human / product / motion / environment). NOT all 4 categories at once. |
| **(v2.3.0) Kling Motion Control character faces wrong direction** | Character Orientation parameter set wrong. Toggle: `Follow Video` (replicate motion-ref spatial position) for complex motion / `Follow Image` (maintain anchor composition) when camera dominates body motion. |
| **(v2.3.0) Kling First+Last Frame rejected as "prominent people"** | Same VEO safety filter — 2 photoreal face images = rejection. For face-dominant scenes (face >30% frame) use single I2V mode. First+Last Frame in Kling is for faceless scenes only (dashboards, products, environments). |
| **(v2.3.0) Kling clip dialogue rushed/clipped** | Dialogue exceeds ~2.5 words/sec budget. Kling has PER-SECOND duration selector (3/4/5/6/7/8/9/10/11/12/13/14/15s) — bump duration up by 1-2 seconds to fit. E.g., 12-word line at 5s = rushed → use 6s instead. No need to split scenes just for pacing. |
| **(v3.0.0) Same line spoken twice, once by the platform and once by the VO** | Scene has `audio_source: elevenlabs` but its platform prompt still carries a speech line. Strip the line and add the verbatim negative `no speech, no voiceover, no dialogue`. A face >30% frame should be `platform-native` instead, then normalised with the Voice Changer |
| **(v3.0.0) A second speaker in the clip came back in the target voice** | Whole-track speech-to-speech converts every voice on the track. Pass `--spans START-END` with only the target's turns; take them from `av-script.md`, never from speaker diarization (it merged two AI voices into one label on a real clip) |
| **(v3.0.0) Voice Changer refuses with a drift number** | Drift past 0.05s means lip-sync would no longer match. Do NOT stretch the audio — that produces exactly the artefact the locked voice exists to avoid. Reopen the mixed-source decision for that scene |
| **(v3.0.0) `voice env ELEVENLABS_VOICE_C2 not set`** | The `VOICE:` block names an env var that `.env` does not define. Add it. The tool never substitutes another voice, by design |
| **(v3.0.0) Explainer scene has no rendered shot** | Scene's Render Path is `explainer` but Phase 4.5 never ran for it, or the render failed. Check `{output_folder}/shots/out/`. Never fall back to a generated clip: the platform cannot render legible text, which is the whole reason for the routing |
| **(v3.0.0) A/V duration mismatch stops the edit** | A clip's audio and video lengths differ past tolerance. Fix the clip or the plan; the gate exists because a drift of a few frames per clip compounds across a whole timeline |
| **(v3.0.0) An SFX cue measures +0 dB no matter the gain** | The cue sits fully under continuous speech, so the duck suppresses it the whole time. Accept it as felt-not-heard, or delete it. Never chase it with gain — it spikes the moment a pause arrives |
| **(v3.0.0) Caption text differs from the script** | Captions are built from `av-script.md`; ASR supplies TIMING only. A wrong word means the cue was hand-edited or a scene had no timing source and was left in `untimed` — timings are never guessed |
| **(v3.0.0) Music makes the voice hard to follow** | Bed is too loud under speech, or the duck is not engaging. Check the headroom measurement the music pass prints; the bed fails soft (no music) rather than shipping a mix that buries the narration |
| **(v3.0.0) Thumbnail promises more than the video delivers** | Packaging honesty guardrail. The frame's promise must sit inside what the video actually shows. Pick a different lever, not a bigger claim |
| **(v2.3.0) Kling duration mismatch (padding or rushing)** | Picked 8s default when scene needed 5s (awkward pause) OR picked 5s when needed 9s (rushed). Use Kling's per-second selector — pick exact duration matching natural dialogue/beat pace. Eliminates re-pacing in post-edit. |

---

**Version:** 3.0.0
**Last Updated:** 2026-09-03

### v3.0.0 Changelog

- **Renamed** `ai-video-promo-engine` → **`gaspol-video`**, published through the `gaspol-one` marketplace.
- **Three new skills:** `/video-explainer` (Phase 4.5, Remotion shots for scenes that must be readable),
  `/video-post` (Phase 6, five passes: VO → edit → SFX → subtitles+music → mix), `/video-package`
  (Phase 7, title + thumbnail bets + description).
- **Ten CLI tools** in `tools/`, zero dependencies: python3 stdlib, node builtins, ffmpeg.
- **Eight new references** in `reference/post-production/` (10 through 17), plus §29-30 in the global config.
- **Render Path** column added to the Scene Breakdown table: `platform` or `explainer`, decided at Phase 3,
  before NB2 credits are spent.
- **Voice cast:** per-character `VOICE:` block in `cast-profile.md`. Voice ids live in `.env` and are named,
  never written, in the repo.
- **Speech-to-speech converts spans, not tracks** (fix after a real multi-speaker failure) — see the
  debugging rows above and `docs/evals/voice-changer-probe.md` run 4.
- **Adopted from `hassancs91/claude-youtube-editor`:** ElevenLabs VO and voice changing, AssemblyAI timing,
  ffmpeg assembly, packaging decisions. **From `harry0703/MoneyPrinterTurbo`:** burned subtitles and the
  music bed. Rejected from both: clean-cut, brand-setup, YouTube upload, stock-footage matching, the LLM
  script writer, the WebUI and service layer, moviepy, `edge-tts`, and any local whisper model. See `NOTICE`.
- **Validator:** agent checks C5-C10, plus I17, V13, V14 and a new `--post` section (P1-P5).

### v2.4.0 Changelog

- **NEW reference file `09-voice-consistency-workflow.md`** (~4200 tokens, cross-platform):
  - Path A — Native voice lock per platform: Kling Elements 3.0 (audio sample or video extraction), Seedance @Audio1 (max 15s ref), VEO NOT supported
  - Path B — Universal ElevenLabs Voice Changer post-prod (3-step workflow: generate → export → voice changer)
  - Path C — Single VO recording + video sync (B-Roll-heavy promo)
  - Hybrid workflow per video type (Pure-VEO / Pure-Kling / Pure-Seedance / Mixed / B-Roll-heavy)
  - Prompt-level discipline rules (verbatim voice description, accent lock, one emotion per scene)
  - Anti-patterns table + cost/time comparison
- **video-gen SKILL.md:** NEW Step 5.0a VOICE CONSISTENCY STRATEGY runs BEFORE Step 5.0 Platform Selection. Voice consistency invariant added to cross-platform invariants table
- **CLAUDE.md Smart Context Loading:** ALL Phase 5 rows (VEO / Seedance / Kling / Mixed) now include `09-voice-consistency.md` (5-7 refs per batch instead of 4-6)
- **00-index.md + agent:** voice consistency reference row added

### v2.3.1 Changelog (fact correction)

- **Bahasa Indonesia audio support — clarified two-tier model**:
  - ✅ Voice-over narrator (off-screen, B-Roll) — **SUPPORTED NATIVELY** in Kling 3.0
  - ❌ On-screen lip-sync (face >30% speaking ID) — restricted to 5 langs (EN/ZH/JA/KO/ES)
  - Previously incorrectly stated "NO Bahasa Indonesia" — now correctly distinguishes lip-sync vs VO paths
- **Impact:** Most Indonesian B-Roll production scenes work natively in Kling without post-prod dub. Only switch to VEO for face-front ID dialogue scenes.
- **Files updated:** 7 (08-kling guide, global-promo-config, script-to-scene-bridge, video-gen SKILL.md, CLAUDE.md, 00-index, README)

### v2.3.0 Changelog

- **NEW reference file `08-kling-production-guide.md`** (~7200 tokens): Kling 3.0 specs, 5-part prompt formula, 5 modes (T2V/I2V/First-Last/Multi-Shot/Motion Control), Omni audio (5 langs incl mixed-language scene), camera movement library, negative prompt strategy, cross-platform comparison vs VEO/Seedance
- **Global config (Section 2):** Added Kling 3.0 Defaults table. `video_model` enum extended to `veo | seedance | kling | mixed`
- **Global config (Section 9):** Added Kling prompt length guidelines (80-120 words optimal, 5-part formula)
- **video-gen SKILL.md:** Added **Step 5.0 Platform Selection** before Image Review. Platform-conditional CONTEXT LOADING (load matching guide only). Cross-platform invariants table. Per-scene mode selection happens during Image Review.
- **script-to-scene-bridge.md:** Added Step 3c (Kling Mode Selection per Scene) with full 5-mode decision tree
- **CLAUDE.md:** Production Stack lists Kling as 3rd alt platform with constraints. Smart Context Loading adds Phase 5 (Kling) and Phase 5 (Mixed) rows. Debugging Checklist adds 8 Kling-specific rows
- **Agent (`video-engine-agent.md`):** Reference table adds Kling row; capability list mentions tri-platform Phase 5
- **00-index.md:** Production stack lists 3 video models; constraints section adds Kling clip duration + no-native-extension + 5-language lip-sync + cannot-render-text constraints
- **plugin.json:** v2.1.1 → 2.3.0, description mentions all three platforms, keywords add `Kling`

### v2.2.0 Changelog

### v2.2.0 Changelog

- **§25 added (global-promo-config.md):** Narrative Arc Hard Rules — 6-stage user framework alias to 7-beat, BODY 1 Completeness rule (count pain dramatized ≥ count pain brainstormed), pairing rules, validator C1
- **§26 added (global-promo-config.md):** NB2 Reference Image Inclusion Rule — Uniqueness Filter (UNIQUE/COMMON/AMBIGUOUS), 2-question decision test, combined filter (uniqueness AND recurrence), Max 5 inline refs per Phase 4B prompt (replaces old Max 3 identity locks), validators C2 + C3
- **§27 added (global-promo-config.md):** Cross-Scene Reference Conditional (Environment-Gated) — replaces blanket "MUST reference scene-N-end.png" rule. Cross-ref allowed ONLY if env(N) == env(N+1). Hard cuts drop cross-ref entirely. Validator C4
- **video-prompt-reviewer.md:** Added 4 new validator checks (C1-C4) cross-referenced to §25-§27. Updated batch report table with applicability matrix
- **video-script SKILL.md:** Added Hard Rule #15 (BODY 1 Pain Coverage HARD GATE)
- **video-image SKILL.md:** Updated Rule #24 (env-gated cross-ref conditional), added Rule #31 (uniqueness filter Phase 4A), added Rule #32 (max 5 inline refs Phase 4B)
- **F2_Narrative_Arc_and_Video_Typology.md:** Added 6-stage user framework alias subsection
- **project-instruction.md:** Added BODY 1 COVERAGE line in Production Notes output template + 2 new entries in Structural Failures table
- **script-to-scene-bridge.md:** Updated sequential cross-ref rule (env-gated), Required Reference Images table row 11 conditional, production checklist 4 new v2.2.0 checks
- **01-nb2-image-generation.md:** Added Uniqueness Filter subsection + Max 5 Inline References subsection

## gaspol Ticket Counter

Prefix: GV
Last ticket: GV-1
