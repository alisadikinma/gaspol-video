"""Hard checks to run before an assembly step. Each raises GateError instead of exiting, so a
caller can catch it; the CLI turns it into exit 1.

Why they exist (all learned the hard way on shipped films):

* ``gate_av``: video and audio of one file must be the same length. amix and the AAC encoder each
  add ~0.08 s of tail, so a long chain drifts out of sync unless every step is checked.
* ``gate_uniform``: ``ffmpeg -f concat`` builds the encoder ONCE from the FIRST file and forces
  every later file through it. A mono file followed by a stereo one, or 44.1 kHz mixed with
  48 kHz, comes out garbled or stretched 8.8 %. Check sample rate AND channel count.
"""
from pathlib import Path

from .ff import probe

AV_TOLERANCE_S = 0.04


class GateError(Exception):
    pass


def gate_av(path, tolerance=AV_TOLERANCE_S):
    """Video and audio stream durations must match within ``tolerance`` seconds.
    Returns (video_s, audio_s)."""
    info = probe(path)
    if info["video"] is None or info["audio"] is None:
        raise GateError(f"{path}: needs both a video and an audio stream")
    v = info["video"]["duration"] or info["duration"]
    a = info["audio"]["duration"] or info["duration"]
    if abs(v - a) > tolerance:
        raise GateError(f"{path}: video {v:.3f}s vs audio {a:.3f}s, off by {abs(v - a):.3f}s > {tolerance}s")
    return v, a


def gate_uniform(paths):
    """Every file to be concatenated must share one (sample rate, channels) shape."""
    shapes = {}
    for p in paths:
        a = probe(p)["audio"]
        if a is None:
            raise GateError(f"{p}: no audio stream")
        shapes.setdefault((a["sample_rate"], a["channels"]), []).append(Path(p).name)
    if len(shapes) > 1:
        lines = "\n".join(f"  {sr} Hz, {ch} ch: {', '.join(n)}" for (sr, ch), n in shapes.items())
        raise GateError("files are not uniform; concat would corrupt the later ones:\n" + lines)
    return next(iter(shapes))
