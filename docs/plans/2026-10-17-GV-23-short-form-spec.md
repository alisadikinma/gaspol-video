**Ticket:** GV-23

# GV-23 — Video type routing, short-form timeline, repackage merge, short-form layout gate

## Design

One ticket, five items, one subsystem (the gaspol-video short-form path). Owner decisions taken in
the 2026-10-17 brainstorm are marked **[owner]**.

### 1. Video type decides the format (`video-brainstorm`)

Step 1.0b becomes four types. Step 1.5 (platform pick) is removed: the brief derives format and
platforms from the type, shows them, and the owner confirms or edits.

| `video_type` | aspect | `max_duration_s` | `platforms` | Arc |
|---|---|---|---|---|
| `presentasi` | 16:9 | 180 | `[youtube, linkedin]` | 7-beat, no F12/F13 |
| `promo` (indusia.ai product) | 9:16 | 60 | `[shorts, reels, tiktok, linkedin]` | product gates kept + F13 timeline + F12 |
| `isu` | 9:16 | 60 | `[shorts, reels, tiktok, linkedin]` | honesty limits kept + F13 + F12 |
| `edukasi` | – | – | – | STOP: ask for the link(s), route to `/video-repackage` |

- `strategic-brief.md` gains `video_type`, `aspect`, `max_duration_s`, `platforms: [...]`. The
  `## Platform:` line stays (derived) so existing readers do not break.
- Existing `promo | issue` values keep working: `issue` is read as `isu`.
- Why 60 s, not 90: the notebook's Body ends at second 50 and CTA follows (§2).
- Why `edukasi` leaves the skill: the owner's education videos are always a remake of someone
  else's video by link; brainstorm questions have no true answer for it.

### 2. Short-form timeline (new reference `F13_Short_Form_Timeline.md`)

Source: NotebookLM notebook `fd70ee32` (SAMUEL-STYLE 2026-10), queried 2026-10-17. Every rule is
labelled `[DATA]` (stated by the sources) or `[TAFSIRAN]` (the notebook's own interpretation).

| Stage | Seconds | Rule |
|---|---|---|
| Thumbnail | frame 0-1 | cover shown first; text per §5 |
| Hook | 0-3 | bold statement + bold on-screen text + sudden motion; no greeting; promise kept in the video |
| Foreshadow | 3-6 | micro visual clue 0.5-1 s, a reaction/audio snippet, or a mystery prop; show the conflict, never the answer; cut right before resolution; no fake foreshadow |
| Body | 6-50 | point system or escalation; chat tone; no dead air |
| CTA | last 2-4 s | follow `@alisadikinma` + a reason ("follow biar ..."); never a bare "jangan lupa subscribe" |
| Watermark | 0-100 % | inside the safe area, small, never over face or text |

Support rules: loop ending ("Dan itulah ..." reconnecting to the hook line), a cut or zoom every
1-3 s, b-roll matches the spoken word, BGM under the voice.

- F13 adds timing; F12 (notebook `114215f6`) keeps its 7-stage checklist. F13 never overrides the
  9 Commandments, F5 or F6.
- `video-script`: a 9:16 `av-script.md` carries `Tahap` and `Detik` columns.
- `tools/viral_checklist.py` gains `timeline <av-script.md>`: exit 1 when a stage is missing, out of
  order, or outside its second range (tolerance from the profile file, not hard-coded).

### 3. `video-repackage`: Foreshadow + merge two links

- The rebuilt storyline gets a Foreshadow beat (F13) between hook and body.
- **Merge mode**, max two links **[owner]**:
  1. `vidkit ingest` each link to `ref/sumber-1/`, `ref/sumber-2/`; `vidkit scenes` each.
  2. Transcribe both (AssemblyAI, existing `gen_subs.py` path) into a point list tagged by source.
  3. Point table: same in both (pick the clearer), unique (add), conflicting (owner decides),
     strongest hook of the two. **Hard stop for owner approval** before any storyline is written.
  4. One storyline in F13 order within 60 s. Over budget: propose cuts, or a two-part series.
  5. Each scene's reference still comes from whichever source shows it best.
  6. Both links recorded in `strategic-brief.md`.

### 4. `video-repackage` not registered in sessions

Root cause (measured): `~/.claude/plugins/installed_plugins.json` has gaspol-video **3.11.1**,
because `gaspol-one/.claude-plugin/marketplace.json` pins `"version": "3.11.1"`. `video-repackage`
shipped in 3.13.0. Fix: release step sets the marketplace entry to this ticket's version, then
`claude plugin update gaspol-video@gaspol-one`, then verify in a new session that
`gaspol-video:video-repackage` is listed. Recorded as a release-checklist item so it cannot drift
again.

### 5. Short-form layout

**Profiles** — new `media/layout-profiles.json`; every number carries `source`
(`official` | `data` | `tafsiran`), same contract as `media/loudness-profiles.json`.

- `short-organic` (default **[owner]**): safe area top 14 %, bottom 21 %, left 6 %, right 10 % of a
  1080×1920 frame. Top/sides from Meta (official, facebook.com/business/help/980593475366490);
  bottom 21 % and right 10 % from YouTube Shorts / TikTok overlay templates (third-party, labelled).
- `short-ads`: bottom 35 % (Meta official, ad placements). Shipped, used only when asked.

**Measurement phase [owner]** — download 6 Samuel Christ Shorts with `vidkit ingest` into the
scratch folder (never committed), sample frames, measure: subtitle cap height and Y, words per
display, cover title Y and height. Written to `docs/evals/short-form-layout-measurement.md`.
Measured values enter the profile as `source: data`. A measured value outside the safe area is
clamped to it and the difference recorded.

**Subtitle spec** — bold sans, white fill, black outline, active word in the accent colour, words
per display and size from the measurement (start range 1-3 words), baseline inside the safe area
and at least the profile's chin gap below the face box. `vidkit karaoke` and `KineticOverlay`
defaults read the profile (today `margin_v=360` puts the line at 81 % from top, inside the UI band).

**Thumbnail title spec** — 9:16 cover image is rendered **without text [owner]** (expressive face,
high-value object); the title is stamped by a new `vidkit title` (ffmpeg, no new dependency): 3-5
words, ALL CAPS, formula = extreme number + public figure + curiosity word, contrast box behind,
position and size from the profile, never over the face. Honesty guardrail of doc 15 applies: the
promise must be in the video. Doc 21 gains the 9:16 path; the 16:9 path is unchanged.

**Three different texts** — `video-package` fills each separately:

| Text | Length | Job |
|---|---|---|
| Thumbnail title | 3-5 words | the click in the feed |
| Video title | 5-9 words + tags, ALL CAPS | search and algorithm |
| Hook on-screen text | 4-7 words | stop the scroll at 0-3 s, appears with the narration |

**Gate — `tools/layout_gate.py`, blocking [owner]** (exit 0 pass, 1 fail, 2 bad input):
- Text boxes are measured, not guessed: the subtitle ASS, overlay text and title are re-rendered
  alone on black with ffmpeg; the bounding box of non-black pixels is the real box.
- Checks: every text/watermark box inside the profile's safe area; subtitle and title boxes do not
  intersect the face box; a subtitle below the face starts at least the chin gap below it (a
  subtitle wholly above the face does not cover it and passes — decided 2026-10-17).
- Face box: OpenCV YuNet (`cv2.FaceDetectorYN`, CPU) on every Nth frame — the MediaPipe face
  detector aborts on this Mac's Metal backend, owner chose YuNet 2026-10-17 (model fetched by `tools/setup.sh`, pinned
  sha256, venv via `_venv.py`). No face in a frame = face checks skipped for that frame, reported.
