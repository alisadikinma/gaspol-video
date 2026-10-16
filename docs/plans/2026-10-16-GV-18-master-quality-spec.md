# GV-18 — Master quality: music & SFX, colour, credit control, thumbnails, reliable render

**Ticket:** GV-18
**Status:** design, awaiting spec review
**Sister ticket:** GV-19 (viral style + framework). Split reason: different subsystem and GV-19 needs an audio study first.

## Why

Review of `claude-youtube-editor` and `MoneyPrinterTurbo` (NOTICE already lists what was adopted), a NotebookLM expert pass (notebook `GV-VIDEO 2026-10`), and the owner's own complaint: **music does not follow the topic, SFX lack punch.** Candidates already adopted are not repeated. Rejected on purpose: zoompan Ken-Burns (integer-pixel stutter; `plan_motion.py` covers it), multi-provider TTS, stock round-robin, semantic rerank, avatar path (NOTICE), ControlNet (no model access, render is MCP-only).

## Root cause of the owner's complaint (read from the repo)

- `media/music/library/palette.json` has 5 moods, picked from **tone only** (`17-music-bed.md` tone→mood table). Topic, domain, location and scene arc are not inputs. Every prompt is generic ("no melody", "very quiet") and 60 s flat.
- `media/sfx/library/palette.json` has 12 recipes. `14-sfx-design.md` caps at 8–12 cues/min, marks the rest `optional`, and calibrates gain to stay out of the narration. No layered impact, no beat-synced cue.

## Phases (one plan phase each, ordered by owner pain)

| # | Phase | What changes | Done when |
|---|---|---|---|
| 1 | Music & SFX | Music prompt built from topic + domain + tone + scene arc (calm intro, rising body, peak, CTA resolve), generated per segment. SFX library grows with layered impacts (sub boom + hit + tail) and cues snapped to music beats. Existing audit gate stays. | Same script rendered with two different topics yields two audibly different beds; a layered impact (`stack`) is available for the biggest moments (the doc says use it on two or three, not every cue); audit gate passes; loudness gates unchanged |
| 2 | Colour | BT.709 tags at final encode (`vidkit` mixdown/normalize). Cross-clip colour match pass before concat. | `ffprobe` shows bt709 on master; contact sheet of adjacent clips shows no temperature jump |
| 3 | Credit control | Stills-first verdict gate (page with PASS/MAYBE/NO) before any clip render. Per-project cost log of units (no prices, no estimate; see Owner decisions). | No clip render starts before stills verdict; `cost_log.py report` shows units, failed share and re-rolls per scene |
| 4 | Thumbnails | Style-element menu with slots + failure table. Render-verify loop (reject wrong text, unrecognisable face, no dominant element). | A rejected render is re-rolled automatically; menu referenced from `video-package` |
| 5 | Reliable render | Per-stage fingerprint cache inside the edit render (an unchanged segment is not re-encoded). The music mix is a separate pass and never re-runs the edit render. Encoder probe with libx264 fallback. Heartbeat log on silent ffmpeg stages. Per-platform loudness profile. | Changing only the music re-renders only the export stage; platform loudness values are sourced (see open item) |
| 6 | Wrap | Docs, `tool-routing.md` rows, NOTICE entries, tests, version bump (README + changelog + marketplace) | `bash tests/run.sh` green |

## Constraints

- Library first: reusable helpers live in `tools/vidkit/`; CLI entry points that consume project files (`music_brief`, `sfx_snap`, `verdict_page`, `cost_log`, `thumb_verify`) are top-level `tools/*.py`. Every tool has tests and a `tool-routing.md` row (CLAUDE.md tool-first rule).
- Generated audio stays out of the repo (existing rule); recipes only.
- Music generation bills ElevenLabs: always confirm the mood/length before a billed run (existing rule in `17-music-bed.md`).
- Reference clients' names and assets never enter repo docs.

## Open items (must be resolved in the plan, not guessed)

1. Per-platform loudness targets. The expert pass claimed TikTok/Reels want -11 to -13 LUFS; no source was given. The GV-19 study measured 12 Shorts from one channel at -24.1 to -7.8 LUFS (11 of 12 between -13.6 and -7.8, median -11.8 over all 12); see docs/evals/short-form-loudness-measurement.md. A data point from one channel, not a rule. Decide the numbers from a real source before phase 5.
2. How topic/domain reaches the music prompt: reuse `strategic-brief.md` Domain Knowledge, or ask once at Phase 1 brainstorm.
3. Cost estimate needs real per-clip prices; read them from the render MCP responses, do not hardcode.

## Out of scope

GV-19 items (sticker icons, step counter, retention gate, script framework). Avatar and cheap-model video paths. Anything needing model access beyond the render MCPs.

## Owner decisions and scope cuts (2026-10-16, during execution)

- **Phase F listening test skipped.** No billed generation and no listening evidence file. The owner tests music and SFX on a real video. The 8 new SFX recipes exist as recipes only.
- **Cost log reduced to units.** No estimate, budget, `check`, or `media/pricing.json`: without real prices an estimate is meaningless. `cost_log.py add/report` records units, failed share and re-rolls per scene.
- **Loudness.** Only the `default` profile ships. A `short-vertical` profile needs a sourced number. Evidence from one channel is in `docs/evals/short-form-loudness-measurement.md` (12 clips, -24.1 to -7.8 LUFS; a data point, not a rule).
- **Encoder.** Hardware encoder is opt-in (`GASPOL_VIDEO_ENCODER`); measured slower and larger on the owner's Mac for a synthetic test, so the default stays `libx264`.
- **ElevenLabs Music length.** Verified against the ElevenLabs docs: `music_length_ms` must be 3,000 to 600,000. The plugin clamps segments to 10 to 120 s, inside that range.
- **Marketplace.** Not bumped during execution: `gaspol-one` points at the GitHub repo, and the version is bumped when the release is pushed.
