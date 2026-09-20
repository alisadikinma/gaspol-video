#!/usr/bin/env python3
"""Track the FOUR CORNERS of a screen in a clip, so a Remotion panel lands on the glass.

    python3 tools/track_screen.py clips/scene-15.mp4 work/track-scene-15.json \
        --seed 640,520 --from 0.0 --to 6.0 --step 0.5 --threshold 165 --qa .tmp/qa-s15

Why this exists: a panel pasted onto a screen is the single most-rejected artefact in this
pipeline. Four failure modes were paid for before this tool existed, all of them in how the
corners were measured, none of them in the Remotion component:

  1. A bounding BOX was used. A monitor seen off-axis is a trapezoid, not a rotated rectangle
     (measured: left edge 524px, right edge 375px on the same screen). A box plus rotation
     always overhangs one corner.
  2. Corners were taken as EXTREME points (max x+y and friends). On a tilted screen the point
     with the largest x+y is not the bottom-right corner, and one stray bright pixel moves it
     by tens of pixels. The panel visibly wobbled: 750, 752, 758, 771 over six seconds while
     the camera moved smoothly.
  3. The brightness THRESHOLD was too high (210). The dimmer half of the screen came out full
     of holes, and the right edge was read up to 55px too far left.
  4. Corners were measured at ONE time only, then reused. Cameras drift even when the prompt
     says locked-off (measured: 80 -> 44 px over 8 seconds).

What this does instead, per sampled time:
  - flood fill from a seed INSIDE the screen, so the dark bezel stops the fill and a bright
    whiteboard behind the monitor cannot join in;
  - for each row, take the leftmost and rightmost filled pixel; for each column, the topmost
    and bottommost — four clouds of edge points;
  - fit each cloud to a straight line by least squares, using only the middle 20%-80% of it so
    the corners themselves do not bend the line;
  - intersect the four lines to get four corners;
  - re-seed the next sample from the centre of this quad, so the fill follows the screen;
  - smooth the corner tracks with an EMA (default decay 0.90) because the fill edge jitters by
    a pixel or two per frame while the camera does not.

Output: JSON keyframes ready for `QuadScreenTracked` (templates/remotion/lib/quad-screen.tsx):

    {"clip": "...", "width": 1920, "height": 1080,
     "keys": [{"t": 0.0, "corners": [[x,y],[x,y],[x,y],[x,y]]}, ...]}

Corners are clockwise from top-left, in delivery-resolution pixels.

Verification is not optional. `--qa DIR` writes one JPEG per sample with the quad drawn on the
frame. Look at them. The tool also refuses, with exit code 2, in the two cases where a tracked
panel is the wrong answer to begin with:

  - the screen is narrower than --min-width (default 120px): use a floating card;
  - the fill covers less than 85% of the fitted quad: the threshold is too high, or the surface
    is not one flat plane. Lower --threshold and look at the QA frames before trusting it.

No third-party dependencies: ffmpeg writes grayscale PGM, this reads it.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

Corner = tuple[float, float]


# ---------------------------------------------------------------- frame access
def probe_size(clip: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0:s=x", str(clip)],
        capture_output=True, text=True, check=True).stdout.strip().split("\n")[0]
    w, h = out.split("x")[:2]
    return int(w), int(h)


def probe_duration(clip: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(clip)], capture_output=True, text=True, check=True).stdout.strip()
    return float(out) if out else 0.0


def gray_frame(clip: Path, t: float, tmp: Path) -> tuple[int, int, bytes]:
    """One frame at time t as (width, height, grayscale bytes)."""
    pgm = tmp / f"f-{t:.3f}.pgm"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(clip),
                    "-frames:v", "1", "-pix_fmt", "gray", str(pgm)], check=True)
    data = pgm.read_bytes()
    pos, fields = 0, []
    while len(fields) < 4:                      # P5 <w> <h> <maxval>
        while data[pos:pos + 1].isspace():
            pos += 1
        start = pos
        while not data[pos:pos + 1].isspace():
            pos += 1
        fields.append(data[start:pos])
    pos += 1
    w, h = int(fields[1]), int(fields[2])
    pgm.unlink(missing_ok=True)
    return w, h, data[pos:pos + w * h]


# ---------------------------------------------------------------- geometry
def flood(px: bytes, w: int, h: int, seed: tuple[int, int], threshold: int):
    """4-connected flood fill from seed over pixels >= threshold.

    Returns (rows, cols, count): rows[y] = [xmin, xmax], cols[x] = [ymin, ymax].
    """
    sx, sy = seed
    if not (0 <= sx < w and 0 <= sy < h):
        raise SystemExit(f"seed {seed} is outside the {w}x{h} frame")
    if px[sy * w + sx] < threshold:
        raise SystemExit(
            f"seed {seed} sits on brightness {px[sy * w + sx]}, below --threshold {threshold}. "
            f"Pick a point inside the lit screen, or lower the threshold.")
    seen = bytearray(w * h)
    seen[sy * w + sx] = 1
    q = deque([(sx, sy)])
    rows: dict[int, list[int]] = {}
    cols: dict[int, list[int]] = {}
    count = 0
    while q:
        x, y = q.popleft()
        count += 1
        r = rows.setdefault(y, [x, x]); r[0] = min(r[0], x); r[1] = max(r[1], x)
        c = cols.setdefault(x, [y, y]); c[0] = min(c[0], y); c[1] = max(c[1], y)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and px[ny * w + nx] >= threshold:
                seen[ny * w + nx] = 1
                q.append((nx, ny))
    return rows, cols, count


def fit_line(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Least squares fit of u = a*v + b over (v, u) pairs."""
    n = len(points)
    if n < 2:
        raise SystemExit("not enough edge points to fit a line — is the seed inside the screen?")
    sv = sum(v for v, _ in points)
    su = sum(u for _, u in points)
    svv = sum(v * v for v, _ in points)
    svu = sum(v * u for v, u in points)
    d = n * svv - sv * sv
    if d == 0:
        raise SystemExit("degenerate edge (all points on one line of pixels)")
    a = (n * svu - sv * su) / d
    return a, (su - a * sv) / n


