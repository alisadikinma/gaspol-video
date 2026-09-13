#!/usr/bin/env python3
"""Clean platform-native dialogue before it goes through the Voice Changer.

    python3 tools/clean_voice.py IN.mp4 -o OUT.mp4 [--method isolate|rnnoise]
                                  [--model sh|cb] [--no-preserve-level]

The Voice Changer (`voice_changer.mjs`) expects a clean, single-speaker dialogue take. A
platform-native clip recorded outdoors carries wind, traffic or crowd noise underneath the
speech, and that noise survives conversion (11-voice-cast-and-vo.md §5 "the conversion eats
the scene, not just the voice"). This tool removes it BEFORE the clip reaches the changer.

Two methods:
  --method isolate  ElevenLabs Voice Isolator (default). Removes dynamic broadband noise
                     (wind, water, traffic) near-completely. Costs API credits.
  --method rnnoise  Local ffmpeg `arnndn` (RNNoise). Free and offline, but only partially
                     removes non-stationary noise. Models live in tools/models/rnnoise/.

Gain is matched back to the source's RMS so cleaning does not also change the perceived
loudness, and the video stream is always COPIED — never re-encoded — so cleaning cannot
itself introduce the kind of drift the Voice Changer's 0.05s rule exists to catch. If the
output duration differs from the source by more than 0.05s, the output is deleted and this
tool refuses: stretching audio to force a match would create exactly the artefact that rule
protects against. The source file is never modified.

Stdlib only; `--method isolate` calls the ElevenLabs API over urllib, no requests dependency.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
ISO_URL = "https://api.elevenlabs.io/v1/audio-isolation"
ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "tools" / "models" / "rnnoise"
KNOWN_MODELS = ("sh", "cb")


class CleanError(Exception):
    """The clip cannot be cleaned as asked."""


def model_path(model):
    """Resolve an RNNoise model name to its .rnnn file. Raises for an unknown model."""
    if model not in KNOWN_MODELS:
        raise CleanError(f"unknown rnnoise model {model!r} (models: {', '.join(KNOWN_MODELS)})")
    path = MODELS_DIR / f"{model}.rnnn"
    if not path.exists():
        raise CleanError(f"rnnoise model not found: {path}")
    return path


def level_gain(src_rms, clean_rms, clean_peak, ceiling=-1.0):
    """Flat gain (dB) that restores the source's loudness without clipping the cleaned peak."""
    gain = src_rms - clean_rms
    if clean_peak + gain > ceiling:
        gain = ceiling - clean_peak
    return gain


def multipart_body(field, filename, data, boundary):
    """Build a single-file multipart/form-data body without a third-party HTTP client."""
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + data + tail


def _run(cmd, cwd=None):
    if FFMPEG is None:
        raise CleanError("ffmpeg not found on PATH")
    proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=cwd)
    if proc.returncode != 0:
        raise CleanError(f"ffmpeg failed:\n{proc.stderr.strip()[-800:]}")
    return proc.stdout


def duration_of(path):
    if FFPROBE is None:
        raise CleanError("ffprobe not found on PATH")
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out or out == "N/A":
        return None
    try:
        return float(out)
    except ValueError:
        return None


def has_audio_stream(path):
    if FFPROBE is None:
        raise CleanError("ffprobe not found on PATH")
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return bool(proc.stdout.strip())


def _astat(path, label):
    proc = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(path), "-af", "astats=metadata=1",
         "-f", "null", os.devnull],
        capture_output=True, text=True,
    )
    combined = proc.stdout + proc.stderr
    m = re.search(rf"{label}:\s*(-?[\d.]+)", combined)
    return float(m.group(1)) if m else None


