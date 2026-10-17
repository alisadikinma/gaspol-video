#!/usr/bin/env python3
"""Layout gate for 9:16 short video (GV-23): text must sit inside the measured safe area.

Boxes are pixel ints [x0, y0, x1, y1], end-exclusive, like tools/vidkit/layout.safe_box and
layout.text_box. Subtitle and watermark boxes are measured, not computed: the ASS event is
rendered alone on a black canvas with ffmpeg and the non-black extent is read back.
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.vidkit import ff, layout  # noqa: E402

WATERMARK_RE = re.compile(r"\\an5\\pos\(")
EDGE_ORDER = ("left", "top", "right", "bottom")


class InputError(Exception):
    """Bad input: the tool cannot run (exit 2)."""


def _clock_seconds(text):
    h, m, s = text.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _split_ass(ass_text):
    """(header lines, [(start_s, end_s, line)]) of the Dialogue events."""
    header, events = [], []
    for line in ass_text.splitlines():
        if line.startswith("Dialogue:"):
            fields = line.split(",", 9)
            events.append((_clock_seconds(fields[1]), _clock_seconds(fields[2]), line))
        else:
            header.append(line)
    return header, events


def is_watermark(line):
    return bool(WATERMARK_RE.search(line))


def subtitle_times(ass_text):
    """Midpoint of every subtitle event (watermark excluded), in file order."""
    _, events = _split_ass(ass_text)
    return [round((s + e) / 2, 3) for s, e, line in events if not is_watermark(line)]


def play_res(ass_text):
    """(PlayResX, PlayResY) from an ASS header, or None."""
    x = re.search(r"^PlayResX:\s*(\d+)", ass_text, re.M)
    y = re.search(r"^PlayResY:\s*(\d+)", ass_text, re.M)
    return (int(x.group(1)), int(y.group(1))) if x and y else None


def _render_box(ass_lines, t, size, tmp):
    """Render the given ASS lines alone on black at time t; return the text box or None."""
    w, h = size
    ass_path = os.path.join(tmp, "only.ass")
    Path(ass_path).write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
    png = os.path.join(tmp, "frame.png")
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=black:s={w}x{h}:r=25:d={t + 2:.3f}",
            "-vf", f"ass=filename={_filter_path(ass_path)}", "-ss", f"{t:.3f}", "-frames:v", "1", png])
    return layout.text_box(png)


def _filter_path(path):
    return "'" + str(path).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:") + "'"


def _only(ass_text, want_watermark):
    header, events = _split_ass(ass_text)
    return header + [line for _, _, line in events if is_watermark(line) == want_watermark]


def _size_for(ass_text, size):
    if size is not None:
        return size
    return play_res(ass_text) or (1080, 1920)


def text_boxes_from_ass(ass_path, times=None, size=None):
    """[{"t", "box"}] for the subtitle events (watermark left out).

    `times` defaults to the midpoint of each subtitle event. `box` is None when nothing is
    drawn at that time. `size` is the canvas (w, h); default the ASS PlayRes.
    """
    ass_text = Path(ass_path).read_text(encoding="utf-8")
    if times is None:
        times = subtitle_times(ass_text)
    size = _size_for(ass_text, size)
    lines = _only(ass_text, want_watermark=False)
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for t in times:
            out.append({"t": t, "box": _render_box(lines, t, size, tmp)})
    return out


def watermark_box(ass_path, size=None):
    """Box of the watermark event, measured the same way. None when the ASS has none."""
    ass_text = Path(ass_path).read_text(encoding="utf-8")
    header, events = _split_ass(ass_text)
    marks = [(s, e, line) for s, e, line in events if is_watermark(line)]
    if not marks:
        return None
    s, e, _ = marks[0]
    lines = _only(ass_text, want_watermark=True)
    with tempfile.TemporaryDirectory() as tmp:
        return _render_box(lines, round((s + e) / 2, 3), _size_for(ass_text, size), tmp)


def title_box(thumb_path):
    """Box written by `vidkit title` next to the thumbnail (<thumb>.box.json)."""
    box_file = Path(str(thumb_path) + ".box.json")
    if not box_file.is_file():
        raise InputError(f"{box_file} missing: stamp the title with `python3 -m tools.vidkit title` "
                         "so the gate can read its box")
    try:
        return json.loads(box_file.read_text())["box"]
    except (ValueError, KeyError) as e:
        raise InputError(f"{box_file}: unreadable ({e})") from e


def check_safe(boxes, profile):
    """Findings for boxes that leave the safe area, one per overflowed edge.

    `boxes` is [{"what", "t", "box"}]; a box of None is skipped (nothing drawn). Findings are
    {"what", "t", "box", "overflow_px", "edge"}.
    """
    sx0, sy0, sx1, sy1 = layout.safe_box(profile)
    found = []
    for b in boxes:
        box = b["box"]
        if box is None:
            continue
        over = {"left": sx0 - box[0], "top": sy0 - box[1],
                "right": box[2] - sx1, "bottom": box[3] - sy1}
        for edge in EDGE_ORDER:
            if over[edge] > 0:
                found.append({"what": b["what"], "t": b["t"], "box": box,
                              "overflow_px": over[edge], "edge": edge})
    return found
