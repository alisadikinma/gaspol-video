# Subtitles and Captions (Phase 6 pass 4)

Most promo views on IG, TikTok and LinkedIn happen with the sound off. A video without captions is a
video most of its audience cannot follow.

Schema (`subtitle-plan.json`) in `10-post-production-pipeline.md`. Style values in
`global-promo-config.md` §30. Tools: `tools/gen_subs.py`, `tools/burn_subs.py`.

---

## 1. The text comes from the script. Always.

The usual pipeline transcribes the audio and then repairs the transcript against the script. This
plugin does not need the first half: it WROTE the narration, so the words are already known and
correct, including every product name and piece of jargon a recognizer would mangle.

A recognizer supplies **timing only**, and only where nothing else can:

| Timing source | Used for | Cost |
|---|---|---|
| `tts-timestamps` | anything ElevenLabs spoke | free — it comes back in the same response |
| `assemblyai` | dialogue the video platform generated | one API call per clip |
| `manual` | anything a human times by hand | — |

**Nothing is guessed.** A scene with no timing source is listed as untimed and left out, rather than
given invented timings that drift a little further with every line.

---

## 2. Keyterms are derived, not drafted

The recognizer still needs help with proper nouns for the `assemblyai` path. The editor asks the user
to write a keyterms file per video; here the list is built from `strategic-brief.md` (product name,
brand, domain equipment from the six research queries) and `cast-profile.md` (names), then written
into `subtitle-plan.json` as `keyterms` where a wrong entry is visible and can be corrected.

---

## 3. Reading width, and what happens when a line is too long

Captions wrap at the reading width and are **never clipped**. When a line does not fit in
`max_lines` at `max_chars_per_line`, the cue is **split into consecutive cues** sharing the line's
time in proportion to its characters.

The alternative — squeezing — either drops words or blows past the reading width, and both are worse
than showing the sentence in two takes.

Defaults are 38 characters and 2 lines. Vertical formats need larger type and a higher bottom margin
than 16:9, because the platform's own UI sits over the lower band. See §30.

---

## 4. Two guards before anything is burned

Both failures are invisible until someone watches the finished file:

1. **Font coverage.** A font that cannot draw a character renders a box, and a box ships. Every
   character in every cue is checked against the chosen font.
2. **Contrast.** Subtitle colour is checked against its outline and backing at a 4.5:1 floor. Below
   that the caption is unreadable on exactly the frames whose background happens to match it.

---

## 5. This does not contradict the `no subtitles` prompt rule

Every platform prompt still carries `no subtitles, no audience sounds, no text overlays`, and that
stays. The two rules are about different things:

- The **prompt negative** stops the video model hallucinating text INTO the picture, where it comes
  out warped and cannot be corrected.
- **Burned captions** are added afterwards, from text this plugin already holds, at a size and
  position it chose.

One is a defect; the other is a deliverable.

**The em-dash ban does not apply here either.** `—` is banned in spoken text because the audio engine
mistranslates it. A printed caption is not read aloud by anything, so the em dash stays exactly as the
script wrote it.

---

## 6. Degradation

No `ASSEMBLYAI_API_KEY`: cues from TTS timestamps are still built, the scenes that needed the
recognizer are listed as untimed, and the manual command is printed.

No ffmpeg: the `.srt` is still written. The video ships with a sidecar subtitle file, which most
platforms accept, and the skill says the burn-in did not happen.
