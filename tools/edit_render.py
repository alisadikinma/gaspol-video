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
import math
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

VALID_MOTION_KINDS = ("punch-in", "punch-out", "none")

# Beyond this, 1080p platform-generated clips go visibly soft, which costs more than a
# still frame does.
MAX_ZOOM = 1.12

# An act change may dissolve into the next segment. Under 0.2s it reads as a glitch, over
# 1.0s it eats the beat it is meant to punctuate.
VALID_TRANSITIONS = ("dissolve",)
TRANSITION_MIN_S = 0.2
TRANSITION_MAX_S = 1.0


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

        _check_motion(seg.get("motion"), where)
        _check_transition(seg, segments[i - 2] if i > 1 else None, i, project, check_durations)

        if check_durations:
            actual = _probe_duration(src_path)
            if actual is not None and out_s > actual + AV_TOLERANCE_S:
                raise PlanError(
                    f"{where}: out_s {out_s}s is longer than {src} ({actual:.2f}s)"
                )

    return plan


def _check_motion(motion, where):
    """Validate a segment's `motion` field. None (absent or JSON null) is fine — the
    field is additive, an old plan without it keeps working. Raises PlanError naming
    `where` (the segment) for anything that cannot be rendered as written."""
    if motion is None:
        return
    if not isinstance(motion, dict):
        raise PlanError(f"{where}: motion must be an object, got {motion!r}")

    kind = motion.get("kind")
    if kind not in VALID_MOTION_KINDS:
        raise PlanError(
            f"{where}: unknown motion kind {kind!r}, expected one of {', '.join(VALID_MOTION_KINDS)}"
        )
    if kind == "none":
        return

    try:
        frm = float(motion["from"])
        to = float(motion["to"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanError(f"{where}: motion.from/to missing or not a number") from exc

    if not math.isfinite(frm) or not math.isfinite(to):
        raise PlanError(f"{where}: motion.from/to must be finite numbers (from={frm}, to={to})")
    if not (1.0 <= frm <= MAX_ZOOM):
        raise PlanError(f"{where}: motion.from {frm} must be between 1.0 and {MAX_ZOOM}")
    if not (1.0 <= to <= MAX_ZOOM):
        raise PlanError(f"{where}: motion.to {to} must be between 1.0 and {MAX_ZOOM}")
    if kind == "punch-in" and not (to > frm):
        raise PlanError(f"{where}: punch-in requires to > from (from={frm}, to={to})")
    if kind == "punch-out" and not (to < frm):
        raise PlanError(f"{where}: punch-out requires to < from (from={frm}, to={to})")


def _check_transition(seg, prev, i, project, check_durations):
    """Validate a segment's `transition_in`. None (absent or JSON null) is fine — the
    field is additive. The dissolve is rendered over source frames past the previous
    segment's out_s, so the timeline never moves; every refusal below is a case where
    those frames would not exist or the fade would not fit."""
    transition = seg.get("transition_in")
    if transition is None:
        return
    where = f"segment {i}"
    if prev is None:
        raise PlanError(f"{where}: transition_in on the first segment — there is nothing to dissolve from")
    if not isinstance(transition, dict):
        raise PlanError(f"{where}: transition_in must be an object, got {transition!r}")

    kind = transition.get("kind")
    if kind not in VALID_TRANSITIONS:
        raise PlanError(
            f"{where}: unknown transition kind {kind!r}, expected one of {', '.join(VALID_TRANSITIONS)}"
        )
    try:
        dur = float(transition["dur_s"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanError(f"{where}: transition_in.dur_s missing or not a number") from exc
    if not math.isfinite(dur):
        raise PlanError(f"{where}: transition_in.dur_s must be a finite number ({dur})")
    if not (TRANSITION_MIN_S <= dur <= TRANSITION_MAX_S):
        raise PlanError(
            f"{where}: transition_in.dur_s {dur} must be between {TRANSITION_MIN_S} and {TRANSITION_MAX_S}"
        )

    if dur >= _segment_length(seg):
        raise PlanError(f"{where}: transition_in.dur_s {dur} is not shorter than this segment ({_segment_length(seg):.2f}s)")
    if dur >= _segment_length(prev):
        raise PlanError(f"{where}: transition_in.dur_s {dur} is not shorter than the previous segment ({_segment_length(prev):.2f}s)")

    if float(prev.get("pad_end_s", 0.0) or 0.0) > 0:
        mode = prev.get("pad_mode", "freeze")
        raise PlanError(f"{where}: previous segment ends in a {mode} pad — no source frames to dissolve over")

    if check_durations:
        prev_src = prev.get("src")
        actual = _probe_duration(Path(project) / prev_src) if prev_src else None
        if actual is not None:
            handle = actual - float(prev["out_s"])
            if actual < float(prev["out_s"]) + dur - AV_TOLERANCE_S:
                raise PlanError(
                    f"{where}: previous source {prev_src} has {handle:.2f}s after out_s, "
                    f"dissolve needs {dur}s — extend out_s earlier or shorten dur_s"
                )


def _motion_filter(motion, duration_s, width, height, clamp=False):
    """The zoom filter for one segment, or None when there is no motion (absent, JSON
    null, or `kind: none`) — in which case the caller adds nothing and the chain stays
    byte-identical to what this tool renders today.

    Deliberately not ffmpeg's frame-quantized pan/zoom filter: that one rounds pan
    position to whole pixels, so a slow move stutters. An earlier version of this
    function animated `crop`'s `w`/`h` with a `t` expression instead — ffmpeg refuses
    that outright, because `crop` evaluates `w`/`h` ONCE, at filter-configuration time,
    where `t` does not exist yet; only `x`/`y` are per-frame there. `scale` is the
    filter that accepts `eval=frame`, so the zoom happens there and `crop` then takes a
    fixed, centred window out of the enlarged frame. `ceil(.../2)*2` keeps every
    intermediate dimension even, which yuv420p requires.

    `clamp` is for a segment rendered past its planned length (a dissolve handle): the
    zoom holds at `to` instead of running on over the frames the fade consumes.
    """
    if not motion or motion.get("kind") == "none":
        return None

    frm = float(motion["from"])
    to = float(motion["to"])
    # Rounded so plain values like 1.0 -> 1.08 don't pick up float-subtraction noise
    # (1.08 - 1.0 == 0.08000000000000007) in the emitted expression.
    delta = round(to - frm, 6)
    t = f"min(t\\,{duration_s})" if clamp else "t"
    zoom = f"({frm}+({delta})*{t}/{duration_s})"
    return (
        f"scale=w='ceil({width}*{zoom}/2)*2':h='ceil({height}*{zoom}/2)*2':eval=frame,"
        f"crop={width}:{height}"
    )


def _dissolve_dur(seg):
    """Seconds of dissolve INTO this segment, 0.0 when it has none."""
    transition = seg.get("transition_in")
    return float(transition["dur_s"]) if transition else 0.0


def build_commands(plan):
    """One ffmpeg invocation per segment, one merge per run of dissolved segments, then a
    concat. Returned so --print can show them; `parts` are the files the concat joins.

    A dissolve must not move the timeline, so the segment BEFORE it is rendered
    `dur_s` longer, from the source frames past its out_s, and the merge overlaps that
    handle with the head of the incoming segment.
    """
    width, height = plan.size
    work = plan.project / "work" / "render"
    cmds = []
    seg_parts = []
    segments = plan.segments

    for i, seg in enumerate(segments, start=1):
        src = plan.project / seg["src"]
        part = work / f"part-{i:03d}.mp4"
        seg_parts.append(part)
        dur = seg["out_s"] - seg["in_s"]
        pad = float(seg.get("pad_end_s", 0.0) or 0.0)
        # The handle: source frames past out_s that the next segment dissolves over.
        ext = _dissolve_dur(segments[i]) if i < len(segments) else 0.0
        render_dur = round(dur + ext, 3) if ext else dur

        vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease," \
             f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        motion_filter = _motion_filter(seg.get("motion"), dur, width, height, clamp=bool(ext))
        if motion_filter:
            vf += "," + motion_filter
        vf += f",fps={plan.fps}"
        if pad:
            # tpad holds the final frame (freeze) or appends black; audio is padded with
            # silence either way so the two streams stay the same length.
            clone = "clone" if seg.get("pad_mode", "freeze") == "freeze" else "add=black"
            vf += f",tpad=stop_mode={clone}:stop_duration={pad}"

        cmd = [FFMPEG, "-y", "-v", "error",
               "-ss", str(seg["in_s"]), "-t", str(render_dur), "-i", str(src),
               "-vf", vf,
               "-af", f"apad=pad_dur={pad}" if pad else "anull",
               "-t", str(render_dur + pad),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-ar", "48000", "-ac", "2",
               str(part)]
        cmds.append(cmd)

    # Consecutive dissolves form a group; each group becomes one file for the concat.
    groups = []
    for i, seg in enumerate(segments):
        if i and seg.get("transition_in"):
            groups[-1].append(i)
        else:
            groups.append([i])

    parts = []
    merges = []
    for g, members in enumerate(groups, start=1):
        if len(members) == 1:
            parts.append(seg_parts[members[0]])
            continue
        merged = work / f"group-{g:03d}.mp4"
        parts.append(merged)
        merges.append(_merge_command(plan, members, seg_parts, merged))

    return cmds + merges, parts, work


def _merge_command(plan, members, seg_parts, merged):
    """Chain xfade/acrossfade over the parts of one group. The offset of each dissolve is
    the PLANNED length of everything before the incoming part, so it starts at exactly its
    planned second; the outgoing part's handle is what the fade eats."""
    inputs = []
    for idx in members:
        inputs += ["-i", str(seg_parts[idx])]

    video, audio = [], []
    v_in, a_in = "[0:v]", "[0:a]"
    planned = _segment_length(plan.segments[members[0]])
    for k, idx in enumerate(members[1:], start=1):
        d = _dissolve_dur(plan.segments[idx])
        last = k == len(members) - 1
        v_out, a_out = ("[vout]", "[aout]") if last else (f"[v{k}]", f"[a{k}]")
        video.append(f"{v_in}[{k}:v]xfade=transition=fade:duration={d}:offset={round(planned, 3)}{v_out}")
        audio.append(f"{a_in}[{k}:a]acrossfade=d={d}:c1=tri:c2=tri{a_out}")
        v_in, a_in = v_out, a_out
        planned += _segment_length(plan.segments[idx])

    # The last part carries no handle, so `planned` is now the group's exact planned
    # length. Capping at it drops the encoder padding aac appends after the final frame,
    # which the concat would otherwise add to the master.
    return [FFMPEG, "-y", "-v", "error", *inputs,
            "-filter_complex", ";".join(video + audio),
            "-map", "[vout]", "-map", "[aout]", "-r", str(plan.fps), "-t", str(round(planned, 3)),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
            str(merged)]


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
        if seg.get("transition_in"):
            note += f"  ~{_dissolve_dur(seg)}s dissolve at {at:.2f}s"
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
            what = "a dissolve merge" if Path(cmd[-1]).name.startswith("group-") else "a segment"
            raise PlanError(f"ffmpeg failed on {what}:\n{proc.stderr.strip()[-800:]}")

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
        for p in [*parts, *work.glob("part-*.mp4")]:
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
