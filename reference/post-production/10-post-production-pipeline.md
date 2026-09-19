# Post-Production Pipeline (Phase 6) — folder contract and plan schemas

Read this FIRST for anything after the video clips exist. It defines where files live, what every
plan file looks like, and what happens when a tool or a key is missing. The per-topic references
(`11` voice, `12` Remotion, `13` ffmpeg, `14` SFX, `15` packaging, `16` subtitles, `17` music) assume
this file and do not repeat it.

Phases 1 to 5 produce a **prompt package**. Phase 6 turns generated clips into a **finished file**.

---

## 1. Where Phase 6 sits

```
Phase 4B  scene keyframes (NB2)          live-action scenes only
Phase 4.5 /video-explainer               explainer scenes -> Remotion shots
Phase 5   /video-gen                     platform prompts + audio-source decision
          per kelompok: VO -> clips -> voice change -> Remotion -> kelompok cut -> approval
Phase 6   /video-post --final            global tail, once every kelompok is approved
Phase 7   /video-package                 title, thumbnail bets, description
```

### The kelompok is the unit of delivery (v3.2.0)

A **kelompok** is the batch Phase 5 already works in: one ACT, or a sub-batch of at most 5 scenes.
A kelompok is carried to a near-final state before the next one starts, because a clip is not
reviewable on picture alone — it is reviewable when it carries its narration and its overlay, which
is what the audience sees.

| Step | What runs | Why it sits here |
|---|---|---|
| K.1 | Pass 1 scoped to this kelompok's lines | VO-first sets clip duration; it cannot come after the clips |
| K.2 | Render this kelompok's clips (Phase 5 step 5.5) | unchanged |
| K.3 | Voice change on platform-native dialogue in those clips | needs the clip audio to exist |
| K.4 | Remotion shots and overlays belonging to this kelompok | independent of clips, needed for the cut |
| K.5 | Pass 2 scoped: `output/kelompok-K{N}.mp4` under the A/V duration gate | the reviewable artefact |
| K.6 | User approves the kelompok | a fix here is contained to at most 5 scenes |

State lives in `work/kelompok.json` (§3.9). A kelompok that is not `approved` never feeds the tail.

### The global tail runs once

| # | Pass | Why it stays global |
|---|---|---|
| 2 | Edit (full) | concatenates the approved kelompok segments into `output/master.mp4` |
| 3 | SFX | cue levels are judged against the whole film |
| 4 | Subtitles + music | music is levelled against the finished voice across the film |
| 5 | Final mix | loudness and limiting are set once |

The passes keep their internal order. What v3.2.0 changes is their **scope**: passes 1 and 2 run per
kelompok first, then passes 2 to 5 run once over segments that are already approved. Pass 1 never
runs in the tail — every line was spoken, measured and approved inside its kelompok.

---

## 2. Project folder contract

Everything Phase 6 reads and writes lives under the project's `{output_folder}`.

```
{output_folder}/
  strategic-brief.md     Phase 1   domain context + cultural research (SFX cues read this)
  cast-profile.md        Phase 1   cast + VOICE: blocks
  av-script.md           Phase 2   narration text + per-scene SFX and music direction
  scene-plan.md          Phase 3   scene list, Render Path, durations
  ref/                   Phase 3.5 reference images
  keyframes/             Phase 4B  NB2 stills for live-action scenes
  shots/                 Phase 4.5 Remotion workspace; rendered shots in shots/out/
  clips/                 USER      generated clips, scene-{NN}[-ext{K}].mp4
  vo/                    Phase 6   narration and converted dialogue audio + vo-manifest.json
  sfx/                   Phase 6   cues generated for this project
  work/                  Phase 6   the plan files below
    kelompok.json
    clip-manifest.json
    audio-plan.json
    edit-plan.json
    sfx-plan.json
    subtitle-plan.json
    music-plan.json
  output/                Phase 6   kelompok-K{N}.mp4, master.mp4, master.srt, master-mixed.mp4
  _arsip/                any phase  rejected or superseded paid artefacts, kept with their reason
  .tmp/                  any phase  every derived file; safe to delete at any time
```

### 2.1 These folders are the whole contract. Do not create others.

Set 2026-09-20, after a project reached 25 folders: seven held preview JPEGs, seven held
"temporary" copies nobody deleted, and rejects were spread across three differently named
archives. The user could no longer tell which folder was safe to delete, which is the real cost
— not the disk space.

