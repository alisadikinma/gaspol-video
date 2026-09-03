---
name: video-brainstorm
description: >
  Phase 1 brainstorm for AI video promotional production. Covers language selection,
  multi-character cast builder (max 5), product/service discovery, institution detection,
  location & setting context, domain deep research (6 WebSearch queries), target market,
  awareness level, platform selection, emotional core, storyline input with 7-beat arc mapping,
  and tone/mood selection.
  Triggers on: video brainstorm, cast setup, karakter video, brainstorm video, pemeran,
  mulai video baru, start video, new video project, video planning, rencana video.
---

# Video Brainstorm — Phase 1: Strategic Planning

## Overview

Phase 1 of the video production pipeline. This skill guides the user through strategic planning for a 2-3 minute promotional video: language selection, multi-character cast setup, product/service discovery, institution detection, location context, domain deep research, target market, awareness level, platform selection, emotional core discovery, storyline input with 7-beat arc mapping, and tone/mood selection. Output: `strategic-brief.md` + `cast-profile.md`.

## Reference Files (Read On-Demand)

| Task | Read |
|------|------|
| ANY generation | `reference/global-promo-config.md` (ALWAYS FIRST) |
| Cast profile system | `reference/creator-profile-system.md` |
| Target market psychology | `reference/storytelling_script_gen/F1_Audience_Psychology_Matrix.md` |
| Awareness level routing | `reference/storytelling_script_gen/F8_Awareness_Level_Routing.md` |

### CONTEXT LOADING — Phase 1
READ these files ONLY (do NOT read other reference files):
1. `reference/global-promo-config.md`
2. `reference/creator-profile-system.md`
3. `reference/storytelling_script_gen/F1_Audience_Psychology_Matrix.md`
4. `reference/storytelling_script_gen/F8_Awareness_Level_Routing.md`
Total: 4 files. Do NOT preload Phase 2-5 references.

---

## Hard Rules (NON-NEGOTIABLE)

1. **Product is NEVER the hero** — customer is hero, product is bridge
2. **First 3 seconds determine everything** — hook must stop the scroll
3. **Forbidden words** — synergy, leverage, robust, revolutionary, cutting-edge, seamlessly, innovative solution, state-of-the-art
4. **Every feature MUST have human consequence** — no feature listing without "so what?"
5. **All AskUserQuestion interactions** — NEVER ask questions as plain text, ALWAYS use AskUserQuestion tool with selectable options
6. **Max 5 cast members** — 1-3 Pemeran Utama + 0-2 Pemeran Pendamping (NB2 identity lock limit)
7. **Cast ref by role** — Utama: face+body+costume(if institutional) MANDATORY. Pendamping: face MANDATORY, body/costume OPTIONAL.
8. **Narration language from Step 1.0** — script dialogue and VEO `says:` text MUST be in user's chosen language. NB2/VEO prompt structure stays English.
9. **Tone consistency** — `video_tone` from Step 1.7b MUST be applied across ALL phases: script word choice (Phase 2), cinematography (Phase 4), atmosphere (Phase 5). Reference global-promo-config.md Section 13 Tone Impact Matrix.
10. **Cultural accuracy** — when location is specified, web search MUST be performed and cultural details MUST be injected into environment NB2 prompts and VEO scene prompts. Wrong license plate / wrong ethnicity / wrong architecture = rejection signal.
11. **Location context first** — Video setting/location MUST be confirmed (Step 1.2c) BEFORE domain research. Domain knowledge is location-specific: RS Indonesia ≠ RS USA ≠ RS Japan.
12. **Domain deep research (MANDATORY, location-aware)** — AI MUST WebSearch `{domain} in {location}` BEFORE scripting (Step 1.2d). 6 queries: local process flow, local equipment brands, local workforce/PPE, local facility layout, product interface, local regulations/signage. See `global-promo-config.md` Section 24.

---

## Workflow

#### Step 1.0: Language Selection

```
AskUserQuestion:
"Bahasa apa yang mau digunakan untuk narasi/voiceover video?"

Options:
A) Bahasa Indonesia
B) English
C) Bilingual (Indonesia primary, English for tech terms)
```

