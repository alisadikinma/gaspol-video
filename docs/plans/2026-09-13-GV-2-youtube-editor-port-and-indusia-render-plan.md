> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.
> **Progress ledger — HARD PER-PHASE GATE:** `.gaspol/progress/PROGRESS-GV-2.md`. After EACH phase and **BEFORE** starting the next, STOP and do BOTH: (a) tick that phase's `## Checklist` line, (b) append a `## Log` line ending with the handoff cursor. This is **blocking**, like a test gate: no next phase until both are written. **Never batch all updates at the end** — a crash mid-run must leave a truthful state, not a stale one. Update ONLY this file — never the shared `.gaspol/progress.md`.
> **Self-contained:** this plan is the COMPLETE spec. It must be executable by an agent with **no other context**. Every file path, contract, config key, and convention it needs is written here **verbatim**.

**Ticket:** GV-2
**Ledger:** .gaspol/progress/PROGRESS-GV-2.md
**Spec:** docs/plans/2026-09-13-GV-2-youtube-editor-port-and-indusia-render-spec.md

## Goal

Bring `gaspol-video` from 3.0.0 to 3.1.0 by (1) rendering Phase 4 images and Phase 5 VEO clips inside
the Claude session through the `indusia-image-gen` / `indusia-video-gen` MCP servers, offered per
approved batch; (2) adding `tools/gen_app_screen.py`, which produces believable, legible app screens
either by capturing a real URL (Playwright) or by rendering a TSX mock (Remotion `renderStill`), and a
screencast shot type that animates them; and (3) porting the remaining tools from
`claude-youtube-editor` that strengthen post-production and packaging: `gen_music`, `verify_render`,
`clean_voice`, `composite` split/insert, `make_stems`, Remotion QA scripts, `composite_logo`,
`thumb_scrim`, `yt_stats`. It matters because app screens are currently drawn by NB2 with garbled
text, prompts are copy-pasted by hand, the music pass ships with an empty library, and nothing checks
what the final mix actually says.

## Architecture Context

Paths are relative to the repo root, which during execution is the worktree
`/Users/alisadikin/Drive-D/claude-plugin/gaspol-video/.claude/worktrees/gv-2` (branch
`feat/GV-2-youtube-editor-port`). Run every command from there. Never `cd` to the main checkout.

Source repo for ports (read-only, never modify):
`/Users/alisadikin/Drive-D/claude-plugin/claude-youtube-editor` — below abbreviated `$YE`.

**Plugin layout (from CLAUDE.md):**

| Path | Purpose |
|---|---|
| `skills/<name>/SKILL.md` | Skills: `video-brainstorm`, `video-script`, `video-image`, `video-explainer`, `video-gen`, `video-post`, `video-package`, `video-validate`, `video-full`, `video-add-platform` |
| `agents/video-prompt-reviewer.md` | Independent validator, checks C1–C10 |
| `agents/video-engine-agent.md` | Batch production subagent |
| `tools/*.py`, `tools/*.mjs` | CLI tools. Existing: `burn_subs.py composite.py edit_render.py gen_sfx.py gen_subs.py mix_music.py mix_sfx.py probe_clips.py gen_vo.mjs voice_changer.mjs` |
| `templates/remotion/` | `scaffold.mjs`, `Shot.template.tsx`, `brand.json` |
| `media/sfx/library/` | `palette.json`, `catalog.json` |
| `media/music/library/` | `palette.json` (moods); tracks never committed |
| `reference/post-production/10..17-*.md` | Phase 4.5–7 method references |
| `reference/global-promo-config.md` | Single source of truth for settings; §29 = post-production defaults (29.1 Enums … 29.5 Explainer shots) |
| `reference/script-to-scene-bridge.md` | Phase 3 Scene Breakdown table incl. `Render Path` (`live-action` / `explainer`) |
| `tests/run.sh` | `bash tests/run.sh [all|consistency|py|node]` — bash checks in `tests/consistency/*.sh`, `python3 -m unittest discover -s tests/py -t .`, `node --test "tests/node/*.test.mjs"` |
| `tests/py/media.py` | ffmpeg fixture helpers: `requires_ffmpeg`, `make_clip(path, seconds, fps, size, audio, audio_seconds)`, `make_silent_clip`, `duration_of(path, stream)` |
| `.env.example` | env var NAMES only |
| `NOTICE` | attribution for adapted methods |

**Project folder contract** (`reference/post-production/10-post-production-pipeline.md` §2), unchanged
except the additions marked NEW:

```
{output_folder}/
  strategic-brief.md  cast-profile.md  av-script.md  scene-plan.md
  ref/                reference images (NEW: ui-{name}-{state}.png from gen_app_screen)
  keyframes/          NB2 stills
  shots/              Remotion workspace; rendered shots in shots/out/
  screens/            NEW: screens.json, data.json, manifest.json
  clips/              scene-{NN}.mp4, scene-{NN}-ext{K}.mp4
  vo/  sfx/
  work/               clip-manifest.json audio-plan.json edit-plan.json sfx-plan.json subtitle-plan.json music-plan.json
                      NEW: verify-report.md
  output/             master.mp4 master.srt master-mixed.mp4  NEW: stems/
  renders.json        NEW: in-session render ledger
```

**Plan schemas this ticket reads** (verbatim from reference 10 §3):

`audio-plan.json`:
```jsonc
{ "audio_source": "mixed",
  "scenes": [ { "scene": 1, "audio_source": "platform-native",
    "layers": [
      { "kind": "dialogue", "cast": "c2", "at_s": 0.0, "dur_s": 3.2, "text": "...", "from": "clip", "changer": true, "out": "vo/scene-01-c2.mp3" },
      { "kind": "narration", "cast": "c1", "at_s": 3.6, "dur_s": 4.1, "text": "...", "from": "tts", "out": "vo/scene-01-narr.mp3" } ] } ] }
```
`kind` ∈ `dialogue | narration | ambient | sfx`; `from` ∈ `clip | tts`.

`edit-plan.json`:
```jsonc
{ "fps": 30, "width": 1920, "height": 1080, "out": "output/master.mp4",
  "segments": [ { "kind": "clip", "src": "clips/scene-01.mp4", "in_s": 0.0, "out_s": 7.4 },
                { "kind": "shot", "src": "shots/out/MetricReveal.mp4", "in_s": 0.0, "out_s": 5.0 } ] }
```

`sfx-plan.json`:
```jsonc
{ "master": "output/master.mp4", "catalog": "media/sfx/library/catalog.json",
  "render": { "out": "output/master-mixed.mp4", "duck": true },
  "events": [ { "at_s": 12.40, "sfx_id": "amb-factory-floor", "gain_db": -16, "scene": 4 } ] }
```

`music-plan.json`:
```jsonc
{ "out": "output/master-mixed.mp4",
  "segments": [ { "from_s": 0.0, "to_s": 28.4, "track": "media/music/library/tracks/tense-low-pulse.mp3",
                  "gain_db": -22, "fade_in_s": 1.2, "fade_out_s": 2.0, "source": "av-script.md scene 1-4 music direction" } ] }
```

**Existing code to reuse, not rewrite:**
- `tools/gen_subs.py::transcribe_assemblyai(audio_path, api_key, keyterms=(), poll_s=3.0, log=print)` — returns `{"words": [{"text","start_ms","end_ms"}]}`. Phase K adds `confidence` to each word (additive).
- `tools/gen_subs.py::derive_keyterms(project, limit=40)`.
- `.env` loading idiom used by `gen_sfx.py` and `gen_subs.py`: `env = dict(os.environ)` then `setdefault` from lines of `Path(".env")`.
- `tools/composite.py`: `CompositeError`, `duration_of`, `require_alpha`, `validate_span`, `_run`, `cutaway`, `overlay`, `main`.
- `tools/mix_music.py`: `TONE_TO_MOOD`, fail-soft `apply()`, `resolve_segments`, `fit_track`.
- `tools/gen_sfx.py` shape: `LibraryError`, `load_palette`, `load_catalog`, `TARGET_LUFS = -20.0`, `TARGET_PEAK_DBFS = -1.5`, `--only/--force/--dry-run/--renorm`.

