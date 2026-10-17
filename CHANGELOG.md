# Changelog

Every release of gaspol-video, newest first. The README carries the product overview; this file carries the history.

> **v3.16.0 — viral style and framework.** Overlay sticker icons, step counter, red vignette, falling burst and a
> `viral` caption preset; a retention report on a finished cut (`tools/retention_gate.py`, `video-validate --retention`);
> a 7-stage viral checklist every short-form script must carry (`tools/viral_checklist.py`). Course figures are tagged
> `source: course`; the reports never block. See [v3.16.0 Changelog](#v3160-changelog).

> **v3.11.0 — keywords that move, and pictures behind the speaker.**
> Only the important keywords are highlighted — not subtitles: `tools/overlay_plan.py` refuses text
> on screen for more than half a scene's speech. Each keyword animates in (blur-to-sharp, glitch
> slices, count-up, handwrite) and out, timed from the voice's words. Image and video panels, a
> sliding carousel and round photo bubbles sit BEHIND the speaker's head through a per-frame person
> mask (`tools/person_mask.py`), rendered by the Remotion composition `KineticOverlay`.
> See [v3.11.0 Changelog](#v3110-changelog).

> **v3.6.0 — pauses you can write, dissolves at act changes, a look at every clip, and a bed composed to the picture.**
> `[pause: 1.2s]` in narration renders as sample-exact silence (`tools/gen_vo.mjs`) and is stripped
> from captions and the P6 check. `transition_in` on an edit-plan segment dissolves over source
> handles without moving the timeline. `tools/qa_frames.py` writes contact sheets and a verdict
> sheet that Claude judges before the edit (V15). `tools/gen_music.py video` composes the music bed
> to the finished master, and falls back to the palette (exit 3) when the request fails.

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

## v3.19.0 Changelog

- **File cleanup (GV-21).** `python3 tools/renders.py <project> archive --file F [--reason R]` moves an existing paid file to `_arsip/<kind>-<stem>-v<N>-<reason><ext>` before a re-render; the `video-image` and `video-gen` render offers call it after a `check` that printed `render`. `python3 -m tools.vidkit tidy <project>` reports unknown folders, subfolders inside flat folders, duplicates, stale ledger entries and old `.tmp/` files and changes nothing; `--apply` moves strays into `_arsip/folder-...` (a `folder-*` entry already in `_arsip/` is never reported or moved again); `--empty-tmp` is the only deletion and never touches `_arsip/` or `shots/out/`. It deletes a `.tmp/image` or `.tmp/video` MCP copy only when the same bytes already sit in a home folder (prints `deleted <tmp> (copy of <home>)`); an unmoved paid render, or an unreadable media file there, is kept unless `--include-mcp`. The folder contract in the four skills and the pipeline doc now lists twelve folders (adds `sfx/`, `screens/`, `packaging/`) and the subfolder rule; pipeline doc gains section 2.4. Registry totals: 63 tool entries, 63 routes. Tests: `tests/py/test_renders.py`, `tests/py/test_vidkit.py`, `tests/consistency/tidy-contract.sh`.

## v3.18.0 Changelog

- **Tool registry (GV-20).** `tools/registry.json` holds every tool and every task-to-tool route; the table in `docs/tool-routing.md` is generated from it (`python3 tools/registry_build.py render`). Gates fail on an unregistered tool, an unexplained duplicate, or a new direct `ffprobe` caller. A write-time hook (`hooks/tool-reminder.sh`) reminds you of the existing tool when a script outside `tools/` touches ffmpeg, ffprobe or Remotion; it never blocks. `check_vo_duration.py` and `track_screen.py` moved to `vidkit.ff`. Not done: 17 other ffprobe callers stay on an allowlist with written reasons; duplicate detection is exact (phase + task set) only.

## v3.17.0 Changelog

- **Cleanup.** Removed the Antigravity manifest (`plugin.json`, `rules/AGENTS.md`), the superseded `tools/keyword_cards.py`, the unused `docs/seedance_2_new_rag/`, and the Windows-only `scripts/bootstrap-kling-notebooklm.ps1`.

- **Master quality (GV-18).** Music prompts follow the topic and arc (`tools/music_brief.py`); SFX cues can be layered (`stack`), with eight new recipes and beat snapping (`tools/sfx_snap.py`); final encodes are BT.709 tagged and clips can be colour matched; a stills-first verdict page (`tools/verdict_page.py`) gates clip spend; `tools/cost_log.py` logs billed units only; thumbnail style menu and `tools/thumb_verify.py`; per-stage cache, encoder probe (opt-in, `libx264` stays default) and ffmpeg heartbeat in the edit render; sourced loudness profiles (only `default` ships). Not done: billed listening test, real-clip colour check, short-vertical profile.

## v3.16.0 Changelog

- **Viral style and framework (GV-19).** `vidkit audiostudy` and a 12-clip study (onsets follow speech, so music tempo and SFX timing are `not measured`); `KineticOverlay` icons `warning money check cross clock lock`, `steps`, `vignette`, `burst`, `center` anchor, `viral` preset; `tools/retention_gate.py` + doc 20 + `video-validate --retention`; `F12_Viral_Framework.md` + `tools/viral_checklist.py` + `video-script` Hard Rule 27 + `--script` S10. Imitation of structure only, see `NOTICE`.

## v3.11.0 Changelog

- **Kinetic text overlay replaces the gold-serif keyword cards (GV-17).** Style taken from a 9:16 explainer the user supplied. Keywords, not subtitles: only the important words are highlighted and `overlay_plan.py` refuses text on screen for more than 50% of a scene's speech. Two-tier text (small lead words, big heavy keyword, highlight colour for numbers and hard words, an occasional handwriting word, line icons), never static: six effects (blur-to-sharp, glitch slices, count-up, handwrite, stroke draw, exit). Image/video panels, a sliding carousel and round photo bubbles sit BEHIND the speaker through a per-frame person mask, plus a source box. New `tools/person_mask.py` (MediaPipe selfie segmenter `mediapipe==1.0.1`, model fetched by `tools/setup.sh` with a pinned sha256), `tools/overlay_plan.py` (cues timed from `vo-manifest.json` words or ASR `words_file`; `key_words` for a keyword shown differently than spoken), Remotion `KineticOverlay` (`Overlay.template.tsx`, `lib/overlay-fx.tsx`, `lib/overlayFx.mjs`), brand tokens `highlight` and `scriptFont`. `video-gen` Rule 25 and `video-post` K.4 rewritten, doc 19 rewritten. `tools/keyword_cards.py` kept, marked superseded. Real render on a client scene: `docs/evals/overlay-kinetik-run.md`. Tests: `tests/consistency/{keyword-text-overlay,person-mask-setup,overlay-template-contract,overlay-evidence}.sh`, `tests/py/test_{person_mask,overlay_plan}.py`, `tests/node/overlay-fx.test.mjs`.

## v3.10.0 Changelog

- **Keyword text overlay pattern.** Animated highlight over a speaker, in the look the user approved: stacked lines, no box or pill, small white sans, big gold serif-italic keyword (red for a danger word), soft shadow, 0.35 s fly-in and 0.25 s fly-out on the spoken word, cue times from voice word timestamps, never on the face. Optional red alarm flash on the background only through a person mask (alphamerge; a full-frame drawbox or maskedmerge tints the person). `video-gen` Rule 25, new `reference/post-production/19-keyword-text-overlay.md`, new tool `tools/keyword_cards.py` (needs Pillow, via `_venv`). Test: `tests/consistency/keyword-text-overlay.sh`. Source: Ekaputra film K1, 2026-10-03.

## v3.9.2 Changelog

- **VEO clips first, Remotion after.** Within each kelompok the VEO clips are rendered and audited before any Remotion shot or overlay is built. `video-gen` Rule 24 and step 5.1b K.4; `video-explainer` prerequisite refuses to start while the kelompok's clips are missing; `video-full` drops the standalone Step 4 (Remotion before video); pipeline doc diagram and K.4 reason fixed. A card cut to a clip needs the real clip length, light and last frame. Test: `tests/consistency/clips-before-remotion.sh`. Source: Ekaputra film, 2026-10-02.

## v3.9.1 Changelog

- **Logo only where the camera sees it, and checked against the real file.** `video-image` Rule 43: uniform logo only on garment areas that face the camera (no back logo in a shoulder close-up; plain garment there). Rule 44: after each render compare every vehicle, cooler box, carton and uniform logo with `ref/brand-<client>-logo.png`; fix by edit pass, never re-render. `video-prompt-reviewer` C13 fails a forced or unlocked logo. Source: Ekaputra scenes 04a, 07, 12a, 18, 2026-10-02.

## v3.9.0 Changelog

- **Vehicle variety + one company uniform.** `video-brainstorm` Step 1.2e (Hard Rules 14, 15) asks the delivery-point types and which vehicle serves each (truck/pickup to docks and restaurants, motorbike with cooler box to housing-complex shops and alleys a truck cannot enter), saved as `### Delivery Points & Vehicles`; and the company uniform (garment, colour, logo, placement, roles), saved as `### Company Uniform` plus one verbatim phrase in `cast-profile.md` `## Company Uniform`. `video-script` rules 22-23 + 3.5.1: scene-plan covers every vehicle class marked appears=yes, STOP on a truck at a truck-excluded point, every customer employee in the uniform phrase. `video-image` prerequisite + Rules 41-42: `ref/vehicle-<class>.png` per class, `ref/costume-uniform-<client>.png` (front + back, real logo), uniform phrase in every NB2 prompt with a customer employee. `video-prompt-reviewer` check C13. Test: `tests/consistency/uniform-and-vehicle-contract.sh`. Source: Ekaputra film, 2026-10-02.

## v3.8.0 Changelog

- **Customer business profile + reference photos.** `video-brainstorm` Step 1.2e asks what the customer sells, where, and what a visitor sees, then collects real product and site photos (`ref/biz-product-*.png`, `ref/biz-site-*.png`, optional asset and uniform). Hard gate before Phase 4A. No photo: web research + NB2 reference the user approves (`source: generated-approved`). `video-script` 3.5.1 pre-fills the manifest from these photos and stops on a product the customer never confirmed. `video-image` prerequisite + Rule 40: env and product assets derive FROM the photos. Test: `tests/consistency/business-reference-contract.sh`. Source: Ekaputra Scenes 11/12a, 2026-10-02.

## v3.7.2 Changelog

- **Keyframe name without `-start`.** One frame per clip, so the file is `keyframes/scene-{NN}.png` (letters allowed: `scene-02a.png`). Docs updated across `video-image`, `video-gen`, `script-to-scene-bridge.md`, `global-promo-config.md`, Kling guide, post-production pipeline.
- **Face fix by edit pass** (`video-image` Rule 39): when the face still drifts, edit the keyframe with the front ref only instead of re-rolling the scene.

## v3.7.1 Changelog

- **Fewest refs that do the job.** The side face ref is used only when the face in the keyframe is turned more than about 45°; a near-frontal face gets `cast-c{N}-face.png` alone. No stacking of real photo, 3-angle sheet or a continuity keyframe that contains the same person — NB2 averages the extra faces into someone else. Updated `video-image` Rule 38, reviewer D0, `01-nb2-image-generation.md`. Source: Ekaputra scene-06, 2026-10-02.

## v3.7.0 Changelog

- **One keyframe per clip.** Phase 4B renders only the start frame; no END frame and no First+Last mode unless the user explicitly asks for it on a named clip. Motion and state change move into the video prompt. Updated: `video-image` Rule 37, `video-gen` Rule 13, `script-to-scene-bridge.md` Step 3/3b/3c, `global-promo-config.md`, reviewer check D0. Source: Ekaputra film, 2026-10-02.
- **Side-view face ref for main cast.** Phase 3.5 requires `cast-c{N}-face-side.png` (three-quarter/profile, made from the front ref) for every Pemeran Utama; Phase 4B names front AND side refs inline whenever the character is not facing camera. Updated: `video-script` manifest, `video-image` Rule 38, `01-nb2-image-generation.md`, `creator-profile-system.md`, naming tables, reviewer check D0. Source: Ekaputra scene-02b, a three-quarter face from a front-only ref did not resemble the person.

## v3.6.0 Changelog

- **Pause tags in narration.** `[pause: 1.2s]` or `[jeda: 1.2 detik]` inside a layer's `text` in
  `audio-plan.json` now renders as silence. `tools/gen_vo.mjs` splits the text at each tag, sends
  one ElevenLabs request per speech chunk (chained through `previousIds` so delivery stays warm),
  decodes each chunk to PCM, joins them with zero samples and encodes once, so a pause is exact to
  the sample and word offsets come from sample counts, not from probing an mp3 with encoder
  padding. A length outside 0.2-5.0s or a broken bracket is refused. `strip_pause_tags()` in
  `tools/gen_subs.py` is imported by `tools/gen_captions.py` and `tools/verify_render.py`, so
  captions, subtitles and the P6 diff never see the tag. Adapted from MoneyPrinterTurbo.
- **Dissolves at act changes.** A segment in `work/edit-plan.json` may carry
  `transition_in: {dur_s}`. `tools/edit_render.py` renders the segment BEFORE it `dur_s` longer,
  from source frames past its `out_s` (the handle), and merges the pair with an ffmpeg `xfade`
  under a `-t` cap equal to the planned length, so the timeline does not move by a frame and the
  A/V gate still holds. The plan is refused when there is no previous segment, the previous source
  has too little handle, or the previous segment ends in a freeze pad (nothing to dissolve over).
  Motion on the handle is clamped so the zoom does not overshoot.
- **Visual QA of rendered clips (V15).** New `tools/qa_frames.py` tiles five frames per rendered
  clip into `.tmp/qa-scene-NN.jpg` and writes `work/visual-qa.md`, one section per scene with its
  `PLAUSIBILITY:` block and a seven-row verdict table that Claude fills after looking at the sheet.
  Verdicts survive a re-run for an unchanged clip and are cleared for a changed one. `--check`
  reads only the Verdict cells and exits 1 on a missing, empty or `FAIL:` cell. Validator check
  V15 and `video-gen` Rule 23. Catches the defects the plausibility gate names but only a picture
  can confirm, before the edit is paid for.
- **Video-to-music bed.** `tools/gen_music.py video` sends a picture-only proxy of the master
  (`.tmp/music-proxy.mp4`) to ElevenLabs and writes `output/music.mp3` sized to the master, logged
  in `renders.json` as phase 6 so an unchanged result is reused and not re-billed. Any failure
  (HTTP error, missing key, bad TLS) exits 3 with `FALLBACK palette: <reason>`; the tool never
  rewrites a plan it did not write, so `video-post` keeps the palette segments. On success the plan
  gets `"bed_source": "video"` (`palette` otherwise). Adapted from MoneyPrinterTurbo.
- **V16.** A pause tag inside a platform prompt in `video-prompts.md` is a FAIL: the platform
  would speak it. Reviewer check V16 and `video-validate` V16.
- **Nothing general is generated twice.**
  - `tools/gen_vo.mjs` fingerprints each layer (text, voice env, a sha256 of the voice id, model,
    settings) into `vo-manifest.json` and reuses an unchanged layer with no request. The speech
    chunks around pause tags are cached flat in `.tmp/vocache-*.mp3`, so changing only a pause
    length re-requests nothing.
  - Generated SFX clips and music tracks moved out of the versioned plugin cache (where the next
    update would have dropped them) into `${GASPOL_VIDEO_HOME:-~/.gaspol-video}/library/{sfx,music}`
    via the new `tools/asset_home.py`. Adoption copies whatever an older version dir already holds,
    and music plans may name a track as `library:<id>`.
  - New `tools/asset_library.py` keeps a cross-project library of generic images, matched only on
    the exact normalised prompt plus aspect. It refuses anything that names `cast-`, `brand-`,
    `ui-`, `product-`, `costume-`, `env-`, an identity lock or a scene continuity frame, because
    those are project-specific by definition. `video-image` checks the library before a Phase 4A
    render and offers to add a generic asset after one.
- **Real scene naming in QA.** `qa_frames.py` reads `### S01b —` headings and `scene-01b.mp4` clips
  as their own scenes (`qa-scene-01b.jpg`) instead of folding `01`, `01b` and `01c` into one — found
  on a real project before release.
- **Docs.** `reference/post-production/11-voice-cast-and-vo.md` (pause tags),
  `13-ffmpeg-edit.md` (dissolves and handles) and `17-music-bed.md` (video bed, fallback) carry the
  detail; `video-post`, `video-gen`, `video-script`, `video-validate` and both agents point at it.
- **Tool count:** 29 CLI tools (27 Python + 2 Node) — counted from `tools/`; earlier releases stopped updating this number at 19 while `check_vo_duration.py`, `check_overlay_strings.py`, `track_screen.py`, `caption_keywords.py`, `gen_captions.py` and `plan_motion.py` landed. Excluded on purpose: TwelveLabs
  analysis, Sonilo, other render adapters, slide/zoom transitions, transitions outside act
  changes.

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