Save selection as `narration_language` in strategic-brief.md.
This affects: script dialogue (Phase 2), VEO `says:` text (Phase 5), strategic brief language.
NB2/VEO prompt structure always stays English (per `global-promo-config.md` `prompt_language`).

#### Step 1.1: Welcome & Cast Setup

**Read:** `creator-profile-system.md` (Cast Profile System)

```
AskUserQuestion:
"Selamat datang di Video Brainstorm! Pertama, siapkan cast (pemeran) untuk video ini."

Options:
A) Build cast baru (isi profile per karakter)
B) Use Ali Sadikin preset (fills 1 Pemeran Utama slot)
C) Load existing cast (dari cast-profile.md)
```

If "Build cast baru" or "Ali Sadikin preset" → follow Cast Builder Flow in `creator-profile-system.md` Section 1:
1. Cast size selection (1-5 characters)
2. Per-character role assignment (Utama/Pendamping)
3. Per-character profile collection (name, gender, age, ethnicity, features)
4. Ali Sadikin preset assignment (if selected)
5. Institution detection (auto-scan brand + confirm)

Save output: `{project}/cast-profile.md`

#### Step 1.2: Product/Service Discovery

```
AskUserQuestion:
"Produk atau layanan apa yang akan dipromosikan di video ini?"

Options:
A) SaaS / Software product
B) Physical product
C) Professional service
D) Other (jelaskan)
```

Follow-up:
```
AskUserQuestion:
"Apakah kamu punya technical document atau product brief yang bisa di-upload?
(PDF, doc, atau paste text langsung)"

Options:
A) Ya, saya akan upload/paste
B) Tidak, kita diskusi langsung
```

If user uploads/pastes → silently ingest 6 elements per `project-instruction.md` Phase 1:
1. Product category
2. Core value proposition
3. Target audience
4. Shame layer (pain they want to escape)
5. Pride layer (identity they want to claim)
6. Awareness level

#### Step 1.2b: Institution Detection

After product/service is identified, auto-scan for institutional keywords per `global-promo-config.md` Section 12.

If institution detected:

```
AskUserQuestion:
"Terdeteksi produk ini terkait dengan {institution}. Apakah karakter di video perlu pakai seragam {institution}?"

Options:
A) Ya, semua pemeran pakai seragam
B) Ya, tapi hanya pemeran tertentu
C) Tidak, pakai outfit generic
```

If A → update cast-profile.md with `costume_type = "institutional"` for ALL cast members.
If B → follow per-character costume assignment per `creator-profile-system.md` Section 7.
If C → no costume refs required (unless user manually adds later).

If no institution keyword detected → skip this step automatically.

#### Step 1.2c: Location & Setting Context

**Purpose:** Domain knowledge is location-specific. RS di Indonesia ≠ RS di US/China. Factory floor di Jepang ≠ di Cikarang. Location MUST be known before domain research.

```
AskUserQuestion:
"Di mana setting/lokasi video ini?"

Options:
A) Lokasi spesifik (kota/negara tertentu — misal: Surabaya, Jakarta, Shenzhen)
B) Negara saja (Indonesia, Japan, USA, dll)
C) Generic / tidak spesifik lokasi
D) Multiple lokasi (jelaskan)
```

Follow-up if A or D:
```
AskUserQuestion:
"Sebutkan detail lokasi:
- Kota/daerah: {input}
- Jenis tempat: (pabrik, kantor, rumah sakit, pelabuhan, outdoor, dll)
- Indoor/Outdoor/Both: {input}"
```

Save as `video_location`, `video_country`, `video_setting_type` in strategic-brief.md.

**Why this matters:**
- RS Indonesia: bangunan bertingkat, lorong lebar, perawat jilbab, papan nama Bahasa Indonesia, plat kendaraan lokal
- RS Jepang: bersih minimalis, kanji signage, staff berbaju putih rapi, tatami-style patient rooms
- RS Amerika: large campus, English signage, scrubs + sneakers, insurance desk, parking lot
- Same domain, completely different visuals. Location changes EVERYTHING.

#### Step 1.2d: Domain Deep Research (MANDATORY)

