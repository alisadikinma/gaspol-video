# Script-to-Scene Bridge

Converts a finished A/V script into a scene-by-scene production plan with NB2 image prompts and VEO 3.1 video prompts. This is the critical bridge between Phase 2 (Script) and Phase 4-5 (Image/Video Prompts).

---

## 1. Script → Scene Decomposition Algorithm

### Input: A/V Script (from Phase 2)

The script from Phase 2 contains:
- Beat labels (Pattern Interrupt, Hook, Foreshadow, Agitate, Guide, Peak, CTA, Won Day)
- Timing per beat
- Narration/dialogue text
- Visual descriptions
- Audio direction

### Step 1: Beat → Scene Mapping

Each beat in the 7-beat arc maps to 1 or more scenes:

| Beat | Typical Duration | Scenes | VEO Clips Needed |
|------|-----------------|--------|-------------------|
| Pattern Interrupt | 0–1.7s | 1 | 1 clip (4s) |
| Hook | 1.7–5s | 1 | 1 clip (4-6s) |
| Foreshadow | 5–8s | 1 | 1 clip (8s) |
| Agitate | 8–15s | 1-2 | 1-2 clips |
| Guide + Plan | 15–40s | 3-5 | 3-5 clips + extends |
| Peak | 60-75% mark | 1-2 | 1-2 clips |
| CTA | Post-peak | 1 | 1 clip (8s) |
| Won Day | Final frame | 1 | 1 clip (4-8s) |
| **Total** | **120-180s** | **10-15** | **10-18 clips** |

### Step 2: Scene Duration Allocation

For each scene, calculate optimal VEO clip strategy:

```
IF scene_duration <= 8s:
    → 1 VEO generation (4/6/8s)
    → Resolution: 1080p OK (no extend needed)

IF 8s < scene_duration <= 15s:
    → 1 VEO generation (8s) + 1 extend (+7s)
    → Resolution: MUST be 720p (extend requirement)

IF 15s < scene_duration <= 22s:
    → 1 VEO generation (8s) + 2 extends (+14s)
    → Resolution: MUST be 720p

IF scene_duration > 22s:
    → Consider splitting into 2 separate scenes
    → Or: 1 gen (8s) + 3+ extends (diminishing quality)
```

### Step 3: VEO Mode Selection per Scene

```
FOR each scene:
    IF scene has SAME CHARACTER talking (lip sync):
        IF same character continues from previous scene:
            → Ingredients mode (character consistency)
            → Use same ref images
        ELSE:
            → Ingredients mode (new ref images)

    IF scene shows STATE CHANGE (before→after, open→close):
        IF face >30% of frame (presenter, talking head, character CU):
            → Single I2V mode (start frame only)
            → ⚠️ Safety filter rejects 2 face images in First+Last Frame
        ELSE (dashboard, product, environment, wide shot):
            → First+Last Frame mode
            → Generate START image (NB2) + END image (NB2)

    IF scene is B-ROLL (product/environment, no dominant face):
        → First+Last Frame mode
        → Generate START image (NB2) + END image (NB2)

    IF scene is B-ROLL WITH visible character face:
        → Single I2V mode (start frame only)
        → ⚠️ Safety filter rejects 2 face images in First+Last Frame

    IF scene CONTINUES previous scene (same location, same action):
        → Extend mode
        → Source: previous VEO clip (720p)
        → Max: +7s per hop

    NEVER combine Ingredients + First+Last Frame in same generation
    FACE SAFETY: First+Last Frame → ONLY for faceless scenes (face <30% frame)
```

### Step 3b: Seedance 2.0 Mode Selection per Scene (if `video_model` = `seedance`)

```
FOR each scene:
    IF scene has RECURRING CHARACTER (needs identity consistency):
        → Omni mode (Full Multi-Reference)
        → @Image1-3: character 3-angle views (front, profile, 3/4) — MANDATORY
        → @Video1: motion/camera reference (if available)
        → @Audio1: voice/rhythm reference (if available)
        → CRITICAL: Real face upload BANNED — use AI-generated faces only

    IF scene shows STATE CHANGE (before→after, product transform):
        → First+Last Frame mode (2 NB2 images: start + end)
        → Interpolation-based — model fills between two states
        → Good for low-complexity transitions

    IF scene is SIMPLE B-ROLL (environment, product, no character):
        → Single Image I2V (1 NB2 image as start frame)
        → Faster generation, computationally lighter

    IF scene CONTINUES previous scene:
        → Extension via @Video state-setter
        → 4-15s per extension hop, unlimited chains
        → Re-upload @Image reference every 5-10 extensions to prevent drift

    SEEDANCE CONSTRAINTS:
    - ~50 words max per prompt (shorter = better reliability)
    - No negative prompts — use positive constraint syntax
    - No real face upload (0% success rate)
    - 3-Angle Rule mandatory for character consistency (front, profile, 3/4)
    - Multi-shot timestamps available: [0-5s], [5-10s], [10-15s]
    - 6 aspect ratios: 16:9, 9:16, 1:1, 3:4, 4:3, 21:9

See reference/image-video-gen/07-seedance-production-guide.md for full specs.
```

### Step 3c: Kling 3.0 Mode Selection per Scene (if `video_model` = `kling`, v2.3.0+)

```
FOR each scene:
    IF scene applies motion FROM existing reference video TO new subject/scene:
        → Motion Control mode
        → Source: 1 motion-ref video + new anchor image + text prompt
        → Character Orientation parameter:
            • Follow Video → replicate spatial positioning + camera angles (best for complex motion/dance/action)
            • Follow Image → maintain anchor composition (best when camera dominates body motion)

    IF scene has HOOK / MONTAGE / VIRAL CUT (3-6 quick shots in <=15s, shared env/character):
        → Multi-Shot Storyboard mode
        → Single 15s render containing up to 6 distinct shots
        → Shot boundaries: numbered (`Shot 1: ... Shot 2: ...`) OR transition cues (`match cut to`, `whip pan to`)
        → NB2 anchor required ONLY for Shot 1 (Kling extrapolates further shots from text)
        → Trade-off: less control per shot, cannot extend, failures = full re-render
        → AVOID for high-stakes hero shots / complex dialogue beats / scenes needing extension

    IF scene shows STATE CHANGE (before→after, product unbox, environment shift), FACELESS only:
        → First+Last Frame mode (2 NB2 images: start + end)
        → ⚠ Same safety filter risk as VEO — 2 photoreal face images = "prominent people" rejection
        → For face-dominant scenes (face >30% frame) → use single I2V instead

    IF scene has CHARACTER speaking / face >30% frame:
        → Single I2V mode (1 NB2 image as start anchor)
        → Anchor = identity/layout lock; text prompt = how scene evolves
        → Frame 1 quality rule: clean lighting + clean pose = >90% success

    IF scene has NO anchor image (rare — most production uses NB2 upstream):
        → Text-to-Video (T2V) mode
        → Lowest control over identity, best for atmospheric B-roll / environmental establish

    KLING CONSTRAINTS:
    - 80-120 word prompt optimal (longer = ignored)
    - 5-part prompt formula MANDATORY: Camera Movement + Scene Setup + Subject Action + Vibe/Lighting + Time/Audio
    - Camera term position determines weight: start = camera dominates, end = camera follows subject
    - No native extension chain — for long-form, restart with new NB2 anchor
    - Cannot render legible text (use post-prod overlay for logos/text)
    - Bahasa Indonesia: **on-screen lip-sync** NOT supported (5 langs only: EN/ZH/JA/KO/ES). **Voice-over narrator IS supported natively** — for B-Roll/off-screen ID, use `Voice-over narrator, [tone]: [ID text]` directly (no post-prod dub needed). Only switch to VEO for face-front lip-sync ID scenes.
    - Mixed-language scene UNIQUE feature — different characters can speak different languages in same shot
    - Duration: PER-SECOND granular (3s/4s/5s/6s/7s/8s/9s/10s/11s/12s/13s/14s/15s) — pick exact second matching scene need, no padding
    - Dialogue budget ~2.5 words/sec: 3s→6-8 words, 5s→10-13, 8s→18-22, 10s→25-30, 15s→38-45
    - Negative prompts focused (3-5 terms per relevant category), NOT 20-term generic dump
    - 3 aspect ratios in UI: 16:9, 9:16, 1:1
    - Resolution: 720p or 1080p (UI); 4K available via API on selected providers
    - Frame rates: 24/30/60fps (24 default for promo)

See reference/image-video-gen/08-kling-production-guide.md for full specs and 5-part prompt formula examples.
```

---

## 2. Scene Plan Output Format

### Scene Plan Table (scene-plan.md)

