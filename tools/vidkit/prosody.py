"""How a voice is delivered: pace per sentence, pauses, and the words that carry the stress.

Used to copy the delivery of a reference voice (skills/video-repackage) without copying the voice:
the report becomes per-line direction for a new TTS take. Pure Python (wave + math), so it runs
without numpy. Pitch is a normalised autocorrelation on a short window at the middle of each word,
which is enough to rank words against each other; it is not a pitch tracker.
"""
import json
import math
import statistics
import struct
import wave
from pathlib import Path

SENTENCE_END = (".", "?", "!")


def load_words(path):
    """Words json -> [(word, start_s, end_s)].

    Accepts gen_subs.py output (``{"words": [{"text", "start_ms", "end_ms"}]}``), a raw AssemblyAI
    transcript (``{"words": [{"text", "start", "end"}]}``, also milliseconds), triplets
    ``[[word, start, end], ...]`` and ``[{"word", "start", "end"}]`` in seconds.
    """
    doc = json.loads(Path(path).read_text())
    if isinstance(doc, dict) and "words" in doc:
        out = []
        for w in doc["words"]:
            if "start_ms" in w and "end_ms" in w:
                out.append((w["text"], w["start_ms"] / 1000, w["end_ms"] / 1000))
            elif "start" in w and "end" in w:
                out.append((w["text"], w["start"] / 1000, w["end"] / 1000))
            else:
                raise ValueError(f"{path}: word without start/end times: {w!r}")
        return out
    if isinstance(doc, list) and all(isinstance(w, list) and len(w) == 3 for w in doc):
        return [(w[0], float(w[1]), float(w[2])) for w in doc]
    if isinstance(doc, list) and all(isinstance(w, dict) and "word" in w for w in doc):
        return [(w["word"], float(w["start"]), float(w["end"])) for w in doc]
    raise ValueError(f"{path}: unknown words format")


def sentences(words):
    """Group words into sentences on . ? ! — each with pace (words/s) and the pause after it."""
    out, buf = [], []
    for w in words:
        buf.append(w)
        if w[0].rstrip("\"')").endswith(SENTENCE_END):
            out.append(buf)
            buf = []
    if buf:
        out.append(buf)
    rows = []
    for i, ws in enumerate(out):
        start, end = ws[0][1], ws[-1][2]
        nxt = out[i + 1][0][1] if i + 1 < len(out) else None
        rows.append({
            "text": " ".join(w[0] for w in ws),
            "start": round(start, 3), "end": round(end, 3), "words": len(ws),
            "wps": round(len(ws) / (end - start), 2) if end > start else None,
            "pause_after": round(nxt - end, 3) if nxt is not None else None,
        })
    return rows


def read_wav(path):
    """Mono 16-bit PCM wav -> (samples in -1..1, sample rate). Extract with ffmpeg -ac 1 first."""
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError(f"{path}: need mono 16-bit PCM (ffmpeg -ac 1 -c:a pcm_s16le)")
        raw = w.readframes(w.getnframes())
        sr = w.getframerate()
    n = len(raw) // 2
    return [v / 32768 for v in struct.unpack(f"<{n}h", raw[: n * 2])], sr


def _slice(samples, sr, t0, t1):
    return samples[max(0, int(t0 * sr)): max(0, int(t1 * sr))]


def rms_db(samples, sr, t0, t1):
    seg = _slice(samples, sr, t0, t1)
    if not seg:
        return None
    return round(20 * math.log10(math.sqrt(sum(v * v for v in seg) / len(seg)) + 1e-9), 2)


