# Cast Profile System

Multi-character cast system for promotional video production. Supports 1–5 characters with role-based reference requirements. Replaces the old single-creator model.

**Key Rules:**
- Max 5 characters total (matches NB2 identity lock limit)
- 1–3 Pemeran Utama (main characters — full reference required)
- 0–2 Pemeran Pendamping (supporting — face reference required)
- Ali Sadikin preset fills exactly 1 Pemeran Utama cast slot
- Reference images are MANDATORY — no skip option anywhere in the flow

---

## 1. Cast Builder Flow (Phase 1: Brainstorm)

Iterative cast builder that collects all character profiles during Phase 1. Each step uses AskUserQuestion with selectable options.

### Step 1: Cast Size Selection

```
AskUserQuestion:
"Berapa pemeran (karakter) yang akan tampil di video ini? (max 5)"

Options:
A) 1 pemeran
B) 2 pemeran
C) 3 pemeran
D) 4-5 pemeran
```

If user selects D, follow up:

```
AskUserQuestion:
"Berapa total pemeran?"

Options:
A) 4 pemeran
B) 5 pemeran
```

### Step 2: Per-Character Role Assignment

Repeat for each character (1 through N):

```
AskUserQuestion:
"Pemeran #{N} — role apa?"

Options:
A) Pemeran Utama (main character — full ref required: face + body + costume)
B) Pemeran Pendamping (supporting — face ref required, body/costume optional)
```

**Constraints enforced automatically:**
- Max 3 Pemeran Utama. If 3 already assigned, only Pendamping available.
- Max 2 Pemeran Pendamping. If 2 already assigned, only Utama available.
- At least 1 Pemeran Utama required. First character defaults to Utama.

### Step 3: Per-Character Profile Collection

Repeat for each character. Collect via sequential AskUserQuestion:

| Field | Question | Required? |
|-------|----------|-----------|
| `character_name` | "Nama karakter/pemeran #{N}?" | YES |
| `character_gender` | "Gender pemeran #{N}?" → Male / Female / Non-binary | YES |
| `character_age_range` | "Range usia pemeran #{N}?" → 20s / 30s / 40s / 50s+ | YES |
| `character_ethnicity` | "Etnis/appearance pemeran #{N}?" (e.g., Indonesian, Chinese-Indonesian, etc.) | YES |
| `character_key_features` | "Ciri khas pemeran #{N} yang harus konsisten di semua scene?" (e.g., berkacamata, berjanggut, botak, etc.) | YES for Utama, Optional for Pendamping |
| `character_role_desc` | "Deskripsi peran pemeran #{N} di video?" (e.g., "CEO yang memperkenalkan produk", "teman yang meragukan solusi") | YES |

**Gender question format:**

```
AskUserQuestion:
"Gender pemeran #{N}?"

Options:
A) Male
B) Female
C) Non-binary
```

**Age range question format:**

```
AskUserQuestion:
"Range usia pemeran #{N}?"

Options:
A) 20s
B) 30s
C) 40s
D) 50s+
```

### Step 4: Ali Sadikin Preset Option

```
AskUserQuestion:
"Apakah salah satu pemeran menggunakan Ali Sadikin preset?"

Options:
A) Ya, assign ke Pemeran #1 (Utama)
B) Ya, assign ke Pemeran #2 (Utama)
C) Ya, assign ke Pemeran #{N} (Utama)
D) Tidak, semua custom
```

Only Pemeran Utama slots are listed as options. If user selects a slot, that character's profile is auto-filled with Ali Sadikin data from Section 2. The user can still override individual fields after auto-fill.

### Step 5: Institution Detection (Auto-Triggered)

Engine scans `brand_name` + `product` from Phase 1 brainstorm context. Reference `global-promo-config.md` Section 12 for institution keyword mapping.

**If institution keyword detected:**

```
AskUserQuestion:
"Terdeteksi produk ini untuk {institution_name}. Apakah karakter perlu pakai seragam {institution_name}?"

Options:
A) Ya, semua pemeran pakai seragam {institution_name}
B) Ya, tapi hanya pemeran tertentu (pilih di langkah berikutnya)
C) Tidak, pakai outfit generic
```

**If Option B selected, follow up per character:**

```
AskUserQuestion:
"Pemeran #{N} ({character_name}) — pakai seragam {institution_name}?"

Options:
A) Ya, pakai seragam
B) Tidak, pakai outfit generic
```