```markdown
# Scene Plan — {Video Title}

## Overview
| Total Duration | {X}s |
| Total Scenes | {N} |
| Total VEO Clips | {M} (generations + extensions) |
| Resolution Strategy | 720p for extendable, 1080p for final-only |
| Aspect Ratio | {16:9 / 9:16} |

## Scene Breakdown

| # | Beat | Duration | Render Path | VEO Mode | Extend? | Resolution | Scene Type | Dialogue? |
|---|------|----------|-------------|----------|---------|------------|------------|-----------|
| 1 | Pattern Interrupt | 4s | live-action | Frame | No | 1080p | B-Roll | No |
| 2 | Hook | 6s | live-action | Frame | No | 1080p | Presenter | Yes (lip sync) |
| 3 | Foreshadow | 8s | live-action | Frame | No | 720p | Presenter | Yes (lip sync) |
| 4 | Agitate | 15s | live-action | Ingredients+Ext | 1x | 720p | Presenter | Yes (lip sync) |
| 5 | Guide 1 | 5s | explainer | — | No | 720p | B-Roll | VO only |
| 6 | Guide 2 | 15s | live-action | Ingredients+Ext | 1x | 720p | Presenter | Yes (lip sync) |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

### Render Path — which engine builds this scene (v3.0.0)

`Render Path` decides WHICH ENGINE builds the scene. It is orthogonal to `Scene Type`, which decides
WHO is on screen. A Presenter scene can be live-action; a B-Roll scene can be explainer.

| Value | Built by | Gets an NB2 keyframe? | Gets a platform prompt? |
|---|---|---|---|
| `live-action` | VEO 3.1 / Seedance 2.0 / Kling 3.0 | Yes, Phase 4B | Yes, Phase 5 |
| `explainer` | Remotion shot, Phase 4.5 `/video-explainer` | **No** | **No** |

**Assignment rule — apply to every scene in Phase 3:**

```
A scene is `explainer` when its job is to make legible information readable:
  - on-screen numbers, metrics, KPI, before/after comparison
  - a diagram, flow, architecture, timeline, map with labels
  - a product UI walkthrough where the text itself must be read
  - a list, checklist, price table, spec table
Otherwise the scene is `live-action`.
```

**Why this is decided here and not later.** No supported platform renders legible text — VEO,
Seedance and Kling all warp it to gibberish. A scene whose whole job is a number or a diagram is
therefore unbuildable as a generated clip, and finding that out in Phase 5 means the NB2 keyframes for
it were already paid for. Deciding in Phase 3 costs nothing and saves the whole chain.

**The mixed case.** A scene that needs BOTH a human performance and readable data stays
`live-action`, and the readable part becomes an overlay shot composited on top in Phase 6. Record it
as `live-action + overlay:<shot-id>`. A presenter reading a chart is this case, not an explainer.

**Duration for explainer scenes** is not bound by any platform's clip limit. A Remotion shot can be
any length, so its duration comes from the narration that runs over it, not from an 8-second budget.

## Extension Chain Map

Scene 4: Clip 4a (8s, 720p) → Extend → Clip 4b (+7s) = 15s total
Scene 6: Clip 6a (8s, 720p) → Extend → Clip 6b (+7s) = 15s total
```

---

## 3. Scene → NB2 Image Prompts (Phase 4B — Scene Keyframes)

> **CRITICAL:** Scene keyframes are MOLECULES composed FROM Phase 4A ATOMS.
> NEVER describe a visual element from text alone if an asset exists in ref/.
> Every character, vehicle, object, product, environment MUST reference its asset file.
> See `global-promo-config.md` Section 17 (Asset-First Production Model).

### For First+Last Frame Mode

Generate TWO NB2 images per scene:

**Start Frame Template:**
```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
{If scene index > 1 in timeline: Continuation from scene-{NN-1}-end.png — maintaining character position, lighting, and environment from previous scene.}
SUBJECT: {character name} (Maintain exact facial identity from reference image: cast-c{N}-face.png) — {ethnicity} {gender}, {age_range}, {key_features}, body proportions matching cast-c{N}-body.png. {If institutional: Wearing official {institution} uniform EXACTLY as shown in cast-c{N}-costume.png — badge placement, color scheme, emblem detail.} {Creator reference phrase from creator-profile.md}.
{character/product description from script}.
{If vehicle in scene: The {vehicle} — EXACTLY matching vehicle-{type}-{name}.png — {vehicle action/position}.}
{If object/equipment in scene: The {equipment} — EXACTLY matching object-{name}.png — {equipment context}.}
SCENE: {environment from script A/V direction}, environment layout EXACTLY as shown in env-{location}.png.
{If product visible: Product texture EXACTLY matching product-closeup-{name}.png.}
{If product hero shot: Product EXACTLY matching product-{name}.png.}
{If brand visible: Brand asset EXACTLY matching brand-{asset}.png.}
{If UI/screen visible: Screen layout EXACTLY matching ui-{name}.png.}
EXPRESSION: {emotion from beat — see 04-cinematography-lookup.md}.
CAMERA: {shot size} {lens} {aperture}, {angle}.
LIGHTING: {pattern} {ratio}, {kelvin}K {film stock}.
ATMOSPHERE: {atmosphere type}.
CULTURAL CONTEXT: {from strategic-brief.md Cultural Context — local architecture, landmarks, plate codes, ethnicity of background figures}.
DOMAIN CONTEXT: {from strategic-brief.md Domain Knowledge — accurate equipment description, correct process step, realistic operator action for this scene}.
TECHNICAL: 16:9 landscape, {resolution}, CFG {cfg}, Denoise {denoise}, Thinking High.
TONE: {atmosphere keywords from global-promo-config.md Section 13 per video_tone}.
WARDROBE: {wardrobe from creator profile}.
NARRATIVE CONTEXT: Previous scene {N-1} showed {summary}. This scene {action + cause}. Visual breadcrumb: {shared element with adjacent scene}.
EXPLICIT NEGATIVES: No {inappropriate element 1}, no {inappropriate element 2}.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/scene-{NN}-start.png`

**Required Reference Images (upload all to `{project}/ref/` folder):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{N}-face.png` | {Character name} face | ⬜ |
| 2 | `cast-c{N}-body.png` | {Character name} full body | ⬜ |
| 3 | `cast-c{N}-costume.png` | {Institution} uniform | ⬜ (if institutional) |
| 4 | `env-{location}.png` | {Location} establishing | ⬜ |
| 5 | `product-{name}.png` | Product hero shot | ⬜ (if product visible) |
| 6 | `product-closeup-{name}.png` | Product texture closeup | ⬜ (if product texture visible) |
| 7 | `brand-{asset}.png` | Brand asset | ⬜ (if brand visible) |
| 8 | `vehicle-{type}-{name}.png` | Vehicle | ⬜ (if vehicle in scene) |
| 9 | `object-{name}.png` | Object/equipment | ⬜ (if object in scene) |
| 10 | `ui-{name}.png` | UI/screen | ⬜ (if screen visible) |
| 11 | `scene-{NN-1}-end.png` | Previous scene end frame — grading & continuity anchor | ⬜ (CONDITIONAL — v2.2.0: include ONLY IF env(N-1) == env(N). Hard cut between scenes = DROP this row. See global-promo-config.md §27.) |
```

**End Frame Template:**
```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: {SAME character name} (Maintain exact facial identity from reference image: cast-c{N}-face.png) — {SAME description}, body proportions matching cast-c{N}-body.png. {If institutional: Wearing official {institution} uniform EXACTLY as shown in cast-c{N}-costume.png.} NEW pose/position reflecting end-of-scene state.
{If vehicle in scene: The {vehicle} — EXACTLY matching vehicle-{type}-{name}.png — {end-state position}.}
{If object/equipment in scene: The {equipment} — EXACTLY matching object-{name}.png — {end-state context}.}
SCENE: {SAME environment — verbatim}, environment layout EXACTLY as shown in env-{location}.png.
{If product visible: Product texture EXACTLY matching product-closeup-{name}.png.}
{If brand visible: Brand asset EXACTLY matching brand-{asset}.png.}
{If UI/screen visible: Screen layout EXACTLY matching ui-{name}.png.}
EXPRESSION: {evolved emotion — e.g., concern → realization}.
CAMERA: {SAME lens}, {SAME or adjacent shot size — max 1 step change: CU↔MCU, MCU↔MS, MS↔MWS, MWS↔WS}, {SAME angle or max 15° tilt/pan change — VEO interpolation breaks with drastic camera jumps}.
LIGHTING: {SAME pattern, SAME ratio, SAME kelvin — critical for consistency}.
ATMOSPHERE: {SAME atmosphere}.
CULTURAL CONTEXT: {SAME cultural context — verbatim}.
TECHNICAL: 16:9 landscape, {SAME resolution}, CFG {cfg}, Denoise {denoise}, Thinking High.
TONE: {SAME tone atmosphere — verbatim}.
WARDROBE: {SAME wardrobe — verbatim}.
NARRATIVE CONTEXT: {SAME narrative context — verbatim from start frame}.
EXPLICIT NEGATIVES: {SAME explicit negatives — verbatim from start frame}.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/scene-{NN}-end.png`

**Consistency Checklist (Start ↔ End):**
- [ ] Same aspect ratio
- [ ] Same lighting temperature (Kelvin)
- [ ] Same color palette / grading style
- [ ] Character wardrobe identical
- [ ] Same lens focal length
- [ ] End frame = plausible physical destination from start
- [ ] Camera angle change between start/end is max 15° (drastic angle change = broken VEO interpolation)
- [ ] Shot size change between start/end is max 1 step (adjacent sizes only: CU↔MCU, MCU↔MS, MS↔MWS, MWS↔WS)
- [ ] Central 60% rule maintained