def pitch_hz(samples, sr, t0, t1, fmin=70, fmax=400, window_s=0.04, voiced_min=0.5):
    """Pitch at the middle of [t0, t1], or None when unvoiced (silence, noise, a consonant).

    Takes the first lag whose normalised autocorrelation reaches 90% of the best one, so a
    clean tone is not reported an octave low.
    """
    lo, hi = int(sr / fmax), int(sr / fmin)
    win = int(window_s * sr)
    mid = int((t0 + t1) / 2 * sr)
    a = max(0, mid - (win + hi) // 2)
    seg = samples[a: a + win + hi]
    if len(seg) < win + hi:
        return None
    x = seg[:win]
    ex = sum(v * v for v in x)
    if ex < 1e-6:
        return None
    scores = []
    for lag in range(lo, hi + 1):
        y = seg[lag: lag + win]
        ey = sum(v * v for v in y)
        scores.append(sum(p * q for p, q in zip(x, y)) / math.sqrt(ex * ey) if ey > 0 else 0.0)
    best = max(scores)
    if best < voiced_min:
        return None
    i = next(i for i, s in enumerate(scores) if s >= 0.9 * best)
    while i + 1 < len(scores) and scores[i + 1] > scores[i]:  # climb to that peak's top
        i += 1
    shift = 0.0
    if 0 < i < len(scores) - 1:  # parabolic interpolation between integer lags
        l, c, r = scores[i - 1], scores[i], scores[i + 1]
        den = l - 2 * c + r
        shift = 0.5 * (l - r) / den if den else 0.0
    return round(sr / (lo + i + shift), 1)


def _z(values):
    known = [v for v in values if v is not None]
    if len(known) < 2:
        return [0.0] * len(values)
    mu, sd = statistics.fmean(known), statistics.pstdev(known)
    return [((v - mu) / sd if sd > 0 and v is not None else 0.0) for v in values]


def _pct(values, q):
    s = sorted(values)
    return s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))]


def gate(rep, min_range_st=None, min_wps=None, max_pause_s=None):
    """Problems of one take against delivery targets; [] = passes.

    Run it before speech-to-speech: a voice changer keeps the input's pitch and pace, so a flat
    take stays flat after conversion. A value that could not be measured fails its threshold,
    except the pause, which is legitimately absent in a one-sentence take.
    """
    o, problems = rep["overall"], []
    if min_range_st is not None and (o["pitch_range_st"] is None or o["pitch_range_st"] < min_range_st):
        problems.append(f"pitch range {o['pitch_range_st']} st < {min_range_st} st (too flat)")
    if min_wps is not None and (o["wps"] is None or o["wps"] < min_wps):
        problems.append(f"pace {o['wps']} w/s < {min_wps} w/s (too slow)")
    if max_pause_s is not None and o["pause_mean_s"] is not None and o["pause_mean_s"] > max_pause_s:
        problems.append(f"mean pause {o['pause_mean_s']} s > {max_pause_s} s (too much air)")
    return problems


def report(wav, words, stress_z=1.0):
    """Delivery report of one voice: overall pace and pitch range, per-sentence pace and pauses,
    and the stressed words (loudness + pitch, each as a z-score within this voice, averaged)."""
    samples, sr = read_wav(wav)
    per = []
    for w, s, e in words:
        per.append({"word": w, "start": round(s, 3), "end": round(e, 3),
                    "db": rms_db(samples, sr, s, e), "hz": pitch_hz(samples, sr, s, e)})
    st = [12 * math.log2(p["hz"]) if p["hz"] else None for p in per]
    zl, zp = _z([p["db"] for p in per]), _z(st)
    for p, a, b in zip(per, zl, zp):
        p["stress"] = round((a + b) / 2, 2)
    voiced = [p["hz"] for p in per if p["hz"]]
    sents = sentences(words)
    pauses = [x["pause_after"] for x in sents if x["pause_after"] is not None]
    span = words[-1][2] - words[0][1] if words else 0
    overall = {
        "words": len(words),
        "wps": round(len(words) / span, 2) if span > 0 else None,
        "pause_mean_s": round(statistics.fmean(pauses), 3) if pauses else None,
        "pitch_median_hz": round(statistics.median(voiced), 1) if voiced else None,
        "pitch_range_st": round(12 * math.log2(_pct(voiced, 0.9) / _pct(voiced, 0.1)), 1) if voiced else None,
    }
    return {"overall": overall, "sentences": sents,
            "emphasis": [p for p in per if p["stress"] >= stress_z], "words": per}