**If no institution keyword detected:** Skip institution detection automatically. Costume references only required if user manually specifies institutional context.

### Step 6: Reference Image Upload Confirmation

After all profiles collected, present the full reference image checklist:

```
AskUserQuestion:
"Upload reference images berikut ke folder {project}/ref/:

Pemeran Utama (#{N} — {name}):
  ✦ ref/cast-c{N}-face.png — foto wajah (front view, clear, well-lit)
  ✦ ref/cast-c{N}-body.png — foto full body (standing pose)
  ✦ ref/cast-c{N}-costume.png — foto seragam/kostum (jika institutional)

Pemeran Pendamping (#{N} — {name}):
  ✦ ref/cast-c{N}-face.png — foto wajah (front view, clear, well-lit)

Brand:
  ✦ ref/brand-logo.png — logo brand

Sudah di-upload semua?"

Options:
A) Sudah semua, lanjut
B) Mau tanya soal requirements
```

**CRITICAL: There is NO skip option. No "Belum, skip dulu". No "lanjut tanpa ref". All listed reference images must be uploaded before proceeding.**

If user selects B, clarify requirements and re-present the checklist.

---

## 2. Ali Sadikin Preset

Ali Sadikin preset fills exactly 1 Pemeran Utama cast slot. When selected, auto-fills one character entry in `cast-profile.md`. The slot number `{N}` is determined during Cast Builder Step 4.

Activated via `--preset ali` flag or interactive selection during Step 4.

### Physical Reference

| Attribute | Spec | Cinematography Impact |
|-----------|------|----------------------|
| Ethnicity | Indonesian | — |
| Age | Late 30s | — |
| Head | Bald, round face | Avoid harsh overhead → angled key, flag above |
| Skin | Warm undertone, natural texture | Responds well to 3200K tungsten |
| Eyes | Dark brown | Need adequate light for catchlights |
| Glasses | Rectangular gunmetal, semi-rimless | Key at 30-45° to avoid glare |
| Facial hair | Clean-shaven | — |
| Build | Medium | — |
| Presence | Confident, approachable, authoritative | — |

### Standard Reference Phrase (Copy Verbatim — Inline with Character Description)

```
Ali Sadikin (Maintain exact facial identity from reference image: cast-c{N}-face.png) —
Indonesian male, late 30s, bald, round face, warm skin undertone with natural
texture, dark brown eyes, rectangular gunmetal semi-rimless glasses, clean-shaven,
confident approachable presence.
```

Where `{N}` = Ali Sadikin's assigned cast slot number from Step 4.

**Usage:** This phrase goes INLINE inside the SUBJECT line of every NB2 prompt where Ali Sadikin appears. Do NOT place it as a standalone header line above the prompt body.

### Wardrobe Defaults

| Context | Wardrobe |
|---------|----------|
| Professional/Tech | Navy blazer, white open-collar shirt |
| Casual explainer | Dark henley or polo |
| Formal | Dark suit, light shirt |

### Lighting Setups

| Content | Pattern | Ratio | Kelvin | Shot | Lens | Angle |
|---------|---------|-------|--------|------|------|-------|
| Hook | Rembrandt | 4:1 | 3200K | CU | 85mm f/1.8 | Eye-level to slight low |
| Explanation | Loop | 2:1 | 5600K | MCU | 50mm f/2.8 | Eye-level |
| CTA | Butterfly | 2:1 | 3500K | CU | 85mm f/2 | Eye-level |
| Dramatic | Split/Rembrandt | 8:1 | 5600K | CU | 85mm f/1.8 | Eye-level |

### Glasses Anti-Glare

Key light at 30-45° angle to avoid specular reflection on lenses. Never use direct frontal lighting. In multi-character scenes, ensure key light position accounts for Ali Sadikin's glasses — slight head tilt or flag can eliminate secondary reflections from fill light.

---

## 3. Cast Profile Template

When cast builder completes, generate this structure and save to `{project}/cast-profile.md`:

