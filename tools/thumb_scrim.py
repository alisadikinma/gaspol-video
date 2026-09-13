#!/usr/bin/env python3
"""Deepen the dark scrim behind a thumbnail headline, deterministically, in post.

    python3 tools/thumb_scrim.py --in D4.png --out D4.png --fade-y 620 --strength 0.55
    python3 tools/thumb_scrim.py --in D4.png --out D4.png \
        --target-contrast 4.5 --text-box 40,40,900,220

A scrim is a graphic overlay, not photography, and an image model treats it as a
suggestion — the rendered scrim can plateau well short of what a headline needs against
it. This darkens the ground deterministically, either to a fixed `--strength` or, with
`--target-contrast` and `--text-box`, by searching strength upward until the WCAG contrast
between the headline fill and its ground reaches the target.

The headline itself is protected by default: saturated fill pixels near `--hue` are
excluded from the darkening, so only the ground behind them goes down. `--protect none`
darkens everything, headline included.

Pillow is imported lazily and only inside the functions that need it (`tools/_venv.py`),
so `wcag_contrast` and `parse_box` stay importable — and unit-testable — on a stdlib-only
interpreter.
"""

import argparse
import colorsys
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import _venv  # noqa: E402

DEFAULT_STRENGTH = 0.55
DEFAULT_HUE = 120.0
STRENGTH_STEP = 0.05
MAX_STRENGTH = 0.95
JPEG_SIZE_LIMIT = 2 * 1024 * 1024
MIN_JPG_W, MIN_JPG_H = 1280, 720


