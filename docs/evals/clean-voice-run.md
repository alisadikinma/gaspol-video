# `clean_voice.py` real run — Moni promo project

Phase L step 6 (real run) on real clips from the user's Moni project. Source clips are
read-only and were never modified (verified below); all cleaning ran on a scratch copy.

## Clip selection

Probed all 5 candidate clips (ffprobe streams/duration, ffmpeg `astats` overall RMS/peak,
`silencedetect` at `-30dB:d=0.3`, and a custom noise-floor scan: 0.5s windows stepped by
0.25s across the whole clip, RMS per window via `astats`, minimum = noise floor, maximum =
speech-level estimate):

| Clip | Overall RMS | Overall Peak | Noise floor (quietest 0.5s) | Speech est. (loudest 0.5s) | Headroom |
|---|---|---|---|---|---|
| `S11b-cara-kerja-v1.mp4` | -31.96 dB | -9.67 dB | -53.72 dB | -30.13 dB | 23.59 dB |
| `S12-penyerahan-v1.mp4` | -22.59 dB | -1.29 dB | -46.75 dB | -14.89 dB | 31.86 dB |
| `S16-cta-v1.mp4` | -15.43 dB | -1.47 dB | **-36.14 dB** | -13.06 dB | **23.09 dB** |
| `hook-S01-S02-v1.mp4` | -18.18 dB | -1.18 dB | -73.09 dB | -13.17 dB | 59.92 dB |
| `hook-S01-S02-v2.mp4` | -18.62 dB | -0.45 dB | -75.15 dB | -11.53 dB | 63.62 dB |

**Chosen: `S16-cta-v1.mp4`.** It has both the highest absolute noise floor (-36.14 dB, next
closest is -46.75 dB) and the smallest headroom between its noise floor and its speech level
(23.09 dB, worst signal-to-noise ratio of the five). It is also the only clip of the five with
**zero** `silencedetect` hits at a `-30dB` threshold — every other clip has clear silent gaps
that dip below -30 dB; S16's floor never does, meaning its background noise sits audibly closer
to the dialogue throughout the clip, not just in isolated pauses.

## Commands run

Copy verified byte-identical to source before cleaning (`md5` matched):

```
SCRATCH=<scratch>/gv2-clean
cp $YE/media/projects/moni-promo/clips/S16-cta-v1.mp4 "$SCRATCH/S16-cta-v1.mp4"
```

RNNoise:

```
python3 tools/clean_voice.py "$SCRATCH/S16-cta-v1.mp4" -o "$SCRATCH/out-rnnoise.mp4" --method rnnoise --model sh
```

Isolate (ElevenLabs Voice Isolator; key exported from `.env` in the same shell command, never
printed or committed):

```
set -a; . /Users/alisadikin/Drive-D/claude-plugin/gaspol-video/.env; set +a; \
python3 tools/clean_voice.py "$SCRATCH/S16-cta-v1.mp4" -o "$SCRATCH/out-isolate.mp4" --method isolate
```

The first `isolate` attempt failed with a real error, recorded verbatim (no secret in it):

```
clean_voice: ElevenLabs audio-isolation request failed: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1082)
```

Root cause: the python.org 3.14 interpreter on this machine ships without a CA bundle wired up
(`certifi` was not installed and no `SSL_CERT_FILE` was set) — a known python.org macOS
installer gap, not a bug in `clean_voice.py`. Fixed by running the interpreter's own
`/Applications/Python 3.14/Install Certificates.command` (installs `certifi`, symlinks the
bundle), then re-running the same command above, which then succeeded. This is a one-time
machine-level fix, unrelated to this repo's code.

## Results

| Metric | Source | `out-rnnoise.mp4` | `out-isolate.mp4` |
|---|---|---|---|
| RMS | -15.43 dB | -22.52 dB | -21.40 dB |
| Peak | -1.47 dB | -1.01 dB | -1.01 dB |
| Noise floor before (quietest 0.5s window, source) | -36.14 dB | -36.14 dB | -36.14 dB |
| Noise floor after (quietest 0.5s window, output) | — | -58.67 dB | -73.03 dB |
| Noise floor improvement | — | 22.53 dB | 36.89 dB |
| Duration | 8.000000s | 8.000000s | 8.000000s |
| Duration delta vs source | — | 0.000s | 0.000s |
| Video codec | h264 | h264 (unchanged) | h264 (unchanged) |
| Tool-reported gain applied | — | +5.45 dB | +17.48 dB |

Tool's own console output:

```
clean_voice: method=rnnoise src RMS -15.807487 dB, cleaned RMS -27.973795 dB / peak -6.452926 dB -> gain +5.45 dB
clean_voice: wrote <scratch>/gv2-clean/out-rnnoise.mp4 (8.00s)

clean_voice: method=isolate src RMS -15.807487 dB, cleaned RMS -38.876078 dB / peak -18.484478 dB -> gain +17.48 dB
clean_voice: wrote <scratch>/gv2-clean/out-isolate.mp4 (8.00s)
```

(The tool's own `src RMS -15.807487 dB` is the mono-extracted PCM RMS used internally for level
matching; the `-15.43 dB` row above is the stereo `astats` reading of the original file — same
signal, expected small difference from the mono downmix.)

## Duration gate

**Held for both runs.** `clean_voice.py`'s internal gate (`abs(duration(out) - duration(in)) >
0.05` deletes the output and raises) did not trigger for either method — both outputs measured
`8.000000s`, an exact match to the source, `0.000s` drift. Confirmed independently above via
`ffprobe` on both output files (not just trusting the tool's own printed "8.00s").

## Source integrity

`S16-cta-v1.mp4` at the original `claude-youtube-editor` path was never opened for writing.
`md5` of the source and the scratch copy matched before cleaning; only the scratch copy and its
derived outputs were touched.

## Listening check

listening check: pending — Ali to listen to out-rnnoise.mp4 and out-isolate.mp4 at
`/private/tmp/claude-501/-Users-alisadikin-Drive-D-claude-plugin-gaspol-video/a2fdaf4a-0852-4766-bd11-f133860002b5/scratchpad/gv2-clean/`