```markdown
# Cast Profile — {Video Title}

## Brand Identity
- **Brand Name:** {brand_name}
- **Brand Colors:** {brand_colors or "TBD — user to specify"}
- **Tagline:** {brand_tagline or "N/A"}
- **Product Category:** {product_category}
- **Institution:** {institution_name or "N/A"}

## Cast Summary
| # | Name | Role | Scenes | Identity Lock | Ref Level |
|---|------|------|--------|---------------|-----------|
| 1 | {name} | Pemeran Utama | {scene_list} | FULL | face+body+costume |
| 2 | {name} | Pemeran Utama | {scene_list} | FULL | face+body+costume |
| 3 | {name} | Pendamping | {scene_list} | PARTIAL | face only |

(Rows match actual cast count. Scene list populated after Phase 3.)

## Character 1: {Name} — PEMERAN UTAMA
- **Gender:** {gender}
- **Age Range:** {age_range}
- **Ethnicity:** {ethnicity}
- **Key Features:** {key_features}
- **Role Description:** {role_desc}
- **Costume:** {costume description, institutional uniform details, or "generic professional attire"}

### Reference Phrase (copy verbatim INLINE with SUBJECT line in ALL NB2 prompts with this character)
{Name} (Maintain exact facial identity from reference image: cast-c1-face.png) —
{ethnicity} {gender}, {age_range}, {key_features}.

**Usage:** This phrase goes INSIDE the SUBJECT/character description, NOT as a standalone header line.

### Reference Files
- `ref/cast-c1-face.png` — Face photo (front view, clear, well-lit) — MANDATORY
- `ref/cast-c1-body.png` — Full body photo (standing pose, full wardrobe visible) — MANDATORY
- `ref/cast-c1-costume.png` — Costume/uniform (front view, emblem/badge visible) — MANDATORY (if institutional)

### Wardrobe Defaults
| Context | Wardrobe |
|---------|----------|
| Professional | {wardrobe_professional} |
| Casual | {wardrobe_casual} |

### Lighting Notes
- Skin tone responds to: {kelvin_recommendation}K
- Key features to maintain: {lighting_notes for key features, e.g., "glasses → key at 30-45°"}

## Character 2: {Name} — PEMERAN UTAMA
- **Gender:** {gender}
- **Age Range:** {age_range}
- **Ethnicity:** {ethnicity}
- **Key Features:** {key_features}
- **Role Description:** {role_desc}
- **Costume:** {costume description}

### Reference Phrase (copy verbatim INLINE with SUBJECT line in ALL NB2 prompts with this character)
{Name} (Maintain exact facial identity from reference image: cast-c2-face.png) —
{ethnicity} {gender}, {age_range}, {key_features}.

**Usage:** This phrase goes INSIDE the SUBJECT/character description, NOT as a standalone header line.

### Reference Files
- `ref/cast-c2-face.png` — Face photo (front view) — MANDATORY
- `ref/cast-c2-body.png` — Full body photo — MANDATORY
- `ref/cast-c2-costume.png` — Costume/uniform — MANDATORY (if institutional)

### Wardrobe Defaults
| Context | Wardrobe |
|---------|----------|
| Professional | {wardrobe_professional} |
| Casual | {wardrobe_casual} |

### Lighting Notes
- Skin tone responds to: {kelvin_recommendation}K
- Key features to maintain: {lighting_notes}

## Character 3: {Name} — PENDAMPING
- **Gender:** {gender}
- **Age Range:** {age_range}
- **Ethnicity:** {ethnicity}
- **Key Features:** {key_features or "N/A"}
- **Role Description:** {role_desc}
- **Costume:** {costume description or "generic — follows scene wardrobe"}

### Reference Phrase (copy verbatim INLINE with SUBJECT line in ALL NB2 prompts with this character)
{Name} (Maintain exact facial identity from reference image: cast-c3-face.png) —
{ethnicity} {gender}, {age_range}, {key_features}.

**Usage:** This phrase goes INSIDE the SUBJECT/character description, NOT as a standalone header line.

### Reference Files
- `ref/cast-c3-face.png` — Face photo (front view) — MANDATORY
- `ref/cast-c3-body.png` — Full body photo — OPTIONAL
- `ref/cast-c3-costume.png` — Costume/uniform — OPTIONAL
```

**Template rules:**
- Repeat character sections for actual cast count (1–5 characters)
- Pemeran Utama sections include full wardrobe defaults + lighting notes
- Pemeran Pendamping sections are minimal (face ref mandatory, rest optional)
- Scene list in Cast Summary is filled after Phase 3 (Scene Breakdown)
- All Reference Phrase blocks must be copy-paste ready for INLINE injection into NB2 SUBJECT lines (not as standalone header lines)

---

## 4. Mandatory Character Appearances

Role-based appearance rules for each scene type:

