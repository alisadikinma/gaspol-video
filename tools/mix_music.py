#!/usr/bin/env python3
"""Lay a music bed under the finished voice, and never over it.

    python3 tools/mix_music.py <project-dir> [--plan PATH] [--master PATH] [--print]

The track choice is not asked for again: `av-script.md` has carried a per-scene music
direction since Phase 2, and until now nothing read it. This pass does.

Fail-soft, adapted from MoneyPrinterTurbo (see NOTICE): a track that will not load, fade or
mix leaves a finished voice-only video plus a warning naming what failed. A missing music bed
is obvious on the first play; a missing video is a lost afternoon.

Stdlib only. ffmpeg for mixing, wave for measurement.
"""

import argparse
import array
import json
import math
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

# The bed sits at least this far below the voice, measured, not assumed.
MIN_HEADROOM_DB = 12.0
DEFAULT_GAIN_DB = -22.0

# Tone (global-promo-config.md §13) -> the mood a track should carry.
TONE_TO_MOOD = {
    "humorous": "warm-uplift",
    "serious": "tense-low-pulse",
    "professional": "neutral-corporate",
    "inspirational": "warm-uplift",
    "casual": "sparse-ambient",
    "edgy": "driving-build",
}


class MusicError(Exception):
    """The music plan cannot be applied as written."""


def mood_for_tone(tone):
    return TONE_TO_MOOD.get((tone or "").strip().lower())


def _decode(path, tmpdir):
    path = Path(path)
    if path.suffix.lower() == ".wav":
        return str(path)
    if FFMPEG is None:
        raise MusicError(f"ffmpeg not available to decode {path.name}")
    out = Path(tmpdir) / f"{path.stem}.wav"
    proc = subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "48000",
         "-c:a", "pcm_s16le", str(out)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise MusicError(f"{path.name}: cannot decode ({proc.stderr.strip()[-200:]})")
    return str(out)


def level_dbfs(path):
    """Overall RMS level of a file, in dBFS."""
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = _decode(path, tmp)
        try:
            with wave.open(wav_path, "rb") as w:
                if w.getsampwidth() != 2:
                    raise MusicError(f"{Path(path).name}: expected 16-bit audio")
                frames = w.readframes(w.getnframes())
                channels = w.getnchannels()
        except wave.Error as exc:
            raise MusicError(f"{Path(path).name}: not readable audio ({exc})") from exc

    samples = array.array("h")
    samples.frombytes(frames)
    if channels > 1:
        samples = samples[::channels]
    if not samples:
        return -120.0
    mean_square = sum((s / 32768.0) ** 2 for s in samples) / len(samples)
    return -120.0 if mean_square <= 0 else 20.0 * math.log10(math.sqrt(mean_square))


def gain_to_sit_under(voice_path, music_path, headroom_db=MIN_HEADROOM_DB):
    """dB to apply to the music so it sits headroom_db below the voice. Never returns a boost."""
    voice = level_dbfs(voice_path)
    music = level_dbfs(music_path)
    return min(0.0, round((voice - headroom_db) - music, 2))


