#!/usr/bin/env python3
"""Fill in automatic zoom motion for the static segments of work/edit-plan.json.

    python3 tools/plan_motion.py <project-dir> [--plan PATH] [--print]

Pass 2 authors work/edit-plan.json by hand. A segment that holds still on screen for more
than five seconds reads as dead air, and a rule for fixing that applied only in prose gives
a different answer every time someone eyeballs it. This tool applies the rule the same way
every run, prints exactly what it changed and what it skipped, and writes the plan back.

The rule:
  * A segment longer than 5.0s is split into `ceil(duration / 5.0)` equal beats, motion
    alternating punch-in/punch-out starting with punch-in.
  * A segment of 5.0s or less gets a single slow punch-in (1.0 -> 1.04).
  * A segment that already carries a `motion` field is left exactly as it is — manual beats
    a planner.
  * A `kind: "shot"` segment is skipped — a Remotion shot already animates itself.

Every motion value this tool emits is a value tools/edit_render.py's own `load_plan()`
already accepts; nothing here re-derives that validation.

Stdlib only. Degrades loudly: a missing or malformed plan file is refused with the file
named, never guessed at.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

from tools.edit_render import MAX_ZOOM, VALID_MOTION_KINDS

# Beyond this, a segment is split into beats rather than given a single slow move.
BEAT_SPLIT_THRESHOLD_S = 5.0
# The beat count is ceil(duration / BEAT_MAX_S); beats are equal length, so a beat can land
# a little under the 3.0s the plan describes as the usual floor (a 5.01s segment makes two
# 2.505s beats) — that is accepted on purpose, not a bug: the alternative is not splitting
# a barely-over-5s segment at all, which defeats the rule it exists for.
BEAT_MAX_S = 5.0

PUNCH_IN = {"kind": "punch-in", "from": 1.0, "to": 1.08}
PUNCH_OUT = {"kind": "punch-out", "from": 1.08, "to": 1.0}
SHORT_MOTION = {"kind": "punch-in", "from": 1.0, "to": 1.04}

# Reuse edit_render's own contract instead of re-deriving it: if either ceiling ever moves
# there, a mismatch here fails loudly at import time instead of shipping a plan that
# edit_render.load_plan() would then reject.
assert PUNCH_IN["kind"] in VALID_MOTION_KINDS and PUNCH_OUT["kind"] in VALID_MOTION_KINDS
assert PUNCH_IN["to"] <= MAX_ZOOM and PUNCH_OUT["from"] <= MAX_ZOOM and SHORT_MOTION["to"] <= MAX_ZOOM

_SCENE_LABEL = re.compile(r"scene-(\d+)", re.IGNORECASE)


class PlanMotionError(Exception):
    """The plan cannot be planned as written. Message names the offending segment."""


def _label(seg, index):
    """A readable name for a report line: `S12` from `clips/scene-12.mp4`, or the plain
    segment index when the source name doesn't say a scene number (a rendered shot, say)."""
    match = _SCENE_LABEL.search(seg.get("src") or "")
    if match:
        return f"S{int(match.group(1))}"
    return f"segment {index}"


