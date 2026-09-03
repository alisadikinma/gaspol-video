---
source: Cross-platform voice-over consistency workflow — compiled from community guides (VEO 3 Voice Consistency TikTok workflow), ElevenLabs official docs, Atlabs AI Mirror Voice, Kling Elements 3.0 docs, Seedance @Audio system, post-production sync techniques (DaVinci/Premiere/CapCut)
curated: 2026-05-16
version: 1.0
tokens: ~4200
platform: claude-projects
applies_to: VEO 3.1, Seedance 2.0, Kling 3.0 (all three platforms + external tools)
---

# Voice-Over Consistency — Cross-Platform Workflow

## The Core Problem

All three video models (VEO 3.1, Seedance 2.0, Kling 3.0) generate **random voice characteristics per clip**. Same prompt, same character description → different voice on every generation. No memory between clips.

This breaks viewer trust in multi-scene videos:
- Viewers detect voice mismatches within **45 milliseconds**
- Voice drift can reduce message retention by up to **40%**
- Same character "sounding different" across scenes = subconscious "fake" trigger

**This file is mandatory reading for any video with >1 scene OR with character voice continuity.**

---

## 3 Solution Paths (pick by use case)

```
Decision Tree:

Has the user uploaded a voice reference (own voice OR pre-generated clone)?
├── YES → Path A or Path C
│   ├── Mixed platforms / multi-scene → Path C (single VO recording, post-prod sync)
│   └── Single platform with native voice lock → Path A (per-platform native)
│
└── NO → Path B (post-prod ElevenLabs unification, no prep needed)
```

---

## Path A — Native Voice Lock (Platform-Specific)

Lock voice at GENERATION time using each platform's native voice cloning.

### A1. Kling 3.0 — Elements 3.0 Voice Cloning ✅

**UNIQUE FEATURE** — VEO 3.1 and Sora 2 don't have this.

**Two sub-modes:**

| Mode | Input | Output |
|---|---|---|
| Audio sample binding | 3-8 second audio clip of target voice | Voice locked to character ID, reused across all scenes |
| Video extraction | 3-8 second video clip (face + audio together) | BOTH face AND voice extracted simultaneously — perfect identity-voice lock |

**Workflow:**
```
1. Record (or source) 3-8 second clean audio sample of target voice
   - Quality: minimum 16kHz, no background noise, single speaker
   - Content: natural narration (not script reading)

2. In Kling 3.0 UI:
   - Upload audio sample to Elements 3.0
   - Bind to character slot (cast-c{N})
   - OR upload video clip → extract face + voice in one step

3. Reference character in every Kling prompt:
   - "Character {cast-c{N}}: Voice-over narrator, [tone]: [text]"
   - Kling auto-uses the bound voice profile

4. Consistency: 90-95% across scenes (vs <50% without voice lock)
```

**When to use:** Pure-Kling production where you have user's voice sample or pre-cloned voice.

### A2. Seedance 2.0 — @Audio Reference System ✅

Seedance accepts up to **3 @Audio refs** (max 15s each) per generation.

**Workflow:**
```
1. Prepare 1-15 second voice reference audio (target voice speaking naturally)

2. In Seedance 2.0 prompt:
   - Tag: @Audio1 = voice reference
   - Example: "The character speaks with the voice tone, accent, and rhythm
     of @Audio1, narrating: [text]"

3. Strength of voice lock:
   - Strong: rhythm, accent, timbre — replicated
   - Weak: exact phonetic identity (voice "feels similar" not "identical")

4. Consistency: 80-90% across scenes when same @Audio1 used in all prompts
```

**When to use:** Pure-Seedance production with audio reference. Excellent for character voice rhythm/cadence lock.

### A3. VEO 3.1 — NOT Supported ❌

VEO has no native voice cloning. Voice control is prompt-only:
```
Voice-over narrator, warm baritone Indonesian male mid-30s, calm pace,
slight Jakarta accent, professional tone: [text]
```