### For Ingredients Mode

Generate 1-3 reference images:

**Character Reference Template:**
```
SUBJECT: {character name} (Maintain exact facial identity from reference image: cast-c{N}-face.png) — {character full description — SAME text verbatim across ALL refs}. {Creator reference phrase from creator-profile.md}.
ANGLE: {front / three-quarter / profile} — generate all 3 for best consistency.
LIGHTING: Neutral diffused (clean identity data — NOT dramatic).
BACKGROUND: Clean, simple (studio white or neutral).
EXPRESSION: Neutral, natural.
TECHNICAL: {aspect_ratio}, 4K resolution, high thinking mode.
WARDROBE: {wardrobe from creator profile}.
```

**Required Reference Images (upload all to `{project}/ref/` folder):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{N}-face.png` | {Character name} face | ⬜ |
| 2 | `cast-c{N}-body.png` | {Character name} full body | ⬜ (if Utama) |
```

### For Multi-Character Scenes

When 2+ characters from cast-profile.md appear in the same scene:

**Multi-Character Frame Template (First+Last Frame mode):**
```
SUBJECT: Character {A} — {name_A} (Maintain exact facial identity from reference image: cast-c{A}-face.png), body proportions matching cast-c{A}-body.png — {full description from cast-profile.md}. {If institutional: Wearing official uniform EXACTLY as shown in cast-c{A}-costume.png.} {Else: WARDROBE: {costume from cast-profile.md}.}
AND Character {B} — {name_B} (Maintain exact facial identity from reference image: cast-c{B}-face.png), body proportions matching cast-c{B}-body.png — {full description from cast-profile.md}. {If institutional: Wearing official uniform EXACTLY as shown in cast-c{B}-costume.png.} {Else: WARDROBE: {costume from cast-profile.md}.}
INTERACTION: {specific action between characters from script A/V direction}.
POSITIONING: Pemeran Utama more prominent (closer to camera, better lit, larger in frame). Pendamping in supporting position.
SCENE: {environment description}, environment layout EXACTLY as shown in env-{location}.png.
CAMERA: {shot size wide enough to fit both characters} {lens} {aperture}, {angle}.
LIGHTING: {pattern} {ratio}, {kelvin}K {film stock}.
ATMOSPHERE: {atmosphere type}.
TECHNICAL: {aspect_ratio}, {resolution}, high thinking mode.
```

**Multi-Character Ingredients Template:**
```
CHARACTER {A} REFERENCE:
SUBJECT: {Character A name} (Maintain exact facial identity from reference image: cast-c{A}-face.png) — {full description verbatim from cast-profile.md}. WARDROBE: {costume from cast-profile.md}.
ANGLE: {front / three-quarter / profile}.
LIGHTING: Neutral diffused (clean identity data).
BACKGROUND: Clean studio white.
TECHNICAL: {aspect_ratio}, 4K, high thinking mode.

CHARACTER {B} REFERENCE:
SUBJECT: {Character B name} (Maintain exact facial identity from reference image: cast-c{B}-face.png) — {full description verbatim from cast-profile.md}. WARDROBE: {costume from cast-profile.md}.
(same structure, different character data)

NOTE: Generate separate reference images per character for Ingredients mode.
VEO Ingredients accepts up to 3 reference images — use 1 per character (max 3 chars per generation).
```

**Character Hierarchy in Frame:**
- Pemeran Utama: Always more prominent (closer to camera, better lit, larger in frame)
- Pemeran Pendamping: Supporting position (slightly behind, beside, or angled away)
- Max 3 characters per frame for clean composition
- If 4+ characters needed: use shot/reverse-shot or group-then-individual sequence

**Multi-Character Consistency Checklist (in addition to standard checklist):**
- [ ] Each character's reference phrase used verbatim from cast-profile.md
- [ ] Each character's identity ref file specified (ref/cast-c{N}-face.png)
- [ ] Character hierarchy correct (Utama prominent, Pendamping supporting)
- [ ] Costume matches cast-profile.md (institutional if applicable)
- [ ] Spatial relationship between characters is physically plausible

### Multi-POV Environment Scenes (2+ env-* refs of same location)

When a scene's upload table includes 2+ `env-*` references showing the **SAME physical location from DIFFERENT camera angles** (e.g., entry/exit/side/interior/exterior views of one facility):

**MANDATORY: Insert SPATIAL CONTEXT block** immediately after the opening line of the prompt, BEFORE any per-element descriptions:

```
SPATIAL CONTEXT — The following {N} environment references show the SAME
{facility name} from {N} DIFFERENT camera angles. Use each ONLY for the
specific zone it depicts, then COMPOSE into one coherent {shot type} shot:
- {env-ref-angle1.png} = {ANGLE} view → use for: {specific elements this ref provides}
- {env-ref-angle2.png} = {ANGLE} view → use for: {specific elements this ref provides}
CAMERA for this scene: {camera position/angle description} — compositing
spatial information from all {N} views into this single perspective.
```

**Why this matters:**
NB2 receives all uploaded refs simultaneously. Without a spatial map, it cannot reconcile images taken from conflicting viewpoints. The SPATIAL CONTEXT block tells the model: "these are different windows into the same 3D space — here's how they fit together from YOUR camera angle."

**Checklist addition for multi-POV scenes:**
- [ ] SPATIAL CONTEXT block present after opening line
- [ ] Each env-* ref mapped to specific zone/elements it provides
- [ ] Camera position for THIS scene explicitly stated relative to ref angles
- [ ] PRIMARY layout ref identified (usually the widest/most comprehensive view)
- [ ] Per-element `EXACTLY matching` references still appear inline (standard rule)
- [ ] Upload table Purpose column includes POV label (e.g., "entry view", "side view")

---

## 4. Scene → VEO 3.1 Video Prompts

### Presenter Scene (Lip Sync) Template

**VEO Mode:** Single I2V (start frame only) — safety filter rejects First+Last Frame with face >30%.

```
~{duration}s, {resolution}, {aspect_ratio}.
Camera: {camera_movement from 04-cinematography-lookup.md}, {speed}.
Subject: {micro-movements — subtle eye blinks every 2-3 seconds, gentle breathing motion}.
Maintain visual continuity with reference frame character appearance throughout clip.
Host says: {narration text from script — max 8-15 words per 8s, NO em dash, use comma/period instead}.
Expression shift: {start_emotion} to {end_emotion} over {duration}s.
SFX: {sound effects from script}.
Ambient: {background atmosphere + music direction}.
Tone atmosphere: {from global-promo-config.md Section 13 per video_tone}.
Domain context: {from strategic-brief.md Domain Knowledge — equipment/process detail relevant to this scene}.
Narrative context: Continues from scene {N-1} where {summary}. {Visual breadcrumb shared with adjacent scene}.
{veo_negative_prompt from global-promo-config.md}
Maintain exact lighting, environment, appearance from reference frame.
```

**CRITICAL VEO DIALOGUE RULES:**
- Use `Host says:` / `Presenter says:` / `Speaker says:` — NEVER real person names (safety filter)
- NO em dash `—` in dialogue text — VEO audio engine mistranslates it, use `,` or `. ` instead
- Face reference filenames (`cast-c{N}-face.png`) belong ONLY in NB2 prompts, NOT VEO prompts

**Required Reference Images (upload all to `{project}/ref/` folder — place below heading, before prompt body):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{N}-face.png` | {Character name} face | ⬜ |
| 2 | `cast-c{N}-costume.png` | Costume/uniform | ⬜ (if institutional) |
| 3 | `env-{location}.png` | Environment | ⬜ (if location-specific) |
```

### B-Roll Scene (Voiceover, No Lip Sync) Template

**EVERY B-Roll scene MUST have voiceover narration** — no silent B-Roll in promo videos. VO text comes from av-script.md, segmented per scene (max 12-15 words per 8s clip).

```
~{duration}s, {resolution}, {aspect_ratio}.
Camera: {camera_movement}, {speed}.
Subject: {product/environment action from script}.
{If characters visible: Maintain visual continuity with reference frame character appearance.}
{ambient_motion — floating particles, screen content shifting, etc.}
Voice-over narrator, {tone from video_tone}: {narration text from script — max 12-15 words per 8s, NO em dash, use comma/period instead}.
SFX: {sound effects}.
Ambient: {background music + atmosphere}.
Tone atmosphere: {from global-promo-config.md Section 13 per video_tone — e.g., "lighthearted, bright" or "tense, dramatic"}.
Cultural context: {from strategic-brief.md — local ambient sounds, weather atmosphere, architectural backdrop}.
Domain context: {from strategic-brief.md Domain Knowledge — equipment/process detail relevant to this scene}.
Narrative context: Continues from scene {N-1} where {summary}. {Visual breadcrumb shared with adjacent scene}.
{veo_negative_prompt}
```

> **POST-PROD VO:** "{same narration text as above}" — fallback if VEO narrator layer fails. Record separately and overlay in post-production.

