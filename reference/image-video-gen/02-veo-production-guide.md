---
source: VEO 3.1 Complete Production Guide, PROD_STEP2, PROD_STEP3 (Docs 8-10)
curated: 2026-03-19
version: 2.0
tokens: ~3500
platform: claude-projects
---

# VEO 3.1 — Video Production Reference

## Core Specs

| Param | Value | Notes |
|-------|-------|-------|
| Resolution | 720p (default), 1080p | 1080p = 8s clips only, cannot extend |
| Aspect | 16:9, 9:16 | No 1:1 support |
| Frame rate | 24fps | Fixed |
| Duration | 4, 6, 8 seconds | 8s required for extensions |
| Max tokens | 1,024 | Optimal: 100-150 words |
| Extensions | +7s per hop, max 20 | ~148s total possible |
| Reference images | Up to 3 | Asset or style type |
| Pricing | $0.40/s (audio) / $0.20/s (no audio) | Fast: $0.15/$0.10 |

## Model Selection — Veo vs GROK (Failover)

VEO 3.1 is the DEFAULT for quality + native audio. But it has TWO hard Google walls on certain clips, and **neither is fixable by prompt wording**:

| Wall | Error | Trigger | Reality |
|------|-------|---------|---------|
| **Mandatory audio** | `PUBLIC_ERROR_AUDIO_FILTERED` ("Audio generation failed") | Veo 3.x ALWAYS generates audio (no off-switch); its audio safety filter trips **nondeterministically** | Tweaking the `Audio:` bed (positive ambiance, fewer negations) only *reduces* it — never fully stops it. A model limit, not a prompt bug. |
| **Prominent people** | `PUBLIC_ERROR_PROMINENT_PEOPLE_FILTER_FAILED` | A recognizable public figure's FACE is in the source/keyframe (NOT the prompt words) | Renaming/rewording the prompt does nothing — the filter reads the IMAGE. Veo will never animate the celebrity. |

**GROK (xAI `grok-3` → grok-video) is the failover** — it clears BOTH (audio is stripped on download anyway; xAI ≠ Google, so figures pass). Use it when:

1. **A public figure is on the source frame → GROK immediately.** Don't waste a Veo attempt — Veo refuses deterministically.
2. **Veo fails audio (or times out) → retry Veo FIRST (preserve quality), then fail over to GROK** once the retry budget is spent. For a clip whose audio is discarded anyway (re-skin / carousel bookend / B-roll) GROK is the cleaner choice from the start.

**GROK gotchas:**
- `aspect_ratio` MUST be `2:3` — `9:16` returns **HTTP 400**. Crop the 2:3 output to your target ratio downstream.
- Audio is stripped on download (GROK has no mandatory audio model) → only use it where you don't need synthetic audio. A narrated promo that NEEDS Veo dialogue/SFX stays on Veo + works the audio bed.
- Image-to-video from a keyframe via `file_urls`; poll-based delivery (no webhook).

**Rule of thumb:** narrated / audio-driven promo → **Veo**. Audio-stripped re-skin / bookend clips, OR any clip with a recognizable public figure → **GROK**.

## Prompt Formula

```
[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]
```

**8-part pro version:**
```
[Subject] + [Context] + [Action] + [Style] + [Camera] + [Composition] + [Ambiance] + [Audio]
```

## Audio (NOT OPTIONAL)

Unspecified audio = model guesses (random laughter, wrong sounds).

**3 layers — specify all:**

| Layer | Syntax | Example |
|-------|--------|---------|
| Dialogue (lip sync) | `Host says: text` | Host says: Two hard steps, plant, explode. |
| Voiceover (off-screen) | `Voice-over narrator, [tone]: text` | Voice-over narrator, confident: This changes everything. |
| SFX | `SFX: description` | SFX: metallic clank, thunder cracks |
| Ambient | `Ambient: description` | Ambient: distant waterfall roar |

**Dialogue — lip sync rules:**
- Use generic role (`Host says:`, `Presenter says:`, `Speaker says:`) — NEVER real person names
- VEO safety filter rejects real person names + photorealistic face = "prominent people" error
- NB2 prompts can still use real names (NB2 has no such filter)

**Voiceover — off-screen narration rules:**
- ALWAYS use `Voice-over narrator, [tone]: text` — VEO treats "narrator" as off-screen entity
- NEVER use bare `Voiceover: text` — VEO assigns speech to visible on-screen character
- NEVER use `[Character name] says:` for background narration — triggers lip sync on visible character
- Works for ALL scenes: with or without visible human faces

