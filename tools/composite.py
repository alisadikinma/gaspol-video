#!/usr/bin/env python3
"""Put a rendered Remotion shot onto the master.

    python3 tools/composite.py cutaway <master> <shot> --at 12.0 --out-s 17.0 -o out.mp4
    python3 tools/composite.py overlay <master> <shot> --at 12.0 -o out.mp4

Two modes, and the difference matters:

  cutaway  the shot REPLACES the picture for its span. Master audio continues underneath,
           which is what keeps a narration line running across the cut.
  overlay  a transparent shot is composited OVER the picture. For a badge, a lower third,
           or a number appearing beside a presenter who stays on screen.

Master audio survives in both. A shot that carried its own audio would double whatever the
narration is already saying.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


class CompositeError(Exception):
    """The shot cannot be placed as asked."""


def _probe(path, entries, stream="v:0"):
    if FFPROBE is None:
        raise CompositeError("ffprobe not found on PATH")
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", stream,
         "-show_entries", entries, "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise CompositeError(f"{Path(path).name}: unreadable")
    return json.loads(proc.stdout)


def duration_of(path):
    data = _probe(path, "stream=duration")
    streams = data.get("streams", [])
    if not streams or streams[0].get("duration") in (None, "N/A"):
        return None
    return float(streams[0]["duration"])


def require_alpha(path):
    """An overlay without an alpha channel would black out the picture it is meant to sit on."""
    data = _probe(path, "stream=pix_fmt")
    streams = data.get("streams", [])
    pix_fmt = streams[0].get("pix_fmt", "") if streams else ""
    if "a" not in pix_fmt.replace("yuva", "A").lower().replace("rgba", "A").lower() and \
       not any(tag in pix_fmt for tag in ("yuva", "rgba", "argb", "abgr")):
        raise CompositeError(
            f"{Path(path).name} has no alpha channel (pix_fmt {pix_fmt or 'unknown'}). "
            "Render the shot with transparent: true, or place it as a cutaway instead."
        )
    return True


def validate_span(at_s, out_s, master_duration_s):
    if at_s < 0:
        raise CompositeError(f"span starts before the master ({at_s}s)")
    if out_s <= at_s:
        raise CompositeError(f"span ends at {out_s}s, which is not after {at_s}s")
    if master_duration_s is not None and at_s >= master_duration_s:
        raise CompositeError(
            f"span starts at {at_s}s, past the end of the master ({master_duration_s:.2f}s)"
        )
    return True


def _run(cmd):
    if FFMPEG is None:
        raise CompositeError(
            "ffmpeg not found on PATH — nothing was composited. Run this elsewhere:\n  "
            + " ".join(str(c) for c in cmd)
        )
    proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        raise CompositeError(f"composite failed:\n{proc.stderr.strip()[-600:]}")


def cutaway(master, shot, at_s, out_s, out):
    validate_span(at_s, out_s, duration_of(master))
    span = out_s - at_s
    filt = (
        f"[1:v]trim=0:{span},setpts=PTS-STARTPTS,scale=-2:ih[shot];"
        f"[0:v][shot]overlay=0:0:enable='between(t,{at_s},{out_s})'[v]"
    )
    _run([FFMPEG, "-y", "-v", "error", "-i", master, "-itsoffset", at_s, "-i", shot,
          "-filter_complex", filt, "-map", "[v]", "-map", "0:a?",
          "-c:a", "copy", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", out])
    return str(out)


def overlay(master, shot, at_s, out=None, out_s=None):
    master_duration = duration_of(master)
    shot_duration = duration_of(shot) or 0.0
    end = out_s if out_s is not None else at_s + shot_duration
    validate_span(at_s, end, master_duration)
    filt = f"[0:v][1:v]overlay=0:0:enable='between(t,{at_s},{end})'[v]"
    _run([FFMPEG, "-y", "-v", "error", "-i", master, "-itsoffset", at_s, "-i", shot,
          "-filter_complex", filt, "-map", "[v]", "-map", "0:a?",
          "-c:a", "copy", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", out])
    return str(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("cutaway", "overlay"))
    ap.add_argument("master")
    ap.add_argument("shot")
    ap.add_argument("--at", type=float, required=True)
    ap.add_argument("--out-s", type=float)
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args(argv)
    try:
        if args.mode == "cutaway":
            if args.out_s is None:
                raise CompositeError("cutaway needs --out-s")
            cutaway(args.master, args.shot, args.at, args.out_s, args.out)
        else:
            require_alpha(args.shot)
            overlay(args.master, args.shot, args.at, out=args.out, out_s=args.out_s)
        print(f"wrote {args.out}")
        return 0
    except CompositeError as exc:
        print(f"composite: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