**CRITICAL B-ROLL AUDIO RULES:**
- ALWAYS use `Voice-over narrator, {tone}: text` — VEO treats "narrator" as off-screen entity
- NEVER use bare `Voiceover: text` — VEO assigns speech to any visible on-screen character
- NEVER use `[Character name] says:` for background narration — triggers lip sync
- NO em dash `—` in voiceover text — replace with `,` or `. `
- Face reference filenames (e.g., `cast-c{N}-face.png`) do NOT go in VEO prompts — use generic continuity language
- Always include `> POST-PROD VO:` backup line outside the prompt block

**Required Reference Images (upload all to `{project}/ref/` folder — place below heading, before prompt body):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `product-{name}.png` | Product shot | ⬜ (if product visible) |
| 2 | `env-{location}.png` | Environment | ⬜ (if location-specific) |
| 3 | `brand-{asset}.png` | Brand asset | ⬜ (if brand visible) |
```

### Extension Prompt Template

**For lip sync extensions:**
```
Continue from previous clip. {new_action from next script beat}.
Camera continues {same_movement} at {same_speed}.
Maintain lighting, environment, character appearance.
Host says: {next_dialogue — max 8-15 words, NO em dash, use comma/period}.
Audio continues: {same_ambient}, {new_sfx if any}.
{veo_negative_prompt}
```

**For B-Roll extensions (voiceover):**
```
Continue from previous clip. {new_action from next script beat}.
Camera continues {same_movement} at {same_speed}.
Maintain lighting, environment, character appearance.
Voice-over narrator, {tone}: {next_narration — max 12-15 words, NO em dash}.
Audio continues: {same_ambient}, {new_sfx if any}.
{veo_negative_prompt}
```

> **POST-PROD VO:** "{same narration text}" — fallback for B-Roll extensions.

### Multi-Character Presenter Scene (Sequential Dialogue)

When 2+ characters have dialogue in the same scene:

```
~{duration}s, {resolution}, {aspect_ratio}.
Camera: {camera_movement — typically wider shot to fit both characters}, {speed}.
Character {A} and Character {B} in {setting from scene}.
Maintain visual continuity with reference frame character appearances throughout clip.
Speaker A says: {dialogue line — max 8-15 words, NO em dash}.
[0.3-0.5s pause — Character {B} reacts with {micro-expression}]
Speaker B says: {response — max 8-15 words, NO em dash}.
Both characters: {shared micro-movements — subtle breathing, natural eye contact shifts}.
SFX: {sound effects from script}.
Ambient: {background atmosphere + music direction}.
{veo_negative_prompt from global-promo-config.md}
Maintain visual continuity with reference frame appearances for all characters.
```

**Multi-character dialogue rules:**
- Use `Speaker A says:` / `Speaker B says:` — NEVER real person names
- NO face ref filenames in VEO prompts — identity comes from start frame / ingredient images

**Required Reference Images (upload all to `{project}/ref/` folder — place below heading, before prompt body):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{A}-face.png` | {Character A name} face | ⬜ |
| 2 | `cast-c{B}-face.png` | {Character B name} face | ⬜ |
| 3 | `cast-c{A}-costume.png` | {Character A} costume | ⬜ (if institutional) |
| 4 | `cast-c{B}-costume.png` | {Character B} costume | ⬜ (if institutional) |
| 5 | `env-{location}.png` | Environment | ⬜ |
```

**CRITICAL VEO LIP SYNC RULE:** VEO handles 1 speaker at a time.
- For dialogue exchange: sequential delivery with reaction pauses, NOT simultaneous speaking
- Max 2 dialogue turns per 8s clip (each turn 3-6s)
- If scene needs more dialogue turns: use Extend or split into multiple clips

### Multi-Character B-Roll Scene (Voiceover, No Dialogue)

```
~{duration}s, {resolution}, {aspect_ratio}.
Camera: {camera_movement}, {speed}.
Character {A} and Character {B} {action from script — e.g., walking through facility, reviewing dashboard}.
Maintain visual continuity with reference frame character appearances throughout clip.
{ambient_motion — characters interact naturally with environment}.
Voice-over narrator, {tone}: {narration text from script — max 12-15 words per 8s, NO em dash}.
SFX: {sound effects}.
Ambient: {background music + atmosphere}.
{veo_negative_prompt}
Maintain visual continuity with reference frame appearances for all characters.
```

> **POST-PROD VO:** "{same narration text}" — fallback if VEO narrator layer fails.

**Multi-char B-Roll rules:**
- `Voice-over narrator, {tone}: text` — NOT `Voiceover:`, NOT `[Name] says:`
- NO face ref filenames in VEO prompt — identity from start frame / ingredient images
- Always include POST-PROD VO backup

**Required Reference Images (upload all to `{project}/ref/` folder — place below heading, before prompt body):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{A}-face.png` | {Character A name} face | ⬜ |
| 2 | `cast-c{B}-face.png` | {Character B name} face | ⬜ |
| 3 | `cast-c{A}-costume.png` | {Character A} costume | ⬜ (if institutional) |
| 4 | `cast-c{B}-costume.png` | {Character B} costume | ⬜ (if institutional) |
| 5 | `product-{name}.png` | Product shot | ⬜ (if product visible) |
| 6 | `env-{location}.png` | Environment | ⬜ |
```

---

## 5. Scene Transition Handling

### Between Different Scenes (Cut/Dissolve/etc.)

1. Check transition type from script A/V direction
2. Add transition end instruction to PREVIOUS scene's VEO prompt:

| Transition | VEO Instruction |
|-----------|-----------------|
| Cut | `Hard cut, immediate switch` |
| Push-In | `End with slow dolly push-in` |
| Pull-Back | `End with gentle pull-back` |
| Whip-Pan | `Fast horizontal pan with motion blur` |
| Fade to Black | `Slow opacity fade to black over 12 frames` |
| Dissolve | `Cross-dissolve preparation, hold final pose` |
| Match Cut | `End framing matches first frame of next shot` |

3. **CONDITIONAL: Last Frame → Next Scene Anchor (ENVIRONMENT-GATED per v2.2.0).** For sequential scene pairs WHERE env(N) == env(N+1) (same location, same lighting), you MUST:
   1. Export the END frame output of Scene N as `ref/scene-{NN}-end.png`.
   2. Inject `scene-{NN}-end.png` (bare filename, NO ref/ prefix) as the FIRST reference image in Scene N+1's start frame prompt.
   3. Include it in Scene N+1's Required Reference Images upload table as row 11.

   **HARD CUT case (env differs — indoor↔outdoor, kopitiam↔yard, yard↔warehouse, golden hour↔morning):** DROP `scene-{NN}-end.png` cross-ref ENTIRELY. Visual continuity carried by text SUBJECT spec + standalone identity refs (cast-c{N}-face.png) + standalone prop refs. Character/prop continuity ALONE is NOT sufficient justification to keep cross-ref — environment is the SOLE gating criterion.

   See `global-promo-config.md` §27 for full conditional rule + decision algorithm + validator C4. **Old blanket "MUST reference" behavior is deprecated in v2.2.0.**

   **Why env-gated:** NB2 treats `scene-NN-end.png` as a compositional template (it tries to match lighting, color grading, framing from the reference). When env differs, this CONFUSES the model into mixing wrong-location elements (e.g., yard pavement texture bleeding into customer warehouse floor). Text-only continuity is cleaner for hard cuts.

#### Few-Shot: Dependency Chain

**BAD — header block refs, no previous scene reference:**
```
#### START Frame → ref/scene-15-start.png
Using reference image cast-c1-face.png for driver face.
Using reference image vehicle-truck.png for truck.