def _segment_duration(seg, where):
    try:
        in_s = float(seg["in_s"])
        out_s = float(seg["out_s"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanMotionError(f"{where}: in_s/out_s missing or not a number") from exc
    if out_s <= in_s:
        raise PlanMotionError(f"{where}: out_s {out_s} is not after in_s {in_s}")
    return out_s - in_s


def _split_into_beats(seg, duration, count):
    """`count` new segment dicts covering the same source span as `seg`, each carrying its
    own alternating motion. Only the final beat keeps `pad_end_s`/`pad_mode` — that padding
    belongs at the end of the whole cut, not tacked onto an interior beat."""
    in_s = float(seg["in_s"])
    out_s = float(seg["out_s"])
    beat_len = duration / count
    beats = []
    for i in range(count):
        beat = {k: v for k, v in seg.items()
                 if k not in ("in_s", "out_s", "motion", "pad_end_s", "pad_mode")}
        beat["in_s"] = round(in_s + i * beat_len, 6)
        beat["out_s"] = out_s if i == count - 1 else round(in_s + (i + 1) * beat_len, 6)
        beat["motion"] = dict(PUNCH_IN) if i % 2 == 0 else dict(PUNCH_OUT)
        if i == count - 1:
            if "pad_end_s" in seg:
                beat["pad_end_s"] = seg["pad_end_s"]
            if "pad_mode" in seg:
                beat["pad_mode"] = seg["pad_mode"]
        beats.append(beat)
    return beats


def plan_motion(data):
    """Mutate `data["segments"]` in place: fill `motion` on every eligible segment,
    splitting a long one into beats. Returns `{"changed": [...], "skipped": [...]}`, one
    report line per segment touched or left alone, in plan order."""
    segments = data.get("segments")
    if not isinstance(segments, list):
        raise PlanMotionError("edit-plan.json has no segments list")

    new_segments = []
    changed = []
    skipped = []

    for i, seg in enumerate(segments, start=1):
        where = f"segment {i}"
        if not isinstance(seg, dict):
            raise PlanMotionError(f"{where}: segment is not an object")
        label = _label(seg, i)

        if seg.get("motion") is not None:
            skipped.append(f"{label}: already has motion")
            new_segments.append(seg)
            continue

        if seg.get("kind") == "shot":
            skipped.append(f"{label}: already animated")
            new_segments.append(seg)
            continue

        duration = _segment_duration(seg, where)

        if duration <= BEAT_SPLIT_THRESHOLD_S:
            seg = dict(seg)
            seg["motion"] = dict(SHORT_MOTION)
            new_segments.append(seg)
            changed.append(f"{label} {duration:.1f}s -> in 0.0-{duration:.1f}")
            continue

        count = math.ceil(duration / BEAT_MAX_S)
        beats = _split_into_beats(seg, duration, count)
        new_segments.extend(beats)

        beat_len = duration / count
        parts = []
        for j in range(count):
            start = j * beat_len
            end = duration if j == count - 1 else (j + 1) * beat_len
            word = "in" if j % 2 == 0 else "out"
            parts.append(f"{word} {start:.1f}-{end:.1f}")
        changed.append(f"{label} {duration:.1f}s -> " + ", ".join(parts))

    data["segments"] = new_segments
    return {"changed": changed, "skipped": skipped}


def load_plan_data(plan_path):
    """Read and JSON-parse the plan. Raises PlanMotionError naming the file for anything
    that goes wrong before a single segment is even looked at."""
    plan_path = Path(plan_path)
    try:
        raw = plan_path.read_text()
    except OSError as exc:
        raise PlanMotionError(f"cannot read {plan_path.name}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanMotionError(
            f"{plan_path.name} is not valid JSON: line {exc.lineno}, {exc.msg}"
        ) from exc


def format_report(report):
    lines = []
    if report["changed"]:
        lines.append(f"{len(report['changed'])} segment(s) given automatic motion:")
        lines += [f"  {line}" for line in report["changed"]]
    else:
        lines.append("0 segments changed")
    if report["skipped"]:
        lines.append(f"{len(report['skipped'])} segment(s) skipped:")
        lines += [f"  {line}" for line in report["skipped"]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--plan", help="default: <project>/work/edit-plan.json")
    ap.add_argument("--print", dest="show", action="store_true",
                     help="print the report, write nothing back")
    args = ap.parse_args(argv)

    project = Path(args.project)
    plan_path = Path(args.plan) if args.plan else project / "work" / "edit-plan.json"

    try:
        data = load_plan_data(plan_path)
        report = plan_motion(data)
    except PlanMotionError as exc:
        print(f"plan_motion: {exc}", file=sys.stderr)
        return 1

    print(format_report(report))
    if args.show:
        return 0

    plan_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"\nwrote {plan_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
