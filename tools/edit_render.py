#!/usr/bin/env python3
"""Assemble a master from work/edit-plan.json with ffmpeg.

    python3 tools/edit_render.py <project-dir> [--plan PATH] [--print] [--out PATH]

The plan is the reviewable artefact; this tool is deliberately dumb. It validates the
plan hard BEFORE touching ffmpeg, because a plan error found after a 40-second encode is
a plan error found too late.

Two things it will not do:
  * render a plan whose numbers do not hold up (see PlanError below)
  * hand back a master whose video and audio durations disagree

Stdlib only. Degrades loudly when ffmpeg is missing.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

# One frame at 25fps. See probe_clips for why this is equality and not a growing budget.
AV_TOLERANCE_S = 0.04

# A freeze longer than this reads as a stall rather than a beat. Warned, never blocked:
# sometimes a held frame is the intent.
PAD_WARN_S = 1.0

VALID_KINDS = ("clip", "shot")
VALID_PAD_MODES = ("freeze", "black")


class PlanError(Exception):
    """The plan cannot be rendered as written. Message names the offending segment."""


class Plan:
    def __init__(self, data, project, path):
        self.data = data
        self.project = Path(project)
        self.path = Path(path)
        self.warnings = []

    @property
    def segments(self):
        return self.data["segments"]

    @property
    def out(self):
        return self.project / self.data.get("out", "output/master.mp4")

    @property
    def fps(self):
        return self.data.get("fps", 30)

    @property
    def size(self):
        return self.data.get("width", 1920), self.data.get("height", 1080)

    @property
    def total_s(self):
        return round(sum(_segment_length(s) for s in self.segments), 3)


def _segment_length(seg):
    return (seg["out_s"] - seg["in_s"]) + seg.get("pad_end_s", 0.0)


def _probe_duration(path):
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


def load_plan(plan_path, project, check_durations=True):
    """Read and validate. Raises PlanError with a message naming what is wrong."""
    plan_path = Path(plan_path)
    project = Path(project)

    try:
        raw = plan_path.read_text()
    except OSError as exc:
        raise PlanError(f"cannot read {plan_path.name}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanError(f"{plan_path.name} is not valid JSON: line {exc.lineno}, {exc.msg}") from exc

    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise PlanError(f"{plan_path.name} has no segments — nothing to render")

    plan = Plan(data, project, plan_path)

    for i, seg in enumerate(segments, start=1):
        where = f"segment {i}"
        kind = seg.get("kind")
        if kind not in VALID_KINDS:
            raise PlanError(f"{where}: unknown kind {kind!r}, expected one of {', '.join(VALID_KINDS)}")

        src = seg.get("src")
        if not src:
            raise PlanError(f"{where}: no src")
        src_path = project / src
        if not src_path.is_file():
            raise PlanError(f"{where}: source not found: {src}")

        try:
            in_s = float(seg["in_s"])
            out_s = float(seg["out_s"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanError(f"{where}: in_s/out_s missing or not a number") from exc

        if in_s < 0:
            raise PlanError(f"{where}: in_s is negative ({in_s})")
        if out_s <= in_s:
            raise PlanError(f"{where}: out_s {out_s} is not after in_s {in_s}")

        pad = float(seg.get("pad_end_s", 0.0) or 0.0)
        if pad < 0:
            raise PlanError(f"{where}: pad_end_s is negative ({pad})")
        mode = seg.get("pad_mode", "freeze")
        if pad and mode not in VALID_PAD_MODES:
            raise PlanError(f"{where}: unknown pad_mode {mode!r}")
        if pad > PAD_WARN_S:
            plan.warnings.append(
                f"{where}: pad_end_s {pad}s is over {PAD_WARN_S}s — a freeze that long reads as a stall"
            )

        if check_durations:
            actual = _probe_duration(src_path)
            if actual is not None and out_s > actual + AV_TOLERANCE_S:
                raise PlanError(
                    f"{where}: out_s {out_s}s is longer than {src} ({actual:.2f}s)"
                )

    return plan


def build_commands(plan):
    """One ffmpeg invocation per segment, then a concat. Returned so --print can show them."""
    width, height = plan.size
    work = plan.project / "work" / "render"
    cmds = []
    parts = []

    for i, seg in enumerate(plan.segments, start=1):
        src = plan.project / seg["src"]
        part = work / f"part-{i:03d}.mp4"
        parts.append(part)
        dur = seg["out_s"] - seg["in_s"]
        pad = float(seg.get("pad_end_s", 0.0) or 0.0)

        vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease," \
             f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={plan.fps}"
        if pad:
            # tpad holds the final frame (freeze) or appends black; audio is padded with
            # silence either way so the two streams stay the same length.
            clone = "clone" if seg.get("pad_mode", "freeze") == "freeze" else "add=black"
            vf += f",tpad=stop_mode={clone}:stop_duration={pad}"

        cmd = [FFMPEG, "-y", "-v", "error",
               "-ss", str(seg["in_s"]), "-t", str(dur), "-i", str(src),
               "-vf", vf,
               "-af", f"apad=pad_dur={pad}" if pad else "anull",
               "-t", str(dur + pad),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-ar", "48000", "-ac", "2",
               str(part)]
        cmds.append(cmd)

    return cmds, parts, work


def av_durations(path):
    return _probe_duration_stream(path, "v:0"), _probe_duration_stream(path, "a:0")


def _probe_duration_stream(path, stream):
    if FFPROBE is None:
        return None
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", stream,
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    line = proc.stdout.strip().splitlines()
    if not line or line[0] in ("", "N/A"):
        return None
    try:
        return float(line[0])
    except ValueError:
        return None


def check_av_gate(path):
    """Returns (ok, message). The gate is equality within one frame at 25fps."""
    v, a = av_durations(path)
    if v is None:
        return False, "rendered master has no readable video duration"
    if a is None:
        return False, "rendered master has no audio stream"
    if abs(v - a) > AV_TOLERANCE_S:
        return False, f"A/V duration gate FAILED: v:0 {v:.3f}s != a:0 {a:.3f}s"
    return True, f"A/V duration gate passed: v:0 {v:.3f}s, a:0 {a:.3f}s"


def format_sheet(plan):
    lines = [f"{plan.path.name}: {len(plan.segments)} segment(s), {plan.total_s:.2f}s total, "
             f"{plan.size[0]}x{plan.size[1]} @ {plan.fps}fps",
             f"out: {plan.data.get('out', 'output/master.mp4')}"]
    at = 0.0
    for i, seg in enumerate(plan.segments, start=1):
        length = _segment_length(seg)
        pad = seg.get("pad_end_s", 0.0)
        note = f"  +{pad}s {seg.get('pad_mode', 'freeze')}" if pad else ""
        lines.append(f"  {i:>3}. {at:7.2f} -> {at + length:7.2f}  {length:5.2f}s  "
                     f"{seg['kind']:<5} {seg['src']}  [{seg['in_s']:.2f}-{seg['out_s']:.2f}]{note}")
        at += length
    for w in plan.warnings:
        lines.append(f"  ! {w}")
    return "\n".join(lines)


def render(plan_path, project, out=None, allow_degraded=False, keep_parts=False):
    """Render the plan. Returns the output path, or None when degraded."""
    if FFMPEG is None:
        msg = ("ffmpeg not found on PATH — nothing was rendered. Install ffmpeg, or run the "
               "printed commands elsewhere: python3 tools/edit_render.py <project> --print")
        if allow_degraded:
            print(msg, file=sys.stderr)
            return None
        raise PlanError(msg)

    plan = load_plan(plan_path, project)
    if out:
        plan.data["out"] = str(out)

    cmds, parts, work = build_commands(plan)
    work.mkdir(parents=True, exist_ok=True)
    plan.out.parent.mkdir(parents=True, exist_ok=True)

    for cmd in cmds:
        print("+ " + " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise PlanError(f"ffmpeg failed on a segment:\n{proc.stderr.strip()[-800:]}")

    listfile = work / "concat.txt"
    listfile.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    concat = [FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listfile),
              "-c", "copy", str(plan.out)]
    print("+ " + " ".join(concat))
    proc = subprocess.run(concat, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PlanError(f"concat failed:\n{proc.stderr.strip()[-800:]}")

    ok, message = check_av_gate(plan.out)
    print(message)
    if not ok:
        raise PlanError(f"{message} — the render is rejected, not shipped with a note")

    if not keep_parts:
        for p in parts:
            p.unlink(missing_ok=True)
        listfile.unlink(missing_ok=True)

    return str(plan.out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--plan", help="default: <project>/work/edit-plan.json")
    ap.add_argument("--out", help="override the plan's out path")
    ap.add_argument("--print", dest="show", action="store_true",
                    help="print the segment sheet and the ffmpeg commands, render nothing")
    ap.add_argument("--keep", action="store_true", help="keep the per-segment parts")
    args = ap.parse_args(argv)

    project = Path(args.project)
    plan_path = Path(args.plan) if args.plan else project / "work" / "edit-plan.json"

    try:
        if args.show:
            plan = load_plan(plan_path, project)
            print(format_sheet(plan))
            if FFMPEG:
                print("\ncommands:")
                for cmd in build_commands(plan)[0]:
                    print("  " + " ".join(cmd))
            return 0
        result = render(plan_path, project, out=args.out, allow_degraded=True, keep_parts=args.keep)
        return 0 if result else 0
    except PlanError as exc:
        print(f"edit_render: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
