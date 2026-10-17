# F13: Short-Form Timeline (9:16, up to 60 s)

**When used:** the video is vertical 9:16 and at most 60 s (`aspect: 9:16`). Skip it for long-form films.

**What it is:** second-by-second timing for the stages F12 names. F12 says what each stage must contain; F13 says when it happens. It is imitation of **structure and timing**, never of content: no footage, voice, face, script, music or sound effect of any reference channel is copied.

**What it does not do:** F13 adds timing to F12 and never overrides the 9 Commandments, F5 (Hook Vault) or F6 (CTA Vault). When F13 and a Commandment disagree, the Commandment wins. Layout numbers (safe area, subtitle size, title size and position) live in `media/layout-profiles.json`, not here.

## Source and how to read the tags

- **Source: NotebookLM notebook `fd70ee32` ("SAMUEL-STYLE 2026-10")**, queried 2026-10-17. F12 comes from notebook `114215f6`.
- `[DATA]` = stated by the notebook, or measured on the 6 Samuel Christ Shorts (`docs/evals/short-form-layout-measurement.md`).
- `[TAFSIRAN]` = our interpretation, turned into a testable line.
- Timings are advice from a source, not platform data.

## Timeline

| Tahap | Detik | Purpose |
|---|---|---|
| Thumbnail | 0-1 | Cover frame (optional row) |
| Hook | 0-3 | Curiosity gap |
| Foreshadow | 3-6 | Clue, never the answer |
| Body | 6-50 | Points or escalation |
| CTA | last 2-4 s (50-54) | Specific follow ask |

`[TAFSIRAN]` The `av-script.md` table for 9:16 carries the columns `Tahap` and `Detik`. `python3 tools/viral_checklist.py timeline <av-script.md>` checks the order Thumbnail (optional), Hook, Foreshadow, Body, CTA; that Hook ends by 3 s, Foreshadow by 6 s and Body by 50 s; that the CTA lasts 2-4 s and is the last stage; and that the total stays within `--max-s` (default 60, the brief's `max_duration_s`). Tolerance is `timeline_tolerance_s` from `media/layout-profiles.json`, applied to the late side (a CTA under 2 s always fails).

## Thumbnail (frame 0-1 s)

- **Rule:** a big, contrasting title in the centre safe zone, a shock or number element, an expressive face. `[TAFSIRAN]`
- **Rule:** mistakes are a blurry or dark frame, a flat face, no text. `[TAFSIRAN]`
- **Rule:** the 6 measured Samuel Shorts carry NO title on the cover, so a cover title is our choice, not his pattern. `[DATA]`

## Hook (0-3 s)

- **Rule:** a multi-sensory hook = a bold statement (narration) + bold on-screen text + sudden visual motion, which opens a curiosity gap. `[DATA]`
- **Rule:** examples: "Seberapa kaya Ghozali?", "Sini aku bongkar teknik marketing odol yang buat kamu mau beli odol kamu", "Ini cara marketing supermarket agar buat kamu belanja lebih banyak". `[DATA]`
- **Rule:** no greeting ("Hi guys"), no static first second, no deceptive clickbait; the body keeps the promise. `[DATA]`

## Foreshadow (3-6 s, 1-3 s long, right after the hook)

- **Rule:** techniques are a visual micro-clue of 0.5-1 s on the most unique element; a micro-reaction or an audio snippet of the conflict first; a mystery prop (two objects shown before they are compared). `[DATA]`
- **Rule:** show the conflict process or the shocked reaction, never the answer; cut right before the resolution. `[DATA]`
- **Rule:** examples: Dr Richard house tour, a glimpse then "Segokil apa ya rumah ini, nonton sampai habis ya!"; bank data leak test, a CS call snippet "Saya tawarkan pemblokiran..." then "Gila bisa ditutup hanya kayak gitu doang!". `[DATA]`
- **Rule:** mistakes are leaking the result, and a fake foreshadow that the video never shows. `[DATA]`

## Body (6-50 s)

- **Rule:** a points system (a 5 to 1 listicle such as "5 Barang Murah": sandal jepit, bensin, mie instan, gorengan, tempe Rp10.000 jadi Rp50.000 di Eropa) or an escalation or chronology. `[DATA]`
- **Rule:** "the chat" tone, no fluff, no dead air, never drift from the hook's promise. `[DATA]`

## CTA (last 2-4 s)

- **Rule:** specific and with a value: "Follow akun ini biar kamu cepat dapatkan 1 miliar pertamamu", "Follow ini kalau kamu suka konten seperti ini". `[DATA]`
- **Rule:** plugin standard: follow @alisadikinma plus a reason ("follow @alisadikinma biar ..."). `[TAFSIRAN]`
- **Rule:** mistakes are a long CTA in the middle of the video and a bare "jangan lupa subscribe". `[DATA]`

## Watermark

- **Rule:** visible from 0 to 100 % of the video, in a safe corner or area, never covering a face or the main text. `[TAFSIRAN]`

## Supporting rules

- **Rule:** loop ending: the last line hangs and reconnects to the hook ("...Dan itulah..." then "5 barang yang murah di Indonesia tapi mahal di luar negeri"). `[DATA]`
- **Rule:** title formula [Sensation] + [Public figure or brand] + [specific number], ALL CAPS with "!", for example "SISKA KOHL BELI NASI GORENG SEHARGA 400 JUTA! #shorts". `[DATA]`
- **Rule:** a cut, angle or zoom change every 1-3 s. `[TAFSIRAN]`
- **Rule:** b-roll matches the spoken word 100 %. `[TAFSIRAN]`
- **Rule:** BGM follows the emotion and sits under the voice; cut all dead air. `[TAFSIRAN]`
- **Rule:** captions word by word in the centre safe zone, bold, with contrast and shadow. `[TAFSIRAN]`
