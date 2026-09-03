> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-1.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. This is **blocking**: no next phase until both are written. Never batch updates at the end. Update ONLY this file — never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. Every path, schema, config key, and constant it needs is written here verbatim.

**Ticket:** GV-1
**Ledger:** .gaspol/progress/PROGRESS-GV-1.md
**Spec:** docs/plans/2026-09-03-GV-1-gaspol-video-post-production-merge-spec.md
**Artifact:** https://claude.ai/code/artifact/f322a041-b1db-4dd9-b949-50514b03b56a

## Goal

Turn `ai-video-promo-engine` v2.4.0 (a prompt-package generator that stops at `video-prompts.md`)
into `gaspol-video` v3.0.0 — a pipeline that reaches a finished, mixed video file. Three new skills
(`/video-explainer`, `/video-post`, `/video-package`), eight new reference documents, ten executable
tools, six new validator checks, burned subtitles and a music bed, a render-path decision moved upstream into Phase 3, a
binding audio-source decision in Phase 5, and the rename plus `gaspol-one` marketplace listing.
Post-production method is adapted from `hassancs91/claude-youtube-editor` (MIT) with attribution;
the named delta over it is domain-aware SFX, per-cast voice profiles, ElevenLabs Voice Changer,
explainer routing at scene-plan time, and VO-first duration budgeting. Subtitles and the music bed are
adapted from `harry0703/MoneyPrinterTurbo` (MIT); the delta there is that this plugin owns the narration
text, so captions come from TTS timestamps rather than from repaired ASR output.

## Architecture Context (from CLAUDE.md)

- **Plugin layout:** `.claude-plugin/plugin.json`, `hooks/hooks.json` + `hooks/session-start.sh`,
  `skills/<name>/SKILL.md` (7 today), `agents/*.md` (2), `reference/` (25 docs), `docs/plans/`.
- **Existing skills:** `video-brainstorm` (Phase 1), `video-script` (Phase 2-3.5), `video-image`
  (Phase 4A/4B), `video-gen` (Phase 5), `video-full` (orchestrator), `video-validate` (unified
  validator with checks C1-C4), `video-add-platform`.
- **Single source of truth for settings:** `reference/global-promo-config.md` (§25 BODY 1
  completeness, §26 uniqueness filter + max 5 inline refs, §27 env-gated cross-scene refs, §28
  platform routing). New settings go here, not scattered.
- **Existing voice work to build on, not duplicate:** `reference/image-video-gen/09-voice-consistency-workflow.md`
  (Path A native lock / Path B ElevenLabs post-prod / Path C single VO) and `video-gen` Step 5.0a,
  which currently only writes `voice-consistency-plan.md` and generates no audio.
- **Existing cast model:** `reference/creator-profile-system.md` — 1-5 cast, Pemeran Utama (full
  identity lock) / Pemeran Pendamping (face only), `--preset ali`, refs named
  `cast-c{N}-face.png` / `-body.png` / `-costume.png`.
- **Existing scene contract:** `reference/script-to-scene-bridge.md` builds `scene-plan.md`
  (scene list, platform mode, duration, extension strategy) — this is where `Render Path` lands.
  Its table at line 197 already has a `Scene Type` column meaning `B-Roll | Presenter`; do not reuse it.
- **Existing validator:** `skills/video-validate/SKILL.md` runs `--script / --image / --video /
  --refs / --all` with checks C1-C4; C5-C8 join it.
- **Hard rules that constrain new work:** no em dash in spoken text; `Host says:` never a real
  name; B-Roll uses `Voice-over narrator, [tone]: text`; NB2 filenames bare (no `ref/` prefix) and
  inline with the element; aspect ratio triple enforcement; no platform can render legible text.
- **Client-agnostic rule (project CLAUDE.md, top):** never hardcode project-specific values
  (client names, ids, counts). Use `{{placeholder}}`. This is why voice ids live in the user's
  `.env`, never in the repo.

## Tech Stack

Zero new runtime dependencies in the plugin repo.

| Concern | Choice | Why |
|---|---|---|
| Test runner | `bash tests/run.sh` | repo has no stack markers; `detect-stack` printed nothing at plan time |
| Python tests | `python3 -m unittest discover -s tests/py -t .` | stdlib, no pytest install |
| Node tests | `node --test tests/node` | Node's built-in runner (Node 26 present) |
| Python tools | stdlib only (`json`, `subprocess`, `urllib.request`, `argparse`, `wave`, `audioop`-free RMS via `array`) | no `requirements.txt`, nothing to install |
| Node tools | ESM `.mjs`, global `fetch` | Node 18+ has fetch; no npm deps |
| Media | `ffmpeg` / `ffprobe` on PATH | present at `/opt/homebrew/bin` |
| ASR (only where needed) | AssemblyAI over HTTP, `ASSEMBLYAI_API_KEY` | same provider as the editor's `transcribe.py`; no local model, no GPU |
| Remotion | scaffolded per video project, never in this repo | keeps repo free of `node_modules` |
| Test media | synthesized by ffmpeg `lavfi` (`testsrc`, `sine`) | no binary fixtures committed |

**Degradation policy (applies to every tool and every skill that calls one):** a missing binary or
missing API key never fails a skill. The skill prints the exact command the user should run
elsewhere, states plainly which capability was lost, and continues. Silent degradation is banned.

## Data Integration Map

| Feature | Data Source | Tool/API | Exists? | Action |
|---|---|---|---|---|
| Render path routing | `scene-plan.md` `Render Path` column | `video-script` Phase 3 | No | Create — new column, written by Phase 3 |
| Audio source per video/scene | `strategic-brief.md` + Step 5.0a answer → `audio-plan.md` | `video-gen` Step 5.0a | No | Create — replaces inert `voice-consistency-plan.md` |
| Cast voice profile | `cast-profile.md` `VOICE:` block + `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_<SLOT>` in user `.env` | `tools/gen_vo.mjs` | No | Create — ids read from env, never committed |
| Narration text | `av-script.md` narration/dialogue column | `tools/gen_vo.mjs` | Yes | Use existing, verbatim as TTS input |
| Clip duration budget | measured mp3 duration from `vo-manifest.json` | `ffprobe` via `tools/gen_vo.mjs` | No | Create — replaces word-count estimate |
| Clip inventory | `{output_folder}/clips/*.mp4` uploaded by user | `tools/probe_clips.py` → `clip-manifest.json` | No | Create |
| Dialogue voice normalisation | audio extracted from a platform clip | `tools/voice_changer.mjs` (ElevenLabs speech-to-speech) | No | Create — new, editor has no equivalent |
| SFX cue derivation | `strategic-brief.md` DOMAIN CONTEXT + cultural research + scene visual beat | `/video-post` SFX pass → `sfx-plan.json` | Partly | Source exists; derivation logic is new |
| SFX clips | `media/sfx/library/` (grows per install) + ElevenLabs Sound Effects | `tools/gen_sfx.py` | No | Create — recipes committed, `.mp3` never |
| Subtitle cues | narration text in `audio-plan.json` + word timings from the ElevenLabs TTS response; AssemblyAI only for platform-spoken dialogue | `tools/gen_subs.py` → `work/subtitle-plan.json` + `output/master.srt` | No | Create — same provider and key as the editor's `transcribe.py` |
| ASR keyterms | `strategic-brief.md` product/brand/domain terms + `cast-profile.md` names | derived by `tools/gen_subs.py`, sent to AssemblyAI | Yes (sources exist) | Derive — the editor writes this list by hand per video |
| Subtitle burn-in | `output/master.srt` + style block in `global-promo-config.md` §30 | `tools/burn_subs.py` (ffmpeg `subtitles` filter) | No | Create |
| Music direction | per-scene music column already written in `av-script.md` by Phase 2 | `/video-post` music pass → `work/music-plan.json` | Yes (unread today) | Wire up — nothing consumes it now |
| Music tracks | `media/music/library/` + optional ElevenLabs Music | `tools/mix_music.py` | No | Create — recipes committed, audio files never |
| Assembly | `edit-plan.json` | `tools/edit_render.py` (ffmpeg) | No | Create |
| Explainer shot over clip | rendered `.mp4`/`.mov` in `{output_folder}/shots/` | `tools/composite.py` (ffmpeg) | No | Create |
| Explainer brand tokens | `strategic-brief.md` brand section | `/video-explainer` | Yes | Use existing; no bundled palette |
| Thumbnail image prompts | delegated to `ai-image-carousel-prompt-gen` | soft reference | Yes (other plugin) | Route out; degrade loudly if absent |
| Marketplace listing | `gaspol-one/.claude-plugin/marketplace.json` | manual edit + push | Yes (other repo) | Add entry, mirror version 3.0.0 |

