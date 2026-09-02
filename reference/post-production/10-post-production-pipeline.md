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
          [user generates clips, uploads them to {output_folder}/clips/]
Phase 6   /video-post                    five passes, in this order
Phase 7   /video-package                 title, thumbnail bets, description
```

The five passes of `/video-post` run in a fixed order, and the order is not a preference:

| # | Pass | Why it cannot move |
|---|---|---|
| 1 | Audio | The voice-over has to exist before anything knows how long a beat really is. |
| 2 | Edit | Cue times only mean something once the master timeline exists. |
| 3 | SFX | Needs the assembled master to place cues against. |
| 4 | Subtitles + music | Subtitles need the final audio; music is levelled against the finished voice. |
| 5 | Final mix | Everything else must be in place before loudness and limiting are set. |

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
    clip-manifest.json
    audio-plan.json
    edit-plan.json
    sfx-plan.json
    subtitle-plan.json
    music-plan.json
  output/                Phase 6   master.mp4, master.srt, master-mixed.mp4
```

Naming rules that other tools depend on:

- A clip for scene 3 is `clips/scene-03.mp4`. Its first extension is `clips/scene-03-ext1.mp4`.
- A rendered Remotion shot is `shots/out/<ShotId>.mp4`, or `.mov` when it carries alpha.
- Narration audio is `vo/scene-{NN}-narr.mp3`; converted dialogue is `vo/scene-{NN}-c{N}.mp3`.

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

---

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