| Scene Type | Pemeran Utama | Pemeran Pendamping | Notes |
|------------|--------------|-------------------|-------|
| Hook (opening) | YES (at least 1 Utama) | Optional | Utama with exaggerated emotion for pattern interrupt |
| Presenter segments | YES (assigned character) | If scene requires | Lip sync dialogue — face >30% of frame |
| B-Roll with humans | YES (prominent) | Supporting position | Utama always more prominent than Pendamping in frame |
| B-Roll without humans | NO | NO | Product/environment only — no character refs needed |
| CTA (closing) | YES (lead Utama) | Optional | Warm, inviting expression — direct to camera |
| Dialogue/interaction | YES | YES (if in conversation) | Max 3 characters per frame for clean composition |
| Testimonial | YES (speaking character) | As listener/reactor | Utama delivers testimonial, Pendamping reacts |
| Demo/walkthrough | YES (demonstrator) | Optional observer | Utama hands-on with product |

**Hierarchy rule:** In any frame with multiple characters, Pemeran Utama is always more prominent — closer to camera, better lit, larger in frame. Pemeran Pendamping occupies supporting position (slightly behind, beside, or angled away from camera center).

---

## 5. Reference Image Requirements by Role

| Ref Type | Pemeran Utama | Pemeran Pendamping | Specifications |
|----------|--------------|-------------------|----------------|
| Face (front view) | MANDATORY | MANDATORY | Clear, well-lit, no obstruction, neutral expression, high resolution |
| Full body | MANDATORY | OPTIONAL | Standing pose, full wardrobe visible, neutral background |
| Costume/uniform | MANDATORY (if institutional) | OPTIONAL | Front view, emblem/badge visible, full uniform from neck to shoes |
| Multiple angles | Recommended (3 angles) | Not needed | Front + three-quarter + profile for maximum identity consistency |

### Naming Convention

All reference images follow `global-promo-config.md` Section 11 naming:

| Role | Face | Body | Costume |
|------|------|------|---------|
| Cast member 1 | `ref/cast-c1-face.png` | `ref/cast-c1-body.png` | `ref/cast-c1-costume.png` |
| Cast member 2 | `ref/cast-c2-face.png` | `ref/cast-c2-body.png` | `ref/cast-c2-costume.png` |
| Cast member 3 | `ref/cast-c3-face.png` | `ref/cast-c3-body.png` | `ref/cast-c3-costume.png` |
| Cast member 4 | `ref/cast-c4-face.png` | `ref/cast-c4-body.png` | `ref/cast-c4-costume.png` |
| Cast member 5 | `ref/cast-c5-face.png` | `ref/cast-c5-body.png` | `ref/cast-c5-costume.png` |

### Product & Brand Reference Images

| Type | Naming Pattern | When Required |
|------|---------------|---------------|
| Product hero shot | `ref/product-{name}.png` | When showing specific product |
| Brand logo | `ref/brand-logo.png` | When brand must be visible |
| UI/Dashboard | `ref/brand-{product}-ui.png` | For SaaS/tech product demos |
| Packaging | `ref/product-{name}-packaging.png` | For physical products |
| Environment | `ref/env-{location}.png` | For location-specific scenes |

---

## 6. Holiday Wardrobe Swaps

Holiday wardrobe applies per cast member. Each character in `cast-profile.md` can have independent holiday wardrobe selection based on the video's release timing and cultural context.

### Available Holiday Wardrobes

| Holiday | Wardrobe | Cultural Context |
|---------|----------|-----------------|
| Chinese New Year | Slim-fit red tang jacket, gold embroidery, black turtleneck | January–February, Indonesian-Chinese community |
| Eid / Lebaran | White modern koko shirt, silver embroidery, white peci | Varies (Hijri calendar), majority Muslim audience |
| Christmas | Charcoal blazer over cream cable-knit sweater | December, Christian community |
| Diwali | Navy kurta with gold threadwork | October–November, Hindu community |
| Valentine's | Burgundy velvet blazer over white dress shirt | February 14, romantic/lifestyle content |
| Independence Day (17 Agustus) | Red-and-white themed formal attire, batik merah putih | August 17, national patriotic content |
| Kartini Day | Kebaya (female) or batik formal (male) with national colors | April 21, women's empowerment content |

### Holiday Assignment Flow

