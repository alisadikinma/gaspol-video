"""Shorten the air between words without touching the words.

A guide-voice take is often right in pitch and too slow in its pauses. Cutting every gap longer
than `max_gap` down to `keep` seconds, at word boundaries from an ASR word list, fixes the pace
for free, before a paid speech-to-speech pass (which keeps durations). A silence detector cuts
breaths and whispers unevenly; word timings do not.
"""
from . import ff


def plan_cuts(words, max_gap=0.3, keep=0.2):
    """[(word, start, end)] -> [(cut_start, cut_end)] to remove; half of `keep` stays each side."""
    if keep > max_gap:
        raise ValueError("keep must not exceed max_gap")
    cuts = []
    for (_, _, end), (_, start, _) in zip(words, words[1:]):
        if start - end > max_gap:
            cuts.append((round(end + keep / 2, 3), round(start - keep / 2, 3)))
    return cuts


def apply(audio, words, out, max_gap=0.3, keep=0.2):
    """Write `out` with the planned cuts removed. Returns {"cuts", "removed_s", "duration"}."""
    cuts = plan_cuts(words, max_gap, keep)
    dur = ff.probe(audio)["duration"]
    keeps, t = [], 0.0
    for a, b in cuts:
        keeps.append((t, a))
        t = b
    keeps.append((t, dur))
    parts = "".join(f"[0:a]atrim={a}:{b},asetpts=N/SR/TB[p{i}];" for i, (a, b) in enumerate(keeps))
    graph = parts + "".join(f"[p{i}]" for i in range(len(keeps))) + f"concat=n={len(keeps)}:v=0:a=1[o]"
    ff.ffmpeg("-i", audio, "-filter_complex", graph, "-map", "[o]", out)
    return {"cuts": len(cuts), "removed_s": round(sum(b - a for a, b in cuts), 3),
            "duration": round(ff.probe(out)["duration"], 3)}