**Reality check:** Even with verbatim-identical voice description across all VEO prompts, consistency is **~50-70%** (significant drift). For VEO production with voice consistency requirement, **MUST use Path B (post-prod unification)**.

### A4. Cross-Platform Limitation

Voice lock is **PER-PLATFORM ONLY**:
- Kling Elements 3.0 voice ≠ Seedance @Audio1 voice (different model weights, different phonetic interpretation)
- Even with same source audio sample, the two platforms render it differently

**For Mixed-platform videos (Step 5.0 = Mixed): Path A alone is insufficient. Must combine with Path B final pass.**

---

## Path B — Post-Production Voice Replacement (UNIVERSAL)

**Works regardless of source platform.** This is the most reliable path for guaranteed 100% consistency.

### The 3-Step Community Workflow

```
Step 1: GENERATE (any platform mix)
  - Generate ALL video clips using whatever platforms (Kling/VEO/Seedance)
  - Accept that native voice output will be inconsistent
  - Each clip has SOME voice audio (even if random per-clip)
  - Save clips with audio intact

Step 2: EDIT (timeline + vocal export)
  - Import clips to CapCut / DaVinci Resolve / Premiere Pro
  - Arrange in final timeline order
  - Export options:
    a) Export FULL video with audio (recommended — preserves timing)
    b) Export VOCAL TRACK ONLY (smaller file, faster ElevenLabs processing)

Step 3: VOICE CHANGER (ElevenLabs)
  - Open ElevenLabs → Voice Changer tool
  - Select target Voice ID (your own clone or pre-built voice)
  - Upload exported audio/video
  - Generate → ElevenLabs renders entire track in target voice
  - Download new audio
  - Sync back in editor → replace original vocal track
  - Add ambient/SFX/music layer on top
```

### Why This Works

- **Source-independent**: Doesn't care if voice came from VEO/Seedance/Kling — Voice Changer rebuilds from scratch
- **Timing-preserving**: Voice Changer keeps original pacing/breath/pause/emphasis intact, only swaps voice character
- **One-shot**: Process the whole timeline at once, not per-clip → guaranteed consistency

### ElevenLabs Voice ID Setup (one-time)

| Tier | Sample Required | Quality | Use Case |
|---|---|---|---|
| **Instant Voice Cloning** | 1-2 min clean audio | Good (85% accuracy) | Most promo production |
| **Professional Voice Cloning** | 30+ min, multiple sessions | Excellent (95%+ accuracy) | High-budget commercials, brand spokesperson |

**Sample recording tips:**
- Record voice **narrating naturally** (not casual conversation)
- Match the energy/pace you want in final output (AI clones HOW you read, not just voice timbre)
- Include breathing/pauses naturally — don't over-edit
- 1-2 min instant clone is enough for most promo (>3 min hits diminishing returns and can destabilize clone)

### Tools Comparison

| Tool | Tier | Cost | Workflow Fit |
|---|---|---|---|
| **ElevenLabs Voice Changer** | Best | $5-22/mo subscription | Industry standard, recommended |
| **Atlabs AI Mirror Voice** | Native in their video tool | Included with Atlabs sub | If already using Atlabs platform |
| **CapCut AI Voice Clone** | Free tier limited | Free → Pro $7.99/mo | Quick mobile workflow |
| **Descript Overdub** | Pro tier required | $24/mo | Strong text-driven editing fit |

---

## Path C — Single VO Recording + Video Sync (UNIVERSAL)

Skip AI native audio entirely. Record/generate ONE master VO track, sync video to it.

### Workflow