- Preview: one frame per platform with a mock UI overlay, `.tmp/layout-{tiktok,reels,shorts}.jpg`.
- Called by `video-post --final` and `video-package` before anything is final; `video-validate
  --layout`. Registered in `tools/registry.json` (route + tool), table re-rendered.

### Data Integration Map

| Component | Data source | Existing? | Notes |
|---|---|---|---|
| Step 1.0b brief | owner answer → `strategic-brief.md` | changed | `issue` alias kept |
| F13 timeline | notebook `fd70ee32` | new | DATA/TAFSIRAN labels |
| Timeline check | `av-script.md` → `viral_checklist.py timeline` | changed | |
| Merge two links | `vidkit ingest`/`scenes` + AssemblyAI | partly | key from `.env` |
| Layout profiles | `media/layout-profiles.json` | new | `source` per number |
| Samuel numbers | 6 real Shorts, measured | new | clips not committed |
| Subtitle | `vidkit karaoke` | defaults changed | |
| Thumbnail title | `vidkit title` | new | ffmpeg only |
| Face box | OpenCV YuNet (`face_detection_yunet_2023mar.onnx`) | new | pinned model |
| Gate | `tools/layout_gate.py` | new | blocking |
| Skill registration | `gaspol-one/.claude-plugin/marketplace.json` | changed | separate repo |

### Error handling

- Missing profile / unknown profile name → exit 2 naming the file and valid names.
- Missing ffmpeg or venv module → exit 2 naming `tools/setup.sh` (existing `_venv.py` contract).
- `vidkit title` with more than 5 words or a word wider than the safe area → refuse, never shrink
  below the profile's minimum size.
- Merge mode with a failed download → stop, name the link; never continue on one source silently.
- Over-budget merged storyline → proposal shown, nothing dropped without owner approval.

### Testing

TDD per phase: `tests/py/test_layout_gate.py`, `test_vidkit.py` (`title`, karaoke defaults from
profile), `test_viral_checklist.py` (timeline mode), consistency checks for the 4-type Step 1.0b,
F13 references, repackage merge gate, layout-profile `source` contract, marketplace version equals
`plugin.json`. Real-data evidence: the Samuel measurement doc and one gate run on a real finished
9:16 master.

### Out of scope

More than two merge links; a 4:5 LinkedIn variant; OCR of burned-in text; per-platform separate
renders (one file serves all four).
