"""Word timing and speech-gap logic.

Inputs are either an ElevenLabs alignment dict (``characters`` + ``character_start_times_seconds``
+ ``character_end_times_seconds``) or a list of ``{"word", "start", "end"}`` seconds. Everything
here is pure Python so it can be unit-tested without media.
"""
import math
import struct
import subprocess


def words_from_alignment(alignment):
    """Collapse an ElevenLabs character alignment into ``[{"word","start","end"}]``."""
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    words, buf, t0, t1 = [], "", None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if buf:
                words.append({"word": buf, "start": t0, "end": t1})
                buf, t0 = "", None
        else:
            if t0 is None:
                t0 = s
            buf += ch
            t1 = e
    if buf:
        words.append({"word": buf, "start": t0, "end": t1})
    return words


def speech_spans(layers, pad=0.25):
    """Merged speech intervals on the film timeline.

    ``layers`` = ``[{"at": film_seconds, "words": [...]}, ...]``. Each layer's span runs from its
    first to its last word, widened by ``pad`` each side, then overlapping spans are merged.
    """
    spans = []
    for layer in layers:
        w = layer.get("words") or []
        if w:
            spans.append((max(0.0, layer["at"] + w[0]["start"] - pad), layer["at"] + w[-1]["end"] + pad))
    spans.sort()
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def gaps(spans, total, min_len=0.0):
    """Silent intervals between ``spans`` over ``[0, total]`` that are at least ``min_len`` long."""
    out, t = [], 0.0
    for a, b in spans:
        if a - t > 0:
            out.append((t, a))
        t = max(t, b)
    if t < total:
        out.append((t, total))
    return [(a, b) for a, b in out if b - a >= min_len]


def snap_to_gaps(cues, spans, total, window=2.0, min_gap=0.5, margin=0.1, keep=()):
    """Move transient cues out from under speech.

    A sidechain-ducked mix suppresses anything under narration, so raising its gain does not
    help: the cue measures +0 dB however loud it is made. Move it instead, to the nearest gap of
    at least ``min_gap`` within ``window`` seconds. Cues with no gap in reach stay put.
    ``cues`` = ``[{"id","at_s",...}]``; ids in ``keep`` (ambience beds) never move.
    Returns ``(new_cues, report)``; the input is not mutated.
    """
    holes = gaps(spans, total, min_gap)
    moved, report = [], []
    for cue in cues:
        cue = dict(cue)
        at = cue["at_s"]
        if cue.get("id") in keep or any(a <= at <= b - 0.2 for a, b in holes):
            moved.append(cue)
            continue
        near = [a + margin for a, b in holes if abs(a - at) <= window]
        if near:
            new = min(near, key=lambda x: abs(x - at))
            cue["at_s_orig"], cue["at_s"] = at, round(new, 2)
            report.append((cue.get("id"), at, new))
        moved.append(cue)
    return moved, report


def energy_db(path, start, end, hop=0.01, rate=16000):
    """RMS level in dBFS every ``hop`` seconds for ``[start, end]`` of a file's audio, as
    ``[(time_s, dB)]``. Pure Python (no numpy): ffmpeg decodes mono f32."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-to", str(end), "-i", str(path),
                           "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"], capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode()[-600:])
    n = len(proc.stdout) // 4
    samples = struct.unpack(f"<{n}f", proc.stdout[:n * 4])
    step = max(1, int(rate * hop))
    out = []
    for i in range(0, n - step + 1, step):
        rms = (sum(v * v for v in samples[i:i + step]) / step) ** 0.5
        out.append((round(start + i / rate, 3), round(20 * math.log10(rms + 1e-6), 1)))
    return out
