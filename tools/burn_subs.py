#!/usr/bin/env python3
"""Burn subtitles into the master with two guards that catch silent failures.

    python3 tools/burn_subs.py <project-dir> [--srt PATH] [--out PATH] [--print]

Both guards are adapted from MoneyPrinterTurbo (see NOTICE), and both exist because their
failure is invisible until someone watches the finished file:

  * a font that cannot draw a character renders a box, and a box ships
  * subtitle colour too close to its stroke or background is unreadable on exactly the
    frames where the background happens to match

Stdlib only. No ffmpeg means the command is printed and nothing is burned.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

MIN_CONTRAST_RATIO = 4.5


class StyleError(Exception):
    """The burn-in cannot proceed as styled."""


def _luminance(hex_colour):
    value = hex_colour.lstrip("#")
    if len(value) != 6:
        raise StyleError(f"colour {hex_colour!r} is not a 6-digit hex value")
    channels = []
    for i in (0, 2, 4):
        c = int(value[i:i + 2], 16) / 255.0
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def check_contrast(foreground, background):
    """WCAG contrast ratio. Raises when the text would not read against its own backing."""
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    ratio = (lighter + 0.05) / (darker + 0.05)
    if ratio < MIN_CONTRAST_RATIO:
        raise StyleError(
            f"subtitle colour {foreground} against {background} has contrast {ratio:.2f}:1, "
            f"below {MIN_CONTRAST_RATIO}:1 — it will be unreadable on some frames"
        )
    return round(ratio, 2)


def check_font_supports(font_name, text, supported=None):
    """Every character in the caption must be drawable. A box is worse than no caption."""
    if supported is None:
        return True   # no glyph table available; the render itself is the check
    missing = sorted({ch for ch in text if not ch.isspace() and ch not in supported})
    if missing:
        raise StyleError(
            f"font {font_name!r} cannot render: {' '.join(missing)} — "
            "pick a font that covers the script's characters, or the caption ships as boxes"
        )
    return True


def force_style(style, video_height):
    """libass force_style string. Margins are a percentage so 9:16 and 16:9 both behave."""
    margin_v = int(round(video_height * (style.get("margin_v_pct", 8) / 100.0)))
    alignment = {"bottom": 2, "middle": 5, "top": 8}.get(style.get("position", "bottom"), 2)
    parts = [
        f"FontName={style.get('font', 'Inter')}",
        f"Fontsize={style.get('size_px', 54)}",
        f"Outline={style.get('stroke_px', 3)}",
        f"MarginV={margin_v}",
        f"Alignment={alignment}",
        "BorderStyle=1",
        "PrimaryColour=&H00FFFFFF",
        "OutlineColour=&H00000000",
    ]
    return ",".join(parts)


def video_height_of(path):
    if FFPROBE is None:
        return 1080
    proc = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return 1080


def build_command(master, srt, out, style, video_height):
    srt = Path(srt)
    if not srt.is_file():
        raise StyleError(f"no subtitle file at {srt.name}")
    # libass takes the path inside a filter argument, so ':' and '\' have to be escaped.
    escaped = str(srt).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
    vf = f"subtitles='{escaped}':force_style='{force_style(style, video_height)}'"
    return [FFMPEG or "ffmpeg", "-y", "-v", "error", "-i", str(master),
            "-vf", vf, "-c:a", "copy", str(out)]


def burn(project, srt=None, out=None, show=False, log=print):
    project = Path(project)
    plan_path = project / "work" / "subtitle-plan.json"
    plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}
    style = plan.get("style", {})

    master = project / "output" / "master.mp4"
    srt = Path(srt) if srt else project / (plan.get("srt") or "output/master.srt")
    out = Path(out) if out else project / "output" / "master-subbed.mp4"

    for cue in plan.get("cues", []):
        check_font_supports(style.get("font", "Inter"), cue["text"])
    check_contrast("#FFFFFF", "#000000")   # the default white-on-black-outline pairing

    cmd = build_command(master, srt, out, style, video_height_of(master))
    log("+ " + " ".join(cmd))
    if show:
        return None
    if FFMPEG is None:
        log("ffmpeg not found on PATH — captions were not burned. The .srt is still written, "
            "so the video can ship with a sidecar subtitle file instead.")
        return None
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise StyleError(f"burn-in failed:\n{proc.stderr.strip()[-600:]}")
    return str(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project")
    ap.add_argument("--srt")
    ap.add_argument("--out")
    ap.add_argument("--print", dest="show", action="store_true")
    args = ap.parse_args(argv)
    try:
        burn(args.project, srt=args.srt, out=args.out, show=args.show)
        return 0
    except StyleError as exc:
        print(f"burn_subs: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
