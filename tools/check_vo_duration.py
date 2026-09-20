#!/usr/bin/env python3
"""Fail when a narration line does not fit the cut it is laid into.

    python3 tools/check_vo_duration.py work/vo-fit-K4.json
    python3 tools/check_vo_duration.py --vo vo/master/scene-19-narr.mp3 --len 6.0 --start 0.3

Plan file: a list of segments, one per cut.

    [
      {"id": "S15b", "vo": "vo/master/scene-15b-narr.mp3", "seconds": 5.0, "start": 0.3},
      {"id": "S16",  "vo": "vo/master/scene-16-narr.mp3",  "seconds": 6.0, "start": 0.3}
    ]

`seconds` is how long the cut is, `start` is when the line comes in (default 0.3).

Two failures, both measured, both found late in production before this existed:

  - OVERRUN: start + narration > cut length. The last syllable is cut off. It happened with a
    6.87s line in a 6.0s clip; the fix was shortening the sentence and letting the overlay card
    carry the number, not stretching the picture.
  - DEAD TAIL: the cut runs on more than --max-tail seconds after the line ends. Silence at the
    end of a cut reads as a mistake; trim the cut to the narration instead.

Cut length is planned from the NARRATION, never from the render length: platform clips come back
6s because that is what was ordered, not because the shot needs 6s.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(path)], capture_output=True, text=True, check=True).stdout.strip()
    return float(out) if out else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", nargs="?", help="JSON plan file")
    ap.add_argument("--vo", help="single narration file instead of a plan")
    ap.add_argument("--len", dest="seconds", type=float, help="cut length for --vo")
    ap.add_argument("--start", type=float, default=0.3, help="narration in-point (default 0.3)")
    ap.add_argument("--max-tail", type=float, default=1.5,
                    help="allowed silence after the line ends, seconds")
    ap.add_argument("--root", default=".", help="paths in the plan are relative to this")
    args = ap.parse_args()

    if args.vo:
        if args.seconds is None:
            return fail("--vo needs --len")
        rows = [{"id": Path(args.vo).stem, "vo": args.vo,
                 "seconds": args.seconds, "start": args.start}]
    elif args.plan:
        rows = json.loads(Path(args.plan).read_text())
    else:
        return fail("give a plan file, or --vo with --len")

    root = Path(args.root)
    bad = 0
    for row in rows:
        vo = root / row["vo"]
        if not vo.exists():
            print(f"FAIL {row['id']:6} no narration file {vo}")
            bad += 1
            continue
        start = float(row.get("start", args.start))
        cut = float(row["seconds"])
        spoken = duration(vo)
        end = start + spoken
        tail = cut - end
        if end > cut + 1e-6:
            print(f"FAIL {row['id']:6} narration {spoken:.2f}s from {start:.2f}s needs "
                  f"{end:.2f}s, cut is {cut:.2f}s — over by {end - cut:.2f}s")
            bad += 1
        elif tail > args.max_tail:
            print(f"FAIL {row['id']:6} {tail:.2f}s of silence after the line "
                  f"(limit {args.max_tail:.2f}s) — trim the cut to {end + args.max_tail:.2f}s")
            bad += 1
        else:
            print(f"ok   {row['id']:6} narration {spoken:.2f}s in a {cut:.2f}s cut, "
                  f"tail {tail:.2f}s")

    print(f"\n{len(rows) - bad}/{len(rows)} cuts fit")
    return 1 if bad else 0


def fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
