**Ticket:** GV-2

# Spec — `gaspol-video` v3.1.0: app screens, screencasts, in-session rendering, and the rest of the editor port

## Design

### 1. Problem

GV-1 carried `gaspol-video` from brainstorm to a mixed file, adapting part of
`claude-youtube-editor` (MIT, `hassancs91`). A second audit of that repo on 2026-09-13 found tools that
would still strengthen the plugin, plus one gap neither repo covers.

1. **App screens are drawn by the image model.** A promo for software (an ANPR dashboard, a mobile
   app) needs screens with legible, consistent text. Today Phase 4A asks NB2 to draw `ui-*.png`, and
   the text garbles and the numbers drift between scenes. The editor has the pieces to fix this — a
   Playwright capture tool, browser chrome components, a screenshot-driven fake screencast — but no
   single tool that produces a believable screen for an app that does not exist yet.
2. **Prompts are copy-pasted by hand.** Phase 4 and Phase 5 end in prompt files. The
   `indusia-image-gen` and `indusia-video-gen` MCP servers are connected in this environment and can
   render NB2 and VEO directly, but nothing in the pipeline calls them.
3. **The music pass has nothing to play.** `mix_music.py` reads `media/music/library/tracks/`, which
   ships empty. Every project fails soft to voice-only unless the user sources tracks manually.
4. **Nothing checks what the final mix actually says.** P4 checks caption text; nothing checks that the
   narration in the rendered master matches `av-script.md`. The editor learned (ch-3, 2026-07-10) that
   only a second ASR pass over the render catches ghost speech and clipped words.
5. **Smaller gaps.** Platform-native audio sometimes carries noise or stray music into the Voice
   Changer; `composite.py` has no picture-in-picture or insert mode; there are no standalone stems for
   a human editor; Remotion QA is manual `ffmpeg -ss`; packaging calibration has no data source.

### 2. Decisions taken in the brainstorm

| Question | Decision |
|---|---|
| Dependencies | Allowed. One venv at `~/.gaspol-video/venv` (outside the plugin cache, so updates do not wipe it), built by `tools/setup.sh`. Tools that need it fail loudly naming the script; the rest keep working. |
| Rendering engine | MCP only: `indusia-image-gen` (`nano-banana-2`) for Phase 4, `indusia-video-gen` (`veo-3.1-fast`) for Phase 5. No fal, no `geminigen-video` CLI, no GROK. |
| Seedance / Kling | Prompts are still written for scenes that choose them. They are **not rendered** by the pipeline. Reference files stay. |
| When renders run | Offered **per approved batch** (max 5 scenes). Never automatic. |
| Lip-sync to a locked voice | Stays as proven on the Moni project: VEO native lip-sync, then ElevenLabs Voice Changer. `gen_avatar.mjs` is **not** ported. |
| Mock app screens | TSX in the existing Remotion workspace, `renderStill` to PNG. The same component animates in a screencast. |

### 3. Prior art verified before writing

- `indusia-video-gen` exposes VEO (`veo-3.1`, `-fast`, `-lite`, `veo-2`) and GROK; duration 4/6/8;
  aspect 16:9/9:16; `mode_image` `frame` (max 2 refs) or `ingredient` (max 3). **No extend.**
- `indusia-image-gen` exposes `nano-banana-2`, `nano-banana-pro`, `imagen-4`, `gpt-image-2`; aspects
  1:1, 16:9, 9:16, 4:3, 3:4; refs as local paths.
- `geminigen-api-client` `from-file` and `from-manifest` are stubs ("will be implemented in Phase 8/9").
  Not used, and not fixed here (other repo).
- Pillow 12.3.0 exists under `/opt/homebrew/bin/python3` and the editor's venv, not under the default
  `python3`. Playwright browsers are cached in `~/Library/Caches/ms-playwright`; the Python package is
  not installed.
- Vault note 2026-09-04: `security camera` makes Veo write `REC` on screen, and `no music/no voices`
  triggers `Audio generation failed`. Both apply to rendering.

### 4. Scope

In, ordered by impact. Each is one plan phase with its own tests.