## Contracts (verbatim — the executor must not invent these)

### C-1 `scene-plan.md` render path

**Name collision, already checked:** `reference/script-to-scene-bridge.md:197` already defines a
`Scene Type` column whose values are `B-Roll | Presenter`. That column is unrelated to this one and
stays exactly as it is. The new column is therefore named **`Render Path`**.

Every scene row gains a `Render Path` column with exactly one of:

- `live-action` — generated by a video platform (VEO 3.1 / Seedance 2.0 / Kling 3.0). Gets NB2
  keyframes in Phase 4B and a platform prompt in Phase 5.
- `explainer` — built as a Remotion shot. **No NB2 keyframe, no platform prompt, no platform mode.**

Assignment rule, applied in Phase 3 by `video-script`:

```
A scene is `explainer` when its job is to make legible information readable:
  - on-screen numbers, metrics, KPI, before/after comparison
  - a diagram, flow, architecture, timeline, map with labels
  - a product UI walkthrough where the text itself must be read
  - a list, checklist, price table, spec table
Otherwise the scene is `live-action`.
Reason: no supported platform renders legible text (CLAUDE.md debugging checklist;
reference/image-video-gen/08-kling-production-guide.md).
A scene that needs BOTH a human performance and readable data is `live-action`
with an explainer OVERLAY, recorded as `live-action + overlay:<shot-id>`.
The existing `Scene Type` column (B-Roll | Presenter) is orthogonal and unchanged:
a Presenter scene can be live-action, a B-Roll scene can be explainer.
```

### C-2 Audio source

Video-level value written to `{output_folder}/audio-plan.md` header, one of:

- `platform-native` — all speech generated by the video platform.
- `elevenlabs` — all speech generated by ElevenLabs TTS.
- `mixed` — per-scene, decided by the rule below. **This is the default when the answer is
  ElevenLabs and any scene has an on-screen speaker.**

Per-scene resolution rule (binding):

```
IF scene has an on-screen speaker with face > 30% of frame
   → audio_source = platform-native  (platforms cannot lip-sync to external audio)
   → the character's voice is normalised afterwards by tools/voice_changer.mjs
     when that cast member has a VOICE: block with source = native+changer
ELSE
   → audio_source = elevenlabs       (B-Roll, narration, over-shoulder, mouth-not-visible)
```

### C-3 Prompt muting (applies when a scene's `audio_source` is `elevenlabs`)

The platform prompt for that scene:

- MUST NOT contain `Host says:`, `Presenter says:`, or `Voice-over narrator, [tone]:`.
- MUST contain, in the negative block, verbatim: `no speech, no voiceover, no dialogue`
- MUST still specify SFX and ambient layers (audio is never optional — CLAUDE.md hard rule).

### C-4 `VOICE:` block in `cast-profile.md`

One per cast member who speaks. Written by Phase 1 (cast builder) or added in Phase 5.

```markdown
VOICE:
  provider: elevenlabs
  voice_env: ELEVENLABS_VOICE_C1        # env var name holding the voice id — NEVER the id itself
  model: eleven_multilingual_v2         # never v3
  settings: stability=0.55, similarity_boost=0.8, style=0.3, speed=0.95
  source: tts | native+changer          # tts = spoken by ElevenLabs; native+changer = platform
                                        # speaks, then voice_changer.mjs converts it
  description: "<10-15 words, verbatim in every platform prompt for this character>"
```

`voice_env` naming convention: `ELEVENLABS_VOICE_C{N}` for cast slot N, `ELEVENLABS_VOICE_NARRATOR`
for the narrator slot. The plugin reads `process.env[voice_env]`; if unset, the tool stops with
`voice env <NAME> not set` and the skill degrades to printing the manual command.

### C-5 `{output_folder}` additions

```
{output_folder}/
  clips/                 user-uploaded generated clips, named scene-{NN}[-ext{K}].mp4
  shots/                 Remotion workspace (scaffolded) + rendered shots out/<ShotId>.mp4|.mov
  vo/                    <scene>-<slot>.mp3 + vo-manifest.json
  sfx/                   per-project generated cues
  work/
    clip-manifest.json
    audio-plan.json
    edit-plan.json
    sfx-plan.json
  output/                master.mp4, master-mixed.mp4
```

### C-6 `clip-manifest.json`

```jsonc
{
  "generated_at": "2026-09-03T00:00:00Z",
  "clips": [
    { "file": "clips/scene-01.mp4", "scene": 1, "duration_s": 8.0, "fps": 24,
      "width": 1920, "height": 1080, "has_audio": true, "audio_duration_s": 8.0 }
  ],
  "problems": [ "scene-03.mp4: v:0 8.00s != a:0 7.94s" ]
}
```

### C-7 `audio-plan.json`

```jsonc
{
  "audio_source": "mixed",
  "scenes": [
    { "scene": 1, "audio_source": "platform-native",
      "layers": [
        { "kind": "dialogue", "cast": "c2", "at_s": 0.0, "dur_s": 3.2,
          "text": "…", "from": "clip", "changer": true, "out": "vo/scene-01-c2.mp3" },
        { "kind": "narration", "cast": "c1", "at_s": 3.6, "dur_s": 4.1,
          "text": "…", "from": "tts", "out": "vo/scene-01-narr.mp3" }
      ] }
  ]
}
```

`kind` ∈ `dialogue | narration | ambient | sfx`. `from` ∈ `clip | tts`. Layers within a scene are
ordered by `at_s` and MUST NOT overlap when both are speech (a platform lip-syncs one speaker at a
time — CLAUDE.md hard rule).

### C-8 `edit-plan.json`

```jsonc
{
  "fps": 30, "width": 1920, "height": 1080,
  "out": "output/master.mp4",
  "segments": [
    { "kind": "clip",  "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 7.4 },
    { "kind": "shot",  "src": "shots/out/MetricReveal.mp4", "in_s": 0.0, "out_s": 5.0 },
    { "kind": "clip",  "src": "clips/scene-03.mp4", "in_s": 0.2, "out_s": 8.0,
      "pad_end_s": 0.6, "pad_mode": "freeze" }
  ]
}
```

`pad_mode` ∈ `freeze | black`. Trimming is preferred over padding; padding above 1.0s is a
warning the tool prints (a long freeze reads as a stall).

### C-9 `sfx-plan.json`

```jsonc
{
  "master": "output/master.mp4",
  "catalog": "media/sfx/library/catalog.json",
  "render": { "out": "output/master-mixed.mp4", "duck": true },
  "events": [
    { "at_s": 12.40, "sfx_id": "amb-factory-floor", "gain_db": -16, "scene": 4,
      "cue": "wide shot of production line", "domain": "manufacturing/Cikarang" },
    { "at_s": 18.02, "sfx_id": "impact-soft", "gain_db": 0, "scene": 6,
      "cue": "metric lands on screen", "optional": false }
  ]
}
```

### C-10 SFX calibration constants (adopted from the editor's measured results — do not re-derive)