def load_env():
    """`.env` loading idiom shared with gen_sfx.py / gen_subs.py: real env wins."""
    env = dict(os.environ)
    try:
        for line in Path(".env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if v.strip():
                    env.setdefault(k.strip(), v.strip())
    except OSError:
        pass
    return env


def isolate(audio_path, out_path, api_key):
    """POST the audio to ElevenLabs Voice Isolator; write the isolated result."""
    boundary = "----gaspolvideocleanvoice"
    data = Path(audio_path).read_bytes()
    body = multipart_body("audio", Path(audio_path).name, data, boundary)
    req = urllib.request.Request(
        ISO_URL, data=body,
        headers={"xi-api-key": api_key,
                 "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=1200) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:400].decode("utf-8", "ignore")
        raise CleanError(f"ElevenLabs audio-isolation HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        raise CleanError(f"ElevenLabs audio-isolation request failed: {exc.reason}")
    if len(raw) < 1000:
        raise CleanError(f"ElevenLabs audio-isolation returned {len(raw)} bytes — treat as failed")
    Path(out_path).write_bytes(raw)
    return out_path


def rnnoise(audio_path, out_path, model):
    """Local high-pass + RNNoise denoise. Colon-free relative model path, run from ROOT —
    arnndn's model path sits inside the filtergraph, where a Windows-absolute path's `:`
    and `\\` would otherwise mangle the filter string."""
    mpath = model_path(model)
    mrel = mpath.relative_to(ROOT).as_posix()
    _run([FFMPEG, "-y", "-v", "error", "-i", audio_path,
          "-af", f"highpass=f=90,arnndn=m={mrel}", "-ar", "44100", out_path], cwd=ROOT)
    return out_path


def clean(in_path, out_path, method="isolate", model="sh", preserve_level=True,
          env=None, log=print):
    if method not in ("isolate", "rnnoise"):
        raise CleanError(f"unknown method {method!r} (use isolate or rnnoise)")

    in_path = Path(in_path)
    out_path = Path(out_path)
    if in_path.resolve() == out_path.resolve():
        raise CleanError("refusing to overwrite the source")
    if not has_audio_stream(in_path):
        raise CleanError(f"{in_path.name} has no audio stream")

    env = env if env is not None else load_env()
    is_wav = in_path.suffix.lower() == ".wav"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        audio_in = tmp / "audio_in.wav"
        _run([FFMPEG, "-y", "-v", "error", "-i", str(in_path), "-vn", "-ac", "1", "-ar", "44100",
              "-c:a", "pcm_s16le", str(audio_in)])

        if method == "isolate":
            api_key = env.get("ELEVENLABS_API_KEY")
            if not api_key:
                raise CleanError(
                    "ELEVENLABS_API_KEY not set — cannot clean with --method isolate. "
                    "Set it in .env, or use --method rnnoise instead."
                )
            cleaned = tmp / "cleaned.mp3"
            isolate(audio_in, cleaned, api_key)
        else:
            cleaned = tmp / "cleaned.wav"
            rnnoise(audio_in, cleaned, model)

        gain = 0.0
        src_rms = clean_rms = clean_peak = None
        if preserve_level:
            src_rms = _astat(in_path, "RMS level dB")
            clean_rms = _astat(cleaned, "RMS level dB")
            clean_peak = _astat(cleaned, "Peak level dB")
            if None not in (src_rms, clean_rms, clean_peak):
                gain = level_gain(src_rms, clean_rms, clean_peak)
            log(f"clean_voice: method={method} src RMS {src_rms} dB, cleaned RMS {clean_rms} dB "
                f"/ peak {clean_peak} dB -> gain {gain:+.2f} dB")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if is_wav:
            _run([FFMPEG, "-y", "-v", "error", "-i", str(cleaned),
                  "-af", f"volume={gain:.2f}dB", str(out_path)])
        else:
            _run([FFMPEG, "-y", "-v", "error", "-i", str(in_path), "-i", str(cleaned),
                  "-filter_complex", f"[1:a]volume={gain:.2f}dB,apad[a]",
                  "-map", "0:v:0", "-map", "[a]", "-shortest",
                  "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_path)])

    src_dur = duration_of(in_path)
    out_dur = duration_of(out_path)
    if src_dur is None or out_dur is None:
        out_path.unlink(missing_ok=True)
        raise CleanError("cannot measure duration; refusing because lip-sync cannot be checked")
    if abs(out_dur - src_dur) > 0.05:
        drift = out_dur - src_dur
        out_path.unlink(missing_ok=True)
        raise CleanError(f"duration changed by {drift:+.3f}s; lip-sync would drift")

    log(f"clean_voice: wrote {out_path}" + (f" ({out_dur:.2f}s)" if out_dur else ""))
    return str(out_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--method", choices=("isolate", "rnnoise"), default="isolate")
    ap.add_argument("--model", choices=KNOWN_MODELS, default="sh")
    ap.add_argument("--no-preserve-level", action="store_true")
    args = ap.parse_args(argv)
    try:
        clean(args.input, args.out, method=args.method, model=args.model,
              preserve_level=not args.no_preserve_level)
        return 0
    except CleanError as exc:
        print(f"clean_voice: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