```
AskUserQuestion:
"Video ini akan dirilis saat holiday tertentu? Jika ya, wardrobe bisa disesuaikan."

Options:
A) Ya — Chinese New Year
B) Ya — Eid / Lebaran
C) Ya — Christmas
D) Ya — Diwali
E) Ya — Valentine's
F) Ya — Independence Day (17 Agustus)
G) Ya — Kartini Day
H) Tidak, pakai wardrobe default
```

If holiday selected:

```
AskUserQuestion:
"Pemeran mana yang pakai holiday wardrobe?"

Options:
A) Semua pemeran
B) Hanya Pemeran Utama
C) Hanya pemeran tertentu (pilih)
```

---

## 7. Institution-Aware Costume System

Detects institutional context from brand/product information and ensures cast costumes match the institution's uniform requirements.

### Detection Flow

1. **Auto-scan:** Engine scans `brand_name` + `product` description from Phase 1 brainstorm
2. **Keyword matching:** Compare against `global-promo-config.md` Section 12 institution keyword table
3. **User confirmation:** If match found, confirm via AskUserQuestion (see Step 5 in Section 1)
4. **Assignment:** Apply costume requirements to selected cast members

### Institution Keyword Reference

Full keyword table is maintained in `global-promo-config.md` Section 12. Key institutions include:

| Institution | Uniform Type | Common Video Scenarios |
|-------------|-------------|----------------------|
| KAI / Kereta Api Indonesia | Railway uniform (blue-black, cap, badge) | Safety training, service promo, recruitment |
| BRI / BNI / BCA / Mandiri | Banking uniform (formal, name badge, institution colors) | Product launch, CSR, digital banking promo |
| Pertamina | Energy sector uniform (red-blue, safety vest, helmet for field) | Safety campaign, fuel product, green energy |
| PLN | Electricity uniform (blue, safety gear for field) | Service reliability, smart meter, safety |
| Garuda Indonesia | Airline uniform (cabin crew kebaya, pilot uniform) | Route launch, service quality, recruitment |
| RS / Rumah Sakit | Medical uniform (white coat, scrubs, name badge) | Health service promo, facility tour, recruitment |
| Telkom / Telkomsel | Telecom uniform (red-white, technician gear for field) | Network coverage, digital product, service |
| Pos Indonesia | Postal uniform (orange, delivery gear) | Service modernization, logistics promo |

### Per-Cast Costume Assignment Rules

**If "all cast wear uniform" selected:**
- ALL Pemeran Utama: costume ref becomes MANDATORY (`ref/cast-c{N}-costume.png`)
- ALL Pemeran Pendamping: costume ref becomes MANDATORY (upgraded from optional)
- Shared institution reference: `ref/costume-{institution}.png` as the master uniform reference

**If "selective" chosen:**
- Only selected characters get costume ref requirement
- Non-uniform characters use generic wardrobe from their profile

**Costume reference naming:**
- Per-character costume: `ref/cast-c{N}-costume.png` — specific to that cast member (may vary by role/rank)
- Shared institution reference: `ref/costume-{institution}.png` — the canonical uniform template

### Costume Prompt Injection

When generating NB2 or VEO prompts for a character with institutional costume:

```
{Character Name} (Maintain exact facial identity from reference image: cast-c{N}-face.png) —
wearing official {institution_name} uniform EXACTLY as shown in cast-c{N}-costume.png,
maintaining exact badge placement, color scheme, emblem detail, and rank insignia.
Fabric texture: {uniform fabric — e.g., "pressed cotton twill", "polyester blend with matte finish"}.
```

**Usage:** This phrase goes INLINE inside the SUBJECT/character description of the NB2 prompt body. Do NOT place identity lock or costume ref as standalone header lines above the prompt.

**CRITICAL:** ALL reference images (face, body, costume, product, environment) must be embedded INLINE in the prompt text, next to the element they describe. No separate header block. No standalone identity lock lines above the prompt body. Each filename appears MAX 1x per prompt. See `global-promo-config.md` Section 16 for injection syntax per category.

**Every prompt must include a Required Reference Images table** so the user never misses uploading a file. See `global-promo-config.md` Section 16 for table format.

**Role-specific costume variations:**
- Manager/executive: formal variant (blazer, tie, polished shoes)
- Field worker/technician: functional variant (safety vest, helmet, boots)
- Customer service: front-office variant (neat, name badge prominent, institution colors)

### Costume Consistency Rules