**Purpose:** AI is blind about specific product domains. Without domain knowledge, AI generates wrong machines, wrong processes, wrong operator actions. Domain research MUST be **location-aware** — `{domain} in {location}` not just `{domain}`.

**Trigger:** After product (Step 1.2) + institution (1.2b) + location (1.2c) are known.

**Protocol:** Use WebSearch to build location-specific domain knowledge.

```
ALGORITHM: Domain Deep Research (Location-Aware)

INPUT: product_name, product_category, product_description (from Step 1.2)
       video_location, video_country, video_setting_type (from Step 1.2c)

STEP 1: Identify the DOMAIN + LOCATION context
  → Combine industry domain + geographic context
  → Examples:
    "SMT assembly line in Cikarang Indonesia"
    "port container logistics in Dumai Riau Indonesia"
    "hospital emergency room in Jakarta Indonesia"
    "warehouse automation in Shenzhen China"

STEP 2: Execute 6 research queries (WebSearch) — ALL location-qualified

  Query 1: "{domain} in {country} production process workflow"
    → OUTPUT: How this domain operates IN THIS SPECIFIC LOCATION/COUNTRY
    → Local regulations, standards, certifications that affect workflow

  Query 2: "{domain} {country} equipment machines brands commonly used"
    → OUTPUT: What brands/models are actually used locally (not US/EU defaults)
    → CRITICAL: Indonesian factories often use different brands than US ones

  Query 3: "{domain} {country} worker roles uniforms PPE requirements"
    → OUTPUT: Local workforce — what do operators ACTUALLY wear/do here?
    → Local PPE standards, uniform styles, cultural dress norms
    → Example: Indonesian factory workers often wear batik on Fridays

  Query 4: "{domain} {location} facility layout photos"
    → OUTPUT: What do REAL local facilities look like?
    → Architecture style, building materials, interior design norms
    → Example: Indonesian RS = wide open corridors, tile floors, AC units visible

  Query 5: "{product_name} product interface dashboard features"
    → OUTPUT: What the actual product looks like in use
    → If SaaS: screens, UI language, dashboard layout
    → If physical: in-situ appearance at the specific location type

  Query 6: "{domain} {country} regulations standards signage"
    → OUTPUT: Local regulatory context affecting visuals
    → Safety signage language/style, certification marks, warning colors
    → Example: Indonesian factory = K3 safety signs in Bahasa, yellow/black hazard tape

STEP 3: Compile Location-Aware Domain Knowledge Brief

  Save to strategic-brief.md > Domain Knowledge section:

  ### Domain Knowledge — {domain} in {location}, {country}

  #### Location Context
  | Setting | Detail |
  |---------|--------|
  | Country | {country} |
  | City/Region | {city} |
  | Setting type | {factory/hospital/port/office/outdoor} |
  | Indoor/Outdoor | {indoor/outdoor/both} |
  | Local regulations | {relevant standards — K3, ISO, BPOM, etc.} |

  #### Process Flow (as practiced locally)
  {step-by-step process with LOCALLY-USED equipment at each step}

  #### Key Equipment Visual Reference (Local Brands/Models)
  | Equipment | Local Brand/Model | Appearance | Key Visual Feature |
  |-----------|------------------|-----------|-------------------|
  | {machine1} | {local brand} | {description} | {distinguishing feature} |

  #### Operator Roles & Actions (Local Workforce)
  | Role | Typical Action | Local PPE/Uniform | Tools/Equipment |
  |------|---------------|-------------------|-----------------|
  | {role1} | {what they DO locally} | {local dress norms} | {local tools} |

  #### Workspace Environment (Location-Specific)
  | Element | Local Standard | Visual Details |
  |---------|---------------|----------------|
  | Flooring | {local type} | {color, markings} |
  | Signage | {language, style} | {Bahasa/English/bilingual, K3 signs} |
  | Safety markings | {local standard} | {colors, placement per local regs} |
  | Architecture | {local style} | {building materials, ceiling type, ventilation} |

  #### Product Visual Reference
  {what the actual product looks like in this specific local context}

  #### Local Differentiators (vs generic/Western default)
  | Aspect | Generic AI Default | Actual Local Reality |
  |--------|-------------------|---------------------|
  | {aspect1} | {what AI would generate} | {what it actually looks like here} |
  | {aspect2} | {AI default} | {local reality} |
```