**Text sanitization:**
- NEVER use em dash `—` in `says:` or `Voice-over narrator:` text — VEO audio engine mistranslates it
- Replace `—` with `,` (comma) or `. ` (period + space) in all dialogue/voiceover text
- Em dash is OK in Camera/Subject/SFX/Ambient description (non-audio text)

**Constraints:** 12-15 words max per 8s, 20-25 syllables max.
**Always add:** `no subtitles, no audience sounds, no text overlays`

## Camera Movement Library (VEO-Verified)

### Static
`static shot` · `locked-off shot` · `fixed camera`

### Push/Pull
`smooth dolly push-in` · `gentle dolly push-in` · `slow dolly-in` · `dolly-out` · `gentle dolly pull-back`

### Lateral
`tracking shot following subject` · `smooth tracking shot` · `truck left` · `truck right`

### Rotational
`slow pan left/right` · `whip pan` · `tilt up` · `tilt down`

### Complex
`crane shot rising/descending` · `orbit shot circling subject` · `180-degree arc shot` · `Steadicam floating movement`

### Stylistic
`handheld camera` · `documentary-style` · `shaky cam`

## I2V Motion Description

**Rule:** Describe MOTION only — model already sees the image.

### Subject Micro-Movements
- Face: `"subtle eye blinks every 2-3 seconds"`, `"gentle micro-expressions shifting"`
- Head: `"subtle head tilt suggesting thought"`, `"gentle nod of understanding"`
- Hands: `"subtle hand gesture emphasizing point"`, `"fingers gently tapping surface"`

### Ambient Motion
- Atmospheric: `"floating dust particles drifting through light beam"`, `"subtle haze drift"`
- Environmental: `"monitor screen content subtly shifting"`, `"curtain edge gentle flutter"`
- Light: `"subtle light flicker from screen"`, `"gentle shadow shift as clouds pass"`

### I2V Prompt Template
```
"~8s, 720p, [aspect].
Camera: [movement], [speed].
Subject: [micro-movements — blinks, breathing, gestures].
Maintain visual continuity with reference frame character appearance throughout clip.
Expression shift: [if any].
Ambient: [particles, environmental].
Audio: [ambient], [music/no music], no subtitles, no audience sounds.
Maintain exact lighting, environment, appearance from reference frame.
[aspect] output."
```

**Camera Constraint for First+Last Frame mode:**
Start and end frames must share similar camera angle (max 15° deviation) and adjacent shot size (max 1-step change: CU↔MCU↔MS↔MWS↔WS). Drastic camera changes (e.g., eye-level CU to overhead WS) cause VEO interpolation artifacts — distorted faces, warped environments, ghosting.

**CRITICAL — VEO Reference Image Rules:**
- VEO does NOT use NB2's reference image injection system — do NOT put `cast-c{N}-face.png` filenames in VEO prompts
- VEO gets identity from the uploaded start frame / ingredient images, NOT from text filenames
- Use generic continuity language: `Maintain visual continuity with reference frame character appearance throughout clip.`
- Face reference filenames (`cast-c{N}-face.png`) belong ONLY in NB2 prompts — use bare filename, NO ref/ prefix

Every VEO prompt MUST include a **Required Reference Images** table listing start frame / ingredient images needed. See `global-promo-config.md` Section 16.

### Face-Dominant Scene — Single I2V Only (Safety Filter)

VEO safety filter rejects **two photorealistic face images** uploaded together (First+Last Frame mode).

**Rule:** If scene has face >30% frame → use **single I2V** (start frame only), NOT First+Last Frame.
- First+Last Frame mode → ONLY for faceless scenes (dashboards, products, environments, wide shots without prominent faces)
- Single I2V with start frame → safe for all face-dominant scenes

## Lip Sync Mastery

### Colon Syntax (CRITICAL)
✅ `Host says: Welcome to my channel!`
❌ `Ali says: Welcome to my channel!` → safety filter rejects real person names
❌ `A woman says "Welcome to my channel"` → causes subtitles/sync failure

### Speaker Identity (CRITICAL — Safety Filter)
- VEO prompts MUST use **generic role names** for `says:` syntax: `Host`, `Presenter`, `Speaker`
- NEVER use real person names (e.g., `Ali says:`) — triggers "prominent people" safety filter
- NB2 image prompts can still reference real names (no filter)

### 3-6 Second Rule
| Duration | Words | Result |
|----------|-------|--------|
| 3-6s | 8-15 | ✅ Optimal sync |
| <2s | <5 | ❌ AI gibberish |
| >8s | >20 | ❌ Robotic, fast |