**A new folder needs the user's approval.** When you need somewhere to put a file, pick one of
the folders above. If none fits, the file is almost certainly derived, so it belongs in `.tmp/`.

**Variants are distinguished by a FILENAME SUFFIX inside the existing folder, never by a new
subfolder:**

| Instead of | Write |
|---|---|
| `keyframes/_up/S05.png` | `keyframes/S05-1920.png` |
| `keyframes/_small/S05.jpg` | `.tmp/S05.jpg` |
| `clips/_ov/scene-05-ov.mp4` | `.tmp/scene-05-ov.mp4` |
| `clips/_final/scene-05.mp4` | `.tmp/scene-05-jadi.mp4` |
| `clips/_cek/s05-4.0.jpg` | `.tmp/s05-4.0.jpg` |
| `keyframes/_gen/DITOLAK-S07-....png` | `_arsip/keyframe-DITOLAK-S07-....png` |
| `clips/_tidak-dipakai/scene-07-v1.mp4` | `_arsip/klip-scene-07-v1.mp4` |

Suffixes already in use: `-1920` (upload copy), `-ov` (clip plus overlay), `-jadi` (clip plus
overlay plus mixed audio), `-clean` (isolated dialogue), `-v2`/`-v3` (version).

### 2.2 `.tmp/` and `shots/out/` are the only deletable folders

Everything in them rebuilds with no API spend:

```bash
cd shots && node scripts/render-all.mjs     # overlays -> shots/out/
python3 work/rakit_*.py                     # composite + audio mix -> .tmp/ and output/
```

So never leave the ONLY copy of anything in `.tmp/`. Anything that cost money — images from an
image API, clips from a video platform, mp3s from ElevenLabs — belongs in `keyframes/`, `clips/`,
`ref/`, `vo/`, or `_arsip/`.

`_arsip/` holds paid artefacts that were rejected. Deleting one means paying again to compare
against it later, so delete only when the user says to. Every archived name states the REASON it
was rejected, which is what makes the archive worth keeping at all.

### 2.3 Two mechanical rules that caused real damage

- **MCP renders write to `.tmp/`.** `generate_image` and `generate_video` take `output_dir` — pass
  `{output_folder}/.tmp`. Both create their own `image/` or `video/` subfolder underneath; as soon
  as the file lands, move it to its permanent home under a readable name and remove that subfolder.
  Never point `output_dir` at `keyframes/` or `clips/` directly.
- **Never `sips --out <folder>/<file>`.** Twice on 2026-09-19 sips replaced the target FOLDER with
  a single image file, destroying every preview inside it (`keyframes/_small`, then
  `keyframes/_up`). Use `ffmpeg -i in.png -vf scale=1920:-2 out.png` for every resize.

Naming rules that other tools depend on:

- A clip for scene 3 is `clips/scene-03.mp4`. Its first extension is `clips/scene-03-ext1.mp4`.
- A rendered Remotion shot is `shots/out/<ShotId>.mp4`, or `.mov` when it carries alpha.
- Narration audio is `vo/scene-{NN}-narr.mp3`; converted dialogue is `vo/scene-{NN}-c{N}.mp3`.
- A kelompok cut is `output/kelompok-K{N}.mp4`. It is a segment of the film, not a draft of the whole
  film, and the tail concatenates these — it does not re-render them.

---

## 3. Plan schemas

Every pass is a **declarative plan consumed by a tool**. The plan is the reviewable artefact; the
tool is dumb on purpose. Author the plan, show it to the user, then render.

### 3.1 `clip-manifest.json` — written by `tools/probe_clips.py`

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

`problems` is never empty-by-omission: a clip with no audio stream, an A/V mismatch above 0.04s, or
a resolution that disagrees with the project's aspect ratio each add a line.

### 3.2 `audio-plan.json` — pass 1

```jsonc
{
  "audio_source": "mixed",
  "scenes": [
    { "scene": 1, "audio_source": "platform-native",
      "layers": [
        { "kind": "dialogue", "cast": "c2", "at_s": 0.0, "dur_s": 3.2,
          "text": "...", "from": "clip", "changer": true, "out": "vo/scene-01-c2.mp3" },
        { "kind": "narration", "cast": "c1", "at_s": 3.6, "dur_s": 4.1,
          "text": "...", "from": "tts", "out": "vo/scene-01-narr.mp3" }
      ] }
  ]
}
```