**Present domain research summary to user for validation:**

```
AskUserQuestion:
"Saya sudah research domain {domain} di {location}. Berikut ringkasannya:

{domain knowledge summary — location-specific equipment, process, roles, environment}

Apakah informasi ini sudah akurat untuk lokasi {location}?"

Options:
A) Akurat — lanjut
B) Ada yang salah — saya koreksi (jelaskan)
C) Saya punya info tambahan / foto referensi — saya akan paste/upload
D) Lokasi kurang spesifik — saya mau tambah detail lokasi
```

If B, C, or D → user corrects/adds info → update Domain Knowledge section.

**HARD RULE:** Location-aware domain research MUST complete before Phase 2 (Script). Script without domain knowledge = wrong equipment, wrong processes, wrong uniforms, wrong architecture for the location.

#### Step 1.3: Target Market Selection

```
AskUserQuestion:
"Siapa target audience utama video ini?"

Options:
A) C-Level (CEO, CTO, CFO) — strategic, ROI-focused
B) VP / Director — operational efficiency
C) Manager — practical workflow improvement
D) Individual Contributor — technical, hands-on
E) Social Media audience — emotional, punchy, Gen-Z
```

#### Step 1.4: Awareness Level

```
AskUserQuestion:
"Seberapa aware target audience terhadap masalah dan solusi kamu?"

Options:
A) Unaware — belum tahu ada masalah
B) Problem-Aware — tahu masalahnya, belum tahu solusi
C) Solution-Aware — tahu ada solusi, belum tahu produk kamu
D) Product-Aware — tahu produk kamu, belum yakin
E) Most-Aware — sudah yakin, butuh push terakhir
```

#### Step 1.5: Platform Selection

```
AskUserQuestion:
"Platform utama untuk video ini?"

Options:
A) YouTube (16:9, 2-3 min)
B) LinkedIn (16:9, 1-2 min)
C) Instagram Reels (9:16, 60-90s)
D) TikTok (9:16, 60-90s)
```

#### Step 1.6: Emotional Core Discovery

```
AskUserQuestion:
"Apa transformasi emosional yang kamu inginkan dari viewer?
(Dari state A → state B setelah nonton video)"

Options:
A) Frustrated → Relieved (problem-solution)
B) Skeptical → Convinced (proof-driven)
C) Unaware → Curious (discovery)
D) Interested → Urgent (FOMO/scarcity)
E) Custom (jelaskan sendiri)
```

#### Step 1.7: Storyline Input

```
AskUserQuestion:
"Apakah kamu punya ide storyline/cerita untuk video ini?"

Options:
A) Ya, saya mau ketik/paste storyline saya
B) Tidak, bantu saya brainstorm dari nol
C) Saya punya referensi video yang mirip (share link/description)
```

**If A (user has storyline):**

User pastes freeform text in the next message. AI then:

1. Parse storyline against the 7-beat arc (per `storytelling_script_gen/project-instruction.md`):
   - Pattern Interrupt, Hook, Foreshadow, Agitate, Guide+Plan, Peak, CTA, Won Day
2. Present beat mapping:

```markdown
## Storyline → 7-Beat Arc Mapping

| Beat | Status | Your Storyline Element |
|------|--------|----------------------|
| Pattern Interrupt | ✅ Covered | "{extracted element}" |
| Hook | ✅ Covered | "{extracted element}" |
| Foreshadow | ❌ Missing | — |
| Agitate | ✅ Covered | "{extracted element}" |
| Guide + Plan | ✅ Covered | "{extracted element}" |
| Peak | ❌ Missing | — |
| CTA | ✅ Covered | "{extracted element}" |
| Won Day | ❌ Missing | — |
```

3. For missing beats, suggest additions:

```
AskUserQuestion:
"Storyline kamu sudah cover {X}/8 beats. Saya suggest tambahan untuk beat yang missing:

- Foreshadow: {suggestion based on storyline context}
- Peak: {suggestion for emotional climax}
- Won Day: {suggestion for future-state visualization}

Approve suggestions?"

Options:
A) Approve semua suggestions
B) Approve sebagian (saya pilih mana)
C) Saya mau revise storyline sendiri
D) Skip — biarkan AI lengkapi di Phase 2
```