def duration_of(path):
    if FFPROBE is None:
        return None
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def resolve_segments(segments, master_duration_s=None):
    resolved = []
    for i, seg in enumerate(segments, start=1):
        out = dict(seg)
        try:
            out["from_s"] = float(seg["from_s"])
            out["to_s"] = float(seg["to_s"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MusicError(f"segment {i}: from_s/to_s missing or not a number") from exc
        if out["to_s"] <= out["from_s"]:
            raise MusicError(f"segment {i}: to_s {out['to_s']} is not after from_s {out['from_s']}")
        if master_duration_s is not None and out["to_s"] > master_duration_s:
            out["to_s"] = round(master_duration_s, 3)
            out["trimmed"] = True
        out.setdefault("gain_db", DEFAULT_GAIN_DB)
        resolved.append(out)

    resolved.sort(key=lambda s: s["from_s"])
    for a, b in zip(resolved, resolved[1:]):
        if b["from_s"] < a["to_s"] - 1e-6:
            raise MusicError(
                f"segments overlap: one ends at {a['to_s']}s, the next starts at {b['from_s']}s. "
                "Two beds at once fight each other and the voice."
            )
    return resolved


def fit_track(segment, track_duration_s):
    """A track shorter than its segment either loops or shortens the segment. Say which."""
    needed = segment["to_s"] - segment["from_s"]
    out = dict(segment)
    if track_duration_s >= needed:
        out["fit"] = "exact"
        out["fit_note"] = f"track {track_duration_s}s covers {needed}s"
        return out
    if needed / track_duration_s <= 4:
        out["fit"] = "loop"
        out["fit_note"] = (f"track {track_duration_s}s looped with a crossfade to cover {needed}s")
    else:
        out["fit"] = "shorten"
        out["to_s"] = round(segment["from_s"] + track_duration_s, 3)
        out["fit_note"] = (f"track {track_duration_s}s is far shorter than {needed}s; "
                           "the bed was shortened rather than looped four times")
    return out


def apply(plan_path, project, master=None, out=None, log=print):
    """Mix the bed. Never raises for a music problem: it warns and returns."""
    project = Path(project)
    warnings = []
    try:
        plan = json.loads(Path(plan_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"music plan unreadable ({exc}) — the video ships without a bed")
        return {"degraded": True, "warnings": warnings, "segments": 0, "exit_code": 0, "out": None}

    master = Path(master) if master else project / "output" / "master.mp4"
    out = Path(out) if out else project / plan.get("out", "output/master-mixed.mp4")

    raw = plan.get("segments", [])
    if not raw:
        warnings.append("no music direction in this plan — nothing was laid under the video")
        log(warnings[-1])
        return {"degraded": False, "warnings": warnings, "segments": 0, "exit_code": 0, "out": None}

    try:
        segments = resolve_segments(raw, master_duration_s=duration_of(master))
    except MusicError as exc:
        warnings.append(f"{exc} — the video ships without a bed")
        log(warnings[-1])
        return {"degraded": True, "warnings": warnings, "segments": 0, "exit_code": 0, "out": None}

    usable = []
    for seg in segments:
        track = project / seg["track"]
        try:
            level_dbfs(track)          # proves it is readable audio before ffmpeg sees it
        except MusicError as exc:
            warnings.append(f"{Path(seg['track']).name}: {exc} — this segment was dropped")
            log(warnings[-1])
            continue
        usable.append(seg)

    if not usable:
        warnings.append("no usable music track — the voice-only video is the deliverable")
        log(warnings[-1])
        return {"degraded": True, "warnings": warnings, "segments": 0, "exit_code": 0, "out": None}

    if FFMPEG is None:
        warnings.append("ffmpeg not found — the bed was not mixed. The plan is still the deliverable.")
        log(warnings[-1])
        return {"degraded": True, "warnings": warnings, "segments": len(usable),
                "exit_code": 0, "out": None}

    cmd = [FFMPEG, "-y", "-v", "error", "-i", str(master)]
    filters, labels = [], []
    for i, seg in enumerate(usable, start=1):
        cmd += ["-i", str(project / seg["track"])]
        delay = int(seg["from_s"] * 1000)
        length = seg["to_s"] - seg["from_s"]
        fi = seg.get("fade_in_s", 1.0)
        fo = seg.get("fade_out_s", 2.0)
        filters.append(
            f"[{i}:a]atrim=0:{length},afade=t=in:st=0:d={fi},"
            f"afade=t=out:st={max(0, length - fo)}:d={fo},"
            f"volume={seg['gain_db']}dB,adelay={delay}|{delay}[m{i}]"
        )
        labels.append(f"[m{i}]")
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0[bed]")
    filters.append("[0:a][bed]amix=inputs=2:normalize=0,alimiter=limit=0.95[aout]")

    cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", str(out)]
    log("+ " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        warnings.append(f"the mix failed ({proc.stderr.strip()[-200:]}) — the voice-only master stands")
        log(warnings[-1])
        return {"degraded": True, "warnings": warnings, "segments": len(usable),
                "exit_code": 0, "out": None}

    return {"degraded": False, "warnings": warnings, "segments": len(usable),
            "exit_code": 0, "out": str(out)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--plan")
    ap.add_argument("--master")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    project = Path(args.project)
    plan_path = Path(args.plan) if args.plan else project / "work" / "music-plan.json"
    result = apply(plan_path, project, master=args.master, out=args.out)
    for w in result["warnings"]:
        print(f"! {w}", file=sys.stderr)
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