Photorealistic medium shot at the stockpile area...
```
WHY BAD: (1) Scene 15 has no reference to Scene 14 end frame — environment, lighting, and character position will be inconsistent. (2) Reference filenames are in a header block ABOVE the description, not inline with the elements they describe — NB2 receives filenames but doesn't know WHERE each one goes.

**GOOD — inline refs, previous scene anchored:**
```
#### START Frame → ref/scene-15-start.png
Photorealistic medium shot — continuation from scene-14-end.png — maintaining character position, lighting, and environment from previous scene. The SAME stockpile environment. The driver (Maintain exact facial identity from reference image: cast-c1-face.png) stands beside the truck — EXACTLY matching vehicle-truck.png — at the weighbridge...
```
WHY GOOD: (1) Scene 14 end frame anchors continuity inline. (2) Every ref filename appears INSIDE the scene description, next to the element it applies to. (3) No header block — NB2 knows exactly which ref goes with which element.

### Within Same Scene (Extension)

1. Hold pose for final 0.5s of current clip
2. Maintain consistent camera movement speed
3. Avoid new characters entering in final second
4. Keep audio element present in final second
5. Resolution lock: 720p across ALL segments in chain

---

## 6. Audio Layer Planning

For each scene, explicitly plan all 3 audio layers:

| Scene Type | Layer 1: Dialogue | Layer 2: SFX | Layer 3: Ambient |
|------------|-------------------|--------------|------------------|
| Presenter (lip sync) | `Host says: {text}` | `SFX: {effect}` | `Ambient: {atmosphere}` |
| B-Roll (voiceover) | `Voice-over narrator, {tone}: {text}` | `SFX: {effect}` | `Ambient: {music + atmosphere}` |
| Product demo | `Host says: {text}` or VO | `SFX: UI clicks, tech sounds` | `Ambient: subtle music` |
| Testimonial | `Speaker says: {text}` | — | `Ambient: soft room tone` |

**Critical Rules:**
- ALL 3 layers must be specified (or explicitly marked as silent)
- Unspecified audio = VEO guesses random sounds
- No silent B-Roll — every B-Roll needs `Voice-over narrator` + `> POST-PROD VO:` backup
- Use `Voice-over narrator, [tone]: text` NOT bare `Voiceover:` (lip-syncs to visible char)
- Use `Host says:` / `Presenter says:` — NEVER real person names (safety filter)
- NO em dash `—` in dialogue/voiceover text — replace with `,` or `. `
- Pronunciation: spell phonetically for non-English words
- Always add: `no subtitles, no audience sounds`
- Dialogue uses colon syntax (NEVER quotation marks)

---

## 7. Quality Audit Checklist (Per Scene)

Before finalizing each scene's prompts:

### 7A. Technical Checklist
- [ ] NB2 aspect ratio matches VEO target ratio
- [ ] VEO mode is correct (Ingredients ≠ First+Last Frame)
- [ ] Face-dominant scenes use single I2V (NOT First+Last Frame)
- [ ] Audio all 3 layers specified
- [ ] Dialogue: `Host says:` (generic role, NO real names, NO em dash)
- [ ] Voiceover: `Voice-over narrator, [tone]: text` (NOT bare `Voiceover:`)
- [ ] Every B-Roll has VO narration + `> POST-PROD VO:` backup
- [ ] Resolution = 720p if extending, 1080p if final-only
- [ ] Creator reference phrase verbatim (if presenter scene)
- [ ] Wardrobe consistent across all clips in scene
- [ ] Lighting Kelvin consistent between start/end frames
- [ ] Central 60% rule for critical action
- [ ] Face >30% frame for lip sync scenes
- [ ] Extension prompt references previous clip context
- [ ] Transition instruction added to scene-ending clip
- [ ] All cast members' reference phrases used verbatim (not generic "creator")
- [ ] Multi-character NB2 scenes specify EACH character's identity ref (cast-c{N}-face.png — bare filename, NO ref/ prefix)
- [ ] VEO prompts use generic continuity (NO face ref filenames)
- [ ] Character hierarchy correct (Pemeran Utama prominent, Pendamping supporting)
- [ ] Costume matches institution ref (if institutional) — cast-c{N}-costume.png (bare filename, NO ref/ prefix)
- [ ] ref-manifest.md validated before generating any prompts (Phase 3.5 gate)
- [ ] Max 3 characters per frame (4+ use shot/reverse-shot)
- [ ] VEO dialogue scenes: 1 speaker at a time, sequential delivery
- [ ] **All reference images INLINE in NB2 prompt text** — each filename appears next to the element it describes, NOT in a separate header block above the prompt
- [ ] **NB2 reference image injection syntax used INLINE** — identity lock inside SUBJECT line (`{Name} (Maintain exact facial identity from reference image: cast-c{N}-face.png) — {description}`), environment/vehicle/object refs inline with their elements (`EXACTLY matching {filename}.png`)
- [ ] **Required Reference Images table included directly BELOW each prompt heading, BEFORE prompt body** (NB2 and VEO) — bare filenames only, NO ref/ prefix
- [ ] **(v2.2.0 env-gated)** Scene N+1 start frame references Scene N end frame output (`scene-{NN-1}-end.png`) ONLY IF env(N) == env(N+1). For hard cuts (different env), DROP cross-ref — text-only continuity per global-promo-config.md §27.
- [ ] **(v2.2.0 conditional)** Previous scene output included in Required Reference Images upload table (row 11) ONLY when env continues. Hard cut scenes have row 11 dropped entirely.
- [ ] **(v2.2.0 max-5 rule)** Total inline references per prompt ≤5 (combined faces + bodies + costumes + objects + envs + UI). See global-promo-config.md §26.4. If >5 needed → split scene OR consolidate via composite asset.
- [ ] **(v2.2.0 uniqueness)** All Phase 4A assets in upload table pass UNIQUE filter (faces, logos, custom UI, industry-specific equipment). COMMON items (generic phone, generic kopi gelas, generic pavement) should NOT have ref files — render from text. See global-promo-config.md §26.

### 7B. Scene Logic Realism Checklist (9-Point)

Every NB2 and VEO prompt MUST pass this 9-point realism check. AI defaults to "stock photo generic" — these checks prevent it.

| # | Check | What to Verify | Common AI Failure |
|---|-------|---------------|-------------------|
| 1 | **Environment Accuracy** | Location matches cultural research (Step 3.5.2a). Architecture, vegetation, sky, road surface, signage all match the real location. If env-{location}.png exists in ref/ folder, prompt references it (bare filename). | Generic "modern city" instead of specific Dumai pelabuhan / Surabaya industrial zone |
| 2 | **Human Behavior Realism** | People in scene perform plausible actions for context. Workers work, supervisors supervise, operators operate. Body language matches role and situation. No "standing and smiling at camera" in action scenes. | Everyone poses awkwardly. Worker holds tool wrong. Manager does manual labor. |
| 3 | **Data/Display Consistency** | Dashboard numbers, ANPR readings, tracking data, screen content are internally consistent and plausible. If Scene 5 shows "98.7% accuracy," Scene 12 must not show "95.2%" unless script explains the change. | Random numbers on every screen. Inconsistent metrics across scenes. |
| 4 | **Uniform & Rank Accuracy** | Institutional uniforms match rank/role. Supervisor ≠ operator uniform. Manager badge ≠ frontline badge. Epaulettes, stripes, helmet colors, safety vest colors match institutional hierarchy. | Everyone wears identical uniform regardless of rank. Captain has no stripes. |
| 5 | **Explicit Negatives** | Prompt explicitly states what should NOT appear. If indoor scene: "no outdoor elements." If nighttime: "no sunlight." If clean facility: "no rust, no litter, no peeling paint." AI fills gaps with random elements. | AI adds windows to underground rooms. Puts sunshine in night scenes. Makes new facility look old. |
| 6 | **Reference Photo Enforcement** | Every visual element with a reference image in ref/ folder uses it (bare filename in prompt, NO ref/ prefix). No text-only descriptions for elements that have reference photos. User photos = ground truth, NEVER override. | AI ignores uploaded gate photo and generates random fantasy gate instead. |
| 7 | **Timeline & Shift Consistency** | Time of day matches across connected scenes. If establishing shot is "dawn," subsequent scenes keep dawn lighting. Shift patterns (pagi/siang/malam) consistent with narrative. Workers wear appropriate PPE for time/shift. | Dawn establishing shot followed by harsh midday lighting in the next scene. Night shift workers in daylight. |
| 8 | **Prop/Object Scale Accuracy** | All handheld props specified with: (a) exact dimensions in cm/mm, (b) real-world analogy ("like a 7-Eleven receipt"), (c) proportion relative to hand/body ("narrower than a credit card"), (d) explicit negative for wrong sizes ("NOT A4, NOT letter size") |

#### Few-Shot: Prop Scale

**BAD — no size specification:**
```
The officer hands the routing slip to the driver through the window.
```
WHY BAD: "Routing slip" gives no size information. NB2 will generate it as A4 paper.

**GOOD — full size specification:**
```
The officer pinches a tiny thermal receipt slip between thumb and index finger — 5.7cm wide, ~15cm long, like a convenience store cash register receipt or ATM receipt. The slip is narrower than a credit card and LESS THAN the width of the officer's palm. NOT a sheet of paper, NOT A4, NOT letter size.
```
WHY GOOD: 4 anchors — exact cm, real-world analogy, hand proportion, explicit negative.

| 9 | **Domain Context Populated** | DOMAIN CONTEXT line contains specific equipment names, process steps, and local details from strategic-brief.md Domain Knowledge section — NOT generic placeholders or template text |

#### Few-Shot: Domain Context

**BAD — generic placeholder:**
```
DOMAIN CONTEXT: Industrial port facility with loading equipment.
```
WHY BAD: Could be any port in any country. NB2 will generate generic stock-photo environment.

**GOOD — specific from research:**
```
DOMAIN CONTEXT: Pelabuhan Pelindo 1 Cabang Dumai, Riau. Gate booth with KPLP officer in dark blue Pelindo uniform. ANPR camera system (Hikvision) auto-reads plate "BM" prefix (Riau plates). Weighbridge: Mettler Toledo 80-ton capacity. Cangkang kelapa sawit = dark brown broken shell fragments 2-5cm, NOT whole palm fruits.
```
WHY GOOD: Named brands, local plate prefix, specific equipment, visual description of commodity.

**How to apply per prompt:**

```
FOR each NB2/VEO prompt:
    1. Environment: Does location match cultural research? Does it reference ref/env-*?
    2. Behavior: Are character actions plausible for their role?
    3. Data: Are any on-screen numbers consistent with other scenes?
    4. Uniform: Does rank match uniform details? (if institutional)
    5. Negatives: Add "No {inappropriate element}" for at least 2 potential AI failures.
    6. Ref photos: Every element with ref/ file → prompt references it (not text-only).
    7. Timeline: Does time-of-day/lighting match scene before and after?
