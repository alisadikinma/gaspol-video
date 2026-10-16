#!/usr/bin/env python3
"""Snap SFX cue times onto the beats of the music bed.

    python3 tools/sfx_snap.py <project-dir> (--music FILE | --music-plan [work/music-plan.json])
                              [--plan work/sfx-plan.json] [--window 0.12]
                              [--out work/sfx-plan.snapped.json]

`--music FILE` is one bed file. `--music-plan` reads the music plan instead: every segment's
`track` (`library:<id>` or a path relative to the project) is beat-detected, the beats inside the
first (to_s - from_s) seconds are kept (a track shorter than its segment repeats its beats every
track length, as the bed loops), shifted by the segment's from_s, and merged. Generate the
music tracks first; this pass does not mix them.

Reads the cue sheet, moves each event's `at_s` to the nearest beat within `--window` seconds,
and writes a NEW file. The original plan is never changed. A stacked cue moves as one: only the
parent `at_s` snaps, so every layer keeps its offset. Run it after the cue sheet is audited and
before `mix_sfx.py` (point `--plan` at the snapped file).

Exit 0 done, 2 bad input (missing plan, music or track, empty or malformed plan, ffmpeg),
3 no beats found in the music (nothing is written; mix the original plan).
"""
import argparse
import json
import sys
from pathlib import Path

# tools/ is not a package on sys.path when this file runs as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import mix_music  # noqa: E402
from tools.vidkit import beats  # noqa: E402


class SnapInputError(Exception):
    """The music or the plan cannot be used; the message names what and where."""


def _resolve(project, value):
    """Absolute stays absolute; a relative path is resolved against the project folder, never the cwd."""
    p = Path(value)
    return p if p.is_absolute() else Path(project) / p


def beats_from_music_plan(project, plan_path):
    """Beat times on the video timeline from every segment of a music plan."""
    try:
        raw = json.loads(Path(plan_path).read_text())["segments"]
    except FileNotFoundError:
        raise SnapInputError(f"no music plan at {plan_path}") from None
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SnapInputError(f"{Path(plan_path).name} has no usable segments list ({exc!r})") from exc
    try:
        segments = mix_music.resolve_segments(raw)
    except mix_music.MusicError as exc:
        raise SnapInputError(f"{Path(plan_path).name}: {exc}") from exc
    times = []
    for i, seg in enumerate(segments, start=1):
        track = seg.get("track")
        path = mix_music.resolve_track(project, track) if isinstance(track, str) else None
        if path is None or not path.is_file():
            raise SnapInputError(f"segment {i}: track {track!r} not found"
                                 + (f" at {path}" if path else ""))
        try:
            found = beats.detect(str(path))
        except beats.BeatError as exc:
            raise SnapInputError(f"segment {i}: track {track!r}: {exc}") from exc
        span = seg["to_s"] - seg["from_s"]
        length = mix_music.duration_of(path)
        if length and length < span:
            shortened = mix_music.fit_track(seg, length)
            span = shortened["to_s"] - shortened["from_s"]
            if shortened["fit"] == "loop":
                found = [b + k * length for k in range(int(span // length) + 1) for b in found]
        times += [round(seg["from_s"] + b, 3) for b in found if b < span]
    return sorted(set(times))


def _check_stacks(data):
    for i, ev in enumerate(data["events"], start=1):
        if not isinstance(ev, dict):
            raise SnapInputError(f"event {i}: must be an object")
        stack = ev.get("stack")
        if "stack" in ev and (not isinstance(stack, list)
                              or not all(isinstance(l, dict) for l in stack)):
            raise SnapInputError(f"event {i}: stack must be a list of objects, got {stack!r}")


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
    ap.add_argument("--music", help="one music bed file")
    ap.add_argument("--music-plan", nargs="?", const="work/music-plan.json",
                    help="beats from every segment of the music plan (default work/music-plan.json)")
    ap.add_argument("--plan", default="work/sfx-plan.json")
    ap.add_argument("--window", type=float, default=0.12)
    ap.add_argument("--out", default="work/sfx-plan.snapped.json")
    a = ap.parse_args(argv)

    if bool(a.music) == bool(a.music_plan):
        print("FAIL: give exactly one of --music FILE or --music-plan [PATH]", file=sys.stderr)
        return 2
    plan_path = _resolve(a.project, a.plan)
    out_path = _resolve(a.project, a.out)
    if out_path.resolve() == plan_path.resolve():
        print("FAIL: --out is the original plan; the original is never overwritten", file=sys.stderr)
        return 2
    try:
        data = json.loads(plan_path.read_text())
    except FileNotFoundError:
        print(f"FAIL: no cue sheet at {plan_path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"FAIL: {plan_path.name} is not valid JSON: line {exc.lineno}, {exc.msg}", file=sys.stderr)
        return 2
    if not isinstance(data, dict) or not data.get("events"):
        print(f"FAIL: {plan_path.name} has no events to snap", file=sys.stderr)
        return 2

    try:
        _check_stacks(data)
        if a.music_plan:
            found = beats_from_music_plan(a.project, _resolve(a.project, a.music_plan))
        else:
            try:
                found = beats.detect(str(_resolve(a.project, a.music)))
            except beats.BeatError as exc:
                raise SnapInputError(str(exc)) from exc
    except SnapInputError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    if not found:
        print("no beats found in the music; plan not changed, nothing written", file=sys.stderr)
        return 3

    try:
        new, moved = snap_plan(data, found, a.window)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"FAIL: an event has no usable at_s ({exc!r})", file=sys.stderr)
        return 2

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
