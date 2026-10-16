"""Final loudness: two-pass loudnorm, with audio trimmed to the picture length.

One pass misses the target by up to 1 LUFS on wide-dynamics material; pass one measures, pass two
applies the measured values. Order matters: loudnorm shifts output timestamps by ~0.08 s, so
``asetpts`` resets them FIRST (trimming before that cut 0.08 s of real audio). Then ``apad``
(loudnorm also eats tail) and ``atrim`` to the picture length; the A/V gate rejects a gap over 0.04 s.
The picture is stream-copied: by this point it is final.
"""
import json
import os
import re
import warnings
from pathlib import Path

from .ff import ensure_parent, ffmpeg, probe

LUFS, TRUE_PEAK, LRA = -14.0, -1.0, 11.0
PROFILES_PATH = Path(__file__).resolve().parents[2] / "media" / "loudness-profiles.json"
LUFS_RANGE, TP_RANGE = (-24.0, -6.0), (-9.0, 0.0)


class ProfileError(ValueError):
    """A loudness profile is unknown, unsourced, out of range or the file is unreadable."""


def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ProfileError(f"duplicate profile or field name {key!r} in loudness profiles")
        seen[key] = value
    return seen


def _number(name, field, value, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileError(f"profile {name!r}: {field} must be a number, got {value!r}")
    if not lo <= value <= hi:
        raise ProfileError(f"profile {name!r}: {field} {value} outside [{lo:g}, {hi:g}]")
    return float(value)


def profile(name="default", path=None):
    """Return ``{"lufs", "true_peak"}`` for a named, sourced profile.

    ``path`` or env ``GASPOL_LOUDNESS_PROFILES`` overrides ``media/loudness-profiles.json``.
    A missing file falls back to the built-in default (with a warning); anything else wrong raises.
    """
    path = Path(path or os.environ.get("GASPOL_LOUDNESS_PROFILES") or PROFILES_PATH)
    if not path.exists():
        if name == "default":
            warnings.warn(f"loudness profiles file {path} not found; using built-in default "
                          f"{LUFS:g} LUFS / {TRUE_PEAK:g} dBTP", stacklevel=2)
            return {"lufs": LUFS, "true_peak": TRUE_PEAK}
        raise ProfileError(f"loudness profile {name!r} unknown: profiles file {path} not found")
    try:
        data = json.loads(path.read_text(), object_pairs_hook=_no_duplicates)
    except json.JSONDecodeError as exc:
        raise ProfileError(f"loudness profiles file {path} is not valid JSON: {exc}") from exc
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, dict):
        raise ProfileError(f"loudness profiles file {path} needs an object under 'profiles'")
    if name not in profiles:
        raise ProfileError(f"unknown loudness profile {name!r}; known: {', '.join(sorted(profiles)) or 'none'}")
    entry = profiles[name]
    if not isinstance(entry, dict):
        raise ProfileError(f"profile {name!r} must be an object")
    source = entry.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ProfileError(f"profile {name!r} has no source; an unsourced loudness number is refused")
    return {"lufs": _number(name, "lufs", entry.get("lufs"), *LUFS_RANGE),
            "true_peak": _number(name, "true_peak", entry.get("true_peak"), *TP_RANGE)}


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