```

### 7C. Narrative Arc Consistency Checklist

Connected scenes MUST explicitly reference each other. Without cross-scene connections, AI generates isolated frames with no narrative flow.

**Rule: Every scene prompt must include a `NARRATIVE CONTEXT:` block.**

```
NARRATIVE CONTEXT:
  Previous: Scene {N-1} — {1-line summary of what happened}.
  This scene: {what happens now and WHY — cause from previous scene}.
  Next: Scene {N+1} — {what this scene sets up}.
  Visual breadcrumb: {shared element that connects to adjacent scenes — same prop, same screen, same document, same location angle}.
  Emotional arc: {emotion at start of this scene} → {emotion at end}.
```

| Rule | Details | Why |
|------|---------|-----|
| **Name the connection** | Each scene prompt states how it connects to the previous and next scene. Not just "continues," but WHAT continues and WHY. | Without explicit connection, AI generates scenes as isolated stock footage. |
| **Visual breadcrumbs** | At least ONE shared visual element between adjacent scenes. Can be: same prop, same screen content, same document, same background landmark, same character holding same object. | Gives the viewer's eye an anchor across cuts. Without it, each scene feels disconnected. |
| **Cause-effect chains** | If Scene 5 shows a problem, Scene 6 must reference that specific problem (not a generic "problem"). Use exact language: "The alert from Scene 5 triggers the supervisor response in Scene 6." | AI doesn't understand narrative unless you spell it out. |
| **Shared environment refs** | Connected scenes in the same location MUST use the same `ref/env-{location}.png`. Different camera angles of SAME location, not different generated environments. | Without shared ref, AI generates subtly different versions of "the same place." |
| **Character state continuity** | If character was sweating in Scene 3 (outdoor, 33°C), they should still show signs of heat in Scene 4 (same location). If character received news in Scene 7, expression in Scene 8 must reflect it. | AI resets character state between scenes unless explicitly told. |
| **Name labels in UI scenes** | If dashboard shows employee name "Budi" in Scene 5, ANY subsequent dashboard scene must show "Budi" (not random name). Localize ALL on-screen text per `narration_language`. | AI randomizes text content per generation. Pin it down in every prompt. |

### 7D. Character Costume Tracking Table

**MANDATORY for every project with 2+ characters.**

Before generating ANY scene keyframe prompt (Phase 4B), build this tracking table from `cast-profile.md`:

| Character | Role | Default Costume (verbatim from cast-profile.md) | Scene(s) with Costume Change | Changed Costume | Script Justification |
|-----------|------|------------------------------------------------|------------------------------|-----------------|---------------------|
| {name} | {role} | {EXACT text from cast-profile.md} | — | — | — |

**Rules:**
1. The "Default Costume" column MUST be copied **verbatim** from `cast-profile.md` — never paraphrase, never abbreviate, never add details not in the profile.
2. Every NB2/VEO prompt MUST pull the costume description from this table's "Default Costume" column (or "Changed Costume" if applicable for that scene).
3. A costume change is ONLY allowed if the script explicitly calls for it (e.g., time skip, location change from office to field). The "Script Justification" column MUST be filled.
4. If the same character appears in 3+ consecutive scenes with the same costume, use the EXACT SAME text string — do not rephrase for variety.
5. Cross-check: After all prompts are written, grep all costume descriptions for each character. Any variation that is not in the tracking table = rejection.

#### Few-Shot: Costume Consistency

**BAD — paraphrased costume:**
Scene 15 prompt: "QC Inspector wearing a high-vis vest and safety helmet"
Scene 17 prompt: "QC Inspector in white lab coat with safety equipment"
WHY BAD: Same character, different costume text. NB2 generates completely different outfits.

**GOOD — verbatim from tracking table:**
cast-profile.md says: "high-visibility neon yellow/green safety vest with reflective strips over grey work shirt, safety helmet, work boots"
Scene 15 prompt: "QC Inspector (high-visibility neon yellow/green safety vest with reflective strips over grey work shirt, safety helmet, work boots)"
Scene 17 prompt: "QC Inspector (high-visibility neon yellow/green safety vest with reflective strips over grey work shirt, safety helmet, work boots)"
WHY GOOD: Identical text string in both scenes — copy-pasted from tracking table, zero variation.

---

## 8. Full Production Plan Template (--full mode)

```markdown
# Video Production Plan — {Video Title}

## Strategic Brief
{From Phase 1 output}

## Cast Summary
{From cast-profile.md}

| # | Name | Role | Identity Lock | Ref Files |
|---|------|------|---------------|-----------|

## Reference Manifest
{From ref-manifest.md — Phase 3.5 validated}
Total refs: {N}/{N} ✅

## A/V Script Summary
{Key beats and timing from Phase 2}

## Scene Breakdown
{Scene plan table from Section 2}

## Per-Scene Production

### Scene {N}: {Beat Name} ({start_time}–{end_time})

**Storyboard:** {1-2 sentence visual description}
**VEO Mode:** {Frame / Ingredients / Extend}
**Resolution:** {720p / 1080p}
**Duration:** {Xs} = {1 gen} + {N extends}
**Audio Type:** {Presenter lip sync / B-Roll voiceover / Music only}

#### NB2 Start Frame

**Required Reference Images (upload all to `{project}/ref/` folder):**
| # | Filename | Content | Embedded in Prompt? | Upload Status |
|---|----------|---------|--------------------|----|
| 1 | `cast-c1-face.png` | {Character 1 name} face — identity lock | ✅ Yes | ⬜ |
| 2 | `cast-c2-face.png` | {Character 2 name} face — identity lock | ✅ Yes | ⬜ |
| 3 | `product-{name}.png` | Product shot — scene context | ✅ Yes | ⬜ |
| 4 | `env-{location}.png` | Environment — background | ✅ Yes | ⬜ |
| 5 | `costume-{institution}.png` | Institutional uniform — wardrobe ref | ✅ Yes | ⬜ |

```
{full NB2 prompt}
```

#### NB2 End Frame (if Frame mode)
```
{full NB2 prompt}
```

#### VEO Prompt
```
{full VEO prompt}
```

#### Extension Prompt (if applicable)
```
{full extension prompt}
```

---

## Post-Production Checklist
- [ ] No identity drift across all clips
- [ ] Lighting consistent across all segments
- [ ] Audio seamless at extension joints
- [ ] No edge hallucination from ratio mismatch
- [ ] All transitions smooth between scenes
- [ ] Total duration within 120-180s target
- [ ] Narration timing matches dialogue constraints
```

---

## 9. Reference Manifest Generation (Phase 3.5)

### Auto-Derive Algorithm

**INPUT:** scene-plan.md + cast-profile.md + strategic-brief.md

```
# Step 1: Cast references
FOR each character in cast-profile.md:
    IF role == "Pemeran Utama":
        ADD ref/cast-c{N}-face.png    (MANDATORY)
        ADD ref/cast-c{N}-body.png    (MANDATORY)
        IF institution_detected:
            ADD ref/cast-c{N}-costume.png (MANDATORY)
    IF role == "Pemeran Pendamping":
        ADD ref/cast-c{N}-face.png    (MANDATORY)

# Step 2: Environment references
locations = []
FOR each scene in scene-plan.md:
    EXTRACT location from visual description
    IF location NOT IN locations:
        locations.append(location)
        ADD ref/env-{location-slug}.png (MANDATORY)

# Step 3: Product references
products = []
FOR each scene in scene-plan.md:
    IF scene mentions product by name:
        IF product NOT IN products:
            products.append(product)
            ADD ref/product-{product-slug}.png (MANDATORY)

# Step 4: Brand asset references
brand_assets = []
FOR each scene in scene-plan.md:
    IF scene mentions brand logo, UI, dashboard, packaging:
        IF asset NOT IN brand_assets:
            brand_assets.append(asset)
            ADD ref/brand-{asset-slug}.png (MANDATORY)

# Step 5: Institution costume (shared)
IF institution_detected:
    ADD ref/costume-{institution-slug}.png (MANDATORY)
```

**OUTPUT:** ref-manifest.md

### Manifest Output Format

```markdown
# Reference Manifest — {Video Title}

## Overview
| Total Required | {N} images |
| Validation Mode | Hard Block (cannot proceed without 100%) |
| Naming Convention | Per global-promo-config.md Section 11 |

## Cast References

### Character 1: {Name} ({Role}) — {FULL/MINIMAL} REF
| Filename | Content | Used in Scenes | Status |
|----------|---------|----------------|--------|
| ref/cast-c1-face.png | Face front view | {scene_list} | ⬜/✅ |
| ref/cast-c1-body.png | Full body | {scene_list} | ⬜/✅ |
| ref/cast-c1-costume.png | {Institution} uniform | {scene_list} | ⬜/✅ |

(repeat per character)

