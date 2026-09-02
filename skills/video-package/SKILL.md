---
name: video-package
description: >
  Phase 7 of AI video production. Turns a finished video into what makes someone click: one
  locked title, three distinct thumbnail bets built on different levers, and one
  value-forward description, with an honesty guardrail that keeps the frame's promise
  inside what the video delivers. Decides WHAT to bet on; the image itself is rendered by
  the image plugin through a soft reference, never here. Runs standalone or after Phase 6.
  Triggers on: video package, packaging, thumbnail, judul video, cover video, title ideas,
  bikin thumbnail, deskripsi video, phase 7, package this video.
---

# Video Package — Phase 7: Title, Thumbnail Bets, Description

## Overview

A finished video still has to be opened. This phase produces one locked title, three thumbnail
**bets** on three different levers, and a description — plus the honesty check that keeps the frame's
promise inside what the video actually delivers.

It decides what to bet on. It does not render the image: that belongs to
`ai-image-carousel-prompt-gen`, the single source of truth for every image this ecosystem makes.

## Prerequisite

- `{output_folder}/av-script.md` — to check every promise against what the video keeps
- `{output_folder}/strategic-brief.md` — target market, awareness level, platform
- A finished video helps but is not required: packaging can run before the edit.

## Reference Files (Read On-Demand)

| Task | Read |
|------|------|
| ANY generation | `reference/global-promo-config.md` (ALWAYS FIRST) |
| Packaging rules | `reference/post-production/15-packaging.md` |
| Platform shape | `reference/storytelling_script_gen/F9_Platform_Adaptation_Matrix.md` |
| Hook language | `reference/storytelling_script_gen/F5_Hook_Vault.md` |

### CONTEXT LOADING — Phase 7
READ these files ONLY: `global-promo-config.md`, `15-packaging.md`, `F9`, and `F5`.
Plus `av-script.md` and the strategic brief's target-market section. Nothing from the image or video
guides applies here.

---

## Hard Rules (NON-NEGOTIABLE)

1. **No image generation happens in this plugin.** Emit concept briefs and hand them to
   `ai-image-carousel-prompt-gen`. The two-plugin split is not reopened here.
2. **The reference to that plugin is soft.** Absent, this skill prints the briefs and names what is
   missing. `plugin.json` declares no dependencies, deliberately.
3. **Cold-start CTR rules are labelled uncalibrated** every time they are used.
4. **Never quote a target CTR the user has not measured.**
5. **The frame may promise only what the video keeps.** A promise not delivered on screen is cut.
6. **One title across all three bets** — otherwise the test measures two variables at once.

---

## Workflow

### Step 7.1: Establish calibration mode

```
AskUserQuestion:
"Sudah punya data CTR sendiri?"

A) Belum ada video / belum ada data — pakai aturan bawaan, dan katakan
   terus terang bahwa itu belum terkalibrasi
B) Sudah, 10+ video dengan data CTR — datamu yang menang atas aturan bawaan
```

Under A, every output carries the line: *"these are uncalibrated defaults; your own CTR data will
beat them."*

### Step 7.2: Establish the platform shape

Read the platform from `strategic-brief.md`. Where the platform has no cover — Instagram Reels,
TikTok — say so and shift the work to the first second of the video instead of producing three bets
nobody will use.

### Step 7.3: Lock one title

Concrete promise, a magnet word, and a barrier dropped. Written for the awareness level already
chosen in Phase 1. It stays the same across all three bets.

### Step 7.4: Three bets on three levers

| Bet | Lever | Bets on |
|---|---|---|
| A | Outcome | the result, as a number or a state change |
| B | Tension | the problem, before it is solved |
| C | Subject | a face or an object, doing the thing |

Two bets that differ only in colour teach nothing. Each one gets a concept brief: lever, promise,
focal hierarchy (three steps maximum), text budget, and what must be recognisable.

### Step 7.5: Honesty check

For each bet, name the frame in `av-script.md` that delivers its promise. A bet with no such frame is
rewritten or dropped. Present this check to the user — it is the step most likely to be waved
through, and the one that costs the client's credibility when it is.

### Step 7.6: Description

Value forward. What the viewer gets, in the first two lines, before any link.

### Step 7.7: Hand off the render

Pass the three concept briefs to `ai-image-carousel-prompt-gen`. If it is not installed:

> "Thumbnail rendering lives in `ai-image-carousel-prompt-gen`, which is not installed here. The
> three concept briefs below are complete and can be taken there, or to any image tool."

Then print them.

---

## Quality Gates

- [ ] One title, unchanged across all three bets
- [ ] Three bets on three DIFFERENT levers, not three variations of one
- [ ] Every promise traced to a frame in `av-script.md`
- [ ] Calibration mode stated in the output; uncalibrated defaults labelled as such
- [ ] No target CTR quoted that the user has not measured
- [ ] No image generated in this plugin
- [ ] Platform shape respected — no bets produced for a platform with no cover

## Output

`{output_folder}/packaging.md` — the locked title, three concept briefs, the description, the
honesty check, and the calibration mode it was written under.