```
1. RECORD OR CLONE master VO
   - Option a: Voice talent records full 2-3 min script in one take
   - Option b: ElevenLabs TTS with locked Voice ID generates full script
   - Output: Single .mp3/.wav file with complete narration

2. GENERATE VIDEO with placeholder audio
   - In prompt, use generic Voice-over narrator description
   - Or explicitly: "minimal audio, ambient only, voice-over track will be
     added in post"
   - Save clips — discard generated voice in editor

3. SYNC IN EDITOR
   - Import master VO + all video clips into DaVinci/Premiere
   - Lay VO track on audio timeline
   - Cut/arrange video clips to match VO beats
   - VO drives the edit (documentary/tutorial style)
```

### Sync Techniques

**L-cuts and J-cuts (essential for natural flow):**
- **L-cut**: Audio continues from clip A into clip B's video (creates "speaker keeps talking as scene changes")
- **J-cut**: New clip's audio starts BEFORE its video appears (creates anticipation, "we hear it before we see it")

Use these for transitions to avoid jarring audio jumps.

**Rate stretch for timing mismatch:**
- VO line is 6.2 seconds but video clip is 5s → use NLE's rate stretch tool
- Squish audio 5-10% faster without pitch change → undetectable to human ear
- DaVinci Resolve and Premiere both have this feature

### When to Use Path C

- ✅ B-Roll-heavy promo (most of typical 2-3 min B2B video)
- ✅ Voice talent unavailable (use ElevenLabs)
- ✅ Need precise script adherence (no AI hallucinations of dialogue)
- ✅ Brand spokesperson voice required (lock to specific Voice ID)

### When NOT to Use Path C

- ❌ Lip-sync dialogue scenes (face >30% frame speaking) — video timing must match exactly, can't stretch
- ❌ Conversational/multi-character scenes — too complex to sync single track

---

## Recommended Hybrid Workflow Per Video Type

### Type 1: Pure-VEO Production
- Voice cloning: NOT AVAILABLE in VEO
- **Path B (mandatory)**: Generate all clips → ElevenLabs Voice Changer pass → sync
- Time overhead: +15-20 min post-prod for 2-3 min video

### Type 2: Pure-Kling Production
- Voice cloning: ✅ Elements 3.0 (90-95% consistency)
- **Path A (preferred)** if user has voice sample
- **Path B (fallback)** if no voice sample available
- Time overhead: Path A = 0 (handled at generation) / Path B = +15-20 min

### Type 3: Pure-Seedance Production
- Voice cloning: ✅ @Audio1 system (80-90% consistency)
- **Path A (preferred)** if user has voice sample
- **Path B (fallback)** for guaranteed 100%
- Time overhead: similar to Kling

### Type 4: Mixed-Platform (Step 5.0 = Mixed)
- Voice cloning: per-platform = inconsistent across boundaries
- **Path A + B (mandatory combo)**:
  1. Use Path A native voice lock WITHIN each platform's scenes
  2. Post-prod Path B ElevenLabs pass on FULL timeline for cross-platform unification
- Time overhead: +20-30 min post-prod

### Type 5: B-Roll-Heavy Promo (any platform mix)
- **Path C (recommended)** — single VO recording drives the edit
- Skip platform native audio entirely
- Time overhead: +30-45 min sync editing (but saves regeneration cost)

---

## Prompt-Level Discipline (Universal — Apply Always)

Even with Path A/B/C, prompt hygiene matters. These rules apply to ALL platforms:

### Rule 1: Voice Description VERBATIM Across All Prompts

❌ **BAD** (drift trigger):
```
Scene 1: Voice-over narrator, warm friendly tone: "..."
Scene 2: Voiceover, calm professional voice: "..."
Scene 3: Narrator, energetic upbeat: "..."
```

✅ **GOOD** (consistency lock):
```
Scene 1: Voice-over narrator, warm baritone Indonesian male mid-30s, calm pace, slight Jakarta accent: "..."
Scene 2: Voice-over narrator, warm baritone Indonesian male mid-30s, calm pace, slight Jakarta accent: "..."
Scene 3: Voice-over narrator, warm baritone Indonesian male mid-30s, calm pace, slight Jakarta accent: "..."
```