| # | Item | Source |
|---|---|---|
| 0 | `tools/setup.sh` + `requirements.txt` + venv resolution helper | new |
| 1 | In-session rendering through indusia MCP, Phase 4A/4B/5, with `renders.json` | new |
| 2 | `gen_app_screen.py` — `capture` and `mock` modes | editor `capture_web.py` + new |
| 3 | Screencast shot type in Phase 4.5 | editor `screencast.tsx`, `browser.tsx`, `fake-screencast` skill |
| 4 | `gen_music.py` | editor `gen_music.py` |
| 5 | `verify_render.py` + validator check P6 | editor `verify_cut.py` (method) |
| 6 | `clean_voice.py` + RNNoise models | editor `clean_voice.py`, `tools/models/rnnoise/` |
| 7 | `composite.py` `split` and `insert` modes | editor `bake.py` |
| 8 | `make_stems.py` | editor `make_stems.py` |
| 9 | Remotion QA scripts, style presets, generic kit pieces | editor `remotion/scripts/`, `vidtsx-2d-generator/references/style-presets.md`, `lib/kit.tsx` |
| 10 | `composite_logo.py`, `thumb_scrim.py`, `yt_stats.py` | editor tools of the same name |

Out: `gen_video.py` (fal), `gen_avatar.mjs`, the clean-cut family (`render_cuts`, `cutlib`,
`analyze_cut`, `make_proxy`, `make_review`, `format_transcript`, `editor/`), `brand-setup`,
`yt_upload.py`, `notion_sync.py`, `lib/vscode.tsx`, `gen_thumbnail.py`, rendering Seedance/Kling,
rendering VEO extensions, implementing `from-file` in `geminigen-api-client`.

### 5. Component design

#### 5.0 Setup

- `tools/setup.sh` creates `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/venv` and installs
  `requirements.txt` (Pillow, playwright, google-api-python-client, google-auth-oauthlib). It does
  **not** download browsers when `~/Library/Caches/ms-playwright` already holds a compatible Chromium;
  otherwise it runs `playwright install chromium`.
- `tools/_venv.py` is imported first by every dependency-bearing tool. If a module is missing it exits
  2 with `missing <module>: run tools/setup.sh` — never a raw traceback.
- Existing stdlib-only tools are untouched and keep running on bare `python3`.

#### 5.1 In-session rendering (indusia MCP)

Rendering is performed by the skill calling MCP tools, not by a Python tool, because MCP servers are
reachable only from the Claude session.

- **Offer point.** After a batch passes `video-prompt-reviewer` and the user approves it, the skill asks
  once: render this batch now? The offer lists each output filename and the model.
- **Phase 4A/4B.** `generate_image(model="nano-banana-2", aspect=<prompt aspect>, refs=[<ref/ files named
  in the prompt>], output_dir=<scratch>)`, then move the file to the prompt's `**Output →**` path.
  An aspect the MCP does not accept is reported for that prompt; the batch continues.
- **Phase 5.** For scenes whose platform is VEO: `generate_video(model="veo-3.1-fast", duration ∈ {4,6,8},
  aspect ∈ {16:9, 9:16}, resolution, mode_image ∈ {frame, ingredient}, refs)`. The existing safety rules
  hold: face >30% frame → single start frame only. Output lands in `{project}/clips/scene-NN.mp4`.
- **Not offered for render,** reported as copy-paste: Seedance and Kling scenes, Scene Extension, a
  duration outside 4/6/8, an aspect outside 16:9/9:16.
- **Ledger.** `{project}/renders.json`, one entry per output: `{file, phase, scene, model, prompt_sha256,
  refs, status: done|failed|skipped, error, cdn_url, rendered_at}`. A re-offer skips entries whose
  `prompt_sha256` and status `done` still match, so an edited prompt re-renders and an unchanged one
  does not.
- **Errors** are recorded per output and never stop the batch. `Audio generation failed` is annotated
  with the vault fix (positive ambience, no negated audio list).
- **Probe first.** Before any skill text depends on it, confirm whether an uploaded ref keeps its
  filename, since NB2 identity lock matches by filename. If it does not, identity-lock prompts gain a
  descriptive fallback and the finding is recorded in `docs/evals/indusia-render-probe.md`.

#### 5.2 `gen_app_screen.py`

**Routing.** `scene-plan.md` gains a `Screen Source` column: `capture | mock | none`, decided at Phase 3
next to Render Path, before NB2 credits are spent.

