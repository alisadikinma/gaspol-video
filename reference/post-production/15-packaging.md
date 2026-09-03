# Packaging (Phase 7)

One locked title, three distinct thumbnail bets, one value-forward description. Adapted from
`claude-youtube-editor` (see NOTICE), with the CTR rules kept and the rendering removed.

---

## 1. What this owns, and what it does not

| Owns | Does not own |
|---|---|
| the title, and locking it | generating the thumbnail image |
| three distinct thumbnail BETS | the image prompt's craft |
| the description | the face kit |
| the honesty guardrail | |

Image generation belongs to `ai-image-carousel-prompt-gen`, which is the single source of truth for
every image this ecosystem makes — carousels, keyframes, covers, thumbnails. That split was decided
in 2026-06 and this phase does not reopen it.

The routing is a **soft reference**. If that plugin is not installed, this phase prints the concept
briefs and says which capability is missing. It never declares a dependency: `plugin.json`
dependencies are all-or-nothing, and a renamed or yanked third-party entry would disable every
unrelated skill shipped here.

---

## 2. The model, before the rules

**Views = Reach x CTR.** Two levers, two different causes.

- **Reach** comes from the TOPIC. Packaging cannot fix a low-ceiling topic.
- **CTR** comes from packaging craft. This is the only lever here.

Good packaging on a narrow topic produces good CTR and modest views. That is correct behaviour, not
a packaging failure. Never blame the title when CTR is healthy and views are small.

---

## 3. Calibration, and honesty about it

The inherited rules were derived from one channel's CTR data. **They are a bet about YOUR audience,
not a fact.**

- **Cold start, no data yet.** Use them, and say so in the output: *"these are uncalibrated defaults;
  your own CTR data will beat them."* Start logging CTR from the first video.
- **Calibrated, ten or more videos with CTR.** Your data wins over anything written here.

**Never quote a target CTR the user has not measured.**

---

## 4. Three bets, one title

The title is locked first and does not vary across the bets, so the test measures the THUMBNAIL and
nothing else. Three bets means three distinct levers, not three variations of one image:

| Lever | What it bets on |
|---|---|
| Outcome | the result, stated as a number or a state change |
| Tension | the problem, before it is solved |
| Subject | a face or an object, doing the thing |

Two bets that differ only in colour teach nothing.

---

## 5. Honesty guardrail

**The frame may promise only what the video keeps.** A thumbnail that implies a result the video
does not show buys one click and loses the next ten, and for a B2B promo it costs the client's
credibility rather than yours.

Check each bet against `av-script.md`: is the promise in this frame actually delivered on screen?

---

## 6. Platform is not one shape

`F9_Platform_Adaptation_Matrix.md` already differs by platform, and packaging follows:

| Platform | What the cover is doing |
|---|---|
| YouTube | a thumbnail competing in a grid; CTR rules above apply directly |
| LinkedIn | a first frame seen while scrolling with sound off; the caption carries more than the image |
| Instagram, TikTok | often no cover at all — the first second IS the packaging |

Where there is no cover, say so rather than producing three bets nobody will use.

---

## 7. Hand-off contract

For each bet, emit a concept brief: the lever, the promise, the focal hierarchy, the text budget, and
what must be recognisable. Hand those to `ai-image-carousel-prompt-gen`. With that plugin absent,
print the briefs and name what is missing.