Use EXACT SAME 12-word voice description in every prompt. Copy-paste, don't paraphrase.

### Rule 2: Accent Lock > Voice Variation Lock

Accent shifts are MORE jarring than voice timbre shifts. Prioritize accent consistency:
- ✅ Lock accent verbatim: `slight Jakarta accent` in every prompt
- ⚠ Voice may vary slightly between clips (~10% drift acceptable)
- ❌ NEVER mix accents within same video (Jakarta → Sundanese → US-English = unfixable in post)

### Rule 3: One Emotion Per Scene (no transitions within prompt)

❌ **BAD** (causes voice drift mid-clip):
```
"...starts curious, becomes excited, ends with questioning tone"
```

✅ **GOOD** (stable rendering):
```
Scene 1 (curious): "..."
Scene 2 (excited): "..."
Scene 3 (questioning): "..."
```

One emotional state per generation. Transitions live at the EDIT level, not prompt level.

### Rule 4: Specify Audio Layer Independence

```
Audio Layers:
  Dialogue/VO: Voice-over narrator, [verbatim voice description]: "[text]"
  Ambient: [explicit ambient sounds — NOT mixed with voice]
  Music: [explicit music or "no music"]
```

This makes Path B post-prod separation easier — Voice Changer needs clean VO track without music/ambient interference.

---

## Cost / Time Comparison

For a typical 2-3 min Bahasa Indonesia promo (12-18 scenes):

| Approach | Pre-prod | Generation | Post-prod | Total | Voice Consistency |
|---|---|---|---|---|---|
| Path A only (Kling pure) | 30 min (voice clone setup) | Same as base | 0 | +30 min | 90-95% |
| Path A only (Seedance pure) | 30 min | Same as base | 0 | +30 min | 80-90% |
| Path B only (any platform) | 0 (or 5 min if no Voice ID setup) | Same as base | 15-20 min | +15-25 min | 100% |
| Path C (B-Roll-heavy) | 60 min (VO recording) | Same as base (silent) | 30-45 min sync | +90-105 min | 100% |
| Hybrid A+B (Mixed platform) | 30 min | Same as base | 20-30 min | +50-60 min | 100% |

**Recommended default for plugin users:** **Path B** — universal, fastest setup, 100% consistency, works regardless of platform choice.

---

## Plugin Integration — Phase 5 Default Behavior

When user runs `/video-gen` Step 5.0:

```
1. Engine asks platform (VEO / Seedance / Kling / Mixed)

2. Engine checks for voice reference:
   AskUserQuestion:
   "Apakah Anda punya voice reference untuk konsistensi VO antar scene?"

   Options:
   A) Ya, ada audio sample (saya akan kasih path) — engine routes to Path A native lock if Kling/Seedance, OR Path B prep
   B) Tidak ada — engine defaults to Path B (post-prod ElevenLabs pass)
   C) Saya akan record VO sendiri di post-prod (Path C) — engine generates with placeholder audio

3. Engine injects voice description verbatim across all VEO/Kling/Seedance prompts (Rule 1)

4. After Phase 5 completion, engine outputs `voice-consistency-plan.md`:
   - Selected path (A / B / C / Hybrid)
   - Voice description used (for verbatim re-use)
   - Post-prod checklist (if Path B/C)
   - ElevenLabs Voice ID slot (if available)
```

This file should be referenced by `skills/video-gen/SKILL.md` Step 5.0 and read as part of Phase 5 context loading.

---

## Anti-Patterns (Things That Break Voice Consistency)