- `kind` ∈ `dialogue | narration | ambient | sfx`
- `from` ∈ `clip | tts`
- `audio_source` ∈ `platform-native | elevenlabs | mixed`, at video level and again per scene
- `clean` (optional, scene level) ∈ `none | isolate | rnnoise`, default `none`. Set after
  listening to the platform clip: `isolate` (ElevenLabs Voice Isolator) or `rnnoise` (local
  ffmpeg `arnndn`) run `tools/clean_voice.py` on a `dialogue` layer's clip audio BEFORE it goes
  through the Voice Changer, when the clip has background noise the changer would otherwise
  carry into the converted voice. See `11-voice-cast-and-vo.md` §5.
- Two speech layers in one scene MUST NOT overlap. A platform lip-syncs one speaker at a time, and a
  narration line that starts before the dialogue ends renders as garble.

### 3.3 `edit-plan.json` — pass 2

```jsonc
{
  "fps": 30, "width": 1920, "height": 1080,
  "out": "output/master.mp4",
  "segments": [
    { "kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 7.4 },
    { "kind": "shot", "src": "shots/out/MetricReveal.mp4", "in_s": 0.0, "out_s": 5.0 },
    { "kind": "clip", "src": "clips/scene-03.mp4", "in_s": 0.2, "out_s": 8.0,
      "pad_end_s": 0.6, "pad_mode": "freeze" }
  ]
}
```

`pad_mode` ∈ `freeze | black`. Trimming beats padding every time; a pad above 1.0s is warned about,
because a long freeze reads as a stall rather than a beat.

### 3.4 `sfx-plan.json` — pass 3

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

### 3.5 `subtitle-plan.json` — pass 4

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
  "keyterms": ["ANPR", "gate-in"]
}
```

`from` ∈ `tts-timestamps | assemblyai | manual`.

### 3.6 `music-plan.json` — pass 4

```jsonc
{
  "out": "output/master-mixed.mp4",
  "segments": [
    { "from_s": 0.0, "to_s": 28.4, "track": "media/music/library/tracks/tense-low-pulse.mp3",
      "gain_db": -22, "fade_in_s": 1.2, "fade_out_s": 2.0,
      "source": "av-script.md scene 1-4 music direction" }
  ]
}
```

### 3.7 `vo-manifest.json` — written by `tools/gen_vo.mjs`

```jsonc
{
  "generated_at": "2026-09-03T00:00:00Z",
  "model": "eleven_multilingual_v2",
  "settings": { "stability": 0.55, "similarity_boost": 0.8, "style": 0.3, "speed": 0.95 },
  "items": [
    { "id": "scene-01-narr", "file": "vo/scene-01-narr.mp3", "duration_s": 4.12,
      "cast": "c1", "voice_env": "ELEVENLABS_VOICE_C1", "chars": 96,
      "words": [ { "text": "Tiap", "start_ms": 20, "end_ms": 260 } ] }
  ]
}
```

`words` is what the subtitle pass reads when the audio source is ElevenLabs. It is absent for audio
that came from a clip; those cues fall back to AssemblyAI.

**A manifest never records a key.** It records the env var NAME (`voice_env`), never its value.

### 3.8 `renders.json` — in-session render ledger

Written and read by `tools/renders.py`, shared by the Phase 4/5 render offers so an unchanged
prompt is never re-billed. This is the single place this schema is documented — Phase 4
(`skills/video-image/SKILL.md`) and Phase 5 (`skills/video-gen/SKILL.md`) both point back here
instead of restating it.

```jsonc
{ "renders": [
  { "file": "keyframes/scene-03-start.png", "phase": "4B", "scene": 3,
    "model": "nano-banana-2", "prompt_sha256": "<hex>", "refs": ["cast-c1-face.png"],
    "status": "done", "error": null, "cdn_url": "https://...", "rendered_at": "2026-09-13T08:00:00Z" } ] }