| Situation | Gain |
|---|---|
| Long-form, transitions / whooshes | −12 to −18 dB |
| Short-form under near-continuous narration | transitions −3, story pops/impacts 0..+3, stamps/snaps 0..+7, layered risers 0..+2 |
| Percussive transients (knock, stamp, keys, snap) | +3 to +5 dB above the table — they hit the −1.5 dBFS peak ceiling before reaching −20 LUFS, so they catalog quieter |

Audibility verification, run after every mix:

- Story-critical cue must add **≥ +4 dB** RMS over the voice-only reference at its window; texture
  +1 to +3 dB.
- Window size **~0.3s** for transients (snap/pop/zap/stamp); a 0.6s window dilutes a 50ms click to
  nothing and lets an adjacent loud cue fake a pass.
- Measure a riser at its **final third** — its energy is at the end.
- A cue sitting fully under continuous speech will measure +0 dB at any gain. Accept it as
  felt-not-heard or delete it. **Never chase it with gain** — it spikes in the next pause.
- A cue the user calls "noisy" is a character problem, not a level problem. Swap the sound (clean
  mechanical snap) or use silence. Lowering it just makes quiet noise.

Library clips are normalised to **−20 LUFS with a −1.5 dBFS ceiling** so a plan's `gain_db` is
perceptually meaningful across clips.

### C-13 `subtitle-plan.json` and the caption contract

```jsonc
{
  "srt": "output/master.srt",
  "burn": true,
  "style": { "font": "Inter", "size_px": 54, "stroke_px": 3, "position": "bottom",
             "margin_v_pct": 8, "max_chars_per_line": 38, "max_lines": 2 },
  "cues": [
    { "index": 1, "at_s": 0.42, "end_s": 2.86, "text": "Tiap truk antre 42 menit di gerbang.",
      "scene": 1, "from": "tts-timestamps", "script_line": "av-script.md:L64" }
  ],
  "keyterms": ["INDUSIA", "ANPR", "Pelindo", "gate-in", "Cikarang"]
}
```

`from` ∈ `tts-timestamps | assemblyai | manual`.

Rules, all binding:

- **Text is copied from the script, never transcribed back.** When `from` is `assemblyai`, the ASR
  output is used for TIMING only; the text is replaced by the matching script line (this is the repair
  `MoneyPrinterTurbo`'s `subtitle.py:correct` performs, except the script side is authoritative here
  rather than a best-effort match).
- **ASR is AssemblyAI over HTTP, never a local model.** Same provider and key as
  `claude-youtube-editor`'s `tools/transcribe.py`: `ASSEMBLYAI_API_KEY` in the user's `.env`. No
  `faster-whisper`, no model download, no GPU — the plugin's zero-dependency stance holds.
- **Keyterms are derived, not hand-written.** `transcribe.py` in the editor asks the user to draft a
  keyterms file per video. Here the list is built automatically from `strategic-brief.md` (product
  name, brand, domain equipment and jargon from the 6 research queries) plus cast names from
  `cast-profile.md`, then passed to AssemblyAI so proper nouns are not mangled. The derived list is
  written into `subtitle-plan.json` as `keyterms` so a wrong term is visible and fixable.
- Absent `ASSEMBLYAI_API_KEY` AND absent TTS timestamps → the tool writes the cues it can, lists the
  scenes it could not time, and prints the manual command. It never guesses timings.
- A cue never starts before its scene starts or ends after the master ends.
- Cues never overlap. Two speakers in one scene get sequential cues.
- Burn-in style is read from `global-promo-config.md` §30 and may be overridden per project. Before
  rendering, the tool checks that the chosen font can render every character in the text and that the
  text colour is distinguishable from its stroke/background — both checks adapted from
  `MoneyPrinterTurbo`'s `video.py`.
- The `no subtitles` negative stays in every platform prompt. It stops the model hallucinating text
  into the frame; captions are burned afterwards from real text. These are not in conflict.

### C-14 `music-plan.json` and the fail-soft rule

```jsonc
{
  "out": "output/master-mixed.mp4",
  "segments": [
    { "from_s": 0.0, "to_s": 28.4, "track": "media/music/library/tense-low-pulse.mp3",
      "gain_db": -22, "fade_in_s": 1.2, "fade_out_s": 2.0, "source": "av-script.md scene 1-4 music direction" }
  ]
}
```

- Track choice is derived from the **music direction already written per scene in `av-script.md`**, not
  asked again from the user.
