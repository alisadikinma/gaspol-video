"""Beat detection and cue snapping, stdlib + ffmpeg.

``detect`` finds energy onsets (drum hits, plucks, clicks) in a music file. ``snap`` moves cue
times onto the nearest beat when one is close enough, so an SFX hit lands on the groove.
"""
import array
import subprocess
import sys
from pathlib import Path

RATE = 16000
# An onset must also clear this absolute RMS jump (full scale = 1.0), or a noise floor would
# produce "beats" because the median it is compared with is tiny.
MIN_ONSET = 0.01


class BeatError(RuntimeError):
    """ffmpeg is missing, or the file cannot be decoded."""


def _decode(path):
    if not Path(path).is_file():
        raise BeatError(f"no such file: {path}")
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(RATE),
           "-f", "s16le", "-acodec", "pcm_s16le", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True)
    except FileNotFoundError as exc:
        raise BeatError("ffmpeg is not installed or not on PATH") from exc
    if proc.returncode != 0:
        raise BeatError(f"ffmpeg could not decode {path}: {proc.stderr.decode(errors='replace').strip()[-300:]}")
    pcm = array.array("h")
    raw = proc.stdout[: len(proc.stdout) // 2 * 2]
    pcm.frombytes(raw)
    if sys.byteorder == "big":
        pcm.byteswap()
    return pcm


def _energy(pcm, hop):
    out = []
    for i in range(0, len(pcm) - hop + 1, hop):
        chunk = pcm[i:i + hop]
        out.append((sum(v * v for v in chunk) / hop) ** 0.5 / 32768.0)
    return out


def detect(path, hop_s=0.01, min_gap_s=0.25, threshold=1.5):
    """Beat times in seconds, ascending. ``[]`` for silence."""
    pcm = _decode(path)
    hop = max(1, int(RATE * hop_s))
    env = _energy(pcm, hop)
    onset = [0.0] + [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    positive = sorted(v for v in onset if v > 0)
    if not positive:
        return []
    median = positive[len(positive) // 2]
    floor = max(threshold * median, MIN_ONSET)
    peaks = []
    for i in range(1, len(onset) - 1):
        v = onset[i]
        if v >= floor and v > onset[i - 1] and v >= onset[i + 1]:
            peaks.append((i * hop / RATE, v))
    kept = []
    for t, v in peaks:
        if kept and t - kept[-1][0] < min_gap_s:
            if v > kept[-1][1]:
                kept[-1] = (t, v)
        else:
            kept.append((t, v))
    return [round(t, 3) for t, _ in kept]


def snap(times, beats, window_s=0.12):
    """Each time moves to the nearest beat within ``window_s``, else stays."""
    out = []
    for t in times:
        near = min(beats, key=lambda b: abs(b - t)) if beats else None
        out.append(near if near is not None and abs(near - t) <= window_s else t)
    return out
