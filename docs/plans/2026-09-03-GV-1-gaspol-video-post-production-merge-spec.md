**Ticket:** GV-1

# Spec — `gaspol-video` v3.0.0: post-production merge, rename, and gaspol-one listing

## Design

### 1. Problem

`ai-video-promo-engine` v2.4.0 ends at `video-prompts.md`. It produces a *prompt package*, never a
finished video. Everything after clip generation — voice-over, technical explanation, trimming to
beat length, sound design, packaging — is left to the user with no tooling and no written method.

Three concrete gaps drive this ticket:

1. **No voice-over execution.** `reference/image-video-gen/09-voice-consistency-workflow.md` and
   `video-gen` Step 5.0a already *plan* voice consistency (Path A/B/C) and write
   `voice-consistency-plan.md`, but nothing generates an audio file. The plan is inert.
2. **No path for technical/diagram scenes.** VEO 3.1, Seedance 2.0 and Kling 3.0 all fail to render
   legible text — recorded in `08-kling-production-guide.md` and the CLAUDE.md debugging checklist.
   A scene whose job is to explain a diagram, a metric, or a UI flow currently has no correct
   production route; it is generated as a live-action clip and comes out wrong.
3. **No assembly layer.** Clip durations are guessed from word count. A 12-word line at 5s is rushed;
   an 8s VEO clip over a 5s beat pads. There is no cut, no mix, no A/V verification.

Two more gaps were found while studying a second source (see prior art below): the pipeline produces
**no subtitles at all** — a problem for IG/TikTok/LinkedIn, where most views are muted — and it has
**no music layer**, even though `av-script.md` has been writing per-scene music direction since Phase 2
with nothing reading it.

`claude-youtube-editor` (MIT, `hassancs91`) solves the first three for a different input — a real human
recording. Its post-recording half transfers; its pre-recording half does not.
`MoneyPrinterTurbo` (MIT, `harry0703`) solves the last two, also for a different input — stock footage
assembled around a machine-written script.

### 2. Prior-art verdict: DELTA

Three lookups per the KB note `2026-08-21-search-the-market-before-building-a-capability`:

- **Already installed / in-repo?** `09-voice-consistency-workflow.md` covers voice *strategy*, no
  execution. No Remotion, ffmpeg, or SFX method anywhere in the repo.
- **Built into the harness?** No built-in command renders video, generates TTS, or mixes audio.
- **On the market?** `claude-youtube-editor` covers the execution half, under MIT.
  `MoneyPrinterTurbo` (MIT) covers subtitles and the music bed. It is a standalone FastAPI + Streamlit
  application (~10k lines in `app/services/`) built around stock-footage matching, an LLM script writer,
  a redis task queue, and moviepy. Only three of its files carry transferable method:
  `app/services/subtitle.py`, the subtitle rendering half of `app/services/video.py`, and
  `app/services/bgm.py`.

**Verdict: DELTA.** The delta being built, named explicitly:

| Delta | Why the editor cannot supply it |
|---|---|
| **Domain-aware SFX cue derivation** | Editor's palette is generic UI (whoosh/pop/click). This plugin holds `DOMAIN CONTEXT` from 6 domain-research queries plus per-location cultural research in `strategic-brief.md`. Cues can be derived from the actual setting (factory floor in Cikarang ≠ port ≠ control room). |
| **Voice cast (per-character voice), not per-video voice** | Editor assumes one creator narrating. This plugin already supports 1-5 cast members with roles. Voice must bind to a cast slot, and one scene can carry on-screen dialogue from cast-c2 followed by narration from cast-c1. |
| **ElevenLabs Voice Changer** | Editor has TTS (`gen_vo.mjs`) and voice *isolation* (`clean_voice.py`), but no speech-to-speech. Needed to normalise a platform-generated dialogue voice into the locked character voice. Built new. |
| **Explainer routing at scene-plan time** | Editor never chooses between "generated clip" and "coded shot" — it always has footage. This plugin must decide per scene, before any credit is spent. |
| **VO-first duration budgeting** | Editor cuts recorded speech to length. This plugin generates the speech, so measured audio length can drive clip duration — exploiting Kling's per-second selector and VEO's 8s budget. |
| **Subtitles from owned text, not from ASR guessing** | MoneyPrinterTurbo transcribes audio with a local whisper model and repairs the result against its script (`subtitle.py:correct`, levenshtein-matched). This plugin **generates** the narration, so when the audio source is ElevenLabs the word timings come from the TTS response itself and no ASR runs at all. Where ASR is genuinely needed — dialogue spoken by the video platform — it goes to **AssemblyAI over HTTP**, the same provider and key the editor's `tools/transcribe.py` already uses, so no local model, no GPU, and no new install. |
| **Keyterms derived instead of hand-written** | The editor asks the user to draft a keyterms file per video so the recognizer does not mangle proper nouns. This plugin already holds the product name, brand, and domain jargon in `strategic-brief.md` and the cast names in `cast-profile.md`, so the list is built automatically and written back where it can be corrected. |
| **Music direction that already exists upstream** | MoneyPrinterTurbo picks a BGM file from a folder. This plugin has per-scene music direction written into `av-script.md` by Phase 2 and never read — the music pass consumes it rather than asking again. |

