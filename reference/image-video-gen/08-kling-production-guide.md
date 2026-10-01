---
source: Kling 3.0 Production Guide — compiled from Kuaishou official docs (klingai.com), fal.ai prompting guide, NotebookLM-ready research synthesis (May 2026), 10 community/comparison guides
curated: 2026-05-16
version: 1.0
tokens: ~7200
platform: claude-projects
---

# Kling 3.0 — Video Production Reference

## Core Specs

| Param | Value | Notes |
|-------|-------|-------|
| Resolution | **720p or 1080p** (UI default). Native 4K (3840×2160) available via API on selected providers | 16-bit HDR claimed. Most production access ships 720p/1080p — 4K is API-tier feature. For promo use: 1080p default, 720p for rapid iteration |
| Frame Rate | 24, 30, 60 fps | 60fps native. 24fps cinematic. 30fps broadcast-ready HDR |
| Aspect Ratios | **16:9, 9:16, 1:1** (3 options in UI) | Fewer than Seedance (6) but covers all primary promo platforms (YouTube/LinkedIn/Reels/TikTok/Instagram square) |
| Duration | **Per-second granular: 3s, 4s, 5s, 6s, 7s, 8s, 9s, 10s, 11s, 12s, 13s, 14s, 15s** | Pick exact duration matching scene need — no padding/cropping. Multi-shot mode fits up to 6 shots within the chosen duration (typical: 6 shots in 15s) |
| Prompt Length | ~80-120 words optimal | Longer prompts ignored / hallucinated. Concise > verbose |
| Reference Inputs | 1 image (I2V), 1 video (Motion Control), 1 audio (lip-sync source) | Less than Seedance's 12-asset @ system |
| Audio | Native lip sync, 5 languages | EN, ZH, JA, KO, ES + dialects (American/British/Indian for EN; Cantonese/Beijing/Sichuanese/Taiwanese for ZH) |
| Multi-language scene | YES — characters can switch languages mid-scene | Unique — VEO and Seedance lip-sync 1 language per scene |
| Pricing | Free tier (limited) → Pro/Premier paid tiers | Mid-range cost; cheaper than Sora 2, comparable to VEO |
| Success Rate | High for realistic human motion, faces; mediocre for abstract/stylized | "Hyperrealism specialist" — Kling's training bias |

## Variants in v3.0 Family

| Variant | Use Case | When to Choose |
|---------|---------|----------------|
| **Kling 3.0** | Standard T2V / I2V | Default. Realistic scenes, product, dialogue |
| **Kling 3.0 Motion Control** | Transfer camera/character motion FROM reference video TO new scene | When you have a motion reference clip and want to apply it to new characters/environment |
| Kling 3.0 Edit | Frame-level video editing | Out of scope for this plugin (post-prod tool, not generative) |
| Kling O1 | Reasoning/research preview model | Out of scope — preview only |

**This plugin supports Kling 3.0 main + Kling 3.0 Motion Control.**

## Architecture (high-level)

