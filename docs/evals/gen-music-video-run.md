# gen_music.py video — real run (GV-8 Phase L)

Date: 2026-09-29. Spend approved by Ali for one request. Master: `kelompok-K1.mp4` from the
`catalog-4` project (48.541 s, 1080p, 29 MB) copied to a scratch project as `output/master.mp4`.

## Commands

```bash
python3 tools/gen_music.py video <scratch> --dry-run
python3 tools/gen_music.py video <scratch> --description-file desc.txt --tags cinematic,tense,documentary
python3 tools/gen_music.py video <scratch> --description-file desc.txt --tags cinematic,tense,documentary   # again
```

`desc.txt`: "Understated documentary underscore for an Indonesian fleet-operations story: sparse
piano over a low pulse, tension that lifts slightly at each cut, no vocals, no drums until the
last third." It was passed by hand because this project's `av-script.md` has no music direction
lines (`default_description` returned none — correct behaviour).

## Result

| Step | Exit | Output |
|---|---|---|
| dry run | 0 | `WOULD request video-to-music: 3.1 MB, 48.541s, model music_v2, 0 tags` |
| real request | 0 | `wrote output/music.mp3 (48.51s)` in 21.7 s wall clock |
| same command again | 0 | `up-to-date: output/music.mp3 (master unchanged)` — no request |

- Proxy: 3.1 MB picture-only (from a 29 MB master); deleted after the request (`.tmp/` empty).
- `output/music.mp3`: mp3, 44.1 kHz stereo, 142 kb/s, 48.51 s against a 48.54 s master
  (0.03 s short). Normalised by the palette defaults to **−20.0 LUFS integrated, −9.1 dBFS
  true peak**.
- `renders.json`: one entry `file: output/music.mp3, phase: "6", model: music_v2, status: done`.
  No API key in the file.
- Not measured here: whether the bed audibly follows the cuts. That needs a listen against the
  picture, recorded as open debt.

Finding fixed after this run: the dry run showed `0 tags` — the spec asked for tags from the
project's tone and the tool had none. `1537169` adds `default_tags()`: with no `--tags`, the tone
in `strategic-brief.md` plus the matching palette mood's positive descriptors are sent.