```

- `status` ∈ `done | failed | skipped`.
- `phase` ∈ `4A | 4B | 5`.
- `prompt_sha256` — sha256 of the prompt with trailing whitespace stripped per line and CRLF
  normalised to LF, so a whitespace-only re-save of the same prompt does not trigger a re-render.
- An entry is keyed by `file`: `record()` replaces the existing entry for that file rather than
  appending a second one. `needs_render()` is False only when the existing entry for that `file`
  has `status == "done"` AND the same `prompt_sha256` — any other combination (different prompt,
  or a prior `failed`/`skipped` status) means render again.
- `rendered_at` is stamped in UTC ISO-8601 `Z` when the caller does not supply one.
- `python3 tools/renders.py <project> --print` prints one line per entry (`status  phase  file
  model`) and a count per status — the quick way to see what still needs a render offer.

---

### 3.9 `kelompok.json` — the delivery ledger (v3.2.0)

Written by Phase 5 at step 5.0b, updated at every K step, read by `/video-post` in both modes.
One entry per kelompok, in play order.

```json
{
  "kelompok": [
    {
      "id": "K1",
      "act": "BABAK 1 — MASALAH",
      "scenes": ["S01", "S02", "S03", "S04", "S05"],
      "vo": "done",
      "clips": "done",
      "voice_change": "n/a",
      "remotion": "done",
      "cut": "output/kelompok-K1.mp4",
      "status": "approved",
      "approved_at": "2026-09-19"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `id` | `K1`, `K2`, … in play order. Stable for the life of the project. |
| `act` | the ACT this kelompok belongs to, copied from `scene-plan.md` |
| `scenes` | scene ids in this kelompok, including its explainer scenes |
| `vo` `clips` `voice_change` `remotion` | `pending` · `done` · `n/a` |
| `cut` | path to the kelompok segment, written at step K.5 |
| `status` | `pending` · `in-progress` · `cut-ready` · `approved` · `rework` |
| `approved_at` | date the user approved the kelompok; absent until then |

Rules:

- A kelompok reaches `cut-ready` only when every one of its four work fields is `done` or `n/a`.
- Only `approved` kelompok feed the global tail. The tail refuses to start while any kelompok is not
  `approved`, and says which.
- `rework` means the user rejected the cut. Fixing it re-runs only the steps whose field was reset,
  and never touches another kelompok.

## 4. The A/V duration gate

Run after every render that produces a video with sound.

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 OUT.mp4
ffprobe -v error -select_streams a:0 -show_entries stream=duration -of csv=p=0 OUT.mp4
```

The two values must be equal within **0.04s** (one frame at 25fps). Unequal means the render is
rejected, not shipped with a note. Drift accumulates along a timeline, so a budget that grows with
duration hides a real fault; equality is the only check that does not.

When a 10-bit HEVC master will not play in a reviewer's player, produce an 8-bit H.264 by re-stamping
constant frame rate, `-r` BEFORE `-i` so no frame is dropped:

```bash
ffmpeg -r <src_fps> -i master.mp4 -c:v libx264 -crf 19 -pix_fmt yuv420p -c:a aac master-h264.mp4
```

---

## 5. Degradation policy

A missing binary or a missing API key **never fails a skill**. Every tool:

1. Detects the gap before doing any work.
2. Prints the exact command the user can run elsewhere.
3. States plainly which capability is lost.
4. Exits 0 and lets the skill continue with what it can still do.

Silent degradation is banned. So is pretending: a pass that could not run says so in the summary, and
the skill never reports a step as done when it was skipped.

| Missing | Lost | Still works |
|---|---|---|
| `ffmpeg` / `ffprobe` | assembly, compositing, mixing, burn-in | every plan file is still authored |
| `ELEVENLABS_API_KEY` | generated narration, voice conversion | platform-native audio, everything downstream of it |
| `ASSEMBLYAI_API_KEY` | timing for platform-spoken dialogue | cues for ElevenLabs narration, from TTS timestamps |
| Node | Remotion shots | everything not explainer |
| the image plugin | thumbnail prompts | title, bets, description, raw concept briefs |

---

## 6. Gates that block

Two gates in Phase 6 are hard, in the same sense as the Phase 3.5 reference gate:

1. **The SFX cue sheet is audited by the user before anything is mixed.** Print it
   (`mix_sfx.py --print`), get approval, then mix.
2. **The A/V duration gate above.** A failed gate is a rejected render.

Everything else is fail-soft: a caption or a music bed that fails warns and still ships the video.
The difference is deliberate. A wrong mix is invisible until someone listens; a missing music bed is
obvious on the first play.
