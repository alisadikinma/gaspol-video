"""Measure a clip's SFX / music timing: onsets, tempo, loudness, energy, and how onsets sit
against spoken words and picture cuts.

Pure Python (no numpy): ffmpeg decodes mono s16 and everything else is plain loops. An onset
here is any sharp rise in high-frequency energy, so it cannot tell an SFX hit from a speech
consonant. Pass word times to ``relate`` to see which onsets land on a word start.
"""
import math
import statistics
import subprocess
from array import array
from pathlib import Path

from . import ff, ingest, loudness, speech

FLOOR = 0.002          # normalised RMS of the first difference; below this nothing is an onset
HISTORY_S = 0.5
MIN_BPM, MAX_BPM = 60.0, 180.0
BIN_BPM = 2.0
MIN_TAIL_S = 0.5


def decode_mono(path, rate=16000):
    """Mono signed-16 samples at ``rate``. Raises ValueError when the file has no audio."""
    if not Path(path).exists():
        raise ValueError(f"no such file: {path}")
    if not ff.has_audio(path):
        raise ValueError(f"no audio stream: {path}")
    # ff.run decodes stdout as text, which would corrupt raw PCM.
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(rate),
                           "-f", "s16le", "-"], capture_output=True)
    if proc.returncode != 0:
        raise ff.FFError(proc.stderr.decode(errors="replace")[-600:])
    samples = array("h")
    samples.frombytes(proc.stdout[:len(proc.stdout) // 2 * 2])
    return samples


def _frame_energy(samples, hop):
    """RMS of the first difference per hop-sized frame, scaled to 0..1 (a high-pass)."""
    out = []
    for start in range(0, len(samples) - hop + 1, hop):
        total, prev = 0, samples[start - 1] if start else samples[0]
        for v in samples[start:start + hop]:
            d = v - prev
            total += d * d
            prev = v
        out.append((total / hop) ** 0.5 / 32768.0)
    return out


def onsets(samples, rate, hop_ms=10, min_gap_ms=80, k=3.0):
    """Onset times in seconds: frames whose energy beats ``k`` times the median of the previous
    0.5 s and is a local maximum; peaks closer than ``min_gap_ms`` collapse to the first."""
    hop = int(rate * hop_ms / 1000)
    if hop < 1 or len(samples) < hop:
        return []
    energy = _frame_energy(samples, hop)
    back = max(1, int(HISTORY_S * 1000 / hop_ms))
    peaks = []
    for i in range(1, len(energy)):
        e = energy[i]
        if e <= FLOOR or e <= k * statistics.median(energy[max(0, i - back):i]):
            continue
        if e < energy[i - 1] or (i + 1 < len(energy) and e <= energy[i + 1]):
            continue
        t = i * hop / rate
        if not peaks or t - peaks[-1] >= min_gap_ms / 1000:
            peaks.append(t)
    return [round(t, 3) for t in peaks]


def tempo(onset_times):
    """BPM from the inter-onset intervals folded into 60-180; None below four onsets."""
    if len(onset_times) < 4:
        return None
    folded = []
    for a, b in zip(onset_times, onset_times[1:]):
        if b - a <= 0:
            continue
        bpm = 60.0 / (b - a)
        while bpm < MIN_BPM:
            bpm *= 2
        while bpm >= MAX_BPM:
            bpm /= 2
        folded.append(bpm)
    if not folded:
        return None
    bins = {}
    for bpm in folded:
        bins.setdefault(int(bpm // BIN_BPM), []).append(bpm)
    best = max(bins.values(), key=len)
    return round(sum(best) / len(best), 1)


def energy_profile(path, seg_s=2.0):
    """``[{start, end, dbfs}]`` per ``seg_s`` segment; a last segment under 0.5 s is dropped."""
    total = ff.duration(path)
    out, t = [], 0.0
    while t < total:
        end = min(t + seg_s, total)
        if end - t >= MIN_TAIL_S:
            levels = [db for _, db in speech.energy_db(path, t, end, hop=0.1)]
            power = sum(10 ** (db / 10) for db in levels) / len(levels) if levels else 0.0
            out.append({"start": round(t, 3), "end": round(end, 3),
                        "dbfs": round(10 * math.log10(power), 1) if power > 0 else -120.0})
        t += seg_s
    return out


def _nearest(t, times):
    if not times:
        return None, None
    n = min(times, key=lambda x: abs(x - t))
    return n, round(n - t, 3)


def relate(onset_times, word_times, cut_times, tol_s=0.06):
    """Where each onset sits against word starts and cuts. ``d_*`` is nearest minus onset."""
    rows = []
    for t in onset_times:
        word, d_word = _nearest(t, word_times)
        cut, d_cut = _nearest(t, cut_times)
        on_word = d_word is not None and abs(d_word) <= tol_s
        on_cut = d_cut is not None and abs(d_cut) <= tol_s
        label = "both" if on_word and on_cut else "on-word" if on_word else "on-cut" if on_cut else "free"
        rows.append({"t": t, "nearest_word_start": word, "d_word": d_word,
                     "nearest_cut": cut, "d_cut": d_cut, "label": label})
    return rows


def study(clip, words=None):
    """Everything measured about one clip. ``words`` = ``[[word, start_s, end_s], ...]``."""
    samples = decode_mono(clip)
    hits = onsets(samples, 16000)
    cuts = [round(c, 3) for c in ingest.detect_cuts(str(clip))]
    starts = [float(w[1]) for w in words or []]
    return {"clip": str(clip), "duration": round(ff.duration(clip), 3),
            "loudness_lufs": float(loudness.measure(clip)["input_i"]),
            "cuts": cuts, "onsets": hits, "tempo_bpm": tempo(hits),
            "energy": energy_profile(clip), "relations": relate(hits, starts, cuts)}
