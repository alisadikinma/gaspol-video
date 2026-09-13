#!/usr/bin/env python3
"""Paste a REAL logo onto a rendered thumbnail as a layer, pixel-exact.

    python3 tools/composite_logo.py --base plate.png --logo logo.png --out out.png \
        --clear-box 170,455,1105,1465 --center 679,965 --size 940 --glow 255,120,60 --jpg

An image model asked to draw a brand mark redraws it from scratch every roll: petal
counts drift, colours shift, brightness is a lottery. For a fixed asset that is the
wrong tool — this composites the actual logo file, using its own colours (its own alpha
channel, or a white background keyed out for a flat two-colour mark). It never recolours
the logo into a fixed palette and never draws a bloom unless `--glow` is given.

`--clear-box` paints out a region of the base image (a model-drawn logo the composite is
replacing) with a feathered patch before the real logo goes on.

Pillow is imported lazily through `tools/_venv.py`, so this module can be imported by
tests on an interpreter that does not have it (the pure `--clear-box`/`--text-box`
parser it shares, `thumb_scrim.parse_box`, needs no Pillow at all).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import _venv  # noqa: E402
from tools.thumb_scrim import ThumbScrimError, parse_box  # noqa: E402

# (blur radius px, strength) — the multi-radius bloom that reads as a light source.
GLOW_LAYERS = [(28, 0.85), (70, 0.70), (170, 0.55), (320, 0.32)]
JPEG_SIZE_LIMIT = 2 * 1024 * 1024
ALPHA_COVERAGE_WARN = 0.90


class CompositeLogoError(Exception):
    """The logo cannot be composited as asked."""


def _ints(s, n):
    try:
        parts = tuple(int(v) for v in s.split(","))
    except (ValueError, AttributeError) as exc:
        raise CompositeLogoError(f"expected {n} comma-separated ints, got {s!r}") from exc
    if len(parts) != n:
        raise CompositeLogoError(f"expected {n} comma-separated ints, got {s!r}")
    return parts


def load_logo_layer(path, size):
    """Return (rgb, alpha, warn) at `size`x`size`, using the logo file's own colours.

    A file with a real (non-fully-opaque) alpha channel keeps it as-is. A flat, opaque
    logo (presumably on a white background) has its alpha keyed from distance-to-white,
    and its own pixel colours are kept for the fill — never a synthetic recolour. `warn`
    is True when the keyed alpha covers more than 90% of the box, the sign of a logo
    that is not actually on a plain white background.
    """
    Image = _venv.require("PIL.Image")
    ImageChops = _venv.require("PIL.ImageChops")

    src = Image.open(path)
    has_alpha = src.mode in ("RGBA", "LA") and src.getchannel("A").getextrema() != (255, 255)
    rgb = src.convert("RGB")
    warn = False

    if has_alpha:
        alpha = src.getchannel("A")
    else:
        r, g, b = rgb.split()
        darkest = ImageChops.darker(ImageChops.darker(r, g), b)
        # a flat mark's fill bottoms out well short of black; 168 matches the source tool
        alpha = darkest.point(lambda v: max(0, min(255, int((255 - v) * 255 / 168))))
        hist = alpha.histogram()
        total = sum(hist)
        covered = sum(hist[128:])
        if total and covered / total > ALPHA_COVERAGE_WARN:
            warn = True

    box = alpha.getbbox()
    if box:
        rgb = rgb.crop(box)
        alpha = alpha.crop(box)
    rgb = rgb.resize((size, size), Image.LANCZOS)
    alpha = alpha.resize((size, size), Image.LANCZOS)
    return rgb, alpha, warn


def _save(im, out_path, jpg=False):
    out_path = str(out_path)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    im.save(out_path)
    print(f"png  -> {out_path}")
    if jpg:
        jpg_path = os.path.splitext(out_path)[0] + ".jpg"
        im.save(jpg_path, "JPEG", quality=95)
        if os.path.getsize(jpg_path) > JPEG_SIZE_LIMIT:
            im.save(jpg_path, "JPEG", quality=85)
        print(f"jpg  -> {jpg_path} ({im.width}x{im.height}, {os.path.getsize(jpg_path) // 1024}KB)")


def composite_logo(base_path, logo_path, out_path, clear_box=None, feather=34,
                    bg=(4, 5, 6), center=None, size=940, glow=None, jpg=False):
    """Paste `logo_path` onto `base_path`, writing `out_path`. Returns {"out", "warn"}."""
    Image = _venv.require("PIL.Image")
    ImageDraw = _venv.require("PIL.ImageDraw")
    ImageFilter = _venv.require("PIL.ImageFilter")
    ImageChops = _venv.require("PIL.ImageChops")

    base = Image.open(base_path).convert("RGB")
    W, H = base.size

    if clear_box:
        box = clear_box if isinstance(clear_box, tuple) else parse_box(clear_box, W, H)
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rectangle(box, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
        base = Image.composite(Image.new("RGB", (W, H), bg), base, mask)
        default_center = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
    else:
        default_center = (W // 2, H // 2)

    cx, cy = center if center else default_center

    rgb, alpha, warn = load_logo_layer(logo_path, size)
    lw, lh = rgb.size
    ox, oy = cx - lw // 2, cy - lh // 2

    if glow is not None:
        full_alpha = Image.new("L", (W, H), 0)
        full_alpha.paste(alpha, (ox, oy))
        bloom = Image.new("RGB", (W, H), (0, 0, 0))
        for radius, strength in GLOW_LAYERS:
            blurred = full_alpha.filter(ImageFilter.GaussianBlur(radius))
            blurred = blurred.point(lambda v, s=strength: int(v * s))
            layer = Image.new("RGB", (W, H), (0, 0, 0))
            layer.paste(Image.new("RGB", (W, H), glow), (0, 0), blurred)
            bloom = ImageChops.screen(bloom, layer)
        base = ImageChops.screen(base, bloom)

    base.paste(rgb, (ox, oy), alpha)

    _save(base, out_path, jpg=jpg)
    return {"out": str(out_path), "warn": warn}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--logo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--clear-box", help="L,T,R,B — region of the model-drawn logo to paint out")
    ap.add_argument("--feather", type=int, default=34)
    ap.add_argument("--bg", default="4,5,6")
    ap.add_argument("--center", help="X,Y — default: clear-box centre, else image centre")
    ap.add_argument("--size", type=int, default=940)
    glow_group = ap.add_mutually_exclusive_group()
    glow_group.add_argument("--glow", help="R,G,B bloom colour; omit for no bloom")
    glow_group.add_argument("--no-glow", action="store_true")
    ap.add_argument("--jpg", action="store_true")
    args = ap.parse_args(argv)

    try:
        _venv.require("PIL.Image")
    except _venv.DependencyMissing as exc:
        print(f"composite_logo: {exc}", file=sys.stderr)
        return 2

    try:
        bg = _ints(args.bg, 3)
        center = _ints(args.center, 2) if args.center else None
        glow = _ints(args.glow, 3) if (args.glow and not args.no_glow) else None
        result = composite_logo(
            args.base, args.logo, args.out, clear_box=args.clear_box, feather=args.feather,
            bg=bg, center=center, size=args.size, glow=glow, jpg=args.jpg,
        )
        if result["warn"]:
            print(
                "composite_logo: keyed alpha covers >90% of the logo box — the source is "
                "likely not on a plain white background",
                file=sys.stderr,
            )
        return 0
    except (CompositeLogoError, ThumbScrimError) as exc:
        print(f"composite_logo: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
