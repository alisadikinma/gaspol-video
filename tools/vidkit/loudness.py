"""Final loudness: two-pass loudnorm, with audio trimmed to the picture length.

One pass misses the target by up to 1 LUFS on wide-dynamics material; pass one measures, pass two
applies the measured values. Order matters: loudnorm shifts output timestamps by ~0.08 s, so
``asetpts`` resets them FIRST (trimming before that cut 0.08 s of real audio). Then ``apad``
(loudnorm also eats tail) and ``atrim`` to the picture length; the A/V gate rejects a gap over 0.04 s.
The picture is stream-copied: by this point it is final.
"""
import json
import re

from .ff import ensure_parent, ffmpeg, probe

LUFS, TRUE_PEAK, LRA = -14.0, -1.0, 11.0


def measure(path, lufs=LUFS, tp=TRUE_PEAK, lra=LRA):
    err = ffmpeg("-i", path, "-af", f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json",
                 "-f", "null", "-", capture_stderr=True)
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", err, re.S)
    if not m:
        raise RuntimeError("loudnorm printed no measurement")
    return json.loads(m.group(0))


def normalize(src, out, lufs=LUFS, tp=TRUE_PEAK, lra=LRA):
    """Returns ``{"before": {...}, "after": {"I","TP","LRA"}}``."""
    video = probe(src)["video"]
    if video is None:
        raise ValueError("normalize expects a file with a picture")
    vdur = video["duration"] or probe(src)["duration"]
    m = measure(src, lufs, tp, lra)
    second = (f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
              f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
              f":offset={m['target_offset']}:linear=true:print_format=summary")
    ensure_parent(out)
    err = ffmpeg("-i", src, "-af", f"{second},asetpts=N/SR/TB,apad,atrim=0:{vdur:.6f}",
                 "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                 "-ar", "48000", "-ac", "2", "-movflags", "+faststart", out, capture_stderr=True)
    after = {}
    for key, pat in (("I", r"Output Integrated:\s*(-?[\d.]+)"), ("TP", r"Output True Peak:\s*(-?[\d.]+)"),
                     ("LRA", r"Output LRA:\s*(-?[\d.]+)")):
        hit = re.search(pat, err)
        if hit:
            after[key] = float(hit.group(1))
    return {"before": m, "after": after}