**`capture --spec screens.json`.** Playwright Chromium. Spec: `viewport`, `base_url`, optional
`browser_profile` (persistent login, never a password in the spec), and `steps` of `goto | click | fill
| wait | scroll | shot`. Each `shot` writes `ref/ui-{name}-{state}.png`; the run writes
`screens/manifest.json` with `{file, url, state, simulated: false}`.

**`mock --screens screens.json`.** Claude authors `shots/screens/<Name>Screen.tsx` from:
- `src/shots/brand.json` tokens. The scaffolder only places a placeholder and prints "write brand.json
  from strategic-brief.md"; `mock` requires that step done and refuses while the placeholder values
  remain;
- Domain Knowledge vocabulary and flow;
- `screens/data.json`, the **pinned data** — names, figures, plates, timestamps — shared by every scene
  that shows the same screen (Scene Logic Realism check 3);
- `ui_text_language`.

A screen component takes a `state` prop. The tool runs Remotion `renderStill` per state and writes
`ref/ui-{name}-{state}.png`; the manifest records `simulated: true`.

**Consumers.**
1. Phase 4A classifies `ui-*` screens as UNIQUE (§26) and does not generate them with NB2 when a
   manifest entry exists. Phase 4B references them inline (`EXACTLY matching ui-anpr-dashboard.png`).
2. Phase 4.5 screencast (5.3).

**Honesty.** `video-package` and the validator read `simulated`. A simulated screen may illustrate a
flow; packaging copy may not present it as a shipped feature.

#### 5.3 Screencast shots

- Port `lib/screencast.tsx` and `lib/browser.tsx` into `templates/remotion/lib/`, with the editor's
  brand import replaced by the scaffolded `brand.json`.
- New reference `reference/post-production/18-screencast.md`, adapted from the `fake-screencast` skill:
  pages with URL and tab title, cursor keyframes as viewport fractions, click ripples, cut vs crossfade
  transitions, scroll only with a tall capture, ken-burns zoom onto the payoff.
- Mock screens animate the TSX component directly (a counter rising, a row appearing) instead of
  crossfading PNGs.
- Cue times come from narration word timings, as in `12-remotion-explainer.md`.
- QA renders a still at every cursor arrival, click, and page change (5.9) and reads it.

#### 5.4 `gen_music.py`