Everything else — the Remotion crash rules, the cue-sheet/plan-then-tool shape, the SFX gain
calibration numbers, the RMS audibility check, the A/V duration gate — is **adopted**, with
attribution, not reinvented.

### 3. Scope decisions (settled in brainstorm)

| Question | Decision |
|---|---|
| How much of the editor is imported | Post-production (VO, Remotion explainer, ffmpeg edit, SFX) **plus** packaging/thumbnail decisions. `clean-cut`, `brand-setup`, and YouTube upload are **not** imported — they assume raw human footage and a specific channel. |
| Packaging vs image-gen SoT | Packaging owns title / 3 thumbnail bets / description / honesty guardrail / CTR calibration. Image **rendering** is delegated by soft reference to `ai-image-carousel-prompt-gen`, preserving the two-plugin SoT split recorded in the vault (2026-06-14). No second image engine ships here. |
| Plugin name | `ai-video-promo-engine` → **`gaspol-video`** (not `gaspol-video-editor`: editing is one of five phases, and the talking-head editor is explicitly not imported). |
| Repo | GitHub repo renamed in place; git history preserved; GitHub redirects the old URL. |
| Version | 2.4.0 → **3.0.0**. The plugin `name` field is the install identity; changing it is breaking. |
| Tooling depth | **Hybrid.** `tools/` ships real scripts; every skill degrades to printed manual commands when `ffmpeg` / Node / an API key is absent. Degradation is announced, never silent. |
| Remotion location | **Scaffolded per project** inside the video project folder on first use. The plugin ships templates + rules only; no `node_modules` in the plugin repo. |
| SFX library | Recipes and schema (`palette.json`, `catalog.json` shape) plus the editor's measured calibration numbers are adopted. **No `.mp3` files are vendored.** Clips are generated per install and grow a local library. |
| Explainer routing point | **Phase 3 (scene-plan)**. A scene marked `explainer` skips NB2 and skips the video platform entirely. |
| Audio source question | Asked at the **start of Phase 5**, before any prompt is written. If ElevenLabs: VO is generated first and its measured duration sets clip duration. |
| Face-front dialogue under ElevenLabs | **Mixed per scene.** On-screen speaking scenes keep the platform's native voice so lips stay synced; B-Roll and narration use ElevenLabs TTS; the whole dialogue track is normalised at the end through ElevenLabs Voice Changer so the character voice is consistent. This is Path B from `09-voice-consistency-workflow.md`, made executable. |
| Subtitles | Method adopted from `MoneyPrinterTurbo`, provider taken from the editor. Built in Phase 6 from the narration text the plugin already owns; burned in with configurable style. ASR, where needed at all, is **AssemblyAI** (`ASSEMBLYAI_API_KEY`) — never a local whisper model. |
| Music bed | Adopted from `MoneyPrinterTurbo` (fail-soft mixing) and `claude-youtube-editor` (`gen_music.py` / `mix_music.py` shape). Reads the music direction already present in `av-script.md`. A failed music mix never blocks the video — it warns and ships the voice-only mix. |
| edge-tts free voice | **Rejected.** It cannot carry a locked character voice, so it would only ever produce a draft that must be regenerated. Cost control for VO regeneration stays an open item. |
| Explainer shot design | No bundled palette. Colours and type come from each project's `strategic-brief.md`. Only legibility rules are fixed (contrast floor, minimum type size at 1080p, title-safe area). `ui-ux-pro-max` is **not** invoked — the plugin is client-agnostic by contract. |