**If B (brainstorm from scratch):**

Engage user in guided discussion via AskUserQuestion:
- Key pain points of target audience
- Unique selling proposition
- Competitor landscape
- Success stories / case studies
- Desired CTA (what should viewer DO after watching?)

Use AskUserQuestion to present options and brainstorm ideas together.

**If C (reference video):**

User describes or shares reference. AI:
1. Extract narrative structure from description
2. Map to 7-beat arc
3. Adapt to user's product/context
4. Present adapted storyline for approval

#### Step 1.7b: Tone/Mood Selection

```
AskUserQuestion:
"Apa tone/mood yang kamu inginkan untuk video ini?"

Options:
A) Humorous / Playful — ringan, ada jokes, approachable
B) Serious / Dramatic — berat, impactful, emosional
C) Professional / Corporate — formal, data-driven, polished
D) Inspirational / Motivational — uplifting, empowering
E) Casual / Friendly — santai, conversational, relatable
F) Edgy / Bold — provocative, disruptive, berani
```

Save as `video_tone` in strategic-brief.md.

Tone affects ALL subsequent phases — reference `global-promo-config.md` Section 13 (Tone Impact Matrix) for per-phase adjustments to:
- Script word choice and pacing (Phase 2)
- Hook style selection from F5 Hook Vault (Phase 2)
- Lighting ratio and camera style (Phase 4 NB2)
- Music and SFX direction (Phase 5 VEO)
- Character expression guidance (Phase 4 NB2)
- Atmosphere keywords (Phase 5 VEO)

#### Step 1.8: Strategic Brief Presentation

Present the Strategic Brief for approval:

```markdown
# Strategic Brief

## Product: {name}
## Target: {market} — {awareness_level}
## Platform: {platform} ({aspect_ratio}, {duration})
## Language: {narration_language}
## Tone: {video_tone}
## Emotional Arc: {from_state} → {to_state}

## Core Value Proposition
{1-2 sentences}

## Shame Layer (pain to escape)
{1-2 sentences}

## Pride Layer (identity to claim)
{1-2 sentences}

## Key Messages
1. {message_1}
2. {message_2}
3. {message_3}

## CTA
{specific action}

## Storyline (User Input)
{user's original storyline or "AI-generated from brainstorm"}

## Domain Knowledge
{From Step 1.2c — process flow, equipment visuals, operator roles, workspace environment, product appearance}

## Cultural Context
(Populated in Phase 3.5 via web search — see Step 3.5.2a)
```

```
AskUserQuestion:
"Strategic brief di atas sudah sesuai?"

Options:
A) Approve — lanjut ke script generation
B) Revise — ada yang perlu diubah (jelaskan)
C) Start over — mulai brainstorm dari awal
```

**Save output:** `{output_folder}/strategic-brief.md`, `{project}/cast-profile.md`

---

## Next Step

Run `/video-script` to continue to Phase 2 (Script Generation), Phase 3 (Scene Breakdown), and Phase 3.5 (Reference Collection).

### Voice per Speaking Cast Member (v3.0.0)

For every cast member who has a spoken line, ask which voice they use and record a `VOICE:` block in
`cast-profile.md` (format in `reference/creator-profile-system.md`).

```
AskUserQuestion, per speaking character:
"Suara {nama} pakai apa?"

A) Suara ElevenLabs yang sudah ada — sebutkan nama variabel env-nya
   (misal ELEVENLABS_VOICE_C1). Nilainya tidak ditulis di sini.
B) Suara dari platform video saja — tidak perlu VOICE block.
C) Belum tahu — tandai TBD, Phase 5 menanyakannya lagi sebelum VO dibuat.
```

`source` is not asked: it follows from whether the character speaks on camera. A character whose face
fills more than 30% of frame while speaking gets `native+changer`; anyone else gets `tts`.

**Never write a voice id into `cast-profile.md`.** Record the env var name. The id belongs to the
user's account and this plugin stays client-agnostic.
