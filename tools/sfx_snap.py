#!/usr/bin/env python3
"""Snap SFX cue times onto the beats of the music bed.

    python3 tools/sfx_snap.py <project-dir> --music FILE [--plan work/sfx-plan.json]
                              [--window 0.12] [--out work/sfx-plan.snapped.json]

Reads the cue sheet, moves each event's `at_s` to the nearest beat within `--window` seconds,
and writes a NEW file. The original plan is never changed. A stacked cue moves as one: only the
parent `at_s` snaps, so every layer keeps its offset. Run it after the cue sheet is audited and
before `mix_sfx.py` (point `--plan` at the snapped file).

Exit 0 done, 1 bad input (missing plan or music, empty plan, ffmpeg), 2 no beats found in the
music (nothing is written).
"""
import argparse
import json
import sys
from pathlib import Path

# tools/ is not a package on sys.path when this file runs as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.vidkit import beats  # noqa: E402


def _resolve(project, value):
    """Absolute stays absolute; a relative path is resolved against the project folder, never the cwd."""
    p = Path(value)
    return p if p.is_absolute() else Path(project) / p


def snap_plan(data, beat_times, window_s):
    """Return ``(new_data, moved)``; ``moved`` = ``[(label, from_s, to_s)]``. Input untouched."""
    new = json.loads(json.dumps(data))
    moved = []
    for i, ev in enumerate(new["events"], start=1):
        old = float(ev["at_s"])
        to = round(beats.snap([old], beat_times, window_s)[0], 3)
        if abs(to - old) > 1e-9:
            label = ev.get("sfx_id") or "stack:" + "+".join(l.get("sfx_id", "?") for l in ev.get("stack", []))
            moved.append((f"{i}:{label}", old, to))
            ev["at_s"] = to
    return new, moved


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sfx_snap", description="Snap SFX cues to music beats.")
    ap.add_argument("project")
    ap.add_argument("--music", required=True)
    ap.add_argument("--plan", default="work/sfx-plan.json")
    ap.add_argument("--window", type=float, default=0.12)
    ap.add_argument("--out", default="work/sfx-plan.snapped.json")
    a = ap.parse_args(argv)

    plan_path = _resolve(a.project, a.plan)
    out_path = _resolve(a.project, a.out)
    if out_path.resolve() == plan_path.resolve():
        print("FAIL: --out is the original plan; the original is never overwritten", file=sys.stderr)
        return 1
    try:
        data = json.loads(plan_path.read_text())
    except FileNotFoundError:
        print(f"FAIL: no cue sheet at {plan_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAIL: {plan_path.name} is not valid JSON: line {exc.lineno}, {exc.msg}", file=sys.stderr)
        return 1
    if not data.get("events"):
        print(f"FAIL: {plan_path.name} has no events to snap", file=sys.stderr)
        return 1

    try:
        found = beats.detect(str(_resolve(a.project, a.music)))
    except beats.BeatError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if not found:
        print("no beats found in the music; plan not changed, nothing written", file=sys.stderr)
        return 2

    try:
        new, moved = snap_plan(data, found, a.window)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"FAIL: an event has no usable at_s ({exc!r})", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(new, indent=2) + "\n")

    print(f"{len(found)} beats found; window {a.window}s")
    if moved:
        print(f"{'cue':<28}{'from':>8}{'to':>8}{'delta':>8}")
        for label, f, t in moved:
            print(f"{label:<28}{f:>8.2f}{t:>8.2f}{t - f:>+8.2f}")
    total = len(new["events"])
    print(f"{len(moved)} moved, {total - len(moved)} unchanged -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
