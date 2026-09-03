#!/usr/bin/env python3
"""Inventory the generated clips in a project and write work/clip-manifest.json.

The first thing Phase 6 does. Everything downstream assumes it knows how long each
clip is and whether it carries sound; guessing either produces a master that drifts.

    python3 tools/probe_clips.py <project-dir> [--out PATH] [--print]

Stdlib only. Degrades loudly: no ffprobe means a manifest of problems plus the exact
command to run elsewhere, never a crash and never a silent empty result.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FFPROBE = shutil.which("ffprobe")

# scene-03.mp4 -> scene 3, ext 0 ; scene-03-ext1.mp4 -> scene 3, ext 1
CLIP_NAME = re.compile(r"^scene-(\d+)(?:-ext(\d+))?$", re.IGNORECASE)

VIDEO_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm")

# One frame at 25fps. Equality, not a budget that grows with the timeline: drift
# accumulates, so a tolerance that scales hides the fault it is meant to catch.
AV_TOLERANCE_S = 0.04


def _ffprobe_json(path):
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "ffprobe failed")
    return json.loads(proc.stdout)


def _stream_duration(stream, container):
    for value in (stream.get("duration"), container.get("format", {}).get("duration")):
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            continue
    return None


def _fps(stream):
    raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or ""
    if "/" in raw:
        num, den = raw.split("/", 1)
        try:
            num, den = float(num), float(den)
            if den:
                return round(num / den, 3)
        except ValueError:
            pass
    return None


def probe_clip(path):
    """One clip -> its entry, plus a list of problems found in it."""
    entry = {
        "file": None, "scene": None, "ext": 0, "duration_s": None, "fps": None,
        "width": None, "height": None, "has_audio": False, "audio_duration_s": None,
    }
    problems = []
    path = Path(path)
    entry["file"] = f"clips/{path.name}"

    match = CLIP_NAME.match(path.stem)
    if match:
        entry["scene"] = int(match.group(1))
        entry["ext"] = int(match.group(2) or 0)
    else:
        problems.append(
            f"{path.name}: filename does not match scene-NN[-extK] — cannot map it to a scene"
        )

    try:
        data = _ffprobe_json(path)
    except Exception as exc:  # ffprobe present but this file is unreadable
        problems.append(f"{path.name}: unreadable ({exc})")
        return entry, problems

    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)

    if video is None:
        problems.append(f"{path.name}: no video stream")
        return entry, problems

    entry["duration_s"] = _stream_duration(video, data)
    entry["fps"] = _fps(video)
    entry["width"] = video.get("width")
    entry["height"] = video.get("height")

    if audio is None:
        problems.append(f"{path.name}: no audio stream — the clip is silent")
        return entry, problems

    entry["has_audio"] = True
    entry["audio_duration_s"] = _stream_duration(audio, data)

    v, a = entry["duration_s"], entry["audio_duration_s"]
    if v is not None and a is not None and abs(v - a) > AV_TOLERANCE_S:
        problems.append(f"{path.name}: v:0 {v:.2f}s != a:0 {a:.2f}s (tolerance {AV_TOLERANCE_S}s)")

    return entry, problems


def build_manifest(project_dir):
    project = Path(project_dir)
    clips_dir = project / "clips"
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": str(project),
        "clips": [],
        "problems": [],
    }

    if FFPROBE is None:
        manifest["problems"].append(
            "ffprobe not found on PATH — clip durations are unknown. "
            "Install ffmpeg, or run this elsewhere: "
            "ffprobe -v error -show_streams -show_format -of json clips/scene-01.mp4"
        )
        return manifest

    if not clips_dir.is_dir():
        manifest["problems"].append(f"no clips folder at {clips_dir}")
        return manifest

    files = sorted(p for p in clips_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES)
    if not files:
        manifest["problems"].append(f"no clips found in {clips_dir}")
        return manifest

    for path in files:
        entry, problems = probe_clip(path)
        manifest["clips"].append(entry)
        manifest["problems"].extend(problems)

    return manifest


def write_manifest(project_dir, out=None):
    project = Path(project_dir)
    out = Path(out) if out else project / "work" / "clip-manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_manifest(project), indent=2) + "\n")
    return out


def format_sheet(manifest):
    lines = [f"{len(manifest['clips'])} clip(s)"]
    for c in manifest["clips"]:
        scene = f"scene {c['scene']:02d}" if c["scene"] is not None else "scene ??"
        ext = f" ext{c['ext']}" if c["ext"] else ""
        dur = f"{c['duration_s']:.2f}s" if c["duration_s"] is not None else "?s"
        res = f"{c['width']}x{c['height']}" if c["width"] else "?"
        snd = "audio" if c["has_audio"] else "SILENT"
        lines.append(f"  {scene}{ext}  {dur:>8}  {res:>10}  {snd:>6}  {c['file']}")
    if manifest["problems"]:
        lines.append(f"{len(manifest['problems'])} problem(s):")
        lines += [f"  ! {p}" for p in manifest["problems"]]
    else:
        lines.append("no problems")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project", help="project output folder (the one holding clips/)")
    ap.add_argument("--out", help="manifest path (default: <project>/work/clip-manifest.json)")
    ap.add_argument("--print", dest="show", action="store_true", help="print the sheet, write nothing")
    args = ap.parse_args(argv)

    manifest = build_manifest(args.project)
    if args.show:
        print(format_sheet(manifest))
    else:
        out = write_manifest(args.project, args.out)
        print(format_sheet(manifest))
        print(f"\nwrote {out}")

    # Problems are findings, not failures: the skill decides what to do about them.
    return 0


if __name__ == "__main__":
    sys.exit(main())