### 4. Architecture — three new skills, cut by when they run

**`/video-explainer` — Phase 4.5**

Runs between Phase 4 (images) and Phase 5 (video prompts), over scenes marked `explainer` in
`scene-plan.md`. Those scenes have no NB2 keyframe and no platform clip.

- Scaffolds a Remotion workspace inside `{output_folder}/shots/` on first use (Node required; absent
  Node → the skill emits the TSX files plus the exact commands to run elsewhere).
- Authors one `.tsx` per explainer scene following the adopted crash rules: frame-based animation
  only, strictly monotonic `interpolate` ranges, `Easing.bezier` not wrapper syntax, no
  `useState`/`useEffect`/`setTimeout`.
- Reads brand tokens from `strategic-brief.md`; enforces legibility rules.
- Timing anchors to the scene's VO file when the audio source is ElevenLabs (reveals land on the
  spoken cue), otherwise to the scene's allocated duration in `scene-plan.md`.
- **Verification is by rendered still at each cue**, not by reasoning. A shot with no inspected frame
  is not done.

**`/video-post` — Phase 6**, four ordered passes:

1. **Audio pass** — builds `{output_folder}/work/audio-plan.json`: per scene, time-layered entries
   for on-screen dialogue, narration, SFX, and ambience. Generates narration mp3s via ElevenLabs
   TTS, consecutive requests stitched so prosody carries across scenes. Runs Voice Changer over
   extracted platform dialogue where a cast member's voice is locked.
2. **Edit pass** — builds `{output_folder}/work/edit-plan.json` (order, in/out per clip, trim/pad,
   explainer shot insertion, transitions) and renders it with ffmpeg. **Hard gate: v:0 and a:0
   durations must be equal** on the rendered master.
3. **SFX pass** — cues derived from the scene's `DOMAIN CONTEXT` and cultural research plus the
   visual beat; library-first (reuse before generate); generate misses via ElevenLabs Sound Effects;
   `sfx-plan.json` presented for a hard user-audit gate before any mix.
4. **Final mix** — sidechain duck under voice, safety limiter, loudness target, then QA:
   per-cue RMS audibility check (story-critical cue ≥ +4 dB over the voice-only reference; texture
   +1 to +3 dB), A/V duration re-check.

**`/video-package`** — one locked title, three distinct thumbnail bets, one value-forward
description, honesty guardrail (the frame may promise only what the video keeps). Emits thumbnail
*concepts*; image prompts are handed to `ai-image-carousel-prompt-gen` by soft reference. With that
plugin absent, it prints the raw concept briefs and says so. CTR rules ship as uncalibrated defaults
and must be labelled as such until the user has their own data.

### 5. Changes to existing files

