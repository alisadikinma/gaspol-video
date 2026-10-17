"""Stamp a cover title on a 9:16 image, inside the layout profile's safe area.

ffmpeg drawtext does the drawing. The returned box is measured, not computed: the same
drawtext (box in white) is rendered on a black canvas and read back with layout.text_box.
"""
import itertools
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


def split_lines(words, n=None):
    """Split words into `n` lines (default: up to three, one word minimum per line) with the
    widest line as short as possible; ties go to the more even split."""
    n = min(3, len(words)) if n is None else min(n, len(words))
    if n < 2:
        return [" ".join(words)]
    best, best_key = None, None
    for cuts in itertools.combinations(range(1, len(words)), n - 1):
        edges = (0,) + cuts + (len(words),)
        lines = [" ".join(words[edges[i]:edges[i + 1]]) for i in range(n)]
        lens = [len(x) for x in lines]
        key = (max(lens), sum(x * x for x in lens))
        if best_key is None or key < best_key:
            best, best_key = lines, key
    return best


def _filter(textfiles, font, size, pad, cy, box_color, cx=0.5):
    """One drawtext per line, each centred on X with its own box. Boxes of two lines tile
    exactly (line pitch = text height + 2 * pad) and the pair is centred on `cy`."""
    parts = []
    for i, tf in enumerate(textfiles):
        k = len(textfiles)
        if k == 1:
            y = f"h*{cy}-text_h/2"
        else:
            # lines tile exactly: pitch = text_h + 2*pad, the stack is centred on cy
            y = f"h*{cy}+({i}-{k}/2)*(text_h+2*{pad})+{pad}"
        parts.append(f"drawtext=fontfile='{font}':textfile='{tf}':fontsize={size}:fontcolor=white"
                     f":x=w*{cx}-text_w/2:y={y}:box=1:boxcolor={box_color}:boxborderw={pad}")
    return ",".join(parts)


def _measure(textfiles, font, size, pad, cy, w, h, tmp, cx):
    probe_png = os.path.join(tmp, "measure.png")
    ff.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=black:s={w}x{h}",
            "-vf", _filter(textfiles, font, size, pad, cy, "white", cx), "-frames:v", "1", probe_png])
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
    cx = (sx0 + sx1) / 2 / w
    usable = sx1 - sx0
    n_max = min(3, len(words))
    with tempfile.TemporaryDirectory() as tmp:
        def files(lines):
            out_files = []
            for i, line in enumerate(lines):
                tf = os.path.join(tmp, f"title{len(lines)}-{i}.txt")
                Path(tf).write_text(line, encoding="utf-8")
                out_files.append(tf)
            return out_files

        counts = [n for n in (2, 3) if n <= n_max] or [1]
        layouts = {n: split_lines(words, n) for n in counts}
        tfs = {n: files(layouts[n]) for n in counts}
        chosen, size, pad, box = None, None, None, None
        widest_at_min = None
        while chosen is None:
            size = round(pct * h)
            pad = round(size * PAD_PCT)
            for n in counts:
                box = _measure(tfs[n], font, size, pad, cy, w, h, tmp, cx)
                if box is None:
                    raise ValueError("title rendered nothing: check the font")
                if box[0] >= sx0 and box[2] <= sx1:
                    chosen = n
                    break
                if pct <= min_pct + 1e-9:
                    wd = box[2] - box[0]
                    widest_at_min = wd if widest_at_min is None else min(widest_at_min, wd)
            if chosen is not None:
                break
            if pct <= min_pct + 1e-9:
                raise ValueError(f"title does not fit the safe area: usable width {usable} px, widest line "
                                 f"{widest_at_min} px at min font ({min_pct} of the height); "
                                 f"shorten the longest word")
            pct = max(pct - SHRINK_STEP, min_pct)
        lines = layouts[chosen]
        textfiles = tfs[chosen]
        if box[0] < sx0 or box[2] > sx1 or box[1] < sy0 or box[3] > sy1:
            raise ValueError(f"title box {box} falls outside the safe area {[sx0, sy0, sx1, sy1]}")
        ff.ensure_parent(out)
        ff.run(["ffmpeg", "-y", "-v", "error", "-i", img,
                "-vf", _filter(textfiles, font, size, pad, cy, "black@0.85", cx),
                "-frames:v", "1", out])
    Path(str(out) + ".box.json").write_text(json.dumps(
        {"box": box, "profile": profile, "text": " ".join(words), "font": font, "lines": lines,
         "source": str(Path(img).resolve())}, indent=1))
    return box