### Face Requirements
| Face Size (% of frame) | Quality |
|------------------------|---------|
| 30%+ | ✅ Excellent |
| 20-30% | ✅ Good |
| 15-20% | ⚠️ Marginal |
| <15% | ❌ Fails |

### Enhancement Keywords
Add to dialogue prompts: `"clearly enunciates"` · `"visible mouth openings"` · `"jaw moves realistically with dialogue"` · `"no background music"` · `"(no subtitles!)"`

### Pronunciation
Spell phonetically: "foh-fur" not "fofr", "eye-oh-tee" not "IoT"

### Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Frozen mouth | Camera too far | MCU/CU, add "visible mouth openings" |
| Off-beat sync | Dialogue too long | Shorten to 3-6s, add "no background music" |
| No audio generated | Wrong mode or 1080p bug | Use Text-to-Video, generate 720p |
| Unwanted subtitles | Wrong syntax | Use colon syntax, add "(no subtitles!)" multiple times |
| Identity drift | Multi-variable change | Same description verbatim across all prompts |
| "Prominent people" safety error | Real person name in `says:` | Use `Host says:` / `Presenter says:` — never real names |
| "Prominent people" on First+Last Frame | Two photorealistic face images | Use single I2V (start frame only) for face-dominant scenes |
| `PROMINENT_PEOPLE_FILTER_FAILED` on a recognizable celebrity keyframe | Veo won't animate a famous face (image-based, not prompt) | Fail over to **GROK** (xAI animates figures) — keep the figure keyframe, dispatch GROK i2v at aspect 2:3 |
| `AUDIO_FILTERED` ("Audio generation failed"), recurs every retry | Veo 3.x mandatory-audio filter trips nondeterministically — unfixable by prompt | If audio is discarded anyway → fail over to **GROK** (no audio model). If you need Veo audio → retry + simplify the `Audio:` bed (one positive ambiance, ≤1 negation) |
| On-screen character lip-syncs to VO | Used `Voiceover:` with face visible | Use `Voice-over narrator, [tone]: text` — VEO treats narrator as off-screen |
| Audio artifact / wrong word | Em dash `—` in dialogue text | Replace `—` with `,` or `. ` in all says:/narrator: text |
| VEO interpolation distorted/broken | Camera angle or shot size too drastic between start/end frames | Reshoot: max 1-step shot size change, max 15° angle change between frames |

## Scene Extension

| Constraint | Detail |
|------------|--------|
| Resolution | 720p only (1080p cannot extend) |
| Source | Must be VEO-generated video |
| Per hop | +7 seconds |
| Max | 20 extensions (~148s) |
| Context | Uses final 24 frames (1 second) |

**Best practices:**
- Hold pose for final 0.5s
- Maintain consistent camera movement speed
- Avoid new characters entering in final second
- Keep audio element present in final second

**Continuation prompt template:**
```
"Continue from previous clip. [New action].
Camera continues [same movement] at [same speed].
Maintain lighting, environment, character appearance.
Audio continues: [same ambient], [new dialogue if any].
No subtitles, no audience sounds."
```

## Timestamp Prompting (Multi-Shot)

```
[00:00-00:02] Shot 1: CU of hands typing rapidly
[00:02-00:04] Shot 2: MS reaction — subject leans back, eyes widen
[00:04-00:06] Shot 3: Over-shoulder revealing monitor
[00:06-00:08] Shot 4: CU face, dawning realization. Audio: quiet office, no dialogue.
```

Audio spec in final timestamp applies to whole clip.

## Transition End Instructions

| Transition | VEO Instruction | Use |
|-----------|-----------------|-----|
| Cut | "Hard cut, immediate switch" | Standard scene change |
| Push-In | "End with slow dolly push-in" | Building intensity |
| Pull-Back | "End with gentle pull-back" | Context reveal |
| Whip-Pan | "Fast horizontal pan with motion blur" | Energy |
| Fade to Black | "Slow opacity fade to black over 12 frames" | Scene end |
| Dissolve | "Cross-dissolve preparation, hold final pose" | Time passage |
| Match Cut | "End framing matches first frame of next shot" | Visual continuity |

## Negative Prompts (Standard Block)

```
No subtitles, no text overlays, no watermarks, no blurry faces,
no distorted hands, no cartoon effects, no audience sounds, no laugh track.
```

Prefer positive framing: "crystal-clear sharp focus" over "no blur".