1. Same character wears identical costume across ALL scenes (unless explicit wardrobe change in script)
2. Badge/emblem must be visible in MCU and wider shots — position on left chest pocket
3. Institution colors must match reference exactly — do not let AI model improvise colors
4. If scene has mixed uniform/non-uniform cast, uniform characters must still follow institution ref
5. For outdoor/field scenes, add appropriate safety gear (helmet, vest) while maintaining base uniform

---

## 8. Cast Interaction Templates

Templates for multi-character scenes in NB2 image prompts and VEO video prompts.

### 2-Character Scene (NB2 Image Prompt)

**Required Reference Images (upload all to `{project}/ref/` folder — place this table directly below each image heading):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{A}-face.png` | {Character A name} face | ⬜ |
| 2 | `cast-c{B}-face.png` | {Character B name} face | ⬜ |
| 3 | `cast-c{A}-body.png` | {Character A name} body | ⬜ (if Utama) |
| 4 | `cast-c{B}-body.png` | {Character B name} body | ⬜ (if Utama) |
| 5 | `cast-c{A}-costume.png` | {Character A} costume | ⬜ (if institutional) |
| 6 | `cast-c{B}-costume.png` | {Character B} costume | ⬜ (if institutional) |
| 7 | `env-{location}.png` | Environment | ⬜ |
| 8 | `product-{name}.png` | Product shot | ⬜ (if product visible) |
```

```
SUBJECT: Character {A} — {name_A} (Maintain exact facial identity from reference image: cast-c{A}-face.png), body proportions matching cast-c{A}-body.png — {ethnicity_A} {gender_A}, {age_A}, {key_features_A}... wearing {costume_A}. {If institutional: Uniform EXACTLY as shown in cast-c{A}-costume.png.}
AND Character {B} — {name_B} (Maintain exact facial identity from reference image: cast-c{B}-face.png), body proportions matching cast-c{B}-body.png — {ethnicity_B} {gender_B}, {age_B}, {key_features_B}... wearing {costume_B}. {If institutional: Uniform EXACTLY as shown in cast-c{B}-costume.png.}
INTERACTION: {action between characters — e.g., "shaking hands", "looking at laptop together", "Character A presenting to Character B"}.
POSITIONING: Pemeran Utama ({name_of_utama}) more prominent — closer to camera, better lit, occupying frame center-left (rule of thirds).
SCENE: {environment description}, environment layout EXACTLY as shown in env-{location}.png.
{If product visible: Product EXACTLY matching product-{name}.png.}
CAMERA: {shot size — MS or MWS to fit both characters} {lens — 35mm or 50mm} {aperture}.
LIGHTING: {pattern} {ratio}, {kelvin}K.
TECHNICAL: {aspect_ratio}, {resolution}, central 60% safe zone for critical action.
```

### 3+ Character Scene (NB2 Image Prompt)

**Required Reference Images (upload all to `{project}/ref/` folder — place this table directly below each image heading):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{A}-face.png` | {Character A name} face | ⬜ |
| 2 | `cast-c{B}-face.png` | {Character B name} face | ⬜ |
| 3 | `cast-c{C}-face.png` | {Character C name} face | ⬜ |
| 4 | `cast-c{A}-body.png` | {Character A name} body | ⬜ (if Utama) |
| 5 | `cast-c{B}-body.png` | {Character B name} body | ⬜ (if Utama) |
| 6 | `cast-c{C}-body.png` | {Character C name} body | ⬜ (if Utama) |
| 7 | `cast-c{A}-costume.png` | {Char A} costume | ⬜ (if institutional) |
| 8 | `cast-c{B}-costume.png` | {Char B} costume | ⬜ (if institutional) |
| 9 | `cast-c{C}-costume.png` | {Char C} costume | ⬜ (if institutional) |
| 10 | `env-{location}.png` | Environment | ⬜ |
| 11 | `product-{name}.png` | Product shot | ⬜ (if product visible) |
```