def middle(keys) -> list[int]:
    k = sorted(keys)
    n = len(k)
    if n < 10:
        return k
    return k[int(n * 0.2):int(n * 0.8)]


def intersect(a_x: float, b_x: float, a_y: float, b_y: float) -> Corner:
    """x = a_x*y + b_x crossed with y = a_y*x + b_y."""
    den = 1 - a_x * a_y
    if abs(den) < 1e-9:
        raise SystemExit("screen edges came out parallel — check the QA frame and the threshold")
    x = (a_x * b_y + b_x) / den
    return x, a_y * x + b_y


def quad_area(c: list[Corner]) -> float:
    s = 0.0
    for i in range(4):
        x1, y1 = c[i]
        x2, y2 = c[(i + 1) % 4]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def corners_at(px: bytes, w: int, h: int, seed: tuple[int, int], threshold: int):
    rows, cols, count = flood(px, w, h, seed, threshold)
    ys = middle(rows.keys())
    xs = middle(cols.keys())
    a_left, b_left = fit_line([(y, rows[y][0]) for y in ys])
    a_right, b_right = fit_line([(y, rows[y][1]) for y in ys])
    a_top, b_top = fit_line([(x, cols[x][0]) for x in xs])
    a_bottom, b_bottom = fit_line([(x, cols[x][1]) for x in xs])
    tl = intersect(a_left, b_left, a_top, b_top)
    tr = intersect(a_right, b_right, a_top, b_top)
    br = intersect(a_right, b_right, a_bottom, b_bottom)
    bl = intersect(a_left, b_left, a_bottom, b_bottom)
    return [tl, tr, br, bl], count


