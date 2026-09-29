#!/usr/bin/env python3
"""Contact sheets and a verdict sheet for visual QA of rendered Phase 5 clips.

    python3 tools/qa_frames.py <project> [--scenes 5,6] [--clip clips/scene-05.mp4 ...]
    python3 tools/qa_frames.py <project> --check [--scenes 5,6] [--clip ...]

For each rendered clip: five frames (start, 25%, 50%, 75%, last frame) tiled into
`.tmp/qa-scene-NN.jpg`, and one section per scene in `work/visual-qa.md` carrying the
scene's PLAUSIBILITY block and a seven-row verdict table for Claude to fill after looking
at the sheet. Re-running keeps verdicts for a clip whose bytes did not change.

`--check` is the V15 gate: it reads only the Verdict cells of `work/visual-qa.md`, extracts
nothing and writes nothing. Exit 1 when a clip has no section, a cell is empty or malformed
or `FAIL:`, or the section was judged against different bytes; `UNSURE:` is a note for a human.

Stdlib only. Needs ffmpeg and ffprobe.
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import renders  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

DEFAULT_FPS = 25.0

QUESTIONS = ["MECHANISM", "COUNT", "FLOW", "FACING", "PAIR", "PEOPLE", "OVERLAY SURFACE"]
MISSING_BLOCK = ("PLAUSIBILITY block not found in video-prompts.md — "
                 "judge against the scene description")
CHANGED_NOTE = "- note: clip changed since last judged — verdicts cleared"
SHEET_HEADER = ("# Visual QA\n\n"
                "Look at each scene's contact sheet, then fill every Verdict cell: "
                "`PASS`, `FAIL: <what is visible>`, or `UNSURE: <why the frames cannot tell>`.\n\n")


def frame_times(duration_s, fps):
    """Five sample points: start, 25%, 50%, 75%, and the last frame (one frame before the end)."""
    if not fps or fps <= 0:
        fps = DEFAULT_FPS
    frame = 1.0 / fps
    if not duration_s or duration_s < frame:
        raise ValueError(f"clip is shorter than one frame ({duration_s}s)")
    last = max(0.0, duration_s - frame)
    return [round(t, 2) for t in
            (0.0, duration_s * 0.25, duration_s * 0.5, duration_s * 0.75, last)]


_HEADING_RE = re.compile(r"^(#{1,6})\s")
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s")


def find_plausibility(markdown, scene):
    """The scene's `PLAUSIBILITY:` block from video-prompts.md, verbatim, or None.

    The scene's section runs from its `## / ### / ####  Scene N` heading to the next heading
    of the same or higher level. The block is the `PLAUSIBILITY:` line plus the numbered
    lines that follow it; it ends at the first line that is not numbered."""
    heading = re.compile(r"^#{2,4}\s+Scene\s+0*%d\b" % int(scene))
    lines = markdown.splitlines()
    start = level = None
    for i, line in enumerate(lines):
        if heading.match(line):
            start, level = i, len(_HEADING_RE.match(line).group(1))
            break
    if start is None:
        return None
    section = []
    for line in lines[start + 1:]:
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) <= level:
            break
        section.append(line)
    for i, line in enumerate(section):
        if line.strip() == "PLAUSIBILITY:":
            block = [line.strip()]
            for follow in section[i + 1:]:
                if not _NUMBERED_RE.match(follow):
                    break
                block.append(follow.rstrip())
            return "\n".join(block)
    return None


def render_section(scene, clip, sha, sheet, times, plausibility, verdicts=None, note=None):
    """One `## Scene NN` section of work/visual-qa.md. `verdicts` is a list of seven cell
    texts (kept from an earlier judgement) or None for empty cells."""
    verdicts = verdicts or [""] * len(QUESTIONS)
    stamps = ", ".join("%.2fs" % t for t in times)
    lines = ["## Scene %02d" % int(scene), "",
             "- clip: %s" % clip,
             "- clip_sha256: %s" % sha,
             "- sheet: %s — frames at %s" % (sheet, stamps)]
    if note:
        lines.append(note)
    lines += ["", plausibility or MISSING_BLOCK, "",
              "| # | Question | Verdict |", "|---|---|---|"]
    for i, (question, verdict) in enumerate(zip(QUESTIONS, verdicts), 1):
        lines.append("| %d | %s | %s |" % (i, question, verdict) if verdict
                     else "| %d | %s | |" % (i, question))
    return "\n".join(lines) + "\n"


_SECTION_SPLIT_RE = re.compile(r"(?m)^(?=## Scene \d+\s*$)")
_SCENE_RE = re.compile(r"## Scene (\d+)")
_SHA_RE = re.compile(r"(?m)^- clip_sha256: (\S+)")
_ROW_RE = re.compile(r"^\|\s*(\d)\s*\|[^|]*\|(.*)\|\s*$")


def _parse_sections(text):
    """{scene number: (section text, clip_sha256 or None, seven verdict cells)}"""
    found = {}
    for chunk in _SECTION_SPLIT_RE.split(text):
        m = _SCENE_RE.match(chunk)
        if not m:
            continue
        sha = _SHA_RE.search(chunk)
        verdicts = [""] * len(QUESTIONS)
        for line in chunk.splitlines():
            row = _ROW_RE.match(line)
            if row and 1 <= int(row.group(1)) <= len(QUESTIONS):
                verdicts[int(row.group(1)) - 1] = row.group(2).strip()
        found[int(m.group(1))] = (chunk.rstrip("\n") + "\n", sha.group(1) if sha else None, verdicts)
    return found


def merge_sheet(existing_text, sections):
    """Fold freshly rendered `sections` (kwargs dicts for render_section) into an existing
    sheet by scene number. Same clip_sha256 keeps the judged verdicts; a different one clears
    them and says so. Scenes not in `sections` are left exactly as they were."""
    old = _parse_sections(existing_text)
    merged = {n: chunk for n, (chunk, _sha, _v) in old.items()}
    for kwargs in sections:
        scene = int(kwargs["scene"])
        prev = old.get(scene)
        if prev and prev[1] == kwargs["sha"]:
            merged[scene] = render_section(verdicts=prev[2], **kwargs)
        elif prev and prev[1] is not None:
            merged[scene] = render_section(note=CHANGED_NOTE, **kwargs)
        else:
            merged[scene] = render_section(**kwargs)
    return SHEET_HEADER + "\n".join(merged[n] for n in sorted(merged))


def _scene_of(name):
    m = re.search(r"scene-(\d+)", str(name))
    return int(m.group(1)) if m else None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def probe(clip):
    """(duration_s, fps) of the first video stream; duration None when unknown."""
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration,r_frame_rate:format=duration",
         "-of", "default=nw=1", str(clip)], capture_output=True, text=True)
    duration = fps = None
    for line in proc.stdout.splitlines():
        key, _, value = line.partition("=")
        try:
            if key == "r_frame_rate" and "/" in value:
                num, den = value.split("/")
                fps = float(num) / float(den)
            elif key == "duration" and duration is None:
                duration = float(value)
        except (ValueError, ZeroDivisionError):
            continue
    return duration, fps or DEFAULT_FPS


def _run(args):
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[-400:] or "ffmpeg failed")


def make_sheet(clip, project, scene, times):
    """Extract one frame per timestamp, tile them into .tmp/qa-scene-NN.jpg, delete the frames."""
    tmp = project / ".tmp"
    tmp.mkdir(exist_ok=True)
    frames = [tmp / ("qa-scene-%02d-%d.jpg" % (scene, k)) for k in range(len(times))]
    sheet = tmp / ("qa-scene-%02d.jpg" % scene)
    try:
        for t, frame in zip(times, frames):
            _run([FFMPEG, "-v", "error", "-y", "-ss", str(t), "-i", str(clip),
                  "-frames:v", "1", "-vf", "scale=480:-2", str(frame)])
        args = [FFMPEG, "-v", "error", "-y"]
        for frame in frames:
            args += ["-i", str(frame)]
        args += ["-filter_complex", "hstack=inputs=%d" % len(frames), str(sheet)]
        _run(args)
    finally:
        for frame in frames:
            frame.unlink(missing_ok=True)
    return sheet


def _collect(project, ledger, clip_args, wanted):
    """{scene: clip path relative to the project}. Ledger first, --clip wins on a duplicate."""
    found = {}
    for entry in ledger.get("renders", []):
        if str(entry.get("phase")) == "5" and entry.get("status") == "done" and entry.get("file"):
            scene = entry.get("scene")
            scene = scene if isinstance(scene, int) else _scene_of(entry["file"])
            if scene is not None:
                found[scene] = entry["file"]
    for clip in clip_args:
        scene = _scene_of(clip)
        if scene is None:
            raise ValueError("--clip %s has no scene number (expected scene-NN in the name)" % clip)
        found[scene] = clip
    if wanted is not None:
        found = {n: c for n, c in found.items() if n in wanted}
    return found


_VERDICT_RE = re.compile(r"^(PASS|FAIL:\s*(.*)|UNSURE:\s*(.*))$", re.DOTALL)


def check(project, clips):
    """V15 over `work/visual-qa.md`. Returns (problems, notes) as printable lines.

    Only the Verdict cells of each scene's table are read, never the surrounding prose."""
    qa_path = project / "work" / "visual-qa.md"
    text = qa_path.read_text(encoding="utf-8") if qa_path.exists() else ""
    sections = _parse_sections(text)
    problems, notes = [], []
    for scene in sorted(clips):
        label = "scene %02d" % scene
        if scene not in sections:
            problems.append("V15 FAIL %s: no section in work/visual-qa.md" % label)
            continue
        _chunk, sha, verdicts = sections[scene]
        clip = project / clips[scene]
        if not clip.is_file():
            problems.append("V15 FAIL %s: %s is missing on disk" % (label, clips[scene]))
        elif sha != _sha256(clip):
            problems.append("V15 FAIL %s: verdicts were judged against a different clip "
                            "(clip_sha256 does not match %s)" % (label, clips[scene]))
        for k, cell in enumerate(verdicts, 1):
            m = _VERDICT_RE.match(cell)
            if not cell:
                problems.append("V15 FAIL %s q%d: %s has no verdict" % (label, k, QUESTIONS[k - 1]))
            elif not m:
                problems.append("V15 FAIL %s q%d: verdict must start with PASS, FAIL: or "
                                "UNSURE: (got %r)" % (label, k, cell))
            elif m.group(1).startswith("FAIL"):
                problems.append("V15 FAIL %s q%d: %s" % (label, k, m.group(2) or QUESTIONS[k - 1]))
            elif m.group(1).startswith("UNSURE"):
                notes.append("V15 NOTE %s q%d: %s \u2014 needs a human look"
                             % (label, k, m.group(3) or QUESTIONS[k - 1]))
    return problems, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--scenes", help="comma-separated scene numbers to keep, e.g. 5,6")
    ap.add_argument("--clip", action="append", default=[],
                    help="a hand-rendered clip relative to the project (repeatable)")
    ap.add_argument("--check", action="store_true",
                    help="V15 gate: verify work/visual-qa.md is fully and honestly judged")
    args = ap.parse_args(argv)

    project = Path(args.project)
    try:
        wanted = ({int(x) for x in args.scenes.split(",") if x.strip()}
                  if args.scenes else None)
    except ValueError:
        print("qa_frames: --scenes must be comma-separated numbers, e.g. 5,6", file=sys.stderr)
        return 2
    try:
        clips = _collect(project, renders.load(project), args.clip, wanted)
    except renders.RenderLedgerError as exc:
        print("qa_frames: %s" % exc, file=sys.stderr)
        return 2
    except ValueError as exc:
        print("qa_frames: %s" % exc, file=sys.stderr)
        return 2
    if not clips:
        print("qa_frames: no rendered clips found (renders.json has no done phase-5 entry; "
              "pass --clip for hand-rendered clips)", file=sys.stderr)
        return 2
    if args.check:
        problems, notes = check(project, clips)
        for line in problems + notes:
            print(line)
        return 1 if problems else 0
    if not (FFMPEG and FFPROBE):
        print("qa_frames: ffmpeg and ffprobe are required and were not found on PATH",
              file=sys.stderr)
        return 2

    prompts_path = project / "video-prompts.md"
    prompts = prompts_path.read_text(encoding="utf-8") if prompts_path.exists() else ""

    sections = []
    failed = False
    for scene in sorted(clips):
        rel = clips[scene]
        clip = project / rel
        if not clip.is_file():
            print("scene %02d  skipped: %s is missing on disk" % (scene, rel))
            continue
        duration, fps = probe(clip)
        try:
            times = frame_times(duration, fps)
        except ValueError as exc:
            print("scene %02d  skipped: %s" % (scene, exc))
            continue
        try:
            sheet = make_sheet(clip, project, scene, times)
        except RuntimeError as exc:
            print("scene %02d  failed: %s" % (scene, exc), file=sys.stderr)
            failed = True
            continue
        sheet_rel = sheet.relative_to(project).as_posix()
        print("scene %02d  %.2fs  sheet %s" % (scene, duration, sheet_rel))
        sections.append(dict(scene=scene, clip=rel, sha=_sha256(clip), sheet=sheet_rel,
                             times=times, plausibility=find_plausibility(prompts, scene)))

    if not sections:
        print("qa_frames: no clip could be processed", file=sys.stderr)
        return 2

    qa_path = project / "work" / "visual-qa.md"
    existing = qa_path.read_text(encoding="utf-8") if qa_path.exists() else ""
    qa_path.parent.mkdir(exist_ok=True)
    tmp_path = qa_path.with_name(qa_path.name + ".tmp")
    tmp_path.write_text(merge_sheet(existing, sections), encoding="utf-8")
    os.replace(tmp_path, qa_path)
    print("wrote %s" % qa_path.relative_to(project).as_posix())
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
