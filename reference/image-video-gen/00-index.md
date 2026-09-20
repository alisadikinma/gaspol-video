---
source: Consolidated from 10 project knowledge files
curated: 2026-03-19
version: 2.0
tokens: ~200
platform: claude-projects
---

# AI Video Production — Knowledge Index

## Production Stack
- **Image Model:** Nano Banana 2 (Gemini 3.1 Flash Image) — all start/end frames
- **Video Model (Primary):** Google VEO 3.1 — temporal animation, audio, lip sync
- **Video Model (Alt):** Bytedance Seedance 2.0 — native 2K, dual-branch AV, @ reference system
- **Video Model (Alt):** Kuaishou Kling 3.0 — native 4K, multi-shot storyboarding (6 shots/15s), mixed-language lip sync
- **Pipeline (VEO):** NB2 image → VEO First+Last Frame → VEO Extend (same scene)
- **Pipeline (Seedance):** NB2 image → Seedance @Image refs + Omni mode → Seedance @Video extend
- **Pipeline (Kling):** NB2 image → Kling I2V / First+Last / Multi-Shot Storyboard / Motion Control

## File Map

| File | Content | Read When |
|------|---------|-----------|
| `01-nb2-image-generation.md` | NB2 params, resolution, color, text, identity lock | Generating any image asset |
| `02-veo-production-guide.md` | VEO 3.1 specs, motion library, lip sync, audio, extend | Creating video from images |
| `03-workflow-pipeline.md` | NB2→VEO handoff, decision tree, extend vs keyframe | Planning production sequence |
| `04-cinematography-lookup.md` | Lighting, camera, lens, film stocks, emotion mapping, atmosphere | Crafting any visual prompt |
| `05-creator-and-holidays.md` | Ali Sadikin profile, holiday palettes, thumbnail templates | Creator content or seasonal campaigns |
| `07-seedance-production-guide.md` | Seedance 2.0 specs, @ reference system, modes, audio, camera, materials | Using Seedance 2.0 as video model |
| `08-kling-production-guide.md` | Kling 3.0 specs, 5-part prompt formula, multi-shot storyboarding, motion control, omni audio | Using Kling 3.0 as video model (PRIMARY) |
| `08b-kling-notebooklm-briefing.md` | Kling 3.0 NotebookLM-distilled briefing — efficiency data, Elements 3.0, 5-layer formula, cross-validates 08-kling | Cross-check Kling guide claims (SUPPLEMENTARY RAG) |
| `09-voice-consistency-workflow.md` | **Cross-platform** VO consistency — 3 paths (native lock / ElevenLabs post-prod / single VO sync), prompt-level discipline, hybrid workflow per video type | MANDATORY for any video >1 scene OR with character voice continuity |
| `10-physical-plausibility-gate.md` | Nine defect classes measured in production, the seven-question PLAUSIBILITY block (mechanism, count, flow, facing, pair, people, overlay surface), the flow gate and the post-render frame audit | MANDATORY before writing any Phase 4B keyframe or Phase 5 platform prompt |

## Critical Constraints (Always Apply)
- VEO max 8s/clip, 24fps, 720p for extensions, 1080p for final only
- Seedance max 15s/clip, 24-60fps, native 2K, unlimited extension chains (drift ~20th hop)
- Kling clip duration: per-second granular 3-15s (pick exact second matching scene), up to 6 shots in single 10-15s render, 24/30/60fps, 720p/1080p (UI) or 4K (API), no native extension chain
- NB2 image aspect ratio MUST match video model target ratio — mismatch = edge hallucination
- "Ingredients to Video" and "First+Last Frame" are **mutually exclusive** in VEO
- Seedance: First/Last Frame and Omni are separate modes — use Omni for character consistency
- Kling: I2V / First+Last Frame / Multi-Shot / Motion Control are 4 separate modes — pick one per generation
- Audio is NOT optional — VEO: unspecified = random sounds; Seedance: native dual-branch AV; Kling: native omni audio (lip-sync 5 langs: EN/ZH/JA/KO/ES; **Voice-over narrator supports Bahasa Indonesia natively** + other langs)
- All dialogue: colon syntax (`says:` not `says ""`)
- Seedance: real face upload BANNED — use AI-generated faces only
- Keep critical action in **central 60%** of frame for cross-platform safety
- Kling: cannot render legible text (same as VEO/Seedance) — use post-prod overlay for logos/text