- Music sits under everything: it is ducked below voice and never peaks above it at any measured
  window (same RMS method as C-10's SFX check).
- **Fail-soft (adopted from `MoneyPrinterTurbo`'s `generate_video`):** if the music track fails to load,
  fade, or mix, the pass still writes a voice-only master, prints a warning naming what failed, and
  records it. A missing music bed is never a missing deliverable.

### C-11 A/V duration gate

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 OUT.mp4
ffprobe -v error -select_streams a:0 -show_entries stream=duration -of csv=p=0 OUT.mp4
```

The two values MUST be equal within 0.04s (one frame at 25fps). Unequal → the render is rejected,
not shipped with a note.

### C-12 Remotion shot rules (adopted from `vidtsx-2d-generator`)

- Frame-based animation only: `useCurrentFrame()`. **No `useState`, `useEffect`, `setTimeout`,
  `Math.random()` without a seed.**
- `interpolate` input ranges strictly monotonic increasing.
- `Easing.bezier(...)` called directly, not wrapped.
- `compositionConfig.id` PascalCase, no hyphens or underscores.
- Design at 1920×1080 (or the project's aspect ratio from `global-promo-config.md`).
- Legibility floors: body text ≥ 32px at 1080p, headline ≥ 64px, contrast ratio ≥ 4.5:1 against its
  own background, all content inside a 5% title-safe margin.
- Colours and fonts come from `strategic-brief.md`. **No palette ships in this plugin.**
- Verification is a rendered still at each cue, inspected. A shot only reasoned about is not done.

## Phases

### Phase A: Test harness

**Estimated time:** 12 minutes

**Files:**
- Create: `tests/run.sh`, `tests/consistency/plugin-identity.sh`, `tests/py/__init__.py`,
  `tests/node/.gitkeep`, `.gitignore` (append `.gaspol/`)

**Steps:**
1. Write failing test `tests/consistency/plugin-identity.sh` asserting `.claude-plugin/plugin.json`
   has `"name": "gaspol-video"`. Expected error: `FAIL plugin name: got ai-video-promo-engine, want gaspol-video`
2. Run `bash tests/consistency/plugin-identity.sh`, confirm it fails for that exact reason
3. Write `tests/run.sh` that runs, in order: every `tests/consistency/*.sh`, then
   `python3 -m unittest discover -s tests/py -t .`, then `node --test tests/node`; exits non-zero if
   any fail; prints a one-line summary per group
4. Run `bash tests/run.sh`, confirm it fails only on the identity assertion (empty python/node
   groups must pass, not error)
5. Append `.gaspol/` to `.gitignore`
6. Commit: "test: add dependency-free test harness (bash + unittest + node --test)"

**Verification:**
- [ ] detect-stack: no stack markers for this project — verification is plan-declared only
- [ ] `bash tests/run.sh` runs all three groups and exits non-zero (identity test still red)
- [ ] Empty `tests/py` and `tests/node` groups pass rather than error
- [ ] No placeholder/TODO comments in new code

---

### Phase B: Rename, license, attribution, local marketplace

**Estimated time:** 15 minutes

**Files:**
- Modify: `.claude-plugin/plugin.json`, `README.md`, `CLAUDE.md`,
  `../../.claude-plugin/marketplace.json` (the `local-dev` marketplace at
  `/Users/alisadikin/Drive-D/claude-plugin/.claude-plugin/marketplace.json`)
- Create: `LICENSE`, `NOTICE`
- Test: `tests/consistency/plugin-identity.sh` (extend), `tests/consistency/no-old-name.sh`

**Steps:**
1. Write failing test `tests/consistency/no-old-name.sh` asserting the string
   `ai-video-promo-engine` appears nowhere under `skills/`, `reference/`, `agents/`, `hooks/`,
   `README.md`, `CLAUDE.md` (docs/plans/ excluded — historical records keep the old name).
   Expected error: `FAIL: 5 files still contain ai-video-promo-engine`
2. Run test, confirm it fails for the expected reason
3. Extend `tests/consistency/plugin-identity.sh` to also assert `"version": "3.0.0"` and that
   `LICENSE` and `NOTICE` exist and are non-empty
4. Set `plugin.json` `name` = `gaspol-video`, `version` = `3.0.0`, update `description` and
   `keywords` to include post-production, voice-over, Remotion, SFX
5. Write `LICENSE` — MIT, copyright Ali Sadikin, year 2026
6. Write `NOTICE` naming `hassancs91/claude-youtube-editor` (MIT) and listing which methods were
   adapted: SFX plan/mix + calibration numbers, Remotion shot authoring rules, ffmpeg assembly and
   A/V duration gate, ElevenLabs TTS prosody stitching
7. Replace remaining old-name occurrences in `README.md`, `CLAUDE.md`, `hooks/session-start.sh`
8. Update `local-dev` marketplace entry: `name` → `gaspol-video`, `source` → `./gaspol-video`,
   description updated
9. Run `bash tests/run.sh`, confirm identity + no-old-name pass
10. Commit: "feat!: rename to gaspol-video v3.0.0, add LICENSE and NOTICE"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] `plugin.json` name is `gaspol-video`, version `3.0.0`
- [ ] `LICENSE` (MIT) and `NOTICE` (attribution to `hassancs91/claude-youtube-editor`) exist
- [ ] No `ai-video-promo-engine` outside `docs/plans/`
- [ ] `local-dev` marketplace points at `./gaspol-video`
- [ ] No placeholder/TODO comments in new files
- [ ] **Folder rename and GitHub repo rename are NOT done in this phase** — they are Phase N, after
      everything else is green, so a half-renamed working tree never blocks execution

---

### Phase C: Folder contract + post-production pipeline reference

**Estimated time:** 14 minutes

**Files:**
- Create: `reference/post-production/10-post-production-pipeline.md`
- Modify: `reference/global-promo-config.md` (new §29 Post-Production Defaults)
- Test: `tests/consistency/reference-index.sh`

**Steps:**
1. Write failing test `tests/consistency/reference-index.sh` asserting every `.md` under
   `reference/` appears in the Reference Files table of `CLAUDE.md`, and every file named in that
   table exists. Expected error: `FAIL: reference/post-production/10-post-production-pipeline.md not listed in CLAUDE.md`
2. Run test, confirm it fails for the expected reason
3. Write `reference/post-production/10-post-production-pipeline.md` containing verbatim: the Phase 6
   overview, the `{output_folder}` contract (C-5), all five plan schemas (C-6 through C-9 plus
   `vo-manifest.json`), the degradation policy, and the A/V gate (C-11)
4. Add `§29 Post-Production Defaults` to `global-promo-config.md`: `audio_source` enum
   (`platform-native | elevenlabs | mixed`), `render_path` enum (`live-action | explainer`), master
   fps/resolution defaults, loudness target `-14 LUFS`, SFX density `8-12 cues/min`, library path
   `media/sfx/library/`
5. Add the new reference row to `CLAUDE.md`'s Reference Files table
6. Run `bash tests/run.sh`, confirm green
7. Commit: "docs: post-production pipeline reference + global config §29"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] `reference-index.sh` proves CLAUDE.md's table and `reference/` are in sync both directions
- [ ] All five plan schemas appear verbatim in the reference file (an executor reading only that
      file can author every plan)
- [ ] No placeholder/TODO comments

---

### Phase D: Render-path routing (Phase 3) + validator C6

**Estimated time:** 18 minutes

**Files:**
- Modify: `skills/video-script/SKILL.md`, `skills/video-image/SKILL.md`,
  `skills/video-validate/SKILL.md`, `reference/script-to-scene-bridge.md`
- Create: `docs/evals/render-path-routing.md`
- Test: `tests/consistency/render-path-contract.sh`

**Steps:**
1. Write failing test `tests/consistency/render-path-contract.sh` asserting: `script-to-scene-bridge.md`
   defines the `Render Path` column with both enum values and the assignment rule, AND still defines
   the pre-existing `Scene Type` column with `B-Roll`/`Presenter`; `video-image/SKILL.md` states
   explainer scenes are skipped in Phase 4B; `video-validate/SKILL.md` defines check C6.
   Expected error: `FAIL: Render Path column not defined in script-to-scene-bridge.md`
2. Run test, confirm it fails for the expected reason
3. Add the `Render Path` column and assignment rule (C-1 verbatim) to the Scene Breakdown table at
   `script-to-scene-bridge.md:197`, beside the existing `Scene Type` column, including the
   `live-action + overlay:<shot-id>` case
4. Update `video-script/SKILL.md` Phase 3: every scene row carries `Render Path`; explainer scenes get
   no platform mode; the approval gate summary reports the live-action/explainer split and the
   NB2 credits saved
5. Update `video-image/SKILL.md`: Phase 4B iterates live-action scenes only; Phase 4A still generates
   assets an explainer shot needs (logo, product photo, UI reference)
6. Add validator check **C6** to `video-validate/SKILL.md`: every `explainer` scene has a shot id and
   no keyframe/platform prompt; every `live-action` scene has both
7. Write `docs/evals/render-path-routing.md`: capability cases (metric reveal → explainer; worker at
   machine → live-action; presenter reading a chart → live-action + overlay) and regression cases
   drawn from real scenes in `docs/plans/` history; success is 5/5 correct classifications
8. Run `bash tests/run.sh`, confirm green
9. Commit: "feat: Render Path column routes explainer scenes at scene-plan time + validator C6"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] `render-path-contract.sh` passes; the pre-existing `Scene Type` column is untouched
- [ ] `docs/evals/render-path-routing.md` has ≥5 fixtures with expected labels
- [ ] Phase 4B explicitly skips explainer scenes; Phase 4A explicitly does not
- [ ] No placeholder/TODO comments
- [ ] **LLM-behaviour phase:** success contract is the eval file, not a unit test

---

### Phase E: Audio-source decision (Phase 5) + prompt muting + validator C5

**Estimated time:** 18 minutes

**Files:**
- Modify: `skills/video-gen/SKILL.md` (Step 5.0a rewrite), `skills/video-validate/SKILL.md`,
  `reference/image-video-gen/09-voice-consistency-workflow.md`
- Create: `docs/evals/audio-source-routing.md`
- Test: `tests/consistency/audio-source-contract.sh`

**Steps:**
1. Write failing test `tests/consistency/audio-source-contract.sh` asserting `video-gen/SKILL.md`
   contains the three-value `audio_source` enum, the face>30% resolution rule, and the exact negative
   string `no speech, no voiceover, no dialogue`; and that `video-validate/SKILL.md` defines C5.
   Expected error: `FAIL: audio_source enum not found in skills/video-gen/SKILL.md`
2. Run test, confirm it fails for the expected reason
3. Rewrite Step 5.0a: ask **"Suara di video ini dari mana?"** with options `platform-native` /
   `elevenlabs` / `mixed`, before platform selection and before any prompt is written. Answer
   `elevenlabs` + any on-screen speaker auto-resolves to `mixed` per C-2, and the skill says so
4. Add the VO-first ordering: under `elevenlabs`/`mixed`, narration mp3s are generated and measured
   BEFORE prompts are authored; each scene's clip duration is set from its measured audio length
   (Kling per-second selector 3-15s; VEO 8s budget; Seedance 15s)
5. Add C-3 prompt muting rules to the prompt-authoring step
6. Add validator check **C5** (no double audio) to `video-validate/SKILL.md`
7. Update `09-voice-consistency-workflow.md` Path B to point at `tools/gen_vo.mjs` and
   `tools/voice_changer.mjs` instead of describing a manual process
8. Write `docs/evals/audio-source-routing.md`: fixtures covering face-front dialogue, over-shoulder
   dialogue, pure B-Roll, mixed scene with dialogue then narration; success 4/4
9. Run `bash tests/run.sh`, confirm green
10. Commit: "feat: binding audio-source decision + VO-first duration budgeting + validator C5"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Step 5.0a asks the audio-source question BEFORE platform selection
- [ ] The muting negative string appears verbatim
- [ ] `docs/evals/audio-source-routing.md` has ≥4 fixtures
- [ ] No placeholder/TODO comments
- [ ] **LLM-behaviour phase:** success contract is the eval file

---

### Phase F: Voice cast model + validator C8

**Estimated time:** 14 minutes

**Files:**
- Create: `reference/post-production/11-voice-cast-and-vo.md`, `.env.example`
- Modify: `reference/creator-profile-system.md`, `skills/video-brainstorm/SKILL.md`,
  `skills/video-validate/SKILL.md`, `CLAUDE.md`
- Test: `tests/consistency/voice-cast-contract.sh`, `tests/consistency/no-secrets.sh`

**Steps:**
1. Write failing test `tests/consistency/no-secrets.sh` asserting no file in the repo contains an
   ElevenLabs-shaped voice id (20-char alphanumeric assigned to a `voice_id` key) or an
   `ELEVENLABS_API_KEY=` with a value. Expected error: `FAIL: hardcoded voice id in reference/...`
2. Run test, confirm it passes today and will catch a future leak (add a temporary fixture line,
   see it fail, remove it — record both observations in the ledger)
3. Write failing test `tests/consistency/voice-cast-contract.sh` asserting `creator-profile-system.md`
   defines the `VOICE:` block with all six fields and the `voice_env` naming convention.
   Expected error: `FAIL: VOICE: block not defined in reference/creator-profile-system.md`
4. Add the C-4 `VOICE:` block (verbatim) to `creator-profile-system.md`; wire the cast builder in
   `video-brainstorm/SKILL.md` to ask for a voice per speaking cast member
5. Write `reference/post-production/11-voice-cast-and-vo.md`: voice cast model, C-2 decision tree,
   mixed-source rule, Voice Changer workflow, VO-first budgeting, prompt-level discipline (verbatim
   voice description in every platform prompt, one emotion per scene, accent lock)
6. Write `.env.example` documenting `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_C{N}`,
   `ELEVENLABS_VOICE_NARRATOR` — names only, never values
7. Add validator check **C8** (every speaking cast has a resolvable VOICE block; a locked-voice
   character never ships with an un-changed platform voice)
8. Add the new reference row to `CLAUDE.md`
9. Run `bash tests/run.sh`, confirm green
10. Commit: "feat: per-cast voice profiles read from env + validator C8"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] **Security:** no voice ids and no API keys in source; `.env.example` documents names only;
      `no-secrets.sh` proven to fail on a planted fixture and pass after removal
- [ ] `VOICE:` block documented with all six fields
- [ ] No placeholder/TODO comments

---

### Phase G: `probe_clips.py` + `edit_render.py` + ffmpeg reference + validator C7

**Estimated time:** 20 minutes

**Files:**
- Create: `tools/probe_clips.py`, `tools/edit_render.py`,
  `reference/post-production/13-ffmpeg-edit.md`, `tests/py/test_probe_clips.py`,
  `tests/py/test_edit_render.py`, `tests/py/media.py` (ffmpeg synth helper)
- Modify: `skills/video-validate/SKILL.md`, `CLAUDE.md`

**Steps:**
1. Write failing test `tests/py/test_probe_clips.py::test_reports_av_mismatch` — synthesize with
   `ffmpeg -f lavfi -i testsrc=size=320x240:rate=30 -f lavfi -i sine=frequency=440 -t 5` a clip whose
   audio is 0.3s shorter, assert `probe_clips` lists it under `problems`.
   Expected error: `ModuleNotFoundError: No module named 'tools.probe_clips'`
2. Run `python3 -m unittest discover -s tests/py -t .`, confirm it fails for that reason
3. Implement `tools/probe_clips.py`: walk `{project}/clips/`, `ffprobe` each, emit
   `work/clip-manifest.json` per C-6, flag A/V mismatch > 0.04s and missing audio streams; exit 0
   with a `ffprobe not found` message and no crash when the binary is absent
4. Run tests, confirm pass
5. Write failing test `tests/py/test_edit_render.py::test_av_duration_gate` — an `edit-plan.json`
   with two synthesized segments; assert the rendered output's v:0 and a:0 durations differ by
   ≤0.04s and that the function raises on a deliberately corrupted plan
6. Run test, confirm it fails
7. Implement `tools/edit_render.py`: read `edit-plan.json` (C-8), trim/pad each segment, concat,
   run the C-11 gate, warn when `pad_end_s` > 1.0; `--print` prints the resolved segment sheet
   without rendering
8. Run tests, confirm pass
9. Write `reference/post-production/13-ffmpeg-edit.md` — C-8 schema, trim-over-pad rule, explainer
   insertion, the C-11 gate, the playable-transcode note (`-r <src_fps>` before `-i` to re-stamp CFR)
10. Add validator **C7** (rendered master v:0 == a:0) and both reference rows to `CLAUDE.md`
11. Commit: "feat: clip probe + ffmpeg assembly with A/V duration gate (C7)"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] `python3 -m unittest discover -s tests/py -t .` passes
- [ ] Edge cases covered by tests: zero clips, one clip, clip with no audio stream, A/V mismatch,
      trim beyond clip length, `pad_end_s` > 1.0 warning, malformed plan JSON
- [ ] Both tools exit cleanly with a printed manual command when `ffmpeg`/`ffprobe` is absent
- [ ] **Observability:** every render prints the exact ffmpeg command it ran before running it
- [ ] No placeholder/TODO comments

---

### Phase H: `gen_vo.mjs` + `voice_changer.mjs` + Voice Changer feasibility probe

**Estimated time:** 22 minutes

**Files:**
- Create: `tools/gen_vo.mjs`, `tools/voice_changer.mjs`, `tests/node/gen_vo.test.mjs`,
  `tests/node/voice_changer.test.mjs`, `docs/evals/voice-changer-probe.md`

**Steps:**
1. Write failing test `tests/node/gen_vo.test.mjs` — inject a stub fetch, assert consecutive
   requests carry `previous_request_ids` from prior responses and that `vo-manifest.json` records
   duration + the exact settings used. Expected error: `Cannot find module '../../tools/gen_vo.mjs'`
2. Run `node --test tests/node`, confirm it fails for that reason
3. Implement `tools/gen_vo.mjs`: read `audio-plan.json` narration layers, resolve each cast's voice
   id from `process.env[voice_env]`, POST to ElevenLabs TTS with the C-4 settings, stitch prosody via
   `previous_request_ids`, write `vo/<scene>-<slot>.mp3` + `vo-manifest.json` with `ffprobe`
   durations. Missing key or missing env → print the manual `curl` and exit 0
4. Run tests, confirm pass
5. Write failing test `tests/node/voice_changer.test.mjs` — stub fetch; assert the tool extracts audio
   from a clip, posts to speech-to-speech with the target voice, and **asserts output duration is
   within 0.05s of input duration** (the property lip-sync depends on). Expected error:
   `Cannot find module '../../tools/voice_changer.mjs'`
6. Run test, confirm it fails
7. Implement `tools/voice_changer.mjs`: `ffmpeg` extract → ElevenLabs speech-to-speech → duration
   check → write `vo/<scene>-<cast>.mp3`; refuse to write and report when duration drifts > 0.05s
8. Run tests, confirm pass
9. **Feasibility probe (spec risk #1) — real API, real clip.** Write `docs/evals/voice-changer-probe.md`
   recording: the source clip, its dialogue duration, the converted duration, the measured drift, and
   a human verdict on whether the lips still match. Needs one real platform clip with on-screen
   dialogue plus `ELEVENLABS_API_KEY`
10. **If the probe fails** (drift > 0.05s or visibly broken lip-sync): STOP, do not continue to
    Phase K. Record the failure in the ledger under `## Keputusan saat jalan` and re-open the
    mixed-source decision with the user — Phase E's C-2 rule depends on this working
11. Commit: "feat: ElevenLabs TTS + speech-to-speech voice changer, with duration-preservation probe"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] `node --test tests/node` passes
- [ ] Error paths covered: missing `ELEVENLABS_API_KEY`, missing `voice_env`, HTTP 401, HTTP 429
      with retry, empty text, text with an em dash (must be rejected — CLAUDE.md hard rule)
- [ ] **Security:** key read from `.env`/env only, never logged, never written into any output file
      or manifest
- [ ] `docs/evals/voice-changer-probe.md` records a real measured drift and a human verdict
- [ ] Probe verdict is PASS, or execution is stopped and the user consulted
- [ ] No placeholder/TODO comments

---

### Phase I: `gen_sfx.py` + `mix_sfx.py` + domain-aware SFX reference

**Estimated time:** 20 minutes

**Files:**
- Create: `tools/gen_sfx.py`, `tools/mix_sfx.py`, `media/sfx/library/palette.json`,
  `media/sfx/library/catalog.json`, `reference/post-production/14-sfx-design.md`,
  `tests/py/test_mix_sfx.py`, `tests/py/test_gen_sfx.py`
- Modify: `CLAUDE.md`, `.gitignore` (ignore `media/sfx/library/clips/`)

**Steps:**
1. Write failing test `tests/py/test_mix_sfx.py::test_rms_window_sizes` — synthesize a 50ms click over
   speech-like noise; assert the audibility checker uses a 0.3s window for transients and reports the
   cue as inaudible rather than passing it on a diluted 0.6s window.
   Expected error: `ModuleNotFoundError: No module named 'tools.mix_sfx'`
2. Run tests, confirm it fails for that reason
3. Implement `tools/mix_sfx.py`: read `sfx-plan.json` (C-9), `--print` the cue sheet (the audit
   artifact), mix with sidechain duck + limiter, then run the C-10 audibility check and print a
   per-cue dB delta table
4. Run tests, confirm pass
5. Write failing test `tests/py/test_gen_sfx.py::test_normalisation_target` — stub the HTTP call, feed
   a loud synthetic clip, assert output is normalised to −20 LUFS with a −1.5 dBFS ceiling and that
   `catalog.json` records `source`, `license`, `prompt`, `peak_dbfs`, `loudness_lufs`
6. Run test, confirm it fails
7. Implement `tools/gen_sfx.py`: read `palette.json` recipes, generate misses via ElevenLabs Sound
   Effects, normalise, append to `catalog.json`; `--dry-run`, `--only`, `--renorm` (no API call)
8. Run tests, confirm pass
9. Seed `palette.json` with generic recipes (whoosh-soft, pop-reveal, impact-soft, riser-short,
   ui-click-soft) **plus domain categories** the editor has no equivalent for: `amb-factory-floor`,
   `amb-port-yard`, `amb-control-room`, `amb-clinic-corridor`, `machine-conveyor-loop`,
   `vehicle-forklift-pass`. `catalog.json` starts empty. **No `.mp3` is committed**
10. Write `reference/post-production/14-sfx-design.md`: cue derivation from `DOMAIN CONTEXT` +
    cultural research, library-first sourcing, C-9 schema, the C-10 constants verbatim, the hard
    user-audit gate before any mix
11. Add reference row to `CLAUDE.md`; ignore `media/sfx/library/clips/`
12. Commit: "feat: domain-aware SFX generation and mixing with measured audibility check"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Edge cases covered: empty event list, two cues at the same `at_s` (layering must sum), cue past
      master duration (rejected), `--no-optional` drops only `optional: true`, transient vs sustained
      window selection, riser measured at final third
- [ ] `palette.json` contains at least 6 domain-specific recipes; `catalog.json` ships empty
- [ ] No `.mp3` committed anywhere
- [ ] **Security:** ElevenLabs key from env only, never logged
- [ ] No placeholder/TODO comments

---

### Phase J: Subtitles — `gen_subs.py`, `burn_subs.py`, validator C9

**Estimated time:** 20 minutes

**Files:**
- Create: `tools/gen_subs.py`, `tools/burn_subs.py`,
  `reference/post-production/16-subtitles-and-captions.md`, `tests/py/test_gen_subs.py`,
  `tests/py/test_burn_subs.py`
- Modify: `reference/global-promo-config.md` (new §30 Subtitle Style), `skills/video-validate/SKILL.md`,
  `.env.example`, `CLAUDE.md`

**Steps:**
1. Write failing test `tests/py/test_gen_subs.py::test_text_comes_from_script_not_asr` — feed a fake
   AssemblyAI response whose text is mangled (`"anpr"` → `"an peer"`) plus the real script line; assert
   the emitted cue carries the SCRIPT text and the ASR timing.
   Expected error: `ModuleNotFoundError: No module named 'tools.gen_subs'`
2. Run `python3 -m unittest discover -s tests/py -t .`, confirm it fails for that reason
3. Implement `tools/gen_subs.py`: build cues from `audio-plan.json` narration text plus ElevenLabs TTS
   word timings; for `from: clip` dialogue, POST the extracted audio to AssemblyAI with keyterms derived
   from `strategic-brief.md` + `cast-profile.md`; repair text against the script; emit
   `work/subtitle-plan.json` (C-13) and `output/master.srt`
4. Run tests, confirm pass
5. Write failing test `tests/py/test_burn_subs.py::test_rejects_font_missing_glyphs` — a style naming a
   font that cannot render the text; assert the tool refuses and names the characters.
   Expected error: `ModuleNotFoundError: No module named 'tools.burn_subs'`
6. Run test, confirm it fails
7. Implement `tools/burn_subs.py`: ffmpeg `subtitles` filter with the §30 style, plus the two adopted
   checks — font-supports-every-character, and subtitle colour distinguishable from its stroke and
   background
8. Run tests, confirm pass
9. Add `§30 Subtitle Style` to `global-promo-config.md` (font, size, stroke, position, vertical margin,
   max chars per line, max lines, per-platform defaults: 9:16 needs larger type and a higher margin
   than 16:9) and add `ASSEMBLYAI_API_KEY` to `.env.example`
10. Add validator **C9** and both new rows to `CLAUDE.md`
11. Write `reference/post-production/16-subtitles-and-captions.md` — C-13 verbatim, when captions are
    required per platform, the derived-keyterms rule, and why the `no subtitles` prompt negative does
    not conflict with burned captions
12. Commit: "feat: subtitles built from owned script text, burned with legibility checks (C9)"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Edge cases covered: no narration at all, one cue, cue past master end (rejected), overlapping
      cues (rejected), two speakers in one scene (sequential cues), missing `ASSEMBLYAI_API_KEY`
      (writes what it can, lists untimed scenes, prints the manual command), AssemblyAI HTTP 401 and
      429, text longer than `max_chars_per_line` (wrapped, never clipped), a script line with an em
      dash (kept in the caption — the em-dash ban is about spoken audio, not printed text)
- [ ] Caption text is never ASR output; a test proves the script text wins over a mangled transcript
- [ ] **Security:** `ASSEMBLYAI_API_KEY` read from env only, never logged, never written into
      `subtitle-plan.json`
- [ ] No placeholder/TODO comments
### Phase K: Music bed — `mix_music.py`, validator C10

**Estimated time:** 16 minutes

**Files:**
- Create: `tools/mix_music.py`, `media/music/library/palette.json`,
  `reference/post-production/17-music-bed.md`, `tests/py/test_mix_music.py`
- Modify: `skills/video-validate/SKILL.md`, `CLAUDE.md`, `.gitignore` (ignore `media/music/library/tracks/`)

**Steps:**
1. Write failing test `tests/py/test_mix_music.py::test_music_never_peaks_above_voice` — synthesize a
   voice track and a loud music track; assert the mixed output measures music below voice at every
   window. Expected error: `ModuleNotFoundError: No module named 'tools.mix_music'`
2. Run tests, confirm it fails for that reason
3. Implement `tools/mix_music.py`: read `work/music-plan.json` (C-14), place each segment with its fade
   in/out, duck under voice, run the same RMS check as the SFX pass, write the mixed master
4. Run tests, confirm pass
5. Write failing test `test_mix_music.py::test_fail_soft_on_bad_track` — a plan pointing at a corrupt
   file; assert a voice-only master IS still written, a warning naming the failure is printed, and the
   exit code stays 0
6. Run test, confirm it fails, then implement the fail-soft path
7. Seed `media/music/library/palette.json` with generic mood recipes matching the tone system in
   `global-promo-config.md` §13 (tense-low-pulse, warm-uplift, neutral-corporate, sparse-ambient,
   driving-build). **No audio files are committed**; ignore `media/music/library/tracks/`
8. Write `reference/post-production/17-music-bed.md` — C-14 verbatim, how the per-scene music direction
   in `av-script.md` maps to a track and a level, the fail-soft rule, and how music interacts with the
   SFX duck so the two do not both fight the voice
9. Add validator **C10** and the reference row to `CLAUDE.md`
10. Commit: "feat: music bed driven by av-script music direction, fail-soft (C10)"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] Edge cases covered: no music direction in the script (pass does nothing, says so), one segment,
      segments that touch end-to-start, a segment longer than the master (trimmed), corrupt track
      (fail-soft), track shorter than its segment (looped with a crossfade, or the segment shortened —
      the tool prints which)
- [ ] A failed music mix leaves a shipped voice-only master plus a printed warning, never a missing file
- [ ] `palette.json` moods line up with the six tones in `global-promo-config.md` §13
- [ ] No audio file committed anywhere
- [ ] No placeholder/TODO comments
### Phase L: `/video-explainer` skill + Remotion reference + `composite.py`

**Estimated time:** 20 minutes

**Files:**
- Create: `skills/video-explainer/SKILL.md`, `reference/post-production/12-remotion-explainer.md`,
  `templates/remotion/Shot.template.tsx`, `templates/remotion/scaffold.mjs`, `tools/composite.py`,
  `tests/py/test_composite.py`, `tests/consistency/skill-frontmatter.sh`
- Modify: `CLAUDE.md`

**Steps:**
1. Write failing test `tests/consistency/skill-frontmatter.sh` asserting every `skills/*/SKILL.md`
   has YAML frontmatter with `name` and `description`, and that `name` matches its folder.
   Expected error: `FAIL: skills/video-explainer/SKILL.md missing`
2. Run test, confirm it fails for that reason
3. Write failing test `tests/py/test_composite.py::test_overlay_preserves_master_audio` — synthesize a
   clip and a shorter shot; assert the composited output keeps the clip's audio and the shot replaces
   video only for its span. Expected error: `ModuleNotFoundError: No module named 'tools.composite'`
4. Run test, confirm it fails
5. Implement `tools/composite.py`: cutaway (shot replaces video, master audio continues) and overlay
   (transparent `.mov` over master) modes, frame-accurate segment split + concat
6. Run tests, confirm pass
7. Write `templates/remotion/Shot.template.tsx` (C-12 compliant skeleton reading brand tokens from a
   `brand.json` the skill writes from `strategic-brief.md`) and `templates/remotion/scaffold.mjs`
   (creates `{output_folder}/shots/` with `package.json`, `remotion.config.ts`, registry generator)
8. Write `reference/post-production/12-remotion-explainer.md` — C-12 verbatim, when a scene is
   explainer, brand-token binding, legibility floors, per-cue still verification, and the exact
   render/still commands
9. Write `skills/video-explainer/SKILL.md` — Phase 4.5, context loading (global config, 12-remotion,
   strategic-brief brand section, this batch's explainer scenes only), scaffold-on-first-use,
   author → render → **inspect a still at each cue** → approve gate, degradation when Node absent
10. Add skill + reference rows to `CLAUDE.md`
11. Commit: "feat: /video-explainer — Remotion shots for scenes that must be readable"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] `skill-frontmatter.sh` passes for all 8 skills
- [ ] Composite edge cases: shot longer than its span (trimmed), shot at t=0, shot at master end,
      overlay `.mov` without alpha (rejected with a clear message)
- [ ] The skill's done-criteria explicitly require an inspected still per cue
- [ ] No palette or font is hardcoded in the plugin — tokens come from `strategic-brief.md`
- [ ] No placeholder/TODO comments

---

### Phase M: `/video-post` skill — audio and edit passes

**Estimated time:** 18 minutes

**Files:**
- Create: `skills/video-post/SKILL.md` (passes 1-2)
- Test: `tests/consistency/post-skill-audio-edit.sh`

**Steps:**
1. Write failing test `tests/consistency/post-skill-audio-edit.sh` asserting `skills/video-post/SKILL.md`
   documents pass 1 (Audio) and pass 2 (Edit) in that order, names `gen_vo.mjs`, `voice_changer.mjs`,
   `probe_clips.py`, `edit_render.py`, and states the degradation policy.
   Expected error: `FAIL: skills/video-post/SKILL.md missing`
2. Run test, confirm it fails for that reason
3. Write pass 1 (Audio): read `av-script.md` + `cast-profile.md` VOICE blocks + `audio-plan.md` from
   Phase 5, build `audio-plan.json` (C-7), call `tools/gen_vo.mjs` for `from: tts` layers and
   `tools/voice_changer.mjs` for `from: clip` layers with `changer: true`, present the layer sheet for
   approval
4. Write pass 2 (Edit): `tools/probe_clips.py` first, then build `edit-plan.json` (C-8) from
   `scene-plan.md` order + measured VO durations + explainer shots, `--print` for the user audit gate,
   then render and run the C-11 gate
5. Run `bash tests/run.sh`, confirm green
6. Commit: "feat: /video-post passes 1-2 (audio build, ffmpeg assembly)"

**Verification:**
- [ ] `bash tests/run.sh` passes (`post-skill-audio-edit.sh` green — passes 3-4 are Phase L's own test)
- [ ] Pass 1 handles: no speaking cast (skip), cast without VOICE block (stop and ask), overlapping
      speech layers (rejected per C-7)
- [ ] Pass 2 handles: missing clip for a scene (stop and list), clip shorter than its beat (pad with
      warning), clip longer (trim), explainer scene with no rendered shot (stop)
- [ ] Both passes state what is lost when a tool is unavailable
- [ ] No placeholder/TODO comments

---

### Phase N: `/video-post` skill — SFX, subtitles, music, final mix

**Estimated time:** 16 minutes

**Files:**
- Modify: `skills/video-post/SKILL.md` (passes 3-5), `CLAUDE.md`
- Test: `tests/consistency/post-skill-sfx-mix.sh`

**Steps:**
1. Write failing test `tests/consistency/post-skill-sfx-mix.sh` asserting `skills/video-post/SKILL.md`
   documents pass 3 (SFX), pass 4 (subtitles + music) and pass 5 (final mix), names `gen_sfx.py`,
   `mix_sfx.py`, `gen_subs.py`, `burn_subs.py` and `mix_music.py`, carries the hard
   user-audit gate before mixing, and reproduces the C-10 audibility thresholds (+4 dB, 0.3s window).
   Expected error: `FAIL: pass 3 (SFX) not documented in skills/video-post/SKILL.md`
2. Run `bash tests/consistency/post-skill-sfx-mix.sh`, confirm it fails for the expected reason
3. Write pass 3 (SFX): derive cues from each scene's `DOMAIN CONTEXT` + cultural research + visual
   beat, library-first sourcing via `catalog.json`, generate misses with `tools/gen_sfx.py`, author
   `sfx-plan.json` (C-9), **hard user-audit gate** on the printed cue sheet before any mix
4. Write pass 4 (Subtitles + music): `tools/gen_subs.py` → user reviews the cue text → `tools/burn_subs.py`;
   then `tools/mix_music.py` reading the music direction already in `av-script.md`. Both are fail-soft:
   a caption or music failure warns and still ships the video
5. Write pass 5 (Final mix): `tools/mix_sfx.py` with duck + limiter, loudness to `-14 LUFS`, the C-10
   audibility check with its per-cue dB table, then the C-11 A/V re-check; iterate on user notes
6. Add the density ceiling (8-12 cues/min, everything past that `optional: true`) and the
   "noisy character, not level" rule verbatim
7. Add skill row + Smart Context Loading rows for Phase 6 to `CLAUDE.md`
8. Run `bash tests/run.sh`, confirm green
9. Commit: "feat: /video-post passes 3-5 (SFX, subtitles, music, final mix)"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] `post-skill-sfx-mix.sh` passes; `post-skill-audio-edit.sh` still passes
- [ ] The user-audit gate before mixing is stated as hard, matching the Phase 3.5 ref gate's language
- [ ] The audibility thresholds and window sizes from C-10 appear verbatim
- [ ] `CLAUDE.md` Smart Context Loading has a Phase 6 row capping refs per pass
- [ ] No placeholder/TODO comments

---

### Phase O: `/video-package` skill + packaging reference

**Estimated time:** 14 minutes

**Files:**
- Create: `skills/video-package/SKILL.md`, `reference/post-production/15-packaging.md`
- Modify: `CLAUDE.md`
- Test: `tests/consistency/packaging-soft-reference.sh`

**Steps:**
1. Write failing test `tests/consistency/packaging-soft-reference.sh` asserting
   `skills/video-package/SKILL.md` names `ai-image-carousel-prompt-gen` as a **soft** reference,
   contains no image-generation API call, and `plugin.json` declares no `dependencies`.
   Expected error: `FAIL: skills/video-package/SKILL.md missing`
2. Run test, confirm it fails for that reason
3. Write `reference/post-production/15-packaging.md`: one locked title + 3 distinct thumbnail bets +
   one value-forward description, the honesty guardrail (the frame may promise only what the video
   keeps), CTR calibration mode (cold-start defaults must be labelled uncalibrated; never quote a
   target CTR the user has not measured), and the hand-off contract to the image plugin
4. Write `skills/video-package/SKILL.md`: runs standalone or after Phase 6; emits thumbnail concept
   briefs; hands prompts to `ai-image-carousel-prompt-gen`; with that plugin absent, prints the raw
   briefs and says which capability was lost
5. Add rows to `CLAUDE.md`
6. Run `bash tests/run.sh`, confirm green
7. Commit: "feat: /video-package — titles and thumbnail bets, rendering delegated to the image plugin"

**Verification:**
- [ ] `bash tests/run.sh` passes
- [ ] No image-generation call exists in this plugin; the SoT split holds
- [ ] `plugin.json` still declares no `dependencies` (soft reference only)
- [ ] Cold-start CTR rules are labelled uncalibrated
- [ ] No placeholder/TODO comments

---

### Phase P: Orchestrator, docs sync, repo rename, marketplace publish, external references

**Estimated time:** 20 minutes

**Files:**
- Modify: `skills/video-full/SKILL.md`, `hooks/session-start.sh`, `CLAUDE.md`, `README.md`,
  `agents/video-engine-agent.md`, `/Users/alisadikin/Drive-D/claude-plugin/gaspol-one/.claude-plugin/marketplace.json`,
  `/Users/alisadikin/CLAUDE.md`, vault files listed below
- Test: `tests/consistency/orchestrator-phases.sh`

**Steps:**
1. Write failing test `tests/consistency/orchestrator-phases.sh` asserting `video-full/SKILL.md`
   invokes `/video-explainer`, `/video-post`, `/video-package` in that order after `/video-gen`, and
   that `hooks/session-start.sh` announces all 8 skills.
   Expected error: `FAIL: video-full does not invoke /video-explainer`
2. Run test, confirm it fails for the expected reason
3. Update `video-full/SKILL.md` with steps 5-7 and an extended production summary listing
   `master-mixed.mp4` and the packaging outputs
4. Update `hooks/session-start.sh` and `agents/video-engine-agent.md` reference table
5. Sync `CLAUDE.md`: version 3.0.0, Commands table, Architecture table, Reference Files table, Smart
   Context Loading, new debugging rows (double audio, explainer with no shot, A/V mismatch, voice env
   unset, Voice Changer drift, inaudible cue, oversized pad)
6. Rewrite `README.md`: new name, 8 commands, dependency table (ffmpeg / Node / ElevenLabs key), the
   degradation policy, attribution to the editor
7. Run `bash tests/run.sh`, confirm fully green — **this is the gate before anything leaves the repo**
8. Rename the working folder `ai-video-promo-engine` → `gaspol-video`; `git worktree repair`; verify
   `bash tests/run.sh` still passes from the new path
9. Rename the GitHub repo to `gaspol-video`; update `origin`; push the branch
10. Add the `gaspol-video` entry to `gaspol-one/.claude-plugin/marketplace.json` with
    `source: {source: "url", url: "https://github.com/alisadikinma/gaspol-video.git"}` and
    `version: "3.0.0"` (version duplication contract), commit and push that repo
11. Update external references to the old name: `/Users/alisadikin/CLAUDE.md`,
    `Obsidian-Vault/30-Knowledge/video-pipeline-shared.md`, `image-gen-shared.md`,
    `playbook-media-generation.md`, `20-Projects/claude-plugin/README.md`,
    `20-Projects/Portfolio_v2/README.md`, `10-Identity/capability-dossier-lkh.md`,
    `40-Daily/2026-04-29.md`, `40-Daily/2026-07-10.md`, and
    `~/.claude/projects/.../Portfolio-v2/memory/*.md`
12. **List, do not run, the VPS steps** for the user: recompile the reference bundle with the new
    path, scp it, `claude plugin enable --scope user`. Record them in the ledger under
    `## Utang terbuka` until the user confirms they ran
13. Commit: "feat: orchestrate phases 6-7, sync docs, publish gaspol-video 3.0.0 to gaspol-one"

**Verification:**
- [ ] `bash tests/run.sh` passes from the renamed folder
- [ ] `orchestrator-phases.sh` passes
- [ ] `reference-index.sh` and `no-old-name.sh` still pass after the docs rewrite
- [ ] `gaspol-one` marketplace entry version matches `plugin.json` exactly (3.0.0)
- [ ] Every external reference in step 11 is updated, verified by
      `grep -rl ai-video-promo-engine` over those paths returning nothing outside `docs/plans/`
- [ ] VPS steps are written in the ledger as open debt, not silently assumed done
- [ ] No placeholder/TODO comments

---

## Out of scope (one line each)

- `clean-cut`, `brand-setup`, YouTube upload, and channel analytics from the editor.
- Rendering thumbnail images inside this plugin.
- Any hard `dependencies` declaration on `ai-image-carousel-prompt-gen`.
- Recompiling and deploying the VPS reference bundle (listed for the user, run by the user).
- From `MoneyPrinterTurbo`: stock-footage matching, the LLM script writer, the Streamlit WebUI, the
  FastAPI service and its redis queue, moviepy, `edge-tts`, and any local whisper model.

## Completeness ladder — rungs recorded as not applicable

- **Phase B, C, M observability:** not applicable — these phases add documentation and metadata, and
  produce no runtime behaviour a 3am debugger would inspect.
- **Phase D, E unit tests:** not applicable in the deterministic sense — these change LLM-driven
  routing behaviour, so their success contract is the eval file, per the plan's non-deterministic
  phase rule. Consistency tests still assert the rules are present in the skill text.
- **Concurrency edge cases:** not applicable anywhere in this plan — every tool is a single-shot CLI
  over one project folder, with no shared mutable state and no parallel execution.