| Anti-pattern | Why it breaks | Fix |
|---|---|---|
| Different voice description per scene | Model interprets differently each time | Verbatim copy across all prompts |
| Mixing voice description with emotion modifiers | "warm baritone, urgent tone" — model conflates voice and emotion | Separate: lock voice description, vary emotion ONLY |
| Using real person names in voice description | "voice like David Attenborough" — triggers safety filter on VEO, hallucinates on others | Generic timbre description only (baritone/tenor/alto) |
| Switching accents mid-video | Voice can drift, accent shift is unfixable | Lock accent verbatim, vary nothing else |
| Generating with music mixed in dialogue | ElevenLabs Voice Changer struggles to separate | Keep music as explicit separate layer |
| Multiple speakers per VO scene | Path B can only swap ONE voice at a time | Generate single-speaker VO scenes; dialogue scenes use Path A native |
| Skipping voice description entirely | Model picks random voice every clip | Always include voice description, even if simple |

---

## Sources & Tools

### Tools Referenced
- ElevenLabs Voice Cloning: https://elevenlabs.io/voice-cloning
- ElevenLabs Voice Changer: https://elevenlabs.io/voice-changer
- ElevenLabs Studio 3.0 (integrated AI audio+video editor): https://elevenlabs.io/studio
- Atlabs AI Mirror Voice: https://www.atlabs.ai/blog/consistent-character-voices-ai-video
- Kling Create Voice API: https://www.segmind.com/models/kling-create-voice
- DaVinci Resolve (free NLE): https://www.blackmagicdesign.com/products/davinciresolve
- CapCut (free NLE, mobile-friendly): https://www.capcut.com/

### Community Workflows Referenced
- VEO 3 Voice Consistency 3-Step Workflow (TikTok): https://www.tiktok.com/@ai.for.real.life/video/7537477893442538766
- AI Multi-Shot Video Character + Voice Consistency: https://www.aimagicx.com/blog/ai-multi-shot-video-character-consistency-2026
- AI Voice Sync Post-Production Guide (Kukarella): https://www.kukarella.com/resources/ai-audio-engineering/how-to-seamlessly-sync-ai-voiceovers-with-video-ai-dubbing-and-adr
- Best Practices for AI Voice and Lip-Sync Consistency (longstories.ai): https://longstories.ai/blog/best-practices-ai-voice-lip-sync-consistency

### Platform Voice Cloning Docs
- Kling 3.0 Omni Audio + Elements 3.0: https://kling.ai/blog/kling-video-3-omni-native-lip-sync-audio-guide
- Seedance 2.0 @Audio reference system: see `07-seedance-production-guide.md` §"The @ Reference System"
- VEO 3.1 audio (no voice cloning): see `02-veo-production-guide.md` §"Audio Specs"

---

## Executable path (v3.0.0 — this file is no longer only a plan)

Until v3.0.0 the three paths above were described and never performed: Step 5.0a wrote
`voice-consistency-plan.md` and no audio file was ever produced. That gap is closed.

| Path | Now performed by | Reference |
|---|---|---|
| **A** — native voice lock (Kling Elements 3.0, Seedance @Audio1) | unchanged, done inside the platform UI | this file |
| **B** — ElevenLabs | `tools/gen_vo.mjs` for narration, `tools/voice_changer.mjs` for converting platform-spoken dialogue into the locked character voice | `reference/post-production/11-voice-cast-and-vo.md` |
| **C** — single VO recording + sync | `tools/edit_render.py`, driven by the measured VO length | `reference/post-production/13-ffmpeg-edit.md` |

Two things changed in how Path B is reached:

1. **The question is about the audio SOURCE, not about consistency.** Phase 5 Step 5.0a asks where the
   voice comes from, and the answer is binding on how every prompt is written — see the muting rules
   there.
2. **Voice belongs to a cast member, not to a video.** A `VOICE:` block in `cast-profile.md` pins the
   provider, the env var holding the voice id, the model and the settings per character, so one scene
   can carry cast-c2 speaking on screen followed by cast-c1 narrating over the same shot.

The `voice_changer.mjs` step depends on speech-to-speech preserving duration, which is what keeps the
lips matching after the voice is replaced. That tolerance is 0.05s and it is enforced, not assumed:
see `global-promo-config.md` §29.4 `voice_changer_max_drift_s`.
