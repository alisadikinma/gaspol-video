"""Stamp a cover title on a 9:16 image, inside the layout profile's safe area.

ffmpeg drawtext does the drawing. The returned box is measured, not computed: the same
drawtext (box in white) is rendered on a black canvas and read back with layout.text_box.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import ff, layout

FONT_QUERIES = ("Montserrat:bold", "Helvetica Neue:bold", "Arial:bold")
SHRINK_STEP = 0.0025
PAD_PCT = 0.25  # box border as a share of the font size


def resolve_font():
    """Path of the first bold font that fc-match really finds.

    The family must match the query, the style must say Bold, and the face must be index 0
    of its file: drawtext cannot pick another face of a .ttc, so Helvetica Neue Bold (face 1
    of HelveticaNeue.ttc) would silently draw Regular. Such a font is skipped, not used.
    """
    if shutil.which("fc-match") is None:
        raise ValueError("fc-match not found on PATH: cannot resolve a title font")
    tried = []
    for query in FONT_QUERIES:
        proc = subprocess.run(["fc-match", "-f", "%{family}\n%{style}\n%{index}\n%{file}", query],
                              capture_output=True, text=True)
        lines = proc.stdout.strip().split("\n") if proc.returncode == 0 else []
        if len(lines) < 4:
            tried.append(f"{query} -> nothing")
            continue
        family, style, index, path = lines[0], lines[1], lines[2], lines[-1]
        name = query.split(":")[0].lower()
        if name not in family.lower():
            tried.append(f"{query} -> {family}")
        elif "bold" not in style.lower():
            tried.append(f"{query} -> {family} has no bold face")
        elif index != "0":
            tried.append(f"{query} -> bold is face {index} of {path}, drawtext reads face 0 only")
        elif not os.path.isfile(path):
            tried.append(f"{query} -> {path} missing")
        else:
            return path
    raise ValueError("no usable title font from fc-match (" + "; ".join(tried) + ")")


def split_lines(words):
    """Up to two lines, split at the word boundary nearest the middle of the text."""
    if len(words) < 2:
        return [" ".join(words)]
    total = len(" ".join(words))
    best = min(range(1, len(words)),
               key=lambda k: abs(len(" ".join(words[:k])) - total / 2))
    return [" ".join(words[:best]), " ".join(words[best:])]


def _filter(textfiles, font, size, pad, cy, box_color):
    """One drawtext per line, each centred on X with its own box. Boxes of two lines tile
    exactly (line pitch = text height + 2 * pad) and the pair is centred on `cy`."""
    parts = []
    for i, tf in enumerate(textfiles):
        if len(textfiles) == 1:
            y = f"h*{cy}-text_h/2"
        elif i == 0:
            y = f"h*{cy}-text_h-{pad}"
        else:
            y = f"h*{cy}+{pad}"
        parts.append(f"drawtext=fontfile='{font}':textfile='{tf}':fontsize={size}:fontcolor=white"
                     f":x=(w-text_w)/2:y={y}:box=1:boxcolor={box_color}:boxborderw={pad}")
    return ",".join(parts)


def _measure(textfiles, font, size, pad, cy, w, h, tmp):
    probe_png = os.path.join(tmp, "measure.png")
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=black:s={w}x{h}",
            "-vf", _filter(textfiles, font, size, pad, cy, "white"), "-frames:v", "1", probe_png])
    return layout.text_box(probe_png)


def stamp(img, text, out, profile="short-organic", y_pct=None):
    """Write `out` = `img` with `text` on it; return the drawn box [x0, y0, x1, y1].

    Also writes `<out>.box.json` with {"box", "profile", "text", "font"}.
    Raises ValueError for empty text, too many words, a non-9:16 image, a missing font, or a
    line wider than the safe area at the profile's min_font_pct.
    """
    prof = layout.load(profile)
    words = text.upper().split()
    if not words:
        raise ValueError("title text is empty")
    max_words = int(layout.value(prof, "title.max_words"))
    if len(words) > max_words:
        raise ValueError(f"title has {len(words)} words, max_words is {max_words}")
    video = ff.probe(img)["video"]
    if not video:
        raise ValueError(f"{img}: no picture")
    w, h = video["width"], video["height"]
    if abs(w / h - 9 / 16) > 0.01:
        raise ValueError(f"{img} is {w}x{h}, a title needs a 9:16 image")
    font = resolve_font()
    print(f"title font: {font}")
    cy = layout.value(prof, "title.center_y_pct") if y_pct is None else y_pct
    pct = layout.value(prof, "title.font_pct")
    min_pct = layout.value(prof, "title.min_font_pct")
    sx0, sy0, sx1, sy1 = layout.safe_box({**prof, "width": w, "height": h})
    lines = split_lines(words)
    with tempfile.TemporaryDirectory() as tmp:
        textfiles = []
        for i, line in enumerate(lines):
            tf = os.path.join(tmp, f"title{i}.txt")
            Path(tf).write_text(line, encoding="utf-8")
            textfiles.append(tf)
        while True:
            size = round(pct * h)
            pad = round(size * PAD_PCT)
            box = _measure(textfiles, font, size, pad, cy, w, h, tmp)
            if box is None:
                raise ValueError("title rendered nothing: check the font")
            if box[0] >= sx0 and box[2] <= sx1:
                break
            if pct - SHRINK_STEP < min_pct - 1e-9:
                raise ValueError(f"title is {box[2] - box[0]}px wide, centred on the screen it is wider than the "
                                 f"safe area {[sx0, sx1]} at min_font_pct {min_pct}")
            pct = max(pct - SHRINK_STEP, min_pct)
        if box[0] < sx0 or box[2] > sx1 or box[1] < sy0 or box[3] > sy1:
            raise ValueError(f"title box {box} falls outside the safe area {[sx0, sy0, sx1, sy1]}")
        ff.ensure_parent(out)
        ff.run(["ffmpeg", "-y", "-v", "error", "-i", img,
                "-vf", _filter(textfiles, font, size, pad, cy, "black@0.85"),
                "-frames:v", "1", out])
    Path(str(out) + ".box.json").write_text(json.dumps(
        {"box": box, "profile": profile, "text": " ".join(words), "font": font}, indent=1))
    return box
