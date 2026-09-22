# gaspol-video — AI Video Production Rules

═══════════════════════════════════════════════════════════════
gaspol-video Master Plugin Active — End-to-end AI Video Production.
═══════════════════════════════════════════════════════════════

## Video Production Routing Table
When a video production task is requested, activate the `gaspol-video` master skill and dispatch to the matching sub-module in `references/`:

| Intent | Sub-Module | Reference Document | Purpose |
| :--- | :--- | :--- | :--- |
| **end-to-end video** | `video-full` | `references/video-full.md` | Full pipeline: brainstorm → script → images → video → post → package |
| **video brainstorm** | `video-brainstorm` | `references/video-brainstorm.md` | Phase 1: concept, cast, product, location, domain research |
| **video script** | `video-script` | `references/video-script.md` | Phase 2-3.5: script, scene breakdown, visual references |
| **image prompts** | `video-image` | `references/video-image.md` | Phase 4: NB2 asset library & keyframe prompts |
| **explainer / remotion** | `video-explainer` | `references/video-explainer.md` | Phase 4.5: Remotion code shots for legible text & app UI |
| **video generation prompts** | `video-gen` | `references/video-gen.md` | Phase 5: VEO 3.1 / Seedance 2.0 / Kling 3.0 prompts |
| **post-production** | `video-post` | `references/video-post.md` | Phase 6: voice-over, ffmpeg edit, SFX, subtitles, music mix |
| **video packaging** | `video-package` | `references/video-package.md` | Phase 7: title bets, description, thumbnail prompts |
| **validate video assets** | `video-validate` | `references/video-validate.md` | Unified validator (--script, --image, --video, --post, --all) |
| **add video platform** | `video-add-platform` | `references/video-add-platform.md` | Scaffold support for new AI video platforms |

---

## Core Operational Directives
1. **Prompt Configuration**: Read `reference/global-promo-config.md` FIRST before generating image or video prompts.
2. **Text Legibility Rule**: Never ask video generation models (VEO/Seedance/Kling) to render complex or legible UI/typography; route text-heavy scenes to Remotion code shots (`video-explainer`).
3. **Graceful Degradation**: If external APIs or tools (e.g. ffmpeg, ElevenLabs, AssemblyAI) are not configured, degrade loudly and state what could not run — never skip silently.
4. **Interactive Confirmation**: Use the `ask_question` tool whenever presenting storyboard choices, voice-over options, or approvals.

---

## Slash Command Invocations
If the user's message begins with or contains `/gaspol-video`, `/video-full`, `/video-brainstorm`, `/video-script`, `/video-gen`, `/video-post`, etc.:
1. Treat it as a direct command to execute the video pipeline or the specified sub-module.
2. Activate `gaspol-video` and follow the relevant reference protocol.