| File | Change |
|---|---|
| `.claude-plugin/plugin.json` | `name` → `gaspol-video`; `version` → `3.0.0`; description and keywords cover post-production |
| `skills/video-script/SKILL.md` | Phase 3 assigns every scene `scene_type: live-action \| explainer`; explainer scenes get no platform mode and no keyframe requirement |
| `skills/video-image/SKILL.md` | Phase 4B skips `explainer` scenes; Phase 4A assets still generated if an explainer shot needs them |
| `skills/video-gen/SKILL.md` | Step 5.0a rewritten from "voice consistency plan" to **binding audio-source selection** (platform-native / ElevenLabs / mixed per scene). Under ElevenLabs: VO generated first, measured duration sets clip duration; prompts for those scenes carry no dialogue line and add the explicit negative `no speech, no voiceover, no dialogue`; SFX and ambience stay |
| `skills/video-full/SKILL.md` | Steps 5 (explainer), 6 (post), 7 (package) added; production summary lists the new outputs |
| `skills/video-validate/SKILL.md` | New checks C5-C8 (below) |
| `reference/creator-profile-system.md` | `VOICE:` block per cast member (provider, voice id reference, model, settings, source = tts \| native+changer). **Voice ids are read from the user's `.env`, never written into the repo** — the plugin stays client-agnostic per its own CLAUDE.md rule |
| `reference/image-video-gen/09-voice-consistency-workflow.md` | Path B section points at the executable tools; cross-links the new voice-cast reference |
| `CLAUDE.md` | New phases, new reference table rows, new debugging rows, version 3.0.0, ticket counter |
| `README.md` | Rename, new commands, dependency table (ffmpeg / Node / ElevenLabs key), degradation policy |
| `hooks/session-start.sh` | Announces the three new skills |
| `LICENSE` (new) | MIT, Ali Sadikin |
| `NOTICE` (new) | Attribution: portions adapted from `hassancs91/claude-youtube-editor` (MIT), naming which methods were adopted |

New reference files under `reference/post-production/`:

| File | Content |
|---|---|
| `10-post-production-pipeline.md` | Phase 6 overview, project folder contract, all plan-file schemas, degradation policy |
| `11-voice-cast-and-vo.md` | Voice cast model, audio-source decision tree, mixed-source rule, Voice Changer workflow, VO-first duration budgeting, prompt-muting rules |
| `12-remotion-explainer.md` | When a scene is explainer, TSX crash rules, brand-token binding, legibility floors, per-cue still verification |
| `13-ffmpeg-edit.md` | `edit-plan.json` schema, trim/pad/retime decisions, insertion of explainer shots, A/V duration gate, playable transcode |
| `14-sfx-design.md` | Domain-aware cue derivation, library-first sourcing, `sfx-plan.json` schema, gain calibration table, RMS audibility method and its pitfalls (transient windows, cues under continuous speech) |
| `15-packaging.md` | Title/bet/description rules, honesty guardrail, CTR calibration, hand-off contract to the image plugin |
| `16-subtitles-and-captions.md` | When captions are required per platform, SRT build from owned text, AssemblyAI fallback policy and derived keyterms, burn-in style contract, legibility and safe-area rules, the "no subtitles" prompt rule and why it does not conflict |
| `17-music-bed.md` | Reading music direction from `av-script.md`, track selection, fade in/out, level under voice, fail-soft rule, interaction with SFX ducking |

New scripts under `tools/` (each degrades with a printed manual command):

