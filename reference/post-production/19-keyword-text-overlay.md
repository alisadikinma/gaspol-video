# Keyword Text Overlay (animated highlight over a speaker)

Use it when a speaker or narrator says the one phrase the viewer must keep ("Barang baru keluar
duluan", "Karyawan lama resign"). It is the film's kinetic-typography beat, not a caption.
Not a subtitle (`16-subtitles-and-captions.md`) and not a Remotion card (`12-remotion-explainer.md`).
Tool: `tools/keyword_cards.py`. Source: Ekaputra film K1, user's reference images, 2026-10-03.

## 1. Look (user-approved, do not restyle)

- **No box, no pill, no background.** A boxed label was rejected on first try.
- **Stacked lines**, tight leading, left-aligned. Plain words small white bold sans (~62 px).
  The **keyword big in gold serif italic** (~106–156 px). A danger word (expired, rugi, telat,
  kewalahan) is red serif italic instead of gold.
- Soft dark drop shadow only, so the text reads on a bright wall.
- Reference: small white "Minimal" / big gold italic "3 Sample" / small white "harga cash".

## 2. Motion and timing

- Each phrase is its own block. It **flies in from the screen edge (0.35 s, ease-out)** when the
  keyword is spoken, **flies out (0.25 s)**, and the next block overlaps it by ~0.15 s.
- Cue `in` = start of the first word of the phrase (minus 0.1 s), `out` = end of the last word + 0.3 s.
  Take word times from the voice (`whisper-cli -ml 1 -sow`, or the TTS alignment), never by eye.
- Three to five words per block. One keyword per block.

## 3. Placement

- Beside the speaker, never on the face or mouth. Look at a frame first. Left or right of a
  centred speaker; if a blurred foreground person sits on one side, use the other.
- A card on the right edge: `x = 1920 - card_width - 10` (the tool prints the width).
- Keep it off other burned text (subtitles at the bottom, a Remotion card).
- Over a red flash keep the keyword gold, not red (red on red disappears).

## 4. Red alarm flash behind a person (optional)

For a "danger" beat ("ini bukan yang pertama"): flash the **background only**, never the person.
Paint a grayscale mask once (white = may flash, black = Pak X, foreground person, table, glass),
feather it 3–6 px, pass it as `flash.mask`. Blink 0.3 s period, alpha 0.45, start exactly on the
word, not before it. Pair with a short alarm SFX (`14-sfx-design.md`) at the same moment, volume
low enough to keep the voice clear. Full-frame `drawbox` is wrong: it tints the face and shirt.
Do not let `maskedmerge` do it: in yuv420 the chroma leaks and tints the person; use `alphamerge`.

## 5. Workflow (per kelompok, after the clips and voice exist)

1. Pick the phrases with the user, or from the script lines marked keyword.
2. Get word times from the final voice track.
3. Write `spec.json`, run `python3 tools/keyword_cards.py render clip.mp4 out.mp4 spec.json`.
4. Check three frames: in, hold, out. Fix placement, not the style.
5. Record the cue times in `work/` so a re-cut can rebuild them.
