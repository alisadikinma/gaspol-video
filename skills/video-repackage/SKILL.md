---
name: video-repackage
description: >
  Repackage someone else's video into Ali's own version. The user shares a link (Instagram Reel,
  TikTok, YouTube Short). The skill downloads it, cuts it into scenes, uses each scene as an image
  reference, keeps the storyline but regenerates every image asset with gpt-image-2, localises the
  cast and costume for an Indonesian audience, and then runs the normal kelompok production
  (VO in Ali's cloned voice, VEO clips, Remotion, cut, approval, final post). Adds the standard
  Ali packaging: a 3-second hook, a thumbnail at the front, and a follow CTA that shows @alisadikinma.
  Triggers on: repackage, repackaging, ambil dari link, tiru video ini, versi saya, remake reel,
  konten orang lain, link instagram, link reel, bikin ulang video ini.
---

# Video Repackage: from someone else's link to Ali's version

Read first: `docs/pembelajaran-rea.md` (what went wrong and right on the REA video). This skill
reuses the whole production line; it only adds the front end (ingest, analysis, localisation) and
the packaging rules.

## Rules that do not bend

1. **Storyline is kept, assets are new.** Same beats, same order, same message. Every image, face,
   costume and place is regenerated. Never reuse the source's frames, voice, music or footage in
   the output. Source frames are references for generation only.
2. **Indonesian audience by default.** Cast and costume become Indonesian: face, skin, clothing,
   setting, signage, plates, money, language on screen.
   **Exception:** when the product itself is aimed at another country (an India-only app, a Japan
   transit card, a local-language tool), the cast, costume and setting stay as the product's market.
   Decide this in step 2 and write the reason in `strategic-brief.md`.
3. **Default image model is `gpt-image-2`** (via the indusia `generate_image` MCP, `quality high`,
   `2K`, 9:16, with reference images). Use another model only when the user says so.
4. **Ali's voice, Ali's face.** Narration is the ElevenLabs clone of Ali (same voice everywhere,
   never a system voice). Presenter is Ali from the approved face references.
5. **The first 3 seconds decide everything.** The video opens on a hook (the strongest, most curious
   moment, often moved from the end), not on an intro. Details in "Packaging".
6. **Say where it came from.** Keep the source link in `strategic-brief.md`. The repackage changes
   the words, images and voice, but the idea belongs to someone. Mention the creator in the caption
   when the idea is theirs ("ide dari ..."), and do not copy their script word for word.
7. **Never spend credits unasked.** A VEO clip or image regeneration is paid. Ask before each repeat.

## Flow

### 1. Ingest
```bash
python3 -m tools.vidkit ingest "<url>" {output_folder}/ref/sumber
python3 -m tools.vidkit scenes {output_folder}/ref/sumber/source.mp4 {output_folder}/ref/sumber/scenes
```
`scenes.json` lists every scene with start, end, a clip, and first/mid/last stills. A source with a
few very long scenes (a screen recording) is normal: those become Remotion shots, not VEO clips.
Look at the contact sheet (`vidkit sheet`) and fix the cut by hand if the detector missed or
over-split (change `--threshold`: 0.2 sensitive, 0.5 hard cuts only).

### 2. Read the source
- Transcript with timings: `whisper-cli` (`-l auto`, then `-l id`). Write the original script down.
- For each scene note: what is said, what is shown, why it is there (hook, proof, step, CTA).
- Who is in it, what they wear, where, and who the product is for. Decide the localisation
  (rule 2) and ask the user only when the product's market is unclear.
- Check every factual claim in the source (numbers, prices, "free", "10 minutes"). Keep only what
  can be backed up. A claim the source made does not become true because you repeated it.

### 3. Storyline map
One table, scene by scene: source scene, beat, new narration (Indonesian, Ali's voice, short
sentences), new visual, production method (VEO presenter clip / Remotion shot / screen recording),
reference still. Move the strongest beat to the front as the hook. Show the table and wait for approval.
This is the gate where the user changes the story; after it, only fixes.

### 4. Assets with gpt-image-2
- One keyframe per scene, with the source mid-frame (and first/last when the scene moves) as the
  reference for composition and camera, and Ali's face/outfit references for identity.
- Prompt order: identity, localised costume and place, composition copied from the reference,
  props with real size, text that must be readable (exact spelling, side of frame, position).
- Text on clothing or props is rendered inside the image, never pasted on later (it jitters and
  looks fake). Ask for the exact side ("on the LEFT half of the image") or it will flip between scenes.
- Keep a living character (a pet, a mascot) consistent by giving the same reference every time.
- Look at every keyframe at full size before spending a video credit on it.

### 5. Production
Hand over to the normal line. Nothing here is new, do not re-explain it:
`video-gen` (VO first, then clips, kelompok of at most 5 scenes) -> voice change ->
`video-explainer` (Remotion) -> `video-post K{N}` (cut, approval) -> `video-post --final`.
Gates that must pass: ASR on every clip with speech (a dropped sentence looks fine on screen),
A/V gate 0.04 s, loudness -14 LUFS with true peak under -1 dBFS.

### 6. Packaging (every video)
| Item | Rule |
|---|---|
| Hook | 0 to 3 s. A question, a surprise or a joke that makes the viewer need the answer. Visible text under 6 words. The REA video opens on the blackout joke and shout before any intro. |
| Thumbnail | Built from the most curious scene. Hide the key thing (blur the logo/answer) so people wonder. A headline of 3 to 6 words that says the result, not the topic. Keep text above y 1540 (platform UI covers the bottom). Put it as cover metadata AND on the first 4 frames. Hide subtitles on those frames. |
| Title | Result plus a number or contrast. Offer 5, recommend 1, say which numbers are unproven. |
| CTA | Near the end: ask a question that earns a comment, then a follow popup with `@alisadikinma` (avatar, name, FOLLOW button, cursor that clicks, button turns to "Mengikuti"), centered on screen. |
| Watermark | `@alisadikinma` at the centre, 12% opacity, whole video. |
| Subtitles | Karaoke, two words at a time, accent colour on the active word, kept clear of overlays. |
| Copy | One text per platform (Instagram, TikTok, Threads max 500 chars, LinkedIn, YouTube Shorts). Pull for a two-sided debate. Include a licence/legal note when the topic needs one. Do not claim trend data you did not fetch. |

### 6b. Tools for the packaging (do not rewrite them)
| Need | Use |
|---|---|
| Karaoke subtitles + watermark | `python3 -m tools.vidkit karaoke`. Default `--profile short-organic`: 56 px, 4 words in 2 lines, last baseline about 61.7% from the top. `--profile none` = the old look |
| Cover title inside the safe area | `python3 -m tools.vidkit title <img> "<text>" <out>` |
| Text and watermark in the 9:16 safe area, off the face | `python3 tools/layout_gate.py check <project> --video <mp4> --ass <ass> [--thumb <png>]`; not final until it exits 0 |
| Follow popup, "Ssst!", "WOW!", thumbnail art | Remotion `lib/ali-effects.tsx`: `FollowModal`, `ShushEffect`, `WowBurst`, `ThumbCover` |
| Logo that must sit on a prop (not look pasted) | `vidkit unwhite`, then `mix-blend-mode: multiply`, a little blur and grain |
| Final mix, loudness, thumbnail on first frames and as cover | `python3 -m tools.vidkit mixdown plan.json` |

### 7. Hand-off
Report plainly: what was made, what was checked, what was NOT (usually: audio listened by a human),
which claims are unproven, how many credits were spent and on what.
