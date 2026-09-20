# gaspol-video

**v3.5.0** — Claude Code plugin that carries a promotional video from an idea to a finished, mixed file: brainstorm, script, image prompts (NB2, with an in-session render offer), video prompts (VEO 3.1 / Seedance 2.0 / Kling 3.0, with a VEO 3.1 fast render offer), believable app screens and screencasts for software that does not exist yet, Remotion shots for anything that must be readable, then post-production — word-by-word kinetic captions and title cards, automatic shot motion — and packaging. Delivery is per kelompok — a batch of at most 5 scenes is carried to a reviewable cut before the next batch starts — and every prompt passes a physical plausibility gate before a credit is spent.

Anyone — video agencies, freelancers, brand owners — can produce a professional 2-3 minute promotional video by following the generated plan and running the tools it calls.

> **v3.5.0 — captions that reveal word by word, title cards, and shots that no longer hold still.**
> `tools/gen_captions.py` builds a per-scene caption plan from timings this plugin already has —
> ElevenLabs word timings, or AssemblyAI aligned back onto the script so caption text always traces
> to `av-script.md`, never to the recognizer — and scores one highlighted key phrase per page.
> `Captions.template.tsx` renders it as a kinetic word-by-word reveal; `TitleCard.template.tsx` draws
> an eyebrow-plus-title card at a topic boundary and holds captions clear of it for 2.5s. A shot that
> would otherwise hold still for more than five seconds now gets automatic zoom —
> `tools/plan_motion.py` fills `work/edit-plan.json`'s new `motion` field, `tools/edit_render.py`
> renders it with `scale=...:eval=frame,crop` (not `zoompan`, which rounds pan position to whole
> pixels and stutters). No Node or no Remotion workspace falls back to the plain burned-in SRT the
> plugin already had. See [v3.5.0 Changelog](#v350-changelog).

> **v3.4.0 — the plugin asks whether the shot is possible, not just whether the prompt is compliant.**
> Nine defect classes measured on a real film — an impossible fuel filler, duplicated gates and
> nozzles, an upside-down phone, an arrival framed exactly like a departure, two characters reading
> as one person, overlays that cannot attach, broken pairs, a story claim that never closed, and
> narration longer than its cut — all of them found by the client AFTER the render was paid for, and
> all of them passing the existing compliance checks. Every Phase 4B and Phase 5 prompt now carries a
> seven-question `PLAUSIBILITY:` block, the script passes a flow gate, and the reviewer runs checks
> K1-K7 and C12. New `tools/track_screen.py` finds a screen's four corners by fitting its edges, and
> `templates/remotion/lib/quad-screen.tsx` maps a panel onto them by homography, which is what a
> panel on an off-axis monitor actually needs. Two defects became scripts instead of prose:
> `check_vo_duration.py` and `check_overlay_strings.py`. See [v3.4.0 Changelog](#v340-changelog).

> **v3.3.0 — folder contract.** Nine folders per project and no others; variants are distinguished
> by a filename suffix, derived files live in `.tmp/`, rejected paid artefacts in `_arsip/` with the
> reason in the name. Written after a project reached 25 folders and nobody could tell which were
> safe to delete. See [v3.3.0 Changelog](#v330-changelog).

> **v3.2.0 / v3.2.1 — the kelompok is the unit of delivery, and rejects stop repeating.** A Phase 5
> batch (one ACT, max 5 scenes) is now carried all the way to a reviewable cut — VO, clips, voice
> change, Remotion, kelompok cut, approval — before the next batch starts, so narration length and
> overlay text are checked while a fix is still cheap. 3.2.1 adds the reject loop: after the SECOND
> reject with the same defect, stop re-prompting and inspect the keyframe, the identity ref, then the
> physics. See [v3.2.0 Changelog](#v320-changelog).

> **v3.1.0 — the plugin can render, not just prompt.** Phase 4 and Phase 5 now offer to render the
> approved batch in-session through the `indusia-image-gen` (`nano-banana-2`) and
> `indusia-video-gen` (`veo-3.1-fast`) MCP servers, tracked in `renders.json` so an unchanged prompt
> never re-renders. `tools/gen_app_screen.py` captures a real app with Playwright or mocks one in
> Remotion, and a new screencast shot type animates it in Phase 4.5. `tools/verify_render.py` (Check
> P6) transcribes the finished master a second time and diffs it against the script. Plus
> `gen_music.py`, `clean_voice.py`, `composite.py split/insert`, `make_stems.py`,
> `composite_logo.py`, `thumb_scrim.py` and `yt_stats.py`. See [v3.1.0 Changelog](#v310-changelog).

> **v3.0.0 — the plugin now finishes the video.** Phases 4.5, 6 and 7 are new: `/video-explainer`
> renders scenes that must be READABLE as coded Remotion shots (no video platform renders legible
> text); `/video-post` builds the voice-over, assembles with ffmpeg under an A/V duration gate,
> scores domain-aware SFX, burns captions taken from the script, lays a music bed and mixes;
> `/video-package` decides the title, three thumbnail bets and the description.
> Renamed from `ai-video-promo-engine`. See [v3.0.0 Changelog](#v300-changelog).

> **v2.4.0 expansion:** Cross-platform voice-over consistency workflow added. New reference `09-voice-consistency-workflow.md` covers 3 solution paths (native voice lock per platform, ElevenLabs Voice Changer post-prod, single-VO sync), prompt-level discipline rules, hybrid workflows per video type. New Step 5.0a Voice Consistency Strategy in Phase 5 runs BEFORE platform selection. Mandatory for any video with >1 scene or character voice continuity. See [v2.4.0 Changelog](#v240-changelog).

> **v2.3.1 fix:** Bahasa Indonesia audio support clarified as two-tier — Voice-over narrator SUPPORTED NATIVELY in Kling 3.0; only on-screen lip-sync restricted to 5 langs.

> **v2.3.0 expansion:** Kling 3.0 added as 3rd video platform peer alongside VEO 3.1 (primary) and Seedance 2.0. New: 5-part Kling prompt formula, per-second granular duration (3-15s), multi-shot storyboarding (6 shots in single render), mixed-language scene support, Motion Control sub-model. Platform selection step added to Phase 5 with per-scene routing in Mixed mode. See [v2.3.0 Changelog](#v230-changelog) below.

> **v2.2.0 hardening:** 4 enforcement rules close gaps that previously allowed mid-production restructures — BODY 1 narrative completeness, NB2 reference uniqueness filter, max 5 inline refs per prompt, and environment-gated cross-scene references. See [v2.2.0 Hard Rules](#v220-hard-rules) below.

## What It Does

Give it a product or service, and the engine walks you through the pipeline, Phase 1 to Phase 7:

1. **Brainstorm** — language selection, cast builder (1-5 characters), institution detection, target market, awareness level, storyline input, tone/mood selection
2. **Script** — 2-3 min A/V script with 7-beat narrative arc (or 6-stage user framework alias: HOOK → Foreshadow → BODY 1 → BODY 2 → Peak → Ending+CTA), beat labels, timing, narration, audio direction. v2.2.0+: BODY 1 Completeness rule enforces ALL identified pains dramatized as dedicated scenes.
3. **Scene Breakdown** — auto-calculated scene count, VEO mode per scene, extension strategy
4. **Reference Collection** — auto-derive ref manifest, cultural location research, batch NB2 prompts for missing refs, hard-block validation gate
5. **Image Prompts (NB2)** — Phase 4A: asset library (atoms with dependency graph) → Phase 4B: scene keyframes (molecules composed from assets)
6. **Video Prompts (VEO 3.1 / Seedance 2.0 / Kling 3.0)** — per-scene prompts with camera movement, 3-layer audio, lip sync, extensions, vocal performance direction. Phase 5 starts with platform selection (or Mixed for per-scene routing). VEO 3.1: broadcast cinematic, prompt-faithful, 8s + extend to 148s. Seedance 2.0: native 2K, @ reference system (12 assets), dual-branch AV, 10+ lip-sync languages, unlimited extension. **Kling 3.0 (new in v2.3.0):** 5-part prompt formula, per-second duration (3-15s), multi-shot storyboard (6 shots in single render), mixed-language scene unique, Motion Control sub-model, omni audio (5 languages — no Bahasa Indonesia lip-sync)

6.5. **Explainer Shots (Remotion)** — scenes whose Render Path is `explainer` are coded, not generated: metrics, diagrams, tables, UI walkthroughs. Decided at Phase 3, before any NB2 credit is spent. Reveals are timed to the narration, and each cue is verified by looking at a still.
7. **Post-Production** — five passes in a fixed order: voice-over (ElevenLabs TTS plus speech-to-speech for platform-spoken dialogue), ffmpeg assembly under an A/V duration gate, domain-aware SFX scored from the brief's DOMAIN CONTEXT, captions built from the script with AssemblyAI supplying timing only, a music bed that ducks under the voice, then the final mix.
8. **Packaging** — one locked title, three thumbnail bets on different levers, one value-forward description, with an honesty guardrail that keeps the frame's promise inside what the video delivers.

Each phase has a user approval gate before proceeding. Phase 3.5 (Reference Collection) is a hard block — 100% of reference images must be validated before image generation. The Phase 6 SFX cue sheet is a second hard gate: nothing is mixed until you have read it.

## Requirements

| What | Needed for | If missing |
|---|---|---|
| Claude Code | everything | — |
| `ffmpeg` / `ffprobe` on PATH | Phase 6 assembly, SFX, captions, music, mix | Plans are still written and printed; nothing is rendered, and the skill says so |
| `node` 20+ | voice-over and voice changing | Those passes are skipped, named, not silently dropped |
| `python3` | most tools (stdlib only, no pip install) | — |
| `bash tools/setup.sh` (builds `~/.gaspol-video/venv`) | app-screen capture/mock, thumbnail post-process, YouTube stats (Pillow, Playwright, google-api-python-client) | The tool exits 2 naming the script; every stdlib-only tool keeps working |
| `ELEVENLABS_API_KEY` in `.env` | voice-over, voice changing, SFX generation, music bed generation, voice cleanup (isolate method) | Dialogue stays in the platform's own voice; every recipe that could not be made is listed with its prompt |
| `ASSEMBLYAI_API_KEY` in `.env` | caption timing for platform-spoken dialogue, and Check P6 (render verification) | Those scenes are listed as untimed; P6 reports SKIPPED, never PASS |
| Node + `npx` | Remotion explainer shots, screencasts, mock app screens | Shot source is still written; rendering is left to you |
| YouTube OAuth client under `~/.gaspol-video/youtube/` | `yt_stats.py` packaging calibration | Calibration has no real view/watch-time data; CTR is always manual regardless |

Copy `.env.example` to `.env` and fill in the values. **`.env` is gitignored and the repo only ever
names variables, never their values** — a voice id identifies one person's cloned voice on one
account, and does not belong in a plugin.

**Nothing degrades silently.** Every tool that cannot do its job says what it could not do and what
to run to fix it, then lets the rest of the pipeline continue.

## Installation

### Via Claude Code Marketplace (Recommended)

```bash
# Step 1: Add marketplace source
claude plugins marketplace add alisadikinma/ai-content-suite

# Step 2: Install plugin
claude plugins install gaspol-video
```

### Manual Installation

Clone into your Claude Code plugins directory:

```bash
# macOS / Linux
git clone https://github.com/alisadikinma/gaspol-video.git \
  ~/.claude/plugins/gaspol-video

# Windows
git clone https://github.com/alisadikinma/gaspol-video.git ^
  %USERPROFILE%\.claude\plugins\gaspol-video
```

Then restart Claude Code. The plugin auto-registers on session start.

## Usage

### Full Pipeline (End-to-End)

```
/video-full
```

Starts the full interactive pipeline. The orchestrator runs all 7 production skills in sequence, asking questions and generating outputs phase-by-phase with approval gates. It stops before Phase 6 until you have actually rendered the platform clips — post-production runs on video, not on prompts.

**Flags:**
- `--full` (default) — full production plan with storyboard notes, NB2 prompts, VEO prompts, audio specs, extension strategy, post-production checklist
- `--quick` — copy-paste ready prompts only (NB2 + VEO per scene, no production plan)
- `--preset ali` — use Ali Sadikin creator preset instead of generic brand profile

### Individual Skills

Run any phase independently:

```
/video-brainstorm      # Phase 1: brainstorm, cast, product, location, domain research
/video-script          # Phase 2-3.5: script, scene breakdown, reference collection
/video-image           # Phase 4: NB2 asset library + scene keyframes
/video-explainer       # Phase 4.5: Remotion shots for scenes that must be readable
/video-gen             # Phase 5: image review + VEO / Seedance / Kling prompts
/video-post            # Phase 6: voice-over, edit, SFX, subtitles, music, final mix
/video-package         # Phase 7: title, thumbnail bets, description
```

### Utility Skills

```
/video-validate            # Unified validator (--script / --image / --video / --refs / --post / --all)
/video-add-platform        # Scaffold support for a new AI video platform
```

### Agents

- **`video-engine-agent`** — handles batch or complex promo work, can be dispatched for parallel processing
- **`video-prompt-reviewer`** — independent validator for NB2/VEO prompt batches (auto-spawned during Phase 4B and Phase 5)

## Production Stack

| Component | Technology |
|-----------|------------|
| Image Generation | Nano Banana 2 (NB2) — Gemini 3.1 Flash Image |
| Video Generation (Primary) | VEO 3.1 — 720p/1080p, 8s clips, 148s extension chain |
| Video Generation (Alt) | Seedance 2.0 — native 2K, 15s clips, @ reference system, dual-branch AV |
| Pipeline (VEO) | NB2 image → VEO First+Last Frame / Ingredients → VEO Extend |
| Video Generation (Alt) | Kling 3.0 — per-second duration 3-15s, multi-shot storyboard, omni audio |
| Pipeline (Seedance) | NB2 image → Seedance @Image refs + Omni mode → Seedance @Video extend |
| Readable Shots | Remotion — coded animation for metrics, diagrams, tables, UI |
| Voice | ElevenLabs `eleven_multilingual_v2` (TTS) and `eleven_multilingual_sts_v2` (voice changing) |
| Caption Timing | AssemblyAI. Caption TEXT always comes from the script, never from the recognizer |
| Assembly and Mix | ffmpeg — concat, sidechain duck, loudnorm, burned subtitles |
| Screen-Attached Overlays | `tools/track_screen.py` (four-corner tracking) + CSS `matrix3d` homography in `QuadScreenTracked` |

## Key Features

- **Multi-Character Cast System** — 1-5 characters with Pemeran Utama/Pendamping roles, per-character identity lock, institution-aware costume detection
- **Language Selection** — Bahasa Indonesia, English, or Bilingual (NB2/VEO prompts always English)
- **6 Tone/Mood Options** — Humorous, Serious, Professional, Inspirational, Casual, Edgy — affects cinematography, audio, and expression across all phases
- **5 Target Markets** — C-Level, VP/Director, Manager, Individual Contributor, Social Media — each with adapted tone, depth, and CTA style
- **5 Awareness Levels** — Unaware → Most-Aware routing to different narrative strategies
- **7-Beat Universal Arc** — Pattern Interrupt → Hook → Foreshadow → Agitate → Guide+Plan → Peak → CTA → Won Day. **v2.2.0+: also exposed as 6-stage user framework alias** — HOOK → Foreshadow → BODY 1 (Problems) → BODY 2 (Solutions) → Peak → Ending+CTA. Internally identical, user-facing simpler.
- **Asset-First Production with Uniqueness Filter (v2.2.0+)** — recurring elements (2+ scenes) auto-detected and generated as standalone assets BUT filtered by uniqueness criterion (UNIQUE → generate, COMMON generic items → skip and render from text). Dependency graph and tier system. Max 5 inline references per Phase 4B prompt enforced.
- **Film Directing Guide** — 180° rule, gaze direction, actor blocking, vocal performance direction, natural acting methodology, visual continuity supervision
- **Reference Image Validation Gate** — Phase 3.5 hard block with 5 ref categories, cultural location research (5 facts per location), batch NB2 prompt generation for missing refs
- **37 Reference Documents** — storytelling psychology, cinematography lookup, hook vault (100 hooks), CTA frameworks, directing grammar, platform adaptation, Seedance 2.0 production guide, the physical plausibility gate, and more
- **Scene Auto-Calculation** — optimal scene count from script beats with VEO mode mapping
- **Dual Video Platform Support** — VEO 3.1 (primary) + Seedance 2.0 (alt) with platform-specific prompt generation, camera libraries, and audio specs
- **Seedance 2.0 Integration** — native 2K resolution, @ reference system (9 images + 3 videos + 3 audio), dual-branch AV generation, 3-Angle Rule identity lock, 10+ lip-sync languages including Indonesian, timestamp-based multi-shot storyboarding
- **Extension Strategy** — VEO Extend (up to ~148s chains) or Seedance @Video extend (unlimited chains, drift ~20th hop)
- **"Last Frame Secret"** — seamless scene transitions by feeding Clip A's final frame into Clip B's NB2 start frame
- **Image Review Before Video** — per-scene collaborative review where AI reads actual keyframe images (multimodal), compares with NB2 prompts, and brainstorms VEO approach with user before generating video prompts
- **Physical Plausibility Gate (v3.4.0)** — seven questions answered per prompt (mechanism, count, flow, facing, pair, people, overlay surface), each answer also present in the prompt text. Catches impossible mechanisms, duplicated objects, flipped devices and unreadable direction before the render is paid for
- **Flow Gate on the script (v3.4.0)** — a measurement claim must close its loop (reading before, event, reading after, resulting number), every scene answers "what changed?", and an object that is carried is visible in frame
- **Screen-accurate overlays (v3.4.0)** — `track_screen.py` fits each screen edge to a line and intersects them for four per-frame corners; `QuadScreenTracked` maps the panel on by homography. Refuses to track a surface under 120px wide and tells you to use a floating card instead
- **Per-Kelompok Delivery (v3.2.0)** — a batch of at most 5 scenes reaches a finished, narrated cut before the next batch starts, instead of rendering every clip and discovering audio problems at the end
- **Reject Loop (v3.2.1)** — the second identical reject stops the prompting and sends you to the input: keyframe, identity ref, requested physics. Rejects are archived with the reason in the filename, so `ls _arsip/` reads as a defect histogram
- **Folder Contract (v3.3.0)** — nine folders, no new ones; `.tmp/` for anything rebuildable, `_arsip/` for paid rejects
- **Cross-File Validation** — unified validator with 5 targets: script, image, video, refs, all
- **Kinetic Captions (v3.5.0)** — word-by-word reveal with one highlighted key phrase per page, built from timings this plugin already has (ElevenLabs word timings, or AssemblyAI aligned back onto the script so caption text always comes from `av-script.md`). Falls back to the plain burned-in SRT when Node or the Remotion workspace is unavailable
- **Title Cards (v3.5.0)** — an eyebrow-plus-title card at a topic boundary, declared on the left or right third in `scene-plan.md` so it never covers a speaking face, holding captions clear of it for 2.5s
- **Automatic Shot Motion (v3.5.0)** — any static segment over five seconds gets alternating punch-in/punch-out zoom beats from `tools/plan_motion.py`, rendered with a per-frame `scale`+`crop` chain (not `zoompan`, which stutters on a slow move); a hand-written `motion` is never overwritten

## Storytelling Philosophy

> Product is NEVER the hero. Product is the BRIDGE. Customer is the hero. Brand is the guide.

The script engine enforces **9 commandments (v2.2.0+)** (no opening with brand name, no jargon without translation, every feature needs a human consequence, **BODY 1 must dramatize ALL identified problems**, etc.) and auto-checks for 22+ structural failure patterns.

## v3.5.0 Changelog

**Kinetic captions, title cards, and automatic shot motion (GV-7).** Word timings already existed
in `vo/vo-manifest.json`; nothing here invents data — Remotion draws the text, ffmpeg does the zoom.

- **`tools/caption_keywords.py`** scores candidate highlight spans in a scene's word list —
  number+unit, a brand term from `gen_subs.derive_keyterms()`, an acronym, or a reversal word —
  and returns the non-overlapping, highest-scoring spans with the rule and score that picked them.
- **`tools/gen_captions.py`** builds `work/caption-plan.json`: per-scene words and highlights from
  `vo/vo-manifest.json`, or from AssemblyAI for platform-spoken dialogue. `align_to_script()` keeps
  the contract every caption tool in this plugin already states — caption TEXT always comes from
  `av-script.md`, timing may come from a recognizer, the text never does — by matching the
  recognizer's words onto the script's own words with `difflib.SequenceMatcher` and interpolating
  timing for anything the recognizer missed. Reusable and deterministic: re-running on unchanged
  inputs reuses the existing plan and exits 0; `--force` regenerates it byte-identical apart from
  `generated_at`. Also parses `scene-plan.md`'s new `Title Card` column and computes
  `captions_held_until_s` so a title card and the kinetic captions never compete for the same
  reading order.
- **`Captions.template.tsx`** (`KineticCaptions`) renders a stack of up to three caption lines: the
  line being spoken at full opacity, others dimmed, each word appearing at its own timing, a
  highlighted span boxed in `accent` that grows from zero width. Its page/word/highlight arithmetic
  lives in **`captionPages.mjs`**, which has zero imports on purpose — this repo has no
  `node_modules` and deliberately no npm, so the tested part of a Remotion composition still runs
  under bare `node --test`.
- **`TitleCard.template.tsx`** (`TitleCard`) draws an accent eyebrow over a display title, declared
  `left` or `right` in `scene-plan.md` so a card never covers a speaking face, with a 2.5s hold.
- **Two contrast thresholds**, not one: ordinary caption text (`ink` on `background`) still needs
  `burn_subs.py`'s existing 4.5:1; a highlight box's own text only needs WCAG AA's large-text floor,
  3:1, since caption text here is never smaller than 32px. `check_brand_contrast(brand)` measures
  both and writes the winning token into `style.highlight_text_token`, so the component reads a
  decision instead of making one.
- **`work/edit-plan.json` gains a `motion` field** (`{"kind": "punch-in", "from": 1.0, "to": 1.08}`,
  `punch-in`/`punch-out`/`none`, `1.0`-`1.12`) and `tools/edit_render.py` renders it with
  `scale=...:eval=frame` then a fixed `crop` — not `zoompan`, which rounds pan position to whole
  pixels and stutters on a slow move, and not an animated `crop`, which ffmpeg refuses to configure
  with a `t` expression on `w`/`h`. Verified by rendering a synthetic clip and measuring PSNR, not
  by string-matching the filter.
- **`tools/plan_motion.py`** fills that field automatically: a segment over 5.0s splits into
  `ceil(duration / 5.0)` alternating punch-in/punch-out beats as separate segments; 5.0s or under
  gets one slow punch-in. A hand-written `motion`, and any `kind: "shot"` segment (a Remotion shot
  already animates itself), are left exactly as they are — running the tool twice reports zero
  changes on the second run.
- **Wired into `/video-post`.** Pass 2 runs `plan_motion.py` after the edit plan is authored and
  before it renders. Pass 4.1 runs `gen_captions.py` alongside the unchanged `gen_subs.py` SRT
  sidecar (YouTube still needs it), renders `KineticCaptions`/`TitleCard` per scene through the
  Remotion workspace, and composites each over the master with `tools/composite.py overlay`. No
  Node or no Remotion workspace falls back to the plain burned-in SRT path this plugin already had.
- **`@remotion/captions`** (`createTikTokStyleCaptions()`) is the one new dependency, added to
  `templates/remotion/scaffold.mjs`; every `tools/` file stays stdlib-only.

## v3.4.0 Changelog

**Physical Plausibility Gate.** New `reference/image-video-gen/10-physical-plausibility-gate.md`
records nine defect classes measured on one production. Every one was found by the client after the
render was paid for, and every one passed checks A-J: the prompts were compliant, the objects were
impossible.

| Class | What happened |
|---|---|
| Impossible mechanism | A fuel filler drawn on the SIDE of a truck tank (a full tank would spill); a closed cap on a tank being filled |
| Duplicated objects | Two boom barriers and two RFID antennas at one gate; a nozzle that became two at 3.5s; a telephone handset that reappeared on a stapler |
| Wrong orientation | A phone upside down, then screen face-down; a proof photo shot from the wrong side |
| Unreadable direction | A truck arriving framed exactly like the truck leaving — the viewer cannot tell a return from a departure |
| Characters read as one person | A male admin, back to camera, read as the protagonist from another angle. Rejected once, then repeated |
| Overlay cannot attach | A panel mapped to an upright rectangle while the screen was a trapezoid (left edge 524px, right edge 375px); a guard-post screen measuring 60x45px |
| Continuity break across a pair | The same sensor drawn with a different body; an evening clip drifting back to midday while its card says 16:05 |
| Story logic hole | "Parts leave the store" with empty hands; a fuel sensor that never produced a consumption number |
| Sound/picture mismatch | A number spoken at 6.34s while its text finished appearing at 6.8s; a 6.87s line cut into a 6.0s clip |

- **Seven-question `PLAUSIBILITY:` block** on every Phase 4B keyframe and Phase 5 platform prompt:
  MECHANISM, COUNT, FLOW, FACING, PAIR, PEOPLE, OVERLAY SURFACE. Each answer must also appear in the
  prompt text — an answer only in the block is a note to nobody. `video-image` Rules 35-36,
  `video-gen` Rules 21-22, `video-explainer` Rules 9-10.
- **Flow gate on the script.** `video-script` gained four rules: close the loop (a measurement claim
  needs reading-before, event, reading-after and a resulting number), every scene answers "what
  changed?", a carried object is visible in frame, and repeated locations are recorded as PAIRS with
  identical-vs-differ columns.
- **Post-render frame audit.** Three frames per clip (≈1s, mid, 0.5s before the end) checked for
  count, facing, mechanism, teleporting objects, direction and light drift. Count/facing/mechanism
  failures re-render; a light-only drift is graded in assembly, not re-bought.
- **Validator checks K1-K7 and C12** in `video-prompt-reviewer`.
- **`tools/track_screen.py`** — four-corner screen tracking. Flood fill from a seed inside the
  screen, each edge fitted by least squares over its middle 20-80%, the four lines intersected,
  corners smoothed with an EMA, QA frames written with the corners drawn. Exits 2 when the screen is
  under 120px wide (use a floating card) or when the fill covers less than 85% of the fitted quad
  (the threshold is too high). Replaces four ad-hoc measuring attempts that each shipped a visibly
  wrong panel: a bounding box on a trapezoid, corners taken as extreme points, a brightness
  threshold of 210 that left the dim half of the screen full of holes, and corners measured once and
  reused while the camera drifted.
- **`templates/remotion/lib/quad-screen.tsx`** — `QuadScreen` and `QuadScreenTracked` map a panel
  onto four (moving) corners by homography, expressed as CSS `matrix3d`.
- **`tools/check_vo_duration.py`** fails when narration does not fit its cut, or when a cut runs on
  in silence past a tolerance. **`tools/check_overlay_strings.py`** reads the rendered Remotion
  components and fails on any on-screen string missing from the script's approved list, expanding
  `X 1 of 6` … `X 6 of 6` series.

## v3.3.0 Changelog

- **Folder contract, enforceable rather than implied.** Nine folders per project — `ref/`
  `keyframes/` `clips/` `vo/` `shots/` `output/` `work/` `_arsip/` `.tmp/` — and no others without
  the user's approval. Variants are distinguished by a filename suffix, never a new subfolder.
  Written after a project reached 25 folders: seven of preview JPEGs, seven of "temporary" copies
  nobody deleted, three differently named archives, and a user who could no longer tell what was
  safe to delete. `reference/post-production/10-post-production-pipeline.md` §2.1-§2.3, plus a
  numbered Hard Rule in `video-image`, `video-gen`, `video-explainer` and `video-post`.
- **MCP renders land in `{output_folder}/.tmp`**, not `.render-tmp/`. `voice_changer.mjs` writes its
  intermediates to the project's `.tmp/` (overridable with `GASPOL_TMP_DIR`), not to `vo/.work/`.
- **Never `sips --out <folder>/<file>`** — it replaced the target FOLDER with a single image twice,
  destroying every preview in it. Use `ffmpeg -vf scale`.

## v3.2.0 Changelog

- **The kelompok is the unit of delivery.** The Phase 5 batch (one ACT, at most 5 scenes) is carried
  to a reviewable cut before the next batch starts: VO, clips, voice change, Remotion, kelompok cut,
  approval. Previously every clip was finished first and Phase 6 started afterwards, so narration
  length, overlay text and lip sync were only checked once all clips existed — and a fix meant
  re-rendering clips already approved on picture alone. Passes 3-5 stay global and run once in
  `/video-post --final` over the approved cuts. `work/kelompok.json` records the state per batch.

### v3.2.1

- **The reject loop.** After the SECOND reject carrying the same defect, stop prompting and inspect
  the input in order: keyframe, identity ref, requested physics, then the prompt. Five revision
  rounds on a real film spent nine video renders rediscovering four defects that were visible in
  their source stills. Rejects are archived with the reason in the filename, so `ls _arsip/` reads
  as a defect histogram. A regenerated keyframe invalidates its clip, voice change, composites and
  cut.
- **Three-angle face references** — a front-only reference survived five renders as "not similar at
  all". Plus the 10 MB per-image API cap, and a keyframe inspection checklist: count the hands,
  check every prop's state, reject anything the script did not ask for.
- **"Motion VEO Will Not Do"** in the VEO guide: liquid transfer in a wide shot, fine hand
  manipulation, a screen face-on in a handheld shot, one object doing two contradictory things.

## v3.1.0 Changelog

- **In-session rendering.** Phase 4 and Phase 5 now offer to render the approved batch instead of
  only writing copy-paste prompts — NB2 stills via `mcp__indusia-image-gen__generate_image`
  (`nano-banana-2`), VEO clips via `mcp__indusia-video-gen__generate_video` (`veo-3.1-fast`).
  Rendering is always an offer per batch, never automatic, and every output is tracked in
  `renders.json` so an unchanged prompt is never re-billed. Seedance, Kling, Scene Extension, and
  durations/aspects the MCP does not accept stay copy-paste.
- **App screens and screencasts.** `tools/gen_app_screen.py capture` drives Playwright against a
  real URL; `mock` renders a Remotion TSX component to a still for software that does not exist yet.
  A new `Screen Source` column on the Scene Breakdown table routes these scenes away from NB2
  entirely, and a screencast shot type animates the result in Phase 4.5, timed to the narration.
  Simulated screens are flagged in `screens/manifest.json` so packaging never claims a mock as a
  shipped feature.
- **`gen_music.py`** fills the empty `media/music/library/tracks/` from the mood palette via
  ElevenLabs Music, library-first, so the music pass ships something instead of voice-only by
  default.
- **`verify_render.py` and validator check P6** — a second ASR pass over the finished master, diffed
  against `av-script.md`, catching ghost speech and clipped words that P4 (caption text) cannot see.
  Collapses spoken and written numbers (Indonesian and English) before the diff.
- **`clean_voice.py`** — ElevenLabs Voice Isolator or ffmpeg RNNoise, cleaning platform-native
  dialogue before the Voice Changer, with the same duration-preservation refusal the Voice Changer
  already enforces.
- **`composite.py` gains `split`** (picture-in-picture) **and `insert`** (pauses the master for a
  full shot with its own audio).
- **`make_stems.py`** writes full-length voice/SFX/music stems for a human editor.
- **`composite_logo.py`, `thumb_scrim.py`** — deterministic thumbnail post-process (real logo paste,
  headline scrim to a measured contrast target) on top of what the image plugin renders.
- **`yt_stats.py`** pulls YouTube view/watch-time/retention stats into packaging calibration data
  over a read-only OAuth scope.
- **One shared venv**, opt-in: `tools/setup.sh` builds `~/.gaspol-video/venv` for the four tools that
  need Pillow, Playwright, or the Google API client. Every other tool stays stdlib-only.
- Full detail, including everything deliberately excluded and why, in [CLAUDE.md](CLAUDE.md)'s
  v3.1.0 changelog.

## v3.0.0 Changelog

- **Renamed** to `gaspol-video`, published through the `gaspol-one` marketplace.
- **`/video-explainer` (Phase 4.5)** — Remotion shots for scenes that must be readable. Routing is
  decided at Phase 3 through a new **Render Path** column, before NB2 credits are spent.
- **`/video-post` (Phase 6)** — five passes in a fixed order: voice-over, ffmpeg assembly under an
  A/V duration gate, domain-aware SFX with a measured audibility gate, captions built from the
  script, a music bed that ducks under the voice, final mix.
- **`/video-package` (Phase 7)** — one locked title, three thumbnail bets on different levers, one
  description. The image itself is rendered by the image plugin through a soft reference.
- **Voice cast** — a `VOICE:` block per speaking character in `cast-profile.md`. Voice ids live in
  `.env` and are only ever NAMED in the repo.
- **Speech-to-speech converts spans, not tracks.** Handing the API a whole clip converts every voice
  on it: a supporting character came back in the target's voice on a real clip. `--spans` now
  converts only the target's turns and splices them into the original audio.
- **Ten CLI tools** in v3.0.0 (19 as of v3.1.0), most still dependency-free: python3 stdlib, node builtins, ffmpeg. Four newer tools use a self-contained venv — see [v3.1.0 Changelog](#v310-changelog).
- **Attribution** — ElevenLabs VO, voice changing, AssemblyAI timing, ffmpeg assembly and the
  packaging decisions are adopted from [hassancs91/claude-youtube-editor]; burned subtitles and the
  music bed from [harry0703/MoneyPrinterTurbo]. What was deliberately NOT taken from either is
  listed in [NOTICE](NOTICE).

## v2.4.0 Changelog

Released 2026-05-16. **Cross-platform voice-over consistency workflow.**

**New reference file** — `reference/image-video-gen/09-voice-consistency-workflow.md` (~4200 tokens, platform-agnostic):

The plugin now solves the cross-platform voice drift problem. All 3 video models (VEO 3.1 / Seedance 2.0 / Kling 3.0) generate random voices per clip — viewers detect mismatches within 45ms, retention drops 40%. Three solution paths:

**Path A — Native Voice Lock (platform-specific):**
- ✅ **Kling 3.0 Elements 3.0** — upload 3-8s audio sample OR video clip (extract face+voice), bind to character. 90-95% consistency. UNIQUE — Veo and Sora don't have this.
- ✅ **Seedance 2.0 @Audio1** — voice rhythm/tone reference via @ system. 80-90% consistency.
- ❌ **VEO 3.1** — no native voice cloning. Must use Path B.

**Path B — Universal ElevenLabs Voice Changer post-prod (works for any platform mix):**
1. Generate clips on any platform mix → accept inconsistent voices
2. Edit timeline in CapCut/DaVinci/Premiere → export vocal track
3. ElevenLabs Voice Changer → assign target Voice ID → regenerate → sync back
- Result: 100% voice consistency regardless of source
- Setup cost: 1-2 min audio sample for ElevenLabs Instant Clone

**Path C — Single VO recording + sync (B-Roll-heavy promo):**
1. Record/clone master VO (own voice OR ElevenLabs full TTS)
2. Generate video silent (placeholder audio)
3. Sync in DaVinci/Premiere with L-cuts/J-cuts + rate stretch (±5-10% undetectable)

**Phase 5 enhancement — Step 5.0a Voice Consistency Strategy:**

Runs BEFORE Step 5.0 Platform Selection. Asks user about voice continuity needs, locks voice description verbatim across all prompts in the video, saves `voice-consistency-plan.md` to output folder.

**Prompt-level discipline (universal — applied automatically):**
- Voice description verbatim across all prompts (copy-paste, no paraphrasing)
- Accent lock priority (accent shifts more jarring than voice shifts)
- One emotion per scene (no in-prompt transitions)
- Explicit audio layer separation (dialogue + ambient + music as separate lines)

**When voice consistency is critical:**
- ✅ Multi-scene promo (2-3 min B2B videos)
- ✅ Brand spokesperson video
- ✅ Mixed-platform production (Step 5.0 = Mixed)
- ✅ Same character speaking across multiple shots

**When skip:**
- ❌ Single-scene video (no continuity needed)
- ❌ Pure ambient/music-only video (no VO)

## v2.3.1 Changelog (fact correction)

Released 2026-05-16. Bahasa Indonesia audio support in Kling 3.0 clarified as two-tier:
- ✅ **Voice-over narrator** (off-screen, B-Roll) — SUPPORTED NATIVELY
- ❌ **On-screen lip-sync** (face >30% speaking) — restricted to 5 langs (EN/ZH/JA/KO/ES)

Most Indonesian B-Roll production works natively in Kling without post-prod dub. Switch to VEO 3.1 only for face-front ID dialogue scenes.

## v2.3.0 Changelog

Released 2026-05-16. **Kling 3.0 added as 3rd video platform peer.**

**New reference files (dual-RAG, complementary):**

`reference/image-video-gen/08-kling-production-guide.md` — **PRIMARY** Kling reference (~7200 tokens, curated synthesis from 10-source WebSearch + Kling UI ground truth):
- Core Specs (per-second duration 3-15s, 720p/1080p UI, 4K via API, 3 aspect ratios, native lip sync 5 langs)
- 5-Part Prompt Formula: `Camera Movement + Scene Setup + Subject Action + Vibe/Lighting + Time/Audio`
- 5 Generation Modes: T2V, I2V (anchor-based default), First+Last Frame, Multi-Shot Storyboard (up to 6 shots in single render), Motion Control (with Character Orientation toggle)
- Omni Audio Engine: 5 languages with dialect support, **mixed-language scene unique** to Kling (different chars speak different languages, each lip-syncs correctly)
- Camera Movement Library (Kling-verified phrases)
- Negative Prompts (focused 3-5 terms per category, NOT generic dump)
- Common Pitfalls & Fixes (per-second duration calibration, multi-shot boundary syntax, mixed-language declaration)
- Cross-platform comparison vs VEO 3.1 / Seedance 2.0

`reference/image-video-gen/08b-kling-notebooklm-briefing.md` — **SUPPLEMENTARY** RAG layer #2 (~10KB NotebookLM-distilled briefing):
- Independently generated by Google NotebookLM from same 11 sources
- Cross-validates primary guide claims with concrete efficiency data:
  - 4.2 rerolls avg without best practices → 1.5 with → ~45% credit waste reduction → ~8 hr/week saved
  - Elements 3.0 system: video-extracted face+voice traits, multi-image angle binding
  - 5-layer Master Prompt + Shot Prompt taxonomy
- Auto-regeneratable via `nlm report create kling-prod --format "Briefing Doc" --confirm` when Kuaishou ships v3.x updates
- Live NotebookLM notebook stays available for ad-hoc queries: `nlm notebook query kling-prod "..."` or generate Audio Deep Dive / Mind Map / Quiz for team onboarding
- Bootstrap script: [scripts/bootstrap-kling-notebooklm.ps1](scripts/bootstrap-kling-notebooklm.ps1) — re-seed notebook from scratch in <1 min

**Phase 5 (video-gen) enhancements:**
- **Step 5.0 Platform Selection** runs before Image Review (VEO / Seedance / Kling / Mixed per-scene)
- Platform-conditional CONTEXT LOADING (load only matching platform guide per batch)
- Cross-platform invariants table (audio rules, colon syntax, em dash ban, B-Roll VO pattern, face >30% rule)
- Per-scene mode selection during Image Review uses matching platform's mode tree

**Updated files:**
- `script-to-scene-bridge.md` — Step 3c Kling Mode Selection (5-mode decision tree)
- `global-promo-config.md` — Kling 3.0 Defaults table (Section 2), Kling prompt length guidelines (Section 9), version bump to 2.3.0
- `CLAUDE.md` — Production Stack lists Kling, Reference Files table, Smart Context Loading (Phase 5 Kling + Mixed), 9 new Kling-specific debugging rows
- `agents/video-engine-agent.md` — Kling reference row, tri-platform Phase 5 mention
- `00-index.md` — production stack and constraints

**When to pick Kling 3.0:**
- ✅ Face-heavy realistic dialogue / emotional close-ups
- ✅ Viral hook reels with 3-6 quick cuts (Multi-Shot in single 15s render)
- ✅ Mixed-language scenes (e.g., EN + ZH in same shot)
- ✅ Per-second duration match to dialogue/beat (no padding/rushing)
- ✅ Motion transfer from existing reference clip (Motion Control sub-model)

**When NOT to pick Kling 3.0:**
- ❌ **On-screen** Bahasa Indonesia lip-sync (face >30% speaking ID) → use VEO. **NOTE**: Bahasa Indonesia **Voice-over narrator IS supported natively** in Kling — most B-Roll ID production works fine
- ❌ Long-form extension chain (>15s continuous) → use VEO (~148s) or Seedance (unlimited)
- ❌ Stylized/anime/abstract content → use VEO (better range)
- ❌ Complex @ reference control over individual assets → use Seedance Omni mode

## v2.2.0 Hard Rules

Released 2026-05-14 to close gaps revealed during real-world production (IRN-Logistik hero promo). The 4 rules are enforced at validator phase gates:

| # | Rule | Validator | Phase | What it prevents |
|---|---|---|---|---|
| 1 | **BODY 1 Completeness** — count(pains dramatized in BODY 1 scenes) ≥ count(pains identified in brainstorm). Pairing OK if shared root cause (max 2/scene). Anchor pain non-pairable. | C1 | Phase 2 (Script) | Solutions outweighing problems → under-earned Peak. Auto-fails when script overlay says "1 dari N" while N>1, or coverage <50%. |
| 2 | **NB2 Reference Uniqueness Filter** — generate Phase 4A assets ONLY for UNIQUE items (faces, logos, custom UI, industry-specific equipment). SKIP for COMMON items (generic phone, kopi gelas, pavement) — NB2 renders these reliably from text. | C2 | Phase 4A (Asset Library) | Wasted generation budget on generic assets that don't need refs. Cluttered upload tables. |
| 3 | **Max 5 Inline References per Phase 4B Prompt** — combined cap on faces + bodies + costumes + objects + envs + UI. All inline. Each filename max 1× per prompt. Replaces old "Max 3 identity locks". | C3 | Phase 4B (Scene Keyframes) | NB2 ignoring lower-priority refs when prompts exceed cap. Forces scene splitting or composite asset consolidation. |
| 4 | **Cross-Scene Reference Env-Gated** — Scene N+1 START references `scene-N-end.png` ONLY IF env(N) == env(N+1). Character/prop continuity alone is NOT sufficient. Hard cuts (different env) drop cross-ref entirely. | C4 | Phase 4B (Scene Keyframes) | NB2 mixing wrong-location elements when treating cross-env scene-end.png as compositional template (e.g., yard pavement bleeding into customer warehouse floor). |

Full rule text + decision tables + examples: [`reference/global-promo-config.md`](reference/global-promo-config.md) §25, §26, §27.

Validator details: [`agents/video-prompt-reviewer.md`](agents/video-prompt-reviewer.md) checks C1-C4.

Implementation plan: [`docs/plans/2026-05-14-plugin-rules-hardening.md`](docs/plans/2026-05-14-plugin-rules-hardening.md).

## Project Structure

```
.claude-plugin/plugin.json          # Plugin metadata
hooks/                              # Session start hook
skills/
  video-brainstorm/SKILL.md         # Phase 1 — brainstorm, cast, product, location
  video-script/SKILL.md             # Phase 2-3.5 — script, scene, reference collection
  video-image/SKILL.md              # Phase 4 — NB2 asset library + scene keyframes
  video-explainer/SKILL.md          # Phase 4.5 — Remotion shots for readable scenes
  video-gen/SKILL.md                # Phase 5 — image review + video prompts
  video-post/SKILL.md               # Phase 6 — VO, edit, SFX, subtitles+music, mix
  video-package/SKILL.md            # Phase 7 — title, thumbnail bets, description
  video-full/SKILL.md               # Orchestrator — runs all 7 skills in sequence
  video-validate/SKILL.md           # Unified validator (5 targets)
  video-add-platform/SKILL.md       # Scaffold new video platform
agents/
  video-engine-agent.md             # Subagent for batch/complex work
  video-prompt-reviewer.md          # Independent prompt quality validator
reference/
  global-promo-config.md            # Single source of truth for all settings
  creator-profile-system.md         # Creator/brand profile setup
  script-to-scene-bridge.md         # Script → scene → prompts bridge
  storytelling_script_gen/           # 12 storytelling & script reference files
  image-video-gen/                  # 13 image & video production reference files (incl. 10-physical-plausibility-gate.md)
  post-production/                  # 9 post-production & packaging reference files (incl. 18-screencast.md)
tools/                              # 22 CLI tools: 20 python3 (mostly stdlib) + 2 node (ffmpeg throughout)
  _venv.py, setup.sh                # Dependency guard + venv builder for the 4 tools below that need libs
  gen_app_screen.py                 # capture (Playwright) / mock (Remotion renderStill) app screens
  composite_logo.py, thumb_scrim.py # Deterministic thumbnail post-process (needs Pillow)
  yt_stats.py                       # YouTube stats into packaging calibration (needs the venv + OAuth)
  renders.py                        # Render ledger shared by the Phase 4/5 render offers
  track_screen.py                   # Four screen corners per frame, with QA frames and a width floor
  check_vo_duration.py              # Fails when narration does not fit its cut, or the cut runs on silent
  check_overlay_strings.py          # Fails on any on-screen string missing from the script's approved list
  gen_music.py, verify_render.py, clean_voice.py, make_stems.py  # stdlib + ffmpeg + one HTTPS call each
templates/remotion/                 # Shot/screen templates, brand tokens, workspace scaffolder, QA scripts
  lib/quad-screen.tsx               # QuadScreen / QuadScreenTracked — homography panel attachment
media/sfx/library/palette.json      # SFX recipes. Clips generated per install, never committed
media/music/library/palette.json    # Music moods mapped to the six tones
docs/evals/                         # Routing fixtures and the Voice Changer probe measurements
.env.example                        # Variable NAMES the tools read. Never their values
```

## Configuration

All configurable values live in `reference/global-promo-config.md` — the single source of truth. Settings include default language, video/image resolution, film stock, color temperature, NB2 parameters, VEO duration, output mode, and creator preset.

## Contributing

1. **Change a setting** — edit `reference/global-promo-config.md` only
2. **Add a reference file** — create in `reference/`, update relevant SKILL.md + agent + CLAUDE.md, run `/video-validate --refs`
3. **Add a video platform** — run `/video-add-platform` to scaffold everything

## License

[MIT](LICENSE)

## Author

**Ali Sadikin** — [GitHub](https://github.com/alisadikinma)