**Conventions (hard rules):**
- Python tools: `#!/usr/bin/env python3`, a module docstring whose first line is the CLI purpose, one custom `XError(Exception)`, `main(argv=None)` returning an exit code, `sys.exit(main())`. Errors print `"<tool>: <message>"` to stderr.
- Tools that need a third-party module import `tools/_venv.py` FIRST (Phase A). All other tools stay stdlib-only.
- No binary fixtures committed; tests synthesise media with ffmpeg (`tests/py/media.py`). RNNoise `.rnnn` models are the one sanctioned binary asset (copied verbatim, ~600 KB total).
- Never write an API key or voice id into any repo file. `.env.example` names variables only.
- NB2 prompts reference ref images by bare filename (`cast-c1-face.png`), never `ref/` prefix.
- No em dash `—` inside any VEO `says:` / `Voice-over narrator:` text.
- Docs in `docs/plans/` and `reference/` are English. User-facing chat is simple Indonesian.
- Commit after each phase: `git add <files> && git commit -m "<type>(GV-2): <summary>"` ending with the line `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

**MCP facts (verified 2026-09-13, `list_video_models` / `list_image_models`):**
- `mcp__indusia-image-gen__generate_image(prompt, model="nano-banana-pro", aspect="1:1", style="Photorealistic", mode=None, resolution="2K", output_format="png", output_dir, refs=None, poll_timeout=420, poll_interval=6)`. Models: `nano-banana-pro`, `nano-banana-2`, `imagen-4`, `gpt-image-2`. Aspects for NB models: `1:1 | 16:9 | 9:16 | 4:3 | 3:4`. Resolution `1K | 2K | 4K`. Refs: local paths or https URLs. Returns a summary string with local file path + CDN URL, or an error string.
- `mcp__indusia-video-gen__generate_video(prompt, model="veo-3.1-fast", resolution="720p", duration=8, aspect="16:9", mode_image="frame", output_dir, refs=None, poll_timeout=900, poll_interval=15)`. VEO: resolution `720p | 1080p`; duration `4 | 6 | 8`; aspect `16:9 | 9:16`; `mode_image` `frame` (start/end, max 2 refs) or `ingredient` (max 3 refs). No extend endpoint.
- Decision: images render with `nano-banana-2`; clips with `veo-3.1-fast` only. No GROK, no Seedance, no Kling, no fal, no `geminigen-video` CLI (its `from-file`/`from-manifest` are unimplemented stubs).
- Vault finding 2026-09-04: `security camera` in a Veo prompt makes Veo draw `REC` text; a negated audio list (`no music, no voices`) triggers `Audio generation failed`. Fix: `fixed overhead view`, positive ambience description.

**Environment facts (verified 2026-09-13):** macOS arm64; default `python3` = 3.14.7 without Pillow; `/opt/homebrew/bin/python3` 3.14.6 has Pillow; Playwright browsers cached at `~/Library/Caches/ms-playwright/chromium-1243`; `node` v26.0.0; `ffmpeg` at `/opt/homebrew/bin/ffmpeg`. Repo `.env` defines `ASSEMBLYAI_API_KEY`, `ELEVENLABS_API_KEY` (values never printed). No YouTube OAuth client secret exists anywhere.

## Tech Stack

- Python 3 stdlib + ffmpeg/ffprobe for audio/video tools (existing choice).
- Venv at `${GASPOL_VIDEO_HOME:-$HOME/.gaspol-video}/venv` for Pillow, playwright, google-api-python-client, google-auth-oauthlib (new, approved by user).
- Node ESM builtins for tests; Remotion 4 (`remotion`, `@remotion/cli`, `@remotion/bundler`, `@remotion/renderer`) inside each project's `shots/` workspace, installed by the user with `npm install`.
- MCP tools called by skills (not by Python).
- detect-stack: **no stack markers for this project — verification is plan-declared only.** The suite command is `bash tests/run.sh`.

## Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Venv resolution | `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/venv` | `tools/_venv.py` | No | Create (A) |
| Render ledger | `{output_folder}/renders.json` | `tools/renders.py` | No | Create (B) |
| Filename-preservation finding | indusia-image-gen MCP | `generate_image` | Yes (MCP connected) | Real probe run (B) |
| Phase 4 image render | `image-prompts.md`, `nb2-reference-prompts.md`, `ref/` | `mcp__indusia-image-gen__generate_image` | Yes | Wire into `skills/video-image/SKILL.md` (C) |
| Phase 5 clip render | `video-prompts.md`, `keyframes/`, `scene-plan.md` | `mcp__indusia-video-gen__generate_video` | Yes | Wire into `skills/video-gen/SKILL.md` (D) |
| Remotion lib + scripts | `$YE/remotion/src/lib/{browser,screencast,kit}.tsx`, `$YE/remotion/scripts/*.mjs` | `templates/remotion/scaffold.mjs` | Source yes, port no | Port (E) |
| App screen capture | live URL + `screens/screens.json` | Playwright Chromium | No | Create `gen_app_screen.py capture` (F) |
| App screen mock | `shots/src/shots/brand.json`, Domain Knowledge in `strategic-brief.md`, `screens/data.json` | Remotion `renderStill` via `shots/scripts/render-stills.mjs` | brief yes, rest no | Create `gen_app_screen.py mock` (G) |
| Screen Source routing | `scene-plan.md` | bridge + skills + reviewer C11 | No | Create (H) |
| Screencast shot | screen PNGs / TSX + `vo/vo-manifest.json` word times | `templates/remotion/lib/screencast.tsx` | timings yes | Reference + skill step (I) |
| Music tracks | `media/music/library/palette.json` | ElevenLabs `POST https://api.elevenlabs.io/v1/music` | palette yes | Create `gen_music.py` (J) |
| Render verification | `output/master-mixed.mp4` (fallback `output/master.mp4`) + `work/audio-plan.json` | `gen_subs.transcribe_assemblyai` | Yes | Create `verify_render.py`, P6 (K) |
| Voice cleanup | clip audio | ElevenLabs `POST https://api.elevenlabs.io/v1/audio-isolation`; ffmpeg `arnndn` | models in `$YE/tools/models/rnnoise/` | Create `clean_voice.py` (L) |
| PiP / insert | master + shot files | ffmpeg | No | Extend `composite.py` (M, N) |
| Stems | `output/master.mp4`, `work/sfx-plan.json`, `work/music-plan.json`, catalogs | ffmpeg | Yes | Create `make_stems.py` (O) |
| Thumbnail post-process | rendered thumbnail PNG + user logo | Pillow | No | Create `composite_logo.py`, `thumb_scrim.py` (P) |
| Packaging calibration | YouTube Data API v3 + Analytics API v2 | google-api-python-client, OAuth | No (no client secret yet) | Create `yt_stats.py`; real run STOPS for user credential (Q) |

## Phase overview

| Phase | Code Deliverable | Design Deliverable | Verification |
|---|---|---|---|
| A | venv setup + `_venv.py` | n/a (tooling) | unit tests + real `setup.sh` run |
| B | `renders.py` ledger + probe eval | n/a | unit tests + real MCP probe |
| C | Phase 4 render offer in skill | n/a (skill text) | consistency check |
| D | Phase 5 render offer in skill | n/a | unit + consistency |
| E | Remotion lib + scripts in template | Brand tokens from `brand.json` only; no palette shipped (existing GV-1 rule) | node tests + real scaffold/render |
| F | `gen_app_screen.py capture` | n/a | unit + real capture |
| G | `gen_app_screen.py mock` | Screen look = client brand.json + domain vocabulary; no plugin palette | unit + real renderStill |
| H | Screen Source routing, C11 | n/a | consistency |
| I | `18-screencast.md` + explainer step | Cursor/zoom motion rules from `fake-screencast` | consistency + real screencast render |
| J | `gen_music.py` | n/a | unit + real API run |
| K | `verify_render.py` + P6 | n/a | unit + real ASR run |
| L | `clean_voice.py` | n/a | unit + real runs |
| M | `composite.py split` | n/a | unit |
| N | `composite.py insert` | n/a | unit |
| O | `make_stems.py` | n/a | unit |
| P | `composite_logo.py`, `thumb_scrim.py` | n/a | unit |
| Q | `yt_stats.py` | n/a | unit; real run user-gated |
| R | Docs, version 3.1.0 | n/a | full suite + consistency |

---

### Phase A: Venv setup and dependency guard

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/_venv.py`
- Create: `tools/setup.sh`
- Create: `requirements.txt`
- Test: `tests/py/test_venv.py`

**Contract:**
- `requirements.txt` lines: `Pillow>=12`, `playwright>=1.50`, `google-api-python-client>=2.200`, `google-auth-oauthlib>=1.4`.
- `tools/setup.sh`: `set -euo pipefail`; `HOME_DIR="${GASPOL_VIDEO_HOME:-$HOME/.gaspol-video}"`; creates `$HOME_DIR/venv` with `python3 -m venv` only if `$HOME_DIR/venv/bin/python` is missing; runs `"$HOME_DIR/venv/bin/pip" install -r "$ROOT/requirements.txt"`; runs `"$HOME_DIR/venv/bin/python" -m playwright install chromium` (a no-op when the matching build is cached); prints the interpreter path. Exit non-zero on any failure.
- `tools/_venv.py` exposes `venv_python() -> Path` and `require(module: str) -> ModuleType`. `require` first tries `importlib.import_module(module)`; on `ImportError` it checks `venv_python()` exists; if it does and `sys.executable != venv_python()`, it re-execs the current script with `os.execv(str(venv_python()), [str(venv_python())] + sys.argv)`; otherwise raises `DependencyMissing(f"missing {module}: run tools/setup.sh")`. Re-exec is guarded by env `GASPOL_VIDEO_REEXEC=1` so it happens at most once (set it before `execv`; if already set, raise instead of looping).
- A tool catching `DependencyMissing` prints the message and exits **2**.

**Steps:**
1. Write failing test for `_venv.require("module_that_does_not_exist_gv2")` raising `DependencyMissing` whose message contains `run tools/setup.sh` when `GASPOL_VIDEO_REEXEC=1` is set. Expected error: `ModuleNotFoundError: No module named 'tools._venv'`
2. Run `python3 -m unittest tests.py.test_venv -v`, confirm it fails for that reason.
3. Add test: `venv_python()` honours `GASPOL_VIDEO_HOME` (set to a temp dir; expect `<tmp>/venv/bin/python`).
4. Add test: `require("json")` returns the stdlib module without re-exec.
5. Implement `tools/_venv.py`.
6. Run the test file, confirm pass.
7. Write `requirements.txt` and `tools/setup.sh`; `chmod +x tools/setup.sh`.
8. Real run: `bash tools/setup.sh`; confirm it prints the interpreter path and `~/.gaspol-video/venv/bin/python -c "import PIL, playwright, googleapiclient"` exits 0.
9. Run `bash tests/run.sh`, confirm `RESULT PASS`.
10. Commit: `feat(GV-2): venv setup and dependency guard for tools that need libraries`

**Error paths:** module missing and no venv (raise, exit 2); venv present but module still missing after re-exec (guard env var prevents loop, raise); `python3 -m venv` unavailable (setup.sh exits non-zero with pip/venv output).
**Edge cases:** `GASPOL_VIDEO_HOME` with spaces (quote every expansion); re-running setup.sh on an existing venv (skips creation, pip is idempotent).
**Observability:** setup.sh echoes each step and the final interpreter path; `DependencyMissing` names the module.

**Verification:**
- [ ] detect-stack: no stack markers for this project — verification is plan-declared only
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] `~/.gaspol-video/venv/bin/python -c "import PIL, playwright, googleapiclient"` exits 0
- [ ] Running a tool that requires a missing module prints `missing <module>: run tools/setup.sh` and exits 2
- [ ] No placeholder/TODO comments in new code

---

### Phase B: Render ledger and indusia filename probe

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/renders.py`
- Create: `docs/evals/indusia-render-probe.md`
- Test: `tests/py/test_renders.py`

**Contract — `renders.json`:**
```jsonc
{ "renders": [
  { "file": "keyframes/scene-03-start.png", "phase": "4B", "scene": 3,
    "model": "nano-banana-2", "prompt_sha256": "<hex>", "refs": ["cast-c1-face.png"],
    "status": "done", "error": null, "cdn_url": "https://...", "rendered_at": "2026-09-13T08:00:00Z" } ] }
```
`status` ∈ `done | failed | skipped`. `phase` ∈ `4A | 4B | 5`.

**Contract — `tools/renders.py` (stdlib):**
- `prompt_sha256(prompt: str) -> str` — sha256 of the prompt with trailing whitespace stripped per line and CRLF normalised to LF.
- `load(project) -> dict` — returns `{"renders": []}` when the file is missing; raises `RenderLedgerError` naming the file on invalid JSON.
- `needs_render(ledger, file, prompt) -> bool` — False only when an entry with the same `file` has `status == "done"` and the same `prompt_sha256`.
- `record(project, entry) -> None` — replaces an existing entry with the same `file`, else appends; writes atomically (`tmp` then `os.replace`); stamps `rendered_at` in UTC ISO-8601 `Z` when absent.
- `parse_mcp_result(text) -> dict` — extracts the first absolute local path ending in `.png|.jpg|.jpeg|.mp4` and the first `https://` URL from the MCP summary string; returns `{"local_path", "cdn_url", "error"}`, with `error` set to the whole text when no local path is found.
- CLI: `python3 tools/renders.py <project> --print` prints one line per entry `status  phase  file  model` and a count per status.

**Steps:**
1. Write failing test for `needs_render` returning False for an unchanged done prompt and True after the prompt changes. Expected error: `ModuleNotFoundError: No module named 'tools.renders'`
2. Run `python3 -m unittest tests.py.test_renders -v`, confirm it fails for that reason.
3. Add tests: missing ledger file loads empty; invalid JSON raises `RenderLedgerError`; `record` replaces same-file entry (count stays 1); `failed` entry always needs render; CRLF vs LF prompt hash equal; `parse_mcp_result` on a sample success string (`"Saved: /tmp/x/abc.png\nURL: https://cdn.example/abc.png"`) and on an error string (`"Error: Audio generation failed"`).
4. Implement `tools/renders.py`.
5. Run tests, confirm pass.
6. Real probe (requires the MCP; costs one image credit): in a scratch dir, write a small solid-colour PNG named `probe-ref-face.png` with ffmpeg (`ffmpeg -f lavfi -i color=c=0x3366cc:s=512x512 -frames:v 1 probe-ref-face.png`). Call `mcp__indusia-image-gen__generate_image(prompt="A plain studio backdrop tinted with the exact colour of reference image: probe-ref-face.png", model="nano-banana-2", aspect="1:1", resolution="1K", output_dir=<scratch>, refs=[<abs path>])`. Record in `docs/evals/indusia-render-probe.md`: the raw result text, whether the output colour follows the ref, and whether the tool's upload keeps the filename (read `/Users/alisadikin/Drive-D/claude-plugin/geminigen-api-client/scripts/geminigen_client.py` upload function to confirm what filename is sent in the multipart body). State a verdict line: `filename-preserved: yes|no`.
7. If the verdict is `no`: add to the eval file the fallback rule Phase C must use (identity-lock prompts keep the filename AND add a one-clause descriptive anchor). If `yes`: record that no fallback is needed.
8. Commit: `feat(GV-2): render ledger and indusia filename-preservation probe`

**Error paths:** corrupt ledger JSON; MCP returns an error string; MCP returns no local path; disk write fails mid-record (atomic replace leaves old file intact).
**Edge cases:** empty prompt (hash of empty string, still recorded); two scenes writing the same filename (second replaces first — test asserts one entry); unicode prompt text.
**Observability:** `--print` summary; each entry carries `error` text verbatim from MCP.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] `docs/evals/indusia-render-probe.md` exists with the raw MCP result and a `filename-preserved:` verdict line
- [ ] `python3 tools/renders.py <scratch-project> --print` runs on a ledger written by the tests
- [ ] No placeholder/TODO comments in new code

---

### Phase C: Phase 4 render offer (NB2 via indusia-image-gen)

**Estimated time:** 15 minutes

**Files:**
- Modify: `skills/video-image/SKILL.md` (after Step 4A.5 approval; inside Step 4B.2 after `5. APPROVE`)
- Modify: `reference/global-promo-config.md` (new §29.6 Rendering)
- Test: `tests/consistency/render-offer-contract.sh`

**Contract — text to add to `skills/video-image/SKILL.md`:**

After Step 4A.5 option A and after Step 4B.2 step 5 option A, insert a step `RENDER OFFER` with:
1. Build the render list for the approved batch: each prompt's `**Output →**` filename, model `nano-banana-2`, aspect from the prompt's first line, refs = every bare filename in the prompt's Required Reference Images table resolved to `{output_folder}/ref/<name>` (a ref file that does not exist is listed as missing and that prompt is `skipped`, never rendered without it).
2. Skip prompts where `python3 tools/renders.py` logic says the file is already `done` with the same prompt hash (state that it is up to date).
3. AskUserQuestion: `Render batch {N} sekarang? ({k} gambar, model nano-banana-2)` with options `Render sekarang` / `Nanti, simpan prompt saja` / `Pilih scene tertentu`.
4. On render: for each prompt call `mcp__indusia-image-gen__generate_image(prompt=<full prompt body>, model="nano-banana-2", aspect=<aspect>, resolution="2K", output_format="png", output_dir="{output_folder}/.render-tmp", refs=[...])`, move the returned local file to the `**Output →**` path, and record the entry with `phase` 4A or 4B.
5. An aspect outside `1:1 16:9 9:16 4:3 3:4` → entry `skipped` with error `aspect <x> not supported by indusia-image-gen`.
6. A failed call → entry `failed` with the MCP text; continue with the next prompt; list failures at the end of the batch.
7. After rendering, Read each produced image (multimodal) and report anything visibly wrong against the prompt before moving on.
8. If `docs/evals/indusia-render-probe.md` says `filename-preserved: no`, apply the fallback rule recorded there.

**Contract — §29.6 Rendering (global-promo-config.md), exact table:**

| Key | Value |
|---|---|
| `render_offer` | `per_batch` |
| `render_image_model` | `nano-banana-2` |
| `render_image_resolution` | `2K` |
| `render_video_model` | `veo-3.1-fast` |
| `render_video_durations` | `4, 6, 8` |
| `render_video_aspects` | `16:9, 9:16` |
| `render_ledger` | `{output_folder}/renders.json` |
| `render_not_offered` | Seedance scenes, Kling scenes, Scene Extension, duration outside 4/6/8, aspect outside 16:9/9:16 |

**Steps:**
1. Write failing test for `tests/consistency/render-offer-contract.sh` asserting `skills/video-image/SKILL.md` contains `mcp__indusia-image-gen__generate_image`, `nano-banana-2`, `renders.json`, `RENDER OFFER`, and `reference/global-promo-config.md` contains `29.6` and `render_offer`. Expected error: `FAIL video-image has no RENDER OFFER step` (script exit 1).
2. Run `bash tests/consistency/render-offer-contract.sh`, confirm it fails.
3. Edit `skills/video-image/SKILL.md` with the contract text above (both insertion points).
4. Add §29.6 to `reference/global-promo-config.md` after §29.5.
5. Run the check, confirm pass; run `bash tests/run.sh`.
6. Commit: `feat(GV-2): offer NB2 rendering through indusia-image-gen after each approved Phase 4 batch`

**Error paths:** missing ref file; unsupported aspect; MCP error; move fails because the output directory does not exist (create parent first).
**Edge cases:** batch where every prompt is already done (offer says up to date, no question asked); user picks specific scenes; zero prompts in batch.
**Observability:** end-of-batch table `file | status | error`; ledger entries.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] `bash tests/consistency/render-offer-contract.sh` exits 0
- [ ] Skill text never renders without the user choosing `Render sekarang`
- [ ] No placeholder/TODO comments in new text

---

### Phase D: Phase 5 render offer (VEO 3.1 fast via indusia-video-gen)

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/renders.py` (add `video_render_eligibility`)
- Modify: `skills/video-gen/SKILL.md` (inside Step 5.1 after `5. APPROVE`)
- Modify: `tests/consistency/render-offer-contract.sh`
- Test: `tests/py/test_renders.py`

**Contract — `video_render_eligibility(scene: dict) -> tuple[bool, str]`:**
Input keys: `platform` (`veo|seedance|kling`), `mode` (`frame|ingredients|i2v|extend`), `duration_s` (number), `aspect` (`16:9|9:16|...`), `refs` (list). Rules in order, first failing rule returns `(False, reason)`:
1. `platform != "veo"` → `"platform <p> is prompt-only; render it in its own UI"`
2. `mode == "extend"` → `"Scene Extension is not available in indusia-video-gen"`
3. `duration_s not in (4, 6, 8)` → `"duration <d>s not in 4/6/8"`
4. `aspect not in ("16:9", "9:16")` → `"aspect <a> not supported"`
5. `mode in ("frame", "i2v") and len(refs) > 2` or `mode == "ingredients" and len(refs) > 3` → `"too many refs for <mode>"`
Otherwise `(True, "")`. `mode` mapping to MCP: `frame` and `i2v` → `mode_image="frame"`; `ingredients` → `mode_image="ingredient"`.

**Contract — text for `skills/video-gen/SKILL.md` Step 5.1 `RENDER OFFER`:**
1. For each approved scene build `{platform, mode, duration_s, aspect, refs}` from `scene-plan.md` and the prompt; run eligibility; ineligible scenes are listed with the reason and stay copy-paste.
2. Face >30% frame keeps the existing safety rule: start frame only (`refs` = one keyframe).
3. Before calling, check the prompt for the vault traps: the phrase `security camera` (replace with `fixed overhead view` and tell the user) and a negated audio list like `no music, no voices` (replace with a positive ambience line).
4. AskUserQuestion: `Render batch {N} sekarang? ({k} clip VEO 3.1 fast, {s} detik total)` / `Nanti` / `Pilih scene`.
5. Call `mcp__indusia-video-gen__generate_video(prompt, model="veo-3.1-fast", resolution=<scene resolution>, duration=<d>, aspect=<a>, mode_image=<mapped>, output_dir="{output_folder}/.render-tmp", refs=[abs keyframe paths])`; move to `{output_folder}/clips/scene-{NN}.mp4`; record ledger `phase` 5.
6. `Audio generation failed` → record `failed` with note `negated audio list or silent prompt; rewrite ambience positively`.
7. After the batch, run `python3 tools/probe_clips.py {output_folder}` and report its `problems`.

**Steps:**
1. Write failing test for `video_render_eligibility({"platform":"kling","mode":"i2v","duration_s":5,"aspect":"16:9","refs":[]})` returning `(False, ...)` with `prompt-only` in the reason. Expected error: `AttributeError: module 'tools.renders' has no attribute 'video_render_eligibility'`
2. Run tests, confirm failure.
3. Add tests: seedance ineligible; extend ineligible; duration 5 ineligible; aspect 1:1 ineligible; frame with 3 refs ineligible; ingredients with 3 refs eligible; veo frame 8s 16:9 one ref eligible; duration as float `8.0` eligible.
4. Implement.
5. Extend consistency check: `skills/video-gen/SKILL.md` contains `mcp__indusia-video-gen__generate_video`, `veo-3.1-fast`, `RENDER OFFER`, `security camera`, `probe_clips.py`.
6. Edit `skills/video-gen/SKILL.md`.
7. Run `bash tests/run.sh`, confirm pass.
8. Commit: `feat(GV-2): offer VEO 3.1 fast rendering through indusia-video-gen after each approved Phase 5 batch`

**Error paths:** ineligible scene; MCP error; poll timeout (MCP error text recorded); missing keyframe file (skipped, named).
**Edge cases:** batch with zero eligible scenes (no question, list reasons); mixed-platform batch; extension scenes where the base clip is eligible but the extension is not.
**Observability:** reasons per ineligible scene; ledger; `probe_clips.py` problems.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] All 9 eligibility cases pass
- [ ] Skill text never offers Seedance/Kling/extend rendering
- [ ] No placeholder/TODO comments in new code

---

### Phase E: Remotion lib and QA scripts in the template

**Estimated time:** 15 minutes

**Files:**
- Create: `templates/remotion/lib/brand.ts`, `templates/remotion/lib/kit.tsx`, `templates/remotion/lib/browser.tsx`, `templates/remotion/lib/screencast.tsx`
- Create: `templates/remotion/scripts/gen-registry.mjs`, `templates/remotion/scripts/render-all.mjs`, `templates/remotion/scripts/qa-frames.mjs`
- Modify: `templates/remotion/scaffold.mjs`
- Test: `tests/node/scaffold.test.mjs`, `tests/node/gen_registry.test.mjs`

**Contract:**
- `lib/brand.ts` adapts the project's `src/shots/brand.json` (fields `background ink inkSoft accent displayFont bodyFont`) to the names the ported lib expects:
  ```ts
  import brand from '../shots/brand.json';
  export const COLORS = { paper: brand.background, ink: brand.ink, muted: brand.inkSoft, accent: brand.accent, signal: brand.accent, line: `${brand.inkSoft}55`, warn: brand.accent, cream: brand.background };
  export const FONT_DISPLAY = brand.displayFont; export const FONT_BODY = brand.bodyFont; export const FONT_MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';
  export const EASINGS = { easeOut: Easing.bezier(0.16, 1, 0.3, 1), easeInOut: Easing.bezier(0.65, 0, 0.35, 1) };
  export const SHADOW = { card: '0 24px 60px rgba(0,0,0,0.28)' }; export const RADIUS = { card: 20, pill: 999 };
  ```
  (import `Easing` from `remotion`).
- `lib/kit.tsx`: port only `CLAMP`, `BrandBg`, `useRise`, `ImageRevealShot` from `$YE/remotion/src/lib/kit.tsx`, with imports changed to `./brand`. Drop `ClaudeCodePromptShot`, `LevelTitleShot`, `Sunburst`, `V`, `VSC`, `VSCodeShell`, `ClaudeChatPanel`, and every Claude-specific constant.
- `lib/browser.tsx`: port `$YE/remotion/src/lib/browser.tsx` verbatim except imports (`./brand`, `./kit`) and replacing `lucide-react` icons with inline SVG components `ArrowLeft ArrowRight RotateCw Lock Star MoreVertical Plus X` defined in the same file (24×24 viewBox strokes), so the workspace needs no icon package.
- `lib/screencast.tsx`: port `$YE/remotion/src/lib/screencast.tsx` verbatim except imports, and remove `CloudFavicon`; the default `favicon` becomes a 17px rounded square in `COLORS.accent`.
- `scripts/gen-registry.mjs`: port `$YE/remotion/scripts/gen-registry.mjs`, remove the `--type` / `typeOfGroup` logic, and `export { parseConfig }` guarded so the script body only runs when executed directly (`if (import.meta.url === pathToFileURL(process.argv[1]).href)`). Composition config keys read: `id` (required), `durationInFrames` (NEW, preferred) else `durationInSeconds × fps`, `fps` (default 30), `width` (1920), `height` (1080), `transparent` (false).
- `scripts/render-all.mjs`: port, `publicDir` = `path.join(root, 'public')`, default `SCALE` = 1, mp4 h264 crf 18 for opaque, ProRes 4444 `yuva444p10le` `.mov` for transparent; `--still` renders a PNG at 60% of duration.
- `scripts/qa-frames.mjs`: port verbatim, `publicDir` as above; usage `node scripts/qa-frames.mjs <CompId> --out <dir> name=frame ...`.
- `scaffold.mjs` changes: `PACKAGE_JSON.dependencies` adds `"@remotion/bundler": "^4.0.0"` and `"@remotion/renderer": "^4.0.0"`; `scripts` becomes `{ gen: "node scripts/gen-registry.mjs", studio: "node scripts/gen-registry.mjs && remotion studio src/index.ts", render: "node scripts/gen-registry.mjs && node scripts/render-all.mjs", still: "node scripts/gen-registry.mjs && node scripts/render-all.mjs --still" }`; copies `lib/*` into `src/lib/` and `scripts/*` into `scripts/`; creates `public/`; `ROOT_TSX` renders every entry of `./registry.gen` (`shots.map(({Comp, config}) => <Composition key id durationInFrames fps width height component />)`); writes an initial `src/registry.gen.tsx` exporting an empty `shots` array so Studio opens before `gen` runs. Existing-workspace behaviour unchanged (prints and overwrites nothing).

**Steps:**
1. Write failing test for `tests/node/gen_registry.test.mjs` importing `parseConfig` from `../../templates/remotion/scripts/gen-registry.mjs` and asserting it returns `{id:'MetricReveal', durationInFrames:150, fps:30, width:1920, height:1080, transparent:false}` for the `compositionConfig` block of `templates/remotion/Shot.template.tsx`. Expected error: `ERR_MODULE_NOT_FOUND`
2. Run `node --test tests/node/gen_registry.test.mjs`, confirm failure.
3. Add cases: no `compositionConfig` → `null`; missing `id` → `null`; `durationInSeconds: 4` with `fps: 25` → `durationInFrames: 100`; `transparent: true` → true.
4. Implement `scripts/gen-registry.mjs`; run, pass.
5. Write failing `tests/node/scaffold.test.mjs`: run `node templates/remotion/scaffold.mjs <tmp>` via `child_process.execFileSync`; assert files `shots/src/lib/{brand.ts,kit.tsx,browser.tsx,screencast.tsx}`, `shots/scripts/{gen-registry.mjs,render-all.mjs,qa-frames.mjs}`, `shots/public/`, `shots/src/registry.gen.tsx` exist and `package.json` has `@remotion/renderer`; second run prints `already exists` and changes no mtime. Expected error: `AssertionError` on missing `shots/src/lib/brand.ts`.
6. Create the lib and script files per contract; update `scaffold.mjs`.
7. Run `bash tests/run.sh`, confirm pass.
8. Real run: scaffold into a scratch project, write a non-placeholder `brand.json`, `npm install` in `shots/`, `npm run gen`, `node scripts/render-all.mjs MetricReveal --still`, Read the PNG. `grep -rn "lucide-react\|Claude\|Cloudflare" shots/src/lib` returns nothing.
9. Commit: `feat(GV-2): ship browser, screencast and kit components plus QA scripts in the Remotion template`

**Error paths:** duplicate composition id (gen-registry warns and skips second); shot file without config (warns, skips); render of an unknown id (render-all prints nothing rendered and exits 0 — add `if (!n) { console.error('no shot matched'); process.exit(1); }`).
**Edge cases:** empty `src/shots` (registry with zero shots, Studio still opens); nested shot folders; brand font with commas.
**Observability:** gen-registry prints each id with size/fps/duration; render-all prints progress and output paths.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Real scaffold + `npm run gen` + still render produces a readable PNG that was Read
- [ ] No `lucide-react`, Claude or Cloudflare references in `templates/remotion/lib`
- [ ] No placeholder/TODO comments in new code

---

### Phase F: `gen_app_screen.py capture`

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/gen_app_screen.py`
- Test: `tests/py/test_gen_app_screen.py`

**Contract — `screens/screens.json` (capture part):**
```jsonc
{ "viewport": [1920, 1080], "device_scale": 1,
  "capture": {
    "base_url": "https://app.example.com",
    "browser_profile": "~/.gaspol-video/browser-profiles/<client>",
    "steps": [
      {"goto": "/"}, {"wait": 800}, {"wait_for": "css=.report-table"},
      {"click": "text=Export PDF", "optional": true, "timeout": 4000},
      {"fill": ["#search", "B 1234 XYZ"]}, {"press": "Enter"}, {"scroll": 400},
      {"shot": "anpr-dashboard-initial", "url_label": "app.example.com/dashboard", "title": "Dashboard"} ] } }
```
- Allowed step keys: `goto wait wait_for click fill press scroll shot`. **`eval` is not allowed** (arbitrary JS from a spec file). Any other key → `ScreenError("unknown step <i>: <keys>")`.
- A `fill` value that looks like a secret (key name or selector containing `password`, `passwd`, `token`, `secret`) → `ScreenError("do not put credentials in screens.json; log in once with --headed and a browser_profile")`.
- `shot` name must match `^[a-z0-9][a-z0-9-]*$`; output `ref/ui-<name>.png`; the name already carries the state (e.g. `anpr-dashboard-initial`).
- Writes `screens/manifest.json`: `{"screens": [{"name", "file": "ui-<name>.png", "url_label", "title", "source": "capture", "simulated": false, "captured_at"}]}`, merging by `name` with existing entries (mock entries are kept).
- CLI: `python3 tools/gen_app_screen.py capture <project> [--headed]`. `--headed` opens a visible browser (first login into `browser_profile`).
- Playwright imported via `_venv.require("playwright.sync_api")`.
- Pure functions for tests: `validate_steps(steps)`, `shot_path(project, name)`, `merge_manifest(existing, new_entries)`.

**Steps:**
1. Write failing test for `validate_steps([{"eval": "x"}])` raising `ScreenError` mentioning `unknown step`. Expected error: `ModuleNotFoundError: No module named 'tools.gen_app_screen'`
2. Run, confirm failure.
3. Add tests: credential fill rejected; bad shot name rejected; valid spec returns normalised steps; `shot_path` → `<project>/ref/ui-<name>.png`; `merge_manifest` keeps mock entries and replaces same-name capture entries; missing `capture` block → `ScreenError("screens.json has no capture block")`; missing screens.json → `ScreenError` naming the path.
4. Implement pure functions and the Playwright runner (`launch_persistent_context` when `browser_profile` set, else `launch`; `~` expanded; relative `goto` joined to `base_url`; `wait_for` timeout 30000; optional click swallows the timeout and logs `optional click skipped`).
5. Run tests, confirm pass.
6. Real run: capture `https://example.com` with steps `goto /`, `wait 500`, `shot example-home` into a scratch project; Read `ref/ui-example-home.png`; confirm manifest entry `simulated: false`.
7. Run `bash tests/run.sh`.
8. Commit: `feat(GV-2): capture real app screens into ref/ with gen_app_screen.py capture`

**Error paths:** navigation timeout (Playwright error re-raised as `ScreenError` with the step index); selector not found; venv missing (exit 2); output dir not writable.
**Edge cases:** zero `shot` steps (warn `no shots captured`, exit 1); duplicate shot names in one spec (reject); `device_scale` 2 (screenshot at 2×).
**Observability:** one line per step `step 03 click text=Export PDF`; per shot `shot [01] ui-<name>.png`; final count.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Real capture of example.com produced a PNG that was Read
- [ ] Spec with `eval` or a password fill is refused
- [ ] Security: no credentials accepted in spec files; no arbitrary JS evaluation
- [ ] No placeholder/TODO comments in new code

---

### Phase G: `gen_app_screen.py mock`

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/gen_app_screen.py`
- Create: `templates/remotion/scripts/render-stills.mjs`
- Create: `templates/remotion/Screen.template.tsx`
- Modify: `templates/remotion/scaffold.mjs` (copy `render-stills.mjs`)
- Test: `tests/py/test_gen_app_screen.py`, `tests/node/render_stills.test.mjs`

**Contract — `screens/screens.json` (mock part) and `screens/data.json`:**
```jsonc
// screens.json
{ "viewport": [1920, 1080],
  "mock": [ { "name": "anpr-dashboard", "component": "AnprDashboardScreen",
              "states": ["initial", "plate-detected"], "url_label": "anpr.client.co.id/gate", "title": "Gate Monitor" } ] }
// data.json — pinned data shared by every scene showing these screens
{ "anpr-dashboard": { "gate": "Gerbang 3", "plates": ["B 1234 XYZ", "D 5678 ABC"], "queue_minutes": 6 } }
```
- Screen component file: `{output_folder}/shots/src/shots/screens/<Component>.tsx`, authored by Claude from `Screen.template.tsx`. It exports `compositionConfig` (`id` = component name, `width`/`height` from viewport, `fps: 30`, `durationInFrames: 1`) and a default component taking props `{ state: string; data: Record<string, unknown> }`. Colours/fonts only from `lib/brand.ts`. UI language = `ui_text_language` from `strategic-brief.md`.
- `render-stills.mjs` usage: `node scripts/render-stills.mjs <CompId> --props '<json>' --out <png>`; bundles once (`publicDir` = `public`), `selectComposition({serveUrl, id, inputProps})`, `renderStill({serveUrl, composition, output, frame: 0, imageFormat: 'png', inputProps, overwrite: true})`. Exported pure helper `parseArgs(argv)`.
- `gen_app_screen.py mock <project> [--only name]`:
  1. Refuse when `shots/src/shots/brand.json` still equals the template placeholder (compare against `templates/remotion/brand.json` values ignoring `_comment`): `ScreenError("brand.json still holds template placeholders; write it from strategic-brief.md first")`.
  2. Refuse when a mock entry's component file is missing: name the expected path.
  3. Refuse when `data.json` has no key for the screen name.
  4. For each state run `node scripts/render-stills.mjs <component> --props '{"state": <s>, "data": <data[name]>}' --out <project>/ref/ui-<name>-<state>.png` with `cwd = shots/`; first run `node scripts/gen-registry.mjs`.
  5. Manifest entries `source: "mock"`, `simulated: true`, `component`, `state`, `data_key`.
- Pure functions: `is_placeholder_brand(brand, template)`, `mock_jobs(spec, data, project) -> list[dict]`.

**Steps:**
1. Write failing test for `is_placeholder_brand` returning True for the template values and False when `accent` differs. Expected error: `AttributeError: module 'tools.gen_app_screen' has no attribute 'is_placeholder_brand'`
2. Run, confirm failure.
3. Add tests: `mock_jobs` expands 2 states into 2 jobs with paths `ref/ui-anpr-dashboard-initial.png` and `…-plate-detected.png`; missing data key raises; missing component file raises with path; state name validation `^[a-z0-9][a-z0-9-]*$`; `--only` filters.
4. Write failing `tests/node/render_stills.test.mjs` for `parseArgs(['X','--props','{"state":"a"}','--out','o.png'])` → `{id:'X', props:{state:'a'}, out:'o.png'}` and invalid JSON props throwing `props is not valid JSON`.
5. Implement `render-stills.mjs`, `Screen.template.tsx`, scaffold copy, and the mock mode.
6. Run `bash tests/run.sh`, confirm pass.
7. Real run: in the scratch project from Phase E, write `brand.json` with real values, author `ExampleDashboardScreen.tsx` showing a table from `data.json` in two states, run `mock`, Read both PNGs; text must be legible and the state difference visible.
8. Commit: `feat(GV-2): render simulated app screens from TSX with gen_app_screen.py mock`

**Error paths:** placeholder brand; missing component; missing data; node not on PATH (`ScreenError("node not found")`); `npm install` not run (`@remotion/renderer` import fails → `ScreenError` telling the user to run `npm install` in `shots/`); render crash (stderr tail included).
**Edge cases:** one state; component that ignores `state` (not detectable — the Read step in the real run is the check); 9:16 viewport.
**Observability:** per job `mock anpr-dashboard/initial -> ref/ui-anpr-dashboard-initial.png`; render stderr tail on failure.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Real mock run produced two legible PNGs that were Read
- [ ] Manifest marks mock screens `simulated: true`
- [ ] No placeholder/TODO comments in new code

---

### Phase H: Screen Source routing and validator check C11

**Estimated time:** 15 minutes

**Files:**
- Modify: `reference/script-to-scene-bridge.md` (Scene Breakdown table + new subsection)
- Modify: `skills/video-script/SKILL.md` (Phase 3 assigns Screen Source)
- Modify: `skills/video-image/SKILL.md` (new Rule 34)
- Modify: `agents/video-prompt-reviewer.md` (check C11)
- Modify: `skills/video-package/SKILL.md` (Step 7.5 honesty check reads `simulated`)
- Test: `tests/consistency/screen-source-contract.sh`

**Contract:**
- Scene Breakdown table gains column `Screen Source` placed right after `Render Path`: header `| # | Beat | Duration | Render Path | Screen Source | VEO Mode | Extend? | Resolution | Scene Type | Dialogue? |`; example rows get `none` except row 5 (`explainer`) gets `mock`.
- New subsection `### Screen Source — where an app screen comes from (v3.1.0)` with table:

| Value | Meaning | Tool |
|---|---|---|
| `capture` | the real app is reachable by URL | `python3 tools/gen_app_screen.py capture {output_folder}` |
| `mock` | the app does not exist yet or cannot be reached | `python3 tools/gen_app_screen.py mock {output_folder}` |
| `none` | no app screen in this scene | — |

  Assignment rule: a scene whose frame shows a monitor, phone, tablet, dashboard or browser with readable product UI gets `capture` or `mock`; decide at Phase 3, before Phase 4A spends credits.
- Rule 34 in video-image: `A scene with Screen Source capture|mock never gets an NB2 prompt that draws the UI. Phase 4A lists ui-*.png as UNIQUE assets produced by gen_app_screen.py, not by NB2. Phase 4B references them inline: "...the monitor shows EXACTLY matching ui-<name>-<state>.png".`
- C11 in reviewer: `C11. Screen Source honoured — for every scene with Screen Source capture|mock, no Phase 4A prompt generates its ui-*.png, and the Phase 4B prompt references ui-<name>-<state>.png inline exactly once. FAIL otherwise.`
- video-package Step 7.5 adds: `Read screens/manifest.json. A screen with simulated: true may illustrate a flow; the title, thumbnail and description must not claim it as a shipped feature.`

**Steps:**
1. Write failing test for `tests/consistency/screen-source-contract.sh` asserting: bridge contains `Screen Source`, `capture`, `mock`, `gen_app_screen.py`; `Render Path` and `Scene Type` still present; video-script contains `Screen Source`; video-image contains `Rule 34`; reviewer contains `C11.`; video-package contains `simulated`. Expected error: `FAIL Screen Source column not defined` (exit 1).
2. Run it, confirm failure.
3. Make the edits above.
4. Run the check and `bash tests/run.sh` (existing `render-path-contract.sh` must still pass).
5. Commit: `feat(GV-2): route app screens through Screen Source at Phase 3 and validate with C11`

**Error paths:** n/a (documentation contract) — the reviewer check is the runtime error path.
**Edge cases:** explainer scene with a mock screen (allowed: screencast in Phase 4.5); live-action scene with capture screen on a monitor (Phase 4B inline ref).
**Observability:** C11 FAIL lines name scene and filename.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] `render-path-contract.sh` still passes
- [ ] No placeholder/TODO comments in new text

---

### Phase I: Screencast reference and explainer step

**Estimated time:** 15 minutes

**Files:**
- Create: `reference/post-production/18-screencast.md`
- Modify: `reference/post-production/12-remotion-explainer.md` (append `## Style presets` section)
- Modify: `skills/video-explainer/SKILL.md` (Step 4.5.2b, Step 4.5.3 uses qa-frames)
- Test: `tests/consistency/screencast-contract.sh`

**Contract — `18-screencast.md` sections (adapted from `$YE/.claude/skills/fake-screencast/SKILL.md`, read it in full first):**
1. When a screencast is right vs a single static screen (`WebBrowserFrame` alone) vs a real recording.
2. Inputs: capture/mock PNGs from `screens/manifest.json` as `pages[].img` (copy PNGs into `shots/public/screens/` and reference `screens/<file>`), or a mock TSX component as `pages[].node`.
3. API: `<Screencast pages cursor clicks box glow favicon appearAt />`, `ScreencastPage` fields verbatim from `lib/screencast.tsx`, cursor/click coordinates = viewport fractions, zoom `fx/fy` = image fractions.
4. Timing: `enterAt` and click frames from narration word times in `vo/vo-manifest.json` (`local_frame = (cue_seconds - shot_start_on_master) * fps`). Never show a page before it is spoken.
5. Motion rules: navigation = hard cut (URL path changes), in-page filter = crossfade 5 frames, scroll only with a tall capture, constant drift 0.02, ken-burns onto the payoff.
6. Mock animation: a `node` page can animate data (counter rising, row appearing) with frame-based `interpolate` only.
7. QA: `node scripts/qa-frames.mjs <Id> --out <scratch> arrive1=<f> click1=<f> nav1=<f> payoff=<f>` and Read every still.
8. Honesty: a mock screencast illustrates; it is never presented as a recording of a shipped product.
- `12-remotion-explainer.md` `## Style presets`: port the content of `$YE/.claude/skills/vidtsx-2d-generator/references/style-presets.md` (101 lines), replacing any hardcoded palette with `brand.json` token names.
- `video-explainer` Step 4.5.2b `Screencast shots`: for scenes with Screen Source `capture|mock`, build a `Screencast` shot per `18-screencast.md`. Step 4.5.3 replaces the manual `ffmpeg -ss` example with `node scripts/qa-frames.mjs` (keep ffmpeg as fallback when Node renderer packages are missing).
- CLAUDE.md Smart Context Loading row for Phase 4.5 becomes `global-promo-config §29.5, 12-remotion-explainer, 18-screencast (screen scenes only) | 3 per shot` (done in Phase R, listed here so the check can require it later).

**Steps:**
1. Write failing test for `tests/consistency/screencast-contract.sh` asserting `reference/post-production/18-screencast.md` exists and contains `ScreencastPage`, `qa-frames.mjs`, `vo-manifest.json`, `simulated`; explainer skill contains `18-screencast` and `qa-frames.mjs`; 12 reference contains `## Style presets`. Expected error: `FAIL 18-screencast.md missing` (exit 1).
2. Run, confirm failure.
3. Read `$YE/.claude/skills/fake-screencast/SKILL.md` and `$YE/.claude/skills/vidtsx-2d-generator/references/style-presets.md` in full; write the reference and section.
4. Edit the explainer skill.
5. Real run: in the scratch project, build a 6-second screencast from the two mock PNGs of Phase G with one cursor move and one click; render; run `qa-frames.mjs` at arrival, click and payoff; Read the stills.
6. Run `bash tests/run.sh`.
7. Commit: `feat(GV-2): screencast shots for app screens in Phase 4.5`

**Error paths:** image path not under `public/` (Remotion 404 — reference states the copy step); interpolate with non-monotonic range (existing template rule, repeated in reference).
**Edge cases:** single-page screencast; 9:16 box; page without cursor.
**Observability:** qa-frames prints each named frame file.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Real screencast render + three QA stills Read
- [ ] No placeholder/TODO comments in new text

---

### Phase J: `gen_music.py`

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/gen_music.py`
- Modify: `media/music/library/palette.json` (add `defaults` block)
- Modify: `reference/post-production/17-music-bed.md` (§1: tracks can be generated)
- Test: `tests/py/test_gen_music.py`

**Contract:**
- `palette.json` gains `"defaults": {"model": "music_v2", "force_instrumental": true, "target_lufs": -20.0, "ceiling_dbfs": -1.5, "output_format": "mp3_44100_128"}`. `moods` unchanged.
- `python3 tools/gen_music.py [--library media/music/library] [--only id1,id2] [--length-s N] [--force] [--dry-run] [--renorm]`.
- Library-first: a mood whose `tracks/<id>.mp3` exists is skipped unless `--force`. `--length-s` overrides every mood's `duration_s` (use the master duration).
- Request: `POST https://api.elevenlabs.io/v1/music?output_format=<fmt>`, headers `xi-api-key`, `Content-Type: application/json`, `Accept: audio/mpeg`; body `{"prompt", "music_length_ms": int(duration_s*1000), "model_id", "force_instrumental"}`; timeout 300s.
- After write: loudness-normalise with ffmpeg `ebur128` measurement and `volume` gain toward `target_lufs`, clamped so peak (`volumedetect` max_volume) never exceeds `ceiling_dbfs`.
- `catalog.json` (in the library dir): `{"tracks": [{"id", "file": "tracks/<id>.mp3", "tones", "duration_s", "requested_ms", "loudness_lufs", "peak_dbfs", "source": "elevenlabs:music", "model", "prompt", "generated_at"}]}`.
- Missing key with work to do → exit 1 with `ELEVENLABS_API_KEY not set — cannot generate <ids>. Supply licensed tracks in tracks/ instead, or set the key.`
- HTTP error → `MusicLibraryError(f"ElevenLabs HTTP {code}: {body[:400]}")`, exit 1; tracks already generated in this run stay in the catalog.
- Pure functions: `build_request(mood, defaults, length_s=None) -> (url, headers, body_bytes)` (headers without the key value in tests — pass key as argument), `plan_work(palette, library, only, force) -> (todo, skipped)`, `gain_for(lufs, peak, target, ceiling) -> float`.

**Steps:**
1. Write failing test for `plan_work` skipping a mood whose track exists and including one that does not. Expected error: `ModuleNotFoundError: No module named 'tools.gen_music'`
2. Run, confirm failure.
3. Add tests: `--force` includes existing; `--only` filters and unknown id raises `MusicLibraryError("unknown mood: x")`; `build_request` body has `music_length_ms` 60000 for `duration_s` 60 and 90000 with `length_s=90`; `gain_for(-26, -8, -20, -1.5)` = 6.0; `gain_for(-26, -3, -20, -1.5)` = 1.5 (clamped); silent track (`lufs` None) uses ceiling − peak; `--dry-run` makes no request (patch `urllib.request.urlopen` to raise if called).
4. Implement.
5. Run tests, confirm pass.
6. Real run: `python3 tools/gen_music.py --only sparse-ambient --length-s 20` from the repo root (key in `.env`); confirm `tracks/sparse-ambient.mp3` exists, duration ≈ 20s, catalog entry has loudness within 1 LU of −20. Record command and numbers in `docs/evals/gen-music-run.md`. The mp3 stays untracked (verify `git status` does not list it; add `media/music/library/tracks/` and `media/music/library/catalog.json` to `.gitignore` if absent).
7. Commit: `feat(GV-2): generate music bed tracks from the mood palette with ElevenLabs Music`

**Error paths:** missing key; HTTP 4xx/5xx; empty response body (< 1000 bytes → error); ffmpeg missing (track written, normalisation skipped with warning, catalog loudness null).
**Edge cases:** palette with zero moods; `duration_s` missing (default 60); `--renorm` with no tracks (prints `0 tracks renormalised`).
**Observability:** per mood `-> sparse-ambient (20s)` and `dur=… lufs=… peak=…`; summary counts.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Real generated track measured and recorded in `docs/evals/gen-music-run.md`
- [ ] No audio file or key appears in `git status`
- [ ] No placeholder/TODO comments in new code

---

### Phase K: `verify_render.py` and validator check P6

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/verify_render.py`
- Modify: `tools/gen_subs.py` (`transcribe_assemblyai` keeps `confidence`)
- Modify: `skills/video-validate/SKILL.md` (Check P6, `--post` line lists P1-P6)
- Modify: `skills/video-post/SKILL.md` (Pass 5 runs verify_render)
- Test: `tests/py/test_verify_render.py`, `tests/py/test_gen_subs.py`

**Contract:**
- `gen_subs.transcribe_assemblyai` word dicts become `{"text", "start_ms", "end_ms", "confidence"}` (`w.get("confidence")`). Existing callers ignore the extra key.
- `python3 tools/verify_render.py <project> [--master PATH] [--asr-json PATH]`. Master default: `output/master-mixed.mp4` if it exists else `output/master.mp4`. `--asr-json` reads a saved `{"words": [...]}` instead of calling AssemblyAI (used by tests and re-runs); a live run saves the ASR result to `work/verify-asr.json`.
- Intended text: every layer of `work/audio-plan.json` with `kind` in `narration|dialogue`, in order of scene then `at_s`. Scene start on the master = cumulative `(out_s - in_s + pad_end_s)` of `work/edit-plan.json` segments in order; the n-th segment is scene n (P2 already guarantees one segment per scene). Planned word-start of a layer = scene start + `at_s`.
- Normalisation `norm(token)`: lowercase, strip punctuation except apostrophes, split on whitespace; digits kept as-is (Indonesian numerals in scripts are written as digits, e.g. `42`).
- Alignment: `difflib.SequenceMatcher(None, intended_words, rendered_words, autojunk=False).get_opcodes()` → inserted / missing / replaced lists with master timestamps.
- Intra-layer gaps: consecutive matched rendered words from the same layer with `start_ms[n+1] - end_ms[n] >= 400`.
- Low confidence: rendered words with `confidence < 0.70`.
- Drift: for each layer, first matched rendered word start vs planned start; flag when `abs(delta) > 0.25` s.
- Report `work/verify-report.md`: header line `Extra: a · missing: b · heard differently: c · gaps: d · low-confidence: e · drift flags: f`, then sections with `mm:ss (ss.ss s) · "word"` lines.
- Exit codes: 0 when `missing == 0 and inserted == 0`; 1 otherwise (P6 FAIL); 3 when no key and no `--asr-json` (prints `ASSEMBLYAI_API_KEY not set — P6 skipped, not passed`).
- P6 text in video-validate: `### Check P6: The Render Says What The Script Says (v3.1.0)` — run `python3 tools/verify_render.py {output_folder}`; FAIL on any missing or inserted word; WARN on replaced, gaps, low confidence, drift; exit 3 is reported as `SKIPPED`, never PASS. Advisory: the report says where to listen.

**Steps:**
1. Write failing test for audio-plan with one narration layer `"Tiap truk antre 42 menit di gerbang."`, edit-plan with one segment, ASR words identical → report counts all zero and exit 0. Expected error: `ModuleNotFoundError: No module named 'tools.verify_render'`
2. Run, confirm failure.
3. Add tests: extra ASR word `eh` → inserted 1, exit 1; dropped `menit` → missing 1; `gerbang` heard `gerbong` → replaced 1, exit 0; gap 0.6s inside layer flagged; gap between two layers not flagged; confidence 0.5 flagged; second scene's layer planned start uses cumulative segment length incl. `pad_end_s`; drift 0.4s flagged, 0.1s not; punctuation/case differences not counted; missing audio-plan → `VerifyError` naming file; no key and no `--asr-json` → exit 3.
4. Add `gen_subs` test that a mocked AssemblyAI payload with `confidence` keeps it.
5. Implement both.
6. Edit video-validate (P6 + `(P1-P6)`) and video-post Pass 5 (run after the A/V gate).
7. Real run: on a scratch project, generate a VO with `node tools/gen_vo.mjs` for one short Indonesian line (or reuse any existing `vo/*.mp3` from a real project with its audio-plan), assemble a master with `tools/edit_render.py`, run `verify_render.py` live; record command, counts and any finding in `docs/evals/verify-render-run.md`.
8. Run `bash tests/run.sh`.
9. Commit: `feat(GV-2): verify the rendered narration against the script with a second ASR pass (P6)`

**Error paths:** missing plan files; master missing; ffmpeg extract failure; AssemblyAI error (`SubtitleError` surfaced, exit 1 with message); ASR returns zero words (all intended missing, exit 1).
**Edge cases:** no narration/dialogue layers (report `nothing to verify`, exit 0); fewer edit segments than scenes (drift check skipped with a note, word diff still runs); repeated words.
**Observability:** printed header counts; report file path; saved `work/verify-asr.json` for re-runs without re-billing.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Real live run recorded in `docs/evals/verify-render-run.md`
- [ ] Exit 3 path never reported as PASS in skill text
- [ ] No placeholder/TODO comments in new code

---

### Phase L: `clean_voice.py`

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/clean_voice.py`
- Create: `tools/models/rnnoise/sh.rnnn`, `cb.rnnn`, `bd.rnnn` (copied from `$YE/tools/models/rnnoise/`)
- Modify: `reference/post-production/10-post-production-pipeline.md` §3.2 (`clean` field)
- Modify: `reference/post-production/11-voice-cast-and-vo.md` (when to clean)
- Modify: `skills/video-post/SKILL.md` §1.3 (clean before Voice Changer)
- Test: `tests/py/test_clean_voice.py`

**Contract:**
- `audio-plan.json` scene gains optional `"clean": "none" | "isolate" | "rnnoise"` (default `none`), set after listening to the clip. Documented in §3.2 bullet list.
- `python3 tools/clean_voice.py <in.mp4|in.wav> -o <out> [--method isolate|rnnoise] [--model sh|cb|bd] [--no-preserve-level]`. Refuses when `out` resolves to the same path as `in` (`CleanError("refusing to overwrite the source")`).
- Steps: extract mono 44.1 kHz PCM; `isolate` → `POST https://api.elevenlabs.io/v1/audio-isolation` multipart field `audio` (build multipart body with stdlib; header `xi-api-key`), response bytes must be ≥ 1000 else error; `rnnoise` → ffmpeg `-af highpass=f=90,arnndn=m=<relative model path>` run with `cwd` = plugin root (colon-free relative path, reason documented in a comment); level match: gain = source RMS − cleaned RMS (ffmpeg `astats` `RMS level dB`), capped so cleaned peak + gain ≤ −1.0 dBFS; remux: video stream copied, cleaned audio `volume=<gain>dB,apad`, `-shortest`, AAC 192k.
- Duration gate: `abs(duration(out) - duration(in)) > 0.05` → delete `out`, raise `CleanError(f"duration changed by {d:+.3f}s; lip-sync would drift")`.
- Pure functions: `level_gain(src_rms, clean_rms, clean_peak, ceiling=-1.0) -> float`, `model_path(model) -> Path` (raises on unknown model), `multipart_body(field, filename, data, boundary) -> bytes`.

**Steps:**
1. Write failing test for `level_gain(-20, -26, -4, -1.0)` returning 3.0 (clamped from 6.0). Expected error: `ModuleNotFoundError: No module named 'tools.clean_voice'`
2. Run, confirm failure.
3. Add tests: unclamped gain case; `model_path("xx")` raises; `multipart_body` contains `name="audio"` and the bytes; same in/out path refused; ffmpeg rnnoise run on a 2s `make_clip` fixture keeps duration within 0.05s and video stream copied (codec unchanged); duration-gate raise when a patched `duration_of` returns +0.2s (out file removed).
4. Copy the three models; implement.
5. Run tests, confirm pass.
6. Real run: `--method rnnoise` and `--method isolate` on one real platform clip with background noise (ask the user for a clip path if no project clip is available — do not synthesise one for the real run); record commands, RMS before/after, duration delta, and a listening note in `docs/evals/clean-voice-run.md`.
7. Edit docs/skill.
8. Commit: `feat(GV-2): clean platform-native dialogue before voice conversion (isolate or RNNoise)`

**Error paths:** missing key for isolate; HTTP error; tiny response; missing model; ffmpeg failure; duration drift.
**Edge cases:** input without audio stream (`CleanError("no audio stream")`); wav input (no remux, write wav); very short clip < 1s.
**Observability:** prints method, source RMS, cleaned RMS/peak, applied gain, duration delta.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Real runs for both methods recorded in `docs/evals/clean-voice-run.md`
- [ ] Source file never modified (mtime unchanged in test)
- [ ] No placeholder/TODO comments in new code

---

### Phase M: `composite.py split`

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/composite.py`
- Modify: `reference/post-production/13-ffmpeg-edit.md` (split mode)
- Test: `tests/py/test_composite.py`

**Contract:**
- `split(master, shot, at_s, out_s, box, out, crop_cx=0.5, crop_cy=0.5, zoom=1.0)`; `box` = `(x, y, w, h)` in the master's pixel space.
- Validation: `validate_span`; `require_alpha(shot)`; box inside the master frame and `w, h > 0`, else `CompositeError("box <x,y,w,h> outside <W>x<H>")`; `0 <= crop_cx, crop_cy <= 1`; `zoom >= 1`.
- Even-dimension box: `w -= w % 2; h -= h % 2`.
- Filter for the span (outside the span the master passes through untouched):
  ```
  [0:v]split[base][pipsrc];
  [pipsrc]crop=w='min(iw,ih*A)/Z':h='min(ih,iw/A)/Z':x='clip(CX*iw-ow/2,0,iw-ow)':y='clip(CY*ih-oh/2,0,ih-oh)',scale=W_BOX:H_BOX[pip];
  color=c=black:s=WxH:r=FPS[bg];
  [bg][pip]overlay=X:Y:shortest=1[boxed];
  [1:v]setpts=PTS-STARTPTS+AT/TB,scale=W:H[ov];
  [boxed][ov]overlay=0:0:format=auto[splitv];
  [base][splitv]overlay=0:0:enable='between(t,AT,OUT)'[v]
  ```
  with `A = w/h` of the box, master audio mapped `0:a?` and copied.
- CLI: `composite.py split <master> <shot> --at --out-s --box x,y,w,h [--crop-cx --crop-cy --zoom] -o out`.

**Steps:**
1. Write failing test for `split` on a 4s master and a 1.5s alpha shot (make an alpha `.mov` with ffmpeg `-f lavfi -i color=c=black@0.0:s=320x240,format=yuva420p -c:v qtrle`) produces a 4.0±0.2s video with audio. Expected error: `AttributeError: module 'tools.composite' has no attribute 'split'`
2. Run, confirm failure.
3. Add tests: box outside frame raises; odd box width becomes even (inspect built filter string via a pure `split_filter(...)` function); zoom < 1 raises; crop centre out of range raises; opaque shot raises alpha error.
4. Implement `split_filter` and `split`; add CLI mode.
5. Run tests; run `bash tests/run.sh`.
6. Update reference 13 with a `split` subsection (when to use PiP, box and crop parameters).
7. Commit: `feat(GV-2): picture-in-picture split mode in composite.py`

**Error paths:** listed validations; ffmpeg failure surfaced by `_run`.
**Edge cases:** box equal to full frame; span at t=0; shot shorter than span (last frame holds via overlay `eof_action` default repeat — assert duration only).
**Observability:** CLI prints `wrote <out>`; errors name the offending value.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Existing cutaway/overlay tests still pass
- [ ] No placeholder/TODO comments in new code

---

### Phase N: `composite.py insert`

**Estimated time:** 15 minutes

**Files:**
- Modify: `tools/composite.py`
- Modify: `reference/post-production/13-ffmpeg-edit.md` (insert mode)
- Test: `tests/py/test_composite.py`

**Contract:**
- `insert(master, shot, at_s, out, gain_db=0.0)`: output = master[0..at] + shot (video and its own audio) + master[at..end]. Total duration = master + shot.
- Validation: `0 <= at_s <= master_duration`; shot must have a video stream; a shot without audio gets silence of its length (`anullsrc`).
- Method (frame-accurate, from `$YE/tools/bake.py`): render three video segments with identical encoding (`scale=W:H,fps=FPS,format=yuv420p`, libx264 crf 18), exact frame counts `round(at*FPS)`, `round(shot_dur*FPS)`, `round(end*FPS) - round(at*FPS)`; concat; audio `[m]atrim=0:at` + shot audio (`volume=<gain>dB,alimiter=limit=0.97:level=false` when gain > 0) + `[m]atrim=at:end`, each `aresample=48000,aformat=fltp:stereo`, `concat=n=3:v=0:a=1`; mux with `-t` total.
- Skip empty segments when `at_s == 0` or `at_s == master_duration`.
- A/V gate on the result: `abs(v - a) <= 0.04` else `CompositeError`.
- CLI: `composite.py insert <master> <shot> --at [--gain-db] -o out`.

**Steps:**
1. Write failing test for `insert` of a 1.0s clip at 2.0s into a 4.0s master → video 5.0±0.1s, audio 5.0±0.1s. Expected error: `AttributeError: module 'tools.composite' has no attribute 'insert'`
2. Run, confirm failure.
3. Add tests: at 0.0 (two segments); at end (two segments); at beyond master raises; silent shot gets silence and passes the A/V gate; positive gain builds a limiter in the filter (pure `insert_audio_filter`).
4. Implement.
5. Run tests; run `bash tests/run.sh`.
6. Update reference 13 with an `insert` subsection (the master clock pauses; every later cue time shifts by the shot length — say that SFX/music/subtitle plans after an insert must use output time).
7. Commit: `feat(GV-2): insert mode in composite.py pauses the master for a full shot`

**Error paths:** span out of range; shot without video; A/V gate failure; ffmpeg failure.
**Edge cases:** insert at 0 and at end; shot with different fps/size (normalised by the filter).
**Observability:** prints the three segment frame counts and total duration.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] A/V gate enforced on insert output
- [ ] No placeholder/TODO comments in new code

---

### Phase O: `make_stems.py`

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/make_stems.py`
- Modify: `skills/video-post/SKILL.md` (optional step after Pass 5)
- Test: `tests/py/test_make_stems.py`

**Contract:**
- `python3 tools/make_stems.py <project> [--voice] [--sfx] [--music] [--all]`. Output `output/stems/voice.wav`, `sfx.wav`, `music.wav`; 48 kHz stereo `pcm_s24le`; every stem starts at 0.000 and has exactly the duration of `output/master.mp4` (`-t`).
- `voice`: audio stream of `output/master.mp4` (the assembled master before SFX/music), `aformat=sample_rates=48000:channel_layouts=stereo`.
- `sfx`: events from `work/sfx-plan.json`; clip file per event = catalog entry `file` resolved against the catalog's directory (`Path(plan["catalog"]).parent`); each input `aformat=…,adelay=<ms>:all=1,volume=<gain_db>dB`; mixed onto `anullsrc` with `amix=inputs=N:normalize=0:dropout_transition=0`; batches of 30 inputs summed in a second pass; graphs written to a temp file and passed with `-filter_complex_script`. Events with `at_s >= duration` are skipped and counted. Missing catalog ids → `StemError("missing clips: …")`.
- `music`: segments from `work/music-plan.json`; each `track` resolved against the project (absolute paths kept); per segment `atrim=0:<to-from>`, `afade=t=in:d=<fade_in_s>`, `afade=t=out:st=<len-fade_out_s>:d=<fade_out_s>`, `volume=<gain_db>dB`, `adelay=<from_ms>:all=1`; `amix` normalize=0; `alimiter=limit=0.97:level=disabled`. No ducking. A missing track file → skip that segment with a warning (fail-soft like `mix_music.py`); zero usable segments → no music stem, exit 0 with warning.
- Pure functions: `sfx_batches(events, duration, batch=30)`, `music_filter(segments, duration)`.

**Steps:**
1. Write failing test for `sfx_batches` on 65 events with one at `at_s` beyond duration returns batches of 30, 30, 4 and a skipped count of 1. Expected error: `ModuleNotFoundError: No module named 'tools.make_stems'`
2. Run, confirm failure.
3. Add tests: `music_filter` contains the fade and delay values for a 2-segment plan; real ffmpeg run (fixtures: 4s master via `make_clip`, a 0.5s sine as SFX clip in a temp catalog, a 3s sine as music track) → three stems each 4.0±0.02s, 48000 Hz, 2 channels; missing catalog id raises; missing music track skipped with warning.
4. Implement.
5. Run tests; `bash tests/run.sh`.
6. Add the optional stems step to video-post (`python3 tools/make_stems.py {output_folder} --all` — hand-off for a human editor or single-layer revision).
7. Commit: `feat(GV-2): full-length voice, SFX and music stems for editors`

**Error paths:** missing master; missing plans (the requested stem only fails, others still build); missing catalog ids; ffmpeg failure.
**Edge cases:** zero SFX events (silent stem of full length); music segment past the end (trimmed); no flags given (print usage, exit 2).
**Observability:** per stem `sfx stem: N cues -> output/stems/sfx.wav (4.000s)`; final table of durations and sample counts.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Stem durations equal the master within 0.02s in tests
- [ ] No placeholder/TODO comments in new code

---

### Phase P: `composite_logo.py` and `thumb_scrim.py`

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/composite_logo.py`, `tools/thumb_scrim.py`
- Modify: `reference/post-production/15-packaging.md` (post-process section)
- Modify: `skills/video-package/SKILL.md` (Step 7.7 after render hand-off)
- Test: `tests/py/test_thumb_tools.py`

**Contract:**
- Both import Pillow through `_venv.require("PIL")` (exit 2 message when missing).
- `composite_logo.py --base <png> --logo <png> --out <png> [--clear-box L,T,R,B] [--feather 34] [--bg R,G,B] [--center X,Y] [--size N] [--glow R,G,B | --no-glow] [--jpg]`. Port `$YE/tools/composite_logo.py` minus `--tile/--tile-color/--mark-color/--tile-radius/--mark-scale` and minus the Claude-colour defaults: `--glow` has no default (no glow unless given); the logo is pasted with its own colours (RGBA alpha, or white keyed out for flat logos) instead of a recoloured `--core`. `--clear-box` must lie inside the image.
- `thumb_scrim.py --in <png> --out <png> [--strength 0.55] [--fade-y N] [--x-hold N] [--x-fade N] [--hue H | --protect none] [--target-contrast 4.0 --text-box L,T,R,B] [--jpg]`. Port `$YE/tools/thumb_scrim.py`. NEW `--target-contrast` with `--text-box`: compute WCAG contrast between the median headline-fill colour (saturated pixels near `--hue`) and the median ground inside the box; increase `strength` in 0.05 steps up to 0.95 until contrast ≥ target; print the reached contrast; exit 1 if the target is not reachable.
- `--jpg` writes a 1280×720-or-larger JPEG quality 95, and if > 2 MB re-saves at quality 85 (YouTube limit).
- Pure functions: `wcag_contrast(rgb1, rgb2) -> float`, `parse_box(s, w, h) -> tuple`.

**Steps:**
1. Write failing test for `wcag_contrast((255,255,255),(0,0,0))` ≈ 21.0. Expected error: `ModuleNotFoundError: No module named 'tools.thumb_scrim'`
2. Run, confirm failure (runs under the venv interpreter when stdlib python lacks Pillow: tests skip with `unittest.skipUnless` when `PIL` is not importable, and the verification step runs them with `~/.gaspol-video/venv/bin/python -m unittest tests.py.test_thumb_tools`).
3. Add tests: `parse_box` rejects out-of-image boxes; scrim on a synthetic 640×360 image with green text on grey reaches contrast ≥ 4.0; `composite_logo` places an RGBA logo at the centre (pixel check) and clear-box paints the region with `--bg`; JPEG ≤ 2 MB.
4. Implement both.
5. Run under the venv interpreter; run `bash tests/run.sh`.
6. Edit reference 15 and video-package Step 7.7: after the image plugin returns thumbnails, optionally run these tools; they render nothing new.
7. Commit: `feat(GV-2): deterministic thumbnail post-process — real logo paste and headline scrim`

**Error paths:** Pillow missing (exit 2); unreadable image; box outside image; unreachable contrast.
**Edge cases:** logo with no alpha on non-white background (documented limitation, warn when keyed alpha covers > 90% of the logo box); `--protect none`.
**Observability:** prints output paths, applied strength, reached contrast.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] `~/.gaspol-video/venv/bin/python -m unittest tests.py.test_thumb_tools` passes (no skips)
- [ ] No Claude brand colour constants in the ported code
- [ ] No placeholder/TODO comments in new code

---

### Phase Q: `yt_stats.py`

**Estimated time:** 15 minutes

**Files:**
- Create: `tools/yt_stats.py`
- Modify: `reference/post-production/15-packaging.md` §3 (calibration data source)
- Modify: `skills/video-package/SKILL.md` Step 7.1
- Modify: `.gitignore` (nothing under repo; token lives in home — assert no `.youtube/` needed)
- Test: `tests/py/test_yt_stats.py`

**Contract:**
- Paths: `YT_DIR = ${GASPOL_VIDEO_HOME:-~/.gaspol-video}/youtube`; `client_secret.json` and `token-analytics.json` there. Scopes: `https://www.googleapis.com/auth/youtube.readonly`, `https://www.googleapis.com/auth/yt-analytics.readonly`. Metrics: `views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,subscribersGained` (never `impressionClickThroughRate` — it returns 400).
- `python3 tools/yt_stats.py auth` → OAuth installed-app flow, saves token, prints its path.
- `python3 tools/yt_stats.py fetch <video_id> <project> [--json]` → appends or replaces (by `videoId`) an entry in `<project>/packaging/calibration.json`: `{"videos": [{"videoId","title","publishedAt","durationMin","views","likes","comments","avgViewPct","avgViewDurationS","watchTimeH","subsGained","ctr": null,"ctr_source": "manual — YouTube Studio only","fetched_at"}]}`.
- Missing client secret → exit 1 with setup steps: create a Google Cloud project, enable YouTube Data API v3 and YouTube Analytics API, create an OAuth Desktop client, download JSON to `<YT_DIR>/client_secret.json`.
- Analytics HttpError → public stats only, warning printed, exit 0.
- Pure functions (stdlib-testable, no Google import at module top): `iso8601_to_minutes`, `merge_calibration(existing, entry)`, `analytics_row_to_fields(column_headers, row)`.

**Steps:**
1. Write failing test for `iso8601_to_minutes("PT5M30S") == 5.5` and `("PT1H2M") == 62.0` and invalid → None. Expected error: `ModuleNotFoundError: No module named 'tools.yt_stats'`
2. Run, confirm failure.
3. Add tests: `merge_calibration` replaces same videoId and keeps others; `analytics_row_to_fields` rounds avgViewPct to 1 decimal and watch time hours; missing client secret message lists the four setup steps (call the check function with a temp `GASPOL_VIDEO_HOME`).
4. Implement with lazy Google imports via `_venv.require`.
5. Run tests; `bash tests/run.sh`.
6. Real run gate: **STOP and ask the user** whether they have or want to create the OAuth client now. If yes, run `auth` then `fetch` on one of their published videos and record the output (no token contents) in `docs/evals/yt-stats-run.md`. If not, record in the ledger `## Utang terbuka`: `yt_stats real run pending — no OAuth client`, and do not fake a run.
7. Edit reference 15 and video-package Step 7.1.
8. Commit: `feat(GV-2): pull YouTube stats into packaging calibration data`

**Error paths:** missing client secret; token expired without refresh token (re-auth); video not found; analytics forbidden (non-owner).
**Edge cases:** statistics hidden (likes None); calibration file missing (created); malformed calibration JSON (`StatsError` naming the file).
**Observability:** prints each field; notes CTR is Studio-only.
**Security:** OAuth token and client secret stay under the home directory, never in the repo; read-only scopes only.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] Real run recorded OR open debt recorded in the ledger (no fabricated output)
- [ ] Security: read-only scopes; no secret or token path inside the repo
- [ ] No placeholder/TODO comments in new code

---

### Phase R: Docs sync and version 3.1.0

**Estimated time:** 15 minutes

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `NOTICE`, `.env.example`, `.claude-plugin/plugin.json`, `agents/video-engine-agent.md`, `skills/video-full/SKILL.md`, `reference/global-promo-config.md` (§29.7 Screens, §29.8 Verify)
- Modify: `tests/consistency/reference-index.sh` if it enumerates references (add `18-screencast.md`)
- Test: `tests/consistency/tools-index.sh` (new)

**Contract:**
- `tests/consistency/tools-index.sh`: every `tools/*.py` (except `__init__.py`, `_venv.py`) and `tools/*.mjs` filename appears in CLAUDE.md; every `reference/post-production/*.md` appears in CLAUDE.md; `plugin.json` version is `3.1.0`; NOTICE mentions `capture_web`, `screencast`, `verify_cut`, `make_stems`, `gen_music`, `clean_voice`, `composite_logo`, `thumb_scrim`, `yt_stats`, `bake.py`.
- CLAUDE.md: Architecture rows for each new tool, `templates/remotion/lib`, `tools/models/rnnoise`, `requirements.txt`, `tools/setup.sh`; tool count updated (count the files); Post-Production reference table row for `18-screencast.md`; Smart Context Loading Phase 4.5 row `global-promo-config §29.5, 12-remotion-explainer, 18-screencast (screen scenes only) | 3 per shot`; Debugging rows:
  - `(v3.1.0) Tool exits 2 with "missing <module>: run tools/setup.sh"` → run `bash tools/setup.sh`.
  - `(v3.1.0) Render offer skips a scene with "prompt-only"` → Seedance/Kling/extend are not rendered by the pipeline; render in the platform UI.
  - `(v3.1.0) VEO render fails "Audio generation failed"` → negated audio list; describe ambience positively.
  - `(v3.1.0) Veo draws REC text` → remove `security camera`; use `fixed overhead view`.
  - `(v3.1.0) gen_app_screen mock refuses: brand.json placeholders` → write brand.json from strategic-brief.md.
  - `(v3.1.0) NB2 draws a garbled dashboard` → scene needs Screen Source capture/mock; screen PNG comes from gen_app_screen.py.
  - `(v3.1.0) P6 reports missing words` → listen at the timestamps in work/verify-report.md; fix the edit or regenerate VO.
  - `(v3.1.0) clean_voice refuses with duration changed` → do not stretch; try the other method or skip cleaning.
  - v3.1.0 changelog block summarising phases A–Q and the explicit exclusions (fal, gen_avatar, GROK/Seedance/Kling rendering, clean-cut family, brand-setup, yt_upload, notion_sync, vscode.tsx, gen_thumbnail).
  - Version footer `3.1.0`, Last Updated `2026-09-13` (or execution date).
- `.env.example`: comments that `ELEVENLABS_API_KEY` now also serves `gen_music.py` and `clean_voice.py --method isolate`, and `ASSEMBLYAI_API_KEY` serves `verify_render.py`; a line stating YouTube uses OAuth files in `~/.gaspol-video/youtube/`, not an env var.
- NOTICE: add adapted items under `claude-youtube-editor`: capture_web step runner (minus `eval` and VS Code serve-web), screencast/browser/kit components, gen-registry/render-all/qa-frames scripts, verify_cut method (second ASR pass diff, interior gaps, confidence, drift), make_stems stem method, gen_music library-first loudness method, clean_voice isolate/RNNoise and RMS level match, bake.py split/insert filter method, composite_logo, thumb_scrim, yt_stats. Update "Not adopted" list with gen_video.py, gen_avatar.mjs.
- `global-promo-config.md` §29.7 Screens: `screen_source` enum `capture | mock | none`, screens folder, manifest `simulated` flag. §29.8 Verify: `verify_gap_s 0.40`, `verify_low_confidence 0.70`, `verify_drift_s 0.25`, P6 exit codes 0/1/3.
- `video-full` orchestrator: mention render offers in Phase 4/5, Screen Source at Phase 3, P6 after Phase 6.
- `video-engine-agent.md`: capabilities list adds screens, render offers, verify.

**Steps:**
1. Write failing test for `tests/consistency/tools-index.sh` per contract. Expected error: `FAIL tools/gen_music.py not listed in CLAUDE.md` (exit 1).
2. Run, confirm failure.
3. Make every doc edit above.
4. Run `bash tests/run.sh` and `~/.gaspol-video/venv/bin/python -m unittest tests.py.test_thumb_tools`.
5. `grep -rn "TODO\|FIXME\|placeholder" tools templates/remotion/lib templates/remotion/scripts` returns only intentional uses (the brand placeholder guard wording); review each hit.
6. `git status` shows no `.env`, audio, video, image, token or `node_modules` files staged.
7. Commit: `docs(GV-2): sync CLAUDE.md, NOTICE and config for 3.1.0`

**Error paths:** n/a (documentation) — the consistency check is the guard.
**Edge cases:** tool count text elsewhere in README; `plugin.json` description mentions render offers.
**Observability:** consistency script prints each missing item.

**Verification:**
- [ ] `bash tests/run.sh` prints `RESULT       PASS`
- [ ] `tools-index.sh` passes
- [ ] `plugin.json` version `3.1.0`
- [ ] `git status` clean of media, secrets and tokens
- [ ] No placeholder/TODO comments in new code

---

## Out of scope

- Implementing `from-file` / `from-manifest` in `geminigen-api-client` (other repo).
- Rendering Seedance, Kling, GROK clips, or VEO Scene Extensions.
- `gen_video.py` (fal), `gen_avatar.mjs`, clean-cut tools, `brand-setup`, `yt_upload.py`, `notion_sync.py`, `lib/vscode.tsx`, `gen_thumbnail.py`.
- Changing `voice_changer.mjs` (its claim stands for the platforms this plugin renders).