Kling 3.0 uses a multi-shot diffusion transformer with native audio embedding:
- **Visual branch**: hyperrealistic motion priors (Kuaishou's edge — trained on massive short-video corpus from Kuaishou platform)
- **Audio branch**: lip-sync embedded at generation time (not post-hoc dub) — eliminates "talking head feel disconnect"
- **Multi-shot planner**: parses prompt for shot boundaries (commas, "then", numbered shots) — generates up to 6 shots in single 15s clip
- **Motion Control sub-model**: separate weights for motion transfer with Character Orientation toggle

Kling's training bias = **photoreal human realism**. Best at: faces, hands, micro-expressions, fabric, hair, skin texture, natural human movement. Weak at: stylized/anime/illustration, abstract concepts, fictional creatures.

---

## The 5-Part Prompt Formula

```
Camera Movement + Scene Setup + Subject Action + Vibe/Lighting + Time/Audio
```

This is the canonical Kling prompt structure (community-validated across 2026 guides). Each part is mandatory — skipping any part = AI hallucinates that dimension.

### Part 1: Camera Movement (CRITICAL — first or last in prompt for max weight)

Kling parses camera terms FIRST. Camera term position determines influence:
- **Beginning of prompt** = camera dominates motion (subject motion adapts to camera)
- **End of prompt** = camera follows subject (subject motion drives, camera reacts)

Recognized camera vocabulary:
- `pan left/right`, `tilt up/down`
- `dolly in`, `dolly out`, `dolly tracking`
- `orbital`, `360° orbit`, `arc shot`
- `crane up`, `crane down`, `boom shot`
- `tracking shot` (lateral, follows subject)
- `POV` (point of view from subject)
- `shot-reverse-shot` (dialogue alternation)
- `profile shot` (90° side angle)
- `macro close-up` (extreme detail, <10cm subject distance)
- `static`, `locked-off` (no camera movement)
- `handheld`, `gimbal-smooth` (movement style)

**Cinematic intent > visual description.** Write directions, not lists.

### Part 2: Scene Setup

Location, time of day, environment, weather, key props. Use established cinematic shorthand:
- `interior office, late afternoon, golden hour light through blinds`
- `rainy Jakarta street, neon reflections, after midnight`

When using I2V (image-to-video), **scene setup describes what changes from the image**, not what's already in the image. The image is the anchor.

### Part 3: Subject Action

What the subject DOES. Verbs first, modifiers second. Be specific about speed, direction, intent:
- ❌ `person walking`
- ✅ `young woman walks briskly toward camera, hands in coat pockets, breath visible in cold air`

For dialogue, use simple `Subject says: "text"` format. Word limits scale roughly **~2.5 words per second** (Kling per-second granular duration 3-15s):
- 3s → 6-8 words
- 5s → 10-13 words
- 8s → 18-22 words
- 10s → 25-30 words
- 15s → 38-45 words (multi-shot: split across shots)

Pick duration to fit your dialogue length — Kling's per-second selector means no forced padding. If a line is exactly 12 words and reads at natural pace ~5s, pick `5s` not `8s`.

### Part 4: Vibe / Lighting

Mood + light source + color grade:
- `cinematic teal-and-orange grade, soft key light from window, dramatic shadows`
- `desaturated documentary feel, harsh top light, natural skin tones`

Reference film stocks (Kling recognizes these): `Kodak Portra 400`, `Fujifilm Velvia`, `Arri Alexa LF look`.

### Part 5: Time / Audio

Time-of-day cue + audio direction:
- `dusk, distant traffic ambient, soft jazz piano underscore`
- `pre-dawn, factory hum, no music, voice-over only`

**Audio is NEVER optional in Kling 3.0** — same rule as VEO. Unspecified audio = Kling guesses (often wrong).

### Example: Full 5-part Prompt

```
Slow dolly-in from medium to close-up. Interior cargo dispatch office, late afternoon
golden hour. Young Indonesian woman (mid-30s) in navy uniform leans over dashboard
monitor, scrolling fleet data with index finger, then exhales as she spots a delayed
truck row. Cinematic teal-orange grade, warm key light from west-facing window,
soft fill, gentle shadow falloff on face. Office ambient: keyboard clicks, distant
HVAC, radio chatter on dispatch channel low in mix. 16:9, 1080p, 8s.
```

This hits all 5 parts. Note: NO em dash in dialogue/VO text (same VEO audio engine pitfall — Kling's lip-sync also mistranslates `—`).

---

## Generation Modes

### Mode 1: Text-to-Video (T2V)
Pure text prompt. Use when no reference image available. Lower control over identity — good for environmental shots, abstract atmospherics, product hero B-roll.

### Mode 2: Image-to-Video (I2V) — DEFAULT for production
Single image + text prompt. **Treat image as anchor**: it locks identity, layout, brand details, text. Prompt = HOW scene evolves, NOT what scene contains.

```
Anchor image: cast-c1-keyframe-start.png
Prompt: Subject from anchor image turns head left to look out window. Slow
push-in. Sunlight intensifies. Soft string music swells. 8s.
```

**Frame 1 quality rule**: If anchor image lighting/pose is clean → >90% success rate. Blurry or compositionally weak anchor → cascading errors in motion.

### Mode 3: First + Last Frame (Keyframe Control)
Start image + End image + text prompt. Kling interpolates between.
- Best for: faceless transitions (dashboard A → dashboard B, product unbox → reveal, environment shift)
- ⚠ **Same VEO safety filter risk**: 2 photorealistic face images → may reject as "prominent people"
- For face-dominant scenes (face >30% frame): use single I2V instead

### Mode 4: Multi-Shot Storyboard (UNIQUE TO KLING)
Single generation (any duration 3-15s, typically picked at 10-15s for max shot count) containing up to **6 distinct shots**. Shot boundaries declared via:
- Numbered markers: `Shot 1: ... Shot 2: ... Shot 3: ...`
- Transition cues: `then cut to`, `match cut to`, `whip pan to`

Use case: short-form viral hooks (TikTok/Reels 15s with 4-6 cuts), product montages, before-after sequences. **Saves render time** — one 15s job vs six separate 2-3s clips.

⚠ **Trade-off**: less control per shot. Use only when shots share environment/character. For complex narrative arcs, generate shots separately.

### Mode 5: Motion Control (separate sub-model)
Reference video + new subject/scene → applies motion FROM reference TO new render.

Key parameter: **Character Orientation**
- `Follow Video` → replicate exact spatial positioning + camera angles from reference. Best for **complex motions** (dances, action, choreography).
- `Follow Image` → maintain original character composition from image anchor. Best when **camera movement dominates** over body motion.

Use case: client gives reference clip ("make my character do THIS"), or apply VEO-generated camera arc to a Kling scene.

---

## Audio & Lip Sync (Omni Audio Engine)

### Supported Languages
| Language | Lip-sync quality | Notable dialects |
|----------|------------------|------------------|
| English | Excellent | American, British, Indian accents |
| Mandarin Chinese | Excellent | Cantonese, Beijing, Northeastern, Sichuanese, Taiwanese |
| Japanese | Very good | Standard Tokyo |
| Korean | Very good | Standard Seoul |
| Spanish | Very good | Castilian, Latin American |

### Bahasa Indonesia Status (CORRECTED v2.3.1)

**Two-tier support:**

| Use Case | Kling 3.0 Bahasa Indonesia | Workflow |
|---|---|---|
| **Voice-over narrator (off-screen, B-Roll)** | ✅ **SUPPORTED NATIVELY** | Use `Voice-over narrator, [tone]: [Bahasa Indonesia text]` directly in prompt. Kling renders ID voiceover natively — no post-prod dub needed |
| **On-screen lip-sync (face >30%, character speaks)** | ❌ NOT in 5-lang native lip-sync (EN/ZH/JA/KO/ES) | Either: (a) generate with English lip-sync + ID subtitle overlay; (b) use mouth-neutral framing (back-of-head, partial obscure) + `Voice-over narrator: [ID text]`; (c) generate visual silent + post-prod dub |

**Practical implication for Indonesian promo production:**
- B-Roll scenes (most of typical 2-3 min promo) → **fully usable with native ID VO**
- Presenter/dialogue scenes with face-front lip-sync → switch to VEO 3.1 (which supports ID lip-sync) OR reframe as VO-over-B-roll
- Same two-tier logic applies for other non-5-lang languages (Malay, Vietnamese, Thai, Tagalog)

This makes Kling **viable for full-Indonesian promo production** — not just B-roll filler.

### Mixed-Language Scene (Kling's USP)
Within ONE scene, different characters can speak DIFFERENT languages:
```
Character A (Mandarin): "我们准备好了" (We're ready)
[shot-reverse-shot]
Character B (English): "Then we go now."
```
Each character's lip-sync renders correctly. **Unique to Kling 3.0** — VEO and Seedance lock to 1 language per scene.

### Audio Prompt Syntax (matches VEO conventions for cross-platform portability)
- Presenter scene: `Host says: text` — generic role, colon syntax (NEVER real names per safety filter)
- B-Roll narration: `Voice-over narrator, [tone]: text` — never bare `Voiceover:`
- Multi-char: `Character A says: text. Character B replies: text.`
- Ambient: explicit 3rd line — `Ambient: keyboard clicks, distant phones, HVAC hum`
- Music: explicit 4th line — `Music: minimal piano underscore, low mix`
- **NEVER em dash `—` in audio text** — replace with `,` or `. ` (audio engine mistranslates, same as VEO)
- Always add: `no subtitles, no audience sounds, no text overlays`

---

## Camera Movement Library (Kling-Verified)

Kling 3.0 reliably executes these camera moves (community-tested):

| Move | Kling Prompt Phrase | Best Use |
|------|---------------------|----------|
| Static | `static locked-off shot` | Dialogue, product hero, interview |
| Slow push-in | `slow dolly-in from medium to close-up` | Tension build, emotional reveal |
| Pull-back reveal | `dolly-out from close-up to wide` | Context reveal, environmental scale |
| Lateral tracking | `tracking shot moving left, parallel to subject` | Walking, fleet shots, product line |
| Orbital | `360° orbit around subject, clockwise` | Hero product reveal, character glamour |
| Crane up | `crane shot rising from ground to bird's eye` | Establish location, journey end |
| Whip pan | `quick whip pan right` | Transition between shots in multi-shot mode |
| Handheld | `handheld follow-shot, slight bob` | Documentary feel, urgency |
| POV | `first-person POV, eye-level` | Subjective viewer experience |
| Macro CU | `macro close-up, 10cm from subject` | Texture detail, mechanical part, food |

⚠ **Avoid**: vague `camera moves`, `dynamic shot`, `cinematic angle`. These default to generic and often produce static or wrong direction.

---

## Negative Prompts (Kling-Specific Best Practice)

Kling responds VERY well to negative prompts — but **focused beats generic**.

### Universal Negative (always add)
```
deformed hands, extra fingers, asymmetrical facial features, unnatural joint angles,
sliding feet, morphing limbs, frozen mouth during speech, no subtitles, no text overlays,
no audience sounds
```

### Human Subject Negative (add when face/hands visible)
```
plastic skin, waxy texture, dead eyes, dental anomalies, mismatched eye gaze,
finger fusion, six fingers, missing thumbs
```

### Product / Brand Negative (add when logo/text visible)
```
logo distortion, text warping, brand color shifts, blurred typography, misspelled text,
warped product geometry
```

### Environment / Motion Negative (add for dynamic scenes)
```
camera shake jitter, motion blur excess, frozen background, teleporting objects,
inconsistent lighting between frames, sudden color shifts
```

⚠ **Anti-pattern**: dumping all 4 lists into one prompt = Kling overweights negatives and produces stiff, lifeless output. Pick the 1-2 relevant categories per scene. **3-5 focused negative terms outperform 20 generic ones.**

---

## VEO 3.1 Mode Selection — Cross-Platform Logic

When user picks Kling 3.0 in Phase 5, scene-by-scene mode selection follows:

```
Need to APPLY motion from existing reference clip?
├── YES → Kling 3.0 Motion Control (Character Orientation = Follow Video for complex action)
│
└── NO, generating from scratch?
    ├── Have anchor image (keyframe)?
    │   ├── YES, face >30% frame? → Kling 3.0 I2V (single image)
    │   ├── YES, faceless (dashboard, product, env)?
    │   │   ├── Want controlled A→B transition? → Kling 3.0 First+Last Frame
    │   │   └── Open-ended motion from anchor? → Kling 3.0 I2V
    │   └── NO anchor image? → Kling 3.0 T2V (text only)
    │
    └── Want multiple shots in single 15s render?
        └── Kling 3.0 Multi-Shot Storyboard (max 6 shots, shared env/character)
```

---

## Multi-Shot Storyboard Syntax

For single 15s render with up to 6 distinct shots:

```
SCENE: Cargo dispatch operations center, dawn shift change

Shot 1 (2s): Wide establishing — Indonesian dispatch supervisor enters glass-walled
control room, takes off coat. Static.

Shot 2 (3s): Medium — Supervisor sits at main dashboard. Slow dolly-in.
Says: "Status overnight?"

Shot 3 (2s): Match cut to dashboard close-up — fleet map shows 3 delayed trucks
flashing amber. Static.

Shot 4 (3s): Shot-reverse-shot — junior operator (cast-c2) looks up from monitor.
Says: "Truck 14 broke axle, others rerouted."

Shot 5 (3s): Push-in on supervisor's face — slight relief. Static eyes.

Shot 6 (2s): Wide overhead — dispatch team in coordinated action, screens glowing.
Crane up.

Audio: dispatch radio chatter low, keyboard typing, HVAC hum.
Music: building tension underscore, minimal strings.
Total: 15s. 16:9. 1080p.
```

⚠ Trade-offs:
- ✅ Single-render efficiency (vs 6 separate jobs)
- ✅ Shared character/environment consistency
- ❌ Less per-shot control
- ❌ Can't extend individual shots
- ❌ Failures require full re-render

**Use multi-shot when**: hook reel, before-after montage, viral 15s cuts.
**Avoid multi-shot when**: high-stakes hero shots, complex dialogue beats, scenes requiring extension.

---

## Common Pitfalls & Fixes

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Wrong duration assumption | Picked 8s when line was 5s of dialogue → awkward pause OR picked 5s for 10-word line → rushed delivery | Kling has per-second selector (3-15s). Calculate at ~2.5 words/sec, pick exact match. No padding, no rushing. |
| Vague motion | Generic static or wrong direction | Specify type + speed + direction (`slow dolly-in` not `camera moves`) |
| Overloaded prompt | Half the prompt ignored, hallucinated elements | Keep to 80-120 words, follow 5-part formula |
| Text in scene | Logos/text warp into gibberish | Same as VEO — Kling cannot render legible text. Use bare brand colors + shapes, add text in post |
| Too many subjects | Random face-swapping, identity drift | Max 3 named characters per scene. Pemeran Utama get full identity lock |
| Generic camera term | Static when motion expected | Replace `dynamic`/`cinematic` with specific term from camera library |
| Open-ended motion | 99% generation hang / failed render | State end-state explicitly (`woman walks to door and stops, hand on handle`) |
| Filter trigger | "Content rejected" error | Avoid: real person names in `says:`, weapons, explicit brand of competitor, copyrighted character names |
| Spatial vagueness | Subject teleports / distorted body | Anchor with `eye-level`, `from camera left`, `2 meters from camera` |
| Multi-language fail | Wrong lip-sync language | Explicitly declare per character: `Character A (Mandarin): "..."` not `they speak Mandarin` |
| Bahasa Indonesia on-screen lip-sync | Garbled mouth movement when char speaks ID on-camera | Lip-sync limited to 5 langs (EN/ZH/JA/KO/ES). For ID dialogue: use mouth-neutral framing + `Voice-over narrator, [tone]: [ID text]` (NATIVELY supported), OR switch to VEO 3.1 for that scene |
| Bahasa Indonesia voiceover not working | User wrote `Host says: [ID]` for B-Roll | Wrong syntax — B-Roll uses `Voice-over narrator, [tone]: [ID text]`. Kling renders ID VO natively when written as off-screen narrator, NOT as on-screen `says:` dialogue |
| Dialogue rushed/clipped | Speech > ~2.5 words/sec budget | Bump duration up by 1-2 seconds (per-second selector). E.g., 5s with 18 words → switch to 7s. |
| Em dash audio artifact | VO mispronounces / clips | Replace `—` with `,` or `. ` (same as VEO) |
| Stylized/abstract content | Looks photorealistic anyway, mismatched intent | Kling's bias = realism. For anime/illustration → use VEO or Seedance instead |
| Multi-shot scenes flicker | Shots blend incorrectly | Strengthen shot boundaries: `match cut to`, `whip pan to`, numbered shots |
| Motion Control wrong orientation | Character faces wrong way | Toggle Character Orientation parameter (Follow Video vs Follow Image) |

---

## Cross-Platform Comparison (Quick Reference)

| Feature | VEO 3.1 | Seedance 2.0 | Kling 3.0 |
|---------|---------|--------------|-----------|
| Max native resolution | 1080p | 2K (2048×1080) | 1080p UI / 4K via API |
| Max single clip | 8s (fixed) | 4-15s (range) | **3-15s per-second granular** (pick exact second) |
| Multi-shot in single render | No | No | **YES (up to 6 shots)** |
| Aspect ratios | 2 | 6 | 3 (UI) |
| Reference inputs | 1-3 images | **12 assets (img+vid+audio)** | 1 img + 1 vid + 1 audio |
| Audio languages | 10+ | 10+ | 5 (but **mixed-language scene!**) |
| Bahasa Indonesia lip-sync | ✅ | ✅ | ❌ (use VO + dub) |
| Extension chain | ~148s (20 hops × 7s) | Unlimited | No native extend (use Motion Control + new anchor) |
| Strength | Broadcast cinematic, prompt-faithful | Director-control, @ refs, audio reference | **Photoreal human motion, viral short-form, multi-shot efficiency** |
| Weakness | Less ratio variety, 8s/clip | Premium price | Weaker at stylized/abstract, no Indonesian lip-sync |
| Best when | Cinematic story, multi-char dialogue, broadcast brand | Director-level @ ref control, audio reference needed | Realistic faces, viral hook cuts, multi-shot in 1 render |

### When to Pick Kling Per Scene

- ✅ Face-heavy realistic dialogue (close-up emotional beat)
- ✅ Multi-shot viral hook (3-6 cuts in 15s, single render)
- ✅ Cross-language scene (English + Mandarin in same shot)
- ✅ Need 4K native delivery (API tier)
- ✅ Need exact duration match to dialogue/beat (per-second selector 3-15s eliminates re-pacing in edit)
- ✅ Motion transfer from existing reference clip
- ✅ Hyperreal human micro-expression

### When NOT to Pick Kling

- ❌ Bahasa Indonesia **on-screen lip-sync** needed (face >30% speaking ID) → use VEO 3.1 for those scenes. **NOTE**: Bahasa Indonesia **voice-over narrator** IS supported natively in Kling — only on-screen lip-sync is restricted to 5 langs
- ❌ Long-form (>15s) extension chain → use VEO or Seedance
- ❌ Stylized / anime / abstract → use VEO (better range)
- ❌ Complex multi-character cinematic with @ refs → use Seedance
- ❌ Director-control over each asset → use Seedance Omni mode

---

## Production Integration with NB2 Upstream

Kling 3.0 I2V mode = same upstream pattern as VEO First Frame:
1. NB2 generates anchor keyframe (`scene-NN.png`) at TARGET ASPECT RATIO
2. Aspect ratio MUST match Kling output (mismatch = edge hallucination, same VEO rule)
3. Kling I2V animates from anchor
4. For First+Last Frame mode: NB2 generates BOTH `-start.png` and `-end.png` (only for faceless scenes)
5. For multi-shot mode: NB2 generates ONLY the shot-1 anchor (Kling extrapolates further shots from text)
6. For Motion Control: source motion reference video required (user-provided or VEO-generated 720p clip)

### Same NB2 Identity Lock Rules as VEO
- Inline reference: `[Character] (Maintain exact facial identity from reference image: cast-c{N}-face.png)`
- Bare filenames only (NO `ref/` prefix)
- Max 5 inline refs per Phase 4B prompt (v2.2.0 §26.4)
- Aspect ratio triple enforcement (first line + TECHNICAL + last line)

### Kling-Specific Phase 5 Prompt Block

```
PLATFORM: Kling 3.0
MODE: I2V (single anchor) | First+Last Frame | Multi-Shot Storyboard | Motion Control
DURATION: 3s | 4s | 5s | 6s | 7s | 8s | 9s | 10s | 11s | 12s | 13s | 14s | 15s (per-second granular)
RESOLUTION: 720p | 1080p (UI) | 4K (API only)
ASPECT RATIO: 16:9 | 9:16 | 1:1
ANCHOR IMAGE: scene-NN.png (NB2 output, must match target ratio)
SECOND ANCHOR: scene-NN-end.png (First+Last mode only, faceless scenes only)
MOTION REF: motion-ref-{name}.mp4 (Motion Control only)
CHARACTER ORIENTATION: Follow Video | Follow Image (Motion Control only)

PROMPT (5-part formula):
[Camera Movement] + [Scene Setup] + [Subject Action] + [Vibe/Lighting] + [Time/Audio]

DIALOGUE:
Host says: "[max words per duration limit]"

AUDIO LAYERS:
Ambient: [explicit ambient sounds]
Music: [explicit music direction or "no music"]

NEGATIVE PROMPT (focused, 3-5 terms):
[1-2 categories relevant to scene: human / product / motion / environment]

NARRATIVE CONTEXT:
Previous: Scene {N-1} — [what happened]
This scene: [what happens now and WHY]
Next: Scene {N+1} — [what this sets up]
Visual breadcrumb: [shared element]
Emotional arc: [start emotion] → [end emotion]
```

---

## Phase 5 Decision Matrix — Platform Per Scene

Engine asks at Phase 5 start: "Which platform default for this video?" Options: VEO 3.1 (primary) | Seedance 2.0 | Kling 3.0 | Mixed (per-scene).

If user picks **Mixed**, scene-plan.md gets a `platform` column per scene. Heuristic suggestions:

| Scene Type | Suggested Platform | Reason |
|------------|-------------------|--------|
| Hook (Beat 1) — 3s face | Kling 3.0 | Photoreal face dominates |
| Problem (Beat 2) — environmental B-roll | VEO 3.1 | Broadcast cinematic |
| Reveal (Beat 3) — product hero | Seedance 2.0 | @ ref control over product |
| Solution (Beat 4) — dashboard UI | VEO 3.1 | Prompt-faithful UI rendering |
| Proof (Beat 5) — testimonial CU | Kling 3.0 | Realistic face emotion |
| Emotional Climax (Beat 6) — multi-shot montage | Kling 3.0 Multi-Shot | 4-6 cuts in single 15s render |
| CTA (Beat 7) — presenter to camera | VEO 3.1 | Reliable lip-sync EN/ID |

This matrix is suggestive — user can override per scene.

---

## Anti-Hallucination Rules (Same as VEO/Seedance)

1. **NEVER use real person names in `says:`** — `Host says:` / `Presenter says:` / `Speaker says:`. NB2 can still use real names.
2. **NEVER use em dash in audio text** — replace with `,` or `. `
3. **Audio is NEVER optional** — specify all 3 layers (dialogue/VO, ambient, music)
4. **Aspect ratio MUST match anchor image** — NB2 output ratio = Kling output ratio
5. **B-Roll narration = `Voice-over narrator, [tone]: text`** — never bare `Voiceover:` (lip-syncs to visible char)
6. **Face >30% frame for lip-sync** — smaller face = sync failure
7. **Negative prompts must be focused** — 3-5 relevant terms, NOT 20-term generic dump
8. **Multi-shot only when shots share env/char** — split into separate generations otherwise
9. **Bahasa Indonesia → use VO + post-prod dub** — not natively supported
10. **Text in scene = use post-prod overlay** — Kling cannot render legible text

---

## Sources (Curated 2026-05-16)

- Kling 3.0 Motion Control Official Guide — https://app.klingai.com/global/quickstart/motion-control-user-guide
- Kling Video 3.0 Omni Audio Native Lip Sync — https://kling.ai/blog/kling-video-3-omni-native-lip-sync-audio-guide
- Kling 3.0 Prompting Guide (fal.ai) — https://blog.fal.ai/kling-3-0-prompting-guide/
- Kling 3.0 Complete Guide (invideo) — https://invideo.io/blog/kling-3-0-complete-guide/
- Seedance vs Kling vs Sora vs VEO (WaveSpeed) — https://wavespeed.ai/blog/posts/seedance-2-0-vs-kling-3-0-sora-2-veo-3-1-video-generation-comparison-2026/
- Kling 3.0 Prompt Guide (Atlabs AI) — https://www.atlabs.ai/blog/kling-3-0-prompting-guide-master-ai-video-generation
- Kling 3.0 Multi-Shot Video Generator (VEED) — https://www.veed.io/ai-models/video/kling-3-0
- 12 Common Kling AI Prompt Mistakes — https://videoai.me/blog/kling-ai-prompt-mistakes
- Kling 3.0 vs VEO 3.1 for Ads/UGC (magichour) — https://magichour.ai/blog/kling-30-vs-veo-31
- Kling 3.0 Image-to-Video 20 Tested Prompts (vicsee) — https://vicsee.com/blog/kling-3-prompts

**For ongoing maintenance**: Feed this guide + above URLs into NotebookLM as a notebook called "Kling 3.0 Production Reference". Run Deep Research on prompt updates as Kuaishou ships v3.x updates.
