# gen_music.py — real run

Date: 2026-09-13. One ElevenLabs Music generation, billed.

## Command

```bash
cd .claude/worktrees/gv-2
set -a; . /Users/alisadikin/Drive-D/claude-plugin/gaspol-video/.env; set +a
/opt/homebrew/bin/python3 tools/gen_music.py --only sparse-ambient --length-s 20
```

Ran with `/opt/homebrew/bin/python3` (not the default framework `python3`): the framework
interpreter's `cert.pem` does not exist on this machine
(`/Library/Frameworks/Python.framework/Versions/3.14/etc/openssl/cert.pem` — no such file, the
usual "run Install Certificates.command" gap on a python.org installer), so `urllib.request`
fails every HTTPS call with `CERTIFICATE_VERIFY_FAILED`. Homebrew's python3 points
`ssl.get_default_verify_paths()` at `/opt/homebrew/etc/openssl@3/cert.pem`, which resolves to a
real certificate bundle, so it works unmodified. This is an environment fact, not a code
change — the tool itself is stdlib-only and unaware of which interpreter runs it.

The `.env` was never copied into the worktree; it was sourced from the main checkout's path
into the current shell's environment for this one command.

## Output

- `media/music/library/tracks/sparse-ambient.mp3` — 420.2 KB
- `media/music/library/catalog.json` entry:

```json
{
  "id": "sparse-ambient",
  "file": "tracks/sparse-ambient.mp3",
  "tones": ["Casual"],
  "duration_s": 20.036,
  "requested_ms": 20000,
  "loudness_lufs": -20.0,
  "peak_dbfs": -7.2,
  "source": "elevenlabs:music",
  "model": "music_v2",
  "prompt": "sparse ambient pad, very quiet, almost texture, no rhythm",
  "generated_at": "2026-09-13T04:47:40Z"
}
```

## Measurements vs contract

| Check | Target | Measured | Result |
|---|---|---|---|
| Duration | ≈ 20s (`--length-s 20`) | 20.036s | PASS (36ms over, within any reasonable tolerance) |
| Loudness | within 1 LU of −20.0 target | −20.0 LUFS | PASS (exact) |
| Peak | ≤ −1.5 dBFS ceiling | −7.2 dBFS | PASS (well under ceiling, no clamp triggered) |

## Repo cleanliness

`git status --short` after the run shows only the tracked source/doc edits
(`.gitignore`, `media/music/library/palette.json`, `reference/post-production/17-music-bed.md`,
`tests/py/test_gen_music.py`, `tools/gen_music.py`). Neither `media/music/library/tracks/sparse-ambient.mp3`
nor `media/music/library/catalog.json` appears — both are covered by `.gitignore`
(`media/music/library/tracks/` was already ignored; `media/music/library/catalog.json` was added
in this phase, mirroring the tracks-are-never-committed rule since the catalog carries no
information not derivable by regenerating).

## Verdict

`gen_music.py` works end-to-end against the real ElevenLabs Music API: request, write, measure,
normalise-in-place (no gain applied here since the raw peak already sat under the ceiling and
loudness landed exactly on target), and catalog write are all confirmed live.