## Product References
| Filename | Content | Used in Scenes | Status |
|----------|---------|----------------|--------|
| ref/product-{name}.png | {description} | {scene_list} | ⬜/✅ |

## Environment References
| Filename | Content | Used in Scenes | Status |
|----------|---------|----------------|--------|
| ref/env-{location}.png | {description} | {scene_list} | ⬜/✅ |

## Brand Assets
| Filename | Content | Used in Scenes | Status |
|----------|---------|----------------|--------|
| ref/brand-{asset}.png | {description} | {scene_list} | ⬜/✅ |

## Costume/Uniform (Institution: {name})
| Filename | Content | Used in Scenes | Status |
|----------|---------|----------------|--------|
| ref/costume-{institution}.png | {uniform_type} front view | All cast scenes | ⬜/✅ |

## Validation Summary
- Total required: {N}
- Uploaded: {M}/{N}
- Status: ❌ BLOCKED / ✅ PASSED
```

### Scene-to-Ref Mapping

After manifest is built, create a reverse mapping showing which refs each scene needs:

```markdown
## Scene-to-Reference Map

| Scene # | Beat | Characters | Product | Environment | Brand | Costume |
|---------|------|-----------|---------|-------------|-------|---------|
| 1 | Pattern Interrupt | — | — | ref/env-outdoor.png | — | — |
| 2 | Hook | c1, c3 | — | ref/env-studio.png | — | ref/costume-kai.png |
| 3 | Foreshadow | c1 | ref/product-hero.png | ref/env-studio.png | — | ref/costume-kai.png |
| ... | ... | ... | ... | ... | ... | ... |
```

This map is used in Phase 4 to ensure each scene's NB2 prompts reference the correct files.

---

## 10. Tone-to-Cinematography Mapping

Reference `global-promo-config.md` Section 13 for the full Tone Impact Matrix. This section provides operational lookup for Phase 4 (NB2) and Phase 5 (VEO).

### Tone → Lighting Setup

| Tone | Lighting Ratio | Kelvin | Atmosphere | Film Stock Override |
|------|---------------|--------|------------|-------------------|
| Humorous | 2:1 (bright, flat) | 5600K (daylight) | Clean, bright | Kodak Portra 400 (warm, friendly) |
| Serious | 4:1+ (dramatic) | 3200K (tungsten) | Heavy haze, shadows | Kodak Vision3 500T (default) |
| Professional | 2:1 (clean, even) | 4500K (neutral) | Clean, minimal | Kodak Ektar 100 (sharp, precise) |
| Inspirational | 3:1 (warm glow) | 3500K (golden) | Light haze, warm | Kodak Portra 400 (warm) |
| Casual | 2:1 (natural) | 5600K (daylight) | Natural, minimal | Fujifilm Pro 400H (soft, natural) |
| Edgy | 6:1+ (harsh contrast) | Mixed warm/cool | Smoke, grit | Kodak T-MAX 3200 (grainy, raw) |

### Tone → Camera Style

| Tone | Default Shot | Lens | Movement | Angle |
|------|-------------|------|----------|-------|
| Humorous | MS/MWS (wider) | 35mm | Handheld-style, bounce | Eye-level, playful |
| Serious | CU/MCU (tight) | 85mm | Slow dolly/push | Eye-level to low |
| Professional | MCU/MS (standard) | 50mm | Steady, precise | Eye-level |
| Inspirational | MS to WS (sweeping) | 35mm | Crane/jib, reveal | Low angle (heroic) |
| Casual | MCU/MS | 50mm | Gentle handheld | Eye-level |
| Edgy | CU/ECU (extreme) | 24mm wide | Fast whip pan, dutch | Dutch tilt 10-15° |

### Tone → Audio Direction

| Tone | Music Style | SFX | Ambient |
|------|------------|-----|---------|
| Humorous | Upbeat, quirky, pizzicato | Comic timing whooshes, playful pops | Light, airy room tone |
| Serious | Orchestral, minimal, sparse | Impact hits, silence beats, bass drops | Deep rumble, tension drone |
| Professional | Corporate ambient, clean synth | Subtle UI clicks, clean transitions | Quiet office hum |
| Inspirational | Swelling strings, piano, emotional build | Risers, swells, chime accents | Open air, nature |
| Casual | Acoustic guitar, chill lo-fi | Natural sounds, soft transitions | Cafe ambiance, street life |
| Edgy | Electronic, aggressive beats, distortion | Glitch effects, bass stabs, static | Industrial hum, urban noise |

### Tone → Character Expression (NB2)

| Tone | Default Expression | Eye Direction | Micro-movements |
|------|-------------------|---------------|-----------------|
| Humorous | Warm smile, playful, expressive | Direct to camera, wink | Active gestures, head tilts |
| Serious | Stern, determined, intense | Direct to camera, unwavering | Minimal, controlled |
| Professional | Confident, neutral, composed | Direct, slight nod | Measured hand gestures |
| Inspirational | Hopeful, inspired, eyes bright | Upward/forward, visionary | Open palms, expansive |
| Casual | Relaxed, friendly, natural | Varied, conversational | Natural fidgets, nods |
| Edgy | Intense, challenging, sharp | Piercing direct stare | Sharp head turns, pointed |

### How to Apply

When generating NB2/VEO prompts:
1. Read `video_tone` from strategic-brief.md
2. Look up tone in tables above
3. Override default cinematography values with tone-specific values
4. Inject tone atmosphere keywords into VEO prompt
5. Apply tone expression to character NB2 prompts

---

## 11. Ref Image NB2 Prompt Templates

Templates for generating reference images when user doesn't have them. Used in Phase 3.5 Step 3.5.2b.

Reference `global-promo-config.md` Section 15 for NB2 defaults (ref images use neutral lighting, clean bg, 4K, CFG 6.0, Denoise 0.40, Thinking High).

**CRITICAL: Follow dependency order from `global-promo-config.md` Section 17.**
Generate in this order: Tier 1 (face + product + env) → Tier 2 (body) → Tier 3 (costume) → Tier 4 (scene images). Each downstream tier MUST inject upstream refs in its prompt.

### Cast Face Reference Template — TIER 1 (no upstream dependency)

```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: {ethnicity} {gender}, {age_range}, {key_features from cast-profile.md}.
Portrait, front view, looking directly at camera.
EXPRESSION: Neutral, natural, relaxed.
BACKGROUND: Clean studio white, seamless.
LIGHTING: Neutral diffused soft light, even illumination, no dramatic shadows.
CAMERA: Medium close-up, 85mm f/2.8, eye-level.
TECHNICAL: 16:9 landscape, 4K resolution, CFG 6.0, Denoise 0.40, Thinking High.
No accessories obscuring face. Hair naturally styled. Skin texture visible.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/cast-c{N}-face.png`
**Dependency:** None — this is the foundational identity anchor. Generate FIRST.

### Cast Body Reference Template — TIER 2 (depends on face ref)

```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: {ethnicity} {gender}, {age_range} (Maintain exact facial identity from reference image: cast-c{N}-face.png) — {key_features from cast-profile.md}.
Full body standing pose, feet visible, arms relaxed at sides.
WARDROBE: {wardrobe from cast-profile.md — e.g., "navy blazer, white open-collar shirt"}.
EXPRESSION: Neutral, confident posture.
BACKGROUND: Clean studio white, seamless.
LIGHTING: Neutral diffused soft light, even from head to toe.
CAMERA: Full body shot, 50mm f/4, eye-level.
TECHNICAL: 16:9 landscape, 4K resolution, CFG 6.0, Denoise 0.40, Thinking High.
Full wardrobe clearly visible. Natural standing pose.
Face MUST match cast-c{N}-face.png exactly — same person, same features.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/cast-c{N}-body.png`
**Dependency:** ref/cast-c{N}-face.png MUST exist before generating this.

**Required Upstream Reference:**
```markdown
| # | Reference File | Content | Status |
|---|---------------|---------|--------|
| 1 | ref/cast-c{N}-face.png | Face identity anchor (Tier 1) | Must be ✅ |
```

### Cast Costume/Uniform Reference Template — TIER 3 (depends on face + body ref)

```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: {ethnicity} {gender}, {age_range} (Maintain exact facial identity from reference image: cast-c{N}-face.png), body proportions matching cast-c{N}-body.png — wearing official {institution} uniform.
Front view, full uniform visible from collar to shoes.
DETAILS: {uniform_color}, {emblem/badge description — position, colors, text if known}.
{Rank insignia if applicable}. {Hat/headwear if applicable}.
ACCESSORIES: {ID badge, belt, shoes specific to institution}.
BACKGROUND: Clean neutral gray.
LIGHTING: Neutral diffused, even illumination to show all uniform details.
CAMERA: Full body, 50mm f/4, eye-level.
TECHNICAL: 16:9 landscape, 4K resolution, CFG 6.0, Denoise 0.40, Thinking High.
Face and body MUST match cast-c{N}-face.png and cast-c{N}-body.png — same person in uniform.
NOTE: AI cannot generate accurate institutional logos/badges — describe placement and colors instead.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/cast-c{N}-costume.png`
**Dependency:** ref/cast-c{N}-face.png AND ref/cast-c{N}-body.png MUST exist before generating this.

**Required Upstream References:**
```markdown
| # | Reference File | Content | Status |
|---|---------------|---------|--------|
| 1 | ref/cast-c{N}-face.png | Face identity anchor (Tier 1) | Must be ✅ |
| 2 | ref/cast-c{N}-body.png | Body proportions (Tier 2) | Must be ✅ |
```

### Product Reference Template — TIER 1 (no upstream dependency)

```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: {product_name} — {brief product description from strategic-brief.md}.
Hero angle, {product_orientation — e.g., "three-quarter view showing interface"}.
{Key visual features — screen content, buttons, packaging details}.
BACKGROUND: Clean white or light gradient.
LIGHTING: Soft commercial lighting, subtle shadow for depth, even illumination.
CAMERA: Product shot, {lens based on product size — 50mm for small, 35mm for large}, f/5.6.
TECHNICAL: 16:9 landscape, 4K resolution, CFG 6.0, Denoise 0.40, Thinking High.
Professional product photography style. No distracting elements.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/product-{name}.png`
**Dependency:** None — independent of character refs. Can be generated in parallel with Tier 1 face refs.

### Environment Reference Template — TIER 1 (depends on cultural research, not other refs)

```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: Wide establishing shot of {location}, {region}, Indonesia.
ARCHITECTURE: {cultural_architecture from strategic-brief.md Cultural Context}.
LANDMARKS: {cultural_landmarks visible in mid-ground or background}.
VEHICLES: Vehicles with {cultural_plate_code}-series license plates visible in street/parking.
PEOPLE: Background figures with {cultural_ethnicity} appearance — {cultural_physical_features}.
SKY/WEATHER: {cultural_weather — e.g., "tropical humid atmosphere, bright equatorial sun, cumulus clouds"}.
VEGETATION: {local_flora — e.g., "tropical palms, frangipani trees"}.
TIME OF DAY: {morning/midday/afternoon/evening — based on scene requirement}.
CAMERA: Wide shot, 24mm f/8, eye-level.
LIGHTING: Natural {time_of_day} light, {cultural_weather_kelvin}K.
TECHNICAL: 16:9 landscape, 4K resolution, CFG 6.0, Denoise 0.40, Thinking High.
Photorealistic, authentic Indonesian {region} atmosphere.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/env-{location}.png`
**Dependency:** Cultural research data (Step 3.5.2a) must be completed first. No dependency on other ref images. Can be generated in parallel with Tier 1 face/product refs.

### Brand Logo — CANNOT GENERATE

```
⚠️ Brand logo CANNOT be reliably generated by AI image models.
Logos require exact typography, specific color codes, and precise geometry
that AI models cannot reproduce accurately.