class ThumbScrimError(Exception):
    """The scrim, or the requested contrast target, cannot be applied as asked."""


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    r, g, b = (srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag_contrast(rgb1, rgb2):
    """The standard WCAG contrast ratio, 1.0 (identical) to 21.0 (white vs black)."""
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def open_image_or_raise(Image, path):
    """`Image.open(path)`, wrapping the ways a bad path or a bad file surface so callers get
    one clear ThumbScrimError instead of a raw traceback from PIL or the filesystem."""
    try:
        im = Image.open(path)
        im.load()
        return im
    except FileNotFoundError as exc:
        raise ThumbScrimError(f"input image not found: {path}") from exc
    except Image.UnidentifiedImageError as exc:
        raise ThumbScrimError(f"input image is not a readable image file: {path}") from exc
    except OSError as exc:
        raise ThumbScrimError(f"input image unreadable: {path} ({exc})") from exc


def require_min_jpg_size(w, h):
    """YouTube's own stated minimum for an uploaded thumbnail. A smaller source is refused
    up front rather than silently shipped undersized."""
    if w < MIN_JPG_W or h < MIN_JPG_H:
        raise ThumbScrimError(
            f"--jpg needs at least {MIN_JPG_W}x{MIN_JPG_H} (YouTube's thumbnail minimum), "
            f"got {w}x{h}"
        )


def parse_box(s, w, h):
    """Parse an "L,T,R,B" box string, rejecting anything outside a `w`x`h` image."""
    try:
        left, top, right, bottom = (int(v) for v in s.split(","))
    except (ValueError, AttributeError) as exc:
        raise ThumbScrimError(f"box must be L,T,R,B (got {s!r})") from exc
    if not (0 <= left < right <= w and 0 <= top < bottom <= h):
        raise ThumbScrimError(f"box {s} outside {w}x{h}")
    return left, top, right, bottom


def hue_distance(a, b):
    """Shortest distance between two hues on the 0..360 wheel — 355 and 0 are 5 apart,
    not 355; a plain abs() difference fails to protect a headline whose hue sits just
    across the wrap-around boundary from `--hue`."""
    d = abs(a - b) % 360
    return min(d, 360 - d)


def is_headline_pixel(r, g, b, hue):
    """True for a saturated, bright pixel near `hue` degrees — the letters, not the ground."""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return s > 0.45 and v > 0.45 and hue_distance(h * 360, hue) < 40


def _sample_colors(im, box, predicate=None):
    left, top, right, bottom = box
    px = im.convert("RGB").load()
    colors = []
    for y in range(top, bottom):
        for x in range(left, right):
            r, g, b = px[x, y]
            if predicate is None or predicate(r, g, b):
                colors.append((r, g, b))
    return colors


def _median_rgb(colors):
    if not colors:
        return None
    rs = sorted(c[0] for c in colors)
    gs = sorted(c[1] for c in colors)
    bs = sorted(c[2] for c in colors)
    mid = len(colors) // 2
    return (rs[mid], gs[mid], bs[mid])


def apply_scrim(im, strength=DEFAULT_STRENGTH, fade_y=None, x_hold=None, x_fade=None,
                 protect="hue", hue=DEFAULT_HUE):
    """Return a new RGB image with the scrim applied. `im` is left untouched."""
    Image = _venv.require("PIL.Image")
    ImageFilter = _venv.require("PIL.ImageFilter")

    im = im.convert("RGB")
    W, H = im.size
    fade_y = int(fade_y) if fade_y is not None else int(H * 0.40)
    x_hold = int(x_hold) if x_hold is not None else int(W * 0.55)
    x_fade = int(x_fade) if x_fade is not None else int(W * 0.75)

    alpha = Image.new("L", (W, H), 0)
    ap = alpha.load()
    col = []
    for x in range(W):
        if x <= x_hold:
            col.append(1.0)
        elif x >= x_fade:
            col.append(0.0)
        else:
            col.append(1.0 - smoothstep((x - x_hold) / max(1, x_fade - x_hold)))
    for y in range(H):
        v = 0.0 if y >= fade_y else 1.0 - smoothstep(y / max(1, fade_y))
        if v <= 0:
            continue
        for x in range(W):
            a = v * col[x]
            if a > 0:
                ap[x, y] = int(a * 255)

    if protect != "none":
        keep = Image.new("L", (W, H), 0)
        kp = keep.load()
        sp = im.load()
        for y in range(0, min(fade_y, H)):
            for x in range(0, min(x_fade, W)):
                r, g, b = sp[x, y]
                if is_headline_pixel(r, g, b, hue):
                    kp[x, y] = 255
        keep = keep.filter(ImageFilter.MaxFilter(5))
        keep = keep.filter(ImageFilter.GaussianBlur(2))
        kp = keep.load()
        for y in range(0, min(fade_y, H)):
            for x in range(0, min(x_fade, W)):
                if kp[x, y]:
                    ap[x, y] = int(ap[x, y] * (1 - kp[x, y] / 255))

    alpha = alpha.filter(ImageFilter.GaussianBlur(3))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    scaled = alpha.point(lambda v: int(v * strength))
    return Image.composite(dark, im, scaled)


def fit_to_target_contrast(im, box, target_contrast, hue=DEFAULT_HUE, protect="hue",
                           fade_y=None, x_hold=None, x_fade=None):
    """Raise `strength` in `STRENGTH_STEP` steps until the headline/ground contrast inside
    `box` reaches `target_contrast`. Returns (out_image, strength, contrast). Raises
    ThumbScrimError when `MAX_STRENGTH` is not enough."""
    headline_colors = _sample_colors(
        im, box, predicate=lambda r, g, b: is_headline_pixel(r, g, b, hue)
    )
    headline = _median_rgb(headline_colors) or (255, 255, 255)

    # Start the search from 0.0, not DEFAULT_STRENGTH: contrast only rises with strength,
    # so starting high never fails to reach the target, it just skips every lower strength
    # that would already have worked and over-darkens the thumbnail for no reason.
    strength = 0.0
    out = None
    contrast = 0.0
    while strength <= MAX_STRENGTH + 1e-9:
        out = apply_scrim(im, strength=strength, fade_y=fade_y, x_hold=x_hold, x_fade=x_fade,
                          protect=protect, hue=hue)
        ground_colors = _sample_colors(
            out, box, predicate=lambda r, g, b: not is_headline_pixel(r, g, b, hue)
        )
        ground = _median_rgb(ground_colors) or (0, 0, 0)
        contrast = wcag_contrast(headline, ground)
        if contrast >= target_contrast:
            return out, round(strength, 2), contrast
        strength = round(strength + STRENGTH_STEP, 2)

    raise ThumbScrimError(
        f"target contrast {target_contrast} not reachable "
        f"(best {contrast:.2f} at strength {MAX_STRENGTH})"
    )


def _save(im, out_path, jpg=False):
    out_path = str(out_path)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    im.convert("RGB").save(out_path)
    print(f"png  -> {out_path}")
    if jpg:
        jpg_path = os.path.splitext(out_path)[0] + ".jpg"
        im.convert("RGB").save(jpg_path, "JPEG", quality=95)
        if os.path.getsize(jpg_path) > JPEG_SIZE_LIMIT:
            im.convert("RGB").save(jpg_path, "JPEG", quality=85)
        print(f"jpg  -> {jpg_path} ({im.width}x{im.height}, {os.path.getsize(jpg_path) // 1024}KB)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--strength", type=float, default=DEFAULT_STRENGTH)
    ap.add_argument("--fade-y", type=int)
    ap.add_argument("--x-hold", type=int)
    ap.add_argument("--x-fade", type=int)
    ap.add_argument("--hue", type=float, default=DEFAULT_HUE)
    ap.add_argument("--protect", default="hue", choices=("hue", "none"))
    ap.add_argument("--target-contrast", type=float)
    ap.add_argument("--text-box", help="L,T,R,B — required with --target-contrast")
    ap.add_argument("--jpg", action="store_true")
    args = ap.parse_args(argv)

    try:
        Image = _venv.require("PIL.Image")
    except _venv.DependencyMissing as exc:
        print(f"thumb_scrim: {exc}", file=sys.stderr)
        return 2

    try:
        im = open_image_or_raise(Image, args.src)
        w, h = im.size
        if args.jpg:
            require_min_jpg_size(w, h)
        if args.target_contrast is not None:
            if not args.text_box:
                raise ThumbScrimError("--target-contrast needs --text-box L,T,R,B")
            box = parse_box(args.text_box, w, h)
            out_im, strength, contrast = fit_to_target_contrast(
                im, box, args.target_contrast, hue=args.hue, protect=args.protect,
                fade_y=args.fade_y, x_hold=args.x_hold, x_fade=args.x_fade,
            )
            print(f"reached contrast {contrast:.2f} at strength {strength}")
        else:
            out_im = apply_scrim(
                im, strength=args.strength, fade_y=args.fade_y, x_hold=args.x_hold,
                x_fade=args.x_fade, protect=args.protect, hue=args.hue,
            )
        _save(out_im, args.out, jpg=args.jpg)
        return 0
    except ThumbScrimError as exc:
        print(f"thumb_scrim: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