```
GROUP in {setting}:
Character {A} — {name_A} (Maintain exact facial identity from reference image: cast-c{A}-face.png), body proportions matching cast-c{A}-body.png — {full description}... wearing {costume_A}. {If institutional: Uniform EXACTLY as shown in cast-c{A}-costume.png.}
Character {B} — {name_B} (Maintain exact facial identity from reference image: cast-c{B}-face.png), body proportions matching cast-c{B}-body.png — {full description}... wearing {costume_B}. {If institutional: Uniform EXACTLY as shown in cast-c{B}-costume.png.}
Character {C} — {name_C} (Maintain exact facial identity from reference image: cast-c{C}-face.png), body proportions matching cast-c{C}-body.png — {full description}... wearing {costume_C}. {If institutional: Uniform EXACTLY as shown in cast-c{C}-costume.png.}
COMPOSITION: Pemeran Utama center/foreground. Pemeran Pendamping flanking or background.
Triangular composition — tallest character slightly back, others angled toward camera.
INTERACTION: {group dynamic from script — e.g., "team discussing around whiteboard", "group walking through facility"}.
SCENE: {environment description}, environment layout EXACTLY as shown in env-{location}.png.
{If product visible: Product EXACTLY matching product-{name}.png.}
CAMERA: {wider shot — MS to MWS} {lens — 35mm} {aperture} to fit all characters.
LIGHTING: {pattern} {ratio}, {kelvin}K — ensure all faces adequately lit.
TECHNICAL: {aspect_ratio}, {resolution}. Central 60% safe zone.
NOTE: Max 3 characters per frame for clean composition.
If 4+ cast needed in a sequence, use shot/reverse-shot or group-then-individual sequence.
```

### 2-Character Dialogue Exchange (VEO Video Prompt)

```
~{duration}s, {resolution}, {aspect_ratio}.
Camera: {shot size — MCU to MS, accommodate both speakers}, {lens}, {movement — subtle or static}.

Character {A} — {name_A}, appearance matching cast-c{A}-face.png{If institutional: , wearing uniform as shown in cast-c{A}-costume.png} — and Character {B} — {name_B}, appearance matching cast-c{B}-face.png{If institutional: , wearing uniform as shown in cast-c{B}-costume.png}.

Speaker A says: {line, max 15 words, natural spoken rhythm}.
[0.5s pause, reaction shot of Character {B}, visible micro-expression]
Speaker B says: {response, max 15 words}.

Character {A} during {B}'s line: {micro-reaction — nodding, slight smile, furrowed brow}.
Character {B} during {A}'s line: {listening pose — attentive gaze, slight lean forward}.

SFX: {effects — e.g., "soft keyboard clicks", "ambient office hum"}.
Ambient: {atmosphere — e.g., "modern office, diffused daylight, gentle air conditioning hum"}.
No subtitles, no text overlays, no watermarks, no audience sounds.

Maintain exact appearance from reference images for both characters throughout clip.
NOTE: VEO lip sync = 1 speaker at a time. Sequential delivery, NOT simultaneous.
For longer exchanges, split into separate 8s clips with consistent camera angle.
```

**Required Reference Images (upload all to `{project}/ref/` folder — place below heading, before prompt body):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{A}-face.png` | {Character A name} face | ⬜ |
| 2 | `cast-c{B}-face.png` | {Character B name} face | ⬜ |
| 3 | `cast-c{A}-costume.png` | {Char A} costume | ⬜ (if institutional) |
| 4 | `cast-c{B}-costume.png` | {Char B} costume | ⬜ (if institutional) |
| 5 | `env-{location}.png` | Environment | ⬜ |
```

### 3+ Character Group Scene (VEO Video Prompt)

```
~{duration}s, {resolution}, {aspect_ratio}.
Camera: {wider shot — MS to MWS}, {lens — 35mm}, {movement — slow dolly or static}.

Group of {N} people in {setting}:
Character {A} — {name_A}, appearance matching cast-c{A}-face.png{If institutional: , wearing uniform as shown in cast-c{A}-costume.png}: {position in frame, action}.
Character {B} — {name_B}, appearance matching cast-c{B}-face.png{If institutional: , wearing uniform as shown in cast-c{B}-costume.png}: {position in frame, action}.
Character {C} — {name_C}, appearance matching cast-c{C}-face.png{If institutional: , wearing uniform as shown in cast-c{C}-costume.png}: {position in frame, action}.

Speaker says: {line, max 15 words}.
Other characters: {group reaction — nodding, looking at speaker, taking notes}.

SFX: {effects}.
Ambient: {atmosphere}.
No subtitles, no text overlays, no watermarks, no audience sounds.

Maintain exact appearance from reference images for all characters throughout clip.
NOTE: Only 1 character speaks at a time. Group reactions are non-verbal.
If multiple characters need to speak, use sequential 8s clips.
```