# ---------------------------------------------------------------- QA
def qa_frame(clip: Path, t: float, corners: list[Corner], out: Path, size: int = 14) -> None:
    """Write a JPEG of the frame with a box drawn on each fitted corner."""
    out.parent.mkdir(parents=True, exist_ok=True)
    boxes = ",".join(
        f"drawbox=x={int(x) - size // 2}:y={int(y) - size // 2}:w={size}:h={size}"
        f":color={c}@1:t=fill"
        for (x, y), c in zip(corners, ("red", "yellow", "lime", "cyan")))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(clip),
                    "-frames:v", "1", "-vf", boxes, str(out)], check=True)


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("out_json")
    ap.add_argument("--seed", required=True,
                    help="x,y of a point INSIDE the lit screen, in delivery pixels")
    ap.add_argument("--from", dest="t_from", type=float, default=0.0)
    ap.add_argument("--to", dest="t_to", type=float, default=None)
    ap.add_argument("--step", type=float, default=0.5, help="seconds between samples")
    ap.add_argument("--threshold", type=int, default=165,
                    help="brightness 0-255 of screen pixels; lower it if the mask has holes")
    ap.add_argument("--decay", type=float, default=0.90,
                    help="EMA smoothing, 1.0 = no smoothing")
    ap.add_argument("--min-width", type=float, default=120.0,
                    help="below this the answer is a floating card, not a tracked panel")
    ap.add_argument("--min-coverage", type=float, default=0.85,
                    help="filled pixels / fitted quad area")
    ap.add_argument("--qa", help="directory for QA frames with the corners drawn")
    args = ap.parse_args()

    clip = Path(args.clip)
    if not clip.exists():
        return fail(f"no clip {clip}")
    sx, sy = (int(v) for v in args.seed.split(","))
    duration = probe_duration(clip)
    t_to = args.t_to if args.t_to is not None else duration
    # A seek to exactly the duration lands past the last frame and ffmpeg writes nothing.
    t_to = min(t_to, max(0.0, duration - 0.05))
    width, height = probe_size(clip)

    tmp = Path(tempfile.mkdtemp(prefix="track-screen-"))
    seed = (sx, sy)
    keys: list[dict] = []
    smoothed: list[Corner] | None = None
    worst_coverage = 1.0
    narrowest = 1e9

    t = args.t_from
    while t <= t_to + 1e-6:
        w, h, px = gray_frame(clip, t, tmp)
        if (w, h) != (width, height):            # ffmpeg may hand back the coded size
            width, height = w, h
        corners, filled = corners_at(px, w, h, seed, args.threshold)

        area = quad_area(corners)
        coverage = filled / area if area > 0 else 0.0
        worst_coverage = min(worst_coverage, coverage)
        top_w = abs(corners[1][0] - corners[0][0])
        bottom_w = abs(corners[2][0] - corners[3][0])
        narrowest = min(narrowest, top_w, bottom_w)

        if smoothed is None:
            smoothed = corners
        else:
            # EMA: decay is the weight kept from the previous sample. 0.90 was measured as the
            # point where per-pixel jitter stops without the track lagging a pushing camera.
            k = args.decay
            smoothed = [(k * p[0] + (1 - k) * c[0], k * p[1] + (1 - k) * c[1])
                        for p, c in zip(smoothed, corners)]

        keys.append({"t": round(t, 3),
                     "corners": [[round(x, 1), round(y, 1)] for x, y in smoothed],
                     "coverage": round(coverage, 3)})
        print(f"  t={t:5.2f}s  corners="
              f"{[(round(x), round(y)) for x, y in smoothed]}  coverage={coverage:.2f}")

        if args.qa:
            qa_frame(clip, t, smoothed, Path(args.qa) / f"qa-{t:05.2f}.jpg")

        cx = sum(x for x, _ in smoothed) / 4
        cy = sum(y for _, y in smoothed) / 4
        seed = (int(cx), int(cy))
        t += args.step

    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(
        {"clip": clip.name, "width": width, "height": height,
         "threshold": args.threshold, "keys": keys}, indent=2) + "\n")
    print(f"\nwrote {args.out_json}  ({len(keys)} keys)")
    if args.qa:
        print(f"QA frames in {args.qa} — look at them before rendering the overlay")

    if narrowest < args.min_width:
        return fail(f"screen is only {narrowest:.0f}px wide at its narrowest sample "
                    f"(limit {args.min_width:.0f}). Use a floating card, not a tracked panel.")
    if worst_coverage < args.min_coverage:
        return fail(f"fill covers {worst_coverage:.2f} of the fitted quad "
                    f"(limit {args.min_coverage:.2f}). Lower --threshold and re-run; the mask "
                    f"has holes, so at least one edge is being read too far in.")
    return 0


def fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