INSTRUCTION TO USER:
"Brand logo tidak bisa di-generate oleh AI. Silakan provide file logo asli
dalam format PNG (transparent background preferred) ke: ref/brand-{name}.png"

If user insists on AI generation, warn:
"Logo yang di-generate AI TIDAK akan akurat — typography, warna, dan proporsi
akan berbeda dari logo asli. Sangat direkomendasikan pakai file logo yang sudah ada."
```

### Vehicle Asset Template — TIER 1 (no upstream dependency)

For vehicles that appear in 2+ scenes (auto-detected by recurring element algorithm).

```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: {vehicle_type} {brand/model if known} — {color}, {condition}, {cargo if visible}.
{Specific identifying features — license plate region code from cultural research, damage marks, stickers, cargo type visible}.
Three-quarter front view, slightly elevated angle to show full vehicle profile.
CARGO: {If applicable — e.g., "bed loaded with dark brown cangkang kelapa sawit pieces, match exact cargo texture from reference image: product-closeup-{name}.png"}.
BACKGROUND: Clean neutral (light gray road surface, minimal background).
LIGHTING: Neutral diffused, even illumination showing all vehicle details.
CAMERA: Medium wide shot, 35mm f/5.6, slightly elevated angle.
TECHNICAL: 16:9 landscape, 4K resolution, CFG 6.0, Denoise 0.40, Thinking High.
Photorealistic, industrial/commercial vehicle photography style.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/vehicle-{type}-{name}.png`
**Dependency:** None (unless cargo references a product closeup — then depends on that product ref).

### Object/Equipment Asset Template — TIER 1 (no upstream dependency)

For objects/equipment that appear in 2+ scenes.

```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: {object_name} — {detailed description, manufacturer if known, digital/analog, condition}.
{Specific features — display type, labels, buttons, indicators}.
Front-facing view showing all operational details clearly.
BACKGROUND: In-situ (actual environment where object is used) OR clean neutral if standalone.
LIGHTING: Neutral diffused, even illumination, no dramatic shadows.
CAMERA: {Appropriate shot size for object}, 50mm f/5.6, eye-level.
TECHNICAL: 16:9 landscape, 4K resolution, CFG 6.0, Denoise 0.40, Thinking High.
Photorealistic, technical/industrial photography style.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/object-{name}.png`
**Dependency:** None.

### Product Closeup Template — TIER 1 (no upstream dependency)

MANDATORY for every product/commodity shown in the video. User photo STRONGLY preferred over AI generation.

```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: Extreme closeup of {product_name} — {SPECIFIC texture description}.
{If commodity: "broken/cracked pieces, NOT whole fruit/bean" or equivalent specificity}.
{Size reference: "pieces approximately {X}-{Y}cm diameter"}.
{Color specifics: "{primary color} to {secondary color}, {surface quality — glossy/matte/fibrous}"}.
{Texture details: "visible grain/fiber/crystal/crack patterns, {inner vs outer surface difference}"}.
Multiple pieces scattered naturally on {surface — e.g., "clean white surface for contrast"}.
Scale reference object if helpful (coin, ruler, hand).
CAMERA: Macro closeup, 100mm macro f/4, top-down or 45° angle.
LIGHTING: Soft commercial, even illumination to show texture detail.
TECHNICAL: 16:9 landscape, 4K resolution, CFG 6.0, Denoise 0.40, Thinking High.
⚠️ WARNING: AI-generated product images may not match real product texture/shape.
User photo is ALWAYS better for product accuracy.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/product-closeup-{name}.png`
**Dependency:** None.

### UI/Screen Composite Template — TIER N (depends on sub-elements)

For UI screens, dashboards, CCTV displays, etc. that contain other visual elements.

```
IMPORTANT: Generate in LANDSCAPE 16:9 aspect ratio. Do NOT generate portrait or square.
SUBJECT: {Screen/display type} showing operational interface.
SCREEN CONTENT:
  {Element 1}: {purpose in screen}, EXACTLY matching {sub-element-1}.png.
  {Element 2}: {purpose in screen}, EXACTLY matching {sub-element-2}.png.
  {If brand visible}: Brand logo EXACTLY matching brand-{name}.png.
UI TEXT ({language from ui_text_language config}):
  {Label 1}: "{translated text}"
  {Label 2}: "{translated text}"
  {Status}: "{translated text}"
  (Technical abbreviations stay English: ANPR, PLC, GPS, RFID)
LAYOUT: {screen layout description — split view, grid, single view with overlay}.
SCREEN TYPE: {LCD panel / CRT / tablet / monitor / outdoor digital signage}.
BACKGROUND: {Screen mounted on {wall/desk/post} in {environment}}.
CAMERA: {Shot framing screen} {lens}, {angle}.
LIGHTING: {Screen backlight + ambient}.
TECHNICAL: 16:9 landscape, 4K resolution, CFG 6.0, Denoise 0.40, Thinking High.
OUTPUT: 16:9 LANDSCAPE aspect ratio. Width > Height. Do NOT crop or change ratio.
```

**Output →** `ref/ui-{name}.png`
**Dependency:** ALL sub-elements shown in the screen MUST be generated first. Tier = max(sub-element tiers) + 1.

### Template Usage Notes

1. All ref image templates use **neutral lighting** — NOT cinematic/dramatic
2. All ref image templates use **clean backgrounds** — NOT scene environments (except object/equipment in-situ)
3. Ref images are for AI identity lock — they need CLARITY over AESTHETICS
4. Cultural context (from Step 3.5.2a) is ONLY injected into **Environment** template
5. Cast face/body templates pull description from **cast-profile.md** verbatim
6. If institution detected, costume template pulls from **global-promo-config.md** Section 12
7. **MUST follow dependency order** from `global-promo-config.md` Section 18: auto-detected tiers
8. **Downstream refs MUST inject upstream refs** — body injects face, costume injects face+body, composite injects ALL sub-elements
9. **Within each tier, generate in parallel** — all same-tier refs can be generated simultaneously
10. **Validate each tier before advancing** — all tier N refs must be ✅ before starting tier N+1
11. **Every prompt MUST have `Output →` line** — explicit filename so user knows where to save
12. **Every prompt MUST have aspect ratio triple enforcement** — first line, TECHNICAL section, last line
13. **UI text MUST be localized** — per `global-promo-config.md` Section 21 (`ui_text_language`)
14. **Product closeup: user photo > AI generation** — always ask user first
15. **Recurring elements (2+ scenes) MUST be standalone assets** — per Section 18 algorithm