**Required Reference Images (upload all to `{project}/ref/` folder — place below heading, before prompt body):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{A}-face.png` | {Character A name} face | ⬜ |
| 2 | `cast-c{B}-face.png` | {Character B name} face | ⬜ |
| 3 | `cast-c{C}-face.png` | {Character C name} face | ⬜ |
| 4 | `cast-c{A}-costume.png` | {Char A} costume | ⬜ (if institutional) |
| 5 | `cast-c{B}-costume.png` | {Char B} costume | ⬜ (if institutional) |
| 6 | `cast-c{C}-costume.png` | {Char C} costume | ⬜ (if institutional) |
| 7 | `env-{location}.png` | Environment | ⬜ |
```

### Character Handoff Between Scenes (VEO Extension)

When transitioning from one character's scene to another character's scene:

```
[End of Scene X — Character {A} speaking]
Final 1s: Character {A} holds expression, looks toward camera-right (direction of next character).

[Start of Scene X+1 — Character {B} enters]
NEW generation (not extension). Use First+Last Frame mode.
Start frame: NB2 image of Character {B} in new setting.
End frame: NB2 image of Character {B} completing the scene's action.
Match: same lighting Kelvin, same color palette, same aspect ratio as previous scene.
Use "Last Frame Secret": export final frame of Scene X → feed into NB2 as color/lighting reference for Scene X+1 start frame.
```

### Solo Character Scene (Single Cast Member)

For scenes with only 1 character (most common for presenter segments):

**Required Reference Images (upload all to `{project}/ref/` folder — place this table directly below each image heading, before prompt body):**
```markdown
| # | Filename | Content | Upload Status |
|---|----------|---------|---------------|
| 1 | `cast-c{N}-face.png` | {Character name} face | ⬜ |
| 2 | `cast-c{N}-body.png` | {Character name} full body | ⬜ (if Utama) |
| 3 | `cast-c{N}-costume.png` | Costume/uniform | ⬜ (if institutional) |
| 4 | `env-{location}.png` | Environment | ⬜ (if location-specific) |
| 5 | `product-{name}.png` | Product shot | ⬜ (if product visible) |
```

```
SUBJECT: {name} (Maintain exact facial identity from reference image: cast-c{N}-face.png) — {ethnicity} {gender}, {age_range}, {key_features}, body proportions matching cast-c{N}-body.png... wearing {costume}. {If institutional: Uniform EXACTLY as shown in cast-c{N}-costume.png.}
ACTION: {what character is doing in this scene}.
EXPRESSION: {emotional state — confident, curious, concerned, excited}.
SCENE: {environment description}{If environment ref: , environment layout EXACTLY as shown in env-{location}.png}.
{If product visible: Product EXACTLY matching product-{name}.png.}
CAMERA: {shot size} {lens} {aperture}.
LIGHTING: {pattern} {ratio}, {kelvin}K.
TECHNICAL: {aspect_ratio}, {resolution}.
```

This is the default template for most scenes. Multi-character templates from above are only used when 2+ characters share the frame.

---

## VOICE Block (v3.0.0) — a speaking character carries its own voice

Any cast member with a spoken line gets a `VOICE:` block in `cast-profile.md`. Without one, Phase 6
stops and asks rather than picking a voice, because a substituted voice is worse than a missing one.

```markdown
VOICE:
  provider: elevenlabs
  voice_env: ELEVENLABS_VOICE_C1        # env var NAME holding the voice id — never the id itself
  model: eleven_multilingual_v2         # never v3
  settings: stability=0.55, similarity_boost=0.8, style=0.3, speed=0.95
  source: tts | native+changer
  description: "<10-15 words, verbatim in every platform prompt for this character>"
```

**Naming convention for `voice_env`:** `ELEVENLABS_VOICE_C{N}` for cast slot N,
`ELEVENLABS_VOICE_NARRATOR` for the narrator slot. The value lives in the user's `.env`; this repo
only ever names the variable, the same rule that forbids hardcoding a client name.

**`source` picks itself** from whether the character speaks on camera:

- Face over 30% of frame while speaking → `native+changer`. The platform speaks so the lips match,
  then the voice is converted in Phase 6.
- Never speaks on camera → `tts`. ElevenLabs speaks it directly.

The **Ali Sadikin preset** fills a Pemeran Utama slot as before; its VOICE block reads
`voice_env: ELEVENLABS_VOICE_C1` and `source: tts` for narration, and the preset does NOT carry a
voice id — the user supplies it in their own `.env`.

Full workflow, the 0.05s Voice Changer tolerance, and the prompt-level discipline rules live in
`reference/post-production/11-voice-cast-and-vo.md`.