| Script | Origin |
|---|---|
| `gen_vo.mjs` | Adapted from editor |
| `voice_changer.mjs` | **New** — ElevenLabs speech-to-speech |
| `gen_sfx.py`, `mix_sfx.py` | Adapted from editor |
| `edit_render.py` | New, informed by editor's `render_cuts.py` / `cutlib.py` |
| `composite.py` | Adapted from editor's `bake.py` (explainer shot over clip) |
| `probe_clips.py` | New — ffprobe inventory of `{output_folder}/clips/` into `clip-manifest.json` |
| `gen_subs.py` | New — SRT from owned text + TTS timestamps; AssemblyAI (as in the editor's `transcribe.py`) for platform-spoken dialogue; keyterms derived from the brief; script-alignment repair from `MoneyPrinterTurbo` |
| `burn_subs.py` | New, style rules from `MoneyPrinterTurbo` `video.py` — burn-in with font/stroke/position/wrap, font-supports-text and contrast checks |
| `mix_music.py` | Adapted from editor's `mix_music.py`, fail-soft behaviour from `MoneyPrinterTurbo` |

### 6. Project folder contract (additions)

```
{output_folder}/
  clips/                 user-uploaded generated clips (one per scene/extension)
  shots/                 Remotion workspace + rendered explainer shots
  vo/                    generated narration + changed-dialogue audio
  sfx/                   per-project generated cues (library lives outside the project)
  work/
    clip-manifest.json   ffprobe inventory
    audio-plan.json      time-layered audio per scene
    edit-plan.json       assembly instructions
    sfx-plan.json        cue sheet (user-audited before mixing)
  output/                master + mixed deliverables
```

### 7. New validator checks

| Check | Rule |
|---|---|
| **C5** | No double audio: a scene whose audio source is ElevenLabs must have no `says:` / `Voice-over narrator:` line in its platform prompt, and must carry the `no speech, no voiceover, no dialogue` negative |
| **C6** | Every scene marked `explainer` has a rendered shot; no explainer scene has an NB2 keyframe or a platform prompt |
| **C7** | Rendered master v:0 duration equals a:0 duration |
| **C8** | Every cast member with a speaking line has a `VOICE:` block resolving to a configured voice; a locked-voice character never appears with an un-changed platform voice in the final mix |
| **C9** | Every subtitle cue's text matches the script line it came from (no ASR drift), sits inside the master's duration, and does not overlap the next cue |
| **C10** | The music bed never peaks above the voice at any measured window, and a failed music mix leaves a shipped voice-only master plus a recorded warning — never a missing file |

### 8. Data Integration Map

| Component | Data source | Exists today? | Notes |
|---|---|---|---|
| Cast voice profile | `cast-profile.md` `VOICE:` block + user `.env` | No | New field; ids stay out of the repo |
| Narration text | `av-script.md` narration column | Yes | Used verbatim as TTS input |
| Clip duration budget | measured length of generated VO mp3 | No | Replaces word-count estimation |
| SFX cues | `strategic-brief.md` DOMAIN CONTEXT + cultural research + visual beat | Yes | The named delta over the editor |
| Explainer shot tokens | `strategic-brief.md` brand section | Yes | No bundled palette |
| Thumbnail prompts | delegated to `ai-image-carousel-prompt-gen` | Yes (other plugin) | Soft reference; degrade loudly |
| Generated clips | `{output_folder}/clips/` (user-supplied) | No | New folder contract |
| Explainer shot timing | scene VO mp3 when present, else `scene-plan.md` duration | Partly | Word-time sync only exists when VO is generated here |

### 9. Distribution

- `gaspol-one` `marketplace.json` gains a `gaspol-video` entry with `source: url` →
  `https://github.com/alisadikinma/gaspol-video.git`, mirroring version `3.0.0` per the version
  duplication contract in the KB.
- Local `local-dev` marketplace entry is repointed to `./gaspol-video` for development iteration.
- Old install must be uninstalled once by hand; a renamed plugin does not upgrade in place.

### 10. Known risks

1. **Voice Changer over a platform-generated dialogue clip is unproven here.** Speech-to-speech is
   expected to preserve duration and rhythm, so lip-sync should survive. This must be proven with one
   real clip in the first implementation phase, before the workflow is written as settled.
2. **Remotion scaffolding is heavy per project** (~300MB of `node_modules`). Accepted as the cost of
   keeping the plugin repo clean and client outputs separate.
3. **First gaspol plugin to want external binaries** (`ffmpeg`, Node). Hard rule: no skill may fail
   because a binary is missing; it degrades to printed commands and says which capability was lost.
4. **The old plugin name is embedded in VPS compiled reference bundles**, `~/CLAUDE.md`, 7 vault
   files, and Portfolio_v2 memory. A missed reference makes `/video-*` fail silently on the VPS.
   Renaming those references is part of this ticket, not a follow-up.
5. **CTR packaging rules are inherited from another channel's data.** They must ship labelled as
   uncalibrated defaults; quoting a target CTR the user has not measured is forbidden.

### 11. Out of scope

- `clean-cut` (raw-footage transcription and take selection), `brand-setup`, YouTube upload, and
  channel analytics from the editor.
- Rendering thumbnail images inside this plugin.
- Any hard dependency declaration on `ai-image-carousel-prompt-gen` — routing is by soft reference
  only, so a broken third-party entry cannot disable this plugin.
- From `MoneyPrinterTurbo`: stock-footage matching (`material.py`), the LLM script writer, the
  Streamlit WebUI, the FastAPI service and its redis task queue, moviepy as a render engine,
  `edge-tts` as a second voice provider, and `faster-whisper` as a local ASR model (AssemblyAI is used
  instead, matching the editor).