Reads `media/music/library/palette.json` moods. For each mood without a track, calls ElevenLabs Music
with `force_instrumental`, at `--length` (default: the project master's duration), loudness-normalises
to the bed target, writes `tracks/<mood>.mp3` and rewrites `catalog.json`. Library-first: existing
tracks are never re-billed without `--force`. `--dry-run` makes no request. Missing key: exits with the
variable name; `mix_music.py` stays fail-soft.

#### 5.5 `verify_render.py` and check P6

After pass 5. Extracts mono 16 kHz audio from the master, transcribes with the AssemblyAI client already
in `gen_subs.py` (factored into a shared module, not copied), and aligns tokens against the narration
and dialogue text of `av-script.md`. Reports, each with a master timestamp:
- inserted words (ghost speech), missing words (clipped), replaced words;
- intra-sentence gaps ≥ 0.40 s;
- tokens with confidence < 0.70;
- per-scene drift between the planned scene start and the first matched word.

Advisory: it says where to listen. P6 in `video-validate --post` fails on any missing or inserted word
and warns on the rest. Without `ASSEMBLYAI_API_KEY`, P6 reports `skipped`, never `pass`.

#### 5.6 `clean_voice.py`

Pass 1, only for `platform-native` scenes. No noise field exists today, so the audio plan gains an
optional per-scene `clean: none | isolate | rnnoise` (default `none`), set after listening to the clip. `--method eleven` (Voice Isolator) or
`--method rnnoise` (ffmpeg `arnndn`, models `sh` and `cb` shipped in `tools/models/rnnoise/`). A
third model, `bd`, was dropped: its upstream file is a 404 page, not a real model, in the source
project as well as here — `model_path("bd")` raises rather than shipping a broken 14-byte asset.
RMS is matched back to the source; the source file is never overwritten. Output duration must
equal input within 0.05 s or the tool refuses, the same rule the Voice Changer enforces.

#### 5.7 `composite.py` — `split` and `insert`

- `split <master> <shot> --at --out-s --box x,y,w,h [--crop-cx --crop-cy --zoom]`: the master is scaled
  and cropped into the box; an alpha shot is composited over it.
- `insert <master> <shot> --at`: the master freezes at `--at`, the shot plays in full with its own
  audio, then the master resumes. Output duration = master + shot.
- Both run through the existing A/V duration gate.

#### 5.8 `make_stems.py`

`--voice | --sfx | --music | --all`. Full-length WAVs starting at 0.000 in `{output_folder}/stems/`.
No ducking; plan gains are baked in.

#### 5.9 Remotion QA and kit

Into `templates/remotion/scripts/`: `qa-frames.mjs` (stills at named frames, scale 0.5, for reading),
`render-all.mjs`, `gen-registry.mjs`. The scaffolder copies them. Generic `kit.tsx` pieces (brand
background, rise-in hook, image reveal) are ported without the Claude-Code-specific components.
`style-presets.md` joins `12-remotion-explainer.md` as a section.

#### 5.10 Packaging tools

- `composite_logo.py` and `thumb_scrim.py` post-process a thumbnail already rendered by the image
  plugin: real logo pasted over the model's drawing; scrim darkened until the headline reaches ≥ 4:1.
  They render nothing, so the GV-1 split stands.
- `yt_stats.py auth | fetch <video_id>` writes views, average view duration and average view
  percentage to `packaging/calibration.json`. Read-only OAuth token in `~/.gaspol-video/youtube/`.
  CTR is not in the API; the output says so and leaves the field for manual entry.

### 6. Data Integration Map

| Component | Data source | Existing? | Notes |
|---|---|---|---|
| Render Phase 4 | image prompts + `ref/` + `indusia-image-gen` | Yes | filename-preservation probe first |
| Render Phase 5 | video prompts + keyframes + `indusia-video-gen` | Yes | `veo-3.1-fast` only |
| `renders.json` | render results | New | per project |
| `gen_app_screen capture` | live URL + spec | New | Playwright |
| `gen_app_screen mock` | `brand.json`, Domain Knowledge, `screens/data.json` | brand yes, data new | Remotion `renderStill` |
| Screencast shot | screen PNGs or TSX + narration timings | timings yes | |
| `gen_music.py` | `palette.json` + ElevenLabs Music API | palette yes | |
| `verify_render.py` | master + `av-script.md` + AssemblyAI | Yes | shares client with `gen_subs.py` |
| `clean_voice.py` | native clip + ElevenLabs Isolator / RNNoise | models copied | |
| `make_stems.py` | `sfx-plan.json`, music plan, VO files | Yes | |
| `yt_stats.py` | YouTube Data + Analytics APIs | New OAuth | CTR manual |

No placeholder integration: every API above is called for real in one recorded run under
`docs/evals/`.

### 7. Error handling

- A missing API key or venv degrades exactly one capability, loudly, naming the fix.
- Render failures are per output, recorded, and never abort a batch.
- Duration-changing audio tools refuse rather than stretch.
- P6 without transcription is `skipped`, not `pass`.

### 8. Testing

- `tests/py/` unittest per Python tool, using ffmpeg-synthesised audio and video fixtures; API tools are
  tested at request construction and `--dry-run`.
- `tests/node/` for the Remotion scripts' argument handling.
- `tests/consistency/` gains: `Screen Source` column present in bridge + skills; P6 listed in validator
  and CLAUDE.md; every new tool listed in CLAUDE.md Architecture; `renders.json` schema documented once.
- One real run per integration recorded in `docs/evals/`: indusia render probe, ElevenLabs Music,
  Voice Isolator, AssemblyAI verify, Playwright capture, mock renderStill, YouTube stats.

### 9. Docs touched

`CLAUDE.md` (architecture, tools count, Smart Context Loading rows for 18-screencast, debugging rows,
v3.1.0 changelog), `reference/global-promo-config.md` §29 (render defaults, screen source enum,
verify thresholds), `reference/script-to-scene-bridge.md` (Screen Source column),
`skills/video-image`, `video-gen`, `video-explainer`, `video-post`, `video-package`, `video-validate`,
`video-full`, `agents/video-engine-agent.md`, `.env.example`, `NOTICE`, `README.md`, `plugin.json`
(3.1.0).
